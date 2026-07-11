import pandas as pd
from typing import Any, Callable, Mapping

from tw_stock_tool.backtesting.signals import validate_standard_signals
from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedOrder,
    SimulatedPortfolio,
)
from tw_stock_tool.paper_trading.runtime import SimulatedPaperTradingRuntimeState
from tw_stock_tool.paper_trading.results import (
    SimulatedPaperTradingResult,
    build_simulated_paper_trading_result,
)
from tw_stock_tool.simulated_paper_trading_guard.models import SimulatedPaperTradingGuardDecision
from tw_stock_tool.paper_trading.stepper import step_simulated_symbol_bar


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
    strategy: str | None = None,
    strategy_metadata: Mapping[str, Any] | None = None,
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

    runtime_state = SimulatedPaperTradingRuntimeState(
        portfolio=SimulatedPortfolio(cash=float(initial_cash))
    )

    for pos, (index_label, row) in enumerate(df.iterrows()):
        open_price = float(row["Open"]) if "Open" in row else float('nan')
        entry_sig = bool(row.get("entry_signal", False))
        exit_sig = bool(row.get("exit_signal", False))

        step_simulated_symbol_bar(
            runtime_state=runtime_state,
            symbol=symbol,
            bar_position=pos,
            index_label=index_label,
            open_price=open_price,
            entry_signal=entry_sig,
            exit_signal=exit_sig,
            quantity_per_trade=quantity_per_trade,
            fee_rate=fee_rate,
            tax_rate=tax_rate,
            slippage_per_share=slippage_per_share,
            guard_decision=guard_decision,
            guard_decision_provider=guard_decision_provider,
            strategy=strategy,
            strategy_metadata=strategy_metadata,
        )

    return runtime_state.portfolio


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
    strategy: str | None = None,
    strategy_metadata: Mapping[str, Any] | None = None,
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
        strategy=strategy,
        strategy_metadata=strategy_metadata,
    )
    return build_simulated_paper_trading_result(
        portfolio=portfolio,
        symbol=symbol,
        initial_cash=initial_cash,
        last_price=last_price,
    )
