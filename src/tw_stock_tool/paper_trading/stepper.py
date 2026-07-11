import math
from typing import Any, Callable, Mapping

from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedFill,
    SimulatedOrder,
    SimulatedOrderRejection,
    SimulatedPortfolio,
    SimulatedTradeEventType,
    SimulatedTradeStatus,
)
from tw_stock_tool.paper_trading.runtime import (
    SimulatedPaperTradingRuntimeState,
    SimulatedPendingOrderState,
)
from tw_stock_tool.simulated_paper_trading_guard.models import (
    SimulatedPaperTradingGuardDecision,
)


def process_simulated_pending_fill(
    runtime_state: SimulatedPaperTradingRuntimeState,
    *,
    symbol: str,
    open_price: float,
    index_label: Any,
    fee_rate: float = 0.0,
    tax_rate: float = 0.0,
    slippage_per_share: float = 0.0,
) -> None:
    try:
        op = float(open_price)
        is_valid_open = math.isfinite(op) and op > 0.0
    except (ValueError, TypeError):
        op = 0.0
        is_valid_open = False

    pending_state = runtime_state.pending_orders.pop(symbol, None)
    if pending_state is None:
        return

    order = pending_state.order
    log = runtime_state.portfolio.trade_log
    if not is_valid_open:
        log.record_event(
            order,
            SimulatedTradeEventType.FILL_SKIPPED,
            SimulatedTradeStatus.SKIPPED_INVALID_OPEN,
            fill_time=index_label,
            error_code="invalid_next_bar_open",
            error_message="No finite positive next-bar-open price was available.",
        )
        return

    fee = order.quantity * op * fee_rate
    tax = order.quantity * op * tax_rate if order.side == "SELL" else 0.0
    slippage = order.quantity * slippage_per_share
    try:
        fill = SimulatedFill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=op,
            filled_at=index_label,
            fee=fee,
            tax=tax,
            slippage=slippage,
        )
        runtime_state.portfolio.apply_fill(fill)
    except PaperTradingModelError as exc:
        log.record_event(
            order,
            SimulatedTradeEventType.FILL_FAILED,
            SimulatedTradeStatus.FAILED_PORTFOLIO_VALIDATION,
            fill_time=index_label,
            fill_price=op,
            fee=fee,
            tax=tax,
            slippage=slippage,
            error_code="portfolio_fill_validation_failed",
            error_message=str(exc),
        )
        return

    log.record_event(
        order,
        SimulatedTradeEventType.FILLED,
        SimulatedTradeStatus.FILLED,
        fill_time=index_label,
        fill_price=fill.price,
        fee=fill.fee,
        tax=fill.tax,
        slippage=fill.slippage,
    )


def build_simulated_symbol_candidate_order(
    runtime_state: SimulatedPaperTradingRuntimeState,
    *,
    symbol: str,
    bar_position: int,
    index_label: Any,
    open_price: float,
    entry_signal: bool,
    exit_signal: bool,
    quantity_per_trade: int,
    strategy: str | None = None,
    strategy_metadata: Mapping[str, Any] | None = None,
) -> SimulatedOrder | None:
    try:
        op = float(open_price)
        is_valid_open = math.isfinite(op) and op > 0.0
    except (ValueError, TypeError):
        is_valid_open = False
    if not is_valid_open:
        return None

    shares = runtime_state.portfolio.position_for(symbol).quantity
    if shares > 0 and exit_signal:
        side, quantity = "SELL", shares
    elif shares == 0 and entry_signal:
        side, quantity = "BUY", quantity_per_trade
    else:
        return None

    return SimulatedOrder(
        order_id=f"{symbol}-{side}-{bar_position}",
        symbol=symbol,
        side=side,
        quantity=quantity,
        signal_time=index_label,
        created_at=index_label,
        strategy=strategy,
        metadata=dict(strategy_metadata or {}),
    )


