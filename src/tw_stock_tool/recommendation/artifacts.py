"""Version-dispatching helpers for Recommendation Evidence artifacts."""

from __future__ import annotations

import json
from typing import Any, NoReturn, TypeAlias

from tw_stock_tool.recommendation.models import RecommendationEvidence
from tw_stock_tool.recommendation.serialization import (
    RecommendationSerializationError,
    export_recommendation_evidence_json,
    load_recommendation_evidence_json,
)
from tw_stock_tool.recommendation.strategy_bound import (
    STRATEGY_BOUND_RECOMMENDATION_EVIDENCE_SCHEMA_VERSION,
    StrategyBoundRecommendationEvidence,
    StrategyBoundSerializationError,
    export_strategy_bound_recommendation_evidence_json,
    load_strategy_bound_recommendation_evidence_json,
)

RecommendationArtifact: TypeAlias = (
    RecommendationEvidence | StrategyBoundRecommendationEvidence
)


class RecommendationArtifactSerializationError(ValueError):
    """Raised when a Recommendation artifact cannot be version-dispatched."""


def _reject_constant(value: str) -> NoReturn:
    raise RecommendationArtifactSerializationError(
        f"$: invalid JSON numeric constant {value}"
    )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RecommendationArtifactSerializationError(
                f"$: duplicate JSON field {key!r}"
            )
        result[key] = value
    return result


def _schema_version(text: str) -> str:
    if type(text) is not str:
        raise RecommendationArtifactSerializationError(
            "$: JSON input must be an exact string"
        )
    try:
        payload = json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_strict_object,
        )
    except RecommendationArtifactSerializationError:
        raise
    except json.JSONDecodeError as exc:
        raise RecommendationArtifactSerializationError(
            f"$: invalid JSON: {exc.msg}"
        ) from exc
    if type(payload) is not dict:
        raise RecommendationArtifactSerializationError(
            "$: expected a JSON object"
        )
    if "schema_version" not in payload:
        raise RecommendationArtifactSerializationError(
            "$.schema_version: missing field"
        )
    version = payload["schema_version"]
    if type(version) is not str:
        raise RecommendationArtifactSerializationError(
            "$.schema_version: expected an exact string"
        )
    return version


def load_recommendation_artifact_json(text: str) -> RecommendationArtifact:
    """Load Recommendation Evidence by explicit schema-version dispatch."""
    version = _schema_version(text)
    try:
        if version == "1.0":
            return load_recommendation_evidence_json(text)
        if version == STRATEGY_BOUND_RECOMMENDATION_EVIDENCE_SCHEMA_VERSION:
            return load_strategy_bound_recommendation_evidence_json(text)
    except (RecommendationSerializationError, StrategyBoundSerializationError) as exc:
        raise RecommendationArtifactSerializationError(str(exc)) from exc
    raise RecommendationArtifactSerializationError(
        f"$.schema_version: unsupported schema version {version!r}"
    )


def export_recommendation_artifact_json(
    evidence: RecommendationArtifact,
) -> str:
    """Export Recommendation Evidence using its concrete schema type."""
    if isinstance(evidence, StrategyBoundRecommendationEvidence):
        return export_strategy_bound_recommendation_evidence_json(evidence)
    if isinstance(evidence, RecommendationEvidence):
        return export_recommendation_evidence_json(evidence)
    raise RecommendationArtifactSerializationError(
        "$: unsupported Recommendation artifact type "
        f"{type(evidence).__name__}"
    )


__all__ = [
    "RecommendationArtifact",
    "RecommendationArtifactSerializationError",
    "export_recommendation_artifact_json",
    "load_recommendation_artifact_json",
]
