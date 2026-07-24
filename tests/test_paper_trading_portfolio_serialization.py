import json
import math
import unittest
import copy
from datetime import datetime
from typing import Any

from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedOrder,
    SimulatedFill,
    SimulatedOrderRejection,
    SimulatedTradeLogRecord,
    SimulatedTradeEventType,
    SimulatedTradeStatus,
)
from tw_stock_tool.paper_trading.portfolio_results import (
    SimulatedPortfolioPositionResult,
    SimulatedPortfolioPendingOrderResult,
    SimulatedPortfolioTradingResult,
)
from tw_stock_tool.paper_trading.portfolio_serialization import (
    serialize_simulated_portfolio_trading_result,
    deserialize_simulated_portfolio_trading_result,
    export_simulated_portfolio_trading_result_json,
    load_simulated_portfolio_trading_result_json,
)
from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult
from tw_stock_tool.paper_trading.serialization import serialize_simulated_paper_trading_result

import tw_stock_tool.paper_trading as p_export


class TestSimulatedPortfolioSerialization(unittest.TestCase):
    def setUp(self):
        self.dt = datetime(2026, 7, 10, 10, 0, 0)
        self.dt_str = "2026-07-10T10:00:00"

        self.pos1 = SimulatedPortfolioPositionResult(
            symbol="2330",
            quantity=1000,
            average_cost=100.0,
            last_price=110.0,
            market_value=110000.0,
            realized_pnl=500.0,
            unrealized_pnl=10000.0,
        )
        self.pos2 = SimulatedPortfolioPositionResult(
            symbol="2331",
            quantity=0,
            average_cost=0.0,
            last_price=None,
            market_value=0.0,
            realized_pnl=-200.0,
            unrealized_pnl=0.0,
        )
        self.pending = SimulatedPortfolioPendingOrderResult(
            order_id="O1",
            symbol="2330",
            side="BUY",
            quantity=500,
            signal_time=self.dt,
            created_at=self.dt,
            strategy="test",
            reference_price=105.0,
            reserved_buy_notional=52500.0,
        )
        self.order = SimulatedOrder(
            order_id="O1",
            symbol="2330",
            side="BUY",
            quantity=500,
            signal_time=self.dt,
            strategy="test",
            metadata={"m": "1"}
        )
        self.fill = SimulatedFill(
            order_id="O1",
            symbol="2330",
            side="BUY",
            quantity=500,
            price=105.0,
            filled_at=self.dt,
            fee=5.0,
            tax=0.0,
            slippage=10.0,
        )
        self.rejection = SimulatedOrderRejection(
            candidate_order=self.order,
            reasons=("no_cash",)
        )
        self.audit = SimulatedTradeLogRecord(
            sequence=1,
            record_id="R1",
            event_type=SimulatedTradeEventType.ACCEPTED_PENDING,
            status=SimulatedTradeStatus.PENDING_NEXT_BAR_OPEN,
            order_id="O1",
            symbol="2330",
            side="BUY",
            quantity=500,
            signal_time=self.dt,
            order_created_at=self.dt,
        )
        self.valid_result = SimulatedPortfolioTradingResult(
            initial_cash=100000.0,
            final_cash=47500.0,
            total_market_value=110000.0,
            total_equity=157500.0,
            realized_pnl=300.0,
            unrealized_pnl=10000.0,
            total_return=57500.0,
            total_return_pct=0.575,
            open_position_count=1,
            order_count=1,
            fill_count=1,
            rejection_count=1,
            audit_record_count=1,
            positions=(self.pos1, self.pos2),
            pending_orders=(self.pending,),
            orders=(self.order,),
            fills=(self.fill,),
            rejections=(self.rejection,),
            audit_log=(self.audit,),
        )

    def test_round_trip(self):
        json_str = export_simulated_portfolio_trading_result_json(self.valid_result)
        result2 = load_simulated_portfolio_trading_result_json(json_str)

        self.assertEqual(result2.initial_cash, 100000.0)
        self.assertEqual(result2.final_cash, 47500.0)
        self.assertEqual(result2.total_market_value, 110000.0)
        self.assertEqual(result2.total_equity, 157500.0)
        self.assertEqual(result2.realized_pnl, 300.0)
        self.assertEqual(result2.unrealized_pnl, 10000.0)
        self.assertEqual(result2.total_return, 57500.0)
        self.assertEqual(result2.total_return_pct, 0.575)
        self.assertEqual(result2.open_position_count, 1)
        self.assertEqual(result2.order_count, 1)
        self.assertEqual(result2.fill_count, 1)
        self.assertEqual(result2.rejection_count, 1)
        self.assertEqual(result2.audit_record_count, 1)

        self.assertEqual(len(result2.positions), 2)
        p1 = result2.positions[0]
        self.assertEqual(p1.symbol, "2330")
        self.assertEqual(p1.quantity, 1000)
        self.assertEqual(p1.last_price, 110.0)

        p2 = result2.positions[1]
        self.assertEqual(p2.symbol, "2331")
        self.assertEqual(p2.quantity, 0)
        self.assertIsNone(p2.last_price)

        self.assertEqual(len(result2.pending_orders), 1)
        po = result2.pending_orders[0]
        self.assertEqual(po.order_id, "O1")
        self.assertEqual(po.signal_time, self.dt_str)
        self.assertEqual(po.created_at, self.dt_str)

        self.assertEqual(len(result2.orders), 1)
        self.assertEqual(result2.orders[0].metadata, {"m": "1"})

    def test_optional_strategy_policy(self):
        # Accepts None, "", "   ", "strategy"
        for val in [None, "", "   ", "my_strategy"]:
            with self.subTest(val=val):
                po = copy.deepcopy(self.pending)
                object.__setattr__(po, "strategy", val)
                r = copy.copy(self.valid_result)
                object.__setattr__(r, "pending_orders", (po,))
                d = serialize_simulated_portfolio_trading_result(r)
                self.assertEqual(d["pending_orders"][0]["strategy"], val)

                des = deserialize_simulated_portfolio_trading_result(d)
                self.assertEqual(des.pending_orders[0].strategy, val)

        # Rejects non-strings: 123, True, [], {}
        for bad in [123, True, [], {}]:
            with self.subTest(bad=bad):
                po = copy.deepcopy(self.pending)
                object.__setattr__(po, "strategy", bad)
                r = copy.copy(self.valid_result)
                object.__setattr__(r, "pending_orders", (po,))
                with self.assertRaises(PaperTradingModelError):
                    serialize_simulated_portfolio_trading_result(r)

    def test_serializer_collection_validation(self):
        for field in ["positions", "pending_orders", "orders", "fills", "rejections", "audit_log"]:
            with self.subTest(field=field):
                kwargs = {f.name: getattr(self.valid_result, f.name) for f in self.valid_result.__dataclass_fields__.values()}
                kwargs[field] = []  # List instead of tuple
                r = SimulatedPortfolioTradingResult(**kwargs)
                with self.assertRaisesRegex(PaperTradingModelError, "must be a tuple"):
                    serialize_simulated_portfolio_trading_result(r)

    def test_serializer_collection_element_validation(self):
        cases = [
            ("positions", (object(),)),
            ("pending_orders", (object(),)),
            ("orders", (object(),)),
            ("fills", (object(),)),
            ("rejections", (object(),)),
            ("audit_log", (object(),)),
        ]
        for field, bad_tuple in cases:
            with self.subTest(field=field):
                r = copy.copy(self.valid_result)
                object.__setattr__(r, field, bad_tuple)
                with self.assertRaises(PaperTradingModelError):
                    serialize_simulated_portfolio_trading_result(r)

    def test_serializer_exact_string_validation(self):
        bad_strings = [123, None, "", "   ", True, [], {}]
        for bad in bad_strings:
            with self.subTest(bad=bad):
                p = copy.deepcopy(self.pos1)
                object.__setattr__(p, "symbol", bad)
                r = copy.copy(self.valid_result)
                object.__setattr__(r, "positions", (p, self.pos2))
                with self.assertRaises(PaperTradingModelError):
                    serialize_simulated_portfolio_trading_result(r)

                po = copy.deepcopy(self.pending)
                object.__setattr__(po, "order_id", bad)
                r = copy.copy(self.valid_result)
                object.__setattr__(r, "pending_orders", (po,))
                with self.assertRaises(PaperTradingModelError):
                    serialize_simulated_portfolio_trading_result(r)

                po = copy.deepcopy(self.pending)
                object.__setattr__(po, "symbol", bad)
                r = copy.copy(self.valid_result)
                object.__setattr__(r, "pending_orders", (po,))
                with self.assertRaises(PaperTradingModelError):
                    serialize_simulated_portfolio_trading_result(r)

                po = copy.deepcopy(self.pending)
                object.__setattr__(po, "side", bad)
                r = copy.copy(self.valid_result)
                object.__setattr__(r, "pending_orders", (po,))
                with self.assertRaises(PaperTradingModelError):
                    serialize_simulated_portfolio_trading_result(r)

    def test_serializer_exact_int_validation(self):
        bad_ints = [True, False, 1.0, 1.5, "1"]
        for bad in bad_ints:
            with self.subTest(bad=bad):
                p = copy.deepcopy(self.pos1)
                object.__setattr__(p, "quantity", bad)
                r = copy.copy(self.valid_result)
                object.__setattr__(r, "positions", (p, self.pos2))
                with self.assertRaises(PaperTradingModelError):
                    serialize_simulated_portfolio_trading_result(r)

                po = copy.deepcopy(self.pending)
                object.__setattr__(po, "quantity", bad)
                r = copy.copy(self.valid_result)
                object.__setattr__(r, "pending_orders", (po,))
                with self.assertRaises(PaperTradingModelError):
                    serialize_simulated_portfolio_trading_result(r)

    def test_exact_count_matrix(self):
        invalid_counts = [True, False, 1.0, 1.5, "1", -1]
        fields = ["open_position_count", "order_count", "fill_count", "rejection_count", "audit_record_count"]
        for field in fields:
            for bad in invalid_counts:
                with self.subTest(field=field, bad=bad):
                    # Serializer test
                    r = copy.copy(self.valid_result)
                    object.__setattr__(r, field, bad)
                    with self.assertRaises(PaperTradingModelError):
                        serialize_simulated_portfolio_trading_result(r)

                    # Deserializer test
                    d = serialize_simulated_portfolio_trading_result(self.valid_result)
                    d[field] = bad
                    with self.assertRaises(PaperTradingModelError):
                        deserialize_simulated_portfolio_trading_result(d)

    def test_huge_integer_validation(self):
        huge = 10**1000
        # Serializer check
        fields_to_test = [
            ("initial_cash", huge),
        ]
        for field, val in fields_to_test:
            with self.subTest(field=field):
                r = copy.copy(self.valid_result)
                object.__setattr__(r, field, val)
                with self.assertRaises(PaperTradingModelError):
                    serialize_simulated_portfolio_trading_result(r)

        # Position average_cost
        p = copy.deepcopy(self.pos1)
        object.__setattr__(p, "average_cost", huge)
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "positions", (p, self.pos2))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # Position last_price
        p = copy.deepcopy(self.pos1)
        object.__setattr__(p, "last_price", huge)
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "positions", (p, self.pos2))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # Pending reference_price & reserved_buy_notional
        po = copy.deepcopy(self.pending)
        object.__setattr__(po, "reference_price", huge)
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "pending_orders", (po,))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        po = copy.deepcopy(self.pending)
        object.__setattr__(po, "reserved_buy_notional", huge)
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "pending_orders", (po,))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # Deserializer check
        d = serialize_simulated_portfolio_trading_result(self.valid_result)
        d["initial_cash"] = huge
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result(d)

    def test_position_invariants(self):
        # open position average_cost == 0
        p = copy.deepcopy(self.pos1)
        object.__setattr__(p, "average_cost", 0.0)
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "positions", (p, self.pos2))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # open position last_price is None
        p = copy.deepcopy(self.pos1)
        object.__setattr__(p, "last_price", None)
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "positions", (p, self.pos2))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # closed position average_cost != 0
        p = copy.deepcopy(self.pos2)
        object.__setattr__(p, "average_cost", 10.0)
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "positions", (self.pos1, p))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # closed position last_price is not None
        p = copy.deepcopy(self.pos2)
        object.__setattr__(p, "last_price", 10.0)
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "positions", (self.pos1, p))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # closed position market_value != 0
        p = copy.deepcopy(self.pos2)
        object.__setattr__(p, "market_value", 100.0)
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "positions", (self.pos1, p))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # closed position unrealized_pnl != 0
        p = copy.deepcopy(self.pos2)
        object.__setattr__(p, "unrealized_pnl", 50.0)
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "positions", (self.pos1, p))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # positions unsorted
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "positions", (self.pos2, self.pos1))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # duplicate symbol
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "positions", (self.pos1, self.pos1))
        object.__setattr__(r, "open_position_count", 2)
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # symbol blank or whitespace
        for bad_sym in ["", "   ", 123, None]:
            p = copy.deepcopy(self.pos1)
            object.__setattr__(p, "symbol", bad_sym)
            r = copy.copy(self.valid_result)
            object.__setattr__(r, "positions", (p, self.pos2))
            with self.assertRaises(PaperTradingModelError):
                serialize_simulated_portfolio_trading_result(r)

    def test_pending_invariants(self):
        # SELL reservation nonzero
        p = copy.deepcopy(self.pending)
        object.__setattr__(p, "side", "SELL")
        object.__setattr__(p, "reserved_buy_notional", 100.0)
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "pending_orders", (p,))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # quantity <= 0, bool, float
        for bad_q in [0, -1, True, 1.5]:
            p = copy.deepcopy(self.pending)
            object.__setattr__(p, "quantity", bad_q)
            r = copy.copy(self.valid_result)
            object.__setattr__(r, "pending_orders", (p,))
            with self.assertRaises(PaperTradingModelError):
                serialize_simulated_portfolio_trading_result(r)

        # deserializer timestamp type check
        d = serialize_simulated_portfolio_trading_result(self.valid_result)
        d["pending_orders"][0]["signal_time"] = 123
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result(d)

        d = serialize_simulated_portfolio_trading_result(self.valid_result)
        d["pending_orders"][0]["created_at"] = 123
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result(d)

    def test_audit_log_validation(self):
        # wrong record type
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "audit_log", (object(),))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # invalid sequence (bool, <= 0)
        for bad_seq in [True, 0, -1, 1.5]:
            a = copy.copy(self.audit)
            object.__setattr__(a, "sequence", bad_seq)
            r = copy.copy(self.valid_result)
            object.__setattr__(r, "audit_log", (a,))
            with self.assertRaises(PaperTradingModelError):
                serialize_simulated_portfolio_trading_result(r)

        # risk_allowed invalid type (e.g. 0, 1, "true")
        for bad_risk in [0, 1, "true"]:
            a = copy.copy(self.audit)
            object.__setattr__(a, "risk_allowed", bad_risk)
            r = copy.copy(self.valid_result)
            object.__setattr__(r, "audit_log", (a,))
            with self.assertRaises(PaperTradingModelError):
                serialize_simulated_portfolio_trading_result(r)

        # risk_rejection_reasons non-tuple or blank reason
        a = copy.copy(self.audit)
        object.__setattr__(a, "risk_rejection_reasons", ["reason"])  # list instead of tuple
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "audit_log", (a,))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        a = copy.copy(self.audit)
        object.__setattr__(a, "risk_rejection_reasons", ("",))
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "audit_log", (a,))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

    def test_malformed_event_payloads(self):
        d = serialize_simulated_portfolio_trading_result(self.valid_result)

        # Order payload missing / extra field
        bad_d = copy.deepcopy(d)
        bad_d["orders"][0] = "not_a_dict"
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result(bad_d)

        bad_d = copy.deepcopy(d)
        del bad_d["orders"][0]["order_id"]
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result(bad_d)

        bad_d = copy.deepcopy(d)
        bad_d["orders"][0]["extra"] = 1
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result(bad_d)

        # Fill payload not dict
        bad_d = copy.deepcopy(d)
        bad_d["fills"][0] = 123
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result(bad_d)

        # Rejection payload not dict
        bad_d = copy.deepcopy(d)
        bad_d["rejections"][0] = 123
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result(bad_d)

        # Audit payload not dict
        bad_d = copy.deepcopy(d)
        bad_d["audit_log"][0] = 123
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result(bad_d)

    def test_exact_schema_shape_and_payload_keys(self):
        data = serialize_simulated_portfolio_trading_result(self.valid_result)
        expected_keys = {
            "schema_version", "result_type", "initial_cash", "final_cash",
            "total_market_value", "total_equity", "realized_pnl", "unrealized_pnl",
            "total_return", "total_return_pct", "open_position_count",
            "order_count", "fill_count", "rejection_count", "audit_record_count",
            "positions", "pending_orders", "orders", "fills", "rejections", "audit_log"
        }
        self.assertEqual(set(data.keys()), expected_keys)

        # Compare aggregate event item keys with single-symbol schema v3 event item keys
        single_res = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=100000.0,
            final_cash=47500.0,
            final_position_quantity=500,
            average_cost=100.0,
            realized_pnl=0.0,
            unrealized_pnl=2500.0,
            total_equity=100000.0,
            order_count=1,
            fill_count=1,
            open_position_count=1,
            orders=(self.order,),
            fills=(self.fill,),
            rejections=(self.rejection,),
            audit_log=(self.audit,),
        )
        single_data = serialize_simulated_paper_trading_result(single_res)

        self.assertEqual(set(data["orders"][0].keys()), set(single_data["orders"][0].keys()))
        self.assertEqual(set(data["fills"][0].keys()), set(single_data["fills"][0].keys()))
        self.assertEqual(set(data["rejections"][0].keys()), set(single_data["rejections"][0].keys()))
        self.assertEqual(set(data["audit_log"][0].keys()), set(single_data["audit_log"][0].keys()))

    def test_mutation(self):
        r1 = self.valid_result
        data = serialize_simulated_portfolio_trading_result(r1)

        # Verify no mutation on input result
        self.assertEqual(r1.positions[0].quantity, 1000)
        self.assertEqual(id(r1.orders[0]), id(self.order))
        self.assertEqual(id(r1.positions), id(self.valid_result.positions))
        self.assertEqual(id(r1.pending_orders), id(self.valid_result.pending_orders))
        self.assertEqual(id(r1.orders), id(self.valid_result.orders))

        data_copy = copy.deepcopy(data)
        r2 = deserialize_simulated_portfolio_trading_result(data_copy)
        self.assertEqual(data, data_copy)

    def test_compatibility(self):
        self.assertFalse(hasattr(p_export, "serialize_simulated_portfolio_trading_result"))
        self.assertFalse(hasattr(p_export, "deserialize_simulated_portfolio_trading_result"))
        self.assertFalse(hasattr(p_export, "export_simulated_portfolio_trading_result_json"))
        self.assertFalse(hasattr(p_export, "load_simulated_portfolio_trading_result_json"))


if __name__ == "__main__":
    unittest.main()
