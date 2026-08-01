from pathlib import Path
import ast
from datetime import datetime
from shutil import move
import stat
import tempfile
import unittest
from unittest import mock

from tw_stock_tool.artifacts import (
    RunDirectory,
    RunFinding,
    RunFindingCode,
    RunHealth,
    Workspace,
    WorkspaceCatalog,
    WorkspaceCatalogError,
    WorkspaceCollisionError,
    WorkspaceManifestError,
    WorkspacePathError,
    WorkspaceRunEntry,
    WorkspaceValidationError,
    canonical_run_directory_name,
    parse_run_directory_name,
    scan_workspace,
    validate_artifact_path,
    validate_workflow_slug,
)
from tw_stock_tool.research_run.models import (
    RUN_MANIFEST_SCHEMA_VERSION,
    ArtifactReference,
    RunConfig,
    RunManifest,
)
from tw_stock_tool.research_run.serialization import ResearchRunSerializationError, export_run_manifest_json

_RUN_IDS = (
    "550e8400-e29b-41d4-a716-446655440000",
    "6ba7b810-9dad-41d1-80b4-00c04fd430c8",
    "7c1e9c4d-5b2a-4a92-8c2f-1234567890ab",
    "8d2fad5e-6c3b-4ba3-9d30-2345678901bc",
    "9e30be6f-7d4c-4cb4-ae41-3456789012cd",
)


def _manifest(
    run_id: str = _RUN_IDS[0],
    created_at: str = "2026-07-31T12:00:00Z",
    workflow: str = "scan",
    artifacts: tuple[ArtifactReference, ...] = (),
) -> RunManifest:
    return RunManifest(
        schema_version=RUN_MANIFEST_SCHEMA_VERSION,
        run_id=run_id,
        created_at=created_at,
        tool_version="0.4.0",
        status="success",
        config=RunConfig(
            workflow=workflow,
            universe="custom",
            canonical_symbols=("2330.TW",),
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
            strategy=None,
            backtest=None,
            parameter_sweep=None,
            walk_forward=None,
            ml=None,
            workflow_options={},
        ),
        data_sources=(),
        success_count=0,
        failure_count=0,
        partial_count=0,
        artifacts=artifacts,
        errors=(),
        limitations=("\u50c5\u4f9b\u7814\u7a76\u4f7f\u7528",),
    )


def _catalog_entry(
    workspace: Workspace,
    *,
    health: RunHealth = RunHealth.VALID,
    findings: tuple[RunFinding, ...] = (),
    canonical_symbols: tuple[str, ...] = ("2330.TW",),
    artifact_count: int = 0,
    manifest: RunManifest | None = None,
) -> WorkspaceRunEntry:
    return WorkspaceRunEntry(
        run_id=_RUN_IDS[0],
        created_at="2026-07-31T12:00:00Z",
        workflow="scan",
        status="success",
        canonical_symbols=canonical_symbols,
        universe="custom",
        tool_version="0.4.0",
        artifact_count=artifact_count,
        run_directory=workspace.root / "runs" / "2026" / "07" / "run",
        manifest_path=workspace.root / "runs" / "2026" / "07" / "run" / "manifest.json",
        health=health,
        findings=findings,
        manifest=manifest,
    )


