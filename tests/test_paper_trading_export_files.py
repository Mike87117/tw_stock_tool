import unittest
import tempfile
from pathlib import Path

from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult
from tw_stock_tool.paper_trading.models import SimulatedOrder, SimulatedFill
from tw_stock_tool.paper_trading.export_files import (
    export_simulated_paper_trading_markdown_file,
    export_simulated_paper_trading_csv_files,
)

class TestPaperTradingExportFiles(unittest.TestCase):

    def setUp(self):
        self.order = SimulatedOrder(
            order_id="order-1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            signal_time="2023-01-01 10:00:00",
            created_at="2023-01-01 10:05:00",
            strategy="test_strategy"
        )
        self.fill = SimulatedFill(
            order_id="order-1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            price=100.5,
            filled_at="2023-01-01 10:10:00",
            fee=143.0,
            tax=0.0,
            slippage=50.0
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
            orders=(self.order,),
            fills=(self.fill,),
        )

    def test_export_markdown_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            temp_path = Path(tempdir) / "nested" / "report.md"

            result_path = export_simulated_paper_trading_markdown_file(self.result, temp_path)

            self.assertIsInstance(result_path, Path)
            self.assertTrue(result_path.exists())
            self.assertTrue(result_path.is_absolute())

            with open(result_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("# Simulated Paper Trading Report", content)
            self.assertIn("## Summary", content)
            self.assertIn("## Orders", content)
            self.assertIn("## Fills", content)

            with self.assertRaises(FileExistsError):
                export_simulated_paper_trading_markdown_file(self.result, result_path, overwrite=False)

            # Overwrite should succeed
            export_simulated_paper_trading_markdown_file(self.result, result_path, overwrite=True)

    def test_export_csv_files(self):
        with tempfile.TemporaryDirectory() as tempdir:
            temp_dir_path = Path(tempdir) / "csv_out"

            result_paths = export_simulated_paper_trading_csv_files(
                self.result, temp_dir_path, basename="test_run"
            )

            self.assertEqual(set(result_paths.keys()), {"summary", "orders", "fills"})

            for p in result_paths.values():
                self.assertIsInstance(p, Path)
                self.assertTrue(p.exists())

            self.assertEqual(result_paths["summary"].name, "test_run_summary.csv")
            self.assertEqual(result_paths["orders"].name, "test_run_orders.csv")
            self.assertEqual(result_paths["fills"].name, "test_run_fills.csv")

            with open(result_paths["summary"], "r", encoding="utf-8") as f:
                self.assertTrue(f.read().startswith("metric,value\n"))

            with open(result_paths["orders"], "r", encoding="utf-8") as f:
                self.assertTrue(f.read().startswith("order_id,symbol,side,quantity,signal_time,created_at,strategy\n"))

            with open(result_paths["fills"], "r", encoding="utf-8") as f:
                self.assertTrue(f.read().startswith("order_id,symbol,side,quantity,price,filled_at,fee,tax,slippage,gross_amount,net_cash_effect\n"))

            with self.assertRaises(FileExistsError):
                export_simulated_paper_trading_csv_files(self.result, temp_dir_path, basename="test_run", overwrite=False)

            # Overwrite should succeed
            export_simulated_paper_trading_csv_files(self.result, temp_dir_path, basename="test_run", overwrite=True)

if __name__ == "__main__":
    unittest.main()
