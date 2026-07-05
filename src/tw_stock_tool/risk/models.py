from dataclasses import dataclass, field
from typing import Any, Tuple, Union, Sequence

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
    def allow(cls, reasons: Union[Sequence[str], None] = None, metadata: dict[str, Any] = None) -> "RiskDecision":
        reasons_tup = tuple(reasons) if reasons is not None else ()
        return cls(allowed=True, reasons=reasons_tup, metadata=metadata or {})

    @classmethod
    def reject(cls, reasons: Sequence[str], metadata: dict[str, Any] = None) -> "RiskDecision":
        if not reasons:
            raise RiskModelError("A rejected decision must have at least one reason.")
        return cls(allowed=False, reasons=tuple(reasons), metadata=metadata or {})

    @property
    def is_rejected(self) -> bool:
        return not self.allowed
