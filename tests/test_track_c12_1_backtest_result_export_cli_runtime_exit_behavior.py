from __future__ import annotations

import ast
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

from tests.subprocess_test_support import run_repo_python
from tw_stock_tool.backtesting.backtest import BacktestError
from tw_stock_tool.backtesting.results import BacktestResult
from tw_stock_tool.backtesting.serialization import BacktestResultSerializationError
from tw_stock_tool.backtesting.serialization_files import load_backtest_result_json_file
from tw_stock_tool.cli import backtest_result_export_cli as export_cli
from tw_stock_tool.cli import twstock_cli

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _result(index: pd.DatetimeIndex) -> BacktestResult:
    return BacktestResult(
        initial_capital=100000.0,
        final_capital=100500.0,
        total_return_pct=0.5,
        buy_hold_return_pct=0.2,
        cagr_pct=0.1,
        exposure_pct=0.5,
        trade_count=0,
        win_rate_pct=0.0,
        max_drawdown_pct=0.0,
        profit_factor=0.0,
        best_trade_pct=0.0,
        worst_trade_pct=0.0,
        avg_hold_days=0.0,
        sharpe_ratio=0.0,
        sortino_ratio=0.0,
        avg_profit=0.0,
        avg_loss=0.0,
        trades=pd.DataFrame(),
        equity_curve=pd.Series([100000.0] * len(index), index=index, dtype=float),
    )


def _args(output: Path, strategy: str = "ma_cross", extra: tuple[str, ...] = ()) -> list[str]:
    return [
        "--stock",
        "2330",
        "--strategy",
        strategy,
        "--output-json",
        str(output),
        *extra,
    ]


