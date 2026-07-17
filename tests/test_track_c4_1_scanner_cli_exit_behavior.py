import argparse
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.cli import main as analyze_cli
from tw_stock_tool.cli import scan_stocks as scanner_cli
from tw_stock_tool.cli import twstock_cli
from tw_stock_tool.reports.report import ReportError
from tests.subprocess_test_support import run_repo_python


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class TrackC41ScannerCliExitBehaviorTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.temp_path = Path(self._temporary_directory.name)

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _missing_file(self) -> Path:
        return self.temp_path / "missing-stocks.txt"

    def _scanner_args(self) -> argparse.Namespace:
        return scanner_cli._parse_args(
            ["--stocks", "2330", "--output-dir", str(self.temp_path)]
        )

    def _ranking(self) -> pd.DataFrame:
        return pd.DataFrame([{"Status": "OK"}])

    def _assert_no_artifacts(self) -> None:
        self.assertEqual(list(self.temp_path.iterdir()), [])

    def _run_direct_missing_file(self) -> tuple[object, str]:
        output = StringIO()
        with patch.object(
            sys,
            "argv",
            ["scan_stocks.py", "--file", str(self._missing_file())],
        ):
            with redirect_stdout(output):
                result = scanner_cli.main()
        return result, output.getvalue()

    def _run_direct_scan_failure(self, exc: BaseException) -> tuple[object, str]:
        output = StringIO()
        with patch.object(scanner_cli, "_parse_args", return_value=self._scanner_args()):
            with patch.object(scanner_cli, "_collect_stock_ids", return_value=["2330"]):
                with patch.object(scanner_cli, "scan_stocks", side_effect=exc):
                    with redirect_stdout(output):
                        result = scanner_cli.main()
        return result, output.getvalue()

    def _run_process(self, *command: str) -> subprocess.CompletedProcess[str]:
        return run_repo_python(
            *command,
            include_repository_root=False,
            suppress_bytecode=False,
        )

    def _package_module_failure(self) -> subprocess.CompletedProcess[str]:
        return self._run_process(
            "-m",
            "tw_stock_tool.cli.scan_stocks",
            "--file",
            str(self._missing_file()),
        )

    def _root_wrapper_failure(self) -> subprocess.CompletedProcess[str]:
        return self._run_process("scan_stocks.py", "--file", str(self._missing_file()))

    def _unified_module_failure(self) -> subprocess.CompletedProcess[str]:
        return self._run_process(
            "-m",
            "tw_stock_tool.cli.twstock_cli",
            "scan",
            "--file",
            str(self._missing_file()),
        )

    def _run_unified_missing_file(self) -> tuple[int, str]:
        output = StringIO()
        original_argv = sys.argv[:]
        with redirect_stdout(output):
            status = twstock_cli.main(["scan", "--file", str(self._missing_file())])
        self.assertEqual(sys.argv, original_argv)
        return status, output.getvalue()

    def test_direct_success_keeps_legacy_none_return_without_artifacts(self) -> None:
        paths = {
            "excel": self.temp_path / "ranking.xlsx",
            "csv": self.temp_path / "ranking.csv",
            "html": self.temp_path / "ranking.html",
        }
        output = StringIO()
        with patch.object(scanner_cli, "_parse_args", return_value=self._scanner_args()):
            with patch.object(scanner_cli, "_collect_stock_ids", return_value=["2330"]):
                with patch.object(scanner_cli, "scan_stocks", return_value=self._ranking()):
                    with patch.object(
                        scanner_cli,
                        "export_stock_ranking",
                        return_value=paths,
                    ):
                        with redirect_stdout(output):
                            result = scanner_cli.main()

        self.assertIsNone(result)
        self.assertIn("Excel:", output.getvalue())
        self.assertIn("CSV:", output.getvalue())
        self.assertIn("HTML:", output.getvalue())
        self._assert_no_artifacts()

    def test_direct_value_error_is_printed_without_scanning_or_exporting(self) -> None:
        output = StringIO()
        with patch.object(
            sys,
            "argv",
            ["scan_stocks.py", "--file", str(self._missing_file())],
        ):
            with patch.object(scanner_cli, "scan_stocks") as scan_mock:
                with patch.object(scanner_cli, "export_stock_ranking") as export_mock:
                    with redirect_stdout(output):
                        result = scanner_cli.main()

        self.assertEqual(result, 1)
        self.assertIn("錯誤：", output.getvalue())
        scan_mock.assert_not_called()
        export_mock.assert_not_called()
        self._assert_no_artifacts()

    def test_direct_report_error_is_printed_without_success_summary(self) -> None:
        output = StringIO()
        with patch.object(scanner_cli, "_parse_args", return_value=self._scanner_args()):
            with patch.object(scanner_cli, "_collect_stock_ids", return_value=["2330"]):
                with patch.object(scanner_cli, "scan_stocks", return_value=self._ranking()):
                    with patch.object(
                        scanner_cli,
                        "export_stock_ranking",
                        side_effect=ReportError("controlled report failure"),
                    ):
                        with redirect_stdout(output):
                            result = scanner_cli.main()

        self.assertEqual(result, 1)
        self.assertIn("錯誤：controlled report failure", output.getvalue())
        self.assertNotIn("Excel:", output.getvalue())
        self._assert_no_artifacts()

    def test_direct_cancellation_is_printed_without_exporting(self) -> None:
        result, output = self._run_direct_scan_failure(KeyboardInterrupt())

        self.assertEqual(result, 1)
        self.assertIn("已取消", output)
        self._assert_no_artifacts()

    def test_direct_unexpected_error_is_printed_without_exporting(self) -> None:
        result, output = self._run_direct_scan_failure(RuntimeError("controlled failure"))

        self.assertEqual(result, 1)
        self.assertIn("未預期錯誤：controlled failure", output)
        self._assert_no_artifacts()

    def test_direct_value_error_should_return_nonzero(self) -> None:
        result, _ = self._run_direct_missing_file()
        self.assertEqual(result, 1)

    def test_direct_report_error_should_return_nonzero(self) -> None:
        result, _ = self._run_direct_scan_failure(ReportError("controlled report failure"))
        self.assertEqual(result, 1)

    def test_direct_cancellation_should_return_nonzero(self) -> None:
        result, _ = self._run_direct_scan_failure(KeyboardInterrupt())
        self.assertEqual(result, 1)

    def test_direct_unexpected_error_should_return_nonzero(self) -> None:
        result, _ = self._run_direct_scan_failure(RuntimeError("controlled failure"))
        self.assertEqual(result, 1)

    def test_package_module_process_reports_failure_and_exits_one(self) -> None:
        completed = self._package_module_failure()

        self.assertEqual(completed.returncode, 1)
        self.assertIn("錯誤：", completed.stdout)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self._assert_no_artifacts()

    def test_package_module_runtime_failure_should_exit_nonzero(self) -> None:
        self.assertEqual(self._package_module_failure().returncode, 1)

    def test_root_wrapper_process_reports_failure_and_exits_one(self) -> None:
        completed = self._root_wrapper_failure()

        self.assertEqual(completed.returncode, 1)
        self.assertIn("錯誤：", completed.stdout)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self._assert_no_artifacts()

    def test_root_wrapper_runtime_failure_should_exit_nonzero(self) -> None:
        self.assertEqual(self._root_wrapper_failure().returncode, 1)

    def test_unified_function_propagates_scanner_failure_status(self) -> None:
        status, output = self._run_unified_missing_file()

        self.assertEqual(status, 1)
        self.assertIn("錯誤：", output)
        self._assert_no_artifacts()

    def test_unified_function_scanner_failure_should_return_nonzero(self) -> None:
        status, _ = self._run_unified_missing_file()
        self.assertEqual(status, 1)

    def test_unified_module_process_reports_failure_and_exits_one(self) -> None:
        completed = self._unified_module_failure()

        self.assertEqual(completed.returncode, 1)
        self.assertIn("錯誤：", completed.stdout)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self._assert_no_artifacts()

    def test_unified_module_scanner_failure_should_exit_nonzero(self) -> None:
        self.assertEqual(self._unified_module_failure().returncode, 1)

    def test_console_script_mapping_is_direct_but_installed_command_is_unavailable(self) -> None:
        with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)

        target = project["project"]["scripts"]["twstock"]
        self.assertEqual(target, "tw_stock_tool.cli.twstock_cli:main")
        module_name, function_name = target.split(":")
        module = __import__(module_name, fromlist=[function_name])
        self.assertTrue(callable(getattr(module, function_name)))

    def test_argparse_failures_raise_nonzero_system_exit_at_scanner_and_unified_boundaries(self) -> None:
        with patch.object(sys, "argv", ["scan_stocks.py", "--workers", "not-an-int"]):
            with redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as scanner_exit:
                    scanner_cli.main()
        self.assertEqual(scanner_exit.exception.code, 2)

        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as unified_exit:
                twstock_cli.main(["scan", "--workers", "not-an-int"])
        self.assertEqual(unified_exit.exception.code, 2)

    def test_sibling_analyze_runtime_failure_and_unified_propagation_return_one(self) -> None:
        direct_output = StringIO()
        with redirect_stdout(direct_output):
            direct_status = analyze_cli.main(["--stock", ""])
        unified_output = StringIO()
        with redirect_stdout(unified_output):
            unified_status = twstock_cli.main(["analyze", "--stock", ""])

        self.assertEqual(direct_status, 1)
        self.assertEqual(unified_status, 1)
        self.assertIn("錯誤：", direct_output.getvalue())
        self.assertIn("錯誤：", unified_output.getvalue())


if __name__ == "__main__":
    unittest.main()
