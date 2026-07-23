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
from types import SimpleNamespace
from unittest.mock import mock_open, patch

import pandas as pd

from tw_stock_tool.cli import twstock_cli
from tw_stock_tool.cli import backtest_report, daily_report_cli, parameter_sweep_report
from tw_stock_tool.cli import simulated_paper_trading_cli, walk_forward_report
from tw_stock_tool.utils import doctor


ROOT = Path(__file__).resolve().parents[1]
ENV = os.environ.copy()
ENV["PYTHONPATH"] = os.pathsep.join(
    value for value in (str(ROOT / "src"), ENV.get("PYTHONPATH")) if value
)


def ns(**values):
    return argparse.Namespace(**values)


def frame():
    return pd.DataFrame(
        {"Open": [10.0], "Close": [11.0], "entry_signal": [False], "exit_signal": [False]},
        index=pd.to_datetime(["2026-01-01"]),
    )


def summary():
    return {
        "symbol": "2330", "initial_cash": 1000, "final_cash": 1000,
        "final_position_quantity": 0, "realized_pnl": 0, "unrealized_pnl": 0,
        "total_equity": 1000, "total_return": 0, "total_return_pct": 0,
        "order_count": 0, "fill_count": 0,
    }


CASES = (
    ("backtest_report", backtest_report, "tw_stock_tool.cli.backtest_report",
     "src/tw_stock_tool/cli/backtest_report.py", "backtest-report",
     ns(stock="2330", strategy="ma_cross", period="1y", initial_capital=100000,
        output_md=None, output_excel=None, output_dir="output", force_refresh=False,
        short_window=5, long_window=20, rsi_buy_below=30.0, rsi_sell_above=70.0,
        score_buy=None, score_sell=None, fee_rate=0.001425, tax_rate=0.003,
        position_size=1.0, stop_loss_pct=None, take_profit_pct=None, max_hold_days=None),
     "analyze_stock", []),
    ("daily_report_cli", daily_report_cli, "tw_stock_tool.cli.daily_report_cli",
     "src/tw_stock_tool/cli/daily_report_cli.py", "daily",
     ns(stocks=["2330"], file=None, auto_stock_list=False, stock_market="all",
        stock_list_output="stocks.txt", allow_partial_stock_list=False, stock_limit=None,
        stock_sample=None, random_state=42, period="1y", interval="1d",
        signals=["BUY"], min_score=4.0, top=20, force_refresh=False,
        auto_adjust=False, output_md=None, output_excel=None, output_dir="output"),
     "collect_stock_ids", ["--stock-market", "bad"]),
    ("parameter_sweep_report", parameter_sweep_report,
     "tw_stock_tool.cli.parameter_sweep_report",
     "src/tw_stock_tool/cli/parameter_sweep_report.py", "parameter-sweep",
     ns(stock="2330", strategy="ma_cross", period="1y", output_md=None,
        output_excel=None, output_dir="output", force_refresh=False,
        ma_short_windows=None, ma_long_windows=None, rsi_buy_below=None,
        rsi_sell_above=None, score_buy=None, score_sell=None,
        initial_capital=100000, fee_rate=0.001425, tax_rate=0.003,
        position_size=1.0, stop_loss_pct=None, take_profit_pct=None, max_hold_days=None),
     "run_parameter_sweep", []),
    ("simulated_paper_trading_cli", simulated_paper_trading_cli,
     "tw_stock_tool.cli.simulated_paper_trading_cli",
     "src/tw_stock_tool/cli/simulated_paper_trading_cli.py",
     "simulated-paper-trading",
     ns(stock="2330", strategy="ma_cross", period="1y", initial_cash=1000,
        quantity_per_trade=10, fee_rate=0.001425, tax_rate=0.003,
        slippage_per_share=0.0, force_refresh=False, max_order_notional=None,
        max_position_quantity=None, max_position_notional=None),
     "analyze_stock", []),
    ("walk_forward_report", walk_forward_report,
     "tw_stock_tool.cli.walk_forward_report",
     "src/tw_stock_tool/cli/walk_forward_report.py", "walk-forward",
     ns(stock="2330", strategy="ma_cross", period="1y", output_md=None,
        output_excel=None, output_dir="output", force_refresh=False,
        ma_short_windows=None, ma_long_windows=None, rsi_buy_below=None,
        rsi_sell_above=None, score_buy=None, score_sell=None, train_days=10,
        test_days=5, step_days=None, sort_by="Train Sharpe Ratio",
        initial_capital=100000, fee_rate=0.001425, tax_rate=0.003,
        position_size=1.0, stop_loss_pct=None, take_profit_pct=None, max_hold_days=None),
     "run_walk_forward", []),
    ("doctor", doctor, "tw_stock_tool.utils.doctor",
     "src/tw_stock_tool/utils/doctor.py", "doctor", ns(live=False),
     "run_doctor", ["--unknown"]),
)


