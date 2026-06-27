import unittest
from unittest.mock import patch, MagicMock
import sys
import pandas as pd
from pathlib import Path

from tw_stock_tool.cli.daily_report_cli import _parse_args, main

class TestDailyReportCli(unittest.TestCase):

    def test_parse_args_defaults(self):
        args = _parse_args([])
        self.assertEqual(args.stocks, None)
        self.assertEqual(args.stock_market, "all")
        self.assertEqual(args.output_dir, "output")
        self.assertEqual(args.output_md, None)

    def test_parse_args_custom(self):
        args = _parse_args([
            "--stocks", "2330", "2317",
            "--output-md", "test.md"
        ])
        self.assertEqual(args.stocks, ["2330", "2317"])
        self.assertEqual(args.output_md, "test.md")

    @patch("tw_stock_tool.cli.daily_report_cli.render_daily_report_markdown")
    @patch("tw_stock_tool.cli.daily_report_cli.build_daily_report_data")
    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_report")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids")
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_e2e_mvp_execution_no_output_md(self, mock_open, mock_mkdir, mock_collect, mock_run_daily, mock_build, mock_render):
        mock_collect.return_value = ["2330"]
        summary_df = pd.DataFrame([{"Stocks Scanned": 1}])
        candidates_df = pd.DataFrame([{"Stock": "2330", "Score": 5}])
        mock_run_daily.return_value = (summary_df, candidates_df, pd.DataFrame(), None)
        mock_build.return_value = {"dummy": "data"}
        mock_render.return_value = "# Markdown Report"

        test_args = ["--stocks", "2330"]
        with patch.object(sys, "argv", ["daily_report_cli.py"] + test_args):
            main()

        # output_md should default to output/daily_report.md
        mock_open.assert_called_once_with(Path("output/daily_report.md"), "w", encoding="utf-8")
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("tw_stock_tool.cli.daily_report_cli.render_daily_report_markdown")
    @patch("tw_stock_tool.cli.daily_report_cli.build_daily_report_data")
    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_report")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids")
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_e2e_mvp_execution_output_md_empty(self, mock_open, mock_mkdir, mock_collect, mock_run_daily, mock_build, mock_render):
        mock_collect.return_value = ["2330"]
        mock_run_daily.return_value = (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None)

        test_args = ["--stocks", "2330", "--output-md"]
        with patch.object(sys, "argv", ["daily_report_cli.py"] + test_args):
            main()

        mock_open.assert_called_once_with(Path("output/daily_report.md"), "w", encoding="utf-8")

    @patch("tw_stock_tool.cli.daily_report_cli.render_daily_report_markdown")
    @patch("tw_stock_tool.cli.daily_report_cli.build_daily_report_data")
    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_report")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids")
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_e2e_mvp_execution_output_dir(self, mock_open, mock_mkdir, mock_collect, mock_run_daily, mock_build, mock_render):
        mock_collect.return_value = ["2330"]
        mock_run_daily.return_value = (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None)

        test_args = ["--stocks", "2330", "--output-dir", "reports"]
        with patch.object(sys, "argv", ["daily_report_cli.py"] + test_args):
            main()

        mock_open.assert_called_once_with(Path("reports/daily_report.md"), "w", encoding="utf-8")

    @patch("tw_stock_tool.cli.daily_report_cli.render_daily_report_markdown")
    @patch("tw_stock_tool.cli.daily_report_cli.build_daily_report_data")
    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_report")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids")
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_e2e_mvp_execution_output_md_custom(self, mock_open, mock_mkdir, mock_collect, mock_run_daily, mock_build, mock_render):
        mock_collect.return_value = ["2330"]
        mock_run_daily.return_value = (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None)

        test_args = ["--stocks", "2330", "--output-md", "custom/report.md"]
        with patch.object(sys, "argv", ["daily_report_cli.py"] + test_args):
            main()

        mock_open.assert_called_once_with(Path("custom/report.md"), "w", encoding="utf-8")

    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids")
    def test_no_stocks_exits(self, mock_collect):
        mock_collect.return_value = []
        with patch.object(sys, "argv", ["daily_report_cli.py", "--stocks"]):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertEqual(cm.exception.code, 1)

if __name__ == "__main__":
    unittest.main()
