import argparse
import contextlib
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tw_stock_tool.cli import backtest_report, parameter_sweep_report, twstock_cli, walk_forward_report
from tw_stock_tool.cli.parsers import parse_int_tuple


def _capture_parser(module, argv):
    captured = []
    real_argument_parser = argparse.ArgumentParser

    def factory(*args, **kwargs):
        parser = real_argument_parser(*args, **kwargs)
        captured.append(parser)
        return parser

    # The CLI stores the argparse module, so replace that module reference with
    # a proxy. Patching argparse.ArgumentParser globally breaks argparse's own
    # super() lookup while constructing the real parser.
    fake_argparse = SimpleNamespace(ArgumentParser=factory)
    with patch.object(module, "argparse", fake_argparse):
        if module is backtest_report:
            parsed = module._parse_args(argv)
        else:
            with patch.object(sys, "argv", [module.__name__.rsplit(".", 1)[-1], *argv]):
                parsed = module._parse_args()
    return captured[0], parsed


def _type_name(value):
    if value is None:
        return None
    if value is parse_int_tuple:
        return "parse_int_tuple"
    return getattr(value, "__name__", repr(value))


def _assert_parser_contract(test_case, parser, expected_actions):
    actions = parser._actions
    test_case.assertEqual([action.dest for action in actions], [item[0] for item in expected_actions])
    for action, expected in zip(actions, expected_actions):
        dest, option_strings, action_type, required, nargs, value_type, help_text = expected
        test_case.assertEqual(action.dest, dest)
        test_case.assertEqual(action.option_strings, list(option_strings))
        test_case.assertEqual(action.__class__.__name__, action_type)
        test_case.assertEqual(action.required, required)
        test_case.assertEqual(action.nargs, nargs)
        test_case.assertEqual(_type_name(action.type), value_type)
        test_case.assertEqual(action.help, help_text)


BACKTEST_ACTIONS = [
    ("help", ("-h", "--help"), "_HelpAction", False, 0, None, "show this help message and exit"),
    ("stock", ("--stock",), "_StoreAction", True, None, None, "Stock ID (e.g., 2330)"),
    ("strategy", ("--strategy",), "_StoreAction", True, None, None, "Strategy name (e.g., ma_cross)"),
    ("period", ("--period",), "_StoreAction", False, None, None, "Data period"),
    ("initial_capital", ("--initial-capital",), "_StoreAction", False, None, "float", "Initial capital"),
    ("output_md", ("--output-md",), "_StoreAction", False, "?", None, "Export Markdown report"),
    ("output_excel", ("--output-excel",), "_StoreAction", False, "?", None, "Export Excel report"),
    ("output_dir", ("--output-dir",), "_StoreAction", False, None, None, "Default output directory"),
    ("force_refresh", ("--force-refresh",), "_StoreTrueAction", False, 0, None, "Redownload data ignoring cache"),
    ("short_window", ("--short-window",), "_StoreAction", False, None, "int", "Short MA window"),
    ("long_window", ("--long-window",), "_StoreAction", False, None, "int", "Long MA window"),
    ("rsi_buy_below", ("--rsi-buy-below",), "_StoreAction", False, None, "float", "RSI threshold (buy below)"),
    ("rsi_sell_above", ("--rsi-sell-above",), "_StoreAction", False, None, "float", "RSI threshold (sell above)"),
    ("score_buy", ("--score-buy",), "_StoreAction", False, None, "float", "Score threshold (buy)"),
    ("score_sell", ("--score-sell",), "_StoreAction", False, None, "float", "Score threshold (sell)"),
    ("fee_rate", ("--fee-rate",), "_StoreAction", False, None, "float", "Backtest fee rate assumption"),
    ("tax_rate", ("--tax-rate",), "_StoreAction", False, None, "float", "Backtest tax rate assumption"),
    ("position_size", ("--position-size",), "_StoreAction", False, None, "float", "Backtest position size"),
    ("stop_loss_pct", ("--stop-loss-pct",), "_StoreAction", False, None, "float", "Stop-loss threshold percentage"),
    ("take_profit_pct", ("--take-profit-pct",), "_StoreAction", False, None, "float", "Take-profit threshold percentage"),
    ("max_hold_days", ("--max-hold-days",), "_StoreAction", False, None, "int", "Max holding days"),
]

