"""Typed application services for research runs."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from tw_stock_tool.analysis.scanner import ProgressCallback, ScanConfig
from tw_stock_tool.reports.daily_pipeline import DailyPipelineConfig
from tw_stock_tool.research_run.backtest import (
    BacktestStageCallback,
    run_backtest_research,
)
from tw_stock_tool.research_run.daily import run_daily_report_research
from tw_stock_tool.research_run.market_data_adapter import MarketDataLoader
from tw_stock_tool.research_run.models import ResearchRunResult
from tw_stock_tool.research_run.scan import run_scan_research
from tw_stock_tool.utils.config import (
    DEFAULT_AUTO_ADJUST,
    DEFAULT_INTERVAL,
    DEFAULT_PERIOD,
)


def _clean_string(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be an exact str")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be a clean exact string")
    return value


def _path_value(name: str, value: object, *, allow_none: bool = False) -> str | Path | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, (str, Path)):
        raise TypeError(f"{name} must be str or Path")
    if type(value) is str and (not value or value != value.strip()):
        raise ValueError(f"{name} must be a nonblank path")
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _mapping_snapshot(name: str, value: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a Mapping or None")
    return MappingProxyType({key: _freeze(item) for key, item in dict(value).items()})


@dataclass(frozen=True, slots=True)
class SymbolRequest:
    requested_symbol: str
    canonical_symbol: str

    def __post_init__(self) -> None:
        _clean_string("requested_symbol", self.requested_symbol)
        _clean_string("canonical_symbol", self.canonical_symbol)


def _validate_symbols(symbols: object) -> tuple[SymbolRequest, ...]:
    if type(symbols) is not tuple or not symbols:
        raise TypeError("symbols must be a non-empty exact tuple")
    requested: set[str] = set()
    canonical: set[str] = set()
    for index, symbol in enumerate(symbols):
        if type(symbol) is not SymbolRequest:
            raise TypeError(f"symbols[{index}] must be an exact SymbolRequest")
        if symbol.requested_symbol in requested:
            raise ValueError(f"Duplicate requested symbol: {symbol.requested_symbol}")
        if symbol.canonical_symbol in canonical:
            raise ValueError(f"Duplicate canonical symbol: {symbol.canonical_symbol}")
        requested.add(symbol.requested_symbol)
        canonical.add(symbol.canonical_symbol)
    return symbols


def _validate_universe(universe: object) -> str | None:
    return None if universe is None else _clean_string("universe", universe)


@dataclass(frozen=True, slots=True)
class ScanRunRequest:
    symbols: tuple[SymbolRequest, ...]
    universe: str | None
    config: ScanConfig
    output_dir: str | Path
    manifest_path: str | Path | None = None
    sheet_by_signal: bool = False
    log_errors: bool = False

    def __post_init__(self) -> None:
        _validate_symbols(self.symbols)
        _validate_universe(self.universe)
        if not isinstance(self.config, ScanConfig):
            raise TypeError("config must be a ScanConfig")
        _path_value("output_dir", self.output_dir)
        _path_value("manifest_path", self.manifest_path, allow_none=True)
        if type(self.sheet_by_signal) is not bool:
            raise TypeError("sheet_by_signal must be an exact bool")
        if type(self.log_errors) is not bool:
            raise TypeError("log_errors must be an exact bool")


@dataclass(frozen=True, slots=True)
class DailyRunRequest:
    symbols: tuple[SymbolRequest, ...]
    universe: str | None
    config: DailyPipelineConfig
    output_dir: str | Path
    markdown_path: str | Path | None = None
    json_path: str | Path | None = None
    manifest_path: str | Path | None = None
    json_overwrite: bool = False

    def __post_init__(self) -> None:
        _validate_symbols(self.symbols)
        _validate_universe(self.universe)
        if not isinstance(self.config, DailyPipelineConfig):
            raise TypeError("config must be a DailyPipelineConfig")
        for name, value, allow_none in (
            ("output_dir", self.output_dir, False),
            ("markdown_path", self.markdown_path, True),
            ("json_path", self.json_path, True),
            ("manifest_path", self.manifest_path, True),
        ):
            _path_value(name, value, allow_none=allow_none)
        if type(self.json_overwrite) is not bool:
            raise TypeError("json_overwrite must be an exact bool")


@dataclass(frozen=True, slots=True)
class BacktestRunRequest:
    symbol: SymbolRequest
    strategy: str
    output_dir: str | Path
    period: str = DEFAULT_PERIOD
    interval: str = DEFAULT_INTERVAL
    auto_adjust: bool = DEFAULT_AUTO_ADJUST
    force_refresh: bool = False
    strategy_parameters: Mapping[str, Any] | None = None
    backtest_parameters: Mapping[str, Any] | None = None
    markdown_path: str | Path | None = None
    excel_path: str | Path | None = None
    manifest_path: str | Path | None = None

    def __post_init__(self) -> None:
        if type(self.symbol) is not SymbolRequest:
            raise TypeError("symbol must be an exact SymbolRequest")
        for name in ("strategy", "period", "interval"):
            _clean_string(name, getattr(self, name))
        for name in ("auto_adjust", "force_refresh"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be an exact bool")
        object.__setattr__(self, "strategy_parameters", _mapping_snapshot("strategy_parameters", self.strategy_parameters))
        object.__setattr__(self, "backtest_parameters", _mapping_snapshot("backtest_parameters", self.backtest_parameters))
        for name, value, allow_none in (
            ("output_dir", self.output_dir, False),
            ("markdown_path", self.markdown_path, True),
            ("excel_path", self.excel_path, True),
            ("manifest_path", self.manifest_path, True),
        ):
            _path_value(name, value, allow_none=allow_none)


def _symbol_pairs(symbols: tuple[SymbolRequest, ...]) -> tuple[tuple[str, str], ...]:
    return tuple((symbol.requested_symbol, symbol.canonical_symbol) for symbol in symbols)


def run_scan(
    request: ScanRunRequest,
    *,
    progress_callback: ProgressCallback | None = None,
    market_data_loader: MarketDataLoader | None = None,
) -> ResearchRunResult:
    if type(request) is not ScanRunRequest:
        raise TypeError("request must be a ScanRunRequest")
    return run_scan_research(
        _symbol_pairs(request.symbols),
        universe=request.universe,
        config=request.config,
        output_dir=request.output_dir,
        manifest_path=request.manifest_path,
        sheet_by_signal=request.sheet_by_signal,
        log_errors=request.log_errors,
        progress_callback=progress_callback,
        market_data_loader=market_data_loader,
    )


def run_daily(
    request: DailyRunRequest,
    *,
    status_callback: Callable[[str], None] | None = None,
    market_data_loader: MarketDataLoader | None = None,
) -> ResearchRunResult:
    if type(request) is not DailyRunRequest:
        raise TypeError("request must be a DailyRunRequest")
    return run_daily_report_research(
        _symbol_pairs(request.symbols),
        universe=request.universe,
        config=request.config,
        output_dir=request.output_dir,
        markdown_path=request.markdown_path,
        json_path=request.json_path,
        manifest_path=request.manifest_path,
        json_overwrite=request.json_overwrite,
        status_callback=status_callback,
        market_data_loader=market_data_loader,
    )


def run_backtest(
    request: BacktestRunRequest,
    *,
    stage_callback: BacktestStageCallback | None = None,
    market_data_loader: MarketDataLoader | None = None,
) -> ResearchRunResult:
    if type(request) is not BacktestRunRequest:
        raise TypeError("request must be a BacktestRunRequest")
    return run_backtest_research(
        (request.symbol.requested_symbol, request.symbol.canonical_symbol),
        strategy=request.strategy,
        period=request.period,
        interval=request.interval,
        auto_adjust=request.auto_adjust,
        force_refresh=request.force_refresh,
        strategy_parameters=request.strategy_parameters,
        backtest_parameters=request.backtest_parameters,
        output_dir=request.output_dir,
        markdown_path=request.markdown_path,
        excel_path=request.excel_path,
        manifest_path=request.manifest_path,
        stage_callback=stage_callback,
        market_data_loader=market_data_loader,
    )
