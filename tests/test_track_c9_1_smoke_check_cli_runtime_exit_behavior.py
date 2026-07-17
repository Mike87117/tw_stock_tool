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

from tw_stock_tool.cli import price_data_smoke_check as price_cli
from tw_stock_tool.cli import stock_list_smoke_check as stock_cli
from tw_stock_tool.cli import twstock_cli


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _stock_frame(stock_ids: list[str], market: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Stock": stock_id,
                "Name": f"Name {stock_id}",
                "Market": market,
                "Type": "stock",
            }
            for stock_id in stock_ids
        ]
    )


def _price_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [101.0, 102.0],
            "Volume": [1000, 1200],
        }
    )


class TrackC91SmokeCheckCliRuntimeExitBehaviorTest(unittest.TestCase):
    def _stock_success_frames(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        twse_ids = ["2317", "2330", *[str(code) for code in range(1000, 1248)]]
        tpex_ids = ["8069", *[str(code) for code in range(2000, 2249)]]
        return _stock_frame(twse_ids, "TWSE"), _stock_frame(tpex_ids, "TPEX")

    def _stock_failure_frames(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        return _stock_frame(["2330"], "TWSE"), _stock_frame(["8299"], "TPEX")

    def _invoke_direct(
        self,
        module: object,
        program_name: str,
        *args: str,
    ) -> tuple[tuple[str, object], str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with patch.object(sys, "argv", [program_name, *args]):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                try:
                    result = module.main()
                except SystemExit as exc:
                    return ("system_exit", exc.code), stdout.getvalue(), stderr.getvalue()
        return ("return", result), stdout.getvalue(), stderr.getvalue()

    def _run_process(
        self,
        *args: str,
        helper_path: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        python_path = []
        if helper_path is not None:
            python_path.append(str(helper_path))
        python_path.extend([str(REPOSITORY_ROOT), str(REPOSITORY_ROOT / "src")])
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

    def _sitecustomize_text(self, mode: str) -> str:
        if mode == "stock":
            return '''import requests


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return [{"Code": "2330", "Name": "TSMC", "Type": "24"}]


def _get(*args, **kwargs):
    return _Response()


requests.get = _get
'''
        return '''import pandas as pd
import requests
import yfinance


def _download(*args, **kwargs):
    return pd.DataFrame()


def _get(*args, **kwargs):
    raise RuntimeError("controlled offline HTTP request")


yfinance.download = _download
requests.get = _get
'''

    def _run_offline_process(
        self,
        mode: str,
        *args: str,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as helper_dir:
            helper_path = Path(helper_dir)
            sitecustomize = helper_path / "sitecustomize.py"
            sitecustomize.write_text(self._sitecustomize_text(mode), encoding="utf-8")
            before = sorted(path.name for path in helper_path.iterdir())
            completed = self._run_process(*args, helper_path=helper_path)
            self.assertEqual(
                sorted(path.name for path in helper_path.iterdir()),
                before,
            )
        return completed

    def _assert_failure_output(self, stdout: str, stderr: str, marker: str) -> None:
        combined = stdout + stderr
        self.assertIn(marker, combined)
        self.assertNotIn("Traceback", combined)

    def _assert_argparse_failure(
        self,
        completed: subprocess.CompletedProcess[str],
    ) -> None:
        combined = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 2)
        self.assertIn("usage:", combined)
        self.assertIn("error", combined.lower())
        self.assertNotIn("Traceback", combined)

    def _stock_direct_failure(self) -> tuple[tuple[str, object], str, str, object]:
        twse, tpex = self._stock_failure_frames()
        with (
            patch.object(stock_cli.stock_list_updater, "fetch_twse_stock_list", return_value=twse),
            patch.object(stock_cli.stock_list_updater, "fetch_tpex_stock_list", return_value=tpex),
            patch.object(stock_cli.stock_list_updater.requests, "get") as request_mock,
        ):
            outcome, stdout, stderr = self._invoke_direct(
                stock_cli,
                "stock_list_smoke_check.py",
            )
        return outcome, stdout, stderr, request_mock

    def _price_direct_failure(self) -> tuple[tuple[str, object], str, str, object]:
        with (
            patch.object(
                price_cli.data_loader,
                "download_tw_stock",
                return_value=(pd.DataFrame(), "2330.TW"),
            ) as download_mock,
            patch.object(price_cli.data_loader.requests, "get") as request_mock,
            patch.object(price_cli.data_loader.yf, "download") as yfinance_mock,
        ):
            outcome, stdout, stderr = self._invoke_direct(
                price_cli,
                "price_data_smoke_check.py",
            )
        self.assert_not_called(request_mock, yfinance_mock)
        return outcome, stdout, stderr, download_mock

    def assert_not_called(self, *mocks: object) -> None:
        for mock in mocks:
            mock.assert_not_called()

    def test_stock_direct_success_preserves_none_and_output_without_artifact(self) -> None:
        twse, tpex = self._stock_success_frames()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            before = list(temp_path.iterdir())
            with (
                patch.object(stock_cli.stock_list_updater, "fetch_twse_stock_list", return_value=twse),
                patch.object(stock_cli.stock_list_updater, "fetch_tpex_stock_list", return_value=tpex),
                patch.object(stock_cli.stock_list_updater.requests, "get") as request_mock,
            ):
                outcome, stdout, stderr = self._invoke_direct(
                    stock_cli,
                    "stock_list_smoke_check.py",
                )

            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertEqual(outcome, ("return", None))
        self.assertIn("Stock List Smoke Check", stdout)
        self.assertIn("TWSE count: 250", stdout)
        self.assertIn("TPEx count: 250", stdout)
        self.assertIn("All count: 500", stdout)
        self.assertIn("Status: PASS", stdout)
        self.assertEqual(stderr, "")
        self.assertNotIn("Traceback", stdout + stderr)
        request_mock.assert_not_called()

    def test_stock_direct_handled_failure_returns_integer_one(self) -> None:
        outcome, stdout, stderr, request_mock = self._stock_direct_failure()

        self.assertEqual(outcome, ("return", 1))
        self._assert_failure_output(stdout, stderr, "Status: FAIL")
        self.assertIn("Error: TWSE count too low", stdout)
        request_mock.assert_not_called()

    def test_stock_direct_handled_failure_should_return_integer_one(self) -> None:
        outcome, _, _, _ = self._stock_direct_failure()
        self.assertEqual(outcome, ("return", 1))

    def test_stock_package_module_failure_exits_one_without_traceback_or_artifact(self) -> None:
        completed = self._run_offline_process(
            "stock",
            "-m",
            "tw_stock_tool.cli.stock_list_smoke_check",
        )

        self.assertEqual(completed.returncode, 1)
        self._assert_failure_output(
            completed.stdout,
            completed.stderr,
            "Status: FAIL",
        )
        self.assertIn("Missing expected stocks: 2317, 8069", completed.stdout)

    def test_stock_root_wrapper_failure_exits_one_without_traceback_or_artifact(self) -> None:
        completed = self._run_offline_process(
            "stock",
            str(REPOSITORY_ROOT / "stock_list_smoke_check.py"),
        )

        self.assertEqual(completed.returncode, 1)
        self._assert_failure_output(
            completed.stdout,
            completed.stderr,
            "Status: FAIL",
        )
        self.assertIn("Missing expected stocks: 2317, 8069", completed.stdout)

    def _stock_root_runpy_outcome(self) -> tuple[tuple[str, object], object]:
        with patch.object(stock_cli, "main", return_value=1) as main_mock:
            try:
                runpy.run_path(
                    str(REPOSITORY_ROOT / "stock_list_smoke_check.py"),
                    run_name="__main__",
                )
            except SystemExit as exc:
                outcome = ("system_exit", exc.code)
            else:
                outcome = ("return", None)
        return outcome, main_mock

    def test_stock_root_runpy_invokes_package_main_once_and_propagates_integer_status(self) -> None:
        outcome, main_mock = self._stock_root_runpy_outcome()

        self.assertEqual(outcome, ("system_exit", 1))
        main_mock.assert_called_once_with()

    def test_stock_root_runpy_should_propagate_integer_status(self) -> None:
        outcome, _ = self._stock_root_runpy_outcome()
        self.assertEqual(outcome, ("system_exit", 1))

    def _stock_unified_failure(self) -> tuple[tuple[str, object], str, str, list[str], object]:
        twse, tpex = self._stock_failure_frames()
        stdout = StringIO()
        stderr = StringIO()
        original_argv = sys.argv[:]
        with (
            patch.object(stock_cli.stock_list_updater, "fetch_twse_stock_list", return_value=twse),
            patch.object(stock_cli.stock_list_updater, "fetch_tpex_stock_list", return_value=tpex),
            patch.object(stock_cli.stock_list_updater.requests, "get") as request_mock,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            try:
                result = twstock_cli.main(["stock-list", "smoke-check"])
            except SystemExit as exc:
                outcome = ("system_exit", exc.code)
            else:
                outcome = ("return", result)
        return outcome, stdout.getvalue(), stderr.getvalue(), original_argv, request_mock

    def test_stock_unified_function_failure_returns_integer_one_and_restores_argv(self) -> None:
        outcome, stdout, stderr, original_argv, request_mock = self._stock_unified_failure()

        self.assertEqual(outcome, ("return", 1))
        self.assertEqual(sys.argv, original_argv)
        self._assert_failure_output(stdout, stderr, "Status: FAIL")
        request_mock.assert_not_called()

    def test_stock_unified_function_failure_should_return_integer_one(self) -> None:
        outcome, _, _, _, _ = self._stock_unified_failure()
        self.assertEqual(outcome, ("return", 1))

    def test_stock_unified_module_failure_exits_one_without_traceback_or_artifact(self) -> None:
        completed = self._run_offline_process(
            "stock",
            "-m",
            "tw_stock_tool.cli.twstock_cli",
            "stock-list",
            "smoke-check",
        )

        self.assertEqual(completed.returncode, 1)
        self._assert_failure_output(
            completed.stdout,
            completed.stderr,
            "Status: FAIL",
        )

    def test_stock_argparse_controls_keep_status_two(self) -> None:
        commands = (
            ("-m", "tw_stock_tool.cli.stock_list_smoke_check"),
            (str(REPOSITORY_ROOT / "stock_list_smoke_check.py"),),
            ("-m", "tw_stock_tool.cli.twstock_cli", "stock-list", "smoke-check"),
        )
        for command in commands:
            with self.subTest(command=command):
                self._assert_argparse_failure(
                    self._run_process(*command, "--definitely-invalid-option")
                )

    def test_stock_root_import_alias_is_compatible_and_does_not_execute(self) -> None:
        with patch.object(stock_cli, "main") as main_mock:
            root_module = importlib.import_module("stock_list_smoke_check")

        self.assertIs(root_module, stock_cli)
        self.assertIs(root_module.main, stock_cli.main)
        main_mock.assert_not_called()

    def _price_direct_success(self) -> tuple[tuple[str, object], str, str, object]:
        def fake_download(stock_id: str, **kwargs: object) -> tuple[pd.DataFrame, str]:
            suffix = ".TWO" if stock_id == "8069" else ".TW"
            return _price_frame(), f"{stock_id}{suffix}"

        with (
            patch.object(price_cli.data_loader, "download_tw_stock", side_effect=fake_download) as download_mock,
            patch.object(price_cli.data_loader.requests, "get") as request_mock,
            patch.object(price_cli.data_loader.yf, "download") as yfinance_mock,
        ):
            outcome, stdout, stderr = self._invoke_direct(
                price_cli,
                "price_data_smoke_check.py",
            )
        self.assert_not_called(request_mock, yfinance_mock)
        return outcome, stdout, stderr, download_mock

    def test_price_direct_success_preserves_none_and_output_without_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            before = list(temp_path.iterdir())
            outcome, stdout, stderr, download_mock = self._price_direct_success()
            self.assertEqual(list(temp_path.iterdir()), before)

        self.assertEqual(outcome, ("return", None))
        self.assertIn("Price Data Smoke Check", stdout)
        self.assertEqual(stdout.count("Status=PASS"), 4)
        self.assertEqual(stderr, "")
        self.assertNotIn("Traceback", stdout + stderr)
        self.assertEqual(download_mock.call_count, 4)

    def test_price_direct_handled_failure_returns_integer_one(self) -> None:
        outcome, stdout, stderr, download_mock = self._price_direct_failure()

        self.assertEqual(outcome, ("return", 1))
        self._assert_failure_output(stdout, stderr, "Price Data Smoke Check")
        self.assertIn("Error: Price data smoke check failed.", stdout)
        self.assertEqual(download_mock.call_count, 4)

    def test_price_direct_handled_failure_should_return_integer_one(self) -> None:
        outcome, _, _, _ = self._price_direct_failure()
        self.assertEqual(outcome, ("return", 1))

    def test_price_package_module_failure_exits_one_without_traceback_or_artifact(self) -> None:
        completed = self._run_offline_process(
            "price",
            "-m",
            "tw_stock_tool.cli.price_data_smoke_check",
        )

        self.assertEqual(completed.returncode, 1)
        self._assert_failure_output(
            completed.stdout,
            completed.stderr,
            "Price Data Smoke Check",
        )
        self.assertIn("Error: Price data smoke check failed.", completed.stdout)

    def test_price_root_wrapper_failure_exits_one_without_traceback_or_artifact(self) -> None:
        completed = self._run_offline_process(
            "price",
            str(REPOSITORY_ROOT / "price_data_smoke_check.py"),
        )

        self.assertEqual(completed.returncode, 1)
        self._assert_failure_output(
            completed.stdout,
            completed.stderr,
            "Price Data Smoke Check",
        )
        self.assertIn("Error: Price data smoke check failed.", completed.stdout)

    def _price_root_runpy_outcome(self) -> tuple[tuple[str, object], object]:
        with patch.object(price_cli, "main", return_value=1) as main_mock:
            try:
                runpy.run_path(
                    str(REPOSITORY_ROOT / "price_data_smoke_check.py"),
                    run_name="__main__",
                )
            except SystemExit as exc:
                outcome = ("system_exit", exc.code)
            else:
                outcome = ("return", None)
        return outcome, main_mock

    def test_price_root_runpy_invokes_package_main_once_and_propagates_integer_status(self) -> None:
        outcome, main_mock = self._price_root_runpy_outcome()

        self.assertEqual(outcome, ("system_exit", 1))
        main_mock.assert_called_once_with()

    def test_price_root_runpy_should_propagate_integer_status(self) -> None:
        outcome, _ = self._price_root_runpy_outcome()
        self.assertEqual(outcome, ("system_exit", 1))

    def _price_unified_failure(self) -> tuple[tuple[str, object], str, str, list[str], object]:
        stdout = StringIO()
        stderr = StringIO()
        original_argv = sys.argv[:]
        with (
            patch.object(
                price_cli.data_loader,
                "download_tw_stock",
                return_value=(pd.DataFrame(), "2330.TW"),
            ) as download_mock,
            patch.object(price_cli.data_loader.requests, "get") as request_mock,
            patch.object(price_cli.data_loader.yf, "download") as yfinance_mock,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            try:
                result = twstock_cli.main(["price-smoke-check"])
            except SystemExit as exc:
                outcome = ("system_exit", exc.code)
            else:
                outcome = ("return", result)
        self.assert_not_called(request_mock, yfinance_mock)
        self.assertEqual(download_mock.call_count, 4)
        return outcome, stdout.getvalue(), stderr.getvalue(), original_argv, download_mock

    def test_price_unified_function_failure_returns_integer_one_and_restores_argv(self) -> None:
        outcome, stdout, stderr, original_argv, _ = self._price_unified_failure()

        self.assertEqual(outcome, ("return", 1))
        self.assertEqual(sys.argv, original_argv)
        self._assert_failure_output(stdout, stderr, "Price Data Smoke Check")

    def test_price_unified_function_failure_should_return_integer_one(self) -> None:
        outcome, _, _, _, _ = self._price_unified_failure()
        self.assertEqual(outcome, ("return", 1))

    def test_price_unified_module_failure_exits_one_without_traceback_or_artifact(self) -> None:
        completed = self._run_offline_process(
            "price",
            "-m",
            "tw_stock_tool.cli.twstock_cli",
            "price-smoke-check",
        )

        self.assertEqual(completed.returncode, 1)
        self._assert_failure_output(
            completed.stdout,
            completed.stderr,
            "Price Data Smoke Check",
        )

    def test_price_argparse_controls_keep_status_two(self) -> None:
        commands = (
            ("-m", "tw_stock_tool.cli.price_data_smoke_check"),
            (str(REPOSITORY_ROOT / "price_data_smoke_check.py"),),
            ("-m", "tw_stock_tool.cli.twstock_cli", "price-smoke-check"),
        )
        for command in commands:
            with self.subTest(command=command):
                self._assert_argparse_failure(
                    self._run_process(*command, "--definitely-invalid-option")
                )

    def test_price_root_import_alias_is_compatible_and_does_not_execute(self) -> None:
        with patch.object(price_cli, "main") as main_mock:
            root_module = importlib.import_module("price_data_smoke_check")

        self.assertIs(root_module, price_cli)
        self.assertIs(root_module.main, price_cli.main)
        main_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
