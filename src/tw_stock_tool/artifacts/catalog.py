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
    WorkspaceValidationError,
)
from tw_stock_tool.artifacts.workspace import (
    ParsedRunDirectory,
    Workspace,
    _ensure_no_reparse_components,
    _is_reparse_point,
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
        if isinstance(self.code, RunFindingCode):
            code = self.code
        elif type(self.code) is str:
            try:
                code = RunFindingCode(self.code)
            except ValueError as exc:
                raise WorkspaceValidationError("validate finding", None, f"unknown finding code: {self.code!r}") from exc
        else:
            raise WorkspaceValidationError("validate finding", None, "code must be a RunFindingCode or exact str")
        object.__setattr__(self, "code", code)

        if type(self.message) is not str or not self.message.strip() or self.message.strip() != self.message:
            raise WorkspaceValidationError("validate finding", None, "message must be a clean nonblank exact str")
        if not isinstance(self.path, (str, Path)):
            raise WorkspaceValidationError("validate finding", None, "path must be str or Path")
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
        if isinstance(self.health, RunHealth):
            health = self.health
        elif type(self.health) is str:
            try:
                health = RunHealth(self.health)
            except ValueError as exc:
                raise WorkspaceValidationError("validate run entry", None, f"unknown run health: {self.health!r}") from exc
        else:
            raise WorkspaceValidationError("validate run entry", None, "health must be a RunHealth or exact str")
        object.__setattr__(self, "health", health)

        for field_name in ("run_id", "created_at", "workflow", "status", "universe", "tool_version"):
            value = getattr(self, field_name)
            if value is not None and (type(value) is not str or not value.strip() or value.strip() != value):
                raise WorkspaceValidationError("validate run entry", None, f"{field_name} must be None or a clean nonblank exact str")

        if isinstance(self.canonical_symbols, (str, bytes)):
            raise WorkspaceValidationError("validate run entry", None, "canonical_symbols must be an iterable of symbols")
        try:
            canonical_symbols = tuple(self.canonical_symbols)
        except TypeError as exc:
            raise WorkspaceValidationError("validate run entry", None, "canonical_symbols must be iterable") from exc
        for index, symbol in enumerate(canonical_symbols):
            if type(symbol) is not str or not symbol.strip() or symbol.strip() != symbol:
                raise WorkspaceValidationError("validate run entry", None, f"canonical_symbols[{index}] must be a clean nonblank exact str")
        object.__setattr__(self, "canonical_symbols", canonical_symbols)

        try:
            findings = tuple(self.findings)
        except TypeError as exc:
            raise WorkspaceValidationError("validate run entry", None, "findings must be iterable") from exc
        for index, finding in enumerate(findings):
            if not isinstance(finding, RunFinding):
                raise WorkspaceValidationError("validate run entry", None, f"findings[{index}] must be a RunFinding")
        object.__setattr__(self, "findings", findings)

        if type(self.artifact_count) is not int or self.artifact_count < 0:
            raise WorkspaceValidationError("validate run entry", None, "artifact_count must be an exact nonnegative int")

        for field_name in ("run_directory", "manifest_path"):
            value = getattr(self, field_name)
            if not isinstance(value, (str, Path)):
                raise WorkspaceValidationError("validate run entry", None, f"{field_name} must be str or Path")
            object.__setattr__(self, field_name, Path(value))

        if self.manifest is not None:
            from tw_stock_tool.research_run.models import RunManifest

            if not isinstance(self.manifest, RunManifest):
                raise WorkspaceValidationError("validate run entry", None, "manifest must be a RunManifest or None")


@dataclass(frozen=True, slots=True)
class WorkspaceCatalog:
    """Immutable result of one offline Workspace scan."""

    workspace: Workspace
    entries: tuple[WorkspaceRunEntry, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.workspace, Workspace):
            raise WorkspaceValidationError("validate catalog", None, "workspace must be a Workspace")
        try:
            entries = tuple(self.entries)
        except TypeError as exc:
            raise WorkspaceValidationError("validate catalog", None, "entries must be iterable") from exc
        for index, entry in enumerate(entries):
            if not isinstance(entry, WorkspaceRunEntry):
                raise WorkspaceValidationError("validate catalog", None, f"entries[{index}] must be a WorkspaceRunEntry")
        object.__setattr__(self, "entries", entries)

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
    # Serialization exposes schema mismatch only through this stable legacy error text.
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


def _lstat_candidate(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise WorkspaceCatalogError("scan workspace", path, "canonical path cannot be inspected") from exc


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
        if not _YEAR_PATTERN.fullmatch(year_directory.name):
            continue
        year_result = _lstat_candidate(year_directory)
        if year_result is None:
            continue
        if _is_reparse_point(year_result):
            raise WorkspaceCatalogError("scan workspace", year_directory, "canonical year directory is a symlink or reparse point")
        if not stat.S_ISDIR(year_result.st_mode):
            continue
        try:
            _ensure_no_reparse_components(year_directory, "scan workspace")
        except WorkspacePathError as exc:
            raise WorkspaceCatalogError("scan workspace", year_directory, "canonical year directory contains an unsafe path component") from exc
        for month_directory in sorted(_directory_children(year_directory), key=lambda path: path.name):
            if not _MONTH_PATTERN.fullmatch(month_directory.name):
                continue
            month_result = _lstat_candidate(month_directory)
            if month_result is None:
                continue
            if _is_reparse_point(month_result):
                raise WorkspaceCatalogError("scan workspace", month_directory, "canonical month directory is a symlink or reparse point")
            if not stat.S_ISDIR(month_result.st_mode):
                continue
            try:
                _ensure_no_reparse_components(month_directory, "scan workspace")
            except WorkspacePathError as exc:
                raise WorkspaceCatalogError("scan workspace", month_directory, "canonical month directory contains an unsafe path component") from exc
            for run_directory in sorted(_directory_children(month_directory), key=lambda path: path.name):
                parsed = parse_run_directory_name(run_directory.name)
                if parsed is None:
                    continue
                if parsed.year != year_directory.name or parsed.month != month_directory.name:
                    continue
                run_result = _lstat_candidate(run_directory)
                if run_result is None:
                    continue
                manifest_path = run_directory / "manifest.json"
                if _is_reparse_point(run_result):
                    entries.append(
                        _invalid_entry(
                            run_directory,
                            manifest_path,
                            [RunFinding(RunFindingCode.UNSAFE_PATH, "canonical run directory is a symlink or reparse point", run_directory)],
                        )
                    )
                    continue
                if not stat.S_ISDIR(run_result.st_mode):
                    continue
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
