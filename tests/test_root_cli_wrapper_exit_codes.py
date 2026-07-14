import importlib
from pathlib import Path
import subprocess
import sys
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class RootCliWrapperExitCodeTest(unittest.TestCase):
    def _run_wrapper(self, wrapper: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(REPOSITORY_ROOT / wrapper), *args],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_handled_failures_exit_one(self) -> None:
        cases = (
            ("main.py", ("--stock", ""), "錯誤："),
            ("ai_walk_forward.py", ("--stock", ""), "Error:"),
            ("twstock_cli.py", ("analyze", "--stock", ""), "錯誤："),
        )
        for wrapper, args, expected_output in cases:
            with self.subTest(wrapper=wrapper):
                completed = self._run_wrapper(wrapper, *args)
                self.assertEqual(completed.returncode, 1)
                self.assertIn(expected_output, completed.stdout + completed.stderr)

    def test_help_exits_zero(self) -> None:
        for wrapper in ("main.py", "ai_walk_forward.py", "twstock_cli.py"):
            with self.subTest(wrapper=wrapper):
                completed = self._run_wrapper(wrapper, "--help")
                self.assertEqual(completed.returncode, 0)
                self.assertIn("usage:", completed.stdout + completed.stderr)

    def test_imports_resolve_to_package_implementations(self) -> None:
        modules = (
            ("main", "tw_stock_tool.cli.main"),
            ("ai_walk_forward", "tw_stock_tool.ml.ai_walk_forward"),
            ("twstock_cli", "tw_stock_tool.cli.twstock_cli"),
        )
        for wrapper_name, package_name in modules:
            with self.subTest(wrapper=wrapper_name):
                wrapper = importlib.import_module(wrapper_name)
                package = importlib.import_module(package_name)
                self.assertIs(wrapper, package)
                self.assertIs(wrapper.main, package.main)


if __name__ == "__main__":
    unittest.main()