REPORT_GRID_ACTIONS = [
    ("ma_short_windows", ("--ma-short-windows",), "_StoreAction", False, None, "parse_int_tuple", "Comma-separated integers, e.g. 5,10"),
    ("ma_long_windows", ("--ma-long-windows",), "_StoreAction", False, None, "parse_int_tuple", "Comma-separated integers"),
    ("rsi_buy_below", ("--rsi-buy-below",), "_StoreAction", False, None, "parse_int_tuple", "Comma-separated integers"),
    ("rsi_sell_above", ("--rsi-sell-above",), "_StoreAction", False, None, "parse_int_tuple", "Comma-separated integers"),
    ("score_buy", ("--score-buy",), "_StoreAction", False, None, "parse_int_tuple", "Comma-separated integers"),
    ("score_sell", ("--score-sell",), "_StoreAction", False, None, "parse_int_tuple", "Comma-separated integers, can be negative"),
]


def _report_actions(extra):
    return [
        ("help", ("-h", "--help"), "_HelpAction", False, 0, None, "show this help message and exit"),
        ("stock", ("--stock",), "_StoreAction", True, None, None, "Stock ID (e.g., 2330)"),
        ("strategy", ("--strategy",), "_StoreAction", True, None, None, "Strategy name (e.g., ma_cross, all)"),
        ("period", ("--period",), "_StoreAction", False, None, None, "Data period"),
        ("output_md", ("--output-md",), "_StoreAction", False, "?", None, "Export Markdown report"),
        ("output_excel", ("--output-excel",), "_StoreAction", False, "?", None, "Export Excel report"),
        ("output_dir", ("--output-dir",), "_StoreAction", False, None, None, "Default output directory"),
        ("force_refresh", ("--force-refresh",), "_StoreTrueAction", False, 0, None, "Redownload data ignoring cache"),
        *extra,
        ("initial_capital", ("--initial-capital",), "_StoreAction", False, None, "float", "Initial capital (default from config)"),
        ("fee_rate", ("--fee-rate",), "_StoreAction", False, None, "float", "Fee rate (default from config)"),
        ("tax_rate", ("--tax-rate",), "_StoreAction", False, None, "float", "Tax rate (default from config)"),
        ("position_size", ("--position-size",), "_StoreAction", False, None, "float", "Position size (0 to 1.0, default 1.0)"),
        ("stop_loss_pct", ("--stop-loss-pct",), "_StoreAction", False, None, "float", "Stop loss percentage (e.g., 0.05 for 5%%)"),
        ("take_profit_pct", ("--take-profit-pct",), "_StoreAction", False, None, "float", "Take profit percentage"),
        ("max_hold_days", ("--max-hold-days",), "_StoreAction", False, None, "int", "Maximum holding days"),
    ]


