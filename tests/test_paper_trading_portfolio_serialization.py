import json
import math
import unittest
from datetime import datetime

from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedOrder,
    SimulatedFill,
    SimulatedOrderRejection,
    SimulatedTradeEventType,
    SimulatedTradeStatus,
    SimulatedTradeLogRecord,
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
from tw_stock_tool.paper_trading.serialization import (
    serialize_simulated_paper_trading_result,
)
from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult


class TestSimulatedPortfolioSerialization(unittest.TestCase):
    def setUp(self):
        self.dt = datetime(2025, 1, 1, 10, 0, 0)
        self.order1 = SimulatedOrder("O1", "2330", "BUY", 1000, self.dt, self.dt, "strategy1", {"k": "v"})
        self.fill1 = SimulatedFill("O1", "2330", "BUY", 1000, 500.0, self.dt, 1.0, 2.0, 3.0)
        self.rej1 = SimulatedOrderRejection(self.order1, ("reason1",))
        self.record1 = SimulatedTradeLogRecord(
            sequence=1,
            record_id="rec1",
            event_type=SimulatedTradeEventType.CANDIDATE_CREATED,
            status=SimulatedTradeStatus.CANDIDATE,
            order_id="O1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            signal_time=self.dt,
            order_created_at=self.dt,
            expected_execution_model="next_bar_open",
            fill_time=self.dt,
            fill_price=500.0,
            fee=1.0,
            tax=2.0,
            slippage=3.0,
            strategy_name="strategy1",
            strategy_metadata={"k": "v"},
            risk_allowed=True,
            risk_rejection_reasons=("reason1",),
            guard_metadata={"g": "v"},
            error_code="E1",
            error_message="msg",
        )

        self.pos1 = SimulatedPortfolioPositionResult("2317", 0, 0.0, None, 0.0, -100.0, 0.0)
        self.pos2 = SimulatedPortfolioPositionResult("2330", 1000, 500.0, 600.0, 600000.0, 0.0, 100000.0)
        
        self.pend1 = SimulatedPortfolioPendingOrderResult("O2", "2317", "SELL", 500, self.dt, self.dt, "strat", 100.0, 0.0)
        self.pend2 = SimulatedPortfolioPendingOrderResult("O1", "2330", "BUY", 1000, self.dt, self.dt, None, 600.0, 600000.0)

        self.valid_result = SimulatedPortfolioTradingResult(
            initial_cash=100000.0,
            final_cash=150000.0,
            total_market_value=600000.0,
            total_equity=750000.0,
            realized_pnl=-100.0,
            unrealized_pnl=100000.0,
            total_return=650000.0,
            total_return_pct=6.5,
            open_position_count=1,
            order_count=1,
            fill_count=1,
            rejection_count=1,
            audit_record_count=1,
            positions=(self.pos1, self.pos2),
            pending_orders=(self.pend1, self.pend2),
            orders=(self.order1,),
            fills=(self.fill1,),
            rejections=(self.rej1,),
            audit_log=(self.record1,),
        )

    def test_basic_serialization(self):
        data = serialize_simulated_portfolio_trading_result(self.valid_result)
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["result_type"], "simulated_portfolio_trading_result")
        self.assertEqual(data["open_position_count"], 1)
        self.assertEqual(len(data["positions"]), 2)
        self.assertEqual(len(data["pending_orders"]), 2)
        
        # Check canonical ordering in data is retained
        self.assertEqual(data["positions"][0]["symbol"], "2317")
        self.assertEqual(data["positions"][1]["symbol"], "2330")

        self.assertEqual(data["pending_orders"][0]["symbol"], "2317")
        self.assertEqual(data["pending_orders"][0]["order_id"], "O2")
        self.assertEqual(data["pending_orders"][1]["symbol"], "2330")
        self.assertEqual(data["pending_orders"][1]["order_id"], "O1")

    def test_round_trip(self):
        data1 = serialize_simulated_portfolio_trading_result(self.valid_result)
        res1 = deserialize_simulated_portfolio_trading_result(data1)
        data2 = serialize_simulated_portfolio_trading_result(res1)
        self.assertEqual(data1, data2)
        
        json_str = export_simulated_portfolio_trading_result_json(self.valid_result)
        res2 = load_simulated_portfolio_trading_result_json(json_str)
        data3 = serialize_simulated_portfolio_trading_result(res2)
        self.assertEqual(data1, data3)

    def test_strict_top_level_validation(self):
        with self.assertRaises(PaperTradingModelError):
            serialize_simulated_portfolio_trading_result(object())
            
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result([])

        data = serialize_simulated_portfolio_trading_result(self.valid_result)
        
        invalid_versions = [True, False, 1.0, "1", 0, 2, None]
        for v in invalid_versions:
            d2 = data.copy()
            d2["schema_version"] = v
            with self.assertRaises(PaperTradingModelError):
                deserialize_simulated_portfolio_trading_result(d2)

        d_wrong_type = data.copy()
        d_wrong_type["result_type"] = "other_type"
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result(d_wrong_type)

        d_missing = data.copy()
        del d_missing["initial_cash"]
        with self.assertRaisesRegex(PaperTradingModelError, "Missing required top-level fields"):
            deserialize_simulated_portfolio_trading_result(d_missing)

        d_extra = data.copy()
        d_extra["extra_key"] = 123
        with self.assertRaisesRegex(PaperTradingModelError, "Extra unknown top-level fields"):
            deserialize_simulated_portfolio_trading_result(d_extra)

        for col in ["positions", "pending_orders", "orders", "fills", "rejections", "audit_log"]:
            d_col = data.copy()
            d_col[col] = {}
            with self.assertRaisesRegex(PaperTradingModelError, "must be a list"):
                deserialize_simulated_portfolio_trading_result(d_col)

    def test_numeric_validation(self):
        data = serialize_simulated_portfolio_trading_result(self.valid_result)
        invalid_nums = [True, "100", math.nan, math.inf, -math.inf]
        
        for num in invalid_nums:
            with self.subTest(num=num):
                d = json.loads(json.dumps(data))
                d["initial_cash"] = num
                with self.assertRaises(PaperTradingModelError):
                    deserialize_simulated_portfolio_trading_result(d)
                    
                d = json.loads(json.dumps(data))
                d["open_position_count"] = num
                with self.assertRaises(PaperTradingModelError):
                    deserialize_simulated_portfolio_trading_result(d)

                d = json.loads(json.dumps(data))
                d["positions"][1]["quantity"] = num
                with self.assertRaises(PaperTradingModelError):
                    deserialize_simulated_portfolio_trading_result(d)

        # Huge int causing float overflow is tricky via JSON, but we can test object creation
        d_huge = data.copy()
        d_huge["initial_cash"] = 10**1000
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_portfolio_trading_result(d_huge)

    def test_position_invariants(self):
        data = serialize_simulated_portfolio_trading_result(self.valid_result)
        
        # open pos avg cost zero
        d = json.loads(json.dumps(data))
        d["positions"][1]["average_cost"] = 0.0
        with self.assertRaisesRegex(PaperTradingModelError, "must have positive average_cost"):
            deserialize_simulated_portfolio_trading_result(d)

        # duplicate symbols
        d = json.loads(json.dumps(data))
        d["positions"][0]["symbol"] = "2330"
        with self.assertRaisesRegex(PaperTradingModelError, "canonically sorted"):
            deserialize_simulated_portfolio_trading_result(d)

        # closed pos with non-zero average cost
        d = json.loads(json.dumps(data))
        d["positions"][0]["average_cost"] = 100.0
        with self.assertRaisesRegex(PaperTradingModelError, "average_cost == 0.0"):
            deserialize_simulated_portfolio_trading_result(d)

    def test_pending_invariants(self):
        data = serialize_simulated_portfolio_trading_result(self.valid_result)
        
        d = json.loads(json.dumps(data))
        d["pending_orders"][0]["side"] = "HOLD"
        with self.assertRaisesRegex(PaperTradingModelError, "invalid side"):
            deserialize_simulated_portfolio_trading_result(d)

        d = json.loads(json.dumps(data))
        d["pending_orders"][0]["reserved_buy_notional"] = 100.0
        with self.assertRaisesRegex(PaperTradingModelError, "reserved_buy_notional == 0.0"):
            deserialize_simulated_portfolio_trading_result(d)

    def test_counts_validation(self):
        data = serialize_simulated_portfolio_trading_result(self.valid_result)
        
        d = json.loads(json.dumps(data))
        d["open_position_count"] = 99
        with self.assertRaisesRegex(PaperTradingModelError, "does not match actual"):
            deserialize_simulated_portfolio_trading_result(d)

        d = json.loads(json.dumps(data))
        d["order_count"] = 99
        with self.assertRaisesRegex(PaperTradingModelError, "does not match"):
            deserialize_simulated_portfolio_trading_result(d)

    def test_existing_compatibility(self):
        # single schema v3 unchanged
        single_res = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=100.0,
            final_cash=100.0,
            final_position_quantity=0,
            average_cost=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            total_equity=100.0,
            order_count=0,
            fill_count=0,
            open_position_count=0,
            orders=(),
            fills=(),
            rejections=(),
            audit_log=()
        )
        data = serialize_simulated_paper_trading_result(single_res)
        self.assertEqual(data["schema_version"], 3)
        self.assertEqual(data["result_type"], "simulated_paper_trading_result")

    def test_source_mutation(self):
        orig_pos_id = id(self.valid_result.positions)
        orig_pend_id = id(self.valid_result.pending_orders)
        
        serialize_simulated_portfolio_trading_result(self.valid_result)
        
        self.assertEqual(id(self.valid_result.positions), orig_pos_id)
        self.assertEqual(id(self.valid_result.pending_orders), orig_pend_id)

    def test_json_errors(self):
        with self.assertRaises(PaperTradingModelError):
            load_simulated_portfolio_trading_result_json("{invalid_json: true")
        with self.assertRaises(PaperTradingModelError):
            load_simulated_portfolio_trading_result_json("[]")
            
        with self.assertRaises(PaperTradingModelError):
            load_simulated_portfolio_trading_result_json(123)

if __name__ == '__main__':
    unittest.main()
