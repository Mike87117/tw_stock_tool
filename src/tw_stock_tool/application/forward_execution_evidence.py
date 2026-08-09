"""Build immutable per-decision evidence from one trusted C1 result."""

from __future__ import annotations

from collections import defaultdict
import hashlib
from collections.abc import Mapping
from typing import Any

import pandas as pd

from tw_stock_tool.application.forward_paper_execution import (
    ForwardPaperExecutionError,
    _validate_replay_evidence,
    _validated_trust_chain,
)
from tw_stock_tool.application.recommendation_evidence import (
    RecommendationApplicationError,
    _canonical_timestamp,
)
from tw_stock_tool.forward_paper.execution_models import (
    ForwardExecutionDecisionEvidence,
    ForwardExecutionEvidence,
    ForwardExecutionOutcome,
)
from tw_stock_tool.paper_trading.models import (
    SimulatedOrder,
    SimulatedTradeEventType,
    SimulatedTradeLogRecord,
    SimulatedTradeStatus,
)
from tw_stock_tool.paper_trading.portfolio_results import (
    SimulatedPortfolioPendingOrderResult,
    SimulatedPortfolioTradingResult,
)
from tw_stock_tool.paper_trading.portfolio_serialization import (
    export_simulated_portfolio_trading_result_json,
    load_simulated_portfolio_trading_result_json,
)
from tw_stock_tool.forward_paper.decision_models import ForwardDecisionLedger
from tw_stock_tool.forward_paper.models import ForwardPaperActivation
from tw_stock_tool.application.universe_qualification import UniverseOOSArtifact


class ForwardExecutionEvidenceError(ValueError):
    """Raised when a supplied C1 result cannot be correlated unambiguously."""


def _fail(message: str) -> None:
    raise ForwardExecutionEvidenceError(message)


def _time(value: Any, name: str) -> str:
    try:
        return _canonical_timestamp(value, name)
    except RecommendationApplicationError as first_error:
        if isinstance(value, str):
            try:
                return _canonical_timestamp(pd.Timestamp(value), name)
            except (RecommendationApplicationError, TypeError, ValueError):
                pass
        raise ForwardExecutionEvidenceError(str(first_error)) from first_error


def _same(value: Any, expected: Any, name: str) -> None:
    if value != expected:
        _fail(f"{name} mismatch")


def _identity(metadata: Any, strategy: Any, expected: Mapping[str, Any], path: str) -> None:
    if strategy != expected["strategy_id"]:
        _fail(f"{path}.strategy mismatch")
    expected_metadata = expected["metadata"]
    if not isinstance(metadata, Mapping) or dict(metadata) != dict(expected_metadata):
        _fail(f"{path}.strategy metadata identity mismatch")


def _trusted_result(result: SimulatedPortfolioTradingResult) -> tuple[SimulatedPortfolioTradingResult, str, str]:
    if type(result) is not SimulatedPortfolioTradingResult:
        _fail("portfolio_result must be an exact SimulatedPortfolioTradingResult")
    try:
        canonical = export_simulated_portfolio_trading_result_json(result)
        loaded = load_simulated_portfolio_trading_result_json(canonical)
        round_trip = export_simulated_portfolio_trading_result_json(loaded)
    except Exception as exc:
        raise ForwardExecutionEvidenceError(
            f"portfolio result canonical validation failed: {exc}"
        ) from exc
    if round_trip != canonical:
        _fail("portfolio result canonical round-trip drift")
    return loaded, canonical, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _order_key(order: SimulatedOrder, path: str) -> tuple[str, str, str]:
    if type(order) is not SimulatedOrder:
        _fail(f"{path} must be SimulatedOrder")
    if order.side not in ("BUY", "SELL"):
        _fail(f"{path}.side invalid")
    if type(order.quantity) is not int or order.quantity <= 0:
        _fail(f"{path}.quantity invalid")
    return (_time(order.signal_time, f"{path}.signal_time"), order.symbol, order.side)


def _audit_key(record: SimulatedTradeLogRecord, path: str) -> tuple[str, str, str]:
    if type(record) is not SimulatedTradeLogRecord:
        _fail(f"{path} must be SimulatedTradeLogRecord")
    if record.event_type is SimulatedTradeEventType.EXECUTION_ERROR or record.status is SimulatedTradeStatus.EXECUTION_ERROR:
        _fail("completed portfolio result cannot contain EXECUTION_ERROR")
    return (_time(record.signal_time, f"{path}.signal_time"), record.symbol, record.side)


