from __future__ import annotations

import argparse
import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tw_stock_tool.cli import backtest_report, parameter_sweep_report, walk_forward_report
from tw_stock_tool.cli import twstock_cli


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MINIMAL_ARGS = ["--stock", "2330", "--strategy", "ma_cross"]
MODULES = {
    "backtest": (backtest_report, "backtest_report.py"),
    "sweep": (parameter_sweep_report, "parameter_sweep_report.py"),
    "walk": (walk_forward_report, "walk_forward_report.py"),
}
WRAPPERS = {
    "backtest": "backtest_report.py",
    "sweep": "parameter_sweep_report.py",
    "walk": "walk_forward_report.py",
}


def _callable_name(value: object) -> str | None:
    if value is None:
        return None
    return f"{value.__module__}.{value.__qualname__}"


def _metadata_value(value: object) -> object:
    if value is argparse.SUPPRESS:
        return "<SUPPRESS>"
    if callable(value):
        return _callable_name(value)
    if isinstance(value, tuple):
        return list(value)
    return value


def _normalized_metadata(parser: argparse.ArgumentParser) -> dict[str, object]:
    return {
        "description": parser.description,
        "epilog": parser.epilog,
        "actions": [
            {
                "option_strings": list(action.option_strings),
                "dest": action.dest,
                "required": action.required,
                "action_class": type(action).__name__,
                "nargs": _metadata_value(action.nargs),
                "const": _metadata_value(action.const),
                "default": _metadata_value(action.default),
                "default_type": type(action.default).__name__,
                "type": _callable_name(action.type),
                "choices": _metadata_value(action.choices),
                "metavar": _metadata_value(action.metavar),
                "help": action.help,
            }
            for action in parser._actions
        ],
    }


def _expected_action(
    option_strings: list[str],
    dest: str,
    action_class: str,
    nargs: object,
    const: object,
    default: object,
    default_type: str,
    type_name: str | None,
    help_text: str | None,
    *,
    required: bool = False,
    choices: object = None,
    metavar: object = None,
) -> dict[str, object]:
    return {
        "option_strings": option_strings,
        "dest": dest,
        "required": required,
        "action_class": action_class,
        "nargs": nargs,
        "const": const,
        "default": default,
        "default_type": default_type,
        "type": type_name,
        "choices": choices,
        "metavar": metavar,
        "help": help_text,
    }


