"""Shared application boundary for opt-in Workspace research runs."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import uuid4

from tw_stock_tool.artifacts import RunDirectory, Workspace, resolve_artifact_path, validate_artifact_path
from tw_stock_tool.artifacts.errors import WorkspacePathError
from tw_stock_tool.research_run.models import ArtifactReference, RunConfig, RunManifest


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _absolute(value: str | Path) -> Path:
    return Path(os.path.normpath(os.path.abspath(os.fspath(value))))


@dataclass(frozen=True, slots=True)
class WorkspaceRunLifecycle:
    """Allocated, collision-safe context shared by all managed workflows."""

    workspace: Workspace
    run_directory: RunDirectory

    @classmethod
    def begin(cls, workspace_root: str | Path, workflow: str) -> "WorkspaceRunLifecycle":
        workspace = Workspace(workspace_root)
        created_at = _now_utc()
        run_id = str(uuid4())
        run_directory = workspace.allocate_run_directory(created_at, workflow, run_id)
        return cls(workspace=workspace, run_directory=run_directory)

    @property
    def run_id(self) -> str:
        return self.run_directory.run_id

    @property
    def created_at(self) -> str:
        return self.run_directory.created_at

    @property
    def manifest_path(self) -> Path:
        return self.run_directory.manifest_path

    @property
    def artifacts_directory(self) -> Path:
        path = resolve_artifact_path(self.run_directory, "artifacts")
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise WorkspacePathError("create managed artifacts directory", path, "directory creation failed") from exc
        resolved = resolve_artifact_path(self.run_directory, "artifacts")
        if not resolved.is_dir():
            raise WorkspacePathError("create managed artifacts directory", resolved, "path is not a directory")
        return resolved

    def artifact_reference(
        self,
        path: str | Path,
        artifact_type: str,
        media_type: str,
        schema_version: int | str | None = None,
    ) -> ArtifactReference:
        candidate = _absolute(path)
        try:
            relative = candidate.relative_to(self.run_directory.path).as_posix()
        except ValueError as exc:
            raise WorkspacePathError(
                "build managed artifact reference",
                candidate,
                "artifact destination is outside the allocated run directory",
            ) from exc
        validate_artifact_path(relative)
        resolved = self.run_directory.resolve_artifact_path(relative)
        try:
            if not resolved.is_file():
                raise WorkspacePathError("build managed artifact reference", resolved, "artifact is not a regular file")
        except OSError as exc:
            raise WorkspacePathError("build managed artifact reference", resolved, "artifact cannot be inspected") from exc
        return ArtifactReference(artifact_type, relative, media_type, schema_version)

    def normalize_config(self, config: RunConfig) -> RunConfig:
        """Keep path-valued resolved options portable inside the manifest."""
        options = dict(config.workflow_options)
        for name in ("output_dir", "markdown_path", "json_path", "excel_path", "manifest_path"):
            value = options.get(name)
            if value is None:
                continue
            candidate = _absolute(value)
            if candidate == self.manifest_path:
                options[name] = "manifest.json"
                continue
            try:
                relative = candidate.relative_to(self.run_directory.path).as_posix()
            except ValueError as exc:
                raise WorkspacePathError(
                    "normalize managed run configuration",
                    candidate,
                    f"{name} is outside the allocated run directory",
                ) from exc
            validate_artifact_path(relative)
            options[name] = relative
        return replace(config, workflow_options=options)

    def publish(self, manifest: RunManifest) -> RunManifest:
        return self.workspace.write_manifest(self.run_directory, manifest)

__all__ = ["WorkspaceRunLifecycle"]
