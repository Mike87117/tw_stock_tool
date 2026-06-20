"""Update Taiwan stock id lists from official public data sources.

The tool fetches listed (TWSE) and over-the-counter (TPEx) company lists,
filters out non-common-stock products, and writes one stock id per line.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests

TWSE_STOCK_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_STOCK_LIST_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
VALID_MARKETS = {"twse", "tpex", "all"}
MIN_COMMON_STOCKS = 100

CODE_KEYS = (
    "\u516c\u53f8\u4ee3\u865f",  # TWSE: company code
    "SecuritiesCompanyCode",  # TPEx OpenAPI
    "Code",
    "\u8b49\u5238\u4ee3\u865f",
    "\u6709\u50f9\u8b49\u5238\u4ee3\u865f",
    "\u80a1\u7968\u4ee3\u865f",
    "stock_id",
)
NAME_KEYS = (
    "\u516c\u53f8\u540d\u7a31",  # TWSE: company name
    "CompanyName",  # TPEx OpenAPI
    "Name",
    "\u8b49\u5238\u540d\u7a31",
    "\u6709\u50f9\u8b49\u5238\u540d\u7a31",
    "\u80a1\u7968\u540d\u7a31",
    "name",
)
TYPE_KEYS = (
    "\u6709\u50f9\u8b49\u5238\u5225",
    "\u7522\u696d\u5225",  # TWSE: industry type
    "SecuritiesIndustryCode",  # TPEx OpenAPI
    "Type",
    "\u5e02\u5834\u5225",
    "\u985e\u5225",
    "security_type",
)
EXCLUDE_KEYWORDS = (
    "ETF",
    "ETN",
    "WARRANT",
    "CALL",
    "PUT",
    "\u6b0a\u8b49",
    "\u8a8d\u8cfc",
    "\u8a8d\u552e",
    "\u725b\u8b49",
    "\u718a\u8b49",
    "\u725b\u718a",
    "\u6307\u6578\u6295\u8cc7\u8b49\u5238",
    "\u53d7\u76ca\u8b49\u5238",
    "\u5b58\u8a17\u6191\u8b49",
)


class StockListUpdaterError(Exception):
    """Raised when stock list update fails."""


def _field(record: dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None:
            return str(value).strip()
    return ""


def _fetch_json(url: str, timeout: int = 20) -> list[dict[str, Any]]:
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise StockListUpdaterError(f"Failed to fetch official data: {url} ({exc})") from exc
    except ValueError as exc:
        raise StockListUpdaterError(f"Failed to parse JSON from official data: {url}") from exc

    if not isinstance(payload, list):
        raise StockListUpdaterError(f"Unexpected official data format from: {url}")
    return [item for item in payload if isinstance(item, dict)]


def _records_to_frame(records: list[dict[str, Any]], market: str) -> pd.DataFrame:
    rows = []
    for record in records:
        rows.append(
            {
                "Stock": _field(record, CODE_KEYS),
                "Name": _field(record, NAME_KEYS),
                "Market": market.upper(),
                "Type": _field(record, TYPE_KEYS),
            }
        )
    frame = pd.DataFrame(rows, columns=["Stock", "Name", "Market", "Type"])
    if records and not frame["Stock"].astype(str).str.strip().any():
        sample_keys = sorted({key for record in records[:3] for key in record.keys()})
        raise StockListUpdaterError(
            f"Cannot find stock code field for {market.upper()} data. "
            f"Supported keys: {', '.join(CODE_KEYS)}. "
            f"Sample keys: {sample_keys}"
        )
    return frame


def fetch_twse_stock_list() -> pd.DataFrame:
    """Fetch TWSE listed company stock ids from official public data."""
    return _records_to_frame(_fetch_json(TWSE_STOCK_LIST_URL), market="twse")


def fetch_tpex_stock_list() -> pd.DataFrame:
    """Fetch TPEx mainboard company stock ids from official public data."""
    return _records_to_frame(_fetch_json(TPEX_STOCK_LIST_URL), market="tpex")


def _is_common_stock_code(stock_id: str) -> bool:
    value = str(stock_id).strip()
    return len(value) == 4 and value.isdigit() and not value.startswith("00")


def filter_common_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """Keep ordinary stock ids and exclude ETF/warrant-like products."""
    if df.empty:
        return df.reindex(columns=["Stock", "Name", "Market", "Type"])

    filtered = df.copy()
    filtered["Stock"] = filtered["Stock"].astype(str).str.strip()
    filtered["Name"] = filtered.get("Name", "").astype(str).str.strip()
    filtered["Type"] = filtered.get("Type", "").astype(str).str.strip()
    mask = filtered["Stock"].map(_is_common_stock_code)
    text = (filtered["Name"] + " " + filtered["Type"]).str.upper()
    for keyword in EXCLUDE_KEYWORDS:
        mask &= ~text.str.contains(keyword.upper(), regex=False, na=False)
    return filtered[mask].reset_index(drop=True)


def normalize_stock_list(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize, filter, sort, and de-duplicate stock rows."""
    normalized = filter_common_stocks(df)
    if normalized.empty:
        return normalized.reindex(columns=["Stock", "Name", "Market", "Type"])
    normalized = normalized.drop_duplicates(subset=["Stock"], keep="first")
    normalized = normalized.sort_values(by="Stock", kind="mergesort").reset_index(drop=True)
    return normalized.reindex(columns=["Stock", "Name", "Market", "Type"])


