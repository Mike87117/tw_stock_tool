import argparse
import ast
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from io import StringIO
import importlib
import inspect
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.cli import twstock_cli
from tw_stock_tool.backtesting import parameter_sweep, strategy_compare, walk_forward
from tw_stock_tool.ml import ai_stock_scanner, ml_dataset
from tw_stock_tool.reports import ai_prediction_report


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ENV = os.environ.copy()
PYTHON_ENV["PYTHONPATH"] = os.pathsep.join(
    value for value in (str(REPOSITORY_ROOT / "src"), PYTHON_ENV.get("PYTHONPATH")) if value
)


def _args(**values: object) -> argparse.Namespace:
    return argparse.Namespace(**values)


DIRECT_CASES = (
    {
        "name": "parameter_sweep",
        "module": parameter_sweep,
        "args": _args(
            stock="2330", period="1y", strategy="ma_cross", sort_by="Total Return %", top=1,
            force_refresh=False, output=None, output_excel=None, stop_loss_pct=None,
            take_profit_pct=None, max_hold_days=None, position_size=1.0,
        ),
        "boundary": "run_parameter_sweep",
        "success": pd.DataFrame({"Result": [1]}),
        "exports": ("export_parameter_sweep", "export_parameter_sweep_excel"),
        "marker": "Result",
        "error": "Error:",
    },
    {
        "name": "strategy_compare",
        "module": strategy_compare,
        "args": _args(
            stock="2330", period="1y", stop_loss=None, take_profit=None, max_hold_days=None,
            position_size=1.0, ma_short=5, ma_long=20, rsi_buy_below=30, rsi_sell_above=70,
            score_buy=None, score_sell=None, force_refresh=False, output=None, output_excel=None,
        ),
        "boundary": "compare_strategies",
        "success": pd.DataFrame({"Strategy": ["ma_cross"]}),
        "exports": ("export_strategy_compare",),
        "marker": "Strategy",
        "error": "Error:",
    },
    {
        "name": "walk_forward",
        "module": walk_forward,
        "args": _args(
            stock="2330", period="1y", strategy="ma_cross", train_days=10, test_days=5,
            step_days=None, sort_by="Train Sharpe Ratio", force_refresh=False, output=None,
            stop_loss_pct=None, take_profit_pct=None, max_hold_days=None, position_size=1.0,
        ),
        "boundary": "run_walk_forward",
        "success": pd.DataFrame({"Window": [1]}),
        "exports": ("export_walk_forward_excel",),
        "marker": "Walk-forward results are historical validation only",
        "error": "Error:",
    },
    {
        "name": "ai_stock_scanner",
        "module": ai_stock_scanner,
        "args": _args(
            stocks=["2330"], file=None, auto_stock_list=False, stock_market="all",
            stock_list_output="stocks.txt", allow_partial_stock_list=False, stock_limit=None,
            stock_sample=None, period="1y", horizon=5, train_size=10, test_size=5,
            step_size=None, workers=1, force_refresh=False, dropna=True, n_estimators=5,
            random_state=42, output=None,
        ),
        "boundary": "collect_stock_ids",
        "success": ["2330"],
        "success_patches": {"scan_ai_stocks": pd.DataFrame({"Stock": ["2330"]})},
        "exports": ("export_ai_stock_ranking",),
        "marker": "AI stock scanner is for research only",
        "error": "Error:",
    },
    {
        "name": "ml_dataset",
        "module": ml_dataset,
        "args": _args(
            stock="2330", period="1y", horizon=5, force_refresh=False, dropna=True, output_csv=None,
        ),
        "boundary": "build_ml_dataset",
        "success": pd.DataFrame({"Feature": [1]}),
        "exports": ("export_ml_dataset",),
        "marker": "This dataset is for research only",
        "error": "Error:",
    },
    {
        "name": "ai_prediction_report",
        "module": ai_prediction_report,
        "args": _args(
            stock="2330", period="1y", horizon=5, train_size=10, test_size=5, step_size=None,
            force_refresh=False, dropna=True, n_estimators=5, random_state=42, output_excel=None,
        ),
        "boundary": "run_ai_prediction_report",
        "success": {
            "Summary": pd.DataFrame({"Stock": ["2330"]}),
            "Detail": pd.DataFrame({"Window": [1]}),
        },
        "exports": ("export_ai_prediction_report_excel",),
        "marker": "Summary",
        "extra_markers": ("Detail",),
        "error": "Error:",
    },
)


