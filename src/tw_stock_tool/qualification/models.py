"""Immutable models for research-only strategy qualification."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
import math
from types import MappingProxyType
from typing import Any, Literal, TypeAlias
from uuid import UUID

STRATEGY_QUALIFICATION_ARTIFACT_TYPE = "strategy_qualification"
STRATEGY_QUALIFICATION_SCHEMA_VERSION = "1.0"


class QualificationModelError(ValueError):
    """Raised when strategy-qualification model data violates its contract."""


FindingSeverity: TypeAlias = Literal["info", "warning", "blocking"]
PromotionState: TypeAlias = Literal["REJECTED", "RESEARCH_CANDIDATE", "PAPER_READY"]
EvidenceScope: TypeAlias = Literal["in_sample", "out_of_sample"]
JsonScalar: TypeAlias = str | int | float | bool | None
FrozenJsonValue: TypeAlias = JsonScalar | tuple["FrozenJsonValue", ...] | Mapping[str, "FrozenJsonValue"]

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

DEFAULT_FINDING_SEVERITIES = MappingProxyType(
    {
        "data_leakage_risk": "blocking",
        "insufficient_oos_observations": "blocking",
        "insufficient_trades": "blocking",
        "insufficient_symbols": "blocking",
        "insufficient_valid_windows": "blocking",
        "benchmark_missing": "blocking",
        "underperforms_benchmark": "warning",
        "cost_stress_failure": "blocking",
        "max_drawdown_exceeded": "blocking",
        "window_instability": "blocking",
        "symbol_concentration": "blocking",
        "parameter_instability": "blocking",
        "non_finite_metric": "blocking",
        "partial_data_failure": "blocking",
        "unsupported_policy": "blocking",
    }
)


def _clean_string(name: str, value: Any) -> str:
    if type(value) is not str:
        raise QualificationModelError(f"{name} must be exact str, got {type(value).__name__}")
    if not value or value.strip() != value:
        raise QualificationModelError(f"{name} must be a clean non-blank string")
    return value


def _optional_clean_string(name: str, value: Any) -> str | None:
    if value is None:
        return None
    return _clean_string(name, value)


def _exact_bool(name: str, value: Any) -> bool:
    if type(value) is not bool:
        raise QualificationModelError(f"{name} must be exact bool, got {type(value).__name__}")
    return value


def _nonnegative_int(name: str, value: Any) -> int:
    if type(value) is not int:
        raise QualificationModelError(f"{name} must be exact int, got {type(value).__name__}")
    if value < 0:
        raise QualificationModelError(f"{name} must be non-negative, got {value}")
    return value


def _positive_int(name: str, value: Any) -> int:
    result = _nonnegative_int(name, value)
    if result == 0:
        raise QualificationModelError(f"{name} must be greater than 0")
    return result


def _finite_float(name: str, value: Any) -> float:
    if type(value) not in (int, float):
        raise QualificationModelError(f"{name} must be an exact finite number, got {type(value).__name__}")
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise QualificationModelError(
            f"{name} must be a finite number; conversion failed"
        ) from exc
    if not math.isfinite(result):
        raise QualificationModelError(f"{name} must be finite, got {value!r}")
    return result


def _optional_finite_float(name: str, value: Any) -> float | None:
    if value is None:
        return None
    return _finite_float(name, value)


def _percentage(name: str, value: Any, *, maximum: float = 100.0) -> float:
    result = _finite_float(name, value)
    if result < 0.0 or result > maximum:
        raise QualificationModelError(f"{name} must be between 0 and {maximum}, got {result}")
    return result


def _ratio(name: str, value: Any) -> float:
    result = _finite_float(name, value)
    if result < 0.0 or result > 1.0:
        raise QualificationModelError(f"{name} must be between 0 and 1, got {result}")
    return result


def _exact_tuple(name: str, value: Any) -> tuple[Any, ...]:
    if type(value) is not tuple:
        raise QualificationModelError(f"{name} must be exact tuple, got {type(value).__name__}")
    return value


def _validate_uuid_v4(name: str, value: Any) -> str:
    clean = _clean_string(name, value)
    try:
        parsed = UUID(clean)
    except ValueError as exc:
        raise QualificationModelError(f"{name} must be a canonical UUID v4") from exc
    if parsed.version != 4 or str(parsed) != clean:
        raise QualificationModelError(f"{name} must be a canonical lowercase UUID v4")
    return clean


def _validate_utc_timestamp(name: str, value: Any) -> str:
    clean = _clean_string(name, value)
    try:
        parsed = datetime.strptime(clean, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise QualificationModelError(
            f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != clean:
        raise QualificationModelError(
            f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
        )
    return clean


def _freeze_json(name: str, value: Any) -> FrozenJsonValue:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise QualificationModelError(f"{name} contains a non-finite float")
        return value
    if type(value) in (list, tuple):
        return tuple(_freeze_json(f"{name}[{index}]", item) for index, item in enumerate(value))
    if isinstance(value, Mapping):
        frozen: dict[str, FrozenJsonValue] = {}
        for key, item in value.items():
            clean_key = _clean_string(f"{name} key", key)
            frozen[clean_key] = _freeze_json(f"{name}.{clean_key}", item)
        return MappingProxyType(frozen)
    raise QualificationModelError(f"{name} contains unsupported type {type(value).__name__}")


def _freeze_mapping(name: str, value: Any) -> Mapping[str, FrozenJsonValue]:
    if not isinstance(value, Mapping):
        raise QualificationModelError(f"{name} must be a Mapping, got {type(value).__name__}")
    frozen = _freeze_json(name, value)
    assert isinstance(frozen, Mapping)
    return frozen


def _finding_scalar(name: str, value: Any) -> JsonScalar:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise QualificationModelError(f"{name} must be finite")
        return value
    raise QualificationModelError(f"{name} must be a JSON scalar")


@dataclass(frozen=True, slots=True)
class QualificationPolicy:
    policy_id: str
    policy_version: str
    minimum_oos_observations: int
    minimum_completed_trades: int
    minimum_evaluated_symbols: int
    minimum_valid_windows: int
    require_benchmark: bool
    minimum_excess_return_pct: float
    require_cost_stress: bool
    maximum_drawdown_pct: float
    minimum_positive_window_ratio: float
    maximum_symbol_concentration_pct: float
    require_parameter_stability: bool
    finding_severities: Mapping[str, FindingSeverity] = field(
        default_factory=lambda: DEFAULT_FINDING_SEVERITIES
    )

    def __post_init__(self) -> None:
        _clean_string("policy_id", self.policy_id)
        _clean_string("policy_version", self.policy_version)
        _positive_int("minimum_oos_observations", self.minimum_oos_observations)
        _positive_int("minimum_completed_trades", self.minimum_completed_trades)
        _positive_int("minimum_evaluated_symbols", self.minimum_evaluated_symbols)
        _positive_int("minimum_valid_windows", self.minimum_valid_windows)
        _exact_bool("require_benchmark", self.require_benchmark)
        object.__setattr__(
            self,
            "minimum_excess_return_pct",
            _finite_float("minimum_excess_return_pct", self.minimum_excess_return_pct),
        )
        _exact_bool("require_cost_stress", self.require_cost_stress)
        object.__setattr__(
            self,
            "maximum_drawdown_pct",
            _percentage("maximum_drawdown_pct", self.maximum_drawdown_pct),
        )
        object.__setattr__(
            self,
            "minimum_positive_window_ratio",
            _ratio("minimum_positive_window_ratio", self.minimum_positive_window_ratio),
        )
        object.__setattr__(
            self,
            "maximum_symbol_concentration_pct",
            _percentage(
                "maximum_symbol_concentration_pct",
                self.maximum_symbol_concentration_pct,
            ),
        )
        _exact_bool("require_parameter_stability", self.require_parameter_stability)
        if not isinstance(self.finding_severities, Mapping):
            raise QualificationModelError("finding_severities must be a Mapping")
        if set(self.finding_severities) != set(SUPPORTED_FINDING_CODES):
            raise QualificationModelError(
                "finding_severities must contain exactly the supported finding codes"
            )
        severities: dict[str, str] = {}
        for code in SUPPORTED_FINDING_CODES:
            severity = _clean_string(
                f"finding_severities[{code!r}]", self.finding_severities[code]
            )
            if severity not in ("info", "warning", "blocking"):
                raise QualificationModelError(
                    f"finding_severities[{code!r}] has unsupported severity {severity!r}"
                )
            severities[code] = severity
        object.__setattr__(self, "finding_severities", MappingProxyType(severities))


@dataclass(frozen=True, slots=True)
class StrategyDescriptor:
    strategy_id: str
    parameters: Mapping[str, FrozenJsonValue]

    def __post_init__(self) -> None:
        _clean_string("strategy_id", self.strategy_id)
        object.__setattr__(self, "parameters", _freeze_mapping("parameters", self.parameters))


@dataclass(frozen=True, slots=True)
class QualificationMetricSet:
    evidence_scope: EvidenceScope
    data_leakage_free: bool
    oos_observations: int
    completed_trades: int
    evaluated_symbols: int
    valid_windows: int
    benchmark_available: bool
    total_return_pct: float
    benchmark_return_pct: float | None
    cost_stress_pass: bool
    stressed_return_pct: float | None
    max_drawdown_pct: float
    positive_window_ratio: float
    symbol_concentration_pct: float
    parameter_stable: bool
    partial_failure_count: int

    def __post_init__(self) -> None:
        scope = _clean_string("evidence_scope", self.evidence_scope)
        if scope not in ("in_sample", "out_of_sample"):
            raise QualificationModelError(
                "evidence_scope must be 'in_sample' or 'out_of_sample'"
            )
        _exact_bool("data_leakage_free", self.data_leakage_free)
        _nonnegative_int("oos_observations", self.oos_observations)
        _nonnegative_int("completed_trades", self.completed_trades)
        _nonnegative_int("evaluated_symbols", self.evaluated_symbols)
        _nonnegative_int("valid_windows", self.valid_windows)
        _exact_bool("benchmark_available", self.benchmark_available)
        object.__setattr__(
            self,
            "total_return_pct",
            _finite_float("total_return_pct", self.total_return_pct),
        )
        benchmark = _optional_finite_float(
            "benchmark_return_pct", self.benchmark_return_pct
        )
        if self.benchmark_available and benchmark is None:
            raise QualificationModelError(
                "benchmark_return_pct is required when benchmark_available is True"
            )
        if not self.benchmark_available and benchmark is not None:
            raise QualificationModelError(
                "benchmark_return_pct must be None when benchmark_available is False"
            )
        object.__setattr__(self, "benchmark_return_pct", benchmark)
        _exact_bool("cost_stress_pass", self.cost_stress_pass)
        object.__setattr__(
            self,
            "stressed_return_pct",
            _optional_finite_float("stressed_return_pct", self.stressed_return_pct),
        )
        object.__setattr__(
            self,
            "max_drawdown_pct",
            _percentage("max_drawdown_pct", self.max_drawdown_pct),
        )
        object.__setattr__(
            self,
            "positive_window_ratio",
            _ratio("positive_window_ratio", self.positive_window_ratio),
        )
        object.__setattr__(
            self,
            "symbol_concentration_pct",
            _percentage("symbol_concentration_pct", self.symbol_concentration_pct),
        )
        _exact_bool("parameter_stable", self.parameter_stable)
        _nonnegative_int("partial_failure_count", self.partial_failure_count)


@dataclass(frozen=True, slots=True)
class QualificationFinding:
    code: str
    severity: FindingSeverity
    scope: str
    message: str
    metric_name: str | None = None
    observed_value: JsonScalar = None
    threshold_value: JsonScalar = None
    symbol: str | None = None
    window: int | None = None

    def __post_init__(self) -> None:
        _clean_string("code", self.code)
        if self.code not in SUPPORTED_FINDING_CODES:
            raise QualificationModelError(
                f"unsupported qualification finding code: {self.code}"
            )
        severity = _clean_string("severity", self.severity)
        if severity not in ("info", "warning", "blocking"):
            raise QualificationModelError(
                "severity must be 'info', 'warning', or 'blocking'"
            )
        _clean_string("scope", self.scope)
        _clean_string("message", self.message)
        _optional_clean_string("metric_name", self.metric_name)
        _finding_scalar("observed_value", self.observed_value)
        _finding_scalar("threshold_value", self.threshold_value)
        _optional_clean_string("symbol", self.symbol)
        if self.window is not None:
            _nonnegative_int("window", self.window)


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    state: PromotionState
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        state = _clean_string("state", self.state)
        if state not in ("REJECTED", "RESEARCH_CANDIDATE", "PAPER_READY"):
            raise QualificationModelError(
                "state must be REJECTED, RESEARCH_CANDIDATE, or PAPER_READY"
            )
        _exact_tuple("reason_codes", self.reason_codes)
        seen: set[str] = set()
        for index, code in enumerate(self.reason_codes):
            clean = _clean_string(f"reason_codes[{index}]", code)
            if clean in seen:
                raise QualificationModelError(f"duplicate reason code: {clean}")
            seen.add(clean)


@dataclass(frozen=True, slots=True)
class StrategyQualificationRequest:
    evaluation_id: str
    created_at: str
    strategy: StrategyDescriptor
    metrics: QualificationMetricSet
    policy: QualificationPolicy

    def __post_init__(self) -> None:
        _validate_uuid_v4("evaluation_id", self.evaluation_id)
        _validate_utc_timestamp("created_at", self.created_at)
        if not isinstance(self.strategy, StrategyDescriptor):
            raise QualificationModelError("strategy must be StrategyDescriptor")
        if not isinstance(self.metrics, QualificationMetricSet):
            raise QualificationModelError("metrics must be QualificationMetricSet")
        if not isinstance(self.policy, QualificationPolicy):
            raise QualificationModelError("policy must be QualificationPolicy")


@dataclass(frozen=True, slots=True)
class StrategyQualificationResult:
    schema_version: str
    artifact_type: str
    request: StrategyQualificationRequest
    findings: tuple[QualificationFinding, ...]
    decision: PromotionDecision

    def __post_init__(self) -> None:
        if self.schema_version != STRATEGY_QUALIFICATION_SCHEMA_VERSION:
            raise QualificationModelError(
                f"schema_version must equal {STRATEGY_QUALIFICATION_SCHEMA_VERSION!r}"
            )
        if self.artifact_type != STRATEGY_QUALIFICATION_ARTIFACT_TYPE:
            raise QualificationModelError(
                f"artifact_type must equal {STRATEGY_QUALIFICATION_ARTIFACT_TYPE!r}"
            )
        if not isinstance(self.request, StrategyQualificationRequest):
            raise QualificationModelError("request must be StrategyQualificationRequest")
        _exact_tuple("findings", self.findings)
        for index, finding in enumerate(self.findings):
            if not isinstance(finding, QualificationFinding):
                raise QualificationModelError(
                    f"findings[{index}] must be QualificationFinding"
                )
        if not isinstance(self.decision, PromotionDecision):
            raise QualificationModelError("decision must be PromotionDecision")

        from tw_stock_tool.qualification.derivation import derive_qualification_outcome
        from tw_stock_tool.qualification.findings import normalize_findings

        normalized = normalize_findings(self.findings, self.request.policy)
        if self.findings != normalized:
            raise QualificationModelError(
                "findings must be canonical, supported, unique, and deterministically ordered"
            )
        canonical_findings, canonical_decision = derive_qualification_outcome(self.request)
        if self.findings != canonical_findings:
            raise QualificationModelError(
                "findings must equal canonical evaluator findings"
            )
        if self.decision != canonical_decision:
            raise QualificationModelError(
                "decision must equal canonical evaluator decision"
            )

        unique_codes: list[str] = []
        for finding in self.findings:
            if finding.code not in unique_codes:
                unique_codes.append(finding.code)
        if tuple(unique_codes) != self.decision.reason_codes:
            raise QualificationModelError(
                "decision.reason_codes must equal unique finding codes in order"
            )

        has_blocking = any(finding.severity == "blocking" for finding in self.findings)
        has_warning = any(finding.severity == "warning" for finding in self.findings)
        if self.decision.state == "REJECTED" and not has_blocking:
            raise QualificationModelError("REJECTED requires at least one blocking finding")
        if self.decision.state == "RESEARCH_CANDIDATE":
            if has_blocking or not has_warning:
                raise QualificationModelError(
                    "RESEARCH_CANDIDATE requires warning findings and no blocking findings"
                )
        if self.decision.state == "PAPER_READY" and (has_blocking or has_warning):
            raise QualificationModelError(
                "PAPER_READY cannot contain warning or blocking findings"
            )


__all__ = [
    "STRATEGY_QUALIFICATION_ARTIFACT_TYPE",
    "STRATEGY_QUALIFICATION_SCHEMA_VERSION",
    "DEFAULT_FINDING_SEVERITIES",
    "EvidenceScope",
    "FindingSeverity",
    "PromotionState",
    "QualificationFinding",
    "QualificationMetricSet",
    "QualificationModelError",
    "QualificationPolicy",
    "SUPPORTED_FINDING_CODES",
    "PromotionDecision",
    "StrategyDescriptor",
    "StrategyQualificationRequest",
    "StrategyQualificationResult",
]