def write_stock_list(df: pd.DataFrame, output: str | Path) -> Path:
    """Write one stock id per line."""
    path = Path(output)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        stocks = df["Stock"].astype(str).tolist()
        path.write_text("\n".join(stocks) + ("\n" if stocks else ""), encoding="utf-8")
    except OSError as exc:
        raise StockListUpdaterError(f"Failed to write stock list: {path} ({exc})") from exc
    return path


def _fetch_market(market: str) -> pd.DataFrame:
    if market == "twse":
        return fetch_twse_stock_list()
    if market == "tpex":
        return fetch_tpex_stock_list()
    raise ValueError(f"Unsupported market: {market}. Supported markets: all, tpex, twse")


def update_stock_list(
    market: str = "all",
    output: str | Path = "stocks.txt",
    allow_partial: bool = False,
    min_common_stocks: int = MIN_COMMON_STOCKS,
) -> tuple[pd.DataFrame, Path]:
    """Fetch, normalize, and write a stock list for the selected market."""
    selected = market.lower().strip()
    if selected not in VALID_MARKETS:
        raise ValueError(f"Unsupported market: {market}. Supported markets: all, tpex, twse")

    markets = ["twse", "tpex"] if selected == "all" else [selected]
    frames: list[pd.DataFrame] = []
    errors: list[str] = []
    for item in markets:
        try:
            frames.append(_fetch_market(item))
        except Exception as exc:
            errors.append(f"{item.upper()}: {exc}")

    if errors and (not allow_partial or not frames):
        joined = "; ".join(errors)
        raise StockListUpdaterError(f"Failed to update stock list. {joined}")

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    normalized = normalize_stock_list(combined)
    if len(normalized) < min_common_stocks:
        raise StockListUpdaterError(
            "Abnormally few common stocks parsed: "
            f"{len(normalized)} < {min_common_stocks}. "
            "Official data format may have changed."
        )
    path = write_stock_list(normalized, output)
    return normalized, path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update Taiwan stock list from official sources")
    parser.add_argument("--market", default="all", choices=sorted(VALID_MARKETS))
    parser.add_argument("--output", default="stocks.txt")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow output when one source fails but another source succeeds",
    )
    return parser.parse_args(argv)


def main() -> None:
    try:
        args = _parse_args()
        df, path = update_stock_list(
            market=args.market,
            output=args.output,
            allow_partial=args.allow_partial,
        )
        print(f"Stock list updated: {path}")
        print(f"Stocks: {len(df)}")
    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
