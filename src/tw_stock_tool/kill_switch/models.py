"""
Kill Switch State Models.

Defines the offline `KillSwitchState` and pure functions for activating
and releasing the kill switch.
"""
from dataclasses import dataclass
from datetime import datetime

class KillSwitchModelError(Exception):
    """Raised when kill switch model data is invalid."""
    pass

@dataclass(frozen=True, slots=True)
class KillSwitchState:
    is_active: bool = False
    reason: str | None = None
    activated_at: datetime | None = None

    def __post_init__(self):
        if type(self.is_active) is not bool:
            raise KillSwitchModelError("is_active must be a bool.")
            
        if self.is_active is False:
            if self.reason is not None:
                raise KillSwitchModelError("reason must be None when is_active is False.")
            if self.activated_at is not None:
                raise KillSwitchModelError("activated_at must be None when is_active is False.")
        else:
            if not isinstance(self.reason, str):
                raise KillSwitchModelError("reason must be a string when is_active is True.")
            if not self.reason.strip():
                raise KillSwitchModelError("reason must not be blank or whitespace-only.")
                
            if type(self.activated_at) is not datetime:
                raise KillSwitchModelError("activated_at must be a datetime.datetime object.")

    @property
    def is_inactive(self) -> bool:
        return not self.is_active


def activate_kill_switch(
    state: KillSwitchState,
    reason: str,
    activated_at: datetime,
) -> KillSwitchState:
    if not isinstance(state, KillSwitchState):
        raise KillSwitchModelError("state must be a KillSwitchState object.")
        
    return KillSwitchState(
        is_active=True,
        reason=reason,
        activated_at=activated_at
    )

def release_kill_switch(state: KillSwitchState) -> KillSwitchState:
    if not isinstance(state, KillSwitchState):
        raise KillSwitchModelError("state must be a KillSwitchState object.")
        
    return KillSwitchState(
        is_active=False,
        reason=None,
        activated_at=None
    )
