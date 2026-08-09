"""No-I/O create and append boundaries for forward decisions."""

from __future__ import annotations

from dataclasses import replace
import hashlib
from typing import Any

from tw_stock_tool.application.forward_paper_activation import (
    ForwardPaperActivationError,
    build_forward_paper_activation,
)
from tw_stock_tool.application.universe_qualification import UniverseOOSArtifact
from tw_stock_tool.forward_paper.decision_models import (
    FORWARD_DECISION_LEDGER_ARTIFACT_TYPE,
    FORWARD_DECISION_LEDGER_SCHEMA_VERSION,
    ForwardDecisionLedger,
    ForwardDecisionRecord,
)
from tw_stock_tool.forward_paper.decision_serialization import (
    export_forward_decision_ledger_json,
    load_forward_decision_ledger_json,
)
from tw_stock_tool.forward_paper.models import ForwardPaperActivation
from tw_stock_tool.forward_paper.serialization import (
    ForwardPaperSerializationError,
    export_forward_paper_activation_json,
    load_forward_paper_activation_json,
)
from tw_stock_tool.qualification import export_strategy_qualification_json
from tw_stock_tool.recommendation import (
    StrategyBoundRecommendationError,
    StrategyBoundRecommendationEvidence,
    StrategyBoundSerializationError,
    export_strategy_bound_recommendation_evidence_json,
    load_strategy_bound_recommendation_evidence_json,
    require_strategy_bound_recommendation_evidence,
)


class ForwardDecisionLedgerError(ValueError):
    """Raised when a forward decision violates activation or chronology locks."""


def _validated_activation_source(
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
) -> tuple[ForwardPaperActivation, str]:
    if type(activation) is not ForwardPaperActivation:
        raise ForwardDecisionLedgerError(
            "activation must be an exact ForwardPaperActivation"
        )
    try:
        input_json = export_forward_paper_activation_json(activation)
        trusted = load_forward_paper_activation_json(input_json)
        canonical_json = export_forward_paper_activation_json(trusted)
    except (TypeError, ValueError, ForwardPaperSerializationError) as exc:
        raise ForwardDecisionLedgerError(
            f"activation failed canonical validation: {exc}"
        ) from exc
    if canonical_json != input_json:
        raise ForwardDecisionLedgerError(
            "activation is not in canonical serialized form"
        )
    try:
        expected = build_forward_paper_activation(
            qualification_artifact,
            activation_id=trusted.activation_id,
            created_at=trusted.created_at,
        )
    except ForwardPaperActivationError as exc:
        raise ForwardDecisionLedgerError(
            f"qualification source failed activation validation: {exc}"
        ) from exc
    if expected != trusted:
        raise ForwardDecisionLedgerError(
            "activation does not match the supplied qualification source"
        )
    return trusted, hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _validated_ledger(value: ForwardDecisionLedger) -> ForwardDecisionLedger:
    if type(value) is not ForwardDecisionLedger:
        raise ForwardDecisionLedgerError(
            "ledger must be an exact ForwardDecisionLedger"
        )
    try:
        input_json = export_forward_decision_ledger_json(value)
        trusted = load_forward_decision_ledger_json(input_json)
        canonical_json = export_forward_decision_ledger_json(trusted)
    except (TypeError, ValueError, ForwardPaperSerializationError) as exc:
        raise ForwardDecisionLedgerError(
            f"ledger failed canonical validation: {exc}"
        ) from exc
    if canonical_json != input_json:
        raise ForwardDecisionLedgerError("ledger is not in canonical serialized form")
    return trusted

def _validate_ledger_records(
    ledger: ForwardDecisionLedger,
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
) -> None:
    if not ledger.decisions:
        return
    parameter_grid = {
        tuple(parameters.items())
        for parameters in qualification_artifact.resolved_configuration.parameter_grid
    }
    for item in ledger.decisions:
        if item.observed_at <= activation.qualification_cutoff:
            raise ForwardDecisionLedgerError(
                "existing decision observed_at must be strictly after qualification_cutoff"
            )
        if item.symbol not in activation.qualified_symbols:
            raise ForwardDecisionLedgerError(
                "existing decision symbol is outside the qualified universe"
            )
        if item.qualification_evaluation_id != activation.qualification_evaluation_id:
            raise ForwardDecisionLedgerError(
                "existing decision qualification evaluation ID mismatch"
            )
        if item.strategy_id != activation.strategy_id:
            raise ForwardDecisionLedgerError("existing decision strategy mismatch")
        if tuple(item.selected_parameters.items()) not in parameter_grid:
            raise ForwardDecisionLedgerError(
                "existing decision selected_parameters are outside the qualified parameter grid"
            )



def _validated_evidence(
    value: Any,
) -> tuple[StrategyBoundRecommendationEvidence, str]:
    try:
        evidence = require_strategy_bound_recommendation_evidence(value)
    except StrategyBoundRecommendationError as exc:
        raise ForwardDecisionLedgerError(str(exc)) from exc
    if type(evidence) is not StrategyBoundRecommendationEvidence:
        raise ForwardDecisionLedgerError(
            "decision evidence must be an exact schema-1.1 artifact"
        )
    try:
        input_json = export_strategy_bound_recommendation_evidence_json(evidence)
        trusted = load_strategy_bound_recommendation_evidence_json(input_json)
        canonical_json = export_strategy_bound_recommendation_evidence_json(trusted)
    except (TypeError, ValueError, StrategyBoundSerializationError) as exc:
        raise ForwardDecisionLedgerError(
            f"recommendation evidence failed canonical validation: {exc}"
        ) from exc
    if canonical_json != input_json:
        raise ForwardDecisionLedgerError(
            "recommendation evidence is not in canonical serialized form"
        )
    return trusted, canonical_json


