"""Application-owned Workspace adapters for the supported Research Runs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import os
from pathlib import Path
from typing import Any

from tw_stock_tool.application.research_run import (
    BacktestRunRequest,
    DailyRunRequest,
    ScanRunRequest,
)
from tw_stock_tool.application.workspace_execution import WorkspaceRunLifecycle
from tw_stock_tool.artifacts import read_manifest
from tw_stock_tool.artifacts.errors import WorkspaceError
from tw_stock_tool.research_run import backtest as backtest_workflow
from tw_stock_tool.research_run import daily as daily_workflow
from tw_stock_tool.research_run import scan as scan_workflow
from tw_stock_tool.research_run.models import (
    RUN_MANIFEST_SCHEMA_VERSION,
    ResearchRunResult,
    RunConfig,
    RunManifest,
)


_PROVISIONAL_MANIFEST = ".research-run-manifest.json"


def _absolute(value: str | Path) -> Path:
    return Path(os.path.normcase(os.path.normpath(os.path.abspath(os.fspath(value)))))


def _is_implicit_output_dir(value: str | Path) -> bool:
    candidate = _absolute(value)
    return candidate in {_absolute("output"), _absolute(Path.cwd() / "output")}


def _reject_legacy_output(name: str, value: object) -> None:
    if value is not None:
        raise ValueError(f"{name} conflicts with --workspace")


def _validate_workspace_common(output_dir: str | Path, manifest_path: str | Path | None) -> None:
    if not _is_implicit_output_dir(output_dir):
        raise ValueError("--output-dir conflicts with --workspace")
    _reject_legacy_output("--manifest-path", manifest_path)


def _portable_requested_path(name: str, value: str | Path | None, filename: str) -> str | None:
    if value is None:
        return None
    normalized = Path(value).as_posix()
    if normalized not in (filename, f"artifacts/{filename}"):
        raise ValueError(f"--{name} conflicts with --workspace")
    return filename


def _preflight_scan(request: ScanRunRequest, progress_callback: Callable[..., None] | None, market_data_loader: Callable[..., Any] | None) -> RunConfig:
    return scan_workflow._validate_and_build_config(  # type: ignore[attr-defined]
        tuple((symbol.requested_symbol, symbol.canonical_symbol) for symbol in request.symbols),
        request.universe,
        request.config,
        ".",
        None,
        request.sheet_by_signal,
        request.log_errors,
        progress_callback,
        market_data_loader,
    )[-1]


def _preflight_daily(request: DailyRunRequest, status_callback: Callable[[str], None] | None, market_data_loader: Callable[..., Any] | None) -> RunConfig:
    return daily_workflow._validate_and_build_config(  # type: ignore[attr-defined]
        tuple((symbol.requested_symbol, symbol.canonical_symbol) for symbol in request.symbols),
        request.universe,
        request.config,
        ".",
        request.markdown_path,
        request.json_path,
        None,
        request.json_overwrite,
        status_callback,
        market_data_loader,
    )[-1]


def _preflight_backtest(request: BacktestRunRequest, stage_callback: Callable[[str], None] | None, market_data_loader: Callable[..., Any] | None) -> RunConfig:
    return backtest_workflow._validate_and_build_config(  # type: ignore[attr-defined]
        (request.symbol.requested_symbol, request.symbol.canonical_symbol),
        request.strategy,
        request.period,
        request.interval,
        request.auto_adjust,
        request.force_refresh,
        request.strategy_parameters,
        request.backtest_parameters,
        ".",
        request.markdown_path,
        request.excel_path,
        None,
        market_data_loader,
        stage_callback,
    )[-1]


def _convert_manifest(source: RunManifest, lifecycle: WorkspaceRunLifecycle) -> RunManifest:
    artifacts = tuple(
        lifecycle.artifact_reference(
            artifact.path,
            artifact.artifact_type,
            artifact.media_type,
            artifact.schema_version,
        )
        for artifact in source.artifacts
    )
    return RunManifest(
        schema_version=RUN_MANIFEST_SCHEMA_VERSION,
        run_id=lifecycle.run_id,
        created_at=lifecycle.created_at,
        tool_version=source.tool_version,
        status=source.status,
        config=lifecycle.normalize_config(source.config),
        data_sources=source.data_sources,
        success_count=source.success_count,
        failure_count=source.failure_count,
        partial_count=source.partial_count,
        artifacts=artifacts,
        errors=source.errors,
        limitations=source.limitations,
    )


def _tool_version() -> str:
    try:
        return scan_workflow._tool_version()  # type: ignore[attr-defined]
    except Exception:
        return "unknown"


def _failure_manifest(config: RunConfig, lifecycle: WorkspaceRunLifecycle, error: Exception) -> RunManifest:
    options = dict(config.workflow_options)
    for name, value in tuple(options.items()):
        if value is None:
            continue
        if name == "output_dir":
            options[name] = "artifacts"
        elif name == "manifest_path":
            options[name] = "manifest.json"
        elif name.endswith("_path"):
            options[name] = Path(str(value)).name
    portable_config = replace(config, workflow_options=options)
    return RunManifest(
        schema_version=RUN_MANIFEST_SCHEMA_VERSION,
        run_id=lifecycle.run_id,
        created_at=lifecycle.created_at,
        tool_version=_tool_version(),
        status="failure",
        config=portable_config,
        data_sources=(),
        success_count=0,
        failure_count=1,
        partial_count=0,
        artifacts=(),
        errors=(f"{lifecycle.run_directory.workflow_slug}: {str(error).strip() or type(error).__name__}",),
        limitations=(),
    )


def _read_provisional(path: Path) -> RunManifest | None:
    if not path.exists():
        return None
    return read_manifest(path)


def _cleanup_provisional(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _publish_failure(
    lifecycle: WorkspaceRunLifecycle,
    config: RunConfig,
    error: Exception,
    provisional: Path,
    *,
    preserve_provisional: bool,
) -> None:
    if preserve_provisional:
        try:
            source = _read_provisional(provisional)
            manifest = (
                _convert_manifest(source, lifecycle)
                if source is not None and source.status in {"failure", "partial"}
                else _failure_manifest(config, lifecycle, error)
            )
        except Exception:
            manifest = _failure_manifest(config, lifecycle, error)
    else:
        manifest = _failure_manifest(config, lifecycle, error)
    try:
        lifecycle.publish(manifest)
    except Exception as publication_error:
        raise RuntimeError(
            f"{str(error).strip() or type(error).__name__}; manifest: "
            f"{str(publication_error).strip() or type(publication_error).__name__}"
        ) from error


def _run_managed(
    *,
    workflow: str,
    workspace: str | Path,
    config: RunConfig,
    runner: Callable[[WorkspaceRunLifecycle, Path], ResearchRunResult],
) -> ResearchRunResult:
    lifecycle = WorkspaceRunLifecycle.begin(workspace, workflow)
    provisional = lifecycle.run_directory.path / _PROVISIONAL_MANIFEST
    try:
        result = runner(lifecycle, provisional)
    except Exception as original:
        try:
            _publish_failure(lifecycle, config, original, provisional, preserve_provisional=True)
        finally:
            _cleanup_provisional(provisional)
        raise

    try:
        source = _read_provisional(provisional)
        if source is None:
            raise WorkspaceError("publish Workspace manifest", provisional, "workflow did not produce a provisional manifest")
        manifest = _convert_manifest(source, lifecycle)
        published = lifecycle.publish(manifest)
    except Exception as original:
        try:
            if lifecycle.manifest_path.exists():
                raise
            _publish_failure(lifecycle, config, original, provisional, preserve_provisional=False)
        finally:
            _cleanup_provisional(provisional)
        raise
    finally:
        _cleanup_provisional(provisional)
    return ResearchRunResult(published, result.domain_result, published.artifacts)

def run_scan_workspace(
    request: ScanRunRequest,
    workspace: str | Path,
    *,
    progress_callback: Callable[..., None] | None = None,
    market_data_loader: Callable[..., Any] | None = None,
) -> ResearchRunResult:
    _validate_workspace_common(request.output_dir, request.manifest_path)
    config = _preflight_scan(request, progress_callback, market_data_loader)

    def runner(lifecycle: WorkspaceRunLifecycle, provisional: Path) -> ResearchRunResult:
        return scan_workflow.run_scan_research(
            tuple((symbol.requested_symbol, symbol.canonical_symbol) for symbol in request.symbols),
            universe=request.universe,
            config=request.config,
            output_dir=lifecycle.artifacts_directory,
            manifest_path=provisional,
            sheet_by_signal=request.sheet_by_signal,
            log_errors=request.log_errors,
            progress_callback=progress_callback,
            market_data_loader=market_data_loader,
        )

    return _run_managed(workflow="scan", workspace=workspace, config=config, runner=runner)


def run_daily_workspace(
    request: DailyRunRequest,
    workspace: str | Path,
    *,
    status_callback: Callable[[str], None] | None = None,
    market_data_loader: Callable[..., Any] | None = None,
) -> ResearchRunResult:
    _validate_workspace_common(request.output_dir, request.manifest_path)
    markdown = _portable_requested_path("output-md", request.markdown_path, "daily_report.md")
    json_path = _portable_requested_path("output-json", request.json_path, "daily_report.json")
    excel = request.config.output_excel
    if excel not in (None, "", "daily_report.xlsx", "artifacts/daily_report.xlsx"):
        raise ValueError("--output-excel conflicts with --workspace")
    config = _preflight_daily(request, status_callback, market_data_loader)

    def runner(lifecycle: WorkspaceRunLifecycle, provisional: Path) -> ResearchRunResult:
        managed_config = replace(
            request.config,
            output_excel=None if excel is None else str(lifecycle.artifacts_directory / "daily_report.xlsx"),
        )
        return daily_workflow.run_daily_report_research(
            tuple((symbol.requested_symbol, symbol.canonical_symbol) for symbol in request.symbols),
            universe=request.universe,
            config=managed_config,
            output_dir=lifecycle.artifacts_directory,
            markdown_path=lifecycle.artifacts_directory / "daily_report.md",
            json_path=None if json_path is None else lifecycle.artifacts_directory / "daily_report.json",
            manifest_path=provisional,
            json_overwrite=request.json_overwrite,
            status_callback=status_callback,
            market_data_loader=market_data_loader,
        )

    return _run_managed(workflow="daily", workspace=workspace, config=config, runner=runner)


def run_backtest_workspace(
    request: BacktestRunRequest,
    workspace: str | Path,
    *,
    stage_callback: Callable[[str], None] | None = None,
    market_data_loader: Callable[..., Any] | None = None,
) -> ResearchRunResult:
    _validate_workspace_common(request.output_dir, request.manifest_path)
    markdown = _portable_requested_path("output-md", request.markdown_path, "backtest_report.md")
    excel = _portable_requested_path("output-excel", request.excel_path, "backtest_report.xlsx")
    config = _preflight_backtest(request, stage_callback, market_data_loader)

    def runner(lifecycle: WorkspaceRunLifecycle, provisional: Path) -> ResearchRunResult:
        artifacts = lifecycle.artifacts_directory
        return backtest_workflow.run_backtest_research(
            (request.symbol.requested_symbol, request.symbol.canonical_symbol),
            strategy=request.strategy,
            period=request.period,
            interval=request.interval,
            auto_adjust=request.auto_adjust,
            force_refresh=request.force_refresh,
            strategy_parameters=request.strategy_parameters,
            backtest_parameters=request.backtest_parameters,
            output_dir=artifacts,
            markdown_path=None if markdown is None else artifacts / "backtest_report.md",
            excel_path=None if excel is None else artifacts / "backtest_report.xlsx",
            manifest_path=provisional,
            stage_callback=stage_callback,
            market_data_loader=market_data_loader,
        )

    return _run_managed(workflow="backtest", workspace=workspace, config=config, runner=runner)


__all__ = ["run_backtest_workspace", "run_daily_workspace", "run_scan_workspace"]
