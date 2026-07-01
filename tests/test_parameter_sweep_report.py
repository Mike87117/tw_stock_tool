import unittest
import pandas as pd
from pathlib import Path
import tempfile
import os
from unittest.mock import patch
from src.tw_stock_tool.reports.parameter_sweep_report import (
    build_parameter_sweep_report_data,
    export_parameter_sweep_report_markdown,
    export_parameter_sweep_report_excel,
)

class ParameterSweepReportTest(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame([
            {"short_window": 5, "long_window": 20, "total_return": 0.12, "sharpe": 1.1},
            {"short_window": 10, "long_window": 30, "total_return": 0.08, "sharpe": 0.9},
            {"short_window": 20, "long_window": 60, "total_return": 0.15, "sharpe": 1.5},
        ])
        
        self.dict_input = {
            "Stock": "2330",
            "Strategy": "ma_cross",
            "Results": self.df,
            "Parameter Columns": ["short_window", "long_window"],
            "Metric Columns": ["total_return", "sharpe"],
        }
        
    def test_build_data_with_dataframe(self):
        data = build_parameter_sweep_report_data(self.df)
        self.assertEqual(data["Stock"], "N/A")
        self.assertEqual(data["Strategy"], "N/A")
        self.assertEqual(len(data["Results"]), 3)
        self.assertIn("short_window", data["Parameter Columns"])
        self.assertIn("sharpe", data["Metric Columns"])
        
        # Best row sorting should be based on sharpe descending
        self.assertEqual(data["Best Row"]["short_window"], 20)
        self.assertEqual(data["Best Row"]["sharpe"], 1.5)
        
    def test_build_data_with_dict(self):
        data = build_parameter_sweep_report_data(self.dict_input)
        self.assertEqual(data["Stock"], "2330")
        self.assertEqual(data["Strategy"], "ma_cross")
        self.assertEqual(len(data["Results"]), 3)
        self.assertEqual(data["Parameter Columns"], ["short_window", "long_window"])
        
    def test_build_data_empty_inputs(self):
        # Empty DataFrame
        data = build_parameter_sweep_report_data(pd.DataFrame())
        self.assertEqual(len(data["Results"]), 0)
        self.assertIsNone(data["Best Row"])
        
        # Empty dict
        data2 = build_parameter_sweep_report_data({})
        self.assertEqual(len(data2["Results"]), 0)
        
        # Dict with empty results
        data3 = build_parameter_sweep_report_data({"Stock": "2330", "Results": []})
        self.assertEqual(len(data3["Results"]), 0)
        
        # None input
        data4 = build_parameter_sweep_report_data(None)
        self.assertEqual(len(data4["Results"]), 0)
        
    def test_build_data_missing_metrics(self):
        # Only parameter columns
        df_no_metrics = pd.DataFrame([
            {"short_window": 5, "long_window": 20},
            {"short_window": 10, "long_window": 30},
        ])
        data = build_parameter_sweep_report_data(df_no_metrics)
        self.assertEqual(len(data["Results"]), 2)
        # Should not crash, Best Row should just be first row since no sort_col
        self.assertEqual(data["Best Row"]["short_window"], 5)
        
    def test_build_data_sort_by_total_return(self):
        df = pd.DataFrame([
            {"short_window": 5, "total_return": 0.12},
            {"short_window": 10, "total_return": 0.20},
            {"short_window": 20, "total_return": 0.15},
        ])
        data = build_parameter_sweep_report_data(df)
        self.assertEqual(data["Best Row"]["short_window"], 10)
        self.assertEqual(data["Best Row"]["total_return"], 0.20)
        
    def test_real_schema_sharpe_ratio_sorting(self):
        df = pd.DataFrame([
            {"Strategy": "a", "Total Return %": 1.0, "Sharpe Ratio": 0.1},
            {"Strategy": "b", "Total Return %": 0.5, "Sharpe Ratio": 2.0},
        ])
        data = build_parameter_sweep_report_data(df)
        self.assertEqual(data["Best Row"]["Strategy"], "b")
        self.assertIn("Sharpe Ratio", data["Metric Columns"])
        self.assertIn("Total Return %", data["Metric Columns"])
        
    def test_real_schema_total_return_fallback(self):
        df = pd.DataFrame([
            {"Strategy": "a", "Total Return %": 1.0},
            {"Strategy": "b", "Total Return %": 5.0},
        ])
        data = build_parameter_sweep_report_data(df)
        self.assertEqual(data["Best Row"]["Strategy"], "b")
        
    def test_metric_columns_detection_with_sweep_columns(self):
        from src.tw_stock_tool.backtesting.parameter_sweep import SWEEP_COLUMNS
        df = pd.DataFrame([{col: 0 for col in SWEEP_COLUMNS}])
        data = build_parameter_sweep_report_data(df)
        self.assertIn("Sharpe Ratio", data["Metric Columns"])
        self.assertIn("Total Return %", data["Metric Columns"])
        self.assertIn("Max Drawdown %", data["Metric Columns"])
        
    def test_export_markdown_df(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "test_report.md"
            res = export_parameter_sweep_report_markdown(self.df, output=str(out_path))
            self.assertTrue(out_path.exists())
            self.assertEqual(res, out_path)
            
            content = out_path.read_text(encoding="utf-8")
            self.assertIn("# Parameter Sweep Report", content)
            self.assertIn("Research report only, not investment advice.", content)
            self.assertIn("short_window", content)
            self.assertIn("long_window", content)
            self.assertIn("sharpe", content)
            
    def test_export_markdown_dict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "test_report.md"
            export_parameter_sweep_report_markdown(self.dict_input, output=str(out_path))
            
            content = out_path.read_text(encoding="utf-8")
            self.assertIn("- Stock: 2330", content)
            self.assertIn("- Strategy: ma_cross", content)
            
    def test_export_markdown_real_schema(self):
        df = pd.DataFrame([
            {"Strategy": "a", "Total Return %": 1.0, "Sharpe Ratio": 0.1},
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "test_report.md"
            export_parameter_sweep_report_markdown(df, output=str(out_path))
            content = out_path.read_text(encoding="utf-8")
            self.assertIn("Sharpe Ratio", content)
            self.assertIn("Total Return %", content)
            
    def test_export_excel(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "test_report.xlsx"
            res = export_parameter_sweep_report_excel(self.df, output=str(out_path))
            self.assertTrue(out_path.exists())
            self.assertEqual(res, out_path)
            
            # Read back to verify sheets
            with pd.ExcelFile(out_path) as xls:
                self.assertIn("Summary", xls.sheet_names)
                self.assertIn("Top Results", xls.sheet_names)
                self.assertIn("Full Results", xls.sheet_names)
                self.assertIn("Notes", xls.sheet_names)
                
    def test_export_excel_real_schema(self):
        df = pd.DataFrame([
            {"Strategy": "a", "Total Return %": 1.0, "Sharpe Ratio": 0.1},
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "test_report.xlsx"
            export_parameter_sweep_report_excel(df, output=str(out_path))
            with pd.ExcelFile(out_path) as xls:
                full_results_df = pd.read_excel(xls, sheet_name="Full Results")
                self.assertIn("Sharpe Ratio", full_results_df.columns)
                self.assertIn("Total Return %", full_results_df.columns)
            
    def test_export_empty_result_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_md = Path(tmpdir) / "test_report.md"
            out_xl = Path(tmpdir) / "test_report.xlsx"
            
            export_parameter_sweep_report_markdown(pd.DataFrame(), output=str(out_md))
            self.assertTrue(out_md.exists())
            self.assertIn("No parameter sweep results.", out_md.read_text(encoding="utf-8"))
            
            export_parameter_sweep_report_excel(pd.DataFrame(), output=str(out_xl))
            self.assertTrue(out_xl.exists())
            
    def test_default_output_paths(self):
        import unittest.mock as mock
        
        with mock.patch("src.tw_stock_tool.reports.parameter_sweep_report.Path") as mock_path, \
             mock.patch("pandas.ExcelWriter"), \
             mock.patch("pandas.DataFrame.to_excel"):
            
            mock_path_instance = mock.MagicMock()
            mock_path.return_value = mock_path_instance
            
            export_parameter_sweep_report_markdown(pd.DataFrame())
            mock_path.assert_any_call("output/parameter_sweep_report.md")
            
            export_parameter_sweep_report_excel(pd.DataFrame())
            mock_path.assert_any_call("output/parameter_sweep_report.xlsx")

    @patch("tw_stock_tool.reports.parameter_sweep_report.pd.ExcelWriter")
    def test_export_excel_permission_error(self, mock_writer):
        mock_writer.side_effect = PermissionError("locked")
        with tempfile.TemporaryDirectory() as d:
            out_path = Path(d) / "test.xlsx"
            with self.assertRaisesRegex(ValueError, "Failed to write Excel file.*Please close the file if it is open"):
                export_parameter_sweep_report_excel(self.df, out_path)


if __name__ == '__main__':
    unittest.main()
