from __future__ import annotations

import ast
from dataclasses import fields, replace
from hashlib import sha256
import gc
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from tests import test_phase_56_5a4_broker_execution_contracts as a4_tests
from tw_stock_tool.broker_safety import (
    A4_SCHEMA_VERSION,
    AuthorizationUseState,
    BrokerAccountScope,
    BrokerEnvironment,
    BrokerExecutionRecord,
    BrokerSubmissionEvidence,
    ClaimDisposition,
    ExternalAuditAnchorReceipt,
    ForensicBrokerSafetyStore,
    LeaseConflictError,
    PersistenceConflictError,
    PreSubmitDisposition,
    RestoreRejectedError,
    SQLiteBrokerSafetyStore,
    StaleFenceError,
    StoreCorruptionError,
    TrustedRecoveryCheckpoint,
    audit_anchor_bundle_sha256,
    canonical_audit_anchor_bundle_bytes,
    export_broker_safety_artifact_json,
    prepare_broker_submission,
    reserve_broker_authorization_use,
    transition_broker_submission,
)
from tw_stock_tool.broker_safety.execution_models import EXECUTION_ARTIFACT_TYPE
from tw_stock_tool.broker_safety.source_models import (
    PROGRESSION_ARTIFACT_TYPE,
    SOURCE_SCHEMA_VERSION,
    ForwardEligibilityDecisionAnchor,
    ForwardEligibilityProgression,
    progression_fingerprint,
)
from tw_stock_tool.forward_paper.eligibility_models import ForwardEligibilityState


HERE = Path(__file__).parent
PROCESS_HELPER = HERE / "phase_56_5c_process_helper.py"


class DurableBrokerStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(gc.collect)
        self.root = Path(self.temporary.name)
        self.database = self.root / "broker-safety.sqlite3"
        self.fx = a4_tests.Phase565A4Tests("test_key_is_exact_stable_and_excludes_runtime_metadata")
        self.fx.setUp()
        self.scope = BrokerAccountScope(
            self.fx.authorization.broker_id,
            self.fx.authorization.environment,
            self.fx.authorization.account_reference,
        )
        self.store = SQLiteBrokerSafetyStore(
            self.database,
            migration_applied_at="2025-01-02T00:00:00Z",
        )
        self.lease = self.store.acquire_lease(
            self.scope,
            owner_id="controller-1",
            acquired_at="2025-01-02T00:00:00Z",
            expires_at="2025-01-02T01:00:00Z",
        )

    def write(self) -> dict[str, object]:
        return {
            "owner_id": self.lease.owner_id,
            "fencing_token": self.lease.fencing_token,
            "now": "2025-01-02T00:00:34Z",
            "actor_reference": "operator-ref",
        }

    def extension(
        self,
        state: ForwardEligibilityState = ForwardEligibilityState.PAUSED,
    ) -> ForwardEligibilityProgression:
        head = self.fx.head
        second = ForwardEligibilityDecisionAnchor(
            a4_tests.IDS[11],
            "a" * 64,
            "2025-01-02T00:00:01Z",
            "2330",
            "b" * 64,
        )
        facts = {
            name: getattr(head, name)
            for name in (
                "lineage_key",
                "run_id",
                "publication_id",
                "publication_index_sha256",
                "qualification_evaluation_id",
                "eligibility_id",
                "eligibility_sha256",
                "metrics_id",
                "metrics_sha256",
                "ledger_id",
                "ledger_sha256",
            )
        }
        facts.update(
            eligibility_state=state,
            decision_count=2,
            last_observed_at=second.observed_at,
            recommendation_anchors=(*head.recommendation_anchors, second),
        )
        return ForwardEligibilityProgression(
            SOURCE_SCHEMA_VERSION,
            PROGRESSION_ARTIFACT_TYPE,
            progression_fingerprint=progression_fingerprint(**facts),
            **facts,
        )

    def reserved(self):
        return reserve_broker_authorization_use(
            self.fx.authorization,
            self.fx.intent,
            authorization_use_id=a4_tests.IDS[10],
            reserved_at="2025-01-02T00:00:32Z",
        )

    def authorized_submission(self, attempt_id: str = a4_tests.IDS[12]):
        prepared = prepare_broker_submission(
            self.fx.intent,
            attempt_id=attempt_id,
            recorded_at="2025-01-02T00:00:32Z",
        )
        return transition_broker_submission(
            prepared,
            self.fx.intent,
            BrokerSubmissionEvidence.AUTHORIZATION_GATE,
            recorded_at="2025-01-02T00:00:33Z",
            **self.gate_facts(),
        )

    def gate_facts(self) -> dict[str, object]:
        facts = self.fx.gate_facts()
        facts["authorization"] = self.fx.authorization
        return facts

    def pre_submit_gate_facts(self) -> dict[str, object]:
        facts = self.gate_facts()
        del facts["authorization"]
        return facts

    def persist_dependencies(self) -> None:
        self.store.persist_authorization(self.scope, self.fx.authorization, **self.write())
        self.store.persist_intent(self.scope, self.fx.intent, **self.write())

    def run_processes(self, mode: str, payloads: tuple[str, str]) -> list[str]:
        processes = [
            subprocess.Popen(
                [sys.executable, str(PROCESS_HELPER), mode, str(self.database), payload],
                cwd=HERE.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            for payload in payloads
        ]
        outputs = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, stderr)
            outputs.append(stdout.strip())
        return outputs

    def test_schema_posture_version_and_transactional_migration(self):
        posture = self.store.sqlite_posture()
        self.assertEqual(posture["foreign_keys"], 1)
        self.assertEqual(str(posture["journal_mode"]).lower(), "wal")
        self.assertEqual(posture["synchronous"], 2)
        self.assertGreater(posture["busy_timeout"], 0)

        failed = self.root / "failed.sqlite3"
        with self.assertRaises(Exception):
            SQLiteBrokerSafetyStore(failed, fail_migration=True)
        recovered = SQLiteBrokerSafetyStore(failed)
        self.assertTrue(recovered.store_id)

        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE metadata SET value='999' WHERE key='schema_version'")
        with self.assertRaises(Exception):
            SQLiteBrokerSafetyStore(self.database)

    def test_two_process_lease_race_and_monotonic_fencing(self):
        database = self.root / "lease-race.sqlite3"
        SQLiteBrokerSafetyStore(database)
        original = self.database
        self.database = database
        outputs = self.run_processes("lease", ("owner-a", "owner-b"))
        self.database = original
        self.assertEqual(sum(item.startswith("ACQUIRED:1") for item in outputs), 1)
        self.assertEqual(outputs.count("CONFLICT"), 1)

        takeover = self.store.acquire_lease(
            self.scope,
            owner_id="controller-2",
            acquired_at="2025-01-02T01:00:00Z",
            expires_at="2025-01-02T02:00:00Z",
        )
        self.assertEqual(takeover.fencing_token, 2)
        with self.assertRaises(StaleFenceError):
            self.store.persist_high_water(
                self.scope,
                self.fx.head,
                **self.write(),
            )

    def test_cross_account_isolation_and_lease_conflict(self):
        other = BrokerAccountScope("BROKER", BrokerEnvironment.SANDBOX, "other-account")
        other_lease = self.store.acquire_lease(
            other,
            owner_id="controller-1",
            acquired_at="2025-01-02T00:00:00Z",
            expires_at="2025-01-02T01:00:00Z",
        )
        self.assertEqual(other_lease.fencing_token, 1)
        with self.assertRaises(LeaseConflictError):
            self.store.acquire_lease(
                self.scope,
                owner_id="other-owner",
                acquired_at="2025-01-02T00:00:01Z",
                expires_at="2025-01-02T00:10:01Z",
            )

    def test_high_water_persists_extension_and_rejects_restart_rollback(self):
        initial = self.store.persist_high_water(self.scope, self.fx.head, **self.write())
        self.assertEqual(
            self.store.persist_high_water(self.scope, self.fx.head, **self.write()),
            initial,
        )
        advanced = self.store.persist_high_water(
            self.scope,
            self.extension(ForwardEligibilityState.REVOKED),
            **self.write(),
        )
        restarted = SQLiteBrokerSafetyStore(self.database)
        self.assertEqual(
            restarted.load_high_water(self.scope, self.fx.head.lineage_key),
            advanced,
        )
        with self.assertRaises(Exception):
            restarted.persist_high_water(self.scope, self.fx.head, **self.write())

        base = self.extension()
        facts = {item.name: getattr(base, item.name) for item in fields(base) if item.name not in ("schema_version", "artifact_type", "progression_fingerprint")}
        facts["recommendation_anchors"] = (
            self.fx.head.recommendation_anchors[0],
            replace(
                base.recommendation_anchors[1],
                decision_sha256="c" * 64,
            ),
        )
        fork = ForwardEligibilityProgression(
            schema_version=SOURCE_SCHEMA_VERSION,
            artifact_type=PROGRESSION_ARTIFACT_TYPE,
            progression_fingerprint=progression_fingerprint(**facts),
            **facts,
        )
        with self.assertRaises(Exception):
            restarted.persist_high_water(self.scope, fork, **self.write())

    def test_authorization_and_intent_are_immutable_and_digest_checked(self):
        with self.assertRaises(PersistenceConflictError):
            self.store.persist_intent(self.scope, self.fx.intent, **self.write())
        self.store.persist_authorization(self.scope, self.fx.authorization, **self.write())
        self.assertEqual(
            self.store.load_authorization(self.scope, self.fx.authorization.authorization_id),
            self.fx.authorization,
        )
        with self.assertRaises(PersistenceConflictError):
            self.store.persist_authorization(
                self.scope,
                replace(self.fx.authorization, approver_identity_ref="other-operator"),
                **self.write(),
            )

        self.store.persist_intent(self.scope, self.fx.intent, **self.write())
        self.assertEqual(
            self.store.load_intent_by_idempotency_key(self.scope, self.fx.intent.idempotency_key),
            self.fx.intent,
        )
        same_key_new_id = replace(self.fx.intent, economic_intent_id=a4_tests.IDS[13])
        with self.assertRaises(PersistenceConflictError):
            self.store.persist_intent(self.scope, same_key_new_id, **self.write())
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "UPDATE intents SET artifact_json='{}' WHERE economic_intent_id=?",
                (self.fx.intent.economic_intent_id,),
            )
        with self.assertRaises(StoreCorruptionError):
            self.store.load_intent_by_idempotency_key(self.scope, self.fx.intent.idempotency_key)

    def test_provider_id_mapping_is_collision_checked_and_full_id_preserved(self):
        self.persist_dependencies()
        value = self.store.map_provider_client_id(
            self.scope,
            provider_name="future-provider",
            provider_client_id="provider-safe-id",
            canonical_client_id=self.fx.intent.canonical_client_order_id,
            owner_id=self.lease.owner_id,
            fencing_token=self.lease.fencing_token,
            now="2025-01-02T00:00:35Z",
            actor_reference="operator-ref",
        )
        self.assertEqual(value, self.fx.intent.canonical_client_order_id)
        with self.assertRaises(PersistenceConflictError):
            self.store.map_provider_client_id(
                self.scope,
                provider_name="future-provider",
                provider_client_id="provider-safe-id",
                canonical_client_id="twst1-" + "f" * 64,
                owner_id=self.lease.owner_id,
                fencing_token=self.lease.fencing_token,
                now="2025-01-02T00:00:35Z",
                actor_reference="operator-ref",
            )

        with self.assertRaises(PersistenceConflictError):
            self.store.map_provider_client_id(
                self.scope,
                provider_name="future-provider",
                provider_client_id="provider-safe-id-2",
                canonical_client_id="twst1-" + "e" * 64,
                owner_id=self.lease.owner_id,
                fencing_token=self.lease.fencing_token,
                now="2025-01-02T00:00:35Z",
                actor_reference="operator-ref",
            )

    def test_two_process_authorization_claim_race_exactly_one_wins(self):
        self.persist_dependencies()
        race_lease = replace(self.lease, owner_id="race-owner")
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "UPDATE leases SET owner_id=? WHERE fencing_token=?",
                (race_lease.owner_id, race_lease.fencing_token),
            )
        payload = self.root / "claim.json"
        payload.write_text(export_broker_safety_artifact_json(self.reserved()), encoding="utf-8")
        outputs = self.run_processes("claim", (str(payload), str(payload)))
        self.assertEqual(outputs.count(ClaimDisposition.ACQUIRED.value), 1)
        self.assertEqual(outputs.count(ClaimDisposition.ALREADY_CLAIMED.value), 1)

    def test_claim_rollback_commit_and_terminal_transitions(self):
        self.persist_dependencies()
        record = self.reserved()
        with self.assertRaises(Exception):
            self.store.claim_authorization_use(
                self.scope,
                record,
                fail_before_commit=True,
                **self.write(),
            )
        acquired = self.store.claim_authorization_use(
            self.scope,
            record,
            **self.write(),
        )
        self.assertIs(acquired.disposition, ClaimDisposition.ACQUIRED)
        consumed = self.store.transition_authorization_use(
            self.scope,
            authorization_id=record.authorization_id,
            target_state=AuthorizationUseState.CONSUMED,
            occurred_at="2025-01-02T00:00:34Z",
            reason=None,
            owner_id=self.lease.owner_id,
            fencing_token=self.lease.fencing_token,
            actor_reference="operator-ref",
        )
        self.assertIs(consumed.state, AuthorizationUseState.CONSUMED)
        with self.assertRaises(Exception):
            self.store.transition_authorization_use(
                self.scope,
                authorization_id=record.authorization_id,
                target_state=AuthorizationUseState.ABANDONED,
                occurred_at="2025-01-02T00:00:35Z",
                reason="not-reusable",
                owner_id=self.lease.owner_id,
                fencing_token=self.lease.fencing_token,
                actor_reference="operator-ref",
            )

    def test_pre_submit_is_atomic_at_every_failure_boundary(self):
        for boundary in (
            "high_water",
            "authorization",
            "intent",
            "authorization_use",
            "submission",
            "audit",
            "commit_record",
        ):
            database = self.root / f"fail-{boundary}.sqlite3"
            store = SQLiteBrokerSafetyStore(database)
            lease = store.acquire_lease(
                self.scope,
                owner_id="controller",
                acquired_at="2025-01-02T00:00:00Z",
                expires_at="2025-01-02T01:00:00Z",
            )
            with self.subTest(boundary=boundary), self.assertRaises(Exception):
                store.commit_pre_submit(
                    self.scope,
                    self.fx.head,
                    self.fx.authorization,
                    self.fx.intent,
                    self.reserved(),
                    self.authorized_submission(),
                    persistence_version="persist-v1",
                    occurred_at="2025-01-02T00:00:34Z",
                    owner_id=lease.owner_id,
                    fencing_token=lease.fencing_token,
                    actor_reference="operator-ref",
                    gate_facts=self.pre_submit_gate_facts(),
                    fail_at=boundary,
                )
            plan = store.recovery_plan(self.scope)
            self.assertEqual(
                (plan.high_water_count, plan.authorization_use_count, plan.intent_count),
                (0, 0, 0),
            )
            self.assertEqual(plan.last_audit_sequence, 0)

    def test_pre_submit_rejects_unbound_progression_without_partial_state(self):
        mismatched = replace(
            self.fx.authorization,
            progression_fingerprint="f" * 64,
        )
        with self.assertRaises(PersistenceConflictError):
            self.store.commit_pre_submit(
                self.scope,
                self.fx.head,
                mismatched,
                self.fx.intent,
                self.reserved(),
                self.authorized_submission(),
                persistence_version="persist-mismatch",
                occurred_at="2025-01-02T00:00:34Z",
                gate_facts=self.pre_submit_gate_facts(),
                **{key: value for key, value in self.write().items() if key != "now"},
            )
        plan = self.store.recovery_plan(self.scope)
        self.assertEqual(
            (
                plan.high_water_count,
                plan.authorization_use_count,
                plan.intent_count,
                plan.last_audit_sequence,
            ),
            (0, 0, 0, 0),
        )

    def test_pre_submit_commit_restart_blocks_new_authorization(self):
        committed = self.store.commit_pre_submit(
            self.scope,
            self.fx.head,
            self.fx.authorization,
            self.fx.intent,
            self.reserved(),
            self.authorized_submission(),
            persistence_version="persist-v1",
            occurred_at="2025-01-02T00:00:34Z",
            owner_id=self.lease.owner_id,
            fencing_token=self.lease.fencing_token,
            actor_reference="operator-ref",
            gate_facts=self.pre_submit_gate_facts(),
        )
        self.assertEqual(committed.fencing_token, 1)
        plan = SQLiteBrokerSafetyStore(self.database).recovery_plan(self.scope)
        self.assertTrue(plan.blocks_new_authorization)
        self.assertIn("UNRESOLVED_SUBMISSION_STATE", plan.blocking_reasons)
        self.assertEqual(plan.nonterminal_submission_count, 1)

    def test_pre_submit_exact_restart_replay_and_different_attempt_conflict(self):
        first = self.store.commit_pre_submit(
            self.scope,
            self.fx.head,
            self.fx.authorization,
            self.fx.intent,
            self.reserved(),
            self.authorized_submission(),
            persistence_version="persist-v1",
            occurred_at="2025-01-02T00:00:34Z",
            gate_facts=self.pre_submit_gate_facts(),
            **{key: value for key, value in self.write().items() if key != "now"},
        )
        restarted = SQLiteBrokerSafetyStore(self.database)
        replay = restarted.commit_pre_submit(
            self.scope,
            self.fx.head,
            self.fx.authorization,
            self.fx.intent,
            self.reserved(),
            self.authorized_submission(),
            persistence_version="persist-v1",
            occurred_at="2025-01-02T00:00:34Z",
            gate_facts=self.pre_submit_gate_facts(),
            **{key: value for key, value in self.write().items() if key != "now"},
        )
        self.assertIs(first.disposition, PreSubmitDisposition.COMMITTED)
        self.assertIs(
            replay.disposition,
            PreSubmitDisposition.ALREADY_COMMITTED,
        )
        self.assertEqual(
            (
                first.authorization_use_id,
                first.intent_id,
                first.attempt_id,
                first.audit_sequence,
                first.audit_root_digest,
            ),
            (
                replay.authorization_use_id,
                replay.intent_id,
                replay.attempt_id,
                replay.audit_sequence,
                replay.audit_root_digest,
            ),
        )
        with self.assertRaises(PersistenceConflictError):
            restarted.commit_pre_submit(
                self.scope,
                self.fx.head,
                self.fx.authorization,
                self.fx.intent,
                self.reserved(),
                self.authorized_submission(a4_tests.IDS[13]),
                persistence_version="persist-v1",
                occurred_at="2025-01-02T00:00:34Z",
                gate_facts=self.pre_submit_gate_facts(),
                **{key: value for key, value in self.write().items() if key != "now"},
            )
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM submissions_current").fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM pre_submit_commits").fetchone()[0],
                1,
            )

    def test_atomic_pre_submit_high_water_is_trusted_on_restore(self):
        self.store.commit_pre_submit(
            self.scope,
            self.fx.head,
            self.fx.authorization,
            self.fx.intent,
            self.reserved(),
            self.authorized_submission(),
            persistence_version="persist-v1",
            occurred_at="2025-01-02T00:00:34Z",
            gate_facts=self.pre_submit_gate_facts(),
            **{key: value for key, value in self.write().items() if key != "now"},
        )
        backup = self.root / "pre-submit-high-water.sqlite3"
        manifest_path = self.root / "pre-submit-high-water.json"
        manifest = self.store.backup(
            backup,
            manifest_path,
            backup_timestamp="2025-01-02T00:00:40Z",
        )
        facts = manifest.scope_audit_checkpoints[0]
        restored = SQLiteBrokerSafetyStore.restore_backup(
            backup,
            manifest_path,
            self.root / "pre-submit-restored.sqlite3",
            active=True,
            checkpoint=TrustedRecoveryCheckpoint(
                self.store.store_id,
                facts.scope_key,
                facts.last_audit_sequence,
                facts.last_audit_root,
                facts.high_water_summary_sha256,
            ),
            restored_at="2025-01-02T00:00:41Z",
        )
        self.assertIsNotNone(
            restored.load_high_water(
                self.scope,
                self.fx.head.lineage_key,
            )
        )

    def test_two_process_pre_submit_same_and_different_attempt_races(self):
        for variants, expected in (
            (
                ("same", "same"),
                {
                    PreSubmitDisposition.COMMITTED.value,
                    PreSubmitDisposition.ALREADY_COMMITTED.value,
                },
            ),
            (
                ("same", "different"),
                {
                    PreSubmitDisposition.COMMITTED.value,
                    "CONFLICT",
                },
            ),
        ):
            with self.subTest(variants=variants):
                database = self.root / ("pre-submit-" + "-".join(variants) + ".sqlite3")
                store = SQLiteBrokerSafetyStore(database)
                store.acquire_lease(
                    self.scope,
                    owner_id="race-owner",
                    acquired_at="2025-01-02T00:00:00Z",
                    expires_at="2025-01-02T01:00:00Z",
                )
                original = self.database
                self.database = database
                outputs = self.run_processes("pre-submit", variants)
                self.database = original
                self.assertEqual(set(outputs), expected)
                with sqlite3.connect(database) as connection:
                    self.assertEqual(
                        connection.execute("SELECT COUNT(*) FROM pre_submit_commits").fetchone()[0],
                        1,
                    )
                    self.assertEqual(
                        connection.execute("SELECT COUNT(*) FROM submissions_current").fetchone()[0],
                        1,
                    )

    def test_submission_cas_unknown_state_and_history_survive_restart(self):
        self.store.commit_pre_submit(
            self.scope,
            self.fx.head,
            self.fx.authorization,
            self.fx.intent,
            self.reserved(),
            self.authorized_submission(),
            persistence_version="persist-v1",
            occurred_at="2025-01-02T00:00:34Z",
            gate_facts=self.pre_submit_gate_facts(),
            **{key: value for key, value in self.write().items() if key != "now"},
        )
        with self.assertRaises(PersistenceConflictError):
            self.store.transition_submission(
                self.scope,
                intent_id=self.fx.intent.economic_intent_id,
                attempt_id=a4_tests.IDS[12],
                expected_version=2,
                evidence=BrokerSubmissionEvidence.AMBIGUOUS_OUTCOME,
                recorded_at="2025-01-02T00:00:35Z",
                owner_id=self.lease.owner_id,
                fencing_token=self.lease.fencing_token,
                actor_reference="operator-ref",
            )
        unknown, version = self.store.transition_submission(
            self.scope,
            intent_id=self.fx.intent.economic_intent_id,
            attempt_id=a4_tests.IDS[12],
            expected_version=1,
            evidence=BrokerSubmissionEvidence.AMBIGUOUS_OUTCOME,
            recorded_at="2025-01-02T00:00:35Z",
            owner_id=self.lease.owner_id,
            fencing_token=self.lease.fencing_token,
            actor_reference="operator-ref",
        )
        self.assertEqual(
            (unknown.state.value, version),
            ("UNKNOWN_SUBMISSION_STATE", 2),
        )
        plan = SQLiteBrokerSafetyStore(self.database).recovery_plan(self.scope)
        self.assertIn(
            "UNRESOLVED_SUBMISSION_STATE",
            plan.blocking_reasons,
        )

    def test_direct_submission_persistence_surface_is_absent(self):
        self.assertFalse(hasattr(SQLiteBrokerSafetyStore, "persist_submission"))
        self.persist_dependencies()
        prepared = prepare_broker_submission(
            self.fx.intent,
            attempt_id=a4_tests.IDS[12],
            recorded_at="2025-01-02T00:00:32Z",
        )
        with self.assertRaises(PersistenceConflictError):
            self.store.transition_submission(
                self.scope,
                intent_id=prepared.intent_id,
                attempt_id=prepared.attempt_id,
                expected_version=1,
                evidence=BrokerSubmissionEvidence.AMBIGUOUS_OUTCOME,
                recorded_at="2025-01-02T00:00:33Z",
                owner_id=self.lease.owner_id,
                fencing_token=self.lease.fencing_token,
                actor_reference="operator-ref",
            )
        prepared_text = export_broker_safety_artifact_json(prepared)
        prepared_digest = sha256(prepared_text.encode()).hexdigest()
        with sqlite3.connect(self.database) as connection:
            scope_key = connection.execute("SELECT scope_key FROM account_scopes").fetchone()[0]
            connection.execute(
                "INSERT INTO submissions_current VALUES(?, ?, ?, ?, 1, ?, ?)",
                (
                    scope_key,
                    prepared.intent_id,
                    prepared.attempt_id,
                    prepared.state.value,
                    prepared_text,
                    prepared_digest,
                ),
            )
            connection.execute(
                "INSERT INTO submission_history VALUES(?, ?, ?, 1, ?, ?, ?, ?)",
                (
                    scope_key,
                    prepared.intent_id,
                    prepared.attempt_id,
                    prepared.state.value,
                    "INITIAL_PREPARED",
                    prepared_text,
                    prepared_digest,
                ),
            )
        corrupted = SQLiteBrokerSafetyStore(self.database).recovery_plan(self.scope)
        self.assertIn(
            "STORE_OR_AUDIT_CORRUPTION",
            corrupted.blocking_reasons,
        )

    def test_same_owner_expiry_advances_fence_and_renewal_is_monotonic(self):
        renewed = self.store.renew_lease(
            self.lease,
            renewed_at="2025-01-02T00:30:00Z",
            expires_at="2025-01-02T01:00:00Z",
        )
        with self.assertRaises(StaleFenceError):
            self.store.renew_lease(
                renewed,
                renewed_at="2025-01-02T00:20:00Z",
                expires_at="2025-01-02T00:50:00Z",
            )
        takeover = self.store.acquire_lease(
            self.scope,
            owner_id=self.lease.owner_id,
            acquired_at="2025-01-02T01:00:00Z",
            expires_at="2025-01-02T02:00:00Z",
        )
        self.assertEqual(takeover.fencing_token, 2)
        with self.assertRaises(StaleFenceError):
            self.store.persist_high_water(
                self.scope,
                self.fx.head,
                owner_id=self.lease.owner_id,
                fencing_token=True,
                now="2025-01-02T01:00:01Z",
                actor_reference="operator-ref",
            )

    def test_public_durable_evidence_rejects_loose_types_and_digests(self):
        with self.assertRaises(Exception):
            replace(self.lease, fencing_token=True)
        with self.assertRaises(Exception):
            TrustedRecoveryCheckpoint(
                self.store.store_id,
                "scope-key",
                0,
                "0" * 64,
                "0" * 64,
            )
        with self.assertRaises(Exception):
            ExternalAuditAnchorReceipt(
                "external_audit_anchor_receipt_v1",
                "receipt-1",
                "NOT-A-DIGEST",
                "DETERMINISTIC_FAKE_WORM",
                "fake/object/1",
                "2025-01-02T00:00:40Z",
            )

    def test_restart_recovery_rejects_broken_references_and_history(self):
        for corruption in ("authorization", "history"):
            with self.subTest(corruption=corruption):
                database = self.root / f"recovery-{corruption}.sqlite3"
                store = SQLiteBrokerSafetyStore(database)
                lease = store.acquire_lease(
                    self.scope,
                    owner_id="recovery-controller",
                    acquired_at="2025-01-02T00:00:00Z",
                    expires_at="2025-01-02T01:00:00Z",
                )
                store.commit_pre_submit(
                    self.scope,
                    self.fx.head,
                    self.fx.authorization,
                    self.fx.intent,
                    self.reserved(),
                    self.authorized_submission(),
                    persistence_version=f"persist-{corruption}",
                    occurred_at="2025-01-02T00:00:34Z",
                    owner_id=lease.owner_id,
                    fencing_token=lease.fencing_token,
                    actor_reference="operator-ref",
                    gate_facts=self.pre_submit_gate_facts(),
                )
                with sqlite3.connect(database) as connection:
                    if corruption == "authorization":
                        connection.execute("DELETE FROM authorizations")
                    else:
                        connection.execute("DELETE FROM submission_history")
                plan = store.recovery_plan(self.scope)
                self.assertTrue(plan.blocks_new_authorization)
                self.assertIn(
                    "STORE_OR_AUDIT_CORRUPTION",
                    plan.blocking_reasons,
                )

    def test_operator_recovery_runbook_is_fail_closed_and_non_mutating(self):
        text = (HERE.parent / "docs" / "PHASE_56_5C_OPERATOR_RECOVERY_RUNBOOK.md").read_text(encoding="utf-8")
        for required in (
            "blocks_new_authorization",
            "trusted checkpoint",
            "forensic restore",
            "Never edit or reset",
            "no broker submit",
            "does not grant permission to trade",
        ):
            self.assertIn(required, text)

    def test_execution_dedupe_conflict_and_submission_history(self):
        self.store.commit_pre_submit(
            self.scope,
            self.fx.head,
            self.fx.authorization,
            self.fx.intent,
            self.reserved(),
            self.authorized_submission(),
            persistence_version="persist-v1",
            occurred_at="2025-01-02T00:00:34Z",
            gate_facts=self.pre_submit_gate_facts(),
            **{key: value for key, value in self.write().items() if key != "now"},
        )
        acknowledged, version = self.store.transition_submission(
            self.scope,
            intent_id=self.fx.intent.economic_intent_id,
            attempt_id=a4_tests.IDS[12],
            expected_version=1,
            evidence=BrokerSubmissionEvidence.BROKER_ACK,
            recorded_at="2025-01-02T00:00:35Z",
            owner_id=self.lease.owner_id,
            fencing_token=self.lease.fencing_token,
            actor_reference="operator-ref",
            transition_facts={"broker_order_id": "broker-order-1"},
        )
        self.assertEqual(version, 2)
        self.assertEqual(acknowledged.state.value, "ACKNOWLEDGED")
        execution = BrokerExecutionRecord(
            A4_SCHEMA_VERSION,
            EXECUTION_ARTIFACT_TYPE,
            "broker-order-1",
            "execution-1",
            self.fx.intent.economic_intent_id,
            a4_tests.IDS[12],
            self.fx.intent.quantity,
            self.fx.intent.limit_price,
            "2025-01-02T00:00:36Z",
            None,
            None,
            self.fx.intent.quantity,
            "2025-01-02T00:00:37Z",
        )
        filled, version = self.store.record_execution(
            self.scope,
            self.fx.intent,
            execution,
            expected_submission_version=2,
            owner_id=self.lease.owner_id,
            fencing_token=self.lease.fencing_token,
            actor_reference="operator-ref",
        )
        self.assertEqual((filled.state.value, version), ("FILLED", 3))
        replay, replay_version = self.store.record_execution(
            self.scope,
            self.fx.intent,
            execution,
            expected_submission_version=2,
            owner_id=self.lease.owner_id,
            fencing_token=self.lease.fencing_token,
            actor_reference="operator-ref",
        )
        self.assertEqual((replay, replay_version), (filled, 3))
        with self.assertRaises(PersistenceConflictError):
            self.store.record_execution(
                self.scope,
                self.fx.intent,
                replace(execution, received_at="2025-01-02T00:00:38Z"),
                expected_submission_version=3,
                owner_id=self.lease.owner_id,
                fencing_token=self.lease.fencing_token,
                actor_reference="operator-ref",
            )
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM submission_history").fetchone()[0],
                3,
            )
        plan = self.store.recovery_plan(self.scope)
        self.assertEqual(plan.nonterminal_submission_count, 0)
        self.assertFalse(plan.blocks_new_authorization)

        fake_filled = replace(
            filled,
            execution_ids=("fabricated-execution",),
        )
        fake_text = export_broker_safety_artifact_json(fake_filled)
        fake_digest = sha256(fake_text.encode()).hexdigest()
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "UPDATE submissions_current SET artifact_json=?, artifact_sha256=? WHERE intent_id=? AND attempt_id=?",
                (
                    fake_text,
                    fake_digest,
                    filled.intent_id,
                    filled.attempt_id,
                ),
            )
            connection.execute(
                "UPDATE submission_history SET artifact_json=?, artifact_sha256=? WHERE intent_id=? AND attempt_id=? AND version=3",
                (
                    fake_text,
                    fake_digest,
                    filled.intent_id,
                    filled.attempt_id,
                ),
            )
        corrupted = SQLiteBrokerSafetyStore(self.database).recovery_plan(self.scope)
        self.assertIn(
            "STORE_OR_AUDIT_CORRUPTION",
            corrupted.blocking_reasons,
        )

    def test_audit_chain_detects_deletion_and_reordering(self):
        for corruption in ("delete", "reorder"):
            with self.subTest(corruption=corruption):
                database = self.root / f"audit-{corruption}.sqlite3"
                store = SQLiteBrokerSafetyStore(database)
                lease = store.acquire_lease(
                    self.scope,
                    owner_id="audit-controller",
                    acquired_at="2025-01-02T00:00:00Z",
                    expires_at="2025-01-02T01:00:00Z",
                )
                write = {
                    "owner_id": lease.owner_id,
                    "fencing_token": lease.fencing_token,
                    "now": "2025-01-02T00:00:34Z",
                    "actor_reference": "operator-ref",
                }
                store.persist_high_water(self.scope, self.fx.head, **write)
                store.persist_authorization(
                    self.scope,
                    self.fx.authorization,
                    **write,
                )
                with sqlite3.connect(database) as connection:
                    if corruption == "delete":
                        connection.execute("DELETE FROM audit WHERE sequence=1")
                    else:
                        connection.execute("UPDATE audit SET sequence=sequence+100")
                        connection.execute("UPDATE audit SET sequence=CASE sequence WHEN 101 THEN 2 ELSE 1 END")
                with self.assertRaises(StoreCorruptionError):
                    store.verify_audit_chain(self.scope)

    def test_audit_chain_detects_modified_deleted_and_reordered_rows(self):
        self.store.persist_high_water(self.scope, self.fx.head, **self.write())
        self.store.persist_authorization(self.scope, self.fx.authorization, **self.write())
        sequence, root = self.store.verify_audit_chain(self.scope)
        self.assertEqual(sequence, 2)
        self.assertEqual(len(root), 64)
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE audit SET event_type='MODIFIED' WHERE sequence=2")
        with self.assertRaises(StoreCorruptionError):
            self.store.verify_audit_chain(self.scope)

    def test_audit_rejects_secret_or_raw_payload_fields(self):
        with self.assertRaises(Exception):
            self.store.persist_high_water(
                self.scope,
                self.fx.head,
                owner_id=self.lease.owner_id,
                fencing_token=self.lease.fencing_token,
                now="2025-01-02T00:00:10Z",
                actor_reference="api-key-secret",
            )

    def test_anchor_bundle_is_deterministic_and_receipt_is_correlated(self):
        self.store.persist_high_water(self.scope, self.fx.head, **self.write())
        first = self.store.build_anchor_bundle(self.scope, created_at="2025-01-02T00:00:40Z")
        second = self.store.build_anchor_bundle(self.scope, created_at="2025-01-02T00:00:40Z")
        self.assertEqual(canonical_audit_anchor_bundle_bytes(first), canonical_audit_anchor_bundle_bytes(second))
        digest = audit_anchor_bundle_sha256(first)
        self.assertEqual(digest, sha256(canonical_audit_anchor_bundle_bytes(first)).hexdigest())
        live_receipt = ExternalAuditAnchorReceipt(
            "external_audit_anchor_receipt_v1",
            "caller-live-receipt",
            digest,
            "AMAZON_S3_OBJECT_LOCK_COMPLIANCE",
            "caller/asserted/object",
            "2025-01-02T00:00:41Z",
        )
        with self.assertRaises(PersistenceConflictError):
            self.store.record_anchor_receipt(
                self.scope,
                first,
                live_receipt,
                owner_id=self.lease.owner_id,
                fencing_token=self.lease.fencing_token,
                actor_reference="caller",
            )
        unanchored = SQLiteBrokerSafetyStore(self.database).recovery_plan(self.scope)
        self.assertIsNone(unanchored.last_external_anchor_target)

        receipt = ExternalAuditAnchorReceipt(
            "external_audit_anchor_receipt_v1",
            "receipt-1",
            digest,
            "DETERMINISTIC_FAKE_WORM",
            "fake/object/1",
            "2025-01-02T00:00:41Z",
        )
        self.store.record_anchor_receipt(
            self.scope,
            first,
            receipt,
            owner_id=self.lease.owner_id,
            fencing_token=self.lease.fencing_token,
            actor_reference="anchor-worker",
        )
        recovered = SQLiteBrokerSafetyStore(self.database).recovery_plan(self.scope)
        self.assertEqual(
            (
                recovered.last_external_receipt_reference,
                recovered.last_external_anchor_sequence,
                recovered.last_external_anchor_root,
                recovered.last_external_anchor_target,
            ),
            (
                "receipt-1",
                first.last_audit_sequence,
                first.audit_root_digest,
                "DETERMINISTIC_FAKE_WORM",
            ),
        )
        anchored_sequence = self.store.verify_audit_chain(self.scope)[0]
        self.store.record_anchor_receipt(
            self.scope,
            first,
            receipt,
            owner_id=self.lease.owner_id,
            fencing_token=self.lease.fencing_token,
            actor_reference="anchor-worker",
        )
        self.assertEqual(self.store.verify_audit_chain(self.scope)[0], anchored_sequence)

    def test_backup_restore_round_trip_corruption_and_anti_rollback(self):
        self.store.persist_high_water(self.scope, self.fx.head, **self.write())
        backup = self.root / "backup.sqlite3"
        manifest = self.root / "backup.json"
        result = self.store.backup(
            backup,
            manifest,
            backup_timestamp="2025-01-02T00:00:45Z",
        )
        verified = SQLiteBrokerSafetyStore.verify_backup(backup, manifest)
        self.assertEqual(verified, result)
        checkpoint_facts = result.scope_audit_checkpoints[0]
        forensic = SQLiteBrokerSafetyStore.restore_backup(
            backup,
            manifest,
            self.root / "forensic.sqlite3",
            active=False,
            restored_at="2025-01-02T00:00:46Z",
        )
        self.assertIs(type(forensic), ForensicBrokerSafetyStore)
        with forensic.connect() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM high_water").fetchone()[0],
                1,
            )
        with self.assertRaises(RestoreRejectedError):
            SQLiteBrokerSafetyStore.restore_backup(
                backup,
                manifest,
                self.root / "no-proof.sqlite3",
                active=True,
                restored_at="2025-01-02T00:00:46Z",
            )
        stale_checkpoint = TrustedRecoveryCheckpoint(
            self.store.store_id,
            checkpoint_facts.scope_key,
            checkpoint_facts.last_audit_sequence + 1,
            "f" * 64,
            checkpoint_facts.high_water_summary_sha256,
        )
        with self.assertRaises(RestoreRejectedError):
            SQLiteBrokerSafetyStore.restore_backup(
                backup,
                manifest,
                self.root / "rolled-back.sqlite3",
                active=True,
                checkpoint=stale_checkpoint,
                restored_at="2025-01-02T00:00:46Z",
            )
        checkpoint = TrustedRecoveryCheckpoint(
            self.store.store_id,
            checkpoint_facts.scope_key,
            checkpoint_facts.last_audit_sequence,
            checkpoint_facts.last_audit_root,
            checkpoint_facts.high_water_summary_sha256,
        )
        active = SQLiteBrokerSafetyStore.restore_backup(
            backup,
            manifest,
            self.root / "active.sqlite3",
            active=True,
            checkpoint=checkpoint,
            restored_at="2025-01-02T00:00:46Z",
        )
        self.assertIs(type(active), SQLiteBrokerSafetyStore)
        with self.assertRaises(StaleFenceError):
            active.persist_high_water(
                self.scope,
                self.fx.head,
                owner_id=self.lease.owner_id,
                fencing_token=self.lease.fencing_token,
                now="2025-01-02T00:00:47Z",
                actor_reference="operator-ref",
            )
        reacquired = active.acquire_lease(
            self.scope,
            owner_id=self.lease.owner_id,
            acquired_at="2025-01-02T00:00:46Z",
            expires_at="2025-01-02T00:01:00Z",
        )
        self.assertGreater(
            reacquired.fencing_token,
            self.lease.fencing_token,
        )
        with self.assertRaises(LeaseConflictError):
            active.acquire_lease(
                self.scope,
                owner_id="replacement-owner",
                acquired_at="2025-01-02T00:00:47Z",
                expires_at="2025-01-02T00:01:01Z",
            )
        replacement = active.acquire_lease(
            self.scope,
            owner_id="replacement-owner",
            acquired_at="2025-01-02T00:01:00Z",
            expires_at="2025-01-02T00:02:00Z",
        )
        self.assertGreater(
            replacement.fencing_token,
            reacquired.fencing_token,
        )

        corrupted = self.root / "corrupt.sqlite3"
        corrupted.write_bytes(backup.read_bytes() + b"corrupt")
        with self.assertRaises(RestoreRejectedError):
            SQLiteBrokerSafetyStore.verify_backup(corrupted, manifest)

    def test_multi_account_restore_requires_every_scope_checkpoint(self):
        other = BrokerAccountScope(
            self.scope.broker_id,
            self.scope.environment,
            "other-account",
        )
        other_lease = self.store.acquire_lease(
            other,
            owner_id="other-controller",
            acquired_at="2025-01-02T00:00:00Z",
            expires_at="2025-01-02T01:00:00Z",
        )
        self.store.persist_high_water(self.scope, self.fx.head, **self.write())
        self.store.persist_high_water(
            other,
            self.fx.head,
            owner_id=other_lease.owner_id,
            fencing_token=other_lease.fencing_token,
            now="2025-01-02T00:00:34Z",
            actor_reference="operator-ref",
        )
        backup = self.root / "multi.sqlite3"
        manifest_path = self.root / "multi.json"
        manifest = self.store.backup(
            backup,
            manifest_path,
            backup_timestamp="2025-01-02T00:00:45Z",
        )
        self.assertEqual(len(manifest.scope_audit_checkpoints), 2)
        checkpoints = tuple(
            TrustedRecoveryCheckpoint(
                self.store.store_id,
                item.scope_key,
                item.last_audit_sequence,
                item.last_audit_root,
                item.high_water_summary_sha256,
            )
            for item in manifest.scope_audit_checkpoints
        )
        with self.assertRaises(RestoreRejectedError):
            SQLiteBrokerSafetyStore.restore_backup(
                backup,
                manifest_path,
                self.root / "missing-account-proof.sqlite3",
                active=True,
                checkpoint=checkpoints[:1],
                restored_at="2025-01-02T00:00:46Z",
            )
        stale = (
            checkpoints[0],
            replace(
                checkpoints[1],
                minimum_audit_sequence=(checkpoints[1].minimum_audit_sequence + 1),
                audit_root_digest="f" * 64,
            ),
        )
        with self.assertRaises(RestoreRejectedError):
            SQLiteBrokerSafetyStore.restore_backup(
                backup,
                manifest_path,
                self.root / "account-rollback.sqlite3",
                active=True,
                checkpoint=stale,
                restored_at="2025-01-02T00:00:46Z",
            )
        restored = SQLiteBrokerSafetyStore.restore_backup(
            backup,
            manifest_path,
            self.root / "multi-active.sqlite3",
            active=True,
            checkpoint=checkpoints,
            restored_at="2025-01-02T00:00:46Z",
        )
        self.assertIs(type(restored), SQLiteBrokerSafetyStore)

    def test_trusted_checkpoint_rejects_coherent_high_water_rollback(self):
        self.store.persist_high_water(
            self.scope,
            self.fx.head,
            **self.write(),
        )
        with sqlite3.connect(self.database) as connection:
            old_row = connection.execute("SELECT lineage_key, artifact_json, artifact_sha256 FROM high_water").fetchone()
        self.store.persist_high_water(
            self.scope,
            self.extension(ForwardEligibilityState.PAUSED),
            **self.write(),
        )
        backup = self.root / "coherent-rollback.sqlite3"
        manifest_path = self.root / "coherent-rollback.json"
        manifest = self.store.backup(
            backup,
            manifest_path,
            backup_timestamp="2025-01-02T00:00:45Z",
        )
        trusted_facts = manifest.scope_audit_checkpoints[0]
        trusted = TrustedRecoveryCheckpoint(
            self.store.store_id,
            trusted_facts.scope_key,
            trusted_facts.last_audit_sequence,
            trusted_facts.last_audit_root,
            trusted_facts.high_water_summary_sha256,
        )

        with sqlite3.connect(backup) as connection:
            connection.execute(
                "UPDATE high_water SET artifact_json=?, artifact_sha256=? WHERE lineage_key=?",
                (old_row[1], old_row[2], old_row[0]),
            )
            per_scope_rows = connection.execute(
                "SELECT lineage_key, artifact_sha256 FROM high_water WHERE scope_key=? ORDER BY lineage_key",
                (trusted.scope_key,),
            ).fetchall()
            global_rows = connection.execute("SELECT scope_key, lineage_key, artifact_sha256 FROM high_water ORDER BY scope_key, lineage_key").fetchall()

        canonical = lambda rows: json.dumps(
            [list(row) for row in rows],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        rolled_back_summary = sha256(canonical(per_scope_rows)).hexdigest()
        data["scope_audit_checkpoints"][0]["high_water_summary_sha256"] = rolled_back_summary
        data["high_water_summary_sha256"] = sha256(canonical(global_rows)).hexdigest()
        data["database_sha256"] = sha256(backup.read_bytes()).hexdigest()
        manifest_path.write_bytes(
            (
                json.dumps(
                    data,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                + "\n"
            ).encode()
        )
        SQLiteBrokerSafetyStore.verify_backup(backup, manifest_path)
        with self.assertRaises(RestoreRejectedError):
            SQLiteBrokerSafetyStore.restore_backup(
                backup,
                manifest_path,
                self.root / "coherent-active.sqlite3",
                active=True,
                checkpoint=trusted,
                restored_at="2025-01-02T00:00:46Z",
            )

    def test_backup_verification_rejects_logically_corrupt_artifact(self):
        self.store.persist_high_water(self.scope, self.fx.head, **self.write())
        backup = self.root / "logical.sqlite3"
        manifest_path = self.root / "logical.json"
        self.store.backup(
            backup,
            manifest_path,
            backup_timestamp="2025-01-02T00:00:45Z",
        )
        with sqlite3.connect(backup) as connection:
            connection.execute("UPDATE high_water SET artifact_json='{}'")
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        data["database_sha256"] = sha256(backup.read_bytes()).hexdigest()
        manifest_path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(RestoreRejectedError):
            SQLiteBrokerSafetyStore.verify_backup(backup, manifest_path)

    def test_abrupt_subprocess_exit_rolls_back_open_transaction(self):
        process = subprocess.run(
            [sys.executable, str(PROCESS_HELPER), "abrupt", str(self.database), "unused"],
            cwd=HERE.parent,
            check=False,
        )
        self.assertEqual(process.returncode, 7)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM backup_history WHERE backup_sha256=?",
                    ("f" * 64,),
                ).fetchone()[0],
                0,
            )

    def test_no_broker_mutation_network_secret_or_binary_surface(self):
        package = HERE.parent / "src" / "tw_stock_tool" / "broker_safety"
        forbidden_imports = ("requests", "httpx", "urllib", "socket", "boto3", "fubon_neo")
        forbidden_calls = {
            "place_order",
            "submit_order",
            "cancel_order",
            "modify_order",
            "replace_order",
            "urlopen",
        }
        for path in (package / "durable_models.py", package / "durable_store.py"):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse(any(alias.name.startswith(forbidden_imports) for alias in node.names))
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or "").startswith(forbidden_imports))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, forbidden_calls)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.assertNotIn(node.name, forbidden_calls)
        root = HERE.parent
        self.assertFalse(any(path.suffix.lower() in {".whl", ".pfx", ".p12", ".pem"} for path in root.rglob("*") if ".git" not in path.parts))


if __name__ == "__main__":
    unittest.main()
