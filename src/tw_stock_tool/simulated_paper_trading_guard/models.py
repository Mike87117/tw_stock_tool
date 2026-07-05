"""
Models for the Simulated Paper Trading Guard package.

This module defines the decision boundary model used to aggregate
RiskManager and KillSwitch signals into a single structural decision.
"""
from dataclasses import dataclass, field
from typing import Any

class SimulatedPaperTradingGuardError(Exception):
    pass

@dataclass(frozen=True, slots=True)
class SimulatedPaperTradingGuardDecision:
    is_allowed: bool
    reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if type(self.is_allowed) is not bool:
            raise SimulatedPaperTradingGuardError("is_allowed must be a bool.")

        if not isinstance(self.reasons, (tuple, list)):
            raise SimulatedPaperTradingGuardError("reasons must be a tuple or list.")
        
        # Normalize to tuple and copy metadata
        object.__setattr__(self, 'reasons', tuple(self.reasons))
        
        if not isinstance(self.metadata, dict):
            raise SimulatedPaperTradingGuardError("metadata must be a dict.")
            
        object.__setattr__(self, 'metadata', dict(self.metadata))

        if self.is_allowed is False:
            if not self.reasons:
                raise SimulatedPaperTradingGuardError("At least one reason is required when is_allowed is False.")

        for r in self.reasons:
            if not isinstance(r, str):
                raise SimulatedPaperTradingGuardError("All reasons must be strings.")
            if not r.strip():
                raise SimulatedPaperTradingGuardError("Reasons must not be empty or whitespace-only.")

    @property
    def is_blocked(self) -> bool:
        return not self.is_allowed

    @classmethod
    def allow(cls, reasons=None, metadata=None) -> "SimulatedPaperTradingGuardDecision":
        return cls(is_allowed=True, reasons=reasons or (), metadata=metadata or {})

    @classmethod
    def block(cls, reasons, metadata=None) -> "SimulatedPaperTradingGuardDecision":
        return cls(is_allowed=False, reasons=reasons, metadata=metadata or {})
