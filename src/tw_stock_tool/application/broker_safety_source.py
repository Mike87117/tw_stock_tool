"""Pure construction of trusted Phase 56.5A1 broker-safety source facts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from tw_stock_tool.application.forward_paper_inspection import (
    _inspect_forward_paper_workspace_package_sources,
)
from tw_stock_tool.artifacts import WorkspaceError
from tw_stock_tool.broker_safety.source_models import (
    HANDOFF_ARTIFACT_TYPE,
    PROGRESSION_ARTIFACT_TYPE,
    SOURCE_SCHEMA_VERSION,
    BrokerSafetySourceHandoff,
    BrokerSafetySourceModelError,
    ForwardEligibilityDecisionAnchor,
    ForwardEligibilityLineageKey,
    ForwardEligibilityProgression,
    _canonical_sha256,
    progression_fingerprint,
)
from tw_stock_tool.forward_paper.decision_models import ForwardDecisionLedger
from tw_stock_tool.forward_paper.decision_serialization import (
    export_forward_decision_ledger_json,
    serialize_forward_decision_ledger,
)
from tw_stock_tool.forward_paper.eligibility_models import ForwardEligibilityState
from tw_stock_tool.forward_paper.inspection import (
    ForwardPaperPackageHealth,
    ForwardPaperPackageInspection,
    ForwardPaperPackageSummary,
)
from tw_stock_tool.forward_paper.publication import (
    ForwardPaperPublicationIndex,
    export_forward_paper_publication_index_json,
)
from tw_stock_tool.recommendation.strategy_bound import (
    StrategyBoundRecommendationEvidence,
    export_strategy_bound_recommendation_evidence_json,
)


class BrokerSafetySourceError(ValueError):
    """Raised when trusted Phase 56.4 facts cannot form an A1 contract."""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _trusted_inspection(
    inspection: ForwardPaperPackageInspection,
) -> tuple[ForwardPaperPublicationIndex, ForwardPaperPackageSummary]:
    if type(inspection) is not ForwardPaperPackageInspection:
        raise BrokerSafetySourceError(
            "inspection must be an exact ForwardPaperPackageInspection"
        )
    if (
        inspection.health is not ForwardPaperPackageHealth.VALID
        or inspection.findings
        or type(inspection.publication_index) is not ForwardPaperPublicationIndex
        or type(inspection.summary) is not ForwardPaperPackageSummary
    ):
        raise BrokerSafetySourceError(
            "inspection must be VALID with trusted index, summary, and no findings"
        )
    index = inspection.publication_index
    summary = inspection.summary
    if (
        summary.publication_id != index.publication_id
        or summary.activation_id != index.activation_id
        or summary.qualification_evaluation_id
        != index.qualification_evaluation_id
        or summary.strategy_id != index.strategy_id
        or summary.policy_id != index.policy_id
        or summary.policy_version != index.policy_version
        or summary.eligibility_state is not index.eligibility_state
    ):
        raise BrokerSafetySourceError(
            "inspection summary identities do not match Publication Index"
        )
    return index, summary


def _trusted_ledger(
    index: ForwardPaperPublicationIndex,
    summary: ForwardPaperPackageSummary,
    ledger: ForwardDecisionLedger,
) -> tuple[str, dict[str, Any]]:
    if type(ledger) is not ForwardDecisionLedger:
        raise BrokerSafetySourceError(
            "ledger must be an exact ForwardDecisionLedger"
        )
    canonical = export_forward_decision_ledger_json(ledger)
    digest = _sha256(canonical)
    if (
        digest != index.ledger_sha256
        or ledger.ledger_id != index.ledger_id
        or ledger.activation_id != index.activation_id
        or ledger.qualification_evaluation_id
        != index.qualification_evaluation_id
        or ledger.strategy_id != index.strategy_id
        or len(ledger.decisions) != summary.decision_count
    ):
        raise BrokerSafetySourceError(
            "ledger canonical identity does not match trusted inspection"
        )
    return digest, serialize_forward_decision_ledger(ledger)


def _trusted_workspace_sources(
    workspace_root: str | Path,
    run_id: str,
) -> tuple[
    ForwardPaperPackageInspection,
    ForwardDecisionLedger,
    dict[str, StrategyBoundRecommendationEvidence],
]:
    try:
        inspection, loaded, recommendations = (
            _inspect_forward_paper_workspace_package_sources(
                workspace_root,
                run_id,
            )
        )
    except (OSError, TypeError, ValueError, WorkspaceError) as exc:
        raise BrokerSafetySourceError(
            f"E2 package inspection failed: {exc}"
        ) from exc
    index, summary = _trusted_inspection(inspection)
    if loaded is None:
        raise BrokerSafetySourceError(
            "VALID E2 inspection did not retain trusted package sources"
        )
    ledger = loaded.get("decision_ledger")
    if type(ledger) is not ForwardDecisionLedger:
        raise BrokerSafetySourceError(
            "VALID E2 inspection did not retain an exact decision ledger"
        )
    trusted_recommendations: dict[str, StrategyBoundRecommendationEvidence] = {}
    for recommendation in recommendations:
        if (
            type(recommendation) is not StrategyBoundRecommendationEvidence
            or recommendation.recommendation_id in trusted_recommendations
        ):
            raise BrokerSafetySourceError(
                "VALID E2 inspection retained invalid recommendation sources"
            )
        trusted_recommendations[recommendation.recommendation_id] = recommendation
    if tuple(trusted_recommendations) != tuple(
        anchor.recommendation_id for anchor in index.recommendation_anchors
    ):
        raise BrokerSafetySourceError(
            "trusted recommendation sources do not match Publication Index order"
        )
    _trusted_ledger(index, summary, ledger)
    return inspection, ledger, trusted_recommendations


def _lineage(index: ForwardPaperPublicationIndex) -> ForwardEligibilityLineageKey:
    return ForwardEligibilityLineageKey(
        activation_id=index.activation_id,
        strategy_id=index.strategy_id,
        policy_id=index.policy_id,
        policy_version=index.policy_version,
    )


def _build_forward_eligibility_progression(
    inspection: ForwardPaperPackageInspection,
    ledger: ForwardDecisionLedger,
) -> ForwardEligibilityProgression:
    """Derive one canonical progression from sources retained by fresh E2 inspection."""
    index, summary = _trusted_inspection(inspection)
    ledger_sha256, serialized = _trusted_ledger(index, summary, ledger)
    anchors = tuple(
        ForwardEligibilityDecisionAnchor(
            recommendation_id=record.recommendation_id,
            recommendation_sha256=record.recommendation_sha256,
            observed_at=record.observed_at,
            symbol=record.symbol,
            decision_sha256=_canonical_sha256({
                "schema_version": SOURCE_SCHEMA_VERSION,
                "artifact_type": "forward_eligibility_decision_anchor",
                "decision": payload,
            }),
        )
        for record, payload in zip(ledger.decisions, serialized["decisions"])
    )
    index_anchors = tuple(
        (item.recommendation_id, item.recommendation_sha256)
        for item in index.recommendation_anchors
    )
    if index_anchors != tuple(
        (item.recommendation_id, item.recommendation_sha256) for item in anchors
    ):
        raise BrokerSafetySourceError(
            "ledger recommendation identities do not match Publication Index"
        )
    facts = {
        "lineage_key": _lineage(index),
        "run_id": inspection.run_id,
        "publication_id": index.publication_id,
        "publication_index_sha256": _sha256(
            export_forward_paper_publication_index_json(index)
        ),
        "qualification_evaluation_id": index.qualification_evaluation_id,
        "eligibility_id": index.eligibility_id,
        "eligibility_state": index.eligibility_state,
        "eligibility_sha256": index.eligibility_sha256,
        "metrics_id": index.metrics_id,
        "metrics_sha256": index.metrics_sha256,
        "ledger_id": index.ledger_id,
        "ledger_sha256": ledger_sha256,
        "decision_count": len(anchors),
        "last_observed_at": None if not anchors else anchors[-1].observed_at,
        "recommendation_anchors": anchors,
    }
    try:
        return ForwardEligibilityProgression(
            schema_version=SOURCE_SCHEMA_VERSION,
            artifact_type=PROGRESSION_ARTIFACT_TYPE,
            progression_fingerprint=progression_fingerprint(**facts),
            **facts,
        )
    except (BrokerSafetySourceModelError, TypeError, ValueError) as exc:
        raise BrokerSafetySourceError(str(exc)) from exc


def build_forward_eligibility_progression(
    workspace_root: str | Path,
    run_id: str,
) -> ForwardEligibilityProgression:
    """Freshly inspect one persisted package and derive its progression."""
    inspection, ledger, _ = _trusted_workspace_sources(workspace_root, run_id)
    return _build_forward_eligibility_progression(inspection, ledger)


def build_broker_safety_source_handoff(
    workspace_root: str | Path,
    run_id: str,
    recommendation_id: str,
) -> BrokerSafetySourceHandoff:
    """Freshly inspect one persisted package and build an ACTIVE handoff."""
    inspection, ledger, recommendations = _trusted_workspace_sources(
        workspace_root,
        run_id,
    )
    progression = _build_forward_eligibility_progression(inspection, ledger)
    if progression.eligibility_state is not ForwardEligibilityState.ACTIVE:
        raise BrokerSafetySourceError(
            "broker-safety source handoff requires the current package to be ACTIVE"
        )
    if type(recommendation_id) is not str:
        raise BrokerSafetySourceError("recommendation_id must be an exact string")
    recommendation = recommendations.get(recommendation_id)
    if recommendation is None:
        raise BrokerSafetySourceError(
            "recommendation_id is absent from the freshly inspected package"
        )
    index = inspection.publication_index
    summary = inspection.summary
    assert index is not None and summary is not None
    recommendation_sha256 = _sha256(
        export_strategy_bound_recommendation_evidence_json(recommendation)
    )
    matching_anchors = tuple(
        item for item in index.recommendation_anchors
        if item.recommendation_id == recommendation.recommendation_id
    )
    matching_decisions = tuple(
        item for item in ledger.decisions
        if item.recommendation_id == recommendation.recommendation_id
    )
    if len(matching_anchors) != 1 or len(matching_decisions) != 1:
        raise BrokerSafetySourceError(
            "recommendation must resolve exactly once in trusted index and ledger"
        )
    anchor = matching_anchors[0]
    decision = matching_decisions[0]
    snapshot = recommendation.signal_snapshot
    provenance = snapshot.provenance
    if (
        anchor.recommendation_sha256 != recommendation_sha256
        or decision.recommendation_sha256 != recommendation_sha256
        or recommendation.source_qualification_evaluation_id
        != decision.qualification_evaluation_id
        or recommendation.strategy_id != decision.strategy_id
        or snapshot.observed_at != decision.observed_at
        or recommendation.generated_at != decision.generated_at
        or snapshot.symbol != decision.symbol
        or snapshot.signal != decision.signal
        or recommendation.action != decision.action
        or dict(provenance.selected_parameters)
        != dict(decision.selected_parameters)
    ):
        raise BrokerSafetySourceError(
            "recommendation canonical facts do not match trusted decision"
        )
    if snapshot.symbol not in summary.qualified_symbols:
        raise BrokerSafetySourceError(
            "recommendation symbol is outside the trusted qualified universe"
        )
    qualified_symbols_sha256 = _canonical_sha256({
        "schema_version": SOURCE_SCHEMA_VERSION,
        "artifact_type": "qualified_symbol_universe",
        "qualified_symbols": list(summary.qualified_symbols),
    })
    selected_parameters_sha256 = _canonical_sha256({
        "schema_version": SOURCE_SCHEMA_VERSION,
        "artifact_type": "selected_strategy_parameters",
        "selected_parameters": dict(decision.selected_parameters),
    })
    try:
        return BrokerSafetySourceHandoff(
            schema_version=SOURCE_SCHEMA_VERSION,
            artifact_type=HANDOFF_ARTIFACT_TYPE,
            workspace_run_id=inspection.run_id,
            publication_id=index.publication_id,
            publication_index_sha256=progression.publication_index_sha256,
            activation_id=index.activation_id,
            qualification_evaluation_id=index.qualification_evaluation_id,
            strategy_id=index.strategy_id,
            eligibility_id=index.eligibility_id,
            eligibility_state=index.eligibility_state,
            policy_id=index.policy_id,
            policy_version=index.policy_version,
            qualified_symbols=summary.qualified_symbols,
            qualified_symbols_sha256=qualified_symbols_sha256,
            ledger_id=index.ledger_id,
            ledger_sha256=progression.ledger_sha256,
            recommendation_id=recommendation.recommendation_id,
            recommendation_sha256=recommendation_sha256,
            decision_symbol=decision.symbol,
            decision_observed_at=decision.observed_at,
            decision_signal=decision.signal,
            decision_action=decision.action,
            selected_parameters_sha256=selected_parameters_sha256,
            lineage_key=progression.lineage_key,
            progression_fingerprint=progression.progression_fingerprint,
        )
    except (BrokerSafetySourceModelError, TypeError, ValueError) as exc:
        raise BrokerSafetySourceError(str(exc)) from exc


__all__ = [
    "BrokerSafetySourceError",
    "build_broker_safety_source_handoff",
    "build_forward_eligibility_progression",
]