HELP_ACTION = _expected_action(
    ["-h", "--help"], "help", "_HelpAction", 0, None, "<SUPPRESS>", "str", None,
    "show this help message and exit",
)
STOCK_ACTION = _expected_action(
    ["--stock"], "stock", "_StoreAction", None, None, None, "NoneType", None,
    "Stock ID (e.g., 2330)", required=True,
)
PERIOD_ACTION = _expected_action(
    ["--period"], "period", "_StoreAction", None, None, "1y", "str", None,
    "Data period",
)
OUTPUT_MD_ACTION = _expected_action(
    ["--output-md"], "output_md", "_StoreAction", "?", "", None, "NoneType", None,
    "Export Markdown report",
)
OUTPUT_EXCEL_ACTION = _expected_action(
    ["--output-excel"], "output_excel", "_StoreAction", "?", "", None, "NoneType", None,
    "Export Excel report",
)
OUTPUT_DIR_ACTION = _expected_action(
    ["--output-dir"], "output_dir", "_StoreAction", None, None, "output", "str", None,
    "Default output directory",
)
FORCE_REFRESH_ACTION = _expected_action(
    ["--force-refresh"], "force_refresh", "_StoreTrueAction", 0, True, False, "bool", None,
    "Redownload data ignoring cache",
)
INITIAL_CAPITAL_BACKTEST = _expected_action(
    ["--initial-capital"], "initial_capital", "_StoreAction", None, None, 100000.0,
    "float", "builtins.float", "Initial capital",
)
INITIAL_CAPITAL_CONFIG = _expected_action(
    ["--initial-capital"], "initial_capital", "_StoreAction", None, None, 100000,
    "int", "builtins.float", "Initial capital (default from config)",
)
FEE_BACKTEST = _expected_action(
    ["--fee-rate"], "fee_rate", "_StoreAction", None, None, 0.001425,
    "float", "builtins.float", "Backtest fee rate assumption",
)
FEE_CONFIG = _expected_action(
    ["--fee-rate"], "fee_rate", "_StoreAction", None, None, 0.001425,
    "float", "builtins.float", "Fee rate (default from config)",
)
TAX_BACKTEST = _expected_action(
    ["--tax-rate"], "tax_rate", "_StoreAction", None, None, 0.003,
    "float", "builtins.float", "Backtest tax rate assumption",
)
TAX_CONFIG = _expected_action(
    ["--tax-rate"], "tax_rate", "_StoreAction", None, None, 0.003,
    "float", "builtins.float", "Tax rate (default from config)",
)
POSITION_BACKTEST = _expected_action(
    ["--position-size"], "position_size", "_StoreAction", None, None, 1.0,
    "float", "builtins.float", "Backtest position size",
)
POSITION_CONFIG = _expected_action(
    ["--position-size"], "position_size", "_StoreAction", None, None, 1.0,
    "float", "builtins.float", "Position size (0 to 1.0, default 1.0)",
)
STOP_BACKTEST = _expected_action(
    ["--stop-loss-pct"], "stop_loss_pct", "_StoreAction", None, None, None,
    "NoneType", "builtins.float", "Stop-loss threshold percentage",
)
STOP_CONFIG = _expected_action(
    ["--stop-loss-pct"], "stop_loss_pct", "_StoreAction", None, None, None,
    "NoneType", "builtins.float", "Stop loss percentage (e.g., 0.05 for 5%%)",
)
TAKE_BACKTEST = _expected_action(
    ["--take-profit-pct"], "take_profit_pct", "_StoreAction", None, None, None,
    "NoneType", "builtins.float", "Take-profit threshold percentage",
)
TAKE_CONFIG = _expected_action(
    ["--take-profit-pct"], "take_profit_pct", "_StoreAction", None, None, None,
    "NoneType", "builtins.float", "Take profit percentage",
)
MAX_BACKTEST = _expected_action(
    ["--max-hold-days"], "max_hold_days", "_StoreAction", None, None, None,
    "NoneType", "builtins.int", "Max holding days",
)
MAX_CONFIG = _expected_action(
    ["--max-hold-days"], "max_hold_days", "_StoreAction", None, None, None,
    "NoneType", "builtins.int", "Maximum holding days",
)
INT_RANGE = "tw_stock_tool.cli.parsers.parse_int_tuple"
BACKTEST_RSI_BUY = _expected_action(
    ["--rsi-buy-below"], "rsi_buy_below", "_StoreAction", None, None, 30.0,
    "float", "builtins.float", "RSI threshold (buy below)",
)
BACKTEST_RSI_SELL = _expected_action(
    ["--rsi-sell-above"], "rsi_sell_above", "_StoreAction", None, None, 70.0,
    "float", "builtins.float", "RSI threshold (sell above)",
)
BACKTEST_SCORE_BUY = _expected_action(
    ["--score-buy"], "score_buy", "_StoreAction", None, None, None,
    "NoneType", "builtins.float", "Score threshold (buy)",
)
BACKTEST_SCORE_SELL = _expected_action(
    ["--score-sell"], "score_sell", "_StoreAction", None, None, None,
    "NoneType", "builtins.float", "Score threshold (sell)",
)
RANGE_RSI_BUY = _expected_action(
    ["--rsi-buy-below"], "rsi_buy_below", "_StoreAction", None, None, None,
    "NoneType", INT_RANGE, "Comma-separated integers",
)
RANGE_RSI_SELL = _expected_action(
    ["--rsi-sell-above"], "rsi_sell_above", "_StoreAction", None, None, None,
    "NoneType", INT_RANGE, "Comma-separated integers",
)
RANGE_SCORE_BUY = _expected_action(
    ["--score-buy"], "score_buy", "_StoreAction", None, None, None,
    "NoneType", INT_RANGE, "Comma-separated integers",
)
RANGE_SCORE_SELL = _expected_action(
    ["--score-sell"], "score_sell", "_StoreAction", None, None, None,
    "NoneType", INT_RANGE, "Comma-separated integers, can be negative",
)
MA_SHORT = _expected_action(
    ["--ma-short-windows"], "ma_short_windows", "_StoreAction", None, None, None,
    "NoneType", INT_RANGE, "Comma-separated integers, e.g. 5,10",
)
MA_LONG = _expected_action(
    ["--ma-long-windows"], "ma_long_windows", "_StoreAction", None, None, None,
    "NoneType", INT_RANGE, "Comma-separated integers",
)
BACKTEST_SHORT = _expected_action(
    ["--short-window"], "short_window", "_StoreAction", None, None, 5,
    "int", "builtins.int", "Short MA window",
)
BACKTEST_LONG = _expected_action(
    ["--long-window"], "long_window", "_StoreAction", None, None, 20,
    "int", "builtins.int", "Long MA window",
)
TRAIN_DAYS = _expected_action(
    ["--train-days"], "train_days", "_StoreAction", None, None, 504,
    "int", "builtins.int", "Number of training days per window",
)
TEST_DAYS = _expected_action(
    ["--test-days"], "test_days", "_StoreAction", None, None, 126,
    "int", "builtins.int", "Number of test days per window",
)
STEP_DAYS = _expected_action(
    ["--step-days"], "step_days", "_StoreAction", None, None, None,
    "NoneType", "builtins.int", "Number of days to step forward per window",
)
SORT_BY = _expected_action(
    ["--sort-by"], "sort_by", "_StoreAction", None, None, "Train Sharpe Ratio",
    "str", None, "Metric to select best parameters",
)


