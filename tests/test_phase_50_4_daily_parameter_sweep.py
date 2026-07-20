import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tw_stock_tool.analysis.analysis import StockAnalysis
from tw_stock_tool.backtesting import parameter_sweep
from tw_stock_tool.cli import daily_report_cli
from tw_stock_tool.reports import daily_report


def _analysis(stock_id: str = "2330") -> StockAnalysis:
    signal_df = pd.DataFrame(
        {"Open": [100.0, 101.0], "Close": [100.0, 101.0], "Signal": ["HOLD", "BUY"], "Score": [0, 5]}
    )
    return StockAnalysis(
        stock_id=stock_id,
        symbol=f"{stock_id}.TW",
        raw_df=pd.DataFrame(),
        indicator_df=pd.DataFrame(),
        signal_df=signal_df,
        latest=signal_df.iloc[-1],
        summary={},
    )


def _backtests() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Rank": 1, "Stock": "bad", "Signal": "BUY", "Score": 7, "Status": "ERROR"},
            {"Rank": 2, "Stock": "2330", "Signal": "BUY", "Score": 6, "Status": "OK"},
            {"Rank": 3, "Stock": "2317", "Signal": "WATCH", "Score": 5, "Status": "OK"},
        ]
    )


def _detail() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Strategy": "score", "Parameters": "low", "Total Return %": 10, "Sharpe Ratio": 0.1, "Error": ""},
            {"Strategy": "score", "Parameters": "high", "Total Return %": 5, "Sharpe Ratio": 0.9, "Error": ""},
            {"Strategy": "score", "Parameters": "bad", "Total Return %": None, "Sharpe Ratio": None, "Error": "bad params"},
        ],
        columns=parameter_sweep.SWEEP_COLUMNS,
    )


class ParameterSweepEngineTest(unittest.TestCase):
    def test_forwards_interval_and_auto_adjust_and_reuses_analysis(self) -> None:
        analysis = _analysis()
        with patch.object(parameter_sweep, "analyze_stock", return_value=analysis) as analyzer, patch.object(
            parameter_sweep, "run_backtest", return_value={
                "Total Return %": 1, "Buy and Hold Return %": 1, "CAGR %": 1,
                "Trade Count": 1, "Win Rate %": 1, "Max Drawdown %": -1,
                "Profit Factor": 1, "Sharpe Ratio": 1, "Sortino Ratio": 1,
            }
        ) as backtest:
            parameter_sweep.run_parameter_sweep(
                "2330", strategy="score", top=1, interval="1wk", auto_adjust=True,
            )
            analyzer.assert_called_once_with(
                stock_id="2330", period="1y", interval="1wk", auto_adjust=True, force_refresh=False,
            )
            self.assertEqual(backtest.call_args.kwargs["interval"], "1wk")

        with patch.object(parameter_sweep, "analyze_stock") as analyzer, patch.object(
            parameter_sweep, "run_backtest", return_value={
                "Total Return %": 1, "Buy and Hold Return %": 1, "CAGR %": 1,
                "Trade Count": 1, "Win Rate %": 1, "Max Drawdown %": -1,
                "Profit Factor": 1, "Sharpe Ratio": 1, "Sortino Ratio": 1,
            }
        ):
            parameter_sweep.run_parameter_sweep("2330", strategy="score", top=1, analysis=analysis)
            analyzer.assert_not_called()


