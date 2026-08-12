from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import asdict, fields, replace
from decimal import Decimal
import importlib
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from tw_stock_tool.broker_adapters.fubon_neo import (
    FUBON_NEO_BROKER_ID,
    FUBON_NEO_INSTRUMENT_CATALOG_SOURCE,
    FUBON_NEO_CURRENCY,
    FUBON_NEO_MARKET,
    FUBON_NEO_SDK_VERSION,
    FUBON_NEO_TEST_CONNECTION_IDENTITY,
    FUBON_NEO_SOURCE_VERSION,
    FUBON_NEO_TEST_ENDPOINT,
    FubonNeoErrorCode,
    FubonNeoIncompleteAccountRead,
    FubonNeoInstrumentCatalog,
    FubonNeoReadError,
    FubonNeoReadConnectionIdentity,
    FubonNeoReadonlyAdapter,
    FubonNeoReadonlyPort,
    FubonNeoTestConfig,
    exact_decimal,
    require_fubon_neo_sdk,
)
from tw_stock_tool.broker_safety import (
    ACCOUNT_ARTIFACT_TYPE,
    EXPECTATION_ARTIFACT_TYPE,
    SCHEMA_VERSION,
    BrokerAccountSnapshot,
    BrokerEnvironment,
    BrokerLocalExpectation,
    BrokerOrderStatus,
    BrokerSafetyModelError,
    ExpectedPosition,
    FieldReliability,
    OrderType,
    SupportState,
    TimeInForce,
    TradingPermission,
    reconcile_broker_account,
)


D = Decimal
CAPABILITY_ID = "00000000-0000-4000-8000-000000000101"
SNAPSHOT_ID = "00000000-0000-4000-8000-000000000102"
RECONCILIATION_ID = "00000000-0000-4000-8000-000000000103"
RETRIEVED_AT = "2025-01-02T01:30:10Z"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "fubon_neo_test_readonly_v2_2_8.json"


class RecordedReadonlyPort:
    def __init__(
        self,
        fixture: dict,
        connection_identity: object = FUBON_NEO_TEST_CONNECTION_IDENTITY,
    ) -> None:
        self.fixture = deepcopy(fixture)
        self.connection_identity = connection_identity
        self.calls: list[str] = []

    def _read(self, name: str):
        self.calls.append(name)
        value = self.fixture[name]
        if isinstance(value, BaseException):
            raise value
        return deepcopy(value)

    def read_bank_remain(self):
        return self._read("bank_remain")

    def read_inventories(self):
        return self._read("inventories")

    def read_unrealized_pnl(self):
        return self._read("unrealized_pnl")

    def read_order_results(self):
        return self._read("order_results")


class FubonNeoReadonlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.recorded = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def config(self, **changes) -> FubonNeoTestConfig:
        values = dict(
            environment=BrokerEnvironment.SANDBOX,
            endpoint=FUBON_NEO_TEST_ENDPOINT,
            account_reference="acct-fubon-test-safe",
            expected_account="TEST-ACCOUNT-0001",
            expected_branch="TEST-BRANCH",
        )
        values.update(changes)
        return FubonNeoTestConfig(**values)

    def catalog(self, **changes) -> FubonNeoInstrumentCatalog:
        fixture = self.recorded["instrument_catalog"]
        values = dict(
            source=fixture["source"],
            source_version=fixture["source_version"],
            taiex_symbols=tuple(fixture["TAIEX"]),
            taisdaq_symbols=tuple(fixture["TAISDAQ"]),
        )
        values.update(changes)
        return FubonNeoInstrumentCatalog(**values)

    def adapter(self, port, *, catalog=None, config=None) -> FubonNeoReadonlyAdapter:
        return FubonNeoReadonlyAdapter(
            self.config() if config is None else config,
            port,
            self.catalog() if catalog is None else catalog,
        )

    def read(self, fixture=None):
        port = RecordedReadonlyPort(self.recorded if fixture is None else fixture)
        result = self.adapter(port).read_account_observations(
            capability_snapshot_id=CAPABILITY_ID,
            retrieved_at=RETRIEVED_AT,
        )
        return result, port

    def error(self, fixture, code: FubonNeoErrorCode) -> FubonNeoReadError:
        port = RecordedReadonlyPort(fixture)
        with self.assertRaises(FubonNeoReadError) as caught:
            self.adapter(port).read_account_observations(
                capability_snapshot_id=CAPABILITY_ID,
                retrieved_at=RETRIEVED_AT,
            )
        self.assertIs(caught.exception.code, code)
        return caught.exception

    @staticmethod
    def second_inventory(fixture: dict, symbol: str = "0050") -> None:
        item = deepcopy(fixture["inventories"]["data"][0])
        item["stock_no"] = symbol
        item["lastday_qty"] = 2
        item["buy_qty"] = 0
        item["buy_filled_qty"] = 0
        item["buy_value"] = 0
        item["today_qty"] = 2
        item["tradable_qty"] = 2
        fixture["inventories"]["data"].append(item)
        pnl = deepcopy(fixture["unrealized_pnl"]["data"][0])
        pnl["stock_no"] = symbol
        pnl["today_qty"] = 2
        pnl["tradable_qty"] = 2
        fixture["unrealized_pnl"]["data"].append(pnl)

    def test_official_contract_constants_and_test_environment_lock(self):
        self.assertEqual(FUBON_NEO_SDK_VERSION, "2.2.8")
        self.assertEqual(FUBON_NEO_TEST_ENDPOINT, "wss://neoapitest.fbs.com.tw/TASP/XCPXWS")
        self.assertEqual(self.config().environment, BrokerEnvironment.SANDBOX)
        for environment in (BrokerEnvironment.LIVE, "SANDBOX", "LIVE", "", None):
            with self.subTest(environment=environment), self.assertRaises(FubonNeoReadError) as caught:
                self.config(environment=environment)
            self.assertIs(caught.exception.code, FubonNeoErrorCode.ENVIRONMENT_NOT_TEST)
        for endpoint in (
            "",
            "wss://neoapi.fbs.com.tw/TASP/XCPXWS",
            "wss://neoapitest.fbs.com.tw/TASP/XCPXW",
            "https://neoapitest.fbs.com.tw/TASP/XCPXWS",
            None,
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(FubonNeoReadError) as caught:
                self.config(endpoint=endpoint)
            self.assertIs(caught.exception.code, FubonNeoErrorCode.ENVIRONMENT_NOT_TEST)

    def test_environment_rejection_precedes_every_transport_call(self):
        port = RecordedReadonlyPort(self.recorded)
        for bad in (
            dict(environment=BrokerEnvironment.LIVE),
            dict(environment=None),
            dict(endpoint="wss://production.invalid/TASP/XCPXWS"),
        ):
            with self.subTest(bad=bad), self.assertRaises(FubonNeoReadError):
                self.adapter(port, config=self.config(**bad))
        self.assertEqual(port.calls, [])
        with self.assertRaises(FubonNeoReadError):
            self.adapter(port, config=object())
        self.assertEqual(port.calls, [])

    def test_session_provenance_mismatch_precedes_every_provider_read(self):
        variants = (
            replace(FUBON_NEO_TEST_CONNECTION_IDENTITY, broker_id="OTHER"),
            replace(
                FUBON_NEO_TEST_CONNECTION_IDENTITY,
                environment=BrokerEnvironment.LIVE,
            ),
            replace(
                FUBON_NEO_TEST_CONNECTION_IDENTITY,
                endpoint="wss://neoapi.fbs.com.tw/TASP/XCPXWS",
            ),
            replace(FUBON_NEO_TEST_CONNECTION_IDENTITY, sdk_version="2.2.7"),
            replace(
                FUBON_NEO_TEST_CONNECTION_IDENTITY,
                provider_contract_version="unreviewed-v2",
            ),
            replace(FUBON_NEO_TEST_CONNECTION_IDENTITY, product_scope="OTHER"),
            None,
        )
        self.assertIs(
            type(FUBON_NEO_TEST_CONNECTION_IDENTITY),
            FubonNeoReadConnectionIdentity,
        )
        for identity in variants:
            port = RecordedReadonlyPort(self.recorded, identity)
            with self.subTest(identity=identity), self.assertRaises(FubonNeoReadError) as caught:
                self.adapter(port)
            self.assertIs(
                caught.exception.code,
                FubonNeoErrorCode.SESSION_PROVENANCE_MISMATCH,
            )
            self.assertEqual(port.calls, [])

        swapped_port = RecordedReadonlyPort(self.recorded)
        adapter = self.adapter(swapped_port)
        swapped_port.connection_identity = replace(
            FUBON_NEO_TEST_CONNECTION_IDENTITY,
            endpoint="wss://neoapi.fbs.com.tw/TASP/XCPXWS",
        )
        with self.assertRaises(FubonNeoReadError) as capability_caught:
            adapter.read_capabilities(
                capability_snapshot_id=CAPABILITY_ID,
                observed_at=RETRIEVED_AT,
            )
        self.assertIs(capability_caught.exception.code, FubonNeoErrorCode.SESSION_PROVENANCE_MISMATCH)
        with self.assertRaises(FubonNeoReadError) as caught:
            adapter.read_account_observations(
                capability_snapshot_id=CAPABILITY_ID,
                retrieved_at=RETRIEVED_AT,
            )
        self.assertIs(caught.exception.code, FubonNeoErrorCode.SESSION_PROVENANCE_MISMATCH)
        self.assertEqual(swapped_port.calls, [])

    def test_runtime_account_binding_is_repr_safe(self):
        config = self.config()
        self.assertNotIn("TEST-ACCOUNT-0001", repr(config))
        self.assertNotIn("TEST-BRANCH", repr(config))
        self.assertNotIn("TEST-ACCOUNT-0001", repr(asdict(config)))
        self.assertNotIn("TEST-BRANCH", repr(asdict(config)))
        self.assertTrue(config.matches_provider_account("TEST-ACCOUNT-0001", "TEST-BRANCH"))
        self.assertFalse(config.matches_provider_account("OTHER", "TEST-BRANCH"))

    def test_capabilities_are_exact_and_unknown_semantics_stay_unknown(self):
        capabilities = self.adapter(RecordedReadonlyPort(self.recorded)).read_capabilities(
            capability_snapshot_id=CAPABILITY_ID,
            observed_at=RETRIEVED_AT,
        )
        self.assertEqual(
            (capabilities.broker_id, capabilities.environment, capabilities.market, capabilities.currency),
            (FUBON_NEO_BROKER_ID, BrokerEnvironment.SANDBOX, FUBON_NEO_MARKET, FUBON_NEO_CURRENCY),
        )
        self.assertEqual(capabilities.source_version, FUBON_NEO_SOURCE_VERSION)
        self.assertIs(capabilities.client_order_id_support, SupportState.UNKNOWN)
        self.assertIs(capabilities.query_by_client_id_support, SupportState.UNKNOWN)
        self.assertIs(capabilities.trading_permission, TradingPermission.UNKNOWN)
        self.assertEqual(capabilities.supported_order_types, (OrderType.LIMIT, OrderType.MARKET))
        self.assertNotIn(OrderType.STOP, capabilities.supported_order_types)
        self.assertNotIn(OrderType.STOP_LIMIT, capabilities.supported_order_types)
        self.assertEqual(
            capabilities.supported_time_in_force,
            (TimeInForce.DAY, TimeInForce.FOK, TimeInForce.IOC),
        )

    def test_recorded_fixture_maps_deterministically_without_client_identity_inference(self):
        result, port = self.read()
        self.assertEqual(
            port.calls,
            ["bank_remain", "inventories", "unrealized_pnl", "order_results"],
        )
        self.assertEqual(result.cash.cash, D("5000"))
        self.assertEqual(result.cash.unclassified_available_balance, D("4000"))
        self.assertEqual(len(result.positions), 1)
        position = result.positions[0]
        self.assertEqual((position.canonical_symbol, position.quantity), ("2330", D("10")))
        self.assertEqual(position.average_cost, D("100.25"))
        self.assertEqual(position.unrealized_pnl, D("25"))
        self.assertIs(position.market_value_reliability, FieldReliability.UNAVAILABLE)
        order = result.open_orders[0]
        self.assertEqual(order.status, BrokerOrderStatus.PARTIALLY_FILLED)
        self.assertEqual(
            (order.original_quantity, order.cumulative_filled_quantity, order.remaining_quantity),
            (D("10"), D("4"), D("6")),
        )
        self.assertEqual(order.last_broker_update, "2025-01-02T01:30:05Z")
        self.assertIsNone(order.client_order_id)
        self.assertIsNone(order.economic_intent_id)
        self.assertEqual(result, self.read()[0])

    def test_empty_account_and_multiple_rows_are_canonical(self):
        empty = deepcopy(self.recorded)
        for name in ("inventories", "unrealized_pnl", "order_results"):
            empty[name]["data"] = []
        result, _ = self.read(empty)
        self.assertEqual((result.positions, result.open_orders), ((), ()))

        multiple = deepcopy(self.recorded)
        self.second_inventory(multiple)
        result, _ = self.read(multiple)
        self.assertEqual([item.canonical_symbol for item in result.positions], ["0050", "2330"])

    def test_positions_require_authoritative_versioned_market_classification(self):
        for surface in ("inventories", "unrealized_pnl"):
            self.assertNotIn("market", self.recorded[surface]["data"][0])
        self.assertEqual(self.catalog().source, FUBON_NEO_INSTRUMENT_CATALOG_SOURCE)
        self.assertEqual(self.catalog().source_version, "sanitized-recorded-2025-01-02-v1")

        port = RecordedReadonlyPort(self.recorded)
        with self.assertRaises(FubonNeoReadError) as caught:
            self.adapter(
                port,
                catalog=self.catalog(taiex_symbols=("0050",)),
            ).read_account_observations(
                capability_snapshot_id=CAPABILITY_ID,
                retrieved_at=RETRIEVED_AT,
            )
        self.assertIs(
            caught.exception.code,
            FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
        )

        for surface in ("inventories", "unrealized_pnl"):
            fixture = deepcopy(self.recorded)
            fixture[surface]["data"][0]["market"] = "TAIEX"
            with self.subTest(surface=surface):
                self.error(fixture, FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD)

        no_catalog_port = RecordedReadonlyPort(self.recorded)
        with self.assertRaises(FubonNeoReadError) as caught:
            self.adapter(no_catalog_port, catalog=object())
        self.assertIs(
            caught.exception.code,
            FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
        )
        self.assertEqual(no_catalog_port.calls, [])
        with self.assertRaises(FubonNeoReadError) as caught:
            self.catalog(source="CALLER_ASSERTED")
        self.assertIs(
            caught.exception.code,
            FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
        )

    def test_non_cash_odd_lot_and_unsupported_market_positions_fail_closed(self):
        cases = []
        for order_type in ("Margin", "Short", "DayTrade", "SBL", "Unknown"):
            fixture = deepcopy(self.recorded)
            fixture["inventories"]["data"][0]["order_type"] = order_type
            cases.append((order_type, fixture))
        for name, value in (
            ("odd-lot", ("odd", "today_qty", 1)),
            ("emerging", ("market", None, "TAIEMG")),
            ("intraday-odd", ("market_type", None, "IntradayOdd")),
        ):
            fixture = deepcopy(self.recorded)
            field, nested, replacement = value
            if nested is None:
                fixture["inventories"]["data"][0][field] = replacement
            else:
                fixture["inventories"]["data"][0][field][nested] = replacement
            cases.append((name, fixture))
        for name, fixture in cases:
            with self.subTest(case=name):
                self.error(fixture, FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD)

    def test_position_duplicates_join_conflicts_and_quantity_contradictions_reject(self):
        duplicate = deepcopy(self.recorded)
        duplicate["inventories"]["data"].append(deepcopy(duplicate["inventories"]["data"][0]))
        self.error(duplicate, FubonNeoErrorCode.AMBIGUOUS_PROVIDER_RECORDS)

        duplicate_pnl = deepcopy(self.recorded)
        duplicate_pnl["unrealized_pnl"]["data"].append(deepcopy(duplicate_pnl["unrealized_pnl"]["data"][0]))
        self.error(duplicate_pnl, FubonNeoErrorCode.AMBIGUOUS_PROVIDER_RECORDS)

        orphan_pnl = deepcopy(self.recorded)
        orphan_pnl["unrealized_pnl"]["data"][0]["stock_no"] = "0050"
        self.error(orphan_pnl, FubonNeoErrorCode.AMBIGUOUS_PROVIDER_RECORDS)

        contradictory_pnl = deepcopy(self.recorded)
        contradictory_pnl["unrealized_pnl"]["data"][0]["today_qty"] = 9
        self.error(contradictory_pnl, FubonNeoErrorCode.AMBIGUOUS_PROVIDER_RECORDS)

        contradictory_inventory = deepcopy(self.recorded)
        contradictory_inventory["inventories"]["data"][0]["today_qty"] = 11
        self.error(contradictory_inventory, FubonNeoErrorCode.PROVIDER_RESPONSE_MALFORMED)

    def test_terminal_order_rows_are_not_open_exposure(self):
        for status in (30, 40, 50, 90):
            fixture = deepcopy(self.recorded)
            fixture["order_results"]["data"][0]["status"] = status
            result, _ = self.read(fixture)
            with self.subTest(status=status):
                self.assertEqual(result.open_orders, ())

    def test_failed_change_and_history_rows_never_independently_prove_terminal(self):
        for status in (14, 15, 19, 20, 24, 29, 34, 39):
            fixture = deepcopy(self.recorded)
            fixture["order_results"]["data"][0]["status"] = status
            with self.subTest(status=status):
                self.error(fixture, FubonNeoErrorCode.AMBIGUOUS_PROVIDER_RECORDS)

    def test_failed_modify_cancel_and_history_correlate_to_current_exposure(self):
        for status in (14, 15, 19, 20, 24, 29, 34, 39):
            fixture = deepcopy(self.recorded)
            evidence = deepcopy(fixture["order_results"]["data"][0])
            evidence["status"] = status
            fixture["order_results"]["data"].append(evidence)
            with self.subTest(status=status):
                orders = self.read(fixture)[0].open_orders
                self.assertEqual(len(orders), 1)
                self.assertEqual(orders[0].status, BrokerOrderStatus.PARTIALLY_FILLED)

        for field, value in (("stock_no", "0050"), ("buy_sell", "Sell")):
            fixture = deepcopy(self.recorded)
            evidence = deepcopy(fixture["order_results"]["data"][0])
            evidence["status"] = 19
            evidence[field] = value
            fixture["order_results"]["data"].append(evidence)
            with self.subTest(conflict=field):
                self.error(fixture, FubonNeoErrorCode.AMBIGUOUS_PROVIDER_RECORDS)

        reversed_rows = deepcopy(self.recorded)
        failed_cancel = deepcopy(reversed_rows["order_results"]["data"][0])
        failed_cancel["status"] = 39
        reversed_rows["order_results"]["data"] = [
            failed_cancel,
            reversed_rows["order_results"]["data"][0],
        ]
        self.assertEqual(
            self.read(reversed_rows)[0].open_orders[0].remaining_quantity,
            D("6"),
        )

    def test_backend_and_transmitting_statuses_remain_pending(self):
        for status in (0, 4, 8):
            fixture = deepcopy(self.recorded)
            record = fixture["order_results"]["data"][0]
            record["status"] = status
            record["filled_qty"] = 0
            with self.subTest(status=status):
                mapped = self.read(fixture)[0].open_orders[0]
                self.assertEqual(mapped.status, BrokerOrderStatus.PENDING_SUBMIT)
                self.assertEqual(mapped.remaining_quantity, D("10"))

    def test_timeout_and_unknown_order_statuses_fail_closed(self):
        for status in (9, 8.0, None, 999, "10", True):
            fixture = deepcopy(self.recorded)
            fixture["order_results"]["data"][0]["status"] = status
            with self.subTest(status=status):
                self.error(fixture, FubonNeoErrorCode.PROVIDER_STATUS_UNKNOWN)

    def test_repeated_orders_collapse_only_when_exact_and_conflicts_reject(self):
        repeated = deepcopy(self.recorded)
        repeated["order_results"]["data"].append(deepcopy(repeated["order_results"]["data"][0]))
        self.assertEqual(len(self.read(repeated)[0].open_orders), 1)

        conflict = deepcopy(repeated)
        conflict["order_results"]["data"][1]["filled_qty"] = 3
        self.error(conflict, FubonNeoErrorCode.AMBIGUOUS_PROVIDER_RECORDS)

        active_terminal = deepcopy(repeated)
        active_terminal["order_results"]["data"][1]["status"] = 50
        self.error(active_terminal, FubonNeoErrorCode.AMBIGUOUS_PROVIDER_RECORDS)

    def test_malformed_order_number_and_quantity_accounting_reject(self):
        for name, changes in (
            ("missing-order", {"order_no": None}),
            ("filled-over-original", {"filled_qty": 11}),
            ("remaining-ambiguous", {"after_qty": 9}),
            ("zero-quantity", {"quantity": 0, "after_qty": 0}),
        ):
            fixture = deepcopy(self.recorded)
            fixture["order_results"]["data"][0].update(changes)
            with self.subTest(case=name):
                self.error(fixture, FubonNeoErrorCode.PROVIDER_RESPONSE_MALFORMED)

    def test_unknown_order_enums_and_unsupported_assets_fail_closed(self):
        for field, value in (
            ("asset_type", 1),
            ("market", "TAIEMG"),
            ("market_type", "Odd"),
            ("order_type", "Margin"),
            ("buy_sell", "Unknown"),
            ("price_type", "Reference"),
            ("time_in_force", "GTC"),
            ("function_type", 30),
        ):
            fixture = deepcopy(self.recorded)
            record = fixture["order_results"]["data"][0]
            record[field] = value
            if field == "price_type":
                record["after_price_type"] = None
            with self.subTest(field=field, value=value):
                self.error(fixture, FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD)

    def test_market_ioc_and_fok_have_exact_lossless_mappings(self):
        for price_type, tif, expected_type, expected_tif in (
            ("Market", "IOC", OrderType.MARKET, TimeInForce.IOC),
            ("Limit", "FOK", OrderType.LIMIT, TimeInForce.FOK),
        ):
            fixture = deepcopy(self.recorded)
            record = fixture["order_results"]["data"][0]
            record["price_type"] = price_type
            record["after_price_type"] = price_type
            record["time_in_force"] = tif
            mapped = self.read(fixture)[0].open_orders[0]
            self.assertEqual((mapped.order_type, mapped.time_in_force), (expected_type, expected_tif))

    def test_account_branch_and_currency_mismatches_block_the_batch(self):
        for surface in ("bank_remain", "inventories", "unrealized_pnl", "order_results"):
            for field, value in (("account", "OTHER"), ("branch_no", "OTHER")):
                fixture = deepcopy(self.recorded)
                data = fixture[surface]["data"]
                record = data[0] if type(data) is list else data
                record[field] = value
                with self.subTest(surface=surface, field=field):
                    self.error(fixture, FubonNeoErrorCode.ACCOUNT_IDENTITY_MISMATCH)
        fixture = deepcopy(self.recorded)
        fixture["bank_remain"]["data"]["currency"] = "USD"
        self.error(fixture, FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD)

    def test_missing_failed_and_malformed_provider_results_fail_closed(self):
        cases = []
        for surface in ("bank_remain", "inventories", "unrealized_pnl", "order_results"):
            failed = deepcopy(self.recorded)
            failed[surface] = {"is_success": False, "message": "sensitive provider text", "data": None}
            cases.append((surface + "-failed", failed, FubonNeoErrorCode.PROVIDER_READ_FAILED))
            missing = deepcopy(self.recorded)
            missing[surface] = {"is_success": True, "message": None}
            cases.append((surface + "-missing", missing, FubonNeoErrorCode.PROVIDER_RESPONSE_MALFORMED))
        missing_balance = deepcopy(self.recorded)
        del missing_balance["bank_remain"]["data"]["balance"]
        cases.append(("missing-balance", missing_balance, FubonNeoErrorCode.MANDATORY_ACCOUNT_FIELD_UNAVAILABLE))
        missing_available = deepcopy(self.recorded)
        del missing_available["bank_remain"]["data"]["available_balance"]
        cases.append(("missing-available", missing_available, FubonNeoErrorCode.PROVIDER_RESPONSE_MALFORMED))
        empty_bank = deepcopy(self.recorded)
        empty_bank["bank_remain"]["data"] = {}
        cases.append(("empty-bank", empty_bank, FubonNeoErrorCode.ACCOUNT_IDENTITY_MISMATCH))
        for name, fixture, code in cases:
            with self.subTest(case=name):
                self.error(fixture, code)

    def test_numeric_boundary_is_exact_and_rejects_bool_nonfinite_and_malformed(self):
        for value, expected in (
            (7, D("7")),
            (D("7.25"), D("7.25")),
            ("7.25", D("7.25")),
            (7.25, D("7.25")),
            (0.1, D("0.1")),
        ):
            with self.subTest(value=value):
                self.assertEqual(exact_decimal(value), expected)
        for value in (
            True,
            False,
            math.nan,
            math.inf,
            -math.inf,
            D("NaN"),
            D("Infinity"),
            "NaN",
            "Infinity",
            " 1",
            "+1",
            "01",
            "1e3",
            "x",
            object(),
            10**20,
        ):
            with self.subTest(value=value), self.assertRaises(FubonNeoReadError):
                exact_decimal(value)

    def test_numeric_bool_in_provider_fields_rejects(self):
        for surface, field in (
            ("bank_remain", "balance"),
            ("inventories", "today_qty"),
            ("unrealized_pnl", "today_qty"),
            ("order_results", "filled_qty"),
        ):
            fixture = deepcopy(self.recorded)
            data = fixture[surface]["data"]
            record = data[0] if type(data) is list else data
            record[field] = True
            with self.subTest(surface=surface):
                self.error(fixture, FubonNeoErrorCode.PROVIDER_RESPONSE_MALFORMED)

    def test_timestamp_date_and_ambiguous_time_fail_closed(self):
        for field, value in (
            ("date", "2025-01-02"),
            ("date", "2025/02/30"),
            ("date", "2025/01/03"),
            ("last_time", "09:30"),
            ("last_time", "25:00:00"),
            ("last_time", None),
        ):
            fixture = deepcopy(self.recorded)
            fixture["order_results"]["data"][0][field] = value
            with self.subTest(field=field, value=value):
                self.error(fixture, FubonNeoErrorCode.PROVIDER_RESPONSE_MALFORMED)

    def test_provider_symbol_mapping_cannot_be_redirected(self):
        for surface in ("inventories", "unrealized_pnl", "order_results"):
            for override in ("canonical_symbol", "symbol_override"):
                fixture = deepcopy(self.recorded)
                fixture[surface]["data"][0][override] = "AAPL"
                with self.subTest(surface=surface, override=override):
                    self.error(fixture, FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD)
        fixture = deepcopy(self.recorded)
        for value in ("aapl", "AAPL", "006208"):
            fixture = deepcopy(self.recorded)
            fixture["inventories"]["data"][0]["stock_no"] = value
            with self.subTest(stock_no=value):
                self.error(fixture, FubonNeoErrorCode.PROVIDER_RESPONSE_MALFORMED)

    def test_account_completeness_never_relabels_available_balance_or_synthesizes_equity(self):
        result, _ = self.read()
        self.assertIs(type(result), FubonNeoIncompleteAccountRead)
        self.assertEqual(result.missing_mandatory_fields, ("buying_power", "equity"))
        self.assertFalse(hasattr(result, "buying_power"))
        self.assertFalse(hasattr(result, "equity"))
        with self.assertRaises(FubonNeoReadError) as caught:
            result.require_complete_snapshot()
        self.assertIs(caught.exception.code, FubonNeoErrorCode.MANDATORY_ACCOUNT_FIELD_UNAVAILABLE)
        with self.assertRaises(FubonNeoReadError):
            self.adapter(RecordedReadonlyPort(self.recorded)).read_account_snapshot(
                capability_snapshot_id=CAPABILITY_ID,
                retrieved_at=RETRIEVED_AT,
            )

    def test_reconciliation_delegates_only_for_an_exact_complete_snapshot(self):
        fixture = deepcopy(self.recorded)
        fixture["order_results"]["data"] = []
        observations, _ = self.read(fixture)
        complete = BrokerAccountSnapshot(
            schema_version=SCHEMA_VERSION,
            artifact_type=ACCOUNT_ARTIFACT_TYPE,
            snapshot_id=SNAPSHOT_ID,
            account_reference="acct-fubon-test-safe",
            broker_id=FUBON_NEO_BROKER_ID,
            environment=BrokerEnvironment.SANDBOX,
            retrieved_at=RETRIEVED_AT,
            currency=FUBON_NEO_CURRENCY,
            cash=observations.cash.cash,
            buying_power=D("3000"),
            equity=D("7000"),
            capabilities=observations.capabilities,
            positions=observations.positions,
            open_orders=(),
            broker_data_version=FUBON_NEO_SOURCE_VERSION,
            broker_data_cursor=None,
        )
        expectation = BrokerLocalExpectation(
            schema_version=SCHEMA_VERSION,
            artifact_type=EXPECTATION_ARTIFACT_TYPE,
            local_state_version="local-v1",
            account_reference="acct-fubon-test-safe",
            broker_id=FUBON_NEO_BROKER_ID,
            environment=BrokerEnvironment.SANDBOX,
            expected_positions=(ExpectedPosition("2330", D("10")),),
            expected_open_orders=(),
            expected_nonterminal_submissions=(),
            daily_submitted_notional=D("0"),
            daily_loss=None,
            daily_loss_reliability=FieldReliability.UNAVAILABLE,
            last_reconciled_cursor=None,
        )
        reconciled = reconcile_broker_account(
            complete,
            expectation,
            reconciliation_id=RECONCILIATION_ID,
            completed_at=RETRIEVED_AT,
        )
        self.assertTrue(reconciled.is_reconciled)
        with self.assertRaises(BrokerSafetyModelError):
            reconcile_broker_account(
                observations,
                expectation,
                reconciliation_id=RECONCILIATION_ID,
                completed_at=RETRIEVED_AT,
            )

    def test_optional_sdk_is_lazy_and_missing_dependency_is_typed(self):
        imported = importlib.import_module("tw_stock_tool")
        self.assertIsNotNone(imported)
        with patch(
            "tw_stock_tool.broker_adapters.fubon_neo.adapter.import_module",
            side_effect=ModuleNotFoundError("raw module detail"),
        ):
            with self.assertRaises(FubonNeoReadError) as caught:
                require_fubon_neo_sdk()
        self.assertIs(caught.exception.code, FubonNeoErrorCode.OPTIONAL_DEPENDENCY_MISSING)
        self.assertNotIn("raw module detail", str(caught.exception))
        with (
            patch("tw_stock_tool.broker_adapters.fubon_neo.adapter.import_module"),
            patch(
                "tw_stock_tool.broker_adapters.fubon_neo.adapter.distribution_version",
                return_value="2.2.7",
            ),
            self.assertRaises(FubonNeoReadError) as caught,
        ):
            require_fubon_neo_sdk()
        self.assertIs(caught.exception.code, FubonNeoErrorCode.SESSION_PROVENANCE_MISMATCH)

    def test_provider_exceptions_are_sanitized(self):
        fixture = deepcopy(self.recorded)
        fixture["bank_remain"] = RuntimeError("TEST-ACCOUNT-0001 TEST-BRANCH raw-name raw-id raw-key raw-certificate")
        error = self.error(fixture, FubonNeoErrorCode.PROVIDER_READ_FAILED)
        for token in (
            "TEST-ACCOUNT-0001",
            "TEST-BRANCH",
            "raw-name",
            "raw-id",
            "raw-key",
            "raw-certificate",
        ):
            self.assertNotIn(token, str(error))

    def test_readonly_protocol_dependency_and_side_effect_audits(self):
        protocol_methods = {name for name, value in FubonNeoReadonlyPort.__dict__.items() if callable(value) and not name.startswith("_")}
        self.assertEqual(
            protocol_methods,
            {
                "read_bank_remain",
                "read_inventories",
                "read_unrealized_pnl",
                "read_order_results",
            },
        )
        root = Path(__file__).parents[1]
        package = root / "src" / "tw_stock_tool" / "broker_adapters" / "fubon_neo"
        forbidden_imports = (
            "requests",
            "httpx",
            "urllib",
            "socket",
            "sqlite3",
            "sqlalchemy",
            "pandas",
            "shioaji",
        )
        forbidden_calls = {
            "place_order",
            "cancel_order",
            "modify_order",
            "replace_order",
            "batch_order",
            "submit",
            "cancel",
            "connect",
            "login",
            "open",
            "write_text",
            "write_bytes",
        }
        secret_names = {
            "password",
            "api_key",
            "cert_path",
            "cert_pass",
            "personal_id",
            "access_token",
            "refresh_token",
        }
        for path in package.glob("*.py"):
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
                if isinstance(node, ast.Name):
                    self.assertNotIn(node.id.lower(), secret_names)
                if isinstance(node, ast.arg):
                    self.assertNotIn(node.arg.lower(), secret_names)
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        self.assertNotIn("fubon_neo", pyproject)
        self.assertFalse(any(path.suffix.lower() in {".whl", ".pfx", ".p12"} for path in root.rglob("*") if ".git" not in path.parts))
        fixture_text = FIXTURE_PATH.read_text(encoding="utf-8")
        for token in ("raw-name", "raw-id", "raw-key", "certificate"):
            self.assertNotIn(token, fixture_text)

    def test_fixture_and_outcome_have_no_raw_identity_fields(self):
        result, _ = self.read()
        result_fields = {item.name for item in fields(result)}
        self.assertFalse(result_fields & {"account", "branch_no", "name", "personal_id"})
        serialized = repr(result)
        self.assertNotIn("TEST-ACCOUNT-0001", serialized)
        self.assertNotIn("TEST-BRANCH", serialized)


if __name__ == "__main__":
    unittest.main()
