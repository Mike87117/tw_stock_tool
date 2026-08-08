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
from tw_stock_tool.recommendation.strategy_bound import (
    STRATEGY_BOUND_RECOMMENDATION_EVIDENCE_SCHEMA_VERSION,
    STRATEGY_SIGNAL_SELECTION_RULE,
    StrategyBoundRecommendationError,
    StrategyBoundRecommendationEvidence,
    StrategyBoundSerializationError,
    StrategyBoundSignal,
    StrategyBoundSignalSnapshot,
    StrategySignalProvenance,
    build_strategy_bound_recommendation_evidence,
    deserialize_strategy_bound_recommendation_evidence,
    export_strategy_bound_recommendation_evidence_json,
    load_strategy_bound_recommendation_evidence_json,
    serialize_strategy_bound_recommendation_evidence,
)
from tw_stock_tool.recommendation.artifacts import (
    RecommendationArtifact,
    RecommendationArtifactSerializationError,
    export_recommendation_artifact_json,
    load_recommendation_artifact_json,
)

__all__ = [
    "RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE",
    "RECOMMENDATION_EVIDENCE_SCHEMA_VERSION",
    "STRATEGY_BOUND_RECOMMENDATION_EVIDENCE_SCHEMA_VERSION",
    "STRATEGY_SIGNAL_SELECTION_RULE",
    "CurrentSignal",
    "CurrentSignalSnapshot",
    "RecommendationAction",
    "RecommendationArtifact",
    "RecommendationArtifactSerializationError",
    "RecommendationEvidence",
    "RecommendationModelError",
    "RecommendationSerializationError",
    "StrategyBoundRecommendationError",
    "StrategyBoundRecommendationEvidence",
    "StrategyBoundSerializationError",
    "StrategyBoundSignal",
    "StrategyBoundSignalSnapshot",
    "StrategySignalProvenance",
    "build_recommendation_evidence",
    "build_strategy_bound_recommendation_evidence",
    "derive_recommendation_action",
    "deserialize_recommendation_evidence",
    "deserialize_strategy_bound_recommendation_evidence",
    "export_recommendation_artifact_json",
    "export_recommendation_evidence_json",
    "export_strategy_bound_recommendation_evidence_json",
    "load_recommendation_artifact_json",
    "load_recommendation_evidence_json",
    "load_strategy_bound_recommendation_evidence_json",
    "serialize_recommendation_evidence",
    "serialize_strategy_bound_recommendation_evidence",
]
