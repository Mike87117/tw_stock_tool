"""Read-only offline inspection of one E1 forward-paper Workspace package.

This proves canonical internal package and reviewed trust-chain consistency, not
cryptographic authenticity against an actor who can coherently rewrite the
entire unsigned package and its anchors.
"""

from __future__ import annotations

from collections.abc import Callable
import hashlib
from pathlib import Path
import stat
from typing import Any

from tw_stock_tool.application.forward_eligibility_evidence import (
    build_forward_eligibility_evidence,
)
from tw_stock_tool.application.universe_qualification import (
    export_universe_oos_evidence_json,
    load_universe_oos_evidence_json,
)
from tw_stock_tool.artifacts import (
    RunHealth,
    Workspace,
    lookup_workspace_run,
    resolve_artifact_path,
    scan_workspace,
)
from tw_stock_tool.forward_paper.decision_serialization import (
    export_forward_decision_ledger_json,
    load_forward_decision_ledger_json,
)
from tw_stock_tool.forward_paper.eligibility_serialization import (
    export_forward_eligibility_evidence_json,
    load_forward_eligibility_evidence_json,
)
from tw_stock_tool.forward_paper.execution_serialization import (
    export_forward_execution_evidence_json,
    load_forward_execution_evidence_json,
)
from tw_stock_tool.forward_paper.inspection import (
    FINDING_CODE_ORDER,
    ForwardPaperPackageFinding,
    ForwardPaperPackageFindingCode as Code,
    ForwardPaperPackageHealth,
    ForwardPaperPackageInspection,
    ForwardPaperPackageSummary,
)
from tw_stock_tool.forward_paper.metrics_serialization import (
    export_forward_metrics_evidence_json,
    load_forward_metrics_evidence_json,
)
from tw_stock_tool.forward_paper.portfolio_trace_serialization import (
    export_forward_portfolio_trace_json,
    load_forward_portfolio_trace_json,
)
from tw_stock_tool.forward_paper.publication import (
    PUBLICATION_ARTIFACT_TYPE,
    PUBLICATION_INDEX_PATH,
    ForwardPaperPublicationIndex,
    export_forward_paper_publication_index_json,
    load_forward_paper_publication_index_json,
)
from tw_stock_tool.forward_paper.serialization import (
    export_forward_paper_activation_json,
    load_forward_paper_activation_json,
)
from tw_stock_tool.paper_trading.portfolio_serialization import (
    export_simulated_portfolio_trading_result_json,
    load_simulated_portfolio_trading_result_json,
)
from tw_stock_tool.recommendation.artifacts import (
    export_recommendation_artifact_json,
    load_recommendation_artifact_json,
)
from tw_stock_tool.recommendation.strategy_bound import (
    StrategyBoundRecommendationEvidence,
)
from tw_stock_tool.research_run.models import ArtifactReference, RunManifest


_WORKFLOW = "forward-paper-gate"
_INDEX_REFERENCE = ArtifactReference(
    PUBLICATION_ARTIFACT_TYPE,
    PUBLICATION_INDEX_PATH,
    "application/json",
    "1.0",
)
_ROLE_BOUNDARIES: dict[str, tuple[Callable[[str], Any], Callable[[Any], str]]] = {
    "qualification": (load_universe_oos_evidence_json, export_universe_oos_evidence_json),
    "activation": (load_forward_paper_activation_json, export_forward_paper_activation_json),
    "decision_ledger": (load_forward_decision_ledger_json, export_forward_decision_ledger_json),
    "portfolio_result": (
        load_simulated_portfolio_trading_result_json,
        export_simulated_portfolio_trading_result_json,
    ),
    "execution_evidence": (
        load_forward_execution_evidence_json,
        export_forward_execution_evidence_json,
    ),
    "portfolio_trace": (
        load_forward_portfolio_trace_json,
        export_forward_portfolio_trace_json,
    ),
    "metrics_evidence": (
        load_forward_metrics_evidence_json,
        export_forward_metrics_evidence_json,
    ),
    "eligibility_evidence": (
        load_forward_eligibility_evidence_json,
        export_forward_eligibility_evidence_json,
    ),
}


