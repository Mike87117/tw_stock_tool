import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

import tw_stock_tool.application as application_module
from tw_stock_tool.application import research_run as application_research_run
from tw_stock_tool.application import symbol_resolution
from tw_stock_tool.analysis.scanner import ScanConfig
from tw_stock_tool.application import (
    BacktestRunRequest,
    DailyRunRequest,
    ScanRunRequest,
    SymbolRequest,
    run_backtest,
    run_daily,
    run_scan,
)
from tw_stock_tool.reports.daily_pipeline import DailyPipelineConfig


class ApplicationExportTests(unittest.TestCase):
    def test_exact_exports_and_research_run_identity(self):
        expected = [
            "SymbolRequest",
            "ScanRunRequest",
            "DailyRunRequest",
            "BacktestRunRequest",
            "run_scan",
            "run_daily",
            "run_backtest",
        ]
        self.assertEqual(application_module.__all__, expected)
        for name in expected:
            with self.subTest(name=name):
                self.assertIs(
                    getattr(application_module, name),
                    getattr(application_research_run, name),
                )

    def test_import_does_not_load_cli_or_gui_modules(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys\n"
                    "import tw_stock_tool.application\n"
                    "for name in sys.modules:\n"
                    "    if name.startswith(('tw_stock_tool.cli', 'tw_stock_tool.gui')):\n"
                    "        raise AssertionError(name)\n"
                ),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(completed.stderr, "")


