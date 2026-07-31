from pathlib import Path
from typing import Any

import pandas as pd

from tw_stock_tool.utils.config import (
    CACHE_DIR,
    DEFAULT_AUTO_ADJUST,
    MAX_STALE_CACHE_DAYS,
    VALID_INTERVALS,
    VALID_PERIODS,
)
from tw_stock_tool.data import cache_runtime as _cache_runtime
from tw_stock_tool.data import fallback_orchestration as _fallback_orchestration
from tw_stock_tool.data import ohlcv_normalization as _ohlcv_normalization
from tw_stock_tool.data import official_parsing as _official_parsing
from tw_stock_tool.data.providers import (
    tpex_provider,
    twse_provider,
    yfinance_provider,
)

# Compatibility aliases for callers that historically patched provider modules
# through data_loader. New owner tests patch the provider modules directly.
requests = twse_provider.requests
yf = yfinance_provider.yf


class DataLoaderError(Exception):
    pass


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
    return _cache_runtime._cache_path(
        symbol,
        period,
        interval,
        auto_adjust,
        cache_dir=CACHE_DIR,
    )


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
        normalize_columns=_ohlcv_normalization.normalize_columns,
        error_type=DataLoaderError,
    )


def _period_start(period: str) -> pd.Timestamp:
    return _official_parsing.period_start(period)


def _month_starts(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    return _official_parsing.month_starts(start, end)


def _parse_roc_date(value: str) -> pd.Timestamp:
    return _official_parsing.parse_roc_date(value)


def _parse_tpex_date(value: str, month: pd.Timestamp | None = None) -> pd.Timestamp:
    return _official_parsing.parse_tpex_date(
        value,
        month,
        parse_roc_date=_parse_roc_date,
    )


def _to_float(value: Any) -> float:
    return _official_parsing.to_float(value)


def _to_int(value: Any) -> int:
    return _official_parsing.to_int(
        value,
        to_float=_to_float,
    )


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


def _download_official_stock(
    stock_id: str,
    suffix: str,
    period: str,
    interval: str,
) -> pd.DataFrame:
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
    return _fallback_orchestration.download_tw_stock(
        stock_id,
        period,
        interval,
        auto_adjust,
        force_refresh,
        verbose,
        validate_inputs=_validate_inputs,
        symbol_candidates=_symbol_candidates,
        build_cache_path=_cache_path,
        is_cache_fresh=_is_cache_fresh,
        read_cache=_read_cache,
        prepare_ohlcv=_prepare_ohlcv,
        download_yfinance=_download_yfinance_quiet,
        write_cache=_write_cache,
        download_official=_download_official_stock,
        get_cache_age_days=_get_cache_age_days,
        format_no_data_error=_format_no_data_error,
        default_auto_adjust=DEFAULT_AUTO_ADJUST,
        max_stale_cache_days=MAX_STALE_CACHE_DAYS,
    )
