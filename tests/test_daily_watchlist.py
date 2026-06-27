import unittest
from unittest.mock import patch
import pandas as pd
import tempfile
from pathlib import Path

from tw_stock_tool.scanners.daily_watchlist import (
    build_daily_watchlist,
    export_daily_watchlist_excel,
    export_daily_watchlist_markdown,
)
from tw_stock_tool.analysis.analysis import StockAnalysis
from tw_stock_tool.cli.daily_watchlist import _collect_stock_ids, _parse_args

class TestDailyWatchlist(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _mock_analyze_stock(self, stock_id, **kwargs):
        if stock_id == "ERROR":
            raise ValueError("Test error")
            
        # mock technical breakout (score >= 3.0) for 2330
        if stock_id == "2330":
            df = pd.DataFrame({
                "Close": [100],
                "MA20": [90],
                "MA60": [80],
                "MACD": [1.5],
                "Volume": [1000]
            }, index=[pd.Timestamp("2024-01-01")])
            symbol = "TSMC"
        # mock risk warning (score >= 2.0) for 2317
        elif stock_id == "2317":
            df = pd.DataFrame({
                "Close": [100],
                "MA20": [110],
                "MA60": [120],
                "RSI14": [85],
                "Volume": [1000]
            }, index=[pd.Timestamp("2024-01-01")])
            symbol = "Hon Hai"
        else:
            # no signal
            df = pd.DataFrame({
                "Close": [100],
            }, index=[pd.Timestamp("2024-01-01")])
            symbol = "Unknown"
            
        return StockAnalysis(
            stock_id=stock_id,
            symbol=symbol,
            raw_df=df,
            indicator_df=df,
            signal_df=df,
            latest=df.iloc[-1],
            summary={}
        )

    def test_parse_args_supports_optional_output_paths(self):
        args = _parse_args(["--stock", "2330", "--output-excel", "custom.xlsx", "--output-md"])
        self.assertEqual(args.stocks, ["2330"])
        self.assertEqual(args.output_excel, "custom.xlsx")
        self.assertEqual(args.output_md, "")

    def test_collect_stock_ids_supports_comma_separated_stocks(self):
        args = _parse_args(["--stocks", "2330,2317", "2454"])
        stock_ids = _collect_stock_ids(args)
        self.assertEqual(stock_ids, ["2330", "2317", "2454"])

    @patch("tw_stock_tool.scanners.daily_watchlist.analyze_stock")
    def test_build_daily_watchlist(self, mock_analyze):
        mock_analyze.side_effect = self._mock_analyze_stock
        
        stock_ids = ["2330", "2317", "9999", "ERROR"]
        df = build_daily_watchlist(stock_ids, breakout_min_score=3.0, risk_min_score=2.0)
        
        # 2330 (breakout), 2317 (risk), ERROR (error). 9999 is skipped because scores = 0
        self.assertEqual(len(df), 3)
        
        self.assertEqual(df.iloc[0]["Stock"], "2330")
        self.assertEqual(df.iloc[0]["Category"], "technical_breakout")
        
        self.assertEqual(df.iloc[1]["Stock"], "2317")
        self.assertEqual(df.iloc[1]["Category"], "risk_warning")
        
        self.assertEqual(df.iloc[2]["Stock"], "ERROR")
        self.assertEqual(df.iloc[2]["Status"], "error")

    @patch("tw_stock_tool.scanners.daily_watchlist.analyze_stock")
    def test_export_excel(self, mock_analyze):
        mock_analyze.side_effect = self._mock_analyze_stock
        df = build_daily_watchlist(["2330", "2317", "ERROR"])
        excel_path = export_daily_watchlist_excel(df, str(self.output_dir / "test.xlsx"))
        self.assertTrue(excel_path.exists())

    @patch("tw_stock_tool.scanners.daily_watchlist.analyze_stock")
    def test_export_markdown(self, mock_analyze):
        mock_analyze.side_effect = self._mock_analyze_stock
        df = build_daily_watchlist(["2330", "2317", "ERROR"])
        md_path = export_daily_watchlist_markdown(df, str(self.output_dir / "test.md"))
        self.assertTrue(md_path.exists())
        content = md_path.read_text(encoding="utf-8")
        self.assertIn("not investment advice", content)
        self.assertIn("## Technical Breakout", content)
        self.assertIn("2330", content)
        self.assertIn("2317", content)

    def test_export_excel_default_path(self):
        import os
        old_cwd = Path.cwd()
        try:
            os.chdir(self.temp_dir.name)
            df = build_daily_watchlist([])
            excel_path = export_daily_watchlist_excel(df)
            self.assertEqual(excel_path.parts[-2:], ("output", "daily_watchlist.xlsx"))
            self.assertTrue(excel_path.exists())
        finally:
            os.chdir(old_cwd)

    def test_export_markdown_default_path(self):
        import os
        old_cwd = Path.cwd()
        try:
            os.chdir(self.temp_dir.name)
            df = build_daily_watchlist([])
            md_path = export_daily_watchlist_markdown(df)
            self.assertEqual(md_path.parts[-2:], ("output", "daily_watchlist.md"))
            self.assertTrue(md_path.exists())
        finally:
            os.chdir(old_cwd)

    def test_empty_dataframe_export_markdown(self):
        df = build_daily_watchlist([])
        md_path = export_daily_watchlist_markdown(df, str(self.output_dir / "empty.md"))
        self.assertTrue(md_path.exists())
        content = md_path.read_text(encoding="utf-8")
        self.assertIn("Daily Watchlist", content)
        self.assertIn("Research candidates only, not investment advice.", content)
        self.assertIn("## Technical Breakout", content)
        self.assertIn("No technical breakout candidates.", content)
        self.assertIn("## Risk Warning", content)
        self.assertIn("No risk warning candidates.", content)
        self.assertIn("## Errors", content)
        self.assertIn("No errors.", content)

    def test_empty_dataframe_export_excel(self):
        df = build_daily_watchlist([])
        excel_path = export_daily_watchlist_excel(df, str(self.output_dir / "empty.xlsx"))
        self.assertTrue(excel_path.exists())
        # Check sheet names
        with pd.ExcelFile(excel_path) as xls:
            self.assertIn("All", xls.sheet_names)

    @patch("tw_stock_tool.cli.daily_watchlist.build_daily_watchlist")
    @patch("tw_stock_tool.cli.daily_watchlist._parse_args")
    @patch("tw_stock_tool.cli.daily_watchlist._collect_stock_ids")
    def test_cli_exception_raises_systemexit(self, mock_collect, mock_parse, mock_build):
        mock_build.side_effect = Exception("Test unhandled exception")
        from tw_stock_tool.cli.daily_watchlist import main
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 1)

    @patch("tw_stock_tool.cli.daily_watchlist.export_daily_watchlist_markdown")
    @patch("tw_stock_tool.cli.daily_watchlist.export_daily_watchlist_excel")
    @patch("tw_stock_tool.cli.daily_watchlist._parse_args")
    @patch("tw_stock_tool.cli.daily_watchlist._collect_stock_ids")
    def test_cli_empty_watchlist_exports(self, mock_collect, mock_parse, mock_excel, mock_md):
        mock_collect.return_value = []
        import argparse
        args = argparse.Namespace(
            output_excel="test.xlsx",
            output_md="test.md",
            output_dir=str(self.output_dir),
            period="1y",
            stock_limit=None,
            force_refresh=False,
            breakout_min_score=3.0,
            risk_min_score=2.0
        )
        mock_parse.return_value = args
        from tw_stock_tool.cli.daily_watchlist import main
        main()
        mock_excel.assert_called_once()
        mock_md.assert_called_once()

    @patch("tw_stock_tool.cli.daily_watchlist.stock_list_updater_module.update_stock_list")
    def test_auto_stock_list_defaults_to_ignored_path(self, mock_update):
        mock_update.return_value = (pd.DataFrame({"Stock": ["2330"]}), "mock_path")
        args = _parse_args(["--auto-stock-list"])
        self.assertEqual(args.auto_stock_list_output, "output/auto_stock_list.txt")
        _collect_stock_ids(args)
        mock_update.assert_called_once_with(
            market="all",
            output="output/auto_stock_list.txt",
            allow_partial=False
        )

    @patch("tw_stock_tool.cli.daily_watchlist.stock_list_updater_module.update_stock_list")
    def test_auto_stock_list_supports_custom_output_path(self, mock_update):
        mock_update.return_value = (pd.DataFrame({"Stock": ["2330"]}), "mock_path")
        args = _parse_args(["--auto-stock-list", "--auto-stock-list-output", "custom_path.txt"])
        self.assertEqual(args.auto_stock_list_output, "custom_path.txt")
        _collect_stock_ids(args)
        mock_update.assert_called_once_with(
            market="all",
            output="custom_path.txt",
            allow_partial=False
        )

if __name__ == "__main__":
    unittest.main()