EXPECTED_PACKAGES = frozenset(case[3] for case in CASES)
EXPORTS = {
    "backtest_report": ("export_backtest_report_excel", "export_backtest_report_markdown"),
    "parameter_sweep_report": ("export_parameter_sweep_report_excel", "export_parameter_sweep_report_markdown"),
    "walk_forward_report": ("export_walk_forward_report_excel", "export_walk_forward_report_markdown"),
}


def run_subprocess(*args):
    return subprocess.run(
        [sys.executable, *args], cwd=ROOT, env=ENV,
        capture_output=True, text=True, check=False,
    )


def patch_success(stack, case):
    name, module, _, _, _, args, _, _ = case
    stack.enter_context(patch.object(module, "_parse_args", return_value=args))
    if name == "backtest_report":
        stack.enter_context(patch.object(module, "STRATEGIES", {"ma_cross_strategy": lambda df, **k: df}))
        stack.enter_context(patch.object(module, "analyze_stock", return_value=SimpleNamespace(indicator_df=frame())))
        stack.enter_context(patch.object(module, "run_backtest", return_value={"Total Return %": 1, "Win Rate %": 1, "Trade Count": 1}))
    elif name == "daily_report_cli":
        stack.enter_context(patch.object(module, "collect_stock_ids", return_value=["2330"]))
        stack.enter_context(patch.object(module, "run_daily_research_pipeline", return_value=SimpleNamespace(markdown="# report")))
        stack.enter_context(patch.object(Path, "mkdir"))
        stack.enter_context(patch("builtins.open", mock_open()))
    elif name == "parameter_sweep_report":
        stack.enter_context(patch.object(module, "run_parameter_sweep", return_value=pd.DataFrame({"Result": [1]})))
        stack.enter_context(patch.object(module, "build_parameter_sweep_report_data", return_value={"Best Row": {}}))
    elif name == "simulated_paper_trading_cli":
        stack.enter_context(patch.object(module, "STRATEGIES", {"ma_cross_strategy": lambda df: df}))
        stack.enter_context(patch.object(module, "analyze_stock", return_value=SimpleNamespace(symbol="2330", indicator_df=frame())))
        stack.enter_context(patch.object(module, "run_simulated_paper_trading_result", return_value=object()))
        stack.enter_context(patch.object(module, "build_simulated_paper_trading_summary", return_value=summary()))
    elif name == "walk_forward_report":
        stack.enter_context(patch.object(module, "run_walk_forward", return_value=pd.DataFrame()))
        stack.enter_context(patch.object(module, "build_walk_forward_report_data", return_value={"Best Window": {}}))
    else:
        stack.enter_context(patch.object(module, "run_doctor", return_value=[{"Status": module.PASS, "Check": "local", "Message": ""}]))
        stack.enter_context(patch.object(module, "print_report"))


def patch_failure(stack, case):
    name, module, _, _, _, args, boundary, _ = case
    stack.enter_context(patch.object(module, "_parse_args", return_value=args))
    if name == "doctor":
        return stack.enter_context(patch.object(
            module, "run_doctor",
            return_value=[{"Status": module.FAIL, "Check": "offline", "Message": "controlled failure"}],
        ))
    failure = stack.enter_context(
        patch.object(module, boundary, side_effect=RuntimeError("controlled failure"))
    )
    for exporter in EXPORTS.get(name, ()):
        stack.enter_context(patch.object(module, exporter))
    return failure