class SymbolResolutionTests(unittest.TestCase):
    @staticmethod
    def _catalog(*rows: tuple[str, str, str, str]) -> pd.DataFrame:
        return pd.DataFrame(rows, columns=["Stock", "Name", "Market", "Type"])

    def test_explicit_suffixes_and_market_hints_bypass_catalog(self):
        with patch.object(symbol_resolution, "load_stock_market_catalog") as load:
            cases = (
                ("2330.TW", "2330.TW"),
                ("6488.TWO", "6488.TWO"),
                ("2330.tw", "2330.TW"),
                ("6488.two", "6488.TWO"),
            )
            for requested, canonical in cases:
                with self.subTest(requested=requested):
                    result = symbol_resolution.resolve_symbol_request(requested)
                    self.assertEqual((result.requested_symbol, result.canonical_symbol), (requested, canonical))
            self.assertEqual(symbol_resolution.resolve_symbol_request("2330", market_hint="twse").canonical_symbol, "2330.TW")
            self.assertEqual(symbol_resolution.resolve_symbol_request("6488", market_hint="tpex").canonical_symbol, "6488.TWO")
        load.assert_not_called()

    def test_all_market_resolution_preserves_order_and_loads_once(self):
        catalog = self._catalog(
            ("6488", "TPEX", "TPEX", "stock"),
            ("2330", "TSMC", "TWSE", "stock"),
            ("8069", "E Ink", "TPEX", "stock"),
        )
        with patch.object(symbol_resolution, "load_stock_market_catalog", return_value=catalog) as load:
            result = symbol_resolution.resolve_symbol_requests(("8069", "2330", "6488"))
        self.assertEqual(result, (
            SymbolRequest("8069", "8069.TWO"),
            SymbolRequest("2330", "2330.TW"),
            SymbolRequest("6488", "6488.TWO"),
        ))
        load.assert_called_once_with(market="all", allow_partial=False)

    def test_mixed_batch_and_many_bare_symbols_load_catalog_once(self):
        catalog = self._catalog(("2330", "TSMC", "TWSE", "stock"), ("6488", "", "TPEX", "stock"), ("0050", "", "TWSE", "stock"))
        with patch.object(symbol_resolution, "load_stock_market_catalog", return_value=catalog) as load:
            result = symbol_resolution.resolve_symbol_requests(("0050.TW", "2330", "6488"))
        self.assertEqual(tuple(item.canonical_symbol for item in result), ("0050.TW", "2330.TW", "6488.TWO"))
        self.assertEqual(load.call_count, 1)

    def test_supplied_catalog_is_reused_without_mutation_or_writes(self):
        catalog = self._catalog(("2330", "TSMC", "TWSE", "stock"))
        original = catalog.copy(deep=True)
        with patch.object(symbol_resolution, "load_stock_market_catalog") as load:
            with patch("tw_stock_tool.data.stock_list_updater.update_stock_list") as update:
                result = symbol_resolution.resolve_symbol_request("2330", catalog=catalog)
        self.assertEqual(result, SymbolRequest("2330", "2330.TW"))
        pd.testing.assert_frame_equal(catalog, original)
        load.assert_not_called()
        update.assert_not_called()

    def test_market_membership_and_ambiguity_fail_closed(self):
        cases = (
            (self._catalog(("2330", "", "TWSE", "stock"), ("2330", "", "TPEX", "stock")), "Ambiguous"),
            (self._catalog(("2330", "", "OTC", "stock")), "Unknown market"),
            (self._catalog(("2330", "", "TWSE", "stock")), None),
        )
        for catalog, expected in cases:
            with self.subTest(expected=expected):
                if expected is None:
                    self.assertEqual(symbol_resolution.resolve_symbol_request("2330", catalog=catalog).canonical_symbol, "2330.TW")
                else:
                    with self.assertRaisesRegex(symbol_resolution.SymbolResolutionError, expected):
                        symbol_resolution.resolve_symbol_request("2330", catalog=catalog)

    def test_unrequested_ambiguity_does_not_block_selected_symbol(self):
        catalog = self._catalog(
            ("2330", "", "TWSE", "stock"),
            ("6488", "", "TWSE", "stock"),
            ("6488", "", "TPEX", "stock"),
        )
        result = symbol_resolution.resolve_symbol_request("2330", catalog=catalog)
        self.assertEqual(result.canonical_symbol, "2330.TW")

    def test_zero_match_malformed_suffixes_and_duplicates_fail(self):
        catalog = self._catalog(("2330", "", "TWSE", "stock"))
        with self.assertRaisesRegex(symbol_resolution.SymbolResolutionError, "Unknown symbol"):
            symbol_resolution.resolve_symbol_request("9999", catalog=catalog)
        for value in ("2330.US", "2330.TWO.TW", ".TW", "2330."):
            with self.subTest(value=value):
                with self.assertRaises(symbol_resolution.SymbolResolutionError):
                    symbol_resolution.resolve_symbol_request(value)
        with self.assertRaisesRegex(symbol_resolution.SymbolResolutionError, "Duplicate requested"):
            symbol_resolution.resolve_symbol_requests(("2330", "2330"), market_hint="twse")
        with self.assertRaisesRegex(symbol_resolution.SymbolResolutionError, "Duplicate canonical"):
            symbol_resolution.resolve_symbol_requests(("2330", "2330.TW"), catalog=catalog)

    def test_duplicate_rows_in_one_market_resolve_and_input_is_preserved(self):
        catalog = self._catalog(
            ("2330", "first", "TWSE", "stock"),
            ("2330", "second", "TWSE", "stock"),
        )
        result = symbol_resolution.resolve_symbol_request("2330", catalog=catalog)
        self.assertEqual(result, SymbolRequest("2330", "2330.TW"))
        self.assertEqual(symbol_resolution.resolve_symbol_request("2330.tw").requested_symbol, "2330.tw")

    def test_resolver_validates_inputs_and_catalog_shape(self):
        for requested in ([], ["2330"], ("",), (" 2330",), ("2330", 2330)):
            with self.subTest(requested=requested):
                with self.assertRaises(symbol_resolution.SymbolResolutionError):
                    symbol_resolution.resolve_symbol_requests(requested)  # type: ignore[arg-type]
        with self.assertRaises(symbol_resolution.SymbolResolutionError):
            symbol_resolution.resolve_symbol_request("2330", market_hint="TWSE")  # type: ignore[arg-type]
        with self.assertRaises(symbol_resolution.SymbolResolutionError):
            symbol_resolution.resolve_symbol_request("2330", allow_partial_catalog=1)  # type: ignore[arg-type]
        with self.assertRaisesRegex(symbol_resolution.SymbolResolutionError, "missing required"):
            symbol_resolution.resolve_symbol_request("2330", catalog=pd.DataFrame({"Stock": ["2330"]}))


