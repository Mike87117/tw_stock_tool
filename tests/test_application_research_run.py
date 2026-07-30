import argparse
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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

        with self.assertRaises(TypeError):
            ScanRunRequest(self.symbols, None, ScanConfig(), "out", sheet_by_signal=1)
        with self.assertRaises(TypeError):
            BacktestRunRequest(self.symbols[0], "ma_cross", "out", auto_adjust=BoolInt(1))

        strategy = {"short_window": 3, "nested": {"value": 1}}
        request = BacktestRunRequest(self.symbols[0], "ma_cross", Path("out"), strategy_parameters=strategy)
        strategy["short_window"] = 99
        strategy["nested"]["value"] = 99
        self.assertEqual(request.strategy_parameters["short_window"], 3)
        self.assertEqual(request.strategy_parameters["nested"]["value"], 1)
        with self.assertRaises(TypeError):
            request.strategy_parameters["short_window"] = 4


class ApplicationServiceTests(unittest.TestCase):
    def setUp(self):
        self.symbols = (SymbolRequest("2330", "2330.TW"), SymbolRequest("0050", "0050.TW"))
        self.result = object()

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

    def test_wrong_request_and_namespace_are_rejected_without_output(self):
        cases = ((run_scan, DailyRunRequest(self.symbols, None, DailyPipelineConfig(), "out")),
                 (run_daily, ScanRunRequest(self.symbols, None, ScanConfig(), "out")),
                 (run_backtest, argparse.Namespace()))
        for function, request in cases:
            with self.subTest(function=function.__name__):
                with self.assertRaises(TypeError):
                    function(request)

    def test_workflow_exceptions_propagate_and_application_is_quiet(self):
        request = ScanRunRequest(self.symbols, None, ScanConfig(), "out")
        error = RuntimeError("workflow")
        with patch("tw_stock_tool.application.research_run.run_scan_research", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "workflow") as raised:
                with self.assertLogs(level="CRITICAL") if False else unittest.mock.patch("sys.stdout") as stdout:
                    run_scan(request)
        self.assertIs(raised.exception, error)
        self.assertEqual(stdout.write.call_count, 0)


if __name__ == "__main__":
    unittest.main()
