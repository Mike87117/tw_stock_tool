"""Immutable execution-correlation evidence for trusted forward replays."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import math
import re
from numbers import Real
from typing import Literal
from uuid import UUID


class ForwardExecutionEvidenceModelError(ValueError):
    """Raised when execution evidence violates its frozen domain contract."""


class ForwardExecutionOutcome(StrEnum):
    NON_ACTION = "NON_ACTION"
    NO_CANDIDATE = "NO_CANDIDATE"
    REJECTED = "REJECTED"
    PENDING_NEXT_BAR_OPEN = "PENDING_NEXT_BAR_OPEN"
    FILLED = "FILLED"
    FILL_SKIPPED_INVALID_OPEN = "FILL_SKIPPED_INVALID_OPEN"
    FILL_FAILED_PORTFOLIO_VALIDATION = "FILL_FAILED_PORTFOLIO_VALIDATION"


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_OUTCOMES = frozenset(ForwardExecutionOutcome)


def _string(name: str, value: object) -> str:
    if type(value) is not str or not value.strip():
        raise ForwardExecutionEvidenceModelError(f"{name} must be a non-blank string")
    return value


def _uuid(name: str, value: object) -> str:
    value = _string(name, value)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ForwardExecutionEvidenceModelError(f"{name} must be a UUID v4") from exc
    if parsed.version != 4 or str(parsed) != value or value.lower() != value:
        raise ForwardExecutionEvidenceModelError(f"{name} must be a canonical lowercase UUID v4")
    return value


def _sha(name: str, value: object) -> str:
    value = _string(name, value)
    if _SHA256.fullmatch(value) is None:
        raise ForwardExecutionEvidenceModelError(f"{name} must be a lowercase SHA-256")
    return value


def _timestamp(name: str, value: object) -> str:
    value = _string(name, value)
    if _TIMESTAMP.fullmatch(value) is None:
        raise ForwardExecutionEvidenceModelError(
            f"{name} must match YYYY-MM-DDTHH:MM:SSZ"
        )
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ForwardExecutionEvidenceModelError(f"{name} must be a valid UTC timestamp") from exc
    return value


def _money(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ForwardExecutionEvidenceModelError(f"{name} must be finite numeric data")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ForwardExecutionEvidenceModelError(f"{name} must be finite numeric data") from exc
    if not math.isfinite(value) or value < 0.0:
        raise ForwardExecutionEvidenceModelError(f"{name} must be finite and non-negative")
    return value


def _optional_positive(name: str, value: object) -> float | None:
    if value is None:
        return None
    result = _money(name, value)
    if result <= 0.0:
        raise ForwardExecutionEvidenceModelError(f"{name} must be positive")
    return result


def _optional_quantity(name: str, value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value <= 0:
        raise ForwardExecutionEvidenceModelError(f"{name} must be a positive exact int")
    return value


def _audit_ids(value: object) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise ForwardExecutionEvidenceModelError("audit_record_ids must be an exact tuple")
    result = tuple(_string("audit_record_id", item) for item in value)
    if len(set(result)) != len(result):
        raise ForwardExecutionEvidenceModelError("audit_record_ids must be unique")
    return result


@dataclass(frozen=True, slots=True)
class ForwardExecutionDecisionEvidence:
    recommendation_id: str
    recommendation_sha256: str
    observed_at: str
    symbol: str
    action: Literal["ENTER", "WATCH", "HOLD", "EXIT", "NO_TRADE"]
    expected_side: Literal["BUY", "SELL"] | None
    outcome: ForwardExecutionOutcome
    order_id: str | None
    order_quantity: int | None
    pending_reference_price: float | None
    fill_time: str | None
    fill_price: float | None
    fee: float
    tax: float
    slippage: float
    risk_rejection_reasons: tuple[str, ...]
    audit_record_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _uuid("recommendation_id", self.recommendation_id)
        _sha("recommendation_sha256", self.recommendation_sha256)
        _timestamp("observed_at", self.observed_at)
        _string("symbol", self.symbol)
        if self.action not in ("ENTER", "WATCH", "HOLD", "EXIT", "NO_TRADE"):
            raise ForwardExecutionEvidenceModelError("action is not a frozen ledger action")
        if not isinstance(self.outcome, ForwardExecutionOutcome):
            raise ForwardExecutionEvidenceModelError("outcome must be ForwardExecutionOutcome")
        if self.expected_side not in (None, "BUY", "SELL"):
            raise ForwardExecutionEvidenceModelError("expected_side must be BUY, SELL, or None")
        expected = {"ENTER": "BUY", "EXIT": "SELL"}.get(self.action)
        if expected != self.expected_side:
            raise ForwardExecutionEvidenceModelError("expected_side does not match action")
        if self.action in {"WATCH", "HOLD", "NO_TRADE"} and self.outcome is not ForwardExecutionOutcome.NON_ACTION:
            raise ForwardExecutionEvidenceModelError("non-action decisions must be NON_ACTION")
        if self.action in {"ENTER", "EXIT"} and self.outcome is ForwardExecutionOutcome.NON_ACTION:
            raise ForwardExecutionEvidenceModelError("actionable decisions cannot be NON_ACTION")

        order_id = None if self.order_id is None else _string("order_id", self.order_id)
        order_quantity = _optional_quantity("order_quantity", self.order_quantity)
        pending = _optional_positive("pending_reference_price", self.pending_reference_price)
        fill_price = _optional_positive("fill_price", self.fill_price)
        fill_time = None if self.fill_time is None else _timestamp("fill_time", self.fill_time)
        risk_reasons = tuple(_string("risk_rejection_reason", item) for item in self.risk_rejection_reasons)
        if type(self.risk_rejection_reasons) is not tuple:
            raise ForwardExecutionEvidenceModelError("risk_rejection_reasons must be an exact tuple")
        audit_ids = _audit_ids(self.audit_record_ids)
        object.__setattr__(self, "order_id", order_id)
        object.__setattr__(self, "order_quantity", order_quantity)
        object.__setattr__(self, "pending_reference_price", pending)
        object.__setattr__(self, "fill_price", fill_price)
        object.__setattr__(self, "fill_time", fill_time)
        object.__setattr__(self, "risk_rejection_reasons", risk_reasons)
        object.__setattr__(self, "audit_record_ids", audit_ids)
        object.__setattr__(self, "fee", _money("fee", self.fee))
        object.__setattr__(self, "tax", _money("tax", self.tax))
        object.__setattr__(self, "slippage", _money("slippage", self.slippage))

        if self.outcome in {ForwardExecutionOutcome.NON_ACTION, ForwardExecutionOutcome.NO_CANDIDATE}:
            if any(value is not None for value in (order_id, order_quantity, pending, fill_time, fill_price)):
                raise ForwardExecutionEvidenceModelError("outcome cannot carry runtime references")
            if audit_ids or risk_reasons or self.fee or self.tax or self.slippage:
                raise ForwardExecutionEvidenceModelError("no-lifecycle outcome must have empty costs and audit")
        elif self.outcome is ForwardExecutionOutcome.REJECTED:
            if order_id is None or order_quantity is None or pending is not None or fill_time is not None or fill_price is not None or not audit_ids:
                raise ForwardExecutionEvidenceModelError("REJECTED fields are inconsistent")
        elif self.outcome is ForwardExecutionOutcome.PENDING_NEXT_BAR_OPEN:
            if order_id is None or order_quantity is None or pending is None or fill_time is not None or fill_price is not None or not audit_ids:
                raise ForwardExecutionEvidenceModelError("PENDING fields are inconsistent")
        elif self.outcome is ForwardExecutionOutcome.FILLED:
            if order_id is None or order_quantity is None or fill_time is None or fill_price is None or pending is not None or not audit_ids:
                raise ForwardExecutionEvidenceModelError("FILLED fields are inconsistent")
        elif self.outcome in {ForwardExecutionOutcome.FILL_SKIPPED_INVALID_OPEN, ForwardExecutionOutcome.FILL_FAILED_PORTFOLIO_VALIDATION}:
            if order_id is None or order_quantity is None or fill_time is None or fill_price is not None or pending is not None or not audit_ids:
                raise ForwardExecutionEvidenceModelError("terminal fill-failure fields are inconsistent")


@dataclass(frozen=True, slots=True)
class ForwardExecutionEvidence:
    schema_version: str
    artifact_type: str
    evidence_id: str
    created_at: str
    activation_id: str
    activation_sha256: str
    qualification_evaluation_id: str
    qualification_sha256: str
    ledger_id: str
    ledger_sha256: str
    portfolio_result_sha256: str
    strategy_id: str
    decisions: tuple[ForwardExecutionDecisionEvidence, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise ForwardExecutionEvidenceModelError("schema_version must be '1.0'")
        if self.artifact_type != "forward_execution_evidence":
            raise ForwardExecutionEvidenceModelError("artifact_type is not supported")
        _uuid("evidence_id", self.evidence_id)
        _timestamp("created_at", self.created_at)
        for name in ("activation_id", "qualification_evaluation_id", "ledger_id"):
            _uuid(name, getattr(self, name))
        for name in ("activation_sha256", "qualification_sha256", "ledger_sha256", "portfolio_result_sha256"):
            _sha(name, getattr(self, name))
        _string("strategy_id", self.strategy_id)
        if type(self.decisions) is not tuple or any(type(item) is not ForwardExecutionDecisionEvidence for item in self.decisions):
            raise ForwardExecutionEvidenceModelError("decisions must be an exact tuple of decision evidence")
        keys = tuple((item.observed_at, item.symbol) for item in self.decisions)
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise ForwardExecutionEvidenceModelError("decisions must preserve canonical ledger order")
        ids = tuple(item.recommendation_id for item in self.decisions)
        if len(set(ids)) != len(ids):
            raise ForwardExecutionEvidenceModelError("decision recommendation IDs must be unique")


__all__ = [
    "ForwardExecutionDecisionEvidence",
    "ForwardExecutionEvidence",
    "ForwardExecutionEvidenceModelError",
    "ForwardExecutionOutcome",
]
