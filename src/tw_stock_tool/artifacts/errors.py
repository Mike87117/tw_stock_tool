"""Controlled errors for the local Workspace storage boundary."""

from __future__ import annotations

from pathlib import Path


class WorkspaceError(Exception):
    """Base error for controlled Workspace operations."""

    def __init__(
        self,
        operation: str,
        path: str | Path | None,
        message: str,
    ) -> None:
        self.operation = operation
        self.path = Path(path) if path is not None else None
        self.detail = message
        location = f" path={self.path}" if self.path is not None else ""
        super().__init__(f"{operation}: {message}{location}")


class WorkspaceValidationError(WorkspaceError):
    """Raised when Workspace metadata or a root violates its contract."""


class WorkspaceCollisionError(WorkspaceError):
    """Raised when a run directory or canonical file already exists."""


class WorkspacePathError(WorkspaceError):
    """Raised when a managed filesystem path is unsafe."""


class WorkspaceManifestError(WorkspaceError):
    """Raised when canonical manifest persistence or read-back fails."""


class WorkspaceCatalogError(WorkspaceError):
    """Raised when the catalog cannot inspect the Workspace layout."""

class WorkspaceRunNotFoundError(WorkspaceCatalogError):
    """Raised when an exact Run ID does not appear in a catalog."""

class WorkspaceDuplicateRunIdError(WorkspaceCatalogError):
    """Raised when an exact Run ID appears in multiple catalog entries."""

__all__ = [
    "WorkspaceError",
    "WorkspaceValidationError",
    "WorkspaceCollisionError",
    "WorkspacePathError",
    "WorkspaceManifestError",
    "WorkspaceCatalogError",
    "WorkspaceRunNotFoundError",
    "WorkspaceDuplicateRunIdError",
]
