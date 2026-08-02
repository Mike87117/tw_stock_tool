"""Pure deterministic evaluator for research-only strategy qualification."""

from __future__ import annotations

from tw_stock_tool.qualification.findings import (
    finding_reason_codes,
    normalize_findings,
)
from tw_stock_tool.qualification.models import (
    STRATEGY_QUALIFICATION_ARTIFACT_TYPE,
    STRATEGY_QUALIFICATION_SCHEMA_VERSION,
    PromotionDecision,
    QualificationFinding,
    StrategyQualificationRequest,
    StrategyQualificationResult,
)
from tw_stock_tool.qualification.policies import is_supported_qualification_policy


def _finding(
    code: str,
    severity: str,
    message: str,
    *,
    metric_name: str | None = None,
    observed_value: str | int | float | bool | None = None,
    threshold_value: str | int | float | bool | None = None,
) -> QualificationFinding:
    return QualificationFinding(
        code=code,
        severity=severity,
        scope="aggregate",
        message=message,
        metric_name=metric_name,
        observed_value=observed_value,
        threshold_value=threshold_value,
    )


def evaluate_strategy_qualification(
    request: StrategyQualificationRequest,
) -> StrategyQualificationResult:
    """Evaluate precomputed evidence without data access, backtests, or I/O."""
    if not isinstance(request, StrategyQualificationRequest):
        raise TypeError(
            "request must be a StrategyQualificationRequest, "
            f"got {type(request).__name__}"
        )

    policy = request.policy
    metrics = request.metrics
    findings: list[QualificationFinding] = []

    if not is_supported_qualification_policy(policy):
        findings.append(
            _finding(
                "unsupported_policy",
                "blocking",
                "Qualification policy is not an exact registered policy.",
                observed_value=f"{policy.policy_id}@{policy.policy_version}",
            )
        )
    else:
        if metrics.evidence_scope != "out_of_sample":
            findings.append(
                _finding(
                    "data_leakage_risk",
                    "blocking",
                    "Promotion requires out-of-sample evidence.",
                    metric_name="evidence_scope",
                    observed_value=metrics.evidence_scope,
                    threshold_value="out_of_sample",
                )
            )
        if not metrics.data_leakage_free:
            findings.append(
                _finding(
                    "data_leakage_risk",
                    "blocking",
                    "Evidence does not satisfy the declared data-separation contract.",
                    metric_name="data_leakage_free",
                    observed_value=False,
                    threshold_value=True,
                )
            )
        if metrics.partial_failure_count > 0:
            findings.append(
                _finding(
                    "partial_data_failure",
                    "blocking",
                    "Partial evaluation failures must be resolved before promotion.",
                    metric_name="partial_failure_count",
                    observed_value=metrics.partial_failure_count,
                    threshold_value=0,
                )
            )
        if metrics.oos_observations < policy.minimum_oos_observations:
            findings.append(
                _finding(
                    "insufficient_oos_observations",
                    "warning",
                    "Out-of-sample observations are below the policy minimum.",
                    metric_name="oos_observations",
                    observed_value=metrics.oos_observations,
                    threshold_value=policy.minimum_oos_observations,
                )
            )
        if metrics.completed_trades < policy.minimum_completed_trades:
            findings.append(
                _finding(
                    "insufficient_trades",
                    "warning",
                    "Completed trades are below the policy minimum.",
                    metric_name="completed_trades",
                    observed_value=metrics.completed_trades,
                    threshold_value=policy.minimum_completed_trades,
                )
            )
        if metrics.evaluated_symbols < policy.minimum_evaluated_symbols:
            findings.append(
                _finding(
                    "insufficient_symbols",
                    "warning",
                    "Evaluated symbols are below the policy minimum.",
                    metric_name="evaluated_symbols",
                    observed_value=metrics.evaluated_symbols,
                    threshold_value=policy.minimum_evaluated_symbols,
                )
            )
        if metrics.valid_windows < policy.minimum_valid_windows:
            findings.append(
                _finding(
                    "insufficient_valid_windows",
                    "warning",
                    "Valid out-of-sample windows are below the policy minimum.",
                    metric_name="valid_windows",
                    observed_value=metrics.valid_windows,
                    threshold_value=policy.minimum_valid_windows,
                )
            )

        if policy.require_benchmark and not metrics.benchmark_available:
            findings.append(
                _finding(
                    "benchmark_missing",
                    "blocking",
                    "The selected policy requires benchmark evidence.",
                    metric_name="benchmark_available",
                    observed_value=False,
                    threshold_value=True,
                )
            )
        elif metrics.benchmark_available:
            assert metrics.benchmark_return_pct is not None
            excess_return = metrics.total_return_pct - metrics.benchmark_return_pct
            if excess_return < policy.minimum_excess_return_pct:
                findings.append(
                    _finding(
                        "underperforms_benchmark",
                        "warning",
                        "Out-of-sample return does not meet the benchmark-relative threshold.",
                        metric_name="excess_return_pct",
                        observed_value=excess_return,
                        threshold_value=policy.minimum_excess_return_pct,
                    )
                )

        if policy.require_cost_stress and not metrics.cost_stress_pass:
            findings.append(
                _finding(
                    "cost_stress_failure",
                    "warning",
                    "Strategy evidence fails the required higher-cost stress scenario.",
                    metric_name="cost_stress_pass",
                    observed_value=False,
                    threshold_value=True,
                )
            )
        if metrics.max_drawdown_pct > policy.maximum_drawdown_pct:
            findings.append(
                _finding(
                    "max_drawdown_exceeded",
                    "warning",
                    "Maximum drawdown exceeds the policy limit.",
                    metric_name="max_drawdown_pct",
                    observed_value=metrics.max_drawdown_pct,
                    threshold_value=policy.maximum_drawdown_pct,
                )
            )
        if metrics.positive_window_ratio < policy.minimum_positive_window_ratio:
            findings.append(
                _finding(
                    "window_instability",
                    "warning",
                    "Positive-window ratio is below the policy minimum.",
                    metric_name="positive_window_ratio",
                    observed_value=metrics.positive_window_ratio,
                    threshold_value=policy.minimum_positive_window_ratio,
                )
            )
        if (
            metrics.symbol_concentration_pct
            > policy.maximum_symbol_concentration_pct
        ):
            findings.append(
                _finding(
                    "symbol_concentration",
                    "warning",
                    "Performance concentration exceeds the policy limit.",
                    metric_name="symbol_concentration_pct",
                    observed_value=metrics.symbol_concentration_pct,
                    threshold_value=policy.maximum_symbol_concentration_pct,
                )
            )
        if policy.require_parameter_stability and not metrics.parameter_stable:
            findings.append(
                _finding(
                    "parameter_instability",
                    "warning",
                    "Parameter-neighborhood stability does not meet policy requirements.",
                    metric_name="parameter_stable",
                    observed_value=False,
                    threshold_value=True,
                )
            )

    normalized = normalize_findings(findings)
    if any(finding.severity == "blocking" for finding in normalized):
        state = "REJECTED"
    elif any(finding.severity == "warning" for finding in normalized):
        state = "RESEARCH_CANDIDATE"
    else:
        state = "PAPER_READY"

    decision = PromotionDecision(
        state=state,
        reason_codes=finding_reason_codes(normalized),
    )
    return StrategyQualificationResult(
        schema_version=STRATEGY_QUALIFICATION_SCHEMA_VERSION,
        artifact_type=STRATEGY_QUALIFICATION_ARTIFACT_TYPE,
        request=request,
        findings=normalized,
        decision=decision,
    )


__all__ = ["evaluate_strategy_qualification"]