def process_script(case, success, unified=False):
    name, _, module_name, _, route, args, boundary, _ = case
    data = vars(args).copy()
    lines = [
        "import argparse, importlib, tempfile",
        "from types import SimpleNamespace",
        "import pandas as pd",
        f"module = importlib.import_module({module_name!r})",
        f"data = {data!r}",
        "tmp = tempfile.TemporaryDirectory()",
        "data['output_dir'] = tmp.name if 'output_dir' in data else data.get('output_dir')",
        "module._parse_args = lambda *a, **k: argparse.Namespace(**data)",
    ]
    if success:
        if name == "backtest_report":
            lines += [
                "module.STRATEGIES = {'ma_cross_strategy': lambda df, **k: df}",
                "module.analyze_stock = lambda *a, **k: SimpleNamespace(indicator_df=pd.DataFrame({'Open': [10], 'Close': [11]}, index=pd.to_datetime(['2026-01-01'])))",
                "module.run_backtest = lambda *a, **k: {'Total Return %': 1, 'Win Rate %': 1, 'Trade Count': 1}",
            ]
        elif name == "daily_report_cli":
            lines += [
                "module.collect_stock_ids = lambda *a, **k: ['2330']",
                "module.run_daily_research_pipeline = lambda *a, **k: SimpleNamespace(markdown='# report')",
            ]
        elif name == "parameter_sweep_report":
            lines += [
                "module.run_parameter_sweep = lambda *a, **k: pd.DataFrame({'Result': [1]})",
                "module.build_parameter_sweep_report_data = lambda *a, **k: {'Best Row': {}}",
            ]
        elif name == "simulated_paper_trading_cli":
            lines += [
                "module.STRATEGIES = {'ma_cross_strategy': lambda df: df}",
                "module.analyze_stock = lambda *a, **k: SimpleNamespace(symbol='2330', indicator_df=pd.DataFrame({'Open': [10], 'Close': [11], 'entry_signal': [False], 'exit_signal': [False]}))",
                "module.run_simulated_paper_trading_result = lambda *a, **k: object()",
                f"module.build_simulated_paper_trading_summary = lambda *a, **k: {summary()!r}",
            ]
        elif name == "walk_forward_report":
            lines += [
                "module.run_walk_forward = lambda *a, **k: pd.DataFrame()",
                "module.build_walk_forward_report_data = lambda *a, **k: {'Best Window': {}}",
            ]
        else:
            lines += [
                "module.run_doctor = lambda live=False: [{'Status': module.PASS, 'Check': 'local', 'Message': ''}]",
                "module.print_report = lambda rows: None",
            ]
    elif name == "doctor":
        lines.append("module.run_doctor = lambda live=False: [{'Status': module.FAIL, 'Check': 'offline', 'Message': 'controlled failure'}]")
    else:
        lines.append(f"module.{boundary} = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('controlled failure'))")
    call = f"twstock_cli.main([{route!r}])" if unified else "module.main()"
    if unified:
        lines.insert(4, "from tw_stock_tool.cli import twstock_cli")
    lines.append(f"raise SystemExit({call})")
    return "\n".join(lines)
def parse_args(module, argv):
    return module._parse_args(argv)


