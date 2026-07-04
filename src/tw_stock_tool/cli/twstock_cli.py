"""Unified CLI entrypoint for tw_stock_tool.

This module routes subcommands to the existing CLI modules without changing
those modules' original command-line behavior.
"""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from typing import Callable, Iterator

from tw_stock_tool.cli import parameter_sweep_report
from tw_stock_tool.backtesting import strategy_compare
from tw_stock_tool.cli import main as analyze_cli
from tw_stock_tool.cli import benchmark
from tw_stock_tool.cli import backtest_report
from tw_stock_tool.cli import walk_forward_report
from tw_stock_tool.ml import ai_stock_scanner
from tw_stock_tool.cli import clean_stocks
from tw_stock_tool.cli import daily_report_cli
from tw_stock_tool.utils import doctor
from tw_stock_tool.cli import price_data_smoke_check
from tw_stock_tool.cli import scan_stocks
from tw_stock_tool.cli import stock_list_smoke_check
from tw_stock_tool.cli import simulated_paper_trading_export_cli
from tw_stock_tool.cli import backtest_artifact_cli
from tw_stock_tool.data import cache_manager
from tw_stock_tool.data import stock_list_updater


@contextmanager
def _patched_argv(program_name: str, args: list[str]) -> Iterator[None]:
    original = sys.argv[:]
    sys.argv = [program_name, *args]
    try:
        yield
    finally:
        sys.argv = original


def _dispatch_existing_main(module_main: Callable[[], None], program_name: str, args: list[str]) -> None:
    """Run an existing CLI main with pass-through arguments."""
    with _patched_argv(program_name, args):
        module_main()


def _run_stock_list_update(args: list[str]) -> None:
    _dispatch_existing_main(stock_list_updater.main, "stock_list_updater.py", args)


def _run_stock_list_smoke_check(args: list[str]) -> None:
    _dispatch_existing_main(stock_list_smoke_check.main, "stock_list_smoke_check.py", args)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified tw_stock_tool CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="Check local environment")
    doctor_parser.set_defaults(handler=lambda args: _dispatch_existing_main(doctor.main, "doctor.py", args.args))

    scan_parser = subparsers.add_parser("scan", help="Run multi-stock technical scanner")
    scan_parser.set_defaults(handler=lambda args: _dispatch_existing_main(scan_stocks.main, "scan_stocks.py", args.args))

    daily_parser = subparsers.add_parser("daily", help="Run daily candidate report")
    daily_parser.set_defaults(handler=lambda args: _dispatch_existing_main(daily_report_cli.main, "daily_report_cli.py", args.args))

    stock_list_parser = subparsers.add_parser("stock-list", help="Stock-list utilities")
    stock_list_subparsers = stock_list_parser.add_subparsers(dest="stock_list_command", required=True)

    update_parser = stock_list_subparsers.add_parser("update", help="Update stocks.txt from official sources")
    update_parser.set_defaults(handler=lambda args: _run_stock_list_update(args.args))

    smoke_parser = stock_list_subparsers.add_parser("smoke-check", help="Smoke check official stock-list sources")
    smoke_parser.set_defaults(handler=lambda args: _run_stock_list_smoke_check(args.args))

    clean_parser = stock_list_subparsers.add_parser("clean", help="Clean stock list")
    clean_parser.set_defaults(handler=lambda args: _dispatch_existing_main(clean_stocks.main, "clean_stocks.py", args.args))

    price_parser = subparsers.add_parser("price-smoke-check", help="Smoke check price data sources")
    price_parser.set_defaults(
        handler=lambda args: _dispatch_existing_main(
            price_data_smoke_check.main,
            "price_data_smoke_check.py",
            args.args,
        )
    )

    ai_scan_parser = subparsers.add_parser("ai-scan", help="Run multi-stock AI baseline scanner")
    ai_scan_parser.set_defaults(handler=lambda args: _dispatch_existing_main(ai_stock_scanner.main, "ai_stock_scanner.py", args.args))

    cache_parser = subparsers.add_parser("cache", help="Manage price data cache")
    cache_parser.set_defaults(handler=lambda args: _dispatch_existing_main(cache_manager.main, "cache_manager.py", args.args))

    benchmark_parser = subparsers.add_parser("benchmark", help="Run multi-stock scanner benchmark")
    benchmark_parser.set_defaults(handler=lambda args: _dispatch_existing_main(benchmark.main, "benchmark.py", args.args))

    analyze_parser = subparsers.add_parser("analyze", help="Run single-stock analysis")
    analyze_parser.set_defaults(handler=lambda args: _dispatch_existing_main(analyze_cli.main, "main.py", args.args))

    strategy_compare_parser = subparsers.add_parser("strategy-compare", help="Run strategy comparison")
    strategy_compare_parser.set_defaults(handler=lambda args: _dispatch_existing_main(strategy_compare.main, "strategy_compare.py", args.args))

    parameter_sweep_parser = subparsers.add_parser("parameter-sweep", help="Run parameter sweep")
    parameter_sweep_parser.set_defaults(handler=lambda args: _dispatch_existing_main(parameter_sweep_report.main, "parameter_sweep_report.py", args.args))

    backtest_report_parser = subparsers.add_parser("backtest-report", help="Run backtest report")
    backtest_report_parser.set_defaults(handler=lambda args: _dispatch_existing_main(backtest_report.main, "backtest_report.py", args.args))

    walk_forward_parser = subparsers.add_parser("walk-forward", help="Run walk forward report")
    walk_forward_parser.set_defaults(
        handler=lambda args: _dispatch_existing_main(
            walk_forward_report.main,
            "walk_forward_report.py",
            args.args,
        )
    )

    simulated_paper_trading_export_parser = subparsers.add_parser(
        "simulated-paper-trading-export", 
        help="Export reports from a simulated paper trading JSON artifact",
        description="Export reports from an existing research-only simulated paper trading JSON artifact.\n"
                    "Does not fetch market data, run strategies, connect to brokers, or place orders."
    )
    simulated_paper_trading_export_parser.set_defaults(
        handler=lambda args: _dispatch_existing_main(
            simulated_paper_trading_export_cli.main,
            "simulated_paper_trading_export_cli.py",
            args.args,
        )
    )

    backtest_artifact_parser = subparsers.add_parser(
        "backtest-artifact",
        help="Validate or inspect BacktestResult JSON artifacts",
        description="Validate or inspect existing research-only BacktestResult JSON artifacts.\n"
                    "Does not fetch market data, run strategies, execute backtests, connect to brokers, "
                    "place orders, produce live signals, or provide investment advice."
    )
    backtest_artifact_parser.set_defaults(
        handler=lambda args: _dispatch_existing_main(
            backtest_artifact_cli.main,
            "backtest_artifact_cli.py",
            args.args,
        )
    )

    args, passthrough_args = parser.parse_known_args(argv)
    args.args = passthrough_args
    return args


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    args.handler(args)


if __name__ == "__main__":
    main()