def _finding(
    code: Code,
    message: str,
    *,
    path: str | None = None,
    role: str | None = None,
) -> ForwardPaperPackageFinding:
    return ForwardPaperPackageFinding(code, path, role, message)


def _ordered_findings(
    findings: list[ForwardPaperPackageFinding],
) -> tuple[ForwardPaperPackageFinding, ...]:
    unique = {
        (item.code, item.path, item.role, item.message): item
        for item in findings
    }
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (
                FINDING_CODE_ORDER.index(item.code),
                item.path or "",
                item.role or "",
                item.message,
            ),
        )
    )


def _inspection(
    entry: Any,
    findings: list[ForwardPaperPackageFinding],
    *,
    index: ForwardPaperPublicationIndex | None = None,
    summary: ForwardPaperPackageSummary | None = None,
) -> ForwardPaperPackageInspection:
    manifest = entry.manifest
    if type(manifest) is not RunManifest or type(entry.run_id) is not str:
        raise ValueError("located Workspace entry lacks a strict manifest identity")
    ordered = _ordered_findings(findings)
    return ForwardPaperPackageInspection(
        health=(
            ForwardPaperPackageHealth.INVALID
            if ordered
            else ForwardPaperPackageHealth.VALID
        ),
        run_id=entry.run_id,
        run_directory=entry.run_directory,
        manifest=manifest,
        publication_index=index,
        findings=ordered,
        summary=summary,
    )


def _manifest_findings(manifest: RunManifest) -> list[ForwardPaperPackageFinding]:
    mismatches: list[str] = []
    if manifest.schema_version != "1.0":
        mismatches.append("schema_version")
    if manifest.status != "success":
        mismatches.append("status")
    if manifest.config.workflow != _WORKFLOW:
        mismatches.append("workflow")
    if manifest.data_sources:
        mismatches.append("data_sources")
    if manifest.config.workflow_options:
        mismatches.append("workflow_options")
    if manifest.errors:
        mismatches.append("errors")
    if manifest.limitations:
        mismatches.append("limitations")
    return [
        _finding(
            Code.MANIFEST_CONTRACT_MISMATCH,
            f"Run Manifest fields do not match E1: {', '.join(mismatches)}",
        )
    ] if mismatches else []


def _load_index(
    run_directory: Path,
) -> tuple[ForwardPaperPublicationIndex | None, ForwardPaperPackageFinding | None]:
    try:
        path = resolve_artifact_path(run_directory, PUBLICATION_INDEX_PATH)
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        index = load_forward_paper_publication_index_json(text)
        canonical = export_forward_paper_publication_index_json(index).encode("utf-8")
    except (OSError, UnicodeError, TypeError, ValueError) as exc:
        return None, _finding(
            Code.PUBLICATION_INDEX_INVALID,
            f"Publication Index cannot be strictly loaded: {exc}",
            path=PUBLICATION_INDEX_PATH,
            role="publication_index",
        )
    if raw != canonical:
        return None, _finding(
            Code.PUBLICATION_INDEX_INVALID,
            "Publication Index bytes are not canonical",
            path=PUBLICATION_INDEX_PATH,
            role="publication_index",
        )
    return index, None


def _expected_references(index: ForwardPaperPublicationIndex) -> tuple[ArtifactReference, ...]:
    fixed = tuple(
        ArtifactReference(
            anchor.artifact_type,
            anchor.path,
            anchor.media_type,
            anchor.schema_version,
        )
        for anchor in index.artifact_anchors
    )
    recommendations = tuple(
        ArtifactReference(
            "recommendation_evidence",
            anchor.path,
            "application/json",
            "1.1",
        )
        for anchor in index.recommendation_anchors
    )
    return fixed[:3] + recommendations + fixed[3:] + (_INDEX_REFERENCE,)


