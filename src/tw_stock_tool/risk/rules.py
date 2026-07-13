import math
from collections.abc import Sequence
from typing import Any

from .models import RiskDecision, RiskInputSnapshot, RiskModelError, RiskRuleEvaluation, RiskEvaluationSummary

def _validate_positive_finite_number(name: str, value: object) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) or value <= 0:
        raise RiskModelError(f"{name} must be a finite positive number.")


def check_max_order_notional(snapshot: RiskInputSnapshot, max_order_notional: float) -> RiskDecision:
    if not isinstance(snapshot, RiskInputSnapshot):
        raise RiskModelError("snapshot must be a RiskInputSnapshot.")
        
    _validate_positive_finite_number("max_order_notional", max_order_notional)

    metadata = {
        "symbol": snapshot.symbol,
        "side": snapshot.side,
        "order_notional": snapshot.order_notional,
        "max_order_notional": max_order_notional
    }

    if snapshot.order_notional <= max_order_notional:
        return RiskDecision.allow(metadata=metadata)
    else:
        return RiskDecision.reject(
            reasons=["order_notional exceeds max_order_notional"],
            metadata=metadata
        )

def check_max_position_quantity(snapshot: RiskInputSnapshot, max_position_quantity: int) -> RiskDecision:
    if not isinstance(snapshot, RiskInputSnapshot):
        raise RiskModelError("snapshot must be a RiskInputSnapshot.")
        
    if not isinstance(max_position_quantity, int) or isinstance(max_position_quantity, bool) or max_position_quantity <= 0:
        raise RiskModelError("max_position_quantity must be a positive integer.")

    metadata = {
        "symbol": snapshot.symbol,
        "side": snapshot.side,
        "quantity": snapshot.quantity,
        "current_position_quantity": snapshot.current_position_quantity,
        "projected_position_quantity": snapshot.projected_position_quantity,
        "max_position_quantity": max_position_quantity
    }

    if snapshot.projected_position_quantity <= max_position_quantity:
        return RiskDecision.allow(metadata=metadata)
    else:
        return RiskDecision.reject(
            reasons=["projected_position_quantity exceeds max_position_quantity"],
            metadata=metadata
        )

def check_max_position_notional(snapshot: RiskInputSnapshot, max_position_notional: float) -> RiskDecision:
    if not isinstance(snapshot, RiskInputSnapshot):
        raise RiskModelError("snapshot must be a RiskInputSnapshot.")
        
    _validate_positive_finite_number("max_position_notional", max_position_notional)

    metadata = {
        "symbol": snapshot.symbol,
        "side": snapshot.side,
        "quantity": snapshot.quantity,
        "price": snapshot.price,
        "order_notional": snapshot.order_notional,
        "current_position_notional": snapshot.current_position_notional,
        "projected_position_notional": snapshot.projected_position_notional,
        "max_position_notional": max_position_notional
    }

    if snapshot.projected_position_notional <= max_position_notional:
        return RiskDecision.allow(metadata=metadata)
    else:
        return RiskDecision.reject(
            reasons=["projected_position_notional exceeds max_position_notional"],
            metadata=metadata
        )

def check_max_total_exposure(snapshot: RiskInputSnapshot, max_total_exposure: float) -> RiskDecision:
    if not isinstance(snapshot, RiskInputSnapshot):
        raise RiskModelError("snapshot must be a RiskInputSnapshot.")
        
    _validate_positive_finite_number("max_total_exposure", max_total_exposure)

    if snapshot.side == "BUY":
        projected_total_exposure = snapshot.total_exposure + snapshot.order_notional
    else:
        projected_total_exposure = max(0.0, snapshot.total_exposure - snapshot.order_notional)

    metadata = {
        "symbol": snapshot.symbol,
        "side": snapshot.side,
        "quantity": snapshot.quantity,
        "price": snapshot.price,
        "order_notional": snapshot.order_notional,
        "total_exposure": snapshot.total_exposure,
        "projected_total_exposure": projected_total_exposure,
        "max_total_exposure": max_total_exposure
    }

    if projected_total_exposure <= max_total_exposure:
        return RiskDecision.allow(metadata=metadata)
    else:
        return RiskDecision.reject(
            reasons=["projected_total_exposure exceeds max_total_exposure"],
            metadata=metadata
        )
