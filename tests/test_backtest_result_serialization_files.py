import unittest
import tempfile
from pathlib import Path
import json
import subprocess
import sys
import textwrap

import pandas as pd

from tw_stock_tool.backtesting.results import BacktestResult
from tw_stock_tool.backtesting.serialization import BacktestResultSerializationError
from tw_stock_tool.backtesting.serialization_files import (
    export_backtest_result_json_file,
    load_backtest_result_json_file,
)


class TestBacktestResultSerializationFiles(unittest.TestCase):
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
            total_return_pct=0.1,
            buy_hold_return_pct=0.05,
            cagr_pct=0.1,
            exposure_pct=0.5,
            trade_count=1,
            win_rate_pct=1.0,
            max_drawdown_pct=0.0,
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

    def test_export_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            
            # Parent directories created through the writer path
            file_path = temp_dir / "nested" / "dir" / "result.json"
            
            returned_path = export_backtest_result_json_file(self.backtest_result, file_path)
            
            # returned path is a Path and is absolute
            self.assertIsInstance(returned_path, Path)
            self.assertTrue(returned_path.is_absolute())
            self.assertEqual(returned_path, file_path.resolve())
            
            # writes a valid JSON file
            content = returned_path.read_text(encoding="utf-8")
            data = json.loads(content)
            self.assertEqual(data["result_type"], "backtest_result")
            
            # roundtrips back to BacktestResult
            # UTF-8 content survives roundtrip (strategy/parameters containing Chinese text)
            loaded_br = load_backtest_result_json_file(returned_path)
            self.assertIsInstance(loaded_br, BacktestResult)
            self.assertEqual(loaded_br.strategy, "策略測試")
            self.assertEqual(loaded_br.parameters["note"], "參數測試")

    def test_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as td:
            file_path = Path(td) / "existing.json"
            file_path.write_text("initial content", encoding="utf-8")
            
            # overwrite=False rejects an existing file with FileExistsError
            with self.assertRaises(FileExistsError):
                export_backtest_result_json_file(self.backtest_result, file_path, overwrite=False)
                
            # overwrite=False does not modify the existing file content
            self.assertEqual(file_path.read_text(encoding="utf-8"), "initial content")
            
            # overwrite=True replaces the existing file
            export_backtest_result_json_file(self.backtest_result, file_path, overwrite=True)
            content = file_path.read_text(encoding="utf-8")
            self.assertNotEqual(content, "initial content")
            self.assertTrue(content.startswith("{"))

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as td:
            file_path = Path(td) / "invalid.json"
            file_path.write_text("{invalid json", encoding="utf-8")
            
            # loading invalid JSON raises BacktestResultSerializationError
            with self.assertRaises(BacktestResultSerializationError):
                load_backtest_result_json_file(file_path)

    def test_invalid_schema(self):
        with tempfile.TemporaryDirectory() as td:
            file_path = Path(td) / "schema.json"
            file_path.write_text('{"schema_version": 999, "result_type": "unknown"}', encoding="utf-8")
            
            # loading invalid artifact schema raises BacktestResultSerializationError
            with self.assertRaises(BacktestResultSerializationError):
                load_backtest_result_json_file(file_path)

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as td:
            file_path = Path(td) / "missing.json"
            
            # missing file raises FileNotFoundError
            with self.assertRaises(FileNotFoundError):
                load_backtest_result_json_file(file_path)

    def test_no_forbidden_dependencies_imported(self):
        script = textwrap.dedent("""
            import sys
            from tw_stock_tool.backtesting.serialization_files import export_backtest_result_json_file, load_backtest_result_json_file
            
            forbidden = [
                "shioaji",
                "yfinance",
                "tw_stock_tool.data",
                "tw_stock_tool.data_loader",
                "tw_stock_tool.cli",
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