def _load_verified(
    run_directory: Path,
    *,
    path: str,
    role: str,
    expected_sha256: str,
    loader: Callable[[str], Any],
    exporter: Callable[[Any], str],
) -> tuple[Any | None, ForwardPaperPackageFinding | None]:
    try:
        resolved = resolve_artifact_path(run_directory, path)
        result = resolved.lstat()
        if not stat.S_ISREG(result.st_mode):
            raise OSError("artifact path is not a regular file")
        raw = resolved.read_bytes()
        text = raw.decode("utf-8")
        artifact = loader(text)
        canonical = exporter(artifact).encode("utf-8")
    except (OSError, UnicodeError, TypeError, ValueError) as exc:
        return None, _finding(
            Code.ARTIFACT_READ_FAILURE,
            f"Artifact cannot be strictly read: {exc}",
            path=path,
            role=role,
        )
    if raw != canonical:
        return None, _finding(
            Code.ARTIFACT_NONCANONICAL,
            "Artifact bytes differ from canonical export",
            path=path,
            role=role,
        )
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != expected_sha256:
        return None, _finding(
            Code.ARTIFACT_SHA256_MISMATCH,
            "Artifact SHA-256 does not match the Publication Index",
            path=path,
            role=role,
        )
    return artifact, None


def _identity_findings(
    index: ForwardPaperPublicationIndex,
    loaded: dict[str, Any],
) -> list[ForwardPaperPackageFinding]:
    qualification = loaded["qualification"]
    activation = loaded["activation"]
    ledger = loaded["decision_ledger"]
    execution = loaded["execution_evidence"]
    metrics = loaded["metrics_evidence"]
    eligibility = loaded["eligibility_evidence"]
    expected = {
        "activation_id": activation.activation_id,
        "qualification_evaluation_id": qualification.evaluation_id,
        "ledger_id": ledger.ledger_id,
        "execution_evidence_id": execution.evidence_id,
        "metrics_id": metrics.metrics_id,
        "eligibility_id": eligibility.eligibility_id,
        "strategy_id": activation.strategy_id,
        "policy_id": eligibility.policy_id,
        "policy_version": eligibility.policy_version,
        "eligibility_state": eligibility.state,
    }
    mismatches = [
        name for name, value in expected.items()
        if getattr(index, name) != value
    ]
    if index.created_at < eligibility.created_at:
        mismatches.append("created_at")
    return [
        _finding(
            Code.INDEX_IDENTITY_MISMATCH,
            f"Publication Index identities do not match trusted artifacts: {', '.join(mismatches)}",
            path=PUBLICATION_INDEX_PATH,
            role="publication_index",
        )
    ] if mismatches else []


def _recommendation_findings(
    index: ForwardPaperPublicationIndex,
    ledger: Any,
    recommendations: tuple[Any, ...],
) -> list[ForwardPaperPackageFinding]:
    ledger_ids = tuple(item.recommendation_id for item in ledger.decisions)
    anchor_ids = tuple(item.recommendation_id for item in index.recommendation_anchors)
    problems: list[str] = []
    if anchor_ids != ledger_ids:
        problems.append("anchor IDs/order differ from the decision ledger")
    for anchor, recommendation in zip(index.recommendation_anchors, recommendations):
        if (
            type(recommendation) is not StrategyBoundRecommendationEvidence
            or recommendation.schema_version != "1.1"
            or recommendation.recommendation_id != anchor.recommendation_id
        ):
            problems.append(f"invalid schema-1.1 recommendation {anchor.recommendation_id}")
    return [
        _finding(
            Code.RECOMMENDATION_CONTRACT_MISMATCH,
            "; ".join(problems),
            role="recommendation",
        )
    ] if problems else []


