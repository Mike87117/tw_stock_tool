"""Pure deterministic evaluator for research-only strategy qualification."""

from __future__ import annotations

from tw_stock_tool.qualification.derivation import evaluate_derived_request
from tw_stock_tool.qualification.models import (
    StrategyQualificationRequest,
    StrategyQualificationResult,
)


def evaluate_strategy_qualification(
    request: StrategyQualificationRequest,
) -> StrategyQualificationResult:
    """Evaluate precomputed evidence without data access, backtests, or I/O."""
    return evaluate_derived_request(request)


__all__ = ["evaluate_strategy_qualification"]