PACKAGE_FILES = {
    "parameter_sweep": "src/tw_stock_tool/backtesting/parameter_sweep.py",
    "strategy_compare": "src/tw_stock_tool/backtesting/strategy_compare.py",
    "walk_forward": "src/tw_stock_tool/backtesting/walk_forward.py",
    "ai_stock_scanner": "src/tw_stock_tool/ml/ai_stock_scanner.py",
    "ml_dataset": "src/tw_stock_tool/ml/ml_dataset.py",
    "ai_prediction_report": "src/tw_stock_tool/reports/ai_prediction_report.py",
}

def _parse(module: object, argv: list[str]) -> argparse.Namespace:
    parser = module._parse_args
    if not inspect.signature(parser).parameters:
        with patch.object(sys, "argv", ["test-program", *argv]):
            return parser()
    return parser(argv)


def _run_subprocess(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPOSITORY_ROOT,
        env=PYTHON_ENV,
        capture_output=True,
        text=True,
        check=False,
    )


def _package_harness(spec: dict[str, object], success: bool) -> str:
    module = spec["module"]
    args = spec["args"].__dict__
    boundary = spec["boundary"]
    exports = spec["exports"]
    if spec["name"] == "ai_stock_scanner" and success:
        setup = (
            "module.collect_stock_ids = lambda *args, **kwargs: ['2330']\n"
            "module.scan_ai_stocks = lambda *args, **kwargs: module.pd.DataFrame({'Stock': ['2330']})"
        )
    elif success:
        setup = f"module.{boundary} = lambda *args, **kwargs: module.pd.DataFrame({{'Value': [1]}})"
        if spec["name"] == "ai_prediction_report":
            setup = (
                "module.run_ai_prediction_report = lambda *args, **kwargs: "
                "{'Summary': module.pd.DataFrame({'Stock': ['2330']}), 'Detail': module.pd.DataFrame({'Window': [1]})}"
            )
    else:
        setup = (
            "def controlled_failure(*args, **kwargs):\n"
            "    raise RuntimeError('offline controlled failure')\n"
            f"module.{boundary} = controlled_failure"
        )
    export_setup = "\n".join(
        f"module.{name} = lambda *args, **kwargs: None" for name in exports
    )
    return (
        "import argparse\n"
        "import importlib\n"
        f"module = importlib.import_module({module.__name__!r})\n"
        f"module._parse_args = lambda: argparse.Namespace(**{args!r})\n"
        f"{setup}\n"
        f"{export_setup}\n"
        "raise SystemExit(module.main())\n"
    )


def _unified_harness(route: str, target: object, args: list[str], boundary: str, success: bool) -> str:
    if success:
        if route == "ai-scan":
            setup = (
                "target.collect_stock_ids = lambda *args, **kwargs: ['2330']\n"
                "target.scan_ai_stocks = lambda *args, **kwargs: target.pd.DataFrame({'Stock': ['2330']})\n"
                "target.export_ai_stock_ranking = lambda *args, **kwargs: None"
            )
        else:
            setup = (
                "target.compare_strategies = lambda *args, **kwargs: "
                "target.pd.DataFrame({'Strategy': ['ma_cross']})"
            )
    else:
        setup = (
            "def controlled_failure(*args, **kwargs):\n"
            "    raise RuntimeError('offline controlled failure')\n"
            f"target.{boundary} = controlled_failure"
        )
    return (
        "import importlib\n"
        "from tw_stock_tool.cli import twstock_cli\n"
        f"target = importlib.import_module({target.__name__!r})\n"
        f"{setup}\n"
        f"raise SystemExit(twstock_cli.main({args!r}))\n"
    )