def evaluate_and_record_simulated_candidate(
    runtime_state: SimulatedPaperTradingRuntimeState,
    candidate_order: SimulatedOrder,
    open_price: float,
    guard_decision: SimulatedPaperTradingGuardDecision | None = None,
    guard_decision_provider: Callable[
        [SimulatedOrder, SimulatedPortfolio], SimulatedPaperTradingGuardDecision
    ] | None = None,
) -> None:
    log = runtime_state.portfolio.trade_log
    log.record_event(
        candidate_order,
        SimulatedTradeEventType.CANDIDATE_CREATED,
        SimulatedTradeStatus.CANDIDATE,
    )

    decision = guard_decision
    if guard_decision_provider is not None:
        decision = guard_decision_provider(candidate_order, runtime_state.portfolio)
        if not isinstance(decision, SimulatedPaperTradingGuardDecision):
            raise PaperTradingModelError("guard_decision_provider must return SimulatedPaperTradingGuardDecision.")

    blocked = decision.is_blocked if decision is not None else False
    if decision is not None:
        log.record_event(
            candidate_order,
            SimulatedTradeEventType.RISK_EVALUATED,
            SimulatedTradeStatus.RISK_REJECTED if blocked else SimulatedTradeStatus.RISK_ALLOWED,
            risk_allowed=not blocked,
            risk_rejection_reasons=decision.reasons,
            guard_metadata=decision.metadata,
        )

    if not blocked:
        runtime_state.pending_orders[candidate_order.symbol] = SimulatedPendingOrderState(
            order=candidate_order,
            reference_price=float(open_price),
        )
        log.record_order(candidate_order)
        log.record_event(
            candidate_order,
            SimulatedTradeEventType.ACCEPTED_PENDING,
            SimulatedTradeStatus.PENDING_NEXT_BAR_OPEN,
            risk_allowed=None if decision is None else True,
            guard_metadata={} if decision is None else decision.metadata,
        )
        return

    log.record_rejection(
        SimulatedOrderRejection(candidate_order=candidate_order, reasons=decision.reasons)
    )
    log.record_event(
        candidate_order,
        SimulatedTradeEventType.REJECTED,
        SimulatedTradeStatus.REJECTED,
        risk_allowed=False,
        risk_rejection_reasons=decision.reasons,
        guard_metadata=decision.metadata,
    )


def step_simulated_symbol_bar(
    runtime_state: SimulatedPaperTradingRuntimeState,
    *,
    symbol: str,
    bar_position: int,
    index_label: Any,
    open_price: float,
    entry_signal: bool,
    exit_signal: bool,
    quantity_per_trade: int,
    fee_rate: float = 0.0,
    tax_rate: float = 0.0,
    slippage_per_share: float = 0.0,
    guard_decision: SimulatedPaperTradingGuardDecision | None = None,
    guard_decision_provider: Callable[
        [SimulatedOrder, SimulatedPortfolio], SimulatedPaperTradingGuardDecision
    ] | None = None,
    strategy: str | None = None,
    strategy_metadata: Mapping[str, Any] | None = None,
) -> None:
    if not isinstance(runtime_state, SimulatedPaperTradingRuntimeState):
        raise PaperTradingModelError("runtime_state must be a SimulatedPaperTradingRuntimeState.")
    if not isinstance(symbol, str) or not symbol.strip():
        raise PaperTradingModelError("Symbol must not be blank.")
    if isinstance(bar_position, bool) or not isinstance(bar_position, int) or bar_position < 0:
        raise PaperTradingModelError("bar_position must be a non-negative integer.")
    if isinstance(quantity_per_trade, bool) or not isinstance(quantity_per_trade, int) or quantity_per_trade <= 0:
        raise PaperTradingModelError("quantity_per_trade must be a positive integer.")
    if fee_rate < 0 or tax_rate < 0 or slippage_per_share < 0:
        raise PaperTradingModelError("fee_rate, tax_rate, and slippage_per_share must be non-negative.")
    if guard_decision is not None and guard_decision_provider is not None:
        raise PaperTradingModelError("Cannot provide both guard_decision and guard_decision_provider.")
    if guard_decision is not None and not isinstance(guard_decision, SimulatedPaperTradingGuardDecision):
        raise PaperTradingModelError("guard_decision must be a SimulatedPaperTradingGuardDecision or None.")
    if guard_decision_provider is not None and not callable(guard_decision_provider):
        raise PaperTradingModelError("guard_decision_provider must be callable or None.")

    process_simulated_pending_fill(
        runtime_state=runtime_state,
        symbol=symbol,
        open_price=open_price,
        index_label=index_label,
        fee_rate=fee_rate,
        tax_rate=tax_rate,
        slippage_per_share=slippage_per_share,
    )
    candidate = build_simulated_symbol_candidate_order(
        runtime_state=runtime_state,
        symbol=symbol,
        bar_position=bar_position,
        index_label=index_label,
        open_price=open_price,
        entry_signal=entry_signal,
        exit_signal=exit_signal,
        quantity_per_trade=quantity_per_trade,
        strategy=strategy,
        strategy_metadata=strategy_metadata,
    )
    if candidate is not None:
        evaluate_and_record_simulated_candidate(
            runtime_state=runtime_state,
            candidate_order=candidate,
            open_price=open_price,
            guard_decision=guard_decision,
            guard_decision_provider=guard_decision_provider,
        )