class DailyParameterSweepHelperTest(unittest.TestCase):
    def test_disabled_and_eligibility(self) -> None:
        with patch.object(daily_report, "run_parameter_sweep") as engine:
            empty, limits = daily_report.run_candidate_parameter_sweep_validation(
                _backtests(), parameter_sweep_top=0, strategy="score", period="1y", interval="1d",
                auto_adjust=False, force_refresh=True, sort_by="Sharpe Ratio",
                initial_capital=100000, fee_rate=0.001, tax_rate=0.003, position_size=1.0,
            )
            self.assertEqual(empty.columns.tolist(), daily_report.PARAMETER_SWEEP_HIGHLIGHT_COLUMNS)
            self.assertEqual(limits, [])
            engine.assert_not_called()

        with patch.object(daily_report, "run_parameter_sweep", return_value=_detail()) as engine:
            highlights, limits = daily_report.run_candidate_parameter_sweep_validation(
                _backtests(), parameter_sweep_top=1, strategy="score", period="2y", interval="1wk",
                auto_adjust=True, force_refresh=True, sort_by="Total Return %",
                initial_capital=200000, fee_rate=0.0, tax_rate=0.001, position_size=0.5,
                analysis_provider=Mock(return_value=_analysis("2330")),
            )
        self.assertEqual(highlights.iloc[0]["Stock"], "2330")
        self.assertEqual(highlights.iloc[0]["Status"], "PARTIAL")
        self.assertEqual(highlights.iloc[0]["Best Parameters"], "low")
        self.assertEqual(highlights.iloc[0]["Parameter Combinations"], 3)
        self.assertEqual(highlights.iloc[0]["Successful Combinations"], 2)
        self.assertEqual(highlights.iloc[0]["Error Combinations"], 1)
        self.assertIn("1 failed combination(s): bad params", limits[0])
        self.assertEqual(engine.call_args.kwargs["top"], 0)
        self.assertTrue(engine.call_args.kwargs["force_refresh"])
        self.assertEqual(engine.call_args.kwargs["interval"], "1wk")

    def test_failure_isolation_and_macd_rejection(self) -> None:
        provider = Mock(side_effect=[_analysis("2330"), _analysis("2317")])
        with patch.object(daily_report, "run_parameter_sweep", side_effect=[_detail(), ValueError("network down")]):
            highlights, limits = daily_report.run_candidate_parameter_sweep_validation(
                _backtests(), parameter_sweep_top=2, strategy="score", period="1y", interval="1d",
                auto_adjust=False, force_refresh=False, sort_by="Sharpe Ratio",
                initial_capital=100000, fee_rate=0.001, tax_rate=0.003, position_size=1.0,
                analysis_provider=provider,
            )
        self.assertEqual(highlights["Status"].tolist(), ["PARTIAL", "ERROR"])
        self.assertIn("Parameter sweep for 2317 failed: network down", limits)
        self.assertEqual(provider.call_count, 2)
        with self.assertRaises(ValueError):
            daily_report.run_candidate_parameter_sweep_validation(
                _backtests(), parameter_sweep_top=1, strategy="macd", period="1y", interval="1d",
                auto_adjust=False, force_refresh=False, sort_by="Sharpe Ratio",
                initial_capital=100000, fee_rate=0.001, tax_rate=0.003, position_size=1.0,
            )


class DailyParameterSweepCliTest(unittest.TestCase):
    def test_parser_defaults_and_dependencies(self) -> None:
        args = daily_report_cli._parse_args([])
        self.assertEqual(args.parameter_sweep_top, 0)
        self.assertEqual(args.parameter_sweep_sort_by, "Sharpe Ratio")
        for option in (
            ["--parameter-sweep-top", "1"],
            ["--parameter-sweep-top", "3", "--validate-top", "2"],
            ["--parameter-sweep-top", "1", "--validate-top", "1", "--validation-strategy", "macd"],
        ):
            with self.assertRaises(SystemExit) as raised:
                daily_report_cli._parse_args(option)
            self.assertEqual(raised.exception.code, 2)

    @patch("tw_stock_tool.cli.daily_report_cli.render_daily_report_markdown", return_value="# Report")
    @patch("tw_stock_tool.cli.daily_report_cli.build_daily_report_data", return_value={})
    @patch("tw_stock_tool.cli.daily_report_cli.build_data_limitations_from_ranking", return_value=[])
    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_report", return_value=(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None))
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids", return_value=["2330"])
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_execution_order_report_and_provider(
        self, mock_open, mock_mkdir, collect, run_daily, limitations, build, render,
    ) -> None:
        events: list[str] = []
        backtests = pd.DataFrame([{"Stock": "2330", "Status": "OK"}])
        sweep = pd.DataFrame([{"Status": "OK"}])
        with patch.object(daily_report_cli, "run_candidate_backtest_validation", side_effect=lambda *a, **k: (events.append("backtest") or (backtests, []))), patch.object(
            daily_report_cli, "run_candidate_parameter_sweep_validation", side_effect=lambda *a, **k: (events.append("sweep") or (sweep, [])),
        ) as sweep_runner, patch.object(
            daily_report_cli, "run_candidate_walk_forward_validation", side_effect=lambda *a, **k: (events.append("walk-forward") or (pd.DataFrame(), [])),
        ):
            with patch.object(sys, "argv", ["daily_report_cli.py", "--stocks", "2330", "--validate-top", "1", "--parameter-sweep-top", "1", "--walk-forward-top", "1"]):
                self.assertIsNone(daily_report_cli.main())
        self.assertEqual(events, ["backtest", "sweep", "walk-forward"])
        self.assertTrue(build.call_args.kwargs["parameter_sweep_highlights"].equals(sweep))
        self.assertTrue(any("does not change candidate ranking" in note for note in build.call_args.kwargs["risk_notes"]))
        self.assertIsNotNone(sweep_runner.call_args.kwargs["analysis_provider"])


if __name__ == "__main__":
    unittest.main()
