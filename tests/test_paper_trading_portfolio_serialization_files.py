"""
Unit tests for multi-symbol portfolio trading serialization filesystem helpers.
"""

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedFill,
    SimulatedOrder,
    SimulatedOrderRejection,
    SimulatedTradeEventType,
    SimulatedTradeLogRecord,
    SimulatedTradeStatus,
)
from tw_stock_tool.paper_trading.portfolio_results import (
    SimulatedPortfolioPendingOrderResult,
    SimulatedPortfolioPositionResult,
    SimulatedPortfolioTradingResult,
)
from tw_stock_tool.paper_trading.portfolio_serialization import (
    export_simulated_portfolio_trading_result_json,
)
from tw_stock_tool.paper_trading.portfolio_serialization_files import (
    export_simulated_portfolio_trading_result_json_file,
    load_simulated_portfolio_trading_result_json_file,
)


def _make_sample_portfolio_result() -> SimulatedPortfolioTradingResult:
    pos1 = SimulatedPortfolioPositionResult(
        symbol="2330.TW",
        quantity=1000,
        average_cost=500.0,
        last_price=550.0,
        market_value=550000.0,
        realized_pnl=10000.0,
        unrealized_pnl=50000.0,
    )
    pos2 = SimulatedPortfolioPositionResult(
        symbol="2454.TW",
        quantity=500,
        average_cost=800.0,
        last_price=900.0,
        market_value=450000.0,
        realized_pnl=0.0,
        unrealized_pnl=50000.0,
    )
    pending1 = SimulatedPortfolioPendingOrderResult(
        order_id="ORD_P1",
        symbol="2330.TW",
        side="BUY",
        quantity=500,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="ma_cross",
        reference_price=540.0,
        reserved_buy_notional=270000.0,
    )
    order1 = SimulatedOrder(
        order_id="ORD_1",
        symbol="2330.TW",
        side="BUY",
        quantity=1000,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="ma_cross",
    )
    fill1 = SimulatedFill(
        order_id="ORD_1",
        symbol="2330.TW",
        side="BUY",
        quantity=1000,
        price=500.0,
        filled_at="2026-01-02T09:00:01",
        fee=712.0,
        tax=0.0,
        slippage=0.0,
    )
    rejection1 = SimulatedOrderRejection(
        candidate_order=SimulatedOrder(
            order_id="ORD_R1",
            symbol="2454.TW",
            side="BUY",
            quantity=100,
            signal_time="2026-01-02",
            created_at="2026-01-02T09:00:00",
            strategy="rsi",
        ),
        reasons=("風控拒絕",),
    )
    rec1 = SimulatedTradeLogRecord(
        sequence=1,
        record_id="REC_1",
        event_type=SimulatedTradeEventType.ACCEPTED_PENDING,
        status=SimulatedTradeStatus.PENDING_NEXT_BAR_OPEN,
        order_id="ORD_1",
        symbol="2330.TW",
        side="BUY",
        quantity=1000,
        signal_time="2026-01-02",
        order_created_at="2026-01-02T09:00:00",
        expected_execution_model="next_bar_open",
        fill_time=None,
        fill_price=None,
        fee=0.0,
        tax=0.0,
        slippage=0.0,
        strategy_name="ma_cross",
        strategy_metadata={"window": 10},
        risk_allowed=True,
        risk_rejection_reasons=(),
        guard_metadata={"guard": "ok"},
        error_code=None,
        error_message=None,
    )

    return SimulatedPortfolioTradingResult(
        initial_cash=1000000.0,
        final_cash=1000000.0,
        total_market_value=1000000.0,
        total_equity=2000000.0,
        realized_pnl=10000.0,
        unrealized_pnl=100000.0,
        total_return=1000000.0,
        total_return_pct=1.0,
        open_position_count=2,
        order_count=1,
        fill_count=1,
        rejection_count=1,
        audit_record_count=1,
        positions=(pos1, pos2),
        pending_orders=(pending1,),
        orders=(order1,),
        fills=(fill1,),
        rejections=(rejection1,),
        audit_log=(rec1,),
    )


