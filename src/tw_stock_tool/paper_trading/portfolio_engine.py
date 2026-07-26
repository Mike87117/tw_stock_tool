"""
Pure, reusable module facade for multi-symbol simulated portfolio paper trading execution.
"""

import math
from typing import Any, Callable, Mapping
import pandas as pd

from tw_stock_tool.paper_trading.coordinator import (
    run_chronological_multi_symbol_simulated_paper_trading,
)
from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedOrder,
    SimulatedPortfolio,
)
from tw_stock_tool.paper_trading.portfolio_results import (
    SimulatedPortfolioTradingResult,
    build_simulated_portfolio_trading_result,
)
from tw_stock_tool.paper_trading.runtime import (
    SimulatedPaperTradingRuntimeState,
)
from tw_stock_tool.simulated_paper_trading_guard.adapter import (
    SimulatedPaperTradingGuardDecision,
)


def _require_finite_non_negative_rate(name: str, value: Any) -> float:
    if isinstance(value, bool) or type(value).__name__ in ("bool", "bool_"):
        raise PaperTradingModelError(f"{name} must not be boolean.")
    try:
        fval = float(value)
    except (ValueError, TypeError):
        raise PaperTradingModelError(f"{name} must be numeric.") from None
    if math.isnan(fval) or math.isinf(fval):
        raise PaperTradingModelError(f"{name} must be finite.")
    if fval < 0:
        raise PaperTradingModelError(f"{name} must be non-negative.")
    return fval


def run_simulated_portfolio_trading_result(
    dataframes: Mapping[str, pd.DataFrame],
    *,
    initial_cash: float,
    last_prices: Mapping[str, float],
    quantity_per_trade: int = 1000,
    fee_rate: float = 0.0,
    tax_rate: float = 0.0,
    slippage_per_share: float = 0.0,
    guard_decision: SimulatedPaperTradingGuardDecision | None = None,
    guard_decision_provider: Callable[
        [SimulatedOrder, SimulatedPortfolio],
        SimulatedPaperTradingGuardDecision,
    ] | None = None,
    strategy: str | None = None,
    strategy_metadata: Mapping[str, Any] | None = None,
) -> SimulatedPortfolioTradingResult:
    """Execute multi-symbol historical paper trading and build an aggregate result object."""
    if not isinstance(dataframes, Mapping):
        raise PaperTradingModelError("dataframes must be a Mapping.")
    if not dataframes:
        raise PaperTradingModelError("dataframes must not be empty.")

    for symbol, df in dataframes.items():
        if not isinstance(symbol, str) or not symbol.strip():
            raise PaperTradingModelError("Every symbol key must be a non-blank string.")
        if not isinstance(df, pd.DataFrame):
            raise PaperTradingModelError("Every dataframe value must be a pandas DataFrame.")
        if df.empty:
            raise PaperTradingModelError("DataFrames must not be empty.")

    if not isinstance(last_prices, Mapping):
        raise PaperTradingModelError("last_prices must be a Mapping.")
    if set(last_prices.keys()) != set(dataframes.keys()):
        raise PaperTradingModelError("last_prices keys must match dataframes keys exactly.")

    for sym, price in last_prices.items():
        if isinstance(price, bool) or type(price).__name__ in ("bool", "bool_"):
            raise PaperTradingModelError(f"last_price for '{sym}' must not be boolean.")
        try:
            fprice = float(price)
        except (ValueError, TypeError):
            raise PaperTradingModelError(f"last_price for '{sym}' must be numeric.") from None
        if math.isnan(fprice) or math.isinf(fprice):
            raise PaperTradingModelError(f"last_price for '{sym}' must be finite.")
        if fprice <= 0:
            raise PaperTradingModelError(f"last_price for '{sym}' must be strictly positive.")

    init_cash_float = _require_finite_non_negative_rate("initial_cash", initial_cash)

    if isinstance(quantity_per_trade, bool) or type(quantity_per_trade).__name__ in ("bool", "bool_"):
        raise PaperTradingModelError("quantity_per_trade must not be boolean.")
    if not isinstance(quantity_per_trade, int):
        raise PaperTradingModelError("quantity_per_trade must be an integer.")
    if quantity_per_trade <= 0:
        raise PaperTradingModelError("quantity_per_trade must be a positive integer.")

    fee_rate_float = _require_finite_non_negative_rate("fee_rate", fee_rate)
    tax_rate_float = _require_finite_non_negative_rate("tax_rate", tax_rate)
    slippage_float = _require_finite_non_negative_rate("slippage_per_share", slippage_per_share)

    portfolio = SimulatedPortfolio(cash=init_cash_float)
    runtime_state = SimulatedPaperTradingRuntimeState(portfolio=portfolio)

    run_chronological_multi_symbol_simulated_paper_trading(
        dataframes,
        runtime_state,
        quantity_per_trade=quantity_per_trade,
        fee_rate=fee_rate_float,
        tax_rate=tax_rate_float,
        slippage_per_share=slippage_float,
        guard_decision=guard_decision,
        guard_decision_provider=guard_decision_provider,
        strategy=strategy,
        strategy_metadata=strategy_metadata,
    )

    return build_simulated_portfolio_trading_result(
        runtime_state,
        initial_cash=init_cash_float,
        last_prices=last_prices,
    )
