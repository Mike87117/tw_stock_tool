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


class TestPaperTradingPortfolioExportFiles(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.result = _make_sample_portfolio_result()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_markdown_file_export_delegation_unicode_and_mutation_safety(self) -> None:
        res = self.result

        # Snapshots
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

        target_path = self.temp_dir / "reports" / "portfolio.md"
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

        # Overwrite=False refusal & Overwrite=True replacement
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

        # Delegated exporter string function called once with exact identity
        mock_md = "# Mocked Markdown"
        with patch(
            "tw_stock_tool.paper_trading.portfolio_export_files.export_simulated_portfolio_trading_markdown",
            return_value=mock_md,
        ) as mock_exporter:
            md_path = self.temp_dir / "delegated.md"
            export_simulated_portfolio_trading_markdown_file(res, md_path)
            mock_exporter.assert_called_once_with(res)
            self.assertEqual(md_path.read_text(encoding="utf-8"), mock_md)

        # Source mutation safety
        self.assertIs(res.positions, orig_positions_tuple)
        self.assertIs(res.pending_orders, orig_pending_tuple)
        self.assertIs(res.orders, orig_orders_tuple)
        self.assertIs(res.fills, orig_fills_tuple)
        self.assertIs(res.rejections, orig_rejections_tuple)
        self.assertIs(res.audit_log, orig_audit_tuple)
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

    def test_csv_files_export_overwrite_unicode_and_mutation_safety(self) -> None:
        res = self.result
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

        # Execute overwrite=True
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