def _config_findings(
    manifest: RunManifest,
    qualification: Any,
    activation: Any,
) -> list[ForwardPaperPackageFinding]:
    config = manifest.config
    trusted = qualification.resolved_configuration
    mismatches: list[str] = []
    expected = {
        "workflow": _WORKFLOW,
        "universe": "qualified-universe",
        "canonical_symbols": activation.qualified_symbols,
        "period": trusted.period,
        "interval": trusted.interval,
        "auto_adjust": trusted.auto_adjust,
        "force_refresh": False,
        "strategy": trusted.strategy,
        "backtest": None,
        "parameter_sweep": None,
        "walk_forward": None,
        "ml": None,
    }
    mismatches.extend(
        name for name, value in expected.items()
        if getattr(config, name) != value
    )
    if config.workflow_options:
        mismatches.append("workflow_options")
    if manifest.data_sources:
        mismatches.append("data_sources")
    if (
        manifest.success_count != 1
        or manifest.failure_count != 0
        or manifest.partial_count != 0
    ):
        mismatches.append("result_counts")
    return [
        _finding(
            Code.MANIFEST_CONTRACT_MISMATCH,
            f"Run Manifest config does not match trusted artifacts: {', '.join(mismatches)}",
        )
    ] if mismatches else []


def _summary(
    index: ForwardPaperPublicationIndex,
    loaded: dict[str, Any],
    recommendations: tuple[Any, ...],
) -> ForwardPaperPackageSummary:
    activation = loaded["activation"]
    ledger = loaded["decision_ledger"]
    trace = loaded["portfolio_trace"]
    metrics = loaded["metrics_evidence"]
    eligibility = loaded["eligibility_evidence"]
    return ForwardPaperPackageSummary(
        publication_id=index.publication_id,
        activation_id=activation.activation_id,
        qualification_evaluation_id=activation.qualification_evaluation_id,
        strategy_id=activation.strategy_id,
        policy_id=eligibility.policy_id,
        policy_version=eligibility.policy_version,
        eligibility_state=eligibility.state,
        eligibility_finding_codes=tuple(item.code for item in eligibility.findings),
        qualification_cutoff=activation.qualification_cutoff,
        qualified_symbols=activation.qualified_symbols,
        decision_count=len(ledger.decisions),
        recommendation_count=len(recommendations),
        portfolio_observation_count=len(trace.observations),
        filled_count=metrics.execution_health.filled_count,
        skipped_invalid_open_count=metrics.execution_health.skipped_invalid_open_count,
        failed_portfolio_validation_count=(
            metrics.execution_health.failed_portfolio_validation_count
        ),
        applied_total_cost=metrics.applied_costs.applied_total_cost,
        total_return_pct=metrics.portfolio_metrics.total_return_pct,
        max_drawdown_pct=metrics.portfolio_metrics.max_drawdown_pct,
    )


