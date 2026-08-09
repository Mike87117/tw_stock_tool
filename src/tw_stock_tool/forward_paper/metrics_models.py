"""Immutable factual metrics derived from trusted forward-paper evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from numbers import Real
import re
from uuid import UUID


class ForwardMetricsEvidenceModelError(ValueError):
    """Raised when forward metrics evidence violates schema 1.0."""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _clean_string(name: str, value: object) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ForwardMetricsEvidenceModelError(
            f"{name} must be an exact clean non-empty string"
        )
    return value


def _uuid(name: str, value: object) -> str:
    clean = _clean_string(name, value)
    try:
        parsed = UUID(clean)
    except ValueError as exc:
        raise ForwardMetricsEvidenceModelError(
            f"{name} must be a canonical lowercase UUID v4"
        ) from exc
    if parsed.version != 4 or str(parsed) != clean:
        raise ForwardMetricsEvidenceModelError(
            f"{name} must be a canonical lowercase UUID v4"
        )
    return clean


def _sha(name: str, value: object) -> str:
    clean = _clean_string(name, value)
    if _SHA256.fullmatch(clean) is None:
        raise ForwardMetricsEvidenceModelError(
            f"{name} must be a lowercase SHA-256"
        )
    return clean


def _timestamp(name: str, value: object) -> str:
    clean = _clean_string(name, value)
    try:
        parsed = datetime.strptime(clean, _TIMESTAMP_FORMAT)
    except ValueError as exc:
        raise ForwardMetricsEvidenceModelError(
            f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
        ) from exc
    if parsed.strftime(_TIMESTAMP_FORMAT) != clean:
        raise ForwardMetricsEvidenceModelError(
            f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
        )
    return clean


def _finite_number(name: str, value: object, *, non_negative: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ForwardMetricsEvidenceModelError(
            f"{name} must be finite numeric data"
        )
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ForwardMetricsEvidenceModelError(
            f"{name} must be finite numeric data"
        ) from exc
    if not math.isfinite(number) or (non_negative and number < 0.0):
        requirement = "finite and non-negative" if non_negative else "finite"
        raise ForwardMetricsEvidenceModelError(f"{name} must be {requirement}")
    return number


def _count(name: str, value: object, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if type(value) is not int or value < minimum:
        qualifier = "positive" if positive else "non-negative"
        raise ForwardMetricsEvidenceModelError(
            f"{name} must be a {qualifier} exact int"
        )
    return value


def _optional_ratio(name: str, value: object) -> float | None:
    if value is None:
        return None
    ratio = _finite_number(name, value, non_negative=True)
    if ratio > 1.0:
        raise ForwardMetricsEvidenceModelError(f"{name} must be within [0, 1]")
    return ratio


def _percentage(name: str, value: object) -> float:
    percentage = _finite_number(name, value, non_negative=True)
    if percentage > 100.0:
        raise ForwardMetricsEvidenceModelError(
            f"{name} must be within [0, 100]"
        )
    return percentage


def _expected_ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


@dataclass(frozen=True, slots=True)
class ForwardExecutionHealthMetrics:
    total_decisions: int
    actionable_decisions: int
    enter_decisions: int
    exit_decisions: int
    non_action_decisions: int
    no_candidate_count: int
    candidate_count: int
    rejected_count: int
    accepted_count: int
    pending_count: int
    filled_count: int
    skipped_invalid_open_count: int
    failed_portfolio_validation_count: int
    terminal_attempt_count: int
    candidate_rate: float | None
    rejection_rate: float | None
    terminal_fill_success_rate: float | None
    invalid_open_rate: float | None
    portfolio_validation_failure_rate: float | None
    pending_rate: float | None

    def __post_init__(self) -> None:
        count_names = (
            "total_decisions",
            "actionable_decisions",
            "enter_decisions",
            "exit_decisions",
            "non_action_decisions",
            "no_candidate_count",
            "candidate_count",
            "rejected_count",
            "accepted_count",
            "pending_count",
            "filled_count",
            "skipped_invalid_open_count",
            "failed_portfolio_validation_count",
            "terminal_attempt_count",
        )
        for name in count_names:
            _count(name, getattr(self, name))
        if self.actionable_decisions != self.enter_decisions + self.exit_decisions:
            raise ForwardMetricsEvidenceModelError(
                "actionable_decisions must equal enter_decisions + exit_decisions"
            )
        if self.candidate_count != self.actionable_decisions - self.no_candidate_count:
            raise ForwardMetricsEvidenceModelError(
                "candidate_count must equal actionable_decisions - no_candidate_count"
            )
        expected_accepted = (
            self.pending_count
            + self.filled_count
            + self.skipped_invalid_open_count
            + self.failed_portfolio_validation_count
        )
        if self.accepted_count != expected_accepted:
            raise ForwardMetricsEvidenceModelError(
                "accepted_count does not equal accepted outcome counts"
            )
        if self.candidate_count != self.rejected_count + self.accepted_count:
            raise ForwardMetricsEvidenceModelError(
                "candidate_count must equal rejected_count + accepted_count"
            )
        expected_terminal = (
            self.filled_count
            + self.skipped_invalid_open_count
            + self.failed_portfolio_validation_count
        )
        if self.terminal_attempt_count != expected_terminal:
            raise ForwardMetricsEvidenceModelError(
                "terminal_attempt_count does not equal terminal outcome counts"
            )
        if self.total_decisions != self.non_action_decisions + self.actionable_decisions:
            raise ForwardMetricsEvidenceModelError(
                "total_decisions must equal non_action_decisions + actionable_decisions"
            )
        ratios = {
            "candidate_rate": _expected_ratio(
                self.candidate_count, self.actionable_decisions
            ),
            "rejection_rate": _expected_ratio(
                self.rejected_count, self.candidate_count
            ),
            "terminal_fill_success_rate": _expected_ratio(
                self.filled_count, self.terminal_attempt_count
            ),
            "invalid_open_rate": _expected_ratio(
                self.skipped_invalid_open_count, self.terminal_attempt_count
            ),
            "portfolio_validation_failure_rate": _expected_ratio(
                self.failed_portfolio_validation_count,
                self.terminal_attempt_count,
            ),
            "pending_rate": _expected_ratio(
                self.pending_count, self.accepted_count
            ),
        }
        for name, expected in ratios.items():
            actual = _optional_ratio(name, getattr(self, name))
            if actual != expected:
                raise ForwardMetricsEvidenceModelError(
                    f"{name} does not use its frozen denominator"
                )
            object.__setattr__(self, name, actual)


@dataclass(frozen=True, slots=True)
class ForwardAppliedCostMetrics:
    filled_quantity: int
    filled_gross_notional: float
    applied_fee: float
    applied_tax: float
    applied_slippage: float
    applied_total_cost: float
    applied_cost_bps: float | None
    effective_slippage_per_share: float | None

    def __post_init__(self) -> None:
        _count("filled_quantity", self.filled_quantity)
        numeric_names = (
            "filled_gross_notional",
            "applied_fee",
            "applied_tax",
            "applied_slippage",
            "applied_total_cost",
        )
        values = {
            name: _finite_number(name, getattr(self, name), non_negative=True)
            for name in numeric_names
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)
        expected_total = (
            values["applied_fee"]
            + values["applied_tax"]
            + values["applied_slippage"]
        )
        if values["applied_total_cost"] != expected_total:
            raise ForwardMetricsEvidenceModelError(
                "applied_total_cost must equal fee + tax + slippage"
            )
        if (self.filled_quantity == 0) != (values["filled_gross_notional"] == 0.0):
            raise ForwardMetricsEvidenceModelError(
                "filled quantity and gross notional zero states must agree"
            )
        if self.filled_quantity == 0 and expected_total != 0.0:
            raise ForwardMetricsEvidenceModelError(
                "zero filled quantity cannot have applied costs"
            )
        cost_bps = (
            None
            if values["filled_gross_notional"] == 0.0
            else expected_total / values["filled_gross_notional"] * 10_000.0
        )
        slippage_per_share = (
            None
            if self.filled_quantity == 0
            else values["applied_slippage"] / self.filled_quantity
        )
        actual_bps = (
            None
            if self.applied_cost_bps is None
            else _finite_number(
                "applied_cost_bps", self.applied_cost_bps, non_negative=True
            )
        )
        actual_slippage = (
            None
            if self.effective_slippage_per_share is None
            else _finite_number(
                "effective_slippage_per_share",
                self.effective_slippage_per_share,
                non_negative=True,
            )
        )
        if actual_bps != cost_bps:
            raise ForwardMetricsEvidenceModelError(
                "applied_cost_bps does not match total cost / gross notional"
            )
        if actual_slippage != slippage_per_share:
            raise ForwardMetricsEvidenceModelError(
                "effective_slippage_per_share does not match applied slippage"
            )
        object.__setattr__(self, "applied_cost_bps", actual_bps)
        object.__setattr__(self, "effective_slippage_per_share", actual_slippage)


@dataclass(frozen=True, slots=True)
class ForwardPortfolioMetrics:
    observation_count: int
    observation_start: str
    observation_end: str
    initial_equity: float
    final_equity: float
    total_return_pct: float | None
    max_drawdown_pct: float
    max_open_position_count: int
    max_pending_order_count: int
    max_reserved_buy_notional: float
    max_market_exposure_pct: float
    max_single_symbol_market_value_share_pct: float

    def __post_init__(self) -> None:
        _count("observation_count", self.observation_count, positive=True)
        start = _timestamp("observation_start", self.observation_start)
        end = _timestamp("observation_end", self.observation_end)
        if end < start:
            raise ForwardMetricsEvidenceModelError(
                "observation_end must not predate observation_start"
            )
        initial = _finite_number(
            "initial_equity", self.initial_equity, non_negative=True
        )
        final = _finite_number(
            "final_equity", self.final_equity, non_negative=True
        )
        expected_return = (
            None if initial == 0.0 else (final / initial - 1.0) * 100.0
        )
        actual_return = (
            None
            if self.total_return_pct is None
            else _finite_number(
                "total_return_pct", self.total_return_pct, non_negative=False
            )
        )
        if actual_return != expected_return:
            raise ForwardMetricsEvidenceModelError(
                "total_return_pct does not match initial/final equity"
            )
        _count("max_open_position_count", self.max_open_position_count)
        _count("max_pending_order_count", self.max_pending_order_count)
        reserved = _finite_number(
            "max_reserved_buy_notional",
            self.max_reserved_buy_notional,
            non_negative=True,
        )
        object.__setattr__(self, "initial_equity", initial)
        object.__setattr__(self, "final_equity", final)
        object.__setattr__(self, "total_return_pct", actual_return)
        object.__setattr__(
            self, "max_drawdown_pct", _percentage("max_drawdown_pct", self.max_drawdown_pct)
        )
        object.__setattr__(self, "max_reserved_buy_notional", reserved)
        object.__setattr__(
            self,
            "max_market_exposure_pct",
            _percentage("max_market_exposure_pct", self.max_market_exposure_pct),
        )
        object.__setattr__(
            self,
            "max_single_symbol_market_value_share_pct",
            _percentage(
                "max_single_symbol_market_value_share_pct",
                self.max_single_symbol_market_value_share_pct,
            ),
        )


@dataclass(frozen=True, slots=True)
class ForwardQualificationReference:
    qualification_total_return_pct: float
    qualification_max_drawdown_pct: float
    qualification_completed_trades: int
    qualification_valid_windows: int
    qualification_benchmark_return_pct: float | None
    qualification_return_basis: str
    qualification_drawdown_basis: str
    forward_return_basis: str
    forward_drawdown_basis: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "qualification_total_return_pct",
            _finite_number(
                "qualification_total_return_pct",
                self.qualification_total_return_pct,
                non_negative=False,
            ),
        )
        object.__setattr__(
            self,
            "qualification_max_drawdown_pct",
            _percentage(
                "qualification_max_drawdown_pct",
                self.qualification_max_drawdown_pct,
            ),
        )
        _count("qualification_completed_trades", self.qualification_completed_trades)
        _count("qualification_valid_windows", self.qualification_valid_windows)
        benchmark = (
            None
            if self.qualification_benchmark_return_pct is None
            else _finite_number(
                "qualification_benchmark_return_pct",
                self.qualification_benchmark_return_pct,
                non_negative=False,
            )
        )
        object.__setattr__(self, "qualification_benchmark_return_pct", benchmark)
        expected_bases = {
            "qualification_return_basis": "mean_valid_window_test_return_pct",
            "qualification_drawdown_basis": "worst_valid_window_symbol_backtest_max_drawdown_pct",
            "forward_return_basis": "combined_forward_portfolio_total_equity_return_pct",
            "forward_drawdown_basis": "combined_forward_portfolio_equity_trace_max_drawdown_pct",
        }
        for name, expected in expected_bases.items():
            if getattr(self, name) != expected:
                raise ForwardMetricsEvidenceModelError(f"{name} is not supported")


@dataclass(frozen=True, slots=True)
class ForwardMetricsEvidence:
    schema_version: str
    artifact_type: str
    metrics_id: str
    created_at: str
    activation_id: str
    activation_sha256: str
    qualification_evaluation_id: str
    qualification_sha256: str
    ledger_id: str
    ledger_sha256: str
    execution_evidence_id: str
    execution_evidence_sha256: str
    portfolio_result_sha256: str
    portfolio_trace_sha256: str
    strategy_id: str
    execution_health: ForwardExecutionHealthMetrics
    applied_costs: ForwardAppliedCostMetrics
    portfolio_metrics: ForwardPortfolioMetrics
    qualification_reference: ForwardQualificationReference

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise ForwardMetricsEvidenceModelError("schema_version must be '1.0'")
        if self.artifact_type != "forward_metrics_evidence":
            raise ForwardMetricsEvidenceModelError("artifact_type is not supported")
        _uuid("metrics_id", self.metrics_id)
        _timestamp("created_at", self.created_at)
        for name in (
            "activation_id",
            "qualification_evaluation_id",
            "ledger_id",
            "execution_evidence_id",
        ):
            _uuid(name, getattr(self, name))
        for name in (
            "activation_sha256",
            "qualification_sha256",
            "ledger_sha256",
            "execution_evidence_sha256",
            "portfolio_result_sha256",
            "portfolio_trace_sha256",
        ):
            _sha(name, getattr(self, name))
        _clean_string("strategy_id", self.strategy_id)
        nested = (
            ("execution_health", ForwardExecutionHealthMetrics),
            ("applied_costs", ForwardAppliedCostMetrics),
            ("portfolio_metrics", ForwardPortfolioMetrics),
            ("qualification_reference", ForwardQualificationReference),
        )
        for name, expected_type in nested:
            if type(getattr(self, name)) is not expected_type:
                raise ForwardMetricsEvidenceModelError(
                    f"{name} must be an exact {expected_type.__name__}"
                )


__all__ = [
    "ForwardAppliedCostMetrics",
    "ForwardExecutionHealthMetrics",
    "ForwardMetricsEvidence",
    "ForwardMetricsEvidenceModelError",
    "ForwardPortfolioMetrics",
    "ForwardQualificationReference",
]