class BatchBFalseSuccessRuntimeContractTest(unittest.TestCase):
    def test_direct_callable_failures_return_one_and_preserve_errors(self) -> None:
        for spec in DIRECT_CASES:
            if spec["name"] == "strategy_compare":
                failure_modes = ((ValueError("known failure"), "Error:"), (RuntimeError("unexpected failure"), "Unexpected error:"))
            else:
                failure_modes = ((RuntimeError("controlled failure"), spec["error"]),)
            for exception, prefix in failure_modes:
                with self.subTest(target=spec["name"], exception=type(exception).__name__):
                    output = StringIO()
                    errors = StringIO()
                    with ExitStack() as stack, tempfile.TemporaryDirectory():
                        stack.enter_context(patch.object(spec["module"], "_parse_args", return_value=spec["args"]))
                        boundary = stack.enter_context(
                            patch.object(spec["module"], spec["boundary"], side_effect=exception)
                        )
                        exports = [stack.enter_context(patch.object(spec["module"], name)) for name in spec["exports"]]
                        with redirect_stdout(output), redirect_stderr(errors):
                            result = spec["module"].main()
                    self.assertEqual(result, 1)
                    self.assertIn(prefix, output.getvalue())
                    self.assertIn(str(exception), output.getvalue())
                    self.assertNotIn("Traceback", output.getvalue() + errors.getvalue())
                    for export in exports:
                        export.assert_not_called()
                    boundary.assert_called_once()

    def test_direct_callable_success_returns_none_and_preserves_success_output(self) -> None:
        for spec in DIRECT_CASES:
            with self.subTest(target=spec["name"]):
                output = StringIO()
                with ExitStack() as stack, tempfile.TemporaryDirectory():
                    stack.enter_context(patch.object(spec["module"], "_parse_args", return_value=spec["args"]))
                    if spec["name"] == "ai_stock_scanner":
                        stack.enter_context(patch.object(spec["module"], "collect_stock_ids", return_value=["2330"]))
                        stack.enter_context(
                            patch.object(spec["module"], "scan_ai_stocks", return_value=spec["success_patches"]["scan_ai_stocks"])
                        )
                    else:
                        stack.enter_context(patch.object(spec["module"], spec["boundary"], return_value=spec["success"]))
                    for name in spec["exports"]:
                        stack.enter_context(patch.object(spec["module"], name, return_value=None))
                    with redirect_stdout(output):
                        result = spec["module"].main()
                self.assertIsNone(result)
                self.assertIn(spec["marker"], output.getvalue())
                for marker in spec.get("extra_markers", ()):
                    self.assertIn(marker, output.getvalue())
                self.assertNotIn("Error:", output.getvalue())

    def test_argparse_help_and_failure_statuses_are_preserved(self) -> None:
        for spec in DIRECT_CASES:
            module = spec["module"]
            invalid = ["--horizon", "not-an-int"] if spec["name"] == "ai_stock_scanner" else []
            for argv, expected in ((["--help"], 0), (invalid, 2)):
                with self.subTest(target=spec["name"], argv=argv):
                    output = StringIO()
                    errors = StringIO()
                    original = sys.argv[:]
                    with redirect_stdout(output), redirect_stderr(errors):
                        with self.assertRaises(SystemExit) as raised:
                            _parse(module, argv)
                    self.assertEqual(raised.exception.code, expected)
                    self.assertEqual(sys.argv, original)

    def test_package_main_annotations_and_guards(self) -> None:
        for spec in DIRECT_CASES:
            with self.subTest(target=spec["name"]):
                self.assertEqual(inspect.get_annotations(spec["module"].main, eval_str=True)["return"], int | None)
                tree = ast.parse(Path(PACKAGE_FILES[spec["name"]]).read_text(encoding="utf-8-sig"))
                guards = [
                    node for node in ast.walk(tree)
                    if isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                    and any(isinstance(value, ast.Name) and value.id == "__name__" for value in [node.test.left, *node.test.comparators])
                    and any(isinstance(value, ast.Constant) and value.value == "__main__" for value in [node.test.left, *node.test.comparators])
                ]
                self.assertEqual(len(guards), 1)
                statement = guards[0].body[0]
                self.assertIsInstance(statement, ast.Raise)
                self.assertIsInstance(statement.exc, ast.Call)
                self.assertEqual(statement.exc.func.id, "SystemExit")
                self.assertEqual(statement.exc.args[0].func.id, "main")

    def test_package_process_success_and_failure_statuses_are_offline(self) -> None:
        for spec in DIRECT_CASES:
            for success, expected in ((True, 0), (False, 1)):
                with self.subTest(target=spec["name"], success=success):
                    completed = _run_subprocess("-c", _package_harness(spec, success))
                    self.assertEqual(completed.returncode, expected, completed.stdout + completed.stderr)
                    if not success:
                        prefix = "Unexpected error:" if spec["name"] == "strategy_compare" else spec["error"]
                        self.assertIn(prefix, completed.stdout)

    def test_package_process_help_and_missing_argument_statuses(self) -> None:
        for spec in DIRECT_CASES:
            module_name = spec["module"].__name__
            invalid = ("--horizon", "bad") if spec["name"] == "ai_stock_scanner" else ()
            with self.subTest(target=spec["name"], mode="help"):
                self.assertEqual(_run_subprocess("-m", module_name, "--help").returncode, 0)
            with self.subTest(target=spec["name"], mode="parser-failure"):
                self.assertEqual(_run_subprocess("-m", module_name, *invalid).returncode, 2)

    def test_unified_function_returns_status_and_restores_argv(self) -> None:
        cases = (
            ("strategy-compare", strategy_compare, ["strategy-compare", "--stock", "2330"], "compare_strategies"),
            ("ai-scan", ai_stock_scanner, ["ai-scan", "--stocks", "2330"], "collect_stock_ids"),
        )
        for route, module, argv, boundary in cases:
            original = sys.argv[:]
            with self.subTest(route=route, mode="failure"):
                with patch.object(module, boundary, side_effect=RuntimeError("controlled failure")):
                    with redirect_stdout(StringIO()):
                        status = twstock_cli.main(argv)
                self.assertEqual(status, 1)
                self.assertEqual(sys.argv, original)
            with self.subTest(route=route, mode="success"):
                with ExitStack() as stack:
                    if route == "strategy-compare":
                        stack.enter_context(patch.object(module, boundary, return_value=pd.DataFrame({"Strategy": ["ma_cross"]})))
                    else:
                        stack.enter_context(patch.object(module, "collect_stock_ids", return_value=["2330"]))
                        stack.enter_context(patch.object(module, "scan_ai_stocks", return_value=pd.DataFrame({"Stock": ["2330"]})))
                        stack.enter_context(patch.object(module, "export_ai_stock_ranking", return_value=None))
                    with redirect_stdout(StringIO()):
                        status = twstock_cli.main(argv)
                self.assertEqual(status, 0)
                self.assertEqual(sys.argv, original)

    def test_unified_parser_failures_return_system_exit_two_and_restore_argv(self) -> None:
        for argv in (("strategy-compare",), ("ai-scan", "--horizon", "bad")):
            original = sys.argv[:]
            with self.subTest(argv=argv), redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    twstock_cli.main(list(argv))
            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(sys.argv, original)

    def test_unified_process_statuses_are_offline(self) -> None:
        cases = (
            ("strategy-compare", strategy_compare, ["strategy-compare", "--stock", "2330"], "compare_strategies"),
            ("ai-scan", ai_stock_scanner, ["ai-scan", "--stocks", "2330"], "collect_stock_ids"),
        )
        for route, module, argv, boundary in cases:
            for success, expected in ((True, 0), (False, 1)):
                with self.subTest(route=route, success=success):
                    completed = _run_subprocess("-c", _unified_harness(route, module, argv, boundary, success))
                    self.assertEqual(completed.returncode, expected, completed.stdout + completed.stderr)
            parser_args = ["strategy-compare"] if route == "strategy-compare" else ["ai-scan", "--horizon", "bad"]
            completed = _run_subprocess("-c", f"from tw_stock_tool.cli import twstock_cli; raise SystemExit(twstock_cli.main({parser_args!r}))")
            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)


    def test_batch_b_target_inventory_is_exact_and_excludes_other_batches(self) -> None:
        package_targets = frozenset(PACKAGE_FILES.values())
        self.assertEqual(
            package_targets,
            frozenset({
                "src/tw_stock_tool/backtesting/parameter_sweep.py",
                "src/tw_stock_tool/backtesting/strategy_compare.py",
                "src/tw_stock_tool/backtesting/walk_forward.py",
                "src/tw_stock_tool/ml/ai_stock_scanner.py",
                "src/tw_stock_tool/ml/ml_dataset.py",
                "src/tw_stock_tool/reports/ai_prediction_report.py",
            }),
        )


if __name__ == "__main__":
    unittest.main()