EXPECTED_METADATA = {
    "backtest": {
        "description": "Backtest Report Generator",
        "epilog": "Backtest fills use next-bar Open as a research assumption.",
        "actions": [
            HELP_ACTION, STOCK_ACTION,
            _expected_action(["--strategy"], "strategy", "_StoreAction", None, None, None,
                             "NoneType", None, "Strategy name (e.g., ma_cross)", required=True),
            PERIOD_ACTION, INITIAL_CAPITAL_BACKTEST, OUTPUT_MD_ACTION, OUTPUT_EXCEL_ACTION,
            OUTPUT_DIR_ACTION, FORCE_REFRESH_ACTION, BACKTEST_SHORT, BACKTEST_LONG,
            BACKTEST_RSI_BUY, BACKTEST_RSI_SELL, BACKTEST_SCORE_BUY, BACKTEST_SCORE_SELL,
            FEE_BACKTEST, TAX_BACKTEST, POSITION_BACKTEST, STOP_BACKTEST, TAKE_BACKTEST,
            MAX_BACKTEST,
        ],
    },
    "sweep": {
        "description": "Parameter Sweep Report CLI",
        "epilog": None,
        "actions": [
            HELP_ACTION, STOCK_ACTION,
            _expected_action(["--strategy"], "strategy", "_StoreAction", None, None, None,
                             "NoneType", None, "Strategy name (e.g., ma_cross, all)", required=True),
            PERIOD_ACTION, OUTPUT_MD_ACTION, OUTPUT_EXCEL_ACTION, OUTPUT_DIR_ACTION,
            FORCE_REFRESH_ACTION, MA_SHORT, MA_LONG, RANGE_RSI_BUY, RANGE_RSI_SELL,
            RANGE_SCORE_BUY, RANGE_SCORE_SELL, INITIAL_CAPITAL_CONFIG, FEE_CONFIG, TAX_CONFIG,
            POSITION_CONFIG, STOP_CONFIG, TAKE_CONFIG, MAX_CONFIG,
        ],
    },
    "walk": {
        "description": "Walk Forward Report CLI",
        "epilog": None,
        "actions": [
            HELP_ACTION, STOCK_ACTION,
            _expected_action(["--strategy"], "strategy", "_StoreAction", None, None, None,
                             "NoneType", None, "Strategy name (e.g., ma_cross, all)", required=True),
            PERIOD_ACTION, OUTPUT_MD_ACTION, OUTPUT_EXCEL_ACTION, OUTPUT_DIR_ACTION,
            FORCE_REFRESH_ACTION, MA_SHORT, MA_LONG, RANGE_RSI_BUY, RANGE_RSI_SELL,
            RANGE_SCORE_BUY, RANGE_SCORE_SELL, TRAIN_DAYS, TEST_DAYS, STEP_DAYS, SORT_BY,
            INITIAL_CAPITAL_CONFIG, FEE_CONFIG, TAX_CONFIG, POSITION_CONFIG, STOP_CONFIG,
            TAKE_CONFIG, MAX_CONFIG,
        ],
    },
}


DEFAULT_NAMESPACES = {
    "backtest": {
        "stock": "2330", "strategy": "ma_cross", "period": "1y",
        "initial_capital": 100000.0, "output_md": None, "output_excel": None,
        "output_dir": "output", "force_refresh": False, "short_window": 5,
        "long_window": 20, "rsi_buy_below": 30.0, "rsi_sell_above": 70.0,
        "score_buy": None, "score_sell": None, "fee_rate": 0.001425,
        "tax_rate": 0.003, "position_size": 1.0, "stop_loss_pct": None,
        "take_profit_pct": None, "max_hold_days": None,
    },
    "sweep": {
        "stock": "2330", "strategy": "ma_cross", "period": "1y",
        "output_md": None, "output_excel": None, "output_dir": "output",
        "force_refresh": False, "ma_short_windows": None, "ma_long_windows": None,
        "rsi_buy_below": None, "rsi_sell_above": None, "score_buy": None,
        "score_sell": None, "initial_capital": 100000, "fee_rate": 0.001425,
        "tax_rate": 0.003, "position_size": 1.0, "stop_loss_pct": None,
        "take_profit_pct": None, "max_hold_days": None,
    },
    "walk": {
        "stock": "2330", "strategy": "ma_cross", "period": "1y",
        "output_md": None, "output_excel": None, "output_dir": "output",
        "force_refresh": False, "ma_short_windows": None, "ma_long_windows": None,
        "rsi_buy_below": None, "rsi_sell_above": None, "score_buy": None,
        "score_sell": None, "train_days": 504, "test_days": 126, "step_days": None,
        "sort_by": "Train Sharpe Ratio", "initial_capital": 100000,
        "fee_rate": 0.001425, "tax_rate": 0.003, "position_size": 1.0,
        "stop_loss_pct": None, "take_profit_pct": None, "max_hold_days": None,
    },
}


