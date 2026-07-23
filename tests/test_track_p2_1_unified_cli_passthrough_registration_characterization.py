from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
import importlib
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from tw_stock_tool.cli import twstock_cli


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Route:
    tokens: tuple[str, ...]
    help_text: str
    module: str
    program_name: str
    classification: str
    description: str | None = None

    @property
    def name(self) -> str:
        return " ".join(self.tokens)


ROUTES = (
    Route(("doctor",), "Check local environment", "tw_stock_tool.utils.doctor", "doctor.py", "STANDARD_TOP_LEVEL_PASSTHROUGH"),
    Route(("scan",), "Run multi-stock technical scanner", "tw_stock_tool.cli.scan_stocks", "scan_stocks.py", "STANDARD_TOP_LEVEL_PASSTHROUGH"),
    Route(("daily",), "Run daily candidate report", "tw_stock_tool.cli.daily_report_cli", "daily_report_cli.py", "STANDARD_TOP_LEVEL_PASSTHROUGH"),
    Route(
        ("daily-report-artifact",),
        "Validate, inspect, or export a Daily Report JSON artifact",
        "tw_stock_tool.cli.daily_report_artifact_cli",
        "daily_report_artifact_cli.py",
        "STANDARD_TOP_LEVEL_WITH_DESCRIPTION",
        "Operate on an existing offline Daily Research Report JSON artifact.\n"
        "Does not fetch market data, run analysis, execute strategies or backtests, connect to brokers, place orders, "
        "produce live signals, or provide investment advice.",
    ),
    Route(("stock-list", "update"), "Update stocks.txt from official sources", "tw_stock_tool.data.stock_list_updater", "stock_list_updater.py", "NESTED_CUSTOM_RUNNER"),
    Route(("stock-list", "smoke-check"), "Smoke check official stock-list sources", "tw_stock_tool.cli.stock_list_smoke_check", "stock_list_smoke_check.py", "NESTED_CUSTOM_RUNNER"),
    Route(("stock-list", "clean"), "Clean stock list", "tw_stock_tool.cli.clean_stocks", "clean_stocks.py", "NESTED_STANDARD_PASSTHROUGH"),
    Route(("price-smoke-check",), "Smoke check price data sources", "tw_stock_tool.cli.price_data_smoke_check", "price_data_smoke_check.py", "STANDARD_TOP_LEVEL_PASSTHROUGH"),
    Route(("ai-scan",), "Run multi-stock AI baseline scanner", "tw_stock_tool.ml.ai_stock_scanner", "ai_stock_scanner.py", "STANDARD_TOP_LEVEL_PASSTHROUGH"),
    Route(("ai-report",), "Run baseline ML prediction report", "tw_stock_tool.reports.ai_prediction_report", "ai_prediction_report.py", "STANDARD_TOP_LEVEL_PASSTHROUGH"),
    Route(("ml-dataset",), "Build research ML dataset", "tw_stock_tool.ml.ml_dataset", "ml_dataset.py", "STANDARD_TOP_LEVEL_PASSTHROUGH"),
    Route(("gui",), "Launch local GUI prototype", "tw_stock_tool.gui.gui_app", "gui_app.py", "LAZY_IMPORTED_STANDARD"),
    Route(("cache",), "Manage price data cache", "tw_stock_tool.data.cache_manager", "cache_manager.py", "STANDARD_TOP_LEVEL_PASSTHROUGH"),
    Route(("benchmark",), "Run multi-stock scanner benchmark", "tw_stock_tool.cli.benchmark", "benchmark.py", "STANDARD_TOP_LEVEL_PASSTHROUGH"),
    Route(("analyze",), "Run single-stock analysis", "tw_stock_tool.cli.main", "main.py", "STANDARD_TOP_LEVEL_PASSTHROUGH"),
    Route(("strategy-compare",), "Run strategy comparison", "tw_stock_tool.backtesting.strategy_compare", "strategy_compare.py", "STANDARD_TOP_LEVEL_PASSTHROUGH"),
    Route(("parameter-sweep",), "Run parameter sweep", "tw_stock_tool.cli.parameter_sweep_report", "parameter_sweep_report.py", "STANDARD_TOP_LEVEL_PASSTHROUGH"),
    Route(("backtest-report",), "Run backtest report", "tw_stock_tool.cli.backtest_report", "backtest_report.py", "STANDARD_TOP_LEVEL_PASSTHROUGH"),
    Route(("walk-forward",), "Run walk forward report", "tw_stock_tool.cli.walk_forward_report", "walk_forward_report.py", "STANDARD_TOP_LEVEL_PASSTHROUGH"),
    Route(
        ("simulated-paper-trading",),
        "Run historical simulated paper trading",
        "tw_stock_tool.cli.simulated_paper_trading_cli",
        "simulated_paper_trading_cli.py",
        "LAZY_IMPORTED_WITH_DESCRIPTION",
        "Run research-only simulated paper trading over historical data.\n"
        "Does not connect to brokers, place real orders, or provide investment advice.",
    ),
    Route(
        ("simulated-paper-trading-export",),
        "Export reports from a simulated paper trading JSON artifact",
        "tw_stock_tool.cli.simulated_paper_trading_export_cli",
        "simulated_paper_trading_export_cli.py",
        "STANDARD_TOP_LEVEL_WITH_DESCRIPTION",
        "Export reports from an existing research-only simulated paper trading JSON artifact.\n"
        "Does not fetch market data, run strategies, connect to brokers, or place orders.",
    ),
    Route(
        ("backtest-artifact",),
        "Validate or inspect BacktestResult JSON artifacts",
        "tw_stock_tool.cli.backtest_artifact_cli",
        "backtest_artifact_cli.py",
        "STANDARD_TOP_LEVEL_WITH_DESCRIPTION",
        "Validate or inspect existing research-only BacktestResult JSON artifacts.\n"
        "Does not fetch market data, run strategies, execute backtests, connect to brokers, place orders, "
        "produce live signals, or provide investment advice.",
    ),
    Route(
        ("backtest-result-export",),
        "Export historical BacktestResult JSON artifact",
        "tw_stock_tool.cli.backtest_result_export_cli",
        "backtest_result_export_cli.py",
        "LAZY_IMPORTED_WITH_DESCRIPTION",
        "Export a structured BacktestResult JSON artifact from a historical backtest execution.\n"
        "This is a historical backtest artifact for offline research only. Not investment advice.",
    ),
)

