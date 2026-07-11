import math
from typing import Any, Callable

from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedFill,
    SimulatedOrder,
    SimulatedOrderRejection,
    SimulatedPortfolio,
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
    is_valid_open = True
    try:
        op = float(open_price)
        if not math.isfinite(op) or op <= 0.0:
            is_valid_open = False
    except (ValueError, TypeError):
        is_valid_open = False

    pending_state = runtime_state.pending_orders.pop(symbol, None)
    if pending_state is not None:
        if is_valid_open:
            pending_order = pending_state.order
            op_price = float(open_price)
            try:
                fill = SimulatedFill(
                    order_id=pending_order.order_id,
                    symbol=pending_order.symbol,
                    side=pending_order.side,
                    quantity=pending_order.quantity,
                    price=op_price,
                    filled_at=index_label,
                    fee=pending_order.quantity * op_price * fee_rate,
                    tax=pending_order.quantity * op_price * tax_rate if pending_order.side == "SELL" else 0.0,
                    slippage=pending_order.quantity * slippage_per_share,
                )
                runtime_state.portfolio.apply_fill(fill)
            except PaperTradingModelError:
                pass


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
) -> SimulatedOrder | None:
    is_valid_open = True
    try:
        op = float(open_price)
        if not math.isfinite(op) or op <= 0.0:
            is_valid_open = False
    except (ValueError, TypeError):
        is_valid_open = False

    if not is_valid_open:
        return None

    pos_model = runtime_state.portfolio.position_for(symbol)
    shares = pos_model.quantity

    if shares > 0 and exit_signal:
        order_id = f"{symbol}-SELL-{bar_position}"
        return SimulatedOrder(
            order_id=order_id,
            symbol=symbol,
            side="SELL",
            quantity=shares,
            signal_time=index_label,
            created_at=index_label,
        )
    elif shares == 0 and entry_signal:
        order_id = f"{symbol}-BUY-{bar_position}"
        return SimulatedOrder(
            order_id=order_id,
            symbol=symbol,
            side="BUY",
            quantity=quantity_per_trade,
            signal_time=index_label,
            created_at=index_label,
        )
    return None


def evaluate_and_record_simulated_candidate(
    runtime_state: SimulatedPaperTradingRuntimeState,
    candidate_order: SimulatedOrder,
    open_price: float,
    guard_decision: SimulatedPaperTradingGuardDecision | None = None,
    guard_decision_provider: Callable[
        [SimulatedOrder, SimulatedPortfolio],
        SimulatedPaperTradingGuardDecision,
    ] | None = None,
) -> None:
    decision = None
    if guard_decision_provider is not None:
        decision = guard_decision_provider(candidate_order, runtime_state.portfolio)
        if not isinstance(decision, SimulatedPaperTradingGuardDecision):
            raise PaperTradingModelError("guard_decision_provider must return SimulatedPaperTradingGuardDecision.")
    elif guard_decision is not None:
        decision = guard_decision

    if decision is None or not decision.is_blocked:
        # Create pending order
        pending = SimulatedPendingOrderState(
            order=candidate_order,
            reference_price=float(open_price),
        )
        runtime_state.pending_orders[candidate_order.symbol] = pending
        runtime_state.portfolio.trade_log.record_order(candidate_order)
    else:
        runtime_state.portfolio.trade_log.record_rejection(
            SimulatedOrderRejection(candidate_order=candidate_order, reasons=decision.reasons)
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
        [SimulatedOrder, SimulatedPortfolio],
        SimulatedPaperTradingGuardDecision,
    ] | None = None,
) -> None:
    # 8.2 Validation
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
    )

    if candidate is not None:
        evaluate_and_record_simulated_candidate(
            runtime_state=runtime_state,
            candidate_order=candidate,
            open_price=open_price,
            guard_decision=guard_decision,
            guard_decision_provider=guard_decision_provider,
        )
