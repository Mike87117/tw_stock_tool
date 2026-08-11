from __future__ import annotations

import ast
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import unittest

from tw_stock_tool.broker_safety import (
    ACCOUNT_ARTIFACT_TYPE,
    CAPABILITIES_ARTIFACT_TYPE,
    EXPECTATION_ARTIFACT_TYPE,
    LIMIT_REQUEST_ARTIFACT_TYPE,
    OPEN_ORDER_ARTIFACT_TYPE,
    POLICY_ARTIFACT_TYPE,
    POSITION_ARTIFACT_TYPE,
    SCHEMA_VERSION,
    SESSION_ARTIFACT_TYPE,
    AccountDataFreshness,
    BrokerAccountSnapshot,
    BrokerCapabilities,
    BrokerEnvironment,
    BrokerLimitRequest,
    BrokerLocalExpectation,
    BrokerOpenOrderSnapshot,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    BrokerSafetyModelError,
    BrokerSafetyPolicy,
    BrokerSafetySerializationError,
    CancelReplaceSemantics,
    CapabilityName,
    ExpectedOpenOrder,
    ExpectedPosition,
    ExpectedSubmission,
    FieldReliability,
    FindingCode,
    OrderSide,
    OrderType,
    PermissionState,
    SupportState,
    TimeInForce,
    TradingPermission,
    TradingSessionSnapshot,
    TradingSessionState,
    deserialize_broker_safety_artifact,
    evaluate_broker_limits,
    evaluate_broker_preflight,
    export_broker_safety_artifact_json,
    load_broker_safety_artifact_json,
    reconcile_broker_account,
    serialize_broker_safety_artifact,
)


D = Decimal
CAPABILITY_ID = "00000000-0000-4000-8000-000000000001"
SNAPSHOT_ID = "00000000-0000-4000-8000-000000000002"
SESSION_ID = "00000000-0000-4000-8000-000000000003"
RECONCILIATION_ID = "00000000-0000-4000-8000-000000000004"


