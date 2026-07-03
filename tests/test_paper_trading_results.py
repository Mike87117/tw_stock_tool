import unittest
from dataclasses import FrozenInstanceError

from tw_stock_tool.paper_trading.models import (
    SimulatedPortfolio,
    SimulatedOrder,
    SimulatedFill,
    PaperTradingModelError,
)
from tw_stock_tool.paper_trading.results import (
    SimulatedPaperTradingResult,
    build_simulated_paper_trading_result,
)


class TestSimulatedPaperTradingResults(unittest.TestCase):
    def test_build_result_for_flat_empty_portfolio(self):
        """1. test_build_result_for_flat_empty_portfolio"""
        portfolio = SimulatedPortfolio(cash=100000.0)

        result = build_simulated_paper_trading_result(
            portfolio=portfolio,
            symbol="2330",
            initial_cash=100000.0,
        )

        self.assertEqual(result.final_cash, 100000.0)
        self.assertEqual(result.final_position_quantity, 0)
        self.assertEqual(result.realized_pnl, 0.0)
        self.assertEqual(result.unrealized_pnl, 0.0)
        self.assertEqual(result.total_equity, 100000.0)
        self.assertEqual(result.order_count, 0)
        self.assertEqual(result.fill_count, 0)
        self.assertEqual(result.open_position_count, 0)

    def test_build_result_for_open_position_requires_last_price(self):
        """2. test_build_result_for_open_position_requires_last_price"""
        portfolio = SimulatedPortfolio(cash=100000.0)
        fill = SimulatedFill(
            order_id="1", symbol="2330", side="BUY",
            quantity=1000, price=100.0, filled_at="2026-01-01"
        )
        portfolio.apply_fill(fill)

        with self.assertRaisesRegex(PaperTradingModelError, "last_price is required"):
            build_simulated_paper_trading_result(
                portfolio=portfolio,
                symbol="2330",
                initial_cash=100000.0,
            )

    def test_build_result_for_open_position_calculates_unrealized_and_equity(self):
        """3. test_build_result_for_open_position_calculates_unrealized_and_equity"""
        portfolio = SimulatedPortfolio(cash=100000.0)
        fill = SimulatedFill(
            order_id="1", symbol="2330", side="BUY",
            quantity=1000, price=100.0, filled_at="2026-01-01"
        )
        portfolio.apply_fill(fill)

        result = build_simulated_paper_trading_result(
            portfolio=portfolio,
            symbol="2330",
            initial_cash=100000.0,
            last_price=110.0,
        )

        # BUY cost = 100000. Current cash = 0.
        # market value = 110.0 * 1000 = 110000
        # unrealized pnl = 110000 - 100000 = 10000
        # total equity = 0 + 110000 = 110000
        self.assertEqual(result.final_position_quantity, 1000)
        self.assertEqual(result.unrealized_pnl, 10000.0)
        self.assertEqual(result.total_equity, 110000.0)
        self.assertEqual(result.open_position_count, 1)

    def test_build_result_snapshots_orders_and_fills_as_tuples(self):
        """4. test_build_result_snapshots_orders_and_fills_as_tuples"""
        portfolio = SimulatedPortfolio(cash=100000.0)
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1000, signal_time="2026-01-01")
        fill = SimulatedFill(
            order_id="1", symbol="2330", side="BUY",
            quantity=1000, price=100.0, filled_at="2026-01-01"
        )
        portfolio.trade_log.record_order(order)
        portfolio.apply_fill(fill)

        result = build_simulated_paper_trading_result(
            portfolio=portfolio,
            symbol="2330",
            initial_cash=100000.0,
            last_price=110.0,
        )

        self.assertIsInstance(result.orders, tuple)
        self.assertIsInstance(result.fills, tuple)
        self.assertEqual(len(result.orders), 1)
        self.assertEqual(len(result.fills), 1)
        self.assertEqual(result.order_count, 1)
        self.assertEqual(result.fill_count, 1)

    def test_paper_trading_init_exports_result_helpers(self):
        """6. test_paper_trading_init_exports_result_helpers"""
        import tw_stock_tool.paper_trading as pt
        self.assertTrue(hasattr(pt, "run_simulated_paper_trading"))
        self.assertTrue(hasattr(pt, "SimulatedPaperTradingResult"))
        self.assertTrue(hasattr(pt, "build_simulated_paper_trading_result"))

    def test_result_object_is_frozen(self):
        """7. Verify result object is frozen enough that assigning to top-level result fields raises an error."""
        result = SimulatedPaperTradingResult(
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
            orders=tuple(),
            fills=tuple(),
        )
        with self.assertRaises(FrozenInstanceError):
            result.symbol = "2331"

    def test_build_result_rejects_non_finite_initial_cash(self):
        portfolio = SimulatedPortfolio(cash=100000.0)

        invalid_values = [float("nan"), float("inf"), -float("inf"), -1.0]
        for val in invalid_values:
            with self.assertRaisesRegex(PaperTradingModelError, "initial_cash must be finite and non-negative"):
                build_simulated_paper_trading_result(
                    portfolio=portfolio,
                    symbol="2330",
                    initial_cash=val,
                )

    def test_build_result_rejects_non_finite_last_price_for_open_position(self):
        portfolio = SimulatedPortfolio(cash=100000.0)
        fill = SimulatedFill(
            order_id="1", symbol="2330", side="BUY",
            quantity=1000, price=100.0, filled_at="2026-01-01"
        )
        portfolio.apply_fill(fill)

        invalid_values = [float("nan"), float("inf"), -float("inf"), 0.0, -10.0]
        for val in invalid_values:
            with self.assertRaisesRegex(PaperTradingModelError, "last_price must be finite and positive"):
                build_simulated_paper_trading_result(
                    portfolio=portfolio,
                    symbol="2330",
                    initial_cash=100000.0,
                    last_price=val,
                )