class ApplicationRequestTests(unittest.TestCase):
    def setUp(self):
        self.symbols = (SymbolRequest("2330", "2330.TW"), SymbolRequest("0050", "0050.TW"))

    def test_models_are_frozen_and_slotted(self):
        for model in (SymbolRequest, ScanRunRequest, DailyRunRequest, BacktestRunRequest):
            self.assertTrue(model.__dataclass_params__.frozen)
            self.assertIn("__slots__", model.__dict__)

    def test_clean_string_and_symbol_structure(self):
        for values in (("", "2330.TW"), (" 2330", "2330.TW"), ("2330", "2330.TW ")):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    SymbolRequest(*values)
        with self.assertRaises(TypeError):
            SymbolRequest(2330, "2330.TW")
        with self.assertRaises(TypeError):
            ScanRunRequest((), None, ScanConfig(), "out")
        with self.assertRaises(TypeError):
            DailyRunRequest((), None, DailyPipelineConfig(), "out")

    def test_duplicate_symbols_and_wrong_config_types(self):
        duplicate_requested = (SymbolRequest("2330", "2330.TW"), SymbolRequest("2330", "0050.TW"))
        duplicate_canonical = (SymbolRequest("2330", "2330.TW"), SymbolRequest("0050", "2330.TW"))
        for symbols in (duplicate_requested, duplicate_canonical):
            with self.subTest(symbols=symbols):
                with self.assertRaises(ValueError):
                    ScanRunRequest(symbols, None, ScanConfig(), "out")
        with self.assertRaises(TypeError):
            ScanRunRequest(self.symbols, None, DailyPipelineConfig(), "out")
        with self.assertRaises(TypeError):
            DailyRunRequest(self.symbols, None, ScanConfig(), "out")

    def test_exact_bool_and_backtest_mapping_snapshot(self):
        class BoolInt(int):
            pass

        factories = (
            lambda value: ScanRunRequest(self.symbols, None, ScanConfig(), "out", sheet_by_signal=value),
            lambda value: ScanRunRequest(self.symbols, None, ScanConfig(), "out", log_errors=value),
            lambda value: DailyRunRequest(self.symbols, None, DailyPipelineConfig(), "out", json_overwrite=value),
            lambda value: BacktestRunRequest(self.symbols[0], "ma_cross", "out", auto_adjust=value),
            lambda value: BacktestRunRequest(self.symbols[0], "ma_cross", "out", force_refresh=value),
        )
        for factory in factories:
            for value in (1, BoolInt(1)):
                with self.subTest(factory=factory, value=value):
                    with self.assertRaises(TypeError):
                        factory(value)

        strategy = {"short_window": 3, "nested": {"value": 1}}
        request = BacktestRunRequest(self.symbols[0], "ma_cross", Path("out"), strategy_parameters=strategy)
        strategy["short_window"] = 99
        strategy["nested"]["value"] = 99
        self.assertEqual(request.strategy_parameters["short_window"], 3)
        self.assertEqual(request.strategy_parameters["nested"]["value"], 1)
        with self.assertRaises(TypeError):
            request.strategy_parameters["short_window"] = 4

    def test_backtest_mappings_and_clean_strings_are_validated(self):
        for name in ("strategy_parameters", "backtest_parameters"):
            with self.subTest(name=name):
                with self.assertRaises(TypeError):
                    BacktestRunRequest(
                        self.symbols[0],
                        "ma_cross",
                        "out",
                        **{name: [("value", 1)]},
                    )
        for name in ("strategy", "period", "interval"):
            for value in ("", " dirty", "dirty "):
                kwargs = {"strategy": "ma_cross", "output_dir": "out", name: value}
                with self.subTest(name=name, value=value):
                    with self.assertRaises(ValueError):
                        BacktestRunRequest(self.symbols[0], **kwargs)

    def test_output_and_optional_paths_are_validated(self):
        invalid_requests = (
            lambda: ScanRunRequest(self.symbols, None, ScanConfig(), ""),
            lambda: DailyRunRequest(self.symbols, None, DailyPipelineConfig(), object()),
            lambda: BacktestRunRequest(self.symbols[0], "ma_cross", " "),
            lambda: ScanRunRequest(self.symbols, None, ScanConfig(), "out", manifest_path=""),
            lambda: DailyRunRequest(self.symbols, None, DailyPipelineConfig(), "out", markdown_path=""),
            lambda: DailyRunRequest(self.symbols, None, DailyPipelineConfig(), "out", json_path=b"json"),
            lambda: DailyRunRequest(self.symbols, None, DailyPipelineConfig(), "out", manifest_path=" "),
            lambda: BacktestRunRequest(self.symbols[0], "ma_cross", "out", markdown_path=""),
            lambda: BacktestRunRequest(self.symbols[0], "ma_cross", "out", excel_path=b"xlsx"),
            lambda: BacktestRunRequest(self.symbols[0], "ma_cross", "out", manifest_path=" "),
        )
        for factory in invalid_requests:
            with self.subTest(factory=factory):
                with self.assertRaises((TypeError, ValueError)):
                    factory()


