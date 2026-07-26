"""
CLI for multi-symbol historical simulated portfolio trading.
"""

import argparse
import math
import sys
import pandas as pd

from tw_stock_tool.analysis.analysis import analyze_stock
from tw_stock_tool.analysis.scanner import load_stock_ids_from_file, normalize_stock_ids
from tw_stock_tool.backtesting.strategies import STRATEGIES
from tw_stock_tool.paper_trading.portfolio_engine import run_simulated_portfolio_trading_result
from tw_stock_tool.paper_trading.portfolio_report_data import build_simulated_portfolio_trading_summary
from tw_stock_tool.paper_trading.portfolio_serialization_files import (
    export_simulated_portfolio_trading_result_json_file,
    load_simulated_portfolio_trading_result_json_file,
)
from tw_stock_tool.utils.config import DEFAULT_PERIOD


def _extract_final_close(df: pd.DataFrame) -> float:
    if df.empty:
        raise ValueError("DataFrame is empty.")
    if "Close" not in df.columns:
        raise ValueError("DataFrame missing 'Close' column.")

    val = df["Close"].iloc[-1]

    if type(val) is bool or type(val).__name__ in ("bool", "bool_"):
        raise ValueError("Final Close must not be boolean.")

    try:
        fval = float(val)
    except (ValueError, TypeError):
        raise ValueError("Final Close must be numeric.")

    if math.isnan(fval) or math.isinf(fval):
        raise ValueError("Final Close must be finite.")

    if fval <= 0:
        raise ValueError("Final Close must be positive.")

    return fval


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run research-only multi-symbol simulated portfolio trading over historical data.\nDoes not connect to brokers, place real orders, or provide investment advice."
    )

    parser.add_argument("--stocks", nargs="*", default=None, help="Stock symbols list")
    parser.add_argument("--file", default=None, help="Path to stock list text file")
    parser.add_argument(
        "--strategy",
        required=True,
        choices=["ma_cross", "macd", "rsi"],
        help="Strategy name",
    )

    def check_initial_cash(val: str) -> float:
        if val.lower() in ("true", "false"):
            raise argparse.ArgumentTypeError("initial_cash must be numeric.")
        try:
            fval = float(val)
        except ValueError:
            raise argparse.ArgumentTypeError("initial_cash must be numeric.")
        if math.isnan(fval) or math.isinf(fval) or fval < 0:
            raise argparse.ArgumentTypeError("initial_cash must be a finite non-negative number.")
        return fval

    parser.add_argument("--initial-cash", required=True, type=check_initial_cash, help="Initial cash for simulation")

    def check_quantity(val: str) -> int:
        if val.lower() in ("true", "false"):
            raise argparse.ArgumentTypeError("quantity_per_trade must be an integer.")
        if "." in val:
            raise argparse.ArgumentTypeError("quantity_per_trade must be an integer.")
        try:
            ival = int(val)
        except ValueError:
            raise argparse.ArgumentTypeError("quantity_per_trade must be an integer.")
        if ival <= 0:
            raise argparse.ArgumentTypeError("quantity_per_trade must be a positive integer.")
        return ival

    parser.add_argument("--quantity-per-trade", type=check_quantity, default=1000, help="Quantity per trade")
    parser.add_argument("--period", default=DEFAULT_PERIOD, help="Data period")

    def check_rate(val: str) -> float:
        if val.lower() in ("true", "false"):
            raise argparse.ArgumentTypeError("Rate must be numeric.")
        try:
            fval = float(val)
        except ValueError:
            raise argparse.ArgumentTypeError("Rate must be numeric.")
        if math.isnan(fval) or math.isinf(fval) or fval < 0:
            raise argparse.ArgumentTypeError("Rate must be a finite non-negative number.")
        return fval

    parser.add_argument("--fee-rate", type=check_rate, default=0.0, help="Fee rate")
    parser.add_argument("--tax-rate", type=check_rate, default=0.0, help="Tax rate")
    parser.add_argument("--slippage-per-share", type=check_rate, default=0.0, help="Slippage per share")
    parser.add_argument("--force-refresh", action="store_true", help="Force refresh data")
    parser.add_argument("--output-json", required=True, help="Path for JSON artifact output")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output JSON artifact")

    return parser.parse_args(argv)