class TestPaperTradingPortfolioSerializationFiles(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.result = _make_sample_portfolio_result()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_json_file_success_and_round_trip(self) -> None:
        target_path = self.temp_dir / "nested" / "portfolio.json"
        returned_path = export_simulated_portfolio_trading_result_json_file(
            self.result,
            target_path,
        )

        self.assertEqual(returned_path, target_path.resolve())
        self.assertTrue(returned_path.is_file())

        written_content = returned_path.read_text(encoding="utf-8")
        expected_content = export_simulated_portfolio_trading_result_json(self.result)
        self.assertEqual(written_content, expected_content)
        self.assertIn("風控拒絕", written_content)

        loaded_result = load_simulated_portfolio_trading_result_json_file(returned_path)
        self.assertEqual(loaded_result.initial_cash, self.result.initial_cash)
        self.assertEqual(loaded_result.open_position_count, self.result.open_position_count)
        self.assertEqual(len(loaded_result.positions), 2)
        self.assertEqual(loaded_result.positions[0].symbol, "2330.TW")

    def test_export_json_file_overwrite_behavior(self) -> None:
        target_path = self.temp_dir / "portfolio.json"
        export_simulated_portfolio_trading_result_json_file(self.result, target_path)

        with self.assertRaises(FileExistsError):
            export_simulated_portfolio_trading_result_json_file(
                self.result,
                target_path,
                overwrite=False,
            )

        # Overwrite=True works cleanly
        export_simulated_portfolio_trading_result_json_file(
            self.result,
            target_path,
            overwrite=True,
        )

    def test_load_json_file_error_handling(self) -> None:
        # Missing file -> FileNotFoundError
        missing_path = self.temp_dir / "missing.json"
        with self.assertRaises(FileNotFoundError):
            load_simulated_portfolio_trading_result_json_file(missing_path)

        # Directory used as file -> IsADirectoryError (or PermissionError on Windows)
        dir_path = self.temp_dir / "dir_file"
        dir_path.mkdir()
        with self.assertRaises((IsADirectoryError, PermissionError)):
            load_simulated_portfolio_trading_result_json_file(dir_path)

        # Malformed UTF-8 -> UnicodeDecodeError
        invalid_utf8_path = self.temp_dir / "invalid_utf8.json"
        invalid_utf8_path.write_bytes(b"\x80\x81\x82")
        with self.assertRaises(UnicodeDecodeError):
            load_simulated_portfolio_trading_result_json_file(invalid_utf8_path)

        # Valid UTF-8 but invalid JSON text -> PaperTradingModelError
        malformed_json_path = self.temp_dir / "malformed.json"
        malformed_json_path.write_text("{not valid json}", encoding="utf-8")
        with self.assertRaises(PaperTradingModelError):
            load_simulated_portfolio_trading_result_json_file(malformed_json_path)

        # Unsupported schema version -> PaperTradingModelError
        unsupported_schema_path = self.temp_dir / "unsupported_schema.json"
        data = json.loads(export_simulated_portfolio_trading_result_json(self.result))
        data["schema_version"] = "v999"
        unsupported_schema_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(PaperTradingModelError):
            load_simulated_portfolio_trading_result_json_file(unsupported_schema_path)

        # Missing required schema field -> PaperTradingModelError
        missing_field_path = self.temp_dir / "missing_field.json"
        del data["schema_version"]
        missing_field_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(PaperTradingModelError):
            load_simulated_portfolio_trading_result_json_file(missing_field_path)

        # Extra schema field -> PaperTradingModelError
        extra_field_path = self.temp_dir / "extra_field.json"
        data = json.loads(export_simulated_portfolio_trading_result_json(self.result))
        data["unapproved_extra"] = "bad"
        extra_field_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(PaperTradingModelError):
            load_simulated_portfolio_trading_result_json_file(extra_field_path)


if __name__ == "__main__":
    unittest.main()
