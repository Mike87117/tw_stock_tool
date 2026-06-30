import argparse
from itertools import product
from pathlib import Path
from typing import Any

import pandas as pd

from tw_stock_tool.analysis.analysis import analyze_stock
from tw_stock_tool.backtesting.backtest import run_backtest
from tw_stock_tool.utils.config import DEFAULT_PERIOD, FEE_RATE, INITIAL_CAPITAL, OUTPUT_DIR, TAX_RATE
from tw_stock_tool.backtesting.strategies import ma_cross_strategy, rsi_strategy, score_strategy

SWEEP_COLUMNS = [
    "Rank",
    "Strategy",
    "Parameters",
    "Total Return %",
    "Buy and Hold Return %",
    "CAGR %",
    "Trade Count",
    "Win Rate %",
    "Max Drawdown %",
    "Profit Factor",
    "Sharpe Ratio",
    "Sortino Ratio",
    "Error",
]

SORTABLE_COLUMNS = {
    "Total Return %",
    "Buy and Hold Return %",
    "CAGR %",
    "Trade Count",
    "Win Rate %",
    "Max Drawdown %",
    "Profit Factor",
    "Sharpe Ratio",
    "Sortino Ratio",
}

MA_SHORT_WINDOWS = (5, 10, 20)
MA_LONG_WINDOWS = (20, 30, 60)
RSI_BUY_BELOW = (25, 30, 35)
RSI_SELL_ABOVE = (65, 70, 75)
SCORE_BUY = (4, 5, 6)
SCORE_SELL = (-2, -3, -4)
VALID_STRATEGIES = {"all", "ma_cross", "rsi", "score"}


def ma_cross_parameter_grid(
    short_windows: tuple[int, ...] | None = None,
    long_windows: tuple[int, ...] | None = None,
) -> list[dict[str, int]]:
    shorts = short_windows if short_windows is not None else MA_SHORT_WINDOWS
    longs = long_windows if long_windows is not None else MA_LONG_WINDOWS

    grid = [
        {"short_window": short, "long_window": long}
        for short, long in product(shorts, longs)
        if short < long
    ]
    if not grid:
        raise ValueError("No valid ma_cross parameter combinations found.")
    return grid


def rsi_parameter_grid(
    buy_below: tuple[int, ...] | None = None,
    sell_above: tuple[int, ...] | None = None,
) -> list[dict[str, int]]:
    buys = buy_below if buy_below is not None else RSI_BUY_BELOW
    sells = sell_above if sell_above is not None else RSI_SELL_ABOVE

    grid = [
        {"buy_below": buy, "sell_above": sell}
        for buy, sell in product(buys, sells)
        if buy < sell
    ]
    if not grid:
        raise ValueError("No valid rsi parameter combinations found.")
    return grid


def score_parameter_grid(
    buy_scores: tuple[int, ...] | None = None,
    sell_scores: tuple[int, ...] | None = None,
) -> list[dict[str, int]]:
    buys = buy_scores if buy_scores is not None else SCORE_BUY
    sells = sell_scores if sell_scores is not None else SCORE_SELL

    grid = [
        {"buy_score": buy, "sell_score": sell}
        for buy, sell in product(buys, sells)
        if buy > sell
    ]
    if not grid:
        raise ValueError("No valid score parameter combinations found.")
    return grid


def _validate_inputs(
    stock_id: str,
    strategy: str,
    position_size: float,
    stop_loss_pct: float | None,
    take_profit_pct: float | None,
    max_hold_days: int | None,
) -> None:
    if not stock_id.strip():
        raise ValueError("stock cannot be blank.")
    if strategy not in VALID_STRATEGIES:
        raise ValueError(f"unsupported strategy: {strategy}.")
    if not 0 < position_size <= 1:
        raise ValueError("position_size must satisfy 0 < value <= 1.")
    if stop_loss_pct is not None and stop_loss_pct <= 0:
        raise ValueError("stop_loss_pct must be greater than 0.")
    if take_profit_pct is not None and take_profit_pct <= 0:
        raise ValueError("take_profit_pct must be greater than 0.")
    if max_hold_days is not None and max_hold_days <= 0:
        raise ValueError("max_hold_days must be greater than 0.")


