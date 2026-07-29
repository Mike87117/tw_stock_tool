"""Daily Report Research Run integration service."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
import inspect
import importlib.metadata
import math
import os
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

import pandas as pd

from tw_stock_tool.analysis.analysis import StockAnalysis, build_stock_analysis
from tw_stock_tool.backtesting.parameter_sweep import (
    ma_cross_parameter_grid,
    rsi_parameter_grid,
    score_parameter_grid,
)
from tw_stock_tool.backtesting.strategies import STRATEGIES
from tw_stock_tool.reports.daily_pipeline import (
    DailyPipelineConfig,
    DailyPipelineResult,
    run_daily_research_pipeline,
    validate_daily_pipeline_config,
)
from tw_stock_tool.reports.daily_report import export_daily_report
from tw_stock_tool.reports.daily_report_export_files import export_daily_report_markdown_file
from tw_stock_tool.reports.daily_report_serialization_files import export_daily_report_json_file
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
from tw_stock_tool.utils.config import OUTPUT_DIR, VALID_INTERVALS, VALID_PERIODS


class DailyReportResearchRunError(RuntimeError):
    """Raised when a Daily Report Research Run cannot complete."""


class _DailyValidationError(ValueError):
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
        raise DailyReportResearchRunError(
            "Unable to determine tw-stock-tool package version"
        ) from exc
    match = re.search(r'(?ms)^\[project\].*?^version\s*=\s*["\']([^"\']+)["\']', text)
    if match is None or not match.group(1).strip():
        raise DailyReportResearchRunError(
            "Unable to determine tw-stock-tool package version"
        )
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
        raise _DailyValidationError(f"{name} must be a clean exact string")
    return value


def _path_value(name: str, value: object) -> tuple[Path, str]:
    try:
        raw = os.fspath(value)
    except TypeError as exc:
        raise _DailyValidationError(f"{name} must be a nonblank path-like value") from exc
    if type(raw) is not str or not raw.strip() or "\x00" in raw:
        raise _DailyValidationError(f"{name} must be a nonblank path-like value")
    try:
        path = Path(raw)
    except (TypeError, ValueError) as exc:
        raise _DailyValidationError(f"{name} is not a valid path") from exc
    return path, path.as_posix()


def _json_safe(name: str, value: object) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise _DailyValidationError(f"{name} must contain finite values")
        return
    if type(value) in (list, tuple):
        for index, item in enumerate(value):
            _json_safe(f"{name}[{index}]", item)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str or not key or key != key.strip():
                raise _DailyValidationError(
                    f"{name} mapping keys must be clean exact strings"
                )
            _json_safe(f"{name}.{key}", item)
        return
    raise _DailyValidationError(
        f"{name} contains unsupported value {type(value).__name__}"
    )


def _effective_excel_path(output_excel: object) -> str | None:
    if output_excel is None:
        return None
    if output_excel == "":
        return (OUTPUT_DIR / "daily_report.xlsx").as_posix()
    return _path_value("config.output_excel", output_excel)[1]


def _resolve_validation_strategy_parameters(strategy: str) -> dict[str, Any]:
    resolved_name = f"{strategy}_strategy"
    try:
        signature = inspect.signature(STRATEGIES[resolved_name])
    except (KeyError, TypeError, ValueError) as exc:
        raise _DailyValidationError(
            f"Unable to inspect validation strategy parameters for {strategy}"
        ) from exc

    resolved: dict[str, Any] = {}
    for name, parameter in signature.parameters.items():
        if name == "df":
            continue
        if parameter.default is inspect.Parameter.empty:
            raise _DailyValidationError(
                f"Validation strategy parameter {name} has no resolved default"
            )
        resolved[name] = parameter.default
    _json_safe("validation_strategy_parameters", resolved)
    return resolved


def _resolve_validation_parameter_grid(strategy: str) -> list[dict[str, int]]:
    if strategy == "ma_cross":
        grid = ma_cross_parameter_grid()
    elif strategy == "rsi":
        grid = rsi_parameter_grid()
    elif strategy == "score":
        grid = score_parameter_grid()
    elif strategy == "macd":
        grid = []
    else:
        raise _DailyValidationError(f"Unsupported validation strategy: {strategy}")
    snapshot = [dict(parameters) for parameters in grid]
    _json_safe("validation_parameter_grid", snapshot)
    return snapshot


def _validate_and_build_config(
    symbol_requests: tuple[tuple[str, str], ...],
    universe: str | None,
    config: DailyPipelineConfig,
    output_dir: str | Path,
    markdown_path: str | Path | None,
    json_path: str | Path | None,
    manifest_path: str | Path | None,
    json_overwrite: bool,
    status_callback: Callable[[str], None] | None,
    market_data_loader: MarketDataLoader | None,
) -> tuple[
    dict[str, str],
    list[str],
    Path,
    Path,
    Path | None,
    Path,
    DailyPipelineConfig,
    RunConfig,
]:
    if type(symbol_requests) is not tuple or not symbol_requests:
        raise _DailyValidationError("symbol_requests must be a non-empty exact tuple")

    canonical_by_requested: dict[str, str] = {}
    canonical_symbols: list[str] = []
    requested_symbols: list[str] = []
    for index, pair in enumerate(symbol_requests):
        if type(pair) is not tuple or len(pair) != 2:
            raise _DailyValidationError(
                f"symbol_requests[{index}] must be an exact two-item tuple"
            )
        requested = _clean_string(
            f"symbol_requests[{index}].requested_symbol",
            pair[0],
        )
        canonical = _clean_string(
            f"symbol_requests[{index}].canonical_symbol",
            pair[1],
        )
        if requested in canonical_by_requested:
            raise _DailyValidationError(f"Duplicate requested symbol: {requested}")
        if canonical in canonical_symbols:
            raise _DailyValidationError(f"Duplicate canonical symbol: {canonical}")
        canonical_by_requested[requested] = canonical
        requested_symbols.append(requested)
        canonical_symbols.append(canonical)

    if universe is not None:
        universe = _clean_string("universe", universe)
    if not isinstance(config, DailyPipelineConfig):
        raise _DailyValidationError("config must be a DailyPipelineConfig")
    try:
        validate_daily_pipeline_config(config)
    except Exception as exc:
        raise _DailyValidationError(str(exc)) from exc

    if type(config.period) is not str or config.period not in VALID_PERIODS:
        raise _DailyValidationError(f"Unsupported period: {config.period!r}")
    if type(config.interval) is not str or config.interval not in VALID_INTERVALS:
        raise _DailyValidationError(f"Unsupported interval: {config.interval!r}")
    for name in ("auto_adjust", "force_refresh", "progress"):
        if type(getattr(config, name)) is not bool:
            raise _DailyValidationError(f"{name} must be an exact bool")
    if config.top is not None and type(config.top) is not int:
        raise _DailyValidationError("top must be an exact int or None")
    if config.report_date is not None and type(config.report_date) is not str:
        raise _DailyValidationError("report_date must be an exact str or None")
    if status_callback is not None and not callable(status_callback):
        raise _DailyValidationError("status_callback must be callable or None")
    if market_data_loader is not None and not callable(market_data_loader):
        raise _DailyValidationError("market_data_loader must be callable or None")
    if type(json_overwrite) is not bool:
        raise _DailyValidationError("json_overwrite must be an exact bool")

    output_path, output_text = _path_value("output_dir", output_dir)
    markdown_file = (
        output_path / "daily_report.md"
        if markdown_path is None
        else _path_value("markdown_path", markdown_path)[0]
    )
    json_file = None if json_path is None else _path_value("json_path", json_path)[0]
    manifest_file = (
        output_path / "daily_report_run_manifest.json"
        if manifest_path is None
        else _path_value("manifest_path", manifest_path)[0]
    )
    resolved_report_date = (
        config.report_date
        if config.report_date is not None
        else datetime.now().strftime("%Y-%m-%d")
    )
    pipeline_config = replace(config, report_date=resolved_report_date, output_excel=None)
    resolved_strategy_parameters = _resolve_validation_strategy_parameters(
        config.validation_strategy
    )
    resolved_parameter_grid = _resolve_validation_parameter_grid(
        config.validation_strategy
    )
    backtest = {
        "enabled": config.validate_top > 0,
        "top": config.validate_top,
        "strategy_parameters": resolved_strategy_parameters,
        "initial_capital": config.validation_initial_capital,
        "fee_rate": config.validation_fee_rate,
        "tax_rate": config.validation_tax_rate,
        "position_size": config.validation_position_size,
    }
    parameter_sweep = {
        "enabled": config.parameter_sweep_top > 0,
        "top": config.parameter_sweep_top,
        "sort_by": config.parameter_sweep_sort_by,
        "parameter_grid": (
            [dict(parameters) for parameters in resolved_parameter_grid]
            if config.parameter_sweep_top > 0
            else []
        ),
    }
    walk_forward = {
        "enabled": config.walk_forward_top > 0,
        "top": config.walk_forward_top,
        "train_days": config.walk_forward_train_days,
        "test_days": config.walk_forward_test_days,
        "step_days": (
            config.walk_forward_step_days
            if config.walk_forward_step_days is not None
            else config.walk_forward_test_days
        ),
        "sort_by": config.walk_forward_sort_by,
        "parameter_grid": (
            [dict(parameters) for parameters in resolved_parameter_grid]
            if config.walk_forward_top > 0
            else []
        ),
    }
    workflow_options = {
        "signals": list(config.signals),
        "min_score": config.min_score,
        "top": config.top,
        "progress": config.progress,
        "report_date": resolved_report_date,
        "output_dir": output_text,
        "markdown_path": markdown_file.as_posix(),
        "json_path": None if json_file is None else json_file.as_posix(),
        "excel_path": _effective_excel_path(config.output_excel),
        "manifest_path": manifest_file.as_posix(),
        "json_overwrite": json_overwrite,
    }
    for name, value in (
        ("backtest", backtest),
        ("parameter_sweep", parameter_sweep),
        ("walk_forward", walk_forward),
        ("workflow_options", workflow_options),
    ):
        _json_safe(name, value)
    try:
        run_config = RunConfig(
            workflow="daily",
            universe=universe,
            canonical_symbols=tuple(canonical_symbols),
            period=config.period,
            interval=config.interval,
            auto_adjust=config.auto_adjust,
            force_refresh=config.force_refresh,
            strategy=config.validation_strategy,
            backtest=backtest,
            parameter_sweep=parameter_sweep,
            walk_forward=walk_forward,
            ml=None,
            workflow_options=workflow_options,
        )
    except Exception as exc:
        raise _DailyValidationError(str(exc)) from exc
    return (
        canonical_by_requested,
        requested_symbols,
        output_path,
        markdown_file,
        json_file,
        manifest_file,
        pipeline_config,
        run_config,
    )


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return type(missing) is bool and missing


def _text(value: object, fallback: str) -> str:
    if _is_missing(value):
        return fallback
    text = str(value).strip()
    return text or fallback


def _stage_errors(frame: pd.DataFrame | None, stage: str) -> list[str]:
    if frame is None or frame.empty:
        return []
    errors = []
    for _, row in frame.iterrows():
        status = _text(row.get("Status"), "FAILURE").upper()
        if status == "OK":
            continue
        stock = _text(row.get("Stock"), "Unknown")
        message = _text(row.get("Error"), status)
        errors.append(f"{stage}: {stock}: {message}")
    return errors


def _domain_snapshot(result: DailyPipelineResult) -> tuple[str, int, int, int, tuple[str, ...]]:
    summary = result.report_data.get("Pipeline Run Summary", {})
    success_count = sum(int(summary.get(key, 0)) for key in (
        "Scan OK", "Backtest OK", "Parameter Sweep OK", "Walk Forward OK",
    ))
    failure_count = sum(int(summary.get(key, 0)) for key in (
        "Scan Failed", "Backtest Failed", "Parameter Sweep Failed", "Walk Forward Failed",
    ))
    partial_count = int(summary.get("Parameter Sweep Partial", 0)) + int(
        summary.get("Walk Forward Partial", 0)
    )
    errors = []
    for frame, stage in (
        (result.ranking_df, "scan"),
        (result.backtest_highlights, "backtest"),
        (result.parameter_sweep_highlights, "parameter_sweep"),
        (result.walk_forward_highlights, "walk_forward"),
    ):
        errors.extend(_stage_errors(frame, stage))
    errors = list(dict.fromkeys(errors))
    if success_count == 0 and failure_count == 0 and partial_count == 0:
        return "failure", 0, 1, 0, tuple(errors or ["daily_pipeline: no stage outcomes recorded"])
    if failure_count == 0 and partial_count == 0:
        status = "success"
    elif success_count == 0 and partial_count == 0 and failure_count > 0:
        status = "failure"
    else:
        status = "partial"
    if status == "failure" and not errors:
        errors = ["daily_pipeline: stage failure"]
    return status, success_count, failure_count, partial_count, tuple(errors)


def _artifact(path: object, artifact_type: str, media_type: str, schema_version: int | str | None = None) -> ArtifactReference:
    return ArtifactReference(
        artifact_type=artifact_type,
        path=Path(os.fspath(path)).as_posix(),
        media_type=media_type,
        schema_version=schema_version,
    )


def _make_manifest(*, run_id: str, created_at: str, tool_version: str, config: RunConfig,
                   context: ResearchRunContext, status: str, success_count: int,
                   failure_count: int, partial_count: int, artifacts: tuple[ArtifactReference, ...],
                   errors: tuple[str, ...], limitations: tuple[str, ...]) -> RunManifest:
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
        limitations=limitations,
    )


def _write_manifest(path: Path, manifest: RunManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(export_run_manifest_json(manifest))


def _unique_texts(values: object) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _write_failure_manifest(*, manifest_file: Path, manifest: RunManifest, original: Exception) -> None:
    try:
        _write_manifest(manifest_file, manifest)
    except Exception as manifest_error:
        raise DailyReportResearchRunError(f"manifest: {_error_message(manifest_error)}") from original
    raise DailyReportResearchRunError(_error_message(original)) from original


def run_daily_report_research(
    symbol_requests: tuple[tuple[str, str], ...],
    *,
    universe: str | None,
    config: DailyPipelineConfig,
    output_dir: str | Path,
    markdown_path: str | Path | None = None,
    json_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    json_overwrite: bool = False,
    status_callback: Callable[[str], None] | None = None,
    market_data_loader: MarketDataLoader | None = None,
) -> ResearchRunResult:
    try:
        (
            canonical_by_requested, requested_symbols, _output_path, markdown_file,
            json_file, manifest_file, pipeline_config, run_config,
        ) = _validate_and_build_config(
            symbol_requests, universe, config, output_dir, markdown_path, json_path,
            manifest_path, json_overwrite, status_callback, market_data_loader,
        )
    except Exception as exc:
        if isinstance(exc, DailyReportResearchRunError):
            raise
        raise DailyReportResearchRunError(_error_message(exc)) from exc

    run_id = _new_run_id()
    created_at = _created_at()
    tool_version = _tool_version()
    loader = market_data_loader or build_legacy_market_data_loader(canonical_by_requested)
    context = ResearchRunContext(loader)

    def analysis_provider(requested_symbol: str) -> StockAnalysis:
        canonical_symbol = canonical_by_requested[requested_symbol]
        raw_df = context.load_market_data(
            canonical_symbol=canonical_symbol,
            requested_symbol=requested_symbol,
            period=pipeline_config.period,
            interval=pipeline_config.interval,
            auto_adjust=pipeline_config.auto_adjust,
            force_refresh=pipeline_config.force_refresh,
        )
        return build_stock_analysis(stock_id=requested_symbol, symbol=canonical_symbol, raw_df=raw_df)

    try:
        domain_result = run_daily_research_pipeline(
            requested_symbols, pipeline_config, analysis_provider=analysis_provider,
            status_callback=status_callback,
        )
    except Exception as exc:
        manifest = _make_manifest(
            run_id=run_id, created_at=created_at, tool_version=tool_version,
            config=run_config, context=context, status="failure",
            success_count=0, failure_count=1, partial_count=0, artifacts=(),
            errors=(f"daily_pipeline: {_error_message(exc)}",), limitations=(),
        )
        _write_failure_manifest(manifest_file=manifest_file, manifest=manifest, original=exc)

    status, success_count, failure_count, partial_count, domain_errors = _domain_snapshot(domain_result)
    limitations = _unique_texts(domain_result.data_limitations)
    artifacts = []
    export_errors = []
    export_causes = []

    try:
        generated = export_daily_report_markdown_file(domain_result.report_data, markdown_file, overwrite=True)
        artifacts.append(_artifact(generated, "daily_report_markdown", "text/markdown"))
    except Exception as exc:
        export_errors.append(f"markdown_export: {_error_message(exc)}")
        export_causes.append(exc)

    if json_file is not None:
        try:
            generated = export_daily_report_json_file(domain_result.report_data, json_file, overwrite=json_overwrite)
            artifacts.append(_artifact(generated, "daily_report_json", "application/json", 1))
        except Exception as exc:
            export_errors.append(f"json_export: {_error_message(exc)}")
            export_causes.append(exc)

    if config.output_excel is not None:
        try:
            generated = export_daily_report(
                domain_result.summary_df, domain_result.candidates_df,
                domain_result.ranking_df, config.output_excel,
            )
            artifacts.append(_artifact(
                generated, "daily_report_excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ))
        except Exception as exc:
            export_errors.append(f"excel_export: {_error_message(exc)}")
            export_causes.append(exc)

    errors = tuple(dict.fromkeys((*domain_errors, *export_errors)))
    if export_errors:
        if status == "failure":
            final_status, final_success, final_failure, final_partial = "failure", 0, max(failure_count, 1), 0
        else:
            final_status, final_success, final_failure, final_partial = "partial", success_count, failure_count, max(partial_count, 1)
    else:
        final_status, final_success, final_failure, final_partial = status, success_count, failure_count, partial_count

    manifest = _make_manifest(
        run_id=run_id, created_at=created_at, tool_version=tool_version,
        config=run_config, context=context, status=final_status,
        success_count=final_success, failure_count=final_failure, partial_count=final_partial,
        artifacts=tuple(artifacts), errors=errors, limitations=limitations,
    )
    try:
        _write_manifest(manifest_file, manifest)
    except Exception as exc:
        cause = export_causes[0] if export_causes else exc
        raise DailyReportResearchRunError(f"manifest: {_error_message(exc)}") from cause
    if export_errors:
        raise DailyReportResearchRunError("; ".join(errors)) from export_causes[0]
    return ResearchRunResult(
        manifest=manifest,
        domain_result=domain_result,
        generated_artifacts=manifest.artifacts,
    )
