"""Publish one fully validated forward-paper trust package into a Workspace."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

from tw_stock_tool.application.forward_eligibility_evidence import (
    ForwardEligibilityEvidenceError,
    build_forward_eligibility_evidence,
)
from tw_stock_tool.application.universe_qualification import (
    UniverseOOSArtifact,
    export_universe_oos_evidence_json,
    load_universe_oos_evidence_json,
)
from tw_stock_tool.application.workspace_execution import WorkspaceRunLifecycle
from tw_stock_tool.application.workspace_run import _tool_version
from tw_stock_tool.artifacts import RunDirectory, write_managed_text
from tw_stock_tool.forward_paper.decision_models import ForwardDecisionLedger
from tw_stock_tool.forward_paper.decision_serialization import (
    export_forward_decision_ledger_json,
    load_forward_decision_ledger_json,
)
from tw_stock_tool.forward_paper.eligibility_models import ForwardEligibilityEvidence
from tw_stock_tool.forward_paper.eligibility_serialization import (
    export_forward_eligibility_evidence_json,
    load_forward_eligibility_evidence_json,
)
from tw_stock_tool.forward_paper.execution_models import ForwardExecutionEvidence
from tw_stock_tool.forward_paper.execution_serialization import (
    export_forward_execution_evidence_json,
    load_forward_execution_evidence_json,
)
from tw_stock_tool.forward_paper.metrics_models import ForwardMetricsEvidence
from tw_stock_tool.forward_paper.metrics_serialization import (
    export_forward_metrics_evidence_json,
    load_forward_metrics_evidence_json,
)
from tw_stock_tool.forward_paper.models import ForwardPaperActivation
from tw_stock_tool.forward_paper.portfolio_trace_models import ForwardPortfolioTrace
from tw_stock_tool.forward_paper.portfolio_trace_serialization import (
    export_forward_portfolio_trace_json,
    load_forward_portfolio_trace_json,
)
from tw_stock_tool.forward_paper.publication import (
    PUBLICATION_ARTIFACT_SPECS,
    PUBLICATION_ARTIFACT_TYPE,
    PUBLICATION_INDEX_PATH,
    PUBLICATION_SCHEMA_VERSION,
    RECOMMENDATION_DIRECTORY,
    ForwardPaperPublicationIndex,
    ForwardPublishedArtifactAnchor,
    ForwardRecommendationAnchor,
    export_forward_paper_publication_index_json,
    load_forward_paper_publication_index_json,
)
from tw_stock_tool.forward_paper.serialization import (
    export_forward_paper_activation_json,
    load_forward_paper_activation_json,
)
from tw_stock_tool.paper_trading.portfolio_results import SimulatedPortfolioTradingResult
from tw_stock_tool.paper_trading.portfolio_serialization import (
    export_simulated_portfolio_trading_result_json,
    load_simulated_portfolio_trading_result_json,
)
from tw_stock_tool.recommendation.artifacts import (
    export_recommendation_artifact_json,
    load_recommendation_artifact_json,
)
from tw_stock_tool.research_run.models import (
    RUN_MANIFEST_SCHEMA_VERSION,

    RunConfig,
    RunManifest,
)


WORKFLOW = "forward-paper-gate"


class ForwardPaperPublicationApplicationError(ValueError):
    """Raised before publication when the supplied package is not fully trusted."""


@dataclass(frozen=True, slots=True)
class ForwardPaperWorkspacePublicationResult:
    run_id: str
    run_directory: RunDirectory
    manifest_path: Path
    manifest: RunManifest
    publication_index: ForwardPaperPublicationIndex


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(
    name: str,
    value: Any,
    exporter: Callable[[Any], str],
    loader: Callable[[str], Any],
) -> str:
    try:
        text = exporter(value)
        loaded = loader(text)
        reexported = exporter(loaded)
    except (TypeError, ValueError) as exc:
        raise ForwardPaperPublicationApplicationError(f"{name} is invalid: {exc}") from exc
    if reexported != text:
        raise ForwardPaperPublicationApplicationError(f"{name} failed canonical round-trip")
    return text


def _artifact_anchor(
    role: str,
    artifact_type: str,
    schema_version: int | str,
    path: str,
    sha256: str,
) -> ForwardPublishedArtifactAnchor:
    return ForwardPublishedArtifactAnchor(
        role=role,
        artifact_type=artifact_type,
        schema_version=schema_version,
        media_type="application/json",
        path=path,
        sha256=sha256,
    )


def _write_verified(
    lifecycle: WorkspaceRunLifecycle,
    path: str,
    text: str,
    exporter: Callable[[Any], str],
    loader: Callable[[str], Any],
) -> Path:
    destination = write_managed_text(lifecycle.run_directory, path, text)
    try:
        readback_bytes = destination.read_bytes()
        readback = readback_bytes.decode("utf-8")
        loaded = loader(readback)
        canonical = exporter(loaded)
    except (OSError, UnicodeError, TypeError, ValueError) as exc:
        raise ForwardPaperPublicationApplicationError(f"read-back failed for {path}: {exc}") from exc
    if readback_bytes != text.encode("utf-8") or canonical != text or _sha(readback) != _sha(text):
        raise ForwardPaperPublicationApplicationError(f"read-back did not preserve canonical bytes for {path}")
    return destination


def publish_forward_paper_workspace_package(
    workspace_root: str | Path,
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
    ledger: ForwardDecisionLedger,
    recommendation_evidence_by_id: Mapping[str, Any],
    portfolio_result: SimulatedPortfolioTradingResult,
    execution_evidence: ForwardExecutionEvidence,
    portfolio_trace: ForwardPortfolioTrace,
    metrics_evidence: ForwardMetricsEvidence,
    eligibility_evidence: ForwardEligibilityEvidence,
    *,
    expected_portfolio_trace_sha256: str,
    publication_id: str,
    created_at: str,
) -> ForwardPaperWorkspacePublicationResult:
    """Validate the complete chain, then publish its canonical bytes and manifest."""
    if type(eligibility_evidence) is not ForwardEligibilityEvidence:
        raise ForwardPaperPublicationApplicationError(
            "eligibility_evidence must be an exact ForwardEligibilityEvidence"
        )
    try:
        rebuilt_eligibility = build_forward_eligibility_evidence(
            activation,
            qualification_artifact,
            ledger,
            recommendation_evidence_by_id,
            portfolio_result,
            execution_evidence,
            portfolio_trace,
            metrics_evidence,
            expected_portfolio_trace_sha256=expected_portfolio_trace_sha256,
            policy_id=eligibility_evidence.policy_id,
            policy_version=eligibility_evidence.policy_version,
            eligibility_id=eligibility_evidence.eligibility_id,
            created_at=eligibility_evidence.created_at,
        )
    except (ForwardEligibilityEvidenceError, TypeError, ValueError) as exc:
        raise ForwardPaperPublicationApplicationError(f"trust-chain validation failed: {exc}") from exc
    supplied_eligibility_text = _canonical(
        "eligibility evidence",
        eligibility_evidence,
        export_forward_eligibility_evidence_json,
        load_forward_eligibility_evidence_json,
    )
    if export_forward_eligibility_evidence_json(rebuilt_eligibility) != supplied_eligibility_text:
        raise ForwardPaperPublicationApplicationError(
            "eligibility evidence does not exactly match its trusted rebuild"
        )

    fixed_inputs = (
        ("qualification", qualification_artifact, export_universe_oos_evidence_json, load_universe_oos_evidence_json),
        ("activation", activation, export_forward_paper_activation_json, load_forward_paper_activation_json),
        ("decision ledger", ledger, export_forward_decision_ledger_json, load_forward_decision_ledger_json),
        ("portfolio result", portfolio_result, export_simulated_portfolio_trading_result_json, load_simulated_portfolio_trading_result_json),
        ("execution evidence", execution_evidence, export_forward_execution_evidence_json, load_forward_execution_evidence_json),
        ("portfolio trace", portfolio_trace, export_forward_portfolio_trace_json, load_forward_portfolio_trace_json),
        ("metrics evidence", metrics_evidence, export_forward_metrics_evidence_json, load_forward_metrics_evidence_json),
    )
    fixed_texts = tuple(
        _canonical(name, value, exporter, loader)
        for name, value, exporter, loader in fixed_inputs
    ) + (supplied_eligibility_text,)
    fixed_hashes = tuple(_sha(text) for text in fixed_texts)
    if fixed_hashes[5] != expected_portfolio_trace_sha256:
        raise ForwardPaperPublicationApplicationError(
            "portfolio trace canonical SHA-256 does not match the supplied external anchor"
        )

    recommendation_ids = tuple(decision.recommendation_id for decision in ledger.decisions)
    if set(recommendation_evidence_by_id) != set(recommendation_ids) or len(recommendation_evidence_by_id) != len(recommendation_ids):
        raise ForwardPaperPublicationApplicationError(
            "recommendation mapping must exactly match the decision ledger"
        )
    recommendation_texts: list[str] = []
    recommendation_anchors: list[ForwardRecommendationAnchor] = []
    for recommendation_id in recommendation_ids:
        evidence = recommendation_evidence_by_id[recommendation_id]
        text = _canonical(
            f"recommendation {recommendation_id}",
            evidence,
            export_recommendation_artifact_json,
            load_recommendation_artifact_json,
        )
        if getattr(evidence, "schema_version", None) != "1.1" or getattr(evidence, "recommendation_id", None) != recommendation_id:
            raise ForwardPaperPublicationApplicationError(
                "every ledger recommendation must be its original schema-1.1 artifact"
            )
        path = f"{RECOMMENDATION_DIRECTORY}/{recommendation_id}.json"
        recommendation_texts.append(text)
        recommendation_anchors.append(ForwardRecommendationAnchor(recommendation_id, _sha(text), path))

    hash_names = (
        "qualification_sha256", "activation_sha256", "ledger_sha256",
        "portfolio_result_sha256", "execution_evidence_sha256",
        "portfolio_trace_sha256", "metrics_sha256",
        "eligibility_sha256",
    )
    hashes = dict(zip(hash_names, fixed_hashes, strict=True))
    artifact_anchors = tuple(
        _artifact_anchor(role, artifact_type, schema, path, fixed_hashes[index])
        for index, (role, artifact_type, schema, path) in enumerate(PUBLICATION_ARTIFACT_SPECS)
    )
    try:
        index = ForwardPaperPublicationIndex(
            schema_version=PUBLICATION_SCHEMA_VERSION,
            artifact_type=PUBLICATION_ARTIFACT_TYPE,
            publication_id=publication_id,
            created_at=created_at,
            activation_id=activation.activation_id,
            qualification_evaluation_id=qualification_artifact.evaluation_id,
            ledger_id=ledger.ledger_id,
            execution_evidence_id=execution_evidence.evidence_id,
            metrics_id=metrics_evidence.metrics_id,
            eligibility_id=eligibility_evidence.eligibility_id,
            strategy_id=activation.strategy_id,
            policy_id=eligibility_evidence.policy_id,
            policy_version=eligibility_evidence.policy_version,
            eligibility_state=eligibility_evidence.state,
            recommendation_anchors=tuple(recommendation_anchors),
            artifact_anchors=artifact_anchors,
            **hashes,
        )
        index_text = _canonical(
            "publication index",
            index,
            export_forward_paper_publication_index_json,
            load_forward_paper_publication_index_json,
        )
        if index.created_at < eligibility_evidence.created_at:
            raise ForwardPaperPublicationApplicationError(
                "publication created_at must not predate eligibility evidence"
            )
    except (TypeError, ValueError) as exc:
        raise ForwardPaperPublicationApplicationError(f"publication index is invalid: {exc}") from exc

    lifecycle = WorkspaceRunLifecycle.begin(workspace_root, WORKFLOW)
    paths = tuple(spec[3] for spec in PUBLICATION_ARTIFACT_SPECS)
    written: list[tuple[Path, str, str | int]] = []

    def publish(path: str, text: str, exporter: Callable[[Any], str], loader: Callable[[str], Any], artifact_type: str, schema: str | int) -> None:
        destination = _write_verified(lifecycle, path, text, exporter, loader)
        written.append((destination, artifact_type, schema))

    publish(paths[0], fixed_texts[0], export_universe_oos_evidence_json, load_universe_oos_evidence_json, PUBLICATION_ARTIFACT_SPECS[0][1], "1.0")
    publish(paths[1], fixed_texts[1], export_forward_paper_activation_json, load_forward_paper_activation_json, PUBLICATION_ARTIFACT_SPECS[1][1], "1.0")
    publish(paths[2], fixed_texts[2], export_forward_decision_ledger_json, load_forward_decision_ledger_json, PUBLICATION_ARTIFACT_SPECS[2][1], "1.0")
    for anchor, text in zip(recommendation_anchors, recommendation_texts, strict=True):
        publish(anchor.path, text, export_recommendation_artifact_json, load_recommendation_artifact_json, "recommendation_evidence", "1.1")
    remaining = (
        (3, export_simulated_portfolio_trading_result_json, load_simulated_portfolio_trading_result_json, 1),
        (4, export_forward_execution_evidence_json, load_forward_execution_evidence_json, "1.0"),
        (5, export_forward_portfolio_trace_json, load_forward_portfolio_trace_json, "1.0"),
        (6, export_forward_metrics_evidence_json, load_forward_metrics_evidence_json, "1.0"),
        (7, export_forward_eligibility_evidence_json, load_forward_eligibility_evidence_json, "1.0"),
    )
    for index_number, exporter, loader, schema in remaining:
        publish(paths[index_number], fixed_texts[index_number], exporter, loader, PUBLICATION_ARTIFACT_SPECS[index_number][1], schema)
    publish(PUBLICATION_INDEX_PATH, index_text, export_forward_paper_publication_index_json, load_forward_paper_publication_index_json, PUBLICATION_ARTIFACT_TYPE, "1.0")

    configuration = qualification_artifact.resolved_configuration
    config = RunConfig(
        workflow=WORKFLOW,
        universe="qualified-universe",
        canonical_symbols=activation.qualified_symbols,
        period=configuration.period,
        interval=configuration.interval,
        auto_adjust=configuration.auto_adjust,
        force_refresh=False,
        strategy=configuration.strategy,
        backtest=None,
        parameter_sweep=None,
        walk_forward=None,
        ml=None,
        workflow_options={},
    )
    references = tuple(
        lifecycle.artifact_reference(path, artifact_type, "application/json", schema)
        for path, artifact_type, schema in written
    )
    manifest = RunManifest(
        schema_version=RUN_MANIFEST_SCHEMA_VERSION,
        run_id=lifecycle.run_id,
        created_at=lifecycle.created_at,
        tool_version=_tool_version(),
        status="success",
        config=config,
        data_sources=(),
        success_count=1,
        failure_count=0,
        partial_count=0,
        artifacts=references,
        errors=(),
        limitations=(),
    )
    published_manifest = lifecycle.publish(manifest)
    return ForwardPaperWorkspacePublicationResult(
        run_id=lifecycle.run_id,
        run_directory=lifecycle.run_directory,
        manifest_path=lifecycle.manifest_path,
        manifest=published_manifest,
        publication_index=index,
    )


__all__ = [
    "ForwardPaperPublicationApplicationError",
    "ForwardPaperWorkspacePublicationResult",
    "publish_forward_paper_workspace_package",
]

