"""Immutable research-only forward eligibility models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import math
from numbers import Real
import re
from uuid import UUID


class ForwardEligibilityModelError(ValueError):
    """Raised when forward eligibility data violates schema 1.0."""


class ForwardEligibilitySeverity(StrEnum):
    INFO = "INFO"
    PAUSE = "PAUSE"
    REVOKE = "REVOKE"


class ForwardEligibilityState(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    REVOKED = "REVOKED"


FORWARD_ELIGIBILITY_POLICY_ID = "taiwan_equity_daily_forward_v1"
FORWARD_ELIGIBILITY_POLICY_VERSION = "1.0"
SUPPORTED_FORWARD_ELIGIBILITY_FINDING_CODES = (
    "forward_drawdown_pause",
    "forward_drawdown_revoke",
    "invalid_open_rate_pause",
    "invalid_open_rate_revoke",
    "portfolio_validation_failure_pause",
    "portfolio_validation_failure_revoke",
)

_FINDING_DETAILS = {
    "forward_drawdown_pause": (
        ForwardEligibilitySeverity.PAUSE,
        "max_drawdown_pct",
        15.0,
        25.0,
    ),
    "forward_drawdown_revoke": (
        ForwardEligibilitySeverity.REVOKE,
        "max_drawdown_pct",
        25.0,
        None,
    ),
    "invalid_open_rate_pause": (
        ForwardEligibilitySeverity.PAUSE,
        "invalid_open_rate",
        0.20,
        0.50,
    ),
    "invalid_open_rate_revoke": (
        ForwardEligibilitySeverity.REVOKE,
        "invalid_open_rate",
        0.50,
        None,
    ),
    "portfolio_validation_failure_pause": (
        ForwardEligibilitySeverity.PAUSE,
        "failed_portfolio_validation_count",
        1.0,
        3.0,
    ),
    "portfolio_validation_failure_revoke": (
        ForwardEligibilitySeverity.REVOKE,
        "failed_portfolio_validation_count",
        3.0,
        None,
    ),
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _clean_string(name: str, value: object) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ForwardEligibilityModelError(
            f"{name} must be an exact clean non-empty string"
        )
    return value


def _uuid(name: str, value: object) -> str:
    clean = _clean_string(name, value)
    try:
        parsed = UUID(clean)
    except ValueError as exc:
        raise ForwardEligibilityModelError(
            f"{name} must be a canonical lowercase UUID v4"
        ) from exc
    if parsed.version != 4 or str(parsed) != clean:
        raise ForwardEligibilityModelError(
            f"{name} must be a canonical lowercase UUID v4"
        )
    return clean


def _sha(name: str, value: object) -> str:
    clean = _clean_string(name, value)
    if _SHA256.fullmatch(clean) is None:
        raise ForwardEligibilityModelError(f"{name} must be a lowercase SHA-256")
    return clean


def _timestamp(name: str, value: object) -> str:
    clean = _clean_string(name, value)
    try:
        parsed = datetime.strptime(clean, _TIMESTAMP_FORMAT)
    except ValueError as exc:
        raise ForwardEligibilityModelError(
            f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
        ) from exc
    if parsed.strftime(_TIMESTAMP_FORMAT) != clean:
        raise ForwardEligibilityModelError(
            f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
        )
    return clean


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ForwardEligibilityModelError(f"{name} must be finite numeric data")
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ForwardEligibilityModelError(
            f"{name} must be finite numeric data"
        ) from exc
    if not math.isfinite(number) or number < 0.0:
        raise ForwardEligibilityModelError(
            f"{name} must be finite and non-negative"
        )
    return number


def _positive_int(name: str, value: object) -> int:
    if type(value) is not int or value < 1:
        raise ForwardEligibilityModelError(f"{name} must be a positive exact int")
    return value


@dataclass(frozen=True, slots=True)
class ForwardEligibilityPolicy:
    policy_id: str
    policy_version: str
    pause_max_drawdown_pct: float
    revoke_max_drawdown_pct: float
    minimum_terminal_attempts_for_invalid_open_rate: int
    pause_invalid_open_rate: float
    revoke_invalid_open_rate: float
    pause_portfolio_validation_failure_count: int
    revoke_portfolio_validation_failure_count: int

    def __post_init__(self) -> None:
        _clean_string("policy_id", self.policy_id)
        _clean_string("policy_version", self.policy_version)
        pause_drawdown = _finite_number(
            "pause_max_drawdown_pct", self.pause_max_drawdown_pct
        )
        revoke_drawdown = _finite_number(
            "revoke_max_drawdown_pct", self.revoke_max_drawdown_pct
        )
        pause_invalid = _finite_number(
            "pause_invalid_open_rate", self.pause_invalid_open_rate
        )
        revoke_invalid = _finite_number(
            "revoke_invalid_open_rate", self.revoke_invalid_open_rate
        )
        if not 0.0 <= pause_drawdown < revoke_drawdown <= 100.0:
            raise ForwardEligibilityModelError(
                "drawdown thresholds must satisfy 0 <= pause < revoke <= 100"
            )
        if not 0.0 <= pause_invalid < revoke_invalid <= 1.0:
            raise ForwardEligibilityModelError(
                "invalid-open thresholds must satisfy 0 <= pause < revoke <= 1"
            )
        _positive_int(
            "minimum_terminal_attempts_for_invalid_open_rate",
            self.minimum_terminal_attempts_for_invalid_open_rate,
        )
        pause_failures = _positive_int(
            "pause_portfolio_validation_failure_count",
            self.pause_portfolio_validation_failure_count,
        )
        revoke_failures = _positive_int(
            "revoke_portfolio_validation_failure_count",
            self.revoke_portfolio_validation_failure_count,
        )
        if pause_failures >= revoke_failures:
            raise ForwardEligibilityModelError(
                "portfolio validation failure thresholds must satisfy pause < revoke"
            )
        object.__setattr__(self, "pause_max_drawdown_pct", pause_drawdown)
        object.__setattr__(self, "revoke_max_drawdown_pct", revoke_drawdown)
        object.__setattr__(self, "pause_invalid_open_rate", pause_invalid)
        object.__setattr__(self, "revoke_invalid_open_rate", revoke_invalid)


@dataclass(frozen=True, slots=True)
class ForwardEligibilityFinding:
    code: str
    severity: ForwardEligibilitySeverity
    metric_name: str
    observed_value: float
    threshold_value: float
    message: str

    def __post_init__(self) -> None:
        if self.code not in SUPPORTED_FORWARD_ELIGIBILITY_FINDING_CODES:
            raise ForwardEligibilityModelError("finding code is not supported")
        if type(self.severity) is not ForwardEligibilitySeverity:
            raise ForwardEligibilityModelError(
                "severity must be ForwardEligibilitySeverity"
            )
        expected_severity, metric_name, threshold, upper = _FINDING_DETAILS[
            self.code
        ]
        if self.severity is not expected_severity or self.metric_name != metric_name:
            raise ForwardEligibilityModelError(
                "finding code, severity, and metric_name do not agree"
            )
        observed = _finite_number("observed_value", self.observed_value)
        actual_threshold = _finite_number("threshold_value", self.threshold_value)
        if actual_threshold != threshold or observed < threshold:
            raise ForwardEligibilityModelError(
                "finding values do not match the registered threshold"
            )
        if upper is not None and observed >= upper:
            raise ForwardEligibilityModelError(
                "pause finding cannot contain a revoke-threshold observation"
            )
        _clean_string("message", self.message)
        object.__setattr__(self, "observed_value", observed)
        object.__setattr__(self, "threshold_value", actual_threshold)


@dataclass(frozen=True, slots=True)
class ForwardEligibilityEvidence:
    schema_version: str
    artifact_type: str
    eligibility_id: str
    created_at: str
    activation_id: str
    activation_sha256: str
    qualification_evaluation_id: str
    qualification_sha256: str
    ledger_id: str
    ledger_sha256: str
    metrics_id: str
    metrics_sha256: str
    strategy_id: str
    policy_id: str
    policy_version: str
    state: ForwardEligibilityState
    findings: tuple[ForwardEligibilityFinding, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise ForwardEligibilityModelError("schema_version must be '1.0'")
        if self.artifact_type != "forward_eligibility_evidence":
            raise ForwardEligibilityModelError("artifact_type is not supported")
        _uuid("eligibility_id", self.eligibility_id)
        _timestamp("created_at", self.created_at)
        for name in (
            "activation_id",
            "qualification_evaluation_id",
            "ledger_id",
            "metrics_id",
        ):
            _uuid(name, getattr(self, name))
        for name in (
            "activation_sha256",
            "qualification_sha256",
            "ledger_sha256",
            "metrics_sha256",
        ):
            _sha(name, getattr(self, name))
        _clean_string("strategy_id", self.strategy_id)
        if (
            self.policy_id != FORWARD_ELIGIBILITY_POLICY_ID
            or self.policy_version != FORWARD_ELIGIBILITY_POLICY_VERSION
        ):
            raise ForwardEligibilityModelError("eligibility policy is not supported")
        if type(self.state) is not ForwardEligibilityState:
            raise ForwardEligibilityModelError("state must be ForwardEligibilityState")
        if type(self.findings) is not tuple or any(
            type(item) is not ForwardEligibilityFinding for item in self.findings
        ):
            raise ForwardEligibilityModelError(
                "findings must be an exact tuple of ForwardEligibilityFinding"
            )
        codes = tuple(item.code for item in self.findings)
        expected_codes = tuple(
            sorted(
                codes,
                key=SUPPORTED_FORWARD_ELIGIBILITY_FINDING_CODES.index,
            )
        )
        if codes != expected_codes or len(set(codes)) != len(codes):
            raise ForwardEligibilityModelError(
                "findings must be unique and canonically ordered"
            )
        metrics = tuple(item.metric_name for item in self.findings)
        if len(set(metrics)) != len(metrics):
            raise ForwardEligibilityModelError(
                "findings must contain only one severity per metric"
            )
        expected_state = (
            ForwardEligibilityState.REVOKED
            if any(
                item.severity is ForwardEligibilitySeverity.REVOKE
                for item in self.findings
            )
            else ForwardEligibilityState.PAUSED
            if any(
                item.severity is ForwardEligibilitySeverity.PAUSE
                for item in self.findings
            )
            else ForwardEligibilityState.ACTIVE
        )
        if self.state is not expected_state:
            raise ForwardEligibilityModelError(
                "state does not match the highest finding severity"
            )


__all__ = [
    "FORWARD_ELIGIBILITY_POLICY_ID",
    "FORWARD_ELIGIBILITY_POLICY_VERSION",
    "SUPPORTED_FORWARD_ELIGIBILITY_FINDING_CODES",
    "ForwardEligibilityEvidence",
    "ForwardEligibilityFinding",
    "ForwardEligibilityModelError",
    "ForwardEligibilityPolicy",
    "ForwardEligibilitySeverity",
    "ForwardEligibilityState",
]
