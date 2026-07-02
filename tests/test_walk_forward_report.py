import unittest
import pandas as pd
from pathlib import Path
import tempfile
import sys
import unittest.mock as mock

from src.tw_stock_tool.reports.walk_forward_report import (
    build_walk_forward_report_data,
    export_walk_forward_report_markdown,
    export_walk_forward_report_excel,
)

class WalkForwardReportTest(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame([
            {
                "Window": 1,
                "Train Start": "2022-01-01",
                "Train End": "2022-12-31",
                "Test Start": "2023-01-01",
                "Test End": "2023-03-31",
                "Parameters": "short=5,long=20",
                "Train Sharpe Ratio": 1.4,
                "Test Sharpe Ratio": 0.9,
                "Train Total Return %": 12.0,
                "Test Total Return %": 4.0,
                "Test Max Drawdown %": -3.5,
                "Train Profit Factor": 1.5,
                "Test Profit Factor": 1.1,
                "Train Sortino Ratio": 2.0,
                "Test Sortino Ratio": 1.2,
            },
            {
                "Window": 2,
                "Train Start": "2022-04-01",
                "Train End": "2023-03-31",
                "Test Start": "2023-04-01",
                "Test End": "2023-06-30",
                "Parameters": "short=10,long=30",
                "Train Sharpe Ratio": 1.1,
                "Test Sharpe Ratio": 1.5,
                "Train Total Return %": 10.0,
                "Test Total Return %": 8.0,
                "Test Max Drawdown %": -2.0,
                "Train Profit Factor": 1.8,
                "Test Profit Factor": 1.6,
                "Train Sortino Ratio": 1.8,
                "Test Sortino Ratio": 1.9,
            }
        ])

        self.dict_input = {
            "Stock": "2330",
            "Strategy": "ma_cross",
            "Results": self.df,
        }

    def test_build_data_with_dataframe(self):
        data = build_walk_forward_report_data(self.df)
        self.assertEqual(data["Stock"], "N/A")
        self.assertEqual(len(data["Results"]), 2)
        
        self.assertIn("Window", data["Window Columns"])
        self.assertIn("Train Start", data["Window Columns"])
        self.assertIn("Test Sharpe Ratio", data["Metric Columns"])
        self.assertIn("Test Total Return %", data["Metric Columns"])
        self.assertIn("Train Profit Factor", data["Metric Columns"])
        self.assertIn("Test Profit Factor", data["Metric Columns"])
        self.assertIn("Train Sortino Ratio", data["Metric Columns"])
        self.assertIn("Test Sortino Ratio", data["Metric Columns"])
        
        # Test Sharpe Ratio sort: 1.5 > 0.9 -> Window 2 is Best
        self.assertIsNotNone(data["Best Window"])
        self.assertEqual(data["Best Window"]["Window"], 2)
        
        # Summary metrics
        self.assertEqual(data["Summary"]["Rows"], 2)
        self.assertEqual(data["Summary"]["Best Test Sharpe Ratio"], 1.5)
        self.assertEqual(data["Summary"]["Best Test Total Return %"], 8.0)
        self.assertEqual(data["Summary"]["Worst Test Max Drawdown %"], -3.5)

    def test_build_data_with_dict(self):
        data = build_walk_forward_report_data(self.dict_input)
        self.assertEqual(data["Stock"], "2330")
        self.assertEqual(data["Strategy"], "ma_cross")
        self.assertEqual(len(data["Results"]), 2)

    def test_build_data_empty_inputs(self):
        # Empty DataFrame
        data1 = build_walk_forward_report_data(pd.DataFrame())
        self.assertEqual(len(data1["Results"]), 0)
        self.assertIsNone(data1["Best Window"])
        
        # Empty dict
        data2 = build_walk_forward_report_data({})
        self.assertEqual(len(data2["Results"]), 0)
        self.assertIsNone(data2["Best Window"])
        
        # Dict without results
        data3 = build_walk_forward_report_data({"Stock": "2330"})
        self.assertEqual(len(data3["Results"]), 0)
        
        # None
        data4 = build_walk_forward_report_data(None)
        self.assertEqual(len(data4["Results"]), 0)

    def test_build_data_missing_metrics(self):
        df_no_metrics = pd.DataFrame([
            {"Window": 1, "Train Start": "2022-01-01"},
            {"Window": 2, "Train Start": "2022-04-01"}
        ])
        data = build_walk_forward_report_data(df_no_metrics)
        self.assertEqual(len(data["Results"]), 2)
        self.assertEqual(data["Best Window"]["Window"], 1) # Retains original order

    def test_build_data_sorting_fallback(self):
        df = pd.DataFrame([
            {"Window": 1, "Test Total Return %": 5.0, "Total Return %": 15.0},
            {"Window": 2, "Test Total Return %": 10.0, "Total Return %": 5.0},
        ])
        data = build_walk_forward_report_data(df)
        self.assertEqual(data["Best Window"]["Window"], 2) # Sorted by Test Total Return %

        df_no_test = pd.DataFrame([
            {"Window": 1, "Sharpe Ratio": 1.0, "Total Return %": 15.0},
            {"Window": 2, "Sharpe Ratio": 2.0, "Total Return %": 5.0},
        ])
        data2 = build_walk_forward_report_data(df_no_test)
        self.assertEqual(data2["Best Window"]["Window"], 2) # Sorted by Sharpe Ratio
        
        df_return_only = pd.DataFrame([
            {"Window": 1, "Total Return %": 15.0},
            {"Window": 2, "Total Return %": 5.0},
        ])
        data3 = build_walk_forward_report_data(df_return_only)
        self.assertEqual(data3["Best Window"]["Window"], 1) # Sorted by Total Return %

    def test_export_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "wf.md"
            res = export_walk_forward_report_markdown(self.df, output=str(out_path))
            self.assertEqual(res, out_path)
            
            content = out_path.read_text(encoding="utf-8")
            self.assertIn("# Walk Forward Report", content)
            self.assertIn("Research report only, not investment advice.", content)
            self.assertIn("## Summary", content)
            self.assertIn("## Top Walk-Forward Window", content)
            self.assertIn("## Results", content)
            self.assertIn("## Notes", content)
            self.assertIn("Test Sharpe Ratio", content)

    def test_export_markdown_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "wf_empty.md"
            export_walk_forward_report_markdown(None, output=str(out_path))
            content = out_path.read_text(encoding="utf-8")
            self.assertIn("No walk forward results.", content)
            self.assertIn("No top walk-forward window found.", content)

    def test_export_excel(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "wf.xlsx"
            res = export_walk_forward_report_excel(self.df, output=str(out_path))
            self.assertEqual(res, out_path)
            
            with pd.ExcelFile(out_path) as xls:
                self.assertIn("Summary", xls.sheet_names)
                self.assertIn("Top Walk-Forward Window", xls.sheet_names)
                self.assertIn("Results", xls.sheet_names)
                self.assertIn("Notes", xls.sheet_names)
                
                res_df = pd.read_excel(xls, sheet_name="Results")
                self.assertEqual(len(res_df), 2)
                
                best_df = pd.read_excel(xls, sheet_name="Top Walk-Forward Window")
                self.assertEqual(len(best_df), 1)

    def test_export_excel_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "wf_empty.xlsx"
            export_walk_forward_report_excel(None, output=str(out_path))
            
            with pd.ExcelFile(out_path) as xls:
                res_df = pd.read_excel(xls, sheet_name="Results")
                self.assertEqual(len(res_df), 0)
                best_df = pd.read_excel(xls, sheet_name="Top Walk-Forward Window")
                self.assertEqual(len(best_df), 0)

    def test_default_output_paths(self):
        with mock.patch("src.tw_stock_tool.reports.walk_forward_report.Path") as mock_path, \
             mock.patch("pandas.ExcelWriter"), \
             mock.patch("pandas.DataFrame.to_excel"):
            
            mock_path_instance = mock.MagicMock()
            mock_path.return_value = mock_path_instance
            
            export_walk_forward_report_markdown(None)
            mock_path.assert_any_call("output/walk_forward_report.md")
            
            export_walk_forward_report_excel(None)
            mock_path.assert_any_call("output/walk_forward_report.xlsx")

    @mock.patch("tw_stock_tool.reports.walk_forward_report.pd.ExcelWriter")
    def test_export_excel_permission_error(self, mock_writer):
        mock_writer.side_effect = PermissionError("locked")
        with tempfile.TemporaryDirectory() as d:
            out_path = Path(d) / "test.xlsx"
            with self.assertRaisesRegex(ValueError, "Failed to write Excel file.*Please close the file if it is open"):
                export_walk_forward_report_excel(self.df, out_path)

    def test_no_banned_wording_in_markdown_and_excel(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test Markdown
            md_path = Path(tmpdir) / "wf.md"
            export_walk_forward_report_markdown(self.df, output=str(md_path))
            content = md_path.read_text(encoding="utf-8").lower()

            banned_phrases = [
                "best strategy",
                "best parameters",
                "best test total return",
                "best test sharpe ratio",
                "## best window",
                "no best window found",
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

            # Test Excel Sheet Names
            xl_path = Path(tmpdir) / "wf.xlsx"
            export_walk_forward_report_excel(self.df, output=str(xl_path))
            with pd.ExcelFile(xl_path) as xls:
                sheet_names_lower = [s.lower() for s in xls.sheet_names]
                for phrase in banned_phrases:
                    for s in sheet_names_lower:
                        self.assertNotIn(phrase.lower(), s)


if __name__ == '__main__':
    unittest.main()
