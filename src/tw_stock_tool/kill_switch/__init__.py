"""
Kill Switch Package Boundary.

This package defines the offline, structural, deterministic state model
and decision boundary for the Kill Switch.
"""
from .models import KillSwitchState, KillSwitchModelError, activate_kill_switch, release_kill_switch
from .decisions import KillSwitchDecision, evaluate_kill_switch

__all__ = [
    "KillSwitchState",
    "KillSwitchModelError",
    "activate_kill_switch",
    "release_kill_switch",
    "KillSwitchDecision",
    "evaluate_kill_switch"
]
