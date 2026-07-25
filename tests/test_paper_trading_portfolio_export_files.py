"""
Unit tests for multi-symbol portfolio trading exporter filesystem helpers.
"""

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
from tw_stock_tool.paper_trading.portfolio_export_files import (
    export_simulated_portfolio_trading_csv_files,
    export_simulated_portfolio_trading_markdown_file,
)
from tw_stock_tool.paper_trading.portfolio_exporters import (
    export_simulated_portfolio_trading_csv_bundle,
    export_simulated_portfolio_trading_markdown,
)
from tw_stock_tool.paper_trading.portfolio_results import (
    SimulatedPortfolioPendingOrderResult,
    SimulatedPortfolioPositionResult,
    SimulatedPortfolioTradingResult,
)


class CustomStrSubclass(str):
    pass


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
        strategy="測試策略",
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
        strategy="測試策略",
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
        reasons=("風控拒絕", "額度不足"),
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
        strategy_name="測試策略",
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


class TestPaperTradingPortfolioExportFiles(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.result = _make_sample_portfolio_result()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_markdown_file_export_delegation_unicode_and_mutation_safety(self) -> None:
        res = self.result

        # Pre-execution full snapshot
        snap = _snapshot_result(res)

        target_path = self.temp_dir / "reports" / "portfolio.md"
        # 1. real Markdown export
        returned_path = export_simulated_portfolio_trading_markdown_file(
            res,
            target_path,
        )

        self.assertTrue(returned_path.is_absolute())
        self.assertEqual(returned_path, target_path.resolve())
        self.assertTrue(returned_path.is_file())

        expected_md = export_simulated_portfolio_trading_markdown(res)
        written_md = returned_path.read_text(encoding="utf-8")
        self.assertEqual(written_md, expected_md)
        self.assertIn("風控拒絕", written_md)
        self.assertIn("額度不足", written_md)
        self.assertIn("測試策略", written_md)

        # Overwrite=False refusal & 2. overwrite=True export
        with self.assertRaises(FileExistsError):
            export_simulated_portfolio_trading_markdown_file(
                res,
                target_path,
                overwrite=False,
            )

        export_simulated_portfolio_trading_markdown_file(
            res,
            target_path,
            overwrite=True,
        )

        # Permission error propagation
        with patch("builtins.open", side_effect=PermissionError("Markdown write permission denied")):
            with self.assertRaises(PermissionError) as cm:
                export_simulated_portfolio_trading_markdown_file(res, target_path, overwrite=True)
            self.assertIn("Markdown write permission denied", str(cm.exception))

        # 3. patched string-exporter delegation export
        mock_md = "# Mocked Markdown"
        with patch(
            "tw_stock_tool.paper_trading.portfolio_export_files.export_simulated_portfolio_trading_markdown",
            return_value=mock_md,
        ) as mock_exporter:
            md_path = self.temp_dir / "delegated.md"
            export_simulated_portfolio_trading_markdown_file(res, md_path)
            mock_exporter.assert_called_once_with(res)
            self.assertEqual(md_path.read_text(encoding="utf-8"), mock_md)

        # Complete mutation safety check after ALL 3 exports
        _assert_snapshot_equal(self, res, snap)

    def test_csv_files_export_overwrite_unicode_and_mutation_safety(self) -> None:
        res = self.result
        snap = _snapshot_result(res)

        out_dir = self.temp_dir / "csv_out"
        out_dir.mkdir(parents=True, exist_ok=True)

        expected_keys = (
            "summary",
            "positions",
            "pending_orders",
            "orders",
            "fills",
            "rejections",
            "trade_log",
        )

        # Pre-create all 7 targets with distinct sentinel contents
        for key in expected_keys:
            sentinel_file = out_dir / f"simulated_portfolio_trading_{key}.csv"
            sentinel_file.write_bytes(f"SENTINEL_{key}".encode("utf-8"))

        # 1. Execute overwrite=True seven-file export
        paths = export_simulated_portfolio_trading_csv_files(
            res,
            out_dir,
            overwrite=True,
        )

        self.assertEqual(tuple(paths.keys()), expected_keys)
        bundle = export_simulated_portfolio_trading_csv_bundle(res)

        for key in expected_keys:
            p = paths[key]
            self.assertTrue(p.is_absolute())
            self.assertEqual(p.parent, out_dir.resolve())
            self.assertEqual(p.name, f"simulated_portfolio_trading_{key}.csv")

            written_text = p.read_text(encoding="utf-8")
            self.assertEqual(written_text, bundle[key])
            self.assertNotEqual(written_text, f"SENTINEL_{key}")

        # Unicode preserved
        self.assertIn("風控拒絕", (out_dir / "simulated_portfolio_trading_rejections.csv").read_text(encoding="utf-8"))
        self.assertIn("測試策略", (out_dir / "simulated_portfolio_trading_trade_log.csv").read_text(encoding="utf-8"))

        # 2. Execute custom basename export
        custom_dir = self.temp_dir / "custom_csv_out"
        custom_paths = export_simulated_portfolio_trading_csv_files(
            res,
            custom_dir,
            basename="custom_portfolio",
        )
        self.assertEqual(custom_paths["summary"].name, "custom_portfolio_summary.csv")

        # Complete mutation safety check after ALL exports
        _assert_snapshot_equal(self, res, snap)

    def test_basename_validation_strict_policy_and_mock_not_called(self) -> None:
        invalid_basenames = [
            Path("sub/name"),
            b"bytes_name",
            12345,
            None,
            CustomStrSubclass("subclass"),
            "",
            "   ",
            ".",
            "..",
            "foo/bar",
            "foo\\bar",
        ]

        out_dir = self.temp_dir / "non_existent_dir"
        unrelated_parent_file = self.temp_dir / "unrelated.txt"
        unrelated_parent_file.write_bytes(b"UNRELATED")

        for b in invalid_basenames:
            with self.subTest(basename=type(b).__name__ if not isinstance(b, str) else b):
                with patch(
                    "tw_stock_tool.paper_trading.portfolio_export_files.export_simulated_portfolio_trading_csv_bundle"
                ) as mock_bundle:
                    with self.assertRaises(ValueError):
                        export_simulated_portfolio_trading_csv_files(
                            self.result,
                            out_dir,
                            basename=b,  # type: ignore
                        )
                    mock_bundle.assert_not_called()

                self.assertFalse(out_dir.exists(), f"Output directory created for invalid basename {b}")
                self.assertEqual(unrelated_parent_file.read_bytes(), b"UNRELATED")

        # Valid basename with leading/trailing spaces accepted without trim
        valid_space_dir = self.temp_dir / "space_dir"
        space_paths = export_simulated_portfolio_trading_csv_files(
            self.result,
            valid_space_dir,
            basename=" report ",
        )
        self.assertEqual(space_paths["summary"].name, " report _summary.csv")

    def test_preflight_check_parameterized_for_all_seven_targets(self) -> None:
        expected_keys = (
            "summary",
            "positions",
            "pending_orders",
            "orders",
            "fills",
            "rejections",
            "trade_log",
        )

        for pre_key in expected_keys:
            with self.subTest(preflight_key=pre_key):
                sub_dir = self.temp_dir / f"preflight_{pre_key}"
                sub_dir.mkdir(parents=True, exist_ok=True)

                existing_target = sub_dir / f"simulated_portfolio_trading_{pre_key}.csv"
                target_sentinel_bytes = b"PRE_EXISTING_TARGET_DATA"
                existing_target.write_bytes(target_sentinel_bytes)

                unrelated_file = sub_dir / "unrelated.txt"
                unrelated_bytes = b"UNRELATED_FILE_DATA"
                unrelated_file.write_bytes(unrelated_bytes)

                with patch(
                    "tw_stock_tool.paper_trading.portfolio_export_files.export_simulated_portfolio_trading_csv_bundle"
                ) as mock_bundle:
                    with self.assertRaises(FileExistsError):
                        export_simulated_portfolio_trading_csv_files(
                            self.result,
                            sub_dir,
                            overwrite=False,
                        )
                    mock_bundle.assert_not_called()

                # Existing target & unrelated file bytes unchanged
                self.assertEqual(existing_target.read_bytes(), target_sentinel_bytes)
                self.assertEqual(unrelated_file.read_bytes(), unrelated_bytes)

                # None of the other 6 target files created
                for other_key in expected_keys:
                    if other_key != pre_key:
                        other_path = sub_dir / f"simulated_portfolio_trading_{other_key}.csv"
                        self.assertFalse(
                            other_path.exists(),
                            f"File {other_path} created despite preflight failure on {pre_key}",
                        )

    def test_internal_bundle_contract_failures(self) -> None:
        out_dir = self.temp_dir / "bundle_fail"
        valid_bundle = export_simulated_portfolio_trading_csv_bundle(self.result)

        # 1. Missing key
        missing_key_bundle = dict(valid_bundle)
        del missing_key_bundle["trade_log"]

        # 2. Extra key
        extra_key_bundle = dict(valid_bundle)
        extra_key_bundle["unexpected"] = "extra,csv"

        # 3. Wrong key order (pending_orders before positions)
        wrong_order_bundle = {
            "summary": valid_bundle["summary"],
            "pending_orders": valid_bundle["pending_orders"],
            "positions": valid_bundle["positions"],
            "orders": valid_bundle["orders"],
            "fills": valid_bundle["fills"],
            "rejections": valid_bundle["rejections"],
            "trade_log": valid_bundle["trade_log"],
        }

        bad_bundles = [missing_key_bundle, extra_key_bundle, wrong_order_bundle]
        for idx, bad_b in enumerate(bad_bundles):
            with self.subTest(bundle_case=idx):
                with patch(
                    "tw_stock_tool.paper_trading.portfolio_export_files.export_simulated_portfolio_trading_csv_bundle",
                    return_value=bad_b,
                ):
                    with self.assertRaises(PaperTradingModelError):
                        export_simulated_portfolio_trading_csv_files(self.result, out_dir)

                if out_dir.exists():
                    self.assertEqual(list(out_dir.glob("*.csv")), [])


if __name__ == "__main__":
    unittest.main()
