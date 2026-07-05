from typing import Any
from .models import RiskInputSnapshot, RiskDecision, RiskModelError

def check_max_order_notional(snapshot: RiskInputSnapshot, max_order_notional: float) -> RiskDecision:
    if not isinstance(snapshot, RiskInputSnapshot):
        raise RiskModelError("snapshot must be a RiskInputSnapshot.")
        
    if not isinstance(max_order_notional, (int, float)) or isinstance(max_order_notional, bool) or max_order_notional <= 0:
        raise RiskModelError("max_order_notional must be a positive number.")

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
        
    if not isinstance(max_position_notional, (int, float)) or isinstance(max_position_notional, bool) or max_position_notional <= 0:
        raise RiskModelError("max_position_notional must be a positive number.")

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
