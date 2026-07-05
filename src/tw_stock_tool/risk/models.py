from dataclasses import dataclass, field
from typing import Any, Tuple, Union, Sequence, Literal

class RiskModelError(Exception):
    """Custom exception for invalid risk model data."""
    pass

@dataclass(slots=True)
class RiskDecision:
    allowed: bool
    reasons: Tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.allowed, bool):
            raise RiskModelError("allowed must be a boolean.")
        
        if not isinstance(self.reasons, (tuple, list)):
            raise RiskModelError("reasons must be a tuple or list.")
        
        for reason in self.reasons:
            if not isinstance(reason, str) or not reason.strip():
                raise RiskModelError("reasons must contain non-empty strings.")

        if not self.allowed and not self.reasons:
            raise RiskModelError("A rejected decision must have at least one reason.")

        if not isinstance(self.metadata, dict):
            raise RiskModelError("metadata must be a dictionary.")

        # normalize reasons to tuple
        if isinstance(self.reasons, list):
            object.__setattr__(self, "reasons", tuple(self.reasons))

    @classmethod
    def allow(cls, reasons: Union[Tuple[str, ...], list[str], None] = None, metadata: dict[str, Any] = None) -> "RiskDecision":
        if isinstance(reasons, str):
            raise RiskModelError("reasons must be a tuple or list, not a string.")
        reasons_tup = tuple(reasons) if reasons is not None else ()
        return cls(allowed=True, reasons=reasons_tup, metadata=metadata or {})

    @classmethod
    def reject(cls, reasons: Union[Tuple[str, ...], list[str]], metadata: dict[str, Any] = None) -> "RiskDecision":
        if isinstance(reasons, str):
            raise RiskModelError("reasons must be a tuple or list, not a string.")
        if not reasons:
            raise RiskModelError("A rejected decision must have at least one reason.")
        return cls(allowed=False, reasons=tuple(reasons), metadata=metadata or {})

    @property
    def is_rejected(self) -> bool:
        return not self.allowed

@dataclass(slots=True)
class RiskInputSnapshot:
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: int
    price: float
    cash: float
    current_position_quantity: int = 0
    current_position_notional: float = 0.0
    total_exposure: float = 0.0
    current_open_positions: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise RiskModelError("symbol must be a non-empty string.")
        
        if self.side not in ("BUY", "SELL"):
            raise RiskModelError("side must be 'BUY' or 'SELL'.")
            
        if not isinstance(self.quantity, int) or isinstance(self.quantity, bool) or self.quantity <= 0:
            raise RiskModelError("quantity must be a positive integer.")
            
        if not isinstance(self.price, (int, float)) or isinstance(self.price, bool) or self.price <= 0:
            raise RiskModelError("price must be a positive number.")
            
        if not isinstance(self.cash, (int, float)) or isinstance(self.cash, bool) or self.cash < 0:
            raise RiskModelError("cash must be a non-negative number.")
            
        if not isinstance(self.current_position_quantity, int) or isinstance(self.current_position_quantity, bool) or self.current_position_quantity < 0:
            raise RiskModelError("current_position_quantity must be a non-negative integer.")
            
        if not isinstance(self.current_position_notional, (int, float)) or isinstance(self.current_position_notional, bool) or self.current_position_notional < 0:
            raise RiskModelError("current_position_notional must be a non-negative number.")
            
        if not isinstance(self.total_exposure, (int, float)) or isinstance(self.total_exposure, bool) or self.total_exposure < 0:
            raise RiskModelError("total_exposure must be a non-negative number.")
            
        if not isinstance(self.current_open_positions, int) or isinstance(self.current_open_positions, bool) or self.current_open_positions < 0:
            raise RiskModelError("current_open_positions must be a non-negative integer.")
            
        if not isinstance(self.metadata, dict):
            raise RiskModelError("metadata must be a dictionary.")

    @property
    def order_notional(self) -> float:
        return self.quantity * self.price

    @property
    def projected_position_quantity(self) -> int:
        if self.side == "BUY":
            return self.current_position_quantity + self.quantity
        else:
            return self.current_position_quantity - self.quantity

    @property
    def projected_position_notional(self) -> float:
        if self.side == "BUY":
            return self.current_position_notional + self.order_notional
        else:
            return max(0.0, self.current_position_notional - self.order_notional)

@dataclass(slots=True)
class RiskRuleEvaluation:
    rule_name: str
    decision: RiskDecision
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.rule_name, str) or not self.rule_name.strip():
            raise RiskModelError("rule_name must be a non-empty string.")
        
        if not isinstance(self.decision, RiskDecision):
            raise RiskModelError("decision must be a RiskDecision object.")
            
        if not isinstance(self.metadata, dict):
            raise RiskModelError("metadata must be a dictionary.")

@dataclass(slots=True)
class RiskEvaluationSummary:
    evaluations: tuple[RiskRuleEvaluation, ...]
    decision: RiskDecision
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.evaluations, (tuple, list)):
            raise RiskModelError("evaluations must be a tuple or list.")
        
        if not self.evaluations:
            raise RiskModelError("evaluations cannot be empty.")
            
        for eval_item in self.evaluations:
            if not isinstance(eval_item, RiskRuleEvaluation):
                raise RiskModelError(f"Expected RiskRuleEvaluation in evaluations, got {type(eval_item).__name__}")
                
        if not isinstance(self.decision, RiskDecision):
            raise RiskModelError("decision must be a RiskDecision object.")
            
        if not isinstance(self.metadata, dict):
            raise RiskModelError("metadata must be a dictionary.")
            
        if isinstance(self.evaluations, list):
            object.__setattr__(self, "evaluations", tuple(self.evaluations))
