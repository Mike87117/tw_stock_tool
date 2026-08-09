"""Versioned registry and pure evaluator for forward eligibility."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from tw_stock_tool.forward_paper.eligibility_models import (
    FORWARD_ELIGIBILITY_POLICY_ID,
    FORWARD_ELIGIBILITY_POLICY_VERSION,
    SUPPORTED_FORWARD_ELIGIBILITY_FINDING_CODES,
    ForwardEligibilityFinding,
    ForwardEligibilityPolicy,
    ForwardEligibilitySeverity,
    ForwardEligibilityState,
)
from tw_stock_tool.forward_paper.metrics_models import ForwardMetricsEvidence


class ForwardEligibilityPolicyError(ValueError):
    """Raised when a forward eligibility policy cannot be resolved."""


TAIWAN_EQUITY_DAILY_FORWARD_V1 = ForwardEligibilityPolicy(
    policy_id=FORWARD_ELIGIBILITY_POLICY_ID,
    policy_version=FORWARD_ELIGIBILITY_POLICY_VERSION,
    pause_max_drawdown_pct=15.0,
    revoke_max_drawdown_pct=25.0,
    minimum_terminal_attempts_for_invalid_open_rate=5,
    pause_invalid_open_rate=0.20,
    revoke_invalid_open_rate=0.50,
    pause_portfolio_validation_failure_count=1,
    revoke_portfolio_validation_failure_count=3,
)

_POLICY_REGISTRY: Mapping[
    tuple[str, str], ForwardEligibilityPolicy
] = MappingProxyType(
    {
        (
            TAIWAN_EQUITY_DAILY_FORWARD_V1.policy_id,
            TAIWAN_EQUITY_DAILY_FORWARD_V1.policy_version,
        ): TAIWAN_EQUITY_DAILY_FORWARD_V1,
    }
)


def resolve_forward_eligibility_policy(
    policy_id: str,
    policy_version: str,
) -> ForwardEligibilityPolicy:
    if type(policy_id) is not str or not policy_id or policy_id.strip() != policy_id:
        raise ForwardEligibilityPolicyError("policy_id must be a clean exact string")
    if (
        type(policy_version) is not str
        or not policy_version
        or policy_version.strip() != policy_version
    ):
        raise ForwardEligibilityPolicyError(
            "policy_version must be a clean exact string"
        )
    try:
        return _POLICY_REGISTRY[(policy_id, policy_version)]
    except KeyError as exc:
        raise ForwardEligibilityPolicyError(
            f"unsupported forward eligibility policy: {policy_id}@{policy_version}"
        ) from exc


def is_supported_forward_eligibility_policy(
    policy: ForwardEligibilityPolicy,
) -> bool:
    if type(policy) is not ForwardEligibilityPolicy:
        return False
    registered = _POLICY_REGISTRY.get((policy.policy_id, policy.policy_version))
    return registered == policy


def _finding(
    code: str,
    metric_name: str,
    observed: float,
    threshold: float,
) -> ForwardEligibilityFinding:
    severity = (
        ForwardEligibilitySeverity.REVOKE
        if code.endswith("_revoke")
        else ForwardEligibilitySeverity.PAUSE
    )
    return ForwardEligibilityFinding(
        code=code,
        severity=severity,
        metric_name=metric_name,
        observed_value=observed,
        threshold_value=threshold,
        message=f"{metric_name} {observed} reached {severity.value} threshold {threshold}",
    )


def evaluate_forward_eligibility(
    metrics: ForwardMetricsEvidence,
    policy: ForwardEligibilityPolicy,
) -> tuple[ForwardEligibilityState, tuple[ForwardEligibilityFinding, ...]]:
    """Map trusted metrics to one deterministic research eligibility state."""
    if type(metrics) is not ForwardMetricsEvidence:
        raise ForwardEligibilityPolicyError(
            "metrics must be an exact ForwardMetricsEvidence"
        )
    if not is_supported_forward_eligibility_policy(policy):
        raise ForwardEligibilityPolicyError("policy is not exactly registered")

    findings: list[ForwardEligibilityFinding] = []
    drawdown = metrics.portfolio_metrics.max_drawdown_pct
    if drawdown >= policy.revoke_max_drawdown_pct:
        findings.append(
            _finding(
                "forward_drawdown_revoke",
                "max_drawdown_pct",
                drawdown,
                policy.revoke_max_drawdown_pct,
            )
        )
    elif drawdown >= policy.pause_max_drawdown_pct:
        findings.append(
            _finding(
                "forward_drawdown_pause",
                "max_drawdown_pct",
                drawdown,
                policy.pause_max_drawdown_pct,
            )
        )

    health = metrics.execution_health
    invalid_rate = health.invalid_open_rate
    if health.terminal_attempt_count >= (
        policy.minimum_terminal_attempts_for_invalid_open_rate
    ):
        if invalid_rate is None:
            raise ForwardEligibilityPolicyError(
                "eligible terminal attempts require an invalid-open rate"
            )
        if invalid_rate >= policy.revoke_invalid_open_rate:
            findings.append(
                _finding(
                    "invalid_open_rate_revoke",
                    "invalid_open_rate",
                    invalid_rate,
                    policy.revoke_invalid_open_rate,
                )
            )
        elif invalid_rate >= policy.pause_invalid_open_rate:
            findings.append(
                _finding(
                    "invalid_open_rate_pause",
                    "invalid_open_rate",
                    invalid_rate,
                    policy.pause_invalid_open_rate,
                )
            )

    failures = health.failed_portfolio_validation_count
    if failures >= policy.revoke_portfolio_validation_failure_count:
        findings.append(
            _finding(
                "portfolio_validation_failure_revoke",
                "failed_portfolio_validation_count",
                failures,
                policy.revoke_portfolio_validation_failure_count,
            )
        )
    elif failures >= policy.pause_portfolio_validation_failure_count:
        findings.append(
            _finding(
                "portfolio_validation_failure_pause",
                "failed_portfolio_validation_count",
                failures,
                policy.pause_portfolio_validation_failure_count,
            )
        )

    ordered = tuple(
        sorted(
            findings,
            key=lambda item: SUPPORTED_FORWARD_ELIGIBILITY_FINDING_CODES.index(
                item.code
            ),
        )
    )
    state = (
        ForwardEligibilityState.REVOKED
        if any(
            item.severity is ForwardEligibilitySeverity.REVOKE for item in ordered
        )
        else ForwardEligibilityState.PAUSED
        if ordered
        else ForwardEligibilityState.ACTIVE
    )
    return state, ordered


SUPPORTED_FORWARD_ELIGIBILITY_POLICIES = tuple(_POLICY_REGISTRY.values())

__all__ = [
    "SUPPORTED_FORWARD_ELIGIBILITY_POLICIES",
    "TAIWAN_EQUITY_DAILY_FORWARD_V1",
    "ForwardEligibilityPolicyError",
    "evaluate_forward_eligibility",
    "is_supported_forward_eligibility_policy",
    "resolve_forward_eligibility_policy",
]
