"""
Kill Switch Decision Boundary.

Defines the offline `KillSwitchDecision` model and evaluation logic.
"""
from dataclasses import dataclass
from .models import KillSwitchState, KillSwitchModelError

@dataclass(frozen=True, slots=True)
class KillSwitchDecision:
    is_allowed: bool
    reason: str | None = None

    def __post_init__(self):
        if type(self.is_allowed) is not bool:
            raise KillSwitchModelError("is_allowed must be a bool.")

        if self.is_allowed is True:
            if self.reason is not None:
                raise KillSwitchModelError("reason must be None when is_allowed is True.")
        else:
            if not isinstance(self.reason, str):
                raise KillSwitchModelError("reason must be a non-empty string when is_allowed is False.")
            if not self.reason.strip():
                raise KillSwitchModelError("reason must not be blank or whitespace-only.")

    @property
    def is_blocked(self) -> bool:
        return not self.is_allowed

def evaluate_kill_switch(state: KillSwitchState) -> KillSwitchDecision:
    if not isinstance(state, KillSwitchState):
        raise KillSwitchModelError("state must be a KillSwitchState object.")

    if not state.is_active:
        return KillSwitchDecision(is_allowed=True, reason=None)
    else:
        return KillSwitchDecision(is_allowed=False, reason=state.reason)