EXPLICIT_ARGS = {
    "backtest": MINIMAL_ARGS + [
        "--period", "2y", "--output-md", "custom/report.md",
        "--output-excel", "custom/report.xlsx", "--output-dir", "custom/out",
        "--force-refresh", "--initial-capital", "123456.5", "--fee-rate", "0.002",
        "--tax-rate", "0.004", "--position-size", "0.75", "--stop-loss-pct", "0.05",
        "--take-profit-pct", "0.1", "--max-hold-days", "12", "--short-window", "7",
        "--long-window", "33", "--rsi-buy-below", "25.5", "--rsi-sell-above", "70.5",
        "--score-buy", "4.5", "--score-sell=-2.5",
    ],
    "sweep": MINIMAL_ARGS + [
        "--period", "2y", "--output-md", "custom/report.md",
        "--output-excel", "custom/report.xlsx", "--output-dir", "custom/out",
        "--force-refresh", "--ma-short-windows", "5, 10, 20",
        "--ma-long-windows", "30,60", "--rsi-buy-below", "25,35",
        "--rsi-sell-above", "65,75", "--score-buy", "4,6", "--score-sell=-2,-4",
        "--initial-capital", "123456.5", "--fee-rate", "0.002", "--tax-rate", "0.004",
        "--position-size", "0.75", "--stop-loss-pct", "0.05",
        "--take-profit-pct", "0.1", "--max-hold-days", "12",
    ],
    "walk": MINIMAL_ARGS + [
        "--period", "2y", "--output-md", "custom/report.md",
        "--output-excel", "custom/report.xlsx", "--output-dir", "custom/out",
        "--force-refresh", "--ma-short-windows", "5, 10, 20",
        "--ma-long-windows", "30,60", "--rsi-buy-below", "25,35",
        "--rsi-sell-above", "65,75", "--score-buy", "4,6", "--score-sell=-2,-4",
        "--train-days", "252", "--test-days", "63", "--step-days", "21",
        "--sort-by", "Train Total Return %", "--initial-capital", "123456.5",
        "--fee-rate", "0.002", "--tax-rate", "0.004", "--position-size", "0.75",
        "--stop-loss-pct", "0.05", "--take-profit-pct", "0.1", "--max-hold-days", "12",
    ],
}


EXPLICIT_NAMESPACES = {
    "backtest": {
        "stock": "2330", "strategy": "ma_cross", "period": "2y",
        "initial_capital": 123456.5, "output_md": "custom/report.md",
        "output_excel": "custom/report.xlsx", "output_dir": "custom/out",
        "force_refresh": True, "short_window": 7, "long_window": 33,
        "rsi_buy_below": 25.5, "rsi_sell_above": 70.5, "score_buy": 4.5,
        "score_sell": -2.5, "fee_rate": 0.002, "tax_rate": 0.004,
        "position_size": 0.75, "stop_loss_pct": 0.05, "take_profit_pct": 0.1,
        "max_hold_days": 12,
    },
    "sweep": {
        "stock": "2330", "strategy": "ma_cross", "period": "2y",
        "output_md": "custom/report.md", "output_excel": "custom/report.xlsx",
        "output_dir": "custom/out", "force_refresh": True,
        "ma_short_windows": (5, 10, 20), "ma_long_windows": (30, 60),
        "rsi_buy_below": (25, 35), "rsi_sell_above": (65, 75),
        "score_buy": (4, 6), "score_sell": (-2, -4),
        "initial_capital": 123456.5, "fee_rate": 0.002, "tax_rate": 0.004,
        "position_size": 0.75, "stop_loss_pct": 0.05, "take_profit_pct": 0.1,
        "max_hold_days": 12,
    },
    "walk": {
        "stock": "2330", "strategy": "ma_cross", "period": "2y",
        "output_md": "custom/report.md", "output_excel": "custom/report.xlsx",
        "output_dir": "custom/out", "force_refresh": True,
        "ma_short_windows": (5, 10, 20), "ma_long_windows": (30, 60),
        "rsi_buy_below": (25, 35), "rsi_sell_above": (65, 75),
        "score_buy": (4, 6), "score_sell": (-2, -4),
        "train_days": 252, "test_days": 63, "step_days": 21,
        "sort_by": "Train Total Return %", "initial_capital": 123456.5,
        "fee_rate": 0.002, "tax_rate": 0.004, "position_size": 0.75,
        "stop_loss_pct": 0.05, "take_profit_pct": 0.1, "max_hold_days": 12,
    },
}


