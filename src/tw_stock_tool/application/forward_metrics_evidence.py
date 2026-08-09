"""Pure construction of trusted forward-paper metrics evidence."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
from typing import Any

from tw_stock_tool.application.forward_execution_evidence import (
    ForwardExecutionEvidenceError,
    build_forward_execution_evidence,
)
from tw_stock_tool.application.forward_paper_execution import (
    ForwardPaperExecutionError,
    validate_forward_portfolio_trace,
)
from tw_stock_tool.application.universe_qualification import UniverseOOSArtifact
from tw_stock_tool.forward_paper.decision_models import ForwardDecisionLedger
from tw_stock_tool.forward_paper.execution_models import (
    ForwardExecutionDecisionEvidence,
    ForwardExecutionEvidence,
    ForwardExecutionOutcome,
)
from tw_stock_tool.forward_paper.execution_serialization import (
    export_forward_execution_evidence_json,
)
from tw_stock_tool.forward_paper.metrics_models import (
    ForwardAppliedCostMetrics,
    ForwardExecutionHealthMetrics,
    ForwardMetricsEvidence,
    ForwardPortfolioMetrics,
    ForwardQualificationReference,
)
from tw_stock_tool.forward_paper.models import ForwardPaperActivation
from tw_stock_tool.forward_paper.portfolio_trace_models import ForwardPortfolioTrace
from tw_stock_tool.paper_trading.portfolio_results import (
    SimulatedPortfolioTradingResult,
)


class ForwardMetricsEvidenceError(ValueError):
    """Raised when trusted inputs cannot produce forward metrics evidence."""


def _fail(message: str) -> None:
    raise ForwardMetricsEvidenceError(message)


def _trusted_execution_evidence(
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
    ledger: ForwardDecisionLedger,
    recommendation_evidence_by_id: Mapping[str, Any],
    portfolio_result: SimulatedPortfolioTradingResult,
    execution_evidence: ForwardExecutionEvidence,
) -> tuple[ForwardExecutionEvidence, str]:
    if type(execution_evidence) is not ForwardExecutionEvidence:
        _fail("execution_evidence must be an exact ForwardExecutionEvidence")
    try:
        rebuilt = build_forward_execution_evidence(
            activation,
            qualification_artifact,
            ledger,
            recommendation_evidence_by_id,
            portfolio_result,
            evidence_id=execution_evidence.evidence_id,
            created_at=execution_evidence.created_at,
        )
        supplied_json = export_forward_execution_evidence_json(execution_evidence)
        rebuilt_json = export_forward_execution_evidence_json(rebuilt)
    except (ForwardExecutionEvidenceError, TypeError, ValueError) as exc:
        raise ForwardMetricsEvidenceError(
            f"execution evidence validation failed: {exc}"
        ) from exc
    if supplied_json != rebuilt_json:
        _fail("execution evidence does not exactly match its trusted rebuild")
    return rebuilt, hashlib.sha256(rebuilt_json.encode("utf-8")).hexdigest()


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _build_execution_health_metrics(
    decisions: tuple[ForwardExecutionDecisionEvidence, ...],
) -> ForwardExecutionHealthMetrics:
    total = len(decisions)
    enter = sum(item.action == "ENTER" for item in decisions)
    exit_ = sum(item.action == "EXIT" for item in decisions)
    actionable = enter + exit_
    no_candidate = sum(
        item.outcome is ForwardExecutionOutcome.NO_CANDIDATE for item in decisions
    )
    rejected = sum(
        item.outcome is ForwardExecutionOutcome.REJECTED for item in decisions
    )
    pending = sum(
        item.outcome is ForwardExecutionOutcome.PENDING_NEXT_BAR_OPEN
        for item in decisions
    )
    filled = sum(item.outcome is ForwardExecutionOutcome.FILLED for item in decisions)
    skipped = sum(
        item.outcome is ForwardExecutionOutcome.FILL_SKIPPED_INVALID_OPEN
        for item in decisions
    )
    failed = sum(
        item.outcome
        is ForwardExecutionOutcome.FILL_FAILED_PORTFOLIO_VALIDATION
        for item in decisions
    )
    candidate = actionable - no_candidate
    accepted = pending + filled + skipped + failed
    terminal = filled + skipped + failed
    return ForwardExecutionHealthMetrics(
        total_decisions=total,
        actionable_decisions=actionable,
        enter_decisions=enter,
        exit_decisions=exit_,
        non_action_decisions=total - actionable,
        no_candidate_count=no_candidate,
        candidate_count=candidate,
        rejected_count=rejected,
        accepted_count=accepted,
        pending_count=pending,
        filled_count=filled,
        skipped_invalid_open_count=skipped,
        failed_portfolio_validation_count=failed,
        terminal_attempt_count=terminal,
        candidate_rate=_ratio(candidate, actionable),
        rejection_rate=_ratio(rejected, candidate),
        terminal_fill_success_rate=_ratio(filled, terminal),
        invalid_open_rate=_ratio(skipped, terminal),
        portfolio_validation_failure_rate=_ratio(failed, terminal),
        pending_rate=_ratio(pending, accepted),
    )


def _build_applied_cost_metrics(
    decisions: tuple[ForwardExecutionDecisionEvidence, ...],
    *,
    fee_rate: float,
    tax_rate: float,
) -> ForwardAppliedCostMetrics:
    filled = tuple(
        item for item in decisions if item.outcome is ForwardExecutionOutcome.FILLED
    )
    quantity = 0
    gross_notional = 0.0
    fee = 0.0
    tax = 0.0
    slippage = 0.0
    for item in filled:
        if item.order_quantity is None or item.fill_price is None:
            _fail("FILLED execution evidence lacks quantity or fill price")
        item_gross = item.order_quantity * item.fill_price
        expected_fee = item_gross * fee_rate
        expected_tax = item_gross * tax_rate if item.expected_side == "SELL" else 0.0
        if item.fee != expected_fee or item.tax != expected_tax:
            _fail("FILLED execution costs do not match frozen qualification rates")
        quantity += item.order_quantity
        gross_notional += item_gross
        fee += item.fee
        tax += item.tax
        slippage += item.slippage
    total_cost = fee + tax + slippage
    return ForwardAppliedCostMetrics(
        filled_quantity=quantity,
        filled_gross_notional=gross_notional,
        applied_fee=fee,
        applied_tax=tax,
        applied_slippage=slippage,
        applied_total_cost=total_cost,
        applied_cost_bps=(
            None if gross_notional == 0.0 else total_cost / gross_notional * 10_000.0
        ),
        effective_slippage_per_share=(
            None if quantity == 0 else slippage / quantity
        ),
    )


def _build_portfolio_metrics(
    portfolio_trace: ForwardPortfolioTrace,
) -> ForwardPortfolioMetrics:
    observations = portfolio_trace.observations
    equity_path = (portfolio_trace.initial_equity,) + tuple(
        item.total_equity for item in observations
    )
    peak = equity_path[0]
    max_drawdown = 0.0
    for equity in equity_path:
        peak = max(peak, equity)
        drawdown = 0.0 if peak == 0.0 else (peak - equity) / peak * 100.0
        max_drawdown = max(max_drawdown, drawdown)

    max_exposure = 0.0
    max_single_symbol_share = 0.0
    for observation in observations:
        exposure = (
            0.0
            if observation.total_equity == 0.0
            else observation.total_market_value / observation.total_equity * 100.0
        )
        max_exposure = max(max_exposure, exposure)
        if observation.total_market_value != 0.0:
            max_single_symbol_share = max(
                max_single_symbol_share,
                max(
                    item.market_value / observation.total_market_value * 100.0
                    for item in observation.positions
                ),
            )

    initial_equity = portfolio_trace.initial_equity
    final_equity = observations[-1].total_equity
    return ForwardPortfolioMetrics(
        observation_count=len(observations),
        observation_start=observations[0].observed_at,
        observation_end=observations[-1].observed_at,
        initial_equity=initial_equity,
        final_equity=final_equity,
        total_return_pct=(
            None
            if initial_equity == 0.0
            else (final_equity / initial_equity - 1.0) * 100.0
        ),
        max_drawdown_pct=max_drawdown,
        max_open_position_count=max(item.open_position_count for item in observations),
        max_pending_order_count=max(
            item.pending_order_count for item in observations
        ),
        max_reserved_buy_notional=max(
            item.reserved_buy_notional for item in observations
        ),
        max_market_exposure_pct=max_exposure,
        max_single_symbol_market_value_share_pct=max_single_symbol_share,
    )


def _build_qualification_reference(
    qualification_artifact: UniverseOOSArtifact,
) -> ForwardQualificationReference:
    metrics = qualification_artifact.qualification.request.metrics
    return ForwardQualificationReference(
        qualification_total_return_pct=metrics.total_return_pct,
        qualification_max_drawdown_pct=metrics.max_drawdown_pct,
        qualification_completed_trades=metrics.completed_trades,
        qualification_valid_windows=metrics.valid_windows,
        qualification_benchmark_return_pct=metrics.benchmark_return_pct,
        qualification_return_basis="mean_valid_window_test_return_pct",
        qualification_drawdown_basis=(
            "worst_valid_window_symbol_backtest_max_drawdown_pct"
        ),
        forward_return_basis="combined_forward_portfolio_total_equity_return_pct",
        forward_drawdown_basis=(
            "combined_forward_portfolio_equity_trace_max_drawdown_pct"
        ),
    )


def _validate_chronology(
    activation: ForwardPaperActivation,
    execution_evidence: ForwardExecutionEvidence,
    portfolio_trace: ForwardPortfolioTrace,
) -> None:
    trace_times = {item.observed_at for item in portfolio_trace.observations}
    if any(
        item.observed_at <= activation.qualification_cutoff
        for item in portfolio_trace.observations
    ):
        _fail("portfolio trace observation is at or before qualification cutoff")
    terminal_outcomes = {
        ForwardExecutionOutcome.FILLED,
        ForwardExecutionOutcome.FILL_SKIPPED_INVALID_OPEN,
        ForwardExecutionOutcome.FILL_FAILED_PORTFOLIO_VALIDATION,
    }
    for decision in execution_evidence.decisions:
        if decision.observed_at not in trace_times:
            _fail("execution decision timestamp is absent from portfolio trace")
        if decision.outcome in terminal_outcomes:
            if decision.fill_time is None or decision.fill_time not in trace_times:
                _fail("terminal fill timestamp is absent from portfolio trace")
            if decision.fill_time <= decision.observed_at:
                _fail("terminal fill timestamp must follow its decision timestamp")


def build_forward_metrics_evidence(
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
    ledger: ForwardDecisionLedger,
    recommendation_evidence_by_id: Mapping[str, Any],
    portfolio_result: SimulatedPortfolioTradingResult,
    execution_evidence: ForwardExecutionEvidence,
    portfolio_trace: ForwardPortfolioTrace,
    *,
    expected_portfolio_trace_sha256: str,
    metrics_id: str,
    created_at: str,
) -> ForwardMetricsEvidence:
    """Build factual D2 metrics after independently validating C2 and D1 inputs."""

    trusted_execution, execution_sha256 = _trusted_execution_evidence(
        activation,
        qualification_artifact,
        ledger,
        recommendation_evidence_by_id,
        portfolio_result,
        execution_evidence,
    )
    try:
        trusted_trace = validate_forward_portfolio_trace(
            activation,
            qualification_artifact,
            ledger,
            portfolio_result,
            portfolio_trace,
            expected_portfolio_trace_sha256=expected_portfolio_trace_sha256,
        )
    except (ForwardPaperExecutionError, TypeError, ValueError) as exc:
        raise ForwardMetricsEvidenceError(
            f"portfolio trace validation failed: {exc}"
        ) from exc
    if trusted_execution.portfolio_result_sha256 != trusted_trace.portfolio_result_sha256:
        _fail("execution evidence and portfolio trace result identities differ")
    _validate_chronology(activation, trusted_execution, trusted_trace)

    configuration = qualification_artifact.resolved_configuration
    return ForwardMetricsEvidence(
        schema_version="1.0",
        artifact_type="forward_metrics_evidence",
        metrics_id=metrics_id,
        created_at=created_at,
        activation_id=trusted_execution.activation_id,
        activation_sha256=trusted_execution.activation_sha256,
        qualification_evaluation_id=trusted_execution.qualification_evaluation_id,
        qualification_sha256=trusted_execution.qualification_sha256,
        ledger_id=trusted_execution.ledger_id,
        ledger_sha256=trusted_execution.ledger_sha256,
        execution_evidence_id=trusted_execution.evidence_id,
        execution_evidence_sha256=execution_sha256,
        portfolio_result_sha256=trusted_execution.portfolio_result_sha256,
        portfolio_trace_sha256=expected_portfolio_trace_sha256,
        strategy_id=trusted_execution.strategy_id,
        execution_health=_build_execution_health_metrics(trusted_execution.decisions),
        applied_costs=_build_applied_cost_metrics(
            trusted_execution.decisions,
            fee_rate=configuration.fee_rate,
            tax_rate=configuration.tax_rate,
        ),
        portfolio_metrics=_build_portfolio_metrics(trusted_trace),
        qualification_reference=_build_qualification_reference(
            qualification_artifact
        ),
    )


__all__ = ["ForwardMetricsEvidenceError", "build_forward_metrics_evidence"]
