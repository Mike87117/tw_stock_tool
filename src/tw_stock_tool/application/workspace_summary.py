"""Presentation helpers for the managed-run terminal summary."""

from __future__ import annotations

from pathlib import Path

from tw_stock_tool.artifacts import Workspace, canonical_run_directory_name
from tw_stock_tool.research_run.models import RunManifest


def workspace_run_paths(workspace: str | Path, manifest: RunManifest) -> tuple[Path, Path]:
    store = Workspace(workspace)
    name = canonical_run_directory_name(manifest.created_at, manifest.config.workflow, manifest.run_id)
    run_directory = store.runs_directory / manifest.created_at[:4] / manifest.created_at[5:7] / name
    return run_directory, run_directory / "manifest.json"


__all__ = ["workspace_run_paths"]
