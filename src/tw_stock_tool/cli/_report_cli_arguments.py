import argparse
from typing import Any

from tw_stock_tool.cli.parsers import parse_int_tuple
from tw_stock_tool.utils.config import DEFAULT_PERIOD


def build_backtest_parameters(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "initial_capital": args.initial_capital,
        "fee_rate": args.fee_rate,
        "tax_rate": args.tax_rate,
        "position_size": args.position_size,
        "stop_loss_pct": args.stop_loss_pct,
        "take_profit_pct": args.take_profit_pct,
        "max_hold_days": args.max_hold_days,
    }


def add_stock_strategy_period_arguments(parser: argparse.ArgumentParser, *, strategy_help: str) -> None:
    parser.add_argument("--stock", required=True, help="Stock ID (e.g., 2330)")
    parser.add_argument("--strategy", required=True, help=strategy_help)
    parser.add_argument("--period", default=DEFAULT_PERIOD, help="Data period")


def add_report_output_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-md", nargs="?", const="", default=None, help="Export Markdown report")
    parser.add_argument("--output-excel", nargs="?", const="", default=None, help="Export Excel report")
    parser.add_argument("--output-dir", default="output", help="Default output directory")


def add_force_refresh_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--force-refresh", action="store_true", help="Redownload data ignoring cache")


def add_parameter_range_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ma-short-windows", type=parse_int_tuple, help="Comma-separated integers, e.g. 5,10")
    parser.add_argument("--ma-long-windows", type=parse_int_tuple, help="Comma-separated integers")
    parser.add_argument("--rsi-buy-below", type=parse_int_tuple, help="Comma-separated integers")
    parser.add_argument("--rsi-sell-above", type=parse_int_tuple, help="Comma-separated integers")
    parser.add_argument("--score-buy", type=parse_int_tuple, help="Comma-separated integers")
    parser.add_argument("--score-sell", type=parse_int_tuple, help="Comma-separated integers, can be negative")
