import math
import pandas as pd
from typing import Mapping, Callable

from tw_stock_tool.backtesting.signals import validate_standard_signals
from tw_stock_tool.paper_trading.models import SimulatedOrder, SimulatedPortfolio
from tw_stock_tool.paper_trading.runtime import SimulatedPaperTradingRuntimeState
from tw_stock_tool.simulated_paper_trading_guard.adapter import SimulatedPaperTradingGuardDecision
from tw_stock_tool.paper_trading.stepper import (
    step_simulated_symbol_bar,
    process_simulated_pending_fill,
    build_simulated_symbol_candidate_order,
    evaluate_and_record_simulated_candidate,
)


def run_chronological_multi_symbol_simulated_paper_trading(
    dataframes: Mapping[str, pd.DataFrame],
    runtime_state: SimulatedPaperTradingRuntimeState,
    *,
    quantity_per_trade: int = 1000,
    fee_rate: float = 0.0,
    tax_rate: float = 0.0,
    slippage_per_share: float = 0.0,
    guard_decision: SimulatedPaperTradingGuardDecision | None = None,
    guard_decision_provider: Callable[
        [SimulatedOrder, SimulatedPortfolio],
        SimulatedPaperTradingGuardDecision,
    ] | None = None,
) -> SimulatedPaperTradingRuntimeState:
    if not isinstance(dataframes, Mapping):
        raise TypeError("dataframes must be a Mapping.")
    if not dataframes:
        raise ValueError("dataframes must not be empty.")

    for symbol, df in dataframes.items():
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Every symbol key must be a non-blank string.")
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Value for {symbol} must be a pandas DataFrame.")
        if df.empty:
            raise ValueError(f"DataFrame for {symbol} must not be empty.")
        if "Open" not in df.columns:
            raise ValueError(f"DataFrame for {symbol} must contain 'Open'.")

        validate_standard_signals(df)

        if not df.index.is_unique:
            raise ValueError(f"DataFrame index for {symbol} must be unique.")
        if not df.index.is_monotonic_increasing:
            raise ValueError(f"DataFrame index for {symbol} must be monotonic increasing.")

    if not isinstance(runtime_state, SimulatedPaperTradingRuntimeState):
        raise TypeError("runtime_state must be a SimulatedPaperTradingRuntimeState.")

    if type(quantity_per_trade) is bool or type(quantity_per_trade).__name__ in ("bool", "bool_"):
        raise TypeError("quantity_per_trade must be an integer, not boolean.")
    if not isinstance(quantity_per_trade, int):
        raise TypeError("quantity_per_trade must be an integer.")
    if quantity_per_trade <= 0:
        raise ValueError("quantity_per_trade must be positive.")

    for name, val in [
        ("fee_rate", fee_rate),
        ("tax_rate", tax_rate),
        ("slippage_per_share", slippage_per_share)
    ]:
        if type(val) is bool or type(val).__name__ in ("bool", "bool_"):
            raise TypeError(f"{name} must be numeric, not boolean.")
        try:
            val_f = float(val)
        except (ValueError, TypeError):
            raise TypeError(f"{name} must be numeric.")
        if not math.isfinite(val_f):
            raise ValueError(f"{name} must be finite.")
        if val_f < 0.0:
            raise ValueError(f"{name} must be non-negative.")

    if guard_decision is not None and guard_decision_provider is not None:
        raise ValueError("Cannot provide both guard_decision and guard_decision_provider.")
    if guard_decision is not None and not isinstance(guard_decision, SimulatedPaperTradingGuardDecision):
        raise TypeError("guard_decision must be a SimulatedPaperTradingGuardDecision or None.")
    if guard_decision_provider is not None and not callable(guard_decision_provider):
        raise TypeError("guard_decision_provider must be callable or None.")

    timeline_set = set()
    for symbol, df in dataframes.items():
        try:
            timeline_set.update(df.index.tolist())
        except TypeError as e:
            raise TypeError("Index labels are not comparable across symbols") from e

    try:
        timeline = sorted(list(timeline_set))
    except TypeError as e:
        raise TypeError("Mixed index types cannot be compared globally.") from e

    cursors = {sym: 0 for sym in dataframes}
    deterministic_symbols = sorted(dataframes.keys())

    for t in timeline:
        symbols_at_t = []
        for symbol in deterministic_symbols:
            pos = cursors[symbol]
            df = dataframes[symbol]
            if pos < len(df) and df.index[pos] == t:
                symbols_at_t.append(symbol)

        # Pass 1: Pending Fills
        for symbol in symbols_at_t:
            pos = cursors[symbol]
            df = dataframes[symbol]
            row = df.iloc[pos]
            open_price = row["Open"] if "Open" in row else float('nan')

            process_simulated_pending_fill(
                runtime_state=runtime_state,
                symbol=symbol,
                open_price=open_price,
                index_label=t,
                fee_rate=float(fee_rate),
                tax_rate=float(tax_rate),
                slippage_per_share=float(slippage_per_share),
            )

        # Pass 2 & 3: Build Candidates and Evaluate
        for symbol in symbols_at_t:
            pos = cursors[symbol]
            df = dataframes[symbol]
            row = df.iloc[pos]
            open_price = row["Open"] if "Open" in row else float('nan')
            entry_sig = bool(row.get("entry_signal", False))
            exit_sig = bool(row.get("exit_signal", False))

            candidate = build_simulated_symbol_candidate_order(
                runtime_state=runtime_state,
                symbol=symbol,
                bar_position=pos,
                index_label=t,
                open_price=open_price,
                entry_signal=entry_sig,
                exit_signal=exit_sig,
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

            # Advance cursor
            cursors[symbol] += 1

    return runtime_state
