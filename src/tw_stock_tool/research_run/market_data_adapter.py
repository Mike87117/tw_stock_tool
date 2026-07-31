"""Legacy market-data orchestration adapter for Research Runs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Callable, TypeAlias

import pandas as pd

from tw_stock_tool.data import data_loader
from tw_stock_tool.data import fallback_orchestration
from tw_stock_tool.research_run.context import MarketDataLoadResult
from tw_stock_tool.research_run.models import DataSourceRecord

MarketDataLoader: TypeAlias = Callable[
    [str, str, str, bool, bool],
    MarketDataLoadResult,
]


def build_legacy_market_data_loader(
    canonical_by_requested: Mapping[str, str],
) -> MarketDataLoader:
    expected_symbols = dict(canonical_by_requested)

    def loader(
        requested_symbol: str,
        period: str,
        interval: str,
        auto_adjust: bool,
        force_refresh: bool,
    ) -> MarketDataLoadResult:
        expected_canonical = expected_symbols[requested_symbol]
        fresh_cache_paths: set[object] = set()
        source_events: list[tuple[str, str]] = []

        def is_cache_fresh(path: object) -> bool:
            result = data_loader._is_cache_fresh(path)  # type: ignore[arg-type]
            if result:
                fresh_cache_paths.add(path)
            return result

        def read_cache(path: object) -> pd.DataFrame:
            try:
                cached_df = data_loader._read_cache(path)  # type: ignore[arg-type]
            except Exception:
                fresh_cache_paths.discard(path)
                raise
            cache_state = "fresh" if path in fresh_cache_paths else "stale"
            fresh_cache_paths.discard(path)
            source_events.append(("cache", cache_state))
            return cached_df

        def download_yfinance(
            symbol: str,
            load_period: str,
            load_interval: str,
            load_auto_adjust: bool,
        ) -> pd.DataFrame:
            df = data_loader._download_yfinance_quiet(
                symbol,
                load_period,
                load_interval,
                load_auto_adjust,
            )
            if not df.empty:
                source_events.append(("yfinance", "live"))
            return df

        def download_official(
            base_stock_id: str,
            suffix: str,
            load_period: str,
            load_interval: str,
        ) -> pd.DataFrame:
            df = data_loader._download_official_stock(
                base_stock_id,
                suffix,
                load_period,
                load_interval,
            )
            source_events.append(("twse" if suffix == ".TW" else "tpex", "live"))
            return df

        try:
            data, actual_canonical = fallback_orchestration.download_tw_stock(
                expected_canonical,
                period=period,
                interval=interval,
                auto_adjust=auto_adjust,
                force_refresh=force_refresh,
                validate_inputs=data_loader._validate_inputs,
                symbol_candidates=data_loader._symbol_candidates,
                build_cache_path=data_loader._cache_path,
                is_cache_fresh=is_cache_fresh,
                read_cache=read_cache,
                prepare_ohlcv=data_loader._prepare_ohlcv,
                download_yfinance=download_yfinance,
                write_cache=data_loader._write_cache,
                download_official=download_official,
                get_cache_age_days=data_loader._get_cache_age_days,
                format_no_data_error=data_loader._format_no_data_error,
                default_auto_adjust=data_loader.DEFAULT_AUTO_ADJUST,
                max_stale_cache_days=data_loader.MAX_STALE_CACHE_DAYS,
            )
        except Exception as exc:
            message = str(exc).strip() or type(exc).__name__
            record = DataSourceRecord(
                canonical_symbol=expected_canonical,
                requested_symbol=requested_symbol,
                provider="data_loader",
                period=period,
                interval=interval,
                auto_adjust=auto_adjust,
                source_kind="live",
                cache_state="not_applicable",
                success=False,
                error=message,
            )
            return MarketDataLoadResult(data=None, source_record=record, error=exc)

        provider, source_kind = source_events[-1] if source_events else ("data_loader", "live")
        cache_state = source_kind if source_kind in ("fresh", "stale") else "not_applicable"
        if provider == "cache":
            source_kind = "cache"
        record = DataSourceRecord(
            canonical_symbol=actual_canonical,
            requested_symbol=requested_symbol,
            provider=provider,
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            source_kind=source_kind,
            cache_state=cache_state,
            success=True,
            error=None,
        )
        return MarketDataLoadResult(data=data, source_record=record)

    return loader