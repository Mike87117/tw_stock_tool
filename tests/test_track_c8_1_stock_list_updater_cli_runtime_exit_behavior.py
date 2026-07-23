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
from tw_stock_tool.cli import twstock_cli
from tw_stock_tool.data import stock_list_updater as stock_cli
from tests.subprocess_test_support import run_repo_python


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class StockListUpdaterCliRuntimeExitBehaviorCharacterizationTest(unittest.TestCase):
    def _run_direct(self, *args: str) -> tuple[object, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with patch.object(sys, "argv", ["stock_list_updater.py", *args]):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = stock_cli.main()
        return result, stdout.getvalue(), stderr.getvalue()

    def _run_process(self, *args: str) -> subprocess.CompletedProcess[str]:
        return run_repo_python(*args)

    def _run_offline_process(
        self, *args: str
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        with tempfile.TemporaryDirectory() as helper_dir:
            helper_path = Path(helper_dir)
            (helper_path / "sitecustomize.py").write_text(
                """import requests


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return [{"Code": "2330", "Name": "TSMC", "Type": "24"}]


def _fake_get(*args, **kwargs):
    return _Response()


requests.get = _fake_get
""",
                encoding="utf-8",
            )
            completed = run_repo_python(
                *args,
                extra_pythonpath=(helper_path,),
            )
        return completed, helper_path

    def _one_row(self) -> pd.DataFrame:
        return pd.DataFrame(
            [{"Stock": "2330", "Name": "TSMC", "Market": "TWSE", "Type": "24"}]
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

    def test_direct_success_keeps_legacy_none_and_creates_no_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output = temp_path / "stocks.txt"
            before = list(temp_path.iterdir())
            frame = self._one_row()
            with (
                patch.object(stock_cli, "update_stock_list", return_value=(frame, output)) as update_mock,
                patch.object(stock_cli.requests, "get") as request_mock,
            ):
                result, stdout, stderr = self._run_direct(
                    "--market", "twse", "--output", str(output)
                )

            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertIsNone(result)
        update_mock.assert_called_once_with(
            market="twse",
            output=str(output),
            allow_partial=False,
            add_suffix=False,
        )
        request_mock.assert_not_called()
        self.assertIn("Stock list updated:", stdout)
        self.assertIn("Stocks: 1", stdout)
        self.assertEqual(stderr, "")
        self.assertNotIn("Traceback", stdout + stderr)

    def test_direct_validation_failure_is_visible_and_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output = temp_path / "stocks.txt"
            before = list(temp_path.iterdir())
            with (
                patch.object(stock_cli, "fetch_twse_stock_list", return_value=self._one_row()) as twse_mock,
                patch.object(stock_cli, "fetch_tpex_stock_list") as tpex_mock,
                patch.object(stock_cli.requests, "get") as request_mock,
            ):
                result, stdout, stderr = self._run_direct(
                    "--market", "twse", "--output", str(output)
                )

            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertEqual(result, 1)
        self._assert_error_output(
            stdout,
            stderr,
            "Error: Abnormally few common stocks parsed: 1 < 100.",
        )
        twse_mock.assert_called_once_with()
        tpex_mock.assert_not_called()
        request_mock.assert_not_called()
        self.assertFalse(output.exists())

    def test_direct_validation_failure_should_return_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "stocks.txt"
            with patch.object(stock_cli, "fetch_twse_stock_list", return_value=self._one_row()):
                result, _, _ = self._run_direct(
                    "--market", "twse", "--output", str(output)
                )
        self.assertEqual(result, 1)

    def test_direct_runtime_failure_is_visible_and_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output = temp_path / "stocks.txt"
            before = list(temp_path.iterdir())
            with patch.object(
                stock_cli,
                "update_stock_list",
                side_effect=RuntimeError("controlled stock list updater failure"),
            ) as update_mock:
                result, stdout, stderr = self._run_direct(
                    "--market", "twse", "--output", str(output)
                )

            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertEqual(result, 1)
        self.assertIn("Error: controlled stock list updater failure", stdout)
        self.assertNotIn("Traceback", stdout + stderr)
        self.assertFalse(output.exists())
        update_mock.assert_called_once_with(
            market="twse",
            output=str(output),
            allow_partial=False,
            add_suffix=False,
        )

    def test_direct_runtime_failure_should_return_one(self) -> None:
        with patch.object(
            stock_cli,
            "update_stock_list",
            side_effect=RuntimeError("controlled stock list updater failure"),
        ):
            result, _, _ = self._run_direct("--market", "twse", "--output", "stocks.txt")
        self.assertEqual(result, 1)

    def test_package_module_validation_failure_is_visible_and_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output = temp_path / "stocks.txt"
            before = list(temp_path.iterdir())
            completed, helper_path = self._run_offline_process(
                "-m",
                "tw_stock_tool.data.stock_list_updater",
                "--market",
                "twse",
                "--output",
                str(output),
            )

            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertFalse(helper_path.exists())
        self.assertEqual(completed.returncode, 1)
        self._assert_error_output(
            completed.stdout,
            completed.stderr,
            "Error: Abnormally few common stocks parsed: 1 < 100.",
        )
        self.assertFalse(output.exists())

    def test_package_module_validation_failure_should_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "stocks.txt"
            completed, helper_path = self._run_offline_process(
                "-m",
                "tw_stock_tool.data.stock_list_updater",
                "--market",
                "twse",
                "--output",
                str(output),
            )
        self.assertFalse(helper_path.exists())
        self.assertEqual(completed.returncode, 1)




    def test_unified_function_validation_failure_is_visible_and_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output = temp_path / "stocks.txt"
            before = list(temp_path.iterdir())
            original_argv = sys.argv[:]
            stdout = StringIO()
            stderr = StringIO()
            with (
                patch.object(stock_cli, "fetch_twse_stock_list", return_value=self._one_row()) as twse_mock,
                patch.object(stock_cli, "fetch_tpex_stock_list") as tpex_mock,
                patch.object(stock_cli.requests, "get") as request_mock,
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                status = twstock_cli.main(
                    ["stock-list", "update", "--market", "twse", "--output", str(output)]
                )

            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertEqual(status, 1)
        self.assertEqual(sys.argv, original_argv)
        self._assert_error_output(
            stdout.getvalue(),
            stderr.getvalue(),
            "Error: Abnormally few common stocks parsed: 1 < 100.",
        )
        twse_mock.assert_called_once_with()
        tpex_mock.assert_not_called()
        request_mock.assert_not_called()
        self.assertFalse(output.exists())

    def test_unified_function_validation_failure_should_return_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "stocks.txt"
            with patch.object(stock_cli, "fetch_twse_stock_list", return_value=self._one_row()):
                status = twstock_cli.main(
                    ["stock-list", "update", "--market", "twse", "--output", str(output)]
                )
        self.assertEqual(status, 1)

    def test_unified_module_validation_failure_is_visible_and_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output = temp_path / "stocks.txt"
            before = list(temp_path.iterdir())
            completed, helper_path = self._run_offline_process(
                "-m",
                "tw_stock_tool.cli.twstock_cli",
                "stock-list",
                "update",
                "--market",
                "twse",
                "--output",
                str(output),
            )

            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertFalse(helper_path.exists())
        self.assertEqual(completed.returncode, 1)
        self._assert_error_output(
            completed.stdout,
            completed.stderr,
            "Error: Abnormally few common stocks parsed: 1 < 100.",
        )
        self.assertFalse(output.exists())

    def test_unified_module_validation_failure_should_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "stocks.txt"
            completed, helper_path = self._run_offline_process(
                "-m",
                "tw_stock_tool.cli.twstock_cli",
                "stock-list",
                "update",
                "--market",
                "twse",
                "--output",
                str(output),
            )
        self.assertFalse(helper_path.exists())
        self.assertEqual(completed.returncode, 1)

    def test_package_invalid_argument_is_argparse_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output = temp_path / "stocks.txt"
            before = list(temp_path.iterdir())
            completed = self._run_process(
                "-m", "tw_stock_tool.data.stock_list_updater", "--definitely-invalid-option"
            )
            self.assertEqual(list(temp_path.iterdir()), before)
        self._assert_argparse_failure(completed)
        self.assertFalse(output.exists())


    def test_unified_invalid_argument_is_argparse_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output = temp_path / "stocks.txt"
            before = list(temp_path.iterdir())
            completed = self._run_process(
                "-m",
                "tw_stock_tool.cli.twstock_cli",
                "stock-list",
                "update",
                "--definitely-invalid-option",
            )
            self.assertEqual(list(temp_path.iterdir()), before)
        self._assert_argparse_failure(completed)
        self.assertFalse(output.exists())


    def test_sibling_runtime_status_contract_is_one_and_dispatcher_propagates_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            before = list(temp_path.iterdir())
            clean_args = clean_cli._parse_args(
                ["--file", str(temp_path / "synthetic.txt")]
            )
            stdout = StringIO()
            with (
                patch.object(clean_cli, "_parse_args", return_value=clean_args),
                patch.object(
                    clean_cli,
                    "run_clean_stocks",
                    side_effect=RuntimeError("controlled clean stocks sibling failure"),
                ),
                redirect_stdout(stdout),
            ):
                sibling_status = clean_cli.main()

            self.assertEqual(list(temp_path.iterdir()), before)

        original_argv = sys.argv[:]
        with patch.object(clean_cli, "main", return_value=1):
            unified_status = twstock_cli.main(
                ["stock-list", "clean", "--file", "synthetic.txt"]
            )

        self.assertEqual(sibling_status, 1)
        self.assertIn("Error: controlled clean stocks sibling failure", stdout.getvalue())
        self.assertNotIn("Traceback", stdout.getvalue())
        self.assertEqual(unified_status, 1)
        self.assertEqual(sys.argv, original_argv)


if __name__ == "__main__":
    unittest.main()
