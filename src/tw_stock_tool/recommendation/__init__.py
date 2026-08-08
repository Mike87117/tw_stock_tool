"""Research-only recommendation evidence and deterministic action gate."""

from tw_stock_tool.recommendation.derivation import (
    build_recommendation_evidence,
    derive_recommendation_action,
)
from tw_stock_tool.recommendation.models import (
    RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE,
    RECOMMENDATION_EVIDENCE_SCHEMA_VERSION,
    CurrentSignal,
    CurrentSignalSnapshot,
    RecommendationAction,
    RecommendationEvidence,
    RecommendationModelError,
)
from tw_stock_tool.recommendation.serialization import (
    RecommendationSerializationError,
    deserialize_recommendation_evidence,
    export_recommendation_evidence_json,
    load_recommendation_evidence_json,
    serialize_recommendation_evidence,
)

__all__ = [
    "RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE",
    "RECOMMENDATION_EVIDENCE_SCHEMA_VERSION",
    "CurrentSignal",
    "CurrentSignalSnapshot",
    "RecommendationAction",
    "RecommendationEvidence",
    "RecommendationModelError",
    "RecommendationSerializationError",
    "build_recommendation_evidence",
    "derive_recommendation_action",
    "deserialize_recommendation_evidence",
    "export_recommendation_evidence_json",
    "load_recommendation_evidence_json",
    "serialize_recommendation_evidence",
]
