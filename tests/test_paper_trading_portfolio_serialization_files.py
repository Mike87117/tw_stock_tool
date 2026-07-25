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
        metadata={"order_meta": "val1"},
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
            metadata={"candidate_meta": "val2"},
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
        risk_rejection_reasons=("risk_reason_1",),
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


def _snapshot_result(res: SimulatedPortfolioTradingResult) -> dict:
    return {
        "scalars": (
            res.initial_cash,
            res.final_cash,
            res.total_market_value,
            res.total_equity,
            res.realized_pnl,
            res.unrealized_pnl,
            res.total_return,
            res.total_return_pct,
            res.open_position_count,
            res.order_count,
            res.fill_count,
            res.rejection_count,
            res.audit_record_count,
        ),
        "tuples_identities": {
            "positions": res.positions,
            "pending_orders": res.pending_orders,
            "orders": res.orders,
            "fills": res.fills,
            "rejections": res.rejections,
            "audit_log": res.audit_log,
        },
        "positions": [(p, (p.symbol, p.quantity, p.average_cost, p.last_price, p.market_value, p.realized_pnl, p.unrealized_pnl)) for p in res.positions],
        "pending_orders": [(po, (po.order_id, po.symbol, po.side, po.quantity, po.signal_time, po.created_at, po.strategy, po.reference_price, po.reserved_buy_notional)) for po in res.pending_orders],
        "orders": [
            (
                o,
                (o.order_id, o.symbol, o.side, o.quantity, o.signal_time, o.created_at, o.strategy),
                o.metadata,
                dict(o.metadata) if o.metadata is not None else None,
            )
            for o in res.orders
        ],
        "fills": [(f, (f.order_id, f.symbol, f.side, f.quantity, f.price, f.filled_at, f.fee, f.tax, f.slippage)) for f in res.fills],
        "rejections": [
            (
                r,
                r.candidate_order,
                (r.candidate_order.order_id, r.candidate_order.symbol, r.candidate_order.side, r.candidate_order.quantity, r.candidate_order.signal_time, r.candidate_order.created_at, r.candidate_order.strategy),
                r.candidate_order.metadata,
                dict(r.candidate_order.metadata) if r.candidate_order.metadata is not None else None,
                r.reasons,
                tuple(r.reasons),
            )
            for r in res.rejections
        ],
        "audit_log": [
            (
                rec,
                (rec.sequence, rec.record_id, rec.event_type, rec.status, rec.order_id, rec.symbol, rec.side, rec.quantity, rec.signal_time, rec.order_created_at, rec.expected_execution_model, rec.fill_time, rec.fill_price, rec.fee, rec.tax, rec.slippage, rec.strategy_name, rec.risk_allowed, rec.error_code, rec.error_message),
                rec.strategy_metadata,
                dict(rec.strategy_metadata),
                rec.risk_rejection_reasons,
                tuple(rec.risk_rejection_reasons),
                rec.guard_metadata,
                dict(rec.guard_metadata),
            )
            for rec in res.audit_log
        ],
    }