class ParserAndValueContractTests(unittest.TestCase):
    def test_parser_actions_lock_order_types_required_and_help(self):
        backtest_parser, _ = _capture_parser(backtest_report, ["--stock", "2330", "--strategy", "ma_cross"])
        _assert_parser_contract(self, backtest_parser, BACKTEST_ACTIONS)
        self.assertEqual(backtest_parser.description, "Backtest Report Generator")
        self.assertEqual(backtest_parser.epilog, "Backtest fills use next-bar Open as a research assumption.")

        parameter_parser, _ = _capture_parser(parameter_sweep_report, ["--stock", "2330", "--strategy", "ma_cross"])
        _assert_parser_contract(self, parameter_parser, _report_actions(REPORT_GRID_ACTIONS))
        self.assertEqual(parameter_parser.description, "Parameter Sweep Report CLI")
        self.assertIsNone(parameter_parser.epilog)

        walk_parser, _ = _capture_parser(walk_forward_report, ["--stock", "2330", "--strategy", "ma_cross"])
        walk_extra = [
            *REPORT_GRID_ACTIONS,
            ("train_days", ("--train-days",), "_StoreAction", False, None, "int", "Number of training days per window"),
            ("test_days", ("--test-days",), "_StoreAction", False, None, "int", "Number of test days per window"),
            ("step_days", ("--step-days",), "_StoreAction", False, None, "int", "Number of days to step forward per window"),
            ("sort_by", ("--sort-by",), "_StoreAction", False, None, None, "Metric to select best parameters"),
        ]
        walk_actions = _report_actions(walk_extra)
        for index in range(len(walk_actions) - 7, len(walk_actions)):
            walk_actions[index] = (*walk_actions[index][:-1], None)
        _assert_parser_contract(self, walk_parser, walk_actions)
        self.assertEqual(walk_parser.description, "Walk Forward Report CLI")
        self.assertIsNone(walk_parser.epilog)

    def test_defaults_are_characterized_separately(self):
        backtest = backtest_report._parse_args(["--stock", "2330", "--strategy", "ma_cross"])
        self.assertEqual(
            {name: getattr(backtest, name) for name in (
                "period", "initial_capital", "output_md", "output_excel", "output_dir",
                "force_refresh", "short_window", "long_window", "rsi_buy_below",
                "rsi_sell_above", "score_buy", "score_sell", "fee_rate", "tax_rate",
                "position_size", "stop_loss_pct", "take_profit_pct", "max_hold_days",
            )},
            {
                "period": "1y", "initial_capital": 100000.0, "output_md": None,
                "output_excel": None, "output_dir": "output", "force_refresh": False,
                "short_window": 5, "long_window": 20, "rsi_buy_below": 30.0,
                "rsi_sell_above": 70.0, "score_buy": None, "score_sell": None,
                "fee_rate": 0.001425, "tax_rate": 0.003, "position_size": 1.0,
                "stop_loss_pct": None, "take_profit_pct": None, "max_hold_days": None,
            },
        )

        with patch.object(sys, "argv", ["parameter_sweep_report.py", "--stock", "2330", "--strategy", "ma_cross"]):
            parameter = parameter_sweep_report._parse_args()
        self.assertEqual(
            {name: getattr(parameter, name) for name in (
                "period", "output_md", "output_excel", "output_dir", "force_refresh",
                "ma_short_windows", "ma_long_windows", "rsi_buy_below", "rsi_sell_above",
                "score_buy", "score_sell", "initial_capital", "fee_rate", "tax_rate",
                "position_size", "stop_loss_pct", "take_profit_pct", "max_hold_days",
            )},
            {
                "period": "1y", "output_md": None, "output_excel": None,
                "output_dir": "output", "force_refresh": False,
                "ma_short_windows": None, "ma_long_windows": None,
                "rsi_buy_below": None, "rsi_sell_above": None, "score_buy": None,
                "score_sell": None, "initial_capital": 100000.0, "fee_rate": 0.001425,
                "tax_rate": 0.003, "position_size": 1.0, "stop_loss_pct": None,
                "take_profit_pct": None, "max_hold_days": None,
            },
        )

        with patch.object(sys, "argv", ["walk_forward_report.py", "--stock", "2330", "--strategy", "ma_cross"]):
            walk = walk_forward_report._parse_args()
        self.assertEqual(
            {name: getattr(walk, name) for name in (
                "period", "output_md", "output_excel", "output_dir", "force_refresh",
                "ma_short_windows", "ma_long_windows", "rsi_buy_below", "rsi_sell_above",
                "score_buy", "score_sell", "train_days", "test_days", "step_days",
                "sort_by", "initial_capital", "fee_rate", "tax_rate", "position_size",
                "stop_loss_pct", "take_profit_pct", "max_hold_days",
            )},
            {
                "period": "1y", "output_md": None, "output_excel": None,
                "output_dir": "output", "force_refresh": False,
                "ma_short_windows": None, "ma_long_windows": None,
                "rsi_buy_below": None, "rsi_sell_above": None, "score_buy": None,
                "score_sell": None, "train_days": 504, "test_days": 126,
                "step_days": None, "sort_by": "Train Sharpe Ratio",
                "initial_capital": 100000.0, "fee_rate": 0.001425, "tax_rate": 0.003,
                "position_size": 1.0, "stop_loss_pct": None, "take_profit_pct": None,
                "max_hold_days": None,
            },
        )

    def test_custom_values_keep_types_and_current_negative_grid_behavior(self):
        backtest = backtest_report._parse_args([
            "--stock", "2330", "--strategy", "score", "--period", "2y", "--force-refresh",
            "--initial-capital", "250000", "--fee-rate", "0.001", "--tax-rate", "0.002",
            "--position-size", "0.65", "--stop-loss-pct", "0.08", "--take-profit-pct", "0.16",
            "--max-hold-days", "45", "--short-window", "7", "--long-window", "42",
            "--rsi-buy-below", "25.5", "--rsi-sell-above", "77.5", "--score-buy", "4.5",
            "--score-sell", "-1.5", "--output-md", "report.md", "--output-excel", "report.xlsx",
            "--output-dir", "artifacts",
        ])
        self.assertIsInstance(backtest.initial_capital, float)
        self.assertEqual(backtest.initial_capital, 250000.0)
        self.assertEqual(backtest.max_hold_days, 45)
        self.assertEqual(backtest.score_sell, -1.5)
        self.assertTrue(backtest.force_refresh)

        values = [
            "--stock", "2330", "--strategy", "all", "--period", "2y", "--force-refresh",
            "--ma-short-windows", "5, 10, 10", "--ma-long-windows", "30,60",
            "--rsi-buy-below", "25,35", "--rsi-sell-above", "65,75", "--score-buy", "4,6",
            "--score-sell=-2,-4", "--initial-capital", "250000", "--fee-rate", "0.001",
            "--tax-rate", "0.002", "--position-size", "0.65", "--stop-loss-pct", "0.08",
            "--take-profit-pct", "0.16", "--max-hold-days", "45",
        ]
        with patch.object(sys, "argv", ["parameter_sweep_report.py", *values]):
            parameter = parameter_sweep_report._parse_args()
        self.assertEqual(parameter.ma_short_windows, (5, 10, 10))
        self.assertEqual(parameter.ma_long_windows, (30, 60))
        self.assertEqual(parameter.score_sell, (-2, -4))
        self.assertEqual(parameter.initial_capital, 250000.0)
        self.assertEqual(parameter.max_hold_days, 45)

        with patch.object(sys, "argv", ["walk_forward_report.py", *values, "--train-days", "504", "--test-days", "126", "--step-days", "21", "--sort-by", "Train Total Return %"]):
            walk = walk_forward_report._parse_args()
        self.assertEqual(walk.ma_short_windows, (5, 10, 10))
        self.assertEqual(walk.score_sell, (-2, -4))
        self.assertEqual(walk.train_days, 504)
        self.assertEqual(walk.step_days, 21)
        self.assertEqual(walk.sort_by, "Train Total Return %")

    def test_grid_parser_preserves_order_duplicates_whitespace_and_rejects_bad_values(self):
        self.assertEqual(parse_int_tuple(" 5, 5, -2 "), (5, 5, -2))
        for value in ("", "   ", "5,a,20"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    parse_int_tuple(value)

    def test_strategy_parameter_builder_characterizes_all_backtest_strategies(self):
        args = SimpleNamespace(short_window=7, long_window=42, rsi_buy_below=25.5, rsi_sell_above=77.5, score_buy=4.5, score_sell=-1.5)
        before = vars(args).copy()
        self.assertEqual(backtest_report._build_strategy_params(args, "ma_cross_strategy"), {"short_window": 7, "long_window": 42})
        self.assertEqual(backtest_report._build_strategy_params(args, "rsi_strategy"), {"buy_below": 25.5, "sell_above": 77.5})
        self.assertEqual(backtest_report._build_strategy_params(args, "score_strategy"), {"buy_score": 4.5, "sell_score": -1.5})
        args.score_buy = None
        args.score_sell = None
        self.assertEqual(backtest_report._build_strategy_params(args, "score_strategy"), {})
        self.assertEqual(backtest_report._build_strategy_params(args, "other_strategy"), {})
        self.assertEqual(vars(args), {**before, "score_buy": None, "score_sell": None})


class ForwardingContractTests(unittest.TestCase):
    def test_backtest_report_forwards_engine_kwargs_and_matching_metadata(self):
        analysis = MagicMock(indicator_df=pd.DataFrame())
        strategy_df = pd.DataFrame(index=pd.date_range("2024-01-01", periods=2))
        strategy = MagicMock(return_value=strategy_df)
        args = SimpleNamespace(
            stock="2330", strategy="ma_cross", period="2y", output_md="report.md", output_excel=None,
            output_dir="output", force_refresh=True, short_window=7, long_window=42,
            rsi_buy_below=25.5, rsi_sell_above=77.5, score_buy=4.5, score_sell=-1.5,
            initial_capital=250000.0, fee_rate=0.001, tax_rate=0.002, position_size=0.65,
            stop_loss_pct=0.08, take_profit_pct=0.16, max_hold_days=45,
        )
        with patch.object(backtest_report, "_parse_args", return_value=args), \
             patch.object(backtest_report, "analyze_stock", return_value=analysis), \
             patch.object(backtest_report, "run_backtest", return_value={"Total Return %": 1.0}) as run, \
             patch.object(backtest_report, "export_backtest_report_markdown") as export_md, \
             patch.dict(backtest_report.STRATEGIES, {"ma_cross_strategy": strategy}, clear=True):
            self.assertIsNone(backtest_report.main())
        strategy.assert_called_once_with(analysis.indicator_df, short_window=7, long_window=42)
        run.assert_called_once_with(strategy_df, initial_capital=250000.0, fee_rate=0.001, tax_rate=0.002, position_size=0.65, stop_loss_pct=0.08, take_profit_pct=0.16, max_hold_days=45)
        result = export_md.call_args.args[0]
        self.assertEqual(result["Parameters"]["backtest"], run.call_args.kwargs)
        self.assertEqual(result["Parameters"]["strategy"], {"short_window": 7, "long_window": 42})

    def test_parameter_sweep_forwards_all_engine_and_grid_kwargs_and_metadata(self):
        args = [
            "parameter_sweep_report.py", "--stock", "2330", "--strategy", "all", "--period", "2y", "--force-refresh",
            "--ma-short-windows", "5,10", "--ma-long-windows", "30,60", "--rsi-buy-below", "25,35", "--rsi-sell-above", "65,75",
            "--score-buy", "4,6", "--score-sell=-2,-4", "--initial-capital", "250000", "--fee-rate", "0.001", "--tax-rate", "0.002",
            "--position-size", "0.65", "--stop-loss-pct", "0.08", "--take-profit-pct", "0.16", "--max-hold-days", "45", "--output-md", "report.md",
        ]
        with patch.object(sys, "argv", args), \
             patch.object(parameter_sweep_report, "run_parameter_sweep", return_value=pd.DataFrame()) as run, \
             patch.object(parameter_sweep_report, "export_parameter_sweep_report_markdown") as export_md:
            self.assertIsNone(parameter_sweep_report.main())
        run.assert_called_once_with(
            stock_id="2330", strategy="all", period="2y", force_refresh=True,
            ma_short_windows=(5, 10), ma_long_windows=(30, 60), rsi_buy_below=(25, 35), rsi_sell_above=(65, 75), score_buy=(4, 6), score_sell=(-2, -4),
            initial_capital=250000.0, fee_rate=0.001, tax_rate=0.002, stop_loss_pct=0.08, take_profit_pct=0.16, max_hold_days=45, position_size=0.65,
        )
        result = export_md.call_args.args[0]
        self.assertEqual(result["Parameters"]["strategy"], {"ma_short_windows": (5, 10), "ma_long_windows": (30, 60), "rsi_buy_below": (25, 35), "rsi_sell_above": (65, 75), "score_buy": (4, 6), "score_sell": (-2, -4)})
        self.assertEqual(result["Parameters"]["backtest"], {"initial_capital": 250000.0, "fee_rate": 0.001, "tax_rate": 0.002, "position_size": 0.65, "stop_loss_pct": 0.08, "take_profit_pct": 0.16, "max_hold_days": 45})

    def test_walk_forward_forwards_all_engine_grid_and_window_kwargs_and_metadata(self):
        args = [
            "walk_forward_report.py", "--stock", "2330", "--strategy", "all", "--period", "2y", "--force-refresh",
            "--ma-short-windows", "5,10", "--ma-long-windows", "30,60", "--rsi-buy-below", "25,35", "--rsi-sell-above", "65,75",
            "--score-buy", "4,6", "--score-sell=-2,-4", "--train-days", "504", "--test-days", "126", "--step-days", "21",
            "--sort-by", "Train Total Return %", "--initial-capital", "250000", "--fee-rate", "0.001", "--tax-rate", "0.002",
            "--position-size", "0.65", "--stop-loss-pct", "0.08", "--take-profit-pct", "0.16", "--max-hold-days", "45", "--output-md", "report.md",
        ]
        with patch.object(sys, "argv", args), \
             patch.object(walk_forward_report, "run_walk_forward", return_value=pd.DataFrame()) as run, \
             patch.object(walk_forward_report, "export_walk_forward_report_markdown") as export_md:
            self.assertIsNone(walk_forward_report.main())
        run.assert_called_once_with(
            stock_id="2330", strategy="all", period="2y", force_refresh=True, train_days=504, test_days=126, step_days=21, sort_by="Train Total Return %", initial_capital=250000.0, fee_rate=0.001, tax_rate=0.002, position_size=0.65, stop_loss_pct=0.08, take_profit_pct=0.16, max_hold_days=45, ma_short_windows=(5, 10), ma_long_windows=(30, 60), rsi_buy_below=(25, 35), rsi_sell_above=(65, 75), score_buy=(4, 6), score_sell=(-2, -4),
        )
        result = export_md.call_args.args[0]
        self.assertEqual(result["Parameters"]["strategy"]["ma_short_windows"], (5, 10))
        self.assertEqual(result["Parameters"]["backtest"]["max_hold_days"], 45)
        self.assertEqual(result["Parameters"]["window"], {"train_days": 504, "test_days": 126, "step_days": 21, "sort_by": "Train Total Return %"})

    def test_unified_cli_routes_preserve_child_program_and_status(self):
        routes = [("backtest-report", twstock_cli.backtest_report, "backtest_report.py"), ("parameter-sweep", twstock_cli.parameter_sweep_report, "parameter_sweep_report.py"), ("walk-forward", twstock_cli.walk_forward_report, "walk_forward_report.py")]
        for route, module, program_name in routes:
            with self.subTest(route=route):
                captured = []

                def fake_main():
                    captured.append(sys.argv[:])
                    return 7

                with patch.object(module, "main", side_effect=fake_main) as child:
                    status = twstock_cli.main([route, "--stock", "2330", "--strategy", "ma_cross", "--output-md", "report.md"])
                self.assertEqual(status, 7)
                child.assert_called_once_with()
                self.assertEqual(captured, [[program_name, "--stock", "2330", "--strategy", "ma_cross", "--output-md", "report.md"]])


class HelpAndErrorContractTests(unittest.TestCase):
    def _direct_help(self, module, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                if module is backtest_report:
                    module._parse_args(argv)
                else:
                    with patch.object(sys, "argv", [module.__name__.rsplit(".", 1)[-1], *argv]):
                        module._parse_args()
        self.assertEqual(raised.exception.code, 0)
        self.assertNotIn("Traceback", output.getvalue())
        return output.getvalue()

    def test_direct_help_contains_current_command_contract(self):
        backtest_help = self._direct_help(backtest_report, ["--help"])
        for flag in ("--initial-capital", "--fee-rate", "--tax-rate", "--position-size", "--short-window", "--rsi-buy-below"):
            self.assertIn(flag, backtest_help)
        self.assertIn("Backtest Report Generator", backtest_help)
        self.assertIn("next-bar Open", backtest_help)
        parameter_help = self._direct_help(parameter_sweep_report, ["--help"])
        for flag in ("--ma-short-windows", "--ma-long-windows", "--score-sell", "--initial-capital", "--max-hold-days"):
            self.assertIn(flag, parameter_help)
        self.assertIn("Parameter Sweep Report CLI", parameter_help)
        walk_help = self._direct_help(walk_forward_report, ["--help"])
        for flag in ("--ma-short-windows", "--score-sell", "--train-days", "--test-days", "--step-days", "--sort-by", "--position-size"):
            self.assertIn(flag, walk_help)
        self.assertIn("Walk Forward Report CLI", walk_help)

    def test_required_parser_errors_are_exit_two(self):
        with self.assertRaises(SystemExit) as backtest_error:
            backtest_report._parse_args([])
        self.assertEqual(backtest_error.exception.code, 2)
        with patch.object(sys, "argv", ["parameter_sweep_report.py", "--stock", "2330"]):
            with self.assertRaises(SystemExit) as parameter_error:
                parameter_sweep_report._parse_args()
        self.assertEqual(parameter_error.exception.code, 2)
        with patch.object(sys, "argv", ["walk_forward_report.py", "--stock", "2330"]):
            with self.assertRaises(SystemExit) as walk_error:
                walk_forward_report._parse_args()
        self.assertEqual(walk_error.exception.code, 2)

    def test_unified_route_help_exits_zero_without_using_global_entrypoint(self):
        for route in ("backtest-report", "parameter-sweep", "walk-forward"):
            with self.subTest(route=route), contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(SystemExit) as raised:
                    twstock_cli.main([route, "--help"])
            self.assertEqual(raised.exception.code, 0)
            self.assertIn(route, output.getvalue())


if __name__ == "__main__":
    unittest.main()
