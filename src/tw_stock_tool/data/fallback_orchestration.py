"""Fallback orchestration for Taiwan stock price loading."""

from collections.abc import Callable
import sys
from typing import Any

import pandas as pd


def download_tw_stock(
    stock_id: str,
    period: str = "1y",
    interval: str = "1d",
    auto_adjust: bool | None = None,
    force_refresh: bool = False,
    verbose: bool = False,
    *,
    validate_inputs: Callable[
        [str, str, str],
        None,
    ],
    symbol_candidates: Callable[
        [str],
        list[tuple[str, str, str]],
    ],
    build_cache_path: Callable[
        [str, str, str, bool],
        Any,
    ],
    is_cache_fresh: Callable[
        [Any],
        bool,
    ],
    read_cache: Callable[
        [Any],
        pd.DataFrame,
    ],
    prepare_ohlcv: Callable[
        [pd.DataFrame, str],
        pd.DataFrame,
    ],
    download_yfinance: Callable[
        [str, str, str, bool],
        pd.DataFrame,
    ],
    write_cache: Callable[
        [pd.DataFrame, Any],
        None,
    ],
    download_official: Callable[
        [str, str, str, str],
        pd.DataFrame,
    ],
    get_cache_age_days: Callable[
        [Any],
        float,
    ],
    format_no_data_error: Callable[
        [str, list[str], list[str]],
        Exception,
    ],
    default_auto_adjust: bool,
    max_stale_cache_days: int,
) -> tuple[pd.DataFrame, str]:
    validate_inputs(
        stock_id,
        period,
        interval,
    )
    original_stock_id = stock_id.strip()
    if auto_adjust is None:
        auto_adjust = default_auto_adjust

    candidates = symbol_candidates(original_stock_id)
    tried_symbols = [symbol for symbol, _, _ in candidates]
    errors: list[str] = []

    for symbol, _, _ in candidates:
        path = build_cache_path(
            symbol,
            period,
            interval,
            auto_adjust,
        )
        if not force_refresh and is_cache_fresh(path):
            try:
                cached_df = read_cache(path)
                if verbose:
                    print(f"{symbol}: From cache")
                return prepare_ohlcv(cached_df, symbol), symbol
            except Exception as exc:
                errors.append(f"{symbol} cache read failed: {exc}")

        try:
            df = download_yfinance(
                symbol,
                period,
                interval,
                auto_adjust,
            )
            if not df.empty:
                df = prepare_ohlcv(df, symbol)
                try:
                    write_cache(df, path)
                except Exception as exc:
                    errors.append(f"{symbol} cache write failed: {exc}")
                if verbose:
                    print(f"{symbol}: Downloaded")
                return df, symbol
            errors.append(f"{symbol} has no data")
        except Exception as exc:
            errors.append(f"{symbol} yfinance failed: {exc}")

    if not auto_adjust:
        for symbol, base_stock_id, suffix in candidates:
            path = build_cache_path(
                symbol,
                period,
                interval,
                auto_adjust,
            )
            try:
                df = download_official(
                    base_stock_id,
                    suffix,
                    period,
                    interval,
                )
                try:
                    write_cache(df, path)
                except Exception as exc:
                    errors.append(f"{symbol} cache write failed: {exc}")
                if verbose:
                    source = "TWSE" if suffix == ".TW" else "TPEX"
                    print(f"{symbol}: Downloaded from {source} fallback")
                return df, symbol
            except Exception as exc:
                source = "TWSE" if suffix == ".TW" else "TPEX"
                errors.append(f"{symbol} {source} fallback failed: {exc}")

    if not force_refresh:
        for symbol, _, _ in candidates:
            path = build_cache_path(
                symbol,
                period,
                interval,
                auto_adjust,
            )
            if path.exists():
                try:
                    age_days = get_cache_age_days(path)
                except Exception as exc:
                    errors.append(f"{symbol} stale cache mtime read failed: {exc}")
                    continue

                if age_days > max_stale_cache_days:
                    errors.append(
                        f"{symbol} stale cache rejected: {age_days:.1f} days old (exceeds {max_stale_cache_days} day limit)"
                    )
                    continue

                try:
                    cached_df = read_cache(path)
                    print(
                        f"[WARNING] All live data sources failed for {symbol}. "
                        f"Using {age_days:.1f}-day-old stale cached data from {path} "
                        f"(max stale age: {max_stale_cache_days} days).",
                        file=sys.stderr,
                    )
                    if verbose:
                        print(f"{symbol}: From stale cache")
                    return prepare_ohlcv(cached_df, symbol), symbol
                except Exception as exc:
                    errors.append(f"{symbol} stale cache read failed: {exc}")

    raise format_no_data_error(
        original_stock_id,
        tried_symbols,
        errors,
    )
