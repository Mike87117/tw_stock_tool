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

    def test_analyze_subcommand_dispatches_to_analyze_cli(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.analyze_cli, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["analyze", "--stock", "2330", "--period", "2y"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["main.py", "--stock", "2330", "--period", "2y"])

    def test_strategy_compare_subcommand_dispatches_to_strategy_compare(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.strategy_compare, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["strategy-compare", "--stock", "2330", "--period", "2y"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["strategy_compare.py", "--stock", "2330", "--period", "2y"])

    def test_parameter_sweep_subcommand_dispatches_to_parameter_sweep_report(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.parameter_sweep_report, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["parameter-sweep", "--stock", "2330", "--period", "2y", "--strategy", "all"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["parameter_sweep_report.py", "--stock", "2330", "--period", "2y", "--strategy", "all"])

    def test_backtest_report_subcommand_dispatches_to_backtest_report(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.backtest_report, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["backtest-report", "--stock", "2330", "--strategy", "ma_cross"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["backtest_report.py", "--stock", "2330", "--strategy", "ma_cross"])

    def test_walk_forward_subcommand_dispatches_to_walk_forward_report(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.walk_forward_report, "main", side_effect=fake_main) as mocked:
            twstock_cli.main([
                "walk-forward",
                "--stock", "2330",
                "--strategy", "ma_cross",
                "--train-days", "252",
                "--test-days", "63",
                "--output-md",
            ])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], [
            "walk_forward_report.py",
            "--stock", "2330",
            "--strategy", "ma_cross",
            "--train-days", "252",
            "--test-days", "63",
            "--output-md",
        ])

    def test_unknown_subcommand_shows_error(self) -> None:
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["unknown"])

        self.assertNotEqual(ctx.exception.code, 0)

    def test_simulated_paper_trading_subcommand_dispatches_to_cli(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch("tw_stock_tool.cli.simulated_paper_trading_cli.main", side_effect=fake_main) as mocked:
            twstock_cli.main([
                "simulated-paper-trading",
                "--stock", "2330",
                "--strategy", "ma_cross",
                "--initial-cash", "100000",
                "--quantity-per-trade", "1000",
            ])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], [
            "simulated_paper_trading_cli.py",
            "--stock", "2330",
            "--strategy", "ma_cross",
            "--initial-cash", "100000",
            "--quantity-per-trade", "1000",
        ])

    def test_simulated_paper_trading_export_subcommand_dispatches_to_cli(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.simulated_paper_trading_export_cli, "main", side_effect=fake_main) as mocked:
            twstock_cli.main([
                "simulated-paper-trading-export",
                "result.json",
                "--output-markdown", "out.md",
            ])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], [
            "simulated_paper_trading_export_cli.py",
            "result.json",
            "--output-markdown", "out.md",
        ])

    def test_backtest_result_export_subcommand_dispatches_to_cli(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch("tw_stock_tool.cli.backtest_result_export_cli.main", side_effect=fake_main) as mocked:
            twstock_cli.main([
                "backtest-result-export",
                "--stock", "2330",
                "--strategy", "ma_cross",
                "--output-json", "out.json",
                "--overwrite",
            ])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], [
            "backtest_result_export_cli.py",
            "--stock", "2330",
            "--strategy", "ma_cross",
            "--output-json", "out.json",
            "--overwrite",
        ])

    def test_backtest_artifact_subcommand_dispatches_to_cli(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.backtest_artifact_cli, "main", side_effect=fake_main) as mocked:
            twstock_cli.main([
                "backtest-artifact",
                "validate",
                "result.json",
            ])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], [
            "backtest_artifact_cli.py",
            "validate",
            "result.json",
        ])

    def test_backtest_artifact_convert_subcommand_dispatches_to_cli(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.backtest_artifact_cli, "main", side_effect=fake_main) as mocked:
            twstock_cli.main([
                "backtest-artifact",
                "convert-to-simulated-paper-trading",
                "in.json",
                "--output-json", "out.json",
            ])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], [
            "backtest_artifact_cli.py",
            "convert-to-simulated-paper-trading",
            "in.json",
            "--output-json", "out.json",
        ])

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
        self.assertIn("analyze", output)
        self.assertIn("strategy-compare", output)
        self.assertIn("parameter-sweep", output)
        self.assertIn("backtest-report", output)
        self.assertIn("walk-forward", output)
        self.assertIn("simulated-paper-trading", output)
        self.assertIn("simulated-paper-trading-export", output)
        self.assertIn("backtest-artifact", output)
        self.assertIn("backtest-result-export", output)

    def test_no_banned_data_freshness_wording_in_cli_help(self) -> None:
        banned_phrases = (
            "guaranteed latest data",
            "guaranteed complete",
            "guaranteed accurate",
            "always latest",
            "real-time guaranteed",
            "refresh always succeeds",
            "fallback data is current",
            "official stock list is complete",
            "investment-grade data",
            "safe to invest",
            "best stocks to buy",
            "investment recommendation",
            "recommended stocks",
            "guaranteed profit",
            "guaranteed return",
        )
        subcommands = [
            ["--help"],
            ["stock-list", "update", "--help"],
            ["cache", "--help"],
            ["scan", "--help"],
            ["simulated-paper-trading-export", "--help"],
            ["backtest-artifact", "--help"],
            ["backtest-result-export", "--help"],
        ]

        for cmd in subcommands:
            out = StringIO()
            with redirect_stdout(out):
                with self.assertRaises(SystemExit) as ctx:
                    twstock_cli.main(cmd)
            self.assertEqual(ctx.exception.code, 0)

            output = out.getvalue().lower()
            for phrase in banned_phrases:
                self.assertNotIn(phrase, output, f"Banned phrase '{phrase}' found in 'twstock {' '.join(cmd)}'")

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

    def test_analyze_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["analyze", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())

    def test_strategy_compare_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["strategy-compare", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())

    def test_parameter_sweep_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["parameter-sweep", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())

    def test_backtest_report_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["backtest-report", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())

    def test_walk_forward_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["walk-forward", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())

    def test_simulated_paper_trading_export_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["simulated-paper-trading-export", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        output = out.getvalue()
        self.assertIn("usage:", output)
        self.assertIn("simulated paper trading", output)

    def test_backtest_result_export_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["backtest-result-export", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        output = out.getvalue()
        self.assertIn("usage:", output)
        self.assertIn("historical backtest artifact", output.lower() + output)

    def test_doctor_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["doctor", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())

    def test_scan_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["scan", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())

    def test_daily_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["daily", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())

    def test_price_smoke_check_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["price-smoke-check", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())

    def test_ai_scan_help_exits_successfully(self) -> None:
        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["ai-scan", "--help"])

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
