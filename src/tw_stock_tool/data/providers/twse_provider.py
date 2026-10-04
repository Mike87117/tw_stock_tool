"""Taiwan Stock Exchange market data provider."""

from collections.abc import Callable
from typing import Any

import pandas as pd
import requests

from tw_stock_tool.data.providers.response_validation import month_has_data


def download_twse_stock(
    stock_id: str,
    period: str,
    interval: str,
    *,
    period_start: Callable[[str], pd.Timestamp],
    month_starts: Callable[
        [pd.Timestamp, pd.Timestamp],
        list[pd.Timestamp],
    ],
    parse_roc_date: Callable[[str], pd.Timestamp],
    to_float: Callable[[Any], float],
    to_int: Callable[[Any], int],
    finalize_official_rows: Callable[..., pd.DataFrame],
    error_type: type[Exception],
) -> pd.DataFrame:
    if interval != "1d":
        raise error_type("TWSE fallback only supports 1d interval.")

    start = period_start(period)
    rows: list[dict[str, Any]] = []

    for month in month_starts(
        start,
        pd.Timestamp.today().normalize(),
    ):
        params = {
            "response": "json",
            "date": month.strftime("%Y%m01"),
            "stockNo": stock_id,
        }
        response = requests.get(
            "https://www.twse.com.tw/exchangeReport/STOCK_DAY",
            params=params,
            timeout=20,
        )
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        data = response.json()
        if not month_has_data(data, "TWSE", month, error_type):
            continue
        month_rows = data.get("data")
        if not isinstance(month_rows, list):
            raise error_type(f"TWSE {month:%Y-%m} response is missing a valid data table.")
        for row in month_rows:
            if not isinstance(row, list) or len(row) < 7:
                raise error_type(f"TWSE {month:%Y-%m} contains an incomplete price row.")
            rows.append(
                {
                    "Date": parse_roc_date(row[0]),
                    "Open": to_float(row[3]),
                    "High": to_float(row[4]),
                    "Low": to_float(row[5]),
                    "Close": to_float(row[6]),
                    "Volume": to_int(row[1]),
                }
            )

    return finalize_official_rows(
        rows,
        stock_id,
        ".TW",
        start,
        period,
    )
