"""Application orchestration for deterministic universe-level OOS evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any
from uuid import UUID

import pandas as pd

from tw_stock_tool.application.workspace_execution import WorkspaceRunLifecycle
from tw_stock_tool.artifacts import WorkspacePathError
from tw_stock_tool.backtesting.metrics import calculate_buy_hold_return
from tw_stock_tool.backtesting.walk_forward import (
    _parameter_grid,
    _run_strategy_backtest,
    _sort_metric,
    split_windows,
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
    DataSourceRecord,
    RunConfig,
    RunManifest,
)
from tw_stock_tool.utils.config import DEFAULT_INTERVAL, DEFAULT_PERIOD, FEE_RATE, INITIAL_CAPITAL, TAX_RATE


class UniverseQualificationError(RuntimeError):
    """Raised when a universe qualification cannot be evaluated or published."""


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
        if self.strategy not in {"ma_cross", "rsi", "score"}:
            raise ValueError("strategy must be ma_cross, rsi, or score")
        if not isinstance(self.policy, QualificationPolicy):
            raise TypeError("policy must be a QualificationPolicy")
        if not self.symbol_data:
            raise ValueError("symbol_data must contain at least one symbol")
        for symbol in self.symbol_data:
            if not isinstance(symbol, str) or not symbol or symbol.strip() != symbol:
                raise ValueError("symbol_data keys must be clean non-blank strings")
        if self.train_days <= 0 or self.test_days <= 0:
            raise ValueError("train_days and test_days must be greater than 0")
        if self.step_days is not None and self.step_days <= 0:
            raise ValueError("step_days must be greater than 0")
        if not 0 < self.position_size <= 1:
            raise ValueError("position_size must satisfy 0 < value <= 1")
        for name, value in (("fee_rate", self.fee_rate), ("tax_rate", self.tax_rate), ("stress_fee_rate", self.stress_fee_rate), ("stress_tax_rate", self.stress_tax_rate)):
            if value is not None and (type(value) not in (int, float) or not math.isfinite(float(value)) or value < 0):
                raise ValueError(f"{name} must be a finite non-negative number")
        for source_id in self.source_run_ids:
            if not isinstance(source_id, str) or not source_id.strip():
                raise ValueError("source_run_ids must contain clean strings")


@dataclass(frozen=True, slots=True)
class UniverseQualificationResult:
    request: UniverseQualificationRequest
    symbols: tuple[SymbolEvidence, ...]
    qualification: StrategyQualificationResult
    artifact_references: tuple[ArtifactReference, ...] = ()
    manifest: RunManifest | None = None

    @property
    def decision(self) -> str:
        return self.qualification.decision.state


def _as_text(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _clean_frame(symbol: str, frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise ValueError(f"{symbol}: input must be a pandas DataFrame")
    if "Close" not in frame.columns or "Open" not in frame.columns:
        raise ValueError(f"{symbol}: input requires Open and Close columns")
    if len(frame) == 0:
        raise ValueError(f"{symbol}: input is empty")
    return frame.copy()


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
    grid = _parameter_grid(request.strategy, **_parameter_kwargs(request))
    best: tuple[float, dict[str, int], dict[str, Any]] | None = None
    errors: list[str] = []
    for params in grid:
        try:
            result = _run_strategy_backtest(
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
            metric = _sort_metric(result, request.sort_by)
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


def _window_evidence(request: UniverseQualificationRequest, symbol: str, number: int, train: pd.DataFrame, test: pd.DataFrame, benchmark: pd.DataFrame | None) -> WindowEvidence:
    starts = (_as_text(train.index[0]), _as_text(train.index[-1]), _as_text(test.index[0]), _as_text(test.index[-1]))
    try:
        params, train_result = _select_parameters(request, train)
        test_result = _run_strategy_backtest(
            test, request.strategy, params, request.stop_loss_pct, request.take_profit_pct,
            request.max_hold_days, request.position_size, request.initial_capital,
            request.fee_rate, request.tax_rate, request.interval,
        )
        stressed = _run_strategy_backtest(
            test, request.strategy, params, request.stop_loss_pct, request.take_profit_pct,
            request.max_hold_days, request.position_size, request.initial_capital,
            request.stress_fee_rate if request.stress_fee_rate is not None else request.fee_rate * 2,
            request.stress_tax_rate if request.stress_tax_rate is not None else request.tax_rate * 2,
            request.interval,
        )
        benchmark_return = None
        if benchmark is not None:
            benchmark_return = float(calculate_buy_hold_return(benchmark))
        return WindowEvidence(
            symbol, number, *starts, request.strategy, dict(params),
            float(train_result["Total Return %"]), float(test_result["Total Return %"]),
            benchmark_return, float(stressed["Total Return %"]), int(test_result["Trade Count"]),
            len(test), abs(float(test_result["Max Drawdown %"])), True,
        )
    except Exception as exc:
        return WindowEvidence(symbol, number, *starts, request.strategy, None, None, None, None, None, 0, len(test), None, False, "window_evaluation_failed", str(exc))


def _symbol_evidence(request: UniverseQualificationRequest, symbol: str, frame: pd.DataFrame) -> SymbolEvidence:
    try:
        clean = _clean_frame(symbol, frame)
        windows = split_windows(clean, request.train_days, request.test_days, request.step_days or request.test_days)
    except Exception as exc:
        return SymbolEvidence(symbol, (), 0, 0, 0, 0.0, False, "symbol_evaluation_failed", str(exc))
    benchmark = _benchmark_frame(request.benchmark_data, symbol)
    benchmark_windows: dict[int, pd.DataFrame] = {}
    if benchmark is not None:
        try:
            benchmark_windows = {number: test for number, _train, test in split_windows(benchmark, request.train_days, request.test_days, request.step_days or request.test_days)}
        except Exception:
            benchmark_windows = {}
    details = tuple(_window_evidence(request, symbol, number, train, test, benchmark_windows.get(number)) for number, train, test in windows)
    valid = tuple(item for item in details if item.valid)
    return SymbolEvidence(
        symbol, details, len(valid), sum(item.oos_observations for item in valid),
        sum(item.completed_trades for item in valid),
        sum(item.test_return_pct or 0.0 for item in valid) / len(valid) if valid else 0.0,
        bool(valid), None if len(valid) == len(details) else "partial_window_failure",
        None if len(valid) == len(details) else "one or more windows failed",
    )


def evaluate_universe_qualification(request: UniverseQualificationRequest) -> UniverseQualificationResult:
    if not isinstance(request, UniverseQualificationRequest):
        raise TypeError("request must be a UniverseQualificationRequest")
    symbols = tuple(_symbol_evidence(request, symbol, request.symbol_data[symbol]) for symbol in sorted(request.symbol_data))
    valid_symbols = tuple(symbol for symbol in symbols if symbol.evaluated)
    valid_windows = tuple(window for symbol in valid_symbols for window in symbol.windows if window.valid)
    returns = [window.test_return_pct or 0.0 for window in valid_windows]
    stressed = [window.stressed_return_pct or 0.0 for window in valid_windows]
    benchmark_returns = [window.benchmark_return_pct for window in valid_windows if window.benchmark_return_pct is not None]
    all_benchmarks = len(benchmark_returns) == len(valid_windows) and bool(valid_windows)
    total_return = sum(returns) / len(returns) if returns else 0.0
    benchmark_return = sum(benchmark_returns) / len(benchmark_returns) if all_benchmarks else None
    positive_ratio = sum(value > 0 for value in returns) / len(returns) if returns else 0.0
    drawdowns = [window.max_drawdown_pct or 0.0 for window in valid_windows]
    symbol_abs = {symbol.symbol: abs(sum(window.test_return_pct or 0.0 for window in symbol.windows if window.valid)) for symbol in valid_symbols}
    concentration_denominator = sum(symbol_abs.values())
    concentration = max(symbol_abs.values()) / concentration_denominator * 100 if concentration_denominator else 0.0
    parameter_values = [tuple(sorted((key, value) for key, value in (window.parameters or {}).items())) for window in valid_windows]
    metric = QualificationMetricSet(
        evidence_scope="out_of_sample", data_leakage_free=True,
        oos_observations=sum(window.oos_observations for window in valid_windows),
        completed_trades=sum(window.completed_trades for window in valid_windows),
        evaluated_symbols=len(valid_symbols), valid_windows=len(valid_windows),
        benchmark_available=all_benchmarks, total_return_pct=total_return,
        benchmark_return_pct=benchmark_return, cost_stress_pass=bool(stressed) and min(stressed) >= 0.0,
        stressed_return_pct=sum(stressed) / len(stressed) if stressed else None,
        max_drawdown_pct=max(drawdowns) if drawdowns else 0.0,
        positive_window_ratio=positive_ratio, symbol_concentration_pct=concentration,
        parameter_stable=bool(parameter_values) and len(set(parameter_values)) == 1,
        partial_failure_count=sum(1 for symbol in symbols if not symbol.evaluated) + sum(1 for symbol in symbols for window in symbol.windows if not window.valid),
    )
    descriptor = StrategyDescriptor(request.strategy, {"selection": request.sort_by, "train_days": request.train_days, "test_days": request.test_days, "step_days": request.step_days or request.test_days})
    qualification_request = StrategyQualificationRequest(request.evaluation_id, request.created_at, descriptor, metric, request.policy)
    qualification = evaluate_strategy_qualification(qualification_request)
    return UniverseQualificationResult(request, symbols, qualification)


def _json_evidence(result: UniverseQualificationResult) -> str:
    def window(value: WindowEvidence) -> dict[str, Any]:
        return {"symbol": value.symbol, "window": value.window, "train_start": value.train_start, "train_end": value.train_end, "test_start": value.test_start, "test_end": value.test_end, "strategy": value.strategy, "parameters": dict(value.parameters) if value.parameters is not None else None, "train_return_pct": value.train_return_pct, "test_return_pct": value.test_return_pct, "benchmark_return_pct": value.benchmark_return_pct, "stressed_return_pct": value.stressed_return_pct, "completed_trades": value.completed_trades, "oos_observations": value.oos_observations, "max_drawdown_pct": value.max_drawdown_pct, "valid": value.valid, "error_code": value.error_code, "error": value.error}
    payload = {"schema_version": "1.0", "artifact_type": "universe_oos_evidence", "qualification": result.qualification.request.evaluation_id, "symbols": [{"symbol": item.symbol, "valid_windows": item.valid_windows, "oos_observations": item.oos_observations, "completed_trades": item.completed_trades, "total_return_pct": item.total_return_pct, "evaluated": item.evaluated, "error_code": item.error_code, "error": item.error, "windows": [window(entry) for entry in item.windows]} for item in result.symbols]}
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _exclusive_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise WorkspacePathError("publish qualification artifact", path, "existing artifact will not be overwritten") from exc


def publish_universe_qualification(result: UniverseQualificationResult, lifecycle: WorkspaceRunLifecycle) -> UniverseQualificationResult:
    if not isinstance(result, UniverseQualificationResult):
        raise TypeError("result must be a UniverseQualificationResult")
    if not isinstance(lifecycle, WorkspaceRunLifecycle):
        raise TypeError("lifecycle must be a WorkspaceRunLifecycle")
    qualification_path = lifecycle.artifacts_directory / "strategy_qualification.json"
    evidence_path = lifecycle.artifacts_directory / "universe_oos_evidence.json"
    _exclusive_write(qualification_path, export_strategy_qualification_json(result.qualification))
    try:
        _exclusive_write(evidence_path, _json_evidence(result))
    except Exception:
        qualification_path.unlink(missing_ok=True)
        raise
    refs = tuple(sorted((lifecycle.artifact_reference(qualification_path, STRATEGY_QUALIFICATION_ARTIFACT_TYPE, "application/json", STRATEGY_QUALIFICATION_SCHEMA_VERSION), lifecycle.artifact_reference(evidence_path, "universe_oos_evidence", "application/json", "1.0")), key=lambda item: (item.artifact_type, item.path)))
    request = result.request
    source_ids = tuple(sorted(request.source_run_ids))
    options = {"evaluation_id": request.evaluation_id, "source_run_ids": list(source_ids), "artifact_paths": [ref.path for ref in refs]}
    config = RunConfig("universe-oos-evaluation", None, tuple(sorted(request.symbol_data)), request.period, request.interval, True, False, request.strategy, None, request.parameter_options, {"train_days": request.train_days, "test_days": request.test_days, **options}, None, options)
    errors = tuple(f"{item.symbol}:{item.error_code}:{item.error}" for item in result.symbols for entry in item.windows if not entry.valid for _ in [0])
    errors += tuple(f"{item.symbol}:{item.error_code}:{item.error}" for item in result.symbols if not item.evaluated)
    status = "partial" if errors else "success"
    manifest = RunManifest(RUN_MANIFEST_SCHEMA_VERSION, lifecycle.run_id, lifecycle.created_at, "0.4.0", status, lifecycle.normalize_config(config), tuple(DataSourceRecord(symbol, symbol, "universe_input", request.period, request.interval, True, "live", "not_applicable", item.evaluated, None if item.evaluated else item.error) for symbol, item in ((item.symbol, item) for item in result.symbols)), len(result.symbols) - sum(1 for item in result.symbols if not item.evaluated), sum(1 for item in result.symbols if not item.evaluated), 1 if errors else 0, refs, errors, ("partial symbol/window failures are retained as typed evidence",) if errors else ())
    lifecycle.publish(manifest)
    return UniverseQualificationResult(request, result.symbols, result.qualification, refs, manifest)


def run_universe_qualification(request: UniverseQualificationRequest, *, workspace_root: str | Path | None = None, lifecycle: WorkspaceRunLifecycle | None = None) -> UniverseQualificationResult:
    result = evaluate_universe_qualification(request)
    if lifecycle is not None:
        return publish_universe_qualification(result, lifecycle)
    if workspace_root is not None:
        return publish_universe_qualification(result, WorkspaceRunLifecycle.begin(workspace_root, "universe-oos-evaluation"))
    return result


UniverseEvaluationRequest = UniverseQualificationRequest
UniverseEvaluationResult = UniverseQualificationResult
run_universe_evaluation = run_universe_qualification

__all__ = [
    "UniverseQualificationError", "WindowEvidence", "SymbolEvidence", "UniverseQualificationRequest", "UniverseQualificationResult", "UniverseEvaluationRequest", "UniverseEvaluationResult", "evaluate_universe_qualification", "publish_universe_qualification", "run_universe_qualification", "run_universe_evaluation",
]
