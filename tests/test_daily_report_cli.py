import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tw_stock_tool.cli import daily_report_cli
from tw_stock_tool.cli.daily_report_cli import _parse_args, main


class TestDailyReportCli(unittest.TestCase):
    def test_parse_args_defaults_and_custom_values(self):
        args = _parse_args([])
        self.assertIsNone(args.stocks)
        self.assertEqual(args.stock_market, "all")
        self.assertEqual(args.output_dir, "output")
        self.assertIsNone(args.output_md)
        custom = _parse_args(["--stocks", "2330", "2317", "--output-md", "test.md"])
        self.assertEqual(custom.stocks, ["2330", "2317"])
        self.assertEqual(custom.output_md, "test.md")

    def test_config_adapter_converts_signals_to_tuple(self):
        args = _parse_args(["--signals", "BUY", "WATCH", "--output-excel", "daily.xlsx"])
        config = daily_report_cli._pipeline_config_from_args(args)
        self.assertEqual(config.signals, ("BUY", "WATCH"))
        self.assertEqual(config.output_excel, "daily.xlsx")

    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_research_pipeline")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids", return_value=["2330"])
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_main_calls_pipeline_and_writes_default_markdown(self, mock_open, mock_mkdir, mock_collect, mock_run):
        mock_run.return_value = Mock(markdown="# Report")
        with patch.object(sys, "argv", ["daily_report_cli.py", "--stocks", "2330"]):
            result = main()
        self.assertIsNone(result)
        mock_collect.assert_called_once()
        mock_run.assert_called_once()
        config = mock_run.call_args.args[1]
        self.assertEqual(config.signals, ("BUY", "WATCH"))
        self.assertEqual(config.output_excel, None)
        mock_open.assert_called_once_with(Path("output/daily_report.md"), "w", encoding="utf-8")
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        self.assertTrue(callable(mock_run.call_args.kwargs["status_callback"]))

    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_research_pipeline")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids", return_value=["2330"])
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_main_writes_custom_markdown_and_forwards_excel(self, mock_open, mock_mkdir, mock_collect, mock_run):
        mock_run.return_value = Mock(markdown="# Report")
        with patch.object(sys, "argv", [
            "daily_report_cli.py", "--stocks", "2330",
            "--output-md", "custom/report.md", "--output-excel", "daily.xlsx",
        ]):
            result = main()
        self.assertIsNone(result)
        self.assertEqual(mock_run.call_args.args[1].output_excel, "daily.xlsx")
        mock_open.assert_called_once_with(Path("custom/report.md"), "w", encoding="utf-8")

    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_research_pipeline")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids", return_value=["2330"])
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_main_uses_custom_output_directory(self, mock_open, mock_mkdir, mock_collect, mock_run):
        mock_run.return_value = Mock(markdown="# Report")
        with patch.object(sys, "argv", ["daily_report_cli.py", "--stocks", "2330", "--output-dir", "reports"]):
            self.assertIsNone(main())
        mock_open.assert_called_once_with(Path("reports/daily_report.md"), "w", encoding="utf-8")
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_research_pipeline", return_value=Mock(markdown="# Report"))
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids", return_value=["2330"])
    @patch("builtins.open", side_effect=PermissionError("locked"))
    def test_markdown_write_failure_returns_one(self, mock_open, mock_collect, mock_run):
        output = StringIO()
        with patch.object(sys, "argv", ["daily_report_cli.py", "--stocks", "2330"]), patch.object(
            sys, "stdout", output
        ):
            result = main()
        self.assertEqual(result, 1)
        self.assertIn("Error:", output.getvalue())
        self.assertIn("locked", output.getvalue())

    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_research_pipeline")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids", return_value=[])
    def test_no_stocks_are_rejected_by_the_core_runner(self, mock_collect, mock_run):
        mock_run.side_effect = ValueError("No stocks provided.")
        with patch.object(sys, "argv", ["daily_report_cli.py", "--stocks"]):
            result = main()
        self.assertEqual(result, 1)
        mock_run.assert_called_once()

    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_research_pipeline")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids", return_value=["2330"])
    def test_pipeline_exception_returns_one(self, mock_collect, mock_run):
        mock_run.side_effect = RuntimeError("pipeline failed")
        with patch.object(sys, "argv", ["daily_report_cli.py", "--stocks", "2330"]):
            result = main()
        self.assertEqual(result, 1)

    def test_invalid_dependency_exits_two_before_pipeline(self):
        with self.assertRaises(SystemExit) as raised:
            _parse_args(["--parameter-sweep-top", "1"])
        self.assertEqual(raised.exception.code, 2)

    def test_parser_rejects_invalid_numeric_values(self):
        for argv in (
            ["--validate-top", "-1"],
            ["--validation-initial-capital", "0"],
            ["--validation-fee-rate", "-0.1"],
            ["--validation-tax-rate", "nan"],
            ["--validation-position-size", "1.1"],
            ["--walk-forward-train-days", "0"],
            ["--walk-forward-test-days", "0"],
            ["--walk-forward-step-days", "0"],
        ):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as raised:
                _parse_args(argv)
            self.assertEqual(raised.exception.code, 2)

    def test_macd_remains_valid_for_backtest_only(self):
        args = _parse_args(["--validate-top", "1", "--validation-strategy", "macd"])
        self.assertEqual(args.validation_strategy, "macd")


if __name__ == "__main__":
    unittest.main()
