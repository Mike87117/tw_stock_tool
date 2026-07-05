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
