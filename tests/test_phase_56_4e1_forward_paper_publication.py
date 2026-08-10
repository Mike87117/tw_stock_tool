from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from tw_stock_tool.application.forward_paper_publication import (
    ForwardPaperPublicationApplicationError,
    publish_forward_paper_workspace_package,
)
from tw_stock_tool.artifacts import (
    RunHealth,
    Workspace,
    WorkspaceCollisionError,
    WorkspacePathError,
    scan_workspace,
    write_managed_text,
)
from tw_stock_tool.forward_paper.publication import (
    PUBLICATION_ARTIFACT_SPECS,
    PUBLICATION_INDEX_PATH,
    ForwardPaperPublicationError,
    export_forward_paper_publication_index_json,
    load_forward_paper_publication_index_json,
)
from tw_stock_tool.research_run.serialization import export_run_manifest_json


class ForwardPaperPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from test_phase_56_4d3_forward_eligibility import (
            ForwardEligibilityEvidenceTests,
        )

        ForwardEligibilityEvidenceTests.setUpClass()
        cls.d3 = ForwardEligibilityEvidenceTests(
            "test_genuine_chain_builds_active_evidence_with_canonical_d2_sha"
        )

    def setUp(self) -> None:
        recommendation, ledger, bundle, execution = self.d3.case
        self.recommendation = recommendation
        self.bundle = bundle
        self.values = {
            "activation": self.d3.d2.fixture.activation,
            "qualification_artifact": self.d3.d2.fixture.source,
            "ledger": ledger,
            "recommendation_evidence_by_id": {
                recommendation.recommendation_id: recommendation
            },
            "portfolio_result": bundle.portfolio_result,
            "execution_evidence": execution,
            "portfolio_trace": bundle.portfolio_trace,
            "metrics_evidence": self.d3.metrics,
            "eligibility_evidence": self.d3._build(),
            "expected_portfolio_trace_sha256": bundle.portfolio_trace_sha256,
            "publication_id": "b23e4567-e89b-42d3-a456-426614174000",
            "created_at": "2025-04-02T00:00:02Z",
        }

    def _publish(self, root: str | Path, **overrides):
        values = dict(self.values)
        values.update(overrides)
        return publish_forward_paper_workspace_package(root, **values)

    def test_genuine_package_writes_all_artifacts_index_last_and_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = self._publish(temporary)
            artifact_paths = tuple(item.path for item in result.manifest.artifacts)
            recommendation_path = (
                "artifacts/forward-paper/recommendations/"
                f"{self.recommendation.recommendation_id}.json"
            )
            self.assertEqual(
                artifact_paths,
                (
                    PUBLICATION_ARTIFACT_SPECS[0][3],
                    PUBLICATION_ARTIFACT_SPECS[1][3],
                    PUBLICATION_ARTIFACT_SPECS[2][3],
                    recommendation_path,
                    *(spec[3] for spec in PUBLICATION_ARTIFACT_SPECS[3:]),
                    PUBLICATION_INDEX_PATH,
                ),
            )
            self.assertEqual(len(artifact_paths), 10)
            self.assertTrue(result.manifest_path.is_file())
            self.assertEqual(result.manifest.schema_version, "1.0")
            self.assertEqual(result.manifest.config.workflow, "forward-paper-gate")
            self.assertEqual(result.manifest.data_sources, ())
            self.assertEqual(result.manifest.config.workflow_options, {})
            self.assertNotIn("sha256", export_run_manifest_json(result.manifest))
            entry = scan_workspace(Workspace.open_existing(temporary)).entries[0]
            self.assertIs(entry.health, RunHealth.VALID)

    def test_index_anchors_root_hashes_and_original_recommendation_in_ledger_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = self._publish(temporary)
            index = result.publication_index
            self.assertEqual(
                tuple(anchor.role for anchor in index.artifact_anchors),
                tuple(spec[0] for spec in PUBLICATION_ARTIFACT_SPECS),
            )
            self.assertEqual(
                tuple(anchor.recommendation_id for anchor in index.recommendation_anchors),
                tuple(decision.recommendation_id for decision in self.values["ledger"].decisions),
            )
            self.assertEqual(
                index.portfolio_trace_sha256,
                self.values["expected_portfolio_trace_sha256"],
            )
            self.assertEqual(
                index.metrics_sha256,
                self.values["eligibility_evidence"].metrics_sha256,
            )
            self.assertFalse(hasattr(index, "publication_sha256"))
            text = (result.run_directory.path / PUBLICATION_INDEX_PATH).read_text(encoding="utf-8")
            self.assertEqual(load_forward_paper_publication_index_json(text), index)
            self.assertEqual(export_forward_paper_publication_index_json(index), text)

    def test_bad_chain_and_wrong_external_trace_anchor_fail_before_run_allocation(self):
        forged = replace(
            self.values["eligibility_evidence"],
            metrics_sha256="f" * 64,
        )
        with tempfile.TemporaryDirectory() as temporary:
            with patch(
                "tw_stock_tool.application.forward_paper_publication.WorkspaceRunLifecycle.begin",
                side_effect=AssertionError("run allocated"),
            ) as begin:
                with self.assertRaises(ForwardPaperPublicationApplicationError):
                    self._publish(temporary, eligibility_evidence=forged)
                with self.assertRaises(ForwardPaperPublicationApplicationError):
                    self._publish(temporary, expected_portfolio_trace_sha256="0" * 64)
            begin.assert_not_called()
            self.assertFalse(Path(temporary, "runs").exists())

    def test_missing_extra_or_non_schema_1_1_recommendation_fails_before_allocation(self):
        invalid_mappings = ({}, {
            self.recommendation.recommendation_id: self.recommendation,
            str(uuid4()): self.recommendation,
        })
        with tempfile.TemporaryDirectory() as temporary:
            with patch(
                "tw_stock_tool.application.forward_paper_publication.WorkspaceRunLifecycle.begin"
            ) as begin:
                for mapping in invalid_mappings:
                    with self.subTest(mapping=mapping):
                        with self.assertRaises(ForwardPaperPublicationApplicationError):
                            self._publish(temporary, recommendation_evidence_by_id=mapping)
            begin.assert_not_called()

    def test_readback_failure_leaves_orphan_without_success_manifest(self):
        original = Path.read_bytes

        def altered(path: Path, *args, **kwargs):
            value = original(path, *args, **kwargs)
            if path.name == "qualification.json":
                return value + b" "
            return value

        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(Path, "read_bytes", altered):
                with self.assertRaises(ForwardPaperPublicationApplicationError):
                    self._publish(temporary)
            manifests = tuple(Path(temporary).rglob("manifest.json"))
            self.assertEqual(manifests, ())
            self.assertEqual(len(tuple(Path(temporary).rglob("qualification.json"))), 1)

    def test_publication_index_strict_json_and_frozen_role_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            index = self._publish(temporary).publication_index
        payload = json.loads(export_forward_paper_publication_index_json(index))
        cases = []
        missing = dict(payload)
        missing.pop("publication_id")
        cases.append(missing)
        unknown = dict(payload)
        unknown["sha256"] = "0" * 64
        cases.append(unknown)
        bool_id = dict(payload)
        bool_id["publication_id"] = True
        cases.append(bool_id)
        reordered = dict(payload)
        reordered["artifact_anchors"] = list(reversed(payload["artifact_anchors"]))
        cases.append(reordered)
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(ForwardPaperPublicationError):
                    load_forward_paper_publication_index_json(json.dumps(case))
        duplicate = export_forward_paper_publication_index_json(index).replace(
            '"publication_id":', '"publication_id": "b23e4567-e89b-42d3-a456-426614174000", "publication_id":',
            1,
        )
        with self.assertRaises(ForwardPaperPublicationError):
            load_forward_paper_publication_index_json(duplicate)
        with self.assertRaises(ForwardPaperPublicationError):
            load_forward_paper_publication_index_json('{"created_at": NaN}')

    def test_forged_c2_d1_and_d2_each_fail_before_allocation(self):
        forged_values = (
            {
                "execution_evidence": replace(
                    self.values["execution_evidence"],
                    evidence_id=str(uuid4()),
                )
            },
            {
                "portfolio_trace": replace(
                    self.values["portfolio_trace"],
                    portfolio_result_sha256="f" * 64,
                )
            },
            {
                "metrics_evidence": replace(
                    self.values["metrics_evidence"],
                    metrics_id=str(uuid4()),
                )
            },
        )
        with tempfile.TemporaryDirectory() as temporary:
            with patch(
                "tw_stock_tool.application.forward_paper_publication.WorkspaceRunLifecycle.begin"
            ) as begin:
                for values in forged_values:
                    with self.subTest(values=values):
                        with self.assertRaises(ForwardPaperPublicationApplicationError):
                            self._publish(temporary, **values)
            begin.assert_not_called()

    def test_publisher_never_calls_fetch_replay_runtime_or_backtest(self):
        targets = (
            "tw_stock_tool.application.forward_paper_execution.run_forward_paper_execution_replay",
            "tw_stock_tool.application.forward_paper_execution.run_forward_paper_execution_replay_with_trace",
            "tw_stock_tool.paper_trading.portfolio_engine.run_simulated_portfolio_trading_result",
            "tw_stock_tool.paper_trading.coordinator.run_chronological_multi_symbol_simulated_paper_trading",
            "tw_stock_tool.backtesting.walk_forward.run_strategy_backtest",
            "tw_stock_tool.data.data_loader.download_tw_stock",
        )
        patches = [patch(target, side_effect=AssertionError(target)) for target in targets]
        mocks = [item.start() for item in patches]
        try:
            with tempfile.TemporaryDirectory() as temporary:
                self._publish(temporary)
        finally:
            for item in reversed(patches):
                item.stop()
        self.assertTrue(all(mock.call_count == 0 for mock in mocks))

    def test_generic_writer_fails_closed_on_mocked_reparse_component(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Workspace(temporary)
            run = workspace.allocate_run_directory(
                "2025-04-02T00:00:02Z",
                "forward-paper-gate",
                "d23e4567-e89b-42d3-a456-426614174000",
            )
            artifacts = run.path / "artifacts"
            artifacts.mkdir()
            reparse_stat = artifacts.lstat()
            with patch(
                "tw_stock_tool.artifacts.workspace._is_reparse_point",
                side_effect=lambda result: result == reparse_stat,
            ):
                with self.assertRaises(WorkspacePathError):
                    write_managed_text(run, "artifacts/a.json", "{}\n")

    def test_generic_writer_is_no_clobber_and_rejects_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Workspace(temporary)
            run = workspace.allocate_run_directory(
                "2025-04-02T00:00:02Z",
                "forward-paper-gate",
                "c23e4567-e89b-42d3-a456-426614174000",
            )
            path = write_managed_text(run, "artifacts/a.json", "{}\n")
            self.assertEqual(path.read_text(encoding="utf-8"), "{}\n")
            with self.assertRaises(WorkspaceCollisionError):
                write_managed_text(run, "artifacts/a.json", "{}\n")
            for unsafe in ("/a.json", "../a.json", "artifacts\\a.json", "C:/a.json", "manifest.json"):
                with self.subTest(path=unsafe):
                    with self.assertRaises(WorkspacePathError):
                        write_managed_text(run, unsafe, "{}\n")

    def test_workspace_package_remains_valid_after_relocation(self):
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as relocated:
            result = self._publish(temporary)
            destination = Path(relocated, "workspace")
            shutil.copytree(temporary, destination)
            entry = scan_workspace(Workspace.open_existing(destination)).entries[0]
            self.assertIs(entry.health, RunHealth.VALID)
            self.assertEqual(entry.manifest.run_id, result.run_id)


if __name__ == "__main__":
    unittest.main()

