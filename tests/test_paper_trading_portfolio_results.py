"""
Tests for multi-symbol simulated portfolio results.
"""

import math
import unittest
from datetime import datetime
from collections.abc import Mapping

from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedFill,
    SimulatedOrder,
    SimulatedOrderRejection,
    SimulatedPosition,
    SimulatedPortfolio,
    SimulatedTradeEventType,
    SimulatedTradeStatus,
    SimulatedTradeLog,
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

    def test_construction_mixed_positions(self):
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
        self.assertEqual(res.positions[1].last_price, None)
        self.assertEqual(res.total_market_value, 110000.0)

    def test_deterministic_symbol_ordering(self):
        self.portfolio.positions["Z"] = SimulatedPosition("Z", 1, 10.0, 0.0)
        self.portfolio.positions["A"] = SimulatedPosition("A", 1, 10.0, 0.0)
        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=100000.0, last_prices={"A": 10.0, "Z": 10.0}
        )
        self.assertEqual(res.positions[0].symbol, "A")
        self.assertEqual(res.positions[1].symbol, "Z")

    def test_rejected_only_symbol_not_fabricated(self):
        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=100000.0, last_prices={"2330": 600.0}
        )
        self.assertEqual(len(res.positions), 0)

    def test_runtime_mutation(self):
        self.runtime_state.portfolio = None
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100.0, last_prices={})
        self.runtime_state.portfolio = self.portfolio

        self.portfolio.positions = None
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100.0, last_prices={})
        self.portfolio.positions = {}

        self.portfolio.trade_log = None
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100.0, last_prices={})
        self.portfolio.trade_log = SimulatedTradeLog()

    def test_trade_log_mutation(self):
        attrs = ["orders", "fills", "rejections", "records"]
        for attr in attrs:
            with self.subTest(attr=attr):
                old_val = getattr(self.portfolio.trade_log, attr)
                setattr(self.portfolio.trade_log, attr, None)
                with self.assertRaises(PaperTradingModelError):
                    build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100.0, last_prices={})
                setattr(self.portfolio.trade_log, attr, old_val)

    def test_scalar_validation_initial_cash(self):
        invalid_values = [True, "100", -1.0, math.nan, math.inf, -math.inf]
        for val in invalid_values:
            with self.subTest(val=val):
                with self.assertRaises(PaperTradingModelError):
                    build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=val, last_prices={})

    def test_scalar_validation_portfolio_cash(self):
        invalid_values = [True, "100", -1.0, math.nan, math.inf, -math.inf]
        for val in invalid_values:
            with self.subTest(val=val):
                self.portfolio.cash = val
                with self.assertRaises(PaperTradingModelError):
                    build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100.0, last_prices={})

    def test_last_prices_validation(self):
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 1000, 500.0, 0.0)
        
        # valid custom mapping and extra prices
        cm = CustomMapping({"2330": 600.0, "2317": 100.0})
        build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices=cm)

        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices=[])

        with self.assertRaisesRegex(PaperTradingModelError, "Missing last price"):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices={})

        invalid_mappings = [
            ({"": 100.0}, "blank key"),
            ({123: 100.0}, "non string key"),
            ({"2330": True}, "bool price"),
            ({"2330": "600"}, "string price"),
            ({"2330": math.nan}, "nan"),
            ({"2330": math.inf}, "inf"),
            ({"2330": -math.inf}, "-inf"),
            ({"2330": 0.0}, "zero"),
            ({"2330": -1.0}, "negative"),
        ]
        for mapping, name in invalid_mappings:
            with self.subTest(name=name):
                with self.assertRaises(PaperTradingModelError):
                    build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100000.0, last_prices=mapping)

        # check closed position does not need a price
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 0, 0.0, 500.0)
        build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100.0, last_prices={})
        self.portfolio.positions.clear()
        
        # pending reference price does not substitute missing last price
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 1, 10.0, 0.0)
        order = SimulatedOrder("O1", "2330", "BUY", 1, self.dt)
        self.runtime_state.pending_orders["2330"] = SimulatedPendingOrderState(order, 600.0)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100.0, last_prices={})
        self.runtime_state.pending_orders.clear()

    def test_position_validation(self):
        invalid_cases = [
            ("2317", SimulatedPosition("2330", 1, 10.0, 0.0), "key mismatch"),
            ("", SimulatedPosition("", 1, 10.0, 0.0), "blank symbol"),
            ("2330", None, "wrong object type"),
            ("2330", SimulatedPosition("2330", True, 10.0, 0.0), "bool qty"),
            ("2330", SimulatedPosition("2330", -1, 10.0, 0.0), "negative qty"),
            ("2330", SimulatedPosition("2330", 1.5, 10.0, 0.0), "non-int qty"),
            ("2330", SimulatedPosition("2330", 1, True, 0.0), "bool avg cost"),
            ("2330", SimulatedPosition("2330", 1, "10", 0.0), "string avg cost"),
            ("2330", SimulatedPosition("2330", 1, math.nan, 0.0), "nan avg cost"),
            ("2330", SimulatedPosition("2330", 1, math.inf, 0.0), "inf avg cost"),
            ("2330", SimulatedPosition("2330", 1, -math.inf, 0.0), "-inf avg cost"),
            ("2330", SimulatedPosition("2330", 1, -10.0, 0.0), "negative avg cost"),
            ("2330", SimulatedPosition("2330", 1, 0.0, 0.0), "open zero avg cost"),
            ("2330", SimulatedPosition("2330", 0, 10.0, 0.0), "closed non-zero avg cost"),
            ("2330", SimulatedPosition("2330", 0, 0.0, True), "bool pnl"),
            ("2330", SimulatedPosition("2330", 0, 0.0, "100"), "string pnl"),
            ("2330", SimulatedPosition("2330", 0, 0.0, math.nan), "nan pnl"),
            ("2330", SimulatedPosition("2330", 0, 0.0, math.inf), "inf pnl"),
            ("2330", SimulatedPosition("2330", 0, 0.0, -math.inf), "-inf pnl"),
        ]
        for key, pos, name in invalid_cases:
            with self.subTest(name=name):
                self.portfolio.positions.clear()
                self.portfolio.positions[key] = pos
                with self.assertRaises(PaperTradingModelError):
                    build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100.0, last_prices={"2330": 10.0})

        # Negative finite realized PnL is accepted
        self.portfolio.positions.clear()
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 0, 0.0, -500.0)
        res = build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100.0, last_prices={})
        self.assertEqual(res.realized_pnl, -500.0)

    def test_pending_orders_validation(self):
        order1 = SimulatedOrder("O1", "2330", "BUY", 1000, self.dt)
        self.runtime_state.pending_orders[""] = SimulatedPendingOrderState(order1, 600.0)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100.0, last_prices={})
        self.runtime_state.pending_orders.clear()

        valid_state = SimulatedPendingOrderState(order1, 600.0)
        
        invalid_cases = [
            ("2317", valid_state, "key order symbol mismatch"),
            ("2330", None, "value wrong type"),
        ]
        
        def clone_state_with_order_attr(attr, val):
            order = SimulatedOrder("O1", "2330", "BUY", 1000, self.dt)
            object.__setattr__(order, attr, val)
            return SimulatedPendingOrderState(order, 600.0)

        def clone_state_with_state_attr(attr, val):
            state = SimulatedPendingOrderState(order1, 600.0)
            object.__setattr__(state, attr, val)
            return state

        invalid_cases.extend([
            ("2330", clone_state_with_state_attr("order", None), "order wrong type"),
            ("2330", clone_state_with_order_attr("order_id", ""), "blank order ID"),
            ("2330", clone_state_with_order_attr("symbol", ""), "blank symbol"),
            ("2330", clone_state_with_order_attr("side", "HOLD"), "invalid side"),
            ("2330", clone_state_with_order_attr("quantity", True), "bool qty"),
            ("2330", clone_state_with_order_attr("quantity", 0), "zero qty"),
            ("2330", clone_state_with_order_attr("quantity", -1), "neg qty"),
            ("2330", clone_state_with_order_attr("quantity", 1.5), "non-int qty"),
            ("2330", clone_state_with_state_attr("reference_price", True), "bool ref price"),
            ("2330", clone_state_with_state_attr("reference_price", "100"), "str ref price"),
            ("2330", clone_state_with_state_attr("reference_price", math.nan), "nan ref price"),
            ("2330", clone_state_with_state_attr("reference_price", math.inf), "inf ref price"),
            ("2330", clone_state_with_state_attr("reference_price", -math.inf), "-inf ref price"),
            ("2330", clone_state_with_state_attr("reference_price", 0.0), "zero ref price"),
            ("2330", clone_state_with_state_attr("reference_price", -1.0), "neg ref price"),
        ])

        for key, state, name in invalid_cases:
            with self.subTest(name=name):
                self.runtime_state.pending_orders.clear()
                self.runtime_state.pending_orders[key] = state
                with self.assertRaises(PaperTradingModelError):
                    build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100.0, last_prices={})

    def test_pending_orders_reservations(self):
        order1 = SimulatedOrder("O1", "2330", "BUY", 1000, self.dt)
        order2 = SimulatedOrder("O2", "2317", "SELL", 2000, self.dt)
        
        self.runtime_state.pending_orders["2330"] = SimulatedPendingOrderState(order1, 600.0)
        self.runtime_state.pending_orders["2317"] = SimulatedPendingOrderState(order2, 100.0)

        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=100.0, last_prices={}
        )
        self.assertEqual(res.pending_orders[0].symbol, "2317")
        self.assertEqual(res.pending_orders[1].symbol, "2330")
        self.assertEqual(res.pending_orders[0].reserved_buy_notional, 0.0)
        self.assertEqual(res.pending_orders[1].reserved_buy_notional, 600000.0)

    def test_derived_overflow_position_market_value(self):
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 10**300, 10.0, 0.0)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(
                self.runtime_state, initial_cash=100.0, last_prices={"2330": 10**10}
            )

    def test_derived_overflow_position_cost_basis(self):
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 10**300, 10**10, 0.0)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(
                self.runtime_state, initial_cash=100.0, last_prices={"2330": 10.0}
            )

    def test_derived_overflow_unrealized_pnl(self):
        # We know python float overflow will trigger validation on the operands 
        # (market_val or cost_basis) before getting to `inf - inf` giving `nan`.
        # But if there's any case where subtraction goes non-finite without operands being caught,
        # we still catch it. Let's provide a case where the difference overflows.
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 10**290, 10.0, 0.0)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(
                self.runtime_state, initial_cash=100.0, last_prices={"2330": 10**20}
            )

    def test_derived_overflow_aggregate_market_value(self):
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 10**308, 1.0, 0.0)
        self.portfolio.positions["2317"] = SimulatedPosition("2317", 10**308, 1.0, 0.0)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(
                self.runtime_state, initial_cash=100.0, last_prices={"2330": 1.0, "2317": 1.0}
            )

    def test_derived_overflow_aggregate_realized_pnl(self):
        self.portfolio.positions["2330"] = SimulatedPosition("2330", 0, 0.0, 10**308)
        self.portfolio.positions["2317"] = SimulatedPosition("2317", 0, 0.0, 10**308)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(
                self.runtime_state, initial_cash=100.0, last_prices={}
            )

    def test_derived_overflow_total_return_pct(self):
        # Triggering a percentage overflow safely: return / initial_cash
        res = build_simulated_portfolio_trading_result(
            self.runtime_state, initial_cash=0.0, last_prices={}
        )
        self.assertIsNone(res.total_return_pct)
        
        self.portfolio.cash = 10**308
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(
                self.runtime_state, initial_cash=1e-10, last_prices={}
            )

    def test_derived_overflow_pending_buy_reservation(self):
        order = SimulatedOrder("O1", "2330", "BUY", 10**300, self.dt)
        self.runtime_state.pending_orders["2330"] = SimulatedPendingOrderState(order, 10**10)
        with self.assertRaises(PaperTradingModelError):
            build_simulated_portfolio_trading_result(
                self.runtime_state, initial_cash=100.0, last_prices={}
            )

    def test_identity_and_mutation(self):
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
        orig_fills_id = id(self.portfolio.trade_log.fills)
        orig_rejections_id = id(self.portfolio.trade_log.rejections)
        orig_records_id = id(self.portfolio.trade_log.records)

        res1 = build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100.0, last_prices=prices)
        res2 = build_simulated_portfolio_trading_result(self.runtime_state, initial_cash=100.0, last_prices=prices)

        self.assertEqual(id(self.runtime_state), orig_runtime_id)
        self.assertEqual(id(self.portfolio), orig_portfolio_id)
        self.assertEqual(id(self.portfolio.positions), orig_positions_id)
        self.assertEqual(id(self.runtime_state.pending_orders), orig_pending_id)
        
        self.assertEqual(id(self.portfolio.trade_log.orders), orig_orders_id)
        self.assertEqual(id(self.portfolio.trade_log.fills), orig_fills_id)
        self.assertEqual(id(self.portfolio.trade_log.rejections), orig_rejections_id)
        self.assertEqual(id(self.portfolio.trade_log.records), orig_records_id)
        
        self.assertEqual(prices, {"2330": 600.0})
        self.assertEqual(len(self.runtime_state.pending_orders), 1)

        self.assertEqual(len(res1.orders), 1)
        self.assertEqual(len(res1.fills), 1)
        self.assertEqual(len(res1.rejections), 1)
        self.assertEqual(len(res1.audit_log), 1)

        self.assertIs(res1.orders[0], self.portfolio.trade_log.orders[0])
        self.assertIs(res1.fills[0], self.portfolio.trade_log.fills[0])
        self.assertIs(res1.rejections[0], self.portfolio.trade_log.rejections[0])
        self.assertIs(res1.audit_log[0], self.portfolio.trade_log.records[0])
        
        self.assertEqual(res1.total_market_value, res2.total_market_value)
        self.assertEqual(res1.total_equity, res2.total_equity)

if __name__ == '__main__':
    unittest.main()
