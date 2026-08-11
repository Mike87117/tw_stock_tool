from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal
from pathlib import Path
from typing import get_type_hints
import unittest

import tests.test_phase_56_5a2_a3_broker_safety as a2tests
from tw_stock_tool.broker_safety import (
    A4_SCHEMA_VERSION, AUTHORIZATION_USE_PERSISTENCE_NOTICE,
    BrokerA4ModelError, BrokerAuthorizationUseRecord, BrokerExecutionRecord,
    BrokerKillSwitchSnapshot, BrokerOrderIntentKeyPayload,
    BrokerPersistentEncodingRequiredError, BrokerSafetyModelError,
    BrokerSubmissionEvidence,
    BrokerSubmissionState, KillSwitchState, QuantityMode, AuthorizationUseState,
    OrderSide, OrderType, TimeInForce, FindingCode,
    apply_broker_execution, build_broker_execution_authorization,
    build_broker_order_intent, canonical_broker_client_order_id,
    derive_broker_order_intent_key_v1, evaluate_broker_execution_authorization,
    evaluate_broker_limits, evaluate_broker_preflight,
    export_broker_safety_artifact_json, load_broker_safety_artifact_json,
    prepare_broker_submission, reserve_broker_authorization_use,
    transition_broker_authorization_use, transition_broker_submission,
)
from tw_stock_tool.broker_safety.execution_models import (
    EXECUTION_ARTIFACT_TYPE,
    KILL_SWITCH_ARTIFACT_TYPE,
)
from tw_stock_tool.broker_safety.source_models import (
    HANDOFF_ARTIFACT_TYPE, PROGRESSION_ARTIFACT_TYPE, SOURCE_SCHEMA_VERSION,
    BrokerSafetySourceHandoff, ForwardEligibilityDecisionAnchor,
    ForwardEligibilityLineageKey, ForwardEligibilityProgression,
    _canonical_sha256, progression_fingerprint,
)
from tw_stock_tool.forward_paper.eligibility_models import ForwardEligibilityState

D = Decimal
IDS = [f"00000000-0000-4000-8000-{i:012d}" for i in range(20, 40)]


