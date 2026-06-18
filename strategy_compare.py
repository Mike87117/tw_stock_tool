import argparse
from pathlib import Path

import pandas as pd

from analysis import analyze_stock
from backtest import run_backtest
from config import DEFAULT_INTERVAL, DEFAULT_PERIOD, FEE_RATE, INITIAL_CAPITAL, OUTPUT_DIR, TAX_RATE
from report import ReportError
from strategies import STRATEGIES

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
) -> pd.DataFrame:
    analysis = analyze_stock(
        stock_id=stock_id,
        period=period,
        interval=DEFAULT_INTERVAL,
        force_refresh=force_refresh,
    )

    rows = []
    for strategy_name, strategy_func in STRATEGIES.items():
        if strategy_name == "ma_cross_strategy":
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
        raise ReportError("策略比較檔案可能正在使用中，請先關閉後再試。") from exc
    except Exception as exc:
        raise ReportError(f"匯出策略比較失敗: {exc}") from exc
    return output_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="策略比較器")
    parser.add_argument("--stock", required=True, help="股票代號，例如 2330")
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--stop-loss", type=float, dest="stop_loss")
    parser.add_argument("--take-profit", type=float, dest="take_profit")
    parser.add_argument("--max-hold-days", type=int)
    parser.add_argument("--position-size", type=float, default=1.0)
    parser.add_argument("--ma-short", type=int, default=5)
    parser.add_argument("--ma-long", type=int, default=20)
    parser.add_argument("--rsi-buy-below", type=float, default=30)
    parser.add_argument("--rsi-sell-above", type=float, default=70)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--output", nargs="?", const="", help="輸出 Excel，可省略路徑使用預設位置")
    return parser.parse_args()


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
        )
        print(result.to_string(index=False))

        if args.output is not None:
            output_path = (
                OUTPUT_DIR / f"{args.stock}_strategy_compare.xlsx"
                if args.output == ""
                else Path(args.output)
            )
            path = export_strategy_compare(result, output_path)
            print(f"\n策略比較已輸出：{path}")
    except (ValueError, ReportError) as exc:
        print(f"錯誤：{exc}")
    except Exception as exc:
        print(f"未預期錯誤：{exc}")


if __name__ == "__main__":
    main()
