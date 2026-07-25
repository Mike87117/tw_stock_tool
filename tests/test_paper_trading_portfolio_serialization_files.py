"""
Unit tests for multi-symbol portfolio trading serialization filesystem helpers.
"""

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

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

    def test_export_json_file_delegation(self) -> None:
        target_path = self.temp_dir / "delegated.json"
        mock_json_str = '{"mock_key": "mock_value"}'

        with patch(
            "tw_stock_tool.paper_trading.portfolio_serialization_files.export_simulated_portfolio_trading_result_json",
            return_value=mock_json_str,
        ) as mock_serializer, patch("json.dumps") as mock_json_dumps:
            ret_path = export_simulated_portfolio_trading_result_json_file(self.result, target_path)

            mock_serializer.assert_called_once_with(self.result)
            mock_json_dumps.assert_not_called()
            self.assertTrue(ret_path.is_absolute())
            self.assertEqual(ret_path, target_path.resolve())
            self.assertEqual(target_path.read_text(encoding="utf-8"), mock_json_str)

    def test_load_json_file_delegation(self) -> None:
        file_path = self.temp_dir / "raw_load.json"
        raw_text = '{\n  "schema_version": "v1",\n  "note": "測試 Unicode "\n}\n'
        file_path.write_text(raw_text, encoding="utf-8")

        mock_obj = MagicMock(spec=SimulatedPortfolioTradingResult)

        with patch(
            "tw_stock_tool.paper_trading.portfolio_serialization_files.load_simulated_portfolio_trading_result_json",
            return_value=mock_obj,
        ) as mock_deserializer:
            ret_result = load_simulated_portfolio_trading_result_json_file(file_path)

            mock_deserializer.assert_called_once_with(raw_text)
            self.assertIs(ret_result, mock_obj)

    def test_export_and_load_full_round_trip(self) -> None:
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
        self.assertEqual(loaded_result, self.result)

    def test_export_json_file_overwrite_behavior(self) -> None:
        target_path = self.temp_dir / "portfolio.json"
        export_simulated_portfolio_trading_result_json_file(self.result, target_path)

        with self.assertRaises(FileExistsError):
            export_simulated_portfolio_trading_result_json_file(
                self.result,
                target_path,
                overwrite=False,
            )

        export_simulated_portfolio_trading_result_json_file(
            self.result,
            target_path,
            overwrite=True,
        )

    def test_export_source_mutation_safety(self) -> None:
        res = self.result

        # Pre-export snapshots
        orig_positions_tuple = res.positions
        orig_pos_elems = list(res.positions)
        orig_pending_tuple = res.pending_orders
        orig_pending_elems = list(res.pending_orders)
        orig_orders_tuple = res.orders
        orig_order_elems = list(res.orders)
        orig_fills_tuple = res.fills
        orig_fill_elems = list(res.fills)
        orig_rejections_tuple = res.rejections
        orig_rejection_elems = list(res.rejections)
        orig_audit_tuple = res.audit_log
        orig_audit_elems = list(res.audit_log)

        pos_snapshot = [(p.symbol, p.quantity, p.average_cost, p.last_price, p.market_value, p.realized_pnl, p.unrealized_pnl) for p in res.positions]
        pending_snapshot = [(po.order_id, po.symbol, po.side, po.quantity, po.signal_time, po.created_at, po.strategy, po.reference_price, po.reserved_buy_notional) for po in res.pending_orders]
        order_snapshot = [(o.order_id, o.symbol, o.side, o.quantity, o.signal_time, o.created_at, o.strategy) for o in res.orders]
        fill_snapshot = [(f.order_id, f.symbol, f.side, f.quantity, f.price, f.filled_at, f.fee, f.tax, f.slippage) for f in res.fills]
        rejection_snapshot = [(r.candidate_order, (r.candidate_order.order_id, r.candidate_order.symbol, r.candidate_order.side, r.candidate_order.quantity, r.candidate_order.signal_time, r.candidate_order.created_at, r.candidate_order.strategy), r.reasons) for r in res.rejections]
        audit_snapshot = [(rec.sequence, rec.record_id, rec.event_type, rec.status, rec.order_id, rec.symbol, rec.side, rec.quantity, rec.signal_time, rec.order_created_at, rec.expected_execution_model, rec.fill_time, rec.fill_price, rec.fee, rec.tax, rec.slippage, rec.strategy_name, dict(rec.strategy_metadata), rec.risk_allowed, rec.risk_rejection_reasons, dict(rec.guard_metadata), rec.error_code, rec.error_message) for rec in res.audit_log]

        # Execute export
        target_path = self.temp_dir / "mutation_test.json"
        export_simulated_portfolio_trading_result_json_file(res, target_path)

        # Assert tuple identities unchanged
        self.assertIs(res.positions, orig_positions_tuple)
        self.assertIs(res.pending_orders, orig_pending_tuple)
        self.assertIs(res.orders, orig_orders_tuple)
        self.assertIs(res.fills, orig_fills_tuple)
        self.assertIs(res.rejections, orig_rejections_tuple)
        self.assertIs(res.audit_log, orig_audit_tuple)

        # Assert every single element identity unchanged via assertIs
        for current, original in zip(res.positions, orig_pos_elems):
            self.assertIs(current, original)
        for current, original in zip(res.pending_orders, orig_pending_elems):
            self.assertIs(current, original)
        for current, original in zip(res.orders, orig_order_elems):
            self.assertIs(current, original)
        for current, original in zip(res.fills, orig_fill_elems):
            self.assertIs(current, original)
        for current, original in zip(res.rejections, orig_rejection_elems):
            self.assertIs(current, original)
        for current, original in zip(res.audit_log, orig_audit_elems):
            self.assertIs(current, original)

        # Compare field snapshots
        self.assertEqual([(p.symbol, p.quantity, p.average_cost, p.last_price, p.market_value, p.realized_pnl, p.unrealized_pnl) for p in res.positions], pos_snapshot)
        self.assertEqual([(po.order_id, po.symbol, po.side, po.quantity, po.signal_time, po.created_at, po.strategy, po.reference_price, po.reserved_buy_notional) for po in res.pending_orders], pending_snapshot)
        self.assertEqual([(o.order_id, o.symbol, o.side, o.quantity, o.signal_time, o.created_at, o.strategy) for o in res.orders], order_snapshot)
        self.assertEqual([(f.order_id, f.symbol, f.side, f.quantity, f.price, f.filled_at, f.fee, f.tax, f.slippage) for f in res.fills], fill_snapshot)
        self.assertEqual([(r.candidate_order, (r.candidate_order.order_id, r.candidate_order.symbol, r.candidate_order.side, r.candidate_order.quantity, r.candidate_order.signal_time, r.candidate_order.created_at, r.candidate_order.strategy), r.reasons) for r in res.rejections], rejection_snapshot)
        self.assertEqual([(rec.sequence, rec.record_id, rec.event_type, rec.status, rec.order_id, rec.symbol, rec.side, rec.quantity, rec.signal_time, rec.order_created_at, rec.expected_execution_model, rec.fill_time, rec.fill_price, rec.fee, rec.tax, rec.slippage, rec.strategy_name, dict(rec.strategy_metadata), rec.risk_allowed, rec.risk_rejection_reasons, dict(rec.guard_metadata), rec.error_code, rec.error_message) for rec in res.audit_log], audit_snapshot)

    def test_permission_error_propagation(self) -> None:
        target_path = self.temp_dir / "perm.json"
        with patch("builtins.open", side_effect=PermissionError("Export write permission denied")):
            with self.assertRaises(PermissionError) as cm:
                export_simulated_portfolio_trading_result_json_file(self.result, target_path)
            self.assertIn("Export write permission denied", str(cm.exception))

        with patch("pathlib.Path.read_text", side_effect=PermissionError("Load read permission denied")):
            with self.assertRaises(PermissionError) as cm:
                load_simulated_portfolio_trading_result_json_file(target_path)
            self.assertIn("Load read permission denied", str(cm.exception))


    def test_load_json_file_error_handling(self) -> None:
        missing_path = self.temp_dir / "missing.json"
        with self.assertRaises(FileNotFoundError):
            load_simulated_portfolio_trading_result_json_file(missing_path)

        dir_path = self.temp_dir / "dir_file"
        dir_path.mkdir()
        with self.assertRaises((IsADirectoryError, PermissionError)):
            load_simulated_portfolio_trading_result_json_file(dir_path)

        invalid_utf8_path = self.temp_dir / "invalid_utf8.json"
        invalid_utf8_path.write_bytes(b"\x80\x81\x82")
        with self.assertRaises(UnicodeDecodeError):
            load_simulated_portfolio_trading_result_json_file(invalid_utf8_path)

        malformed_json_path = self.temp_dir / "malformed.json"
        malformed_json_path.write_text("{not valid json}", encoding="utf-8")
        with self.assertRaises(PaperTradingModelError):
            load_simulated_portfolio_trading_result_json_file(malformed_json_path)

        unsupported_schema_path = self.temp_dir / "unsupported_schema.json"
        data = json.loads(export_simulated_portfolio_trading_result_json(self.result))
        data["schema_version"] = "v999"
        unsupported_schema_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(PaperTradingModelError):
            load_simulated_portfolio_trading_result_json_file(unsupported_schema_path)

        missing_field_path = self.temp_dir / "missing_field.json"
        del data["schema_version"]
        missing_field_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(PaperTradingModelError):
            load_simulated_portfolio_trading_result_json_file(missing_field_path)

        extra_field_path = self.temp_dir / "extra_field.json"
        data = json.loads(export_simulated_portfolio_trading_result_json(self.result))
        data["unapproved_extra"] = "bad"
        extra_field_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(PaperTradingModelError):
            load_simulated_portfolio_trading_result_json_file(extra_field_path)


if __name__ == "__main__":
    unittest.main()
