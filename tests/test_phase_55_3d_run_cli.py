from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from tw_stock_tool.application.workspace_query import (
    InspectWorkspaceRunRequest,
    ListWorkspaceRunsRequest,
    inspect_workspace_run,
    list_workspace_runs,
)
from tw_stock_tool.artifacts import (
    Workspace,
    WorkspaceRunNotFoundError,
    WorkspaceValidationError,
    lookup_workspace_run,
    scan_workspace,
)
from tw_stock_tool.cli import twstock_cli
from tw_stock_tool.research_run.models import ArtifactReference, RUN_MANIFEST_SCHEMA_VERSION, RunConfig, RunManifest


RUN_ID = "550e8400-e29b-41d4-a716-446655440000"


def _manifest(artifact: str | None = None) -> RunManifest:
    artifacts = () if artifact is None else (ArtifactReference("report", artifact, "text/plain", None),)
    return RunManifest(
        RUN_MANIFEST_SCHEMA_VERSION, RUN_ID, "2026-08-01T00:00:00Z", "0.4.0", "success",
        RunConfig("scan", "all", ("2330.TW",), "1y", "1d", False, False, None, None, None, None, None, {}),
        (), 0, 0, 0, artifacts, (), (),
    )


def _tree(root: Path) -> tuple[tuple[str, bytes, int], ...]:
    return tuple(sorted((str(path.relative_to(root)), path.read_bytes(), path.stat().st_mtime_ns) for path in root.rglob("*") if path.is_file()))


class ReadOnlyWorkspaceTests(unittest.TestCase):
    def test_open_existing_never_creates_missing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "missing"
            with self.assertRaises(WorkspaceValidationError):
                Workspace.open_existing(root)
            self.assertFalse(root.exists())
            root.mkdir()
            with self.assertRaises(WorkspaceValidationError):
                Workspace.open_existing(root)
            self.assertFalse((root / "runs").exists())
            self.assertTrue(Workspace.open_existing(Workspace(root).root).runs_directory.is_dir())

    def test_exact_lookup_and_query_service(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            run = workspace.allocate_run_directory("2026-08-01T00:00:00Z", "scan", RUN_ID)
            run.write_manifest(_manifest())
            catalog = list_workspace_runs(ListWorkspaceRunsRequest(workspace.root))
            self.assertEqual(lookup_workspace_run(catalog, RUN_ID).run_id, RUN_ID)
            self.assertEqual(inspect_workspace_run(InspectWorkspaceRunRequest(workspace.root, RUN_ID)).manifest, _manifest())
            for invalid in (RUN_ID[:8], RUN_ID.upper(), RUN_ID.replace("-", ""), "550e8400-e29b-11d4-a716-446655440000"):
                with self.subTest(invalid=invalid), self.assertRaises(WorkspaceValidationError):
                    lookup_workspace_run(catalog, invalid)
            with self.assertRaises(WorkspaceRunNotFoundError):
                lookup_workspace_run(catalog, "6ba7b810-9dad-41d1-80b4-00c04fd430c8")

    def test_list_and_inspect_are_offline_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            run = workspace.allocate_run_directory("2026-08-01T00:00:00Z", "scan", RUN_ID)
            run.write_manifest(_manifest("artifacts/missing.txt"))
            before = _tree(workspace.root)
            stdout, stderr = StringIO(), StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(twstock_cli.main(["run", "list", "--workspace", str(workspace.root)]), 0)
            self.assertIn("missing_artifact", stdout.getvalue())
            self.assertEqual(stderr.getvalue(), "")
            stdout = StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(twstock_cli.main(["run", "inspect", RUN_ID, "--workspace", str(workspace.root)]), 0)
            self.assertIn("Artifact References:", stdout.getvalue())
            self.assertIn("Catalog Findings:", stdout.getvalue())
            self.assertEqual(before, _tree(workspace.root))

    def test_cli_errors_and_help_contract(self) -> None:
        for argv in (["run", "--help"], ["run", "list", "--help"], ["run", "inspect", "--help"]):
            with self.subTest(argv=argv), redirect_stdout(StringIO()) as stdout:
                with self.assertRaises(SystemExit) as raised:
                    twstock_cli.main(argv)
                self.assertEqual(raised.exception.code, 0)
                self.assertIn("twstock run", stdout.getvalue())
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "missing"
            stderr = StringIO()
            with redirect_stderr(stderr):
                self.assertEqual(twstock_cli.main(["run", "list", "--workspace", str(missing)]), 1)
            self.assertFalse(missing.exists())
            self.assertIn("Error:", stderr.getvalue())
        with self.assertRaises(SystemExit) as raised:
            twstock_cli.main(["run", "inspect", RUN_ID.upper(), "--workspace", "workspace"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
