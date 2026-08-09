"""Pure construction of trusted forward eligibility evidence."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
from typing import Any

from tw_stock_tool.application.forward_metrics_evidence import (
    ForwardMetricsEvidenceError,
    build_forward_metrics_evidence,
)
from tw_stock_tool.application.universe_qualification import UniverseOOSArtifact
from tw_stock_tool.forward_paper.decision_models import ForwardDecisionLedger
from tw_stock_tool.forward_paper.eligibility_models import (
    ForwardEligibilityEvidence,
    ForwardEligibilityModelError,
)
from tw_stock_tool.forward_paper.eligibility_policies import (
    ForwardEligibilityPolicyError,
    evaluate_forward_eligibility,
    resolve_forward_eligibility_policy,
)
from tw_stock_tool.forward_paper.execution_models import ForwardExecutionEvidence
from tw_stock_tool.forward_paper.metrics_models import ForwardMetricsEvidence
from tw_stock_tool.forward_paper.metrics_serialization import (
    ForwardMetricsEvidenceSerializationError,
    export_forward_metrics_evidence_json,
)
from tw_stock_tool.forward_paper.models import ForwardPaperActivation
from tw_stock_tool.forward_paper.portfolio_trace_models import ForwardPortfolioTrace
from tw_stock_tool.paper_trading.portfolio_results import (
    SimulatedPortfolioTradingResult,
)


class ForwardEligibilityEvidenceError(ValueError):
    """Raised when trusted inputs cannot produce eligibility evidence."""


def _trusted_metrics_evidence(
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
    ledger: ForwardDecisionLedger,
    recommendation_evidence_by_id: Mapping[str, Any],
    portfolio_result: SimulatedPortfolioTradingResult,
    execution_evidence: ForwardExecutionEvidence,
    portfolio_trace: ForwardPortfolioTrace,
    metrics_evidence: ForwardMetricsEvidence,
    *,
    expected_portfolio_trace_sha256: str,
) -> tuple[ForwardMetricsEvidence, str]:
    if type(metrics_evidence) is not ForwardMetricsEvidence:
        raise ForwardEligibilityEvidenceError(
            "metrics_evidence must be an exact ForwardMetricsEvidence"
        )
    try:
        rebuilt = build_forward_metrics_evidence(
            activation,
            qualification_artifact,
            ledger,
            recommendation_evidence_by_id,
            portfolio_result,
            execution_evidence,
            portfolio_trace,
            expected_portfolio_trace_sha256=expected_portfolio_trace_sha256,
            metrics_id=metrics_evidence.metrics_id,
            created_at=metrics_evidence.created_at,
        )
        supplied_json = export_forward_metrics_evidence_json(metrics_evidence)
        rebuilt_json = export_forward_metrics_evidence_json(rebuilt)
    except (
        ForwardMetricsEvidenceError,
        ForwardMetricsEvidenceSerializationError,
        TypeError,
        ValueError,
    ) as exc:
        raise ForwardEligibilityEvidenceError(
            f"metrics evidence validation failed: {exc}"
        ) from exc
    if supplied_json != rebuilt_json:
        raise ForwardEligibilityEvidenceError(
            "metrics evidence does not exactly match its trusted rebuild"
        )
    return rebuilt, hashlib.sha256(rebuilt_json.encode("utf-8")).hexdigest()


def build_forward_eligibility_evidence(
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
    ledger: ForwardDecisionLedger,
    recommendation_evidence_by_id: Mapping[str, Any],
    portfolio_result: SimulatedPortfolioTradingResult,
    execution_evidence: ForwardExecutionEvidence,
    portfolio_trace: ForwardPortfolioTrace,
    metrics_evidence: ForwardMetricsEvidence,
    *,
    expected_portfolio_trace_sha256: str,
    policy_id: str,
    policy_version: str,
    eligibility_id: str,
    created_at: str,
) -> ForwardEligibilityEvidence:
    """Build D3 eligibility only after exact D2 reconstruction."""
    trusted_metrics, metrics_sha256 = _trusted_metrics_evidence(
        activation,
        qualification_artifact,
        ledger,
        recommendation_evidence_by_id,
        portfolio_result,
        execution_evidence,
        portfolio_trace,
        metrics_evidence,
        expected_portfolio_trace_sha256=expected_portfolio_trace_sha256,
    )
    try:
        policy = resolve_forward_eligibility_policy(policy_id, policy_version)
        state, findings = evaluate_forward_eligibility(trusted_metrics, policy)
        evidence = ForwardEligibilityEvidence(
            schema_version="1.0",
            artifact_type="forward_eligibility_evidence",
            eligibility_id=eligibility_id,
            created_at=created_at,
            activation_id=trusted_metrics.activation_id,
            activation_sha256=trusted_metrics.activation_sha256,
            qualification_evaluation_id=(
                trusted_metrics.qualification_evaluation_id
            ),
            qualification_sha256=trusted_metrics.qualification_sha256,
            ledger_id=trusted_metrics.ledger_id,
            ledger_sha256=trusted_metrics.ledger_sha256,
            metrics_id=trusted_metrics.metrics_id,
            metrics_sha256=metrics_sha256,
            strategy_id=trusted_metrics.strategy_id,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            state=state,
            findings=findings,
        )
    except (
        ForwardEligibilityModelError,
        ForwardEligibilityPolicyError,
        TypeError,
        ValueError,
    ) as exc:
        raise ForwardEligibilityEvidenceError(str(exc)) from exc
    if evidence.created_at < trusted_metrics.created_at:
        raise ForwardEligibilityEvidenceError(
            "eligibility created_at must not predate metrics evidence"
        )
    return evidence


__all__ = [
    "ForwardEligibilityEvidenceError",
    "build_forward_eligibility_evidence",
]
