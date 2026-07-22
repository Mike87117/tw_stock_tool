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
from tw_stock_tool.cli import daily_report_artifact_cli
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


def _dispatch_existing_main(
    module_main: Callable[[], int | None],
    program_name: str,
    args: list[str],
) -> int:
    """Run an existing CLI main with pass-through arguments."""
    with _patched_argv(program_name, args):
        result = module_main()
    return 0 if result is None else result


def _run_stock_list_update(args: list[str]) -> int:
    return _dispatch_existing_main(stock_list_updater.main, "stock_list_updater.py", args)


def _run_stock_list_smoke_check(args: list[str]) -> int:
    return _dispatch_existing_main(stock_list_smoke_check.main, "stock_list_smoke_check.py", args)


def _add_passthrough_parser(subparsers, name, module_main, program_name, help_text, description=None) -> None:
    parser_kwargs = {"help": help_text}
    if description is not None:
        parser_kwargs["description"] = description
    parser = subparsers.add_parser(name, **parser_kwargs)
    parser.set_defaults(handler=lambda args: _dispatch_existing_main(module_main, program_name, args.args))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified tw_stock_tool CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_passthrough_parser(subparsers, "doctor", doctor.main, "doctor.py", "Check local environment")

    _add_passthrough_parser(subparsers, "scan", scan_stocks.main, "scan_stocks.py", "Run multi-stock technical scanner")

    _add_passthrough_parser(subparsers, "daily", daily_report_cli.main, "daily_report_cli.py", "Run daily candidate report")

    _add_passthrough_parser(
        subparsers,
        "daily-report-artifact",
        daily_report_artifact_cli.main,
        "daily_report_artifact_cli.py",
        "Validate, inspect, or export a Daily Report JSON artifact",
        (
            "Operate on an existing offline Daily Research Report JSON artifact.\n"
            "Does not fetch market data, run analysis, execute strategies or "
            "backtests, connect to brokers, place orders, produce live signals, "
            "or provide investment advice."
        ),
    )

    stock_list_parser = subparsers.add_parser("stock-list", help="Stock-list utilities")
    stock_list_subparsers = stock_list_parser.add_subparsers(dest="stock_list_command", required=True)

    update_parser = stock_list_subparsers.add_parser("update", help="Update stocks.txt from official sources")
    update_parser.set_defaults(handler=lambda args: _run_stock_list_update(args.args))

    smoke_parser = stock_list_subparsers.add_parser("smoke-check", help="Smoke check official stock-list sources")
    smoke_parser.set_defaults(handler=lambda args: _run_stock_list_smoke_check(args.args))

    _add_passthrough_parser(stock_list_subparsers, "clean", clean_stocks.main, "clean_stocks.py", "Clean stock list")

    _add_passthrough_parser(
        subparsers,
        "price-smoke-check",
        price_data_smoke_check.main,
        "price_data_smoke_check.py",
        "Smoke check price data sources",
    )

    _add_passthrough_parser(subparsers, "ai-scan", ai_stock_scanner.main, "ai_stock_scanner.py", "Run multi-stock AI baseline scanner")

    _add_passthrough_parser(subparsers, "cache", cache_manager.main, "cache_manager.py", "Manage price data cache")

    _add_passthrough_parser(subparsers, "benchmark", benchmark.main, "benchmark.py", "Run multi-stock scanner benchmark")

    _add_passthrough_parser(subparsers, "analyze", analyze_cli.main, "main.py", "Run single-stock analysis")

    _add_passthrough_parser(subparsers, "strategy-compare", strategy_compare.main, "strategy_compare.py", "Run strategy comparison")

    _add_passthrough_parser(subparsers, "parameter-sweep", parameter_sweep_report.main, "parameter_sweep_report.py", "Run parameter sweep")

    _add_passthrough_parser(subparsers, "backtest-report", backtest_report.main, "backtest_report.py", "Run backtest report")

    _add_passthrough_parser(
        subparsers,
        "walk-forward",
        walk_forward_report.main,
        "walk_forward_report.py",
        "Run walk forward report",
    )

    from tw_stock_tool.cli import simulated_paper_trading_cli

    _add_passthrough_parser(
        subparsers,
        "simulated-paper-trading",
        simulated_paper_trading_cli.main,
        "simulated_paper_trading_cli.py",
        "Run historical simulated paper trading",
        "Run research-only simulated paper trading over historical data.\n"
        "Does not connect to brokers, place real orders, or provide investment advice.",
    )

    _add_passthrough_parser(
        subparsers,
        "simulated-paper-trading-export",
        simulated_paper_trading_export_cli.main,
        "simulated_paper_trading_export_cli.py",
        "Export reports from a simulated paper trading JSON artifact",
        "Export reports from an existing research-only simulated paper trading JSON artifact.\n"
        "Does not fetch market data, run strategies, connect to brokers, or place orders.",
    )

    _add_passthrough_parser(
        subparsers,
        "backtest-artifact",
        backtest_artifact_cli.main,
        "backtest_artifact_cli.py",
        "Validate or inspect BacktestResult JSON artifacts",
        "Validate or inspect existing research-only BacktestResult JSON artifacts.\n"
        "Does not fetch market data, run strategies, execute backtests, connect to brokers, "
        "place orders, produce live signals, or provide investment advice.",
    )

    from tw_stock_tool.cli import backtest_result_export_cli

    _add_passthrough_parser(
        subparsers,
        "backtest-result-export",
        backtest_result_export_cli.main,
        "backtest_result_export_cli.py",
        "Export historical BacktestResult JSON artifact",
        "Export a structured BacktestResult JSON artifact from a historical backtest execution.\n"
        "This is a historical backtest artifact for offline research only. Not investment advice.",
    )

    args, passthrough_args = parser.parse_known_args(argv)
    args.args = passthrough_args
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return args.handler(args)

if __name__ == "__main__":
    raise SystemExit(main())
