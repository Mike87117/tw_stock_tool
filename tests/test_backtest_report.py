"""Tests for backtest report exporter."""

import os
import unittest
import pandas as pd
import tempfile
from pathlib import Path

from tw_stock_tool.reports.backtest_report import (
    build_backtest_report_data,
    export_backtest_report_markdown,
    export_backtest_report_excel,
)


class TestBacktestReport(unittest.TestCase):
    def setUp(self):
        self.mock_result = {
            "Stock": "2330",
            "Strategy": "ma_cross",
            "Initial Capital": 100000,
            "Final Capital": 110000,
            "Total Return %": 10.0,
            "Buy and Hold Return %": 5.0,
            "Trades": pd.DataFrame({
                "Entry Date": ["2023-01-01", "2023-02-01"],
                "Exit Date": ["2023-01-15", "2023-02-15"],
                "Entry Price": [100.0, 110.0],
                "Exit Price": [110.0, 105.0],
                "PnL": [10.0, -5.0],
                "Hold Days": [14, 14]
            }),
            "Equity Curve": pd.Series([100000, 105000, 110000], index=["2023-01-01", "2023-01-15", "2023-02-15"])
        }
        self.empty_result = {}

    def test_build_report_data_with_valid_data(self):
        data = build_backtest_report_data(self.mock_result)
        self.assertEqual(data["Summary"]["Stock"], "2330")
        self.assertEqual(data["Summary"]["Total Return %"], 10.0)
        self.assertEqual(data["Trade Summary"]["Total Trades"], 2)
        self.assertEqual(data["Trade Summary"]["Winning Trades"], 1)
        self.assertEqual(data["Trade Summary"]["Losing Trades"], 1)
        self.assertFalse(data["Drawdown"].empty)

    def test_build_report_data_with_empty_data(self):
        data = build_backtest_report_data(self.empty_result)
        self.assertEqual(data["Summary"]["Stock"], "N/A")
        self.assertTrue(data["Trades"].empty)
        self.assertEqual(data["Trade Summary"], {})
        self.assertTrue(data["Drawdown"].empty)

    def test_export_markdown_creates_file_and_content(self):
        with tempfile.TemporaryDirectory() as d:
            out_path = Path(d) / "test.md"
            res_path = export_backtest_report_markdown(self.mock_result, str(out_path))
            
            self.assertTrue(res_path.exists())
            content = res_path.read_text(encoding="utf-8")
            self.assertIn("# Backtest Report", content)
            self.assertIn("Research report only, not investment advice.", content)
            self.assertNotIn("建議買進", content)
            self.assertIn("2330", content)
            self.assertIn("ma_cross", content)

    def test_export_excel_creates_file_and_sheets(self):
        with tempfile.TemporaryDirectory() as d:
            out_path = Path(d) / "test.xlsx"
            res_path = export_backtest_report_excel(self.mock_result, str(out_path))
            
            self.assertTrue(res_path.exists())
            # Check sheets using pandas
            with pd.ExcelFile(res_path) as xls:
                self.assertIn("Summary", xls.sheet_names)
                self.assertIn("Metrics", xls.sheet_names)
                self.assertIn("Trades", xls.sheet_names)
                self.assertIn("Equity Curve", xls.sheet_names)
                self.assertIn("Drawdown", xls.sheet_names)

    def test_export_markdown_default_path(self):
        with tempfile.TemporaryDirectory() as d:
            old_cwd = Path.cwd()
            try:
                os.chdir(d)
                res_path = export_backtest_report_markdown(self.mock_result)
                self.assertEqual(res_path.parts[-2:], ("output", "backtest_report.md"))
                self.assertTrue(res_path.exists())
            finally:
                os.chdir(old_cwd)

    def test_export_excel_default_path(self):
        with tempfile.TemporaryDirectory() as d:
            old_cwd = Path.cwd()
            try:
                os.chdir(d)
                res_path = export_backtest_report_excel(self.mock_result)
                self.assertEqual(res_path.parts[-2:], ("output", "backtest_report.xlsx"))
                self.assertTrue(res_path.exists())
            finally:
                os.chdir(old_cwd)

    def test_export_with_empty_result_does_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            out_md = Path(d) / "empty.md"
            out_xlsx = Path(d) / "empty.xlsx"
            export_backtest_report_markdown(self.empty_result, str(out_md))
            export_backtest_report_excel(self.empty_result, str(out_xlsx))
            self.assertTrue(out_md.exists())
            self.assertTrue(out_xlsx.exists())

    def test_missing_pnl_in_trades_does_not_crash(self):
        result = {
            "Stock": "2330",
            "Strategy": "test",
            "Trades": [
                {
                    "Entry Date": "2024-01-01",
                    "Exit Date": "2024-01-05",
                    "Entry Price": 100,
                    "Exit Price": 105,
                    "Hold Days": 4
                }
            ]
        }
        data = build_backtest_report_data(result)
        self.assertEqual(data["Trade Summary"]["Total Trades"], 1)
        self.assertEqual(data["Trade Summary"]["Winning Trades"], 0)
        self.assertEqual(data["Trade Summary"]["Average Profit"], "N/A")
        
        with tempfile.TemporaryDirectory() as d:
            export_backtest_report_markdown(result, str(Path(d) / "test.md"))
            export_backtest_report_excel(result, str(Path(d) / "test.xlsx"))

    def test_missing_hold_days_in_trades_does_not_crash(self):
        result = {
            "Stock": "2330",
            "Trades": [
                {
                    "Entry Date": "2024-01-01",
                    "PnL": 5.0
                }
            ]
        }
        data = build_backtest_report_data(result)
        self.assertEqual(data["Trade Summary"]["Total Trades"], 1)
        self.assertEqual(data["Trade Summary"]["Average Hold Days"], "N/A")
        
        with tempfile.TemporaryDirectory() as d:
            export_backtest_report_markdown(result, str(Path(d) / "test.md"))
            export_backtest_report_excel(result, str(Path(d) / "test.xlsx"))

    def test_very_incomplete_schema_does_not_crash(self):
        result = {
            "Trades": [
                {"Entry Date": "2024-01-01"}
            ]
        }
        data = build_backtest_report_data(result)
        self.assertEqual(data["Trade Summary"]["Total Trades"], 1)
        self.assertEqual(data["Trade Summary"]["Winning Trades"], 0)
        self.assertEqual(data["Trade Summary"]["Average Hold Days"], "N/A")
        
        with tempfile.TemporaryDirectory() as d:
            export_backtest_report_markdown(result, str(Path(d) / "test.md"))
            export_backtest_report_excel(result, str(Path(d) / "test.xlsx"))
