import argparse
from pathlib import Path

import pandas as pd

from tw_stock_tool.analysis.analysis import analyze_stock
from tw_stock_tool.backtesting.backtest import run_backtest
from tw_stock_tool.utils.config import DEFAULT_INTERVAL, DEFAULT_PERIOD, FEE_RATE, INITIAL_CAPITAL, OUTPUT_DIR, TAX_RATE
from tw_stock_tool.reports.report import ReportError
from tw_stock_tool.backtesting.strategies import STRATEGIES

COMPARE_COLUMNS = [
    "Strategy",
    "Total Return %",
    "Buy and Hold Return %",
    "CAGR %",
    "Trade Count",
    "Win Rate %",
    "Max Drawdown %",
    "Profit Factor",
    "Sharpe Ratio",
    "Sortino Ratio",
]


def compare_strategies(
    stock_id: str,
    period: str = DEFAULT_PERIOD,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
    max_hold_days: int | None = None,
    position_size: float = 1.0,
    force_refresh: bool = False,
    ma_short: int = 5,
    ma_long: int = 20,
    rsi_buy_below: float = 30,
    rsi_sell_above: float = 70,
    score_buy: float | None = None,
    score_sell: float | None = None,
) -> pd.DataFrame:
    analysis = analyze_stock(
        stock_id=stock_id,
        period=period,
        interval=DEFAULT_INTERVAL,
        force_refresh=force_refresh,
    )

    rows = []
    for strategy_name, strategy_func in STRATEGIES.items():
        if strategy_name == "score_strategy":
            strategy_df = strategy_func(
                analysis.signal_df,
                buy_score=score_buy,
                sell_score=score_sell,
            )
        elif strategy_name == "ma_cross_strategy":
            strategy_df = strategy_func(
                analysis.signal_df,
                short_window=ma_short,
                long_window=ma_long,
            )
        elif strategy_name == "rsi_strategy":
            strategy_df = strategy_func(
                analysis.signal_df,
                buy_below=rsi_buy_below,
                sell_above=rsi_sell_above,
            )
        else:
            strategy_df = strategy_func(analysis.signal_df)
        strategy_df = strategy_df.dropna(subset=["Close", "Signal"])
        result = run_backtest(
            strategy_df,
            initial_capital=INITIAL_CAPITAL,
            fee_rate=FEE_RATE,
            tax_rate=TAX_RATE,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            max_hold_days=max_hold_days,
            position_size=position_size,
        )
        row = {"Strategy": strategy_name}
        row.update({column: result[column] for column in COMPARE_COLUMNS if column != "Strategy"})
        rows.append(row)

    return pd.DataFrame(rows, columns=COMPARE_COLUMNS)


def export_strategy_compare(df: pd.DataFrame, output_path: Path) -> Path:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(output_path, index=False, sheet_name="Strategy_Compare")
    except PermissionError as exc:
        raise ReportError("Strategy compare file may be open. Please close it and retry.") from exc
    except Exception as exc:
        raise ReportError(f"Failed to export strategy compare: {exc}") from exc
    return output_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy comparison tool")
    parser.add_argument("--stock", required=True, help="Stock id, for example 2330")
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--stop-loss", type=float, dest="stop_loss")
    parser.add_argument("--take-profit", type=float, dest="take_profit")
    parser.add_argument("--max-hold-days", type=int)
    parser.add_argument("--position-size", type=float, default=1.0)
    parser.add_argument("--ma-short", type=int, default=5)
    parser.add_argument("--ma-long", type=int, default=20)
    parser.add_argument("--rsi-buy-below", type=float, default=30)
    parser.add_argument("--rsi-sell-above", type=float, default=70)
    parser.add_argument("--score-buy", type=float, help="BUY threshold for score_strategy")
    parser.add_argument("--score-sell", type=float, help="SELL threshold for score_strategy")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--output", nargs="?", const="", help="Export Excel; omit path for default output")
    parser.add_argument("--output-excel", nargs="?", const="", help="Export Excel; omit path for default output")
    args = parser.parse_args(argv)
    if getattr(args, "output", None) is not None and getattr(args, "output_excel", None) is not None:
        parser.error("Only one of --output or --output-excel may be used.")
    return args


def main() -> None:
    try:
        args = _parse_args()
        result = compare_strategies(
            stock_id=args.stock,
            period=args.period,
            stop_loss_pct=args.stop_loss,
            take_profit_pct=args.take_profit,
            max_hold_days=args.max_hold_days,
            position_size=args.position_size,
            force_refresh=args.force_refresh,
            ma_short=args.ma_short,
            ma_long=args.ma_long,
            rsi_buy_below=args.rsi_buy_below,
            rsi_sell_above=args.rsi_sell_above,
            score_buy=args.score_buy,
            score_sell=args.score_sell,
        )
        print(result.to_string(index=False))

        final_output = args.output if args.output is not None else args.output_excel

        if final_output is not None:
            output_path = (
                OUTPUT_DIR / f"{args.stock}_strategy_compare.xlsx"
                if final_output == ""
                else Path(final_output)
            )
            path = export_strategy_compare(result, output_path)
            print(f"\nStrategy comparison exported: {path}")
    except (ValueError, ReportError) as exc:
        print(f"Error: {exc}")
    except Exception as exc:
        print(f"Unexpected error: {exc}")


if __name__ == "__main__":
    main()
