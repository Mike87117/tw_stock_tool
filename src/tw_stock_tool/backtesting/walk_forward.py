"""Walk-forward validation for strategy parameter sweeps."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from tw_stock_tool.analysis.analysis import analyze_stock
from tw_stock_tool.backtesting.backtest import run_backtest
from tw_stock_tool.utils.config import DEFAULT_PERIOD, FEE_RATE, INITIAL_CAPITAL, OUTPUT_DIR, TAX_RATE
from tw_stock_tool.backtesting.parameter_sweep import (
    VALID_STRATEGIES,
    _parameters_text,
    ma_cross_parameter_grid,
    rsi_parameter_grid,
    score_parameter_grid,
)
from tw_stock_tool.backtesting.strategies import ma_cross_strategy, rsi_strategy, score_strategy

WALK_FORWARD_COLUMNS = [
    "Window",
    "Train Start",
    "Train End",
    "Test Start",
    "Test End",
    "Strategy",
    "Parameters",
    "Train Total Return %",
    "Test Total Return %",
    "Train CAGR %",
    "Test CAGR %",
    "Train Trade Count",
    "Test Trade Count",
    "Train Win Rate %",
    "Test Win Rate %",
    "Train Max Drawdown %",
    "Test Max Drawdown %",
    "Train Profit Factor",
    "Test Profit Factor",
    "Train Sharpe Ratio",
    "Test Sharpe Ratio",
    "Train Sortino Ratio",
    "Test Sortino Ratio",
    "Error",
]

SUMMARY_COLUMNS = [
    "Stock",
    "Period",
    "Strategy",
    "Train Days",
    "Test Days",
    "Step Days",
    "Windows",
    "Avg Test Total Return %",
    "Avg Test CAGR %",
    "Avg Test Sharpe Ratio",
    "Avg Test Max Drawdown %",
    "Positive Test Windows",
    "Positive Test Windows %",
    "Error Windows",
]

SORTABLE_COLUMNS = {
    "Train Total Return %",
    "Train CAGR %",
    "Train Sharpe Ratio",
    "Train Sortino Ratio",
    "Train Profit Factor",
    "Train Max Drawdown %",
}

METRIC_MAP = {
    "Total Return %": "Total Return %",
    "CAGR %": "CAGR %",
    "Trade Count": "Trade Count",
    "Win Rate %": "Win Rate %",
    "Max Drawdown %": "Max Drawdown %",
    "Profit Factor": "Profit Factor",
    "Sharpe Ratio": "Sharpe Ratio",
    "Sortino Ratio": "Sortino Ratio",
}


def split_windows(
    df: pd.DataFrame,
    train_days: int,
    test_days: int,
    step_days: int,
) -> list[tuple[int, pd.DataFrame, pd.DataFrame]]:
    """Split data into rolling train/test windows by row count."""
    if train_days <= 0:
        raise ValueError("train_days must be greater than 0.")
    if test_days <= 0:
        raise ValueError("test_days must be greater than 0.")
    if step_days <= 0:
        raise ValueError("step_days must be greater than 0.")

    required_rows = train_days + test_days
    windows: list[tuple[int, pd.DataFrame, pd.DataFrame]] = []
    start = 0
    window_number = 1
    while start + required_rows <= len(df):
        train = df.iloc[start:start + train_days].copy()
        test = df.iloc[start + train_days:start + required_rows].copy()
        windows.append((window_number, train, test))
        start += step_days
        window_number += 1

    if not windows:
        raise ValueError(
            "Not enough rows to build walk-forward windows: "
            f"need at least {required_rows}, got {len(df)}."
        )
    return windows


def _validate_inputs(
    stock_id: str,
    strategy: str,
    train_days: int,
    test_days: int,
    step_days: int,
    sort_by: str,
    position_size: float,
    stop_loss_pct: float | None,
    take_profit_pct: float | None,
    max_hold_days: int | None,
) -> None:
    if not stock_id.strip():
        raise ValueError("stock cannot be blank.")
    if strategy not in VALID_STRATEGIES:
        raise ValueError(f"unsupported strategy: {strategy}.")
    if train_days <= 0:
        raise ValueError("train_days must be greater than 0.")
    if test_days <= 0:
        raise ValueError("test_days must be greater than 0.")
    if step_days <= 0:
        raise ValueError("step_days must be greater than 0.")
    if sort_by not in SORTABLE_COLUMNS:
        supported = ", ".join(sorted(SORTABLE_COLUMNS))
        raise ValueError(
            f"Unsupported sort-by column: {sort_by}. "
            f"Supported columns: {supported}"
        )
    if not 0 < position_size <= 1:
        raise ValueError("position_size must satisfy 0 < value <= 1.")
    if stop_loss_pct is not None and stop_loss_pct <= 0:
        raise ValueError("stop_loss_pct must be greater than 0.")
    if take_profit_pct is not None and take_profit_pct <= 0:
        raise ValueError("take_profit_pct must be greater than 0.")
    if max_hold_days is not None and max_hold_days <= 0:
        raise ValueError("max_hold_days must be greater than 0.")


def _selected_strategies(strategy: str) -> list[str]:
    if strategy == "all":
        return ["ma_cross", "rsi", "score"]
    return [strategy]


def _parameter_grid(
    strategy: str,
    ma_short_windows: tuple[int, ...] | None = None,
    ma_long_windows: tuple[int, ...] | None = None,
    rsi_buy_below: tuple[int, ...] | None = None,
    rsi_sell_above: tuple[int, ...] | None = None,
    score_buy: tuple[int, ...] | None = None,
    score_sell: tuple[int, ...] | None = None,
) -> list[dict[str, int]]:
    if strategy == "ma_cross":
        return ma_cross_parameter_grid(ma_short_windows, ma_long_windows)
    if strategy == "rsi":
        return rsi_parameter_grid(rsi_buy_below, rsi_sell_above)
    if strategy == "score":
        return score_parameter_grid(score_buy, score_sell)
    raise ValueError(f"unsupported strategy: {strategy}.")


def _build_strategy_df(
    strategy: str,
    df: pd.DataFrame,
    params: dict[str, int],
) -> pd.DataFrame:
    if strategy == "ma_cross":
        return ma_cross_strategy(df, **params)
    if strategy == "rsi":
        return rsi_strategy(df, **params)
    if strategy == "score":
        return score_strategy(df, **params)
    raise ValueError(f"unsupported strategy: {strategy}.")


def _run_strategy_backtest(
    df: pd.DataFrame,
    strategy: str,
    params: dict[str, int],
    stop_loss_pct: float | None,
    take_profit_pct: float | None,
    max_hold_days: int | None,
    position_size: float,
    initial_capital: float,
    fee_rate: float,
    tax_rate: float,
) -> dict[str, Any]:
    strategy_df = _build_strategy_df(strategy, df, params)
    strategy_df = strategy_df.dropna(subset=["Close", "Signal"])
    return run_backtest(
        strategy_df,
        initial_capital=initial_capital,
        fee_rate=fee_rate,
        tax_rate=tax_rate,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        max_hold_days=max_hold_days,
        position_size=position_size,
    )


def _base_row(
    window_number: int,
    train: pd.DataFrame,
    test: pd.DataFrame,
    strategy: str,
    params: dict[str, int] | None,
) -> dict[str, Any]:
    return {
        "Window": window_number,
        "Train Start": train.index[0],
        "Train End": train.index[-1],
        "Test Start": test.index[0],
        "Test End": test.index[-1],
        "Strategy": strategy,
        "Parameters": _parameters_text(params or {}),
    }


def _error_row(
    window_number: int,
    train: pd.DataFrame,
    test: pd.DataFrame,
    strategy: str,
    error: Exception,
    params: dict[str, int] | None = None,
) -> dict[str, Any]:
    row = _base_row(window_number, train, test, strategy, params)
    for column in WALK_FORWARD_COLUMNS:
        row.setdefault(column, None)
    row["Error"] = str(error)
    return row


def _result_row(
    window_number: int,
    train: pd.DataFrame,
    test: pd.DataFrame,
    strategy: str,
    params: dict[str, int],
    train_result: dict[str, Any],
    test_result: dict[str, Any],
) -> dict[str, Any]:
    row = _base_row(window_number, train, test, strategy, params)
    row.update(
        {
            "Train Total Return %": train_result["Total Return %"],
            "Test Total Return %": test_result["Total Return %"],
            "Train CAGR %": train_result["CAGR %"],
            "Test CAGR %": test_result["CAGR %"],
            "Train Trade Count": train_result["Trade Count"],
            "Test Trade Count": test_result["Trade Count"],
            "Train Win Rate %": train_result["Win Rate %"],
            "Test Win Rate %": test_result["Win Rate %"],
            "Train Max Drawdown %": train_result["Max Drawdown %"],
            "Test Max Drawdown %": test_result["Max Drawdown %"],
            "Train Profit Factor": train_result["Profit Factor"],
            "Test Profit Factor": test_result["Profit Factor"],
            "Train Sharpe Ratio": train_result["Sharpe Ratio"],
            "Test Sharpe Ratio": test_result["Sharpe Ratio"],
            "Train Sortino Ratio": train_result["Sortino Ratio"],
            "Test Sortino Ratio": test_result["Sortino Ratio"],
            "Error": "",
        }
    )
    return row


def _sort_metric(train_result: dict[str, Any], sort_by: str) -> float:
    metric_name = sort_by.replace("Train ", "", 1)
    value = train_result.get(METRIC_MAP.get(metric_name, metric_name))
    return float(pd.to_numeric(value, errors="coerce"))


def _evaluate_window_strategy(
    window_number: int,
    train: pd.DataFrame,
    test: pd.DataFrame,
    strategy: str,
    sort_by: str,
    stop_loss_pct: float | None,
    take_profit_pct: float | None,
    max_hold_days: int | None,
    position_size: float,
    initial_capital: float,
    fee_rate: float,
    tax_rate: float,
    ma_short_windows: tuple[int, ...] | None = None,
    ma_long_windows: tuple[int, ...] | None = None,
    rsi_buy_below: tuple[int, ...] | None = None,
    rsi_sell_above: tuple[int, ...] | None = None,
    score_buy: tuple[int, ...] | None = None,
    score_sell: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    best_params: dict[str, int] | None = None
    best_train_result: dict[str, Any] | None = None
    best_value = float("-inf")
    errors: list[str] = []

    grid = _parameter_grid(
        strategy=strategy,
        ma_short_windows=ma_short_windows,
        ma_long_windows=ma_long_windows,
        rsi_buy_below=rsi_buy_below,
        rsi_sell_above=rsi_sell_above,
        score_buy=score_buy,
        score_sell=score_sell,
    )

    for params in grid:
        try:
            train_result = _run_strategy_backtest(
                train,
                strategy,
                params,
                stop_loss_pct,
                take_profit_pct,
                max_hold_days,
                position_size,
                initial_capital,
                fee_rate,
                tax_rate,
            )
            metric_value = _sort_metric(train_result, sort_by)
            if metric_value > best_value:
                best_value = metric_value
                best_params = params
                best_train_result = train_result
        except Exception as exc:
            errors.append(f"{_parameters_text(params)}: {exc}")

    if best_params is None or best_train_result is None:
        message = "; ".join(errors) if errors else "No parameter set could be evaluated."
        raise ValueError(message)

    test_result = _run_strategy_backtest(
        test,
        strategy,
        best_params,
        stop_loss_pct,
        take_profit_pct,
        max_hold_days,
        position_size,
        initial_capital,
        fee_rate,
        tax_rate,
    )
    return _result_row(
        window_number,
        train,
        test,
        strategy,
        best_params,
        best_train_result,
        test_result,
    )


def run_walk_forward(
    stock_id: str,
    period: str = DEFAULT_PERIOD,
    strategy: str = "all",
    train_days: int = 504,
    test_days: int = 126,
    step_days: int | None = None,
    sort_by: str = "Train Sharpe Ratio",
    force_refresh: bool = False,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
    max_hold_days: int | None = None,
    position_size: float = 1.0,
    initial_capital: float = INITIAL_CAPITAL,
    fee_rate: float = FEE_RATE,
    tax_rate: float = TAX_RATE,
    ma_short_windows: tuple[int, ...] | None = None,
    ma_long_windows: tuple[int, ...] | None = None,
    rsi_buy_below: tuple[int, ...] | None = None,
    rsi_sell_above: tuple[int, ...] | None = None,
    score_buy: tuple[int, ...] | None = None,
    score_sell: tuple[int, ...] | None = None,
) -> pd.DataFrame:
    actual_step_days = test_days if step_days is None else step_days
    _validate_inputs(
        stock_id=stock_id,
        strategy=strategy,
        train_days=train_days,
        test_days=test_days,
        step_days=actual_step_days,
        sort_by=sort_by,
        position_size=position_size,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        max_hold_days=max_hold_days,
    )

    analysis = analyze_stock(
        stock_id=stock_id.strip(),
        period=period,
        force_refresh=force_refresh,
    )
    windows = split_windows(analysis.signal_df, train_days, test_days, actual_step_days)

    rows: list[dict[str, Any]] = []
    for window_number, train, test in windows:
        for strategy_name in _selected_strategies(strategy):
            try:
                rows.append(
                    _evaluate_window_strategy(
                        window_number=window_number,
                        train=train,
                        test=test,
                        strategy=strategy_name,
                        sort_by=sort_by,
                        stop_loss_pct=stop_loss_pct,
                        take_profit_pct=take_profit_pct,
                        max_hold_days=max_hold_days,
                        position_size=position_size,
                        initial_capital=initial_capital,
                        fee_rate=fee_rate,
                        tax_rate=tax_rate,
                        ma_short_windows=ma_short_windows,
                        ma_long_windows=ma_long_windows,
                        rsi_buy_below=rsi_buy_below,
                        rsi_sell_above=rsi_sell_above,
                        score_buy=score_buy,
                        score_sell=score_sell,
                    )
                )
            except Exception as exc:
                rows.append(_error_row(window_number, train, test, strategy_name, exc))

    return pd.DataFrame(rows, columns=WALK_FORWARD_COLUMNS)


def build_summary(
    detail_df: pd.DataFrame,
    stock_id: str,
    period: str,
    strategy: str,
    train_days: int,
    test_days: int,
    step_days: int,
) -> pd.DataFrame:
    ok = detail_df[detail_df["Error"].astype(str) == ""].copy()
    errors = detail_df[detail_df["Error"].astype(str) != ""].copy()

    def mean_value(column: str) -> float:
        if ok.empty:
            return 0.0
        return float(pd.to_numeric(ok[column], errors="coerce").mean())

    positive = int((pd.to_numeric(ok["Test Total Return %"], errors="coerce") > 0).sum())
    positive_pct = (positive / len(ok) * 100) if len(ok) else 0.0
    row = {
        "Stock": stock_id,
        "Period": period,
        "Strategy": strategy,
        "Train Days": train_days,
        "Test Days": test_days,
        "Step Days": step_days,
        "Windows": int(detail_df["Window"].nunique()) if not detail_df.empty else 0,
        "Avg Test Total Return %": mean_value("Test Total Return %"),
        "Avg Test CAGR %": mean_value("Test CAGR %"),
        "Avg Test Sharpe Ratio": mean_value("Test Sharpe Ratio"),
        "Avg Test Max Drawdown %": mean_value("Test Max Drawdown %"),
        "Positive Test Windows": positive,
        "Positive Test Windows %": positive_pct,
        "Error Windows": len(errors),
    }
    return pd.DataFrame([row], columns=SUMMARY_COLUMNS)


def export_walk_forward_excel(
    detail_df: pd.DataFrame,
    stock_id: str,
    period: str,
    strategy: str,
    train_days: int,
    test_days: int,
    step_days: int,
    output: str | None,
) -> Path | None:
    if output is None:
        return None

    output_path = OUTPUT_DIR / f"{stock_id}_walk_forward.xlsx" if output == "" else Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df = build_summary(
        detail_df,
        stock_id=stock_id,
        period=period,
        strategy=strategy,
        train_days=train_days,
        test_days=test_days,
        step_days=step_days,
    )
    errors_df = detail_df[detail_df["Error"].astype(str) != ""].copy()

    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            summary_df.to_excel(writer, index=False, sheet_name="Summary")
            detail_df.reindex(columns=WALK_FORWARD_COLUMNS).to_excel(
                writer,
                index=False,
                sheet_name="Detail",
            )
            errors_df.reindex(columns=WALK_FORWARD_COLUMNS).to_excel(
                writer,
                index=False,
                sheet_name="Errors",
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
    parser = argparse.ArgumentParser(description="Walk-forward strategy validation tool")
    parser.add_argument("--stock", required=True, help="Stock id, for example 2330")
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--strategy", default="all", choices=sorted(VALID_STRATEGIES))
    parser.add_argument("--train-days", type=int, default=504)
    parser.add_argument("--test-days", type=int, default=126)
    parser.add_argument("--step-days", type=int)
    parser.add_argument("--sort-by", default="Train Sharpe Ratio")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument(
        "--output",
        nargs="?",
        const="",
        help="Export Excel; omit path for default output",
    )
    parser.add_argument("--stop-loss", type=float, dest="stop_loss_pct")
    parser.add_argument("--take-profit", type=float, dest="take_profit_pct")
    parser.add_argument("--max-hold-days", type=int)
    parser.add_argument("--position-size", type=float, default=1.0)
    return parser.parse_args()


def main() -> int | None:
    try:
        args = _parse_args()
        actual_step_days = args.test_days if args.step_days is None else args.step_days
        result = run_walk_forward(
            stock_id=args.stock,
            period=args.period,
            strategy=args.strategy,
            train_days=args.train_days,
            test_days=args.test_days,
            step_days=args.step_days,
            sort_by=args.sort_by,
            force_refresh=args.force_refresh,
            stop_loss_pct=args.stop_loss_pct,
            take_profit_pct=args.take_profit_pct,
            max_hold_days=args.max_hold_days,
            position_size=args.position_size,
        )
        print(result.to_string(index=False))
        output_path = export_walk_forward_excel(
            result,
            stock_id=args.stock,
            period=args.period,
            strategy=args.strategy,
            train_days=args.train_days,
            test_days=args.test_days,
            step_days=actual_step_days,
            output=args.output,
        )
        if output_path:
            print(f"\nWalk-forward Excel exported: {output_path}")
        print("\nWalk-forward results are historical validation only, not investment advice.")
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
