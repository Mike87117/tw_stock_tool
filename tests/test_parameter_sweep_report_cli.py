import unittest
import unittest.mock as mock
from pathlib import Path
import pandas as pd
import sys

from src.tw_stock_tool.cli.parameter_sweep_report import main, _parse_args


class ParameterSweepReportCLITest(unittest.TestCase):

    def setUp(self):
        # Sample sweep result
        self.mock_sweep_df = pd.DataFrame([
            {"Strategy": "ma_cross", "Parameters": "short=5", "Total Return %": 10.0, "Sharpe Ratio": 1.5},
            {"Strategy": "ma_cross", "Parameters": "short=10", "Total Return %": 8.0, "Sharpe Ratio": 1.2},
        ])

    @mock.patch("sys.argv", ["parameter_sweep_report.py", "--stock", "2330", "--strategy", "ma_cross"])
    def test_argument_parsing_minimal(self):
        args = _parse_args()
        self.assertEqual(args.stock, "2330")
        self.assertEqual(args.strategy, "ma_cross")
        self.assertEqual(args.output_md, None)
        self.assertEqual(args.output_excel, None)

    @mock.patch("sys.argv", ["parameter_sweep_report.py", "--stock", "2330", "--strategy", "ma_cross", "--output-md", "--output-excel"])
    def test_argument_parsing_default_outputs(self):
        args = _parse_args()
        self.assertEqual(args.output_md, "")
        self.assertEqual(args.output_excel, "")

    @mock.patch("sys.argv", ["parameter_sweep_report.py", "--stock", "2330", "--strategy", "ma_cross", "--output-md", "custom.md"])
    def test_argument_parsing_custom_outputs(self):
        args = _parse_args()
        self.assertEqual(args.output_md, "custom.md")

    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.run_parameter_sweep")
    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.export_parameter_sweep_report_markdown")
    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.export_parameter_sweep_report_excel")
    @mock.patch("sys.argv", ["parameter_sweep_report.py", "--stock", "2330", "--strategy", "ma_cross", "--output-md"])
    def test_markdown_default_output(self, mock_export_excel, mock_export_md, mock_run_sweep):
        mock_run_sweep.return_value = self.mock_sweep_df
        main()
        
        # Verify markdown export is called with default path
        mock_export_md.assert_called_once()
        args, kwargs = mock_export_md.call_args
        self.assertEqual(args[1], "output\\parameter_sweep_report.md" if sys.platform == "win32" else "output/parameter_sweep_report.md")
        # Verify excel export is NOT called
        mock_export_excel.assert_not_called()

    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.run_parameter_sweep")
    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.export_parameter_sweep_report_markdown")
    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.export_parameter_sweep_report_excel")
    @mock.patch("sys.argv", ["parameter_sweep_report.py", "--stock", "2330", "--strategy", "ma_cross", "--output-excel"])
    def test_excel_default_output(self, mock_export_excel, mock_export_md, mock_run_sweep):
        mock_run_sweep.return_value = self.mock_sweep_df
        main()
        
        # Verify excel export is called with default path
        mock_export_excel.assert_called_once()
        args, kwargs = mock_export_excel.call_args
        self.assertEqual(args[1], "output\\parameter_sweep_report.xlsx" if sys.platform == "win32" else "output/parameter_sweep_report.xlsx")
        # Verify markdown export is NOT called
        mock_export_md.assert_not_called()

    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.run_parameter_sweep")
    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.export_parameter_sweep_report_markdown")
    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.export_parameter_sweep_report_excel")
    @mock.patch("sys.argv", ["parameter_sweep_report.py", "--stock", "2330", "--strategy", "ma_cross", "--output-md", "custom_md.md", "--output-excel", "custom_xl.xlsx"])
    def test_custom_output_paths(self, mock_export_excel, mock_export_md, mock_run_sweep):
        mock_run_sweep.return_value = self.mock_sweep_df
        main()
        
        mock_export_md.assert_called_once()
        self.assertEqual(mock_export_md.call_args[0][1], "custom_md.md")
        
        mock_export_excel.assert_called_once()
        self.assertEqual(mock_export_excel.call_args[0][1], "custom_xl.xlsx")

    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.run_parameter_sweep")
    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.export_parameter_sweep_report_markdown")
    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.export_parameter_sweep_report_excel")
    @mock.patch("sys.argv", ["parameter_sweep_report.py", "--stock", "2330", "--strategy", "ma_cross"])
    def test_no_output_flags_prints_summary(self, mock_export_excel, mock_export_md, mock_run_sweep):
        mock_run_sweep.return_value = self.mock_sweep_df
        
        import io
        captured_output = io.StringIO()
        sys.stdout = captured_output
        try:
            main()
        finally:
            sys.stdout = sys.__stdout__
            
        # Verify exporters not called
        mock_export_md.assert_not_called()
        mock_export_excel.assert_not_called()
        
        # Verify summary output
        out = captured_output.getvalue()
        self.assertIn("Total Rows: 2", out)
        self.assertIn("Best Strategy: ma_cross", out)

    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.run_parameter_sweep")
    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.export_parameter_sweep_report_markdown")
    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.export_parameter_sweep_report_excel")
    @mock.patch("sys.argv", ["parameter_sweep_report.py", "--stock", "2330", "--strategy", "invalid_strategy", "--output-md", "--output-excel"])
    def test_invalid_strategy_raises_system_exit(self, mock_export_excel, mock_export_md, mock_run_sweep):
        # Mock run_parameter_sweep to raise ValueError as the real engine would do
        mock_run_sweep.side_effect = ValueError("unsupported strategy: invalid_strategy.")
        
        with self.assertRaises(SystemExit) as cm:
            main()
            
        self.assertEqual(cm.exception.code, 1)
        mock_export_md.assert_not_called()
        mock_export_excel.assert_not_called()

    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.run_parameter_sweep")
    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.export_parameter_sweep_report_markdown")
    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.export_parameter_sweep_report_excel")
    @mock.patch("sys.argv", ["parameter_sweep_report.py", "--stock", "2330", "--strategy", "ma_cross", "--output-md", "--output-excel"])
    def test_sweep_exception_raises_system_exit(self, mock_export_excel, mock_export_md, mock_run_sweep):
        mock_run_sweep.side_effect = Exception("Network Error")
        
        with self.assertRaises(SystemExit) as cm:
            main()
            
        self.assertEqual(cm.exception.code, 1)
        mock_export_md.assert_not_called()
        mock_export_excel.assert_not_called()

    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.run_parameter_sweep")
    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.export_parameter_sweep_report_markdown")
    @mock.patch("src.tw_stock_tool.cli.parameter_sweep_report.export_parameter_sweep_report_excel")
    @mock.patch("sys.argv", ["parameter_sweep_report.py", "--stock", "2330"])
    def test_missing_strategy_raises_system_exit(self, mock_export_excel, mock_export_md, mock_run_sweep):
        # argparse raises SystemExit(2) when required arguments are missing
        with self.assertRaises(SystemExit) as cm:
            main()
            
        # Error code from argparse should be 2, but just verifying it exits
        self.assertIsNotNone(cm.exception.code)
        mock_run_sweep.assert_not_called()
        mock_export_md.assert_not_called()
        mock_export_excel.assert_not_called()


if __name__ == "__main__":
    unittest.main()
