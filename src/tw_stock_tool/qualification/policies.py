"""Versioned policy registry for research-only strategy qualification."""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from tw_stock_tool.qualification.models import QualificationPolicy


class QualificationPolicyError(ValueError):
    """Raised when a qualification policy cannot be resolved."""


TAIWAN_EQUITY_DAILY_V1 = QualificationPolicy(
    policy_id="taiwan_equity_daily_v1",
    policy_version="1.0",
    minimum_oos_observations=252,
    minimum_completed_trades=20,
    minimum_evaluated_symbols=5,
    minimum_valid_windows=4,
    require_benchmark=True,
    minimum_excess_return_pct=0.0,
    require_cost_stress=True,
    maximum_drawdown_pct=25.0,
    minimum_positive_window_ratio=0.5,
    maximum_symbol_concentration_pct=50.0,
    require_parameter_stability=True,
)

_POLICY_REGISTRY: Mapping[tuple[str, str], QualificationPolicy] = MappingProxyType(
    {
        (
            TAIWAN_EQUITY_DAILY_V1.policy_id,
            TAIWAN_EQUITY_DAILY_V1.policy_version,
        ): TAIWAN_EQUITY_DAILY_V1,
    }
)


def resolve_qualification_policy(
    policy_id: str,
    policy_version: str = "1.0",
) -> QualificationPolicy:
    """Resolve one exact registered policy or fail closed."""
    if type(policy_id) is not str or not policy_id or policy_id.strip() != policy_id:
        raise QualificationPolicyError("policy_id must be a clean exact string")
    if (
        type(policy_version) is not str
        or not policy_version
        or policy_version.strip() != policy_version
    ):
        raise QualificationPolicyError("policy_version must be a clean exact string")
    try:
        return _POLICY_REGISTRY[(policy_id, policy_version)]
    except KeyError as exc:
        raise QualificationPolicyError(
            f"unsupported qualification policy: {policy_id}@{policy_version}"
        ) from exc


def is_supported_qualification_policy(policy: QualificationPolicy) -> bool:
    """Return whether policy exactly matches one registered immutable policy."""
    if not isinstance(policy, QualificationPolicy):
        return False
    registered = _POLICY_REGISTRY.get((policy.policy_id, policy.policy_version))
    return registered == policy


SUPPORTED_QUALIFICATION_POLICIES = tuple(_POLICY_REGISTRY.values())


__all__ = [
    "SUPPORTED_QUALIFICATION_POLICIES",
    "TAIWAN_EQUITY_DAILY_V1",
    "QualificationPolicyError",
    "is_supported_qualification_policy",
    "resolve_qualification_policy",
]
