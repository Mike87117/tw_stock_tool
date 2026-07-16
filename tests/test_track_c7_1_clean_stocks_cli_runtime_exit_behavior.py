from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib
from io import StringIO
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.cli import clean_stocks as clean_cli
from tw_stock_tool.cli import scan_stocks as scanner_cli
from tw_stock_tool.cli import twstock_cli
from tw_stock_tool.utils.config import DEFAULT_AUTO_ADJUST, DEFAULT_INTERVAL, DEFAULT_PERIOD


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class CleanStocksCliRuntimeExitBehaviorCharacterizationTest(unittest.TestCase):
    def _run_direct(self, *args: str) -> tuple[object, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with patch.object(sys, "argv", ["clean_stocks.py", *args]):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = clean_cli.main()
        return result, stdout.getvalue(), stderr.getvalue()

    def _run_process(self, *args: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        python_path = [str(REPOSITORY_ROOT), str(REPOSITORY_ROOT / "src")]
        if environment.get("PYTHONPATH"):
            python_path.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(python_path)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, *args],
            cwd=REPOSITORY_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )

    def _assert_error_output(self, stdout: str, stderr: str, message: str) -> None:
        combined = stdout + stderr
        self.assertIn(message, combined)
        self.assertNotIn("Traceback", combined)

    def _assert_argparse_failure(self, completed: subprocess.CompletedProcess[str]) -> None:
        combined = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 2)
        self.assertIn("usage:", combined)
        self.assertIn("error", combined.lower())
        self.assertNotIn("Traceback", combined)

    def _success_result(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, None, None]:
        summary = pd.DataFrame(
            [
                {
                    "File": "synthetic.txt",
                    "Total Input Lines": 1,
                    "Unique Stocks": 1,
                    "Valid Stocks": 1,
                    "Invalid Stocks": 0,
                    "Duplicate Rows": 0,
                    "Output Clean File": "",
                }
            ]
        )
        result = pd.DataFrame(
            [{"Normalized Stock": "2330", "Status": "OK", "Error": ""}]
        )
        duplicates = pd.DataFrame(columns=["Row", "Stock", "Normalized Stock", "First Row"])
        return summary, result, duplicates, None, None

    def test_direct_success_keeps_legacy_none_and_creates_no_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            file_path = temp_path / "synthetic.txt"
            before = list(temp_path.iterdir())
            with (
                patch.object(clean_cli, "run_clean_stocks", return_value=self._success_result()) as run_mock,
                patch.object(clean_cli, "download_tw_stock") as download_mock,
            ):
                result, stdout, stderr = self._run_direct("--file", str(file_path))

            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertIsNone(result)
        run_mock.assert_called_once_with(
            file_path=str(file_path),
            period=DEFAULT_PERIOD,
            interval=DEFAULT_INTERVAL,
            auto_adjust=DEFAULT_AUTO_ADJUST,
            force_refresh=False,
            output=None,
            clean_file=None,
        )
        download_mock.assert_not_called()
        self.assertIn("Clean Stocks", stdout)
        self.assertIn("Valid stocks: 1", stdout)
        self.assertIn("Invalid: none", stdout)
        self.assertEqual(stderr, "")
        self.assertNotIn("Traceback", stdout + stderr)

    def test_direct_validation_failure_is_visible_and_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            missing_path = temp_path / "missing.txt"
            before = list(temp_path.iterdir())
            with patch.object(clean_cli, "download_tw_stock") as download_mock:
                result, stdout, stderr = self._run_direct("--file", str(missing_path))

            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertEqual(result, 1)
        self._assert_error_output(stdout, stderr, f"Error: Stock file not found: {missing_path}")
        download_mock.assert_not_called()

    def test_direct_validation_failure_should_return_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.txt"
            result, _, _ = self._run_direct("--file", str(missing_path))
        self.assertEqual(result, 1)

    def test_direct_runtime_failure_is_visible_and_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            file_path = temp_path / "synthetic.txt"
            before = list(temp_path.iterdir())
            with patch.object(
                clean_cli,
                "run_clean_stocks",
                side_effect=RuntimeError("controlled clean stocks failure"),
            ) as run_mock:
                result, stdout, stderr = self._run_direct("--file", str(file_path))

            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertEqual(result, 1)
        self.assertIn("Error: controlled clean stocks failure", stdout)
        self.assertNotIn("Traceback", stdout + stderr)
        run_mock.assert_called_once()

    def test_direct_runtime_failure_should_return_one(self) -> None:
        with patch.object(
            clean_cli,
            "run_clean_stocks",
            side_effect=RuntimeError("controlled clean stocks failure"),
        ):
            result, _, _ = self._run_direct("--file", "synthetic.txt")
        self.assertEqual(result, 1)

    def test_package_module_validation_failure_is_visible_and_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            missing_path = temp_path / "missing.txt"
            before = list(temp_path.iterdir())
            completed = self._run_process(
                "-m", "tw_stock_tool.cli.clean_stocks", "--file", str(missing_path)
            )
            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertEqual(completed.returncode, 1)
        self._assert_error_output(
            completed.stdout,
            completed.stderr,
            f"Error: Stock file not found: {missing_path}",
        )

    def test_package_module_validation_failure_should_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.txt"
            completed = self._run_process(
                "-m", "tw_stock_tool.cli.clean_stocks", "--file", str(missing_path)
            )
        self.assertEqual(completed.returncode, 1)

    def test_root_wrapper_validation_failure_is_visible_and_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            missing_path = temp_path / "missing.txt"
            before = list(temp_path.iterdir())
            completed = self._run_process(
                str(REPOSITORY_ROOT / "clean_stocks.py"), "--file", str(missing_path)
            )
            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertEqual(completed.returncode, 1)
        self._assert_error_output(
            completed.stdout,
            completed.stderr,
            f"Error: Stock file not found: {missing_path}",
        )

    def test_root_wrapper_execution_calls_package_main_once_and_propagates_status(self) -> None:
        with patch.object(clean_cli, "main", return_value=1) as main_mock:
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(str(REPOSITORY_ROOT / "clean_stocks.py"), run_name="__main__")

        self.assertEqual(raised.exception.code, 1)
        main_mock.assert_called_once_with()

    def test_root_wrapper_validation_failure_should_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.txt"
            completed = self._run_process(
                str(REPOSITORY_ROOT / "clean_stocks.py"), "--file", str(missing_path)
            )
        self.assertEqual(completed.returncode, 1)

    def test_unified_function_validation_failure_is_visible_and_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            missing_path = temp_path / "missing.txt"
            before = list(temp_path.iterdir())
            original_argv = sys.argv[:]
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = twstock_cli.main(["stock-list", "clean", "--file", str(missing_path)])

            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertEqual(status, 1)
        self.assertEqual(sys.argv, original_argv)
        self._assert_error_output(
            stdout.getvalue(),
            stderr.getvalue(),
            f"Error: Stock file not found: {missing_path}",
        )

    def test_unified_function_validation_failure_should_return_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.txt"
            status = twstock_cli.main(["stock-list", "clean", "--file", str(missing_path)])
        self.assertEqual(status, 1)

    def test_unified_module_validation_failure_is_visible_and_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            missing_path = temp_path / "missing.txt"
            before = list(temp_path.iterdir())
            completed = self._run_process(
                "-m",
                "tw_stock_tool.cli.twstock_cli",
                "stock-list",
                "clean",
                "--file",
                str(missing_path),
            )
            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertEqual(completed.returncode, 1)
        self._assert_error_output(
            completed.stdout,
            completed.stderr,
            f"Error: Stock file not found: {missing_path}",
        )

    def test_unified_module_validation_failure_should_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.txt"
            completed = self._run_process(
                "-m",
                "tw_stock_tool.cli.twstock_cli",
                "stock-list",
                "clean",
                "--file",
                str(missing_path),
            )
        self.assertEqual(completed.returncode, 1)

    def test_package_invalid_argument_is_argparse_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            before = list(Path(temp_dir).iterdir())
            completed = self._run_process(
                "-m", "tw_stock_tool.cli.clean_stocks", "--definitely-invalid-option"
            )
            self.assertEqual(list(Path(temp_dir).iterdir()), before)
        self._assert_argparse_failure(completed)

    def test_root_invalid_argument_is_argparse_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            before = list(Path(temp_dir).iterdir())
            completed = self._run_process(
                str(REPOSITORY_ROOT / "clean_stocks.py"), "--definitely-invalid-option"
            )
            self.assertEqual(list(Path(temp_dir).iterdir()), before)
        self._assert_argparse_failure(completed)

    def test_unified_invalid_argument_is_argparse_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            before = list(Path(temp_dir).iterdir())
            completed = self._run_process(
                "-m",
                "tw_stock_tool.cli.twstock_cli",
                "stock-list",
                "clean",
                "--definitely-invalid-option",
            )
            self.assertEqual(list(Path(temp_dir).iterdir()), before)
        self._assert_argparse_failure(completed)

    def test_root_import_alias_remains_compatible(self) -> None:
        with patch.object(clean_cli, "main") as main_mock:
            root_clean_stocks = importlib.import_module("clean_stocks")

        self.assertIs(root_clean_stocks, clean_cli)
        self.assertIs(root_clean_stocks.main, clean_cli.main)
        main_mock.assert_not_called()

    def test_sibling_runtime_status_contract_is_one_and_dispatcher_propagates_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            before = list(temp_path.iterdir())
            scanner_args = scanner_cli._parse_args(
                ["--stocks", "2330", "--output-dir", str(temp_path)]
            )
            with (
                patch.object(scanner_cli, "_parse_args", return_value=scanner_args),
                patch.object(scanner_cli, "_collect_stock_ids", return_value=["2330"]),
                patch.object(
                    scanner_cli,
                    "scan_stocks",
                    side_effect=RuntimeError("controlled scanner failure"),
                ),
                redirect_stdout(StringIO()),
            ):
                scanner_status = scanner_cli.main()

            self.assertEqual(list(temp_path.iterdir()), before)

        original_argv = sys.argv[:]
        with patch.object(scanner_cli, "main", return_value=1):
            unified_status = twstock_cli.main(["scan", "--stocks", "2330"])

        self.assertEqual(scanner_status, 1)
        self.assertEqual(unified_status, 1)
        self.assertEqual(sys.argv, original_argv)


if __name__ == "__main__":
    unittest.main()
