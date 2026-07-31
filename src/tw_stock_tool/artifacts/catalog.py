"""Deterministic, offline catalog scanning for canonical Workspace runs."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import os
from pathlib import Path
import stat
import re
from typing import TYPE_CHECKING

from tw_stock_tool.artifacts.errors import (
    WorkspaceCatalogError,
    WorkspaceError,
    WorkspacePathError,
    WorkspaceManifestError,
)
from tw_stock_tool.artifacts.workspace import (
    ParsedRunDirectory,
    Workspace,
    _ensure_no_reparse_components,
    parse_run_directory_name,
    read_manifest,
    resolve_artifact_path,
)

if TYPE_CHECKING:
    from tw_stock_tool.research_run.models import RunManifest


class RunHealth(str, Enum):
    """Catalog health summary for a single run."""

    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"


class RunFindingCode(str, Enum):
    """Stable first-version catalog finding codes."""

    MISSING_MANIFEST = "missing_manifest"
    INVALID_MANIFEST = "invalid_manifest"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    UNSAFE_PATH = "unsafe_path"
    MISSING_ARTIFACT = "missing_artifact"
    DUPLICATE_RUN_ID = "duplicate_run_id"


@dataclass(frozen=True, slots=True)
class RunFinding:
    """One deterministic health finding attached to a run entry."""

    code: RunFindingCode
    message: str
    path: Path

    def __post_init__(self) -> None:
        if isinstance(self.code, str) and not isinstance(self.code, RunFindingCode):
            object.__setattr__(self, "code", RunFindingCode(self.code))
        object.__setattr__(self, "path", Path(self.path))


@dataclass(frozen=True, slots=True)
class WorkspaceRunEntry:
    """Immutable run-level catalog result, including invalid runs."""

    run_id: str | None
    created_at: str | None
    workflow: str | None
    status: str | None
    canonical_symbols: tuple[str, ...]
    universe: str | None
    tool_version: str | None
    artifact_count: int
    run_directory: Path
    manifest_path: Path
    health: RunHealth
    findings: tuple[RunFinding, ...]
    manifest: RunManifest | None

    def __post_init__(self) -> None:
        if isinstance(self.health, str) and not isinstance(self.health, RunHealth):
            object.__setattr__(self, "health", RunHealth(self.health))
        if type(self.canonical_symbols) is not tuple:
            object.__setattr__(self, "canonical_symbols", tuple(self.canonical_symbols))
        if type(self.findings) is not tuple:
            object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "run_directory", Path(self.run_directory))
        object.__setattr__(self, "manifest_path", Path(self.manifest_path))


@dataclass(frozen=True, slots=True)
class WorkspaceCatalog:
    """Immutable result of one offline Workspace scan."""

    workspace: Workspace
    entries: tuple[WorkspaceRunEntry, ...]

    @property
    def runs(self) -> tuple[WorkspaceRunEntry, ...]:
        return self.entries


_FINDING_PRIORITY = {
    RunFindingCode.MISSING_MANIFEST: 10,
    RunFindingCode.INVALID_MANIFEST: 20,
    RunFindingCode.UNSUPPORTED_SCHEMA: 30,
    RunFindingCode.UNSAFE_PATH: 40,
    RunFindingCode.MISSING_ARTIFACT: 50,
    RunFindingCode.DUPLICATE_RUN_ID: 60,
}
_YEAR_PATTERN = re.compile(r"^\d{4}$")
_MONTH_PATTERN = re.compile(r"^(?:0[1-9]|1[0-2])$")


def _ordered_findings(findings: list[RunFinding]) -> tuple[RunFinding, ...]:
    unique: dict[tuple[RunFindingCode, str, str], RunFinding] = {}
    for finding in findings:
        key = (finding.code, finding.message, os.path.normcase(os.path.normpath(os.fspath(finding.path))))
        unique[key] = finding
    return tuple(
        sorted(
            unique.values(),
            key=lambda finding: (
                _FINDING_PRIORITY[finding.code],
                finding.code.value,
                os.path.normcase(os.path.normpath(os.fspath(finding.path))),
                finding.message,
            ),
        )
    )


def _health(findings: tuple[RunFinding, ...]) -> RunHealth:
    if not findings:
        return RunHealth.VALID
    if all(finding.code is RunFindingCode.MISSING_ARTIFACT for finding in findings):
        return RunHealth.WARNING
    return RunHealth.INVALID


def _invalid_entry(
    run_directory: Path,
    manifest_path: Path,
    findings: list[RunFinding],
) -> WorkspaceRunEntry:
    ordered = _ordered_findings(findings)
    return WorkspaceRunEntry(
        run_id=None,
        created_at=None,
        workflow=None,
        status=None,
        canonical_symbols=(),
        universe=None,
        tool_version=None,
        artifact_count=0,
        run_directory=run_directory,
        manifest_path=manifest_path,
        health=RunHealth.INVALID,
        findings=ordered,
        manifest=None,
    )


def _manifest_error_code(error: WorkspaceManifestError) -> RunFindingCode:
    cause = error.__cause__
    if cause is not None and "unsupported schema version" in str(cause).lower():
        return RunFindingCode.UNSUPPORTED_SCHEMA
    return RunFindingCode.INVALID_MANIFEST


def _consistency_findings(
    parsed: ParsedRunDirectory,
    manifest: RunManifest,
    run_directory: Path,
) -> list[RunFinding]:
    findings: list[RunFinding] = []
    manifest_prefix = manifest.run_id.replace("-", "")[:8]
    if manifest_prefix != parsed.run_id_prefix:
        findings.append(
            RunFinding(
                RunFindingCode.INVALID_MANIFEST,
                "manifest run_id prefix does not match canonical run directory",
                run_directory,
            )
        )
    expected_timestamp = parsed.created_at
    if manifest.created_at != expected_timestamp:
        findings.append(
            RunFinding(
                RunFindingCode.INVALID_MANIFEST,
                "manifest created_at does not match canonical run directory timestamp",
                run_directory,
            )
        )
    if manifest.config.workflow != parsed.workflow_slug:
        findings.append(
            RunFinding(
                RunFindingCode.INVALID_MANIFEST,
                "manifest workflow does not match canonical workflow slug",
                run_directory,
            )
        )
    return findings


def _artifact_findings(manifest: RunManifest, run_directory: Path) -> list[RunFinding]:
    findings: list[RunFinding] = []
    for artifact in manifest.artifacts:
        try:
            artifact_path = resolve_artifact_path(run_directory, artifact.path)
        except WorkspacePathError as exc:
            findings.append(RunFinding(RunFindingCode.UNSAFE_PATH, str(exc), run_directory / artifact.path))
            continue
        try:
            result = artifact_path.lstat()
        except FileNotFoundError:
            findings.append(RunFinding(RunFindingCode.MISSING_ARTIFACT, "artifact does not exist", artifact_path))
            continue
        except OSError as exc:
            findings.append(RunFinding(RunFindingCode.MISSING_ARTIFACT, f"artifact cannot be inspected: {exc}", artifact_path))
            continue
        if not stat.S_ISREG(result.st_mode):
            findings.append(RunFinding(RunFindingCode.MISSING_ARTIFACT, "artifact path is not a regular file", artifact_path))
    return findings


def _read_run_entry(parsed: ParsedRunDirectory, run_directory: Path) -> WorkspaceRunEntry:
    manifest_path = run_directory / "manifest.json"
    if not os.path.lexists(manifest_path):
        return _invalid_entry(
            run_directory,
            manifest_path,
            [RunFinding(RunFindingCode.MISSING_MANIFEST, "canonical manifest is missing", manifest_path)],
        )

    try:
        manifest = read_manifest(manifest_path)
    except WorkspacePathError as exc:
        return _invalid_entry(
            run_directory,
            manifest_path,
            [RunFinding(RunFindingCode.UNSAFE_PATH, str(exc), manifest_path)],
        )
    except WorkspaceManifestError as exc:
        code = _manifest_error_code(exc)
        return _invalid_entry(
            run_directory,
            manifest_path,
            [RunFinding(code, str(exc), manifest_path)],
        )

    findings = _consistency_findings(parsed, manifest, run_directory)
    findings.extend(_artifact_findings(manifest, run_directory))
    ordered = _ordered_findings(findings)
    return WorkspaceRunEntry(
        run_id=manifest.run_id,
        created_at=manifest.created_at,
        workflow=manifest.config.workflow,
        status=manifest.status,
        canonical_symbols=manifest.config.canonical_symbols,
        universe=manifest.config.universe,
        tool_version=manifest.tool_version,
        artifact_count=len(manifest.artifacts),
        run_directory=run_directory,
        manifest_path=manifest_path,
        health=_health(ordered),
        findings=ordered,
        manifest=manifest,
    )


def _directory_children(path: Path) -> list[Path]:
    try:
        return list(path.iterdir())
    except OSError as exc:
        raise WorkspaceCatalogError("scan workspace", path, "workspace directory cannot be listed") from exc


def _is_real_directory(path: Path) -> bool:
    try:
        result = path.lstat()
    except OSError:
        return False
    return stat.S_ISDIR(result.st_mode)


def _ordered_entries(entries: list[WorkspaceRunEntry]) -> tuple[WorkspaceRunEntry, ...]:
    # ISO UTC timestamps sort lexicographically; avoid filesystem mtime entirely.
    readable = [entry for entry in entries if entry.health is not RunHealth.INVALID]
    invalid = [entry for entry in entries if entry.health is RunHealth.INVALID]
    readable.sort(key=lambda entry: (-(int(entry.created_at.replace("-", "").replace("T", "").replace(":", "").replace("Z", "")) if entry.created_at else 0), entry.run_id or "", os.path.normcase(os.path.normpath(os.fspath(entry.run_directory)))))
    invalid.sort(key=lambda entry: os.path.normcase(os.path.normpath(os.fspath(entry.run_directory))))
    return tuple(readable + invalid)


def _mark_duplicate_run_ids(entries: list[WorkspaceRunEntry]) -> list[WorkspaceRunEntry]:
    by_run_id: dict[str, list[int]] = {}
    for index, entry in enumerate(entries):
        if entry.manifest is not None and entry.run_id is not None:
            by_run_id.setdefault(entry.run_id, []).append(index)
    for indexes in by_run_id.values():
        if len(indexes) < 2:
            continue
        for index in indexes:
            entry = entries[index]
            findings = list(entry.findings)
            findings.append(
                RunFinding(
                    RunFindingCode.DUPLICATE_RUN_ID,
                    "full run_id appears in multiple canonical run directories",
                    entry.run_directory,
                )
            )
            ordered = _ordered_findings(findings)
            entries[index] = replace(entry, health=RunHealth.INVALID, findings=ordered)
    return entries


def scan_workspace(workspace: Workspace) -> WorkspaceCatalog:
    """Scan only canonical Workspace run directories without modifying files."""
    if not isinstance(workspace, Workspace):
        raise WorkspaceCatalogError("scan workspace", None, "workspace must be a Workspace")
    try:
        _ensure_no_reparse_components(workspace.root, "scan workspace")
        _ensure_no_reparse_components(workspace.runs_directory, "scan workspace")
    except WorkspaceError as exc:
        raise WorkspaceCatalogError("scan workspace", workspace.root, "workspace contains an unsafe path component") from exc

    entries: list[WorkspaceRunEntry] = []
    for year_directory in sorted(_directory_children(workspace.runs_directory), key=lambda path: path.name):
        if not _YEAR_PATTERN.fullmatch(year_directory.name) or not _is_real_directory(year_directory):
            continue
        try:
            _ensure_no_reparse_components(year_directory, "scan workspace")
        except WorkspacePathError:
            continue
        for month_directory in sorted(_directory_children(year_directory), key=lambda path: path.name):
            if not _MONTH_PATTERN.fullmatch(month_directory.name) or not _is_real_directory(month_directory):
                continue
            try:
                _ensure_no_reparse_components(month_directory, "scan workspace")
            except WorkspacePathError:
                continue
            for run_directory in sorted(_directory_children(month_directory), key=lambda path: path.name):
                parsed = parse_run_directory_name(run_directory.name)
                if parsed is None:
                    continue
                if parsed.year != year_directory.name or parsed.month != month_directory.name:
                    continue
                if not _is_real_directory(run_directory):
                    continue
                manifest_path = run_directory / "manifest.json"
                try:
                    _ensure_no_reparse_components(run_directory, "scan workspace")
                except WorkspacePathError as exc:
                    entries.append(
                        _invalid_entry(
                            run_directory,
                            manifest_path,
                            [RunFinding(RunFindingCode.UNSAFE_PATH, str(exc), run_directory)],
                        )
                    )
                    continue
                entries.append(_read_run_entry(parsed, run_directory))

    return WorkspaceCatalog(workspace=workspace, entries=_ordered_entries(_mark_duplicate_run_ids(entries)))


scan_catalog = scan_workspace


__all__ = [
    "RunFinding",
    "RunFindingCode",
    "RunHealth",
    "WorkspaceCatalog",
    "WorkspaceRunEntry",
    "scan_catalog",
    "scan_workspace",
]
