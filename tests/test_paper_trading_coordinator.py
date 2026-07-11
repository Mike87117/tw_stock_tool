import unittest
import pandas as pd
import numpy as np
from unittest.mock import patch, call
from tw_stock_tool.paper_trading.coordinator import run_chronological_multi_symbol_simulated_paper_trading
from tw_stock_tool.paper_trading.runtime import SimulatedPaperTradingRuntimeState
from tw_stock_tool.paper_trading.models import SimulatedPortfolio, SimulatedOrder
from tw_stock_tool.simulated_paper_trading_guard.adapter import SimulatedPaperTradingGuardDecision
from tw_stock_tool.simulated_paper_trading_guard.models import SimulatedPaperTradingGuardError
from tw_stock_tool.simulated_paper_trading_guard.providers import ChronologicalRuntimePortfolioExposureProvider
from tw_stock_tool.risk.config import SimulatedPaperTradingRiskConfig
from tw_stock_tool.simulated_paper_trading_guard.config import SimulatedPaperTradingGuardConfig
from tw_stock_tool.simulated_paper_trading_guard.builder import build_guard_decision_provider_from_config


class TestChronologicalMultiSymbolCoordinator(unittest.TestCase):

    def setUp(self):
        self.runtime_state = SimulatedPaperTradingRuntimeState(
            portfolio=SimulatedPortfolio(cash=100000.0)
        )
        self.df_a = pd.DataFrame({
            "Open": [100.0, 105.0],
            "entry_signal": [True, False],
            "exit_signal": [False, True]
        }, index=pd.to_datetime(["2023-01-01", "2023-01-03"]))

        self.df_b = pd.DataFrame({
            "Open": [50.0, 52.0],
            "entry_signal": [True, False],
            "exit_signal": [False, True]
        }, index=pd.to_datetime(["2023-01-02", "2023-01-04"]))

    def test_validation_invalid_mapping(self):
        with self.assertRaisesRegex(TypeError, "dataframes must be a Mapping"):
            run_chronological_multi_symbol_simulated_paper_trading(
                [], self.runtime_state
            )

    def test_validation_empty_mapping(self):
        with self.assertRaisesRegex(ValueError, "dataframes must not be empty"):
            run_chronological_multi_symbol_simulated_paper_trading(
                {}, self.runtime_state
            )

    def test_validation_invalid_symbol(self):
        with self.assertRaisesRegex(ValueError, "Every symbol key must be a non-blank string"):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"": self.df_a}, self.runtime_state
            )

    def test_validation_invalid_df(self):
        with self.assertRaisesRegex(TypeError, "Value for A must be a pandas DataFrame"):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"A": "not_df"}, self.runtime_state
            )

    def test_validation_empty_df(self):
        with self.assertRaisesRegex(ValueError, "DataFrame for A must not be empty"):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"A": pd.DataFrame()}, self.runtime_state
            )

    def test_validation_missing_open(self):
        df_no_open = pd.DataFrame({"Close": [100.0]}, index=pd.to_datetime(["2023-01-01"]))
        with self.assertRaisesRegex(ValueError, "DataFrame for A must contain 'Open'"):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"A": df_no_open}, self.runtime_state
            )

    def test_validation_invalid_standard_signals(self):
        df_bad_signal = pd.DataFrame({"Open": [100.0]}, index=pd.to_datetime(["2023-01-01"]))
        # Will raise ValueError from validate_standard_signals
        with self.assertRaises(ValueError):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"A": df_bad_signal}, self.runtime_state
            )

    def test_validation_duplicate_index(self):
        df_dup = pd.DataFrame({
            "Open": [100.0, 105.0],
            "entry_signal": [True, False],
            "exit_signal": [False, True]
        }, index=pd.to_datetime(["2023-01-01", "2023-01-01"]))
        with self.assertRaisesRegex(ValueError, "DataFrame index for A must be unique"):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"A": df_dup}, self.runtime_state
            )

    def test_validation_non_monotonic_index(self):
        df_non_mono = pd.DataFrame({
            "Open": [100.0, 105.0],
            "entry_signal": [True, False],
            "exit_signal": [False, True]
        }, index=pd.to_datetime(["2023-01-03", "2023-01-01"]))
        with self.assertRaisesRegex(ValueError, "DataFrame index for A must be monotonic increasing"):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"A": df_non_mono}, self.runtime_state
            )

    def test_validation_non_comparable_index(self):
        df_c = pd.DataFrame({
            "Open": [100.0],
            "entry_signal": [True],
            "exit_signal": [False]
        }, index=["string_index"])
        with self.assertRaisesRegex(TypeError, "Index labels are not comparable across symbols|Mixed index types cannot be compared globally"):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"A": self.df_a, "C": df_c}, self.runtime_state
            )

    def test_validation_invalid_runtime_state(self):
        with self.assertRaisesRegex(TypeError, "runtime_state must be a SimulatedPaperTradingRuntimeState"):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"A": self.df_a}, "not_state"
            )

    def test_validation_invalid_quantity(self):
        with self.assertRaisesRegex(ValueError, "quantity_per_trade must be positive"):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"A": self.df_a}, self.runtime_state, quantity_per_trade=0
            )
        with self.assertRaisesRegex(TypeError, "quantity_per_trade must be an integer, not boolean"):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"A": self.df_a}, self.runtime_state, quantity_per_trade=False
            )

    def test_validation_invalid_costs(self):
        for cost_kwarg in ["fee_rate", "tax_rate", "slippage_per_share"]:
            with self.assertRaisesRegex(ValueError, f"{cost_kwarg} must be non-negative"):
                run_chronological_multi_symbol_simulated_paper_trading(
                    {"A": self.df_a}, self.runtime_state, **{cost_kwarg: -0.1}
                )
            with self.assertRaisesRegex(ValueError, f"{cost_kwarg} must be finite"):
                run_chronological_multi_symbol_simulated_paper_trading(
                    {"A": self.df_a}, self.runtime_state, **{cost_kwarg: float('inf')}
                )
            with self.assertRaisesRegex(TypeError, f"{cost_kwarg} must be numeric, not boolean"):
                run_chronological_multi_symbol_simulated_paper_trading(
                    {"A": self.df_a}, self.runtime_state, **{cost_kwarg: True}
                )

    def test_validation_both_guards(self):
        with self.assertRaisesRegex(ValueError, "Cannot provide both guard_decision and guard_decision_provider"):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"A": self.df_a}, self.runtime_state,
                guard_decision=SimulatedPaperTradingGuardDecision.allow(),
                guard_decision_provider=lambda o, p: SimulatedPaperTradingGuardDecision.allow()
            )

    def test_exact_identity(self):
        returned_state = run_chronological_multi_symbol_simulated_paper_trading(
            {"A": self.df_a}, self.runtime_state
        )
        self.assertIs(returned_state, self.runtime_state)
        self.assertIs(returned_state.portfolio, self.runtime_state.portfolio)

    @patch("tw_stock_tool.paper_trading.coordinator.step_simulated_symbol_bar")
    def test_actual_chronological_interleaving(self, mock_step):
        run_chronological_multi_symbol_simulated_paper_trading(
            {"A": self.df_a, "B": self.df_b}, self.runtime_state
        )
        self.assertEqual(mock_step.call_count, 4)

        # A@2023-01-01, B@2023-01-02, A@2023-01-03, B@2023-01-04
        calls = mock_step.call_args_list
        self.assertEqual(calls[0].kwargs["symbol"], "A")
        self.assertEqual(calls[0].kwargs["index_label"], pd.to_datetime("2023-01-01"))
        self.assertEqual(calls[0].kwargs["bar_position"], 0)

        self.assertEqual(calls[1].kwargs["symbol"], "B")
        self.assertEqual(calls[1].kwargs["index_label"], pd.to_datetime("2023-01-02"))
        self.assertEqual(calls[1].kwargs["bar_position"], 0)

        self.assertEqual(calls[2].kwargs["symbol"], "A")
        self.assertEqual(calls[2].kwargs["index_label"], pd.to_datetime("2023-01-03"))
        self.assertEqual(calls[2].kwargs["bar_position"], 1)

        self.assertEqual(calls[3].kwargs["symbol"], "B")
        self.assertEqual(calls[3].kwargs["index_label"], pd.to_datetime("2023-01-04"))
        self.assertEqual(calls[3].kwargs["bar_position"], 1)

    @patch("tw_stock_tool.paper_trading.coordinator.step_simulated_symbol_bar")
    def test_same_time_deterministic_ordering(self, mock_step):
        df_same = pd.DataFrame({
            "Open": [10.0],
            "entry_signal": [True],
            "exit_signal": [False]
        }, index=pd.to_datetime(["2023-01-01"]))

        run_chronological_multi_symbol_simulated_paper_trading(
            {"B": df_same, "A": df_same}, self.runtime_state
        )

        self.assertEqual(mock_step.call_count, 2)
        calls = mock_step.call_args_list
        self.assertEqual(calls[0].kwargs["symbol"], "A")
        self.assertEqual(calls[1].kwargs["symbol"], "B")

    def test_no_cross_symbol_look_ahead(self):
        # We process A and B. A has a trade at t1. B has a trade at t2.
        # Check that when evaluating B at t2, A's fill from t1 is present, but A's future fill at t3 is not.

        # We can test this by providing a guard that asserts the portfolio state.

        def mock_provider(order, portfolio):
            if order.symbol == "B" and order.signal_time == pd.to_datetime("2023-01-02"):
                self.assertIn("A", self.runtime_state.pending_orders)
                self.assertEqual(portfolio.position_for("A").quantity, 0)
            elif order.symbol == "A" and order.signal_time == pd.to_datetime("2023-01-03"):
                self.assertNotIn("A", self.runtime_state.pending_orders)
                self.assertEqual(portfolio.position_for("A").quantity, 10)
                self.assertIn("B", self.runtime_state.pending_orders)
            elif order.symbol == "B" and order.signal_time == pd.to_datetime("2023-01-04"):
                self.assertEqual(portfolio.position_for("A").quantity, 10)
            return SimulatedPaperTradingGuardDecision.allow()

        run_chronological_multi_symbol_simulated_paper_trading(
            {"A": self.df_a, "B": self.df_b}, self.runtime_state,
            quantity_per_trade=10,
            guard_decision_provider=mock_provider
        )

    def test_pending_fill_only_on_same_symbols_next_bar(self):
        run_chronological_multi_symbol_simulated_paper_trading(
            {"A": self.df_a, "B": self.df_b}, self.runtime_state,
            quantity_per_trade=10
        )

        fills = self.runtime_state.portfolio.trade_log.fills
        # A creates order at t1 (2023-01-01), B at t2 (2023-01-02)
        # B's bar at t2 should NOT fill A. A's next bar is t3 (2023-01-03), so A fills at t3.
        # B fills at t4 (2023-01-04).
        self.assertEqual(len(fills), 2)
        self.assertEqual(fills[0].symbol, "A")
        self.assertEqual(fills[0].filled_at, pd.to_datetime("2023-01-03"))
        self.assertEqual(fills[1].symbol, "B")
        self.assertEqual(fills[1].filled_at, pd.to_datetime("2023-01-04"))

    def test_same_time_pending_buy_reservation_with_actual_risk_rule(self):
        df_a = pd.DataFrame({
            "Open": [100.0],
            "entry_signal": [True],
            "exit_signal": [False]
        }, index=pd.to_datetime(["2023-01-01"]))

        df_b = pd.DataFrame({
            "Open": [100.0],
            "entry_signal": [True],
            "exit_signal": [False]
        }, index=pd.to_datetime(["2023-01-01"]))

        from tw_stock_tool.risk.config import SimulatedPaperTradingRiskConfig
        from tw_stock_tool.simulated_paper_trading_guard.builder import build_guard_decision_provider_from_config
        from tw_stock_tool.simulated_paper_trading_guard.config import SimulatedPaperTradingGuardConfig
        from tw_stock_tool.simulated_paper_trading_guard.providers import ChronologicalRuntimePortfolioExposureProvider

        risk_config = SimulatedPaperTradingRiskConfig(max_total_exposure=1500.0)
        guard_config = SimulatedPaperTradingGuardConfig(risk=risk_config)

        dataframes = {"A": df_a, "B": df_b}
        exposure_provider = ChronologicalRuntimePortfolioExposureProvider(dataframes, self.runtime_state)
        ref_provider = lambda o, p: 100.0
        guard_adapter = build_guard_decision_provider_from_config(guard_config, reference_price_provider=ref_provider, portfolio_exposure_provider=exposure_provider)

        run_chronological_multi_symbol_simulated_paper_trading(
            dataframes,
            self.runtime_state,
            quantity_per_trade=10,
            guard_decision_provider=guard_adapter
        )

        trade_log = self.runtime_state.portfolio.trade_log
        self.assertEqual(len(trade_log.orders), 1)
        self.assertEqual(trade_log.orders[0].symbol, "A")
        self.assertEqual(trade_log.orders[0].side, "BUY")

        self.assertIn("A", self.runtime_state.pending_orders)
        self.assertEqual(self.runtime_state.pending_orders["A"].order.side, "BUY")
        self.assertEqual(self.runtime_state.pending_orders["A"].reference_price, 100.0)
        self.assertEqual(self.runtime_state.pending_orders["A"].reserved_buy_notional, 1000.0)

        self.assertEqual(self.runtime_state.total_reserved_buy_notional, 1000.0)
        self.assertNotIn("B", self.runtime_state.pending_orders)

        self.assertEqual(len(trade_log.rejections), 1)
        self.assertEqual(trade_log.rejections[0].candidate_order.symbol, "B")
        self.assertEqual(trade_log.rejections[0].candidate_order.side, "BUY")

        self.assertEqual(len(trade_log.fills), 0)

    def test_pending_sell_does_not_release_exposure_early(self):
        from tw_stock_tool.paper_trading.models import SimulatedPosition
        self.runtime_state.portfolio.positions["A"] = SimulatedPosition("A", 10, 100.0, 0.0)

        df_a = pd.DataFrame({
            "Open": [100.0],
            "entry_signal": [False],
            "exit_signal": [True]
        }, index=pd.to_datetime(["2023-01-01"]))

        df_b = pd.DataFrame({
            "Open": [100.0],
            "entry_signal": [True],
            "exit_signal": [False]
        }, index=pd.to_datetime(["2023-01-01"]))

        from tw_stock_tool.risk.config import SimulatedPaperTradingRiskConfig
        from tw_stock_tool.simulated_paper_trading_guard.builder import build_guard_decision_provider_from_config
        from tw_stock_tool.simulated_paper_trading_guard.config import SimulatedPaperTradingGuardConfig
        from tw_stock_tool.simulated_paper_trading_guard.providers import ChronologicalRuntimePortfolioExposureProvider

        risk_config = SimulatedPaperTradingRiskConfig(max_total_exposure=1500.0)
        guard_config = SimulatedPaperTradingGuardConfig(risk=risk_config)

        dataframes = {"A": df_a, "B": df_b}
        exposure_provider = ChronologicalRuntimePortfolioExposureProvider(dataframes, self.runtime_state)
        ref_provider = lambda o, p: 100.0
        guard_adapter = build_guard_decision_provider_from_config(guard_config, reference_price_provider=ref_provider, portfolio_exposure_provider=exposure_provider)

        run_chronological_multi_symbol_simulated_paper_trading(
            dataframes,
            self.runtime_state,
            quantity_per_trade=10,
            guard_decision_provider=guard_adapter
        )

        self.assertIn("A", self.runtime_state.portfolio.positions)
        self.assertIn("A", self.runtime_state.pending_orders)
        self.assertEqual(self.runtime_state.pending_orders["A"].order.side, "SELL")
        self.assertEqual(self.runtime_state.pending_orders["A"].reserved_buy_notional, 0.0)

        self.assertEqual(self.runtime_state.total_reserved_buy_notional, 0.0)

        trade_log = self.runtime_state.portfolio.trade_log
        self.assertEqual(len(trade_log.rejections), 1)
        self.assertEqual(trade_log.rejections[0].candidate_order.symbol, "B")
        self.assertEqual(trade_log.rejections[0].candidate_order.side, "BUY")

        self.assertEqual(len(trade_log.orders), 1)
        self.assertEqual(trade_log.orders[0].symbol, "A")
        self.assertEqual(trade_log.orders[0].side, "SELL")

        self.assertEqual(len(trade_log.fills), 0)

    def test_validation_invalid_quantity_negative(self):
        with self.assertRaisesRegex(ValueError, "quantity_per_trade must be positive"):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"A": self.df_a}, self.runtime_state, quantity_per_trade=-10
            )

    def test_validation_costs_nan(self):
        for cost_kwarg in ["fee_rate", "tax_rate", "slippage_per_share"]:
            with self.assertRaisesRegex(ValueError, f"{cost_kwarg} must be finite"):
                run_chronological_multi_symbol_simulated_paper_trading(
                    {"A": self.df_a}, self.runtime_state, **{cost_kwarg: float('nan')}
                )

    def test_validation_non_string_symbol_key(self):
        with self.assertRaisesRegex(ValueError, "Every symbol key must be a non-blank string."):
            run_chronological_multi_symbol_simulated_paper_trading(
                {1: self.df_a}, self.runtime_state # type: ignore
            )

    def test_validation_invalid_static_guard_type(self):
        with self.assertRaisesRegex(TypeError, "guard_decision must be a SimulatedPaperTradingGuardDecision"):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"A": self.df_a}, self.runtime_state, guard_decision="not_a_decision" # type: ignore
            )

    def test_validation_non_callable_dynamic_guard(self):
        with self.assertRaisesRegex(TypeError, "guard_decision_provider must be callable"):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"A": self.df_a}, self.runtime_state, guard_decision_provider="not_callable" # type: ignore
            )

    def test_validation_invalid_standard_signal_dtype(self):
        df_bad = pd.DataFrame({"Open": [10.0], "entry_signal": ["True"], "exit_signal": [False]}, index=pd.to_datetime(["2023-01-01"]))
        with self.assertRaisesRegex(ValueError, "'entry_signal' must be boolean dtype."):
            run_chronological_multi_symbol_simulated_paper_trading(
                {"A": df_bad}, self.runtime_state
            )

    def test_nonnumeric_open_fail_closed_behavior(self):
        df_bad_open = pd.DataFrame({
            "Open": ["invalid"],
            "entry_signal": [True],
            "exit_signal": [False]
        }, index=pd.to_datetime(["2023-01-01"]))

        called = []
        def mock_guard(order, portfolio):
            called.append("guard")
            return SimulatedPaperTradingGuardDecision.allow()

        run_chronological_multi_symbol_simulated_paper_trading(
            {"A": df_bad_open}, self.runtime_state, guard_decision_provider=mock_guard
        )

        self.assertEqual(len(called), 0) # No guard call
        self.assertEqual(len(self.runtime_state.portfolio.trade_log.orders), 0) # No accepted order
        self.assertEqual(len(self.runtime_state.portfolio.trade_log.rejections), 0) # No rejection
        self.assertEqual(len(self.runtime_state.portfolio.trade_log.fills), 0) # No fill
        self.assertNotIn("A", self.runtime_state.pending_orders) # No pending order
