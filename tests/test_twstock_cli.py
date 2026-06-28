from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import sys
import unittest
from unittest.mock import patch

import twstock_cli


class TwStockCliTest(unittest.TestCase):
    def test_doctor_subcommand_dispatches_to_doctor_main(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.doctor, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["doctor", "--live"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["doctor.py", "--live"])

    def test_stock_list_update_dispatches_to_updater_main(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.stock_list_updater, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["stock-list", "update", "--market", "all", "--output", "stocks.txt"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["stock_list_updater.py", "--market", "all", "--output", "stocks.txt"])

    def test_stock_list_smoke_check_dispatches_to_smoke_main(self) -> None:
        with patch.object(twstock_cli.stock_list_smoke_check, "main") as mocked:
            twstock_cli.main(["stock-list", "smoke-check"])

        mocked.assert_called_once_with()

    def test_stock_list_clean_subcommand_dispatches_to_clean_stocks(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.clean_stocks, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["stock-list", "clean", "--file", "stocks.txt", "--output", "--write-clean-file"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["clean_stocks.py", "--file", "stocks.txt", "--output", "--write-clean-file"])

    def test_price_smoke_check_dispatches_to_price_main(self) -> None:
        with patch.object(twstock_cli.price_data_smoke_check, "main") as mocked:
            twstock_cli.main(["price-smoke-check"])

        mocked.assert_called_once_with()

    def test_scan_subcommand_dispatches_to_scan_stocks(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.scan_stocks, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["scan", "--auto-stock-list", "--stock-limit", "50"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["scan_stocks.py", "--auto-stock-list", "--stock-limit", "50"])

    def test_daily_subcommand_dispatches_to_daily_report(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.daily_report_cli, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["daily", "--auto-stock-list", "--stock-limit", "50", "--output-md"])

        mocked.assert_called_once_with()
        self.assertEqual(
            captured[0],
            ["daily_report_cli.py", "--auto-stock-list", "--stock-limit", "50", "--output-md"],
        )

    def test_ai_scan_subcommand_dispatches_to_ai_stock_scanner(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.ai_stock_scanner, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["ai-scan", "--auto-stock-list", "--stock-limit", "20"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["ai_stock_scanner.py", "--auto-stock-list", "--stock-limit", "20"])

    def test_cache_subcommand_dispatches_to_cache_manager(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.cache_manager, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["cache", "--summary"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["cache_manager.py", "--summary"])

    def test_cache_clear_subcommand_dispatches_to_cache_manager(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.cache_manager, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["cache", "--clear"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["cache_manager.py", "--clear"])

    def test_benchmark_subcommand_dispatches_to_benchmark(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.benchmark, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["benchmark", "--file", "stocks.txt", "--workers", "8", "--repeat", "3"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["benchmark.py", "--file", "stocks.txt", "--workers", "8", "--repeat", "3"])

    def test_unknown_subcommand_shows_error(self) -> None:
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["unknown"])

        self.assertNotEqual(ctx.exception.code, 0)

    def test_top_level_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["--help"])

        self.assertEqual(ctx.exception.code, 0)
        output = out.getvalue()
        self.assertIn("usage:", output)
        self.assertIn("doctor", output)
        self.assertIn("scan", output)
        self.assertIn("daily", output)
        self.assertIn("stock-list", output)
        self.assertIn("price-smoke-check", output)
        self.assertIn("ai-scan", output)
        self.assertIn("cache", output)
        self.assertIn("benchmark", output)

    def test_stock_list_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["stock-list", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        output = out.getvalue()
        self.assertIn("usage:", output)
        self.assertIn("update", output)
        self.assertIn("smoke-check", output)
        self.assertIn("clean", output)

    def test_stock_list_update_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["stock-list", "update", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())

    def test_stock_list_smoke_check_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["stock-list", "smoke-check", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())

    def test_stock_list_clean_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["stock-list", "clean", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())

    def test_cache_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["cache", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())

    def test_benchmark_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["benchmark", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())

    def test_pyproject_twstock_entrypoint_targets_unified_cli_main(self) -> None:
        import tomllib
        import importlib
        from pathlib import Path

        repo_root = Path(__file__).parent.parent
        pyproject_path = repo_root / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        twstock_target = data.get("project", {}).get("scripts", {}).get("twstock")
        self.assertEqual(twstock_target, "tw_stock_tool.cli.twstock_cli:main")

        module_name, func_name = twstock_target.split(":")
        module = importlib.import_module(module_name)
        target_func = getattr(module, func_name)
        self.assertTrue(callable(target_func))

    def test_root_twstock_cli_wrapper_reexports_package_cli_main(self) -> None:
        import importlib
        import tw_stock_tool.cli.twstock_cli as package_twstock_cli
        from pathlib import Path

        repo_root = Path(__file__).parent.parent
        sys.path.insert(0, str(repo_root))
        try:
            root_twstock_cli = importlib.import_module("twstock_cli")
            self.assertIs(root_twstock_cli.main, package_twstock_cli.main)
        finally:
            sys.path.pop(0)

    def test_root_twstock_cli_wrapper_executes_package_main_when_run_as_script(self) -> None:
        import runpy
        from pathlib import Path

        repo_root = Path(__file__).parent.parent
        script_path = repo_root / "twstock_cli.py"

        with patch("tw_stock_tool.cli.twstock_cli.main") as mock_main:
            runpy.run_path(str(script_path), run_name="__main__")
            mock_main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
