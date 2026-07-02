"""Tests for backtest report exporter."""

import os
import unittest
from unittest.mock import patch
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

    def test_markdown_trades_table_supports_pnl_pct(self):
        result = {
            "Stock": "2330",
            "Strategy": "test",
            "Trades": pd.DataFrame({
                "Entry Date": ["2024-01-01"],
                "Exit Date": ["2024-01-05"],
                "Entry Price": [100],
                "Exit Price": [105],
                "Shares": [1000],
                "PnL": [5000],
                "PnL_pct": [5.0],
                "Hold Days": [4],
            }),
        }
        with tempfile.TemporaryDirectory() as d:
            out_md = Path(d) / "test.md"
            export_backtest_report_markdown(result, str(out_md))
            content = out_md.read_text(encoding="utf-8")
            self.assertIn("PnL_pct", content)
            self.assertIn("5.0", content)

    def test_markdown_trades_table_supports_legacy_pnl_pct_string(self):
        result = {
            "Stock": "2330",
            "Strategy": "test",
            "Trades": pd.DataFrame({
                "Entry Date": ["2024-01-01"],
                "PnL %": [5.0],
            }),
        }
        with tempfile.TemporaryDirectory() as d:
            out_md = Path(d) / "test.md"
            export_backtest_report_markdown(result, str(out_md))
            content = out_md.read_text(encoding="utf-8")
            self.assertIn("PnL %", content)
            self.assertIn("5.0", content)

    def test_excel_trades_sheet_keeps_pnl_pct(self):
        result = {
            "Stock": "2330",
            "Strategy": "test",
            "Trades": pd.DataFrame({
                "Entry Date": ["2024-01-01"],
                "PnL_pct": [5.0],
            }),
        }
        with tempfile.TemporaryDirectory() as d:
            out_xlsx = Path(d) / "test.xlsx"
            export_backtest_report_excel(result, str(out_xlsx))
            df = pd.read_excel(out_xlsx, sheet_name="Trades")
            self.assertIn("PnL_pct", df.columns)

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

    @patch("tw_stock_tool.reports.backtest_report.pd.ExcelWriter")
    def test_export_excel_permission_error(self, mock_writer):
        mock_writer.side_effect = PermissionError("locked")
        with tempfile.TemporaryDirectory() as d:
            out_path = Path(d) / "test.xlsx"
            with self.assertRaisesRegex(ValueError, "Failed to write Excel file.*Please close the file if it is open"):
                export_backtest_report_excel(self.mock_result, out_path)

    def test_no_banned_wording_in_markdown_and_excel(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test Markdown
            md_path = Path(tmpdir) / "bt.md"
            export_backtest_report_markdown(self.mock_result, output=str(md_path))
            content = md_path.read_text(encoding="utf-8").lower()

            # Positive assertions
            self.assertIn("## summary", content)
            self.assertIn("## metrics", content)
            self.assertIn("## trade summary", content)
            self.assertIn("## trades", content)
            self.assertIn("## notes", content)
            self.assertIn("research report only, not investment advice", content)
            self.assertIn("past performance does not guarantee future results", content)
            self.assertIn("max profit trade", content)
            self.assertIn("max loss trade", content)

            banned_phrases = [
                "best strategy",
                "best parameters",
                "best result",
                "best trade",
                "worst trade",
                "recommended stocks",
                "buy recommendation",
                "sell recommendation",
                "investment recommendation",
                "investment opportunity",
                "best stocks to buy",
                "should buy",
                "safe to invest",
                "guaranteed profit",
                "guaranteed return",
                "guaranteed latest data"
            ]
            for phrase in banned_phrases:
                self.assertNotIn(phrase.lower(), content)

            # Test Excel
            xl_path = Path(tmpdir) / "bt.xlsx"
            export_backtest_report_excel(self.mock_result, output=str(xl_path))
            with pd.ExcelFile(xl_path) as xls:
                sheet_names_lower = [s.lower() for s in xls.sheet_names]
                for phrase in banned_phrases:
                    for s in sheet_names_lower:
                        self.assertNotIn(phrase.lower(), s)
                
                # Positive sheet names
                self.assertIn("summary", sheet_names_lower)
                self.assertIn("metrics", sheet_names_lower)
                self.assertIn("trade summary", sheet_names_lower)
                self.assertIn("trades", sheet_names_lower)

                # Check visible labels in metrics / trade summary
                metrics_df = pd.read_excel(xls, sheet_name="Metrics")
                metrics_str = metrics_df.astype(str).values.flatten().tolist()
                metrics_str_lower = " ".join(metrics_str).lower()
                self.assertIn("max profit trade", metrics_str_lower)
                self.assertIn("max loss trade", metrics_str_lower)

                for phrase in banned_phrases:
                    self.assertNotIn(phrase.lower(), metrics_str_lower)

