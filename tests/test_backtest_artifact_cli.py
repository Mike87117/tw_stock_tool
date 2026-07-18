import sys
import tempfile
import unittest
import json
import subprocess
import textwrap
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.backtesting.results import BacktestResult
from tw_stock_tool.backtesting.serialization_files import export_backtest_result_json_file
from tw_stock_tool.cli import backtest_artifact_cli
from tw_stock_tool.paper_trading.serialization_files import load_simulated_paper_trading_result_json_file


class TestBacktestArtifactCli(unittest.TestCase):
    def setUp(self):
        self.trades_df = pd.DataFrame([
            {
                "Entry Date": "2024-01-01",
                "Exit Date": "2024-01-05",
                "Entry Price": 100.0,
                "Exit Price": 110.0,
                "Shares": 1000,
                "PnL": 10000.0,
            }
        ])
        
        self.equity_curve = pd.Series(
            [100000.0, 110000.0],
            index=["2024-01-01", "2024-01-05"],
            name="Equity"
        )

        self.backtest_result = BacktestResult(
            initial_capital=100000.0,
            final_capital=110000.0,
            total_return_pct=10.0,
            buy_hold_return_pct=0.05,
            cagr_pct=0.1,
            exposure_pct=0.5,
            trade_count=1,
            win_rate_pct=1.0,
            max_drawdown_pct=-5.0,
            profit_factor=0.0,
            best_trade_pct=0.1,
            worst_trade_pct=0.1,
            avg_hold_days=4.0,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            avg_profit=10000.0,
            avg_loss=0.0,
            trades=self.trades_df,
            equity_curve=self.equity_curve,
            stock="2330",
            strategy="策略測試",
            parameters={"param1": 1, "note": "參數測試"},
            start_date="2024-01-01",
            end_date="2024-01-05"
        )
        
        self.td = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self.td.name)
        self.valid_json_path = self.temp_dir / "valid.json"
        export_backtest_result_json_file(self.backtest_result, self.valid_json_path)

    def tearDown(self):
        self.td.cleanup()

    def test_help_contains_safety_wording(self):
        out = StringIO()
        with patch("sys.stdout", out):
            with self.assertRaises(SystemExit) as cm:
                backtest_artifact_cli.main(["--help"])
            self.assertEqual(cm.exception.code, 0)
            
        help_text = out.getvalue().replace("\n", " ")
        self.assertIn("research-only", help_text)
        self.assertIn("Does not fetch market data", help_text)
        self.assertIn("run strategies", help_text)
        self.assertIn("connect to brokers", help_text)
        self.assertIn("place orders", help_text)
        self.assertIn("produce live signals", help_text)
        self.assertIn("provide investment advice", help_text)
        self.assertIn("retrospective offline mapping to a simulated paper trading JSON artifact", help_text)

        forbidden_words = [
            "investment recommendation",
            "recommended stocks",
            "best stocks to buy",
            "guaranteed profit",
            "guaranteed return",
            "order placement",
            "auto trading",
            "buy/sell/hold advice",
        ]
        for word in forbidden_words:
            self.assertNotIn(word, help_text.lower())
            
    def test_convert_help_contains_safety_wording(self):
        out = StringIO()
        with patch("sys.stdout", out):
            with self.assertRaises(SystemExit) as cm:
                backtest_artifact_cli.main(["convert-to-simulated-paper-trading", "--help"])
            self.assertEqual(cm.exception.code, 0)
            
        help_text = out.getvalue().replace("\n", " ")
        self.assertIn("research-only", help_text)
        self.assertIn("Does not fetch market data", help_text)
        self.assertIn("run strategies", help_text)
        self.assertIn("connect to brokers", help_text)
        self.assertIn("place orders", help_text)
        self.assertIn("produce live signals", help_text)
        self.assertIn("provide investment advice", help_text)
        self.assertIn("simulated paper trading", help_text)

        forbidden_words = [
            "investment recommendation",
            "recommended stocks",
            "best stocks to buy",
            "guaranteed profit",
            "guaranteed return",
            "order placement",
            "auto trading",
        ]
        for word in forbidden_words:
            self.assertNotIn(word, help_text.lower())

    def test_validate_success(self):
        out = StringIO()
        with patch("sys.stdout", out):
            backtest_artifact_cli.main(["validate", str(self.valid_json_path)])
        
        self.assertIn("BacktestResult artifact is valid", out.getvalue())
        self.assertIn(str(self.valid_json_path), out.getvalue())

    def test_inspect_success(self):
        out = StringIO()
        with patch("sys.stdout", out):
            backtest_artifact_cli.main(["inspect", str(self.valid_json_path)])
        
        output = out.getvalue()
        self.assertIn("BacktestResult Artifact Summary", output)
        self.assertIn("Stock:           2330", output)
        self.assertIn("Strategy:        策略測試", output)
        self.assertIn("Start Date:      2024-01-01", output)
        self.assertIn("End Date:        2024-01-05", output)
        self.assertIn("Trade Count:     1", output)
        self.assertIn("Total Return:    10.00%", output)
        self.assertIn("Max Drawdown:    -5.00%", output)
        self.assertNotIn("1000.00%", output)
        self.assertNotIn("-500.00%", output)
        
        forbidden_words = [
            "buy", "sell", "signal", "recommendation", "advice"
        ]
        for word in forbidden_words:
            self.assertNotIn(word, output.lower())

    def test_invalid_json(self):
        invalid_path = self.temp_dir / "invalid.json"
        invalid_path.write_text("{bad_json", encoding="utf-8")
        
        err = StringIO()
        with patch("sys.stderr", err):
            result = backtest_artifact_cli.main(["validate", str(invalid_path)])
            self.assertEqual(result, 1)
        
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_invalid_schema(self):
        schema_path = self.temp_dir / "schema.json"
        schema_path.write_text('{"schema_version": 999}', encoding="utf-8")
        
        err = StringIO()
        with patch("sys.stderr", err):
            result = backtest_artifact_cli.main(["validate", str(schema_path)])
            self.assertEqual(result, 1)
            
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_missing_file(self):
        missing_path = self.temp_dir / "missing.json"
        
        err = StringIO()
        with patch("sys.stderr", err):
            result = backtest_artifact_cli.main(["validate", str(missing_path)])
            self.assertEqual(result, 1)
            
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_convert_success(self):
        output_json = self.temp_dir / "converted.json"
        
        out = StringIO()
        with patch("sys.stdout", out):
            backtest_artifact_cli.main([
                "convert-to-simulated-paper-trading",
                str(self.valid_json_path),
                "--output-json",
                str(output_json),
            ])
            
        self.assertTrue(output_json.exists())
        output_text = out.getvalue()
        self.assertIn(f"Simulated paper trading artifact written: {output_json}", output_text)
        
        forbidden_words = ["BUY", "SELL", "signal", "recommendation", "advice"]
        for word in forbidden_words:
            self.assertNotIn(word, output_text)
            
        result = load_simulated_paper_trading_result_json_file(output_json)
        self.assertEqual(result.symbol, "2330")
        self.assertEqual(len(result.orders), 2)
        self.assertEqual(len(result.fills), 2)
        if len(result.orders) > 0:
            self.assertEqual(result.orders[0].metadata["semantics"], "retrospective_offline_mapping")

    @patch("tw_stock_tool.cli.backtest_artifact_cli.export_simulated_paper_trading_result_json_file")
    @patch("tw_stock_tool.cli.backtest_artifact_cli.load_simulated_paper_trading_result_json_file")
    def test_convert_readback_receives_exact_path(self, mock_load, mock_export):
        mock_export.return_value = "dummy-written-path.json"
        output_json = self.temp_dir / "converted_dummy.json"
        
        out = StringIO()
        with patch("sys.stdout", out):
            backtest_artifact_cli.main([
                "convert-to-simulated-paper-trading",
                str(self.valid_json_path),
                "--output-json",
                str(output_json),
            ])
            
        mock_load.assert_called_once_with("dummy-written-path.json")

    @patch("tw_stock_tool.cli.backtest_artifact_cli.load_simulated_paper_trading_result_json_file")
    def test_convert_readback_validation_failure(self, mock_load):
        from tw_stock_tool.paper_trading.models import PaperTradingModelError
        mock_load.side_effect = PaperTradingModelError("Simulated read-back error")
        output_json = self.temp_dir / "converted_readback_fail.json"
        
        err = StringIO()
        out = StringIO()
        with patch("sys.stderr", err), patch("sys.stdout", out):
            result = backtest_artifact_cli.main([
                    "convert-to-simulated-paper-trading",
                    str(self.valid_json_path),
                    "--output-json",
                    str(output_json),
                ])
            self.assertEqual(result, 1)
            
        self.assertIn("error: Simulated read-back error", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())
        self.assertNotIn("Simulated paper trading artifact written", out.getvalue())

    def test_convert_overwrite_behavior(self):
        output_json = self.temp_dir / "converted.json"
        output_json.write_text('{"dummy": true}', encoding="utf-8")
        
        err = StringIO()
        with patch("sys.stderr", err):
            result = backtest_artifact_cli.main([
                    "convert-to-simulated-paper-trading",
                    str(self.valid_json_path),
                    "--output-json",
                    str(output_json),
                ])
            self.assertEqual(result, 1)
            
        self.assertIn("Use --overwrite", err.getvalue())
        self.assertEqual(output_json.read_text(encoding="utf-8"), '{"dummy": true}')
        
        out = StringIO()
        with patch("sys.stdout", out):
            backtest_artifact_cli.main([
                "convert-to-simulated-paper-trading",
                str(self.valid_json_path),
                "--output-json",
                str(output_json),
                "--overwrite",
            ])
            
        self.assertNotEqual(output_json.read_text(encoding="utf-8"), '{"dummy": true}')
        
    def test_convert_invalid_json(self):
        invalid_path = self.temp_dir / "invalid.json"
        invalid_path.write_text("{bad_json", encoding="utf-8")
        output_json = self.temp_dir / "converted.json"
        
        err = StringIO()
        with patch("sys.stderr", err):
            result = backtest_artifact_cli.main([
                    "convert-to-simulated-paper-trading",
                    str(invalid_path),
                    "--output-json",
                    str(output_json),
                ])
            self.assertEqual(result, 1)
        
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_convert_invalid_schema(self):
        schema_path = self.temp_dir / "schema.json"
        schema_path.write_text('{"schema_version": 999}', encoding="utf-8")
        output_json = self.temp_dir / "converted.json"

        err = StringIO()
        with patch("sys.stderr", err):
            result = backtest_artifact_cli.main([
                    "convert-to-simulated-paper-trading",
                    str(schema_path),
                    "--output-json",
                    str(output_json),
                ])
            self.assertEqual(result, 1)

        self.assertIn("error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_convert_missing_file(self):
        missing_path = self.temp_dir / "missing.json"
        output_json = self.temp_dir / "converted.json"
        
        err = StringIO()
        with patch("sys.stderr", err):
            result = backtest_artifact_cli.main([
                    "convert-to-simulated-paper-trading",
                    str(missing_path),
                    "--output-json",
                    str(output_json),
                ])
            self.assertEqual(result, 1)
            
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_convert_invalid_trade_structure(self):
        # Create a valid BacktestResult with missing trade columns to cause PaperTradingModelError
        invalid_result = BacktestResult(
            initial_capital=100000.0,
            final_capital=110000.0,
            total_return_pct=10.0,
            buy_hold_return_pct=0.05,
            cagr_pct=0.1,
            exposure_pct=0.5,
            trade_count=1,
            win_rate_pct=1.0,
            max_drawdown_pct=-5.0,
            profit_factor=0.0,
            best_trade_pct=0.1,
            worst_trade_pct=0.1,
            avg_hold_days=4.0,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            avg_profit=10000.0,
            avg_loss=0.0,
            trades=pd.DataFrame([{"Bad Column": "Value"}]),
            equity_curve=self.equity_curve,
            stock="2330",
            strategy="策略測試",
            parameters={"param1": 1, "note": "參數測試"},
            start_date="2024-01-01",
            end_date="2024-01-05"
        )
        invalid_path = self.temp_dir / "invalid_trades.json"
        export_backtest_result_json_file(invalid_result, invalid_path)
        output_json = self.temp_dir / "converted.json"
        
        err = StringIO()
        with patch("sys.stderr", err):
            result = backtest_artifact_cli.main([
                    "convert-to-simulated-paper-trading",
                    str(invalid_path),
                    "--output-json",
                    str(output_json),
                ])
            self.assertEqual(result, 1)
            
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_no_forbidden_dependencies_imported(self):
        script = textwrap.dedent("""
            import sys
            import tw_stock_tool.cli.backtest_artifact_cli
            
            forbidden = [
                "shioaji",
                "yfinance",
                "tw_stock_tool.data",
                "tw_stock_tool.data_loader",
                "tw_stock_tool.strategies",
                "tw_stock_tool.broker"
            ]
            
            found = [m for m in forbidden if m in sys.modules]
            if found:
                print(f"Forbidden modules found: {found}", file=sys.stderr)
                sys.exit(1)
        """)
        
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"Subprocess failed:\\n{result.stderr}")

if __name__ == "__main__":
    unittest.main()
