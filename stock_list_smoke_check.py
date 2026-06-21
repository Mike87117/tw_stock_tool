"""Manual smoke check for official Taiwan stock-list data sources.

This tool intentionally uses live TWSE / TPEx APIs and is not part of the
normal unittest or CI path. Run it manually when you want to confirm official
stock-list sources still work in the current network environment.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import pandas as pd

import stock_list_updater

EXPECTED_STOCKS = {"2330", "2317", "8069"}
DEFAULT_MIN_TWSE = 100
DEFAULT_MIN_TPEX = 100
DEFAULT_MIN_ALL = 500


class StockListSmokeCheckError(Exception):
    """Raised when the official stock-list smoke check fails."""


def _stock_set(df: pd.DataFrame) -> set[str]:
    if df.empty or "Stock" not in df.columns:
        return set()
    return set(df["Stock"].astype(str).str.strip())


def run_smoke_check(
    min_twse: int = DEFAULT_MIN_TWSE,
    min_tpex: int = DEFAULT_MIN_TPEX,
    min_all: int = DEFAULT_MIN_ALL,
    expected_stocks: set[str] | None = None,
) -> dict[str, Any]:
    """Fetch live official stock lists, normalize them, and validate counts."""
    expected = expected_stocks or EXPECTED_STOCKS
    twse_raw = stock_list_updater.fetch_twse_stock_list()
    tpex_raw = stock_list_updater.fetch_tpex_stock_list()
    twse = stock_list_updater.normalize_stock_list(twse_raw)
    tpex = stock_list_updater.normalize_stock_list(tpex_raw)
    combined = stock_list_updater.normalize_stock_list(pd.concat([twse_raw, tpex_raw], ignore_index=True))

    missing = sorted(expected - _stock_set(combined))
    errors: list[str] = []
    if len(twse) < min_twse:
        errors.append(f"TWSE count too low: {len(twse)} < {min_twse}")
    if len(tpex) < min_tpex:
        errors.append(f"TPEx count too low: {len(tpex)} < {min_tpex}")
    if len(combined) < min_all:
        errors.append(f"All count too low: {len(combined)} < {min_all}")
    if missing:
        errors.append(f"Missing expected stocks: {', '.join(missing)}")

    result = {
        "twse_count": len(twse),
        "tpex_count": len(tpex),
        "all_count": len(combined),
        "missing_expected_stocks": missing,
        "status": "FAIL" if errors else "PASS",
        "errors": errors,
    }
    if errors:
        raise StockListSmokeCheckError("; ".join(errors))
    return result


def print_result(result: dict[str, Any]) -> None:
    """Print a compact smoke-check report."""
    print("=================================")
    print("Stock List Smoke Check")
    print("=================================")
    print(f"TWSE count: {result['twse_count']}")
    print(f"TPEx count: {result['tpex_count']}")
    print(f"All count: {result['all_count']}")
    missing = result.get("missing_expected_stocks") or []
    print(f"Missing expected stocks: {', '.join(missing) if missing else 'None'}")
    print(f"Status: {result['status']}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke check official Taiwan stock-list sources")
    parser.add_argument("--min-twse", type=int, default=DEFAULT_MIN_TWSE)
    parser.add_argument("--min-tpex", type=int, default=DEFAULT_MIN_TPEX)
    parser.add_argument("--min-all", type=int, default=DEFAULT_MIN_ALL)
    return parser.parse_args(argv)


def main() -> None:
    args = _parse_args()
    try:
        result = run_smoke_check(
            min_twse=args.min_twse,
            min_tpex=args.min_tpex,
            min_all=args.min_all,
        )
        print_result(result)
    except Exception as exc:
        print("=================================")
        print("Stock List Smoke Check")
        print("=================================")
        print(f"Status: FAIL")
        print(f"Error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