class ApplicationServiceTests(unittest.TestCase):
    def setUp(self):
        self.symbols = (SymbolRequest("2330", "2330.TW"), SymbolRequest("0050", "0050.TW"))
        self.result = object()
        self.invocation_boundaries = []
        for target in (
            "tw_stock_tool.data.stock_list_updater.update_stock_list",
            "tw_stock_tool.data.stock_list_updater.fetch_twse_stock_list",
            "tw_stock_tool.data.stock_list_updater.fetch_tpex_stock_list",
            "requests.get",
        ):
            patcher = patch(target)
            self.addCleanup(patcher.stop)
            self.invocation_boundaries.append(patcher.start())

    def assert_no_catalog_or_network_invocation(self):
        for boundary in self.invocation_boundaries:
            boundary.assert_not_called()

    def test_scan_delegates_once_and_preserves_identity(self):
        request = ScanRunRequest(self.symbols, "tw50", ScanConfig(), "out", "manifest.json", True, True)
        progress = Mock()
        loader = Mock()
        with patch("tw_stock_tool.application.research_run.run_scan_research", return_value=self.result) as service:
            result = run_scan(request, progress_callback=progress, market_data_loader=loader)
        self.assertIs(result, self.result)
        service.assert_called_once_with(
            (("2330", "2330.TW"), ("0050", "0050.TW")),
            universe="tw50", config=request.config, output_dir="out", manifest_path="manifest.json",
            sheet_by_signal=True, log_errors=True, progress_callback=progress, market_data_loader=loader,
        )
        self.assert_no_catalog_or_network_invocation()

    def test_daily_delegates_once_and_preserves_identity(self):
        request = DailyRunRequest(self.symbols, None, DailyPipelineConfig(), "out", "md", "json", "manifest", True)
        status = Mock()
        loader = Mock()
        with patch("tw_stock_tool.application.research_run.run_daily_report_research", return_value=self.result) as service:
            result = run_daily(request, status_callback=status, market_data_loader=loader)
        self.assertIs(result, self.result)
        service.assert_called_once_with(
            (("2330", "2330.TW"), ("0050", "0050.TW")),
            universe=None, config=request.config, output_dir="out", markdown_path="md", json_path="json",
            manifest_path="manifest", json_overwrite=True, status_callback=status, market_data_loader=loader,
        )
        self.assert_no_catalog_or_network_invocation()

    def test_backtest_delegates_once_and_preserves_identity(self):
        request = BacktestRunRequest(
            self.symbols[0], "ma_cross", "out", period="6mo", interval="1wk", auto_adjust=True,
            force_refresh=True, strategy_parameters={"short_window": 3}, backtest_parameters={"fee_rate": 0.1},
            markdown_path="md", excel_path="xlsx", manifest_path="manifest",
        )
        stage = Mock()
        loader = Mock()
        with patch("tw_stock_tool.application.research_run.run_backtest_research", return_value=self.result) as service:
            result = run_backtest(request, stage_callback=stage, market_data_loader=loader)
        self.assertIs(result, self.result)
        service.assert_called_once_with(
            ("2330", "2330.TW"), strategy="ma_cross", period="6mo", interval="1wk", auto_adjust=True,
            force_refresh=True, strategy_parameters=request.strategy_parameters,
            backtest_parameters=request.backtest_parameters, output_dir="out", markdown_path="md",
            excel_path="xlsx", manifest_path="manifest", stage_callback=stage, market_data_loader=loader,
        )
        self.assert_no_catalog_or_network_invocation()

    def test_wrong_request_and_namespace_are_rejected_without_output(self):
        cases = ((run_scan, DailyRunRequest(self.symbols, None, DailyPipelineConfig(), "out")),
                 (run_daily, ScanRunRequest(self.symbols, None, ScanConfig(), "out")),
                 (run_backtest, argparse.Namespace()))
        for function, request in cases:
            with self.subTest(function=function.__name__):
                with self.assertRaises(TypeError):
                    function(request)

    def test_workflow_exception_identity_for_all_services(self):
        cases = (
            (run_scan, ScanRunRequest(self.symbols, None, ScanConfig(), "out"), "run_scan_research"),
            (run_daily, DailyRunRequest(self.symbols, None, DailyPipelineConfig(), "out"), "run_daily_report_research"),
            (run_backtest, BacktestRunRequest(self.symbols[0], "ma_cross", "out"), "run_backtest_research"),
        )
        for function, request, service_name in cases:
            error = RuntimeError(service_name)
            with self.subTest(function=function.__name__):
                with patch.object(application_research_run, service_name, side_effect=error):
                    with self.assertRaises(RuntimeError) as raised:
                        function(request)
                self.assertIs(raised.exception, error)
        self.assert_no_catalog_or_network_invocation()

    def test_all_services_are_quiet_when_delegated(self):
        cases = (
            (run_scan, ScanRunRequest(self.symbols, None, ScanConfig(), "out"), "run_scan_research"),
            (run_daily, DailyRunRequest(self.symbols, None, DailyPipelineConfig(), "out"), "run_daily_report_research"),
            (run_backtest, BacktestRunRequest(self.symbols[0], "ma_cross", "out"), "run_backtest_research"),
        )
        for function, request, service_name in cases:
            stdout = io.StringIO()
            stderr = io.StringIO()
            with self.subTest(function=function.__name__):
                with patch.object(application_research_run, service_name, return_value=self.result):
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        function(request)
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(stderr.getvalue(), "")
        self.assert_no_catalog_or_network_invocation()


if __name__ == "__main__":
    unittest.main()
