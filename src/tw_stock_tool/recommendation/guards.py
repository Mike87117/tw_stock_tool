"""Pure-domain trust boundaries for Recommendation Evidence consumers."""

from __future__ import annotations

from typing import Any

from tw_stock_tool.recommendation.strategy_bound import (
    StrategyBoundRecommendationError,
    StrategyBoundRecommendationEvidence,
)


def require_strategy_bound_recommendation_evidence(
    value: Any,
) -> StrategyBoundRecommendationEvidence:
    """Return schema-1.1 evidence or fail closed for every other value."""
    if not isinstance(value, StrategyBoundRecommendationEvidence):
        raise StrategyBoundRecommendationError(
            "strategy-bound consumer requires Recommendation Evidence schema 1.1"
        )
    return value


__all__ = ["require_strategy_bound_recommendation_evidence"]