def _inspect_forward_paper_workspace_package_sources(
    workspace_root: str | Path,
    run_id: str,
) -> tuple[
    ForwardPaperPackageInspection,
    dict[str, Any] | None,
    tuple[Any, ...],
]:
    """Inspect once and retain sources only when the complete chain is valid."""
    workspace = Workspace.open_existing(workspace_root)
    catalog = scan_workspace(workspace)
    entry = lookup_workspace_run(catalog, run_id)
    if entry.health is not RunHealth.VALID:
        return _inspection(
            entry,
            [_finding(
                Code.WORKSPACE_RUN_INVALID,
                "Workspace catalog did not classify the run as VALID",
            )],
        ), None, ()

    manifest = entry.manifest
    assert manifest is not None
    findings = _manifest_findings(manifest)
    index_references = tuple(
        item for item in manifest.artifacts
        if item.path == PUBLICATION_INDEX_PATH
    )
    if index_references != (_INDEX_REFERENCE,):
        findings.append(_finding(
            Code.ARTIFACT_REFERENCE_MISMATCH,
            "Run Manifest must contain exactly one canonical Publication Index reference",
            path=PUBLICATION_INDEX_PATH,
            role="publication_index",
        ))
    if findings:
        return _inspection(entry, findings), None, ()

    index, index_finding = _load_index(entry.run_directory)
    if index_finding is not None:
        return _inspection(entry, [index_finding]), None, ()
    assert index is not None

    if manifest.artifacts != _expected_references(index):
        return _inspection(
            entry,
            [_finding(
                Code.ARTIFACT_REFERENCE_MISMATCH,
                "Run Manifest artifact references do not match the frozen package tuple",
            )],
            index=index,
        ), None, ()

    loaded: dict[str, Any] = {}
    findings = []
    for anchor in index.artifact_anchors:
        loader, exporter = _ROLE_BOUNDARIES[anchor.role]
        artifact, finding = _load_verified(
            entry.run_directory,
            path=anchor.path,
            role=anchor.role,
            expected_sha256=anchor.sha256,
            loader=loader,
            exporter=exporter,
        )
        if finding is not None:
            findings.append(finding)
        else:
            loaded[anchor.role] = artifact

    recommendations: list[Any] = []
    for anchor in index.recommendation_anchors:
        artifact, finding = _load_verified(
            entry.run_directory,
            path=anchor.path,
            role="recommendation",
            expected_sha256=anchor.recommendation_sha256,
            loader=load_recommendation_artifact_json,
            exporter=export_recommendation_artifact_json,
        )
        if finding is not None:
            findings.append(finding)
        else:
            recommendations.append(artifact)
    if findings:
        return _inspection(entry, findings, index=index), None, ()

    recommendation_tuple = tuple(recommendations)
    findings.extend(
        _recommendation_findings(
            index,
            loaded["decision_ledger"],
            recommendation_tuple,
        )
    )
    findings.extend(_identity_findings(index, loaded))
    if findings:
        return _inspection(entry, findings, index=index), None, ()

    recommendation_mapping = {
        item.recommendation_id: item for item in recommendation_tuple
    }
    eligibility = loaded["eligibility_evidence"]
    try:
        rebuilt = build_forward_eligibility_evidence(
            loaded["activation"],
            loaded["qualification"],
            loaded["decision_ledger"],
            recommendation_mapping,
            loaded["portfolio_result"],
            loaded["execution_evidence"],
            loaded["portfolio_trace"],
            loaded["metrics_evidence"],
            expected_portfolio_trace_sha256=index.portfolio_trace_sha256,
            policy_id=eligibility.policy_id,
            policy_version=eligibility.policy_version,
            eligibility_id=eligibility.eligibility_id,
            created_at=eligibility.created_at,
        )
        exact = (
            export_forward_eligibility_evidence_json(rebuilt)
            == export_forward_eligibility_evidence_json(eligibility)
        )
    except (TypeError, ValueError) as exc:
        exact = False
        detail = str(exc)
    else:
        detail = "rebuilt D3 differs from the published D3"
    if not exact:
        return _inspection(
            entry,
            [_finding(
                Code.TRUST_CHAIN_INVALID,
                f"Complete reviewed trust-chain rebuild failed: {detail}",
            )],
            index=index,
        ), None, ()

    findings = _config_findings(
        manifest,
        loaded["qualification"],
        loaded["activation"],
    )
    if findings:
        return _inspection(entry, findings, index=index), None, ()
    return _inspection(
        entry,
        [],
        index=index,
        summary=_summary(index, loaded, recommendation_tuple),
    ), loaded, recommendation_tuple


def inspect_forward_paper_workspace_package(
    workspace_root: str | Path,
    run_id: str,
) -> ForwardPaperPackageInspection:
    """Inspect one package without allocating, writing, replaying, or fetching."""
    inspection, _, _ = _inspect_forward_paper_workspace_package_sources(
        workspace_root,
        run_id,
    )
    return inspection


__all__ = ["inspect_forward_paper_workspace_package"]

