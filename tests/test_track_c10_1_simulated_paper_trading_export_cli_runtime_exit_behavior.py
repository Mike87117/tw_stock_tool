import ast
import json
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path

from tests.subprocess_test_support import run_repo_python
from tw_stock_tool.cli import simulated_paper_trading_export_cli
from tw_stock_tool.cli import twstock_cli
from tw_stock_tool.paper_trading.models import SimulatedFill, SimulatedOrder
from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult
from tw_stock_tool.paper_trading.serialization_files import (
    export_simulated_paper_trading_result_json_file,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_MODULE = "tw_stock_tool.cli.simulated_paper_trading_export_cli"
UNIFIED_MODULE = "tw_stock_tool.cli.twstock_cli"


class TrackC101SimulatedPaperTradingExportCliRuntimeExitCharacterizationTest(
    unittest.TestCase
):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary_directory.name)
        timestamp = datetime(2024, 1, 2, 9, 30, 0)
        order = SimulatedOrder(
            order_id="order-1",
            symbol="2330",
            side="BUY",
            quantity=100,
            signal_time=timestamp,
            created_at=timestamp,
            strategy="c10_fixture",
        )
        fill = SimulatedFill(
            order_id="order-1",
            symbol="2330",
            side="BUY",
            quantity=100,
            price=100.5,
            filled_at=timestamp,
            fee=2.0,
            tax=0.0,
            slippage=0.0,
        )
        result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=100_000.0,
            final_cash=89_948.0,
            final_position_quantity=100,
            average_cost=100.52,
            realized_pnl=0.0,
            unrealized_pnl=99.999999999999,
            total_equity=100_000.0,
            order_count=1,
            fill_count=1,
            open_position_count=1,
            orders=(order,),
            fills=(fill,),
        )
        self.input_json = self.root / "input.json"
        export_simulated_paper_trading_result_json_file(result, self.input_json)

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
                result = simulated_paper_trading_export_cli.main(argv)
            except SystemExit as raised:
                result = raised
        return result, stdout.getvalue(), stderr.getvalue()

    def _package_process(self, *args: str):
        return run_repo_python("-m", PACKAGE_MODULE, *args)

    def _unified_process(self, *args: str):
        return run_repo_python("-m", UNIFIED_MODULE, *args)

    def test_direct_markdown_success_returns_none_and_writes_artifact(self) -> None:
        output = self.root / "report.md"

        result, stdout, stderr = self._call_direct(
            [str(self.input_json), "--output-markdown", str(output)]
        )

        self.assertIsNone(result)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(
            self._files(),
            {"input.json", "report.md"},
        )
        content = output.read_text(encoding="utf-8")
        self.assertIn("# Simulated Paper Trading Report", content)
        self.assertIn("| Symbol | 2330 |", content)
        self.assertIn("| Order Count | 1 |", content)
        self.assertNotIn("Traceback", content)

    def test_direct_csv_success_returns_none_and_writes_expected_bundle(self) -> None:
        output_directory = self.root / "csv"

        result, stdout, stderr = self._call_direct(
            [
                str(self.input_json),
                "--output-csv-dir",
                str(output_directory),
                "--basename",
                "c10_export",
            ]
        )

        self.assertIsNone(result)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(
            self._files(),
            {
                "input.json",
                "csv/c10_export_summary.csv",
                "csv/c10_export_orders.csv",
                "csv/c10_export_fills.csv",
                "csv/c10_export_rejections.csv",
                "csv/c10_export_trade_log.csv",
            },
        )
        summary = (output_directory / "c10_export_summary.csv").read_text(
            encoding="utf-8"
        )
        self.assertTrue(summary.startswith("metric,value\n"))
        self.assertIn("symbol,2330\n", summary)

    def test_direct_combined_export_returns_none_and_has_no_unrelated_files(self) -> None:
        markdown = self.root / "combined.md"
        output_directory = self.root / "combined_csv"

        result, _, stderr = self._call_direct(
            [
                str(self.input_json),
                "--output-markdown",
                str(markdown),
                "--output-csv-dir",
                str(output_directory),
            ]
        )

        self.assertIsNone(result)
        self.assertEqual(stderr, "")
        self.assertEqual(
            self._files(),
            {
                "input.json",
                "combined.md",
                "combined_csv/simulated_paper_trading_summary.csv",
                "combined_csv/simulated_paper_trading_orders.csv",
                "combined_csv/simulated_paper_trading_fills.csv",
                "combined_csv/simulated_paper_trading_rejections.csv",
                "combined_csv/simulated_paper_trading_trade_log.csv",
            },
        )

    def test_direct_help_is_parser_owned_success(self) -> None:
        result, stdout, stderr = self._call_direct(["--help"])

        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 0)
        self.assertIn("research-only simulated paper trading JSON", stdout)
        self.assertIn("Does not fetch market data", stdout)
        self.assertEqual(stderr, "")
        self.assertEqual(self._files(), {"input.json"})

    def test_direct_missing_output_target_is_parser_error_two(self) -> None:
        result, stdout, stderr = self._call_direct([str(self.input_json)])

        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 2)
        self.assertIn("at least one of --output-markdown or --output-csv-dir", stderr)
        self.assertIn("usage:", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(self._files(), {"input.json"})

    def test_direct_invalid_option_is_parser_error_two(self) -> None:
        result, stdout, stderr = self._call_direct(
            [str(self.input_json), "--not-a-real-option"]
        )

        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 2)
        self.assertIn("unrecognized arguments: --not-a-real-option", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(self._files(), {"input.json"})

    def test_direct_missing_input_has_current_system_exit_one_and_no_artifact(self) -> None:
        missing = self.root / "missing.json"
        output = self.root / "missing.md"

        result, stdout, stderr = self._call_direct(
            [str(missing), "--output-markdown", str(output)]
        )

        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 1)
        self.assertIn("No such file or directory", stderr)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(self._files(), {"input.json"})

    def test_direct_invalid_json_has_current_system_exit_one_and_clean_error(self) -> None:
        invalid = self.root / "invalid.json"
        invalid.write_text("not json", encoding="utf-8")
        output = self.root / "invalid.md"

        result, stdout, stderr = self._call_direct(
            [str(invalid), "--output-markdown", str(output)]
        )

        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 1)
        self.assertIn("Invalid JSON content", stderr)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(self._files(), {"input.json", "invalid.json"})

    def test_direct_invalid_schema_has_current_system_exit_one_and_clean_error(self) -> None:
        invalid = self.root / "invalid_schema.json"
        data = json.loads(self.input_json.read_text(encoding="utf-8"))
        data["schema_version"] = 99
        invalid.write_text(json.dumps(data), encoding="utf-8")
        output = self.root / "invalid_schema.md"

        result, stdout, stderr = self._call_direct(
            [str(invalid), "--output-markdown", str(output)]
        )

        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 1)
        self.assertIn("Unsupported schema_version", stderr)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(self._files(), {"input.json", "invalid_schema.json"})

    def test_direct_existing_output_without_overwrite_has_current_system_exit_one(
        self,
    ) -> None:
        output = self.root / "existing.md"
        output.write_text("keep this content", encoding="utf-8")

        result, stdout, stderr = self._call_direct(
            [str(self.input_json), "--output-markdown", str(output)]
        )

        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 1)
        self.assertIn("File already exists", stderr)
        self.assertIn("Use --overwrite", stderr)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(output.read_text(encoding="utf-8"), "keep this content")
        self.assertEqual(self._files(), {"input.json", "existing.md"})

    @unittest.expectedFailure
    def test_direct_runtime_failure_future_contract_returns_integer_one(self) -> None:
        result, _, _ = self._call_direct(
            [
                str(self.root / "missing.json"),
                "--output-markdown",
                str(self.root / "future.md"),
            ]
        )

        self.assertEqual(result, 1)

    def test_package_module_help_exits_zero_without_traceback(self) -> None:
        completed = self._package_process("--help")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("research-only simulated paper trading JSON", completed.stdout)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(self._files(), {"input.json"})

    def test_package_module_missing_output_is_parser_status_two(self) -> None:
        completed = self._package_process(str(self.input_json))

        self.assertEqual(completed.returncode, 2)
        self.assertIn("at least one of --output-markdown or --output-csv-dir", completed.stderr)
        self.assertIn("usage:", completed.stderr)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(self._files(), {"input.json"})

    def test_package_module_missing_input_is_runtime_status_one(self) -> None:
        output = self.root / "package_missing.md"
        completed = self._package_process(
            str(self.root / "missing.json"),
            "--output-markdown",
            str(output),
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("No such file or directory", completed.stderr)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(self._files(), {"input.json"})

    def test_unified_function_success_returns_zero_and_restores_argv(self) -> None:
        original_argv = sys.argv[:]
        output = self.root / "unified.md"

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            result = twstock_cli.main(
                [
                    "simulated-paper-trading-export",
                    str(self.input_json),
                    "--output-markdown",
                    str(output),
                ]
            )

        self.assertEqual(result, 0)
        self.assertEqual(sys.argv, original_argv)
        self.assertTrue(output.exists())
        self.assertEqual(self._files(), {"input.json", "unified.md"})

    def test_unified_function_missing_input_has_current_system_exit_one_and_restores_argv(
        self,
    ) -> None:
        original_argv = sys.argv[:]

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as raised:
                twstock_cli.main(
                    [
                        "simulated-paper-trading-export",
                        str(self.root / "missing.json"),
                        "--output-markdown",
                        str(self.root / "unified_missing.md"),
                    ]
                )

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(sys.argv, original_argv)
        self.assertEqual(self._files(), {"input.json"})

    @unittest.expectedFailure
    def test_unified_function_runtime_failure_future_contract_returns_integer_one(self) -> None:
        original_argv = sys.argv[:]

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            try:
                result = twstock_cli.main(
                    [
                        "simulated-paper-trading-export",
                        str(self.root / "missing.json"),
                        "--output-markdown",
                        str(self.root / "future_unified.md"),
                    ]
                )
            finally:
                self.assertEqual(sys.argv, original_argv)

        self.assertEqual(result, 1)

    def test_unified_module_help_exits_zero(self) -> None:
        completed = self._unified_process(
            "simulated-paper-trading-export",
            "--help",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("research-only simulated paper trading JSON", completed.stdout)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(self._files(), {"input.json"})

    def test_unified_module_missing_output_is_parser_status_two(self) -> None:
        completed = self._unified_process(
            "simulated-paper-trading-export",
            str(self.input_json),
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("at least one of --output-markdown or --output-csv-dir", completed.stderr)
        self.assertIn("usage:", completed.stderr)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(self._files(), {"input.json"})

    def test_unified_module_missing_input_is_runtime_status_one(self) -> None:
        completed = self._unified_process(
            "simulated-paper-trading-export",
            str(self.root / "missing.json"),
            "--output-markdown",
            str(self.root / "unified_module_missing.md"),
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("No such file or directory", completed.stderr)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)
        self.assertEqual(self._files(), {"input.json"})

    @unittest.expectedFailure
    def test_package_guard_future_contract_propagates_integer_results(self) -> None:
        source_path = Path(simulated_paper_trading_export_cli.__file__)
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertTrue(tree.body)
        self.assertIn(
            'if __name__ == "__main__":\n    raise SystemExit(main())',
            source,
        )

    def test_root_wrapper_is_absent_for_this_command(self) -> None:
        self.assertFalse(
            (REPOSITORY_ROOT / "simulated_paper_trading_export_cli.py").exists()
        )

    def test_console_script_metadata_preserves_unified_mapping(self) -> None:
        with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as stream:
            pyproject = tomllib.load(stream)

        self.assertEqual(
            pyproject["project"]["scripts"]["twstock"],
            "tw_stock_tool.cli.twstock_cli:main",
        )

    def test_exporter_imports_remain_offline_and_research_only(self) -> None:
        source_path = Path(simulated_paper_trading_export_cli.__file__)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imported_modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported_modules.append(node.module)

        for forbidden in ("yfinance", "requests", "pandas", "tw_stock_tool.data"):
            self.assertNotIn(forbidden, imported_modules)


if __name__ == "__main__":
    unittest.main()
