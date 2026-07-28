"""Scan-specific Research Run integration service."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
import importlib.metadata
import math
import os
from pathlib import Path
import re
from typing import Any, TypeAlias
from uuid import uuid4

import pandas as pd

from tw_stock_tool.analysis.analysis import StockAnalysis, build_stock_analysis
from tw_stock_tool.analysis.scanner import ScanConfig, ProgressCallback, scan_stocks
from tw_stock_tool.reports.report import export_stock_ranking
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


class ScanResearchRunError(RuntimeError):
    """Raised when a Scan Research Run cannot complete or persist its manifest."""


_Completion: TypeAlias = tuple[str, str]


class _ScanValidationError(ValueError):
    pass


def _new_run_id() -> str:
    return str(uuid4())


def _created_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")



def _tool_version() -> str:
    pyproject = Path(__file__).resolve().parents[2].parent / "pyproject.toml"
    try:
        installed = importlib.metadata.version("tw-stock-tool")
    except importlib.metadata.PackageNotFoundError:
        installed = None
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        if installed is not None:
            return installed
        raise ScanResearchRunError("Unable to determine tw-stock-tool package version")
    match = re.search(r'(?ms)^\[project\].*?^version\s*=\s*["\']([^"\']+)["\']', text)
    if match is None:
        if installed is not None:
            return installed
        raise ScanResearchRunError("Unable to determine tw-stock-tool package version")
    source_version = match.group(1)
    return source_version if installed != source_version else installed

def _error_message(exc: Exception) -> str:
    return str(exc).strip() or type(exc).__name__


def _clean_string(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise _ScanValidationError(f"{name} must be a clean exact string")
    return value


def _path_value(name: str, value: object) -> tuple[Path, str]:
    try:
        raw = os.fspath(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise _ScanValidationError(f"{name} must be a nonblank path-like value") from exc
    if type(raw) is not str or not raw.strip() or "\x00" in raw:
        raise _ScanValidationError(f"{name} must be a nonblank path-like value")
    try:
        path = Path(raw)
    except (TypeError, ValueError) as exc:
        raise _ScanValidationError(f"{name} is not a valid path") from exc
    return path, path.as_posix()


def _json_safe(name: str, value: object) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise _ScanValidationError(f"{name} must contain finite values")
        return
    if type(value) in (list, tuple):
        for index, item in enumerate(value):
            _json_safe(f"{name}[{index}]", item)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                raise _ScanValidationError(f"{name} mapping keys must be exact strings")
            _json_safe(f"{name}.{key}", item)
        return
    raise _ScanValidationError(f"{name} contains unsupported value {type(value).__name__}")


def _validate_and_build_config(
    symbol_requests: tuple[tuple[str, str], ...],
    universe: str | None,
    config: ScanConfig,
    output_dir: str | Path,
    manifest_path: str | Path | None,
    sheet_by_signal: bool,
    log_errors: bool,
    progress_callback: ProgressCallback | None,
    market_data_loader: MarketDataLoader | None,
) -> tuple[dict[str, str], Path, Path, RunConfig]:
    if type(symbol_requests) is not tuple or not symbol_requests:
        raise _ScanValidationError("symbol_requests must be a non-empty exact tuple")

    canonical_by_requested: dict[str, str] = {}
    canonical_symbols: list[str] = []
    for index, pair in enumerate(symbol_requests):
        if type(pair) is not tuple or len(pair) != 2:
            raise _ScanValidationError(f"symbol_requests[{index}] must be an exact two-item tuple")
        requested, canonical = pair
        requested = _clean_string(f"symbol_requests[{index}].requested_symbol", requested)
        canonical = _clean_string(f"symbol_requests[{index}].canonical_symbol", canonical)
        if requested in canonical_by_requested:
            raise _ScanValidationError(f"Duplicate requested symbol: {requested}")
        if canonical in canonical_symbols:
            raise _ScanValidationError(f"Duplicate canonical symbol: {canonical}")
        canonical_by_requested[requested] = canonical
        canonical_symbols.append(canonical)

    if universe is not None:
        _clean_string("universe", universe)
    if not isinstance(config, ScanConfig):
        raise _ScanValidationError("config must be a ScanConfig")
    if config.analysis_provider is not None:
        raise _ScanValidationError("config.analysis_provider must be None")
    if type(sheet_by_signal) is not bool or type(log_errors) is not bool:
        raise _ScanValidationError("sheet_by_signal and log_errors must be exact bool values")
    if progress_callback is not None and not callable(progress_callback):
        raise _ScanValidationError("progress_callback must be callable or None")
    if market_data_loader is not None and not callable(market_data_loader):
        raise _ScanValidationError("market_data_loader must be callable or None")

    output_path, output_text = _path_value("output_dir", output_dir)
    manifest_path_obj = output_path / "scan_run_manifest.json" if manifest_path is None else _path_value("manifest_path", manifest_path)[0]
    manifest_text = manifest_path_obj.as_posix()
    signals = None if config.signals is None else list(config.signals)
    workflow_options = {
        "max_workers": config.max_workers,
        "min_score": config.min_score,
        "min_volume_ratio": config.min_volume_ratio,
        "min_close": config.min_close,
        "max_close": config.max_close,
        "signals": signals,
        "sort_by": config.sort_by,
        "top": config.top,
        "errors_only": config.errors_only,
        "sheet_by_signal": sheet_by_signal,
        "log_errors": log_errors,
        "output_dir": output_text,
        "manifest_path": manifest_text,
    }
    _json_safe("workflow_options", workflow_options)
    try:
        run_config = RunConfig(
            workflow="scan",
            universe=universe,
            canonical_symbols=tuple(canonical_symbols),
            period=config.period,
            interval=config.interval,
            auto_adjust=config.auto_adjust,
            force_refresh=config.force_refresh,
            strategy=None,
            backtest=None,
            parameter_sweep=None,
            walk_forward=None,
            ml=None,
            workflow_options=workflow_options,
        )
    except Exception as exc:
        raise _ScanValidationError(str(exc)) from exc
    return canonical_by_requested, output_path, manifest_path_obj, run_config


def _artifact(path: object, artifact_type: str, media_type: str) -> ArtifactReference:
    return ArtifactReference(artifact_type, Path(os.fspath(path)).as_posix(), media_type, None)


def _ranking_errors(ranking_df: pd.DataFrame) -> tuple[str, ...]:
    rows = ranking_df[ranking_df["Status"] != "OK"].to_dict(orient="records")
    rows.sort(key=lambda row: str(row.get("Stock", "")))
    errors: list[str] = []
    for row in rows:
        error = row.get("Error")
        if error is None or (isinstance(error, float) and math.isnan(error)):
            continue
        message = str(error).strip()
        stock = str(row.get("Stock", "")).strip()
        if message and stock:
            errors.append(f"{stock}: {message}")
    return tuple(dict.fromkeys(errors))


def _limitations(config: ScanConfig, completed: int, data_sources: int) -> tuple[str, ...]:
    limitations: list[str] = []
    if any(
        value is not None and value is not False and value != () and value != []
        for value in (
            config.min_score,
            config.min_volume_ratio,
            config.min_close,
            config.max_close,
            config.signals,
            config.top,
            config.errors_only,
        )
    ):
        limitations.append("The scan domain result may omit successful symbols because scan filters or output limits were applied.")
    if data_sources < completed:
        limitations.append("Some failed scan requests did not produce a valid DataSourceRecord.")
    return tuple(limitations)


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
    limitations: tuple[str, ...],
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
        limitations=limitations,
    )


def _write_manifest(path: Path, manifest: RunManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(export_run_manifest_json(manifest))


def _raise_stage_failure(
    manifest: RunManifest,
    manifest_path: Path,
    original: Exception,
) -> None:
    try:
        _write_manifest(manifest_path, manifest)
    except Exception as manifest_error:
        raise ScanResearchRunError(
            f"{_error_message(original)}; manifest: {_error_message(manifest_error)}"
        ) from original
    raise ScanResearchRunError(_error_message(original)) from original


def run_scan_research(
    symbol_requests: tuple[tuple[str, str], ...],
    *,
    universe: str | None,
    config: ScanConfig,
    output_dir: str | Path,
    manifest_path: str | Path | None = None,
    sheet_by_signal: bool = False,
    log_errors: bool = False,
    progress_callback: ProgressCallback | None = None,
    market_data_loader: MarketDataLoader | None = None,
) -> ResearchRunResult:
    try:
        canonical_by_requested, output_path, manifest_file, run_config = _validate_and_build_config(
            symbol_requests,
            universe,
            config,
            output_dir,
            manifest_path,
            sheet_by_signal,
            log_errors,
            progress_callback,
            market_data_loader,
        )
    except Exception as exc:
        if isinstance(exc, ScanResearchRunError):
            raise
        raise ScanResearchRunError(_error_message(exc)) from exc

    run_id = _new_run_id()
    created_at = _created_at()
    tool_version = _tool_version()
    loader = market_data_loader or build_legacy_market_data_loader(canonical_by_requested)
    context = ResearchRunContext(loader)
    completions: list[_Completion] = []

    def progress_wrapper(completed: int, total: int, stock_id: str, status: str) -> None:
        completions.append((stock_id, status))
        if progress_callback is not None:
            progress_callback(completed, total, stock_id, status)

    def analysis_provider(requested_symbol: str) -> StockAnalysis:
        canonical_symbol = canonical_by_requested[requested_symbol]
        raw_df = context.load_market_data(
            canonical_symbol=canonical_symbol,
            requested_symbol=requested_symbol,
            period=config.period,
            interval=config.interval,
            auto_adjust=config.auto_adjust,
            force_refresh=config.force_refresh,
        )
        return build_stock_analysis(
            stock_id=requested_symbol,
            symbol=canonical_symbol,
            raw_df=raw_df,
        )

    scanner_config = replace(config, analysis_provider=analysis_provider)
    try:
        ranking_df = scan_stocks(
            [requested for requested, _ in symbol_requests],
            config=scanner_config,
            progress_callback=progress_wrapper,
        )
    except Exception as exc:
        manifest = _make_manifest(
            run_id=run_id,
            created_at=created_at,
            tool_version=tool_version,
            config=run_config,
            context=context,
            status="failure",
            success_count=0,
            failure_count=1,
            partial_count=0,
            artifacts=(),
            errors=(f"scan: {_error_message(exc)}",),
            limitations=_limitations(config, len(completions), len(context.data_sources)),
        )
        _raise_stage_failure(manifest, manifest_file, exc)

    success_count = sum(status == "OK" for _, status in completions)
    failure_count = sum(status != "OK" for _, status in completions)
    ranking_errors = _ranking_errors(ranking_df)
    base_errors = ranking_errors
    artifacts: tuple[ArtifactReference, ...] = ()

    try:
        paths = export_stock_ranking(
            ranking_df,
            output_path,
            sheet_by_signal=sheet_by_signal,
        )
        artifacts = (
            _artifact(paths["excel"], "scan_ranking_excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            _artifact(paths["csv"], "scan_ranking_csv", "text/csv"),
            _artifact(paths["html"], "scan_ranking_html", "text/html"),
        )
    except Exception as exc:
        has_success = success_count > 0
        status = "partial" if has_success else "failure"
        manifest = _make_manifest(
            run_id=run_id,
            created_at=created_at,
            tool_version=tool_version,
            config=run_config,
            context=context,
            status=status,
            success_count=success_count if has_success else 0,
            failure_count=failure_count if has_success else max(failure_count, 1),
            partial_count=1 if has_success else 0,
            artifacts=(),
            errors=tuple(dict.fromkeys((*base_errors, f"ranking_export: {_error_message(exc)}"))),
            limitations=_limitations(config, len(completions), len(context.data_sources)),
        )
        _raise_stage_failure(manifest, manifest_file, exc)

    if log_errors and ranking_errors:
        try:
            output_path.mkdir(parents=True, exist_ok=True)
            with (output_path / "scan_errors.log").open("w", encoding="utf-8", newline="\n") as handle:
                handle.write("\n".join(ranking_errors) + "\n")
            artifacts += (_artifact(output_path / "scan_errors.log", "scan_error_log", "text/plain"),)
        except Exception as exc:
            has_success = success_count > 0
            manifest = _make_manifest(
                run_id=run_id,
                created_at=created_at,
                tool_version=tool_version,
                config=run_config,
                context=context,
                status="partial" if has_success else "failure",
                success_count=success_count if has_success else 0,
                failure_count=failure_count if has_success else max(failure_count, 1),
                partial_count=1 if has_success else 0,
                artifacts=artifacts,
                errors=tuple(dict.fromkeys((*base_errors, f"error_log: {_error_message(exc)}"))),
                limitations=_limitations(config, len(completions), len(context.data_sources)),
            )
            _raise_stage_failure(manifest, manifest_file, exc)

    if success_count and failure_count:
        status = "partial"
    elif success_count:
        status = "success"
    else:
        status = "failure"
    manifest = _make_manifest(
        run_id=run_id,
        created_at=created_at,
        tool_version=tool_version,
        config=run_config,
        context=context,
        status=status,
        success_count=success_count,
        failure_count=failure_count,
        partial_count=0,
        artifacts=artifacts,
        errors=base_errors or (("scan: symbol load failed",) if status == "failure" else ()),
        limitations=_limitations(config, len(completions), len(context.data_sources)),
    )
    try:
        _write_manifest(manifest_file, manifest)
    except Exception as exc:
        raise ScanResearchRunError(f"manifest: {_error_message(exc)}") from exc
    return ResearchRunResult(
        manifest=manifest,
        domain_result=ranking_df,
        generated_artifacts=manifest.artifacts,
    )