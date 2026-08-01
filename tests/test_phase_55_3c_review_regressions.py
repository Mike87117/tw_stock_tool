from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tw_stock_tool.application import BacktestRunRequest, DailyRunRequest, ScanRunRequest, SymbolRequest
from tw_stock_tool.application.workspace_execution import WorkspaceRunLifecycle
from tw_stock_tool.application.workspace_run import run_backtest_workspace, run_daily_workspace, run_scan_workspace
from tw_stock_tool.artifacts import RunHealth, Workspace, scan_catalog
from tw_stock_tool.analysis.scanner import ScanConfig
from tw_stock_tool.cli import twstock_cli
from tw_stock_tool.reports.daily_pipeline import DailyPipelineConfig
from tw_stock_tool.research_run import scan as scan_workflow
from tw_stock_tool.research_run.models import (
    RUN_MANIFEST_SCHEMA_VERSION,
    ArtifactReference,
    ResearchRunResult,
    RunConfig,
    RunManifest,
)
from tw_stock_tool.research_run.serialization import export_run_manifest_json


def _source_manifest(output_dir: Path, provisional: Path, *, artifact: Path | None = None, external_config: bool = False) -> RunManifest:
    config = RunConfig(
        workflow="scan",
        universe="all",
        canonical_symbols=("2330.TW",),
        period="1y",
        interval="1d",
        auto_adjust=False,
        force_refresh=False,
        strategy=None,
        backtest=None,
        parameter_sweep=None,
        walk_forward=None,
        ml=None,
        workflow_options={
            "output_dir": (Path("outside") if external_config else output_dir).as_posix(),
            "manifest_path": provisional.as_posix(),
        },
    )
    artifacts = () if artifact is None else (ArtifactReference("report", artifact.as_posix(), "text/plain", None),)
    return RunManifest(
        RUN_MANIFEST_SCHEMA_VERSION,
        "550e8400-e29b-41d4-a716-446655440000",
        "2026-08-01T00:00:00Z",
        "0.4.0",
        "success",
        config,
        (),
        0,
        0,
        0,
        artifacts,
        (),
        (),
    )


class WorkspacePostRunFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        symbol = SymbolRequest("2330", "2330.TW")
        self.request = ScanRunRequest((symbol,), "all", ScanConfig(max_workers=1), "output")

    def _run_and_assert_failure(self, writer) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"

            def runner(*args, output_dir, manifest_path, **kwargs):
                source = _source_manifest(Path(output_dir), Path(manifest_path))
                writer(source, Path(output_dir), Path(manifest_path), Path(temp))
                return ResearchRunResult(source, {"unexpected": "success"}, source.artifacts)

            with patch.object(scan_workflow, "run_scan_research", side_effect=runner):
                with self.assertRaises(Exception):
                    run_scan_workspace(self.request, workspace)

            catalog = scan_catalog(Workspace(workspace))
            self.assertEqual(len(catalog.entries), 1)
            entry = catalog.entries[0]
            self.assertIs(entry.health, RunHealth.VALID)
            self.assertEqual(entry.manifest.status, "failure")
            self.assertEqual(entry.artifact_count, 0)

    def test_post_run_processing_failures_publish_valid_fallback_manifest(self) -> None:
        cases = (
            ("missing", lambda source, output, provisional, temp: None),
            ("invalid_json", lambda source, output, provisional, temp: provisional.write_text("{", encoding="utf-8")),
            ("invalid_schema", lambda source, output, provisional, temp: provisional.write_text('{"schema_version":"bad"}', encoding="utf-8")),
            ("missing_artifact", lambda source, output, provisional, temp: provisional.write_text(export_run_manifest_json(_source_manifest(output, provisional, artifact=output / "missing.txt")), encoding="utf-8")),
            ("external_artifact", lambda source, output, provisional, temp: provisional.write_text(export_run_manifest_json(_source_manifest(output, provisional, artifact=temp / "outside.txt")), encoding="utf-8")),
            ("normalization", lambda source, output, provisional, temp: provisional.write_text(export_run_manifest_json(_source_manifest(output, provisional, external_config=True)), encoding="utf-8")),
        )
        for name, writer in cases:
            with self.subTest(name=name):
                self._run_and_assert_failure(writer)

    def test_failure_publication_preserves_post_processing_error_as_cause(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"

            def runner(*args, output_dir, manifest_path, **kwargs):
                source = _source_manifest(Path(output_dir), Path(manifest_path))
                return ResearchRunResult(source, {}, ())

            with patch.object(scan_workflow, "run_scan_research", side_effect=runner), patch.object(
                WorkspaceRunLifecycle, "publish", side_effect=OSError("publish denied")
            ):
                with self.assertRaisesRegex(RuntimeError, "did not produce.*publish denied") as raised:
                    run_scan_workspace(self.request, workspace)
            self.assertIsNotNone(raised.exception.__cause__)

    def test_callback_and_loader_validation_happens_before_allocation(self) -> None:
        symbol = SymbolRequest("2330", "2330.TW")
        daily_request = DailyRunRequest((symbol,), "all", DailyPipelineConfig(), "output")
        backtest_request = BacktestRunRequest(symbol, "ma_cross", "output")
        cases = (
            (lambda root: run_scan_workspace(self.request, root, progress_callback=object()), "progress_callback"),
            (lambda root: run_daily_workspace(daily_request, root, status_callback=object()), "status_callback"),
            (lambda root: run_backtest_workspace(backtest_request, root, stage_callback=object()), "stage_callback"),
            (lambda root: run_scan_workspace(self.request, root, market_data_loader=object()), "market_data_loader"),
        )
        for call, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temp:
                workspace = Path(temp) / "workspace"
                with self.assertRaisesRegex(ValueError, message):
                    call(workspace)
                self.assertFalse(workspace.exists())

    def test_fallback_uses_project_tool_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"

            def runner(*args, output_dir, manifest_path, **kwargs):
                source = _source_manifest(Path(output_dir), Path(manifest_path))
                return ResearchRunResult(source, {}, ())

            with patch.object(scan_workflow, "run_scan_research", side_effect=runner):
                with self.assertRaises(Exception):
                    run_scan_workspace(self.request, workspace)
            entry = scan_catalog(Workspace(workspace)).entries[0]
            self.assertEqual(entry.manifest.tool_version, scan_workflow._tool_version())


class UnifiedWorkspaceCliTests(unittest.TestCase):
    def test_research_help_is_forwarded_to_underlying_parser(self) -> None:
        for command in ("scan", "daily", "backtest-report"):
            with self.subTest(command=command):
                stdout, stderr = StringIO(), StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                    twstock_cli.main([command, "--help"])
                self.assertEqual(raised.exception.code, 0)
                self.assertIn("--workspace", stdout.getvalue())
                self.assertNotIn("Traceback", stdout.getvalue() + stderr.getvalue())

    def test_workspace_argument_is_forwarded_unchanged(self) -> None:
        cases = (
            ("scan", twstock_cli.scan_stocks, "scan_stocks.py"),
            ("daily", twstock_cli.daily_report_cli, "daily_report_cli.py"),
            ("backtest-report", twstock_cli.backtest_report, "backtest_report.py"),
        )
        for command, module, program in cases:
            with self.subTest(command=command):
                captured: list[list[str]] = []

                def fake_main() -> None:
                    import sys
                    captured.append(sys.argv[:])

                with patch.object(module, "main", side_effect=fake_main):
                    self.assertEqual(twstock_cli.main([command, "--workspace", "runs"]), 0)
                self.assertEqual(captured, [[program, "--workspace", "runs"]])


if __name__ == "__main__":
    unittest.main()