def create_forward_decision_ledger(
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
    *,
    ledger_id: str,
    created_at: str,
) -> ForwardDecisionLedger:
    trusted, activation_sha256 = _validated_activation_source(
        activation, qualification_artifact
    )
    return ForwardDecisionLedger(
        schema_version=FORWARD_DECISION_LEDGER_SCHEMA_VERSION,
        artifact_type=FORWARD_DECISION_LEDGER_ARTIFACT_TYPE,
        ledger_id=ledger_id,
        created_at=created_at,
        activation_id=trusted.activation_id,
        activation_sha256=activation_sha256,
        qualification_evaluation_id=trusted.qualification_evaluation_id,
        qualification_sha256=trusted.qualification_sha256,
        strategy_id=trusted.strategy_id,
        decisions=(),
    )


def append_forward_decision(
    ledger: ForwardDecisionLedger,
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
    evidence: Any,
) -> ForwardDecisionLedger:
    trusted_ledger = _validated_ledger(ledger)
    trusted_activation, activation_sha256 = _validated_activation_source(
        activation, qualification_artifact
    )
    ledger_lock = (
        trusted_ledger.activation_id,
        trusted_ledger.activation_sha256,
        trusted_ledger.qualification_evaluation_id,
        trusted_ledger.qualification_sha256,
        trusted_ledger.strategy_id,
    )
    activation_lock = (
        trusted_activation.activation_id,
        activation_sha256,
        trusted_activation.qualification_evaluation_id,
        trusted_activation.qualification_sha256,
        trusted_activation.strategy_id,
    )
    if ledger_lock != activation_lock:
        raise ForwardDecisionLedgerError(
            "ledger activation and qualification identity lock mismatch"
        )
    _validate_ledger_records(trusted_ledger, trusted_activation, qualification_artifact)

    trusted_evidence, recommendation_json = _validated_evidence(evidence)
    snapshot = trusted_evidence.signal_snapshot
    provenance = snapshot.provenance
    if (
        trusted_evidence.source_qualification_evaluation_id
        != trusted_activation.qualification_evaluation_id
    ):
        raise ForwardDecisionLedgerError(
            "recommendation qualification evaluation ID mismatch"
        )
    if trusted_evidence.strategy_id != trusted_activation.strategy_id:
        raise ForwardDecisionLedgerError("recommendation strategy mismatch")
    if provenance.strategy_id != trusted_activation.strategy_id:
        raise ForwardDecisionLedgerError("signal provenance strategy mismatch")
    if (
        provenance.qualification_evaluation_id
        != trusted_activation.qualification_evaluation_id
    ):
        raise ForwardDecisionLedgerError(
            "signal provenance qualification evaluation ID mismatch"
        )
    if snapshot.symbol not in trusted_activation.qualified_symbols:
        raise ForwardDecisionLedgerError(
            "recommendation symbol is outside the qualified universe"
        )
    if snapshot.observed_at <= trusted_activation.qualification_cutoff:
        raise ForwardDecisionLedgerError(
            "recommendation observed_at must be strictly after qualification_cutoff"
        )
    if export_strategy_qualification_json(
        trusted_evidence.qualification
    ) != export_strategy_qualification_json(qualification_artifact.qualification):
        raise ForwardDecisionLedgerError(
            "embedded qualification content does not match the source artifact"
        )

    recommendation_sha256 = hashlib.sha256(
        recommendation_json.encode("utf-8")
    ).hexdigest()
    key = (snapshot.observed_at, snapshot.symbol)
    if key in {
        (item.observed_at, item.symbol) for item in trusted_ledger.decisions
    }:
        raise ForwardDecisionLedgerError(
            "duplicate (observed_at, symbol) decision key"
        )
    if trusted_ledger.decisions and key < (
        trusted_ledger.decisions[-1].observed_at,
        trusted_ledger.decisions[-1].symbol,
    ):
        raise ForwardDecisionLedgerError("decision append would move chronology backward")
    if any(
        item.recommendation_id == trusted_evidence.recommendation_id
        for item in trusted_ledger.decisions
    ):
        raise ForwardDecisionLedgerError("duplicate recommendation ID")
    if any(
        item.recommendation_sha256 == recommendation_sha256
        for item in trusted_ledger.decisions
    ):
        raise ForwardDecisionLedgerError("duplicate recommendation SHA-256")

    record = ForwardDecisionRecord(
        recommendation_id=trusted_evidence.recommendation_id,
        recommendation_sha256=recommendation_sha256,
        observed_at=snapshot.observed_at,
        generated_at=trusted_evidence.generated_at,
        symbol=snapshot.symbol,
        signal=snapshot.signal,
        action=trusted_evidence.action,
        qualification_evaluation_id=(
            trusted_evidence.source_qualification_evaluation_id
        ),
        strategy_id=trusted_evidence.strategy_id,
        selected_parameters=provenance.selected_parameters,
    )
    return replace(
        trusted_ledger, decisions=trusted_ledger.decisions + (record,)
    )


__all__ = [
    "ForwardDecisionLedgerError",
    "append_forward_decision",
    "create_forward_decision_ledger",
]
