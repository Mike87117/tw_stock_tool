import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tw_stock_tool.cli import simulated_paper_trading_export_cli
from tw_stock_tool.paper_trading.models import (
    SimulatedOrder,
    SimulatedFill,
)
from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult
from tw_stock_tool.paper_trading.serialization_files import (
    export_simulated_paper_trading_result_json_file,
)


class TestSimulatedPaperTradingExportCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        
        self.dt = datetime(2023, 1, 1, 12, 0, 0)
        
        self.order1 = SimulatedOrder(
            order_id="o1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            signal_time=self.dt,
            created_at=self.dt,
            strategy="test_strategy"
        )
        self.fill1 = SimulatedFill(
            order_id="o1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            price=100.5,
            filled_at=self.dt,
            fee=20.0,
            tax=0.0,
            slippage=0.0
        )
        self.result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=1000000.0,
            final_cash=899307.0,
            final_position_quantity=1000,
            average_cost=100.5,
            realized_pnl=0.0,
            unrealized_pnl=5000.0,
            total_equity=1004307.0,
            order_count=1,
            fill_count=1,
            open_position_count=1,
            orders=(self.order1,),
            fills=(self.fill1,)
        )
        self.input_json = self.temp_dir / "input.json"
        export_simulated_paper_trading_result_json_file(self.result, self.input_json)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    def test_cli_help_includes_safety_wording(self):
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            with self.assertRaises(SystemExit) as cm:
                simulated_paper_trading_export_cli.main(["--help"])
            self.assertEqual(cm.exception.code, 0)
            
            help_text = mock_stdout.getvalue().replace('\n', ' ')
            self.assertIn("Export reports from an existing research-only simulated paper trading JSON artifact", help_text)
            self.assertIn("Does not fetch market data, run strategies, connect to brokers, or place orders", help_text)
            
            # Check forbidden words
            forbidden = [
                "trading signal", "buy signal", "sell signal",
                "order placement", "live trading", "investment advice"
            ]
            for word in forbidden:
                self.assertNotIn(word.lower(), help_text.lower())

    def test_cli_rejects_missing_output_targets(self):
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            with self.assertRaises(SystemExit) as cm:
                simulated_paper_trading_export_cli.main([str(self.input_json)])
            self.assertNotEqual(cm.exception.code, 0)
            
            err_text = mock_stderr.getvalue()
            self.assertIn("at least one of --output-markdown or --output-csv-dir is required", err_text)

    def test_cli_exports_markdown_from_json_artifact(self):
        out_md = self.temp_dir / "out.md"
        simulated_paper_trading_export_cli.main([str(self.input_json), "--output-markdown", str(out_md)])
        self.assertTrue(out_md.exists())

    def test_cli_exports_csv_files_from_json_artifact(self):
        out_dir = self.temp_dir / "out_csv"
        simulated_paper_trading_export_cli.main([str(self.input_json), "--output-csv-dir", str(out_dir)])
        self.assertTrue((out_dir / "simulated_paper_trading_summary.csv").exists())

    def test_cli_exports_both_markdown_and_csv_in_one_command(self):
        out_md = self.temp_dir / "out2.md"
        out_dir = self.temp_dir / "out_csv2"
        simulated_paper_trading_export_cli.main([
            str(self.input_json),
            "--output-markdown", str(out_md),
            "--output-csv-dir", str(out_dir)
        ])
        self.assertTrue(out_md.exists())
        self.assertTrue((out_dir / "simulated_paper_trading_summary.csv").exists())

    def test_cli_uses_overwrite_false_by_default(self):
        out_md = self.temp_dir / "out3.md"
        out_md.write_text("existing")
        
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            result = simulated_paper_trading_export_cli.main([str(self.input_json), "--output-markdown", str(out_md)])
            self.assertEqual(result, 1)
            err_text = mock_stderr.getvalue()
            self.assertIn("File already exists", err_text)
            self.assertIn("Use --overwrite", err_text)

    def test_cli_supports_overwrite(self):
        out_md = self.temp_dir / "out4.md"
        out_md.write_text("existing")
        
        # Should not raise
        simulated_paper_trading_export_cli.main([
            str(self.input_json),
            "--output-markdown", str(out_md),
            "--overwrite"
        ])
        
    def test_cli_rejects_invalid_json_with_clean_error(self):
        bad_json = self.temp_dir / "bad.json"
        bad_json.write_text("not json")
        out_md = self.temp_dir / "bad.md"
        
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            result = simulated_paper_trading_export_cli.main([str(bad_json), "--output-markdown", str(out_md)])
            self.assertEqual(result, 1)
            err_text = mock_stderr.getvalue()
            self.assertIn("Invalid JSON content", err_text)
            self.assertNotIn("Traceback", err_text)

    def test_cli_rejects_wrong_schema_with_clean_error(self):
        bad_schema = self.temp_dir / "schema.json"
        data = json.loads(self.input_json.read_text())
        data["schema_version"] = 99
        bad_schema.write_text(json.dumps(data))
        out_md = self.temp_dir / "bad2.md"
        
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            result = simulated_paper_trading_export_cli.main([str(bad_schema), "--output-markdown", str(out_md)])
            self.assertEqual(result, 1)
            err_text = mock_stderr.getvalue()
            self.assertIn("Unsupported schema_version", err_text)
            self.assertNotIn("Traceback", err_text)

    def test_cli_rejects_missing_input_file_with_clean_error(self):
        missing = self.temp_dir / "missing.json"
        out_md = self.temp_dir / "missing.md"
        
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            result = simulated_paper_trading_export_cli.main([str(missing), "--output-markdown", str(out_md)])
            self.assertEqual(result, 1)
            err_text = mock_stderr.getvalue()
            self.assertIn("No such file or directory", err_text)
            self.assertNotIn("Traceback", err_text)

    def test_no_live_data_modules_imported(self):
        # We can check sys.modules if any of the banned modules are loaded by the module itself
        # Note: the test runner might have loaded them, so we just inspect the file ast or strings
        import ast
        cli_file = Path(simulated_paper_trading_export_cli.__file__)
        tree = ast.parse(cli_file.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.append(name.name)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)
                
        for imp in imports:
            self.assertNotEqual(imp, "tw_stock_tool.data")
            self.assertNotEqual(imp, "tw_stock_tool.strategies")
            self.assertNotEqual(imp, "tw_stock_tool.backtesting")

if __name__ == "__main__":
    unittest.main()
