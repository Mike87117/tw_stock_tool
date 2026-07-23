from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import importlib
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.cli import benchmark as benchmark_cli
from tw_stock_tool.cli import scan_stocks as scanner_cli
from tw_stock_tool.cli import twstock_cli
from tw_stock_tool.data import cache_manager
from tw_stock_tool.utils.config import DEFAULT_AUTO_ADJUST, DEFAULT_INTERVAL, DEFAULT_PERIOD
from tests.subprocess_test_support import run_repo_python


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class BenchmarkCliRuntimeExitBehaviorCharacterizationTest(unittest.TestCase):
    def _synthetic_result(self) -> benchmark_cli.BenchmarkResult:
        return benchmark_cli.BenchmarkResult(
            summary=pd.DataFrame([{"Runs": 1, "Stocks": 1}]),
            detail=pd.DataFrame([{"Run": 1, "Stocks": 1, "OK": 1, "ERROR": 0}]),
            errors=pd.DataFrame(columns=["Run", "Stock", "Symbol", "Error"]),
        )

    def _run_direct(self, *args: str) -> tuple[object, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with patch.object(sys, "argv", ["benchmark.py", *args]):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = benchmark_cli.main()
        return result, stdout.getvalue(), stderr.getvalue()

    def _run_process(self, *args: str) -> subprocess.CompletedProcess[str]:
        return run_repo_python(*args)

    def _package_validation_failure(self) -> subprocess.CompletedProcess[str]:
        return self._run_process("-m", "tw_stock_tool.cli.benchmark")


    def _unified_module_validation_failure(self) -> subprocess.CompletedProcess[str]:
        return self._run_process(
            "-m",
            "tw_stock_tool.cli.twstock_cli",
            "benchmark",
        )

    def _run_unified_validation_failure(self) -> tuple[int, str, str]:
        original_argv = sys.argv[:]
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = twstock_cli.main(["benchmark"])
        self.assertEqual(sys.argv, original_argv)
        return status, stdout.getvalue(), stderr.getvalue()

    def _assert_validation_failure_output(self, stdout: str, stderr: str) -> None:
        combined = stdout + stderr
        self.assertIn("Error: benchmark stock list cannot be empty.", combined)
        self.assertNotIn("Traceback", combined)

    def _assert_argparse_failure(self, completed: subprocess.CompletedProcess[str]) -> None:
        combined = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 2)
        self.assertIn("usage:", combined)
        self.assertIn("error", combined.lower())
        self.assertNotIn("Traceback", combined)

    def test_direct_success_keeps_legacy_none_and_creates_no_artifacts(self) -> None:
        synthetic = self._synthetic_result()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            before = list(temp_path.iterdir())
            with (
                patch.object(benchmark_cli, "run_benchmark", return_value=synthetic) as run_mock,
                patch.object(benchmark_cli, "_output_paths", return_value=None) as paths_mock,
            ):
                result, stdout, stderr = self._run_direct("--stocks", "2330")

            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertIsNone(result)
        run_mock.assert_called_once_with(
            stock_ids=["2330"],
            period=DEFAULT_PERIOD,
            interval=DEFAULT_INTERVAL,
            workers=8,
            force_refresh=False,
            auto_adjust=DEFAULT_AUTO_ADJUST,
            repeat=1,
            warmup=0,
        )
        paths_mock.assert_called_once_with(None)
        self.assertIn("[Summary]", stdout)
        self.assertIn("[Detail]", stdout)
        self.assertIn("[Errors]", stdout)
        self.assertIn("(empty)", stdout)
        self.assertEqual(stderr, "")

    def test_direct_validation_failure_is_visible_and_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            before = list(temp_path.iterdir())
            with (
                patch.object(benchmark_cli, "scan_stocks") as scan_mock,
                patch.object(benchmark_cli, "_output_paths") as paths_mock,
            ):
                result, stdout, stderr = self._run_direct()

            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertEqual(result, 1)
        self._assert_validation_failure_output(stdout, stderr)
        scan_mock.assert_not_called()
        paths_mock.assert_not_called()

    def test_direct_validation_failure_should_return_one(self) -> None:
        result, _, _ = self._run_direct()
        self.assertEqual(result, 1)

    def test_direct_runtime_failure_is_visible_and_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            before = list(temp_path.iterdir())
            with (
                patch.object(
                    benchmark_cli,
                    "run_benchmark",
                    side_effect=RuntimeError("controlled benchmark failure"),
                ) as run_mock,
                patch.object(benchmark_cli, "_output_paths") as paths_mock,
            ):
                result, stdout, stderr = self._run_direct("--stocks", "2330")

            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertEqual(result, 1)
        self.assertIn("Error: controlled benchmark failure", stdout)
        self.assertNotIn("Traceback", stdout + stderr)
        run_mock.assert_called_once()
        paths_mock.assert_not_called()

    def test_direct_runtime_failure_should_return_one(self) -> None:
        with patch.object(
            benchmark_cli,
            "run_benchmark",
            side_effect=RuntimeError("controlled benchmark failure"),
        ):
            result, _, _ = self._run_direct("--stocks", "2330")
        self.assertEqual(result, 1)

    def test_package_module_validation_failure_is_visible_and_exits_one(self) -> None:
        completed = self._package_validation_failure()

        self.assertEqual(completed.returncode, 1)
        self._assert_validation_failure_output(completed.stdout, completed.stderr)

    def test_package_module_validation_failure_should_exit_one(self) -> None:
        self.assertEqual(self._package_validation_failure().returncode, 1)




    def test_unified_function_validation_failure_is_visible_and_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            before = list(temp_path.iterdir())
            status, stdout, stderr = self._run_unified_validation_failure()
            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertEqual(status, 1)
        self._assert_validation_failure_output(stdout, stderr)

    def test_unified_function_validation_failure_should_return_one(self) -> None:
        status, _, _ = self._run_unified_validation_failure()
        self.assertEqual(status, 1)

    def test_unified_module_validation_failure_is_visible_and_exits_one(self) -> None:
        completed = self._unified_module_validation_failure()

        self.assertEqual(completed.returncode, 1)
        self._assert_validation_failure_output(completed.stdout, completed.stderr)

    def test_unified_module_validation_failure_should_exit_one(self) -> None:
        self.assertEqual(self._unified_module_validation_failure().returncode, 1)

    def test_package_invalid_argument_is_argparse_exit_two(self) -> None:
        self._assert_argparse_failure(
            self._run_process(
                "-m",
                "tw_stock_tool.cli.benchmark",
                "--definitely-invalid-option",
            )
        )


    def test_unified_invalid_argument_is_argparse_exit_two(self) -> None:
        self._assert_argparse_failure(
            self._run_process(
                "-m",
                "tw_stock_tool.cli.twstock_cli",
                "benchmark",
                "--definitely-invalid-option",
            )
        )


    def test_sibling_runtime_status_contract_is_one_and_dispatcher_propagates_it(self) -> None:
        scanner_args = scanner_cli._parse_args(
            ["--stocks", "2330", "--output-dir", tempfile.gettempdir()]
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

        with (
            patch.object(sys, "argv", ["cache_manager.py", "--summary"]),
            patch.object(
                cache_manager,
                "cache_summary",
                side_effect=RuntimeError("controlled cache failure"),
            ),
            redirect_stdout(StringIO()),
        ):
            cache_status = cache_manager.main()

        original_argv = sys.argv[:]
        with patch.object(benchmark_cli, "main", return_value=1):
            unified_status = twstock_cli.main(["benchmark"])

        self.assertEqual(scanner_status, 1)
        self.assertEqual(cache_status, 1)
        self.assertEqual(unified_status, 1)
        self.assertEqual(sys.argv, original_argv)


if __name__ == "__main__":
    unittest.main()
