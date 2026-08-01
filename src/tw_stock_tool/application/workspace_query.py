"""Typed, read-only Workspace catalog queries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tw_stock_tool.artifacts import (
    Workspace,
    WorkspaceCatalog,
    WorkspaceRunEntry,
    lookup_workspace_run,
    scan_workspace,
)


@dataclass(frozen=True, slots=True)
class ListWorkspaceRunsRequest:
    workspace: str | Path


@dataclass(frozen=True, slots=True)
class InspectWorkspaceRunRequest:
    workspace: str | Path
    run_id: str


def list_workspace_runs(request: ListWorkspaceRunsRequest) -> WorkspaceCatalog:
    workspace = Workspace.open_existing(request.workspace)
    return scan_workspace(workspace)


def inspect_workspace_run(request: InspectWorkspaceRunRequest) -> WorkspaceRunEntry:
    return lookup_workspace_run(list_workspace_runs(ListWorkspaceRunsRequest(request.workspace)), request.run_id)


__all__ = [
    "InspectWorkspaceRunRequest",
    "ListWorkspaceRunsRequest",
    "inspect_workspace_run",
    "list_workspace_runs",
]
