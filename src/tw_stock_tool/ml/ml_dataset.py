"""Create machine-learning datasets from analyzed Taiwan stock data.

This module only builds clean feature/target tables. It does not train or
run any predictive model.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from tw_stock_tool.analysis.analysis import analyze_stock
from tw_stock_tool.utils.config import DEFAULT_PERIOD, OUTPUT_DIR

FEATURE_COLUMNS = [
    "Close",
    "MA5",
    "MA20",
    "MA60",
    "RSI",
    "MACD",
    "MACD_Signal",
    "MACD_Hist",
    "K",
    "D",
    "BB_Upper",
    "BB_Middle",
    "BB_Lower",
    "ATR",
    "OBV",
    "Volume_Ratio",
    "Score",
]


class MLDatasetError(Exception):
    """Raised when an ML dataset cannot be created or exported."""


def _validate_horizon(horizon: int) -> None:
    if horizon <= 0:
        raise ValueError("horizon must be greater than 0.")


def available_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return supported feature columns present in the input frame."""
    return [column for column in FEATURE_COLUMNS if column in df.columns]


def build_ml_dataset_from_signal_df(
    signal_df: pd.DataFrame,
    horizon: int = 5,
    dropna: bool = True,
) -> pd.DataFrame:
    """Build a no-look-ahead ML dataset from an analyzed signal DataFrame.

    Features are restricted to same-day or historical columns already present
    in ``signal_df``. The target uses future returns and is never included in
    the feature column list.
    """
    _validate_horizon(horizon)
    if "Close" not in signal_df.columns:
        raise MLDatasetError("signal_df must contain Close column.")

    feature_columns = available_feature_columns(signal_df)
    future_return_column = f"Future_Return_{horizon}D"
    target_column = f"Target_Up_{horizon}D"

    dataset = signal_df[feature_columns].copy()
    dataset[future_return_column] = signal_df["Close"].shift(-horizon) / signal_df["Close"] - 1
    dataset[target_column] = dataset[future_return_column] > 0

    # The last horizon rows do not have future data and must not be used.
    dataset = dataset.iloc[:-horizon].copy()
    if dropna:
        dataset = dataset.dropna()
    return dataset


def build_ml_dataset(
    stock_id: str,
    period: str = DEFAULT_PERIOD,
    horizon: int = 5,
    force_refresh: bool = False,
    dropna: bool = True,
) -> pd.DataFrame:
    """Analyze one stock and build a machine-learning dataset."""
    if not stock_id.strip():
        raise ValueError("stock cannot be blank.")
    analysis = analyze_stock(
        stock_id=stock_id.strip(),
        period=period,
        force_refresh=force_refresh,
    )
    return build_ml_dataset_from_signal_df(
        analysis.signal_df,
        horizon=horizon,
        dropna=dropna,
    )


def export_ml_dataset(df: pd.DataFrame, stock_id: str, horizon: int, output: str | None) -> Path | None:
    """Export an ML dataset to CSV when output is requested."""
    if output is None:
        return None
    _validate_horizon(horizon)
    output_path = OUTPUT_DIR / f"{stock_id}_ml_dataset_{horizon}d.csv" if output == "" else Path(output)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=True, index_label="Date", encoding="utf-8-sig")
    except PermissionError as exc:
        raise MLDatasetError(
            f"Failed to write CSV file: {output_path}. Please close the file if it is open."
        ) from exc
    except Exception as exc:
        raise MLDatasetError(f"Failed to write CSV file: {output_path}. {exc}") from exc
    return output_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create ML dataset for one Taiwan stock")
    parser.add_argument("--stock", required=True, help="Stock id, for example 2330")
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument(
        "--dropna",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Drop rows with missing feature or target values",
    )
    parser.add_argument("--output", nargs="?", const="", help="Export CSV; omit path for default output")
    return parser.parse_args(argv)


def main() -> None:
    try:
        args = _parse_args()
        dataset = build_ml_dataset(
            stock_id=args.stock,
            period=args.period,
            horizon=args.horizon,
            force_refresh=args.force_refresh,
            dropna=args.dropna,
        )
        print(dataset.to_string())
        output_path = export_ml_dataset(dataset, args.stock, args.horizon, args.output)
        if output_path:
            print(f"\nML dataset exported: {output_path}")
        print("\nThis dataset is for research only and does not train any AI model.")
    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
