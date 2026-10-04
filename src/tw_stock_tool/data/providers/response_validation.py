"""Distinguish explicit empty months from failed official data responses."""

from typing import Any

import pandas as pd


_NO_DATA_STATUSES = {
    "no data",
    "很抱歉，沒有符合條件的資料!",
    "很抱歉，沒有符合條件的資料！",
    "查無資料",
    "查無資料。",
}


def month_has_data(
    payload: Any,
    provider: str,
    month: pd.Timestamp,
    error_type: type[Exception],
) -> bool:
    """Fail closed on unknown statuses; only explicit no-data responses skip."""
    if not isinstance(payload, dict):
        raise error_type(f"{provider} {month:%Y-%m} returned an invalid response.")
    status = str(payload.get("stat", "")).strip()
    if status.lower() == "ok":
        return True
    if status.lower() in _NO_DATA_STATUSES:
        return False
    raise error_type(f"{provider} {month:%Y-%m} request failed: {status or 'missing stat'}")
