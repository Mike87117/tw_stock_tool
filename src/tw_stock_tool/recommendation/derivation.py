"""Pure deterministic recommendation action derivation."""

from __future__ import annotations

from tw_stock_tool.qualification import StrategyQualificationResult
from tw_stock_tool.recommendation.models import (
    RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE,
    RECOMMENDATION_EVIDENCE_SCHEMA_VERSION,
    CurrentSignalSnapshot,
    RecommendationAction,
    RecommendationEvidence,
    RecommendationModelError,
)


def derive_recommendation_action(
    qualification: StrategyQualificationResult,
    signal_snapshot: CurrentSignalSnapshot,
) -> RecommendationAction:
    """Map qualification state plus current signal to one canonical action."""
    if not isinstance(qualification, StrategyQualificationResult):
        raise RecommendationModelError(
            "qualification must be a StrategyQualificationResult"
        )
    if not isinstance(signal_snapshot, CurrentSignalSnapshot):
        raise RecommendationModelError(
            "signal_snapshot must be a CurrentSignalSnapshot"
        )

    promotion = qualification.decision.state
    signal = signal_snapshot.signal
    if promotion == "REJECTED":
        return "NO_TRADE"
    if promotion == "RESEARCH_CANDIDATE":
        return "WATCH" if signal in ("BUY", "WATCH") else "NO_TRADE"
    if promotion == "PAPER_READY":
        return {
            "BUY": "ENTER",
            "WATCH": "WATCH",
            "HOLD": "HOLD",
            "SELL": "EXIT",
        }[signal]
    raise RecommendationModelError(
        f"unsupported qualification promotion state: {promotion!r}"
    )


def build_recommendation_evidence(
    *,
    recommendation_id: str,
    generated_at: str,
    qualification: StrategyQualificationResult,
    signal_snapshot: CurrentSignalSnapshot,
) -> RecommendationEvidence:
    """Build one canonical RecommendationEvidence from supplied research evidence."""
    if not isinstance(qualification, StrategyQualificationResult):
        raise RecommendationModelError(
            "qualification must be a StrategyQualificationResult"
        )
    return RecommendationEvidence(
        schema_version=RECOMMENDATION_EVIDENCE_SCHEMA_VERSION,
        artifact_type=RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE,
        recommendation_id=recommendation_id,
        generated_at=generated_at,
        source_qualification_evaluation_id=qualification.request.evaluation_id,
        promotion_state=qualification.decision.state,
        strategy_id=qualification.request.strategy.strategy_id,
        strategy_parameters=qualification.request.strategy.parameters,
        qualification_finding_codes=qualification.decision.reason_codes,
        signal_snapshot=signal_snapshot,
        action=derive_recommendation_action(qualification, signal_snapshot),
        qualification=qualification,
    )


__all__ = [
    "build_recommendation_evidence",
    "derive_recommendation_action",
]
