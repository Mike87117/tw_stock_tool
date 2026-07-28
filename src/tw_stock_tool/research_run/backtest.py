"""Backtest-specific Research Run integration service."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import importlib.metadata
import inspect
import math
import os
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from tw_stock_tool.analysis.analysis import build_stock_analysis
from tw_stock_tool.backtesting.backtest import run_backtest
from tw_stock_tool.backtesting.strategies import STRATEGIES
from tw_stock_tool.reports.backtest_report import (
    export_backtest_report_excel,
    export_backtest_report_markdown,
)
from tw_stock_tool.research_run.context import ResearchRunContext
from tw_stock_tool.research_run.market_data_adapter import (
    MarketDataLoader,
    build_legacy_market_data_loader,
)
from tw_stock_tool.research_run.models import (
    RUN_MANIFEST_SCHEMA_VERSION,
    ArtifactReference,
    ResearchRunResult,
    RunConfig,
    RunManifest,
)
from tw_stock_tool.research_run.serialization import export_run_manifest_json
from tw_stock_tool.utils.config import (
    DEFAULT_AUTO_ADJUST,
    DEFAULT_INTERVAL,
    DEFAULT_PERIOD,
    VALID_INTERVALS,
    VALID_PERIODS,
)


class BacktestResearchRunError(RuntimeError):
    """Raised when a Backtest Research Run cannot complete."""


class _BacktestValidationError(ValueError):
    pass


def _new_run_id() -> str:
    return str(uuid4())


def _created_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _source_tree_tool_version() -> str:
    pyproject = Path(__file__).resolve().parents[2].parent / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError as exc:
        raise BacktestResearchRunError("Unable to determine tw-stock-tool package version") from exc
    match = re.search(r'(?ms)^\[project\].*?^version\s*=\s*["\']([^"\']+)["\']', text)
    if match is None or not match.group(1).strip():
        raise BacktestResearchRunError("Unable to determine tw-stock-tool package version")
    return match.group(1)


def _tool_version() -> str:
    try:
        return importlib.metadata.version("tw-stock-tool")
    except importlib.metadata.PackageNotFoundError:
        return _source_tree_tool_version()


def _error_message(exc: Exception) -> str:
    return str(exc).strip() or type(exc).__name__


def _clean_string(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise _BacktestValidationError(f"{name} must be a clean exact string")
    return value


def _path_value(name: str, value: object) -> tuple[Path, str]:
    try:
        raw = os.fspath(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise _BacktestValidationError(f"{name} must be a nonblank path-like value") from exc
    if type(raw) is not str or not raw.strip() or "\x00" in raw:
        raise _BacktestValidationError(f"{name} must be a nonblank path-like value")
    try:
        path = Path(raw)
    except (TypeError, ValueError) as exc:
        raise _BacktestValidationError(f"{name} is not a valid path") from exc
    return path, path.as_posix()


def _json_safe(name: str, value: object) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise _BacktestValidationError(f"{name} must contain finite values")
        return
    if type(value) in (list, tuple):
        for index, item in enumerate(value):
            _json_safe(f"{name}[{index}]", item)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str or not key or key != key.strip():
                raise _BacktestValidationError(f"{name} mapping keys must be clean exact strings")
            _json_safe(f"{name}.{key}", item)
        return
    raise _BacktestValidationError(f"{name} contains unsupported value {type(value).__name__}")


def _resolve_strategy(strategy: str) -> str:
    if strategy in STRATEGIES:
        return strategy
    alias = f"{strategy}_strategy"
    if alias in STRATEGIES:
        return alias
    raise _BacktestValidationError(f"Unknown strategy: {strategy}")


def _production_backtest_defaults() -> dict[str, Any]:
    parameters = inspect.signature(run_backtest).parameters
    return {
        name: parameter.default
        for name, parameter in parameters.items()
        if name != "df" and parameter.default is not inspect.Parameter.empty
    }


_BACKTEST_DEFAULTS = _production_backtest_defaults()
_BACKTEST_PARAMETER_NAMES = frozenset(_BACKTEST_DEFAULTS)


def _validate_and_build_config(
    symbol_request: tuple[str, str],
    strategy: str,
    period: str,
    interval: str,
    auto_adjust: bool,
    force_refresh: bool,
    strategy_parameters: Mapping[str, Any] | None,
    backtest_parameters: Mapping[str, Any] | None,
    output_dir: str | Path,
    markdown_path: str | Path | None,
    excel_path: str | Path | None,
    manifest_path: str | Path | None,
    market_data_loader: MarketDataLoader | None,
) -> tuple[
    str,
    str,
    dict[str, Any],
    dict[str, Any],
    Path,
    Path | None,
    Path | None,
    Path,
    RunConfig,
]:
    if type(symbol_request) is not tuple or len(symbol_request) != 2:
        raise _BacktestValidationError("symbol_request must be an exact two-item tuple")
    requested_symbol = _clean_string("symbol_request.requested_symbol", symbol_request[0])
    canonical_symbol = _clean_string("symbol_request.canonical_symbol", symbol_request[1])
    strategy_input = _clean_string("strategy", strategy)
    resolved_strategy = _resolve_strategy(strategy_input)

    period = _clean_string("period", period)
    if period not in VALID_PERIODS:
        raise _BacktestValidationError(f"Unsupported period: {period!r}")
    interval = _clean_string("interval", interval)
    if interval not in VALID_INTERVALS:
        raise _BacktestValidationError(f"Unsupported interval: {interval!r}")
    if type(auto_adjust) is not bool:
        raise _BacktestValidationError("auto_adjust must be an exact bool")
    if type(force_refresh) is not bool:
        raise _BacktestValidationError("force_refresh must be an exact bool")
    if market_data_loader is not None and not callable(market_data_loader):
        raise _BacktestValidationError("market_data_loader must be callable or None")

    if strategy_parameters is not None and not isinstance(strategy_parameters, Mapping):
        raise _BacktestValidationError("strategy_parameters must be a Mapping or None")
    if backtest_parameters is not None and not isinstance(backtest_parameters, Mapping):
        raise _BacktestValidationError("backtest_parameters must be a Mapping or None")
    strategy_snapshot = {} if strategy_parameters is None else dict(strategy_parameters)
    backtest_overrides = {} if backtest_parameters is None else dict(backtest_parameters)
    _json_safe("strategy_parameters", strategy_snapshot)
    _json_safe("backtest_parameters", backtest_overrides)

    unknown = sorted(set(backtest_overrides) - _BACKTEST_PARAMETER_NAMES)
    if unknown:
        raise _BacktestValidationError(f"Unsupported backtest parameter(s): {', '.join(unknown)}")
    if "interval" in backtest_overrides and backtest_overrides["interval"] != interval:
        raise _BacktestValidationError("backtest_parameters.interval must equal interval")
    resolved_backtest = dict(_BACKTEST_DEFAULTS)
    resolved_backtest.update(backtest_overrides)
    resolved_backtest["interval"] = interval
    _json_safe("resolved_backtest_parameters", resolved_backtest)

    output_path, output_text = _path_value("output_dir", output_dir)
    manifest_file = output_path / "backtest_run_manifest.json" if manifest_path is None else _path_value("manifest_path", manifest_path)[0]
    markdown_file = None if markdown_path is None else _path_value("markdown_path", markdown_path)[0]
    excel_file = None if excel_path is None else _path_value("excel_path", excel_path)[0]
    manifest_text = manifest_file.as_posix()
    workflow_options = {
        "strategy_parameters": strategy_snapshot,
        "output_dir": output_text,
        "markdown_path": None if markdown_file is None else markdown_file.as_posix(),
        "excel_path": None if excel_file is None else excel_file.as_posix(),
        "manifest_path": manifest_text,
    }
    _json_safe("workflow_options", workflow_options)
    try:
        run_config = RunConfig(
            workflow="backtest",
            universe=None,
            canonical_symbols=(canonical_symbol,),
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            force_refresh=force_refresh,
            strategy=resolved_strategy,
            backtest=resolved_backtest,
            parameter_sweep=None,
            walk_forward=None,
            ml=None,
            workflow_options=workflow_options,
        )
    except Exception as exc:
        raise _BacktestValidationError(str(exc)) from exc
    return (
        requested_symbol,
        canonical_symbol,
        strategy_snapshot,
        resolved_backtest,
        output_path,
        markdown_file,
        excel_file,
        manifest_file,
        run_config,
    )


def _artifact(path: object, artifact_type: str, media_type: str) -> ArtifactReference:
    return ArtifactReference(artifact_type, Path(os.fspath(path)).as_posix(), media_type, None)


def _make_manifest(
    *,
    run_id: str,
    created_at: str,
    tool_version: str,
    config: RunConfig,
    context: ResearchRunContext,
    status: str,
    success_count: int,
    failure_count: int,
    partial_count: int,
    artifacts: tuple[ArtifactReference, ...],
    errors: tuple[str, ...],
) -> RunManifest:
    return RunManifest(
        schema_version=RUN_MANIFEST_SCHEMA_VERSION,
        run_id=run_id,
        created_at=created_at,
        tool_version=tool_version,
        status=status,  # type: ignore[arg-type]
        config=config,
        data_sources=context.data_sources,
        success_count=success_count,
        failure_count=failure_count,
        partial_count=partial_count,
        artifacts=artifacts,
        errors=errors,
        limitations=(),
    )


def _write_manifest(path: Path, manifest: RunManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(export_run_manifest_json(manifest))


def _dedupe(errors: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(errors))


def _raise_failure(
    *,
    stage: str,
    original: Exception,
    run_id: str,
    created_at: str,
    tool_version: str,
    config: RunConfig,
    context: ResearchRunContext,
    manifest_path: Path,
) -> None:
    error = f"{stage}: {_error_message(original)}"
    manifest = _make_manifest(
        run_id=run_id,
        created_at=created_at,
        tool_version=tool_version,
        config=config,
        context=context,
        status="failure",
        success_count=0,
        failure_count=1,
        partial_count=0,
        artifacts=(),
        errors=(error,),
    )
    try:
        _write_manifest(manifest_path, manifest)
    except Exception as manifest_error:
        raise BacktestResearchRunError(f"manifest: {_error_message(manifest_error)}") from original
    raise BacktestResearchRunError(error) from original


def _normalize_result(
    raw_result: dict[str, Any],
    strategy_df: Any,
    requested_symbol: str,
    strategy: str,
    strategy_parameters: dict[str, Any],
    backtest_parameters: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(raw_result, dict):
        raise TypeError(f"run_backtest must return a dict, got {type(raw_result).__name__}")
    result = raw_result.copy()
    result["Stock"] = requested_symbol
    result["Strategy"] = strategy
    start_date = result.get("Start Date")
    end_date = result.get("End Date")
    if start_date is None:
        start_date = strategy_df.index[0] if not strategy_df.empty else "N/A"
    if end_date is None:
        end_date = strategy_df.index[-1] if not strategy_df.empty else "N/A"
    result["Start Date"] = start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else str(start_date)
    result["End Date"] = end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else str(end_date)
    result["Parameters"] = {
        "strategy": strategy_parameters,
        "backtest": backtest_parameters,
    }
    return result


def run_backtest_research(
    symbol_request: tuple[str, str],
    *,
    strategy: str,
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    auto_adjust: bool = DEFAULT_AUTO_ADJUST,
    force_refresh: bool = False,
    strategy_parameters: Mapping[str, Any] | None = None,
    backtest_parameters: Mapping[str, Any] | None = None,
    output_dir: str | Path,
    markdown_path: str | Path | None = None,
    excel_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    market_data_loader: MarketDataLoader | None = None,
) -> ResearchRunResult:
    try:
        (
            requested_symbol,
            canonical_symbol,
            strategy_snapshot,
            resolved_backtest,
            output_path,
            markdown_file,
            excel_file,
            manifest_file,
            run_config,
        ) = _validate_and_build_config(
            symbol_request,
            strategy,
            period,
            interval,
            auto_adjust,
            force_refresh,
            strategy_parameters,
            backtest_parameters,
            output_dir,
            markdown_path,
            excel_path,
            manifest_path,
            market_data_loader,
        )
    except Exception as exc:
        if isinstance(exc, BacktestResearchRunError):
            raise
        raise BacktestResearchRunError(_error_message(exc)) from exc

    run_id = _new_run_id()
    created_at = _created_at()
    tool_version = _tool_version()
    loader = market_data_loader or build_legacy_market_data_loader({requested_symbol: canonical_symbol})
    context = ResearchRunContext(loader)

    try:
        raw_df = context.load_market_data(
            canonical_symbol=canonical_symbol,
            requested_symbol=requested_symbol,
            period=run_config.period,
            interval=run_config.interval,
            auto_adjust=run_config.auto_adjust,
            force_refresh=run_config.force_refresh,
        )
    except Exception as exc:
        _raise_failure(
            stage="market_data",
            original=exc,
            run_id=run_id,
            created_at=created_at,
            tool_version=tool_version,
            config=run_config,
            context=context,
            manifest_path=manifest_file,
        )

    try:
        analysis = build_stock_analysis(
            stock_id=requested_symbol,
            symbol=canonical_symbol,
            raw_df=raw_df,
        )
    except Exception as exc:
        _raise_failure(
            stage="analysis",
            original=exc,
            run_id=run_id,
            created_at=created_at,
            tool_version=tool_version,
            config=run_config,
            context=context,
            manifest_path=manifest_file,
        )

    try:
        strategy_df = STRATEGIES[run_config.strategy](analysis.indicator_df, **strategy_snapshot)  # type: ignore[index]
    except Exception as exc:
        _raise_failure(
            stage="strategy",
            original=exc,
            run_id=run_id,
            created_at=created_at,
            tool_version=tool_version,
            config=run_config,
            context=context,
            manifest_path=manifest_file,
        )

    try:
        raw_result = run_backtest(strategy_df, **resolved_backtest)
        domain_result = _normalize_result(
            raw_result,
            strategy_df,
            requested_symbol,
            strategy,
            strategy_snapshot,
            resolved_backtest,
        )
    except Exception as exc:
        _raise_failure(
            stage="backtest",
            original=exc,
            run_id=run_id,
            created_at=created_at,
            tool_version=tool_version,
            config=run_config,
            context=context,
            manifest_path=manifest_file,
        )

    artifacts: list[ArtifactReference] = []
    export_errors: list[str] = []
    export_causes: list[Exception] = []
    if markdown_file is not None:
        try:
            generated = export_backtest_report_markdown(domain_result, markdown_file)
            artifacts.append(_artifact(generated, "backtest_report_markdown", "text/markdown"))
        except Exception as exc:
            export_errors.append(f"markdown_export: {_error_message(exc)}")
            export_causes.append(exc)
    if excel_file is not None:
        try:
            generated = export_backtest_report_excel(domain_result, excel_file)
            artifacts.append(
                _artifact(
                    generated,
                    "backtest_report_excel",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            )
        except Exception as exc:
            export_errors.append(f"excel_export: {_error_message(exc)}")
            export_causes.append(exc)

    if export_errors:
        manifest = _make_manifest(
            run_id=run_id,
            created_at=created_at,
            tool_version=tool_version,
            config=run_config,
            context=context,
            status="partial",
            success_count=1,
            failure_count=0,
            partial_count=1,
            artifacts=tuple(artifacts),
            errors=_dedupe(export_errors),
        )
        try:
            _write_manifest(manifest_file, manifest)
        except Exception as exc:
            cause = export_causes[0] if export_causes else exc
            raise BacktestResearchRunError(f"manifest: {_error_message(exc)}") from cause
        raise BacktestResearchRunError("; ".join(_dedupe(export_errors))) from export_causes[0]

    manifest = _make_manifest(
        run_id=run_id,
        created_at=created_at,
        tool_version=tool_version,
        config=run_config,
        context=context,
        status="success",
        success_count=1,
        failure_count=0,
        partial_count=0,
        artifacts=tuple(artifacts),
        errors=(),
    )
    try:
        _write_manifest(manifest_file, manifest)
    except Exception as exc:
        raise BacktestResearchRunError(f"manifest: {_error_message(exc)}") from exc
    return ResearchRunResult(
        manifest=manifest,
        domain_result=domain_result,
        generated_artifacts=manifest.artifacts,
    )
