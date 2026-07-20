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

class DailyParameterSweepReviewerTest(unittest.TestCase):
    def test_missing_error_column_is_candidate_error_and_continues(self) -> None:
        candidates = _backtests().iloc[[1, 2]].reset_index(drop=True)
        missing_error = pd.DataFrame([{"Sharpe Ratio": 1.0}])
        with patch.object(daily_report, "run_parameter_sweep", side_effect=[missing_error, _detail()]):
            highlights, limits = daily_report.run_candidate_parameter_sweep_validation(
                candidates, parameter_sweep_top=2, strategy="score", period="1y", interval="1d",
                auto_adjust=False, force_refresh=False, sort_by="Sharpe Ratio",
                initial_capital=100000, fee_rate=0.001, tax_rate=0.003, position_size=1.0,
            )
        self.assertEqual(highlights["Status"].tolist(), ["ERROR", "PARTIAL"])
        self.assertIn("missing required Error column", highlights.iloc[0]["Error"])
        self.assertIn("missing required Error column", limits[0])

    def test_empty_result_is_candidate_error(self) -> None:
        with patch.object(daily_report, "run_parameter_sweep", return_value=pd.DataFrame()):
            highlights, limits = daily_report.run_candidate_parameter_sweep_validation(
                _backtests(), parameter_sweep_top=1, strategy="score", period="1y", interval="1d",
                auto_adjust=False, force_refresh=False, sort_by="Sharpe Ratio",
                initial_capital=100000, fee_rate=0.001, tax_rate=0.003, position_size=1.0,
            )
        self.assertEqual(highlights.iloc[0]["Status"], "ERROR")
        self.assertIn("no parameter sweep combinations were returned", limits[0])

    def test_all_combinations_failed_is_error(self) -> None:
        failed = pd.DataFrame(
            [{"Strategy": "score", "Parameters": "a", "Error": "first"},
             {"Strategy": "score", "Parameters": "b", "Error": "second"}],
            columns=["Strategy", "Parameters", "Error"],
        )
        with patch.object(daily_report, "run_parameter_sweep", return_value=failed):
            highlights, limits = daily_report.run_candidate_parameter_sweep_validation(
                _backtests(), parameter_sweep_top=1, strategy="score", period="1y", interval="1d",
                auto_adjust=False, force_refresh=False, sort_by="Sharpe Ratio",
                initial_capital=100000, fee_rate=0.001, tax_rate=0.003, position_size=1.0,
            )
        row = highlights.iloc[0]
        self.assertEqual(row["Status"], "ERROR")
        self.assertEqual(row["Parameter Combinations"], 2)
        self.assertEqual(row["Successful Combinations"], 0)
        self.assertEqual(row["Error Combinations"], 2)
        self.assertIn("2 failed combination(s): first", limits[0])

    def test_scalar_highlight_contains_no_nested_values(self) -> None:
        with patch.object(daily_report, "run_parameter_sweep", return_value=_detail()):
            highlights, _ = daily_report.run_candidate_parameter_sweep_validation(
                _backtests(), parameter_sweep_top=1, strategy="score", period="1y", interval="1d",
                auto_adjust=False, force_refresh=False, sort_by="Sharpe Ratio",
                initial_capital=100000, fee_rate=0.001, tax_rate=0.003, position_size=1.0,
            )
        for value in highlights.iloc[0].tolist():
            self.assertNotIsInstance(value, (pd.DataFrame, pd.Series, dict, list))

    def test_invalid_sort_metric_fails_before_provider_or_engine(self) -> None:
        provider = Mock()
        with patch.object(daily_report, "run_parameter_sweep") as engine:
            with self.assertRaisesRegex(ValueError, "Unsupported parameter sweep sort metric"):
                daily_report.run_candidate_parameter_sweep_validation(
                    _backtests(), parameter_sweep_top=1, strategy="score", period="1y", interval="1d",
                    auto_adjust=False, force_refresh=False, sort_by="Not a metric",
                    initial_capital=100000, fee_rate=0.001, tax_rate=0.003, position_size=1.0,
                    analysis_provider=provider,
                )
        provider.assert_not_called()
        engine.assert_not_called()

    def test_sweep_failure_does_not_change_walk_forward_eligibility(self) -> None:
        from tw_stock_tool.reports.daily_report import run_candidate_walk_forward_validation
        candidates = _backtests().iloc[[1, 2]].reset_index(drop=True)
        with patch.object(daily_report, "run_parameter_sweep", side_effect=ValueError("sweep failed")):
            sweep, _ = daily_report.run_candidate_parameter_sweep_validation(
                candidates, parameter_sweep_top=2, strategy="score", period="1y", interval="1d",
                auto_adjust=False, force_refresh=False, sort_by="Sharpe Ratio",
                initial_capital=100000, fee_rate=0.001, tax_rate=0.003, position_size=1.0,
            )
        self.assertTrue((sweep["Status"] == "ERROR").all())
        wf_detail = pd.DataFrame([{
            "Window": 1, "Test Total Return %": 1.0, "Test CAGR %": 1.0,
            "Test Sharpe Ratio": 1.0, "Test Max Drawdown %": -1.0, "Error": "",
        }])
        with patch.object(daily_report, "run_walk_forward", return_value=wf_detail) as wf:
            highlights, _ = run_candidate_walk_forward_validation(
                candidates, walk_forward_top=2, strategy="score", period="1y", interval="1d",
                auto_adjust=False, force_refresh=False, train_days=2, test_days=1, step_days=1,
                sort_by="Train Sharpe Ratio", initial_capital=100000, fee_rate=0.001,
                tax_rate=0.003, position_size=1.0,
            )
        self.assertEqual(wf.call_count, 2)
        self.assertEqual(wf.call_args_list[0].kwargs["stock_id"], "2330")
        self.assertEqual(wf.call_args_list[1].kwargs["stock_id"], "2317")
        self.assertEqual(highlights["Stock"].tolist(), ["2330", "2317"])

    def test_scanner_backtest_sweep_walk_forward_share_cached_provider(self) -> None:
        from tw_stock_tool.analysis.analysis_session import AnalysisSession
        from tw_stock_tool.analysis.scanner import ScanConfig, scan_one_stock
        from tw_stock_tool.reports.daily_report import (
            run_candidate_backtest_validation,
            run_candidate_walk_forward_validation,
        )
        source = _analysis("2330")
        signal_df = source.signal_df.copy()
        for key, value in {
            "MA5": 100.0, "MA20": 100.0, "MA60": 100.0, "RSI": 50.0,
            "MACD": 1.0, "MACD_Signal": 0.5, "K": 50.0, "D": 45.0,
            "BB_Upper": 110.0, "BB_Middle": 100.0, "BB_Lower": 90.0,
            "ATR": 1.0, "OBV": 1000.0, "Volume_Ratio": 1.2,
        }.items():
            signal_df[key] = value
        analysis = StockAnalysis(
            stock_id=source.stock_id, symbol=source.symbol, raw_df=source.raw_df,
            indicator_df=source.indicator_df, signal_df=signal_df,
            latest=signal_df.iloc[-1], summary={"Analysis": "test"},
        )
        analyzer = Mock(return_value=analysis)
        session = AnalysisSession(
            period="1y", interval="1d", auto_adjust=False, force_refresh=True, analyzer=analyzer
        )
        provider = session.get
        scan_row = scan_one_stock("2330", ScanConfig(force_refresh=True, analysis_provider=provider))
        self.assertEqual(scan_row["Status"], "OK")
        candidates = pd.DataFrame([{"Rank": 1, "Stock": "2330", "Signal": "BUY", "Score": 5.0}])
        result = {
            "start_date": "2024-01-01", "end_date": "2024-01-02", "Total Return %": 1.0,
            "Buy and Hold Return %": 1.0, "Trade Count": 1, "Win Rate %": 100.0,
            "Max Drawdown %": -1.0, "Sharpe Ratio": 1.0,
        }
        with patch.object(daily_report, "run_backtest_result", return_value=result):
            backtests, _ = run_candidate_backtest_validation(
                candidates, validate_top=1, strategy="score", period="1y", interval="1d",
                auto_adjust=False, force_refresh=True, initial_capital=100000, fee_rate=0.001,
                tax_rate=0.003, position_size=1.0, analysis_provider=provider,
            )
        with patch.object(daily_report, "run_parameter_sweep", return_value=_detail()) as sweep:
            daily_report.run_candidate_parameter_sweep_validation(
                backtests, parameter_sweep_top=1, strategy="score", period="1y", interval="1d",
                auto_adjust=False, force_refresh=True, sort_by="Sharpe Ratio", initial_capital=100000,
                fee_rate=0.001, tax_rate=0.003, position_size=1.0, analysis_provider=provider,
            )
        wf_detail = pd.DataFrame([{
            "Window": 1, "Test Total Return %": 1.0, "Test CAGR %": 1.0,
            "Test Sharpe Ratio": 1.0, "Test Max Drawdown %": -1.0, "Error": "",
        }])
        with patch.object(daily_report, "run_walk_forward", return_value=wf_detail) as wf:
            run_candidate_walk_forward_validation(
                backtests, walk_forward_top=1, strategy="score", period="1y", interval="1d",
                auto_adjust=False, force_refresh=True, train_days=2, test_days=1, step_days=1,
                sort_by="Train Sharpe Ratio", initial_capital=100000, fee_rate=0.001,
                tax_rate=0.003, position_size=1.0, analysis_provider=provider,
            )
        self.assertIs(sweep.call_args.kwargs["analysis"], analysis)
        self.assertIs(wf.call_args.kwargs["analysis"], analysis)
        analyzer.assert_called_once_with(
            stock_id="2330", period="1y", interval="1d", auto_adjust=False, force_refresh=True,
        )
