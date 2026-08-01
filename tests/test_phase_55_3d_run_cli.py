from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
from io import StringIO
import os
from pathlib import Path
from shutil import move
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch

from tw_stock_tool.application.workspace_query import (
    InspectWorkspaceRunRequest,
    ListWorkspaceRunsRequest,
    inspect_workspace_run,
    list_workspace_runs,
)
from tw_stock_tool.artifacts import (
    Workspace,
    WorkspaceDuplicateRunIdError,
    WorkspacePathError,
    WorkspaceRunNotFoundError,
    WorkspaceValidationError,
    lookup_workspace_run,
    scan_workspace,
    validate_run_id,
)
from tw_stock_tool.artifacts.workspace import canonical_run_directory_name
from tw_stock_tool.cli import twstock_cli
from tw_stock_tool.research_run.models import (
    ArtifactReference,
    DataSourceRecord,
    RUN_MANIFEST_SCHEMA_VERSION,
    RunConfig,
    RunManifest,
)
from tw_stock_tool.research_run.serialization import export_run_manifest_json


RUN_ID = "550e8400-e29b-41d4-a716-446655440000"
SECOND_RUN_ID = "6ba7b810-9dad-41d1-80b4-00c04fd430c8"
THIRD_RUN_ID = "123e4567-e89b-42d3-a456-426614174000"
CREATED_AT = "2026-08-01T00:00:00Z"


def _manifest(
    run_id: str = RUN_ID,
    created_at: str = CREATED_AT,
    workflow: str = "scan",
    artifacts: tuple[ArtifactReference, ...] = (),
    *,
    status: str = "success",
    limitations: tuple[str, ...] = (),
    errors: tuple[str, ...] = (),
) -> RunManifest:
    failure_count = 1 if status == "failure" else 0
    partial_count = 1 if status == "partial" else 0
    return RunManifest(
        RUN_MANIFEST_SCHEMA_VERSION,
        run_id,
        created_at,
        "0.4.0",
        status,
        RunConfig(
            workflow,
            "all",
            ("2330.TW", "2317.TW"),
            "1y",
            "1d",
            False,
            False,
            None,
            None,
            None,
            None,
            None,
            {"threshold": 3},
        ),
        (DataSourceRecord("2330.TW", "2330", "fixture", "1y", "1d", False, "live", "not_applicable", True, None),),
        0 if status == "failure" else 1,
        failure_count,
        partial_count,
        artifacts,
        errors,
        limitations,
    )


def _add_run(
    workspace: Workspace,
    run_id: str = RUN_ID,
    created_at: str = CREATED_AT,
    workflow: str = "scan",
    manifest: RunManifest | None = None,
):
    run = workspace.allocate_run_directory(created_at, workflow, run_id)
    run.write_manifest(manifest or _manifest(run_id, created_at, workflow))
    return run


def _snapshot(root: Path) -> tuple[tuple[object, ...], ...]:
    """Record metadata without following symlinks or reading artifact contents."""
    if not os.path.lexists(root):
        return ()
    records: list[tuple[object, ...]] = []

    def visit(path: Path, relative: str) -> None:
        result = path.lstat()
        mode = stat.S_IMODE(result.st_mode)
        if stat.S_ISLNK(result.st_mode):
            records.append((relative, "symlink", None, result.st_size, mode, result.st_mtime_ns, os.readlink(path)))
            return
        if stat.S_ISDIR(result.st_mode):
            records.append((relative, "directory", None, result.st_size, mode, result.st_mtime_ns, None))
            with os.scandir(path) as entries:
                for entry in sorted(entries, key=lambda item: item.name):
                    visit(Path(entry.path), f"{relative}/{entry.name}" if relative else entry.name)
            return
        content = path.read_bytes() if path.name == "manifest.json" else None
        records.append((relative, "file", content, result.st_size, mode, result.st_mtime_ns, None))

    visit(root, "")
    return tuple(records)


def _cli(argv: list[str]) -> tuple[int, str, str]:
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = twstock_cli.main(argv)
    return status, stdout.getvalue(), stderr.getvalue()


