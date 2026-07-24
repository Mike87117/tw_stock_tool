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

    def test_serializer_collection_validation(self):
        for field in ["positions", "pending_orders", "orders", "fills", "rejections", "audit_log"]:
            with self.subTest(field=field):
                kwargs = {f.name: getattr(self.valid_result, f.name) for f in self.valid_result.__dataclass_fields__.values()}
                kwargs[field] = []  # List instead of tuple
                r = SimulatedPortfolioTradingResult(**kwargs)
                with self.assertRaisesRegex(PaperTradingModelError, "must be a tuple"):
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

                if bad is not None:
                    po = copy.deepcopy(self.pending)
                    object.__setattr__(po, "strategy", bad)
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
                
                r = copy.copy(self.valid_result)
                object.__setattr__(r, "open_position_count", bad)
                with self.assertRaises(PaperTradingModelError):
                    serialize_simulated_portfolio_trading_result(r)

    def test_serializer_numeric_domain_validation(self):
        bad_floats = [-100.0, math.nan, math.inf, -math.inf, "100"]
        for field in ["initial_cash", "final_cash", "total_market_value", "total_equity"]:
            for bad in bad_floats:
                with self.subTest(field=field, bad=bad):
                    r = copy.copy(self.valid_result)
                    object.__setattr__(r, field, bad)
                    with self.assertRaises(PaperTradingModelError):
                        serialize_simulated_portfolio_trading_result(r)
                        
        r = copy.copy(self.valid_result)
        try:
            val = float(10**1000)
        except OverflowError:
            pass
        else:
            object.__setattr__(r, "initial_cash", val)
            with self.assertRaises(PaperTradingModelError):
                serialize_simulated_portfolio_trading_result(r)

    def test_serializer_position_invariants(self):
        # Unsorted
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "positions", (self.pos2, self.pos1))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # Duplicate
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "positions", (self.pos1, self.pos1))
        object.__setattr__(r, "open_position_count", 2)
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # Open avg cost zero
        p = copy.deepcopy(self.pos1)
        object.__setattr__(p, "average_cost", 0.0)
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "positions", (p, self.pos2))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # Closed avg cost nonzero
        p = copy.deepcopy(self.pos2)
        object.__setattr__(p, "average_cost", 10.0)
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "positions", (self.pos1, p))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

    def test_serializer_pending_invariants(self):
        # Unsorted pending
        p2 = copy.deepcopy(self.pending)
        object.__setattr__(p2, "order_id", "A1") # Before O1
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "pending_orders", (self.pending, p2))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # invalid side
        p = copy.deepcopy(self.pending)
        object.__setattr__(p, "side", "HOLD")
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "pending_orders", (p,))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)
            
        # zero quantity
        p = copy.deepcopy(self.pending)
        object.__setattr__(p, "quantity", 0)
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "pending_orders", (p,))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)
            
        # SELL nonzero reservation
        p = copy.deepcopy(self.pending)
        object.__setattr__(p, "side", "SELL")
        object.__setattr__(p, "reserved_buy_notional", 100.0)
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "pending_orders", (p,))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

    def test_serializer_count_mismatches(self):
        for field in ["open_position_count", "order_count", "fill_count", "rejection_count", "audit_record_count"]:
            with self.subTest(field=field):
                r = copy.copy(self.valid_result)
                object.__setattr__(r, field, 999)
                with self.assertRaises(PaperTradingModelError):
                    serialize_simulated_portfolio_trading_result(r)

    def test_deserializer_exact_type_validation(self):
        data = serialize_simulated_portfolio_trading_result(self.valid_result)
        
        bad_data = copy.deepcopy(data)
        bad_data["positions"][0]["symbol"] = "   "
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result(bad_data)

        bad_data = copy.deepcopy(data)
        bad_data["positions"][0]["quantity"] = 1.0
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result(bad_data)

        bad_data = copy.deepcopy(data)
        bad_data["pending_orders"][0]["signal_time"] = 123
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result(bad_data)

        bad_data = copy.deepcopy(data)
        bad_data["initial_cash"] = -100.0
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result(bad_data)

    def test_event_tests(self):
        # wrong order type in tuple
        r = copy.copy(self.valid_result)
        object.__setattr__(r, "orders", (self.fill,))
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)

        # mutable order invalid ID
        r = copy.copy(self.valid_result)
        self.order.order_id = ""
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)
        self.order.order_id = "O1"

        # NaN metadata
        self.order.metadata = {"val": math.nan}
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)
        self.order.metadata = {"m": "1"}

        # non-dict metadata
        self.order.metadata = []
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(r)
        self.order.metadata = {"m": "1"}

    def test_exact_schema_shape(self):
        data = serialize_simulated_portfolio_trading_result(self.valid_result)
        expected_keys = {
            "schema_version", "result_type", "initial_cash", "final_cash",
            "total_market_value", "total_equity", "realized_pnl", "unrealized_pnl",
            "total_return", "total_return_pct", "open_position_count",
            "order_count", "fill_count", "rejection_count", "audit_record_count",
            "positions", "pending_orders", "orders", "fills", "rejections", "audit_log"
        }
        self.assertEqual(set(data.keys()), expected_keys)
        
        bad_data = copy.deepcopy(data)
        bad_data["extra_field"] = 1
        with self.assertRaisesRegex(PaperTradingModelError, "Extra unknown top-level fields"):
            deserialize_simulated_portfolio_trading_result(bad_data)

        bad_data = copy.deepcopy(data)
        del bad_data["initial_cash"]
        with self.assertRaisesRegex(PaperTradingModelError, "Missing required top-level fields"):
            deserialize_simulated_portfolio_trading_result(bad_data)

    def test_mutation(self):
        r1 = self.valid_result
        data = serialize_simulated_portfolio_trading_result(r1)
        # Verify no mutation
        self.assertEqual(r1.positions[0].quantity, 1000)
        self.assertEqual(id(r1.orders[0]), id(self.order))
        
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
