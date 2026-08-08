"""Application orchestration for deterministic universe-level OOS evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any
from uuid import UUID

import pandas as pd

from tw_stock_tool.application.workspace_execution import WorkspaceRunLifecycle
from tw_stock_tool.artifacts import WorkspacePathError
from tw_stock_tool.backtesting.metrics import calculate_buy_hold_return
from tw_stock_tool.backtesting.walk_forward import (
    SORTABLE_COLUMNS,
    parameter_grid,
    run_strategy_backtest,
    sort_train_metric,
    split_windows,
)
from tw_stock_tool.qualification.serialization import (
    QualificationSerializationError,
    deserialize_strategy_qualification_result,
    serialize_strategy_qualification_result,
)
from tw_stock_tool.qualification import (
    STRATEGY_QUALIFICATION_ARTIFACT_TYPE,
    STRATEGY_QUALIFICATION_SCHEMA_VERSION,
    TAIWAN_EQUITY_DAILY_V1,
    QualificationMetricSet,
    QualificationPolicy,
    StrategyDescriptor,
    StrategyQualificationRequest,
    StrategyQualificationResult,
    evaluate_strategy_qualification,
    export_strategy_qualification_json,
)
from tw_stock_tool.research_run.models import (
    RUN_MANIFEST_SCHEMA_VERSION,
    ArtifactReference,
    RunConfig,
    RunManifest,
)
from tw_stock_tool.utils.config import (DEFAULT_INTERVAL, DEFAULT_PERIOD, FEE_RATE, INITIAL_CAPITAL, TAX_RATE, VALID_INTERVALS, VALID_PERIODS)


_PARAMETER_KEYS = {
    "ma_cross": frozenset(("short_window", "long_window")),
    "rsi": frozenset(("buy_below", "sell_above")),
    "score": frozenset(("buy_score", "sell_score")),
}

CONCENTRATION_RULE = MappingProxyType({
    "version": "1.0",
    "basis": "sum_abs_window_return_pct",
})

PARAMETER_STABILITY_RULE = MappingProxyType({
    "version": "1.0",
    "research_only": True,
    "minimum_successful_neighbors": 1,
    "minimum_neighbor_coverage": 0.75,
    "minimum_return_retention": 0.50,
    "maximum_return_dispersion_pct": 25.0,
    "maximum_neighbor_outperformance_ratio": 0.25,
    "minimum_selected_return_pct": 0.0,
})


def _stability_rule_dict() -> dict[str, Any]:
    return dict(PARAMETER_STABILITY_RULE)


def _freeze_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_payload(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_payload(item) for item in value)
    return value


def _validate_stability_rule(value: Any, path: str) -> Mapping[str, Any]:
    expected = {
        "version": str, "research_only": bool, "minimum_successful_neighbors": int,
        "minimum_neighbor_coverage": float, "minimum_return_retention": float,
        "maximum_return_dispersion_pct": float, "maximum_neighbor_outperformance_ratio": float,
        "minimum_selected_return_pct": float,
    }
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise ValueError(f"{path} must contain the exact stability rule fields")
    for key, expected_type in expected.items():
        item = value[key]
        if expected_type is bool:
            valid = type(item) is bool
        elif expected_type is int:
            valid = type(item) is int
        elif expected_type is float:
            valid = type(item) is float and math.isfinite(item)
        else:
            valid = type(item) is expected_type
        if not valid:
            raise ValueError(f"{path}.{key} has invalid exact type")
    if value != PARAMETER_STABILITY_RULE:
        raise ValueError(f"{path} is not the canonical versioned rule")
    return MappingProxyType(dict(sorted(value.items())))


def _validate_concentration_rule(value: Any, path: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping) or set(value) != set(CONCENTRATION_RULE):
        raise ValueError(f"{path} must contain the exact concentration rule fields")
    if type(value["version"]) is not str or type(value["basis"]) is not str or not value["version"].strip() or not value["basis"].strip():
        raise ValueError(f"{path} has invalid exact types")
    if value != CONCENTRATION_RULE:
        raise ValueError(f"{path} is not the canonical versioned rule")
    return MappingProxyType(dict(sorted(value.items())))


def _canonical_timestamp(value: Any, path: str) -> str:
    if type(value) is not str or value != value.strip() or len(value) != 20 or not value.endswith("Z"):
        raise ValueError(f"{path} must be canonical UTC timestamp YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"{path} must be canonical UTC timestamp YYYY-MM-DDTHH:MM:SSZ") from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parameter_mapping(strategy: str, value: Any, path: str) -> Mapping[str, int]:
    if not isinstance(value, Mapping) or isinstance(value, (str, bytes, list, tuple)):
        raise ValueError(f"{path} must be a Mapping")
    if set(value) != _PARAMETER_KEYS[strategy]:
        raise ValueError(f"{path} keys do not match strategy")
    clean: dict[str, int] = {}
    for key in sorted(value):
        if type(key) is not str or not key.strip() or key != key.strip() or type(value[key]) is not int:
            raise ValueError(f"{path} keys and values must be exact strings and integers")
        if abs(value[key]) > 2**63 - 1:
            raise ValueError(f"{path} contains an integer overflow")
        clean[key] = value[key]
    return MappingProxyType(clean)


class UniverseEvidenceSerializationError(ValueError):
    """Raised when universe OOS evidence violates schema 1.0."""


class UniverseQualificationError(RuntimeError):
    """Raised when a universe qualification cannot be evaluated or published."""


def _source_tree_tool_version() -> str:
    pyproject = Path(__file__).resolve().parents[2].parent / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError as exc:
        raise UniverseQualificationError("Unable to determine tw-stock-tool package version") from exc
    match = re.search(r'(?ms)^\[project\].*?^version\s*=\s*["\']([^"\']+)[^"\']*["\']', text)
    if match is None or not match.group(1).strip():
        raise UniverseQualificationError("Unable to determine tw-stock-tool package version")
    return match.group(1)


def _tool_version() -> str:
    try:
        return importlib.metadata.version("tw-stock-tool")
    except importlib.metadata.PackageNotFoundError:
        return _source_tree_tool_version()


def _error_message(exc: Exception) -> str:
    return str(exc).strip() or type(exc).__name__


@dataclass(frozen=True, slots=True)
class BenchmarkDescriptor:
    scope: str
    symbol: str
    rows: int
    index_start: str | None
    index_end: str | None
    close_sha256: str

    def __post_init__(self) -> None:
        if type(self.scope) is not str or self.scope not in ("none", "shared", "per_symbol"):
            raise ValueError("benchmark scope is invalid")
        if type(self.symbol) is not str or not self.symbol.strip() or self.symbol != self.symbol.strip():
            raise ValueError("benchmark symbol must be a clean string")
        if type(self.rows) is not int or self.rows < 0 or self.rows > 2**63 - 1:
            raise ValueError("benchmark rows must be an exact non-negative int")
        if self.index_start is not None:
            _canonical_timestamp(self.index_start, "benchmark index_start")
        if self.index_end is not None:
            _canonical_timestamp(self.index_end, "benchmark index_end")
        if (self.index_start is None) != (self.index_end is None):
            raise ValueError("benchmark index range must be complete")
        if self.index_start is not None and datetime.strptime(self.index_start, "%Y-%m-%dT%H:%M:%SZ") > datetime.strptime(self.index_end, "%Y-%m-%dT%H:%M:%SZ"):
            raise ValueError("benchmark index range must be ordered")
        if type(self.close_sha256) is not str or not self.close_sha256.strip() or self.close_sha256 != self.close_sha256.strip():
            raise ValueError("benchmark close identity must be a clean string")
        if self.scope == "none" and (self.rows != 0 or self.index_start is not None or self.index_end is not None or self.close_sha256 != "none"):
            raise ValueError("empty benchmark descriptor is inconsistent")
        if self.scope != "none" and self.rows == 0:
            raise ValueError("available benchmark descriptor requires rows")

    def to_payload(self) -> dict[str, Any]:
        return {
            "scope": self.scope, "symbol": self.symbol, "rows": self.rows,
            "index_start": self.index_start, "index_end": self.index_end, "close_sha256": self.close_sha256,
        }


@dataclass(frozen=True, slots=True)
class UniverseResolvedConfiguration:
    strategy: str
    parameter_grid: tuple[Mapping[str, int], ...]
    sort_by: str
    train_days: int
    test_days: int
    step_days: int
    period: str
    interval: str
    auto_adjust: bool
    initial_capital: float
    fee_rate: float
    tax_rate: float
    stress_fee_rate: float
    stress_tax_rate: float
    position_size: float
    stop_loss_pct: float | None
    take_profit_pct: float | None
    max_hold_days: int | None
    benchmark_descriptors: tuple[BenchmarkDescriptor, ...]
    source_run_ids: tuple[str, ...]
    parameter_stability_rule: Mapping[str, Any]
    concentration_rule: Mapping[str, str]

    def __post_init__(self) -> None:
        if type(self.strategy) is not str or self.strategy not in _PARAMETER_KEYS:
            raise ValueError("resolved strategy is invalid")
        if type(self.parameter_grid) is not tuple or not self.parameter_grid:
            raise ValueError("parameter_grid must be a non-empty exact tuple")
        normalized_grid = tuple(_parameter_mapping(self.strategy, item, f"parameter_grid[{index}]") for index, item in enumerate(self.parameter_grid))
        if tuple(sorted(tuple(item.items()) for item in normalized_grid)) != tuple(tuple(item.items()) for item in normalized_grid):
            raise ValueError("parameter_grid must be canonically ordered")
        if len({tuple(item.items()) for item in normalized_grid}) != len(normalized_grid):
            raise ValueError("parameter_grid must be unique")
        object.__setattr__(self, "parameter_grid", normalized_grid)
        if type(self.sort_by) is not str or not self.sort_by.strip():
            raise ValueError("resolved sort_by is invalid")
        for name, value in (("train_days", self.train_days), ("test_days", self.test_days), ("step_days", self.step_days)):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive exact int")
        if self.step_days < self.test_days:
            raise ValueError("step_days must be greater than or equal to test_days")
        for name, value in (("period", self.period), ("interval", self.interval)):
            if type(value) is not str or not value.strip():
                raise ValueError(f"{name} must be a clean string")
        if self.period not in VALID_PERIODS or self.interval not in VALID_INTERVALS:
            raise ValueError("resolved period or interval is not supported")
        if self.sort_by not in SORTABLE_COLUMNS:
            raise ValueError("resolved sort_by is not supported")
        if type(self.auto_adjust) is not bool:
            raise ValueError("auto_adjust must be an exact bool")
        for name, value in (("initial_capital", self.initial_capital), ("fee_rate", self.fee_rate), ("tax_rate", self.tax_rate), ("stress_fee_rate", self.stress_fee_rate), ("stress_tax_rate", self.stress_tax_rate), ("position_size", self.position_size)):
            if type(value) not in (int, float) or not math.isfinite(float(value)):
                raise ValueError(f"{name} must be an exact finite number")
        if self.initial_capital <= 0 or self.fee_rate < 0 or self.tax_rate < 0 or self.stress_fee_rate < self.fee_rate or self.stress_tax_rate < self.tax_rate or self.position_size <= 0 or self.position_size > 1:
            raise ValueError("resolved costs/capital/position values are invalid")
        if self.stress_fee_rate == self.fee_rate and self.stress_tax_rate == self.tax_rate:
            raise ValueError("resolved stress costs must strictly exceed at least one base cost")
        for name, value in (("stop_loss_pct", self.stop_loss_pct), ("take_profit_pct", self.take_profit_pct)):
            if value is not None and (type(value) not in (int, float) or not math.isfinite(float(value)) or value <= 0):
                raise ValueError(f"{name} must be finite and positive or None")
        if self.max_hold_days is not None and (type(self.max_hold_days) is not int or self.max_hold_days <= 0):
            raise ValueError("max_hold_days must be positive exact int or None")
        if type(self.benchmark_descriptors) is not tuple or any(not isinstance(item, BenchmarkDescriptor) for item in self.benchmark_descriptors):
            raise ValueError("benchmark_descriptors must be an exact tuple")
        descriptor_keys = tuple((item.scope, item.symbol) for item in self.benchmark_descriptors)
        if descriptor_keys != tuple(sorted(descriptor_keys)) or len(set(descriptor_keys)) != len(descriptor_keys):
            raise ValueError("benchmark_descriptors must be unique and canonically ordered")
        if type(self.source_run_ids) is not tuple or any(type(item) is not str or not item.strip() or item != item.strip() for item in self.source_run_ids):
            raise ValueError("source_run_ids must be an exact clean tuple")
        if tuple(sorted(self.source_run_ids)) != self.source_run_ids or len(set(self.source_run_ids)) != len(self.source_run_ids):
            raise ValueError("source_run_ids must be canonical and unique")
        for item in self.source_run_ids:
            parsed = UUID(item)
            if parsed.version != 4 or str(parsed) != item:
                raise ValueError("source_run_ids must contain canonical UUID v4 values")
        object.__setattr__(self, "parameter_stability_rule", _validate_stability_rule(self.parameter_stability_rule, "parameter_stability_rule"))
        object.__setattr__(self, "concentration_rule", _validate_concentration_rule(self.concentration_rule, "concentration_rule"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy, "parameter_grid": [dict(item) for item in self.parameter_grid], "sort_by": self.sort_by,
            "train_days": self.train_days, "test_days": self.test_days, "step_days": self.step_days, "period": self.period, "interval": self.interval, "auto_adjust": self.auto_adjust,
            "initial_capital": self.initial_capital, "fee_rate": self.fee_rate, "tax_rate": self.tax_rate, "stress_fee_rate": self.stress_fee_rate, "stress_tax_rate": self.stress_tax_rate,
            "position_size": self.position_size, "stop_loss_pct": self.stop_loss_pct, "take_profit_pct": self.take_profit_pct, "max_hold_days": self.max_hold_days,
            "benchmark_descriptors": [item.to_payload() for item in self.benchmark_descriptors], "source_run_ids": list(self.source_run_ids),
            "parameter_stability_rule": dict(self.parameter_stability_rule), "concentration_rule": dict(self.concentration_rule),
        }


@dataclass(frozen=True, slots=True)
class WindowEvidence:
    symbol: str
    window: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    strategy: str
    parameters: Mapping[str, int] | None
    train_return_pct: float | None
    test_return_pct: float | None
    benchmark_return_pct: float | None
    stressed_return_pct: float | None
    completed_trades: int
    oos_observations: int
    max_drawdown_pct: float | None
    valid: bool
    error_code: str | None = None
    error: str | None = None
    benchmark_available: bool = False
    benchmark_error: str | None = None
    neighborhood_parameters: tuple[Mapping[str, int], ...] = ()
    neighborhood_returns_pct: tuple[float | None, ...] = ()
    neighborhood_errors: tuple[str | None, ...] = ()
    parameter_stable: bool = False

    def __post_init__(self) -> None:
        for name, value in (("symbol", self.symbol), ("strategy", self.strategy)):
            if type(value) is not str or not value.strip() or value != value.strip():
                raise ValueError(f"{name} must be a clean string")
        if self.strategy not in _PARAMETER_KEYS:
            raise ValueError("strategy must be supported")
        timestamps = tuple(_canonical_timestamp(value, name) for name, value in (("train_start", self.train_start), ("train_end", self.train_end), ("test_start", self.test_start), ("test_end", self.test_end)))
        train_start, train_end, test_start, test_end = (datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ") for value in timestamps)
        if not (train_start <= train_end < test_start <= test_end):
            raise ValueError("window range must satisfy train_start <= train_end < test_start <= test_end")
        for name, value in zip(("train_start", "train_end", "test_start", "test_end"), timestamps):
            object.__setattr__(self, name, value)
        if type(self.window) is not int or self.window <= 0 or self.window > 2**63 - 1:
            raise ValueError("window must be a positive bounded exact int")
        for name, value in (("completed_trades", self.completed_trades), ("oos_observations", self.oos_observations)):
            if type(value) is not int or value < 0 or value > 2**63 - 1:
                raise ValueError(f"{name} must be a bounded exact int")
        if type(self.valid) is not bool or type(self.benchmark_available) is not bool or type(self.parameter_stable) is not bool:
            raise ValueError("valid, benchmark_available, and parameter_stable must be exact bools")
        for name, value in (("train_return_pct", self.train_return_pct), ("test_return_pct", self.test_return_pct), ("benchmark_return_pct", self.benchmark_return_pct), ("stressed_return_pct", self.stressed_return_pct), ("max_drawdown_pct", self.max_drawdown_pct)):
            if value is not None and (type(value) not in (int, float) or not math.isfinite(float(value))):
                raise ValueError(f"{name} must be an exact finite int/float or None")
        if self.valid:
            if self.error_code is not None or self.error is not None:
                raise ValueError("valid windows cannot contain errors")
            if self.parameters is None or any(value is None for value in (self.train_return_pct, self.test_return_pct, self.stressed_return_pct, self.max_drawdown_pct)):
                raise ValueError("valid windows require complete parameters and metrics")
            if self.oos_observations <= 0:
                raise ValueError("valid windows require OOS observations")
            if not self.benchmark_available and (type(self.benchmark_error) is not str or not self.benchmark_error.strip() or self.benchmark_error != self.benchmark_error.strip()):
                raise ValueError("valid windows without benchmark require benchmark_error")
        else:
            if type(self.error_code) is not str or not self.error_code.strip() or self.error_code != self.error_code.strip() or type(self.error) is not str or not self.error.strip() or self.error != self.error.strip():
                raise ValueError("invalid windows require clean error_code and error")
            if self.parameters is not None or any(value is not None for value in (self.train_return_pct, self.test_return_pct, self.benchmark_return_pct, self.stressed_return_pct, self.max_drawdown_pct)):
                raise ValueError("invalid windows cannot contain success metrics")
            if self.completed_trades != 0 or self.oos_observations != 0 or self.benchmark_available or self.benchmark_error is not None or self.parameter_stable:
                raise ValueError("invalid windows must contain empty metrics and no benchmark or stability evidence")
            if self.neighborhood_parameters or self.neighborhood_returns_pct or self.neighborhood_errors:
                raise ValueError("invalid windows cannot contain neighborhood evidence")
        if self.benchmark_available and self.benchmark_return_pct is None:
            raise ValueError("benchmark_return_pct is required when benchmark_available is True")
        if self.benchmark_available and self.benchmark_error is not None:
            raise ValueError("benchmark_available windows cannot contain benchmark_error")
        if not self.benchmark_available and self.benchmark_return_pct is not None:
            raise ValueError("benchmark_return_pct requires benchmark_available")
        if type(self.neighborhood_parameters) is not tuple or type(self.neighborhood_returns_pct) is not tuple or type(self.neighborhood_errors) is not tuple:
            raise ValueError("neighborhood fields must be exact tuples")
        frozen_parameters = None if self.parameters is None else _parameter_mapping(self.strategy, self.parameters, "parameters")
        object.__setattr__(self, "parameters", frozen_parameters)
        frozen_neighbors = tuple(_parameter_mapping(self.strategy, item, f"neighborhood_parameters[{index}]") for index, item in enumerate(self.neighborhood_parameters))
        if len(set(tuple(sorted(item.items())) for item in frozen_neighbors)) != len(frozen_neighbors):
            raise ValueError("neighborhood parameters must be unique")
        if tuple(sorted(tuple(item.items()) for item in frozen_neighbors)) != tuple(tuple(item.items()) for item in frozen_neighbors):
            raise ValueError("neighborhood parameters must be canonically ordered")
        if frozen_parameters is not None and any(item == frozen_parameters for item in frozen_neighbors):
            raise ValueError("neighborhood cannot contain selected parameters")
        object.__setattr__(self, "neighborhood_parameters", frozen_neighbors)
        if any(type(value) not in (int, float) or not math.isfinite(float(value)) for value in self.neighborhood_returns_pct if value is not None):
            raise ValueError("neighborhood returns must be exact finite numbers or None")
        if any(value is not None and (type(value) is not str or not value.strip() or value != value.strip()) for value in self.neighborhood_errors):
            raise ValueError("neighborhood errors must be clean strings or None")
        if len(frozen_neighbors) != len(self.neighborhood_returns_pct) or len(frozen_neighbors) != len(self.neighborhood_errors):
            raise ValueError("neighborhood parameters, returns, and errors must have equal lengths")
        for index, (return_pct, error) in enumerate(zip(self.neighborhood_returns_pct, self.neighborhood_errors)):
            if (return_pct is None) == (error is None):
                raise ValueError(f"neighborhood entry {index} must contain exactly one return or error")
        object.__setattr__(self, "neighborhood_returns_pct", tuple(None if value is None else float(value) for value in self.neighborhood_returns_pct))
        object.__setattr__(self, "neighborhood_errors", tuple(self.neighborhood_errors))
        expected_stability = False if not self.valid else _assess_parameter_stability(self.test_return_pct, self.neighborhood_returns_pct, self.neighborhood_errors)
        if self.parameter_stable != expected_stability:
            raise ValueError("parameter_stable does not match the canonical stability rule")


@dataclass(frozen=True, slots=True)
class SymbolEvidence:
    symbol: str
    windows: tuple[WindowEvidence, ...]
    valid_windows: int
    oos_observations: int
    completed_trades: int
    total_return_pct: float
    evaluated: bool
    error_code: str | None = None
    error: str | None = None
    separation_verified: bool = False

    def __post_init__(self) -> None:
        if type(self.symbol) is not str or not self.symbol.strip() or self.symbol != self.symbol.strip() or type(self.windows) is not tuple:
            raise ValueError("symbol and windows are invalid")
        if tuple(sorted(self.windows, key=lambda item: item.window)) != self.windows or len({item.window for item in self.windows}) != len(self.windows):
            raise ValueError("windows must be unique and ordered by window number")
        if any(not isinstance(item, WindowEvidence) or item.symbol != self.symbol for item in self.windows):
            raise ValueError("windows must belong to the symbol")
        for previous, current in zip(self.windows, self.windows[1:]):
            previous_test_end = datetime.strptime(previous.test_end, "%Y-%m-%dT%H:%M:%SZ")
            current_test_start = datetime.strptime(current.test_start, "%Y-%m-%dT%H:%M:%SZ")
            if previous_test_end >= current_test_start:
                raise ValueError("same-symbol test ranges must not overlap")
            if datetime.strptime(previous.test_start, "%Y-%m-%dT%H:%M:%SZ") > current_test_start:
                raise ValueError("window order must match test-date order")
        if type(self.valid_windows) is not int or self.valid_windows < 0 or self.valid_windows > 2**63 - 1:
            raise ValueError("valid_windows must be an exact non-negative int")
        if type(self.oos_observations) is not int or self.oos_observations < 0 or self.oos_observations > 2**63 - 1:
            raise ValueError("oos_observations must be an exact non-negative int")
        if type(self.completed_trades) is not int or self.completed_trades < 0 or self.completed_trades > 2**63 - 1:
            raise ValueError("completed_trades must be an exact non-negative int")
        if type(self.total_return_pct) not in (int, float) or type(self.total_return_pct) is bool or not math.isfinite(float(self.total_return_pct)):
            raise ValueError("total_return_pct must be an exact finite int/float")
        if type(self.evaluated) is not bool or type(self.separation_verified) is not bool:
            raise ValueError("evaluated and separation_verified must be exact bools")
        expected = _canonical_symbol_values(self.windows)
        actual = (self.valid_windows, self.oos_observations, self.completed_trades, float(self.total_return_pct), self.evaluated, self.error_code, self.error, self.separation_verified)
        if not self.windows:
            if actual[:5] != expected[:5] or actual[5] != expected[5] or type(self.error) is not str or not self.error.strip() or self.error != self.error.strip() or actual[7] != expected[7]:
                raise ValueError("symbol aggregate fields must equal canonical failure state")
        elif actual != expected:
            raise ValueError("symbol aggregate fields must equal canonical window aggregation")


@dataclass(frozen=True, slots=True)
class UniverseQualificationRequest:
    evaluation_id: str
    created_at: str
    strategy: str
    symbol_data: Mapping[str, pd.DataFrame]
    benchmark_data: pd.DataFrame | Mapping[str, pd.DataFrame] | None = None
    train_days: int = 504
    test_days: int = 126
    step_days: int | None = None
    sort_by: str = "Train Sharpe Ratio"
    parameter_options: Mapping[str, Sequence[int]] | None = None
    period: str = DEFAULT_PERIOD
    interval: str = DEFAULT_INTERVAL
    auto_adjust: bool = False
    initial_capital: float = INITIAL_CAPITAL
    fee_rate: float = FEE_RATE
    tax_rate: float = TAX_RATE
    stress_fee_rate: float | None = None
    stress_tax_rate: float | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    max_hold_days: int | None = None
    position_size: float = 1.0
    policy: QualificationPolicy = TAIWAN_EQUITY_DAILY_V1
    source_run_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        try:
            parsed = UUID(self.evaluation_id)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("evaluation_id must be a canonical UUID v4") from exc
        if parsed.version != 4 or str(parsed) != self.evaluation_id:
            raise ValueError("evaluation_id must be a canonical UUID v4")
        try:
            created = datetime.strptime(self.created_at, "%Y-%m-%dT%H:%M:%SZ")
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("created_at must be UTC YYYY-MM-DDTHH:MM:SSZ") from exc
        if created.strftime("%Y-%m-%dT%H:%M:%SZ") != self.created_at:
            raise ValueError("created_at must be UTC YYYY-MM-DDTHH:MM:SSZ")
        if self.strategy not in _PARAMETER_KEYS:
            raise ValueError("strategy must be ma_cross, rsi, or score")
        if not isinstance(self.policy, QualificationPolicy):
            raise TypeError("policy must be a QualificationPolicy")
        if not isinstance(self.symbol_data, Mapping) or not self.symbol_data:
            raise ValueError("symbol_data must contain at least one symbol")
        snapshots: dict[str, pd.DataFrame] = {}
        for symbol, frame in self.symbol_data.items():
            if type(symbol) is not str or not symbol or symbol.strip() != symbol:
                raise ValueError("symbol_data keys must be clean strings")
            if not isinstance(frame, pd.DataFrame):
                raise ValueError(f"{symbol}: input must be a pandas DataFrame")
            snapshots[symbol] = frame.copy(deep=True)
        object.__setattr__(self, "symbol_data", MappingProxyType(dict(sorted(snapshots.items()))))
        benchmark = self.benchmark_data
        if isinstance(benchmark, pd.DataFrame):
            object.__setattr__(self, "benchmark_data", benchmark.copy(deep=True))
        elif isinstance(benchmark, Mapping):
            benchmark_snapshot = {}
            for symbol, frame in benchmark.items():
                if type(symbol) is not str or not symbol or symbol.strip() != symbol or not isinstance(frame, pd.DataFrame):
                    raise ValueError("benchmark_data mapping must contain clean strings and DataFrames")
                benchmark_snapshot[symbol] = frame.copy(deep=True)
            object.__setattr__(self, "benchmark_data", MappingProxyType(dict(sorted(benchmark_snapshot.items()))))
        elif benchmark is not None:
            raise ValueError("benchmark_data must be a DataFrame, mapping, or None")
        if type(self.train_days) is not int or self.train_days <= 0 or type(self.test_days) is not int or self.test_days <= 0:
            raise ValueError("train_days and test_days must be positive exact integers")
        step = self.test_days if self.step_days is None else self.step_days
        if type(step) is not int or step < self.test_days:
            raise ValueError("step_days must be greater than or equal to test_days")
        object.__setattr__(self, "step_days", step)
        if type(self.sort_by) is not str or self.sort_by not in SORTABLE_COLUMNS:
            raise ValueError(f"unsupported sort_by: {self.sort_by!r}")
        options = self.parameter_options
        if not isinstance(options, Mapping) or set(options) != _PARAMETER_KEYS[self.strategy]:
            raise ValueError(f"parameter_options must contain exactly {_PARAMETER_KEYS[self.strategy]}")
        frozen_options: dict[str, tuple[int, ...]] = {}
        for key in sorted(options):
            values = options[key]
            if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
                raise ValueError(f"parameter_options[{key!r}] must be a sequence")
            try:
                frozen_options[key] = tuple(sorted({int(item) for item in values if type(item) is int}))
            except TypeError as exc:
                raise ValueError(f"parameter_options[{key!r}] must be a sequence") from exc
            if not frozen_options[key] or any(type(item) is not int for item in values):
                raise ValueError(f"parameter_options[{key!r}] must contain exact integers")
        object.__setattr__(self, "parameter_options", MappingProxyType(frozen_options))
        if type(self.period) is not str or type(self.interval) is not str or self.period not in VALID_PERIODS or self.interval not in VALID_INTERVALS:
            raise ValueError("period or interval is not supported")
        if type(self.auto_adjust) is not bool:
            raise ValueError("auto_adjust must be an exact bool")
        if type(self.initial_capital) not in (int, float) or not math.isfinite(float(self.initial_capital)) or self.initial_capital <= 0:
            raise ValueError("initial_capital must be finite and positive")
        for name, value in (("fee_rate", self.fee_rate), ("tax_rate", self.tax_rate), ("stress_fee_rate", self.stress_fee_rate), ("stress_tax_rate", self.stress_tax_rate)):
            if value is not None and (type(value) not in (int, float) or not math.isfinite(float(value)) or value < 0):
                raise ValueError(f"{name} must be finite and non-negative")
        if type(self.position_size) not in (int, float) or not math.isfinite(float(self.position_size)) or not 0 < self.position_size <= 1:
            raise ValueError("position_size must satisfy 0 < value <= 1")
        for name, value in (("stop_loss_pct", self.stop_loss_pct), ("take_profit_pct", self.take_profit_pct)):
            if value is not None and (type(value) not in (int, float) or not math.isfinite(float(value)) or value <= 0):
                raise ValueError(f"{name} must be finite and positive")
        if self.max_hold_days is not None and (type(self.max_hold_days) is not int or self.max_hold_days <= 0):
            raise ValueError("max_hold_days must be a positive exact integer")
        if type(self.source_run_ids) is not tuple:
            raise ValueError("source_run_ids must be an exact tuple")
        if any(type(item) is not str or not item or item.strip() != item for item in self.source_run_ids):
            raise ValueError("source_run_ids must contain clean strings")
        source_ids = tuple(sorted(set(self.source_run_ids)))
        if len(source_ids) != len(self.source_run_ids):
            raise ValueError("source_run_ids must not contain duplicates")
        for source_id in source_ids:
            parsed_source = UUID(source_id)
            if parsed_source.version != 4 or str(parsed_source) != source_id:
                raise ValueError("source_run_ids must contain canonical UUID v4 values")
        object.__setattr__(self, "source_run_ids", source_ids)
        resolved_fee = self.resolved_stress_fee_rate
        resolved_tax = self.resolved_stress_tax_rate
        if self.stress_fee_rate is not None and self.stress_fee_rate < self.fee_rate:
            raise ValueError("stress_fee_rate must be greater than or equal to fee_rate")
        if self.stress_tax_rate is not None and self.stress_tax_rate < self.tax_rate:
            raise ValueError("stress_tax_rate must be greater than or equal to tax_rate")
        if resolved_fee < self.fee_rate or resolved_tax < self.tax_rate or (resolved_fee == self.fee_rate and resolved_tax == self.tax_rate):
            raise ValueError("stress costs must be no lower than base and at least one must be strictly higher")

    @property
    def resolved_stress_fee_rate(self) -> float:
        if self.stress_fee_rate is not None:
            return float(self.stress_fee_rate)
        return float(self.fee_rate * 2 if self.fee_rate > 0 else 1e-9)

    @property
    def resolved_stress_tax_rate(self) -> float:
        if self.stress_tax_rate is not None:
            return float(self.stress_tax_rate)
        return float(self.tax_rate * 2 if self.tax_rate > 0 else 1e-9)


UNIVERSE_OOS_EVIDENCE_ARTIFACT_TYPE = "universe_oos_evidence"
UNIVERSE_OOS_EVIDENCE_SCHEMA_VERSION = "1.0"


def _assess_parameter_stability(selected_return: float | None, returns: Sequence[float | None], errors: Sequence[str | None]) -> bool:
    if selected_return is None or type(selected_return) not in (int, float) or not math.isfinite(float(selected_return)):
        return False
    if len(returns) < PARAMETER_STABILITY_RULE["minimum_successful_neighbors"] or len(returns) != len(errors):
        return False
    if any(error is not None for error in errors) or any(value is None for value in returns):
        return False
    successful = [float(value) for value in returns if value is not None]
    coverage = len(successful) / len(returns)
    selected = float(selected_return)
    if coverage < PARAMETER_STABILITY_RULE["minimum_neighbor_coverage"] or selected <= PARAMETER_STABILITY_RULE["minimum_selected_return_pct"]:
        return False
    retention = min(successful) / selected
    dispersion = (max(successful) - min(successful)) / abs(selected) * 100.0
    if any(value > selected * (1.0 + PARAMETER_STABILITY_RULE["maximum_neighbor_outperformance_ratio"]) for value in successful):
        return False
    return retention >= PARAMETER_STABILITY_RULE["minimum_return_retention"] and dispersion <= PARAMETER_STABILITY_RULE["maximum_return_dispersion_pct"]


def _canonical_symbol_values(windows: tuple[WindowEvidence, ...]) -> tuple[int, int, int, float, bool, str | None, str | None, bool]:
    valid = tuple(item for item in windows if item.valid)
    invalid = tuple(item for item in windows if not item.valid)
    if not windows:
        return (0, 0, 0, 0.0, False, "symbol_evaluation_failed", "symbol evaluation produced no windows", False)
    if invalid:
        return (
            len(valid),
            sum(item.oos_observations for item in valid),
            sum(item.completed_trades for item in valid),
            sum(float(item.test_return_pct) for item in valid) / len(valid) if valid else 0.0,
            bool(valid),
            "partial_window_failure",
            "one or more windows failed",
            True,
        )
    return (
        len(valid),
        sum(item.oos_observations for item in valid),
        sum(item.completed_trades for item in valid),
        sum(float(item.test_return_pct) for item in valid) / len(valid),
        True,
        None,
        None,
        True,
    )


def _canonical_aggregate_metrics(symbols: tuple[SymbolEvidence, ...]) -> QualificationMetricSet:
    valid_windows = tuple(window for symbol in symbols for window in symbol.windows if window.valid)
    returns = [float(window.test_return_pct) for window in valid_windows]
    stressed = [float(window.stressed_return_pct) for window in valid_windows]
    benchmark_returns = [float(window.benchmark_return_pct) for window in valid_windows if window.benchmark_available and window.benchmark_return_pct is not None]
    benchmark_available = bool(valid_windows) and len(benchmark_returns) == len(valid_windows)
    symbol_contributions = {symbol.symbol: sum(abs(float(window.test_return_pct)) for window in symbol.windows if window.valid) for symbol in symbols}
    absolute_returns = symbol_contributions
    denominator = sum(absolute_returns.values())
    concentration = max(absolute_returns.values()) / denominator * 100.0 if denominator else 0.0
    return QualificationMetricSet(
        evidence_scope="out_of_sample",
        data_leakage_free=bool(symbols) and all(symbol.separation_verified for symbol in symbols),
        oos_observations=sum(window.oos_observations for window in valid_windows),
        completed_trades=sum(window.completed_trades for window in valid_windows),
        evaluated_symbols=sum(1 for symbol in symbols if symbol.evaluated),
        valid_windows=len(valid_windows),
        benchmark_available=benchmark_available,
        total_return_pct=sum(returns) / len(returns) if returns else 0.0,
        benchmark_return_pct=sum(benchmark_returns) / len(benchmark_returns) if benchmark_available else None,
        cost_stress_pass=bool(stressed) and min(stressed) >= 0.0,
        stressed_return_pct=sum(stressed) / len(stressed) if stressed else None,
        max_drawdown_pct=max((float(window.max_drawdown_pct) for window in valid_windows), default=0.0),
        positive_window_ratio=sum(value > 0 for value in returns) / len(returns) if returns else 0.0,
        symbol_concentration_pct=concentration,
        parameter_stable=bool(valid_windows) and all(window.parameter_stable for window in valid_windows),
        partial_failure_count=sum(1 for symbol in symbols if not symbol.evaluated) + sum(1 for symbol in symbols for window in symbol.windows if not window.valid),
    )


def aggregate_universe_evidence(symbols: tuple[SymbolEvidence, ...]) -> QualificationMetricSet:
    """Pure canonical aggregation shared by evaluation, validation, and publication."""
    if type(symbols) is not tuple or not symbols:
        raise ValueError("symbols must be a non-empty exact tuple")
    return _canonical_aggregate_metrics(symbols)


def _stability_descriptor() -> dict[str, Any]:
    return _stability_rule_dict()


def _strategy_descriptor(request: UniverseQualificationRequest, resolved: UniverseResolvedConfiguration | None = None) -> StrategyDescriptor:
    resolved = _resolved_configuration(request) if resolved is None else resolved
    return StrategyDescriptor(
        request.strategy,
        {
            "selection": request.sort_by,
            "train_days": request.train_days,
            "test_days": request.test_days,
            "step_days": request.step_days,
            "parameter_neighborhood": _stability_descriptor(),
            "resolved_configuration": resolved.to_payload(),
        },
    )


@dataclass(frozen=True, slots=True)
class UniverseOOSArtifact:
    schema_version: str
    artifact_type: str
    evaluation_id: str
    symbols: tuple[SymbolEvidence, ...]
    qualification: StrategyQualificationResult
    resolved_configuration: UniverseResolvedConfiguration
    stability_rule: Mapping[str, Any] = field(default_factory=_stability_rule_dict)

    def __post_init__(self) -> None:
        if self.schema_version != UNIVERSE_OOS_EVIDENCE_SCHEMA_VERSION or self.artifact_type != UNIVERSE_OOS_EVIDENCE_ARTIFACT_TYPE:
            raise ValueError("unsupported universe OOS evidence artifact identity")
        try:
            parsed = UUID(self.evaluation_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("evaluation_id must be a canonical UUID v4") from exc
        if parsed.version != 4 or str(parsed) != self.evaluation_id:
            raise ValueError("evaluation_id must be a canonical UUID v4")
        if type(self.symbols) is not tuple or not self.symbols or any(not isinstance(item, SymbolEvidence) for item in self.symbols):
            raise ValueError("symbols must be a non-empty tuple of SymbolEvidence")
        if tuple(sorted(self.symbols, key=lambda item: item.symbol)) != self.symbols or len({item.symbol for item in self.symbols}) != len(self.symbols):
            raise ValueError("symbols must be unique and canonically ordered")
        if not isinstance(self.qualification, StrategyQualificationResult):
            raise ValueError("qualification must be a StrategyQualificationResult")
        if not isinstance(self.resolved_configuration, UniverseResolvedConfiguration):
            raise ValueError("resolved_configuration must be a UniverseResolvedConfiguration")
        if self.qualification.request.evaluation_id != self.evaluation_id:
            raise ValueError("qualification and evidence evaluation_id differ")
        try:
            canonical_rule = _validate_stability_rule(self.stability_rule, "stability_rule")
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        object.__setattr__(self, "stability_rule", canonical_rule)
        strategy = self.qualification.request.strategy
        if strategy.strategy_id not in _PARAMETER_KEYS or strategy.parameters.get("parameter_neighborhood") != self.stability_rule or strategy.parameters.get("resolved_configuration") != _freeze_payload(self.resolved_configuration.to_payload()):
            raise ValueError("qualification strategy and resolved configuration are inconsistent")
        if self.resolved_configuration.parameter_stability_rule != self.stability_rule:
            raise ValueError("resolved configuration and stability rule are inconsistent")
        if any(window.strategy != strategy.strategy_id for symbol in self.symbols for window in symbol.windows):
            raise ValueError("window strategies must match qualification strategy")
        aggregate = _canonical_aggregate_metrics(self.symbols)
        if self.qualification.request.metrics != aggregate:
            raise ValueError("qualification metrics must equal canonical evidence aggregation")


@dataclass(frozen=True, slots=True)
class UniverseQualificationResult:
    request: UniverseQualificationRequest
    symbols: tuple[SymbolEvidence, ...]
    qualification: StrategyQualificationResult
    artifact_references: tuple[ArtifactReference, ...] = ()
    manifest: RunManifest | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, UniverseQualificationRequest) or type(self.symbols) is not tuple or not isinstance(self.qualification, StrategyQualificationResult):
            raise ValueError("request, symbols, and qualification must be typed")
        if tuple(sorted(self.symbols, key=lambda item: item.symbol)) != self.symbols or len({item.symbol for item in self.symbols}) != len(self.symbols):
            raise ValueError("symbols must be unique and canonically ordered")
        if tuple(item.symbol for item in self.symbols) != tuple(sorted(self.request.symbol_data)):
            raise ValueError("symbols must exactly match request symbol_data")
        if self.qualification.request.evaluation_id != self.request.evaluation_id or self.qualification.request.created_at != self.request.created_at:
            raise ValueError("qualification request identity differs from universe request")
        if self.qualification.request.strategy != _strategy_descriptor(self.request) or self.qualification.request.policy != self.request.policy:
            raise ValueError("qualification request does not match universe request")
        if self.qualification.request.metrics != _canonical_aggregate_metrics(self.symbols):
            raise ValueError("qualification metrics must equal canonical evidence aggregation")
        if type(self.artifact_references) is not tuple or any(not isinstance(item, ArtifactReference) for item in self.artifact_references):
            raise ValueError("artifact_references must be an exact tuple of ArtifactReference")
        if self.manifest is not None and not isinstance(self.manifest, RunManifest):
            raise ValueError("manifest must be a RunManifest")

    @property
    def aggregate_metrics(self) -> QualificationMetricSet:
        return self.qualification.request.metrics

    @property
    def decision(self) -> str:
        return self.qualification.decision.state


def _as_text(value: Any) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_frame(symbol: str, frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError(f"{symbol}: input must be a non-empty pandas DataFrame")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError(f"{symbol}: index must be a DatetimeIndex")
    if not frame.index.is_unique:
        raise ValueError(f"{symbol}: index must be unique")
    if not frame.index.is_monotonic_increasing:
        raise ValueError(f"{symbol}: index must be monotonically increasing")
    if bool(frame.index.hasnans):
        raise ValueError(f"{symbol}: index must not contain missing values")
    if "Close" not in frame.columns or "Open" not in frame.columns:
        raise ValueError(f"{symbol}: input requires Open and Close columns")
    clean = frame.copy(deep=True)
    for column in ("Open", "Close"):
        numeric = pd.to_numeric(clean[column], errors="coerce")
        if numeric.isna().any() or not numeric.map(lambda value: math.isfinite(float(value))).all():
            raise ValueError(f"{symbol}: {column} must contain only finite numeric values")
        clean[column] = numeric
    return clean


def _validate_windows(symbol: str, windows: Sequence[tuple[int, pd.DataFrame, pd.DataFrame]]) -> None:
    seen = pd.DatetimeIndex([])
    previous_number: int | None = None
    previous_test_end: Any = None
    for number, train, test in windows:
        if type(number) is not int or number <= 0:
            raise ValueError(f"{symbol} window number must be a positive exact int")
        if previous_number is not None and number <= previous_number:
            raise ValueError(f"{symbol} window numbers must be strictly increasing")
        if not isinstance(train.index, pd.DatetimeIndex) or not isinstance(test.index, pd.DatetimeIndex):
            raise ValueError(f"{symbol} window indexes must be DatetimeIndex")
        try:
            if not bool(train.index[-1] < test.index[0]):
                raise ValueError(f"{symbol} window {number} does not satisfy train_end < test_start")
        except TypeError as exc:
            raise ValueError(f"{symbol} window {number} chronology cannot be proved") from exc
        if previous_test_end is not None and previous_test_end >= test.index[0]:
            raise ValueError(f"{symbol} window {number} has overlapping OOS observations")
        if not train.index.intersection(test.index).empty or not seen.intersection(test.index).empty:
            raise ValueError(f"{symbol} window {number} has overlapping OOS observations")
        seen = test.index if seen.empty else seen.append(test.index)
        previous_number = number
        previous_test_end = test.index[-1]


def _align_benchmark(benchmark: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(benchmark, pd.DataFrame) or benchmark.empty or not isinstance(benchmark.index, pd.DatetimeIndex) or not benchmark.index.is_unique or not benchmark.index.is_monotonic_increasing or bool(benchmark.index.hasnans) or "Close" not in benchmark.columns:
        raise ValueError("benchmark index/Close values are incomplete")
    if not test.index.isin(benchmark.index).all():
        raise ValueError("benchmark is missing required test dates")
    aligned = benchmark.reindex(test.index).copy(deep=True)
    closes = pd.to_numeric(aligned["Close"], errors="coerce")
    if len(aligned) != len(test) or closes.isna().any() or not closes.map(lambda value: math.isfinite(float(value))).all():
        raise ValueError("benchmark does not fully cover the test window")
    aligned["Close"] = closes
    return aligned


def _parameter_kwargs(request: UniverseQualificationRequest) -> dict[str, tuple[int, ...] | None]:
    values = dict(request.parameter_options or {})
    return {
        "ma_short_windows": tuple(values["short_window"]) if "short_window" in values else None,
        "ma_long_windows": tuple(values["long_window"]) if "long_window" in values else None,
        "rsi_buy_below": tuple(values["buy_below"]) if "buy_below" in values else None,
        "rsi_sell_above": tuple(values["sell_above"]) if "sell_above" in values else None,
        "score_buy": tuple(values["buy_score"]) if "buy_score" in values else None,
        "score_sell": tuple(values["sell_score"]) if "sell_score" in values else None,
    }


def _select_parameters(
    request: UniverseQualificationRequest,
    train: pd.DataFrame,
) -> tuple[dict[str, int], dict[str, Any]]:
    grid = parameter_grid(request.strategy, **_parameter_kwargs(request))
    best: tuple[float, dict[str, int], dict[str, Any]] | None = None
    errors: list[str] = []
    for params in grid:
        try:
            result = run_strategy_backtest(
                train,
                request.strategy,
                params,
                request.stop_loss_pct,
                request.take_profit_pct,
                request.max_hold_days,
                request.position_size,
                request.initial_capital,
                request.fee_rate,
                request.tax_rate,
                request.interval,
            )
            metric = sort_train_metric(result, request.sort_by)
            if not math.isfinite(metric):
                raise ValueError("train selection metric is non-finite")
            candidate = (metric, params, result)
            if best is None or metric > best[0]:
                best = candidate
        except Exception as exc:
            errors.append(f"{params}: {exc}")
    if best is None:
        raise ValueError("no train parameter set succeeded: " + "; ".join(errors))
    return best[1], best[2]


def _neighbors(selected: Mapping[str, int], grid: Sequence[Mapping[str, int]]) -> tuple[dict[str, int], ...]:
    keys = tuple(sorted(selected))
    positions = {key: {value: index for index, value in enumerate(sorted({item[key] for item in grid}))} for key in keys}
    neighbors: list[dict[str, int]] = []
    for candidate in grid:
        if dict(candidate) == dict(selected):
            continue
        deltas = [abs(positions[key][candidate[key]] - positions[key][selected[key]]) for key in keys]
        if deltas and max(deltas) <= 1:
            neighbors.append(dict(candidate))
    return tuple(sorted(neighbors, key=lambda item: tuple(sorted(item.items()))))


def _benchmark_frame(benchmark: pd.DataFrame | Mapping[str, pd.DataFrame] | None, symbol: str) -> pd.DataFrame | None:
    if benchmark is None:
        return None
    if isinstance(benchmark, pd.DataFrame):
        return benchmark
    if isinstance(benchmark, Mapping):
        candidate = benchmark.get(symbol)
        if not isinstance(candidate, pd.DataFrame):
            candidate = benchmark.get("__benchmark__")
        return candidate if isinstance(candidate, pd.DataFrame) else None
    return None


def _benchmark_descriptor(scope: str, symbol: str, frame: pd.DataFrame | None) -> BenchmarkDescriptor:
    if frame is None:
        return BenchmarkDescriptor("none", "__none__", 0, None, None, "none")
    index_start = index_end = None
    try:
        if isinstance(frame.index, pd.DatetimeIndex) and len(frame.index) > 0 and frame.index.is_unique and frame.index.is_monotonic_increasing and not frame.index.hasnans:
            index_start = _as_text(frame.index[0])
            index_end = _as_text(frame.index[-1])
    except Exception:
        index_start = index_end = None
    digest = hashlib.sha256()
    try:
        values = frame["Close"]
    except Exception:
        values = ()
    try:
        for index, value in zip(frame.index, values):
            digest.update(f"{repr(index)}|{repr(value)}\n".encode("utf-8"))
        close_hash = digest.hexdigest()
    except Exception:
        close_hash = "invalid"
    return BenchmarkDescriptor(scope, symbol, int(len(frame)), index_start, index_end, close_hash)


def _resolved_configuration(request: UniverseQualificationRequest) -> UniverseResolvedConfiguration:
    grid = tuple(sorted((dict(item) for item in parameter_grid(request.strategy, **_parameter_kwargs(request))), key=lambda item: tuple(sorted(item.items()))))
    benchmark = request.benchmark_data
    if benchmark is None:
        descriptors = (_benchmark_descriptor("none", "__none__", None),)
    elif isinstance(benchmark, pd.DataFrame):
        descriptors = (_benchmark_descriptor("shared", "__shared__", benchmark),)
    else:
        descriptors = tuple(sorted((
            _benchmark_descriptor("shared" if symbol == "__benchmark__" else "per_symbol", symbol, frame)
            for symbol, frame in sorted(benchmark.items())
        ), key=lambda item: (item.scope, item.symbol)))
    return UniverseResolvedConfiguration(
        strategy=request.strategy, parameter_grid=grid, sort_by=request.sort_by, train_days=request.train_days, test_days=request.test_days, step_days=request.step_days,
        period=request.period, interval=request.interval, auto_adjust=request.auto_adjust, initial_capital=float(request.initial_capital), fee_rate=float(request.fee_rate), tax_rate=float(request.tax_rate),
        stress_fee_rate=request.resolved_stress_fee_rate, stress_tax_rate=request.resolved_stress_tax_rate, position_size=float(request.position_size), stop_loss_pct=None if request.stop_loss_pct is None else float(request.stop_loss_pct),
        take_profit_pct=None if request.take_profit_pct is None else float(request.take_profit_pct), max_hold_days=request.max_hold_days, benchmark_descriptors=descriptors, source_run_ids=request.source_run_ids,
        parameter_stability_rule=_stability_rule_dict(), concentration_rule=dict(CONCENTRATION_RULE),
    )


def _window_evidence(request: UniverseQualificationRequest, symbol: str, number: int, train: pd.DataFrame, test: pd.DataFrame, benchmark: pd.DataFrame | None) -> WindowEvidence:
    starts = (_as_text(train.index[0]), _as_text(train.index[-1]), _as_text(test.index[0]), _as_text(test.index[-1]))
    try:
        params, train_result = _select_parameters(request, train)
        test_result = run_strategy_backtest(test, request.strategy, params, request.stop_loss_pct, request.take_profit_pct, request.max_hold_days, request.position_size, request.initial_capital, request.fee_rate, request.tax_rate, request.interval)
        stressed = run_strategy_backtest(test, request.strategy, params, request.stop_loss_pct, request.take_profit_pct, request.max_hold_days, request.position_size, request.initial_capital, request.resolved_stress_fee_rate, request.resolved_stress_tax_rate, request.interval)
        benchmark_available = False
        benchmark_return = None
        benchmark_error = "benchmark_missing: benchmark data not supplied"
        if benchmark is not None:
            try:
                benchmark_return = float(calculate_buy_hold_return(_align_benchmark(benchmark, test)))
                benchmark_available = True
                benchmark_error = None
            except Exception as exc:
                benchmark_error = f"benchmark_missing: {exc}"
        grid = parameter_grid(request.strategy, **_parameter_kwargs(request))
        neighbors = _neighbors(params, grid)
        neighbor_returns: list[float | None] = []
        neighbor_errors: list[str | None] = []
        for neighbor in neighbors:
            try:
                neighbor_result = run_strategy_backtest(test, request.strategy, neighbor, request.stop_loss_pct, request.take_profit_pct, request.max_hold_days, request.position_size, request.initial_capital, request.fee_rate, request.tax_rate, request.interval)
                neighbor_returns.append(float(neighbor_result["Total Return %"]))
                neighbor_errors.append(None)
            except Exception as exc:
                neighbor_returns.append(None)
                neighbor_errors.append(f"{neighbor}: {exc}")
        selected_return = float(test_result["Total Return %"])
        parameter_stable = _assess_parameter_stability(selected_return, neighbor_returns, neighbor_errors)
        return WindowEvidence(
            symbol=symbol, window=number, train_start=starts[0], train_end=starts[1], test_start=starts[2], test_end=starts[3], strategy=request.strategy, parameters=dict(params),
            train_return_pct=float(train_result["Total Return %"]), test_return_pct=selected_return, benchmark_return_pct=benchmark_return, stressed_return_pct=float(stressed["Total Return %"]),
            completed_trades=int(test_result["Trade Count"]), oos_observations=int(test.index.nunique()), max_drawdown_pct=abs(float(test_result["Max Drawdown %"])), valid=True,
            benchmark_available=benchmark_available, benchmark_error=benchmark_error, neighborhood_parameters=neighbors, neighborhood_returns_pct=tuple(neighbor_returns), neighborhood_errors=tuple(neighbor_errors), parameter_stable=parameter_stable,
        )
    except Exception as exc:
        return WindowEvidence(
            symbol=symbol, window=number, train_start=starts[0], train_end=starts[1], test_start=starts[2], test_end=starts[3], strategy=request.strategy, parameters=None,
            train_return_pct=None, test_return_pct=None, benchmark_return_pct=None, stressed_return_pct=None, completed_trades=0, oos_observations=0, max_drawdown_pct=None,
            valid=False, error_code="window_evaluation_failed", error=_error_message(exc),
        )


def _symbol_evidence(request: UniverseQualificationRequest, symbol: str, frame: pd.DataFrame) -> SymbolEvidence:
    try:
        clean = _clean_frame(symbol, frame)
        windows = split_windows(clean, request.train_days, request.test_days, request.step_days)
        _validate_windows(symbol, windows)
    except Exception as exc:
        return SymbolEvidence(symbol, (), 0, 0, 0, 0.0, False, "symbol_evaluation_failed", _error_message(exc), False)
    benchmark = _benchmark_frame(request.benchmark_data, symbol)
    details = tuple(_window_evidence(request, symbol, number, train, test, benchmark) for number, train, test in windows)
    values = _canonical_symbol_values(details)
    return SymbolEvidence(symbol, details, *values)


def evaluate_universe_qualification(request: UniverseQualificationRequest) -> UniverseQualificationResult:
    if not isinstance(request, UniverseQualificationRequest):
        raise TypeError("request must be a UniverseQualificationRequest")
    symbols = tuple(_symbol_evidence(request, symbol, request.symbol_data[symbol]) for symbol in sorted(request.symbol_data))
    metrics = _canonical_aggregate_metrics(symbols)
    qualification_request = StrategyQualificationRequest(request.evaluation_id, request.created_at, _strategy_descriptor(request), metrics, request.policy)
    qualification = evaluate_strategy_qualification(qualification_request)
    return UniverseQualificationResult(request, symbols, qualification)


_EVIDENCE_KEYS = ("schema_version", "artifact_type", "evaluation_id", "stability_rule", "resolved_configuration", "qualification", "symbols")
_SYMBOL_EVIDENCE_KEYS = ("symbol", "windows", "valid_windows", "oos_observations", "completed_trades", "total_return_pct", "evaluated", "separation_verified", "error_code", "error")
_WINDOW_EVIDENCE_KEYS = ("symbol", "window", "train_start", "train_end", "test_start", "test_end", "strategy", "parameters", "train_return_pct", "test_return_pct", "benchmark_available", "benchmark_return_pct", "benchmark_error", "stressed_return_pct", "completed_trades", "oos_observations", "max_drawdown_pct", "valid", "error_code", "error", "neighborhood_parameters", "neighborhood_returns_pct", "neighborhood_errors", "parameter_stable")
_MAX_JSON_INT = 2**63 - 1


def build_universe_oos_evidence(result: UniverseQualificationResult) -> UniverseOOSArtifact:
    if not isinstance(result, UniverseQualificationResult):
        raise UniverseEvidenceSerializationError("expected a UniverseQualificationResult")
    resolved = _resolved_configuration(result.request)
    return UniverseOOSArtifact(
        UNIVERSE_OOS_EVIDENCE_SCHEMA_VERSION,
        UNIVERSE_OOS_EVIDENCE_ARTIFACT_TYPE,
        result.request.evaluation_id,
        result.symbols,
        result.qualification,
        resolved,
        _stability_rule_dict(),
    )


def _window_payload(value: WindowEvidence) -> dict[str, Any]:
    return {
        "symbol": value.symbol, "window": value.window, "train_start": value.train_start, "train_end": value.train_end, "test_start": value.test_start, "test_end": value.test_end, "strategy": value.strategy,
        "parameters": dict(value.parameters) if value.parameters is not None else None, "train_return_pct": value.train_return_pct, "test_return_pct": value.test_return_pct,
        "benchmark_available": value.benchmark_available, "benchmark_return_pct": value.benchmark_return_pct, "benchmark_error": value.benchmark_error, "stressed_return_pct": value.stressed_return_pct,
        "completed_trades": value.completed_trades, "oos_observations": value.oos_observations, "max_drawdown_pct": value.max_drawdown_pct, "valid": value.valid, "error_code": value.error_code, "error": value.error,
        "neighborhood_parameters": [dict(item) for item in value.neighborhood_parameters], "neighborhood_returns_pct": list(value.neighborhood_returns_pct), "neighborhood_errors": list(value.neighborhood_errors), "parameter_stable": value.parameter_stable,
    }


def serialize_universe_oos_evidence(artifact: UniverseOOSArtifact) -> dict[str, Any]:
    if not isinstance(artifact, UniverseOOSArtifact):
        raise UniverseEvidenceSerializationError("expected a UniverseOOSArtifact")
    return {
        "schema_version": artifact.schema_version,
        "artifact_type": artifact.artifact_type,
        "evaluation_id": artifact.evaluation_id,
        "stability_rule": dict(artifact.stability_rule),
        "resolved_configuration": artifact.resolved_configuration.to_payload(),
        "qualification": serialize_strategy_qualification_result(artifact.qualification),
        "symbols": [
            {
                "symbol": item.symbol, "windows": [_window_payload(window) for window in item.windows], "valid_windows": item.valid_windows, "oos_observations": item.oos_observations,
                "completed_trades": item.completed_trades, "total_return_pct": item.total_return_pct, "evaluated": item.evaluated, "separation_verified": item.separation_verified, "error_code": item.error_code, "error": item.error,
            }
            for item in artifact.symbols
        ],
    }


def export_universe_oos_evidence_json(artifact: UniverseOOSArtifact) -> str:
    return json.dumps(serialize_universe_oos_evidence(artifact), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _strict_object(value: Any, expected: tuple[str, ...], path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise UniverseEvidenceSerializationError(f"{path}: expected an exact object")
    missing = [key for key in expected if key not in value]
    unknown = [key for key in value if key not in expected]
    if missing or unknown:
        raise UniverseEvidenceSerializationError(f"{path}: missing={missing}, unknown={unknown}")
    return value


def _parameters(value: Any, path: str) -> Mapping[str, int] | None:
    if value is None:
        return None
    if type(value) is not dict:
        raise UniverseEvidenceSerializationError(f"{path}: expected object or null")
    result: dict[str, int] = {}
    for key, item in value.items():
        if type(key) is not str or not key.strip() or key != key.strip() or type(item) is not int or abs(item) > _MAX_JSON_INT:
            raise UniverseEvidenceSerializationError(f"{path}: parameter keys/values are invalid")
        result[key] = item
    return result


_CONFIG_KEYS = ("strategy", "parameter_grid", "sort_by", "train_days", "test_days", "step_days", "period", "interval", "auto_adjust", "initial_capital", "fee_rate", "tax_rate", "stress_fee_rate", "stress_tax_rate", "position_size", "stop_loss_pct", "take_profit_pct", "max_hold_days", "benchmark_descriptors", "source_run_ids", "parameter_stability_rule", "concentration_rule")
_BENCHMARK_DESCRIPTOR_KEYS = ("scope", "symbol", "rows", "index_start", "index_end", "close_sha256")


def _resolved_configuration_from_payload(value: Any, path: str) -> UniverseResolvedConfiguration:
    raw = _strict_object(value, _CONFIG_KEYS, path)
    if type(raw["parameter_grid"]) is not list or type(raw["benchmark_descriptors"]) is not list or type(raw["source_run_ids"]) is not list:
        raise UniverseEvidenceSerializationError(f"{path}: list fields must be exact lists")
    grid = tuple(_parameters(item, f"{path}.parameter_grid[{index}]") for index, item in enumerate(raw["parameter_grid"]))
    descriptors: list[BenchmarkDescriptor] = []
    for index, item in enumerate(raw["benchmark_descriptors"]):
        descriptor_raw = _strict_object(item, _BENCHMARK_DESCRIPTOR_KEYS, f"{path}.benchmark_descriptors[{index}]")
        try:
            descriptors.append(BenchmarkDescriptor(**descriptor_raw))
        except (TypeError, ValueError) as exc:
            raise UniverseEvidenceSerializationError(f"{path}.benchmark_descriptors[{index}]: invalid descriptor: {exc}") from exc
    if type(raw["parameter_stability_rule"]) is not dict or type(raw["concentration_rule"]) is not dict:
        raise UniverseEvidenceSerializationError(f"{path}: rule fields must be exact objects")
    try:
        return UniverseResolvedConfiguration(
            strategy=raw["strategy"], parameter_grid=grid, sort_by=raw["sort_by"], train_days=raw["train_days"], test_days=raw["test_days"], step_days=raw["step_days"],
            period=raw["period"], interval=raw["interval"], auto_adjust=raw["auto_adjust"], initial_capital=raw["initial_capital"], fee_rate=raw["fee_rate"], tax_rate=raw["tax_rate"],
            stress_fee_rate=raw["stress_fee_rate"], stress_tax_rate=raw["stress_tax_rate"], position_size=raw["position_size"], stop_loss_pct=raw["stop_loss_pct"], take_profit_pct=raw["take_profit_pct"], max_hold_days=raw["max_hold_days"],
            benchmark_descriptors=tuple(descriptors), source_run_ids=tuple(raw["source_run_ids"]), parameter_stability_rule=raw["parameter_stability_rule"], concentration_rule=raw["concentration_rule"],
        )
    except (TypeError, ValueError) as exc:
        raise UniverseEvidenceSerializationError(f"{path}: model validation failed: {exc}") from exc


def _window_from_payload(value: Any, path: str) -> WindowEvidence:
    raw = _strict_object(value, _WINDOW_EVIDENCE_KEYS, path)
    if raw["strategy"] not in _PARAMETER_KEYS:
        raise UniverseEvidenceSerializationError(f"{path}.strategy: unsupported strategy")
    parameter_values = _parameters(raw["parameters"], f"{path}.parameters")
    if raw["valid"]:
        if parameter_values is None or set(parameter_values) != _PARAMETER_KEYS[raw["strategy"]]:
            raise UniverseEvidenceSerializationError(f"{path}.parameters: keys do not match strategy")
    elif parameter_values is not None:
        raise UniverseEvidenceSerializationError(f"{path}.parameters: invalid windows must use null parameters")
    neighbors = raw["neighborhood_parameters"]
    returns = raw["neighborhood_returns_pct"]
    errors = raw["neighborhood_errors"]
    if type(neighbors) is not list or type(returns) is not list or type(errors) is not list:
        raise UniverseEvidenceSerializationError(f"{path}: neighborhood fields must be lists")
    neighborhood_parameters = tuple(_parameters(item, f"{path}.neighborhood_parameters[{index}]") for index, item in enumerate(neighbors))
    if any(item is None for item in neighborhood_parameters):
        raise UniverseEvidenceSerializationError(f"{path}.neighborhood_parameters cannot contain null")
    try:
        return WindowEvidence(
            symbol=raw["symbol"], window=raw["window"], train_start=raw["train_start"], train_end=raw["train_end"], test_start=raw["test_start"], test_end=raw["test_end"], strategy=raw["strategy"], parameters=parameter_values,
            train_return_pct=raw["train_return_pct"], test_return_pct=raw["test_return_pct"], benchmark_return_pct=raw["benchmark_return_pct"], stressed_return_pct=raw["stressed_return_pct"],
            completed_trades=raw["completed_trades"], oos_observations=raw["oos_observations"], max_drawdown_pct=raw["max_drawdown_pct"], valid=raw["valid"], error_code=raw["error_code"], error=raw["error"],
            benchmark_available=raw["benchmark_available"], benchmark_error=raw["benchmark_error"], neighborhood_parameters=neighborhood_parameters, neighborhood_returns_pct=tuple(returns), neighborhood_errors=tuple(errors), parameter_stable=raw["parameter_stable"],
        )
    except (TypeError, ValueError) as exc:
        raise UniverseEvidenceSerializationError(f"{path}: model validation failed: {exc}") from exc


def deserialize_universe_oos_evidence(data: dict[str, Any]) -> UniverseOOSArtifact:
    root = _strict_object(data, _EVIDENCE_KEYS, "$")
    if root["schema_version"] != UNIVERSE_OOS_EVIDENCE_SCHEMA_VERSION or root["artifact_type"] != UNIVERSE_OOS_EVIDENCE_ARTIFACT_TYPE:
        raise UniverseEvidenceSerializationError("$: unsupported schema or artifact type")
    if type(root["stability_rule"]) is not dict:
        raise UniverseEvidenceSerializationError("$.stability_rule: expected exact object")
    try:
        _validate_stability_rule(root["stability_rule"], "$.stability_rule")
    except ValueError as exc:
        raise UniverseEvidenceSerializationError(str(exc)) from exc
    resolved_configuration = _resolved_configuration_from_payload(root["resolved_configuration"], "$.resolved_configuration")
    if type(root["symbols"]) is not list:
        raise UniverseEvidenceSerializationError("$.symbols: expected list")
    symbols: list[SymbolEvidence] = []
    for index, item in enumerate(root["symbols"]):
        path_value = f"$.symbols[{index}]"
        raw = _strict_object(item, _SYMBOL_EVIDENCE_KEYS, path_value)
        if type(raw["windows"]) is not list:
            raise UniverseEvidenceSerializationError(f"{path_value}.windows: expected list")
        windows = tuple(_window_from_payload(window, f"{path_value}.windows[{window_index}]") for window_index, window in enumerate(raw["windows"]))
        try:
            symbols.append(SymbolEvidence(raw["symbol"], windows, raw["valid_windows"], raw["oos_observations"], raw["completed_trades"], raw["total_return_pct"], raw["evaluated"], raw["error_code"], raw["error"], raw["separation_verified"]))
        except (TypeError, ValueError) as exc:
            raise UniverseEvidenceSerializationError(f"{path_value}: model validation failed: {exc}") from exc
    try:
        qualification = deserialize_strategy_qualification_result(root["qualification"])
    except (QualificationSerializationError, TypeError, ValueError) as exc:
        raise UniverseEvidenceSerializationError(f"$.qualification: invalid Phase 56.1 result: {exc}") from exc
    try:
        return UniverseOOSArtifact(root["schema_version"], root["artifact_type"], root["evaluation_id"], tuple(symbols), qualification, resolved_configuration, root["stability_rule"])
    except (TypeError, ValueError) as exc:
        raise UniverseEvidenceSerializationError(f"$: model validation failed: {exc}") from exc


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise UniverseEvidenceSerializationError(f"$: duplicate JSON field {key!r}")
        result[key] = value
    return result


def _parse_json_int(value: str) -> int:
    result = int(value)
    if abs(result) > _MAX_JSON_INT:
        raise UniverseEvidenceSerializationError("$: numeric overflow")
    return result


def _parse_json_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise UniverseEvidenceSerializationError("$: non-finite JSON number")
    return result


def load_universe_oos_evidence_json(text: str) -> UniverseOOSArtifact:
    if type(text) is not str:
        raise UniverseEvidenceSerializationError("JSON input must be an exact string")
    try:
        payload = json.loads(text, parse_int=_parse_json_int, parse_float=_parse_json_float, parse_constant=lambda value: (_ for _ in ()).throw(UniverseEvidenceSerializationError(f"$: invalid JSON numeric constant {value}")), object_pairs_hook=_reject_duplicate_json_keys)
    except UniverseEvidenceSerializationError:
        raise
    except json.JSONDecodeError as exc:
        raise UniverseEvidenceSerializationError(f"$: invalid JSON: {exc.msg}") from exc
    return deserialize_universe_oos_evidence(payload)

def _exclusive_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise WorkspacePathError("publish qualification artifact", path, "existing artifact will not be overwritten") from exc


def _manifest_outcome(symbols: tuple[SymbolEvidence, ...]) -> tuple[str, int, int, int, tuple[str, ...]]:
    failed_symbols = tuple(item for item in symbols if not item.evaluated)
    failed_windows = tuple(window for item in symbols for window in item.windows if not window.valid)
    complete_symbols = tuple(item for item in symbols if item.evaluated and not any(not window.valid for window in item.windows))
    errors = tuple(f"{window.symbol}:window={window.window}:{window.error_code}:{window.error}" for window in failed_windows)
    errors += tuple(f"{item.symbol}:symbol:{item.error_code}:{item.error}" for item in failed_symbols if not item.windows)
    if not complete_symbols:
        failed_count = len({item.symbol for item in failed_symbols} | {window.symbol for window in failed_windows})
        return "failure", 0, failed_count, 0, errors
    if failed_symbols or failed_windows:
        return "partial", len(complete_symbols), len(failed_symbols), len(failed_windows), errors
    return "success", len(symbols), 0, 0, errors


def _cleanup_publication(paths: Sequence[Path], manifest_path: Path, manifest_preexisted: bool) -> None:
    failures: list[str] = []
    for path in reversed(paths):
        try:
            path.unlink(missing_ok=True)
        except Exception as exc:
            failures.append(f"{path}: {exc}")
    if not manifest_preexisted:
        try:
            manifest_path.unlink(missing_ok=True)
        except Exception as exc:
            failures.append(f"{manifest_path}: {exc}")
    if failures:
        raise UniverseQualificationError(
            "publication cleanup failed; possible orphaned paths: " + "; ".join(failures)
        )


def publish_universe_qualification(result: UniverseQualificationResult, lifecycle: WorkspaceRunLifecycle) -> UniverseQualificationResult:
    if not isinstance(result, UniverseQualificationResult) or not isinstance(lifecycle, WorkspaceRunLifecycle):
        raise TypeError("result and lifecycle must be their typed instances")
    if result.qualification.request.evaluation_id != result.request.evaluation_id:
        raise UniverseQualificationError("qualification and request evaluation_id differ")
    evidence = build_universe_oos_evidence(result)
    qualification_path = lifecycle.artifacts_directory / "strategy_qualification.json"
    evidence_path = lifecycle.artifacts_directory / "universe_oos_evidence.json"
    created: list[Path] = []
    manifest_preexisted = lifecycle.manifest_path.exists()
    try:
        _exclusive_write(qualification_path, export_strategy_qualification_json(result.qualification))
        created.append(qualification_path)
        _exclusive_write(evidence_path, export_universe_oos_evidence_json(evidence))
        created.append(evidence_path)
        refs = tuple(sorted((
            lifecycle.artifact_reference(qualification_path, STRATEGY_QUALIFICATION_ARTIFACT_TYPE, "application/json", STRATEGY_QUALIFICATION_SCHEMA_VERSION),
            lifecycle.artifact_reference(evidence_path, UNIVERSE_OOS_EVIDENCE_ARTIFACT_TYPE, "application/json", UNIVERSE_OOS_EVIDENCE_SCHEMA_VERSION),
        ), key=lambda item: (item.artifact_type, item.path)))
        request = result.request
        resolved_payload = evidence.resolved_configuration.to_payload()
        options = {
            "evaluation_id": request.evaluation_id,
            "source_run_ids": list(request.source_run_ids),
            "artifact_paths": [ref.path for ref in refs],
            "provided_input": True,
            "resolved_configuration": resolved_payload,
        }
        config = RunConfig(
            "universe-oos-evaluation", None, tuple(sorted(request.symbol_data)), request.period, request.interval, request.auto_adjust, False, request.strategy, None, request.parameter_options,
            resolved_payload, None, options,
        )
        status, success_count, failure_count, partial_count, errors = _manifest_outcome(result.symbols)
        manifest = RunManifest(
            RUN_MANIFEST_SCHEMA_VERSION, lifecycle.run_id, lifecycle.created_at, _tool_version(), status, lifecycle.normalize_config(config), (), success_count, failure_count, partial_count, refs, errors,
            ("caller-provided in-memory input; data-source provenance was not supplied", "partial symbol/window failures are retained as typed evidence") if status == "partial" else ("caller-provided in-memory input; data-source provenance was not supplied",),
        )
        lifecycle.publish(manifest)
    except Exception as publish_error:
        try:
            _cleanup_publication(created, lifecycle.manifest_path, manifest_preexisted)
        except UniverseQualificationError as cleanup_error:
            raise UniverseQualificationError(
                f"publication failed: {publish_error}; {cleanup_error}"
            ) from publish_error
        raise
    return UniverseQualificationResult(result.request, result.symbols, result.qualification, refs, manifest)


def run_universe_qualification(request: UniverseQualificationRequest, *, workspace_root: str | Path | None = None, lifecycle: WorkspaceRunLifecycle | None = None) -> UniverseQualificationResult:
    result = evaluate_universe_qualification(request)
    if lifecycle is not None:
        return publish_universe_qualification(result, lifecycle)
    if workspace_root is not None:
        return publish_universe_qualification(result, WorkspaceRunLifecycle.begin(workspace_root, "universe-oos-evaluation"))
    return result


UniverseEvaluationRequest = UniverseQualificationRequest
UniverseEvaluationResult = UniverseQualificationResult
UniverseOOSEvidence = UniverseOOSArtifact
UniverseOOSWindowEvidence = WindowEvidence
UniverseOOSSymbolEvidence = SymbolEvidence
run_universe_evaluation = run_universe_qualification

__all__ = [
    "UNIVERSE_OOS_EVIDENCE_ARTIFACT_TYPE", "UNIVERSE_OOS_EVIDENCE_SCHEMA_VERSION", "PARAMETER_STABILITY_RULE", "CONCENTRATION_RULE",
    "UniverseQualificationError", "UniverseEvidenceSerializationError", "aggregate_universe_evidence", "BenchmarkDescriptor", "UniverseResolvedConfiguration", "WindowEvidence", "SymbolEvidence", "UniverseOOSArtifact", "UniverseOOSEvidence", "UniverseOOSWindowEvidence", "UniverseOOSSymbolEvidence", "UniverseQualificationRequest", "UniverseQualificationResult", "UniverseEvaluationRequest", "UniverseEvaluationResult", "evaluate_universe_qualification", "build_universe_oos_evidence", "serialize_universe_oos_evidence", "deserialize_universe_oos_evidence", "export_universe_oos_evidence_json", "load_universe_oos_evidence_json", "publish_universe_qualification", "run_universe_qualification", "run_universe_evaluation",
]
