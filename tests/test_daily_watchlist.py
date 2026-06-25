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

if __name__ == "__main__":
    unittest.main()