HELP_SNAPSHOTS = {
    "backtest": """usage: backtest_report.py [-h] --stock STOCK --strategy STRATEGY [--period PERIOD] [--initial-capital INITIAL_CAPITAL]
                          [--output-md [OUTPUT_MD]] [--output-excel [OUTPUT_EXCEL]] [--output-dir OUTPUT_DIR]
                          [--force-refresh] [--short-window SHORT_WINDOW] [--long-window LONG_WINDOW]
                          [--rsi-buy-below RSI_BUY_BELOW] [--rsi-sell-above RSI_SELL_ABOVE] [--score-buy SCORE_BUY]
                          [--score-sell SCORE_SELL] [--fee-rate FEE_RATE] [--tax-rate TAX_RATE]
                          [--position-size POSITION_SIZE] [--stop-loss-pct STOP_LOSS_PCT]
                          [--take-profit-pct TAKE_PROFIT_PCT] [--max-hold-days MAX_HOLD_DAYS]

Backtest Report Generator

options:
  -h, --help            show this help message and exit
  --stock STOCK         Stock ID (e.g., 2330)
  --strategy STRATEGY   Strategy name (e.g., ma_cross)
  --period PERIOD       Data period
  --initial-capital INITIAL_CAPITAL
                        Initial capital
  --output-md [OUTPUT_MD]
                        Export Markdown report
  --output-excel [OUTPUT_EXCEL]
                        Export Excel report
  --output-dir OUTPUT_DIR
                        Default output directory
  --force-refresh       Redownload data ignoring cache
  --short-window SHORT_WINDOW
                        Short MA window
  --long-window LONG_WINDOW
                        Long MA window
  --rsi-buy-below RSI_BUY_BELOW
                        RSI threshold (buy below)
  --rsi-sell-above RSI_SELL_ABOVE
                        RSI threshold (sell above)
  --score-buy SCORE_BUY
                        Score threshold (buy)
  --score-sell SCORE_SELL
                        Score threshold (sell)
  --fee-rate FEE_RATE   Backtest fee rate assumption
  --tax-rate TAX_RATE   Backtest tax rate assumption
  --position-size POSITION_SIZE
                        Backtest position size
  --stop-loss-pct STOP_LOSS_PCT
                        Stop-loss threshold percentage
  --take-profit-pct TAKE_PROFIT_PCT
                        Take-profit threshold percentage
  --max-hold-days MAX_HOLD_DAYS
                        Max holding days

Backtest fills use next-bar Open as a research assumption.
""",
    "sweep": """usage: parameter_sweep_report.py [-h] --stock STOCK --strategy STRATEGY [--period PERIOD] [--output-md [OUTPUT_MD]]
                                 [--output-excel [OUTPUT_EXCEL]] [--output-dir OUTPUT_DIR] [--force-refresh]
                                 [--ma-short-windows MA_SHORT_WINDOWS] [--ma-long-windows MA_LONG_WINDOWS]
                                 [--rsi-buy-below RSI_BUY_BELOW] [--rsi-sell-above RSI_SELL_ABOVE]
                                 [--score-buy SCORE_BUY] [--score-sell SCORE_SELL] [--initial-capital INITIAL_CAPITAL]
                                 [--fee-rate FEE_RATE] [--tax-rate TAX_RATE] [--position-size POSITION_SIZE]
                                 [--stop-loss-pct STOP_LOSS_PCT] [--take-profit-pct TAKE_PROFIT_PCT]
                                 [--max-hold-days MAX_HOLD_DAYS]

Parameter Sweep Report CLI

options:
  -h, --help            show this help message and exit
  --stock STOCK         Stock ID (e.g., 2330)
  --strategy STRATEGY   Strategy name (e.g., ma_cross, all)
  --period PERIOD       Data period
  --output-md [OUTPUT_MD]
                        Export Markdown report
  --output-excel [OUTPUT_EXCEL]
                        Export Excel report
  --output-dir OUTPUT_DIR
                        Default output directory
  --force-refresh       Redownload data ignoring cache
  --ma-short-windows MA_SHORT_WINDOWS
                        Comma-separated integers, e.g. 5,10
  --ma-long-windows MA_LONG_WINDOWS
                        Comma-separated integers
  --rsi-buy-below RSI_BUY_BELOW
                        Comma-separated integers
  --rsi-sell-above RSI_SELL_ABOVE
                        Comma-separated integers
  --score-buy SCORE_BUY
                        Comma-separated integers
  --score-sell SCORE_SELL
                        Comma-separated integers, can be negative
  --initial-capital INITIAL_CAPITAL
                        Initial capital (default from config)
  --fee-rate FEE_RATE   Fee rate (default from config)
  --tax-rate TAX_RATE   Tax rate (default from config)
  --position-size POSITION_SIZE
                        Position size (0 to 1.0, default 1.0)
  --stop-loss-pct STOP_LOSS_PCT
                        Stop loss percentage (e.g., 0.05 for 5%)
  --take-profit-pct TAKE_PROFIT_PCT
                        Take profit percentage
  --max-hold-days MAX_HOLD_DAYS
                        Maximum holding days
""",
    "walk": """usage: walk_forward_report.py [-h] --stock STOCK --strategy STRATEGY [--period PERIOD] [--output-md [OUTPUT_MD]]
                              [--output-excel [OUTPUT_EXCEL]] [--output-dir OUTPUT_DIR] [--force-refresh]
                              [--ma-short-windows MA_SHORT_WINDOWS] [--ma-long-windows MA_LONG_WINDOWS]
                              [--rsi-buy-below RSI_BUY_BELOW] [--rsi-sell-above RSI_SELL_ABOVE]
                              [--score-buy SCORE_BUY] [--score-sell SCORE_SELL] [--train-days TRAIN_DAYS]
                              [--test-days TEST_DAYS] [--step-days STEP_DAYS] [--sort-by SORT_BY]
                              [--initial-capital INITIAL_CAPITAL] [--fee-rate FEE_RATE] [--tax-rate TAX_RATE]
                              [--position-size POSITION_SIZE] [--stop-loss-pct STOP_LOSS_PCT]
                              [--take-profit-pct TAKE_PROFIT_PCT] [--max-hold-days MAX_HOLD_DAYS]

Walk Forward Report CLI

options:
  -h, --help            show this help message and exit
  --stock STOCK         Stock ID (e.g., 2330)
  --strategy STRATEGY   Strategy name (e.g., ma_cross, all)
  --period PERIOD       Data period
  --output-md [OUTPUT_MD]
                        Export Markdown report
  --output-excel [OUTPUT_EXCEL]
                        Export Excel report
  --output-dir OUTPUT_DIR
                        Default output directory
  --force-refresh       Redownload data ignoring cache
  --ma-short-windows MA_SHORT_WINDOWS
                        Comma-separated integers, e.g. 5,10
  --ma-long-windows MA_LONG_WINDOWS
                        Comma-separated integers
  --rsi-buy-below RSI_BUY_BELOW
                        Comma-separated integers
  --rsi-sell-above RSI_SELL_ABOVE
                        Comma-separated integers
  --score-buy SCORE_BUY
                        Comma-separated integers
  --score-sell SCORE_SELL
                        Comma-separated integers, can be negative
  --train-days TRAIN_DAYS
                        Number of training days per window
  --test-days TEST_DAYS
                        Number of test days per window
  --step-days STEP_DAYS
                        Number of days to step forward per window
  --sort-by SORT_BY     Metric to select best parameters
  --initial-capital INITIAL_CAPITAL
  --fee-rate FEE_RATE
  --tax-rate TAX_RATE
  --position-size POSITION_SIZE
  --stop-loss-pct STOP_LOSS_PCT
  --take-profit-pct TAKE_PROFIT_PCT
  --max-hold-days MAX_HOLD_DAYS
""",
}


