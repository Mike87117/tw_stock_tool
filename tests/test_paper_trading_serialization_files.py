import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from tw_stock_tool.paper_trading.models import (
    SimulatedOrder,
    SimulatedFill,
    PaperTradingModelError,
)
from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult
from tw_stock_tool.paper_trading.serialization import (
    serialize_simulated_paper_trading_result,
    export_simulated_paper_trading_result_json,
    load_simulated_paper_trading_result_json,
)
from tw_stock_tool.paper_trading.serialization_files import (
    export_simulated_paper_trading_result_json_file,
    load_simulated_paper_trading_result_json_file,
)
import tw_stock_tool.paper_trading


class TestPaperTradingSerializationFiles(unittest.TestCase):
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
            strategy="test_strategy",
            metadata={"note": "測試"}
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

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    def test_export_json_file_writes_file_and_returns_absolute_path(self):
        target = self.temp_dir / "result.json"
        returned_path = export_simulated_paper_trading_result_json_file(self.result, target)
        
        self.assertEqual(returned_path, target.resolve())
        self.assertTrue(target.exists())
        self.assertTrue(returned_path.is_absolute())

    def test_export_json_file_creates_parent_dirs(self):
        target = self.temp_dir / "nested" / "dirs" / "result.json"
        returned_path = export_simulated_paper_trading_result_json_file(self.result, target)
        
        self.assertTrue(target.exists())

    def test_export_json_file_uses_utf8(self):
        target = self.temp_dir / "result.json"
        export_simulated_paper_trading_result_json_file(self.result, target)
        
        content = target.read_text(encoding="utf-8")
        self.assertIn("測試", content)

    def test_export_json_file_respects_overwrite_false(self):
        target = self.temp_dir / "result.json"
        export_simulated_paper_trading_result_json_file(self.result, target)
        
        with self.assertRaises(FileExistsError):
            export_simulated_paper_trading_result_json_file(self.result, target, overwrite=False)

    def test_export_json_file_supports_overwrite_true(self):
        target = self.temp_dir / "result.json"
        export_simulated_paper_trading_result_json_file(self.result, target)
        
        # Should not raise
        export_simulated_paper_trading_result_json_file(self.result, target, overwrite=True)

    def test_load_json_file_returns_result(self):
        target = self.temp_dir / "result.json"
        export_simulated_paper_trading_result_json_file(self.result, target)
        
        loaded = load_simulated_paper_trading_result_json_file(target)
        self.assertEqual(loaded.symbol, "2330")
        self.assertEqual(loaded.orders[0].metadata["note"], "測試")

    def test_write_then_read_round_trip(self):
        # Result -> JSON file -> Result
        # (datetime will be strings, so we test with strings initially)
        self.result.orders[0].signal_time = self.dt.isoformat()
        self.result.orders[0].created_at = self.dt.isoformat()
        self.result.fills[0].filled_at = self.dt.isoformat()

        target = self.temp_dir / "result.json"
        export_simulated_paper_trading_result_json_file(self.result, target)
        loaded = load_simulated_paper_trading_result_json_file(target)
        
        self.assertEqual(self.result, loaded)

    def test_read_missing_file_behavior(self):
        target = self.temp_dir / "missing.json"
        with self.assertRaises(FileNotFoundError):
            load_simulated_paper_trading_result_json_file(target)

    def test_read_directory_path_behavior(self):
        target = self.temp_dir / "dir.json"
        target.mkdir()
        
        with self.assertRaises((IsADirectoryError, PermissionError)):
            load_simulated_paper_trading_result_json_file(target)

    def test_read_invalid_json_behavior(self):
        target = self.temp_dir / "result.json"
        target.write_text("invalid json", encoding="utf-8")
        
        with self.assertRaisesRegex(PaperTradingModelError, "Invalid JSON content"):
            load_simulated_paper_trading_result_json_file(target)

    def test_read_wrong_schema_behavior(self):
        target = self.temp_dir / "result.json"
        
        data = serialize_simulated_paper_trading_result(self.result)
        data["schema_version"] = 99
        target.write_text(json.dumps(data), encoding="utf-8")
        
        with self.assertRaisesRegex(PaperTradingModelError, "Unsupported schema_version"):
            load_simulated_paper_trading_result_json_file(target)

    def test_public_api_exports(self):
        self.assertTrue(hasattr(tw_stock_tool.paper_trading, "export_simulated_paper_trading_result_json_file"))
        self.assertTrue(hasattr(tw_stock_tool.paper_trading, "load_simulated_paper_trading_result_json_file"))
        
        self.assertIs(tw_stock_tool.paper_trading.export_simulated_paper_trading_result_json_file, export_simulated_paper_trading_result_json_file)
        self.assertIs(tw_stock_tool.paper_trading.load_simulated_paper_trading_result_json_file, load_simulated_paper_trading_result_json_file)

if __name__ == "__main__":
    unittest.main()
