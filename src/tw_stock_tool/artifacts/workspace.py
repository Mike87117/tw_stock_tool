"""Offline, filesystem-backed Workspace and run-directory primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import ntpath
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import tempfile
from typing import TYPE_CHECKING, Final
from uuid import UUID

from tw_stock_tool.artifacts.errors import (
    WorkspaceCollisionError,
    WorkspaceError,
    WorkspaceManifestError,
    WorkspacePathError,
    WorkspaceValidationError,
)

if TYPE_CHECKING:
    from tw_stock_tool.artifacts.catalog import WorkspaceCatalog
    from tw_stock_tool.research_run.models import RunManifest


CANONICAL_MANIFEST_FILENAME: Final = "manifest.json"
_WORKFLOW_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_DIRECTORY_TIMESTAMP_PATTERN = re.compile(r"^\d{8}T\d{6}Z$")
_RUN_DIRECTORY_PATTERN = re.compile(
    r"^(?P<timestamp>\d{8}T\d{6}Z)_(?P<workflow>[a-z][a-z0-9]*(?:-[a-z0-9]+)*)_(?P<prefix>[0-9a-f]{8})$"
)
_UTC_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _absolute_path(value: str | Path, operation: str) -> Path:
    if not isinstance(value, (str, Path)):
        raise WorkspaceValidationError(operation, None, f"path must be str or Path, got {type(value).__name__}")
    try:
        # abspath/normpath intentionally do not resolve symlinks.
        return Path(os.path.normpath(os.path.abspath(os.fspath(value))))
    except (OSError, TypeError, ValueError) as exc:
        raise WorkspaceValidationError(operation, None, "path cannot be normalized") from exc


def _path_components(path: Path) -> tuple[Path, ...]:
    anchor = Path(path.anchor) if path.anchor else Path()
    parts = path.parts[1:] if path.anchor else path.parts
    current = anchor
    components: list[Path] = []
    for part in parts:
        current = current / part
        components.append(current)
    return tuple(components)


def _is_reparse_point(result: os.stat_result) -> bool:
    if stat.S_ISLNK(result.st_mode):
        return True
    return bool(getattr(result, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _ensure_no_reparse_components(path: Path, operation: str) -> None:
    """Reject symlink/reparse components without resolving the path."""
    for component in _path_components(path):
        try:
            result = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise WorkspacePathError(operation, component, "cannot inspect path component") from exc

        if _is_reparse_point(result):
            raise WorkspacePathError(operation, component, "symlink or reparse-point component is not allowed")
        if component != path and not stat.S_ISDIR(result.st_mode):
            raise WorkspacePathError(operation, component, "non-directory path component")


def _ensure_directory(path: Path, operation: str) -> None:
    _ensure_no_reparse_components(path, operation)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WorkspaceValidationError(operation, path, "directory creation failed") from exc
    _ensure_no_reparse_components(path, operation)
    try:
        result = path.lstat()
    except OSError as exc:
        raise WorkspaceValidationError(operation, path, "directory cannot be inspected") from exc
    if not stat.S_ISDIR(result.st_mode):
        raise WorkspaceValidationError(operation, path, "path is not a directory")


def _validate_utc_timestamp(value: str, operation: str = "validate timestamp") -> datetime:
    if type(value) is not str:
        raise WorkspaceValidationError(operation, None, f"timestamp must be exact str, got {type(value).__name__}")
    if not _UTC_TIMESTAMP_PATTERN.fullmatch(value):
        raise WorkspaceValidationError(operation, None, "timestamp must use YYYY-MM-DDTHH:MM:SSZ")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise WorkspaceValidationError(operation, None, "timestamp contains an invalid date/time") from exc


def _validate_run_id(value: str, operation: str = "validate run id") -> str:
    if type(value) is not str:
        raise WorkspaceValidationError(operation, None, f"run_id must be exact str, got {type(value).__name__}")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise WorkspaceValidationError(operation, None, "run_id must be a canonical lowercase UUID v4") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise WorkspaceValidationError(operation, None, "run_id must be a canonical lowercase UUID v4")
    return value


def validate_workflow_slug(value: str) -> str:
    """Validate and return a filesystem-safe lowercase workflow slug."""
    if type(value) is not str:
        raise WorkspaceValidationError("validate workflow slug", None, f"workflow slug must be exact str, got {type(value).__name__}")
    if not 1 <= len(value) <= 64 or value.strip() != value or not _WORKFLOW_SLUG_PATTERN.fullmatch(value):
        raise WorkspaceValidationError("validate workflow slug", None, "workflow slug must match the lowercase ASCII slug contract")
    return value


def canonical_run_directory_name(created_at: str, workflow_slug: str, run_id: str) -> str:
    """Return the exact canonical directory name for one Run Manifest."""
    timestamp = _validate_utc_timestamp(created_at)
    slug = validate_workflow_slug(workflow_slug)
    canonical_run_id = _validate_run_id(run_id)
    directory_timestamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
    return f"{directory_timestamp}_{slug}_{canonical_run_id.replace('-', '')[:8]}"


@dataclass(frozen=True, slots=True)
class ParsedRunDirectory:
    """The metadata recoverable from a canonical run-directory name."""

    directory_timestamp: str
    workflow_slug: str
    run_id_prefix: str

    @property
    def year(self) -> str:
        return self.directory_timestamp[:4]

    @property
    def month(self) -> str:
        return self.directory_timestamp[4:6]

    @property
    def created_at(self) -> str:
        parsed = datetime.strptime(self.directory_timestamp, "%Y%m%dT%H%M%SZ")
        return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_run_directory_name(value: str) -> ParsedRunDirectory | None:
    """Parse an exact canonical run-directory name; return None for noncanonical names."""
    if type(value) is not str:
        return None
    match = _RUN_DIRECTORY_PATTERN.fullmatch(value)
    if match is None:
        return None
    timestamp = match.group("timestamp")
    try:
        datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ")
    except ValueError:
        return None
    workflow_slug = match.group("workflow")
    try:
        validate_workflow_slug(workflow_slug)
    except WorkspaceValidationError:
        return None
    return ParsedRunDirectory(
        directory_timestamp=timestamp,
        workflow_slug=workflow_slug,
        run_id_prefix=match.group("prefix"),
    )


def validate_artifact_path(value: str) -> PurePosixPath:
    """Validate a Workspace-managed artifact path and return its POSIX form."""
    if type(value) is not str:
        raise WorkspacePathError("validate artifact path", None, f"artifact path must be exact str, got {type(value).__name__}")
    if not value or not value.strip():
        raise WorkspacePathError("validate artifact path", None, "artifact path must be nonblank")
    if "\x00" in value:
        raise WorkspacePathError("validate artifact path", None, "artifact path must not contain NUL")
    if "\\" in value:
        raise WorkspacePathError("validate artifact path", value, "artifact path must use POSIX '/' separators")
    if value.startswith("/") or value.endswith("/"):
        raise WorkspacePathError("validate artifact path", value, "artifact path must be relative and must not start or end with '/'")
    drive, _ = ntpath.splitdrive(value)
    if drive or PureWindowsPath(value).drive or PureWindowsPath(value).root:
        raise WorkspacePathError("validate artifact path", value, "artifact path must not contain a drive or UNC anchor")
    segments = value.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        raise WorkspacePathError("validate artifact path", value, "artifact path contains an unsafe path segment")
    return PurePosixPath(value)


def resolve_artifact_path(run_directory: Path | "RunDirectory", artifact_path: str) -> Path:
    """Resolve a managed artifact path without following unsafe components."""
    run_path = run_directory.path if isinstance(run_directory, RunDirectory) else _absolute_path(run_directory, "resolve artifact path")
    _ensure_no_reparse_components(run_path, "resolve artifact path")
    try:
        run_result = run_path.lstat()
    except OSError as exc:
        raise WorkspacePathError("resolve artifact path", run_path, "run directory cannot be inspected") from exc
    if not stat.S_ISDIR(run_result.st_mode):
        raise WorkspacePathError("resolve artifact path", run_path, "run directory is not a directory")

    relative = validate_artifact_path(artifact_path)
    candidate = run_path.joinpath(*relative.parts)
    try:
        candidate.relative_to(run_path)
    except ValueError as exc:
        raise WorkspacePathError("resolve artifact path", candidate, "artifact path escapes the run directory") from exc
    _ensure_no_reparse_components(candidate, "resolve artifact path")
    return candidate


@dataclass(frozen=True, slots=True)
class Workspace:
    """Validated local Workspace root with collision-safe run allocation."""

    root: Path | str

    def __post_init__(self) -> None:
        normalized = _absolute_path(self.root, "validate workspace root")
        _ensure_no_reparse_components(normalized, "validate workspace root")
        _ensure_directory(normalized, "validate workspace root")
        runs = normalized / "runs"
        _ensure_directory(runs, "validate workspace runs directory")
        object.__setattr__(self, "root", normalized)

    @property
    def runs_directory(self) -> Path:
        return self.root / "runs"

    def allocate_run_directory(self, created_at: str, workflow_slug: str, run_id: str) -> "RunDirectory":
        """Create a unique canonical run directory, rejecting every collision."""
        name = canonical_run_directory_name(created_at, workflow_slug, run_id)
        timestamp = _validate_utc_timestamp(created_at)
        year_directory = self.runs_directory / timestamp.strftime("%Y")
        month_directory = year_directory / timestamp.strftime("%m")
        _ensure_directory(month_directory, "allocate run directory")
        target = month_directory / name
        _ensure_no_reparse_components(target.parent, "allocate run directory")
        try:
            target.mkdir()
        except FileExistsError as exc:
            raise WorkspaceCollisionError("allocate run directory", target, "canonical run directory already exists") from exc
        except OSError as exc:
            raise WorkspaceValidationError("allocate run directory", target, "run directory creation failed") from exc
        _ensure_no_reparse_components(target, "allocate run directory")
        return RunDirectory(
            workspace=self,
            path=target,
            created_at=created_at,
            workflow_slug=workflow_slug,
            run_id=run_id,
        )

    def write_manifest(self, run_directory: "RunDirectory", manifest: RunManifest) -> RunManifest:
        return write_manifest(run_directory, manifest)

    def read_manifest(self, run_directory: "RunDirectory") -> RunManifest:
        return read_manifest(run_directory)

    def catalog(self) -> WorkspaceCatalog:
        from tw_stock_tool.artifacts.catalog import scan_workspace

        return scan_workspace(self)


@dataclass(frozen=True, slots=True)
class RunDirectory:
    """Immutable handle for one allocated canonical run directory."""

    workspace: Workspace
    path: Path
    created_at: str
    workflow_slug: str
    run_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.workspace, Workspace):
            raise WorkspaceValidationError("validate run directory", None, "workspace must be a Workspace")
        normalized = _absolute_path(self.path, "validate run directory")
        timestamp = _validate_utc_timestamp(self.created_at, "validate run directory")
        validate_workflow_slug(self.workflow_slug)
        _validate_run_id(self.run_id, "validate run directory")
        runs_directory = self.workspace.runs_directory
        try:
            normalized.relative_to(runs_directory)
        except ValueError as exc:
            raise WorkspacePathError(
                "validate run directory",
                normalized,
                "path must be inside the workspace runs directory",
            ) from exc

        expected = runs_directory / timestamp.strftime("%Y") / timestamp.strftime("%m") / canonical_run_directory_name(
            self.created_at,
            self.workflow_slug,
            self.run_id,
        )
        if normalized != expected:
            raise WorkspaceValidationError(
                "validate run directory",
                normalized,
                "path must equal the canonical run directory for its metadata",
            )

        _ensure_no_reparse_components(normalized, "validate run directory")
        try:
            result = normalized.lstat()
        except OSError as exc:
            raise WorkspaceValidationError("validate run directory", normalized, "path cannot be inspected") from exc
        if not stat.S_ISDIR(result.st_mode):
            raise WorkspaceValidationError("validate run directory", normalized, "path is not a directory")
        object.__setattr__(self, "path", normalized)

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def manifest_path(self) -> Path:
        return self.path / CANONICAL_MANIFEST_FILENAME

    @property
    def run_id_prefix(self) -> str:
        return self.run_id.replace("-", "")[:8]

    def validate_artifact_path(self, value: str) -> PurePosixPath:
        return validate_artifact_path(value)

    def resolve_artifact_path(self, value: str) -> Path:
        return resolve_artifact_path(self, value)

    def write_manifest(self, manifest: RunManifest) -> RunManifest:
        return write_manifest(self, manifest)

    def read_manifest(self) -> RunManifest:
        return read_manifest(self)


def _manifest_path(value: RunDirectory | Path) -> Path:
    if isinstance(value, RunDirectory):
        path = value.manifest_path
    else:
        path = _absolute_path(value, "read manifest")
    _ensure_no_reparse_components(path, "read manifest")
    return path


def read_manifest(run_directory_or_path: RunDirectory | Path) -> RunManifest:
    """Strictly read a canonical UTF-8 manifest using the Research Run loader."""
    from tw_stock_tool.research_run.serialization import (
        ResearchRunSerializationError,
        load_run_manifest_json,
    )

    path = _manifest_path(run_directory_or_path)
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            content = handle.read()
    except (OSError, UnicodeError) as exc:
        raise WorkspaceManifestError("read manifest", path, "canonical manifest cannot be read") from exc
    try:
        return load_run_manifest_json(content)
    except ResearchRunSerializationError as exc:
        raise WorkspaceManifestError("read manifest", path, "canonical manifest failed strict validation") from exc


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        directory_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    except OSError:
        return
    finally:
        os.close(directory_fd)


def _remove_temp_file(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def write_manifest(run_directory: RunDirectory, manifest: RunManifest) -> RunManifest:
    """Publish a canonical manifest once, atomically and without clobbering."""
    from tw_stock_tool.research_run.serialization import (
        ResearchRunSerializationError,
        export_run_manifest_json,
    )
    from tw_stock_tool.research_run.models import RunManifest

    if not isinstance(run_directory, RunDirectory):
        raise WorkspaceManifestError("write manifest", None, "run_directory must be a RunDirectory")
    _ensure_no_reparse_components(run_directory.path, "write manifest")
    try:
        result = run_directory.path.lstat()
    except OSError as exc:
        raise WorkspaceManifestError("write manifest", run_directory.path, "run directory cannot be inspected") from exc
    if not stat.S_ISDIR(result.st_mode):
        raise WorkspaceManifestError("write manifest", run_directory.path, "run directory is not a directory")

    final_path = run_directory.manifest_path
    _ensure_no_reparse_components(final_path, "write manifest")
    if not isinstance(manifest, RunManifest):
        raise WorkspaceManifestError("write manifest", final_path, "manifest must be a RunManifest")
    if manifest.run_id != run_directory.run_id:
        raise WorkspaceManifestError("write manifest", final_path, "manifest run_id does not match run directory")
    if manifest.created_at != run_directory.created_at:
        raise WorkspaceManifestError("write manifest", final_path, "manifest created_at does not match run directory")
    if manifest.config.workflow != run_directory.workflow_slug:
        raise WorkspaceManifestError("write manifest", final_path, "manifest workflow does not match run directory")
    for artifact in manifest.artifacts:
        try:
            validate_artifact_path(artifact.path)
        except WorkspacePathError as exc:
            raise WorkspaceManifestError(
                "write manifest",
                final_path,
                f"manifest artifact path is unsafe: {artifact.path!r}",
            ) from exc
    if final_path.exists() or os.path.lexists(final_path):
        raise WorkspaceCollisionError("write manifest", final_path, "canonical manifest already exists")
    try:
        content = export_run_manifest_json(manifest)
    except ResearchRunSerializationError as exc:
        raise WorkspaceManifestError("write manifest", final_path, "manifest cannot be serialized") from exc

    temporary_path: Path | None = None
    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=".manifest.",
            suffix=".tmp",
            dir=run_directory.path,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        _ensure_no_reparse_components(temporary_path, "write manifest")

        # Hard-link publication adds the final name atomically and fails if it exists;
        # unlike os.replace, it preserves the no-clobber guarantee on local filesystems.
        os.link(temporary_path, final_path)
        temporary_path.unlink()
        temporary_path = None
        _fsync_directory(run_directory.path)
    except WorkspaceError:
        raise
    except (OSError, UnicodeError) as exc:
        raise WorkspaceManifestError("write manifest", final_path, "atomic manifest publication failed") from exc
    finally:
        _remove_temp_file(temporary_path)

    try:
        loaded = read_manifest(run_directory)
    except WorkspaceError:
        raise
    if loaded != manifest:
        raise WorkspaceManifestError("write manifest", final_path, "strict read-back did not equal input manifest")
    return loaded


__all__ = [
    "CANONICAL_MANIFEST_FILENAME",
    "ParsedRunDirectory",
    "RunDirectory",
    "Workspace",
    "canonical_run_directory_name",
    "parse_run_directory_name",
    "read_manifest",
    "resolve_artifact_path",
    "validate_artifact_path",
    "validate_workflow_slug",
    "write_manifest",
]