def _assert_snapshot_equal(tc: unittest.TestCase, res: SimulatedPortfolioTradingResult, snap: dict) -> None:
    current_scalars = (
        res.initial_cash,
        res.final_cash,
        res.total_market_value,
        res.total_equity,
        res.realized_pnl,
        res.unrealized_pnl,
        res.total_return,
        res.total_return_pct,
        res.open_position_count,
        res.order_count,
        res.fill_count,
        res.rejection_count,
        res.audit_record_count,
    )
    tc.assertEqual(current_scalars, snap["scalars"])

    # Tuple identities
    tc.assertIs(res.positions, snap["tuples_identities"]["positions"])
    tc.assertIs(res.pending_orders, snap["tuples_identities"]["pending_orders"])
    tc.assertIs(res.orders, snap["tuples_identities"]["orders"])
    tc.assertIs(res.fills, snap["tuples_identities"]["fills"])
    tc.assertIs(res.rejections, snap["tuples_identities"]["rejections"])
    tc.assertIs(res.audit_log, snap["tuples_identities"]["audit_log"])

    # Positions
    for (p_obj, p_vals), (orig_obj, orig_vals) in zip([(p, (p.symbol, p.quantity, p.average_cost, p.last_price, p.market_value, p.realized_pnl, p.unrealized_pnl)) for p in res.positions], snap["positions"]):
        tc.assertIs(p_obj, orig_obj)
        tc.assertEqual(p_vals, orig_vals)

    # Pending orders
    for (po_obj, po_vals), (orig_obj, orig_vals) in zip([(po, (po.order_id, po.symbol, po.side, po.quantity, po.signal_time, po.created_at, po.strategy, po.reference_price, po.reserved_buy_notional)) for po in res.pending_orders], snap["pending_orders"]):
        tc.assertIs(po_obj, orig_obj)
        tc.assertEqual(po_vals, orig_vals)

    # Orders
    for o, (orig_obj, orig_vals, orig_meta_id, orig_meta_dict) in zip(res.orders, snap["orders"]):
        tc.assertIs(o, orig_obj)
        tc.assertEqual((o.order_id, o.symbol, o.side, o.quantity, o.signal_time, o.created_at, o.strategy), orig_vals)
        tc.assertIs(o.metadata, orig_meta_id)
        if o.metadata is not None:
            tc.assertEqual(dict(o.metadata), orig_meta_dict)

    # Fills
    for (f_obj, f_vals), (orig_obj, orig_vals) in zip([(f, (f.order_id, f.symbol, f.side, f.quantity, f.price, f.filled_at, f.fee, f.tax, f.slippage)) for f in res.fills], snap["fills"]):
        tc.assertIs(f_obj, orig_obj)
        tc.assertEqual(f_vals, orig_vals)

    # Rejections
    for r, (orig_rej_id, orig_cand_id, orig_cand_vals, orig_cand_meta_id, orig_cand_meta_dict, orig_reasons_id, orig_reasons_tuple) in zip(res.rejections, snap["rejections"]):
        tc.assertIs(r, orig_rej_id)
        tc.assertIs(r.candidate_order, orig_cand_id)
        tc.assertEqual((r.candidate_order.order_id, r.candidate_order.symbol, r.candidate_order.side, r.candidate_order.quantity, r.candidate_order.signal_time, r.candidate_order.created_at, r.candidate_order.strategy), orig_cand_vals)
        tc.assertIs(r.candidate_order.metadata, orig_cand_meta_id)
        if r.candidate_order.metadata is not None:
            tc.assertEqual(dict(r.candidate_order.metadata), orig_cand_meta_dict)
        tc.assertIs(r.reasons, orig_reasons_id)
        tc.assertEqual(r.reasons, orig_reasons_tuple)

    # Audit log
    for rec, (orig_rec_id, orig_rec_vals, orig_strat_meta_id, orig_strat_meta_dict, orig_risk_reasons_id, orig_risk_reasons_tuple, orig_guard_meta_id, orig_guard_meta_dict) in zip(res.audit_log, snap["audit_log"]):
        tc.assertIs(rec, orig_rec_id)
        tc.assertEqual((rec.sequence, rec.record_id, rec.event_type, rec.status, rec.order_id, rec.symbol, rec.side, rec.quantity, rec.signal_time, rec.order_created_at, rec.expected_execution_model, rec.fill_time, rec.fill_price, rec.fee, rec.tax, rec.slippage, rec.strategy_name, rec.risk_allowed, rec.error_code, rec.error_message), orig_rec_vals)
        tc.assertIs(rec.strategy_metadata, orig_strat_meta_id)
        tc.assertEqual(dict(rec.strategy_metadata), orig_strat_meta_dict)
        tc.assertIs(rec.risk_rejection_reasons, orig_risk_reasons_id)
        tc.assertEqual(rec.risk_rejection_reasons, orig_risk_reasons_tuple)
        tc.assertIs(rec.guard_metadata, orig_guard_meta_id)
        tc.assertEqual(dict(rec.guard_metadata), orig_guard_meta_dict)


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

        # Pre-export full snapshot
        snap = _snapshot_result(res)

        # Execute export
        target_path = self.temp_dir / "mutation_test.json"
        export_simulated_portfolio_trading_result_json_file(res, target_path)

        # Assert zero mutations on result, scalar fields, identities, metadata
        _assert_snapshot_equal(self, res, snap)

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
