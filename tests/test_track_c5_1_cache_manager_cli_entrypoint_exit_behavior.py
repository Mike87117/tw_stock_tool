from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.cli import twstock_cli
from tw_stock_tool.data import cache_manager


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class CacheManagerCliEntrypointExitCharacterizationTest(unittest.TestCase):
    def _run_direct(self, *args: str) -> tuple[object, str]:
        original_argv = sys.argv[:]
        output = StringIO()
        try:
            sys.argv = ["cache_manager.py", *args]
            with redirect_stdout(output):
                result = cache_manager.main()
        finally:
            sys.argv = original_argv
        return result, output.getvalue()

    def _run_process(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        python_path = [str(REPOSITORY_ROOT), str(REPOSITORY_ROOT / "src")]
        if env.get("PYTHONPATH"):
            python_path.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(python_path)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, *args],
            cwd=REPOSITORY_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def _run_python(self, source: str) -> subprocess.CompletedProcess[str]:
        return self._run_process("-c", textwrap.dedent(source))

    def _assert_temp_dir_unchanged(self, path: Path, before: list[Path]) -> None:
        self.assertEqual(list(path.iterdir()), before)

    def test_direct_list_success_keeps_legacy_none_and_dispatches_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            before = list(temp_path.iterdir())
            with (
                patch.object(cache_manager, "list_cache_files", return_value=[Path("a.csv"), Path("b.csv")]) as listed,
                patch.object(cache_manager, "clear_cache") as cleared,
                patch.object(cache_manager, "cache_summary") as summarized,
            ):
                result, output = self._run_direct("--list")

            self.assertIsNone(result)
            listed.assert_called_once_with()
            cleared.assert_not_called()
            summarized.assert_not_called()
            self.assertIn("a.csv", output)
            self.assertIn("b.csv", output)
            self._assert_temp_dir_unchanged(temp_path, before)

    def test_direct_clear_success_keeps_legacy_none_and_dispatches_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            before = list(temp_path.iterdir())
            with (
                patch.object(cache_manager, "list_cache_files") as listed,
                patch.object(cache_manager, "clear_cache", return_value=2) as cleared,
                patch.object(cache_manager, "cache_summary") as summarized,
            ):
                result, output = self._run_direct("--clear")

            self.assertIsNone(result)
            cleared.assert_called_once_with()
            listed.assert_not_called()
            summarized.assert_not_called()
            self.assertIn("2", output)
            self._assert_temp_dir_unchanged(temp_path, before)

    def test_direct_summary_success_keeps_legacy_none_and_dispatches_once(self) -> None:
        summary = pd.DataFrame([{"File": "a.csv", "Size KB": 1.0}])
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            before = list(temp_path.iterdir())
            with (
                patch.object(cache_manager, "list_cache_files") as listed,
                patch.object(cache_manager, "clear_cache") as cleared,
                patch.object(cache_manager, "cache_summary", return_value=summary) as summarized,
            ):
                result, output = self._run_direct("--summary")

            self.assertIsNone(result)
            summarized.assert_called_once_with()
            listed.assert_not_called()
            cleared.assert_not_called()
            self.assertIn("a.csv", output)
            self.assertIn("Size KB", output)
            self._assert_temp_dir_unchanged(temp_path, before)

    def test_direct_list_failure_should_return_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            before = list(temp_path.iterdir())
            with (
                patch.object(cache_manager, "list_cache_files", side_effect=RuntimeError("controlled list failure")) as listed,
                patch.object(cache_manager, "clear_cache") as cleared,
                patch.object(cache_manager, "cache_summary") as summarized,
            ):
                result, output = self._run_direct("--list")

            listed.assert_called_once_with()
            cleared.assert_not_called()
            summarized.assert_not_called()
            self.assertIn("controlled list failure", output)
            self._assert_temp_dir_unchanged(temp_path, before)
            self.assertEqual(result, 1)

    def test_direct_clear_failure_should_return_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            before = list(temp_path.iterdir())
            with (
                patch.object(cache_manager, "list_cache_files") as listed,
                patch.object(cache_manager, "clear_cache", side_effect=RuntimeError("controlled clear failure")) as cleared,
                patch.object(cache_manager, "cache_summary") as summarized,
            ):
                result, output = self._run_direct("--clear")

            cleared.assert_called_once_with()
            listed.assert_not_called()
            summarized.assert_not_called()
            self.assertIn("controlled clear failure", output)
            self._assert_temp_dir_unchanged(temp_path, before)
            self.assertEqual(result, 1)

    def test_direct_summary_failure_should_return_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            before = list(temp_path.iterdir())
            with (
                patch.object(cache_manager, "list_cache_files") as listed,
                patch.object(cache_manager, "clear_cache") as cleared,
                patch.object(cache_manager, "cache_summary", side_effect=RuntimeError("controlled summary failure")) as summarized,
            ):
                result, output = self._run_direct("--summary")

            summarized.assert_called_once_with()
            listed.assert_not_called()
            cleared.assert_not_called()
            self.assertIn("controlled summary failure", output)
            self._assert_temp_dir_unchanged(temp_path, before)
            self.assertEqual(result, 1)

    def test_package_module_failure_should_exit_one_without_traceback(self) -> None:
        completed = self._run_python(
            """
            import runpy
            import sys
            from tw_stock_tool.data import cache_utils

            def fail():
                raise RuntimeError("controlled summary failure")

            cache_utils.cache_summary = fail
            sys.argv = ["cache_manager.py", "--summary"]
            runpy.run_module("tw_stock_tool.data.cache_manager", run_name="__main__", alter_sys=True)
            """
        )
        combined = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 1)
        self.assertIn("controlled summary failure", combined)
        self.assertNotIn("Traceback", combined)

    def test_root_wrapper_runtime_should_invoke_cache_manager_and_exit_one(self) -> None:
        wrapper = repr(str(REPOSITORY_ROOT / "cache_manager.py"))
        completed = self._run_python(
            f"""
            import runpy
            import sys
            from tw_stock_tool.data import cache_utils

            def fail():
                raise RuntimeError("controlled summary failure")

            cache_utils.cache_summary = fail
            sys.argv = ["cache_manager.py", "--summary"]
            runpy.run_path({wrapper}, run_name="__main__")
            """
        )
        combined = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 1)
        self.assertIn("controlled summary failure", combined)
        self.assertNotIn("Traceback", combined)

    def test_root_wrapper_invalid_argument_should_exit_two(self) -> None:
        completed = self._run_process(str(REPOSITORY_ROOT / "cache_manager.py"), "--definitely-invalid-option")
        combined = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 2)
        self.assertIn("usage:", combined)
        self.assertIn("error", combined.lower())

    def test_package_invalid_argument_is_parser_owned_exit_two(self) -> None:
        completed = self._run_process(
            "-m",
            "tw_stock_tool.data.cache_manager",
            "--definitely-invalid-option",
        )
        combined = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 2)
        self.assertIn("usage:", combined)
        self.assertIn("error", combined.lower())

    def test_unified_invalid_argument_is_parser_owned_exit_two(self) -> None:
        completed = self._run_process(
            "-m",
            "tw_stock_tool.cli.twstock_cli",
            "cache",
            "--definitely-invalid-option",
        )
        combined = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 2)
        self.assertIn("usage:", combined)
        self.assertIn("error", combined.lower())

    def test_unified_function_failure_should_return_one_and_restore_argv(self) -> None:
        original_argv = sys.argv[:]
        output = StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            before = list(Path(temp_dir).iterdir())
            with patch.object(
                cache_manager,
                "cache_summary",
                side_effect=RuntimeError("controlled summary failure"),
            ):
                with redirect_stdout(output):
                    status = twstock_cli.main(["cache", "--summary"])

            self.assertEqual(sys.argv, original_argv)
            self.assertEqual(list(Path(temp_dir).iterdir()), before)
        self.assertIn("controlled summary failure", output.getvalue())
        self.assertEqual(status, 1)

    def test_unified_module_failure_should_exit_one_without_traceback(self) -> None:
        completed = self._run_python(
            """
            import runpy
            import sys
            from tw_stock_tool.data import cache_utils

            def fail():
                raise RuntimeError("controlled summary failure")

            cache_utils.cache_summary = fail
            sys.argv = ["twstock_cli.py", "cache", "--summary"]
            runpy.run_module("tw_stock_tool.cli.twstock_cli", run_name="__main__", alter_sys=True)
            """
        )
        combined = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 1)
        self.assertIn("controlled summary failure", combined)
        self.assertNotIn("Traceback", combined)

    def test_root_import_alias_remains_compatible(self) -> None:
        import cache_manager as root_cache_manager

        self.assertIs(root_cache_manager, cache_manager)
        self.assertIs(root_cache_manager.main, cache_manager.main)


if __name__ == "__main__":
    unittest.main()
