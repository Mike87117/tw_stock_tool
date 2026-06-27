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
        self.assertFalse(args.run_backtest)
        self.assertFalse(args.run_sweep)
        self.assertFalse(args.run_walk_forward)
        self.assertEqual(args.deep_dive_strategy, "ma_cross")
        self.assertEqual(args.output_dir, "output")

    def test_parse_args_custom(self):
        args = _parse_args([
            "--stocks", "2330", "2317",
            "--run-backtest",
            "--run-sweep",
            "--deep-dive-strategy", "rsi",
            "--output-md", "test.md"
        ])
        self.assertEqual(args.stocks, ["2330", "2317"])
        self.assertTrue(args.run_backtest)
        self.assertTrue(args.run_sweep)
        self.assertFalse(args.run_walk_forward)
        self.assertEqual(args.deep_dive_strategy, "rsi")
        self.assertEqual(args.output_md, "test.md")

    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_report")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids")
    @patch("tw_stock_tool.cli.daily_report_cli.run_backtest")
    @patch("tw_stock_tool.cli.daily_report_cli.analyze_stock")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_e2e_with_backtest_deep_dive(self, mock_open, mock_analyze, mock_bt, mock_collect, mock_run_daily):
        mock_collect.return_value = ["2330"]
        
        # Mock scanner output
        summary_df = pd.DataFrame([{"Stocks Scanned": 1}])
        candidates_df = pd.DataFrame([{"Stock": "2330", "Score": 5}])
        mock_run_daily.return_value = (summary_df, candidates_df, pd.DataFrame(), None)
        
        # Mock backtest output
        mock_bt.return_value = {"Summary": {"Total Return": 5.0, "Win Rate": 0.5}}
        
        # Mock analyze stock
        mock_analysis = MagicMock()
        mock_analysis.indicator_df = pd.DataFrame({"Close": [100, 102], "Volume": [1000, 1000]})
        mock_analyze.return_value = mock_analysis

        test_args = ["--stocks", "2330", "--run-backtest", "--output-md", "test_out.md"]
        with patch.object(sys, "argv", ["daily_report_cli.py"] + test_args):
            with patch.dict("tw_stock_tool.cli.daily_report_cli.STRATEGIES", {"ma_cross_strategy": MagicMock(return_value=pd.DataFrame())}):
                main()

        # Ensure backtest was called since the candidate dataframe was not empty
        mock_bt.assert_called_once()
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
