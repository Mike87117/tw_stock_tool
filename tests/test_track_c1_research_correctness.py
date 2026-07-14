import math
import unittest
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.analysis import analysis
from tw_stock_tool.analysis.indicators import add_indicators
from tw_stock_tool.analysis.signals import generate_signals
from tw_stock_tool.backtesting.backtest import BacktestError, run_backtest
from tw_stock_tool.backtesting.metrics import calculate_sharpe, calculate_sortino
from tw_stock_tool.cli import main as analyze_cli
from tw_stock_tool.kill_switch.models import KillSwitchState
from tw_stock_tool.ml import ai_walk_forward
from tw_stock_tool.ml.ai_walk_forward import split_time_windows
from tw_stock_tool.paper_trading.models import PaperTradingModelError, SimulatedFill, SimulatedOrder, SimulatedPortfolio
from tw_stock_tool.risk.models import RiskDecision, RiskInputSnapshot, RiskModelError
from tw_stock_tool.risk.rules import (
    check_max_order_notional, check_max_position_notional, check_max_total_exposure,
)
from tw_stock_tool.simulated_paper_trading_guard import SimulatedPaperTradingGuardAdapter
from tw_stock_tool.simulated_paper_trading_guard.models import SimulatedPaperTradingGuardError
from tw_stock_tool.utils.config import VALID_INTERVALS

NONFINITE_VALUES = (("nan", float("nan")), ("positive_infinity", float("inf")), ("negative_infinity", -float("inf")))


def _collect_unrejected_cases(cases):
    accepted = []
    for case_name, invoke, expected_error in cases:
        try:
            invoke()
        except expected_error:
            continue
        except Exception as exc:
            accepted.append(f"{case_name}: wrong exception {type(exc).__name__}: {exc}")
        else:
            accepted.append(f"{case_name}: accepted")
    return accepted


def _rising_ohlcv(rows=100):
    index = pd.date_range("2024-01-01", periods=rows, freq="D")
    close = [100.0 + number for number in range(rows)]
    return pd.DataFrame({"Open": close, "High": [value + 1 for value in close], "Low": [value - 1 for value in close], "Close": close, "Volume": [1000.0] * rows}, index=index)


def _flat_ohlcv(rows=130):
    index = pd.date_range("2024-01-01", periods=rows, freq="D")
    close = [100.0] * rows
    return pd.DataFrame({"Open": close, "High": [101.0] * rows, "Low": [99.0] * rows, "Close": close, "Volume": [1000.0] * rows}, index=index)


def _backtest_frame():
    return pd.DataFrame({"Open": [100.0, 101.0, 102.0], "Close": [100.0, 101.0, 102.0], "Signal": ["HOLD", "HOLD", "HOLD"]}, index=pd.date_range("2024-01-01", periods=3, freq="D"))


def _snapshot(**overrides):
    values = dict(symbol="2330", side="BUY", quantity=1, price=100.0, cash=1000.0)
    values.update(overrides)
    return RiskInputSnapshot(**values)