class BrokerSafetyA2A3Tests(unittest.TestCase):
    def capabilities(self, **changes) -> BrokerCapabilities:
        values = dict(
            schema_version=SCHEMA_VERSION,
            artifact_type=CAPABILITIES_ARTIFACT_TYPE,
            capability_snapshot_id=CAPABILITY_ID,
            broker_id="demo-broker",
            environment=BrokerEnvironment.SANDBOX,
            market="TWSE",
            currency="TWD",
            client_order_id_support=SupportState.SUPPORTED,
            client_order_id_max_length=32,
            query_by_client_id_support=SupportState.SUPPORTED,
            fractional_quantity_support=SupportState.UNSUPPORTED,
            supported_order_types=(OrderType.LIMIT, OrderType.MARKET),
            supported_time_in_force=(TimeInForce.DAY,),
            partial_fill_reporting=SupportState.SUPPORTED,
            cancel_replace_semantics=CancelReplaceSemantics.CANCEL_THEN_NEW,
            account_data_freshness=AccountDataFreshness.POLLING,
            trading_permission=TradingPermission.ENABLED,
            short_selling_support=SupportState.UNSUPPORTED,
            borrow_availability_support=SupportState.UNSUPPORTED,
            fee_estimate_support=SupportState.SUPPORTED,
            observed_at="2025-01-02T00:00:10Z",
            source_version="fixture-v1",
        )
        values.update(changes)
        return BrokerCapabilities(**values)

    def position(self, **changes) -> BrokerPositionSnapshot:
        values = dict(
            schema_version=SCHEMA_VERSION,
            artifact_type=POSITION_ARTIFACT_TYPE,
            canonical_symbol="2330",
            broker_symbol="2330.TW",
            quantity=D("10"),
            available_quantity=D("10"),
            average_cost=D("100"),
            average_cost_reliability=FieldReliability.RELIABLE,
            market_value=D("1000"),
            market_value_reliability=FieldReliability.RELIABLE,
            realized_pnl=None,
            realized_pnl_reliability=FieldReliability.UNAVAILABLE,
            unrealized_pnl=None,
            unrealized_pnl_reliability=FieldReliability.UNAVAILABLE,
            as_of="2025-01-02T00:00:05Z",
        )
        values.update(changes)
        return BrokerPositionSnapshot(**values)

    def order(self, **changes) -> BrokerOpenOrderSnapshot:
        values = dict(
            schema_version=SCHEMA_VERSION,
            artifact_type=OPEN_ORDER_ARTIFACT_TYPE,
            broker_order_id="broker-1",
            client_order_id="client-1",
            economic_intent_id="intent-1",
            canonical_symbol="2330",
            broker_symbol="2330.TW",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            time_in_force=TimeInForce.DAY,
            original_quantity=D("5"),
            cumulative_filled_quantity=D("2"),
            remaining_quantity=D("3"),
            status=BrokerOrderStatus.PARTIALLY_FILLED,
            submitted_at="2025-01-02T00:00:01Z",
            last_broker_update="2025-01-02T00:00:06Z",
            fees=None,
            taxes=None,
        )
        values.update(changes)
        return BrokerOpenOrderSnapshot(**values)

    def account(self, **changes) -> BrokerAccountSnapshot:
        values = dict(
            schema_version=SCHEMA_VERSION,
            artifact_type=ACCOUNT_ARTIFACT_TYPE,
            snapshot_id=SNAPSHOT_ID,
            account_reference="acct-safe",
            broker_id="demo-broker",
            environment=BrokerEnvironment.SANDBOX,
            retrieved_at="2025-01-02T00:00:10Z",
            currency="TWD",
            cash=D("5000"),
            buying_power=D("4000"),
            equity=D("6000"),
            capabilities=self.capabilities(),
            positions=(self.position(),),
            open_orders=(self.order(),),
            broker_data_version="v7",
            broker_data_cursor=None,
        )
        values.update(changes)
        return BrokerAccountSnapshot(**values)

    def session(self, **changes) -> TradingSessionSnapshot:
        values = dict(
            schema_version=SCHEMA_VERSION,
            artifact_type=SESSION_ARTIFACT_TYPE,
            session_snapshot_id=SESSION_ID,
            market="TWSE",
            timezone_id="Asia/Taipei",
            session_date="2025-01-02",
            state=TradingSessionState.REGULAR,
            submission_permissions=PermissionState.PERMITTED,
            cancel_permissions=PermissionState.PERMITTED,
            is_holiday=False,
            is_special_closure=False,
            is_early_close=False,
            source_id="calendar-fixture",
            source_version="2025a",
            as_of="2025-01-02T00:00:10Z",
        )
        values.update(changes)
        return TradingSessionSnapshot(**values)

    def policy(self, **changes) -> BrokerSafetyPolicy:
        values = dict(
            schema_version=SCHEMA_VERSION,
            artifact_type=POLICY_ARTIFACT_TYPE,
            policy_id="policy-safe",
            policy_version="1",
            currency="TWD",
            allowed_broker_ids=("demo-broker",),
            allowed_environments=(BrokerEnvironment.SANDBOX,),
            allowed_account_references=("acct-safe",),
            allowed_markets=("TWSE",),
            allowed_order_types=(OrderType.LIMIT,),
            maximum_order_notional=D("1000"),
            maximum_post_fill_account_exposure=D("10000"),
            maximum_per_symbol_exposure=D("5000"),
            maximum_per_symbol_quantity=D("100"),
            maximum_simultaneous_open_orders=5,
            maximum_daily_submitted_notional=D("10000"),
            maximum_daily_loss=D("500"),
            snapshot_ttl_seconds=60,
            reconciliation_ttl_seconds=60,
            authorization_ttl_seconds=30,
            initial_allocation_ceiling=D("500"),
            required_capabilities=(
                CapabilityName.CLIENT_ORDER_ID,
                CapabilityName.FEE_ESTIMATE,
                CapabilityName.PARTIAL_FILL_REPORTING,
            ),
        )
        values.update(changes)
        return BrokerSafetyPolicy(**values)

    def expectation(self, **changes) -> BrokerLocalExpectation:
        values = dict(
            schema_version=SCHEMA_VERSION,
            artifact_type=EXPECTATION_ARTIFACT_TYPE,
            local_state_version="local-v3",
            account_reference="acct-safe",
            broker_id="demo-broker",
            environment=BrokerEnvironment.SANDBOX,
            expected_positions=(ExpectedPosition("2330", D("10")),),
            expected_open_orders=(
                ExpectedOpenOrder(
                    "broker-1",
                    "client-1",
                    "intent-1",
                    "2330",
                    OrderSide.BUY,
                    D("5"),
                    D("30"),
                ),
            ),
            expected_nonterminal_submissions=(),
            daily_submitted_notional=D("200"),
            daily_loss=D("10"),
            daily_loss_reliability=FieldReliability.RELIABLE,
            last_reconciled_cursor=None,
        )
        values.update(changes)
        return BrokerLocalExpectation(**values)

    def reconciliation(self, account=None, expectation=None, **changes):
        result = reconcile_broker_account(
            account or self.account(),
            expectation or self.expectation(),
            reconciliation_id=RECONCILIATION_ID,
            completed_at="2025-01-02T00:00:20Z",
        )
        return replace(result, **changes) if changes else result

    def request(self, **changes) -> BrokerLimitRequest:
        values = dict(
            schema_version=SCHEMA_VERSION,
            artifact_type=LIMIT_REQUEST_ARTIFACT_TYPE,
            canonical_symbol="2330",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=D("1"),
            reference_price=D("10"),
            projected_order_notional=D("10"),
            current_daily_submitted_notional=D("200"),
            current_daily_loss=D("10"),
            daily_loss_reliability=FieldReliability.RELIABLE,
            broker_open_order_reserved_notional=D("30"),
            unknown_submission_reserved_notional=D("0"),
            unresolved_submission_count=0,
            estimated_fees=D("0"),
            estimated_taxes=D("0"),
            currency="TWD",
            is_initial_allocation=False,
        )
        values.update(changes)
        return BrokerLimitRequest(**values)

    @staticmethod
    def codes(findings) -> set[FindingCode]:
        return {item.code for item in findings}

    def test_capability_states_keep_unknown_distinct_and_reject_contradictions(self):
        unknown = self.capabilities(
            client_order_id_support=SupportState.UNKNOWN,
            client_order_id_max_length=None,
            query_by_client_id_support=SupportState.UNKNOWN,
            account_data_freshness=AccountDataFreshness.UNKNOWN,
            trading_permission=TradingPermission.UNKNOWN,
            cancel_replace_semantics=CancelReplaceSemantics.UNKNOWN,
        )
        self.assertIs(unknown.capability_state(CapabilityName.CLIENT_ORDER_ID), SupportState.UNKNOWN)
        self.assertIs(unknown.capability_state(CapabilityName.ACCOUNT_DATA_FRESHNESS), SupportState.UNKNOWN)
        self.assertIs(unknown.capability_state(CapabilityName.TRADING_PERMISSION), SupportState.UNKNOWN)
        self.assertIs(unknown.capability_state(CapabilityName.CANCEL_REPLACE), SupportState.UNKNOWN)
        invalid = (
            {"schema_version": "2.0"},
            {"capability_snapshot_id": "not-a-uuid"},
            {"broker_id": " demo-broker"},
            {"market": "twse"},
            {"currency": "twd"},
            {"client_order_id_max_length": True},
            {"client_order_id_support": SupportState.UNSUPPORTED},
            {
                "client_order_id_support": SupportState.UNSUPPORTED,
                "client_order_id_max_length": None,
            },
            {"supported_order_types": (OrderType.MARKET, OrderType.LIMIT)},
            {"supported_order_types": (OrderType.LIMIT, OrderType.LIMIT)},
            {"supported_time_in_force": ()},
            {"observed_at": "2025-01-02T00:00:00+00:00"},
            {"source_version": ""},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(BrokerSafetyModelError):
                self.capabilities(**changes)

    def test_observation_models_reject_ambiguous_or_impossible_values(self):
        position_invalid = (
            {"quantity": D("NaN")},
            {"available_quantity": D("11")},
            {"quantity": D("-1"), "available_quantity": D("1")},
            {"average_cost": None, "average_cost_reliability": FieldReliability.RELIABLE},
            {"market_value": D("1"), "market_value_reliability": FieldReliability.UNAVAILABLE},
            {"realized_pnl_reliability": "UNKNOWN"},
            {"average_cost": D("-1")},
            {"as_of": "2025-02-30T00:00:00Z"},
        )
        for changes in position_invalid:
            with self.subTest(position=changes), self.assertRaises(BrokerSafetyModelError):
                self.position(**changes)
        order_invalid = (
            {"original_quantity": D("0")},
            {"cumulative_filled_quantity": D("6")},
            {"remaining_quantity": D("2")},
            {"side": "BUY"},
            {"last_broker_update": "2025-01-01T00:00:00Z"},
            {"fees": D("-0.1")},
            {"taxes": D("Infinity")},
            {"client_order_id": ""},
        )
        for changes in order_invalid:
            with self.subTest(order=changes), self.assertRaises(BrokerSafetyModelError):
                self.order(**changes)
        unknown_ids = self.order(client_order_id=None, economic_intent_id=None)
        self.assertIsNone(unknown_ids.client_order_id)
        self.assertIsNone(unknown_ids.economic_intent_id)

    def test_account_and_session_preserve_observed_identity_and_time(self):
        with self.assertRaises(BrokerSafetyModelError):
            self.account(capabilities=self.capabilities(broker_id="other"))
        with self.assertRaises(BrokerSafetyModelError):
            self.account(capabilities=self.capabilities(observed_at="2025-01-02T00:00:11Z"))
        with self.assertRaises(BrokerSafetyModelError):
            self.account(positions=(self.position(), self.position()))
        with self.assertRaises(BrokerSafetyModelError):
            self.account(open_orders=(self.order(broker_order_id="z"), self.order(broker_order_id="a")))
        with self.assertRaises(BrokerSafetyModelError):
            self.account(buying_power=D("-1"))
        with self.assertRaises(BrokerSafetyModelError):
            self.session(timezone_id="Not/AZone")
        with self.assertRaises(BrokerSafetyModelError):
            self.session(session_date="2025-02-30")
        with self.assertRaises(BrokerSafetyModelError):
            self.session(state=TradingSessionState.CLOSED)
        with self.assertRaises(BrokerSafetyModelError):
            self.session(is_holiday=True)
        closed = self.session(
            state=TradingSessionState.CLOSED,
            submission_permissions=PermissionState.NOT_PERMITTED,
            is_holiday=True,
        )
        self.assertFalse(closed.submit_allowed)
        self.assertTrue(self.session().submit_allowed)

    def test_policy_is_closed_by_default_and_validates_exact_limits(self):
        deny = BrokerSafetyPolicy.deny_all(
            policy_id="deny", policy_version="1", currency="TWD"
        )
        self.assertEqual(deny.maximum_order_notional, D("0"))
        self.assertEqual(deny.allowed_broker_ids, ())
        self.assertEqual(deny.required_capabilities, ())
        invalid = (
            {"allowed_broker_ids": ("demo-broker", "demo-broker")},
            {"allowed_environments": (BrokerEnvironment.SANDBOX, BrokerEnvironment.SANDBOX)},
            {"allowed_order_types": (OrderType.MARKET, OrderType.LIMIT)},
            {"maximum_order_notional": -D("1")},
            {"maximum_daily_loss": D("NaN")},
            {"maximum_simultaneous_open_orders": True},
            {"snapshot_ttl_seconds": -1},
            {"required_capabilities": (CapabilityName.FEE_ESTIMATE, CapabilityName.CLIENT_ORDER_ID)},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(BrokerSafetyModelError):
                self.policy(**changes)

    def test_all_artifacts_have_strict_lossless_deterministic_round_trips(self):
        account = self.account()
        expectation = self.expectation()
        artifacts = (
            account.capabilities,
            account.positions[0],
            account.open_orders[0],
            account,
            self.session(),
            self.policy(),
            expectation,
            self.reconciliation(account, expectation),
            self.request(reference_price=D("10.500"), projected_order_notional=D("10.500")),
        )
        for artifact in artifacts:
            with self.subTest(artifact=type(artifact).__name__):
                payload = serialize_broker_safety_artifact(artifact)
                restored = deserialize_broker_safety_artifact(payload)
                text = export_broker_safety_artifact_json(artifact)
                self.assertEqual(restored, artifact)
                self.assertEqual(load_broker_safety_artifact_json(text), artifact)
                self.assertEqual(export_broker_safety_artifact_json(restored), text)
                self.assertTrue(text.endswith("\n"))
        text = export_broker_safety_artifact_json(artifacts[-1])
        self.assertIn('"projected_order_notional": "10.5"', text)
        self.assertNotIn("10.500", text)

    def test_loader_rejects_malformed_noncanonical_and_ambiguous_payloads(self):
        payload = serialize_broker_safety_artifact(self.request())
        mutations = []
        item = dict(payload)
        item.pop("currency")
        mutations.append(item)
        item = dict(payload, surprise=True)
        mutations.append(item)
        mutations.append(dict(payload, artifact_type="future_artifact"))
        mutations.append(dict(payload, quantity=1))
        mutations.append(dict(payload, quantity="1.0"))
        mutations.append(dict(payload, quantity="NaN"))
        mutations.append(dict(payload, side="UNKNOWN"))
        mutations.append(dict(payload, unresolved_submission_count=False))
        mutations.append(dict(payload, is_initial_allocation=1))
        for item in mutations:
            with self.subTest(item=item), self.assertRaises(BrokerSafetySerializationError):
                deserialize_broker_safety_artifact(item)
        malformed_json = (
            '{"artifact_type":"broker_limit_request","artifact_type":"broker_limit_request"}',
            "[]",
            '{"artifact_type": NaN}',
            "{",
        )
        for text in malformed_json:
            with self.subTest(text=text), self.assertRaises(BrokerSafetySerializationError):
                load_broker_safety_artifact_json(text)
        with self.assertRaises(BrokerSafetySerializationError):
            serialize_broker_safety_artifact(object())

    def test_reconciliation_is_deterministic_complete_and_does_not_repair(self):
        account = self.account()
        expectation = self.expectation()
        before_account = export_broker_safety_artifact_json(account)
        before_expectation = export_broker_safety_artifact_json(expectation)
        clean = self.reconciliation(account, expectation)
        self.assertTrue(clean.is_reconciled)
        self.assertEqual(clean.findings, ())
        self.assertEqual(export_broker_safety_artifact_json(account), before_account)
        self.assertEqual(export_broker_safety_artifact_json(expectation), before_expectation)

        cases = (
            (self.account(account_reference="other"), expectation, FindingCode.IDENTITY_MISMATCH),
            (account, self.expectation(expected_positions=(ExpectedPosition("2330", D("9")),)), FindingCode.POSITION_MISMATCH),
            (account, self.expectation(expected_open_orders=()), FindingCode.UNKNOWN_BROKER_OPEN_ORDER),
            (self.account(open_orders=()), expectation, FindingCode.UNRESOLVED_LOCAL_ORDER),
            (
                self.account(open_orders=(self.order(broker_order_id="broker-2"),)),
                expectation,
                FindingCode.CLIENT_ORDER_ID_CONFLICT,
            ),
            (
                account,
                self.expectation(
                    expected_open_orders=(
                        ExpectedOpenOrder("broker-1", "client-1", "other-intent", "2330", OrderSide.BUY, D("5"), D("30")),
                    )
                ),
                FindingCode.CLIENT_ORDER_ID_CONFLICT,
            ),
            (
                self.account(open_orders=()),
                self.expectation(
                    expected_open_orders=(),
                    expected_nonterminal_submissions=(
                        ExpectedSubmission("submission-1", "client-2", "intent-2", "2330", OrderSide.BUY, D("1"), D("10")),
                    ),
                ),
                FindingCode.UNRESOLVED_SUBMISSION,
            ),
        )
        for observed, local, code in cases:
            with self.subTest(code=code):
                result = self.reconciliation(observed, local)
                self.assertIn(code, self.codes(result.findings))
                self.assertFalse(result.is_reconciled)
                keys = [
                    (item.code.value, item.subject_type.value, item.subject_id, item.observed or "", item.expected or "", item.message)
                    for item in result.findings
                ]
                self.assertEqual(keys, sorted(keys))

    def test_preflight_requires_allowlists_capabilities_freshness_and_session(self):
        account = self.account()
        policy = self.policy()
        reconciliation = self.reconciliation(account, self.expectation())
        self.assertEqual(
            evaluate_broker_preflight(
                account, self.session(), policy, reconciliation, evaluated_at="2025-01-02T00:00:30Z"
            ),
            (),
        )
        deny_codes = self.codes(
            evaluate_broker_preflight(
                account,
                self.session(market="TPEX"),
                BrokerSafetyPolicy.deny_all(policy_id="deny", policy_version="1", currency="USD"),
                reconciliation,
                evaluated_at="2025-01-02T00:01:10Z",
            )
        )
        self.assertTrue(
            {
                FindingCode.BROKER_NOT_ALLOWED,
                FindingCode.ACCOUNT_NOT_ALLOWED,
                FindingCode.ENVIRONMENT_NOT_ALLOWED,
                FindingCode.MARKET_NOT_ALLOWED,
                FindingCode.CURRENCY_MISMATCH,
                FindingCode.IDENTITY_MISMATCH,
                FindingCode.SNAPSHOT_STALE,
                FindingCode.RECONCILIATION_STALE,
            }.issubset(deny_codes)
        )
        unknown_account = self.account(
            capabilities=self.capabilities(
                client_order_id_support=SupportState.UNKNOWN,
                client_order_id_max_length=None,
                query_by_client_id_support=SupportState.UNKNOWN,
                trading_permission=TradingPermission.UNKNOWN,
            )
        )
        unknown_reconciliation = self.reconciliation(unknown_account, self.expectation())
        unknown_codes = self.codes(
            evaluate_broker_preflight(
                unknown_account,
                self.session(
                    state=TradingSessionState.UNKNOWN,
                    submission_permissions=PermissionState.UNKNOWN,
                    cancel_permissions=PermissionState.UNKNOWN,
                ),
                policy,
                unknown_reconciliation,
                evaluated_at="2025-01-02T00:00:30Z",
            )
        )
        self.assertIn(FindingCode.CAPABILITY_UNKNOWN, unknown_codes)
        self.assertIn(FindingCode.TRADING_PERMISSION_UNKNOWN, unknown_codes)
        self.assertIn(FindingCode.SESSION_UNKNOWN, unknown_codes)
        disabled_account = self.account(
            capabilities=self.capabilities(trading_permission=TradingPermission.DISABLED)
        )
        disabled_codes = self.codes(
            evaluate_broker_preflight(
                disabled_account,
                self.session(submission_permissions=PermissionState.NOT_PERMITTED),
                policy,
                self.reconciliation(disabled_account, self.expectation()),
                evaluated_at="2025-01-02T00:00:30Z",
            )
        )
        self.assertIn(FindingCode.TRADING_PERMISSION_DISABLED, disabled_codes)
        self.assertIn(FindingCode.SESSION_NOT_PERMITTED, disabled_codes)

    def test_preflight_frozen_ttl_boundaries_and_reconciliation_identity_fail_closed(self):
        account = self.account()
        reconciliation = self.reconciliation(account, self.expectation())
        policy = self.policy(snapshot_ttl_seconds=20, reconciliation_ttl_seconds=10)
        at_boundary = self.codes(
            evaluate_broker_preflight(
                account, self.session(), policy, reconciliation, evaluated_at="2025-01-02T00:00:30Z"
            )
        )
        self.assertIn(FindingCode.SNAPSHOT_STALE, at_boundary)
        self.assertIn(FindingCode.RECONCILIATION_STALE, at_boundary)
        self.assertIn(FindingCode.SESSION_UNKNOWN, at_boundary)
        stale_subjects = {
            item.subject_type.value
            for item in evaluate_broker_preflight(
                account,
                self.session(),
                policy,
                reconciliation,
                evaluated_at="2025-01-02T00:00:30Z",
            )
            if item.code is FindingCode.SNAPSHOT_STALE
        }
        self.assertEqual(stale_subjects, {"ACCOUNT", "CAPABILITY"})
        before_boundary = evaluate_broker_preflight(
            account,
            self.session(),
            policy,
            reconciliation,
            evaluated_at="2025-01-02T00:00:29Z",
        )
        self.assertNotIn(FindingCode.SNAPSHOT_STALE, self.codes(before_boundary))
        self.assertNotIn(FindingCode.RECONCILIATION_STALE, self.codes(before_boundary))
        wrong = replace(reconciliation, snapshot_id=CAPABILITY_ID)
        self.assertIn(
            FindingCode.RECONCILIATION_REQUIRED,
            self.codes(
                evaluate_broker_preflight(
                    account, self.session(), self.policy(), wrong, evaluated_at="2025-01-02T00:00:30Z"
                )
            ),
        )
        future_codes = self.codes(
            evaluate_broker_preflight(
                account,
                self.session(as_of="2025-01-02T00:00:31Z"),
                self.policy(),
                reconciliation,
                evaluated_at="2025-01-02T00:00:30Z",
            )
        )
        self.assertIn(FindingCode.SESSION_UNKNOWN, future_codes)

    def test_limit_equal_boundaries_pass_and_each_overage_blocks(self):
        account = self.account()
        equal_policy = self.policy(
            maximum_order_notional=D("10"),
            maximum_post_fill_account_exposure=D("1040"),
            maximum_per_symbol_exposure=D("1040"),
            maximum_per_symbol_quantity=D("14"),
            maximum_simultaneous_open_orders=2,
            maximum_daily_submitted_notional=D("240"),
            maximum_daily_loss=D("10"),
            initial_allocation_ceiling=D("10"),
        )
        equal_request = self.request()
        self.assertEqual(evaluate_broker_limits(account, self.expectation(), equal_policy, equal_request), ())
        overages = (
            ("maximum_order_notional", D("9.99"), FindingCode.ORDER_NOTIONAL_LIMIT),
            ("maximum_post_fill_account_exposure", D("1039.99"), FindingCode.ACCOUNT_EXPOSURE_LIMIT),
            ("maximum_per_symbol_exposure", D("1039.99"), FindingCode.SYMBOL_EXPOSURE_LIMIT),
            ("maximum_per_symbol_quantity", D("13.99"), FindingCode.SYMBOL_QUANTITY_LIMIT),
            ("maximum_simultaneous_open_orders", 1, FindingCode.OPEN_ORDER_LIMIT),
            ("maximum_daily_submitted_notional", D("239.99"), FindingCode.DAILY_NOTIONAL_LIMIT),
            ("maximum_daily_loss", D("9.99"), FindingCode.DAILY_LOSS_LIMIT),
        )
        for field, value, code in overages:
            with self.subTest(field=field):
                findings = evaluate_broker_limits(account, self.expectation(), replace(equal_policy, **{field: value}), equal_request)
                self.assertIn(code, self.codes(findings))

    def test_limits_include_fees_pending_unknowns_and_never_assume_sell_reduces_risk(self):
        account = self.account()
        with_charges = self.request(estimated_fees=D("1"), estimated_taxes=D("2"))
        codes = self.codes(
            evaluate_broker_limits(
                account,
                self.expectation(),
                self.policy(maximum_order_notional=D("12")),
                with_charges,
            )
        )
        self.assertIn(FindingCode.ORDER_NOTIONAL_LIMIT, codes)
        daily_codes = self.codes(
            evaluate_broker_limits(
                account,
                self.expectation(),
                self.policy(maximum_daily_submitted_notional=D("239")),
                self.request(),
            )
        )
        self.assertIn(FindingCode.DAILY_NOTIONAL_LIMIT, daily_codes)
        sell_codes = self.codes(
            evaluate_broker_limits(
                account,
                self.expectation(),
                self.policy(maximum_per_symbol_exposure=D("1005")),
                self.request(side=OrderSide.SELL),
            )
        )
        self.assertIn(FindingCode.SYMBOL_EXPOSURE_LIMIT, sell_codes)

    def test_limit_unknowns_and_capability_gaps_block_conservatively(self):
        account = self.account()
        missing_charges = self.codes(
            evaluate_broker_limits(
                account,
                self.expectation(),
                self.policy(),
                self.request(estimated_fees=None, estimated_taxes=None),
            )
        )
        self.assertIn(FindingCode.INSUFFICIENT_LIMIT_INPUT, missing_charges)
        unreliable_position = self.position(
            market_value=None,
            market_value_reliability=FieldReliability.UNAVAILABLE,
        )
        unreliable_codes = self.codes(
            evaluate_broker_limits(
                self.account(positions=(unreliable_position,)), self.expectation(), self.policy(), self.request()
            )
        )
        self.assertIn(FindingCode.INSUFFICIENT_LIMIT_INPUT, unreliable_codes)
        unreliable_expectation = self.expectation(
            daily_loss=None,
            daily_loss_reliability=FieldReliability.UNAVAILABLE,
        )
        unreliable_loss = self.codes(
            evaluate_broker_limits(
                account,
                unreliable_expectation,
                self.policy(),
                self.request(current_daily_loss=None, daily_loss_reliability=FieldReliability.UNAVAILABLE),
            )
        )
        self.assertIn(FindingCode.DAILY_LOSS_UNRELIABLE, unreliable_loss)
        unresolved_expectation = self.expectation(
            expected_nonterminal_submissions=(
                ExpectedSubmission(
                    "local-2",
                    "client-2",
                    "intent-2",
                    "2330",
                    OrderSide.BUY,
                    D("1"),
                    D("20"),
                ),
            ),
        )
        unresolved = self.codes(
            evaluate_broker_limits(
                account,
                unresolved_expectation,
                self.policy(),
                self.request(unknown_submission_reserved_notional=D("20"), unresolved_submission_count=1),
            )
        )
        self.assertIn(FindingCode.INSUFFICIENT_LIMIT_INPUT, unresolved)
        fractional = self.codes(
            evaluate_broker_limits(
                account,
                self.expectation(),
                self.policy(),
                self.request(quantity=D("0.5"), projected_order_notional=D("5")),
            )
        )
        self.assertIn(FindingCode.CAPABILITY_UNSUPPORTED, fractional)
        short = self.codes(
            evaluate_broker_limits(
                account,
                self.expectation(),
                self.policy(),
                self.request(side=OrderSide.SELL, quantity=D("11"), projected_order_notional=D("110")),
            )
        )
        self.assertIn(FindingCode.CAPABILITY_UNSUPPORTED, short)
        incompatible = self.codes(
            evaluate_broker_limits(
                account,
                self.expectation(),
                self.policy(),
                self.request(currency="USD", order_type=OrderType.STOP),
            )
        )
        self.assertIn(FindingCode.CURRENCY_MISMATCH, incompatible)
        self.assertIn(FindingCode.ORDER_TYPE_NOT_ALLOWED, incompatible)
        self.assertIn(FindingCode.CAPABILITY_UNSUPPORTED, incompatible)

    def test_reconciliation_blocks_ambiguous_and_terminal_order_statuses(self):
        cases = (
            (BrokerOrderStatus.UNKNOWN, D("2"), D("3")),
            (BrokerOrderStatus.CANCELED, D("2"), D("3")),
            (BrokerOrderStatus.REJECTED, D("0"), D("5")),
            (BrokerOrderStatus.EXPIRED, D("2"), D("3")),
            (BrokerOrderStatus.FILLED, D("5"), D("0")),
        )
        for status, filled, remaining in cases:
            with self.subTest(status=status):
                account = self.account(
                    open_orders=(
                        self.order(
                            status=status,
                            cumulative_filled_quantity=filled,
                            remaining_quantity=remaining,
                        ),
                    )
                )
                result = self.reconciliation(account, self.expectation())
                self.assertFalse(result.is_reconciled)
                self.assertIn(FindingCode.BROKER_ORDER_STATUS_MISMATCH, self.codes(result.findings))

        invalid_status_accounting = (
            {"status": BrokerOrderStatus.OPEN},
            {
                "status": BrokerOrderStatus.PARTIALLY_FILLED,
                "cumulative_filled_quantity": D("0"),
                "remaining_quantity": D("5"),
            },
            {"status": BrokerOrderStatus.FILLED},
            {"status": BrokerOrderStatus.REJECTED},
        )
        for changes in invalid_status_accounting:
            with self.subTest(changes=changes), self.assertRaises(BrokerSafetyModelError):
                self.order(**changes)

    def test_session_date_is_bound_to_observation_and_evaluation_timezone(self):
        with self.assertRaises(BrokerSafetyModelError):
            self.session(session_date="2025-01-01")

        account = self.account()
        findings = evaluate_broker_preflight(
            account,
            self.session(as_of="2025-01-02T15:59:59Z"),
            self.policy(snapshot_ttl_seconds=100000, reconciliation_ttl_seconds=100000),
            self.reconciliation(account, self.expectation()),
            evaluated_at="2025-01-02T16:00:00Z",
        )
        self.assertIn(FindingCode.SESSION_NOT_PERMITTED, self.codes(findings))

    def test_limit_state_is_bound_to_account_and_local_expectation(self):
        account = self.account()

        with self.assertRaises(BrokerSafetyModelError):
            ExpectedOpenOrder(
                "broker-1",
                "client-1",
                "intent-1",
                "2330",
                OrderSide.BUY,
                D("5"),
                D("0"),
            )
        with self.assertRaises(BrokerSafetyModelError):
            ExpectedSubmission(
                "local-1",
                "client-1",
                "intent-1",
                "2330",
                OrderSide.BUY,
                D("5"),
                D("0"),
            )
        daily_expectation = self.expectation(daily_submitted_notional=D("60"))
        daily_codes = self.codes(
            evaluate_broker_limits(
                account,
                daily_expectation,
                self.policy(maximum_daily_submitted_notional=D("99")),
                self.request(current_daily_submitted_notional=D("0")),
            )
        )
        self.assertIn(FindingCode.INSUFFICIENT_LIMIT_INPUT, daily_codes)
        self.assertIn(FindingCode.DAILY_NOTIONAL_LIMIT, daily_codes)

        loss_expectation = self.expectation(daily_loss=D("501"))
        loss_codes = self.codes(
            evaluate_broker_limits(
                account,
                loss_expectation,
                self.policy(),
                self.request(current_daily_loss=D("0")),
            )
        )
        self.assertIn(FindingCode.INSUFFICIENT_LIMIT_INPUT, loss_codes)
        self.assertIn(FindingCode.DAILY_LOSS_LIMIT, loss_codes)

        unreliable_expectation = self.expectation(
            daily_loss=None,
            daily_loss_reliability=FieldReliability.UNAVAILABLE,
        )
        unreliable_codes = self.codes(
            evaluate_broker_limits(
                account,
                unreliable_expectation,
                self.policy(),
                self.request(current_daily_loss=D("0")),
            )
        )
        self.assertIn(FindingCode.INSUFFICIENT_LIMIT_INPUT, unreliable_codes)
        self.assertIn(FindingCode.DAILY_LOSS_UNRELIABLE, unreliable_codes)

        reserved_codes = self.codes(
            evaluate_broker_limits(
                account,
                self.expectation(),
                self.policy(maximum_post_fill_account_exposure=D("1020")),
                self.request(broker_open_order_reserved_notional=D("0")),
            )
        )
        self.assertIn(FindingCode.INSUFFICIENT_LIMIT_INPUT, reserved_codes)
        self.assertIn(FindingCode.ACCOUNT_EXPOSURE_LIMIT, reserved_codes)

        unresolved_expectation = self.expectation(
            expected_nonterminal_submissions=(
                ExpectedSubmission(
                    "local-2",
                    "client-2",
                    "intent-2",
                    "2330",
                    OrderSide.BUY,
                    D("1"),
                    D("20"),
                ),
            ),
        )
        unresolved_codes = self.codes(
            evaluate_broker_limits(
                account,
                unresolved_expectation,
                self.policy(maximum_simultaneous_open_orders=2),
                self.request(),
            )
        )
        self.assertIn(FindingCode.INSUFFICIENT_LIMIT_INPUT, unresolved_codes)
        self.assertIn(FindingCode.OPEN_ORDER_LIMIT, unresolved_codes)

        initial_account = self.account(positions=(), open_orders=())
        initial_expectation = self.expectation(
            expected_positions=(),
            expected_open_orders=(),
        )
        initial_codes = self.codes(
            evaluate_broker_limits(
                initial_account,
                initial_expectation,
                self.policy(initial_allocation_ceiling=D("9.99")),
                self.request(
                    broker_open_order_reserved_notional=D("0"),
                    is_initial_allocation=False,
                ),
            )
        )
        self.assertIn(FindingCode.INSUFFICIENT_LIMIT_INPUT, initial_codes)
        self.assertIn(FindingCode.INITIAL_ALLOCATION_LIMIT, initial_codes)

        unbound_codes = self.codes(
            evaluate_broker_limits(
                account,
                self.expectation(expected_open_orders=()),
                self.policy(),
                self.request(broker_open_order_reserved_notional=D("0")),
            )
        )
        self.assertIn(FindingCode.INSUFFICIENT_LIMIT_INPUT, unbound_codes)

    def test_fee_capability_ambiguity_blocks_even_with_numeric_estimates(self):
        cases = (
            (SupportState.UNKNOWN, FindingCode.CAPABILITY_UNKNOWN),
            (SupportState.UNSUPPORTED, FindingCode.CAPABILITY_UNSUPPORTED),
        )
        for state, expected_code in cases:
            with self.subTest(state=state):
                account = self.account(
                    capabilities=self.capabilities(fee_estimate_support=state)
                )
                findings = evaluate_broker_limits(
                    account,
                    self.expectation(),
                    self.policy(required_capabilities=()),
                    self.request(estimated_fees=D("0"), estimated_taxes=D("0")),
                )
                self.assertIn(expected_code, self.codes(findings))

    def test_limit_request_rejects_implicit_or_inexact_input(self):
        invalid = (
            {"quantity": D("0")},
            {"quantity": 1},
            {"reference_price": D("Infinity")},
            {"projected_order_notional": D("11")},
            {"current_daily_submitted_notional": D("-1")},
            {"current_daily_loss": D("-1")},
            {"broker_open_order_reserved_notional": D("-1")},
            {"unknown_submission_reserved_notional": D("NaN")},
            {"unresolved_submission_count": True},
            {"estimated_fees": D("-1")},
            {"currency": "twd"},
            {"is_initial_allocation": 1},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(BrokerSafetyModelError):
                self.request(**changes)

    def test_domain_has_no_forbidden_import_secret_or_side_effect_surface(self):
        root = Path(__file__).resolve().parents[1]
        domain = root / "src" / "tw_stock_tool" / "broker_safety"
        files = [domain / name for name in ("models.py", "evaluation.py", "serialization.py")]
        forbidden_import_roots = {
            "requests", "httpx", "urllib", "socket", "aiohttp", "websockets",
            "sqlite3", "sqlalchemy", "keyring", "boto3", "paper_runtime",
            "workspace", "risk", "simulated", "auth", "execution",
        }
        forbidden_fields = {
            "api_key", "api_secret", "access_token", "refresh_token", "password",
            "credential", "credentials", "private_key", "account_number",
        }
        forbidden_calls = {"submit", "cancel", "replace", "retry", "connect", "login", "authorize"}
        for path in files:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {item.name.split(".")[0] for item in node.names}
                    self.assertTrue(roots.isdisjoint(forbidden_import_roots), (path, roots))
                elif isinstance(node, ast.ImportFrom) and node.module:
                    parts = set(node.module.split("."))
                    self.assertTrue(parts.isdisjoint(forbidden_import_roots), (path, parts))
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.assertNotIn(node.name.lower(), forbidden_calls, (path, node.name))
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertFalse(
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "datetime"
                        and node.func.attr in {"now", "utcnow"},
                        (path, node.lineno),
                    )
            lowered = source.lower()
            for field in forbidden_fields:
                self.assertNotIn(field, lowered, (path, field))
            self.assertNotIn("os.environ", lowered)
            self.assertNotIn("open(", lowered)


if __name__ == "__main__":
    unittest.main()