def _assert_audit_matches_order(record: SimulatedTradeLogRecord, order: SimulatedOrder, path: str) -> None:
    _same(record.order_id, order.order_id, f"{path}.order_id")
    _same(record.symbol, order.symbol, f"{path}.symbol")
    _same(record.side, order.side, f"{path}.side")
    _same(record.quantity, order.quantity, f"{path}.quantity")
    _same(_time(record.signal_time, f"{path}.signal_time"), _time(order.signal_time, "order.signal_time"), f"{path}.signal_time")


def _validate_result_identity(
    result: SimulatedPortfolioTradingResult,
    expected: Mapping[str, str],
) -> None:
    seen_order_ids: set[str] = set()
    seen_rejection_ids: set[str] = set()
    accepted: dict[str, SimulatedOrder] = {}
    candidates: dict[str, SimulatedOrder] = {}
    candidate_keys: dict[tuple[str, str, str], str] = {}
    for index, order in enumerate(result.orders):
        key = _order_key(order, f"orders[{index}]")
        if order.order_id in seen_order_ids:
            _fail("accepted order IDs must be unique")
        seen_order_ids.add(order.order_id)
        _identity(order.metadata, order.strategy, expected, f"orders[{index}]")
        accepted[order.order_id] = order
        if key in candidate_keys:
            _fail("multiple candidate orders match one decision")
        candidate_keys[key] = order.order_id
        candidates[order.order_id] = order
    for index, rejection in enumerate(result.rejections):
        order = rejection.candidate_order
        key = _order_key(order, f"rejections[{index}].candidate_order")
        if order.order_id in seen_rejection_ids or order.order_id in seen_order_ids:
            _fail("accepted/rejected order IDs must be unique and unambiguous")
        seen_rejection_ids.add(order.order_id)
        _identity(order.metadata, order.strategy, expected, f"rejections[{index}].candidate_order")
        if type(rejection.reasons) is not tuple or any(type(reason) is not str or not reason.strip() for reason in rejection.reasons):
            _fail("rejection reasons must be an immutable tuple of strings")
        if key in candidate_keys:
            _fail("multiple candidate orders match one decision")
        candidate_keys[key] = order.order_id
        candidates[order.order_id] = order

    seen_fill_ids: set[str] = set()
    fills = {}
    for index, fill in enumerate(result.fills):
        if fill.order_id in seen_fill_ids:
            _fail("fill order IDs must be unique")
        if fill.order_id not in accepted:
            _fail("orphan fill")
        seen_fill_ids.add(fill.order_id)
        order = accepted[fill.order_id]
        _same(fill.symbol, order.symbol, f"fills[{index}].symbol")
        _same(fill.side, order.side, f"fills[{index}].side")
        _same(fill.quantity, order.quantity, f"fills[{index}].quantity")
        fills[fill.order_id] = fill

    seen_pending_ids: set[str] = set()
    pending = {}
    for index, item in enumerate(result.pending_orders):
        if type(item) is not SimulatedPortfolioPendingOrderResult:
            _fail(f"pending_orders[{index}] must be SimulatedPortfolioPendingOrderResult")
        if item.order_id in seen_pending_ids:
            _fail("pending order IDs must be unique")
        if item.order_id not in accepted:
            _fail("orphan pending order")
        seen_pending_ids.add(item.order_id)
        order = accepted[item.order_id]
        _same(item.symbol, order.symbol, f"pending_orders[{index}].symbol")
        _same(item.side, order.side, f"pending_orders[{index}].side")
        _same(item.quantity, order.quantity, f"pending_orders[{index}].quantity")
        _same(item.strategy, order.strategy, f"pending_orders[{index}].strategy")
        _same(_time(item.signal_time, f"pending_orders[{index}].signal_time"), _time(order.signal_time, "order.signal_time"), f"pending_orders[{index}].signal_time")
        pending[item.order_id] = item

    sequences = tuple(record.sequence for record in result.audit_log)
    if sequences != tuple(range(1, len(result.audit_log) + 1)):
        _fail("audit sequence must be positive contiguous ascending")
    audit_by_order: dict[str, list[SimulatedTradeLogRecord]] = defaultdict(list)
    for index, record in enumerate(result.audit_log):
        if record.record_id != f"audit-{record.sequence:06d}":
            _fail("audit record ID is inconsistent with sequence")
        _audit_key(record, f"audit_log[{index}]")
        _identity(record.strategy_metadata, record.strategy_name, expected, f"audit_log[{index}]")
        if record.order_id not in candidates:
            _fail("orphan audit record")
        order = candidates[record.order_id]
        _assert_audit_matches_order(record, order, f"audit_log[{index}]")
        audit_by_order[record.order_id].append(record)

    if set(audit_by_order) != set(candidates):
        _fail("every candidate order must have lifecycle audit records")

    for order_id, events in audit_by_order.items():
        if not events or events[0].event_type is not SimulatedTradeEventType.CANDIDATE_CREATED or events[0].status is not SimulatedTradeStatus.CANDIDATE:
            _fail("lifecycle must begin with CANDIDATE_CREATED")
        accepted_event = [event for event in events if event.event_type is SimulatedTradeEventType.ACCEPTED_PENDING]
        rejected_event = [event for event in events if event.event_type is SimulatedTradeEventType.REJECTED]
        terminal = [event for event in events if event.event_type in {SimulatedTradeEventType.FILLED, SimulatedTradeEventType.FILL_SKIPPED, SimulatedTradeEventType.FILL_FAILED}]
        if len(accepted_event) > 1 or len(rejected_event) > 1 or len(terminal) > 1:
            _fail("lifecycle contains duplicate terminal or accepted events")
        risk_events = [event for event in events if event.event_type is SimulatedTradeEventType.RISK_EVALUATED]
        if len(risk_events) > 1:
            _fail("lifecycle contains duplicate risk events")
        event_types = tuple(event.event_type for event in events)
        if risk_events and events.index(risk_events[0]) != 1:
            _fail("risk evaluation must follow candidate creation")
        if rejected_event:
            if order_id not in seen_rejection_ids or accepted_event or terminal or pending.get(order_id) is not None:
                _fail("rejected lifecycle is incompatible with accepted/pending/fill state")
            if rejected_event[0].status is not SimulatedTradeStatus.REJECTED:
                _fail("rejected lifecycle status mismatch")
            if not risk_events or risk_events[0].status is not SimulatedTradeStatus.RISK_REJECTED:
                _fail("rejected lifecycle risk status mismatch")
            if risk_events[0].risk_allowed is not False or rejected_event[0].risk_allowed is not False:
                _fail("rejected lifecycle risk_allowed must be false")
            rejection_reasons = tuple(next(item.reasons for item in result.rejections if item.candidate_order.order_id == order_id))
            if tuple(risk_events[0].risk_rejection_reasons) != rejection_reasons or tuple(rejected_event[0].risk_rejection_reasons) != rejection_reasons:
                _fail("risk rejection reasons disagree with rejection")
            expected_types = (SimulatedTradeEventType.CANDIDATE_CREATED, SimulatedTradeEventType.RISK_EVALUATED, SimulatedTradeEventType.REJECTED)
            if event_types != expected_types:
                _fail("rejected lifecycle event ordering is invalid")
        else:
            if order_id not in accepted or not accepted_event:
                _fail("accepted lifecycle missing accepted order/event")
            if accepted_event[0].status is not SimulatedTradeStatus.PENDING_NEXT_BAR_OPEN:
                _fail("accepted lifecycle status mismatch")
            if risk_events and risk_events[0].status is not SimulatedTradeStatus.RISK_ALLOWED:
                _fail("accepted lifecycle risk status mismatch")
            if terminal and pending.get(order_id) is not None:
                _fail("pending order cannot also have terminal fill event")
            if not terminal and pending.get(order_id) is None:
                _fail("accepted lifecycle must be terminal or pending")
            expected_types = (SimulatedTradeEventType.CANDIDATE_CREATED, SimulatedTradeEventType.ACCEPTED_PENDING)
            if risk_events:
                expected_types = (SimulatedTradeEventType.CANDIDATE_CREATED, SimulatedTradeEventType.RISK_EVALUATED, SimulatedTradeEventType.ACCEPTED_PENDING)
            if terminal:
                event = terminal[0]
                expected_types = expected_types + (event.event_type,)
                expected_status = {
                    SimulatedTradeEventType.FILLED: SimulatedTradeStatus.FILLED,
                    SimulatedTradeEventType.FILL_SKIPPED: SimulatedTradeStatus.SKIPPED_INVALID_OPEN,
                    SimulatedTradeEventType.FILL_FAILED: SimulatedTradeStatus.FAILED_PORTFOLIO_VALIDATION,
                }[event.event_type]
                if event.status is not expected_status:
                    _fail("terminal lifecycle event/status mismatch")
            if event_types != expected_types:
                _fail("accepted lifecycle event ordering is invalid")

    return candidates, accepted, fills, pending, audit_by_order


