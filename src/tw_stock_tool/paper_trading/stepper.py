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

    is_valid_open = True
    try:
        op = float(open_price)
        if not math.isfinite(op) or op <= 0.0:
            is_valid_open = False
    except (ValueError, TypeError):
        is_valid_open = False

    # Phase A — Pending Fill
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

    # Phase B — Current Signal
    if not is_valid_open:
        return

    pos_model = runtime_state.portfolio.position_for(symbol)
    shares = pos_model.quantity

    candidate_order = None
    if shares > 0 and exit_signal:
        order_id = f"{symbol}-SELL-{bar_position}"
        candidate_order = SimulatedOrder(
            order_id=order_id,
            symbol=symbol,
            side="SELL",
            quantity=shares,
            signal_time=index_label,
            created_at=index_label,
        )
    elif shares == 0 and entry_signal:
        order_id = f"{symbol}-BUY-{bar_position}"
        candidate_order = SimulatedOrder(
            order_id=order_id,
            symbol=symbol,
            side="BUY",
            quantity=quantity_per_trade,
            signal_time=index_label,
            created_at=index_label,
        )
    else:
        return

    # Phase C & D — Guard Evaluation and Accept/Reject
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
        runtime_state.pending_orders[symbol] = pending
        runtime_state.portfolio.trade_log.record_order(candidate_order)
    else:
        runtime_state.portfolio.trade_log.record_rejection(
            SimulatedOrderRejection(candidate_order=candidate_order, reasons=decision.reasons)
        )
