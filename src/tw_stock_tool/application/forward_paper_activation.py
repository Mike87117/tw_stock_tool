"""No-I/O application builder for a forward-paper activation lock."""

from __future__ import annotations

import hashlib

from tw_stock_tool.application.universe_qualification import (
    UNIVERSE_OOS_EVIDENCE_ARTIFACT_TYPE,
    UNIVERSE_OOS_EVIDENCE_SCHEMA_VERSION,
    UniverseEvidenceSerializationError,
    UniverseOOSArtifact,
    export_universe_oos_evidence_json,
    load_universe_oos_evidence_json,
)
from tw_stock_tool.forward_paper import (
    FORWARD_PAPER_ACTIVATION_ARTIFACT_TYPE,
    FORWARD_PAPER_ACTIVATION_SCHEMA_VERSION,
    ForwardPaperActivation,
)


class ForwardPaperActivationError(ValueError):
    """Raised when qualification evidence cannot activate forward paper."""


def build_forward_paper_activation(
    qualification_artifact: UniverseOOSArtifact,
    *,
    activation_id: str,
    created_at: str,
) -> ForwardPaperActivation:
    """Freeze one validated PAPER_READY universe evidence identity."""
    if type(qualification_artifact) is not UniverseOOSArtifact:
        raise ForwardPaperActivationError(
            "qualification_artifact must be an actual UniverseOOSArtifact"
        )

    try:
        input_json = export_universe_oos_evidence_json(qualification_artifact)
        source = load_universe_oos_evidence_json(input_json)
        canonical_json = export_universe_oos_evidence_json(source)
    except (TypeError, ValueError, UniverseEvidenceSerializationError) as exc:
        raise ForwardPaperActivationError(
            f"qualification artifact failed canonical validation: {exc}"
        ) from exc
    if canonical_json != input_json:
        raise ForwardPaperActivationError(
            "qualification artifact is not in canonical serialized form"
        )

    qualification = source.qualification
    if qualification.decision.state != "PAPER_READY":
        raise ForwardPaperActivationError("qualification decision must be PAPER_READY")
    if qualification.request.evaluation_id != source.evaluation_id:
        raise ForwardPaperActivationError(
            "qualification and evidence evaluation IDs must agree"
        )

    strategy_id = qualification.request.strategy.strategy_id
    policy = qualification.request.policy
    if not strategy_id or not policy.policy_id or not policy.policy_version:
        raise ForwardPaperActivationError(
            "qualification strategy and policy identities must be valid"
        )

    qualified_symbols = tuple(
        symbol.symbol
        for symbol in source.symbols
        if symbol.evaluated and symbol.valid_windows > 0 and symbol.oos_observations > 0
    )
    if not qualified_symbols:
        raise ForwardPaperActivationError(
            "qualification must contain successful OOS symbol evidence"
        )

    cutoff_candidates = [
        window.test_end
        for symbol in source.symbols
        for window in symbol.windows
    ]
    cutoff_candidates.extend(
        descriptor.index_end
        for descriptor in source.resolved_configuration.benchmark_descriptors
        if descriptor.index_end is not None
    )
    if not cutoff_candidates:
        raise ForwardPaperActivationError(
            "qualification_cutoff cannot be derived from evidence"
        )
    qualification_cutoff = max(cutoff_candidates)
    if created_at < qualification.request.created_at:
        raise ForwardPaperActivationError(
            "activation created_at must not predate qualification creation"
        )
    if created_at < qualification_cutoff:
        raise ForwardPaperActivationError(
            "activation created_at must not predate qualification_cutoff"
        )

    return ForwardPaperActivation(
        schema_version=FORWARD_PAPER_ACTIVATION_SCHEMA_VERSION,
        artifact_type=FORWARD_PAPER_ACTIVATION_ARTIFACT_TYPE,
        activation_id=activation_id,
        created_at=created_at,
        qualification_evaluation_id=source.evaluation_id,
        qualification_artifact_type=UNIVERSE_OOS_EVIDENCE_ARTIFACT_TYPE,
        qualification_schema_version=UNIVERSE_OOS_EVIDENCE_SCHEMA_VERSION,
        qualification_sha256=hashlib.sha256(canonical_json.encode("utf-8")).hexdigest(),
        strategy_id=strategy_id,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        qualification_cutoff=qualification_cutoff,
        qualified_symbols=qualified_symbols,
    )


__all__ = ["ForwardPaperActivationError", "build_forward_paper_activation"]