ROUTE_BY_NAME = {route.name: route for route in ROUTES}
TOP_LEVEL_ORDER = (
    "doctor",
    "scan",
    "daily",
    "daily-report-artifact",
    "stock-list",
    "price-smoke-check",
    "ai-scan",
    "ai-report",
    "ml-dataset",
    "gui",
    "cache",
    "benchmark",
    "analyze",
    "strategy-compare",
    "parameter-sweep",
    "backtest-report",
    "walk-forward",
    "simulated-paper-trading",
    "simulated-paper-trading-export",
    "backtest-artifact",
    "backtest-result-export",
)
NESTED_ORDER = ("update", "smoke-check", "clean")


TOP_HELP = """usage: twstock [-h]
               {doctor,scan,daily,daily-report-artifact,stock-list,price-smoke-check,ai-scan,ai-report,ml-dataset,gui,cache,benchmark,analyze,strategy-compare,parameter-sweep,backtest-report,walk-forward,simulated-paper-trading,simulated-paper-trading-export,backtest-artifact,backtest-result-export}
               ...

Unified tw_stock_tool CLI

positional arguments:
  {doctor,scan,daily,daily-report-artifact,stock-list,price-smoke-check,ai-scan,ai-report,ml-dataset,gui,cache,benchmark,analyze,strategy-compare,parameter-sweep,backtest-report,walk-forward,simulated-paper-trading,simulated-paper-trading-export,backtest-artifact,backtest-result-export}
    doctor              Check local environment
    scan                Run multi-stock technical scanner
    daily               Run daily candidate report
    daily-report-artifact
                        Validate, inspect, or export a Daily Report JSON artifact
    stock-list          Stock-list utilities
    price-smoke-check   Smoke check price data sources
    ai-scan             Run multi-stock AI baseline scanner
    ai-report           Run baseline ML prediction report
    ml-dataset          Build research ML dataset
    gui                 Launch local GUI prototype
    cache               Manage price data cache
    benchmark           Run multi-stock scanner benchmark
    analyze             Run single-stock analysis
    strategy-compare    Run strategy comparison
    parameter-sweep     Run parameter sweep
    backtest-report     Run backtest report
    walk-forward        Run walk forward report
    simulated-paper-trading
                        Run historical simulated paper trading
    simulated-paper-trading-export
                        Export reports from a simulated paper trading JSON artifact
    backtest-artifact   Validate or inspect BacktestResult JSON artifacts
    backtest-result-export
                        Export historical BacktestResult JSON artifact

options:
  -h, --help            show this help message and exit
"""