class BacktestResultExportRuntimeExitCharacterizationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._tmp_path = Path(self._tmp.name)

    def _path(self, name: str) -> Path:
        return self._tmp_path / name

    def _direct(self, argv: list[str]):
        stdout = StringIO()
        stderr = StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = export_cli.main(argv)
        except SystemExit as exc:
            result = exc
        return result, stdout.getvalue(), stderr.getvalue()

    def _analysis(self, frame: pd.DataFrame) -> SimpleNamespace:
        return SimpleNamespace(indicator_df=frame)

    def _frame(self, *, empty: bool = False) -> pd.DataFrame:
        if empty:
            return pd.DataFrame(index=pd.DatetimeIndex([]))
        index = pd.date_range("2024-01-01", periods=2, freq="D")
        return pd.DataFrame(
            {"Open": [100.0, 101.0], "Close": [100.0, 101.0], "Signal": ["HOLD", "HOLD"]},
            index=index,
        )

    def _bootstrap(self, directory: str, *, unexpected: bool = False) -> Path:
        run_body = 'raise RuntimeError("controlled unexpected failure")' if unexpected else "return _result()"
        content = textwrap.dedent(
            f"""
            from types import SimpleNamespace
            import pandas as pd

            from tw_stock_tool.backtesting.results import BacktestResult
            import tw_stock_tool.analysis.analysis as analysis_module
            import tw_stock_tool.backtesting.backtest as backtest_module
            import tw_stock_tool.backtesting.strategies as strategies_module

            _index = pd.date_range("2024-01-01", periods=2, freq="D")

            def _result():
                return BacktestResult(
                    initial_capital=100000.0,
                    final_capital=100500.0,
                    total_return_pct=0.5,
                    buy_hold_return_pct=0.2,
                    cagr_pct=0.1,
                    exposure_pct=0.5,
                    trade_count=0,
                    win_rate_pct=0.0,
                    max_drawdown_pct=0.0,
                    profit_factor=0.0,
                    best_trade_pct=0.0,
                    worst_trade_pct=0.0,
                    avg_hold_days=0.0,
                    sharpe_ratio=0.0,
                    sortino_ratio=0.0,
                    avg_profit=0.0,
                    avg_loss=0.0,
                    trades=pd.DataFrame(),
                    equity_curve=pd.Series([100000.0, 100500.0], index=_index),
                )

            def _analyze(*args, **kwargs):
                return SimpleNamespace(
                    indicator_df=pd.DataFrame(
                        {{"Open": [100.0, 101.0], "Close": [100.0, 101.0], "Signal": ["HOLD", "HOLD"]}},
                        index=_index,
                    )
                )

            def _strategy(frame, **kwargs):
                return frame.copy()

            def _run(*args, **kwargs):
                {run_body}

            analysis_module.analyze_stock = _analyze
            backtest_module.run_backtest_result = _run
            strategies_module.STRATEGIES.clear()
            strategies_module.STRATEGIES.update({{"ma_cross_strategy": _strategy}})
            """
        ).strip() + "\n"
        path = Path(directory) / "sitecustomize.py"
        path.write_text(content, encoding="utf-8")
        return path

    def _package_process(self, *args: str, bootstrap: Path | None = None):
        extra = (bootstrap,) if bootstrap is not None else ()
        return run_repo_python(
            "-m",
            "tw_stock_tool.cli.backtest_result_export_cli",
            *args,
            extra_pythonpath=extra,
        )

    def _unified_process(self, *args: str, bootstrap: Path | None = None):
        extra = (bootstrap,) if bootstrap is not None else ()
        return run_repo_python(
            "-m",
            "tw_stock_tool.cli.twstock_cli",
            "backtest-result-export",
            *args,
            extra_pythonpath=extra,
        )

    def _assert_no_traceback(self, completed) -> None:
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)

    def test_direct_success_exports_real_artifact_and_preserves_none(self) -> None:
        frame = self._frame()
        result = _result(frame.index)
        output = self._path("result.json")
        strategy = MagicMock(return_value=frame.copy())

        with patch.object(export_cli, "analyze_stock", return_value=self._analysis(frame)):
            with patch.dict(export_cli.STRATEGIES, {"ma_cross_strategy": strategy}, clear=True):
                with patch.object(export_cli, "run_backtest_result", return_value=result) as run:
                    returned, stdout, stderr = self._direct(
                        _args(
                            output,
                            extra=(
                                "--short-window",
                                "7",
                                "--long-window",
                                "30",
                                "--initial-capital",
                                "200000",
                                "--position-size",
                                "0.5",
                            ),
                        )
                    )

        self.assertIsNone(returned)
        self.assertTrue(output.exists())
        loaded = load_backtest_result_json_file(output)
        self.assertEqual(loaded.stock, "2330")
        self.assertEqual(loaded.strategy, "ma_cross_strategy")
        self.assertEqual(loaded.start_date, "2024-01-01")
        self.assertEqual(loaded.end_date, "2024-01-02")
        self.assertEqual(loaded.parameters["requested_strategy"], "ma_cross")
        self.assertEqual(loaded.parameters["resolved_strategy"], "ma_cross_strategy")
        self.assertEqual(loaded.parameters["strategy"], {"short_window": 7, "long_window": 30})
        self.assertEqual(loaded.parameters["backtest"]["initial_capital"], 200000.0)
        self.assertEqual(loaded.parameters["backtest"]["position_size"], 0.5)
        self.assertIn("BacktestResult artifact written", stdout)
        self.assertEqual(stderr, "")
        self.assertNotIn("Traceback", stdout + stderr)
        run.assert_called_once()

    def test_direct_alias_resolution_records_requested_and_resolved_names(self) -> None:
        frame = self._frame()
        result = _result(frame.index)
        strategy = MagicMock(return_value=frame.copy())
        output = self._path("alias.json")

        with patch.object(export_cli, "analyze_stock", return_value=self._analysis(frame)):
            with patch.dict(export_cli.STRATEGIES, {"ma_cross_strategy": strategy}, clear=True):
                with patch.object(export_cli, "run_backtest_result", return_value=result):
                    with patch.object(export_cli, "export_backtest_result_json_file", return_value="written.json") as export:
                        with patch.object(export_cli, "load_backtest_result_json_file") as load:
                            returned, stdout, stderr = self._direct(_args(output, extra=("--overwrite",)))

        self.assertIsNone(returned)
        strategy.assert_called_once_with(frame, short_window=5, long_window=20)
        self.assertEqual(result.strategy, "ma_cross_strategy")
        self.assertEqual(result.parameters["requested_strategy"], "ma_cross")
        self.assertEqual(result.parameters["resolved_strategy"], "ma_cross_strategy")
        export.assert_called_once_with(result, str(output), overwrite=True)
        load.assert_called_once_with("written.json")
        self.assertIn("BacktestResult artifact written: written.json", stdout)
        self.assertEqual(stderr, "")

    def test_direct_empty_execution_preserves_na_dates_and_none(self) -> None:
        frame = self._frame(empty=True)
        result = _result(pd.date_range("2024-01-01", periods=1))
        strategy = MagicMock(return_value=frame)
        output = self._path("empty.json")

        with patch.object(export_cli, "analyze_stock", return_value=self._analysis(frame)):
            with patch.dict(export_cli.STRATEGIES, {"ma_cross_strategy": strategy}, clear=True):
                with patch.object(export_cli, "run_backtest_result", return_value=result):
                    with patch.object(export_cli, "export_backtest_result_json_file", return_value="empty.json"):
                        with patch.object(export_cli, "load_backtest_result_json_file"):
                            returned, stdout, stderr = self._direct(_args(output))

        self.assertIsNone(returned)
        self.assertEqual(result.start_date, "N/A")
        self.assertEqual(result.end_date, "N/A")
        self.assertIn("BacktestResult artifact written", stdout)
        self.assertEqual(stderr, "")

    def test_direct_help_is_system_exit_zero(self) -> None:
        result, stdout, stderr = self._direct(["--help"])
        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 0)
        self.assertIn("historical backtest artifact", stdout)
        self.assertEqual(stderr, "")
        self.assertNotIn("Traceback", stdout + stderr)

    def test_direct_missing_required_arguments_are_system_exit_two(self) -> None:
        result, stdout, stderr = self._direct(["--stock", "2330"])
        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("required", stderr)
        self.assertNotIn("Traceback", stdout + stderr)

    def test_direct_invalid_typed_argument_is_system_exit_two(self) -> None:
        result, stdout, stderr = self._direct(
            [
                "--stock",
                "2330",
                "--strategy",
                "ma_cross",
                "--output-json",
                "typed.json",
                "--initial-capital",
                "not-a-number",
            ]
        )
        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("invalid float value", stderr)
        self.assertNotIn("Traceback", stdout + stderr)

    def test_direct_unknown_strategy_is_system_exit_one_without_analysis(self) -> None:
        with patch.object(export_cli, "analyze_stock") as analyze:
            result, stdout, stderr = self._direct(_args(self._path("unknown.json"), "not_a_strategy"))

        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 1)
        self.assertIn("Unknown strategy", stderr)
        self.assertEqual(stdout, "")
        self.assertNotIn("Traceback", stderr)
        analyze.assert_not_called()

    def test_direct_file_exists_preserves_overwrite_wording_and_skips_readback(self) -> None:
        frame = self._frame()
        result = _result(frame.index)
        strategy = MagicMock(return_value=frame.copy())
        output = self._path("exists.json")

        with patch.object(export_cli, "analyze_stock", return_value=self._analysis(frame)):
            with patch.dict(export_cli.STRATEGIES, {"ma_cross_strategy": strategy}, clear=True):
                with patch.object(export_cli, "run_backtest_result", return_value=result):
                    with patch.object(export_cli, "export_backtest_result_json_file", side_effect=FileExistsError("already exists")):
                        with patch.object(export_cli, "load_backtest_result_json_file") as load:
                            returned, stdout, stderr = self._direct(_args(output))

        self.assertIsInstance(returned, SystemExit)
        self.assertEqual(returned.code, 1)
        self.assertIn("Use --overwrite", stderr)
        self.assertEqual(stdout, "")
        self.assertNotIn("Traceback", stderr)
        load.assert_not_called()

    def test_direct_known_runtime_failures_are_system_exit_one(self) -> None:
        failures = (
            ("FileNotFoundError", FileNotFoundError("missing file")),
            ("IsADirectoryError", IsADirectoryError("directory path")),
            ("PermissionError", PermissionError("permission denied")),
            ("ValueError", ValueError("invalid value")),
            ("BacktestError", BacktestError("backtest failed")),
            ("BacktestResultSerializationError", BacktestResultSerializationError("invalid artifact")),
        )
        for name, failure in failures:
            with self.subTest(name=name):
                with patch.object(export_cli, "analyze_stock", side_effect=failure) as analyze:
                    result, stdout, stderr = self._direct(_args(self._path("failure.json")))
                self.assertIsInstance(result, SystemExit)
                self.assertEqual(result.code, 1)
                self.assertIn(str(failure), stderr)
                self.assertEqual(stdout, "")
                self.assertNotIn("Traceback", stderr)
                analyze.assert_called_once()

    def test_direct_unexpected_exception_uses_existing_fallback(self) -> None:
        failure = RuntimeError("unexpected execution failure")
        with patch.object(export_cli, "analyze_stock", side_effect=failure):
            result, stdout, stderr = self._direct(_args(self._path("unexpected.json")))

        self.assertIsInstance(result, SystemExit)
        self.assertEqual(result.code, 1)
        self.assertIn("error: Unexpected error:", stderr)
        self.assertEqual(stdout, "")
        self.assertNotIn("Traceback", stderr)

    @unittest.expectedFailure
    def test_future_direct_runtime_failure_returns_integer_one(self) -> None:
        with patch.object(export_cli, "analyze_stock", side_effect=FileNotFoundError("missing file")):
            result, _, _ = self._direct(_args(self._path("future.json")))
        self.assertEqual(result, 1)

    def test_package_help_exits_zero(self) -> None:
        completed = self._package_process("--help")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("historical backtest artifact", completed.stdout)
        self._assert_no_traceback(completed)

    def test_package_missing_arguments_exit_two(self) -> None:
        completed = self._package_process("--stock", "2330")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("required", completed.stderr)
        self._assert_no_traceback(completed)

    def test_package_unknown_strategy_exits_one_without_live_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bootstrap = self._bootstrap(tmp)
            output = Path(tmp) / "unknown.json"
            completed = self._package_process(
                "--stock",
                "2330",
                "--strategy",
                "not_a_strategy",
                "--output-json",
                str(output),
                bootstrap=bootstrap.parent,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Unknown strategy", completed.stderr)
        self.assertFalse(output.exists())
        self._assert_no_traceback(completed)

    def test_package_success_uses_controlled_bootstrap_and_real_serializer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bootstrap = self._bootstrap(tmp)
            output = Path(tmp) / "package.json"
            completed = self._package_process(
                "--stock",
                "2330",
                "--strategy",
                "ma_cross",
                "--output-json",
                str(output),
                bootstrap=bootstrap.parent,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(output.exists())
            loaded = load_backtest_result_json_file(output)

        self.assertEqual(loaded.stock, "2330")
        self.assertEqual(loaded.strategy, "ma_cross_strategy")
        self.assertIn("BacktestResult artifact written", completed.stdout)
        self.assertEqual(completed.stderr, "")
        self._assert_no_traceback(completed)

    def test_package_unexpected_exception_exits_one_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bootstrap = self._bootstrap(tmp, unexpected=True)
            output = Path(tmp) / "unexpected.json"
            completed = self._package_process(
                "--stock",
                "2330",
                "--strategy",
                "ma_cross",
                "--output-json",
                str(output),
                bootstrap=bootstrap.parent,
            )
            self.assertFalse(output.exists())

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Unexpected error", completed.stderr)
        self._assert_no_traceback(completed)

    def test_unified_function_success_returns_zero_restores_argv_and_forwards_order(self) -> None:
        original_argv = sys.argv[:]
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        child_args = ["--stock", "2330", "--strategy", "ma_cross", "--output-json", "out.json"]
        with patch.object(export_cli, "main", side_effect=fake_main):
            result = twstock_cli.main(["backtest-result-export", *child_args])

        self.assertEqual(result, 0)
        self.assertEqual(captured, [["backtest_result_export_cli.py", *child_args]])
        self.assertEqual(sys.argv, original_argv)

    def test_unified_function_known_runtime_failure_propagates_system_exit_one_and_restores_argv(self) -> None:
        original_argv = sys.argv[:]

        def fake_main() -> None:
            raise SystemExit(1)

        with patch.object(export_cli, "main", side_effect=fake_main):
            with self.assertRaises(SystemExit) as raised:
                twstock_cli.main(["backtest-result-export", "--stock", "2330"])

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(sys.argv, original_argv)

    def test_unified_function_unexpected_runtime_failure_propagates_system_exit_one_and_restores_argv(self) -> None:
        original_argv = sys.argv[:]

        def fake_main() -> None:
            raise SystemExit(1)

        with patch.object(export_cli, "main", side_effect=fake_main):
            with self.assertRaises(SystemExit) as raised:
                twstock_cli.main(["backtest-result-export", "--stock", "2330", "--output-json", "out.json"])

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(sys.argv, original_argv)

    def test_unified_function_child_parser_failure_remains_system_exit_two(self) -> None:
        original_argv = sys.argv[:]
        with self.assertRaises(SystemExit) as raised:
            twstock_cli.main(["backtest-result-export", "--stock", "2330"])
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(sys.argv, original_argv)

    @unittest.expectedFailure
    def test_future_unified_function_runtime_failure_returns_integer_one(self) -> None:
        def fake_main() -> None:
            raise SystemExit(1)

        with patch.object(export_cli, "main", side_effect=fake_main):
            result = twstock_cli.main(["backtest-result-export", "--stock", "2330"])
        self.assertEqual(result, 1)

    def test_unified_module_help_exits_zero(self) -> None:
        completed = self._unified_process("--help")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("historical backtest artifact", completed.stdout)
        self._assert_no_traceback(completed)

    def test_unified_module_missing_child_arguments_exit_two(self) -> None:
        completed = self._unified_process("--stock", "2330")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("required", completed.stderr)
        self._assert_no_traceback(completed)

    def test_unified_module_unknown_strategy_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bootstrap = self._bootstrap(tmp)
            output = Path(tmp) / "unknown.json"
            completed = self._unified_process(
                "--stock",
                "2330",
                "--strategy",
                "not_a_strategy",
                "--output-json",
                str(output),
                bootstrap=bootstrap.parent,
            )
            self.assertFalse(output.exists())

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Unknown strategy", completed.stderr)
        self._assert_no_traceback(completed)

    def test_unified_module_success_uses_controlled_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bootstrap = self._bootstrap(tmp)
            output = Path(tmp) / "unified.json"
            completed = self._unified_process(
                "--stock",
                "2330",
                "--strategy",
                "ma_cross",
                "--output-json",
                str(output),
                bootstrap=bootstrap.parent,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(output.exists())
            loaded = load_backtest_result_json_file(output)

        self.assertEqual(loaded.stock, "2330")
        self.assertEqual(loaded.strategy, "ma_cross_strategy")
        self.assertIn("BacktestResult artifact written", completed.stdout)
        self.assertEqual(completed.stderr, "")
        self._assert_no_traceback(completed)

    def test_unified_module_unexpected_failure_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bootstrap = self._bootstrap(tmp, unexpected=True)
            output = Path(tmp) / "unified-unexpected.json"
            completed = self._unified_process(
                "--stock",
                "2330",
                "--strategy",
                "ma_cross",
                "--output-json",
                str(output),
                bootstrap=bootstrap.parent,
            )
            self.assertFalse(output.exists())

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Unexpected error", completed.stderr)
        self._assert_no_traceback(completed)
        self.assertFalse((REPOSITORY_ROOT / "backtest_result_export_cli.py").exists())

    def test_package_guard_currently_calls_main_directly(self) -> None:
        source = Path(export_cli.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertTrue(tree.body)
        self.assertIn('if __name__ == "__main__":\n    main()', source)

    @unittest.expectedFailure
    def test_future_package_guard_uses_raise_system_exit_main(self) -> None:
        source = Path(export_cli.__file__).read_text(encoding="utf-8")
        self.assertIn('if __name__ == "__main__":\n    raise SystemExit(main())', source)

    def test_root_wrapper_is_absent_and_not_applicable(self) -> None:
        self.assertFalse((REPOSITORY_ROOT / "backtest_result_export_cli.py").exists())

    def test_unified_route_dispatch_and_console_metadata(self) -> None:
        source = Path(twstock_cli.__file__).read_text(encoding="utf-8")
        self.assertIn('"backtest-result-export"', source)
        self.assertIn("backtest_result_export_cli.main", source)

        import tomllib

        with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as stream:
            pyproject = tomllib.load(stream)
        self.assertEqual(pyproject["project"]["scripts"]["twstock"], "tw_stock_tool.cli.twstock_cli:main")


if __name__ == "__main__":
    unittest.main()
