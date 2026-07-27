"""Shared date and numeric parsing helpers for official providers."""

from collections.abc import Callable
from typing import Any

import pandas as pd


def period_start(
    period: str,
) -> pd.Timestamp:
    today = pd.Timestamp.today().normalize()
    months = {
        "1d": 1,
        "5d": 1,
        "1mo": 1,
        "3mo": 3,
        "6mo": 6,
        "1y": 12,
        "2y": 24,
        "5y": 60,
        "10y": 120,
        "max": 180,
    }
    if period == "ytd":
        return pd.Timestamp(
            year=today.year,
            month=1,
            day=1,
        )
    return today - pd.DateOffset(
        months=months.get(period, 12)
    )


def month_starts(
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[pd.Timestamp]:
    cursor = pd.Timestamp(
        year=start.year,
        month=start.month,
        day=1,
    )
    final = pd.Timestamp(
        year=end.year,
        month=end.month,
        day=1,
    )
    months = []
    while cursor <= final:
        months.append(cursor)
        cursor += pd.DateOffset(months=1)
    return months


def parse_roc_date(
    value: str,
) -> pd.Timestamp:
    parts = value.strip().split("/")
    if len(parts) != 3:
        raise ValueError(
            f"Invalid ROC date: {value}"
        )
    year, month, day = (
        int(part.strip())
        for part in parts
    )
    return pd.Timestamp(
        year + 1911,
        month,
        day,
    )


def parse_tpex_date(
    value: str,
    month: pd.Timestamp | None = None,
    *,
    parse_roc_date: Callable[
        [str],
        pd.Timestamp,
    ],
) -> pd.Timestamp:
    text = str(value).strip()
    if "/" in text:
        parts = text.split("/")
        if len(parts) == 3:
            return parse_roc_date(text)
        if len(parts) == 2 and month is not None:
            return pd.Timestamp(
                month.year,
                int(parts[0]),
                int(parts[1]),
            )
    if text.isdigit() and len(text) == 7:
        return pd.Timestamp(
            int(text[:3]) + 1911,
            int(text[3:5]),
            int(text[5:7]),
        )
    if text.isdigit() and len(text) == 8:
        return pd.Timestamp(
            int(text[:4]),
            int(text[4:6]),
            int(text[6:8]),
        )
    raise ValueError(
        f"Invalid TPEX date: {value}"
    )


def to_float(
    value: Any,
) -> float:
    text = (
        str(value)
        .replace(",", "")
        .replace("--", "")
        .strip()
    )
    if not text:
        return float("nan")
    return float(text)


def to_int(
    value: Any,
    *,
    to_float: Callable[
        [Any],
        float,
    ],
) -> int:
    return int(
        to_float(value)
    )