def _selected_parameter_sets(
    strategy: str,
    ma_short_windows: tuple[int, ...] | None = None,
    ma_long_windows: tuple[int, ...] | None = None,
    rsi_buy_below: tuple[int, ...] | None = None,
    rsi_sell_above: tuple[int, ...] | None = None,
    score_buy: tuple[int, ...] | None = None,
    score_sell: tuple[int, ...] | None = None,
) -> list[tuple[str, dict[str, int]]]:
    selected: list[tuple[str, dict[str, int]]] = []
    if strategy in {"all", "ma_cross"}:
        selected.extend(("ma_cross", params) for params in ma_cross_parameter_grid(ma_short_windows, ma_long_windows))
    if strategy in {"all", "rsi"}:
        selected.extend(("rsi", params) for params in rsi_parameter_grid(rsi_buy_below, rsi_sell_above))
    if strategy in {"all", "score"}:
        selected.extend(("score", params) for params in score_parameter_grid(score_buy, score_sell))
    return selected


def _parameters_text(params: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in params.items())


def _build_strategy_df(strategy: str, df: pd.DataFrame, params: dict[str, int]) -> pd.DataFrame:
    if strategy == "ma_cross":
        return ma_cross_strategy(df, **params)
    if strategy == "rsi":
        return rsi_strategy(df, **params)
    if strategy == "score":
        return score_strategy(df, **params)
    raise ValueError(f"unsupported strategy: {strategy}.")


def _error_row(strategy: str, params: dict[str, int], error: Exception) -> dict[str, Any]:
    return {
        "Rank": None,
        "Strategy": strategy,
        "Parameters": _parameters_text(params),
        "Total Return %": None,
        "Buy and Hold Return %": None,
        "CAGR %": None,
        "Trade Count": None,
        "Win Rate %": None,
        "Max Drawdown %": None,
        "Profit Factor": None,
        "Sharpe Ratio": None,
        "Sortino Ratio": None,
        "Error": str(error),
    }


def run_parameter_sweep(
    stock_id: str,
    period: str = DEFAULT_PERIOD,
    strategy: str = "all",
    sort_by: str = "Total Return %",
    top: int = 20,
    force_refresh: bool = False,
    initial_capital: float = INITIAL_CAPITAL,
    fee_rate: float = FEE_RATE,
    tax_rate: float = TAX_RATE,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
    max_hold_days: int | None = None,
    position_size: float = 1.0,
    ma_short_windows: tuple[int, ...] | None = None,
    ma_long_windows: tuple[int, ...] | None = None,
    rsi_buy_below: tuple[int, ...] | None = None,
    rsi_sell_above: tuple[int, ...] | None = None,
    score_buy: tuple[int, ...] | None = None,
    score_sell: tuple[int, ...] | None = None,
) -> pd.DataFrame:
    _validate_inputs(
        stock_id=stock_id,
        strategy=strategy,
        position_size=position_size,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        max_hold_days=max_hold_days,
    )

    analysis = analyze_stock(stock_id=stock_id.strip(), period=period, force_refresh=force_refresh)
    rows: list[dict[str, Any]] = []

    parameter_sets = _selected_parameter_sets(
        strategy=strategy,
        ma_short_windows=ma_short_windows,
        ma_long_windows=ma_long_windows,
        rsi_buy_below=rsi_buy_below,
        rsi_sell_above=rsi_sell_above,
        score_buy=score_buy,
        score_sell=score_sell,
    )

    for strategy_name, params in parameter_sets:
        try:
            strategy_df = _build_strategy_df(strategy_name, analysis.signal_df, params)
            strategy_df = strategy_df.dropna(subset=["Close", "Signal"])
            result = run_backtest(
                strategy_df,
                initial_capital=initial_capital,
                fee_rate=fee_rate,
                tax_rate=tax_rate,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
                max_hold_days=max_hold_days,
                position_size=position_size,
            )
            rows.append(
                {
                    "Rank": None,
                    "Strategy": strategy_name,
                    "Parameters": _parameters_text(params),
                    "Total Return %": result["Total Return %"],
                    "Buy and Hold Return %": result["Buy and Hold Return %"],
                    "CAGR %": result["CAGR %"],
                    "Trade Count": result["Trade Count"],
                    "Win Rate %": result["Win Rate %"],
                    "Max Drawdown %": result["Max Drawdown %"],
                    "Profit Factor": result["Profit Factor"],
                    "Sharpe Ratio": result["Sharpe Ratio"],
                    "Sortino Ratio": result["Sortino Ratio"],
                    "Error": "",
                }
            )
        except Exception as exc:
            rows.append(_error_row(strategy_name, params, exc))

    result_df = pd.DataFrame(rows, columns=SWEEP_COLUMNS)
    if sort_by not in SORTABLE_COLUMNS:
        supported = ", ".join(sorted(SORTABLE_COLUMNS))
        raise ValueError(
            f"Unsupported sort-by column: {sort_by}. "
            f"Supported columns: {supported}"
        )

    ok = result_df[result_df["Error"] == ""].copy()
    errors = result_df[result_df["Error"] != ""].copy()
    ok["_SortValue"] = pd.to_numeric(ok[sort_by], errors="coerce").fillna(float("-inf"))
    ok = ok.sort_values(by="_SortValue", ascending=False, kind="mergesort")
    ok = ok.drop(columns=["_SortValue"])
    # top <= 0 means show all rows.
    if top > 0:
        ok = ok.head(top)
    ok = ok.reset_index(drop=True)
    if not ok.empty:
        ok["Rank"] = range(1, len(ok) + 1)
    return pd.concat([ok, errors], ignore_index=True)[SWEEP_COLUMNS]


