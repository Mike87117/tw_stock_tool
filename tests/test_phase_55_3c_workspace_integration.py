from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tw_stock_tool.application import BacktestRunRequest, DailyRunRequest, ScanRunRequest, SymbolRequest
from tw_stock_tool.application.workspace_run import (
    run_backtest_workspace,
    run_daily_workspace,
    run_scan_workspace,
)
from tw_stock_tool.artifacts import RunHealth, Workspace, scan_catalog
from tw_stock_tool.analysis.scanner import ScanConfig
from tw_stock_tool.reports.daily_pipeline import DailyPipelineConfig
from tw_stock_tool.research_run import backtest as backtest_workflow
from tw_stock_tool.research_run import daily as daily_workflow
from tw_stock_tool.research_run import scan as scan_workflow
from tw_stock_tool.research_run.models import (
    RUN_MANIFEST_SCHEMA_VERSION,
    ArtifactReference,
    DataSourceRecord,
    ResearchRunResult,
    RunConfig,
    RunManifest,
)
from tw_stock_tool.research_run.serialization import export_run_manifest_json


def _config(workflow: str, symbols: tuple[str, ...], output_dir: Path, manifest_path: Path) -> RunConfig:
    return RunConfig(
        workflow=workflow,
        universe="all",
        canonical_symbols=symbols,
        period="1y",
        interval="1d",
        auto_adjust=False,
        force_refresh=False,
        strategy="ma_cross_strategy" if workflow == "backtest" else None,
        backtest=None,
        parameter_sweep=None,
        walk_forward=None,
        ml=None,
        workflow_options={
            "output_dir": output_dir.as_posix(),
            "manifest_path": manifest_path.as_posix(),
        },
    )


def _source_manifest(workflow: str, output_dir: Path, manifest_path: Path) -> RunManifest:
    artifact_path = output_dir / f"{workflow}.txt"
    artifact_path.write_text(workflow, encoding="utf-8")
    config = _config(workflow, ("2330.TW",), output_dir, manifest_path)
    return RunManifest(
        RUN_MANIFEST_SCHEMA_VERSION,
        "550e8400-e29b-41d4-a716-446655440000",
        "2026-08-01T00:00:00Z",
        "0.4.0",
        "success",
        config,
        (
            DataSourceRecord(
                "2330.TW", "2330", "fake", "1y", "1d", False,
                "live", "not_applicable", True, None,
            ),
        ),
        1,
        0,
        0,
        (ArtifactReference(workflow, artifact_path.as_posix(), "text/plain", None),),
        (),
        (),
    )


def _fake_success(workflow: str):
    def run(*args, output_dir, manifest_path, **kwargs):
        source = _source_manifest(workflow, Path(output_dir), Path(manifest_path))
        Path(manifest_path).write_text(export_run_manifest_json(source), encoding="utf-8")
        return ResearchRunResult(source, {"workflow": workflow}, source.artifacts)

    return run


class WorkspaceIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.symbol = SymbolRequest("2330", "2330.TW")
        self.scan_request = ScanRunRequest((self.symbol,), "all", ScanConfig(max_workers=1), "output")
        self.daily_request = DailyRunRequest((self.symbol,), "all", DailyPipelineConfig(), "output")
        self.backtest_request = BacktestRunRequest(self.symbol, "ma_cross", "output")

    def test_three_workflows_use_canonical_manifest_and_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            with patch.object(scan_workflow, "run_scan_research", side_effect=_fake_success("scan")), patch.object(
                daily_workflow, "run_daily_report_research", side_effect=_fake_success("daily")
            ), patch.object(backtest_workflow, "run_backtest_research", side_effect=_fake_success("backtest")):
                results = (
                    run_scan_workspace(self.scan_request, workspace),
                    run_daily_workspace(self.daily_request, workspace),
                    run_backtest_workspace(self.backtest_request, workspace),
                )

            self.assertEqual({result.manifest.config.workflow for result in results}, {"scan", "daily", "backtest"})
            catalog = scan_catalog(Workspace(workspace))
            self.assertEqual(len(catalog.entries), 3)
            self.assertTrue(all(entry.health is RunHealth.VALID for entry in catalog.entries))
            self.assertTrue(all(entry.manifest_path.name == "manifest.json" for entry in catalog.entries))
            self.assertTrue(all("\\" not in artifact.path and not Path(artifact.path).is_absolute() for result in results for artifact in result.manifest.artifacts))

    def test_identical_runs_are_append_only_and_workspace_is_portable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            with patch.object(scan_workflow, "run_scan_research", side_effect=_fake_success("scan")):
                first = run_scan_workspace(self.scan_request, workspace)
                second = run_scan_workspace(self.scan_request, workspace)
            self.assertNotEqual(first.manifest.run_id, second.manifest.run_id)
            self.assertEqual(len(scan_catalog(Workspace(workspace)).entries), 2)

            moved = Path(temp) / "moved-workspace"
            shutil.move(str(workspace), moved)
            catalog = scan_catalog(Workspace(moved))
            self.assertTrue(all(entry.health is RunHealth.VALID for entry in catalog.entries))

    def test_external_output_options_fail_before_workspace_allocation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            conflicting = ScanRunRequest((self.symbol,), "all", ScanConfig(max_workers=1), "external")
            with self.assertRaisesRegex(ValueError, "output-dir"):
                run_scan_workspace(conflicting, workspace)
            self.assertFalse(workspace.exists())

    def test_failure_publishes_failure_manifest_without_artifacts(self) -> None:
        def fail(*args, output_dir, manifest_path, **kwargs):
            source = _source_manifest("backtest", Path(output_dir), Path(manifest_path))
            failed = RunManifest(
                source.schema_version, source.run_id, source.created_at, source.tool_version,
                "failure", source.config, source.data_sources, 0, 1, 0, (), ("backtest: boom",), (),
            )
            Path(manifest_path).write_text(export_run_manifest_json(failed), encoding="utf-8")
            raise RuntimeError("boom")

        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            with patch.object(backtest_workflow, "run_backtest_research", side_effect=fail):
                with self.assertRaisesRegex(RuntimeError, "boom"):
                    run_backtest_workspace(self.backtest_request, workspace)
            catalog = scan_catalog(Workspace(workspace))
            self.assertEqual(len(catalog.entries), 1)
            self.assertEqual(catalog.entries[0].manifest.status, "failure")
            self.assertEqual(catalog.entries[0].artifact_count, 0)


if __name__ == "__main__":
    unittest.main()