def check_max_open_positions(snapshot: RiskInputSnapshot, max_open_positions: int) -> RiskDecision:
    if not isinstance(snapshot, RiskInputSnapshot):
        raise RiskModelError("snapshot must be a RiskInputSnapshot.")
        
    if not isinstance(max_open_positions, int) or isinstance(max_open_positions, bool) or max_open_positions <= 0:
        raise RiskModelError("max_open_positions must be a positive integer.")

    projected_open_positions = snapshot.current_open_positions
    opens_new_position = False
    closes_position = False

    if snapshot.side == "BUY" and snapshot.current_position_quantity == 0:
        projected_open_positions += 1
        opens_new_position = True
    elif (
        snapshot.side == "SELL"
        and snapshot.current_position_quantity > 0
        and snapshot.quantity >= snapshot.current_position_quantity
    ):
        projected_open_positions = max(0, snapshot.current_open_positions - 1)
        closes_position = True

    metadata = {
        "symbol": snapshot.symbol,
        "side": snapshot.side,
        "quantity": snapshot.quantity,
        "current_position_quantity": snapshot.current_position_quantity,
        "current_open_positions": snapshot.current_open_positions,
        "projected_open_positions": projected_open_positions,
        "max_open_positions": max_open_positions,
        "opens_new_position": opens_new_position,
        "closes_position": closes_position
    }

    if projected_open_positions <= max_open_positions:
        return RiskDecision.allow(metadata=metadata)
    else:
        return RiskDecision.reject(
            reasons=["projected_open_positions exceeds max_open_positions"],
            metadata=metadata
        )


def combine_risk_decisions(decisions: Sequence[RiskDecision]) -> RiskDecision:
    if not isinstance(decisions, Sequence) or isinstance(decisions, (str, bytes)):
        raise RiskModelError("decisions must be a non-string sequence of RiskDecision objects.")
    
    if not decisions:
        raise RiskModelError("decisions cannot be empty.")

    decision_count = len(decisions)
    allowed_count = 0
    rejected_count = 0
    reasons = []

    for decision in decisions:
        if not isinstance(decision, RiskDecision):
            raise RiskModelError(f"Expected RiskDecision, got {type(decision).__name__}")
        
        if decision.allowed:
            allowed_count += 1
        else:
            rejected_count += 1
            reasons.extend(decision.reasons)

    metadata = {
        "decision_count": decision_count,
        "allowed_count": allowed_count,
        "rejected_count": rejected_count,
        "all_allowed": rejected_count == 0
    }

    if rejected_count == 0:
        return RiskDecision.allow(metadata=metadata)
    else:
        return RiskDecision.reject(reasons=reasons, metadata=metadata)


def combine_risk_rule_evaluations(evaluations: Sequence[RiskRuleEvaluation]) -> RiskDecision:
    if not isinstance(evaluations, Sequence) or isinstance(evaluations, (str, bytes)):
        raise RiskModelError("evaluations must be a non-string sequence of RiskRuleEvaluation objects.")
    
    if not evaluations:
        raise RiskModelError("evaluations cannot be empty.")

    evaluation_count = len(evaluations)
    allowed_count = 0
    rejected_count = 0
    rule_names = []
    rejected_rule_names = []
    reasons = []

    for eval_item in evaluations:
        if not isinstance(eval_item, RiskRuleEvaluation):
            raise RiskModelError(f"Expected RiskRuleEvaluation, got {type(eval_item).__name__}")
        
        rule_names.append(eval_item.rule_name)
        if eval_item.decision.allowed:
            allowed_count += 1
        else:
            rejected_count += 1
            rejected_rule_names.append(eval_item.rule_name)
            for reason in eval_item.decision.reasons:
                reasons.append(f"{eval_item.rule_name}: {reason}")

    metadata = {
        "evaluation_count": evaluation_count,
        "allowed_count": allowed_count,
        "rejected_count": rejected_count,
        "all_allowed": rejected_count == 0,
        "rule_names": rule_names,
        "rejected_rule_names": rejected_rule_names
    }

    if rejected_count == 0:
        return RiskDecision.allow(metadata=metadata)
    else:
        return RiskDecision.reject(reasons=reasons, metadata=metadata)

def build_risk_evaluation_summary(evaluations: Sequence[RiskRuleEvaluation]) -> RiskEvaluationSummary:
    # Check sequence
    if not isinstance(evaluations, Sequence) or isinstance(evaluations, (str, bytes)):
        raise RiskModelError("evaluations must be a non-string sequence of RiskRuleEvaluation objects.")
    
    if not evaluations:
        raise RiskModelError("evaluations cannot be empty.")
        
    for eval_item in evaluations:
        if not isinstance(eval_item, RiskRuleEvaluation):
            raise RiskModelError(f"Expected RiskRuleEvaluation, got {type(eval_item).__name__}")
            
    # Combine decisions
    aggregate_decision = combine_risk_rule_evaluations(evaluations)
    
    # The summary takes normalized tuple, aggregate decision, and metadata.
    # Metadata is copied from aggregate_decision metadata.
    return RiskEvaluationSummary(
        evaluations=tuple(evaluations),
        decision=aggregate_decision,
        metadata=dict(aggregate_decision.metadata)
    )