def _collect_stock_ids(args: argparse.Namespace) -> list[str]:
    if args.stocks is None and args.file is None:
        raise ValueError("At least one of --stocks or --file must be provided.")

    raw_items: list[str] = []

    if args.stocks is not None:
        if not args.stocks:
            # Explicit empty list passed, e.g. --stocks without args
            raise ValueError("At least one of --stocks or --file must be provided.")
        for item in args.stocks:
            item_str = str(item)
            if not item_str.strip():
                raise ValueError("Blank CLI stock item is not allowed.")
            raw_items.append(item_str)

    if args.file is not None:
        file_items = load_stock_ids_from_file(args.file)
        raw_items.extend(file_items)

    normalized = normalize_stock_ids(raw_items)
    if not normalized:
        raise ValueError("Final stock list is empty.")

    return normalized


def main(argv: list[str] | None = None) -> int | None:
    try:
        args = _parse_args(argv)
        stock_ids = _collect_stock_ids(args)

        strategy_key = f"{args.strategy}_strategy"
        strategy_func = STRATEGIES[strategy_key]

        dataframes: dict[str, pd.DataFrame] = {}
        last_prices: dict[str, float] = {}
        input_symbol_map: dict[str, str] = {}

        for input_id in stock_ids:
            analysis = analyze_stock(
                stock_id=input_id,
                period=args.period,
                force_refresh=args.force_refresh,
            )

            canonical_symbol = analysis.symbol
            if not isinstance(canonical_symbol, str) or not canonical_symbol.strip():
                raise ValueError(f"Resolved canonical symbol for '{input_id}' must be a non-blank string.")

            if canonical_symbol in input_symbol_map:
                conflicting_prev = input_symbol_map[canonical_symbol]
                raise ValueError(
                    f"Canonical symbol collision detected: '{conflicting_prev}' and '{input_id}' both resolve to '{canonical_symbol}'."
                )

            input_symbol_map[canonical_symbol] = input_id

            df_exec = strategy_func(analysis.indicator_df)

            if df_exec.empty:
                raise ValueError(f"Strategy returned empty DataFrame for stock '{input_id}'.")
            if "Open" not in df_exec.columns or "Close" not in df_exec.columns:
                raise ValueError(f"Strategy output missing Open or Close for stock '{input_id}'.")
            if "entry_signal" not in df_exec.columns or "exit_signal" not in df_exec.columns:
                raise ValueError(f"Strategy output missing standard signals for stock '{input_id}'.")
            if not df_exec.index.is_unique:
                raise ValueError(f"Strategy output index is not unique for stock '{input_id}'.")
            if not df_exec.index.is_monotonic_increasing:
                raise ValueError(f"Strategy output index is not monotonically increasing for stock '{input_id}'.")

            last_price = _extract_final_close(df_exec)

            dataframes[canonical_symbol] = df_exec
            last_prices[canonical_symbol] = last_price

        result = run_simulated_portfolio_trading_result(
            dataframes,
            initial_cash=args.initial_cash,
            last_prices=last_prices,
            quantity_per_trade=args.quantity_per_trade,
            fee_rate=args.fee_rate,
            tax_rate=args.tax_rate,
            slippage_per_share=args.slippage_per_share,
            strategy=args.strategy,
            strategy_metadata={"period": args.period},
        )

        export_path = export_simulated_portfolio_trading_result_json_file(
            result,
            args.output_json,
            overwrite=args.overwrite,
        )

        read_back_result = load_simulated_portfolio_trading_result_json_file(export_path)
        summary = build_simulated_portfolio_trading_summary(read_back_result)

        print("Simulated portfolio trading finished. Summary:")
        print(f"  Initial Cash: {summary['initial_cash']}")
        print(f"  Final Cash: {summary['final_cash']}")
        print(f"  Total Market Value: {summary['total_market_value']}")
        print(f"  Total Equity: {summary['total_equity']}")
        print(f"  Realized PnL: {summary['realized_pnl']}")
        print(f"  Unrealized PnL: {summary['unrealized_pnl']}")
        print(f"  Total Return: {summary['total_return']}")

        pct = summary["total_return_pct"]
        if pct is None:
            pct_str = "N/A"
        else:
            pct_str = f"{pct * 100:.2f}%"

        print(f"  Total Return %: {pct_str}")
        print(f"  Open Position Count: {summary['open_position_count']}")
        print(f"  Pending Order Count: {summary['pending_order_count']}")
        print(f"  Order Count: {summary['order_count']}")
        print(f"  Fill Count: {summary['fill_count']}")
        print(f"  Rejection Count: {summary['rejection_count']}")
        print(f"  Audit Record Count: {summary['audit_record_count']}")
        print(f"  Output JSON Path: {export_path}")

    except SystemExit:
        raise
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