class Phase565A4Tests(unittest.TestCase):
    def setUp(self):
        self.base = a2tests.BrokerSafetyA2A3Tests("test_capability_states_keep_unknown_distinct_and_reject_contradictions")
        lineage = ForwardEligibilityLineageKey(IDS[0], "strategy-1", "eligibility-policy", "1")
        anchor = ForwardEligibilityDecisionAnchor(IDS[6], "6" * 64, "2025-01-02T00:00:00Z", "2330", "7" * 64)
        facts = dict(
            lineage_key=lineage, run_id=IDS[1], publication_id=IDS[2],
            publication_index_sha256="1" * 64, qualification_evaluation_id=IDS[3],
            eligibility_id=IDS[4], eligibility_state=ForwardEligibilityState.ACTIVE,
            eligibility_sha256="2" * 64, metrics_id=IDS[5], metrics_sha256="3" * 64,
            ledger_id=IDS[7], ledger_sha256="4" * 64, decision_count=1,
            last_observed_at=anchor.observed_at, recommendation_anchors=(anchor,),
        )
        self.head = ForwardEligibilityProgression(
            SOURCE_SCHEMA_VERSION, PROGRESSION_ARTIFACT_TYPE,
            progression_fingerprint=progression_fingerprint(**facts), **facts,
        )
        symbols = ("2330",)
        self.source = BrokerSafetySourceHandoff(
            SOURCE_SCHEMA_VERSION, HANDOFF_ARTIFACT_TYPE, self.head.run_id,
            self.head.publication_id, self.head.publication_index_sha256,
            lineage.activation_id, self.head.qualification_evaluation_id,
            lineage.strategy_id, self.head.eligibility_id, ForwardEligibilityState.ACTIVE,
            lineage.policy_id, lineage.policy_version, symbols,
            _canonical_sha256({"schema_version": SOURCE_SCHEMA_VERSION, "artifact_type": "qualified_symbol_universe", "qualified_symbols": list(symbols)}),
            self.head.ledger_id, self.head.ledger_sha256, anchor.recommendation_id,
            anchor.recommendation_sha256, anchor.symbol, anchor.observed_at,
            "BUY", "ENTER", "8" * 64, lineage, self.head.progression_fingerprint,
        )
        self.account = self.base.account(capabilities=self.base.capabilities(client_order_id_max_length=80))
        self.expectation = self.base.expectation()
        self.reconciliation = self.base.reconciliation(self.account, self.expectation)
        self.policy = self.base.policy()
        self.session = self.base.session()
        self.request = self.base.request()
        self.kill = BrokerKillSwitchSnapshot(
            A4_SCHEMA_VERSION, KILL_SWITCH_ARTIFACT_TYPE, "kill-v1",
            self.account.account_reference, self.account.broker_id, self.account.environment,
            KillSwitchState.INACTIVE, KillSwitchState.INACTIVE,
            KillSwitchState.INACTIVE, None, "2025-01-02T00:00:25Z", "ops-v1",
        )
        self.preflight = evaluate_broker_preflight(self.account, self.session, self.policy, self.reconciliation, evaluated_at="2025-01-02T00:00:30Z")
        self.limits = evaluate_broker_limits(self.account, self.expectation, self.policy, self.request)
        self.authorization = self.make_authorization()
        self.intent = self.make_intent()

    def make_authorization(self, **changes):
        values = dict(
            authorization_id=IDS[8], time_in_force=TimeInForce.DAY,
            approved_at="2025-01-02T00:00:30Z", not_before="2025-01-02T00:00:30Z",
            expires_at="2025-01-02T00:00:59Z", approver_identity_ref="operator-ref",
            preflight_findings=self.preflight, limit_findings=self.limits,
        )
        values.update(changes)
        return build_broker_execution_authorization(
            self.source, self.head, self.account, self.reconciliation,
            self.expectation, self.policy, self.session, self.kill, self.request, **values,
        )

    def make_intent(self, **changes):
        values = dict(
            economic_intent_id=IDS[9], canonical_symbol="2330", broker_symbol="2330.TW",
            side=OrderSide.BUY, quantity_mode=QuantityMode.QUANTITY, quantity=D("1"),
            notional=D("10"), order_type=OrderType.LIMIT, time_in_force=TimeInForce.DAY,
            limit_price=D("10"), currency="TWD", created_at="2025-01-02T00:00:31Z",
            intent_revision=0, broker_client_order_id_max_length=80,
        )
        values.update(changes)
        return build_broker_order_intent(self.authorization, self.source, self.head, self.kill, **values)

    def gate_facts(self, **changes):
        values = dict(
            authorization=self.authorization, source=self.source, current_head=self.head,
            account=self.account, reconciliation=self.reconciliation,
            expectation=self.expectation, policy=self.policy, session=self.session,
            kill_switch=self.kill, request=self.request,
        )
        values.update(changes)
        return values

    def consumed_use(self):
        reserved = reserve_broker_authorization_use(
            self.authorization, self.intent, authorization_use_id=IDS[10],
            reserved_at="2025-01-02T00:00:32Z",
        )
        return transition_broker_authorization_use(
            reserved, AuthorizationUseState.CONSUMED,
            authorization_id=self.authorization.authorization_id,
            economic_intent_id=self.intent.economic_intent_id,
            idempotency_key=self.intent.idempotency_key,
            occurred_at="2025-01-02T00:00:33Z",
        )

    def changed_head(self):
        facts = {
            item.name: getattr(self.head, item.name)
            for item in fields(self.head)
            if item.name not in ("schema_version", "artifact_type", "progression_fingerprint")
        }
        facts["ledger_sha256"] = "f" * 64
        return replace(
            self.head, ledger_sha256=facts["ledger_sha256"],
            progression_fingerprint=progression_fingerprint(**facts),
        )

    def test_models_are_frozen_and_kill_switch_dimensions_are_independent(self):
        with self.assertRaises(FrozenInstanceError):
            self.kill.reason = "changed"
        cancel_only = replace(self.kill, cancel_open_orders_state=KillSwitchState.ACTIVE)
        findings = evaluate_broker_execution_authorization(
            self.authorization, self.source, self.head, self.account,
            self.reconciliation, self.expectation, self.policy, self.session,
            cancel_only, self.request, preflight_findings=self.preflight,
            limit_findings=self.limits, evaluated_at="2025-01-02T00:00:31Z",
        )
        self.assertEqual(findings, ())
        for state, code in ((KillSwitchState.UNKNOWN, FindingCode.KILL_SWITCH_UNKNOWN), (KillSwitchState.ACTIVE, FindingCode.KILL_SWITCH_ACTIVE)):
            blocked = replace(self.kill, stop_new_orders_state=state)
            found = evaluate_broker_execution_authorization(
                self.authorization, self.source, self.head, self.account,
                self.reconciliation, self.expectation, self.policy, self.session,
                blocked, self.request, preflight_findings=self.preflight,
                limit_findings=self.limits, evaluated_at="2025-01-02T00:00:31Z",
            )
            self.assertIn(code, {item.code for item in found})

    def test_authorization_rejects_substitution_findings_ttl_and_time_boundaries(self):
        substitutions = (
            replace(self.authorization, current_lineage_head_fingerprint="f" * 64),
            replace(self.authorization, local_state_version="other"),
            replace(self.authorization, broker_safety_policy_version="other"),
            replace(self.authorization, session_date="2025-01-03"),
        )
        for authorization in substitutions:
            found = evaluate_broker_execution_authorization(
                authorization, self.source, self.head, self.account, self.reconciliation,
                self.expectation, self.policy, self.session, self.kill, self.request,
                preflight_findings=self.preflight, limit_findings=self.limits,
                evaluated_at="2025-01-02T00:00:31Z",
            )
            self.assertIn(FindingCode.IDENTITY_MISMATCH, {item.code for item in found})
        stale = evaluate_broker_preflight(self.account, self.session, self.policy, self.reconciliation, evaluated_at="2025-01-02T00:01:10Z")
        with self.assertRaises(BrokerA4ModelError):
            self.make_authorization(preflight_findings=stale)
        with self.assertRaises(BrokerA4ModelError):
            self.make_authorization(expires_at="2025-01-02T00:01:00Z")
        expired = evaluate_broker_execution_authorization(
            self.authorization, self.source, self.head, self.account, self.reconciliation,
            self.expectation, self.policy, self.session, self.kill, self.request,
            preflight_findings=self.preflight, limit_findings=self.limits,
            evaluated_at=self.authorization.expires_at,
        )
        self.assertIn(FindingCode.AUTHORIZATION_EXPIRED, {item.code for item in expired})

    def test_key_is_exact_stable_and_excludes_runtime_metadata(self):
        payload = BrokerOrderIntentKeyPayload(
            A4_SCHEMA_VERSION, self.authorization.account_reference,
            self.authorization.environment, self.source.publication_id,
            self.source.publication_index_sha256, self.head.progression_fingerprint,
            self.source.ledger_id, self.source.recommendation_id,
            self.source.recommendation_sha256, "2330", OrderSide.BUY,
            QuantityMode.QUANTITY, D("1.0"), D("10.00"),
            OrderType.LIMIT, D("10.00"),
            TimeInForce.DAY, "2025-01-02", 0,
        )
        key = derive_broker_order_intent_key_v1(payload)
        self.assertEqual(key, self.intent.idempotency_key)
        self.assertEqual(len(key), len("broker_order_intent_key_v1:") + 64)
        self.assertEqual(canonical_broker_client_order_id(key), self.intent.canonical_client_order_id)
        self.assertEqual(len(self.intent.canonical_client_order_id), 70)
        changed = replace(payload, intent_revision=1)
        self.assertNotEqual(key, derive_broker_order_intent_key_v1(changed))
        self.assertEqual(self.make_intent(created_at="2025-01-02T00:00:32Z").idempotency_key, key)
        with self.assertRaises(BrokerPersistentEncodingRequiredError) as caught:
            canonical_broker_client_order_id(key, broker_max_length=69)
        self.assertIn("PERSISTENT_ENCODING_REQUIRED", str(caught.exception))
        for name in ("quantity", "notional"):
            for value in (1, 1.0, True):
                with self.assertRaises(Exception):
                    replace(payload, **{name: value})

    def test_intent_enforces_key_authorization_and_economic_bounds(self):
        with self.assertRaises(BrokerA4ModelError):
            replace(self.intent, idempotency_key="broker_order_intent_key_v1:" + "0" * 64)
        with self.assertRaises(BrokerA4ModelError):
            replace(self.intent, canonical_client_order_id="twst1-" + "0" * 64)
        with self.assertRaises(BrokerA4ModelError):
            self.make_intent(quantity=D("2"))
        with self.assertRaises(BrokerA4ModelError):
            self.make_intent(limit_price=D("100"), notional=D("1"))
        with self.assertRaises(BrokerA4ModelError):
            self.make_intent(limit_price=D("100"), notional=D("100"))
        with self.assertRaises(BrokerA4ModelError):
            self.make_intent(currency="USD")
        self.assertNotEqual(self.intent.idempotency_key, self.make_intent(intent_revision=1).idempotency_key)
        self.kill = replace(self.kill, stop_new_orders_state=KillSwitchState.ACTIVE)
        with self.assertRaises(BrokerA4ModelError):
            self.make_intent()

    def test_notional_mode_identity_binds_every_execution_quantity(self):
        payload = BrokerOrderIntentKeyPayload(
            A4_SCHEMA_VERSION, self.authorization.account_reference,
            self.authorization.environment, self.source.publication_id,
            self.source.publication_index_sha256, self.head.progression_fingerprint,
            self.source.ledger_id, self.source.recommendation_id,
            self.source.recommendation_sha256, "2330", OrderSide.BUY,
            QuantityMode.NOTIONAL, D("1"), D("10"), OrderType.LIMIT, D("10"),
            TimeInForce.DAY, "2025-01-02", 0,
        )
        changed = replace(payload, quantity=D("2"), notional=D("20"))
        original_key = derive_broker_order_intent_key_v1(payload)
        changed_key = derive_broker_order_intent_key_v1(changed)
        self.assertNotEqual(original_key, changed_key)
        self.assertNotEqual(
            canonical_broker_client_order_id(original_key),
            canonical_broker_client_order_id(changed_key),
        )
        with self.assertRaises(BrokerA4ModelError):
            replace(payload, quantity=D("2"))

    def test_market_quantity_requires_exact_reviewed_conservative_notional(self):
        market_policy = replace(
            self.policy,
            allowed_order_types=(OrderType.LIMIT, OrderType.MARKET),
        )
        market_request = self.base.request(order_type=OrderType.MARKET)
        market_preflight = evaluate_broker_preflight(
            self.account, self.session, market_policy, self.reconciliation,
            evaluated_at="2025-01-02T00:00:30Z",
        )
        market_limits = evaluate_broker_limits(
            self.account, self.expectation, market_policy, market_request,
        )
        market_authorization = build_broker_execution_authorization(
            self.source, self.head, self.account, self.reconciliation,
            self.expectation, market_policy, self.session, self.kill, market_request,
            authorization_id=IDS[12], time_in_force=TimeInForce.DAY,
            approved_at="2025-01-02T00:00:30Z",
            not_before="2025-01-02T00:00:30Z",
            expires_at="2025-01-02T00:00:59Z",
            approver_identity_ref="operator-ref",
            preflight_findings=market_preflight, limit_findings=market_limits,
        )
        values = dict(
            economic_intent_id=IDS[13], canonical_symbol="2330",
            broker_symbol="2330.TW", side=OrderSide.BUY,
            quantity_mode=QuantityMode.QUANTITY, quantity=D("1"),
            order_type=OrderType.MARKET, time_in_force=TimeInForce.DAY,
            limit_price=None, currency="TWD", created_at="2025-01-02T00:00:31Z",
            intent_revision=0, broker_client_order_id_max_length=80,
        )
        for understated in (None, D("9")):
            with self.subTest(notional=understated), self.assertRaises(BrokerSafetyModelError):
                build_broker_order_intent(
                    market_authorization, self.source, self.head, self.kill,
                    notional=understated, **values,
                )
        market_intent = build_broker_order_intent(
            market_authorization, self.source, self.head, self.kill,
            notional=market_authorization.maximum_notional, **values,
        )
        self.assertEqual(market_intent.notional, market_authorization.maximum_notional)

    def test_submission_authorization_gate_recomputes_and_binds_authority(self):
        prepared = prepare_broker_submission(
            self.intent, attempt_id=IDS[11], recorded_at="2025-01-02T00:00:32Z",
        )
        with self.assertRaises(BrokerA4ModelError):
            transition_broker_submission(
                prepared, self.intent, BrokerSubmissionEvidence.AUTHORIZATION_GATE,
                recorded_at="2025-01-02T00:00:33Z",
            )
        with self.assertRaises(TypeError):
            transition_broker_submission(
                prepared, self.intent, BrokerSubmissionEvidence.AUTHORIZATION_GATE,
                recorded_at="2025-01-02T00:00:33Z", gate_findings=(),
            )
        not_yet_valid = replace(self.authorization, not_before="2025-01-02T00:00:40Z")
        identity_mismatch = replace(self.authorization, authorization_id=IDS[12])
        for authorization, recorded_at in (
            (not_yet_valid, "2025-01-02T00:00:33Z"),
            (identity_mismatch, "2025-01-02T00:00:33Z"),
            (self.authorization, self.authorization.expires_at),
        ):
            with self.subTest(authorization=authorization, recorded_at=recorded_at), self.assertRaises(BrokerA4ModelError):
                transition_broker_submission(
                    prepared, self.intent, BrokerSubmissionEvidence.AUTHORIZATION_GATE,
                    recorded_at=recorded_at,
                    **self.gate_facts(authorization=authorization),
                )
        with self.assertRaises(BrokerA4ModelError):
            transition_broker_submission(
                prepared, self.intent, BrokerSubmissionEvidence.AUTHORIZATION_GATE,
                recorded_at="2025-01-02T00:00:33Z",
                **self.gate_facts(current_head=self.changed_head()),
            )
        for state in (KillSwitchState.UNKNOWN, KillSwitchState.ACTIVE):
            with self.subTest(stop_new_orders_state=state), self.assertRaises(BrokerA4ModelError):
                transition_broker_submission(
                    prepared, self.intent, BrokerSubmissionEvidence.AUTHORIZATION_GATE,
                    recorded_at="2025-01-02T00:00:33Z",
                    **self.gate_facts(kill_switch=replace(self.kill, stop_new_orders_state=state)),
                )

        authorized = transition_broker_submission(
            prepared, self.intent, BrokerSubmissionEvidence.AUTHORIZATION_GATE,
            recorded_at="2025-01-02T00:00:33Z", **self.gate_facts(),
        )
        reserved = reserve_broker_authorization_use(
            self.authorization, self.intent, authorization_use_id=IDS[10],
            reserved_at="2025-01-02T00:00:32Z",
        )
        consumed = self.consumed_use()
        changed_key = self.make_intent(intent_revision=1).idempotency_key
        mismatched_uses = (
            reserved,
            replace(consumed, authorization_id=IDS[12]),
            replace(consumed, economic_intent_id=IDS[12]),
            replace(consumed, idempotency_key=changed_key),
        )
        for authorization_use in mismatched_uses:
            with self.subTest(authorization_use=authorization_use), self.assertRaises(BrokerA4ModelError):
                transition_broker_submission(
                    authorized, self.intent, BrokerSubmissionEvidence.SUBMIT_REQUEST,
                    recorded_at="2025-01-02T00:00:34Z",
                    pre_submit_persistence_version="opaque-v1",
                    authorization_use=authorization_use, **self.gate_facts(),
                )
        with self.assertRaises(BrokerA4ModelError):
            transition_broker_submission(
                authorized, self.intent, BrokerSubmissionEvidence.SUBMIT_REQUEST,
                recorded_at="2025-01-02T00:00:34Z",
                pre_submit_persistence_version="opaque-v1",
                authorization_use=consumed,
                **self.gate_facts(kill_switch=replace(self.kill, stop_new_orders_state=KillSwitchState.ACTIVE)),
            )
        submitting = transition_broker_submission(
            authorized, self.intent, BrokerSubmissionEvidence.SUBMIT_REQUEST,
            recorded_at="2025-01-02T00:00:34Z",
            pre_submit_persistence_version="opaque-v1",
            authorization_use=consumed, **self.gate_facts(),
        )
        self.assertEqual(submitting.state, BrokerSubmissionState.SUBMITTING)

    def test_authorization_use_is_one_way_identity_bound_and_explicitly_not_durable(self):
        use = reserve_broker_authorization_use(self.authorization, self.intent, authorization_use_id=IDS[10], reserved_at="2025-01-02T00:00:32Z")
        self.assertEqual(use.state, AuthorizationUseState.RESERVED)
        consumed = transition_broker_authorization_use(
            use, AuthorizationUseState.CONSUMED,
            authorization_id=self.authorization.authorization_id,
            economic_intent_id=self.intent.economic_intent_id,
            idempotency_key=self.intent.idempotency_key,
            occurred_at="2025-01-02T00:00:33Z",
        )
        self.assertEqual(consumed.state, AuthorizationUseState.CONSUMED)
        with self.assertRaises(BrokerA4ModelError):
            transition_broker_authorization_use(consumed, AuthorizationUseState.ABANDONED, authorization_id=self.authorization.authorization_id, economic_intent_id=self.intent.economic_intent_id, idempotency_key=self.intent.idempotency_key, occurred_at="2025-01-02T00:00:34Z")
        with self.assertRaises(BrokerA4ModelError):
            transition_broker_authorization_use(use, AuthorizationUseState.CONSUMED, authorization_id=IDS[11], economic_intent_id=self.intent.economic_intent_id, idempotency_key=self.intent.idempotency_key, occurred_at="2025-01-02T00:00:33Z")
        self.assertIn("do not prove durable", AUTHORIZATION_USE_PERSISTENCE_NOTICE)
        self.assertIn("Phase 56.5C", AUTHORIZATION_USE_PERSISTENCE_NOTICE)

    def submission(self):
        prepared = prepare_broker_submission(self.intent, attempt_id=IDS[11], recorded_at="2025-01-02T00:00:32Z")
        authorized = transition_broker_submission(
            prepared, self.intent, BrokerSubmissionEvidence.AUTHORIZATION_GATE,
            recorded_at="2025-01-02T00:00:33Z", **self.gate_facts(),
        )
        submitting = transition_broker_submission(
            authorized, self.intent, BrokerSubmissionEvidence.SUBMIT_REQUEST,
            recorded_at="2025-01-02T00:00:34Z",
            pre_submit_persistence_version="persist-v1",
            authorization_use=self.consumed_use(), **self.gate_facts(),
        )
        return transition_broker_submission(submitting, self.intent, BrokerSubmissionEvidence.BROKER_ACK, recorded_at="2025-01-02T00:00:35Z", broker_order_id="broker-order-1")

    def execution(self, **changes):
        values = dict(
            schema_version=A4_SCHEMA_VERSION, artifact_type=EXECUTION_ARTIFACT_TYPE,
            broker_order_id="broker-order-1", execution_id="execution-1",
            intent_id=self.intent.economic_intent_id, attempt_id=IDS[11],
            fill_quantity=D("0.4"), fill_price=D("10"),
            fill_time="2025-01-02T00:00:36Z", incremental_fee=None,
            incremental_tax=None, cumulative_quantity=D("0.4"),
            received_at="2025-01-02T00:00:37Z",
        )
        values.update(changes)
        return BrokerExecutionRecord(**values)

    def test_submission_lifecycle_ambiguous_and_contradictory_evidence_fail_closed(self):
        acknowledged = self.submission()
        partial = apply_broker_execution(acknowledged, self.intent, self.execution())
        self.assertEqual(partial.state, BrokerSubmissionState.PARTIALLY_FILLED)
        self.assertEqual(partial.remaining_quantity, D("0.6"))
        with self.assertRaises(BrokerA4ModelError):
            apply_broker_execution(partial, self.intent, self.execution(execution_id="execution-1", cumulative_quantity=D("0.8"), received_at="2025-01-02T00:00:38Z"))
        filled = apply_broker_execution(partial, self.intent, self.execution(execution_id="execution-2", fill_quantity=D("0.6"), cumulative_quantity=D("1"), fill_time="2025-01-02T00:00:38Z", received_at="2025-01-02T00:00:39Z"))
        self.assertEqual(filled.state, BrokerSubmissionState.FILLED)
        with self.assertRaises(BrokerA4ModelError):
            transition_broker_submission(filled, self.intent, BrokerSubmissionEvidence.CANCEL_REQUEST, recorded_at="2025-01-02T00:00:40Z")
        prepared = prepare_broker_submission(self.intent, attempt_id=IDS[12], recorded_at="2025-01-02T00:00:32Z")
        authorized = transition_broker_submission(
            prepared, self.intent, BrokerSubmissionEvidence.AUTHORIZATION_GATE,
            recorded_at="2025-01-02T00:00:33Z", **self.gate_facts(),
        )
        submitting = transition_broker_submission(
            authorized, self.intent, BrokerSubmissionEvidence.SUBMIT_REQUEST,
            recorded_at="2025-01-02T00:00:34Z",
            pre_submit_persistence_version="persist-v2",
            authorization_use=self.consumed_use(), **self.gate_facts(),
        )
        unknown = transition_broker_submission(submitting, self.intent, BrokerSubmissionEvidence.AMBIGUOUS_OUTCOME, recorded_at="2025-01-02T00:00:35Z")
        self.assertEqual(unknown.state, BrokerSubmissionState.UNKNOWN_SUBMISSION_STATE)
        recon = transition_broker_submission(acknowledged, self.intent, BrokerSubmissionEvidence.BROKER_ACK, recorded_at="2025-01-02T00:00:36Z")
        self.assertEqual(recon.state, BrokerSubmissionState.RECONCILIATION_REQUIRED)

    def test_cancel_after_partial_preserves_fill_and_unknown_fees(self):
        partial = apply_broker_execution(self.submission(), self.intent, self.execution())
        pending = transition_broker_submission(partial, self.intent, BrokerSubmissionEvidence.CANCEL_REQUEST, recorded_at="2025-01-02T00:00:38Z")
        cancelled = transition_broker_submission(pending, self.intent, BrokerSubmissionEvidence.BROKER_CANCELLATION, recorded_at="2025-01-02T00:00:39Z")
        self.assertEqual(cancelled.cumulative_filled_quantity, D("0.4"))
        self.assertEqual(cancelled.remaining_quantity, D("0.6"))
        self.assertIsNone(self.execution().incremental_fee)
        with self.assertRaises(BrokerA4ModelError):
            apply_broker_execution(partial, self.intent, self.execution(execution_id="execution-2", fill_quantity=D("0.7"), cumulative_quantity=D("1.1"), received_at="2025-01-02T00:00:38Z"))
        with self.assertRaises(BrokerA4ModelError):
            self.execution(fill_quantity=D("0.5"), cumulative_quantity=D("0.4"))
        with self.assertRaises(BrokerA4ModelError):
            apply_broker_execution(self.submission(), self.intent, self.execution(fill_time="2025-01-02T00:00:33Z", received_at="2025-01-02T00:00:37Z"))

    def test_all_six_a4_artifacts_round_trip_strictly_and_deterministically(self):
        use = reserve_broker_authorization_use(self.authorization, self.intent, authorization_use_id=IDS[10], reserved_at="2025-01-02T00:00:32Z")
        artifacts = (self.kill, self.authorization, use, self.intent, self.submission(), self.execution())
        for artifact in artifacts:
            encoded = export_broker_safety_artifact_json(artifact)
            self.assertEqual(load_broker_safety_artifact_json(encoded), artifact)
            self.assertEqual(export_broker_safety_artifact_json(load_broker_safety_artifact_json(encoded)), encoded)
        encoded = export_broker_safety_artifact_json(self.intent)
        with self.assertRaises(Exception):
            load_broker_safety_artifact_json(encoded.replace('"quantity": "1"', '"quantity": "1.0"'))
        with self.assertRaises(Exception):
            load_broker_safety_artifact_json(encoded.replace('"artifact_type":', '"unknown": 1, "artifact_type":'))
        with self.assertRaises(Exception):
            load_broker_safety_artifact_json(encoded.replace('"schema_version": "1.0",', '"schema_version": "1.0", "schema_version": "1.0",'))
        with self.assertRaises(Exception):
            load_broker_safety_artifact_json(encoded.replace('"side": "BUY"', '"side": "INVALID"'))

    def test_authorization_use_schema_has_no_fake_global_used_flag(self):
        names = {item.name for item in fields(BrokerAuthorizationUseRecord)}
        self.assertNotIn("used", names)
        self.assertNotIn("is_used", names)

    def test_protocols_are_read_only_and_domain_has_no_io_secret_or_side_effect_surface(self):
        from tw_stock_tool.broker_safety import BrokerAccountSnapshotReader, BrokerCapabilitiesReader, TradingSessionReader
        self.assertEqual(set(BrokerCapabilitiesReader.__dict__) & {"read_capabilities", "submit", "cancel"}, {"read_capabilities"})
        self.assertEqual(set(BrokerAccountSnapshotReader.__dict__) & {"read_account_snapshot", "submit", "cancel"}, {"read_account_snapshot"})
        self.assertEqual(set(TradingSessionReader.__dict__) & {"read_trading_session", "submit", "cancel"}, {"read_trading_session"})
        self.assertEqual(get_type_hints(BrokerCapabilitiesReader.read_capabilities)["return"].__name__, "BrokerCapabilities")
        roots = Path(__file__).parents[1] / "src" / "tw_stock_tool" / "broker_safety"
        paths = [roots / name for name in ("execution_models.py", "execution.py", "protocols.py")]
        forbidden_imports = ("requests", "httpx", "urllib", "socket", "sqlite3", "sqlalchemy", "pandas", "ibapi", "shioaji")
        forbidden_calls = {"submit", "cancel", "replace_order", "connect", "login", "open", "write_text", "write_bytes"}
        secret_tokens = ("password", "api_key", "secret", "access_token", "refresh_token")
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse(any(alias.name.startswith(forbidden_imports) for alias in node.names))
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or "").startswith(forbidden_imports))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, forbidden_calls)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.assertNotIn(node.name, forbidden_calls)
            self.assertFalse(any(token in path.read_text(encoding="utf-8-sig").lower() for token in secret_tokens))


if __name__ == "__main__":
    unittest.main()