def _capture_parse(module, program: str, argv: list[str]) -> dict[str, object]:
    original_parser = argparse.ArgumentParser
    captured: list[argparse.ArgumentParser] = []

    def parser_factory(*args: object, **kwargs: object) -> argparse.ArgumentParser:
        argparse.ArgumentParser = original_parser
        try:
            parser = original_parser(*args, **kwargs)
        finally:
            argparse.ArgumentParser = parser_factory
        captured.append(parser)
        return parser

    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
        patch.object(argparse, "ArgumentParser", new=parser_factory),
        patch.object(sys, "argv", [program]),
        patch.dict(os.environ, {"COLUMNS": "120"}, clear=False),
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
    ):
        try:
            namespace = module._parse_args(argv)
            status = 0
        except SystemExit as exc:
            namespace = None
            status = exc.code

    return {
        "parser": captured[0],
        "namespace": vars(namespace) if namespace is not None else None,
        "status": status,
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
    }


def _normalize_usage(text: str) -> str:
    return re.sub(r"(?m)^usage: \S+", "usage: <program>", text, count=1)


def _subprocess_environment() -> dict[str, str]:
    environment = os.environ.copy()
    pythonpath = [str(REPOSITORY_ROOT), str(REPOSITORY_ROOT / "src")]
    if environment.get("PYTHONPATH"):
        pythonpath.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(pythonpath)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["COLUMNS"] = "120"
    return environment


