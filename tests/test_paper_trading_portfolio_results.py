"""
Tests for multi-symbol simulated portfolio results.
"""

import math
import unittest
from datetime import datetime

from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedFill,
    SimulatedOrder,
    SimulatedOrderRejection,
    SimulatedPosition,
    SimulatedPortfolio,
    SimulatedTradeEventType,
    SimulatedTradeStatus,
)
from tw_stock_tool.paper_trading.runtime import (
    SimulatedPaperTradingRuntimeState,
    SimulatedPendingOrderState,
)
from tw_stock_tool.paper_trading.portfolio_results import (
    SimulatedPortfolioPositionResult,
    SimulatedPortfolioPendingOrderResult,
    SimulatedPortfolioTradingResult,
    build_simulated_portfolio_trading_result,
)


from collections.abc import Mapping

class CustomMapping(Mapping):
    def __init__(self, data):
        self._data = data
    def __getitem__(self, key):
        return self._data[key]
    def __iter__(self):
        return iter(self._data)
    def __len__(self):
        return len(self._data)



class TestSimulatedPortfolioResults(unittest.TestCase):

    def setUp(self):
        self.portfolio = SimulatedPortfolio(cash=100000.0)
        self.runtime_state = SimulatedPaperTradingRuntimeState(
            portfolio=self.portfolio,
            pending_orders={}
        )
        self.dt = datetime(2025, 1, 1)

    def test_dataclasses_frozen_slots(self):
        pos_res = SimulatedPortfolioPositionResult("2330", 1, 100.0, 100.0, 100.0, 0.0, 0.0)
        with self.assertRaises(AttributeError):
            pos_res.symbol = "2317"
            
        pend_res = SimulatedPortfolioPendingOrderResult("O1", "2330", "BUY", 1, self.dt, None, None, 100.0, 100.0)
        with self.assertRaises(AttributeError):
            pend_res.symbol = "2317"
            
        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=100000.0, last_prices={}
        )
        with self.assertRaises(AttributeError):
            res.total_equity = 0.0

    def test_construction_empty_portfolio(self):
        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=0.0, last_prices={}
        )
        self.assertEqual(res.initial_cash, 0.0)
        self.assertEqual(res.final_cash, 100000.0)
        self.assertEqual(res.total_market_value, 0.0)
        self.assertEqual(res.total_equity, 100000.0)
        self.assertEqual(res.total_return, 100000.0)
        self.assertEqual(res.open_position_count, 0)
        self.assertEqual(len(res.positions), 0)

    def test_construction_cash_only(self):
        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=100000.0, last_prices={"2330": 600.0}
        )
        self.assertEqual(res.initial_cash, 100000.0)
        self.assertEqual(res.final_cash, 100000.0)
        self.assertEqual(res.total_equity, 100000.0)
        self.assertEqual(res.total_return, 0.0)
        self.assertEqual(res.total_return_pct, 0.0)

    def test_construction_one_open_position(self):
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 1000, 500.0, 0.0)
        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=500000.0, last_prices={"2330": 600.0}
        )
        self.assertEqual(res.total_market_value, 600000.0)
        self.assertEqual(res.total_equity, 700000.0)
        self.assertEqual(res.unrealized_pnl, 100000.0)
        self.assertEqual(res.open_position_count, 1)

    def test_construction_multiple_open_positions(self):
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 1000, 500.0, 0.0)
        self.portfolio.positions["2317"] = SimulatedPosition("2317", 2000, 100.0, 0.0)
        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=700000.0, last_prices={"2330": 600.0, "2317": 110.0}
        )
        self.assertEqual(res.total_market_value, 600000.0 + 220000.0)
        self.assertEqual(res.unrealized_pnl, 100000.0 + 20000.0)
        self.assertEqual(res.open_position_count, 2)

    def test_construction_one_closed_position_with_realized_pnl(self):
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 0, 0.0, 5000.0)
        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=100000.0, last_prices={}
        )
        self.assertEqual(len(res.positions), 1)
        self.assertEqual(res.positions[0].symbol, "2330")
        self.assertEqual(res.positions[0].last_price, None)
        self.assertEqual(res.positions[0].realized_pnl, 5000.0)
        self.assertEqual(res.realized_pnl, 5000.0)
        self.assertEqual(res.total_market_value, 0.0)

    def test_construction_mixed_open_and_closed_positions(self):
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 0, 0.0, 5000.0)
        self.portfolio.positions["2317"] = SimulatedPosition("2317", 1000, 100.0, 200.0)
        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=100000.0, last_prices={"2317": 110.0}
        )
        self.assertEqual(len(res.positions), 2)
        self.assertEqual(res.positions[0].symbol, "2317")
        self.assertEqual(res.positions[1].symbol, "2330")
        self.assertEqual(res.realized_pnl, 5200.0)
        self.assertEqual(res.unrealized_pnl, 10000.0)

    def test_deterministic_symbol_ordering(self):
        self.portfolio.positions["Z"] = SimulatedPosition("Z", 1, 10.0, 0.0)
        self.portfolio.positions["A"] = SimulatedPosition("A", 1, 10.0, 0.0)
        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=100000.0, last_prices={"A": 10.0, "Z": 10.0}
        )
        self.assertEqual(res.positions[0].symbol, "A")
        self.assertEqual(res.positions[1].symbol, "Z")

    def test_rejected_only_symbol_not_fabricated(self):
        # We test that symbols not in portfolio.positions are not created
        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=100000.0, last_prices={"2330": 600.0}
        )
        self.assertEqual(len(res.positions), 0)

    def test_initial_cash_validation(self):
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=True, last_prices={})
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash="100", last_prices={})
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=-1.0, last_prices={})
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=math.nan, last_prices={})
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=math.inf, last_prices={})

    def test_portfolio_cash_validation(self):
        self.portfolio.cash = -1.0
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100.0, last_prices={})
        self.portfolio.cash = float("nan")
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100.0, last_prices={})

    def test_last_prices_validation(self):
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 1000, 500.0, 0.0)
        
        # extra prices allowed
        build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=100000.0, last_prices={"2330": 600.0, "2317": 100.0}
        )
        
        # custom mapping
        cm = CustomMapping({"2330": 600.0})
        build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices=cm)

        # missing price
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices={})
            
        # extra invalid price
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(
                self.runtime_state, initial_cash=100000.0, last_prices={"2330": 600.0, "2317": -10.0}
            )
            
        # bad keys and values
        bad_prices = [
            ({"": 100.0}, "blank key"),
            ({123: 100.0}, "non string key"),
            ({"2330": True}, "bool price"),
            ({"2330": "600"}, "string price"),
            ({"2330": math.nan}, "nan"),
            ({"2330": math.inf}, "inf"),
            ({"2330": 0.0}, "zero"),
            ({"2330": -1.0}, "negative"),
        ]
        for bp, msg in bad_prices:
            with self.assertRaises(PaperTradingModelError, msg=msg):
                build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices=bp)

    def test_position_validation(self):
        # key mismatch
        self.portfolio.positions["2317"] = SimulatedPosition("2330", 1, 10.0, 0.0)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices={"2330": 10.0, "2317": 10.0})
        self.portfolio.positions.clear()

        # blank symbol
        self.portfolio.positions[""] = SimulatedPosition("", 1, 10.0, 0.0)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices={"": 10.0})
        self.portfolio.positions.clear()

        # bool quantity
        self.portfolio.positions["2330"] = SimulatedPosition("2330", True, 10.0, 0.0)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices={"2330": 10.0})
        self.portfolio.positions.clear()

        # negative avg cost
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 1, -10.0, 0.0)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices={"2330": 10.0})
        self.portfolio.positions.clear()
        
        # open position zero average cost
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 1, 0.0, 0.0)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices={"2330": 10.0})
        self.portfolio.positions.clear()

        # closed position non-zero average cost
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 0, 10.0, 0.0)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices={"2330": 10.0})
        self.portfolio.positions.clear()
        
        # negative realized PnL accepted
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 0, 0.0, -500.0)
        res = build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices={"2330": 10.0})
        self.assertEqual(res.realized_pnl, -500.0)

    def test_metrics(self):
        self.portfolio.cash = 50000.0
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 1000, 500.0, -100.0)
        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=100000.0, last_prices={"2330": 600.0}
        )
        self.assertEqual(res.total_market_value, 600000.0)
        self.assertEqual(res.total_equity, 650000.0)
        self.assertEqual(res.realized_pnl, -100.0)
        self.assertEqual(res.unrealized_pnl, 100000.0)
        self.assertEqual(res.total_return, 550000.0)
        self.assertEqual(res.total_return_pct, 5.5)

        # Initial cash zero
        res_zero = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=0.0, last_prices={"2330": 600.0}
        )
        self.assertIsNone(res_zero.total_return_pct)

    def test_pending_orders(self):
        order1 = SimulatedOrder("O1", "2330", "BUY", 1000, self.dt)
        order2 = SimulatedOrder("O2", "2317", "SELL", 2000, self.dt)
        
        self.runtime_state.pending_orders["2330"] = SimulatedPendingOrderState(order1, 600.0)
        self.runtime_state.pending_orders["2317"] = SimulatedPendingOrderState(order2, 100.0)

        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=100000.0, last_prices={"2330": 600.0, "2317": 100.0}
        )

        self.assertEqual(len(res.pending_orders), 2)
        # ordering by symbol, order_id
        self.assertEqual(res.pending_orders[0].symbol, "2317")
        self.assertEqual(res.pending_orders[1].symbol, "2330")

        self.assertEqual(res.pending_orders[0].reserved_buy_notional, 0.0)
        self.assertEqual(res.pending_orders[1].reserved_buy_notional, 600000.0)
        
        # pending reservation not included in total equity
        self.assertEqual(res.total_equity, 100000.0)

    def test_pending_validation(self):
        # invalid pending dictionary key
        order1 = SimulatedOrder("O1", "2330", "BUY", 1000, self.dt)
        self.runtime_state.pending_orders[""] = SimulatedPendingOrderState(order1, 600.0)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices={})
        self.runtime_state.pending_orders.clear()

        # key/order symbol mismatch
        self.runtime_state.pending_orders["2317"] = SimulatedPendingOrderState(order1, 600.0)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices={})
        self.runtime_state.pending_orders.clear()
        
    def test_mutation_and_identity(self):
        order = SimulatedOrder("O1", "2330", "BUY", 1000, self.dt)
        fill = SimulatedFill("O1", "2330", "BUY", 1000, 500.0, self.dt)
        rej = SimulatedOrderRejection(order, ("reason",))
        self.portfolio.trade_log.record_order(order)
        self.portfolio.trade_log.record_fill(fill)
        self.portfolio.trade_log.record_rejection(rej)
        self.portfolio.trade_log.record_event(order, SimulatedTradeEventType.CANDIDATE_CREATED, SimulatedTradeStatus.CANDIDATE)

        self.portfolio.positions["2330"] = SimulatedPosition("2330", 1000, 500.0, 0.0)
        self.runtime_state.pending_orders["2330"] = SimulatedPendingOrderState(order, 500.0)

        prices = {"2330": 600.0}
        
        orig_runtime_id = id(self.runtime_state)
        orig_portfolio_id = id(self.portfolio)
        orig_positions_id = id(self.portfolio.positions)
        orig_pending_id = id(self.runtime_state.pending_orders)
        orig_orders_id = id(self.portfolio.trade_log.orders)

        res1 = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=100000.0, last_prices=prices
        )
        res2 = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=100000.0, last_prices=prices
        )

        self.assertEqual(id(self.runtime_state), orig_runtime_id)
        self.assertEqual(id(self.portfolio), orig_portfolio_id)
        self.assertEqual(id(self.portfolio.positions), orig_positions_id)
        self.assertEqual(id(self.runtime_state.pending_orders), orig_pending_id)
        self.assertEqual(id(self.portfolio.trade_log.orders), orig_orders_id)
        
        self.assertEqual(prices, {"2330": 600.0})
        self.assertEqual(len(self.runtime_state.pending_orders), 1)

        self.assertEqual(len(res1.orders), 1)
        self.assertEqual(len(res1.fills), 1)
        self.assertEqual(len(res1.rejections), 1)
        self.assertEqual(len(res1.audit_log), 1)

        self.assertIs(res1.orders[0], self.portfolio.trade_log.orders[0])
        self.assertIs(res1.fills[0], self.portfolio.trade_log.fills[0])
        
        # Test counts 
        self.assertEqual(res1.order_count, 1)
        self.assertEqual(res1.fill_count, 1)
        self.assertEqual(res1.rejection_count, 1)
        self.assertEqual(res1.audit_record_count, 1)

        # equivalent output
        self.assertEqual(res1.total_market_value, res2.total_market_value)
        self.assertEqual(res1.total_equity, res2.total_equity)
        
    def test_trade_log_preservation(self):
        order1 = SimulatedOrder("O1", "2330", "BUY", 1000, self.dt)
        order2 = SimulatedOrder("O2", "2317", "SELL", 1000, self.dt)
        self.portfolio.trade_log.record_order(order2)
        self.portfolio.trade_log.record_order(order1)
        
        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=100000.0, last_prices={}
        )
        self.assertEqual(res.orders[0].symbol, "2317")
        self.assertEqual(res.orders[1].symbol, "2330")

if __name__ == '__main__':
    unittest.main()
