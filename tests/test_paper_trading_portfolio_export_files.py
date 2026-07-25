"""
Unit tests for multi-symbol portfolio trading exporter filesystem helpers.
"""

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tw_stock_tool.paper_trading.models import PaperTradingModelError
from tw_stock_tool.paper_trading.portfolio_export_files import (
    export_simulated_portfolio_trading_csv_files,
    export_simulated_portfolio_trading_markdown_file,
)
from tw_stock_tool.paper_trading.portfolio_exporters import (
    export_simulated_portfolio_trading_csv_bundle,
    export_simulated_portfolio_trading_markdown,
)
from tw_stock_tool.paper_trading.portfolio_results import (
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
    return SimulatedPortfolioTradingResult(
        initial_cash=1000000.0,
        final_cash=1000000.0,
        total_market_value=550000.0,
        total_equity=1550000.0,
        realized_pnl=10000.0,
        unrealized_pnl=50000.0,
        total_return=550000.0,
        total_return_pct=0.55,
        open_position_count=1,
        order_count=0,
        fill_count=0,
        rejection_count=0,
        audit_record_count=0,
        positions=(pos1,),
        pending_orders=(),
        orders=(),
        fills=(),
        rejections=(),
        audit_log=(),
    )


class TestPaperTradingPortfolioExportFiles(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.result = _make_sample_portfolio_result()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_markdown_file_export_success_and_overwrite(self) -> None:
        target_path = self.temp_dir / "reports" / "portfolio.md"
        returned_path = export_simulated_portfolio_trading_markdown_file(
            self.result,
            target_path,
        )

        self.assertEqual(returned_path, target_path.resolve())
        self.assertTrue(returned_path.is_file())

        expected_md = export_simulated_portfolio_trading_markdown(self.result)
        written_md = returned_path.read_text(encoding="utf-8")
        self.assertEqual(written_md, expected_md)

        with self.assertRaises(FileExistsError):
            export_simulated_portfolio_trading_markdown_file(
                self.result,
                target_path,
                overwrite=False,
            )

        export_simulated_portfolio_trading_markdown_file(
            self.result,
            target_path,
            overwrite=True,
        )

    def test_csv_files_export_success_default_and_custom_basename(self) -> None:
        out_dir = self.temp_dir / "csv_out"
        paths = export_simulated_portfolio_trading_csv_files(self.result, out_dir)

        expected_keys = [
            "summary",
            "positions",
            "pending_orders",
            "orders",
            "fills",
            "rejections",
            "trade_log",
        ]
        self.assertEqual(list(paths.keys()), expected_keys)

        bundle = export_simulated_portfolio_trading_csv_bundle(self.result)
        for key in expected_keys:
            p = paths[key]
            self.assertTrue(p.is_file())
            self.assertEqual(p.parent, out_dir.resolve())
            self.assertEqual(p.name, f"simulated_portfolio_trading_{key}.csv")
            self.assertEqual(p.read_text(encoding="utf-8"), bundle[key])

        # Custom basename test
        custom_out_dir = self.temp_dir / "csv_custom"
        custom_paths = export_simulated_portfolio_trading_csv_files(
            self.result,
            custom_out_dir,
            basename="custom_portfolio",
        )
        self.assertEqual(custom_paths["summary"].name, "custom_portfolio_summary.csv")

    def test_basename_validation_strict_policy(self) -> None:
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

        for b in invalid_basenames:
            with self.subTest(basename=type(b).__name__ if not isinstance(b, str) else b):
                with self.assertRaises(ValueError):
                    export_simulated_portfolio_trading_csv_files(
                        self.result,
                        out_dir,
                        basename=b,  # type: ignore
                    )
                self.assertFalse(out_dir.exists(), f"Output directory was created for invalid basename {b}")

        # Valid basename with leading/trailing spaces must be accepted without trim
        valid_space_dir = self.temp_dir / "space_dir"
        space_paths = export_simulated_portfolio_trading_csv_files(
            self.result,
            valid_space_dir,
            basename=" report ",
        )
        self.assertEqual(space_paths["summary"].name, " report _summary.csv")

    def test_preflight_check_parameterized_for_all_seven_targets(self) -> None:
        expected_keys = [
            "summary",
            "positions",
            "pending_orders",
            "orders",
            "fills",
            "rejections",
            "trade_log",
        ]

        for pre_key in expected_keys:
            with self.subTest(preflight_key=pre_key):
                sub_dir = self.temp_dir / f"preflight_{pre_key}"
                sub_dir.mkdir(parents=True, exist_ok=True)

                existing_target = sub_dir / f"simulated_portfolio_trading_{pre_key}.csv"
                sentinel_bytes = b"PRE_EXISTING_DATA"
                existing_target.write_bytes(sentinel_bytes)

                with self.assertRaises(FileExistsError):
                    export_simulated_portfolio_trading_csv_files(
                        self.result,
                        sub_dir,
                        overwrite=False,
                    )

                # Existing target file content must remain unchanged
                self.assertEqual(existing_target.read_bytes(), sentinel_bytes)

                # None of the other 6 target files should exist
                for other_key in expected_keys:
                    if other_key != pre_key:
                        other_path = sub_dir / f"simulated_portfolio_trading_{other_key}.csv"
                        self.assertFalse(
                            other_path.exists(),
                            f"File {other_path} was created despite preflight failure on {pre_key}",
                        )

    def test_internal_bundle_failure_raises_model_error(self) -> None:
        out_dir = self.temp_dir / "bundle_fail"
        bad_bundle = {"summary": "csv", "positions": "csv"}  # Missing 5 keys

        with patch(
            "tw_stock_tool.paper_trading.portfolio_export_files.export_simulated_portfolio_trading_csv_bundle",
            return_value=bad_bundle,
        ):
            with self.assertRaises(PaperTradingModelError):
                export_simulated_portfolio_trading_csv_files(self.result, out_dir)

        # Output directory should have no CSV files written
        if out_dir.exists():
            self.assertEqual(list(out_dir.glob("*.csv")), [])

    def test_permission_error_propagation(self) -> None:
        out_dir = self.temp_dir / "perm_dir"

        with patch("pathlib.Path.mkdir", side_effect=PermissionError("Permission denied")):
            with self.assertRaises(PermissionError):
                export_simulated_portfolio_trading_csv_files(self.result, out_dir)


if __name__ == "__main__":
    unittest.main()
