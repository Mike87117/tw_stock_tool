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
    build_simulated_paper_trading_summary,
    build_simulated_order_rows,
    build_simulated_fill_rows,
)
import numbers


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

    def test_build_summary_computes_returns(self):
        result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=100000.0,
            final_cash=110000.0,
            final_position_quantity=0,
            average_cost=0.0,
            realized_pnl=10000.0,
            unrealized_pnl=0.0,
            total_equity=110000.0,
            order_count=2,
            fill_count=2,
            open_position_count=0,
            orders=tuple(),
            fills=tuple(),
        )
        summary = build_simulated_paper_trading_summary(result)
        self.assertEqual(summary["total_return"], 10000.0)
        self.assertEqual(summary["total_return_pct"], 0.1)

    def test_build_summary_handles_zero_initial_cash(self):
        result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=0.0,
            final_cash=0.0,
            final_position_quantity=0,
            average_cost=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            total_equity=0.0,
            order_count=0,
            fill_count=0,
            open_position_count=0,
            orders=tuple(),
            fills=tuple(),
        )
        summary = build_simulated_paper_trading_summary(result)
        self.assertEqual(summary["total_return"], 0.0)
        self.assertIsNone(summary["total_return_pct"])

    def test_build_summary_omits_heavy_structures(self):
        result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=100000.0,
            final_cash=100000.0,
            final_position_quantity=0,
            average_cost=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            total_equity=100000.0,
            order_count=0,
            fill_count=0,
            open_position_count=0,
            orders=tuple(),
            fills=tuple(),
        )
        summary = build_simulated_paper_trading_summary(result)
        self.assertNotIn("orders", summary)
        self.assertNotIn("fills", summary)
        self.assertNotIn("trade_log", summary)

    def test_build_summary_preserves_numeric_types(self):
        result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=100000.0,
            final_cash=110000.0,
            final_position_quantity=0,
            average_cost=0.0,
            realized_pnl=10000.0,
            unrealized_pnl=0.0,
            total_equity=110000.0,
            order_count=2,
            fill_count=2,
            open_position_count=0,
            orders=tuple(),
            fills=tuple(),
        )
        summary = build_simulated_paper_trading_summary(result)
        self.assertIsInstance(summary["total_return"], numbers.Real)
        self.assertIsInstance(summary["total_return_pct"], float)
        self.assertNotIsInstance(summary["total_return_pct"], str)
        self.assertNotIsInstance(summary["initial_cash"], str)
        self.assertNotIsInstance(summary["total_equity"], str)

    def test_build_summary_contains_expected_keys_only(self):
        result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=100000.0,
            final_cash=110000.0,
            final_position_quantity=0,
            average_cost=0.0,
            realized_pnl=10000.0,
            unrealized_pnl=0.0,
            total_equity=110000.0,
            order_count=2,
            fill_count=2,
            open_position_count=0,
            orders=tuple(),
            fills=tuple(),
        )
        summary = build_simulated_paper_trading_summary(result)
        expected_keys = {
            "symbol",
            "initial_cash",
            "final_cash",
            "final_position_quantity",
            "average_cost",
            "realized_pnl",
            "unrealized_pnl",
            "total_equity",
            "order_count",
            "fill_count",
            "open_position_count",
            "total_return",
            "total_return_pct",
        }
        self.assertEqual(set(summary.keys()), expected_keys)

    def test_paper_trading_init_exports_summary_helper(self):
        import tw_stock_tool.paper_trading as pt
        self.assertTrue(hasattr(pt, "build_simulated_paper_trading_summary"))

    def test_build_order_rows_maps_fields(self):
        class DummyTimestamp:
            pass
        signal_time = DummyTimestamp()
        created_at = DummyTimestamp()
        order = SimulatedOrder(
            order_id="order-1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            signal_time=signal_time,
            created_at=created_at,
            strategy="unit-test-strategy"
        )
        result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=100000.0,
            final_cash=100000.0,
            final_position_quantity=0,
            average_cost=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            total_equity=100000.0,
            order_count=1,
            fill_count=0,
            open_position_count=0,
            orders=(order,),
            fills=tuple(),
        )
        rows = build_simulated_order_rows(result)
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        expected_keys = {
            "order_id", "symbol", "side", "quantity", "signal_time", "created_at", "strategy"
        }
        self.assertEqual(set(row.keys()), expected_keys)
        self.assertEqual(row["order_id"], "order-1")
        self.assertEqual(row["symbol"], "2330")
        self.assertEqual(row["side"], "BUY")
        self.assertEqual(row["quantity"], 1000)
        self.assertIs(row["signal_time"], signal_time)
        self.assertIs(row["created_at"], created_at)
        self.assertEqual(row["strategy"], "unit-test-strategy")

    def test_build_fill_rows_maps_fields_and_properties(self):
        class DummyTimestamp:
            pass
        filled_at = DummyTimestamp()
        fill = SimulatedFill(
            order_id="order-1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            price=100.0,
            filled_at=filled_at,
            fee=100.0,
            tax=0.0,
            slippage=50.0
        )
        result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=100000.0,
            final_cash=100000.0,
            final_position_quantity=0,
            average_cost=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            total_equity=100000.0,
            order_count=0,
            fill_count=1,
            open_position_count=0,
            orders=tuple(),
            fills=(fill,),
        )
        rows = build_simulated_fill_rows(result)
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        expected_keys = {
            "order_id", "symbol", "side", "quantity", "price", "filled_at",
            "fee", "tax", "slippage", "gross_amount", "net_cash_effect"
        }
        self.assertEqual(set(row.keys()), expected_keys)
        self.assertEqual(row["order_id"], "order-1")
        self.assertEqual(row["symbol"], "2330")
        self.assertEqual(row["side"], "BUY")
        self.assertEqual(row["quantity"], 1000)
        self.assertEqual(row["price"], 100.0)
        self.assertEqual(row["fee"], 100.0)
        self.assertEqual(row["tax"], 0.0)
        self.assertEqual(row["slippage"], 50.0)
        self.assertEqual(row["gross_amount"], 100000.0)
        self.assertEqual(row["net_cash_effect"], -100150.0)
        self.assertIs(row["filled_at"], filled_at)

    def test_trade_log_helpers_return_empty_lists(self):
        result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=100000.0,
            final_cash=100000.0,
            final_position_quantity=0,
            average_cost=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            total_equity=100000.0,
            order_count=0,
            fill_count=0,
            open_position_count=0,
            orders=tuple(),
            fills=tuple(),
        )
        self.assertEqual(build_simulated_order_rows(result), [])
        self.assertEqual(build_simulated_fill_rows(result), [])

    def test_trade_log_helpers_preserve_original_types(self):
        class DummyTimestamp:
            pass
        signal_time = DummyTimestamp()
        created_at = DummyTimestamp()
        filled_at = DummyTimestamp()
        order = SimulatedOrder(
            order_id="order-1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            signal_time=signal_time,
            created_at=created_at,
            strategy="unit-test-strategy"
        )
        fill = SimulatedFill(
            order_id="order-1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            price=100.0,
            filled_at=filled_at,
            fee=100.0,
            tax=0.0,
            slippage=50.0
        )
        result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=100000.0,
            final_cash=100000.0,
            final_position_quantity=0,
            average_cost=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            total_equity=100000.0,
            order_count=1,
            fill_count=1,
            open_position_count=0,
            orders=(order,),
            fills=(fill,),
        )
        order_rows = build_simulated_order_rows(result)
        fill_rows = build_simulated_fill_rows(result)

        o_row = order_rows[0]
        self.assertNotIsInstance(o_row["signal_time"], str)
        self.assertNotIsInstance(o_row["created_at"], str)
        self.assertIsInstance(o_row["quantity"], numbers.Integral)

        f_row = fill_rows[0]
        self.assertNotIsInstance(f_row["filled_at"], str)
        self.assertIsInstance(f_row["quantity"], numbers.Integral)
        self.assertIsInstance(f_row["price"], numbers.Real)
        self.assertIsInstance(f_row["fee"], numbers.Real)
        self.assertIsInstance(f_row["tax"], numbers.Real)
        self.assertIsInstance(f_row["slippage"], numbers.Real)
        self.assertIsInstance(f_row["gross_amount"], numbers.Real)
        self.assertIsInstance(f_row["net_cash_effect"], numbers.Real)

    def test_paper_trading_init_exports_trade_log_row_helpers(self):
        import tw_stock_tool.paper_trading as pt
        self.assertTrue(hasattr(pt, "build_simulated_order_rows"))
        self.assertTrue(hasattr(pt, "build_simulated_fill_rows"))
