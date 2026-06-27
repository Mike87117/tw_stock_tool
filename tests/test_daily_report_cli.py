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
        self.assertEqual(args.output_md, "output/daily_report.md")

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
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_e2e_mvp_execution(self, mock_open, mock_collect, mock_run_daily, mock_build, mock_render):
        mock_collect.return_value = ["2330"]
        
        # Mock scanner output
        summary_df = pd.DataFrame([{"Stocks Scanned": 1}])
        candidates_df = pd.DataFrame([{"Stock": "2330", "Score": 5}])
        mock_run_daily.return_value = (summary_df, candidates_df, pd.DataFrame(), None)
        
        mock_build.return_value = {"dummy": "data"}
        mock_render.return_value = "# Markdown Report"

        test_args = ["--stocks", "2330", "--output-md", "test_out.md"]
        with patch.object(sys, "argv", ["daily_report_cli.py"] + test_args):
            main()

        mock_run_daily.assert_called_once_with(
            stock_ids=["2330"],
            period='1y',
            interval='1d',
            signals=['BUY', 'WATCH'],
            min_score=4.0,
            top=20,
            force_refresh=False,
            auto_adjust=False,
            output=None,
            progress=True
        )
        mock_build.assert_called_once()
        mock_render.assert_called_once_with({"dummy": "data"})
        mock_open.assert_called_once_with("test_out.md", "w", encoding="utf-8")

    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids")
    def test_no_stocks_exits(self, mock_collect):
        mock_collect.return_value = []
        with patch.object(sys, "argv", ["daily_report_cli.py", "--stocks"]):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertEqual(cm.exception.code, 1)

if __name__ == "__main__":
    unittest.main()
