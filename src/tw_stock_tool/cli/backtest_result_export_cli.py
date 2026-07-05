import argparse
import sys
from typing import Any

from tw_stock_tool.analysis.analysis import analyze_stock
from tw_stock_tool.backtesting.backtest import run_backtest_result, BacktestError
from tw_stock_tool.backtesting.serialization import BacktestResultSerializationError
from tw_stock_tool.backtesting.serialization_files import export_backtest_result_json_file
from tw_stock_tool.backtesting.strategies import STRATEGIES
from tw_stock_tool.utils.config import DEFAULT_PERIOD


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export structured BacktestResult artifact from a historical backtest execution path.",
        epilog="This is a historical backtest artifact for offline research only. Not investment advice."
    )
    parser.add_argument("--stock", required=True, help="Stock ID (e.g., 2330)")
    parser.add_argument("--strategy", required=True, help="Strategy name (e.g., ma_cross)")
    parser.add_argument("--period", default=DEFAULT_PERIOD, help="Data period")
    parser.add_argument("--initial-capital", type=float, default=100000.0, help="Initial capital")
    parser.add_argument("--output-json", required=True, help="Path to write the research-only JSON artifact")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing files")
    parser.add_argument("--force-refresh", action="store_true", help="Redownload data ignoring cache")

    # Strategy specific params
    parser.add_argument("--short-window", type=int, default=5, help="Short MA window")
    parser.add_argument("--long-window", type=int, default=20, help="Long MA window")

    # RSI parameters
    parser.add_argument("--rsi-buy-below", type=float, default=30.0, help="RSI threshold (buy below)")
    parser.add_argument("--rsi-sell-above", type=float, default=70.0, help="RSI threshold (sell above)")

    # Score parameters
    parser.add_argument("--score-buy", type=float, default=None, help="Score threshold (buy)")
    parser.add_argument("--score-sell", type=float, default=None, help="Score threshold (sell)")

    # Backtest engine parameters
    parser.add_argument("--fee-rate", type=float, default=0.001425, help="Backtest fee rate assumption")
    parser.add_argument("--tax-rate", type=float, default=0.003, help="Backtest tax rate assumption")
    parser.add_argument("--position-size", type=float, default=1.0, help="Backtest position size")
    parser.add_argument("--stop-loss-pct", type=float, default=None, help="Stop-loss threshold percentage")
    parser.add_argument("--take-profit-pct", type=float, default=None, help="Take-profit threshold percentage")
    parser.add_argument("--max-hold-days", type=int, default=None, help="Max holding days")

    return parser.parse_args(argv)


def _build_strategy_params(args: argparse.Namespace, strategy_name: str) -> dict[str, Any]:
    if strategy_name == "ma_cross_strategy":
        return {
            "short_window": args.short_window,
            "long_window": args.long_window,
        }
    elif strategy_name == "rsi_strategy":
        return {
            "buy_below": args.rsi_buy_below,
            "sell_above": args.rsi_sell_above,
        }
    elif strategy_name == "score_strategy":
        params = {}
        if args.score_buy is not None:
            params["buy_score"] = args.score_buy
        if args.score_sell is not None:
            params["sell_score"] = args.score_sell
        return params
    return {}


def _build_backtest_params(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "initial_capital": args.initial_capital,
        "fee_rate": args.fee_rate,
        "tax_rate": args.tax_rate,
        "position_size": args.position_size,
        "stop_loss_pct": args.stop_loss_pct,
        "take_profit_pct": args.take_profit_pct,
        "max_hold_days": args.max_hold_days,
    }


def main(argv: list[str] | None = None) -> None:
    try:
        args = _parse_args(argv)

        strategy_name = args.strategy
        if strategy_name not in STRATEGIES:
            if f"{strategy_name}_strategy" in STRATEGIES:
                strategy_name = f"{strategy_name}_strategy"
            else:
                raise ValueError(f"Unknown strategy: {args.strategy}")

        strategy_func = STRATEGIES[strategy_name]

        params = _build_strategy_params(args, strategy_name)

        analysis = analyze_stock(
            stock_id=args.stock,
            period=args.period,
            force_refresh=args.force_refresh,
        )

        df_exec = strategy_func(analysis.indicator_df, **params)

        bt_params = _build_backtest_params(args)
        
        result = run_backtest_result(df_exec, **bt_params)

        start_date = df_exec.index[0].strftime('%Y-%m-%d') if not df_exec.empty else "N/A"
        end_date = df_exec.index[-1].strftime('%Y-%m-%d') if not df_exec.empty else "N/A"

        result.stock = args.stock
        result.strategy = strategy_name
        result.start_date = start_date
        result.end_date = end_date
        result.parameters = {
            "strategy": params,
            "backtest": bt_params,
            "requested_strategy": args.strategy,
            "resolved_strategy": strategy_name,
        }

        export_backtest_result_json_file(result, args.output_json, overwrite=args.overwrite)

    except FileExistsError as exc:
        print(f"error: {exc}. Use --overwrite to replace existing files.", file=sys.stderr)
        sys.exit(1)
    except (FileNotFoundError, IsADirectoryError, PermissionError, ValueError, BacktestError, BacktestResultSerializationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"error: Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
