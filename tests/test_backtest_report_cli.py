import unittest
import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path

from tw_stock_tool.cli.backtest_report import _parse_args, _normalize_result, main


class TestBacktestReportCLI(unittest.TestCase):

    def test_parse_args(self):
        args = _parse_args(["--stock", "2330", "--strategy", "ma_cross"])
        self.assertEqual(args.stock, "2330")
        self.assertEqual(args.strategy, "ma_cross")
        self.assertIsNone(args.output_md)
        self.assertIsNone(args.output_excel)

        args = _parse_args(["--stock", "2330", "--strategy", "ma_cross", "--output-md", "--output-excel"])
        self.assertEqual(args.output_md, "")
        self.assertEqual(args.output_excel, "")

    def test_normalize_result_adds_fields(self):
        raw = {"Total Return %": 10.0}
        norm = _normalize_result(raw, "2330", "test_strat", "2023-01-01", "2023-12-31", {"param": 1})
        self.assertEqual(norm["Stock"], "2330")
        self.assertEqual(norm["Strategy"], "test_strat")
        self.assertEqual(norm["Start Date"], "2023-01-01")
        self.assertEqual(norm["End Date"], "2023-12-31")
        self.assertEqual(norm["Parameters"], {"param": 1})
        self.assertEqual(norm["Total Return %"], 10.0)

    @patch("tw_stock_tool.cli.backtest_report.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_report.run_backtest")
    @patch("tw_stock_tool.cli.backtest_report.export_backtest_report_markdown")
    @patch("tw_stock_tool.cli.backtest_report.export_backtest_report_excel")
    @patch("tw_stock_tool.cli.backtest_report._parse_args")
    def test_main_outputs_both_reports(self, mock_parse, mock_export_excel, mock_export_md, mock_run, mock_analyze):
        mock_parse.return_value = MagicMock(
            stock="2330",
            strategy="ma_cross",
            period="1y",
            initial_capital=100000,
            output_md="",
            output_excel="",
            output_dir="output",
            force_refresh=False,
            short_window=5,
            long_window=20
        )
        mock_run.return_value = {"Total Return %": 5.0}
        
        mock_strat = MagicMock()
        mock_strat.return_value = pd.DataFrame(index=pd.date_range("2023-01-01", "2023-01-10"))
        with patch.dict("tw_stock_tool.cli.backtest_report.STRATEGIES", {"ma_cross_strategy": mock_strat}):
            main()
        
        mock_export_md.assert_called_once()
        mock_export_excel.assert_called_once()
        
        # Verify default paths
        md_path = mock_export_md.call_args[0][1]
        self.assertEqual(Path(md_path).parts[-2:], ("output", "backtest_report.md"))
        
        ex_path = mock_export_excel.call_args[0][1]
        self.assertEqual(Path(ex_path).parts[-2:], ("output", "backtest_report.xlsx"))

    @patch("tw_stock_tool.cli.backtest_report.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_report.run_backtest")
    @patch("tw_stock_tool.cli.backtest_report.export_backtest_report_markdown")
    @patch("tw_stock_tool.cli.backtest_report.export_backtest_report_excel")
    @patch("tw_stock_tool.cli.backtest_report._parse_args")
    def test_main_custom_output_paths(self, mock_parse, mock_export_excel, mock_export_md, mock_run, mock_analyze):
        mock_parse.return_value = MagicMock(
            stock="2330",
            strategy="ma_cross",
            period="1y",
            initial_capital=100000,
            output_md="output/custom.md",
            output_excel="output/custom.xlsx",
            output_dir="output",
            force_refresh=False,
            short_window=5,
            long_window=20
        )
        mock_run.return_value = {"Total Return %": 5.0}
        
        mock_strat = MagicMock()
        mock_strat.return_value = pd.DataFrame(index=pd.date_range("2023-01-01", "2023-01-10"))
        with patch.dict("tw_stock_tool.cli.backtest_report.STRATEGIES", {"ma_cross_strategy": mock_strat}):
            main()
        
        mock_export_md.assert_called_once()
        mock_export_excel.assert_called_once()
        
        self.assertEqual(mock_export_md.call_args[0][1], "output/custom.md")
        self.assertEqual(mock_export_excel.call_args[0][1], "output/custom.xlsx")

    @patch("tw_stock_tool.cli.backtest_report.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_report.run_backtest")
    @patch("tw_stock_tool.cli.backtest_report.export_backtest_report_markdown")
    @patch("tw_stock_tool.cli.backtest_report.export_backtest_report_excel")
    @patch("tw_stock_tool.cli.backtest_report._parse_args")
    def test_main_no_output_specified(self, mock_parse, mock_export_excel, mock_export_md, mock_run, mock_analyze):
        mock_parse.return_value = MagicMock(
            stock="2330",
            strategy="ma_cross",
            period="1y",
            initial_capital=100000,
            output_md=None,
            output_excel=None,
            output_dir="output",
            force_refresh=False,
            short_window=5,
            long_window=20
        )
        mock_run.return_value = {"Total Return %": 5.0}
        
        mock_strat = MagicMock()
        mock_strat.return_value = pd.DataFrame(index=pd.date_range("2023-01-01", "2023-01-10"))
        with patch.dict("tw_stock_tool.cli.backtest_report.STRATEGIES", {"ma_cross_strategy": mock_strat}):
            main()
        
        mock_export_md.assert_not_called()
        mock_export_excel.assert_not_called()

    @patch("tw_stock_tool.cli.backtest_report.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_report._parse_args")
    def test_main_unrecoverable_error_exits_with_1(self, mock_parse, mock_analyze):
        mock_parse.return_value = MagicMock(
            stock="2330",
            strategy="ma_cross",
            period="1y",
            initial_capital=100000,
            output_md=None,
            output_excel=None,
            output_dir="output",
            force_refresh=False,
            short_window=5,
            long_window=20
        )
        mock_analyze.side_effect = Exception("Network Error")
        
        with self.assertRaises(SystemExit) as cm:
            main()
            
        self.assertEqual(cm.exception.code, 1)
