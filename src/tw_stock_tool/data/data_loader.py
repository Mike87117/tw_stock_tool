from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yfinance as yf

from tw_stock_tool.utils.config import CACHE_DIR, DEFAULT_AUTO_ADJUST, VALID_INTERVALS, VALID_PERIODS, MAX_STALE_CACHE_DAYS
from tw_stock_tool.data import cache_runtime as _cache_runtime
from tw_stock_tool.data import ohlcv_normalization as _ohlcv_normalization
from tw_stock_tool.data.providers import (
    tpex_provider,
    twse_provider,
    yfinance_provider,
)


class DataLoaderError(Exception):
    pass


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    return _ohlcv_normalization.normalize_columns(df)


def _validate_inputs(stock_id: str, period: str, interval: str) -> None:
    if not stock_id or not stock_id.strip():
        raise DataLoaderError("Stock id cannot be blank.")

    base = stock_id.strip().upper().replace(".TWO", "").replace(".TW", "")
    if not any(c.isdigit() for c in base):
        raise DataLoaderError(f"Invalid stock ID format: {stock_id}")

    if period not in VALID_PERIODS:
        raise DataLoaderError(f"Invalid period: {period}.")
    if interval not in VALID_INTERVALS:
        raise DataLoaderError(f"Invalid interval: {interval}.")


def _cache_path(symbol: str, period: str, interval: str, auto_adjust: bool) -> Path:
    return _cache_runtime._cache_path(symbol, period, interval, auto_adjust, cache_dir=CACHE_DIR)


def _is_cache_fresh(path: Path) -> bool:
    return _cache_runtime._is_cache_fresh(path)


def _get_cache_age_days(path: Path) -> float:
    return _cache_runtime._get_cache_age_days(path)


def _read_cache(path: Path) -> pd.DataFrame:
    return _cache_runtime._read_cache(path)


def _write_cache(df: pd.DataFrame, path: Path) -> None:
    _cache_runtime._write_cache(df, path)