class WorkspaceOpenExistingAcceptanceTests(unittest.TestCase):
    def test_legacy_constructor_still_creates_root_and_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            workspace = Workspace(root)
            self.assertEqual(workspace.root, root)
            self.assertTrue(root.is_dir())
            self.assertTrue(workspace.runs_directory.is_dir())

    def test_existing_root_and_runs_open_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            before = _snapshot(workspace.root)
            self.assertEqual(Workspace.open_existing(workspace.root).root, workspace.root)
            self.assertEqual(before, _snapshot(workspace.root))

    def test_missing_root_fails_without_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "missing"
            before = _snapshot(root)
            with self.assertRaises(WorkspaceValidationError):
                Workspace.open_existing(root)
            self.assertEqual(before, _snapshot(root))

    def test_missing_runs_fails_without_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            root.mkdir()
            before = _snapshot(root)
            with self.assertRaises(WorkspaceValidationError):
                Workspace.open_existing(root)
            self.assertEqual(before, _snapshot(root))

    def test_root_file_fails_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            root.write_text("fixture", encoding="utf-8")
            before = _snapshot(root)
            with self.assertRaises(WorkspaceValidationError):
                Workspace.open_existing(root)
            self.assertEqual(before, _snapshot(root))

    def test_runs_file_fails_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            root.mkdir()
            (root / "runs").write_text("fixture", encoding="utf-8")
            before = _snapshot(root)
            with self.assertRaises(WorkspaceValidationError):
                Workspace.open_existing(root)
            self.assertEqual(before, _snapshot(root))

    def test_root_symlink_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "target"
            Workspace(target)
            root = Path(temp) / "workspace-link"
            try:
                root.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            before = _snapshot(root)
            with self.assertRaises(WorkspacePathError):
                Workspace.open_existing(root)
            self.assertEqual(before, _snapshot(root))

    def test_runs_symlink_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            root.mkdir()
            target = Path(temp) / "target"
            target.mkdir()
            runs = root / "runs"
            try:
                runs.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            before = _snapshot(root)
            with self.assertRaises(WorkspacePathError):
                Workspace.open_existing(root)
            self.assertEqual(before, _snapshot(root))

    def test_reparse_point_fails_closed_without_symlink_privilege(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            real_lstat = Path.lstat
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

            def mocked_lstat(path: Path):
                result = real_lstat(path)
                if path == workspace.root:
                    return Mock(st_mode=stat.S_IFDIR, st_file_attributes=reparse_flag)
                return result

            with patch.object(Path, "lstat", autospec=True, side_effect=mocked_lstat):
                with self.assertRaises(WorkspacePathError):
                    Workspace.open_existing(workspace.root)


class RunIdAndLookupAcceptanceTests(unittest.TestCase):
    def test_validate_accepts_canonical_lowercase_v4(self) -> None:
        self.assertEqual(validate_run_id(RUN_ID), RUN_ID)

    def test_validate_rejects_prefix(self) -> None:
        with self.assertRaises(WorkspaceValidationError):
            validate_run_id(RUN_ID[:8])

    def test_validate_rejects_uppercase(self) -> None:
        with self.assertRaises(WorkspaceValidationError):
            validate_run_id(RUN_ID.upper())

    def test_validate_rejects_hyphenless_uuid(self) -> None:
        with self.assertRaises(WorkspaceValidationError):
            validate_run_id(RUN_ID.replace("-", ""))

    def test_validate_rejects_braced_uuid(self) -> None:
        with self.assertRaises(WorkspaceValidationError):
            validate_run_id(f"{{{RUN_ID}}}")

    def test_validate_rejects_whitespace(self) -> None:
        with self.assertRaises(WorkspaceValidationError):
            validate_run_id(f" {RUN_ID} ")

    def test_validate_rejects_malformed_uuid(self) -> None:
        with self.assertRaises(WorkspaceValidationError):
            validate_run_id("not-a-uuid")

    def test_validate_rejects_non_v4_uuid(self) -> None:
        with self.assertRaises(WorkspaceValidationError):
            validate_run_id("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

    def test_validate_rejects_non_exact_string(self) -> None:
        class StringSubclass(str):
            pass

        with self.assertRaises(WorkspaceValidationError):
            validate_run_id(StringSubclass(RUN_ID))

    def test_lookup_returns_exact_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            _add_run(workspace)
            self.assertEqual(lookup_workspace_run(scan_workspace(workspace), RUN_ID).run_id, RUN_ID)

    def test_lookup_not_found_is_controlled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            _add_run(workspace)
            with self.assertRaises(WorkspaceRunNotFoundError):
                lookup_workspace_run(scan_workspace(workspace), SECOND_RUN_ID)

    def test_lookup_duplicate_fails_closed_without_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            _add_run(workspace)
            _add_run(workspace, RUN_ID, "2026-08-01T00:01:00Z", "daily")
            catalog = scan_workspace(workspace)
            with self.assertRaises(WorkspaceDuplicateRunIdError):
                lookup_workspace_run(catalog, RUN_ID)
            with self.assertRaises(WorkspaceRunNotFoundError):
                lookup_workspace_run(catalog, SECOND_RUN_ID)

    def test_lookup_warning_entry_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            _add_run(workspace, manifest=_manifest(artifacts=(ArtifactReference("report", "artifacts/missing.txt", "text/plain", None),)))
            self.assertEqual(lookup_workspace_run(scan_workspace(workspace), RUN_ID).run_id, RUN_ID)

    def test_lookup_readable_invalid_entry_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            run = _add_run(workspace, SECOND_RUN_ID)
            run.manifest_path.write_text(export_run_manifest_json(_manifest(RUN_ID)), encoding="utf-8")
            entry = lookup_workspace_run(scan_workspace(workspace), RUN_ID)
            self.assertEqual(entry.run_id, RUN_ID)
            self.assertEqual(entry.health.value, "invalid")

    def test_unreadable_manifest_prefix_cannot_be_looked_up(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            name = canonical_run_directory_name(CREATED_AT, "scan", RUN_ID)
            run = workspace.runs_directory / "2026" / "08" / name
            run.mkdir(parents=True)
            with self.assertRaises(WorkspaceRunNotFoundError):
                lookup_workspace_run(scan_workspace(workspace), RUN_ID)


class RunListAcceptanceTests(unittest.TestCase):
    def test_empty_workspace_prints_stable_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            status, stdout, stderr = _cli(["run", "list", "--workspace", str(workspace.root)])
            self.assertEqual((status, stdout, stderr), (0, "No runs found.\n", ""))

    def test_list_shows_valid_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            _add_run(workspace)
            status, stdout, _ = _cli(["run", "list", "--workspace", str(workspace.root)])
            self.assertEqual(status, 0)
            self.assertIn(f"Run ID: {RUN_ID}", stdout)
            self.assertIn("Health: valid", stdout)

    def test_list_preserves_valid_warning_invalid_order_and_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            _add_run(workspace, RUN_ID, "2026-08-01T00:02:00Z")
            _add_run(workspace, SECOND_RUN_ID, "2026-08-01T00:01:00Z", manifest=_manifest(SECOND_RUN_ID, "2026-08-01T00:01:00Z", artifacts=(ArtifactReference("report", "missing.txt", "text/plain", None),)))
            invalid = _add_run(workspace, THIRD_RUN_ID, "2026-08-01T00:00:00Z")
            invalid.manifest_path.write_text("{", encoding="utf-8")
            status, stdout, _ = _cli(["run", "list", "--workspace", str(workspace.root)])
            self.assertEqual(status, 0)
            self.assertLess(stdout.index(RUN_ID), stdout.index(SECOND_RUN_ID))
            self.assertLess(stdout.index(SECOND_RUN_ID), stdout.index("Run ID: -"))
            self.assertIn("missing_artifact", stdout)
            self.assertIn("invalid_manifest", stdout)

    def test_list_isolates_missing_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            _add_run(workspace)
            missing = workspace.allocate_run_directory("2026-08-01T00:01:00Z", "daily", SECOND_RUN_ID)
            status, stdout, _ = _cli(["run", "list", "--workspace", str(workspace.root)])
            self.assertEqual(status, 0)
            self.assertIn(RUN_ID, stdout)
            self.assertIn(str(missing.path), stdout)
            self.assertIn("missing_manifest", stdout)

    def test_list_isolates_unsupported_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            _add_run(workspace)
            run = _add_run(workspace, SECOND_RUN_ID, "2026-08-01T00:01:00Z")
            run.manifest_path.write_text(run.manifest_path.read_text(encoding="utf-8").replace('"schema_version": "1.0"', '"schema_version": "2.0"'), encoding="utf-8")
            status, stdout, _ = _cli(["run", "list", "--workspace", str(workspace.root)])
            self.assertEqual(status, 0)
            self.assertIn("unsupported_schema", stdout)
            self.assertIn(RUN_ID, stdout)

    def test_list_reports_unsafe_path_and_duplicate_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            unsafe = _add_run(workspace, THIRD_RUN_ID, manifest=_manifest(THIRD_RUN_ID, artifacts=(ArtifactReference("report", "safe.txt", "text/plain", None),)))
            unsafe.manifest_path.write_text(unsafe.manifest_path.read_text(encoding="utf-8").replace("safe.txt", "../unsafe.txt"), encoding="utf-8")
            _add_run(workspace, RUN_ID)
            _add_run(workspace, RUN_ID, "2026-08-01T00:01:00Z", "daily")
            status, stdout, _ = _cli(["run", "list", "--workspace", str(workspace.root)])
            self.assertEqual(status, 0)
            self.assertIn("unsafe_path", stdout)
            self.assertGreaterEqual(stdout.count("duplicate_run_id"), 2)

    def test_list_output_is_repeatable_and_uses_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            workspace.allocate_run_directory(CREATED_AT, "scan", RUN_ID)
            first = _cli(["run", "list", "--workspace", str(workspace.root)])
            second = _cli(["run", "list", "--workspace", str(workspace.root)])
            self.assertEqual(first, second)
            self.assertIn("Run ID: -", first[1])
            self.assertIn("Finding Codes: missing_manifest", first[1])

    def test_list_rejects_unknown_argument(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            twstock_cli.main(["run", "list", "--workspace", "workspace", "--unknown"])
        self.assertEqual(raised.exception.code, 2)

    def test_list_success_and_failure_do_not_mutate_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            _add_run(workspace)
            before = _snapshot(workspace.root)
            self.assertEqual(_cli(["run", "list", "--workspace", str(workspace.root)])[0], 0)
            self.assertEqual(before, _snapshot(workspace.root))
            missing = Path(temp) / "missing"
            before_missing = _snapshot(missing)
            self.assertEqual(_cli(["run", "list", "--workspace", str(missing)])[0], 1)
            self.assertEqual(before_missing, _snapshot(missing))


class RunInspectAcceptanceTests(unittest.TestCase):
    def test_inspect_shows_complete_valid_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            artifact = ArtifactReference("report", "artifacts/report.txt", "text/plain", "1")
            run = _add_run(workspace, manifest=_manifest(artifacts=(artifact,), status="partial", limitations=("fixture warning",), errors=("fixture error",)))
            artifact_path = run.resolve_artifact_path(artifact.path)
            artifact_path.parent.mkdir()
            artifact_path.write_text("artifact", encoding="utf-8")
            status, stdout, stderr = _cli(["run", "inspect", RUN_ID, "--workspace", str(workspace.root)])
            self.assertEqual((status, stderr), (0, ""))
            for label in ("Tool Version: 0.4.0", "Universe: all", "Canonical Symbols: 2330.TW, 2317.TW", "Resolved Configuration:", "Data Sources:", "Artifact References:", "Warnings:", "fixture warning", "Errors:", "fixture error", "Catalog Findings:", "Run Directory:", "Manifest Path:"):
                self.assertIn(label, stdout)

    def test_inspect_warning_and_readable_invalid_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            _add_run(workspace, manifest=_manifest(artifacts=(ArtifactReference("report", "missing.txt", "text/plain", None),)))
            warning = _cli(["run", "inspect", RUN_ID, "--workspace", str(workspace.root)])
            self.assertEqual(warning[0], 0)
            self.assertIn("missing_artifact", warning[1])
            run = _add_run(workspace, SECOND_RUN_ID, "2026-08-01T00:01:00Z")
            run.manifest_path.write_text(export_run_manifest_json(_manifest(THIRD_RUN_ID)), encoding="utf-8")
            invalid = _cli(["run", "inspect", THIRD_RUN_ID, "--workspace", str(workspace.root)])
            self.assertEqual(invalid[0], 0)
            self.assertIn("Health: invalid", invalid[1])

    def test_inspect_works_after_workspace_relocation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            original = Path(temp) / "original"
            workspace = Workspace(original)
            _add_run(workspace)
            moved = Path(temp) / "moved"
            move(str(original), str(moved))
            status, stdout, _ = _cli(["run", "inspect", RUN_ID, "--workspace", str(moved)])
            self.assertEqual(status, 0)
            self.assertIn(str(moved), stdout)

    def test_inspect_not_found_and_duplicate_are_controlled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            _add_run(workspace)
            status, _, stderr = _cli(["run", "inspect", SECOND_RUN_ID, "--workspace", str(workspace.root)])
            self.assertEqual(status, 1)
            self.assertIn("Error:", stderr)
            self.assertNotIn("Traceback", stderr)
            _add_run(workspace, RUN_ID, "2026-08-01T00:01:00Z", "daily")
            status, _, stderr = _cli(["run", "inspect", RUN_ID, "--workspace", str(workspace.root)])
            self.assertEqual(status, 1)
            self.assertIn("duplicate", stderr.lower())
            self.assertNotIn("Traceback", stderr)

    def test_inspect_rejects_invalid_and_unknown_arguments(self) -> None:
        for argv in (
            ["run", "inspect", RUN_ID.upper(), "--workspace", "workspace"],
            ["run", "inspect", RUN_ID[:8], "--workspace", "workspace"],
            ["run", "inspect", RUN_ID, "--workspace", "workspace", "--unknown"],
            ["run", "unknown"],
        ):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as raised:
                twstock_cli.main(argv)
            self.assertEqual(raised.exception.code, 2)

    def test_inspect_never_opens_artifact_content_or_mutates_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            artifact = ArtifactReference("report", "artifacts/report.txt", "text/plain", None)
            run = _add_run(workspace, manifest=_manifest(artifacts=(artifact,)))
            artifact_path = run.resolve_artifact_path(artifact.path)
            artifact_path.parent.mkdir()
            artifact_path.write_text("secret artifact content", encoding="utf-8")
            before = _snapshot(workspace.root)
            original_open = Path.open

            def guarded_open(path: Path, *args, **kwargs):
                if path == artifact_path:
                    raise AssertionError("artifact content must not be opened")
                return original_open(path, *args, **kwargs)

            with patch.object(Path, "open", autospec=True, side_effect=guarded_open):
                self.assertEqual(_cli(["run", "inspect", RUN_ID, "--workspace", str(workspace.root)])[0], 0)
            self.assertEqual(before, _snapshot(workspace.root))

    def test_inspect_success_and_controlled_failures_do_not_mutate_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            _add_run(workspace)
            before = _snapshot(workspace.root)
            self.assertEqual(_cli(["run", "inspect", RUN_ID, "--workspace", str(workspace.root)])[0], 0)
            self.assertEqual(_cli(["run", "inspect", SECOND_RUN_ID, "--workspace", str(workspace.root)])[0], 1)
            self.assertEqual(before, _snapshot(workspace.root))
            _add_run(workspace, RUN_ID, "2026-08-01T00:01:00Z", "daily")
            duplicate_before = _snapshot(workspace.root)
            self.assertEqual(_cli(["run", "inspect", RUN_ID, "--workspace", str(workspace.root)])[0], 1)
            self.assertEqual(duplicate_before, _snapshot(workspace.root))


class OfflineBoundaryAcceptanceTests(unittest.TestCase):
    def test_list_and_inspect_do_not_invoke_workflows_network_cache_or_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            _add_run(workspace)

            def forbidden(*args, **kwargs):
                raise AssertionError("offline read-only command crossed a forbidden seam")

            with ExitStack() as stack:
                for target in (
                    "requests.sessions.Session.request",
                    "tw_stock_tool.application.workspace_run.run_scan_workspace",
                    "tw_stock_tool.application.workspace_run.run_daily_workspace",
                    "tw_stock_tool.application.workspace_run.run_backtest_workspace",
                    "tw_stock_tool.research_run.scan.run_scan_research",
                    "tw_stock_tool.research_run.daily.run_daily_report_research",
                    "tw_stock_tool.research_run.backtest.run_backtest_research",
                    "tw_stock_tool.paper_trading.engine.run_simulated_paper_trading",
                    "tw_stock_tool.paper_trading.portfolio_engine.run_simulated_portfolio_trading_result",
                    "tw_stock_tool.data.cache_runtime._write_cache",
                ):
                    stack.enter_context(patch(target, side_effect=forbidden))
                self.assertEqual(_cli(["run", "list", "--workspace", str(workspace.root)])[0], 0)
                self.assertEqual(_cli(["run", "inspect", RUN_ID, "--workspace", str(workspace.root)])[0], 0)


class ApplicationQueryAcceptanceTests(unittest.TestCase):
    def test_query_service_uses_existing_workspace_and_exact_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            _add_run(workspace)
            catalog = list_workspace_runs(ListWorkspaceRunsRequest(workspace.root))
            entry = inspect_workspace_run(InspectWorkspaceRunRequest(workspace.root, RUN_ID))
            self.assertEqual(catalog.entries[0].run_id, RUN_ID)
            self.assertEqual(entry.run_id, RUN_ID)


if __name__ == "__main__":
    unittest.main()