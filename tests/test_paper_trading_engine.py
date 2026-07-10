import unittest
import pandas as pd
import numpy as np

from tw_stock_tool.paper_trading.engine import (
    run_simulated_paper_trading,
    run_simulated_paper_trading_result,
)
from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult
from tw_stock_tool.paper_trading.models import PaperTradingModelError, SimulatedPortfolio
from tw_stock_tool.simulated_paper_trading_guard import SimulatedPaperTradingGuardDecision
from unittest.mock import patch, PropertyMock


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

    def test_guard_decision_allowed_preserves_behavior(self):
        """Allowed guard decision preserves existing simulated behavior."""
        self.df.loc[self.dates[0], "entry_signal"] = True
        guard = SimulatedPaperTradingGuardDecision.allow()
        portfolio = run_simulated_paper_trading(self.df, "2330", 200000.0, 1000, guard_decision=guard)
        self.assertEqual(len(portfolio.trade_log.orders), 1)
        self.assertEqual(len(portfolio.trade_log.fills), 1)

    def test_guard_decision_blocked_prevents_buy_intent(self):
        """Blocked guard decision prevents BUY order intent from being recorded."""
        self.df.loc[self.dates[0], "entry_signal"] = True
        guard = SimulatedPaperTradingGuardDecision.block(["Blocked buy"])
        portfolio = run_simulated_paper_trading(self.df, "2330", 200000.0, 1000, guard_decision=guard)
        self.assertEqual(len(portfolio.trade_log.orders), 0)
        self.assertEqual(len(portfolio.trade_log.fills), 0)
        self.assertEqual(portfolio.cash, 200000.0)

    @patch('tw_stock_tool.simulated_paper_trading_guard.models.SimulatedPaperTradingGuardDecision.is_blocked', new_callable=PropertyMock)
    def test_guard_decision_blocked_prevents_sell_intent_and_fill(self, mock_is_blocked):
        """Blocked guard decision prevents SELL order intent and fill."""
        # First check is for BUY (allow), second check is for SELL (block)
        mock_is_blocked.side_effect = [False, True]
        
        self.df.loc[self.dates[0], "entry_signal"] = True
        self.df.loc[self.dates[2], "exit_signal"] = True
        
        guard = SimulatedPaperTradingGuardDecision.allow()
        portfolio = run_simulated_paper_trading(self.df, "2330", 200000.0, 1000, guard_decision=guard)
        
        # BUY should happen at pos 0
        self.assertEqual(len(portfolio.trade_log.orders), 1)
        self.assertEqual(portfolio.trade_log.orders[0].side, "BUY")
        
        # SELL should be blocked at pos 2
        self.assertTrue(all(o.side == "BUY" for o in portfolio.trade_log.orders))
        
        # Fills: only BUY fill
        self.assertEqual(len(portfolio.trade_log.fills), 1)
        self.assertEqual(portfolio.trade_log.fills[0].side, "BUY")

    def test_invalid_guard_decision_raises(self):
        """Invalid non-guard object raises PaperTradingModelError."""
        self.df.loc[self.dates[0], "entry_signal"] = True
        with self.assertRaises(PaperTradingModelError):
            run_simulated_paper_trading(self.df, "2330", 200000.0, 1000, guard_decision="invalid") # type: ignore

    def test_run_simulated_result_wrapper_accepts_allowed_guard(self):
        """run_simulated_paper_trading_result accepts allowed guard decision and preserves result behavior."""
        df = pd.DataFrame({
            "Open": [100.0, 101.0],
            "entry_signal": [True, False],
            "exit_signal": [False, False],
        })
        guard = SimulatedPaperTradingGuardDecision.allow()
        result = run_simulated_paper_trading_result(
            df=df, symbol="2330", initial_cash=200000.0, quantity_per_trade=1000, last_price=101.0, guard_decision=guard
        )
        self.assertEqual(result.fill_count, 1)

    def test_run_simulated_result_wrapper_accepts_blocked_guard(self):
        """run_simulated_paper_trading_result accepts blocked guard decision and produces a no-order result."""
        df = pd.DataFrame({
            "Open": [100.0, 101.0],
            "entry_signal": [True, False],
            "exit_signal": [False, False],
        })
        guard = SimulatedPaperTradingGuardDecision.block(["Blocked"])
        result = run_simulated_paper_trading_result(
            df=df, symbol="2330", initial_cash=200000.0, quantity_per_trade=1000, last_price=101.0, guard_decision=guard
        )
        self.assertEqual(result.fill_count, 0)
        self.assertEqual(result.order_count, 0)

    def test_provider_allowed_decision_records_intent(self):
        """Provider allowed decision records simulated BUY order intent and fill normally."""
        self.df.loc[self.dates[0], "entry_signal"] = True
        
        provider_calls = []
        def provider(order, portfolio):
            provider_calls.append((order, portfolio))
            return SimulatedPaperTradingGuardDecision.allow()
            
        portfolio = run_simulated_paper_trading(self.df, "2330", 200000.0, 1000, guard_decision_provider=provider)
        
        self.assertEqual(len(portfolio.trade_log.orders), 1)
        self.assertEqual(len(portfolio.trade_log.fills), 1)
        self.assertEqual(len(provider_calls), 1)
        self.assertEqual(provider_calls[0][0].symbol, "2330")
        self.assertEqual(provider_calls[0][0].side, "BUY")
        self.assertIsInstance(provider_calls[0][1], SimulatedPortfolio)

    def test_provider_blocked_decision_prevents_buy_intent(self):
        """Provider blocked decision prevents simulated BUY order intent from being recorded."""
        self.df.loc[self.dates[0], "entry_signal"] = True
        
        provider_calls = []
        def provider(order, portfolio):
            provider_calls.append(order)
            return SimulatedPaperTradingGuardDecision.block(["Blocked buy"])
            
        portfolio = run_simulated_paper_trading(self.df, "2330", 200000.0, 1000, guard_decision_provider=provider)
        
        self.assertEqual(len(portfolio.trade_log.orders), 0)
        self.assertEqual(len(portfolio.trade_log.fills), 0)
        self.assertEqual(len(provider_calls), 1)
        self.assertEqual(len(portfolio.trade_log.rejections), 1)
        self.assertEqual(portfolio.trade_log.rejections[0].reasons, ("Blocked buy",))
        self.assertEqual(portfolio.trade_log.rejections[0].candidate_order.side, "BUY")

    def test_provider_blocked_decision_prevents_sell_intent(self):
        """Provider blocked decision prevents simulated SELL order intent and fill."""
        self.df.loc[self.dates[0], "entry_signal"] = True
        self.df.loc[self.dates[2], "exit_signal"] = True
        
        provider_calls = []
        def provider(order, portfolio):
            provider_calls.append(order)
            if order.side == "BUY":
                return SimulatedPaperTradingGuardDecision.allow()
            return SimulatedPaperTradingGuardDecision.block(["Blocked sell"])
            
        portfolio = run_simulated_paper_trading(self.df, "2330", 200000.0, 1000, guard_decision_provider=provider)
        
        self.assertEqual(len(portfolio.trade_log.orders), 1)
        self.assertEqual(portfolio.trade_log.orders[0].side, "BUY")
        self.assertEqual(len(portfolio.trade_log.fills), 1)
        self.assertEqual(len(provider_calls), 2)
        self.assertEqual(provider_calls[1].side, "SELL")
        self.assertEqual(len(portfolio.trade_log.rejections), 1)
        self.assertEqual(portfolio.trade_log.rejections[0].reasons, ("Blocked sell",))
        self.assertEqual(portfolio.trade_log.rejections[0].candidate_order.side, "SELL")

    def test_invalid_provider_raises(self):
        """Non-callable provider raises PaperTradingModelError."""
        self.df.loc[self.dates[0], "entry_signal"] = True
        with self.assertRaises(PaperTradingModelError):
            run_simulated_paper_trading(self.df, "2330", 200000.0, 1000, guard_decision_provider="not callable") # type: ignore

    def test_provider_returning_non_guard_raises(self):
        """Provider returning a non-guard object raises PaperTradingModelError."""
        self.df.loc[self.dates[0], "entry_signal"] = True
        def provider(o, p): return "invalid return"
        with self.assertRaises(PaperTradingModelError):
            run_simulated_paper_trading(self.df, "2330", 200000.0, 1000, guard_decision_provider=provider) # type: ignore

    def test_both_static_and_dynamic_guard_raises(self):
        """Providing both static guard_decision and dynamic guard_decision_provider raises PaperTradingModelError."""
        self.df.loc[self.dates[0], "entry_signal"] = True
        guard = SimulatedPaperTradingGuardDecision.allow()
        def provider(o, p): return guard
        with self.assertRaises(PaperTradingModelError):
            run_simulated_paper_trading(self.df, "2330", 200000.0, 1000, guard_decision=guard, guard_decision_provider=provider)

    def test_run_simulated_result_wrapper_passes_provider(self):
        """run_simulated_paper_trading_result passes provider through to the engine."""
        df = pd.DataFrame({
            "Open": [100.0, 101.0],
            "entry_signal": [True, False],
            "exit_signal": [False, False],
        })
        def provider(o, p): return SimulatedPaperTradingGuardDecision.block(["Blocked"])
        result = run_simulated_paper_trading_result(
            df=df, symbol="2330", initial_cash=200000.0, quantity_per_trade=1000, last_price=101.0, guard_decision_provider=provider
        )
        self.assertEqual(result.fill_count, 0)
        self.assertEqual(result.order_count, 0)

    def test_invalid_signal_open_does_not_create_order(self):
        """A signal on an invalid Open does not create an accepted order or fill."""
        for invalid_open in [float('nan'), float('inf'), float('-inf'), 0.0, -10.0]:
            with self.subTest(invalid_open=invalid_open):
                df = pd.DataFrame({
                    "Open": [invalid_open, 100.0],
                    "entry_signal": [True, False],
                    "exit_signal": [False, False],
                })
                portfolio = run_simulated_paper_trading(df, "2330", 100000.0)
                self.assertEqual(len(portfolio.trade_log.orders), 0)
                self.assertEqual(len(portfolio.trade_log.fills), 0)

    def test_last_bar_valid_signal_records_order(self):
        """Last-bar valid signal still records an accepted order but does not fill it."""
        df = pd.DataFrame({
            "Open": [100.0],
            "entry_signal": [True],
            "exit_signal": [False],
        })
        portfolio = run_simulated_paper_trading(df, "2330", 100000.0)
        self.assertEqual(len(portfolio.trade_log.orders), 1)
        self.assertEqual(len(portfolio.trade_log.fills), 0)

    def test_invalid_next_bar_fill_remains_safe(self):
        """Existing invalid next-bar fill behavior remains safe."""
        df = pd.DataFrame({
            "Open": [100.0, float('nan'), 105.0],
            "entry_signal": [True, False, False],
            "exit_signal": [False, False, False],
        })
        portfolio = run_simulated_paper_trading(df, "2330", 100000.0)
        self.assertEqual(len(portfolio.trade_log.orders), 1)
        self.assertEqual(len(portfolio.trade_log.fills), 0)

    @patch("tw_stock_tool.paper_trading.engine.step_simulated_symbol_bar")
    def test_engine_delegates_to_stepper(self, mock_step):
        df = pd.DataFrame({
            "Open": [100.0, 101.0],
            "entry_signal": [True, False],
            "exit_signal": [False, False],
        }, index=["2023-01-01", "2023-01-02"])
        
        portfolio = run_simulated_paper_trading(df, "2330", 100000.0, quantity_per_trade=100)
        
        self.assertEqual(mock_step.call_count, 2)
        
        call_1_kwargs = mock_step.call_args_list[0].kwargs
        call_2_kwargs = mock_step.call_args_list[1].kwargs
        
        self.assertIs(call_1_kwargs["runtime_state"], call_2_kwargs["runtime_state"])
        self.assertIs(portfolio, call_1_kwargs["runtime_state"].portfolio)
        
        self.assertEqual(call_1_kwargs["symbol"], "2330")
        self.assertEqual(call_1_kwargs["bar_position"], 0)
        self.assertEqual(call_1_kwargs["index_label"], "2023-01-01")
        self.assertEqual(call_1_kwargs["open_price"], 100.0)
        self.assertEqual(call_1_kwargs["entry_signal"], True)
        self.assertEqual(call_1_kwargs["exit_signal"], False)

        self.assertEqual(call_2_kwargs["symbol"], "2330")
        self.assertEqual(call_2_kwargs["bar_position"], 1)
        self.assertEqual(call_2_kwargs["index_label"], "2023-01-02")
        self.assertEqual(call_2_kwargs["open_price"], 101.0)
        self.assertEqual(call_2_kwargs["entry_signal"], False)
        self.assertEqual(call_2_kwargs["exit_signal"], False)

    def test_engine_generates_correct_order_ids(self):
        df = pd.DataFrame({
            "Open": [100.0, 101.0, 102.0],
            "entry_signal": [True, False, False],
            "exit_signal": [False, True, False],
        })
        portfolio = run_simulated_paper_trading(df, "AAPL", 100000.0, quantity_per_trade=100)
        orders = portfolio.trade_log.orders
        self.assertEqual(len(orders), 2)
        self.assertEqual(orders[0].order_id, "AAPL-BUY-0")
        self.assertEqual(orders[1].order_id, "AAPL-SELL-1")
