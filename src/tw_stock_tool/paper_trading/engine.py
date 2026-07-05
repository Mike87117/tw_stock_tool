import pandas as pd
from typing import Callable

from tw_stock_tool.backtesting.signals import validate_standard_signals
from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedFill,
    SimulatedOrder,
    SimulatedPortfolio,
)
from tw_stock_tool.paper_trading.results import (
    SimulatedPaperTradingResult,
    build_simulated_paper_trading_result,
)
from tw_stock_tool.simulated_paper_trading_guard.models import SimulatedPaperTradingGuardDecision

def _should_record_order_intent(
    candidate: SimulatedOrder,
    portfolio: SimulatedPortfolio,
    static_guard: SimulatedPaperTradingGuardDecision | None,
    dynamic_provider: Callable[[SimulatedOrder, SimulatedPortfolio], SimulatedPaperTradingGuardDecision] | None,
) -> bool:
    if dynamic_provider is not None:
        decision = dynamic_provider(candidate, portfolio)
        if not isinstance(decision, SimulatedPaperTradingGuardDecision):
            raise PaperTradingModelError("guard_decision_provider must return SimulatedPaperTradingGuardDecision.")
        return not decision.is_blocked
    if static_guard is not None:
        return not static_guard.is_blocked
    return True



def run_simulated_paper_trading(
    df: pd.DataFrame,
    symbol: str,
    initial_cash: float,
    quantity_per_trade: int = 1000,
    fee_rate: float = 0.0,
    tax_rate: float = 0.0,
    slippage_per_share: float = 0.0,
    guard_decision: SimulatedPaperTradingGuardDecision | None = None,
    guard_decision_provider: Callable[[SimulatedOrder, SimulatedPortfolio], SimulatedPaperTradingGuardDecision] | None = None,
) -> SimulatedPortfolio:
    """
    Run a minimal, research-only simulated paper trading engine on historical data.

    This engine does not connect to any external interface, does not create live trades,
    and is strictly for simulated research over standard entry/exit signals.
    """
    if df.empty:
        raise ValueError("DataFrame must not be empty.")
    if not symbol or not symbol.strip():
        raise ValueError("Symbol must not be blank.")
    if initial_cash < 0:
        raise ValueError("initial_cash must be non-negative.")
    if quantity_per_trade <= 0:
        raise ValueError("quantity_per_trade must be positive.")
    if fee_rate < 0 or tax_rate < 0 or slippage_per_share < 0:
        raise ValueError("fee_rate, tax_rate, and slippage_per_share must be non-negative.")
    if "Open" not in df.columns:
        raise ValueError("DataFrame must contain 'Open' column.")
    if guard_decision is not None and guard_decision_provider is not None:
        raise PaperTradingModelError("Cannot provide both guard_decision and guard_decision_provider.")
    if guard_decision is not None and not isinstance(guard_decision, SimulatedPaperTradingGuardDecision):
        raise PaperTradingModelError("guard_decision must be a SimulatedPaperTradingGuardDecision or None.")
    if guard_decision_provider is not None and not callable(guard_decision_provider):
        raise PaperTradingModelError("guard_decision_provider must be callable or None.")

    validate_standard_signals(df)

    portfolio = SimulatedPortfolio(cash=float(initial_cash))

    pending_order: SimulatedOrder | None = None

    for pos, (index_label, row) in enumerate(df.iterrows()):
        open_price = float(row["Open"]) if "Open" in row else float('nan')
        entry_sig = bool(row.get("entry_signal", False))
        exit_sig = bool(row.get("exit_signal", False))

        # Execute pending intent from previous bar (next_bar_open semantics)
        if pending_order is not None:
            if pd.isna(open_price) or open_price <= 0:
                pass # skip fill safely
            else:
                try:
                    fill = SimulatedFill(
                        order_id=pending_order.order_id,
                        symbol=pending_order.symbol,
                        side=pending_order.side,
                        quantity=pending_order.quantity,
                        price=open_price,
                        filled_at=index_label,
                        fee=pending_order.quantity * open_price * fee_rate,
                        tax=pending_order.quantity * open_price * tax_rate if pending_order.side == "SELL" else 0.0,
                        slippage=pending_order.quantity * slippage_per_share,
                    )
                    portfolio.apply_fill(fill)
                except PaperTradingModelError:
                    # e.g., insufficient cash or shares, skip fill
                    pass
            pending_order = None

        pos_model = portfolio.position_for(symbol)
        shares = pos_model.quantity

        if shares > 0 and exit_sig:
            order_id = f"{symbol}-SELL-{pos}"
            candidate_order = SimulatedOrder(
                order_id=order_id,
                symbol=symbol,
                side="SELL",
                quantity=shares,
                signal_time=index_label,
                created_at=index_label,
            )
            if _should_record_order_intent(candidate_order, portfolio, guard_decision, guard_decision_provider):
                pending_order = candidate_order
                portfolio.trade_log.record_order(pending_order)
        elif shares == 0 and entry_sig:
            order_id = f"{symbol}-BUY-{pos}"
            candidate_order = SimulatedOrder(
                order_id=order_id,
                symbol=symbol,
                side="BUY",
                quantity=quantity_per_trade,
                signal_time=index_label,
                created_at=index_label,
            )
            if _should_record_order_intent(candidate_order, portfolio, guard_decision, guard_decision_provider):
                pending_order = candidate_order
                portfolio.trade_log.record_order(pending_order)

    return portfolio


def run_simulated_paper_trading_result(
    df: pd.DataFrame,
    symbol: str,
    initial_cash: float,
    quantity_per_trade: int = 1000,
    fee_rate: float = 0.0,
    tax_rate: float = 0.0,
    slippage_per_share: float = 0.0,
    last_price: float | None = None,
    guard_decision: SimulatedPaperTradingGuardDecision | None = None,
    guard_decision_provider: Callable[[SimulatedOrder, SimulatedPortfolio], SimulatedPaperTradingGuardDecision] | None = None,
) -> SimulatedPaperTradingResult:
    """
    Run simulated paper trading and build a stable summary result object.
    """
    portfolio = run_simulated_paper_trading(
        df=df,
        symbol=symbol,
        initial_cash=initial_cash,
        quantity_per_trade=quantity_per_trade,
        fee_rate=fee_rate,
        tax_rate=tax_rate,
        slippage_per_share=slippage_per_share,
        guard_decision=guard_decision,
        guard_decision_provider=guard_decision_provider,
    )
    return build_simulated_paper_trading_result(
        portfolio=portfolio,
        symbol=symbol,
        initial_cash=initial_cash,
        last_price=last_price,
    )