STOCK_LIST_HELP = """usage: twstock stock-list [-h] {update,smoke-check,clean} ...

positional arguments:
  {update,smoke-check,clean}
    update              Update stocks.txt from official sources
    smoke-check         Smoke check official stock-list sources
    clean               Clean stock list

options:
  -h, --help            show this help message and exit
"""

ORDINARY_HELP = """usage: twstock backtest-report [-h]

options:
  -h, --help  show this help message and exit
"""

NESTED_HELP = """usage: twstock stock-list update [-h]

options:
  -h, --help  show this help message and exit
"""

SAFETY_HELP = """usage: twstock simulated-paper-trading [-h]

Run research-only simulated paper trading over historical data. Does not connect to brokers, place real orders, or
provide investment advice.

options:
  -h, --help  show this help message and exit
"""

ARTIFACT_HELP = """usage: twstock backtest-artifact [-h]

Validate or inspect existing research-only BacktestResult JSON artifacts. Does not fetch market data, run strategies,
execute backtests, connect to brokers, place orders, produce live signals, or provide investment advice.

options:
  -h, --help  show this help message and exit
"""


def _subparser_action(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    return next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))


def _capture_parser() -> argparse.ArgumentParser:
    original_parser = argparse.ArgumentParser
    original_add_parser = argparse._SubParsersAction.add_parser
    captured: list[argparse.ArgumentParser] = []

    def parser_factory(*args: object, **kwargs: object) -> argparse.ArgumentParser:
        argparse.ArgumentParser = original_parser
        try:
            parser = original_parser(*args, **kwargs)
        finally:
            argparse.ArgumentParser = parser_factory
        captured.append(parser)
        return parser

    def add_parser(action: argparse._SubParsersAction, *args: object, **kwargs: object) -> argparse.ArgumentParser:
        argparse.ArgumentParser = original_parser
        try:
            return original_add_parser(action, *args, **kwargs)
        finally:
            argparse.ArgumentParser = parser_factory

    with patch.object(argparse, "ArgumentParser", new=parser_factory), patch.object(
        argparse._SubParsersAction, "add_parser", new=add_parser
    ), patch.object(sys, "argv", ["twstock"]):
        twstock_cli._parse_args(["doctor"])

    return captured[0]


