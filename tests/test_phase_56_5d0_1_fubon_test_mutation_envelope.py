from __future__ import annotations

import ast
from dataclasses import fields, replace
from decimal import Decimal
import inspect
from pathlib import Path
import sqlite3
import tempfile
import unittest

from tw_stock_tool.broker_adapters.fubon_neo import (
    FUBON_NEO_TEST_ENDPOINT,
    FUBON_PROVIDER_NAME,
    FUBON_PROVIDER_OBSERVATION_SCHEMA_VERSION,
    FUBON_TEST_D0_BLOCKER_DISPOSITIONS,
    FUBON_TEST_MUTATION_POLICY,
    D0BlockerTestClassification,
    FubonProviderOrderObservation,
    LostAckDisposition,
    ProviderOrderMatchState,
    TestMutationReadinessOutcome,
    ValidatedProviderOrderMatch,
    apply_fubon_test_lost_ack,
    build_fubon_test_execution_authorization,
    build_fubon_test_mutation_envelope,
    commit_fubon_test_pre_submit,
    correlate_fubon_provider_observations,
    current_fubon_neo_test_mutation_readiness,
    derive_fubon_provider_correlation_tag,
    persist_fubon_test_provider_tag_binding,
    resolve_fubon_lost_ack,
    resolve_validated_fubon_lost_ack,
)
from tw_stock_tool.broker_safety import (
    BrokerAccountScope,
    BrokerEnvironment,
    BrokerExecutionAuthorization,
    BrokerSafetySerializationError,
    BrokerTestMutationModelError,
    BrokerTestMutationSerializationError,
    DurableTestProviderTagBinding,
    PersistenceConflictError,
    SQLiteBrokerTestMutationStore,
    StaleFenceError,
    TEST_MUTATION_SCHEMA_VERSION,
    TestLimitAuthority,
    deserialize_broker_safety_artifact,
    deserialize_test_mutation_artifact,
    export_test_mutation_artifact_json,
    serialize_broker_safety_artifact,
    serialize_test_mutation_artifact,
)
from tw_stock_tool.broker_safety.d0_readiness import D0PrerequisiteName


ROOT = Path(__file__).resolve().parents[1]


class Phase565D01FubonTestMutationEnvelopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.database = Path(self.temporary.name) / "test-mutation.sqlite3"
        self.store = SQLiteBrokerTestMutationStore(
            self.database, migration_applied_at="2025-01-02T00:00:00Z"
        )
        self.scope = BrokerAccountScope(
            "FUBON_NEO", BrokerEnvironment.SANDBOX, "sanitized-test-account"
        )
        self.lease = self.store.acquire_lease(
            self.scope,
            owner_id="test-controller",
            acquired_at="2025-01-02T00:00:00Z",
            expires_at="2025-01-02T01:00:00Z",
        )
        self.envelope = self.make_envelope()
        self.authorization = build_fubon_test_execution_authorization(
            self.envelope,
            authorization_id="30000000-0000-4000-8000-000000000001",
            issued_at="2025-01-02T00:00:02Z",
            expires_at="2025-01-02T00:10:00Z",
            approver_reference="operator-review",
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
            "operator_opt_in_reference": "operator-opt-in-one",
            "created_at": "2025-01-02T00:00:01Z",
            "expires_at": "2025-01-02T00:10:00Z",
        }
        facts.update(changes)
        return build_fubon_test_mutation_envelope(**facts)

    def write(self, now="2025-01-02T00:00:03Z"):
        return {
            "owner_id": self.lease.owner_id,
            "fencing_token": self.lease.fencing_token,
            "now": now,
            "actor_reference": "operator-review",
        }

    def bind(self):
        return persist_fubon_test_provider_tag_binding(
            self.store,
            self.scope,
            self.envelope,
            **self.write(),
        )

    def commit(self, **changes):
        facts = {
            "attempt_id": "40000000-0000-4000-8000-000000000001",
            "occurred_at": "2025-01-02T00:00:04Z",
            "owner_id": self.lease.owner_id,
            "fencing_token": self.lease.fencing_token,
            "actor_reference": "operator-review",
        }
        facts.update(changes)
        return commit_fubon_test_pre_submit(
            self.store, self.scope, self.authorization, self.envelope, **facts
        )

    def observation(self, **changes):
        facts = {
            "schema_version": FUBON_PROVIDER_OBSERVATION_SCHEMA_VERSION,
            "environment": BrokerEnvironment.SANDBOX,
            "endpoint": FUBON_NEO_TEST_ENDPOINT,
            "account_reference": self.envelope.account_reference,
            "trading_date": self.envelope.trading_date,
            "provider_order_id": "provider-order-1",
            "provider_tag": derive_fubon_provider_correlation_tag(
                self.envelope.canonical_client_order_id
            ),
            "symbol": self.envelope.symbol,
            "side": self.envelope.side,
            "quantity": self.envelope.quantity,
            "order_type": self.envelope.order_type,
            "time_in_force": self.envelope.time_in_force,
            "limit_price": self.envelope.limit_price,
        }
        facts.update(changes)
        return FubonProviderOrderObservation(**facts)

    def test_result_is_exact_ready_for_test_adapter_and_preserves_d0_blockers(self):
        result = current_fubon_neo_test_mutation_readiness()
        self.assertIs(
            result.outcome,
            TestMutationReadinessOutcome.READY_FOR_TEST_MUTATION_ADAPTER,
        )
        self.assertEqual(result.d0_blocker_dispositions, FUBON_TEST_D0_BLOCKER_DISPOSITIONS)
        self.assertEqual(
            {item.blocker for item in result.d0_blocker_dispositions},
            {
                D0PrerequisiteName.ACCOUNT_CAPITAL_AUTHORITY,
                D0PrerequisiteName.POSITION_VALUATION_EXPOSURE_AUTHORITY,
                D0PrerequisiteName.TRADING_PERMISSION_PROOF,
                D0PrerequisiteName.FEE_TAX_AUTHORITY,
                D0PrerequisiteName.CLIENT_CORRELATION_LOST_ACK_SAFETY,
                D0PrerequisiteName.SESSION_PROOF,
            },
        )
        self.assertTrue(all(item.live_requirement_preserved for item in result.d0_blocker_dispositions))
        self.assertTrue(
            all(
                item.classification
                in {
                    D0BlockerTestClassification.REQUIRED_ONLY_FOR_LIVE_CAPABLE_AUTHORIZATION,
                    D0BlockerTestClassification.REPLACED_BY_TEST_ONLY_FAIL_CLOSED_RULE,
                }
                for item in result.d0_blocker_dispositions
            )
        )

    def test_live_capable_v1_contract_fields_are_unchanged(self):
        self.assertEqual(
            tuple(item.name for item in fields(BrokerExecutionAuthorization))[:5],
            (
                "schema_version",
                "artifact_type",
                "authorization_id",
                "account_reference",
                "broker_id",
            ),
        )
        self.assertNotIsInstance(self.authorization, BrokerExecutionAuthorization)

    def test_live_is_structurally_rejected_at_policy_envelope_authorization_and_store(self):
        with self.assertRaises(BrokerTestMutationModelError):
            replace(FUBON_TEST_MUTATION_POLICY, environment=BrokerEnvironment.LIVE)
        with self.assertRaises(BrokerTestMutationModelError):
            replace(self.envelope, environment=BrokerEnvironment.LIVE)
        with self.assertRaises(BrokerTestMutationModelError):
            replace(self.authorization, environment=BrokerEnvironment.LIVE)
        with self.assertRaises(Exception):
            self.store.acquire_lease(
                BrokerAccountScope("FUBON_NEO", BrokerEnvironment.LIVE, "live-account"),
                owner_id="controller",
                acquired_at="2025-01-02T00:00:00Z",
                expires_at="2025-01-02T01:00:00Z",
            )

    def test_test_and_live_artifact_namespaces_reject_cross_deserialization_and_casts(self):
        payload = serialize_test_mutation_artifact(self.authorization)
        with self.assertRaises(BrokerSafetySerializationError):
            deserialize_broker_safety_artifact(payload)
        with self.assertRaises(BrokerSafetySerializationError):
            serialize_broker_safety_artifact(self.authorization)
        self.assertEqual(
            deserialize_test_mutation_artifact(payload), self.authorization
        )
        self.assertIn(TEST_MUTATION_SCHEMA_VERSION, export_test_mutation_artifact_json(self.authorization))
        with self.assertRaises(BrokerTestMutationSerializationError):
            serialize_test_mutation_artifact(object())
        with self.assertRaises(BrokerTestMutationSerializationError):
            deserialize_test_mutation_artifact(
                {"artifact_type": "broker_execution_authorization"}
            )

    def test_synthetic_limits_are_not_capital_or_fee_authority(self):
        policy = FUBON_TEST_MUTATION_POLICY
        self.assertIs(
            policy.limit_authority,
            TestLimitAuthority.SYNTHETIC_SANDBOX_HARNESS_ONLY,
        )
        names = {item.name for item in fields(policy)}
        self.assertTrue(
            {"cash", "buying_power", "equity", "fees", "taxes"}.isdisjoint(names)
        )
        with self.assertRaises(BrokerTestMutationModelError):
            self.make_envelope(limit_price=Decimal("1001"))

    def test_profile_is_buy_only_one_common_lot_limit_day(self):
        for changes in (
            {"side": self.envelope.side.SELL},
            {"quantity": 1},
            {"quantity": 2000},
            {"lot_mode": "ODD_LOT"},
            {"trade_mode": "MARGIN"},
            {"order_type": self.envelope.order_type.MARKET},
            {"time_in_force": self.envelope.time_in_force.IOC},
        ):
            with self.subTest(changes=changes), self.assertRaises(BrokerTestMutationModelError):
                replace(self.envelope, **changes)

    def test_full_identity_and_noncanonical_provider_tag_are_durable_under_fence(self):
        binding = self.bind()
        self.assertRegex(binding.canonical_client_order_id, r"twst1-[0-9a-f]{64}\Z")
        self.assertEqual(binding.canonical_client_order_id, self.envelope.canonical_client_order_id)
        self.assertNotEqual(binding.provider_tag, binding.canonical_client_order_id)
        self.assertEqual(binding.provider_name, FUBON_PROVIDER_NAME)
        self.assertEqual(binding.fencing_token, self.lease.fencing_token)
        with self.assertRaises(BrokerTestMutationModelError):
            DurableTestProviderTagBinding(
                binding.schema_version,
                binding.broker_id,
                binding.environment,
                binding.endpoint,
                binding.account_reference,
                binding.envelope_id,
                binding.provider_name,
                binding.provider_tag,
                binding.canonical_client_order_id,
                binding.fencing_token,
                binding.mapped_at,
                binding.mapping_audit_sequence,
                object(),
            )

    def test_atomic_pre_submit_is_one_shot_idempotent_and_restart_blocks(self):
        self.bind()
        first = self.commit()
        self.assertEqual(self.commit(), first)
        with self.assertRaises(PersistenceConflictError):
            self.commit(attempt_id="40000000-0000-4000-8000-000000000002")
        restarted = SQLiteBrokerTestMutationStore(self.database)
        plan = restarted.recovery_plan(self.scope)
        self.assertTrue(plan.blocks_new_test_submission)
        self.assertEqual(plan.active_order_count, 1)
        self.assertEqual(plan.unresolved_submission_count, 1)
        self.assertIn("TEST_UNRESOLVED_SUBMISSION_STATE", plan.blocking_reasons)

    def test_atomic_failure_rolls_back_high_water_use_submission_and_audit(self):
        self.bind()
        before = self.store.recovery_plan(self.scope)
        with self.assertRaises(Exception):
            self.commit(fail_before_commit=True)
        after = self.store.recovery_plan(self.scope)
        self.assertEqual(after.authorization_use_count, 0)
        self.assertEqual(after.unresolved_submission_count, 0)
        self.assertEqual(after.last_audit_sequence, before.last_audit_sequence)

    def test_maximum_one_active_and_unresolved_attempt(self):
        self.bind()
        self.commit()
        other = self.make_envelope(
            envelope_id="20000000-0000-4000-8000-000000000002",
            economic_intent_id="2" * 64,
            idempotency_key="test-intent-v1:two",
            canonical_client_order_id="twst1-" + "b" * 64,
            sequence=2,
        )
        other_auth = build_fubon_test_execution_authorization(
            other,
            authorization_id="30000000-0000-4000-8000-000000000002",
            issued_at="2025-01-02T00:00:02Z",
            expires_at="2025-01-02T00:10:00Z",
            approver_reference="operator-review",
        )
        persist_fubon_test_provider_tag_binding(
            self.store, self.scope, other, **self.write(now="2025-01-02T00:00:05Z")
        )
        with self.assertRaises(PersistenceConflictError):
            commit_fubon_test_pre_submit(
                self.store,
                self.scope,
                other_auth,
                other,
                attempt_id="40000000-0000-4000-8000-000000000002",
                occurred_at="2025-01-02T00:00:06Z",
                owner_id=self.lease.owner_id,
                fencing_token=self.lease.fencing_token,
                actor_reference="operator-review",
            )

    def test_stale_fence_cannot_map_or_commit(self):
        old = self.lease
        self.lease = self.store.acquire_lease(
            self.scope,
            owner_id="replacement-controller",
            acquired_at="2025-01-02T01:00:00Z",
            expires_at="2025-01-02T02:00:00Z",
        )
        with self.assertRaises(StaleFenceError):
            persist_fubon_test_provider_tag_binding(
                self.store,
                self.scope,
                self.envelope,
                owner_id=old.owner_id,
                fencing_token=old.fencing_token,
                now="2025-01-02T01:00:01Z",
                actor_reference="operator-review",
            )

    def test_caller_cannot_manufacture_matched_and_exact_observation_can(self):
        binding = self.bind()
        with self.assertRaises(Exception):
            ValidatedProviderOrderMatch(
                "fubon-provider-order-match-v1",
                ProviderOrderMatchState.MATCHED,
                self.envelope.envelope_id,
                self.envelope.canonical_client_order_id,
                binding.provider_tag,
                "provider-order-1",
                "2025-01-02T00:00:05Z",
                object(),
            )
        with self.assertRaises(Exception):
            resolve_fubon_lost_ack(ProviderOrderMatchState.MATCHED)
        result = correlate_fubon_provider_observations(
            self.envelope,
            binding,
            (self.observation(),),
            observed_at="2025-01-02T00:00:05Z",
        )
        self.assertIs(result.match_state, ProviderOrderMatchState.MATCHED)
        self.assertIs(
            resolve_validated_fubon_lost_ack(result),
            LostAckDisposition.RECONCILED_EXISTING_ORDER,
        )

    def test_provider_match_checks_every_order_fact_and_detects_ambiguity(self):
        binding = self.bind()
        mismatch = correlate_fubon_provider_observations(
            self.envelope,
            binding,
            (self.observation(quantity=2000),),
            observed_at="2025-01-02T00:00:05Z",
        )
        self.assertIs(mismatch.match_state, ProviderOrderMatchState.AMBIGUOUS)
        duplicate = correlate_fubon_provider_observations(
            self.envelope,
            binding,
            (
                self.observation(),
                self.observation(provider_order_id="provider-order-2"),
            ),
            observed_at="2025-01-02T00:00:05Z",
        )
        self.assertIs(duplicate.match_state, ProviderOrderMatchState.AMBIGUOUS)

    def test_validated_lost_ack_updates_only_the_existing_durable_attempt(self):
        binding = self.bind()
        commit = self.commit()
        match = correlate_fubon_provider_observations(
            self.envelope,
            binding,
            (self.observation(),),
            observed_at="2025-01-02T00:00:05Z",
        )
        updated = apply_fubon_test_lost_ack(
            self.store,
            self.scope,
            self.envelope,
            match,
            attempt_id=commit.attempt_id,
            owner_id=self.lease.owner_id,
            fencing_token=self.lease.fencing_token,
            recorded_at="2025-01-02T00:00:06Z",
            actor_reference="operator-review",
        )
        self.assertEqual(updated.provider_order_id, "provider-order-1")
        self.assertEqual(updated.sanitized_outcome, "VALIDATED_PROVIDER_MATCH_RECONCILE_EXISTING")
        self.assertNotIn("RETRY", updated.sanitized_outcome)

    def test_lost_ack_never_creates_retry(self):
        binding = self.bind()
        no_match = correlate_fubon_provider_observations(
            self.envelope, binding, (), observed_at="2025-01-02T00:00:05Z"
        )
        self.assertIs(
            resolve_validated_fubon_lost_ack(no_match),
            LostAckDisposition.RECONCILIATION_REQUIRED,
        )
        self.assertNotIn("RETRY", {item.value for item in LostAckDisposition})

    def test_test_store_and_live_store_tables_are_distinct(self):
        connection = sqlite3.connect(self.database)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        finally:
            connection.close()
        self.assertIn("pre_submit_commits", tables)
        self.assertNotIn("test_pre_submit_commits", tables)
        self.assertNotIn("intents", tables)
        self.assertNotIn("executions", tables)

    def test_no_network_mutation_credentials_or_live_cli_surface(self):
        paths = (
            ROOT / "src/tw_stock_tool/broker_safety/test_mutation_models.py",
            ROOT / "src/tw_stock_tool/broker_safety/test_mutation_serialization.py",
            ROOT / "src/tw_stock_tool/broker_safety/test_mutation_store.py",
            ROOT / "src/tw_stock_tool/broker_adapters/fubon_neo/test_mutation.py",
        )
        forbidden_functions = {
            "place_order",
            "cancel_order",
            "modify_order",
            "replace_order",
            "batch_order",
        }
        forbidden_imports = {"requests", "httpx", "socket", "urllib"}
        for path in paths:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
            defined = {
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            imports = {
                alias.name.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names
            }
            self.assertTrue(forbidden_functions.isdisjoint(defined))
            self.assertTrue(forbidden_imports.isdisjoint(imports))
            self.assertNotIn("credentials", defined)
        self.assertNotIn("LIVE", inspect.getsource(commit_fubon_test_pre_submit))


if __name__ == "__main__":
    unittest.main()
