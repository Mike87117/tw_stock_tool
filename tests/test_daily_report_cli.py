from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tw_stock_tool.application.research_run import DailyRunRequest, SymbolRequest
from tw_stock_tool.cli import daily_report_cli
from tw_stock_tool.cli.daily_report_cli import _parse_args, main
from tw_stock_tool.research_run.daily import DailyReportResearchRunError
from tw_stock_tool.research_run.models import ArtifactReference


def _result(*, json: bool = True, excel: bool = True):
    artifacts = [ArtifactReference("daily_report_markdown", "reports/daily_report.md", "text/markdown", None)]
    if json:
        artifacts.append(ArtifactReference("daily_report_json", "reports/daily_report.json", "application/json", 1))
    if excel:
        artifacts.append(ArtifactReference("daily_report_excel", "reports/daily_report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", None))
    return SimpleNamespace(generated_artifacts=tuple(artifacts), domain_result=SimpleNamespace())


class TestDailyReportCli(unittest.TestCase):
    def setUp(self) -> None:
        self.symbols = (SymbolRequest("2330", "2330.TW"),)

    def _args(self, extra: list[str] | None = None):
        return _parse_args(["--stocks", "2330", *(extra or [])])

    def test_parse_args_manifest_default_and_custom(self):
        self.assertIsNone(_parse_args([]).manifest_path)
        self.assertEqual(_parse_args(["--manifest-path", "custom/daily.json"]).manifest_path, "custom/daily.json")

    def test_parser_defaults_custom_values_and_signal_tuple(self):
        args = _parse_args([])
        self.assertIsNone(args.stocks)
        self.assertEqual(args.stock_market, "all")
        self.assertEqual(args.output_dir, "output")
        self.assertIsNone(args.output_md)
        self.assertIsNone(args.output_json)
        self.assertIsNone(args.manifest_path)
        self.assertFalse(args.overwrite)
        custom = _parse_args([
            "--stocks", "2330", "2317", "--output-md", "test.md",
            "--manifest-path", "manifest.json",
        ])
        self.assertEqual(custom.stocks, ["2330", "2317"])
        self.assertEqual(custom.output_md, "test.md")
        self.assertEqual(custom.manifest_path, "manifest.json")
        config = daily_report_cli._pipeline_config_from_args(
            _parse_args(["--signals", "BUY", "WATCH", "--output-excel", "daily.xlsx"])
        )
        self.assertEqual(config.signals, ("BUY", "WATCH"))
        self.assertEqual(config.output_excel, "daily.xlsx")

    def test_custom_output_directory_and_excel_none_empty_custom_values(self):
        for extra, expected in (
            (["--output-dir", "reports"], None),
            (["--output-dir", "reports", "--output-excel"], ""),
            (["--output-dir", "reports", "--output-excel", "daily.xlsx"], "daily.xlsx"),
        ):
            with self.subTest(extra=extra):
                args = self._args(extra)
                with patch.object(daily_report_cli, "collect_symbol_requests", return_value=self.symbols):
                    with patch.object(daily_report_cli, "run_daily", return_value=_result()) as run:
                        with patch.object(daily_report_cli, "_parse_args", return_value=args):
                            with redirect_stdout(StringIO()):
                                self.assertIsNone(main())
                request = run.call_args.args[0]
                self.assertEqual(request.output_dir, "reports")
                self.assertEqual(request.config.output_excel, expected)

    def test_application_owns_all_report_writes_and_legacy_boundaries_are_unused(self):
        args = self._args(["--output-md", "--output-json"])
        output = StringIO()
        with patch.object(daily_report_cli, "collect_symbol_requests", return_value=self.symbols):
            with patch.object(daily_report_cli, "run_daily", return_value=_result()) as run:
                with patch.object(daily_report_cli, "collect_stock_ids") as legacy_collect:
                    with patch.object(daily_report_cli, "run_daily_research_pipeline") as legacy_pipeline:
                        with patch.object(daily_report_cli, "export_daily_report_json_file") as legacy_export:
                            with patch("builtins.open") as open_mock:
                                with patch.object(Path, "mkdir") as mkdir_mock:
                                    with patch.object(daily_report_cli, "_parse_args", return_value=args):
                                        with redirect_stdout(output):
                                            self.assertIsNone(main())
        run.assert_called_once()
        legacy_collect.assert_not_called()
        legacy_pipeline.assert_not_called()
        legacy_export.assert_not_called()
        open_mock.assert_not_called()
        mkdir_mock.assert_not_called()

    def test_markdown_application_failure_returns_one(self):
        error = DailyReportResearchRunError("markdown_export: locked")
        error.__cause__ = PermissionError("locked")
        output = StringIO()
        with patch.object(daily_report_cli, "collect_symbol_requests", return_value=self.symbols):
            with patch.object(daily_report_cli, "run_daily", side_effect=error):
                with patch.object(daily_report_cli, "_parse_args", return_value=self._args()):
                    with redirect_stdout(output):
                        self.assertEqual(main(), 1)
        self.assertIn("Error: markdown_export: locked", output.getvalue())
        self.assertNotIn("Process completed successfully", output.getvalue())

    def test_invalid_numeric_matrix_and_macd_validation(self):
        for argv in (
            ["--validate-top", "-1"],
            ["--validation-initial-capital", "0"],
            ["--validation-fee-rate", "-0.1"],
            ["--validation-tax-rate", "nan"],
            ["--validation-position-size", "1.1"],
            ["--walk-forward-train-days", "0"],
            ["--walk-forward-test-days", "0"],
            ["--walk-forward-step-days", "0"],
        ):
            with self.subTest(argv=argv):
                with self.assertRaises(SystemExit) as raised:
                    _parse_args(argv)
                self.assertEqual(raised.exception.code, 2)
        args = _parse_args(["--validate-top", "1", "--validation-strategy", "macd"])
        self.assertEqual(args.validation_strategy, "macd")
    def test_main_builds_exact_request_and_calls_service_once(self):
        args = self._args(["--stock-market", "twse", "--output-md", "custom/report.md", "--output-json", "custom/report.json", "--output-excel", "daily.xlsx", "--overwrite", "--manifest-path", "custom/manifest.json"])
        with patch.object(daily_report_cli, "collect_symbol_requests", return_value=self.symbols):
            with patch.object(daily_report_cli, "run_daily", return_value=_result()) as run:
                with patch.object(daily_report_cli, "_parse_args", return_value=args):
                    with redirect_stdout(StringIO()):
                        self.assertIsNone(main())
        run.assert_called_once()
        request = run.call_args.args[0]
        self.assertIsInstance(request, DailyRunRequest)
        self.assertEqual(request.symbols, self.symbols)
        self.assertEqual(request.universe, "twse")
        self.assertEqual(request.output_dir, "output")
        self.assertEqual(request.markdown_path, "custom/report.md")
        self.assertEqual(request.json_path, "custom/report.json")
        self.assertEqual(request.manifest_path, "custom/manifest.json")
        self.assertTrue(request.json_overwrite)
        self.assertEqual(request.config.output_excel, "daily.xlsx")
        self.assertIs(run.call_args.kwargs["status_callback"], print)

    def test_default_and_empty_markdown_json_paths(self):
        cases = [
            ([], None, None),
            (["--output-md"], None, None),
            (["--output-md", "custom.md", "--output-json"], "custom.md", Path("output/daily_report.json")),
            (["--output-json", "custom.json"], None, "custom.json"),
        ]
        for extra, expected_md, expected_json in cases:
            with self.subTest(extra=extra):
                with patch.object(daily_report_cli, "collect_symbol_requests", return_value=self.symbols):
                    with patch.object(daily_report_cli, "run_daily", return_value=_result(json=expected_json is not None)) as run:
                        with patch.object(daily_report_cli, "_parse_args", return_value=self._args(extra)):
                            with redirect_stdout(StringIO()):
                                self.assertIsNone(main())
                request = run.call_args.args[0]
                self.assertEqual(request.markdown_path, expected_md)
                self.assertEqual(request.json_path, expected_json)

    def test_success_prints_markdown_and_json_but_no_new_excel_line(self):
        output = StringIO()
        with patch.object(daily_report_cli, "collect_symbol_requests", return_value=self.symbols):
            with patch.object(daily_report_cli, "run_daily", return_value=_result()):
                with patch.object(daily_report_cli, "_parse_args", return_value=self._args(["--output-json"])):
                    with redirect_stdout(output):
                        self.assertIsNone(main())
        text = output.getvalue()
        self.assertIn("Markdown report exported to reports/daily_report.md", text)
        self.assertIn("JSON artifact exported to reports/daily_report.json", text)
        self.assertIn("Process completed successfully.", text)
        self.assertNotIn("Excel report:", text)

    def test_no_input_is_rejected_before_service_call(self):
        output = StringIO()
        with patch.object(daily_report_cli, "collect_symbol_requests", side_effect=ValueError("No stock ids provided. Use --stocks, --file, or --auto-stock-list.")):
            with patch.object(daily_report_cli, "run_daily") as run:
                with patch.object(daily_report_cli, "_parse_args", return_value=_parse_args([])):
                    with redirect_stdout(output):
                        self.assertEqual(main(), 1)
        run.assert_not_called()
        self.assertIn("No stock ids provided", output.getvalue())

    def test_nested_file_exists_error_preserves_overwrite_guidance(self):
        original = FileExistsError("File already exists: report.json")
        error = DailyReportResearchRunError("json_export: File already exists: report.json")
        error.__cause__ = original
        output = StringIO()
        with patch.object(daily_report_cli, "collect_symbol_requests", return_value=self.symbols):
            with patch.object(daily_report_cli, "run_daily", side_effect=error):
                with patch.object(daily_report_cli, "_parse_args", return_value=self._args(["--output-json"])):
                    with redirect_stdout(output):
                        self.assertEqual(main(), 1)
        self.assertIn("Use --overwrite to replace existing files.", output.getvalue())

    def test_generic_wrapped_error_returns_one(self):
        error = DailyReportResearchRunError("daily stage failed")
        error.__cause__ = RuntimeError("network")
        output = StringIO()
        with patch.object(daily_report_cli, "collect_symbol_requests", return_value=self.symbols):
            with patch.object(daily_report_cli, "run_daily", side_effect=error):
                with patch.object(daily_report_cli, "_parse_args", return_value=self._args()):
                    with redirect_stdout(output):
                        self.assertEqual(main(), 1)
        self.assertIn("Error: daily stage failed", output.getvalue())

    def test_argparse_failure_remains_system_exit_two(self):
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as raised:
                _parse_args(["--validation-position-size", "0"])
        self.assertEqual(raised.exception.code, 2)

    def test_package_and_unified_process_failure_exit_one(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = str(Path(directory) / "missing.txt")
            package = subprocess.run([sys.executable, "-m", "tw_stock_tool.cli.daily_report_cli", "--file", missing], capture_output=True, text=True)
            self.assertEqual(package.returncode, 1)
            unified = subprocess.run([sys.executable, "-m", "tw_stock_tool.cli.twstock_cli", "daily", "--file", missing], capture_output=True, text=True)
            self.assertEqual(unified.returncode, 1)


if __name__ == "__main__":
    unittest.main()
