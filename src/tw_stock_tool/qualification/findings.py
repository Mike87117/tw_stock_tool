"""Deterministic finding registry and ordering for strategy qualification."""

from __future__ import annotations

from collections.abc import Iterable

from tw_stock_tool.qualification.models import QualificationFinding


class QualificationFindingError(ValueError):
    """Raised when a finding is not part of the first-version registry."""


SUPPORTED_FINDING_CODES = (
    "data_leakage_risk",
    "insufficient_oos_observations",
    "insufficient_trades",
    "insufficient_symbols",
    "insufficient_valid_windows",
    "benchmark_missing",
    "underperforms_benchmark",
    "cost_stress_failure",
    "max_drawdown_exceeded",
    "window_instability",
    "symbol_concentration",
    "parameter_instability",
    "non_finite_metric",
    "partial_data_failure",
    "unsupported_policy",
)

_SEVERITY_ORDER = {"blocking": 0, "warning": 1, "info": 2}


def _finding_identity(finding: QualificationFinding) -> tuple[object, ...]:
    return (
        finding.code,
        finding.severity,
        finding.scope,
        finding.message,
        finding.metric_name,
        finding.observed_value,
        finding.threshold_value,
        finding.symbol,
        finding.window,
    )


def _finding_sort_key(finding: QualificationFinding) -> tuple[object, ...]:
    return (
        _SEVERITY_ORDER[finding.severity],
        finding.code,
        finding.scope,
        finding.metric_name or "",
        finding.symbol or "",
        -1 if finding.window is None else finding.window,
        finding.message,
        repr(finding.observed_value),
        repr(finding.threshold_value),
    )


def normalize_findings(
    findings: Iterable[QualificationFinding],
) -> tuple[QualificationFinding, ...]:
    """Validate, deduplicate, and sort findings deterministically."""
    unique: dict[tuple[object, ...], QualificationFinding] = {}
    for finding in findings:
        if not isinstance(finding, QualificationFinding):
            raise QualificationFindingError(
                f"finding must be QualificationFinding, got {type(finding).__name__}"
            )
        if finding.code not in SUPPORTED_FINDING_CODES:
            raise QualificationFindingError(
                f"unsupported qualification finding code: {finding.code}"
            )
        unique.setdefault(_finding_identity(finding), finding)
    return tuple(sorted(unique.values(), key=_finding_sort_key))


def finding_reason_codes(
    findings: Iterable[QualificationFinding],
) -> tuple[str, ...]:
    """Return unique finding codes in normalized finding order."""
    codes: list[str] = []
    for finding in normalize_findings(findings):
        if finding.code not in codes:
            codes.append(finding.code)
    return tuple(codes)


__all__ = [
    "SUPPORTED_FINDING_CODES",
    "QualificationFindingError",
    "finding_reason_codes",
    "normalize_findings",
]