class C15BatchAReturnCodeNormalizationTest(unittest.TestCase):
    def test_direct_success_returns_none(self):
        for case in CASES:
            with self.subTest(target=case[0]):
                output = StringIO()
                with ExitStack() as stack:
                    patch_success(stack, case)
                    with redirect_stdout(output):
                        result = case[1].main()
                self.assertIsNone(result)
                if case[0] == "doctor":
                    self.assertTrue(result is None)
                else:
                    self.assertNotIn("Error:", output.getvalue())

    def test_direct_failures_return_one_and_preserve_output(self):
        for case in CASES:
            with self.subTest(target=case[0]):
                output, errors = StringIO(), StringIO()
                with ExitStack() as stack:
                    boundary = patch_failure(stack, case)
                    with redirect_stdout(output), redirect_stderr(errors):
                        result = case[1].main()
                self.assertEqual(result, 1)
                self.assertNotIn("Traceback", output.getvalue() + errors.getvalue())
                self.assertNotIn("successfully", output.getvalue().lower())
                if case[0] == "doctor":
                    self.assertIn("FAIL", output.getvalue())
                else:
                    self.assertIn("Error: controlled failure", output.getvalue())
                    boundary.assert_called_once()

    def test_daily_no_stock_returns_one(self):
        case = next(item for item in CASES if item[0] == "daily_report_cli")
        output = StringIO()
        with patch.object(case[1], "_parse_args", return_value=case[5]):
            with patch.object(case[1], "collect_stock_ids", return_value=[]):
                with redirect_stdout(output):
                    result = case[1].main()
        self.assertEqual(result, 1)
        self.assertEqual(output.getvalue(), "Error: No stocks provided.\n")

    def test_parser_help_and_usage_are_preserved(self):
        for case in CASES:
            with self.subTest(target=case[0], mode="help"):
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        parse_args(case[1], ["--help"])
                self.assertEqual(raised.exception.code, 0)
            with self.subTest(target=case[0], mode="usage"):
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        parse_args(case[1], case[7])
                self.assertEqual(raised.exception.code, 2)

    def test_simulated_parser_system_exit_is_reraised(self):
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as raised:
                simulated_paper_trading_cli.main(["--invalid"])
        self.assertEqual(raised.exception.code, 2)

    def test_annotations_and_package_guards(self):
        for case in CASES:
            with self.subTest(target=case[0]):
                self.assertEqual(inspect.get_annotations(case[1].main, eval_str=True)["return"], int | None)
                tree = ast.parse(Path(case[3]).read_text(encoding="utf-8"))
                guards = [
                    node for node in ast.walk(tree)
                    if isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                    and any(isinstance(value, ast.Name) and value.id == "__name__" for value in [node.test.left, *node.test.comparators])
                    and any(isinstance(value, ast.Constant) and value.value == "__main__" for value in [node.test.left, *node.test.comparators])
                ]
                self.assertEqual(len(guards), 1)
                statement = guards[0].body[0]
                self.assertIsInstance(statement, ast.Raise)
                self.assertEqual(statement.exc.func.id, "SystemExit")
                self.assertEqual(statement.exc.args[0].func.id, "main")

    def test_package_process_success_and_failure(self):
        for case in CASES:
            for success, expected in ((True, 0), (False, 1)):
                with self.subTest(target=case[0], success=success):
                    completed = run_subprocess("-c", process_script(case, success))
                    self.assertEqual(completed.returncode, expected, completed.stdout + completed.stderr)
                    if not success and case[0] != "doctor":
                        self.assertIn("Error: controlled failure", completed.stdout)

    def test_package_process_help_and_usage(self):
        for case in CASES:
            with self.subTest(target=case[0], mode="help"):
                self.assertEqual(run_subprocess("-m", case[2], "--help").returncode, 0)
            with self.subTest(target=case[0], mode="usage"):
                completed = run_subprocess("-m", case[2], *case[7])
                self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)

    def test_unified_function_statuses_restore_argv(self):
        for case in CASES:
            original = sys.argv[:]
            with self.subTest(target=case[0], mode="success"):
                with ExitStack() as stack:
                    patch_success(stack, case)
                    with redirect_stdout(StringIO()):
                        result = twstock_cli.main([case[4]])
                self.assertEqual(result, 0)
                self.assertEqual(sys.argv, original)
            with self.subTest(target=case[0], mode="failure"):
                with ExitStack() as stack:
                    patch_failure(stack, case)
                    with redirect_stdout(StringIO()):
                        result = twstock_cli.main([case[4]])
                self.assertEqual(result, 1)
                self.assertEqual(sys.argv, original)

    def test_unified_parser_status_and_argv_restoration(self):
        for case in CASES:
            original = sys.argv[:]
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    twstock_cli.main([case[4], *case[7]])
            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(sys.argv, original)

    def test_unified_process_success_failure_and_parser(self):
        for case in CASES:
            for success, expected in ((True, 0), (False, 1)):
                completed = run_subprocess("-c", process_script(case, success, unified=True))
                self.assertEqual(completed.returncode, expected, completed.stdout + completed.stderr)
            parser = [case[4], *case[7]]
            completed = run_subprocess("-c", f"from tw_stock_tool.cli import twstock_cli; raise SystemExit(twstock_cli.main({parser!r}))")
            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)




    def test_static_package_inventory_is_exact(self):
        packages = frozenset(case[3] for case in CASES)
        expected_packages = frozenset({
            "src/tw_stock_tool/cli/backtest_report.py",
            "src/tw_stock_tool/cli/daily_report_cli.py",
            "src/tw_stock_tool/cli/parameter_sweep_report.py",
            "src/tw_stock_tool/cli/simulated_paper_trading_cli.py",
            "src/tw_stock_tool/cli/walk_forward_report.py",
            "src/tw_stock_tool/utils/doctor.py",
        })
        self.assertEqual(packages, expected_packages)


if __name__ == "__main__":
    unittest.main()
