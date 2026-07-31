from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.application.research_run import ScanRunRequest
from tw_stock_tool.application.research_run import SymbolRequest
from tw_stock_tool.cli import scan_stocks as scanner_cli
from tw_stock_tool.cli import twstock_cli
from tw_stock_tool.reports.report import ReportError
from tw_stock_tool.research_run.scan import ScanResearchRunError
from tw_stock_tool.research_run.models import ArtifactReference
from tests.subprocess_test_support import run_repo_python


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class TrackC41ScannerCliExitBehaviorTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.temp_path = Path(self._temporary_directory.name)
        self.symbols = (SymbolRequest("2330", "2330.TW"), SymbolRequest("6488", "6488.TWO"))

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _run_process(self, *command: str) -> subprocess.CompletedProcess[str]:
        return run_repo_python(
            *command,
            include_repository_root=False,
            suppress_bytecode=False,
        )

    def _result(self, *, with_error_log: bool = True):
        artifacts = [
            ArtifactReference("scan_ranking_excel", "reports/ranking.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", None),
            ArtifactReference("scan_ranking_csv", "reports/ranking.csv", "text/csv", None),
            ArtifactReference("scan_ranking_html", "reports/ranking.html", "text/html", None),
        ]
        if with_error_log:
            artifacts.append(ArtifactReference("scan_error_log", "reports/scan_errors.log", "text/plain", None))
        return SimpleNamespace(
            domain_result=pd.DataFrame([{"Status": "OK"}, {"Status": "ERROR"}]),
            generated_artifacts=tuple(artifacts),
        )

    def test_parser_supports_default_and_custom_manifest_path(self) -> None:
        self.assertIsNone(scanner_cli._parse_args([]).manifest_path)
        self.assertEqual(scanner_cli._parse_args(["--manifest-path", "custom/scan.json"]).manifest_path, "custom/scan.json")

    def test_main_builds_exact_request_and_calls_service_once(self) -> None:
        output = StringIO()
        with patch.object(scanner_cli, "collect_symbol_requests", return_value=self.symbols) as collect:
            with patch.object(scanner_cli, "run_scan", return_value=self._result()) as run:
                with patch.object(scanner_cli, "_parse_args", return_value=scanner_cli._parse_args([
                    "--stocks", "2330", "6488", "--stock-market", "all",
                    "--manifest-path", "custom/scan.json", "--output-dir", str(self.temp_path),
                    "--log-errors",
                ])):
                    with redirect_stdout(output):
                        result = scanner_cli.main()
        self.assertIsNone(result)
        collect.assert_called_once()
        run.assert_called_once()
        request = run.call_args.args[0]
        self.assertIsInstance(request, ScanRunRequest)
        self.assertEqual(request.symbols, self.symbols)
        self.assertEqual(request.universe, "all")
        self.assertEqual(request.output_dir, str(self.temp_path))
        self.assertEqual(request.manifest_path, "custom/scan.json")
        self.assertTrue(request.log_errors)
        self.assertIs(run.call_args.kwargs["progress_callback"], scanner_cli._print_progress)
        self.assertIn("成功: 1，失敗: 1", output.getvalue())
        self.assertIn("Excel: reports/ranking.xlsx", output.getvalue())
        self.assertIn("CSV: reports/ranking.csv", output.getvalue())
        self.assertIn("HTML: reports/ranking.html", output.getvalue())
        self.assertIn("錯誤紀錄: reports/scan_errors.log", output.getvalue())

    def test_success_without_error_log_and_direct_none_return(self) -> None:
        output = StringIO()
        with patch.object(scanner_cli, "collect_symbol_requests", return_value=(self.symbols[0],)):
            with patch.object(scanner_cli, "run_scan", return_value=self._result(with_error_log=False)):
                with patch.object(scanner_cli, "_parse_args", return_value=scanner_cli._parse_args(["--stocks", "2330"])):
                    with redirect_stdout(output):
                        self.assertIsNone(scanner_cli.main())
        self.assertNotIn("錯誤紀錄:", output.getvalue())

    def test_controlled_nested_application_error_uses_controlled_category(self) -> None:
        cause = ReportError("controlled report failure")
        error = ScanResearchRunError("scan stage failed")
        error.__cause__ = cause
        output = StringIO()
        with patch.object(scanner_cli, "collect_symbol_requests", return_value=(self.symbols[0],)):
            with patch.object(scanner_cli, "run_scan", side_effect=error):
                with patch.object(scanner_cli, "_parse_args", return_value=scanner_cli._parse_args(["--stocks", "2330"])):
                    with redirect_stdout(output):
                        self.assertEqual(scanner_cli.main(), 1)
        self.assertIn("錯誤：scan stage failed", output.getvalue())

    def test_unexpected_wrapper_and_keyboard_interrupt_return_one(self) -> None:
        wrapped = ScanResearchRunError("unexpected stage")
        wrapped.__cause__ = RuntimeError("network")
        for failure, marker in ((wrapped, "未預期錯誤：unexpected stage"), (KeyboardInterrupt(), "已取消掃描") ):
            with self.subTest(type=type(failure).__name__):
                output = StringIO()
                with patch.object(scanner_cli, "collect_symbol_requests", return_value=(self.symbols[0],)):
                    with patch.object(scanner_cli, "run_scan", side_effect=failure):
                        with patch.object(scanner_cli, "_parse_args", return_value=scanner_cli._parse_args(["--stocks", "2330"])):
                            with redirect_stdout(output):
                                self.assertEqual(scanner_cli.main(), 1)
                self.assertIn(marker, output.getvalue())

    def test_argparse_failure_remains_system_exit_two(self) -> None:
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as raised:
                with patch.object(sys, "argv", ["scan_stocks.py", "--workers", "not-an-int"]):
                    scanner_cli.main()
        self.assertEqual(raised.exception.code, 2)

    def test_unified_passthrough_preserves_manifest_argument_and_status(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.scan_stocks, "main", side_effect=fake_main) as mocked:
            status = twstock_cli.main(["scan", "--stocks", "2330", "--manifest-path", "scan.json"])
        self.assertEqual(status, 0)
        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["scan_stocks.py", "--stocks", "2330", "--manifest-path", "scan.json"])

    def test_package_and_unified_missing_file_exit_one(self) -> None:
        missing = self.temp_path / "missing.txt"
        package = run_repo_python("-m", "tw_stock_tool.cli.scan_stocks", "--file", str(missing), include_repository_root=False)
        self.assertEqual(package.returncode, 1)
        self.assertIn("錯誤：", package.stdout)
        unified = run_repo_python("-m", "tw_stock_tool.cli.twstock_cli", "scan", "--file", str(missing), include_repository_root=False)
        self.assertEqual(unified.returncode, 1)
        self.assertIn("錯誤：", unified.stdout)


if __name__ == "__main__":
    unittest.main()
