"""Shared OHLCV normalization helpers."""

from collections.abc import Callable
import math
from numbers import Number, Real
from typing import Any

import pandas as pd

from tw_stock_tool.utils.price_validation import validate_close_prices


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
    validate_close_prices(out["Close"], error_type=error_type)

    for column in ("Open", "High", "Low", "Volume"):
        for value in out[column]:
            # Missing volume remains supported; missing OHLC rows were dropped.
            if column == "Volume" and pd.api.types.is_scalar(value) and pd.isna(value):
                continue
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(float(value))
                or (value < 0 if column == "Volume" else value <= 0)
            ):
                bound = "greater than or equal to 0" if column == "Volume" else "greater than 0"
                raise error_type(f"{column} must be a finite numeric value {bound}; got {value!r}.")

    # Integer bar positions are not epoch timestamps. Mixed object indexes
    # need the same check before pandas can interpret numbers as nanoseconds.
    if pd.api.types.is_numeric_dtype(out.index.dtype) or any(isinstance(value, Number) for value in out.index):
        raise error_type(f"{symbol} index is not a valid DatetimeIndex.")

    if not pd.api.types.is_datetime64_any_dtype(
        out.index
    ):
        try:
            out.index = pd.to_datetime(out.index)
        except (TypeError, ValueError):
            raise error_type(
                f"{symbol} index is not a valid "
                "DatetimeIndex."
            )

    if not isinstance(out.index, pd.DatetimeIndex) or out.index.hasnans:
        raise error_type(f"{symbol} index is not a valid DatetimeIndex.")
    if not out.index.is_unique:
        raise error_type(f"{symbol} index contains duplicate dates.")
    out = out.sort_index()
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