def _prepare_ohlcv(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    return _ohlcv_normalization.prepare_ohlcv(
        df,
        symbol,
        normalize_columns=_normalize_columns,
        error_type=DataLoaderError,
    )


def _period_start(period: str) -> pd.Timestamp:
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
        return pd.Timestamp(year=today.year, month=1, day=1)
    return today - pd.DateOffset(months=months.get(period, 12))


def _month_starts(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    cursor = pd.Timestamp(year=start.year, month=start.month, day=1)
    final = pd.Timestamp(year=end.year, month=end.month, day=1)
    months = []
    while cursor <= final:
        months.append(cursor)
        cursor += pd.DateOffset(months=1)
    return months


def _parse_roc_date(value: str) -> pd.Timestamp:
    parts = value.strip().split("/")
    if len(parts) != 3:
        raise ValueError(f"Invalid ROC date: {value}")
    year, month, day = (int(part.strip()) for part in parts)
    return pd.Timestamp(year + 1911, month, day)


def _parse_tpex_date(value: str, month: pd.Timestamp | None = None) -> pd.Timestamp:
    text = str(value).strip()
    if "/" in text:
        parts = text.split("/")
        if len(parts) == 3:
            return _parse_roc_date(text)
        if len(parts) == 2 and month is not None:
            return pd.Timestamp(month.year, int(parts[0]), int(parts[1]))
    if text.isdigit() and len(text) == 7:
        return pd.Timestamp(int(text[:3]) + 1911, int(text[3:5]), int(text[5:7]))
    if text.isdigit() and len(text) == 8:
        return pd.Timestamp(int(text[:4]), int(text[4:6]), int(text[6:8]))
    raise ValueError(f"Invalid TPEX date: {value}")


def _to_float(value: Any) -> float:
    text = str(value).replace(",", "").replace("--", "").strip()
    if not text:
        return float("nan")
    return float(text)


def _to_int(value: Any) -> int:
    return int(_to_float(value))


def _finalize_official_rows(
    rows: list[dict[str, Any]],
    stock_id: str,
    suffix: str,
    start: pd.Timestamp,
    period: str,
) -> pd.DataFrame:
    return _ohlcv_normalization.finalize_official_rows(
        rows,
        stock_id,
        suffix,
        start,
        period,
        prepare_ohlcv=_prepare_ohlcv,
        error_type=DataLoaderError,
    )


def _download_twse_stock(stock_id: str, period: str, interval: str) -> pd.DataFrame:
    return twse_provider.download_twse_stock(
        stock_id,
        period,
        interval,
        period_start=_period_start,
        month_starts=_month_starts,
        parse_roc_date=_parse_roc_date,
        to_float=_to_float,
        to_int=_to_int,
        finalize_official_rows=_finalize_official_rows,
        error_type=DataLoaderError,
    )


def _download_tpex_stock(stock_id: str, period: str, interval: str) -> pd.DataFrame:
    return tpex_provider.download_tpex_stock(
        stock_id,
        period,
        interval,
        period_start=_period_start,
        month_starts=_month_starts,
        parse_tpex_date=_parse_tpex_date,
        to_float=_to_float,
        to_int=_to_int,
        finalize_official_rows=_finalize_official_rows,
        download_latest_quote=_download_tpex_latest_quote,
        error_type=DataLoaderError,
    )


def _download_tpex_latest_quote(
    stock_id: str,
    period: str,
    start: pd.Timestamp,
) -> pd.DataFrame:
    return tpex_provider.download_tpex_latest_quote(
        stock_id,
        period,
        start,
        parse_tpex_date=_parse_tpex_date,
        to_float=_to_float,
        to_int=_to_int,
        finalize_official_rows=_finalize_official_rows,
        error_type=DataLoaderError,
    )


def _download_official_stock(stock_id: str, suffix: str, period: str, interval: str) -> pd.DataFrame:
    if suffix == ".TW":
        return _download_twse_stock(stock_id, period, interval)
    if suffix == ".TWO":
        return _download_tpex_stock(stock_id, period, interval)
    raise DataLoaderError(f"Unsupported official fallback suffix: {suffix}")


def _symbol_candidates(stock_id: str) -> list[tuple[str, str, str]]:
    normalized = stock_id.strip().upper()
    if normalized.endswith(".TWO"):
        base = normalized[:-4]
        return [(normalized, base, ".TWO")]
    if normalized.endswith(".TW"):
        base = normalized[:-3]
        return [(normalized, base, ".TW")]
    return [
        (f"{normalized}.TW", normalized, ".TW"),
        (f"{normalized}.TWO", normalized, ".TWO"),
    ]


def _download_yfinance_quiet(
    symbol: str,
    period: str,
    interval: str,
    auto_adjust: bool,
) -> pd.DataFrame:
    return yfinance_provider.download_yfinance_quiet(
        symbol,
        period,
        interval,
        auto_adjust,
    )


def _format_no_data_error(
    original_stock_id: str,
    tried_symbols: list[str],
    errors: list[str],
) -> DataLoaderError:
    details = " | ".join(errors)
    message = (
        f"No price data found for {original_stock_id}. "
        f"Tried: {', '.join(tried_symbols)}. "
        "The stock may be delisted, the symbol may be wrong, "
        "or the data source may be temporarily unavailable or rate-limited."
    )
    if details:
        message = f"{message} Attempts: {details}"
    return DataLoaderError(message)


def download_tw_stock(
    stock_id: str,
    period: str = "1y",
    interval: str = "1d",
    auto_adjust: bool | None = None,
    force_refresh: bool = False,
    verbose: bool = False,
) -> tuple[pd.DataFrame, str]:
    _validate_inputs(stock_id, period, interval)
    original_stock_id = stock_id.strip()
    if auto_adjust is None:
        auto_adjust = DEFAULT_AUTO_ADJUST

    candidates = _symbol_candidates(original_stock_id)
    tried_symbols = [symbol for symbol, _, _ in candidates]
    errors: list[str] = []

    for symbol, _, _ in candidates:
        cache_path = _cache_path(symbol, period, interval, auto_adjust)
        if not force_refresh and _is_cache_fresh(cache_path):
            try:
                cached_df = _read_cache(cache_path)
                if verbose:
                    print(f"{symbol}: From cache")
                return _prepare_ohlcv(cached_df, symbol), symbol
            except Exception as exc:
                errors.append(f"{symbol} cache read failed: {exc}")

        try:
            df = _download_yfinance_quiet(symbol, period, interval, auto_adjust)
            if not df.empty:
                df = _prepare_ohlcv(df, symbol)
                try:
                    _write_cache(df, cache_path)
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
            cache_path = _cache_path(symbol, period, interval, auto_adjust)
            try:
                df = _download_official_stock(base_stock_id, suffix, period, interval)
                try:
                    _write_cache(df, cache_path)
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
            cache_path = _cache_path(symbol, period, interval, auto_adjust)
            if cache_path.exists():
                try:
                    age_days = _get_cache_age_days(cache_path)
                except Exception as exc:
                    errors.append(f"{symbol} stale cache mtime read failed: {exc}")
                    continue

                if age_days > MAX_STALE_CACHE_DAYS:
                    errors.append(f"{symbol} stale cache rejected: {age_days:.1f} days old (exceeds {MAX_STALE_CACHE_DAYS} day limit)")
                    continue

                try:
                    cached_df = _read_cache(cache_path)
                    import sys
                    print(f"[WARNING] All live data sources failed for {symbol}. Using {age_days:.1f}-day-old stale cached data from {cache_path} (max stale age: {MAX_STALE_CACHE_DAYS} days).", file=sys.stderr)
                    if verbose:
                        print(f"{symbol}: From stale cache")
                    return _prepare_ohlcv(cached_df, symbol), symbol
                except Exception as exc:
                    errors.append(f"{symbol} stale cache read failed: {exc}")

    raise _format_no_data_error(original_stock_id, tried_symbols, errors)

