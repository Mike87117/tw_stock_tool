from __future__ import annotations

import hashlib
import importlib
import os
from pathlib import Path
import sys
import textwrap
import unittest
from unittest.mock import patch, sentinel


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
INHERITED_PYTHONPATH = "inherited-pythonpath"

C8_SITE_CUSTOMIZE = """import requests


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return [{"Code": "2330", "Name": "TSMC", "Type": "24"}]


def _fake_get(*args, **kwargs):
    return _Response()


requests.get = _fake_get
"""

C9_STOCK_SITE_CUSTOMIZE = """import requests


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return [{"Code": "2330", "Name": "TSMC", "Type": "24"}]


def _get(*args, **kwargs):
    return _Response()


requests.get = _get
"""

C9_PRICE_SITE_CUSTOMIZE = """import pandas as pd
import requests
import yfinance


def _download(*args, **kwargs):
    return pd.DataFrame()


def _get(*args, **kwargs):
    raise RuntimeError("controlled offline HTTP request")


yfinance.download = _download
requests.get = _get
"""


class TrackP31SubprocessTestHelperCharacterizationTest(unittest.TestCase):
    def _assert_environment(
        self,
        environment: dict[str, str],
        expected_pythonpath: list[str],
        expected_bytecode: str | None,
    ) -> None:
        self.assertEqual(
            environment["PYTHONPATH"],
            os.pathsep.join(expected_pythonpath),
        )
        if expected_bytecode is None:
            self.assertNotIn("PYTHONDONTWRITEBYTECODE", environment)
        else:
            self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], expected_bytecode)

    def _assert_process_snapshot(
        self,
        module: object,
        case_type: type[unittest.TestCase],
        args: tuple[str, ...],
        expected_pythonpath: list[str],
        expected_bytecode: str | None,
        expected_errors: str | None,
    ) -> None:
        case = case_type("runTest")
        with (
            patch.object(module.os, "environ", {"PYTHONPATH": INHERITED_PYTHONPATH}),
            patch.object(module.subprocess, "run", return_value=sentinel.completed) as run,
        ):
            result = case._run_process(*args)

        self.assertIs(result, sentinel.completed)
        self.assertEqual(run.call_args.args, ([sys.executable, *args],))
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["cwd"], module.REPOSITORY_ROOT)
        self._assert_environment(kwargs["env"], expected_pythonpath, expected_bytecode)
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["text"])
        self.assertFalse(kwargs["check"])
        if expected_errors is None:
            self.assertNotIn("errors", kwargs)
        else:
            self.assertEqual(kwargs["errors"], expected_errors)

    def test_each_local_process_helper_preserves_its_exact_invocation_snapshot(self) -> None:
        modules = (
            (
                "tests.test_track_c4_1_scanner_cli_exit_behavior",
                "TrackC41ScannerCliExitBehaviorTest",
                ("--flag", "value"),
                [str(REPOSITORY_ROOT / "src"), INHERITED_PYTHONPATH],
                None,
                "replace",
            ),
            (
                "tests.test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior",
                "CacheManagerCliEntrypointExitCharacterizationTest",
                ("--flag", "value"),
                [str(REPOSITORY_ROOT), str(REPOSITORY_ROOT / "src"), INHERITED_PYTHONPATH],
                "1",
                None,
            ),
            (
                "tests.test_track_c6_1_benchmark_cli_runtime_exit_behavior",
                "BenchmarkCliRuntimeExitBehaviorCharacterizationTest",
                ("--flag", "value"),
                [str(REPOSITORY_ROOT), str(REPOSITORY_ROOT / "src"), INHERITED_PYTHONPATH],
                "1",
                "replace",
            ),
            (
                "tests.test_track_c7_1_clean_stocks_cli_runtime_exit_behavior",
                "CleanStocksCliRuntimeExitBehaviorCharacterizationTest",
                ("--flag", "value"),
                [str(REPOSITORY_ROOT), str(REPOSITORY_ROOT / "src"), INHERITED_PYTHONPATH],
                "1",
                "replace",
            ),
            (
                "tests.test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior",
                "StockListUpdaterCliRuntimeExitBehaviorCharacterizationTest",
                ("--flag", "value"),
                [str(REPOSITORY_ROOT), str(REPOSITORY_ROOT / "src"), INHERITED_PYTHONPATH],
                "1",
                "replace",
            ),
            (
                "tests.test_track_c9_1_smoke_check_cli_runtime_exit_behavior",
                "TrackC91SmokeCheckCliRuntimeExitBehaviorTest",
                ("--flag", "value"),
                [str(REPOSITORY_ROOT), str(REPOSITORY_ROOT / "src"), INHERITED_PYTHONPATH],
                "1",
                "replace",
            ),
        )
        for module_name, case_name, args, pythonpath, bytecode, errors in modules:
            with self.subTest(module=module_name):
                module = importlib.import_module(module_name)
                self._assert_process_snapshot(
                    module,
                    getattr(module, case_name),
                    args,
                    pythonpath,
                    bytecode,
                    errors,
                )

    def test_c5_inline_source_is_dedented_and_delegated_unchanged(self) -> None:
        module = importlib.import_module(
            "tests.test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior"
        )
        case = module.CacheManagerCliEntrypointExitCharacterizationTest("runTest")
        source = """
                print('first')
                  print('second')
        """
        expected = textwrap.dedent(source)
        with patch.object(case, "_run_process", return_value=sentinel.completed) as run:
            result = case._run_python(source)

        self.assertIs(result, sentinel.completed)
        run.assert_called_once_with("-c", expected)

    def _assert_offline_snapshot(
        self,
        module: object,
        case: unittest.TestCase,
        args: tuple[str, ...],
        expected_source: str,
        mode: str | None = None,
    ) -> None:
        with (
            patch.object(module.os, "environ", {"PYTHONPATH": INHERITED_PYTHONPATH}),
            patch.object(module.Path, "write_text", autospec=True) as write_text,
            patch.object(
                module.tempfile,
                "TemporaryDirectory",
                wraps=module.tempfile.TemporaryDirectory,
            ) as temporary_directory,
            patch.object(module.subprocess, "run", return_value=sentinel.completed) as run,
        ):
            if mode is None:
                returned = case._run_offline_process(*args)
            else:
                returned = case._run_offline_process(mode, *args)

        write_text.assert_called_once()
        write_args, write_kwargs = write_text.call_args
        helper_path = write_args[0].parent
        if isinstance(returned, tuple):
            result, returned_helper_path = returned
            self.assertEqual(returned_helper_path, helper_path)
        else:
            result = returned
        self.assertIs(result, sentinel.completed)
        self.assertFalse(helper_path.exists())
        temporary_directory.assert_called_once_with()
        self.assertEqual(write_args[0].name, "sitecustomize.py")
        self.assertEqual(write_args[1], expected_source)
        self.assertEqual(write_kwargs, {"encoding": "utf-8"})

        self.assertEqual(run.call_args.args, ([sys.executable, *args],))
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["cwd"], module.REPOSITORY_ROOT)
        self._assert_environment(
            kwargs["env"],
            [
                str(helper_path),
                str(REPOSITORY_ROOT),
                str(REPOSITORY_ROOT / "src"),
                INHERITED_PYTHONPATH,
            ],
            "1",
        )
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["text"])
        self.assertEqual(kwargs["errors"], "replace")
        self.assertFalse(kwargs["check"])

    def test_c8_offline_sitecustomize_and_cleanup_are_local_and_exact(self) -> None:
        module = importlib.import_module(
            "tests.test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior"
        )
        case = module.StockListUpdaterCliRuntimeExitBehaviorCharacterizationTest("runTest")
        self._assert_offline_snapshot(
            module,
            case,
            ("-m", "tw_stock_tool.cli.stock_list_updater"),
            C8_SITE_CUSTOMIZE,
        )

    def test_c9_stock_and_price_offline_sources_remain_distinct(self) -> None:
        module = importlib.import_module(
            "tests.test_track_c9_1_smoke_check_cli_runtime_exit_behavior"
        )
        case = module.TrackC91SmokeCheckCliRuntimeExitBehaviorTest("runTest")
        modes = (
            ("stock", C9_STOCK_SITE_CUSTOMIZE, "tw_stock_tool.cli.stock_list_smoke_check"),
            ("price", C9_PRICE_SITE_CUSTOMIZE, "tw_stock_tool.cli.price_data_smoke_check"),
        )
        for mode, expected_source, command in modes:
            with self.subTest(mode=mode):
                self.assertEqual(case._sitecustomize_text(mode), expected_source)
                digest = hashlib.sha256(expected_source.encode("utf-8")).hexdigest()
                self.assertEqual(
                    digest,
                    {
                        "stock": "d78209dc93a4ba8e9deb44f1aa1111759137451532aaf5fbce8ca2d2b3d3a4bd",
                        "price": "323cbb507547117f8ef996ea949b6f58ca896c72e1f869526701a1b23ca82b1b",
                    }[mode],
                )
                self._assert_offline_snapshot(
                    module,
                    case,
                    ("-m", command),
                    expected_source,
                    mode=mode,
                )

    def test_offline_sources_encode_their_intended_dependency_boundaries(self) -> None:
        self.assertIn("import requests", C8_SITE_CUSTOMIZE)
        self.assertNotIn("yfinance", C8_SITE_CUSTOMIZE)
        self.assertIn("requests.get = _get", C9_STOCK_SITE_CUSTOMIZE)
        self.assertNotIn("pandas", C9_STOCK_SITE_CUSTOMIZE)
        self.assertIn("yfinance.download = _download", C9_PRICE_SITE_CUSTOMIZE)
        self.assertIn("return pd.DataFrame()", C9_PRICE_SITE_CUSTOMIZE)
        self.assertIn("controlled offline HTTP request", C9_PRICE_SITE_CUSTOMIZE)


if __name__ == "__main__":
    unittest.main()