def _help_snapshot(argv: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with patch.object(sys, "argv", ["twstock"]), patch.dict(os.environ, {"COLUMNS": "120"}), redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            twstock_cli.main(argv)
        except SystemExit as raised:
            return raised.code, stdout.getvalue(), stderr.getvalue()
    raise AssertionError("help did not terminate with SystemExit")


class UnifiedCliPassthroughCharacterizationTest(unittest.TestCase):
    def test_parser_tree_order_help_descriptions_and_nested_structure(self) -> None:
        parser = _capture_parser()
        action = _subparser_action(parser)
        self.assertEqual(action.dest, "command")
        self.assertTrue(action.required)
        self.assertEqual(tuple(action.choices), TOP_LEVEL_ORDER)

        top_help = {choice.dest: choice.help for choice in action._choices_actions}
        self.assertEqual(top_help["stock-list"], "Stock-list utilities")
        for route in ROUTES:
            if len(route.tokens) == 1:
                self.assertEqual(top_help[route.tokens[0]], route.help_text)
                child = action.choices[route.tokens[0]]
                self.assertEqual(child.description, route.description)
                self.assertIn("handler", child._defaults)

        stock_list = action.choices["stock-list"]
        nested = _subparser_action(stock_list)
        self.assertEqual(nested.dest, "stock_list_command")
        self.assertTrue(nested.required)
        self.assertEqual(tuple(nested.choices), NESTED_ORDER)
        nested_help = {choice.dest: choice.help for choice in nested._choices_actions}
        for route in ROUTES:
            if len(route.tokens) == 2:
                child = nested.choices[route.tokens[1]]
                self.assertEqual(nested_help[route.tokens[1]], route.help_text)
                self.assertIsNone(child.description)
                self.assertIn("handler", child._defaults)

        self.assertNotIn("stock-list", ROUTE_BY_NAME)
        self.assertEqual(tuple(action._name_parser_map), TOP_LEVEL_ORDER)

    def test_direct_handlers_preserve_callable_targets_and_child_program_names(self) -> None:
        passthrough = ["--flag", "value", "--output-md", "report.md", "--option=-2", "artifact.json"]
        for route in ROUTES:
            if route.classification in {"NESTED_CUSTOM_RUNNER", "LAZY_IMPORTED_STANDARD"}:
                continue
            expected_main = importlib.import_module(route.module).main
            original_argv = sys.argv[:]
            argv = [*route.tokens, *passthrough]
            with self.subTest(route=route.name), patch.object(twstock_cli, "_dispatch_existing_main", return_value=17) as dispatch:
                result = twstock_cli.main(argv)
            self.assertEqual(result, 17)
            dispatch.assert_called_once_with(expected_main, route.program_name, passthrough)
            self.assertEqual(sys.argv, original_argv)
    def test_custom_nested_runners_remain_distinct_dispatch_boundaries(self) -> None:
        cases = (
            ("update", "_run_stock_list_update", ["--flag", "value", "stocks.txt", "--option=-2"]),
            ("smoke-check", "_run_stock_list_smoke_check", ["--flag", "value", "source.json"]),
        )
        for command, runner, passthrough in cases:
            with self.subTest(command=command), patch.object(twstock_cli, runner, return_value=19) as mocked:
                result = twstock_cli.main(["stock-list", command, *passthrough])
            self.assertEqual(result, 19)
            mocked.assert_called_once_with(passthrough)
    def test_unknown_and_incomplete_routes_fail_at_parser_boundary(self) -> None:
        for argv in ([], ["unknown"], ["stock-list"], ["stock-list", "unknown"]):
            stdout = StringIO()
            stderr = StringIO()
            with self.subTest(argv=argv), redirect_stdout(stdout), redirect_stderr(stderr), patch.object(twstock_cli, "_dispatch_existing_main") as dispatch:
                with self.assertRaises(SystemExit) as raised:
                    twstock_cli.main(argv)
            self.assertEqual(raised.exception.code, 2)
            self.assertIn("usage:", stdout.getvalue() + stderr.getvalue())
            self.assertNotIn("Traceback", stdout.getvalue() + stderr.getvalue())
            dispatch.assert_not_called()

        parsed = twstock_cli._parse_args(["stock-list", "smoke-check", "--future-option", "value"])
        self.assertEqual(parsed.command, "stock-list")
        self.assertEqual(parsed.stock_list_command, "smoke-check")
        self.assertEqual(parsed.args, ["--future-option", "value"])
    def test_help_snapshots_freeze_order_wording_wrapping_and_descriptions(self) -> None:
        snapshots = (
            (["--help"], TOP_HELP),
            (["stock-list", "--help"], STOCK_LIST_HELP),
            (["backtest-report", "--help"], ORDINARY_HELP),
            (["stock-list", "update", "--help"], NESTED_HELP),
            (["simulated-paper-trading", "--help"], SAFETY_HELP),
            (["backtest-artifact", "--help"], ARTIFACT_HELP),
        )
        for argv, expected in snapshots:
            with self.subTest(argv=argv):
                status, stdout, stderr = _help_snapshot(argv)
                self.assertEqual(status, 0)
                self.assertEqual(stderr, "")
                self.assertEqual(stdout, expected)

    def test_passthrough_status_argv_and_system_exit_are_preserved_across_route_shapes(self) -> None:
        cases = (
            (("doctor",), ["--flag", "value", "--option=-2"], "tw_stock_tool.utils.doctor", "doctor.py"),
            (("stock-list", "clean"), ["--output-md", "report.md"], "tw_stock_tool.cli.clean_stocks", "clean_stocks.py"),
            (("stock-list", "update"), ["--path", "stocks.txt"], "tw_stock_tool.data.stock_list_updater", "stock_list_updater.py"),
            (("simulated-paper-trading",), ["--quantity=-2"], "tw_stock_tool.cli.simulated_paper_trading_cli", "simulated_paper_trading_cli.py"),
            (("simulated-paper-trading-export",), ["artifact.json", "--output-md", "report.md"], "tw_stock_tool.cli.simulated_paper_trading_export_cli", "simulated_paper_trading_export_cli.py"),
        )
        for route_tokens, passthrough, module_name, program_name in cases:
            module = importlib.import_module(module_name)
            for child_result in (None, 0, 1, 7):
                original_argv = sys.argv[:]
                captured: list[list[str]] = []

                def fake_main(return_value=child_result) -> int | None:
                    captured.append(sys.argv[:])
                    return return_value

                with self.subTest(route=route_tokens, result=child_result), patch.object(module, "main", side_effect=fake_main) as mocked:
                    status = twstock_cli.main([*route_tokens, *passthrough])
                self.assertEqual(status, 0 if child_result is None else child_result)
                mocked.assert_called_once_with()
                self.assertEqual(captured, [[program_name, *passthrough]])
                self.assertEqual(sys.argv, original_argv)

            for exit_code in (2, 23):
                original_argv = sys.argv[:]
                with self.subTest(route=route_tokens, exit_code=exit_code), patch.object(module, "main", side_effect=SystemExit(exit_code)):
                    with self.assertRaises(SystemExit) as raised:
                        twstock_cli.main([*route_tokens, *passthrough])
                self.assertEqual(raised.exception.code, exit_code)
                self.assertEqual(sys.argv, original_argv)
    def test_lazy_import_timing_is_characterized_without_network_access(self) -> None:
        script = (
            "import contextlib\n"
            "import io\n"
            "import json\n"
            "import sys\n"
            "from tw_stock_tool.cli import twstock_cli\n"
            "names = ('tw_stock_tool.cli.simulated_paper_trading_cli', 'tw_stock_tool.cli.backtest_result_export_cli')\n"
            "before = {name: name in sys.modules for name in names}\n"
            "if sys.argv[1] == 'help':\n"
            "    with contextlib.redirect_stdout(io.StringIO()):\n"
            "        try:\n"
            "            twstock_cli.main(['--help'])\n"
            "        except SystemExit:\n"
            "            pass\n"
            "else:\n"
            "    twstock_cli._parse_args(['doctor'])\n"
            "after = {name: name in sys.modules for name in names}\n"
            "print(json.dumps({'before': before, 'after': after}, sort_keys=True))\n"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join((str(REPOSITORY_ROOT / "src"), str(REPOSITORY_ROOT), env.get("PYTHONPATH", "")))
        expected = {
            "after": {
                "tw_stock_tool.cli.backtest_result_export_cli": True,
                "tw_stock_tool.cli.simulated_paper_trading_cli": True,
            },
            "before": {
                "tw_stock_tool.cli.backtest_result_export_cli": False,
                "tw_stock_tool.cli.simulated_paper_trading_cli": False,
            },
        }
        for mode in ("doctor", "help"):
            completed = subprocess.run(
                [sys.executable, "-c", script, mode],
                cwd=REPOSITORY_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            with self.subTest(mode=mode):
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(json.loads(completed.stdout), expected)
    def test_gui_dispatch_is_lazy_and_rejects_unknown_arguments(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            twstock_cli.main(["gui", "--unknown"])
        self.assertEqual(raised.exception.code, 2)

        with patch("tw_stock_tool.gui.gui_app.main", return_value=None) as gui_main:
            self.assertEqual(twstock_cli.main(["gui"]), 0)
        gui_main.assert_called_once_with()

    def test_gui_help_does_not_import_gui_module_in_clean_process(self) -> None:
        script = (
            "import contextlib, io, json, sys\n"
            "from tw_stock_tool.cli import twstock_cli\n"
            "before = 'tw_stock_tool.gui.gui_app' in sys.modules\n"
            "with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):\n"
            "    try:\n"
            "        twstock_cli.main(sys.argv[1:])\n"
            "    except SystemExit:\n"
            "        pass\n"
            "print(json.dumps({'before': before, 'after': 'tw_stock_tool.gui.gui_app' in sys.modules}))\n"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join((str(REPOSITORY_ROOT / "src"), env.get("PYTHONPATH", "")))
        for argv in (("--help",), ("gui", "--help")):
            completed = subprocess.run(
                [sys.executable, "-c", script, *argv],
                cwd=REPOSITORY_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            with self.subTest(argv=argv):
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(json.loads(completed.stdout), {"before": False, "after": False})

    def test_registration_inventory_matches_source_counts_and_helper_boundary(self) -> None:
        self.assertEqual(len(ROUTES), 23)
        self.assertEqual(sum(route.classification == "STANDARD_TOP_LEVEL_PASSTHROUGH" for route in ROUTES), 14)
        self.assertEqual(sum(route.classification == "STANDARD_TOP_LEVEL_WITH_DESCRIPTION" for route in ROUTES), 3)
        self.assertEqual(sum(route.classification == "NESTED_STANDARD_PASSTHROUGH" for route in ROUTES), 1)
        self.assertEqual(sum(route.classification == "NESTED_CUSTOM_RUNNER" for route in ROUTES), 2)
        self.assertEqual(sum(route.classification == "LAZY_IMPORTED_STANDARD" for route in ROUTES), 1)
        self.assertEqual(sum(route.classification == "LAZY_IMPORTED_WITH_DESCRIPTION" for route in ROUTES), 2)

        source = (REPOSITORY_ROOT / "src" / "tw_stock_tool" / "cli" / "twstock_cli.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("def _add_passthrough_parser"), 1)
        self.assertEqual(source.count("_add_passthrough_parser("), 21)
        self.assertEqual(source.count(".add_parser("), 5)
        self.assertEqual(source.count(".set_defaults("), 4)
        self.assertEqual(source.count("stock_list_parser = subparsers.add_parser"), 1)
        self.assertEqual(source.count("update_parser = stock_list_subparsers.add_parser"), 1)
        self.assertEqual(source.count("smoke_parser = stock_list_subparsers.add_parser"), 1)
        self.assertEqual(source.count("_run_stock_list_update(args.args)"), 1)
        self.assertEqual(source.count("_run_stock_list_smoke_check(args.args)"), 1)
        self.assertNotIn("route_table", source)
        self.assertNotIn("ROUTE_SPECS", source)
        self.assertNotIn("dataclass", source)
        self.assertEqual(
            sum(route.classification != "NESTED_CUSTOM_RUNNER" for route in ROUTES),
            21,
        )


if __name__ == "__main__":
    unittest.main()
