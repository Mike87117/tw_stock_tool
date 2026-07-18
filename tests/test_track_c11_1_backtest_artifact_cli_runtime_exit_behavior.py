import ast
import json
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from tests.subprocess_test_support import run_repo_python
from tw_stock_tool.backtesting.results import BacktestResult
from tw_stock_tool.backtesting.serialization_files import export_backtest_result_json_file
from tw_stock_tool.cli import backtest_artifact_cli
from tw_stock_tool.cli import twstock_cli
from tw_stock_tool.paper_trading.serialization_files import (
    load_simulated_paper_trading_result_json_file,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_MODULE = "tw_stock_tool.cli.backtest_artifact_cli"
UNIFIED_MODULE = "tw_stock_tool.cli.twstock_cli"


class TrackC111BacktestArtifactCliRuntimeExitCharacterizationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary_directory.name)
        self.trades = pd.DataFrame(
            [
                {
                    "Entry Date": "2024-01-01",
                    "Exit Date": "2024-01-05",
                    "Entry Price": 100.0,
                    "Exit Price": 110.0,
                    "Shares": 1000,
                    "PnL": 10000.0,
                }
            ]
        )
        self.result = BacktestResult(
            initial_capital=100000.0,
            final_capital=110000.0,
            total_return_pct=10.0,
            buy_hold_return_pct=5.0,
            cagr_pct=10.0,
            exposure_pct=50.0,
            trade_count=1,
            win_rate_pct=100.0,
            max_drawdown_pct=-5.0,
            profit_factor=2.0,
            best_trade_pct=10.0,
            worst_trade_pct=10.0,
            avg_hold_days=4.0,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            avg_profit=10000.0,
            avg_loss=0.0,
            trades=self.trades,
            equity_curve=pd.Series(
                [100000.0, 110000.0],
                index=["2024-01-01", "2024-01-05"],
                name="Equity",
            ),
            stock="2330",
            strategy="ma_cross",
            parameters={"short_window": 5, "long_window": 20},
            start_date="2024-01-01",
            end_date="2024-01-05",
        )
        self.input_json = self.root / "backtest.json"
        export_backtest_result_json_file(self.result, self.input_json)

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _files(self) -> set[str]:
        return {
            str(path.relative_to(self.root)).replace("\\", "/")
            for path in self.root.rglob("*")
            if path.is_file()
        }

    def _call_direct(self, argv: list[str]) -> tuple[object, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                result = backtest_artifact_cli.main(argv)
            except SystemExit as raised:
                result = raised
        return result, stdout.getvalue(), stderr.getvalue()

    def _package_process(self, *args: str):
        return run_repo_python("-m", PACKAGE_MODULE, *args)

    def _unified_process(self, *args: str):
        return run_repo_python("-m", UNIFIED_MODULE, *args)

    def _write_invalid_json(self) -> Path:
        path = self.root / "invalid.json"
        path.write_text("{not valid json", encoding="utf-8")
        return path

    def _write_invalid_schema(self) -> Path:
        path = self.root / "invalid_schema.json"
        data = json.loads(self.input_json.read_text(encoding="utf-8"))
        data["schema_version"] = 999
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def _write_invalid_trade_artifact(self) -> Path:
        invalid_result = BacktestResult(
            initial_capital=self.result.initial_capital,
            final_capital=self.result.final_capital,
            total_return_pct=self.result.total_return_pct,
            buy_hold_return_pct=self.result.buy_hold_return_pct,
            cagr_pct=self.result.cagr_pct,
            exposure_pct=self.result.exposure_pct,
            trade_count=1,
            win_rate_pct=self.result.win_rate_pct,
            max_drawdown_pct=self.result.max_drawdown_pct,
            profit_factor=self.result.profit_factor,
            best_trade_pct=self.result.best_trade_pct,
            worst_trade_pct=self.result.worst_trade_pct,
            avg_hold_days=self.result.avg_hold_days,
            sharpe_ratio=self.result.sharpe_ratio,
            sortino_ratio=self.result.sortino_ratio,
            avg_profit=self.result.avg_profit,
            avg_loss=self.result.avg_loss,
            trades=pd.DataFrame([{"unexpected": "column"}]),
            equity_curve=self.result.equity_curve,
            stock=self.result.stock,
            strategy=self.result.strategy,
            parameters=self.result.parameters,
            start_date=self.result.start_date,
            end_date=self.result.end_date,
        )
        path = self.root / "invalid_trades.json"
        export_backtest_result_json_file(invalid_result, path)
        return path

    def test_direct_validate_success_returns_none_and_preserves_input(self) -> None:
        before = self.input_json.read_bytes()

        result, stdout, stderr = self._call_direct(
            ["validate", str(self.input_json)]
        )

        self.assertIsNone(result)
        self.assertIn("BacktestResult artifact is valid", stdout)
        self.assertEqual(stderr, "")
        self.assertEqual(self.input_json.read_bytes(), before)
        self.assertEqual(self._files(), {"backtest.json"})

    def test_direct_inspect_success_returns_none_and_prints_summary(self) -> None:
        before = self.input_json.read_bytes()

        result, stdout, stderr = self._call_direct(
            ["inspect", str(self.input_json)]
        )

        self.assertIsNone(result)
        self.assertIn("BacktestResult Artifact Summary", stdout)
        self.assertIn("Stock:           2330", stdout)
        self.assertIn("Strategy:        ma_cross", stdout)
        self.assertIn("Start Date:      2024-01-01", stdout)
        self.assertIn("End Date:        2024-01-05", stdout)
        self.assertIn("Total Return:    10.00%", stdout)
        self.assertIn("Trade Count:     1", stdout)
        self.assertEqual(stderr, "")
        self.assertEqual(self.input_json.read_bytes(), before)
        self.assertEqual(self._files(), {"backtest.json"})

    def test_direct_conversion_success_returns_none_and_roundtrips_output(self) -> None:
        output = self.root / "converted.json"

        result, stdout, stderr = self._call_direct(
            [
                "convert-to-simulated-paper-trading",
                str(self.input_json),
                "--output-json",
                str(output),
            ]
        )

        self.assertIsNone(result)
        self.assertIn("Simulated paper trading artifact written", stdout)
        self.assertEqual(stderr, "")
        converted = load_simulated_paper_trading_result_json_file(output)
        self.assertEqual(converted.symbol, "2330")
        self.assertEqual(converted.initial_cash, 100000.0)
        self.assertEqual(converted.final_cash, 110000.0)
        self.assertEqual(len(converted.orders), 2)
        self.assertEqual(len(converted.fills), 2)
        self.assertEqual(self._files(), {"backtest.json", "converted.json"})

    def test_direct_help_is_parser_owned_success(self) -> None:
        result, stdout, stderr = self._call_direct(["--help"])

        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 0)
        self.assertIn("research-only BacktestResult JSON", stdout)
        self.assertEqual(stderr, "")
        self.assertEqual(self._files(), {"backtest.json"})

    def test_direct_missing_command_is_parser_error_two(self) -> None:
        result, stdout, stderr = self._call_direct([])

        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 2)
        self.assertIn("the following arguments are required: command", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(self._files(), {"backtest.json"})

    def test_direct_unknown_command_is_parser_error_two(self) -> None:
        result, stdout, stderr = self._call_direct(["unknown"])

        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 2)
        self.assertIn("invalid choice: 'unknown'", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(self._files(), {"backtest.json"})

    def test_direct_missing_input_returns_integer_one(self) -> None:
        result, stdout, stderr = self._call_direct(
            ["validate", str(self.root / "missing.json")]
        )

        self.assertEqual(result, 1)
        self.assertIn("No such file or directory", stderr)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(self._files(), {"backtest.json"})

    def test_direct_invalid_json_returns_integer_one(self) -> None:
        invalid = self._write_invalid_json()

        result, stdout, stderr = self._call_direct(["validate", str(invalid)])

        self.assertEqual(result, 1)
        self.assertIn("Invalid JSON", stderr)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(self._files(), {"backtest.json", "invalid.json"})

    def test_direct_invalid_schema_returns_integer_one(self) -> None:
        invalid = self._write_invalid_schema()

        result, stdout, stderr = self._call_direct(["validate", str(invalid)])

        self.assertEqual(result, 1)
        self.assertIn("Unsupported schema_version", stderr)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(self._files(), {"backtest.json", "invalid_schema.json"})

    def test_direct_existing_output_without_overwrite_returns_integer_one(
        self,
    ) -> None:
        output = self.root / "existing.json"
        sentinel = b"keep this artifact"
        output.write_bytes(sentinel)

        result, stdout, stderr = self._call_direct(
            [
                "convert-to-simulated-paper-trading",
                str(self.input_json),
                "--output-json",
                str(output),
            ]
        )

        self.assertEqual(result, 1)
        self.assertIn("Use --overwrite", stderr)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(output.read_bytes(), sentinel)
        self.assertEqual(self._files(), {"backtest.json", "existing.json"})

    def test_direct_existing_output_with_overwrite_succeeds(self) -> None:
        output = self.root / "existing.json"
        output.write_text("old", encoding="utf-8")

        result, stdout, stderr = self._call_direct(
            [
                "convert-to-simulated-paper-trading",
                str(self.input_json),
                "--output-json",
                str(output),
                "--overwrite",
            ]
        )

        self.assertIsNone(result)
        self.assertIn("Simulated paper trading artifact written", stdout)
        self.assertEqual(stderr, "")
        self.assertNotEqual(output.read_text(encoding="utf-8"), "old")
        self.assertEqual(
            load_simulated_paper_trading_result_json_file(output).symbol,
            "2330",
        )

    def test_direct_output_directory_returns_integer_one(self) -> None:
        output_directory = self.root / "output-directory"
        output_directory.mkdir()

        result, stdout, stderr = self._call_direct(
            [
                "convert-to-simulated-paper-trading",
                str(self.input_json),
                "--output-json",
                str(output_directory),
            ]
        )

        self.assertEqual(result, 1)
        self.assertIn("Use --overwrite", stderr)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(self._files(), {"backtest.json"})

    def test_direct_converter_failure_returns_integer_one(self) -> None:
        invalid = self._write_invalid_trade_artifact()
        output = self.root / "invalid-conversion.json"

        result, stdout, stderr = self._call_direct(
            [
                "convert-to-simulated-paper-trading",
                str(invalid),
                "--output-json",
                str(output),
            ]
        )

        self.assertEqual(result, 1)
        self.assertIn("Missing required trade column", stderr)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(
            self._files(),
            {"backtest.json", "invalid_trades.json"},
        )

    def test_direct_runtime_failure_returns_integer_one(self) -> None:
        result, _, _ = self._call_direct(
            ["validate", str(self.root / "missing.json")]
        )

        self.assertEqual(result, 1)

    def test_package_module_help_exits_zero(self) -> None:
        completed = self._package_process("--help")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("research-only BacktestResult JSON", completed.stdout)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(self._files(), {"backtest.json"})

    def test_package_module_missing_command_exits_two(self) -> None:
        completed = self._package_process()

        self.assertEqual(completed.returncode, 2)
        self.assertIn("the following arguments are required: command", completed.stderr)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(self._files(), {"backtest.json"})

    def test_package_module_missing_input_exits_one(self) -> None:
        completed = self._package_process(
            "validate",
            str(self.root / "missing.json"),
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("No such file or directory", completed.stderr)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(self._files(), {"backtest.json"})

    def test_package_module_invalid_json_and_schema_exit_one(self) -> None:
        invalid_json = self._write_invalid_json()
        invalid_schema = self._write_invalid_schema()

        for path, expected in (
            (invalid_json, "Invalid JSON"),
            (invalid_schema, "Unsupported schema_version"),
        ):
            with self.subTest(path=path.name):
                completed = self._package_process("validate", str(path))
                self.assertEqual(completed.returncode, 1)
                self.assertIn(expected, completed.stderr)
                self.assertNotIn("Traceback", completed.stdout + completed.stderr)

    def test_package_module_successful_validation_exits_zero(self) -> None:
        completed = self._package_process("validate", str(self.input_json))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("BacktestResult artifact is valid", completed.stdout)
        self.assertEqual(completed.stderr, "")
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(self._files(), {"backtest.json"})

    def test_package_module_successful_conversion_exits_zero(self) -> None:
        output = self.root / "package-converted.json"
        completed = self._package_process(
            "convert-to-simulated-paper-trading",
            str(self.input_json),
            "--output-json",
            str(output),
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Simulated paper trading artifact written", completed.stdout)
        self.assertEqual(completed.stderr, "")
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(
            load_simulated_paper_trading_result_json_file(output).symbol,
            "2330",
        )
        self.assertEqual(self._files(), {"backtest.json", "package-converted.json"})

    def test_unified_function_validate_success_returns_zero_and_restores_argv(self) -> None:
        original_argv = sys.argv[:]

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            result = twstock_cli.main(
                ["backtest-artifact", "validate", str(self.input_json)]
            )

        self.assertEqual(result, 0)
        self.assertEqual(sys.argv, original_argv)
        self.assertEqual(self._files(), {"backtest.json"})

    def test_unified_function_inspect_success_returns_zero(self) -> None:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            result = twstock_cli.main(
                ["backtest-artifact", "inspect", str(self.input_json)]
            )

        self.assertEqual(result, 0)
        self.assertEqual(self._files(), {"backtest.json"})

    def test_unified_function_conversion_success_returns_zero(self) -> None:
        output = self.root / "unified-converted.json"

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            result = twstock_cli.main(
                [
                    "backtest-artifact",
                    "convert-to-simulated-paper-trading",
                    str(self.input_json),
                    "--output-json",
                    str(output),
                ]
            )

        self.assertEqual(result, 0)
        self.assertEqual(
            load_simulated_paper_trading_result_json_file(output).symbol,
            "2330",
        )
        self.assertEqual(self._files(), {"backtest.json", "unified-converted.json"})

    def test_unified_function_missing_input_returns_integer_one_and_restores_argv(
        self,
    ) -> None:
        original_argv = sys.argv[:]

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            result = twstock_cli.main(
                [
                    "backtest-artifact",
                    "validate",
                    str(self.root / "missing.json"),
                ]
            )

        self.assertEqual(result, 1)
        self.assertEqual(sys.argv, original_argv)
        self.assertEqual(self._files(), {"backtest.json"})

    def test_unified_function_invalid_artifact_returns_integer_one(self) -> None:
        invalid = self._write_invalid_json()

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as stderr:
            result = twstock_cli.main(["backtest-artifact", "validate", str(invalid)])

        self.assertEqual(result, 1)
        self.assertIn("Invalid JSON content", stderr.getvalue())
        self.assertEqual(self._files(), {"backtest.json", "invalid.json"})

    def test_unified_function_parser_failure_remains_system_exit_two(self) -> None:
        original_argv = sys.argv[:]

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as raised:
                twstock_cli.main(["backtest-artifact", "validate"])

        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(sys.argv, original_argv)
        self.assertEqual(self._files(), {"backtest.json"})

    def test_unified_function_forwards_child_arguments_in_order(self) -> None:
        original_argv = sys.argv[:]
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(backtest_artifact_cli, "main", side_effect=fake_main):
            result = twstock_cli.main(
                [
                    "backtest-artifact",
                    "convert-to-simulated-paper-trading",
                    "input.json",
                    "--output-json",
                    "output.json",
                    "--overwrite",
                ]
            )

        self.assertEqual(result, 0)
        self.assertEqual(
            captured,
            [
                [
                    "backtest_artifact_cli.py",
                    "convert-to-simulated-paper-trading",
                    "input.json",
                    "--output-json",
                    "output.json",
                    "--overwrite",
                ]
            ],
        )
        self.assertEqual(sys.argv, original_argv)

    def test_unified_function_runtime_failure_returns_integer_one(self) -> None:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            result = twstock_cli.main(
                [
                    "backtest-artifact",
                    "validate",
                    str(self.root / "missing.json"),
                ]
            )

        self.assertEqual(result, 1)

    def test_unified_module_help_exits_zero(self) -> None:
        completed = self._unified_process("backtest-artifact", "--help")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("research-only BacktestResult JSON artifact", completed.stdout)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(self._files(), {"backtest.json"})

    def test_unified_module_parser_failure_exits_two(self) -> None:
        completed = self._unified_process("backtest-artifact", "validate")

        self.assertEqual(completed.returncode, 2)
        self.assertIn("the following arguments are required: input_json", completed.stderr)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(self._files(), {"backtest.json"})

    def test_unified_module_runtime_failure_exits_one(self) -> None:
        completed = self._unified_process(
            "backtest-artifact",
            "validate",
            str(self.root / "missing.json"),
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("No such file or directory", completed.stderr)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(self._files(), {"backtest.json"})

    def test_unified_module_successful_validation_exits_zero(self) -> None:
        completed = self._unified_process(
            "backtest-artifact",
            "validate",
            str(self.input_json),
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("BacktestResult artifact is valid", completed.stdout)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(self._files(), {"backtest.json"})

    def test_unified_module_successful_conversion_exits_zero(self) -> None:
        output = self.root / "unified-module-converted.json"
        completed = self._unified_process(
            "backtest-artifact",
            "convert-to-simulated-paper-trading",
            str(self.input_json),
            "--output-json",
            str(output),
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Simulated paper trading artifact written", completed.stdout)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(
            load_simulated_paper_trading_result_json_file(output).symbol,
            "2330",
        )
        self.assertEqual(
            self._files(),
            {"backtest.json", "unified-module-converted.json"},
        )

    def test_package_guard_propagates_integer_results(self) -> None:
        source = Path(backtest_artifact_cli.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)

        self.assertTrue(tree.body)
        self.assertIn(
            'if __name__ == "__main__":\n    raise SystemExit(main())',
            source,
        )

    def test_root_wrapper_is_not_applicable_and_absent(self) -> None:
        self.assertFalse((REPOSITORY_ROOT / "backtest_artifact_cli.py").exists())

    def test_console_script_metadata_preserves_unified_mapping(self) -> None:
        with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as stream:
            pyproject = tomllib.load(stream)

        self.assertEqual(
            pyproject["project"]["scripts"]["twstock"],
            "tw_stock_tool.cli.twstock_cli:main",
        )

    def test_cli_source_imports_remain_offline_and_research_only(self) -> None:
        source_path = Path(backtest_artifact_cli.__file__)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imported_modules: list[str | None] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported_modules.append(node.module)

        for forbidden in ("yfinance", "requests", "tw_stock_tool.data", "tw_stock_tool.broker"):
            self.assertNotIn(forbidden, imported_modules)


if __name__ == "__main__":
    unittest.main()
