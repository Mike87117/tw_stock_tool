from __future__ import annotations

import ast
from contextlib import closing
from dataclasses import fields, replace
from decimal import Decimal
import inspect
from pathlib import Path
import sqlite3
import tempfile
import unittest

from tw_stock_tool.broker_adapters.fubon_neo import (
    FUBON_NEO_TEST_ENDPOINT,
    FUBON_PROVIDER_OBSERVATION_SCHEMA_VERSION,
    FUBON_TEST_D0_BLOCKER_DISPOSITIONS,
    FUBON_TEST_MUTATION_POLICY,
    FubonProviderOrderObservation,
    ProviderOrderMatchState,
    TestMutationReadinessOutcome,
    ValidatedProviderOrderMatch,
    build_fubon_test_execution_authorization,
    build_fubon_test_mutation_envelope,
    commit_fubon_test_pre_submit,
    correlate_fubon_provider_observations,
    current_fubon_neo_test_mutation_readiness,
    derive_fubon_provider_correlation_tag,
    issue_fubon_test_operator_opt_in,
    persist_fubon_test_provider_tag_binding,
    resolve_fubon_lost_ack,
)
from tw_stock_tool.broker_safety import (
    BrokerAccountScope,
    BrokerEnvironment,
    BrokerExecutionAuthorization,
    BrokerSafetySerializationError,
    BrokerTestMutationModelError,
    BrokerTestMutationSerializationError,
    BrokerTestSubmissionRecord,
    PersistenceConflictError,
    SQLiteBrokerSafetyStore,
    SQLiteBrokerTestMutationStore,
    StaleFenceError,
    StoreCorruptionError,
    TEST_MUTATION_SCHEMA_VERSION,
    TEST_PRE_SUBMIT_PERSISTENCE_VERSION,
    TestLimitAuthority,
    TestSubmissionState,
    deserialize_broker_safety_artifact,
    deserialize_test_mutation_artifact,
    serialize_broker_safety_artifact,
    serialize_test_mutation_artifact,
)
from tw_stock_tool.broker_safety.test_mutation_store import (
    _artifact,
    _canonical,
    _digest,
)


ROOT = Path(__file__).resolve().parents[1]


class Phase565D01FubonTestMutationEnvelopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.scope = BrokerAccountScope(
            "FUBON_NEO", BrokerEnvironment.SANDBOX, "sanitized-test-account"
        )
        self.controller = SQLiteBrokerSafetyStore(
            self.root / "phase-c.sqlite3",
            migration_applied_at="2025-01-02T00:00:00Z",
        )
        self.lease = self.controller.acquire_lease(
            self.scope,
            owner_id="test-controller",
            acquired_at="2025-01-02T00:00:00Z",
            expires_at="2025-01-02T01:00:00Z",
        )
        self.database = self.root / "test-lifecycle.sqlite3"
        self.store = SQLiteBrokerTestMutationStore(
            self.database,
            self.controller,
            migration_applied_at="2025-01-02T00:00:00Z",
        )
        self.envelope = self.make_envelope()
        self.opt_in = self.issue_opt_in()
        self.authorization = build_fubon_test_execution_authorization(
            self.envelope,
            self.opt_in,
            authorization_id="30000000-0000-4000-8000-000000000001",
            issued_at="2025-01-02T00:00:03Z",
            expires_at="2025-01-02T00:10:00Z",
        )

    def make_envelope(self, **changes):
        facts = {
            "envelope_id": "20000000-0000-4000-8000-000000000001",
            "economic_intent_id": "1" * 64,
            "idempotency_key": "test-intent-v1:one",
            "canonical_client_order_id": "twst1-" + "a" * 64,
            "account_reference": self.scope.account_reference,
            "trading_date": "2025-01-02",
            "sequence": 1,
            "symbol": "2330",
            "quantity": 1000,
            "limit_price": Decimal("500"),
            "created_at": "2025-01-02T00:00:01Z",
            "expires_at": "2025-01-02T00:10:00Z",
        }
        facts.update(changes)
        return build_fubon_test_mutation_envelope(**facts)

    def issue_opt_in(self):
        return issue_fubon_test_operator_opt_in(
            self.store,
            self.scope,
            self.envelope,
            operator_opt_in_id="25000000-0000-4000-8000-000000000001",
            issued_at="2025-01-02T00:00:02Z",
            expires_at="2025-01-02T00:10:00Z",
            operator_reference="operator-review",
            owner_id=self.lease.owner_id,
            fencing_token=self.lease.fencing_token,
            actor_reference="operator-review",
        )

    def seed_complete_submitting_lifecycle(self) -> None:
        provider_name = "FUBON_NEO_USER_DEF_V1"
        provider_tag = derive_fubon_provider_correlation_tag(
            self.envelope.canonical_client_order_id
        )
        with self.controller._transaction() as connection:
            phase_c_key = self.controller._ensure_scope(connection, self.scope)
            connection.execute(
                "INSERT INTO provider_ids VALUES(?, ?, ?, ?)",
                (phase_c_key, provider_name, provider_tag, self.envelope.canonical_client_order_id),
            )
            phase_c_audit = self.controller._append_audit(
                connection,
                phase_c_key,
                event_type="SANITIZED_TEST_FIXTURE_PROVIDER_REFERENCE",
                occurred_at="2025-01-02T00:00:03Z",
                recorded_at="2025-01-02T00:00:03Z",
                actor_reference="test-fixture",
                references={"envelope_id": self.envelope.envelope_id},
                payload_sha256="9" * 64,
            )
        attempt_id = "40000000-0000-4000-8000-000000000001"
        submission = BrokerTestSubmissionRecord(
            TEST_MUTATION_SCHEMA_VERSION,
            "broker_test_submission",
            self.envelope.envelope_id,
            attempt_id,
            self.envelope.canonical_client_order_id,
            provider_tag,
            TestSubmissionState.SUBMITTING,
            1,
            "2025-01-02T00:00:04Z",
            None,
            "PRE_SIDE_EFFECT_COMMITTED_NO_PROVIDER_CALL",
        )
        authorization_text, authorization_digest = _artifact(self.authorization)
        submission_text, submission_digest = _artifact(submission)
        request_digest = _digest(
            _canonical(
                {
                    "authorization_sha256": authorization_digest,
                    "envelope_sha256": "8" * 64,
                    "persistence_version": TEST_PRE_SUBMIT_PERSISTENCE_VERSION,
                    "provider_name": provider_name,
                    "provider_tag": provider_tag,
                    "submission_sha256": submission_digest,
                }
            )
        )
        with self.store._transaction() as connection:
            key = self.store._ensure_scope(connection, self.scope)
            mapping_sequence, _ = self.store._append_audit(
                connection,
                key,
                event_type="TEST_PROVIDER_TAG_MAPPED",
                occurred_at="2025-01-02T00:00:03Z",
                actor_reference="test-fixture",
                references={"envelope_id": self.envelope.envelope_id, "provider_name": provider_name},
                payload_sha256="7" * 64,
            )
            connection.execute(
                "INSERT INTO phase_c_provider_binding_refs VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (key, provider_name, provider_tag, self.envelope.canonical_client_order_id, self.envelope.envelope_id, self.lease.fencing_token, "2025-01-02T00:00:03Z", phase_c_audit.sequence, phase_c_audit.record_digest, mapping_sequence),
            )
            connection.execute(
                "INSERT INTO authorizations VALUES(?, ?, ?, ?, ?, ?)",
                (key, self.authorization.authorization_id, self.envelope.envelope_id, self.opt_in.operator_opt_in_id, authorization_text, authorization_digest),
            )
            connection.execute(
                "INSERT INTO authorization_uses VALUES(?, ?, ?, ?, ?)",
                (key, self.authorization.authorization_id, self.opt_in.operator_opt_in_id, attempt_id, "2025-01-02T00:00:04Z"),
            )
            connection.execute(
                "INSERT INTO submissions_current VALUES(?, ?, ?, ?, ?, ?, ?)",
                (key, self.envelope.envelope_id, attempt_id, submission.state.value, 1, submission_text, submission_digest),
            )
            connection.execute(
                "INSERT INTO submission_history VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (key, self.envelope.envelope_id, attempt_id, 1, submission.state.value, "ATOMIC_TEST_PRE_SUBMIT", submission_text, submission_digest),
            )
            connection.execute(
                "INSERT INTO high_water VALUES(?, ?, ?, ?)",
                (key, self.envelope.trading_date, self.envelope.sequence, str(self.envelope.order_notional)),
            )
            audit_sequence, audit_root = self.store._append_audit(
                connection,
                key,
                event_type="TEST_PRE_SUBMIT_COMMITTED",
                occurred_at="2025-01-02T00:00:04Z",
                actor_reference="test-fixture",
                references={"authorization_id": self.authorization.authorization_id, "envelope_id": self.envelope.envelope_id},
                payload_sha256=request_digest,
            )
            connection.execute(
                "INSERT INTO pre_submit_commits VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (key, self.authorization.authorization_id, self.opt_in.operator_opt_in_id, self.envelope.envelope_id, attempt_id, TEST_PRE_SUBMIT_PERSISTENCE_VERSION, request_digest, submission_digest, audit_sequence, audit_root, self.lease.fencing_token),
            )

    def test_reviewed_result_is_explicit_blocked_and_preserves_live_requirements(self):
        result = current_fubon_neo_test_mutation_readiness()
        self.assertIs(result.outcome, TestMutationReadinessOutcome.BLOCKED)
        self.assertEqual(result.d0_blocker_dispositions, FUBON_TEST_D0_BLOCKER_DISPOSITIONS)
        self.assertTrue(all(item.live_requirement_preserved for item in result.d0_blocker_dispositions))

    def test_live_a4_contract_and_test_serialization_namespace_are_unchanged(self):
        self.assertEqual(
            tuple(item.name for item in fields(BrokerExecutionAuthorization))[:5],
            ("schema_version", "artifact_type", "authorization_id", "account_reference", "broker_id"),
        )
        self.assertNotIsInstance(self.authorization, BrokerExecutionAuthorization)
        payload = serialize_test_mutation_artifact(self.authorization)
        with self.assertRaises(BrokerSafetySerializationError):
            deserialize_broker_safety_artifact(payload)
        with self.assertRaises(BrokerSafetySerializationError):
            serialize_broker_safety_artifact(self.authorization)
        self.assertEqual(deserialize_test_mutation_artifact(payload), self.authorization)
        with self.assertRaises(BrokerTestMutationSerializationError):
            serialize_test_mutation_artifact(object())

    def test_profile_and_synthetic_limits_remain_maximally_narrow(self):
        self.assertIs(
            FUBON_TEST_MUTATION_POLICY.limit_authority,
            TestLimitAuthority.SYNTHETIC_SANDBOX_HARNESS_ONLY,
        )
        for changes in (
            {"side": self.envelope.side.SELL},
            {"quantity": 1},
            {"lot_mode": "ODD_LOT"},
            {"trade_mode": "MARGIN"},
            {"order_type": self.envelope.order_type.MARKET},
            {"time_in_force": self.envelope.time_in_force.IOC},
        ):
            with self.subTest(changes=changes), self.assertRaises(BrokerTestMutationModelError):
                replace(self.envelope, **changes)

    def test_full_canonical_identity_remains_distinct_from_short_provider_tag(self):
        tag = derive_fubon_provider_correlation_tag(
            self.envelope.canonical_client_order_id
        )
        self.assertRegex(
            self.envelope.canonical_client_order_id, r"twst1-[0-9a-f]{64}\Z"
        )
        self.assertRegex(tag, r"[A-Za-z0-9]{1,10}\Z")
        self.assertNotEqual(tag, self.envelope.canonical_client_order_id)

    def test_operator_opt_in_is_store_issued_exact_expiring_and_nonreplayable(self):
        self.assertEqual(deserialize_test_mutation_artifact(serialize_test_mutation_artifact(self.opt_in)), self.opt_in)
        with self.assertRaises(Exception):
            replace(self.opt_in, environment=BrokerEnvironment.LIVE)
        other = self.make_envelope(
            envelope_id="20000000-0000-4000-8000-000000000002",
            economic_intent_id="2" * 64,
            idempotency_key="test-intent-v1:two",
            canonical_client_order_id="twst1-" + "b" * 64,
            sequence=2,
        )
        with self.assertRaises(BrokerTestMutationModelError):
            build_fubon_test_execution_authorization(
                other,
                self.opt_in,
                authorization_id="30000000-0000-4000-8000-000000000002",
                issued_at="2025-01-02T00:00:03Z",
                expires_at="2025-01-02T00:10:00Z",
            )
        with self.assertRaises(PersistenceConflictError):
            issue_fubon_test_operator_opt_in(
                self.store,
                self.scope,
                self.envelope,
                operator_opt_in_id="25000000-0000-4000-8000-000000000002",
                issued_at="2025-01-02T00:00:02Z",
                expires_at="2025-01-02T00:09:00Z",
                operator_reference="operator-review",
                owner_id=self.lease.owner_id,
                fencing_token=self.lease.fencing_token,
                actor_reference="operator-review",
            )

    def test_phase_c_stale_controller_never_retains_test_authority(self):
        old = self.lease
        self.lease = self.controller.acquire_lease(
            self.scope,
            owner_id="replacement-controller",
            acquired_at="2025-01-02T01:00:00Z",
            expires_at="2025-01-02T02:00:00Z",
        )
        envelope = self.make_envelope(
            envelope_id="20000000-0000-4000-8000-000000000003",
            economic_intent_id="3" * 64,
            idempotency_key="test-intent-v1:three",
            canonical_client_order_id="twst1-" + "c" * 64,
            sequence=3,
            created_at="2025-01-02T01:00:01Z",
            expires_at="2025-01-02T01:10:00Z",
        )
        with self.assertRaises(StaleFenceError):
            issue_fubon_test_operator_opt_in(
                self.store,
                self.scope,
                envelope,
                operator_opt_in_id="25000000-0000-4000-8000-000000000003",
                issued_at="2025-01-02T01:00:02Z",
                expires_at="2025-01-02T01:10:00Z",
                operator_reference="operator-review",
                owner_id=old.owner_id,
                fencing_token=old.fencing_token,
                actor_reference="operator-review",
            )

    def test_phase_c_mapping_is_required_and_sidecar_has_no_mapping_or_lease_authority(self):
        with self.assertRaises(PersistenceConflictError):
            persist_fubon_test_provider_tag_binding(
                self.store,
                self.scope,
                self.envelope,
                owner_id=self.lease.owner_id,
                fencing_token=self.lease.fencing_token,
                now="2025-01-02T00:00:03Z",
                actor_reference="operator-review",
            )
        with closing(sqlite3.connect(self.database)) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn("leases", tables)
        self.assertNotIn("provider_ids", tables)
        self.assertIn("phase_c_provider_binding_refs", tables)

    def test_arbitrary_caller_provider_facts_cannot_yield_matched(self):
        facts = (
            FUBON_PROVIDER_OBSERVATION_SCHEMA_VERSION,
            BrokerEnvironment.SANDBOX,
            FUBON_NEO_TEST_ENDPOINT,
            self.envelope.account_reference,
            self.envelope.trading_date,
            "provider-order-1",
            derive_fubon_provider_correlation_tag(self.envelope.canonical_client_order_id),
            self.envelope.symbol,
            self.envelope.side,
            self.envelope.quantity,
            self.envelope.order_type,
            self.envelope.time_in_force,
            self.envelope.limit_price,
        )
        with self.assertRaises(BrokerTestMutationModelError):
            FubonProviderOrderObservation(*facts, object())
        with self.assertRaises(BrokerTestMutationModelError):
            ValidatedProviderOrderMatch(
                "fubon-provider-order-match-v1",
                ProviderOrderMatchState.MATCHED,
                self.envelope.envelope_id,
                self.envelope.canonical_client_order_id,
                facts[6],
                "provider-order-1",
                "2025-01-02T00:00:05Z",
                object(),
            )
        with self.assertRaises(BrokerTestMutationModelError):
            correlate_fubon_provider_observations(
                self.envelope, object(), ({"forged": True},), observed_at="2025-01-02T00:00:05Z"
            )
        with self.assertRaises(Exception):
            resolve_fubon_lost_ack(ProviderOrderMatchState.MATCHED)

    def test_complete_restart_lifecycle_keeps_submitting_reservation(self):
        self.seed_complete_submitting_lifecycle()
        restarted = SQLiteBrokerTestMutationStore(self.database, self.controller)
        plan = restarted.recovery_plan(self.scope)
        self.assertEqual(plan.active_order_count, 1)
        self.assertEqual(plan.unresolved_submission_count, 1)
        self.assertNotIn("TEST_LIFECYCLE_CORRUPTION", plan.blocking_reasons)
        self.assertTrue(plan.blocks_new_test_submission)

    def test_missing_lifecycle_rows_block_recovery_and_all_new_test_writes(self):
        for table in (
            "submissions_current",
            "submission_history",
            "authorization_uses",
            "pre_submit_commits",
            "phase_c_provider_binding_refs",
        ):
            with self.subTest(table=table):
                self.setUp()
                self.seed_complete_submitting_lifecycle()
                with closing(sqlite3.connect(self.database)) as connection:
                    connection.execute(f"DELETE FROM {table}")
                    connection.commit()
                restarted = SQLiteBrokerTestMutationStore(self.database, self.controller)
                plan = restarted.recovery_plan(self.scope)
                self.assertIn("TEST_LIFECYCLE_CORRUPTION", plan.blocking_reasons)
                if table == "submissions_current":
                    self.assertEqual(plan.unresolved_submission_count, 0)
                with self.assertRaises(StoreCorruptionError):
                    restarted._assert_lifecycle_integrity(self.scope)

    def test_digest_reference_version_and_duplicate_history_corruption_block(self):
        mutations = (
            "UPDATE submission_history SET artifact_sha256='0' || substr(artifact_sha256, 2)",
            "UPDATE pre_submit_commits SET operator_opt_in_id='25000000-0000-4000-8000-000000000099'",
            "UPDATE submission_history SET version=3",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.setUp()
                self.seed_complete_submitting_lifecycle()
                with closing(sqlite3.connect(self.database)) as connection:
                    connection.execute(mutation)
                    connection.commit()
                plan = SQLiteBrokerTestMutationStore(self.database, self.controller).recovery_plan(self.scope)
                self.assertIn("TEST_LIFECYCLE_CORRUPTION", plan.blocking_reasons)

    def test_no_network_sdk_mutation_credentials_or_live_cli_surface(self):
        paths = (
            ROOT / "src/tw_stock_tool/broker_safety/test_mutation_models.py",
            ROOT / "src/tw_stock_tool/broker_safety/test_mutation_serialization.py",
            ROOT / "src/tw_stock_tool/broker_safety/test_mutation_store.py",
            ROOT / "src/tw_stock_tool/broker_adapters/fubon_neo/test_mutation.py",
        )
        forbidden_functions = {"place_order", "cancel_order", "modify_order", "replace_order", "batch_order"}
        forbidden_imports = {"requests", "httpx", "socket", "urllib"}
        for path in paths:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
            defined = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
            imports = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
            self.assertTrue(forbidden_functions.isdisjoint(defined))
            self.assertTrue(forbidden_imports.isdisjoint(imports))
        self.assertNotIn("LIVE", inspect.getsource(commit_fubon_test_pre_submit))


if __name__ == "__main__":
    unittest.main()
