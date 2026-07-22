import argparse
from pathlib import Path
from typing import Any

from tw_stock_tool.analysis.analysis import analyze_stock
from tw_stock_tool.backtesting.backtest import run_backtest
from tw_stock_tool.backtesting.strategies import STRATEGIES
from tw_stock_tool.reports.backtest_report import (
    export_backtest_report_markdown,
    export_backtest_report_excel,
)
from tw_stock_tool.cli._report_cli_arguments import (
    add_force_refresh_argument,
    add_report_output_arguments,
    add_stock_strategy_period_arguments,
)


def _normalize_result(
    raw_result: dict[str, Any],
    stock: str,
    strategy: str,
    start_date: str,
    end_date: str,
    parameters: dict[str, Any]
) -> dict[str, Any]:
    """Ensure result dictionary has metadata for reporting."""
    result = raw_result.copy()
    result["Stock"] = stock
    result["Strategy"] = strategy
    result["Start Date"] = start_date
    result["End Date"] = end_date
    result["Parameters"] = parameters
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest Report Generator",
        epilog="Backtest fills use next-bar Open as a research assumption."
    )
    add_stock_strategy_period_arguments(parser, strategy_help="Strategy name (e.g., ma_cross)")
    parser.add_argument("--initial-capital", type=float, default=100000.0, help="Initial capital")
    add_report_output_arguments(parser)
    add_force_refresh_argument(parser)
    parser.add_argument("--short-window", type=int, default=5, help="Short MA window")
    parser.add_argument("--long-window", type=int, default=20, help="Long MA window")
    parser.add_argument("--rsi-buy-below", type=float, default=30.0, help="RSI threshold (buy below)")
    parser.add_argument("--rsi-sell-above", type=float, default=70.0, help="RSI threshold (sell above)")
    parser.add_argument("--score-buy", type=float, default=None, help="Score threshold (buy)")
    parser.add_argument("--score-sell", type=float, default=None, help="Score threshold (sell)")
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


def main() -> int | None:
    try:
        args = _parse_args()

        strategy_name = args.strategy
        if strategy_name not in STRATEGIES:
            if f"{strategy_name}_strategy" in STRATEGIES:
                strategy_name = f"{strategy_name}_strategy"
            else:
                raise ValueError(f"Unknown strategy: {args.strategy}")

        strategy_func = STRATEGIES[strategy_name]

        # Prepare strategy parameters
        params = _build_strategy_params(args, strategy_name)

        print(f"Fetching data for {args.stock} (period={args.period})...")
        analysis = analyze_stock(
            stock_id=args.stock,
            period=args.period,
            force_refresh=args.force_refresh,
        )

        print(f"Applying strategy {strategy_name}...")
        df_exec = strategy_func(analysis.indicator_df, **params)

        print(f"Running backtest with initial capital {args.initial_capital}...")
        bt_params = _build_backtest_params(args)
        raw_result = run_backtest(df_exec, **bt_params)

        start_date = df_exec.index[0].strftime('%Y-%m-%d') if not df_exec.empty else "N/A"
        end_date = df_exec.index[-1].strftime('%Y-%m-%d') if not df_exec.empty else "N/A"

        report_params = {
            "strategy": params,
            "backtest": bt_params,
        }

        result = _normalize_result(
            raw_result=raw_result,
            stock=args.stock,
            strategy=args.strategy,
            start_date=start_date,
            end_date=end_date,
            parameters=report_params,
        )

        out_dir = Path(args.output_dir)

        if args.output_excel is not None:
            excel_output = args.output_excel or str(out_dir / "backtest_report.xlsx")
            excel_path = export_backtest_report_excel(result, excel_output)
            print(f"Excel report: {excel_path}")

        if args.output_md is not None:
            md_output = args.output_md or str(out_dir / "backtest_report.md")
            md_path = export_backtest_report_markdown(result, md_output)
            print(f"Markdown report: {md_path}")

        if args.output_excel is None and args.output_md is None:
            print("Backtest finished. Summary:")
            print(f"  Total Return: {result.get('Total Return %', 0)}%")
            print(f"  Win Rate: {result.get('Win Rate %', 0)}%")
            print(f"  Trades: {result.get('Trade Count', 0)}")

    except Exception as exc:
        print(f"Error: {exc}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
