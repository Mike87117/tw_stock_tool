from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from tw_stock_tool.application.forward_paper_inspection import (
    inspect_forward_paper_workspace_package,
)
from tw_stock_tool.artifacts import (
    WorkspaceCatalogError,
    WorkspaceDuplicateRunIdError,
    WorkspaceRunNotFoundError,
    canonical_run_directory_name,
)
from tw_stock_tool.forward_paper.inspection import (
    ForwardPaperPackageFindingCode as Code,
    ForwardPaperPackageHealth,
)
from tw_stock_tool.forward_paper.publication import (
    PUBLICATION_INDEX_PATH,
    export_forward_paper_publication_index_json,
)
from tw_stock_tool.forward_paper.execution_serialization import (
    export_forward_execution_evidence_json,
)
from tw_stock_tool.recommendation.artifacts import (
    export_recommendation_artifact_json,
)
from tw_stock_tool.recommendation.models import (
    CurrentSignalSnapshot,
    RecommendationEvidence,
)
from tw_stock_tool.research_run.models import ArtifactReference
from tw_stock_tool.research_run.serialization import export_run_manifest_json


class ForwardPaperInspectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from test_phase_56_4e1_forward_paper_publication import (
            ForwardPaperPublicationTests,
        )

        ForwardPaperPublicationTests.setUpClass()
        cls.e1_type = ForwardPaperPublicationTests

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.e1 = self.e1_type(
            "test_genuine_package_writes_all_artifacts_index_last_and_manifest"
        )
        self.e1.setUp()
        self.published = self.e1._publish(self.root)

    def _inspect(self):
        return inspect_forward_paper_workspace_package(
            self.root,
            self.published.run_id,
        )

    def _write_manifest(self, manifest) -> None:
        self.published.manifest_path.write_bytes(
            export_run_manifest_json(manifest).encode("utf-8")
        )

    def _write_index(self, index) -> None:
        (self.published.run_directory.path / PUBLICATION_INDEX_PATH).write_bytes(
            export_forward_paper_publication_index_json(index).encode("utf-8")
        )

    @staticmethod
    def _tree(root: Path):
        return tuple(
            (
                path.relative_to(root).as_posix(),
                path.is_dir(),
                path.stat().st_mtime_ns,
                None if path.is_dir() else path.read_bytes(),
            )
            for path in sorted(root.rglob("*"))
        )

    @staticmethod
    def _with_sha(index, role: str, sha256: str):
        anchors = tuple(
            replace(anchor, sha256=sha256) if anchor.role == role else anchor
            for anchor in index.artifact_anchors
        )
        root_name = {
            "decision_ledger": "ledger_sha256",
            "metrics_evidence": "metrics_sha256",
            "eligibility_evidence": "eligibility_sha256",
        }.get(role, f"{role}_sha256")
        return replace(index, artifact_anchors=anchors, **{root_name: sha256})

    def test_genuine_package_is_valid_with_exact_trusted_summary_and_no_writes(self):
        before = self._tree(self.root)
        targets = (
            "tw_stock_tool.artifacts.workspace.write_managed_text",
            "tw_stock_tool.artifacts.workspace.write_manifest",
            "tw_stock_tool.application.forward_paper_publication.publish_forward_paper_workspace_package",
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
            inspection = self._inspect()
        finally:
            for item in reversed(patches):
                item.stop()
        self.assertIs(inspection.health, ForwardPaperPackageHealth.VALID)
        self.assertEqual(inspection.findings, ())
        self.assertIsNotNone(inspection.summary)
        summary = inspection.summary
        metrics = self.e1.values["metrics_evidence"]
        self.assertEqual(summary.publication_id, self.published.publication_index.publication_id)
        self.assertEqual(summary.eligibility_state, self.e1.values["eligibility_evidence"].state)
        self.assertEqual(summary.decision_count, len(self.e1.values["ledger"].decisions))
        self.assertEqual(summary.recommendation_count, 1)
        self.assertEqual(summary.portfolio_observation_count, len(self.e1.values["portfolio_trace"].observations))
        self.assertEqual(summary.filled_count, metrics.execution_health.filled_count)
        self.assertEqual(summary.applied_total_cost, metrics.applied_costs.applied_total_cost)
        self.assertEqual(summary.total_return_pct, metrics.portfolio_metrics.total_return_pct)
        self.assertEqual(summary.max_drawdown_pct, metrics.portfolio_metrics.max_drawdown_pct)
        self.assertFalse(any(hasattr(summary, name) for name in ("live_ready", "broker_approved", "safe_to_trade")))
        self.assertTrue(all(mock.call_count == 0 for mock in mocks))
        self.assertEqual(self._tree(self.root), before)

    def test_relocated_workspace_remains_valid(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary, "workspace")
            shutil.copytree(self.root, destination)
            inspection = inspect_forward_paper_workspace_package(
                destination,
                self.published.run_id,
            )
        self.assertIs(inspection.health, ForwardPaperPackageHealth.VALID)

    def test_unknown_run_reuses_workspace_lookup_exception(self):
        with self.assertRaises(WorkspaceRunNotFoundError):
            inspect_forward_paper_workspace_package(self.root, str(uuid4()))

    def test_duplicate_run_id_reuses_workspace_lookup_exception(self):
        duplicate_created_at = (
            datetime.strptime(
                self.published.manifest.created_at,
                "%Y-%m-%dT%H:%M:%SZ",
            )
            + timedelta(seconds=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        duplicate_name = canonical_run_directory_name(
            duplicate_created_at,
            "forward-paper-gate",
            self.published.run_id,
        )
        duplicate = (
            self.root
            / "runs"
            / duplicate_created_at[:4]
            / duplicate_created_at[5:7]
            / duplicate_name
        )
        duplicate.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.published.run_directory.path, duplicate)
        manifest = replace(
            self.published.manifest,
            created_at=duplicate_created_at,
        )
        (duplicate / "manifest.json").write_bytes(
            export_run_manifest_json(manifest).encode("utf-8")
        )
        with self.assertRaises(WorkspaceDuplicateRunIdError):
            self._inspect()

    def test_manifest_status_other_than_success_is_invalid(self):
        manifest = replace(
            self.published.manifest,
            status="partial",
            partial_count=1,
        )
        self._write_manifest(manifest)
        inspection = self._inspect()
        self.assertEqual(
            inspection.findings[0].code,
            Code.MANIFEST_CONTRACT_MISMATCH,
        )

    def test_manifest_config_mismatch_is_invalid(self):
        config = replace(self.published.manifest.config, period="5y")
        self._write_manifest(replace(self.published.manifest, config=config))
        inspection = self._inspect()
        self.assertIs(inspection.health, ForwardPaperPackageHealth.INVALID)
        self.assertEqual(inspection.findings[0].code, Code.MANIFEST_CONTRACT_MISMATCH)
        self.assertIsNone(inspection.summary)

    def test_wrong_manifest_workflow_cannot_be_trusted(self):
        config = replace(self.published.manifest.config, workflow="scan")
        self._write_manifest(replace(self.published.manifest, config=config))
        inspection = self._inspect()
        self.assertIs(inspection.health, ForwardPaperPackageHealth.INVALID)
        self.assertEqual(inspection.findings[0].code, Code.WORKSPACE_RUN_INVALID)

    def test_manifest_extra_or_reordered_reference_is_invalid(self):
        foreign_path = self.published.run_directory.path / "artifacts/foreign.json"
        foreign_path.write_text("{}\n", encoding="utf-8")
        foreign = ArtifactReference(
            "foreign",
            "artifacts/foreign.json",
            "application/json",
            "1.0",
        )
        cases = (
            self.published.manifest.artifacts[:-1],
            self.published.manifest.artifacts + (foreign,),
            tuple(reversed(self.published.manifest.artifacts)),
        )
        for artifacts in cases:
            with self.subTest(artifacts=artifacts):
                self._write_manifest(replace(self.published.manifest, artifacts=artifacts))
                inspection = self._inspect()
                self.assertIs(inspection.health, ForwardPaperPackageHealth.INVALID)
                self.assertIn(
                    inspection.findings[0].code,
                    (Code.ARTIFACT_REFERENCE_MISMATCH, Code.WORKSPACE_RUN_INVALID),
                )

    def test_missing_or_invalid_utf8_artifact_is_invalid(self):
        qualification = self.published.run_directory.path / "artifacts/forward-paper/qualification.json"
        original = qualification.read_bytes()
        qualification.unlink()
        self.assertIs(self._inspect().health, ForwardPaperPackageHealth.INVALID)
        qualification.write_bytes(b"\xff")
        inspection = self._inspect()
        self.assertIs(inspection.health, ForwardPaperPackageHealth.INVALID)
        self.assertIn(
            inspection.findings[0].code,
            (Code.ARTIFACT_READ_FAILURE, Code.WORKSPACE_RUN_INVALID),
        )
        qualification.write_bytes(original)

    def test_whitespace_tamper_is_noncanonical_and_findings_are_deterministic(self):
        paths = (
            "artifacts/forward-paper/activation.json",
            "artifacts/forward-paper/metrics-evidence.json",
        )
        for relative in paths:
            path = self.published.run_directory.path / relative
            path.write_bytes(path.read_bytes() + b" ")
        first = self._inspect()
        second = self._inspect()
        self.assertEqual(first.findings, second.findings)
        self.assertEqual(
            tuple(item.code for item in first.findings),
            (Code.ARTIFACT_NONCANONICAL, Code.ARTIFACT_NONCANONICAL),
        )
        self.assertEqual(
            tuple(item.path for item in first.findings),
            tuple(sorted(paths)),
        )

    def test_strict_invalid_or_noncanonical_index_is_invalid(self):
        index_path = self.published.run_directory.path / PUBLICATION_INDEX_PATH
        original = index_path.read_bytes()
        index_path.write_bytes(original + b" ")
        inspection = self._inspect()
        self.assertEqual(inspection.findings[0].code, Code.PUBLICATION_INDEX_INVALID)
        index_path.write_bytes(original.replace(b'"publication_id":', b'"self_sha256": "0", "publication_id":', 1))
        inspection = self._inspect()
        self.assertEqual(inspection.findings[0].code, Code.PUBLICATION_INDEX_INVALID)

    def test_wrong_root_sha_is_detected_before_trust_chain_use(self):
        index = self._with_sha(
            self.published.publication_index,
            "qualification",
            "0" * 64,
        )
        self._write_index(index)
        inspection = self._inspect()
        self.assertEqual(inspection.findings[0].code, Code.ARTIFACT_SHA256_MISMATCH)

    def test_coherent_c2_file_and_index_rewrite_still_fails_full_chain(self):
        evidence = replace(
            self.e1.values["execution_evidence"],
            evidence_id=str(uuid4()),
        )
        text = export_forward_execution_evidence_json(evidence)
        path = self.published.run_directory.path / "artifacts/forward-paper/execution-evidence.json"
        path.write_bytes(text.encode("utf-8"))
        sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        index = self._with_sha(
            replace(self.published.publication_index, execution_evidence_id=evidence.evidence_id),
            "execution_evidence",
            sha256,
        )
        self._write_index(index)
        inspection = self._inspect()
        self.assertEqual(inspection.findings[0].code, Code.TRUST_CHAIN_INVALID)

    def test_schema_1_0_recommendation_fails_closed_after_hash_validation(self):
        source = self.e1.recommendation
        legacy = RecommendationEvidence(
            schema_version="1.0",
            artifact_type=source.artifact_type,
            recommendation_id=source.recommendation_id,
            generated_at=source.generated_at,
            source_qualification_evaluation_id=source.source_qualification_evaluation_id,
            promotion_state=source.promotion_state,
            strategy_id=source.strategy_id,
            strategy_parameters=source.strategy_parameters,
            qualification_finding_codes=source.qualification_finding_codes,
            signal_snapshot=CurrentSignalSnapshot(
                symbol=source.signal_snapshot.symbol,
                observed_at=source.signal_snapshot.observed_at,
                signal=source.signal_snapshot.signal,
                score=0.0,
                latest_close=source.signal_snapshot.latest_close,
            ),
            action=source.action,
            qualification=source.qualification,
        )
        text = export_recommendation_artifact_json(legacy)
        anchor = self.published.publication_index.recommendation_anchors[0]
        path = self.published.run_directory.path / anchor.path
        path.write_bytes(text.encode("utf-8"))
        sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        updated_anchor = replace(anchor, recommendation_sha256=sha256)
        index = replace(
            self.published.publication_index,
            recommendation_anchors=(updated_anchor,),
        )
        self._write_index(index)
        inspection = self._inspect()
        self.assertEqual(inspection.findings[0].code, Code.RECOMMENDATION_CONTRACT_MISMATCH)

    def test_index_identity_state_and_created_at_mismatches_are_invalid(self):
        eligibility = self.e1.values["eligibility_evidence"]
        cases = (
            replace(self.published.publication_index, activation_id=str(uuid4())),
            replace(
                self.published.publication_index,
                eligibility_state=(
                    type(eligibility.state).PAUSED
                    if eligibility.state.value != "PAUSED"
                    else type(eligibility.state).REVOKED
                ),
            ),
            replace(self.published.publication_index, created_at="2025-04-01T00:00:00Z"),
        )
        for index in cases:
            with self.subTest(index=index):
                self._write_index(index)
                inspection = self._inspect()
                self.assertEqual(inspection.findings[0].code, Code.INDEX_IDENTITY_MISMATCH)

    def test_mocked_reparse_artifact_component_cannot_be_trusted(self):
        path = self.published.run_directory.path / "artifacts/forward-paper/qualification.json"
        target_stat = path.lstat()
        with patch(
            "tw_stock_tool.artifacts.workspace._is_reparse_point",
            side_effect=lambda result: result == target_stat,
        ):
            inspection = self._inspect()
        self.assertIs(inspection.health, ForwardPaperPackageHealth.INVALID)
        self.assertEqual(inspection.findings[0].code, Code.WORKSPACE_RUN_INVALID)

    def test_unsafe_workspace_scan_exception_is_not_bypassed(self):
        with patch(
            "tw_stock_tool.artifacts.catalog._is_reparse_point",
            return_value=True,
        ):
            with self.assertRaises(WorkspaceCatalogError):
                self._inspect()


if __name__ == "__main__":
    unittest.main()