class WorkspaceFoundationTests(unittest.TestCase):
    def test_workspace_creates_missing_root_and_rejects_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            workspace = Workspace(root)
            self.assertTrue(workspace.root.is_dir())
            self.assertTrue(workspace.runs_directory.is_dir())
            file_root = Path(temp) / "file"
            file_root.write_text("x", encoding="utf-8")
            with self.assertRaises(WorkspaceValidationError):
                Workspace(file_root)

    def test_workspace_rejects_symlink_root_and_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            real = base / "real"
            real.mkdir()
            symlink = base / "link"
            try:
                symlink.symlink_to(real, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            with self.assertRaises(WorkspacePathError):
                Workspace(symlink)
            with self.assertRaises(WorkspacePathError):
                Workspace(symlink / "child")

    def test_workflow_slug_contract(self) -> None:
        for value in ("scan", "daily", "backtest", "daily-report", "a", "a1"):
            self.assertEqual(validate_workflow_slug(value), value)
        for value in ("Scan", "daily_report", "-daily", "daily-", "daily--report", "daily report", "daily/report", "daily.report", " daily", "daily ", "", "x" * 65):
            with self.subTest(value=value):
                with self.assertRaises(WorkspaceValidationError):
                    validate_workflow_slug(value)
        with self.assertRaises(WorkspaceValidationError):
            validate_workflow_slug(1)  # type: ignore[arg-type]

    def test_canonical_name_and_exact_parser(self) -> None:
        name = canonical_run_directory_name("2026-02-03T04:05:06Z", "daily-report", _RUN_IDS[0])
        self.assertEqual(name, "20260203T040506Z_daily-report_550e8400")
        parsed = parse_run_directory_name(name)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.created_at, "2026-02-03T04:05:06Z")
        self.assertEqual((parsed.year, parsed.month, parsed.run_id_prefix), ("2026", "02", "550e8400"))
        self.assertIsNone(parse_run_directory_name("20260203T040506Z_daily-report_550E8400"))
        self.assertIsNone(parse_run_directory_name("20260230T040506Z_daily-report_550e8400"))

    def test_run_directory_allocation_is_collision_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            run = workspace.allocate_run_directory("2026-07-31T12:00:00Z", "scan", _RUN_IDS[0])
            self.assertEqual(run.path.parent.name, "07")
            self.assertEqual(run.path.parent.parent.name, "2026")
            self.assertEqual(run.path.name, "20260731T120000Z_scan_550e8400")
            with self.assertRaises(WorkspaceCollisionError):
                workspace.allocate_run_directory("2026-07-31T12:00:00Z", "scan", _RUN_IDS[0])

    def test_uuid_and_timestamp_validation(self) -> None:
        with self.assertRaises(WorkspaceValidationError):
            canonical_run_directory_name("2026-02-30T04:05:06Z", "scan", _RUN_IDS[0])
        with self.assertRaises(WorkspaceValidationError):
            canonical_run_directory_name("2026-02-03T04:05:06Z", "scan", "550e8400-e29b-11d4-a716-446655440000")
        with self.assertRaises(WorkspaceValidationError):
            canonical_run_directory_name("2026-02-03T04:05:06Z", "scan", "550E8400-E29B-41D4-A716-446655440000")
        with self.assertRaises(WorkspaceValidationError):
            canonical_run_directory_name("2026-02-03T04:05:06+00:00", "scan", _RUN_IDS[0])

    def test_public_run_directory_is_bound_to_existing_canonical_workspace_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            workspace = Workspace(base / "workspace")
            created_at = "2026-07-31T12:00:00Z"
            name = canonical_run_directory_name(created_at, "scan", _RUN_IDS[0])
            outside = base / "outside"
            outside.mkdir()
            wrong_year = workspace.runs_directory / "2025" / "08" / name
            wrong_year.parent.mkdir(parents=True)
            wrong_month = workspace.runs_directory / "2026" / "08" / name
            wrong_month.parent.mkdir(parents=True)
            wrong_name = workspace.runs_directory / "2026" / "07" / "not-canonical"
            wrong_name.parent.mkdir(parents=True)
            nonexistent = workspace.runs_directory / "2026" / "07" / name
            nonexistent.parent.mkdir(parents=True, exist_ok=True)

            for path in (outside, workspace.root, wrong_year, wrong_month, wrong_name, nonexistent):
                with self.subTest(path=path):
                    with self.assertRaises((WorkspacePathError, WorkspaceValidationError)):
                        RunDirectory(workspace, path, created_at, "scan", _RUN_IDS[0])

            file_path = workspace.runs_directory / "2026" / "07" / name
            file_path.write_text("not a directory", encoding="utf-8")
            with self.assertRaises(WorkspaceValidationError):
                RunDirectory(workspace, file_path, created_at, "scan", _RUN_IDS[0])

            allocated = workspace.allocate_run_directory(created_at, "scan", _RUN_IDS[1])
            bound = RunDirectory(workspace, allocated.path, created_at, "scan", _RUN_IDS[1])
            self.assertEqual(bound.path, allocated.path)

    def test_managed_path_profile_and_symlink_rejection(self) -> None:
        for value in ("manifest.json", "artifacts/report.md", "tables/result.csv", "logs/errors.log"):
            self.assertEqual(validate_artifact_path(value).as_posix(), value)
        for value in ("/artifacts/report.md", "C:/report.md", "C:\\report.md", "\\\\server\\share\\report.md", "../report.md", "artifacts/../report.md", "./report.md", "artifacts//report.md", "artifacts/", "artifacts\\report.md", "bad\x00path"):
            with self.subTest(value=value):
                with self.assertRaises(WorkspacePathError):
                    validate_artifact_path(value)

        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            run = workspace.allocate_run_directory("2026-07-31T12:00:00Z", "scan", _RUN_IDS[0])
            real = run.path / "real"
            real.mkdir()
            link = run.path / "link"
            try:
                link.symlink_to(real, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            with self.assertRaises(WorkspacePathError):
                run.resolve_artifact_path("link/result.csv")

    def test_manifest_is_utf8_deterministic_and_no_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            run = workspace.allocate_run_directory("2026-07-31T12:00:00Z", "scan", _RUN_IDS[0])
            manifest = _manifest()
            written = run.write_manifest(manifest)
            self.assertEqual(written, manifest)
            first = run.manifest_path.read_bytes()
            self.assertTrue(first.endswith(b"\n"))
            self.assertIn("\u50c5", first.decode("utf-8"))
            self.assertEqual(first.decode("utf-8"), export_run_manifest_json(manifest))
            with self.assertRaises(WorkspaceCollisionError):
                run.write_manifest(manifest)
            self.assertEqual(run.manifest_path.read_bytes(), first)
            self.assertEqual(scan_workspace(workspace).entries[0].manifest, manifest)

    def test_manifest_publish_failure_cleans_temp_file_and_chains(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            run = workspace.allocate_run_directory("2026-07-31T12:00:00Z", "scan", _RUN_IDS[0])
            with mock.patch("tw_stock_tool.artifacts.workspace.os.link", side_effect=OSError("publish failed")):
                with self.assertRaises(WorkspaceManifestError) as raised:
                    run.write_manifest(_manifest())
            self.assertIsInstance(raised.exception.__cause__, OSError)
            self.assertFalse(run.manifest_path.exists())
            self.assertEqual(list(run.path.glob(".manifest.*.tmp")), [])

    def test_catalog_health_and_corruption_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            valid = workspace.allocate_run_directory("2026-07-31T12:00:00Z", "scan", _RUN_IDS[0])
            valid.write_manifest(_manifest())
            missing = workspace.allocate_run_directory("2026-07-31T12:01:00Z", "daily", _RUN_IDS[1])
            malformed = workspace.allocate_run_directory("2026-07-31T12:02:00Z", "backtest", _RUN_IDS[2])
            malformed.manifest_path.write_text("{", encoding="utf-8")
            catalog = scan_workspace(workspace)
            self.assertEqual(len(catalog.entries), 3)
            self.assertEqual(catalog.entries[0].health, RunHealth.VALID)
            self.assertEqual(catalog.entries[0].run_id, _RUN_IDS[0])
            self.assertEqual(catalog.entries[1].findings[0].code, RunFindingCode.MISSING_MANIFEST)
            self.assertEqual(catalog.entries[2].findings[0].code, RunFindingCode.INVALID_MANIFEST)

    def test_catalog_missing_artifact_is_warning_and_unsafe_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            warning_run = workspace.allocate_run_directory("2026-07-31T12:00:00Z", "scan", _RUN_IDS[0])
            warning_run.write_manifest(_manifest(artifacts=(ArtifactReference("report", "artifacts/report.md", "text/markdown", None),)))
            unsafe_run = workspace.allocate_run_directory("2026-07-31T12:01:00Z", "daily", _RUN_IDS[1])
            unsafe_manifest = _manifest(run_id=_RUN_IDS[1], created_at="2026-07-31T12:01:00Z", workflow="daily", artifacts=(ArtifactReference("report", "../outside.md", "text/markdown", None),))
            unsafe_run.manifest_path.write_text(export_run_manifest_json(unsafe_manifest), encoding="utf-8")
            catalog = scan_workspace(workspace)
            entries = {entry.run_id: entry for entry in catalog.entries}
            self.assertEqual(entries[_RUN_IDS[0]].health, RunHealth.WARNING)
            self.assertEqual(entries[_RUN_IDS[0]].findings[0].code, RunFindingCode.MISSING_ARTIFACT)
            self.assertEqual(entries[_RUN_IDS[1]].health, RunHealth.INVALID)
            self.assertEqual(entries[_RUN_IDS[1]].findings[0].code, RunFindingCode.UNSAFE_PATH)

    def test_manifest_writer_rejects_identity_and_unsafe_paths_before_filesystem_changes(self) -> None:
        cases = (
            ("run_id", {"run_id": _RUN_IDS[1]}, None),
            ("created_at", {"created_at": "2026-07-31T23:59:00Z"}, None),
            ("workflow", {"workflow": "daily"}, None),
            ("parent traversal", {}, "../outside.md"),
            ("absolute path", {}, "/absolute.md"),
        )
        for index, (label, overrides, artifact_path) in enumerate(cases):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp:
                workspace = Workspace(Path(temp) / "workspace")
                created_at = f"2026-07-31T12:0{index}:00Z"
                run = workspace.allocate_run_directory(created_at, "scan", _RUN_IDS[0])
                artifacts = () if artifact_path is None else (ArtifactReference("report", artifact_path, "text/markdown", None),)
                manifest = _manifest(
                    run_id=overrides.get("run_id", _RUN_IDS[0]),
                    created_at=overrides.get("created_at", created_at),
                    workflow=overrides.get("workflow", "scan"),
                    artifacts=artifacts,
                )
                with self.assertRaises(WorkspaceManifestError) as raised:
                    run.write_manifest(manifest)
                if artifact_path is not None:
                    self.assertIsInstance(raised.exception.__cause__, WorkspacePathError)
                self.assertFalse(run.manifest_path.exists())
                self.assertEqual(list(run.path.glob(".manifest.*.tmp")), [])

    def test_catalog_directory_artifact_is_a_warning_with_explicit_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            run = workspace.allocate_run_directory("2026-07-31T12:00:00Z", "scan", _RUN_IDS[0])
            run.resolve_artifact_path("artifacts/report.md").mkdir(parents=True)
            run.write_manifest(_manifest(artifacts=(ArtifactReference("report", "artifacts/report.md", "text/markdown", None),)))
            entry = scan_workspace(workspace).entries[0]
            self.assertEqual(entry.health, RunHealth.WARNING)
            self.assertEqual(entry.findings[0].code, RunFindingCode.MISSING_ARTIFACT)
            self.assertIn("not a regular file", entry.findings[0].message)

    def test_catalog_collects_multiple_findings_in_priority_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            run = workspace.allocate_run_directory("2026-07-31T12:00:00Z", "scan", _RUN_IDS[0])
            manifest = _manifest(
                artifacts=(
                    ArtifactReference("unsafe", "../outside.md", "text/markdown", None),
                    ArtifactReference("missing", "artifacts/missing.md", "text/markdown", None),
                )
            )
            run.manifest_path.write_text(export_run_manifest_json(manifest), encoding="utf-8")
            entry = scan_workspace(workspace).entries[0]
            self.assertEqual(entry.health, RunHealth.INVALID)
            self.assertEqual(
                [finding.code for finding in entry.findings],
                [RunFindingCode.UNSAFE_PATH, RunFindingCode.MISSING_ARTIFACT],
            )

    def test_parser_and_catalog_share_workflow_slug_length_contract(self) -> None:
        slug_64 = "a" + "b" * 63
        slug_65 = "a" + "b" * 64
        name_64 = f"20260731T120000Z_{slug_64}_550e8400"
        name_65 = f"20260731T120000Z_{slug_65}_550e8400"
        self.assertIsNotNone(parse_run_directory_name(name_64))
        self.assertIsNone(parse_run_directory_name(name_65))
        with self.assertRaises(WorkspaceValidationError):
            validate_workflow_slug(slug_65)

        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            with self.assertRaises(WorkspaceValidationError):
                workspace.allocate_run_directory("2026-07-31T12:00:00Z", slug_65, _RUN_IDS[0])
            long_path = workspace.runs_directory / "2026" / "07" / name_65
            long_path.mkdir(parents=True)
            self.assertEqual(scan_workspace(workspace).entries, ())

    def test_catalog_canonical_run_symlink_is_invalid_without_following(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            month = workspace.runs_directory / "2026" / "07"
            month.mkdir(parents=True)
            target = month / "target"
            target.mkdir()
            link = month / canonical_run_directory_name("2026-07-31T12:00:00Z", "scan", _RUN_IDS[0])
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            entries = scan_workspace(workspace).entries
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].health, RunHealth.INVALID)
            self.assertEqual(entries[0].findings[0].code, RunFindingCode.UNSAFE_PATH)
            self.assertIsNone(entries[0].manifest)

    def test_catalog_canonical_year_and_month_symlinks_raise_controlled_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            real_year = Path(temp) / "real-year"
            real_year.mkdir()
            year_link = workspace.runs_directory / "2026"
            try:
                year_link.symlink_to(real_year, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            with self.assertRaises(WorkspaceCatalogError):
                scan_workspace(workspace)

        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            year = workspace.runs_directory / "2026"
            year.mkdir(parents=True)
            real_month = Path(temp) / "real-month"
            real_month.mkdir()
            month_link = year / "07"
            try:
                month_link.symlink_to(real_month, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            with self.assertRaises(WorkspaceCatalogError):
                scan_workspace(workspace)

    def test_catalog_reparse_attribute_is_rejected_without_symlink_privilege(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            run = workspace.runs_directory / "2026" / "07" / canonical_run_directory_name("2026-07-31T12:00:00Z", "scan", _RUN_IDS[0])
            run.mkdir(parents=True)
            real_lstat = Path.lstat
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

            def mocked_lstat(path: Path) -> object:
                result = real_lstat(path)
                if path == run:
                    return mock.Mock(st_mode=stat.S_IFDIR, st_file_attributes=reparse_flag)
                return result

            with mock.patch("tw_stock_tool.artifacts.catalog._lstat_candidate", side_effect=mocked_lstat):
                entries = scan_workspace(workspace).entries
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].findings[0].code, RunFindingCode.UNSAFE_PATH)

    def test_public_catalog_models_snapshot_nested_collections_and_reject_bad_types(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            finding = RunFinding("missing_artifact", "artifact does not exist", workspace.root / "missing")
            finding_list = [finding]
            symbol_list = ["2330.TW"]
            entry = _catalog_entry(workspace, findings=finding_list, canonical_symbols=symbol_list)  # type: ignore[arg-type]
            catalog_entries = [entry]
            catalog = WorkspaceCatalog(workspace, catalog_entries)
            finding_list.append(RunFinding(RunFindingCode.UNSAFE_PATH, "unsafe", workspace.root))
            catalog_entries.clear()
            symbol_list.append("2317.TW")
            self.assertEqual(catalog.entries, (entry,))
            self.assertEqual(entry.findings, (finding,))
            self.assertEqual(entry.canonical_symbols, ("2330.TW",))

            with self.assertRaises(WorkspaceValidationError):
                RunFinding(1, "bad", workspace.root)  # type: ignore[arg-type]
            with self.assertRaises(WorkspaceValidationError):
                RunFinding("not-a-code", "bad", workspace.root)
            with self.assertRaises(WorkspaceValidationError):
                RunFinding(RunFindingCode.UNSAFE_PATH, " ", workspace.root)
            with self.assertRaises(WorkspaceValidationError):
                RunFinding(RunFindingCode.UNSAFE_PATH, "bad", object())  # type: ignore[arg-type]
            with self.assertRaises(WorkspaceValidationError):
                _catalog_entry(workspace, health="not-a-health")  # type: ignore[arg-type]
            with self.assertRaises(WorkspaceValidationError):
                _catalog_entry(workspace, findings=(object(),))  # type: ignore[arg-type]
            with self.assertRaises(WorkspaceValidationError):
                _catalog_entry(workspace, artifact_count=-1)
            with self.assertRaises(WorkspaceValidationError):
                WorkspaceCatalog(workspace, [object()])  # type: ignore[list-item]
            with self.assertRaises(WorkspaceValidationError):
                _catalog_entry(workspace, manifest=object())  # type: ignore[arg-type]

    def test_catalog_classifies_unsupported_unknown_duplicate_and_model_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            cases = (
                ("2026-07-31T12:00:00Z", "scan", _RUN_IDS[0], lambda value: value.replace('"schema_version": "1.0"', '"schema_version": "2.0"', 1), RunFindingCode.UNSUPPORTED_SCHEMA),
                ("2026-07-31T12:01:00Z", "daily", _RUN_IDS[1], lambda value: value.replace('"schema_version": "1.0",', '"schema_version": "1.0",\n  "unknown": 1,', 1), RunFindingCode.INVALID_MANIFEST),
                ("2026-07-31T12:02:00Z", "backtest", _RUN_IDS[2], lambda value: value.replace('"status": "success",', '"status": "success",\n  "status": "success",', 1), RunFindingCode.INVALID_MANIFEST),
                ("2026-07-31T12:03:00Z", "daily-report", _RUN_IDS[3], lambda value: value.replace('"success_count": 0,', '"success_count": -1,', 1), RunFindingCode.INVALID_MANIFEST),
            )
            expected: dict[str, RunFindingCode] = {}
            for created_at, workflow, run_id, transform, code in cases:
                run = workspace.allocate_run_directory(created_at, workflow, run_id)
                run.manifest_path.write_text(transform(export_run_manifest_json(_manifest(run_id, created_at, workflow))), encoding="utf-8")
                expected[run.path.name] = code
            entries = {entry.run_directory.name: entry for entry in scan_workspace(workspace).entries}
            self.assertEqual({name: entry.findings[0].code for name, entry in entries.items()}, expected)

    def test_catalog_duplicate_run_id_marks_all_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            first = workspace.allocate_run_directory("2026-07-31T12:00:00Z", "scan", _RUN_IDS[0])
            second = workspace.allocate_run_directory("2026-07-31T12:01:00Z", "daily", _RUN_IDS[0])
            first.write_manifest(_manifest())
            second.write_manifest(_manifest(created_at="2026-07-31T12:01:00Z", workflow="daily"))
            entries = scan_workspace(workspace).entries
            self.assertEqual([entry.health for entry in entries], [RunHealth.INVALID, RunHealth.INVALID])
            self.assertTrue(all(entry.findings[-1].code is RunFindingCode.DUPLICATE_RUN_ID for entry in entries))

    def test_catalog_same_timestamp_uses_run_id_tiebreaker(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            first = workspace.allocate_run_directory("2026-07-31T12:00:00Z", "scan", _RUN_IDS[1])
            second = workspace.allocate_run_directory("2026-07-31T12:00:00Z", "daily", _RUN_IDS[0])
            first.write_manifest(_manifest(run_id=_RUN_IDS[1]))
            second.write_manifest(_manifest(run_id=_RUN_IDS[0], workflow="daily"))
            entries = scan_workspace(workspace).entries
            self.assertEqual([entry.run_id for entry in entries], sorted((_RUN_IDS[0], _RUN_IDS[1])))

    def test_catalog_ignores_noncanonical_and_bad_year_month(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            bad = workspace.runs_directory / "not-a-year" / "13"
            bad.mkdir(parents=True)
            (bad / "20260731T120000Z_scan_550e8400").mkdir()
            other = workspace.runs_directory / "2026" / "07" / "not-a-run"
            other.mkdir(parents=True)
            self.assertEqual(scan_workspace(workspace).entries, ())

    def test_manifest_write_failure_and_readback_failure_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / "workspace")
            run = workspace.allocate_run_directory("2026-07-31T12:00:00Z", "scan", _RUN_IDS[0])
            with mock.patch("tw_stock_tool.artifacts.workspace.os.fsync", side_effect=OSError("write failed")):
                with self.assertRaises(WorkspaceManifestError) as raised:
                    run.write_manifest(_manifest())
            self.assertIsInstance(raised.exception.__cause__, OSError)
            self.assertEqual(list(run.path.glob(".manifest.*.tmp")), [])

            with mock.patch("tw_stock_tool.research_run.serialization.load_run_manifest_json", side_effect=ResearchRunSerializationError("readback failed")):
                with self.assertRaises(WorkspaceManifestError) as raised:
                    run.write_manifest(_manifest())
            self.assertIsInstance(raised.exception.__cause__, ResearchRunSerializationError)

    def test_workspace_relocation_preserves_relative_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            original = parent / "original"
            workspace = Workspace(original)
            run = workspace.allocate_run_directory("2026-07-31T12:00:00Z", "scan", _RUN_IDS[0])
            artifact = run.resolve_artifact_path("artifacts/report.md")
            artifact.parent.mkdir()
            artifact.write_text("report", encoding="utf-8")
            run.write_manifest(_manifest(artifacts=(ArtifactReference("report", "artifacts/report.md", "text/markdown", None),)))
            relocated = parent / "relocated"
            move(str(original), str(relocated))
            new_workspace = Workspace(relocated)
            entry = scan_workspace(new_workspace).entries[0]
            self.assertEqual(entry.health, RunHealth.VALID)
            self.assertEqual(entry.manifest_path.parent, relocated / "runs" / "2026" / "07" / run.path.name)
            self.assertTrue((entry.manifest_path.parent / "artifacts" / "report.md").exists())
            self.assertNotIn(str(original), entry.manifest_path.read_text(encoding="utf-8"))

    def test_artifacts_package_has_no_forbidden_imports(self) -> None:
        root = Path(__file__).parents[1] / "src" / "tw_stock_tool" / "artifacts"
        forbidden = ("tw_stock_tool.cli", "tw_stock_tool.application", "tw_stock_tool.analysis", "tw_stock_tool.backtest", "tw_stock_tool.backtesting", "tw_stock_tool.data", "tw_stock_tool.reports", "tw_stock_tool.gui", "tw_stock_tool.paper_trading")
        for source in root.glob("*.py"):
            tree = ast.parse(source.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                for name in names:
                    self.assertFalse(name.startswith(forbidden), f"forbidden import {name} in {source}")


if __name__ == "__main__":
    unittest.main()
