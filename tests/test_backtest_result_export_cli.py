import unittest
import sys
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch, MagicMock

import pandas as pd

from tw_stock_tool.cli.backtest_result_export_cli import main, _parse_args
from tw_stock_tool.backtesting.results import BacktestResult
from tw_stock_tool.backtesting.backtest import BacktestError


class TestBacktestResultExportCLI(unittest.TestCase):
    def test_help_contains_safe_wording(self):
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                main(["--help"])

        self.assertEqual(ctx.exception.code, 0)
        output = out.getvalue()
        
        normalized_output = output.lower().replace('\n', ' ').replace('\r', ' ')
        self.assertIn("historical backtest artifact", normalized_output)
        self.assertIn("offline research", normalized_output)
        self.assertIn("not investment advice", normalized_output)

        # Verify no forbidden wording
        forbidden_words = [
            "live signal", "order signal", "buy/sell/hold advice", 
            "investment recommendation", "recommended stocks", "best stocks to buy",
            "guaranteed profit", "guaranteed return", "broker order", 
            "order placement", "live trading", "auto trading"
        ]
        for word in forbidden_words:
            self.assertNotIn(word.lower(), output.lower())

    def test_parse_args_defaults(self):
        args = _parse_args([
            "--stock", "2330",
            "--strategy", "ma_cross",
            "--output-json", "out.json",
        ])
        
        self.assertEqual(args.stock, "2330")
        self.assertEqual(args.strategy, "ma_cross")
        self.assertEqual(args.output_json, "out.json")
        self.assertFalse(args.overwrite)
        self.assertEqual(args.initial_capital, 100000.0)
        self.assertEqual(args.position_size, 1.0)

    def test_missing_required_args_exits_1(self):
        err = StringIO()
        with redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                main(["--stock", "2330"])
        
        self.assertEqual(ctx.exception.code, 2) # argparse missing required returns 2
        self.assertNotIn("Traceback", err.getvalue())
        
    @patch("tw_stock_tool.cli.backtest_result_export_cli.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_result_export_cli.STRATEGIES")
    @patch("tw_stock_tool.cli.backtest_result_export_cli.run_backtest_result")
    @patch("tw_stock_tool.cli.backtest_result_export_cli.export_backtest_result_json_file")
    def test_successful_export_sets_metadata_and_calls_export(self, mock_export, mock_run, mock_strategies, mock_analyze):
        # Setup mocks
        mock_strategy_func = MagicMock()
        mock_strategies.__contains__.side_effect = lambda k: True
        mock_strategies.__getitem__.return_value = mock_strategy_func
        
        mock_analysis = MagicMock()
        mock_analyze.return_value = mock_analysis
        
        mock_df_exec = pd.DataFrame({"Open": [100]}, index=pd.date_range("2024-01-01", periods=1))
        mock_strategy_func.return_value = mock_df_exec
        
        mock_result = BacktestResult(
            initial_capital=100000.0, final_capital=100000.0, total_return_pct=0.0,
            buy_hold_return_pct=0.0, cagr_pct=0.0, exposure_pct=0.0, trade_count=0,
            win_rate_pct=0.0, max_drawdown_pct=0.0, profit_factor=0.0, best_trade_pct=0.0,
            worst_trade_pct=0.0, avg_hold_days=0.0, sharpe_ratio=0.0, sortino_ratio=0.0,
            avg_profit=0.0, avg_loss=0.0, trades=pd.DataFrame(), equity_curve=pd.Series(),
            stock="", strategy=""
        )
        mock_run.return_value = mock_result
        
        out = StringIO()
        err = StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            main([
                "--stock", "2330", 
                "--strategy", "ma_cross", 
                "--output-json", "test.json"
            ])
            
        # Verify run_backtest_result was called (NOT run_backtest)
        mock_run.assert_called_once()
        
        # Verify metadata is set
        self.assertEqual(mock_result.stock, "2330")
        self.assertEqual(mock_result.strategy, "ma_cross")
        self.assertEqual(mock_result.start_date, "2024-01-01")
        self.assertEqual(mock_result.end_date, "2024-01-01")
        self.assertIn("strategy", mock_result.parameters)
        self.assertIn("backtest", mock_result.parameters)
        
        # Verify file export uses export_backtest_result_json_file
        mock_export.assert_called_once_with(mock_result, "test.json", overwrite=False)
        
        # Verify no forbidden words in output
        forbidden_words = [
            "live signal", "order signal", "buy/sell/hold advice", 
            "investment recommendation", "recommended stocks", "best stocks to buy",
            "guaranteed profit", "guaranteed return", "broker order", 
            "order placement", "live trading", "auto trading"
        ]
        for word in forbidden_words:
            self.assertNotIn(word.lower(), out.getvalue().lower())

    @patch("tw_stock_tool.cli.backtest_result_export_cli.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_result_export_cli.STRATEGIES")
    @patch("tw_stock_tool.cli.backtest_result_export_cli.run_backtest_result")
    @patch("tw_stock_tool.cli.backtest_result_export_cli.export_backtest_result_json_file")
    def test_overwrite_flag_passes_true(self, mock_export, mock_run, mock_strategies, mock_analyze):
        mock_strategy_func = MagicMock()
        mock_strategies.__contains__.side_effect = lambda k: True
        mock_strategies.__getitem__.return_value = mock_strategy_func
        mock_analyze.return_value = MagicMock()
        mock_strategy_func.return_value = pd.DataFrame({"Open": [100]}, index=pd.date_range("2024-01-01", periods=1))
        mock_run.return_value = MagicMock()
        
        out = StringIO()
        err = StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            main([
                "--stock", "2330", 
                "--strategy", "ma_cross", 
                "--output-json", "test.json",
                "--overwrite"
            ])
            
        mock_export.assert_called_once()
        self.assertTrue(mock_export.call_args[1]["overwrite"])

    @patch("tw_stock_tool.cli.backtest_result_export_cli.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_result_export_cli.STRATEGIES")
    @patch("tw_stock_tool.cli.backtest_result_export_cli.run_backtest_result")
    @patch("tw_stock_tool.cli.backtest_result_export_cli.export_backtest_result_json_file")
    def test_existing_output_error_exits_cleanly(self, mock_export, mock_run, mock_strategies, mock_analyze):
        mock_strategy_func = MagicMock()
        mock_strategies.__contains__.side_effect = lambda k: True
        mock_strategies.__getitem__.return_value = mock_strategy_func
        mock_analyze.return_value = MagicMock()
        mock_strategy_func.return_value = pd.DataFrame({"Open": [100]}, index=pd.date_range("2024-01-01", periods=1))
        mock_run.return_value = MagicMock()
        mock_export.side_effect = FileExistsError("File exists")
        
        err = StringIO()
        with redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                main([
                    "--stock", "2330", 
                    "--strategy", "ma_cross", 
                    "--output-json", "test.json"
                ])
                
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("error:", err.getvalue())
        self.assertIn("Use --overwrite", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    @patch("tw_stock_tool.cli.backtest_result_export_cli.analyze_stock")
    def test_unknown_strategy_exits_cleanly(self, mock_analyze):
        err = StringIO()
        with redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                main([
                    "--stock", "2330", 
                    "--strategy", "invalid_strategy_xyz123", 
                    "--output-json", "test.json"
                ])
                
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())
        mock_analyze.assert_not_called()

    @patch("tw_stock_tool.cli.backtest_result_export_cli.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_result_export_cli.STRATEGIES")
    @patch("tw_stock_tool.cli.backtest_result_export_cli.run_backtest_result")
    def test_run_backtest_error_exits_cleanly(self, mock_run, mock_strategies, mock_analyze):
        mock_strategy_func = MagicMock()
        mock_strategies.__contains__.side_effect = lambda k: True
        mock_strategies.__getitem__.return_value = mock_strategy_func
        mock_analyze.return_value = MagicMock()
        mock_strategy_func.return_value = pd.DataFrame({"Open": [100]}, index=pd.date_range("2024-01-01", periods=1))
        mock_run.side_effect = BacktestError("Invalid position size")
        
        err = StringIO()
        with redirect_stderr(err):
            with self.assertRaises(SystemExit) as ctx:
                main([
                    "--stock", "2330", 
                    "--strategy", "ma_cross", 
                    "--output-json", "test.json"
                ])
                
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())


if __name__ == "__main__":
    unittest.main()
