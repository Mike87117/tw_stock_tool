"""Shared OHLCV normalization helpers."""

from collections.abc import Callable
from typing import Any

import pandas as pd


def normalize_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def prepare_ohlcv(
    df: pd.DataFrame,
    symbol: str,
    *,
    normalize_columns: Callable[
        [pd.DataFrame],
        pd.DataFrame,
    ],
    error_type: type[Exception],
) -> pd.DataFrame:
    df = normalize_columns(df)
    required = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]
    missing = [
        column
        for column in required
        if column not in df.columns
    ]
    if missing:
        raise error_type(
            f"Missing data columns: {missing}"
        )
    out = df[required].dropna(
        subset=[
            "Open",
            "High",
            "Low",
            "Close",
        ]
    )
    if out.empty:
        raise error_type(
            f"{symbol} has no usable OHLC data."
        )

    if not pd.api.types.is_datetime64_any_dtype(
        out.index
    ):
        try:
            out.index = pd.to_datetime(out.index)
        except Exception:
            raise error_type(
                f"{symbol} index is not a valid "
                "DatetimeIndex."
            )

    out.index.name = "Date"
    return out


def finalize_official_rows(
    rows: list[dict[str, Any]],
    stock_id: str,
    suffix: str,
    start: pd.Timestamp,
    period: str,
    *,
    prepare_ohlcv: Callable[
        [pd.DataFrame, str],
        pd.DataFrame,
    ],
    error_type: type[Exception],
) -> pd.DataFrame:
    if not rows:
        raise error_type(
            f"Official fallback has no data: "
            f"{stock_id}{suffix}"
        )

    df = pd.DataFrame(rows).drop_duplicates(
        subset=["Date"]
    )
    df = df.set_index("Date").sort_index()
    df = df[df.index >= start]
    if period == "1d":
        df = df.tail(1)
    elif period == "5d":
        df = df.tail(5)
    return prepare_ohlcv(
        df,
        f"{stock_id}{suffix}",
    )
