import unittest
import pandas as pd
import numpy as np

from tw_stock_tool.paper_trading.engine import (
    run_simulated_paper_trading,
    run_simulated_paper_trading_result,
)
from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult
from tw_stock_tool.paper_trading.models import PaperTradingModelError


class TestSimulatedPaperTradingEngine(unittest.TestCase):
    def setUp(self):
        self.dates = pd.date_range("2026-01-01", periods=5)
        self.df = pd.DataFrame(
            {
                "Open": [100.0, 105.0, 110.0, 115.0, 120.0],
                "entry_signal": [False, False, False, False, False],
                "exit_signal": [False, False, False, False, False],
            },
            index=self.dates
        )

    def test_standard_signal_input_and_next_bar_open_timing(self):
        """1. Standard signal input and next-bar-open timing"""
        self.df.loc[self.dates[0], "entry_signal"] = True

        portfolio = run_simulated_paper_trading(self.df, "2330", 200000.0, 1000)

        self.assertEqual(len(portfolio.trade_log.orders), 1)
        self.assertEqual(len(portfolio.trade_log.fills), 1)

        fill = portfolio.trade_log.fills[0]
        self.assertEqual(fill.price, 105.0)  # Row 1 Open
        self.assertEqual(fill.filled_at, self.dates[1])  # Row 1 index

    def test_buy_updates_portfolio(self):
        """2. BUY updates portfolio"""
        self.df.loc[self.dates[0], "entry_signal"] = True

        initial_cash = 200000.0
        portfolio = run_simulated_paper_trading(self.df, "2330", initial_cash, 1000)

        fill = portfolio.trade_log.fills[0]
        self.assertEqual(portfolio.cash, initial_cash - fill.gross_amount)
        pos = portfolio.position_for("2330")
        self.assertEqual(pos.quantity, 1000)

    def test_sell_updates_portfolio_and_realizes_pnl(self):
        """3. SELL updates portfolio and realizes PnL"""
        self.df.loc[self.dates[0], "entry_signal"] = True
        self.df.loc[self.dates[2], "exit_signal"] = True

        portfolio = run_simulated_paper_trading(self.df, "2330", 200000.0, 1000)

        self.assertEqual(len(portfolio.trade_log.fills), 2)
        buy_fill = portfolio.trade_log.fills[0]
        sell_fill = portfolio.trade_log.fills[1]

        self.assertEqual(buy_fill.price, 105.0)  # Row 1 Open
        self.assertEqual(sell_fill.price, 115.0) # Row 3 Open

        pos = portfolio.position_for("2330")
        self.assertEqual(pos.quantity, 0)

        expected_pnl = (115.0 * 1000) - (105.0 * 1000)
        self.assertEqual(pos.realized_pnl, expected_pnl)

    def test_last_bar_signal_does_not_fill(self):
        """4. Last-bar signal does not fill"""
        self.df.loc[self.dates[-1], "entry_signal"] = True

        portfolio = run_simulated_paper_trading(self.df, "2330", 200000.0, 1000)

        self.assertEqual(len(portfolio.trade_log.orders), 1)
        self.assertEqual(len(portfolio.trade_log.fills), 0)
        pos = portfolio.position_for("2330")
        self.assertEqual(pos.quantity, 0)

    def test_missing_invalid_open_skips_fill(self):
        """5. Missing / invalid Open skips fill"""
        # NaN Open
        self.df.loc[self.dates[0], "entry_signal"] = True
        self.df.loc[self.dates[1], "Open"] = np.nan

        portfolio1 = run_simulated_paper_trading(self.df.copy(), "2330", 200000.0, 1000)
        self.assertEqual(len(portfolio1.trade_log.fills), 0)

        # 0 Open
        self.df.loc[self.dates[1], "Open"] = 0.0
        portfolio2 = run_simulated_paper_trading(self.df.copy(), "2330", 200000.0, 1000)
        self.assertEqual(len(portfolio2.trade_log.fills), 0)

        # Negative Open
        self.df.loc[self.dates[1], "Open"] = -10.0
        portfolio3 = run_simulated_paper_trading(self.df.copy(), "2330", 200000.0, 1000)
        self.assertEqual(len(portfolio3.trade_log.fills), 0)

    def test_insufficient_cash_rejects_buy_safely(self):
        """6. Insufficient cash rejects BUY safely"""
        self.df.loc[self.dates[0], "entry_signal"] = True

        # Row 1 Open is 105.0. 1000 * 105.0 = 105000.
        initial_cash = 10000.0 # not enough

        portfolio = run_simulated_paper_trading(self.df, "2330", initial_cash, 1000)

        self.assertEqual(len(portfolio.trade_log.orders), 1)
        self.assertEqual(len(portfolio.trade_log.fills), 0)
        self.assertEqual(portfolio.cash, initial_cash)

    def test_flat_exit_is_ignored(self):
        """7. Flat exit is ignored"""
        self.df.loc[self.dates[0], "exit_signal"] = True

        portfolio = run_simulated_paper_trading(self.df, "2330", 200000.0, 1000)

        self.assertEqual(len(portfolio.trade_log.orders), 0)
        self.assertEqual(len(portfolio.trade_log.fills), 0)

    def test_additional_entry_while_holding_is_ignored(self):
        """8. Additional entry while holding is ignored"""
        self.df.loc[self.dates[0], "entry_signal"] = True
        self.df.loc[self.dates[2], "entry_signal"] = True

        portfolio = run_simulated_paper_trading(self.df, "2330", 200000.0, 1000)

        self.assertEqual(len(portfolio.trade_log.orders), 1)
        self.assertEqual(len(portfolio.trade_log.fills), 1)

    def test_legacy_text_signal_is_not_direct_input(self):
        """9. Legacy text Signal is not direct input"""
        # Only legacy signal, no entry/exit -> should raise ValueError from validate_standard_signals
        df_legacy = pd.DataFrame(
            {
                "Open": [100.0, 105.0],
                "Signal": ["BUY", "HOLD"],
            },
            index=self.dates[:2]
        )
        with self.assertRaises(ValueError):
            run_simulated_paper_trading(df_legacy, "2330", 200000.0, 1000)

        # Standard signals False + legacy Signal BUY -> no BUY intent
        df_mixed = pd.DataFrame(
            {
                "Open": [100.0, 105.0],
                "entry_signal": [False, False],
                "exit_signal": [False, False],
                "Signal": ["BUY", "HOLD"],
            },
            index=self.dates[:2]
        )
        portfolio = run_simulated_paper_trading(df_mixed, "2330", 200000.0, 1000)
        self.assertEqual(len(portfolio.trade_log.orders), 0)

    def test_public_docstring_safety(self):
        """10. Public docstring safety wording"""
        import tw_stock_tool.paper_trading.engine as engine

        banned = [
            "broker api",
            "real order",
            "order execution",
            "auto trading",
            "semi-auto trading",
            "investment recommendation",
            "guaranteed profit",
            "guaranteed return",
            "safe to invest",
        ]

        doc = engine.run_simulated_paper_trading.__doc__
        if doc:
            doc_lower = doc.lower()
            for b in banned:
                self.assertNotIn(b, doc_lower, f"Banned phrase '{b}' found in docstring.")

    def test_cost_handling(self):
        """11. Cost handling test hardening"""
        dates = pd.date_range("2026-01-01", periods=4)
        df = pd.DataFrame(
            {
                "Open": [100.0, 100.0, 110.0, 110.0],
                "entry_signal": [True, False, False, False],
                "exit_signal": [False, False, True, False],
            },
            index=dates
        )

        portfolio = run_simulated_paper_trading(
            df=df,
            symbol="2330",
            initial_cash=200000.0,
            quantity_per_trade=1000,
            fee_rate=0.001,
            tax_rate=0.003,
            slippage_per_share=0.5,
        )

        self.assertEqual(len(portfolio.trade_log.fills), 2)
        buy_fill = portfolio.trade_log.fills[0]
        sell_fill = portfolio.trade_log.fills[1]

        self.assertEqual(buy_fill.fee, 100.0)
        self.assertEqual(buy_fill.tax, 0.0)
        self.assertEqual(buy_fill.slippage, 500.0)

        self.assertEqual(sell_fill.fee, 110.0)
        self.assertEqual(sell_fill.tax, 330.0)
        self.assertEqual(sell_fill.slippage, 500.0)

        pos = portfolio.position_for("2330")
        self.assertEqual(pos.realized_pnl, 8460.0)
        self.assertEqual(portfolio.cash, 208460.0)

    def test_run_simulated_result_wrapper_flat_portfolio(self):
        df = pd.DataFrame({
            "Open": [100.0, 101.0, 102.0],
            "entry_signal": [False, False, False],
            "exit_signal": [False, False, False],
        })
        result = run_simulated_paper_trading_result(
            df=df, symbol="2330", initial_cash=100000.0, quantity_per_trade=1000
        )
        self.assertIsInstance(result, SimulatedPaperTradingResult)
        self.assertEqual(result.final_cash, 100000.0)
        self.assertEqual(result.final_position_quantity, 0)
        self.assertEqual(result.total_equity, 100000.0)
        self.assertEqual(result.order_count, 0)
        self.assertEqual(result.fill_count, 0)

    def test_run_simulated_result_wrapper_closed_position_without_last_price(self):
        df = pd.DataFrame({
            "Open": [100.0, 101.0, 102.0, 103.0],
            "entry_signal": [True, False, False, False],
            "exit_signal": [False, False, True, False],
        })
        result = run_simulated_paper_trading_result(
            df=df, symbol="2330", initial_cash=200000.0, quantity_per_trade=1000
        )
        self.assertIsInstance(result, SimulatedPaperTradingResult)
        self.assertEqual(result.final_position_quantity, 0)
        self.assertEqual(result.fill_count, 2)
        self.assertEqual(result.total_equity, result.final_cash)

    def test_run_simulated_result_wrapper_open_position_uses_last_price(self):
        df = pd.DataFrame({
            "Open": [100.0, 101.0, 102.0],
            "entry_signal": [True, False, False],
            "exit_signal": [False, False, False],
        })
        result = run_simulated_paper_trading_result(
            df=df, symbol="2330", initial_cash=200000.0, quantity_per_trade=1000, last_price=105.0
        )
        self.assertIsInstance(result, SimulatedPaperTradingResult)
        self.assertGreater(result.final_position_quantity, 0)
        self.assertEqual(result.unrealized_pnl, 4000.0)  # (105 - 101) * 1000 = 4000
        self.assertEqual(result.total_equity, 200000.0 - 101000.0 + 105000.0)

    def test_run_simulated_result_wrapper_open_position_missing_price(self):
        df = pd.DataFrame({
            "Open": [100.0, 101.0, 102.0],
            "entry_signal": [True, False, False],
            "exit_signal": [False, False, False],
        })
        with self.assertRaises(PaperTradingModelError):
            run_simulated_paper_trading_result(
                df=df, symbol="2330", initial_cash=200000.0, quantity_per_trade=1000
            )

    def test_paper_trading_init_exports_run_result_helper(self):
        import tw_stock_tool.paper_trading as pt
        self.assertTrue(hasattr(pt, "run_simulated_paper_trading_result"))