class TrackC1ResearchCorrectnessTest(unittest.TestCase):
    def test_generate_signals_keeps_rows_with_finite_rsi(self):
        indicators = add_indicators(_rising_ohlcv())
        result = generate_signals(indicators)
        self.assertEqual(len(result), len(indicators))
        self.assertTrue((result["RSI"].iloc[14:] == 100.0).all())

    def test_analyze_stock_keeps_rising_rows_when_rsi_is_finite(self):
        with patch.object(analysis, "download_tw_stock", return_value=(_rising_ohlcv(), "2330.TW")):
            result = analysis.analyze_stock("2330")

        self.assertFalse(result.signal_df.empty)
        self.assertEqual(float(result.latest["RSI"]), 100.0)
        self.assertEqual(float(result.summary["RSI"]), 100.0)
        self.assertTrue(math.isfinite(float(result.latest["RSI"])))
        self.assertEqual(result.latest.name, result.signal_df.index[-1])

    def test_analyze_stock_keeps_flat_rows_with_neutral_rsi(self):
        with patch.object(analysis, "download_tw_stock", return_value=(_flat_ohlcv(), "2330.TW")):
            result = analysis.analyze_stock("2330")

        self.assertFalse(result.signal_df.empty)
        self.assertEqual(float(result.latest["RSI"]), 50.0)
        self.assertEqual(float(result.summary["RSI"]), 50.0)
        self.assertTrue(math.isfinite(float(result.latest["RSI"])))
        self.assertFalse(bool(result.latest["RSI_Hot"]))
        self.assertFalse(bool(result.latest["RSI_Cold"]))

    def test_walk_forward_purges_train_labels_that_reach_test_window(self):
        horizon = 5
        dataset = pd.DataFrame({"Close": range(17)}, index=pd.date_range("2024-01-01", periods=17, freq="D"))
        _, train, test = split_time_windows(dataset, train_size=8, test_size=4, purge_size=horizon)[0]
        first_test_date = test.index[0]
        label_dates = [(feature_row_date, dataset.index[dataset.index.get_loc(feature_row_date) + horizon]) for feature_row_date in train.index]
        self.assertLess(train.index[-1], first_test_date)
        self.assertFalse(any(feature_row_date < first_test_date <= label_source_date for feature_row_date, label_source_date in label_dates))
        self.assertEqual(dataset.index.get_loc(first_test_date) - dataset.index.get_loc(train.index[-1]) - 1, horizon)
        last_train_label_source_date = label_dates[-1][1]
        self.assertEqual(last_train_label_source_date, dataset.index[12])
        self.assertEqual(first_test_date, dataset.index[13])
        self.assertLess(last_train_label_source_date, first_test_date)

    def test_risk_snapshot_rejects_all_nonfinite_numeric_fields(self):
        cases = []
        for field in ("price", "cash", "current_position_notional", "total_exposure"):
            for value_name, value in NONFINITE_VALUES:
                cases.append((f"{field}/{value_name}", lambda field=field, value=value: _snapshot(**{field: value}), RiskModelError))
        self.assertEqual(_collect_unrejected_cases(cases), [])

    def test_risk_monetary_limits_reject_all_nonfinite_values(self):
        snapshot = _snapshot()
        cases = []
        for name, rule in (("order_notional_limit", check_max_order_notional), ("position_notional_limit", check_max_position_notional), ("total_exposure_limit", check_max_total_exposure)):
            for value_name, value in NONFINITE_VALUES:
                cases.append((f"{name}/{value_name}", lambda rule=rule, value=value: rule(snapshot, value), RiskModelError))
        self.assertEqual(_collect_unrejected_cases(cases), [])

    def test_risk_quantity_limit_rejects_nonfinite_values(self):
        from tw_stock_tool.risk.rules import check_max_position_quantity
        cases = [(f"quantity_limit/{name}", lambda value=value: check_max_position_quantity(_snapshot(), value), RiskModelError) for name, value in NONFINITE_VALUES]
        self.assertEqual(_collect_unrejected_cases(cases), [])

    def test_simulated_fill_and_portfolio_reject_all_nonfinite_money(self):
        cases = []
        for field in ("price", "fee", "tax", "slippage"):
            for value_name, value in NONFINITE_VALUES:
                cases.append((f"fill.{field}/{value_name}", lambda field=field, value=value: SimulatedFill("o", "2330", "BUY", 1, filled_at=None, **{field: value}) if field == "price" else SimulatedFill("o", "2330", "BUY", 1, 100.0, None, **{field: value}), PaperTradingModelError))
        for value_name, value in NONFINITE_VALUES:
            cases.append((f"portfolio.cash/{value_name}", lambda value=value: SimulatedPortfolio(value), PaperTradingModelError))
        self.assertEqual(_collect_unrejected_cases(cases), [])

    def test_portfolio_arithmetic_rejects_nonfinite_fill_before_contamination(self):
        portfolio = SimulatedPortfolio(1000.0)
        fill = SimulatedFill("o", "2330", "BUY", 1, 100.0, None)
        fill.price = float("nan")
        initial_cash = portfolio.cash
        initial_positions = dict(portfolio.positions)
        initial_fills = list(portfolio.trade_log.fills)

        with self.assertRaises(PaperTradingModelError):
            portfolio.apply_fill(fill)

        self.assertEqual(portfolio.cash, initial_cash)
        self.assertEqual(portfolio.cash, 1000.0)
        self.assertTrue(math.isfinite(portfolio.cash))
        self.assertEqual(portfolio.positions, initial_positions)
        self.assertEqual(portfolio.position_for("2330").quantity, 0)
        self.assertEqual(portfolio.trade_log.fills, initial_fills)
        self.assertEqual(len(portfolio.trade_log.fills), 0)

    def test_backtest_rejects_all_nonfinite_parameters_and_prices(self):
        cases = []
        for field in ("initial_capital", "fee_rate", "tax_rate", "position_size", "stop_loss_pct", "take_profit_pct"):
            for value_name, value in NONFINITE_VALUES:
                cases.append((f"parameter.{field}/{value_name}", lambda field=field, value=value: run_backtest(_backtest_frame(), **{field: value}), BacktestError))
        for field in ("Open", "Close"):
            for value_name, value in NONFINITE_VALUES:
                def invoke(field=field, value=value):
                    frame = _backtest_frame().copy()
                    frame.loc[frame.index[1], field] = value
                    run_backtest(frame)
                cases.append((f"price.{field}/{value_name}", invoke, BacktestError))
        self.assertEqual(_collect_unrejected_cases(cases), [])

    def test_guard_adapter_rejects_boolean_zero_and_negative_reference_prices(self):
        order = SimulatedOrder("o", "2330", "BUY", 1, None)
        cases = []
        for value_name, value in (("bool", True), ("zero", 0.0), ("negative", -1.0), ("negative_infinity", -float("inf"))):
            cases.append((value_name, lambda value=value: SimulatedPaperTradingGuardAdapter(KillSwitchState(), lambda *_: value, lambda _: RiskDecision.allow())(order, SimulatedPortfolio(1000.0)), SimulatedPaperTradingGuardError))
        self.assertEqual(_collect_unrejected_cases(cases), [])

    def test_guard_adapter_rejects_all_nonfinite_positive_reference_prices(self):
        order = SimulatedOrder("o", "2330", "BUY", 1, None)
        cases = [(name, lambda value=value: SimulatedPaperTradingGuardAdapter(KillSwitchState(), lambda *_: value, lambda _: RiskDecision.allow())(order, SimulatedPortfolio(1000.0)), SimulatedPaperTradingGuardError) for name, value in (("nan", float("nan")), ("positive_infinity", float("inf")))]
        self.assertEqual(_collect_unrejected_cases(cases), [])

    def test_guard_adapter_rejects_nonfinite_and_boolean_exposure(self):
        order = SimulatedOrder("o", "2330", "BUY", 1, None)
        cases = []
        for value_name, value in (("bool", True), *NONFINITE_VALUES, ("negative", -1.0)):
            cases.append((value_name, lambda value=value: SimulatedPaperTradingGuardAdapter(KillSwitchState(), lambda *_: 100.0, lambda _: RiskDecision.allow(), portfolio_exposure_provider=lambda *_: value)(order, SimulatedPortfolio(1000.0)), SimulatedPaperTradingGuardError))
        self.assertEqual(_collect_unrejected_cases(cases), [])

    def test_analyze_propagates_selected_interval_to_backtest(self):
        signal_df = _backtest_frame()
        analysis_result = type(
            "AnalysisResult",
            (),
            {"signal_df": signal_df, "symbol": "2330.TW", "summary": {}},
        )()
        with patch.object(analyze_cli, "OUTPUT_DIR"), patch.object(
            analyze_cli, "analyze_stock", return_value=analysis_result
        ) as analyze_stock, patch.object(
            analyze_cli, "run_backtest", return_value={}
        ) as backtest:
            analyze_cli.run_analysis_result(
                analyze_cli.MainOptions(stock_id="2330", interval="1wk")
            )

        self.assertEqual(analyze_stock.call_args.kwargs["interval"], "1wk")
        self.assertEqual(backtest.call_args.kwargs["interval"], "1wk")

    def test_metrics_use_interval_specific_annualization(self):
        equity = pd.Series([100.0, 110.0, 99.0, 108.0, 91.8, 101.0])
        returns = equity.pct_change().dropna()
        downside = returns[returns < 0]
        sharpe_base = returns.mean() / returns.std(ddof=0)
        sortino_base = returns.mean() / downside.std(ddof=0)
        self.assertEqual(VALID_INTERVALS, {"1d", "1wk", "1mo"})
        for interval, periods_per_year in (("1d", 252), ("1wk", 52), ("1mo", 12)):
            with self.subTest(metric="sharpe", interval=interval):
                self.assertAlmostEqual(
                    calculate_sharpe(equity, interval),
                    sharpe_base * math.sqrt(periods_per_year),
                )
            with self.subTest(metric="sortino", interval=interval):
                self.assertAlmostEqual(
                    calculate_sortino(equity, interval),
                    sortino_base * math.sqrt(periods_per_year),
                )
        self.assertEqual(calculate_sharpe(equity), calculate_sharpe(equity, "1d"))
        self.assertEqual(calculate_sortino(equity), calculate_sortino(equity, "1d"))
    def test_argparse_invalid_option_exits_nonzero(self):
        with self.assertRaises(SystemExit) as raised:
            analyze_cli._parse_args(["--period", "invalid"])
        self.assertNotEqual(raised.exception.code, 0)

    def test_ai_walk_forward_runtime_exception_returns_nonzero_exit_status(self):
        args = type("Args", (), {"stock": "2330", "period": "1y", "horizon": 5, "train_size": 8, "test_size": 4, "step_size": None, "force_refresh": False, "dropna": True})()
        with patch.object(ai_walk_forward, "run_ai_walk_forward", side_effect=ValueError("controlled failure")), patch.object(ai_walk_forward, "_parse_args", return_value=args):
            self.assertEqual(ai_walk_forward.main(), 1)

    def test_analyze_cli_runtime_validation_returns_nonzero_exit_status(self):
        self.assertEqual(analyze_cli.main(["--stock", ""]), 1)
