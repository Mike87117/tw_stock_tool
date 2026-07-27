"""Taipei Exchange market data provider."""

from collections.abc import Callable
from typing import Any

import pandas as pd
import requests


def download_tpex_stock(
    stock_id: str,
    period: str,
    interval: str,
    *,
    period_start: Callable[[str], pd.Timestamp],
    month_starts: Callable[
        [pd.Timestamp, pd.Timestamp],
        list[pd.Timestamp],
    ],
    parse_tpex_date: Callable[..., pd.Timestamp],
    to_float: Callable[[Any], float],
    to_int: Callable[[Any], int],
    finalize_official_rows: Callable[..., pd.DataFrame],
    download_latest_quote: Callable[
        [str, str, pd.Timestamp],
        pd.DataFrame,
    ],
    error_type: type[Exception],
) -> pd.DataFrame:
    if interval != "1d":
        raise error_type("TPEX fallback only supports 1d interval.")

    start = period_start(period)
    rows: list[dict[str, Any]] = []
    for month in month_starts(start, pd.Timestamp.today().normalize()):
        params = {
            "response": "json",
            "date": month.strftime("%Y/%m/01"),
            "id": stock_id,
        }
        response = requests.get(
            "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock",
            params=params,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        data = response.json()
        if str(data.get("stat", "")).lower() != "ok":
            continue
        tables = data.get("tables", [])
        month_rows = tables[0].get("data", []) if tables else []
        for row in month_rows:
            if len(row) < 7:
                continue
            rows.append(
                {
                    "Date": parse_tpex_date(row[0], month),
                    "Open": to_float(row[3]),
                    "High": to_float(row[4]),
                    "Low": to_float(row[5]),
                    "Close": to_float(row[6]),
                    "Volume": to_int(row[1]),
                }
            )

    if rows:
        return finalize_official_rows(rows, stock_id, ".TWO", start, period)
    return download_latest_quote(stock_id, period, start)


def download_tpex_latest_quote(
    stock_id: str,
    period: str,
    start: pd.Timestamp,
    *,
    parse_tpex_date: Callable[..., pd.Timestamp],
    to_float: Callable[[Any], float],
    to_int: Callable[[Any], int],
    finalize_official_rows: Callable[..., pd.DataFrame],
    error_type: type[Exception],
) -> pd.DataFrame:
    response = requests.get(
        "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    if hasattr(response, "raise_for_status"):
        response.raise_for_status()
    data = response.json()
    for row in data:
        if str(row.get("SecuritiesCompanyCode", "")).strip() != stock_id:
            continue
        rows = [
            {
                "Date": parse_tpex_date(str(row["Date"])),
                "Open": to_float(row["Open"]),
                "High": to_float(row["High"]),
                "Low": to_float(row["Low"]),
                "Close": to_float(row["Close"]),
                "Volume": to_int(row["TradingShares"]),
            }
        ]
        return finalize_official_rows(rows, stock_id, ".TWO", start, period)
    raise error_type(f"TPEX fallback has no data: {stock_id}.TWO")