def export_parameter_sweep(df: pd.DataFrame, stock_id: str, output: str | None) -> Path | None:
    if output is None:
        return None
    output_path = OUTPUT_DIR / f"{stock_id}_parameter_sweep.csv" if output == "" else Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


def export_parameter_sweep_excel(
    df: pd.DataFrame,
    stock_id: str,
    output_excel: str | None,
) -> Path | None:
    if output_excel is None:
        return None

    output_path = (
        OUTPUT_DIR / f"{stock_id}_parameter_sweep.xlsx"
        if output_excel == ""
        else Path(output_excel)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheets = {
        "All": df,
        "MA_Cross": df[df["Strategy"] == "ma_cross"],
        "RSI": df[df["Strategy"] == "rsi"],
        "Score": df[df["Strategy"] == "score"],
        "Errors": df[df["Error"].astype(str) != ""],
    }
    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for sheet_name, sheet_df in sheets.items():
                sheet_df.reindex(columns=SWEEP_COLUMNS).to_excel(
                    writer,
                    index=False,
                    sheet_name=sheet_name,
                )
    except PermissionError as exc:
        raise ValueError(
            f"Failed to write Excel file: {output_path}. "
            "Please close the file if it is open."
        ) from exc
    except Exception as exc:
        raise ValueError(f"Failed to write Excel file: {output_path}. {exc}") from exc
    return output_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy parameter sweep tool")
    parser.add_argument("--stock", required=True, help="Stock id, for example 2330")
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--strategy", default="all", choices=sorted(VALID_STRATEGIES))
    parser.add_argument("--sort-by", default="Total Return %")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--output", nargs="?", const="", help="Export CSV; omit path for default output")
    parser.add_argument(
        "--output-excel",
        nargs="?",
        const="",
        help="Export Excel; omit path for default output",
    )
    parser.add_argument("--stop-loss", type=float, dest="stop_loss_pct")
    parser.add_argument("--take-profit", type=float, dest="take_profit_pct")
    parser.add_argument("--max-hold-days", type=int)
    parser.add_argument("--position-size", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    try:
        args = _parse_args()
        result = run_parameter_sweep(
            stock_id=args.stock,
            period=args.period,
            strategy=args.strategy,
            sort_by=args.sort_by,
            top=args.top,
            force_refresh=args.force_refresh,
            stop_loss_pct=args.stop_loss_pct,
            take_profit_pct=args.take_profit_pct,
            max_hold_days=args.max_hold_days,
            position_size=args.position_size,
        )
        print(result.to_string(index=False))
        output_path = export_parameter_sweep(result, args.stock, args.output)
        if output_path:
            print(f"\nParameter sweep exported: {output_path}")
        excel_path = export_parameter_sweep_excel(result, args.stock, args.output_excel)
        if excel_path:
            print(f"\nParameter sweep Excel exported: {excel_path}")
    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
