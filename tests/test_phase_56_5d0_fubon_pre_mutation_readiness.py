from __future__ import annotations

import ast
from dataclasses import fields, replace
import inspect
from pathlib import Path
import re
import unittest

from tw_stock_tool.broker_adapters.fubon_neo import (
    FUBON_NEO_D0_PREREQUISITES,
    FUBON_NEO_D0_REVIEWED_SOURCE_URLS,
    FUBON_NEO_D0_SAFETY_PATH_MATRIX,
    FUBON_NEO_MINIMUM_TEST_PROFILE,
    FUBON_PROVIDER_NAME,
    LostAckDisposition,
    ProviderOrderMatchState,
    ProviderTagCollisionError,
    current_fubon_neo_56_5d0_readiness,
    current_fubon_neo_56_5d_readiness,
    derive_fubon_provider_correlation_tag,
    map_capabilities,
    require_unambiguous_provider_tag_binding,
    resolve_fubon_lost_ack,
)
from tw_stock_tool.broker_safety import (
    BrokerAccountSnapshot,
    BrokerEnvironment,
    CapitalAuthorityModel,
    D0BlockReason,
    D0PrerequisiteName,
    D0PrerequisiteStatus,
    D0ReadinessModelError,
    D0ReadinessOutcome,
    D0RequirementState,
    OrderSide,
    OrderType,
    PROVIDER_READINESS_SCHEMA_VERSION,
    ProviderReadinessState,
    SCHEMA_VERSION,
    SafetyFactUsage,
    SafetyPathFact,
    SupportState,
    TimeInForce,
    TradingPermission,
    derive_d0_outcome,
)


ROOT = Path(__file__).resolve().parents[1]


