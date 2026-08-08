from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import sys
import unittest
from unittest.mock import patch

from tw_stock_tool.cli import twstock_cli


class TwStockCliTest(unittest.TestCase):
    def test_doctor_subcommand_dispatches_to_doctor_main(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.doctor, "main", side_effect=fake_main) as mocked:
            status = twstock_cli.main(["doctor", "--live"])

        self.assertEqual(status, 0)
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

    def test_child_integer_status_is_propagated_and_argv_is_restored(self) -> None:
        original = sys.argv[:]
        captured: list[list[str]] = []

        def fake_main() -> int:
            captured.append(sys.argv[:])
            return 7

        with patch.object(twstock_cli.cache_manager, "main", side_effect=fake_main) as mocked:
            status = twstock_cli.main(["cache", "--summary"])

        self.assertEqual(status, 7)
        mocked.assert_called_once_with()
        self.assertEqual(captured, [["cache_manager.py", "--summary"]])
        self.assertEqual(sys.argv, original)

    def test_analyze_failure_status_is_propagated(self) -> None:
        with patch.object(twstock_cli.analyze_cli, "main", return_value=1) as mocked:
            status = twstock_cli.main(["analyze", "--stock", ""])

        self.assertEqual(status, 1)
        mocked.assert_called_once_with()

    def test_child_system_exit_is_not_swallowed_and_argv_is_restored(self) -> None:
        original = sys.argv[:]
        with patch.object(twstock_cli.doctor, "main", side_effect=SystemExit(3)):
            with self.assertRaises(SystemExit) as raised:
                twstock_cli.main(["doctor"])

        self.assertEqual(raised.exception.code, 3)
        self.assertEqual(sys.argv, original)

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
                "--max-order-notional", "50000",
                "--max-position-quantity", "1000",
                "--max-position-notional", "100000",
            ])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], [
            "simulated_paper_trading_cli.py",
            "--stock", "2330",
            "--strategy", "ma_cross",
            "--initial-cash", "100000",
            "--quantity-per-trade", "1000",
            "--max-order-notional", "50000",
            "--max-position-quantity", "1000",
            "--max-position-notional", "100000",
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
            ["simulated-paper-trading", "--help"],
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

    # Every route's --help must prove it reached its intended owner. Asserting
    # only exit 0 + "usage:" was satisfied by the option-less wrapper stub that
    # Issue #84 B2 describes, so each case pins a command-specific marker.
    HELP_CONTRACT = (
        (["doctor", "--help"], "--live"),
        (["scan", "--help"], "--min-volume-ratio"),
        (["daily", "--help"], "--validation-strategy"),
        (["price-smoke-check", "--help"], "--tpex-stock"),
        (["ai-scan", "--help"], "--n-estimators"),
        (["cache", "--help"], "--summary"),
        (["benchmark", "--help"], "--warmup"),
        (["analyze", "--help"], "--save-chart"),
        (["strategy-compare", "--help"], "--score-sell"),
        (["parameter-sweep", "--help"], "--output-excel"),
        (["backtest-report", "--help"], "--manifest-path"),
        (["walk-forward", "--help"], "--train-days"),
        (["stock-list", "update", "--help"], "--add-suffix"),
        (["stock-list", "smoke-check", "--help"], "--min-tpex"),
        (["stock-list", "clean", "--help"], "--write-clean-file"),
        (["simulated-paper-trading-export", "--help"], "--output-csv-dir"),
        (["backtest-result-export", "--help"], "--output-json"),
    )

    WRAPPER_OWNED_HELP_CONTRACT = (
        (["stock-list", "--help"], "{update,smoke-check,clean}"),
        (["gui", "--help"], "Takes no arguments"),
    )

    def _help_output(self, argv: list[str]) -> str:
        out = StringIO()
        # argparse derives prog from sys.argv[0]; pin it so assertions describe
        # the CLI rather than how the test suite happens to be launched.
        with patch.object(sys, "argv", ["twstock"]), redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(argv)
        self.assertEqual(ctx.exception.code, 0)
        return out.getvalue()

    @staticmethod
    def _unwrapped(text: str) -> str:
        """Collapse argparse line wrapping so a marker can span wrapped lines."""
        return " ".join(text.lower().split())

    def test_passthrough_help_is_answered_by_the_underlying_cli(self) -> None:
        for argv, marker in self.HELP_CONTRACT:
            with self.subTest(argv=argv):
                output = self._help_output(argv)
                self.assertIn("usage:", output)
                self.assertIn(marker, output)
                # The stub this replaces advertised no options at all.
                stub = f"usage: twstock {' '.join(argv[:-1])} [-h]\n\noptions:\n"
                self.assertNotIn(stub, output)

    def test_wrapper_owned_help_is_answered_by_the_unified_cli(self) -> None:
        for argv, marker in self.WRAPPER_OWNED_HELP_CONTRACT:
            with self.subTest(argv=argv):
                output = self._help_output(argv)
                self.assertIn(f"usage: twstock {argv[0]}", output)
                self.assertIn(marker, output)

    def test_safety_scope_text_survives_help_forwarding(self) -> None:
        cases = (
            (["simulated-paper-trading-export", "--help"], "research-only simulated paper trading json artifact"),
            (["backtest-result-export", "--help"], "historical backtest artifact for offline research only"),
            (["simulated-paper-trading", "--help"], "does not connect to brokers, place real orders, or provide investment advice"),
            (["backtest-artifact", "--help"], "or provide investment advice"),
            (["simulated-portfolio-trading", "--help"], "research-only multi-symbol simulated portfolio trading"),
            (["daily-report-artifact", "--help"], "existing offline daily research report json artifact"),
            (["simulated-portfolio-artifact", "--help"], "existing offline simulated portfolio trading json artifact"),
        )
        for argv, marker in cases:
            with self.subTest(argv=argv):
                self.assertIn(marker, self._unwrapped(self._help_output(argv)))

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




class DailyReportArtifactUnifiedCliTests(unittest.TestCase):
    def test_daily_report_artifact_commands_forward_exact_argv(self):
        cases = [
            (
                ["validate", "report.json"],
                ["daily_report_artifact_cli.py", "validate", "report.json"],
            ),
            (
                ["inspect", "report.json"],
                ["daily_report_artifact_cli.py", "inspect", "report.json"],
            ),
            (
                [
                    "export-markdown", "report.json",
                    "--output-markdown", "report.md", "--overwrite",
                ],
                [
                    "daily_report_artifact_cli.py", "export-markdown", "report.json",
                    "--output-markdown", "report.md", "--overwrite",
                ],
            ),
        ]
        for child_args, expected_argv in cases:
            with self.subTest(child_args=child_args):
                captured = []

                def fake_main():
                    captured.append(sys.argv[:])

                with patch.object(
                    twstock_cli.daily_report_artifact_cli,
                    "main",
                    side_effect=fake_main,
                ) as mocked:
                    status = twstock_cli.main(["daily-report-artifact", *child_args])

                self.assertEqual(status, 0)
                mocked.assert_called_once_with()
                self.assertEqual(captured, [expected_argv])

    def test_daily_report_artifact_status_and_sys_argv_restoration(self):
        original = sys.argv[:]
        captured = []

        def fake_main():
            captured.append(sys.argv[:])
            return 9

        with patch.object(
            twstock_cli.daily_report_artifact_cli,
            "main",
            side_effect=fake_main,
        ) as mocked:
            status = twstock_cli.main([
                "daily-report-artifact", "validate", "report.json",
            ])

        self.assertEqual(status, 9)
        mocked.assert_called_once_with()
        self.assertEqual(
            captured,
            [["daily_report_artifact_cli.py", "validate", "report.json"]],
        )
        self.assertEqual(sys.argv, original)

    def test_cli_and_artifact_help_register_command_and_safety(self):
        root = StringIO()
        with redirect_stdout(root), self.assertRaises(SystemExit) as raised:
            twstock_cli.main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("daily-report-artifact", root.getvalue())

        artifact = StringIO()
        with redirect_stdout(artifact), self.assertRaises(SystemExit) as raised:
            twstock_cli.main(["daily-report-artifact", "--help"])
        self.assertEqual(raised.exception.code, 0)
        text = artifact.getvalue().lower()
        self.assertIn("existing offline daily research report json artifact", text)
        for forbidden in (
            "recommended stocks", "best stocks to buy", "guaranteed return",
        ):
            self.assertNotIn(forbidden, text)

    def test_simulated_portfolio_artifact_passthrough_routing(self):
        cases = [
            (
                ["validate", "artifact.json"],
                ["simulated_portfolio_artifact_cli.py", "validate", "artifact.json"],
            ),
            (
                ["inspect", "artifact.json"],
                ["simulated_portfolio_artifact_cli.py", "inspect", "artifact.json"],
            ),
            (
                ["export-markdown", "artifact.json", "--output-markdown", "out.md"],
                ["simulated_portfolio_artifact_cli.py", "export-markdown", "artifact.json", "--output-markdown", "out.md"],
            ),
            (
                ["export-csv", "artifact.json", "--output-csv-dir", "dir"],
                ["simulated_portfolio_artifact_cli.py", "export-csv", "artifact.json", "--output-csv-dir", "dir"],
            ),
        ]
        for child_args, expected_argv in cases:
            with self.subTest(child_args=child_args):
                captured = []

                def fake_main():
                    captured.append(sys.argv[:])
                    return 0

                with patch.object(
                    twstock_cli.simulated_portfolio_artifact_cli,
                    "main",
                    side_effect=fake_main,
                ) as mocked:
                    status = twstock_cli.main(["simulated-portfolio-artifact", *child_args])

                self.assertEqual(status, 0)
                mocked.assert_called_once_with()
                self.assertEqual(captured, [expected_argv])

    def test_simulated_portfolio_artifact_status_and_sys_argv_restoration(self):
        original = sys.argv[:]
        captured = []

        def fake_main():
            captured.append(sys.argv[:])
            return 7

        with patch.object(
            twstock_cli.simulated_portfolio_artifact_cli,
            "main",
            side_effect=fake_main,
        ) as mocked:
            status = twstock_cli.main([
                "simulated-portfolio-artifact", "validate", "artifact.json",
            ])

        self.assertEqual(status, 7)
        mocked.assert_called_once_with()
        self.assertEqual(
            captured,
            [["simulated_portfolio_artifact_cli.py", "validate", "artifact.json"]],
        )
        self.assertEqual(sys.argv, original)

    def test_simulated_portfolio_artifact_help_registration_and_safety(self):
        root = StringIO()
        with redirect_stdout(root), self.assertRaises(SystemExit) as raised:
            twstock_cli.main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("simulated-portfolio-artifact", root.getvalue())

        artifact = StringIO()
        with redirect_stdout(artifact), self.assertRaises(SystemExit) as raised:
            twstock_cli.main(["simulated-portfolio-artifact", "--help"])
        self.assertEqual(raised.exception.code, 0)
        text = artifact.getvalue().lower()
        self.assertIn("existing offline simulated portfolio trading json artifact", text)

    def test_simulated_portfolio_trading_dispatches_to_simulated_portfolio_trading_cli(self):
        captured = []

        def fake_main():
            captured.append(sys.argv[:])
            return 0

        with patch.object(
            twstock_cli.simulated_portfolio_trading_cli,
            "main",
            side_effect=fake_main,
        ) as mocked:
            status = twstock_cli.main([
                "simulated-portfolio-trading",
                "--stocks",
                "2330",
                "2317",
                "--strategy",
                "ma_cross",
                "--initial-cash",
                "1000000",
                "--output-json",
                "portfolio.json",
            ])

        self.assertEqual(status, 0)
        mocked.assert_called_once_with()
        self.assertEqual(
            captured,
            [[
                "simulated_portfolio_trading_cli.py",
                "--stocks",
                "2330",
                "2317",
                "--strategy",
                "ma_cross",
                "--initial-cash",
                "1000000",
                "--output-json",
                "portfolio.json",
            ]],
        )

    def test_simulated_portfolio_trading_help_registration_and_safety(self):
        root = StringIO()
        with redirect_stdout(root), self.assertRaises(SystemExit) as raised:
            twstock_cli.main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("simulated-portfolio-trading", root.getvalue())

        trading = StringIO()
        with redirect_stdout(trading), self.assertRaises(SystemExit) as raised:
            twstock_cli.main(["simulated-portfolio-trading", "--help"])
        self.assertEqual(raised.exception.code, 0)
        text = trading.getvalue().lower()
        self.assertIn("run research-only multi-symbol simulated portfolio trading", text)


    def test_research_cli_manifest_options_passthrough(self) -> None:
        cases = [
            ("scan", twstock_cli.scan_stocks, "scan_stocks.py"),
            ("daily", twstock_cli.daily_report_cli, "daily_report_cli.py"),
            ("backtest-report", twstock_cli.backtest_report, "backtest_report.py"),
        ]
        for command, module, program in cases:
            with self.subTest(command=command):
                captured: list[list[str]] = []

                def fake_main() -> None:
                    captured.append(sys.argv[:])

                with patch.object(module, "main", side_effect=fake_main) as mocked:
                    status = twstock_cli.main([command, "--manifest-path", "custom/manifest.json"])
                self.assertEqual(status, 0)
                mocked.assert_called_once_with()
                self.assertEqual(captured, [[program, "--manifest-path", "custom/manifest.json"]])

    def test_research_cli_passthrough_status_and_argv_contract(self) -> None:
        original = sys.argv[:]
        for command, module in (("scan", twstock_cli.scan_stocks), ("daily", twstock_cli.daily_report_cli), ("backtest-report", twstock_cli.backtest_report)):
            with self.subTest(command=command):
                with patch.object(module, "main", return_value=1) as mocked:
                    self.assertEqual(twstock_cli.main([command]), 1)
                mocked.assert_called_once_with()
                self.assertEqual(sys.argv, original)
if __name__ == "__main__":
    unittest.main()
