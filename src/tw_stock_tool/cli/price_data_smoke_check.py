"""Manual smoke check for Taiwan price data sources.

This tool intentionally calls live data providers through data_loader and is
not part of the default unittest or CI workflow.
"""

from __future__ import annotations

import argparse
from typing import Any

import pandas as pd

from tw_stock_tool.data import data_loader

REQUIRED_COLUMNS = ("Open", "High", "Low", "Close", "Volume")
DEFAULT_TWSE_STOCK = "2330"
DEFAULT_TPEX_STOCK = "8069"
DEFAULT_PERIOD = "1mo"
DEFAULT_INTERVAL = "1d"


class PriceDataSmokeCheckError(Exception):
    """Raised when the live price data smoke check fails."""


def _validate_price_data(df: pd.DataFrame, symbol: str) -> None:
    if df.empty:
        raise PriceDataSmokeCheckError("price dataframe is empty")
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise PriceDataSmokeCheckError(f"missing required columns: {', '.join(missing)}")
    if not symbol or not (symbol.endswith(".TW") or symbol.endswith(".TWO")):
        raise PriceDataSmokeCheckError(f"unexpected symbol: {symbol}")


def run_one_check(
    check_name: str,
    stock_id: str,
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    auto_adjust: bool = True,
) -> dict[str, Any]:
    """Run one live price-data check and return a result row."""
    try:
        df, symbol = data_loader.download_tw_stock(
            stock_id,
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            force_refresh=True,
        )
        _validate_price_data(df, symbol)
        return {
            "Check": check_name,
            "Stock": stock_id,
            "Symbol": symbol,
            "Rows": len(df),
            "Status": "PASS",
            "Error": "",
        }
    except Exception as exc:
        return {
            "Check": check_name,
            "Stock": stock_id,
            "Symbol": "",
            "Rows": 0,
            "Status": "FAIL",
            "Error": str(exc),
        }


def collect_smoke_check_results(
    twse_stock: str = DEFAULT_TWSE_STOCK,
    tpex_stock: str = DEFAULT_TPEX_STOCK,
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
) -> list[dict[str, Any]]:
    """Collect yfinance and official-fallback price data check rows."""
    checks = [
        ("yfinance TWSE", twse_stock, True),
        ("yfinance TPEx", tpex_stock, True),
        ("fallback TWSE", twse_stock, False),
        ("fallback TPEx", tpex_stock, False),
    ]
    return [
        run_one_check(name, stock, period=period, interval=interval, auto_adjust=auto_adjust)
        for name, stock, auto_adjust in checks
    ]


def raise_for_failures(results: list[dict[str, Any]]) -> None:
    """Raise a concise error if any smoke-check row failed."""
    failures = [row for row in results if row["Status"] != "PASS"]
    if failures:
        detail = "; ".join(f"{row['Check']} {row['Stock']}: {row['Error']}" for row in failures)
        raise PriceDataSmokeCheckError(f"Price data smoke check failed. {detail}")


def run_smoke_check(
    twse_stock: str = DEFAULT_TWSE_STOCK,
    tpex_stock: str = DEFAULT_TPEX_STOCK,
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
) -> list[dict[str, Any]]:
    """Check yfinance and official-fallback price data paths."""
    results = collect_smoke_check_results(
        twse_stock=twse_stock,
        tpex_stock=tpex_stock,
        period=period,
        interval=interval,
    )
    raise_for_failures(results)
    return results


def print_results(results: list[dict[str, Any]]) -> None:
    """Print a compact price-data smoke check report."""
    print("=================================")
    print("Price Data Smoke Check")
    print("=================================")
    for row in results:
        print(
            f"{row['Check']} | Stock={row['Stock']} | Symbol={row['Symbol']} | "
            f"Rows={row['Rows']} | Status={row['Status']}"
        )
        if row["Error"]:
            print(f"  Error: {row['Error']}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke check Taiwan price data sources")
    parser.add_argument("--twse-stock", default=DEFAULT_TWSE_STOCK)
    parser.add_argument("--tpex-stock", default=DEFAULT_TPEX_STOCK)
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--interval", default=DEFAULT_INTERVAL)
    return parser.parse_args(argv)


def main() -> int | None:
    args = _parse_args()
    results = collect_smoke_check_results(
        twse_stock=args.twse_stock,
        tpex_stock=args.tpex_stock,
        period=args.period,
        interval=args.interval,
    )
    print_results(results)
    try:
        raise_for_failures(results)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