def build_forward_execution_evidence(
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
    ledger: ForwardDecisionLedger,
    recommendation_evidence_by_id: Mapping[str, Any],
    portfolio_result: SimulatedPortfolioTradingResult,
    *,
    evidence_id: str,
    created_at: str,
) -> ForwardExecutionEvidence:
    try:
        trusted_activation, trusted_source, trusted_ledger, ledger_sha = _validated_trust_chain(
            activation, qualification_artifact, ledger
        )
        resolved = _validate_replay_evidence(
            trusted_ledger, trusted_activation, trusted_source, recommendation_evidence_by_id
        )
    except (ForwardPaperExecutionError, TypeError, ValueError) as exc:
        raise ForwardExecutionEvidenceError(f"forward trust chain validation failed: {exc}") from exc

    trusted_result, _result_json, result_sha = _trusted_result(portfolio_result)
    expected_identity = {
        "activation_id": trusted_activation.activation_id,
        "ledger_id": trusted_ledger.ledger_id,
        "qualification_evaluation_id": trusted_activation.qualification_evaluation_id,
        "qualification_sha256": trusted_activation.qualification_sha256,
        "ledger_sha256": ledger_sha,
        "strategy_id": trusted_activation.strategy_id,
        "metadata": {
            "activation_id": trusted_activation.activation_id,
            "ledger_id": trusted_ledger.ledger_id,
            "qualification_evaluation_id": trusted_activation.qualification_evaluation_id,
            "qualification_sha256": trusted_activation.qualification_sha256,
            "ledger_sha256": ledger_sha,
        },
    }
    candidates, accepted, fills, pending, audit_by_order = _validate_result_identity(
        trusted_result, expected_identity
    )
    candidate_by_key = {
        (_time(order.signal_time, "order.signal_time"), order.symbol, order.side): order_id
        for order_id, order in candidates.items()
    }
    decisions: list[ForwardExecutionDecisionEvidence] = []
    consumed_candidates: set[str] = set()
    for record in trusted_ledger.decisions:
        action = resolved[record.recommendation_id].action
        expected_side = {"ENTER": "BUY", "EXIT": "SELL"}.get(action)
        if expected_side is None:
            outcome = ForwardExecutionOutcome.NON_ACTION
            order_id = None
        else:
            key = (record.observed_at, record.symbol, expected_side)
            order_id = candidate_by_key.get(key)
            outcome = ForwardExecutionOutcome.NO_CANDIDATE if order_id is None else None
        if outcome is ForwardExecutionOutcome.NON_ACTION or outcome is ForwardExecutionOutcome.NO_CANDIDATE:
            decisions.append(ForwardExecutionDecisionEvidence(
                recommendation_id=record.recommendation_id,
                recommendation_sha256=record.recommendation_sha256,
                observed_at=record.observed_at,
                symbol=record.symbol,
                action=action,
                expected_side=expected_side,
                outcome=outcome,
                order_id=None,
                order_quantity=None,
                pending_reference_price=None,
                fill_time=None,
                fill_price=None,
                fee=0.0,
                tax=0.0,
                slippage=0.0,
                risk_rejection_reasons=(),
                audit_record_ids=(),
            ))
            continue

        consumed_candidates.add(order_id)
        order = candidates[order_id]
        events = audit_by_order[order_id]
        terminal = [event for event in events if event.event_type in {SimulatedTradeEventType.REJECTED, SimulatedTradeEventType.FILLED, SimulatedTradeEventType.FILL_SKIPPED, SimulatedTradeEventType.FILL_FAILED}]
        audit_ids = tuple(event.record_id for event in events)
        rejection = next((item for item in trusted_result.rejections if item.candidate_order.order_id == order_id), None)
        if rejection is not None:
            terminal_event = terminal[-1]
            if terminal_event.event_type is not SimulatedTradeEventType.REJECTED:
                _fail("rejection candidate does not end in REJECTED")
            if tuple(terminal_event.risk_rejection_reasons) != tuple(rejection.reasons):
                _fail("rejection reasons disagree with terminal audit")
            decisions.append(ForwardExecutionDecisionEvidence(
                record.recommendation_id, record.recommendation_sha256, record.observed_at, record.symbol,
                action, expected_side, ForwardExecutionOutcome.REJECTED, order_id, order.quantity,
                None, None, None, terminal_event.fee, terminal_event.tax, terminal_event.slippage,
                tuple(rejection.reasons), audit_ids,
            ))
            continue

        if order_id in pending:
            item = pending[order_id]
            decisions.append(ForwardExecutionDecisionEvidence(
                record.recommendation_id, record.recommendation_sha256, record.observed_at, record.symbol,
                action, expected_side, ForwardExecutionOutcome.PENDING_NEXT_BAR_OPEN, order_id, order.quantity,
                item.reference_price, None, None, 0.0, 0.0, 0.0, (), audit_ids,
            ))
            continue

        if order_id not in accepted or len(terminal) != 1:
            _fail("accepted order has no unique terminal lifecycle")
        event = terminal[0]
        fill = fills.get(order_id)
        if event.event_type is SimulatedTradeEventType.FILLED:
            if fill is None:
                _fail("FILLED audit has no matching fill")
            fill_time = _time(fill.filled_at, "fill.filled_at")
            _same(_time(event.fill_time, "audit.fill_time"), fill_time, "fill time")
            _same(event.fill_price, fill.price, "fill price")
            _same(event.fee, fill.fee, "fill fee")
            _same(event.tax, fill.tax, "fill tax")
            _same(event.slippage, fill.slippage, "fill slippage")
            outcome = ForwardExecutionOutcome.FILLED
            fill_price = fill.price
            fill_time_value = fill_time
        elif event.event_type is SimulatedTradeEventType.FILL_SKIPPED:
            if fill is not None or event.fill_time is None or event.fill_price is not None:
                _fail("invalid skipped-fill lifecycle")
            outcome = ForwardExecutionOutcome.FILL_SKIPPED_INVALID_OPEN
            fill_price = None
            fill_time_value = _time(event.fill_time, "audit.fill_time")
        elif event.event_type is SimulatedTradeEventType.FILL_FAILED:
            if fill is not None or event.fill_time is None or event.fill_price is None:
                _fail("invalid failed-fill lifecycle")
            outcome = ForwardExecutionOutcome.FILL_FAILED_PORTFOLIO_VALIDATION
            fill_price = None
            fill_time_value = _time(event.fill_time, "audit.fill_time")
        else:
            _fail("accepted order has an invalid terminal event")
        decisions.append(ForwardExecutionDecisionEvidence(
            record.recommendation_id, record.recommendation_sha256, record.observed_at, record.symbol,
            action, expected_side, outcome, order_id, order.quantity, None, fill_time_value,
            fill_price, event.fee if fill is None else fill.fee, event.tax if fill is None else fill.tax,
            event.slippage if fill is None else fill.slippage, (), audit_ids,
        ))

    if consumed_candidates != set(candidates):
        _fail("runtime candidate order does not match a frozen actionable decision")

    return ForwardExecutionEvidence(
        schema_version="1.0",
        artifact_type="forward_execution_evidence",
        evidence_id=evidence_id,
        created_at=_time(created_at, "created_at"),
        activation_id=trusted_activation.activation_id,
        activation_sha256=trusted_ledger.activation_sha256,
        qualification_evaluation_id=trusted_activation.qualification_evaluation_id,
        qualification_sha256=trusted_activation.qualification_sha256,
        ledger_id=trusted_ledger.ledger_id,
        ledger_sha256=ledger_sha,
        portfolio_result_sha256=result_sha,
        strategy_id=trusted_activation.strategy_id,
        decisions=tuple(decisions),
    )


__all__ = ["ForwardExecutionEvidenceError", "build_forward_execution_evidence"]