class Phase565D0FubonPreMutationReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.readiness = current_fubon_neo_56_5d0_readiness()

    def prerequisite(self, name: D0PrerequisiteName) -> D0PrerequisiteStatus:
        return next(item for item in self.readiness.prerequisites if item.name is name)

    def test_reviewed_result_is_exactly_blocked_and_retains_144_gate(self):
        self.assertIs(self.readiness.outcome, D0ReadinessOutcome.BLOCKED)
        self.assertIs(self.readiness.prior_56_5d_gate, current_fubon_neo_56_5d_readiness())
        self.assertIs(self.readiness.prior_56_5d_gate.overall, ProviderReadinessState.BLOCKED)
        self.assertEqual(self.readiness.prerequisites, FUBON_NEO_D0_PREREQUISITES)
        self.assertEqual(
            self.readiness.blocking_reasons,
            tuple(sorted(D0BlockReason, key=lambda item: item.value)),
        )

    def test_existing_v1_account_contract_does_not_silently_change(self):
        self.assertEqual(SCHEMA_VERSION, "1.0")
        self.assertEqual(PROVIDER_READINESS_SCHEMA_VERSION, "provider-account-readiness-v1")
        account_fields = tuple(item.name for item in fields(BrokerAccountSnapshot))
        self.assertIn("cash", account_fields)
        self.assertIn("buying_power", account_fields)
        self.assertIn("equity", account_fields)
        self.assertLess(account_fields.index("cash"), account_fields.index("buying_power"))
        self.assertLess(account_fields.index("buying_power"), account_fields.index("equity"))

    def test_path_matrix_covers_every_frozen_fact_once(self):
        self.assertEqual(self.readiness.safety_path_matrix, FUBON_NEO_D0_SAFETY_PATH_MATRIX)
        self.assertEqual(
            tuple(item.fact for item in self.readiness.safety_path_matrix),
            tuple(sorted(SafetyPathFact, key=lambda item: item.value)),
        )
        usage = {item.fact: item.usage for item in self.readiness.safety_path_matrix}
        for fact in (SafetyPathFact.CASH, SafetyPathFact.BUYING_POWER, SafetyPathFact.EQUITY):
            self.assertIs(usage[fact], SafetyFactUsage.UNUSED_IN_CURRENT_GATE)
        for fact in set(SafetyPathFact) - {
            SafetyPathFact.CASH,
            SafetyPathFact.BUYING_POWER,
            SafetyPathFact.EQUITY,
        }:
            self.assertIs(usage[fact], SafetyFactUsage.REQUIRED_FOR_SAFETY_DECISION)

    def test_current_gate_really_does_not_use_v1_capital_fields(self):
        from tw_stock_tool.broker_safety.evaluation import (
            evaluate_broker_limits,
            evaluate_broker_preflight,
        )

        gate_source = inspect.getsource(evaluate_broker_preflight) + inspect.getsource(
            evaluate_broker_limits
        )
        self.assertNotIn("account.cash", gate_source)
        self.assertNotIn("account.buying_power", gate_source)
        self.assertNotIn("account.equity", gate_source)

    def test_missing_capital_and_unresolved_settlement_cannot_authorize_buy(self):
        proof = self.readiness.capital_authority
        self.assertIs(proof.model, CapitalAuthorityModel.UNPROVEN)
        self.assertIs(proof.state, D0RequirementState.BLOCKED)
        self.assertIs(
            proof.settlements_complete_without_double_counting,
            D0RequirementState.BLOCKED,
        )
        self.assertIs(proof.conservative_fees_and_taxes, D0RequirementState.BLOCKED)
        self.assertIs(proof.cannot_overstate_available_capital, D0RequirementState.BLOCKED)
        self.assertIs(
            self.prerequisite(D0PrerequisiteName.ACCOUNT_CAPITAL_AUTHORITY).state,
            D0RequirementState.BLOCKED,
        )

    def test_fee_and_permission_authorities_remain_unknown_and_blocking(self):
        capabilities = map_capabilities(
            capability_snapshot_id="5acf3f15-7e62-4eb2-a977-987f4fcb6f07",
            observed_at="2025-01-02T01:00:00Z",
        )
        self.assertIs(capabilities.fee_estimate_support, SupportState.UNKNOWN)
        self.assertIs(capabilities.trading_permission, TradingPermission.UNKNOWN)
        self.assertIs(
            self.prerequisite(D0PrerequisiteName.FEE_TAX_AUTHORITY).state,
            D0RequirementState.BLOCKED,
        )
        self.assertIs(
            self.prerequisite(D0PrerequisiteName.TRADING_PERMISSION_PROOF).state,
            D0RequirementState.BLOCKED,
        )

    def test_unavailable_position_valuation_blocks_required_exposure_path(self):
        row = next(
            item
            for item in self.readiness.safety_path_matrix
            if item.fact is SafetyPathFact.POSITIONS_MARKET_VALUE
        )
        self.assertIs(row.usage, SafetyFactUsage.REQUIRED_FOR_SAFETY_DECISION)
        self.assertIs(
            self.prerequisite(
                D0PrerequisiteName.POSITION_VALUATION_EXPOSURE_AUTHORITY
            ).state,
            D0RequirementState.BLOCKED,
        )

    def test_short_provider_tag_is_deterministic_noncanonical_and_collision_checked(self):
        canonical = "twst1-" + "a" * 64
        other = "twst1-" + "b" * 64
        tag = derive_fubon_provider_correlation_tag(canonical)
        self.assertEqual(tag, derive_fubon_provider_correlation_tag(canonical))
        self.assertRegex(tag, r"[A-Z0-9]{10}\Z")
        self.assertEqual(len(tag), 10)
        self.assertNotEqual(tag, canonical)
        self.assertEqual(FUBON_PROVIDER_NAME, "FUBON_NEO_USER_DEF_V1")
        require_unambiguous_provider_tag_binding(tag, canonical, canonical)
        with self.assertRaises(ProviderTagCollisionError):
            require_unambiguous_provider_tag_binding(tag, canonical, other)
        with self.assertRaises(D0ReadinessModelError):
            derive_fubon_provider_correlation_tag("short-user-def")

    def test_lost_ack_no_match_never_creates_a_retry_path(self):
        self.assertIs(
            resolve_fubon_lost_ack(ProviderOrderMatchState.NO_MATCH),
            LostAckDisposition.RECONCILIATION_REQUIRED,
        )
        self.assertIs(
            resolve_fubon_lost_ack(ProviderOrderMatchState.AMBIGUOUS),
            LostAckDisposition.UNKNOWN_SUBMISSION_STATE,
        )
        self.assertNotIn("RETRY", {item.value for item in LostAckDisposition})
        self.assertIs(
            self.prerequisite(
                D0PrerequisiteName.CLIENT_CORRELATION_LOST_ACK_SAFETY
            ).state,
            D0RequirementState.BLOCKED,
        )

    def test_minimum_profile_is_sandbox_limit_day_cash_common_lot_only(self):
        profile = self.readiness.minimum_test_profile
        self.assertEqual(profile, FUBON_NEO_MINIMUM_TEST_PROFILE)
        self.assertIs(profile.environment, BrokerEnvironment.SANDBOX)
        self.assertEqual(profile.allowed_order_types, (OrderType.LIMIT,))
        self.assertEqual(profile.allowed_time_in_force, (TimeInForce.DAY,))
        self.assertTrue(
            profile.accepts(
                product="TW_SECURITIES",
                trade_mode="CASH_STOCK",
                side=OrderSide.BUY,
                lot_mode="COMMON_LOT",
                order_type=OrderType.LIMIT,
                time_in_force=TimeInForce.DAY,
                owned_available_quantity=False,
            )
        )
        self.assertTrue(
            profile.accepts(
                product="TW_SECURITIES",
                trade_mode="CASH_STOCK",
                side=OrderSide.SELL,
                lot_mode="COMMON_LOT",
                order_type=OrderType.LIMIT,
                time_in_force=TimeInForce.DAY,
                owned_available_quantity=True,
            )
        )

    def test_wrong_product_and_forbidden_modes_are_rejected(self):
        profile = self.readiness.minimum_test_profile
        candidates = (
            {"product": "FUTURES_OPTIONS"},
            {"trade_mode": "MARGIN"},
            {"trade_mode": "SHORT"},
            {"trade_mode": "SBL"},
            {"trade_mode": "DAY_TRADE"},
            {"lot_mode": "ODD_LOT"},
            {"order_type": OrderType.MARKET},
            {"time_in_force": TimeInForce.IOC},
            {"side": OrderSide.SELL, "owned_available_quantity": False},
        )
        base = {
            "product": "TW_SECURITIES",
            "trade_mode": "CASH_STOCK",
            "side": OrderSide.BUY,
            "lot_mode": "COMMON_LOT",
            "order_type": OrderType.LIMIT,
            "time_in_force": TimeInForce.DAY,
            "owned_available_quantity": True,
        }
        for changes in candidates:
            with self.subTest(changes=changes):
                self.assertFalse(profile.accepts(**(base | changes)))

    def test_session_proof_is_explicitly_blocked(self):
        session = self.prerequisite(D0PrerequisiteName.SESSION_PROOF)
        self.assertIs(session.state, D0RequirementState.BLOCKED)
        self.assertIn("calendar", session.reason)
        self.assertIn("timezone TTL", session.reason)

    def test_every_single_prerequisite_downgrade_blocks_generic_gate(self):
        proven = tuple(
            D0PrerequisiteStatus(
                name,
                D0RequirementState.PROVEN,
                "reviewed-authority",
                "every exact obligation is proven",
            )
            for name in sorted(D0PrerequisiteName, key=lambda item: item.value)
        )
        self.assertIs(derive_d0_outcome(proven), D0ReadinessOutcome.READY_FOR_56_5D)
        for index, item in enumerate(proven):
            downgraded = proven[:index] + (
                replace(item, state=D0RequirementState.BLOCKED),
            ) + proven[index + 1 :]
            with self.subTest(prerequisite=item.name):
                self.assertIs(derive_d0_outcome(downgraded), D0ReadinessOutcome.BLOCKED)

    def test_reviewed_fubon_result_cannot_be_manufactured_ready(self):
        with self.assertRaises(D0ReadinessModelError):
            replace(
                self.readiness,
                outcome=D0ReadinessOutcome.READY_FOR_56_5D,
                blocking_reasons=(),
                _authority=object(),
            )

    def test_official_sources_are_https_fubon_and_normal_contract_is_offline(self):
        self.assertEqual(self.readiness.reviewed_source_urls, FUBON_NEO_D0_REVIEWED_SOURCE_URLS)
        self.assertTrue(
            all(url.startswith("https://www.fbs.com.tw/TradeAPI/docs/") for url in self.readiness.reviewed_source_urls)
        )
        source = inspect.getsource(current_fubon_neo_56_5d0_readiness)
        self.assertNotRegex(source, r"requests|urllib|socket|httpx")

    def test_no_mutation_network_or_credential_surface_was_added(self):
        paths = (
            ROOT / "src/tw_stock_tool/broker_safety/d0_readiness.py",
            ROOT / "src/tw_stock_tool/broker_adapters/fubon_neo/d0_readiness.py",
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
            self.assertIsNone(re.search(r"password|certificate|private[_-]?key", text, re.I))


if __name__ == "__main__":
    unittest.main()