class ReportCliArgumentCharacterizationTest(unittest.TestCase):
    def test_normalized_parser_metadata_is_frozen(self) -> None:
        for key, (module, program) in MODULES.items():
            with self.subTest(parser=key):
                result = _capture_parse(module, program, MINIMAL_ARGS)
                self.assertEqual(result["status"], 0)
                self.assertEqual(_normalized_metadata(result["parser"]), EXPECTED_METADATA[key])

    def test_complete_default_namespace_snapshots_are_frozen(self) -> None:
        for key, (module, program) in MODULES.items():
            with self.subTest(parser=key):
                result = _capture_parse(module, program, MINIMAL_ARGS)
                self.assertEqual(result["namespace"], DEFAULT_NAMESPACES[key])

    def test_complete_explicit_namespace_snapshots_are_frozen(self) -> None:
        for key, (module, program) in MODULES.items():
            with self.subTest(parser=key):
                result = _capture_parse(module, program, EXPLICIT_ARGS[key])
                self.assertEqual(result["namespace"], EXPLICIT_NAMESPACES[key])

    def test_output_options_have_none_bare_and_explicit_states(self) -> None:
        for key, (module, program) in MODULES.items():
            for option, explicit in (
                ("--output-md", "custom/report.md"),
                ("--output-excel", "custom/report.xlsx"),
            ):
                with self.subTest(parser=key, option=option):
                    absent = _capture_parse(module, program, MINIMAL_ARGS)
                    bare = _capture_parse(module, program, MINIMAL_ARGS + [option])
                    named = _capture_parse(module, program, MINIMAL_ARGS + [option, explicit])
                    destination = option[2:].replace("-", "_")
                    self.assertIsNone(absent["namespace"][destination])
                    self.assertEqual(bare["namespace"][destination], "")
                    self.assertEqual(named["namespace"][destination], explicit)

            output_dir = _capture_parse(
                module, program, MINIMAL_ARGS + ["--output-dir", "custom/output"]
            )
            self.assertEqual(output_dir["namespace"]["output_dir"], "custom/output")

            omitted_refresh = _capture_parse(module, program, MINIMAL_ARGS)
            supplied_refresh = _capture_parse(
                module, program, MINIMAL_ARGS + ["--force-refresh"]
            )
            self.assertFalse(omitted_refresh["namespace"]["force_refresh"])
            self.assertTrue(supplied_refresh["namespace"]["force_refresh"])

    def test_parameter_ranges_preserve_tuple_parsing_and_negative_scores(self) -> None:
        for key in ("sweep", "walk"):
            module, program = MODULES[key]
            args = MINIMAL_ARGS + [
                "--ma-short-windows", " 5, 10 ,20 ",
                "--ma-long-windows", "30",
                "--rsi-buy-below", "25",
                "--rsi-sell-above", "65, 75",
                "--score-buy", "4,6",
                "--score-sell=-2, -4",
            ]
            result = _capture_parse(module, program, args)
            self.assertEqual(result["namespace"]["ma_short_windows"], (5, 10, 20))
            self.assertEqual(result["namespace"]["ma_long_windows"], (30,))
            self.assertEqual(result["namespace"]["rsi_buy_below"], (25,))
            self.assertEqual(result["namespace"]["rsi_sell_above"], (65, 75))
            self.assertEqual(result["namespace"]["score_buy"], (4, 6))
            self.assertEqual(result["namespace"]["score_sell"], (-2, -4))

    def test_help_snapshots_exit_zero_and_match_exactly(self) -> None:
        for key, (module, program) in MODULES.items():
            with self.subTest(parser=key):
                result = _capture_parse(module, program, ["--help"])
                self.assertEqual(result["status"], 0)
                self.assertEqual(result["stderr"], "")
                self.assertEqual(result["stdout"], HELP_SNAPSHOTS[key])

    def test_argparse_failures_are_status_two_and_do_not_run_runtime(self) -> None:
        failures = {
            "backtest": [
                ("missing-stock", ["--strategy", "ma_cross"]),
                ("missing-strategy", ["--stock", "2330"]),
                ("invalid-integer", MINIMAL_ARGS + ["--short-window", "not-an-int"]),
                ("invalid-float", MINIMAL_ARGS + ["--fee-rate", "not-a-float"]),
                ("unknown-option", MINIMAL_ARGS + ["--unknown-option"]),
            ],
            "sweep": [
                ("missing-stock", ["--strategy", "ma_cross"]),
                ("missing-strategy", ["--stock", "2330"]),
                ("invalid-integer", MINIMAL_ARGS + ["--max-hold-days", "not-an-int"]),
                ("invalid-float", MINIMAL_ARGS + ["--fee-rate", "not-a-float"]),
                ("invalid-tuple", MINIMAL_ARGS + ["--ma-short-windows", "5,broken"]),
                ("unknown-option", MINIMAL_ARGS + ["--unknown-option"]),
            ],
            "walk": [
                ("missing-stock", ["--strategy", "ma_cross"]),
                ("missing-strategy", ["--stock", "2330"]),
                ("invalid-integer", MINIMAL_ARGS + ["--max-hold-days", "not-an-int"]),
                ("invalid-float", MINIMAL_ARGS + ["--fee-rate", "not-a-float"]),
                ("invalid-tuple", MINIMAL_ARGS + ["--ma-short-windows", "5,broken"]),
                ("unknown-option", MINIMAL_ARGS + ["--unknown-option"]),
            ],
        }

        for key, cases in failures.items():
            module, program = MODULES[key]
            for case, argv in cases:
                with self.subTest(parser=key, case=case), tempfile.TemporaryDirectory() as temp_dir:
                    before = set(Path(temp_dir).iterdir())
                    result = _capture_parse(module, program, argv)
                    after = set(Path(temp_dir).iterdir())
                    combined = result["stdout"] + result["stderr"]
                    self.assertEqual(result["status"], 2)
                    self.assertIn("usage:", combined)
                    self.assertIn("error:", result["stderr"])
                    self.assertNotIn("Traceback", combined)
                    self.assertEqual(before, after)

    def test_package_and_root_help_subprocesses_match_parser_snapshots(self) -> None:
        commands = {
            "backtest": (
                ["-m", "tw_stock_tool.cli.backtest_report", "--help"],
                "backtest_report.py",
            ),
            "sweep": (
                ["-m", "tw_stock_tool.cli.parameter_sweep_report", "--help"],
                "parameter_sweep_report.py",
            ),
            "walk": (
                ["-m", "tw_stock_tool.cli.walk_forward_report", "--help"],
                "walk_forward_report.py",
            ),
        }
        for key, (module_command, wrapper_name) in commands.items():
            expected = _normalize_usage(HELP_SNAPSHOTS[key])
            for boundary, command in (
                ("package", [sys.executable, *module_command]),
                ("root", [sys.executable, str(REPOSITORY_ROOT / wrapper_name), "--help"]),
            ):
                with self.subTest(parser=key, boundary=boundary):
                    completed = subprocess.run(
                        command,
                        cwd=REPOSITORY_ROOT,
                        env=_subprocess_environment(),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(completed.returncode, 0)
                    self.assertEqual(completed.stderr, "")
                    self.assertEqual(_normalize_usage(completed.stdout), expected)

    def test_public_parser_modules_and_routes_remain_present(self) -> None:
        for key, (module, _) in MODULES.items():
            self.assertTrue(callable(module._parse_args), key)
            self.assertTrue((REPOSITORY_ROOT / WRAPPERS[key]).is_file())

        for command in ("backtest-report", "parameter-sweep", "walk-forward"):
            with self.subTest(command=command):
                parsed = twstock_cli._parse_args(
                    [command, "--stock", "2330", "--strategy", "ma_cross"]
                )
                self.assertTrue(callable(parsed.handler))
                self.assertEqual(
                    parsed.args,
                    ["--stock", "2330", "--strategy", "ma_cross"],
                )


if __name__ == "__main__":
    unittest.main()


for _action in EXPECTED_METADATA['walk']['actions']:
    if _action['option_strings'][0] in {'--initial-capital', '--fee-rate', '--tax-rate', '--position-size', '--stop-loss-pct', '--take-profit-pct', '--max-hold-days'}:
        _action['help'] = None
EXPECTED_METADATA['sweep']['actions'] = [dict(action) for action in EXPECTED_METADATA['sweep']['actions']]
EXPECTED_METADATA['walk']['actions'] = [dict(action) for action in EXPECTED_METADATA['walk']['actions']]
_SWEEP_ENGINE_HELP = {
    '--initial-capital': 'Initial capital (default from config)',
    '--fee-rate': 'Fee rate (default from config)',
    '--tax-rate': 'Tax rate (default from config)',
    '--position-size': 'Position size (0 to 1.0, default 1.0)',
    '--stop-loss-pct': 'Stop loss percentage (e.g., 0.05 for 5%%)',
    '--take-profit-pct': 'Take profit percentage',
    '--max-hold-days': 'Maximum holding days',
}
for _action in EXPECTED_METADATA['sweep']['actions']:
    if _action['option_strings'][0] in _SWEEP_ENGINE_HELP:
        _action['help'] = _SWEEP_ENGINE_HELP[_action['option_strings'][0]]