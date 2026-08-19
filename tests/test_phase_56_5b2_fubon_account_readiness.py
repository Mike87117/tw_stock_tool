from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import asdict, replace
import inspect
import json
from pathlib import Path
import unittest

from tw_stock_tool.broker_adapters.fubon_neo import (
    FUBON_NEO_ACCOUNT_EVIDENCE_SHA256,
    FUBON_NEO_ACCOUNT_EVIDENCE_VERSION,
    FUBON_NEO_ACCOUNT_FACT_CONTRACT_VERSION,
    FUBON_NEO_ACCOUNT_FACT_EVIDENCE,
    FUBON_NEO_SOURCE_VERSION,
    FUBON_NEO_TEST_CONNECTION_IDENTITY,
    FUBON_NEO_TEST_ENDPOINT,
    FubonNeo56_5DReadiness,
    FubonNeoAccountFactReadiness,
    FubonNeoErrorCode,
    FubonNeoReadError,
    FubonNeoReadonlyAdapter,
    FubonNeoTestConfig,
    build_reviewed_instrument_catalog,
    current_fubon_neo_56_5d_readiness,
    current_fubon_neo_account_fact_readiness,
    map_cash,
    map_positions,
)
from tw_stock_tool.broker_safety import (
    PROVIDER_READINESS_SCHEMA_VERSION,
    BrokerAccountFact,
    BrokerEnvironment,
    ProviderAccountFactEvidence,
    ProviderDerivationProof,
    ProviderFactScope,
    ProviderMappingClassification,
    ProviderProductScope,
    ProviderReadinessBlockReason,
    ProviderReadinessCheckState,
    ProviderReadinessModelError,
    ProviderReadinessState,
)


ROOT = Path(__file__).parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "fubon_neo_account_fact_evidence_v1.json"
READONLY_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "fubon_neo_test_readonly_v2_2_8.json"
RETRIEVED_AT = "2025-01-02T01:30:10Z"
CAPABILITY_ID = "00000000-0000-4000-8000-000000000201"


class RecordedReadonlyPort:
    def __init__(self, fixture: dict) -> None:
        self.fixture = deepcopy(fixture)
        self.connection_identity = FUBON_NEO_TEST_CONNECTION_IDENTITY
        self.calls: list[str] = []

    def _read(self, name: str):
        self.calls.append(name)
        return deepcopy(self.fixture[name])

    def read_bank_remain(self):
        return self._read("bank_remain")

    def read_inventories(self):
        return self._read("inventories")

    def read_unrealized_pnl(self):
        return self._read("unrealized_pnl")

    def read_order_results(self):
        return self._read("order_results")


class FubonNeoAccountReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.readonly_fixture = json.loads(READONLY_FIXTURE_PATH.read_text(encoding="utf-8"))

    def config(self) -> FubonNeoTestConfig:
        return FubonNeoTestConfig(
            environment=BrokerEnvironment.SANDBOX,
            endpoint=FUBON_NEO_TEST_ENDPOINT,
            account_reference="acct-fubon-test-safe",
            expected_account="SANITIZED-ACCOUNT-01",
            expected_branch="SANITIZED-BRANCH",
        )

    def readonly_config(self) -> FubonNeoTestConfig:
        return FubonNeoTestConfig(
            environment=BrokerEnvironment.SANDBOX,
            endpoint=FUBON_NEO_TEST_ENDPOINT,
            account_reference="acct-fubon-test-safe",
            expected_account="TEST-ACCOUNT-0001",
            expected_branch="TEST-BRANCH",
        )

    def catalog(self):
        return build_reviewed_instrument_catalog(
            deepcopy(self.readonly_fixture["instrument_catalog_evidence"])
        )

    @staticmethod
    def evidence(identity: str) -> ProviderAccountFactEvidence:
        matches = [
            item
            for item in FUBON_NEO_ACCOUNT_FACT_EVIDENCE
            if item.observation_identity == identity
        ]
        if len(matches) != 1:
            raise AssertionError(f"expected one evidence row for {identity}")
        return matches[0]

    def test_evidence_matrix_is_versioned_typed_complete_and_digest_pinned(self):
        self.assertEqual(PROVIDER_READINESS_SCHEMA_VERSION, "provider-account-readiness-v1")
        self.assertEqual(FUBON_NEO_ACCOUNT_FACT_CONTRACT_VERSION, "fubon-neo-securities-account-facts-v1")
        self.assertEqual(FUBON_NEO_ACCOUNT_EVIDENCE_VERSION, "official-fubon-docs-reviewed-2026-08-19-v1")
        self.assertEqual(
            FUBON_NEO_ACCOUNT_EVIDENCE_SHA256,
            "f34931c057487b4571462826de1d569cefe65fb096a8066ac0a4a8bd595f754b",
        )
        self.assertEqual(len(FUBON_NEO_ACCOUNT_FACT_EVIDENCE), 11)
        self.assertTrue(
            all(type(item) is ProviderAccountFactEvidence for item in FUBON_NEO_ACCOUNT_FACT_EVIDENCE)
        )
        self.assertEqual(
            {item.observation_identity for item in FUBON_NEO_ACCOUNT_FACT_EVIDENCE},
            {
                "accounting.bank_remain.balance",
                "accounting.bank_remain.available_balance",
                "accounting.query_settlement.details[*]",
                "accounting.inventories[*]",
                "accounting.unrealized_gains_and_loses[*]",
                "accounting.realized_gains_and_loses[*]",
                "accounting.realized_gains_and_loses_summary[*]",
                "accounting.maintenance",
                "stock.margin_quota(account,stock_no)",
                "stock.get_order_results(account)",
                "futopt_accounting.query_margin_equity",
            },
        )
        for item in FUBON_NEO_ACCOUNT_FACT_EVIDENCE:
            self.assertEqual(item.source_version, FUBON_NEO_ACCOUNT_EVIDENCE_VERSION)
            self.assertTrue(item.source_url.startswith("https://www.fbs.com.tw/TradeAPI/docs/"))
            self.assertIsNone(item.derivation_proof)

    def test_available_balance_stays_unclassified_and_balance_stays_cash(self):
        balance = self.evidence("accounting.bank_remain.balance")
        available = self.evidence("accounting.bank_remain.available_balance")
        self.assertIs(balance.candidate_fact, BrokerAccountFact.CASH)
        self.assertIs(balance.classification, ProviderMappingClassification.EXACT_AUTHORITATIVE)
        self.assertIs(available.candidate_fact, BrokerAccountFact.BUYING_POWER)
        self.assertIs(available.classification, ProviderMappingClassification.UNCLASSIFIED)
        readiness = current_fubon_neo_account_fact_readiness()
        self.assertIs(readiness.cash.classification, ProviderMappingClassification.EXACT_AUTHORITATIVE)
        self.assertIs(readiness.buying_power.classification, ProviderMappingClassification.UNCLASSIFIED)

    def test_missing_securities_equity_returns_typed_blocked_readiness(self):
        readiness = current_fubon_neo_account_fact_readiness()
        self.assertIs(type(readiness), FubonNeoAccountFactReadiness)
        self.assertEqual(
            readiness.account_fact_contract_version,
            FUBON_NEO_ACCOUNT_FACT_CONTRACT_VERSION,
        )
        self.assertIs(readiness.equity.fact, BrokerAccountFact.EQUITY)
        self.assertIs(readiness.equity.classification, ProviderMappingClassification.UNAVAILABLE)
        self.assertIs(readiness.overall, ProviderReadinessState.BLOCKED)
        self.assertEqual(
            readiness.blocking_reasons,
            (
                ProviderReadinessBlockReason.BUYING_POWER_SEMANTICS_UNCLASSIFIED,
                ProviderReadinessBlockReason.EQUITY_UNAVAILABLE,
                ProviderReadinessBlockReason.ACCOUNT_FACTS_INCOMPLETE,
            ),
        )
        self.assertTrue(readiness.cash.is_ready)
        self.assertTrue(readiness.positions.is_ready)
        self.assertTrue(readiness.open_orders.is_ready)
        self.assertFalse(readiness.buying_power.is_ready)
        self.assertFalse(readiness.equity.is_ready)

    def test_futures_equity_is_rejected_as_securities_authority(self):
        evidence = self.evidence("futopt_accounting.query_margin_equity")
        self.assertIs(evidence.product_scope, ProviderProductScope.FUTURES_OPTIONS)
        self.assertIs(evidence.fact_scope, ProviderFactScope.ACCOUNT)
        self.assertIs(evidence.candidate_fact, BrokerAccountFact.EQUITY)
        self.assertIs(evidence.classification, ProviderMappingClassification.UNAVAILABLE)
        self.assertIn(
            "today_equity",
            self.fixture["normal"]["futures_options_margin_equity_rejected"],
        )
        self.assertIs(current_fubon_neo_account_fact_readiness().overall, ProviderReadinessState.BLOCKED)

    def test_symbol_margin_quota_cannot_satisfy_account_buying_power(self):
        quota = self.evidence("stock.margin_quota(account,stock_no)")
        self.assertIs(quota.fact_scope, ProviderFactScope.SYMBOL)
        self.assertIs(quota.candidate_fact, BrokerAccountFact.BUYING_POWER)
        self.assertIs(quota.classification, ProviderMappingClassification.UNCLASSIFIED)
        self.assertEqual(self.fixture["normal"]["margin_quota"]["data"][0]["stock_no"], "2330")

    def test_settlement_rows_are_not_derived_or_double_counted_with_cash(self):
        settlement = self.evidence("accounting.query_settlement.details[*]")
        self.assertIs(settlement.classification, ProviderMappingClassification.UNCLASSIFIED)
        self.assertFalse(
            any(
                item.candidate_fact is BrokerAccountFact.BUYING_POWER
                and item.classification is ProviderMappingClassification.DERIVED_AUTHORITATIVE
                for item in FUBON_NEO_ACCOUNT_FACT_EVIDENCE
            )
        )
        duplicate_rows = self.fixture["adversarial"]["duplicate_settlement_rows"]
        self.assertEqual(duplicate_rows[0], duplicate_rows[1])
        self.assertIs(current_fubon_neo_account_fact_readiness().overall, ProviderReadinessState.BLOCKED)

    def test_account_currency_date_and_contradiction_inputs_fail_closed(self):
        for name, code in (
            ("wrong_account", FubonNeoErrorCode.ACCOUNT_IDENTITY_MISMATCH),
            ("wrong_currency", FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD),
        ):
            with self.subTest(case=name), self.assertRaises(FubonNeoReadError) as caught:
                map_cash(self.fixture["adversarial"][name], self.config())
            self.assertIs(caught.exception.code, code)

        stale_inventory = deepcopy(self.fixture["normal"]["inventories"]["data"])
        stale_unrealized = deepcopy(
            self.fixture["normal"]["unrealized_gains_and_loses"]["data"]
        )
        stale_inventory[0]["date"] = self.fixture["adversarial"]["stale_date"]["date"]
        with self.assertRaises(FubonNeoReadError) as stale_caught:
            map_positions(
                stale_inventory,
                stale_unrealized,
                self.config(),
                instrument_catalog=self.catalog(),
                retrieved_at=RETRIEVED_AT,
            )
        self.assertIs(stale_caught.exception.code, FubonNeoErrorCode.PROVIDER_RESPONSE_MALFORMED)

        contradictory_inventory = deepcopy(self.fixture["normal"]["inventories"]["data"])
        contradictory_unrealized = deepcopy(
            self.fixture["normal"]["unrealized_gains_and_loses"]["data"]
        )
        contradictory_unrealized[0]["today_qty"] = self.fixture["adversarial"][
            "contradictory_accounting_inputs"
        ]["unrealized_today_qty"]
        with self.assertRaises(FubonNeoReadError) as contradiction_caught:
            map_positions(
                contradictory_inventory,
                contradictory_unrealized,
                self.config(),
                instrument_catalog=self.catalog(),
                retrieved_at=RETRIEVED_AT,
            )
        self.assertIs(contradiction_caught.exception.code, FubonNeoErrorCode.AMBIGUOUS_PROVIDER_RECORDS)

    def test_missing_duplicate_and_empty_official_shapes_remain_non_authorizing(self):
        self.assertNotIn("balance", self.fixture["adversarial"]["missing_field"])
        self.assertEqual(self.fixture["normal"]["empty_inventories"]["data"], [])
        with self.assertRaises(FubonNeoReadError) as caught:
            map_cash(self.fixture["adversarial"]["missing_field"], self.config())
        self.assertIs(caught.exception.code, FubonNeoErrorCode.MANDATORY_ACCOUNT_FIELD_UNAVAILABLE)
        for _case in self.fixture["adversarial"].values():
            self.assertIs(
                current_fubon_neo_account_fact_readiness().overall,
                ProviderReadinessState.BLOCKED,
            )

    def test_derivation_contract_requires_complete_non_overstatement_proof(self):
        proof = ProviderDerivationProof(
            accounting_identity="authoritative input A plus authoritative input B",
            input_observation_identities=("provider.input_a", "provider.input_b"),
            account_scope="one runtime-bound securities account",
            currency="TWD",
            freshness_rule="same complete observation cut",
            settlement_rule="all settlement dates and receivable/payable effects are explicit",
            open_order_exposure_rule="all reserved nonterminal exposure is deducted exactly once",
            instrument_mode_rule="cash, margin, short, day-trade, SBL, lot modes remain distinct",
            missing_duplicate_contradiction_rule="any missing duplicate or contradiction blocks",
            inputs_authoritative=True,
            complete_accounting_identity=True,
            same_account=True,
            same_currency=True,
            sufficiently_fresh=True,
            settlement_complete=True,
            open_orders_complete=True,
            instrument_modes_complete=True,
            no_market_estimate=True,
            missing_duplicate_contradiction_fail_closed=True,
            cannot_overstate_available_capital=True,
        )
        derived = ProviderAccountFactEvidence(
            observation_identity="provider.derived_fact",
            documented_meaning="A hypothetical fully proven derived fact.",
            candidate_fact=BrokerAccountFact.BUYING_POWER,
            classification=ProviderMappingClassification.DERIVED_AUTHORITATIVE,
            product_scope=ProviderProductScope.SECURITIES,
            fact_scope=ProviderFactScope.ACCOUNT,
            source_url="https://provider.invalid/official",
            source_version="reviewed-v1",
            reason="All exact derivation obligations are frozen in the proof.",
            derivation_proof=proof,
        )
        self.assertIs(derived.derivation_proof, proof)
        for field in (
            "inputs_authoritative",
            "complete_accounting_identity",
            "same_account",
            "same_currency",
            "sufficiently_fresh",
            "settlement_complete",
            "open_orders_complete",
            "instrument_modes_complete",
            "no_market_estimate",
            "missing_duplicate_contradiction_fail_closed",
            "cannot_overstate_available_capital",
        ):
            with self.subTest(field=field), self.assertRaises(ProviderReadinessModelError):
                replace(proof, **{field: False})
        with self.assertRaises(ProviderReadinessModelError):
            replace(derived, derivation_proof=None)

    def test_adapter_exposes_blocked_result_and_snapshot_has_no_override(self):
        port = RecordedReadonlyPort(self.readonly_fixture)
        adapter = FubonNeoReadonlyAdapter(self.readonly_config(), port, self.catalog())
        self.assertIs(adapter.read_account_fact_readiness(), current_fubon_neo_account_fact_readiness())
        self.assertEqual(port.calls, [])
        observations = adapter.read_account_observations(
            capability_snapshot_id=CAPABILITY_ID,
            retrieved_at=RETRIEVED_AT,
        )
        self.assertIs(observations.account_fact_readiness, current_fubon_neo_account_fact_readiness())
        self.assertEqual(observations.missing_mandatory_fields, ("buying_power", "equity"))
        with self.assertRaises(FubonNeoReadError) as caught:
            observations.require_complete_snapshot()
        self.assertIs(caught.exception.code, FubonNeoErrorCode.MANDATORY_ACCOUNT_FIELD_UNAVAILABLE)
        with self.assertRaises(FubonNeoReadError):
            adapter.read_account_snapshot(
                capability_snapshot_id=CAPABILITY_ID,
                retrieved_at=RETRIEVED_AT,
            )
        self.assertEqual(
            set(inspect.signature(adapter.read_account_snapshot).parameters),
            {"capability_snapshot_id", "retrieved_at"},
        )

    def test_callers_cannot_forge_ready_results(self):
        readiness = current_fubon_neo_account_fact_readiness()
        with self.assertRaises(ValueError):
            replace(readiness, overall=ProviderReadinessState.READY)
        gate = current_fubon_neo_56_5d_readiness()
        with self.assertRaises(ValueError):
            replace(
                gate,
                complete_account_snapshot_capability=ProviderReadinessCheckState.PROVEN,
                overall=ProviderReadinessState.READY,
                blocking_reasons=(),
            )

    def test_explicit_56_5d_gate_is_typed_pure_and_blocked(self):
        gate = current_fubon_neo_56_5d_readiness()
        self.assertIs(type(gate), FubonNeo56_5DReadiness)
        self.assertEqual(gate.provider_contract_version, FUBON_NEO_SOURCE_VERSION)
        self.assertEqual(
            gate.account_fact_contract_version,
            FUBON_NEO_ACCOUNT_FACT_CONTRACT_VERSION,
        )
        self.assertIs(gate.official_test_provenance, ProviderReadinessCheckState.PROVEN)
        self.assertIs(gate.sdk_version_match, ProviderReadinessCheckState.PROVEN)
        self.assertIs(gate.position_open_order_reconciliation, ProviderReadinessCheckState.PROVEN)
        self.assertIs(
            gate.complete_account_snapshot_capability,
            ProviderReadinessCheckState.BLOCKED,
        )
        self.assertIs(gate.provider_account_fact_readiness.overall, ProviderReadinessState.BLOCKED)
        self.assertIs(gate.overall, ProviderReadinessState.BLOCKED)
        self.assertIn(
            ProviderReadinessBlockReason.COMPLETE_ACCOUNT_SNAPSHOT_UNPROVEN,
            gate.blocking_reasons,
        )
        self.assertIs(gate, current_fubon_neo_56_5d_readiness())
        serialized = json.dumps(asdict(gate), sort_keys=True)
        self.assertEqual(json.loads(serialized)["overall"], "BLOCKED")
        self.assertEqual(json.loads(serialized)["schema_version"], PROVIDER_READINESS_SCHEMA_VERSION)

    def test_fixture_is_sanitized_offline_deterministic_and_official_shaped(self):
        self.assertEqual(self.fixture["schema_version"], "fubon-neo-account-fact-fixture-v1")
        normal = self.fixture["normal"]
        self.assertEqual(
            set(normal),
            {
                "bank_remain",
                "query_settlement",
                "inventories",
                "empty_inventories",
                "unrealized_gains_and_loses",
                "realized_gains_and_loses",
                "realized_gains_and_loses_summary",
                "maintenance",
                "margin_quota",
                "futures_options_margin_equity_rejected",
            },
        )
        fixture_text = FIXTURE_PATH.read_text(encoding="utf-8")
        for forbidden in ("6460", "1234567", "api_key", "password", "certificate"):
            self.assertNotIn(forbidden, fixture_text.lower())
        self.assertEqual(self.fixture, json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))

    def test_new_contract_has_no_network_mutation_or_persistence_surface(self):
        package = ROOT / "src" / "tw_stock_tool" / "broker_adapters" / "fubon_neo"
        inspected = [
            ROOT / "src" / "tw_stock_tool" / "broker_safety" / "provider_readiness.py",
            package / "account_readiness.py",
            package / "adapter.py",
        ]
        forbidden_imports = {"requests", "httpx", "urllib", "socket", "sqlite3", "sqlalchemy"}
        forbidden_functions = {
            "place_order",
            "cancel_order",
            "modify_order",
            "replace_order",
            "batch_order",
            "connect",
            "login",
            "write_text",
            "write_bytes",
        }
        for path in inspected:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse(any(alias.name.split(".")[0] in forbidden_imports for alias in node.names))
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or "").split(".")[0], forbidden_imports)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.assertNotIn(node.name, forbidden_functions)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, forbidden_functions)


if __name__ == "__main__":
    unittest.main()
