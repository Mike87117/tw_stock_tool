"""
Pure, reusable module facade for multi-symbol simulated portfolio paper trading execution.
"""

import math
from numbers import Real
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


from tw_stock_tool.risk.config import SimulatedPaperTradingRiskConfig
from tw_stock_tool.simulated_paper_trading_guard.builder import (
    build_guard_decision_provider_from_config,
)
from tw_stock_tool.simulated_paper_trading_guard.config import (
    SimulatedPaperTradingGuardConfig,
)
from tw_stock_tool.simulated_paper_trading_guard.providers import (
    ChronologicalRuntimePortfolioExposureProvider,
    MultiSymbolDataFrameReferencePriceProvider,
)


def _require_finite_number(
    name: str,
    value: object,
    *,
    non_negative: bool = False,
    strictly_positive: bool = False,
) -> float:
    if isinstance(value, bool) or type(value).__name__ in ("bool", "bool_") or not isinstance(value, Real):
        raise PaperTradingModelError(f"{name} must be finite numeric data.")

    try:
        numeric = float(value)
    except (OverflowError, TypeError, ValueError):
        raise PaperTradingModelError(f"{name} must be finite numeric data.") from None

    if not math.isfinite(numeric):
        raise PaperTradingModelError(f"{name} must be finite numeric data.")

    if non_negative and numeric < 0:
        raise PaperTradingModelError(f"{name} must be non-negative.")

    if strictly_positive and numeric <= 0:
        raise PaperTradingModelError(f"{name} must be strictly positive.")

    return numeric


def _normalize_optional_risk_notional(name: str, value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or type(value).__name__ in ("bool", "bool_"):
        raise PaperTradingModelError(f"{name} must be numeric, not boolean.")
    if type(value) not in (int, float):
        raise PaperTradingModelError(f"{name} must be an integer or float.")
    try:
        numeric = float(value)
    except (OverflowError, TypeError, ValueError):
        raise PaperTradingModelError(
            f"{name} must be a finite strictly positive integer or float."
        ) from None
    if not math.isfinite(numeric) or numeric <= 0.0:
        raise PaperTradingModelError(
            f"{name} must be a finite strictly positive integer or float."
        )
    return numeric


def _normalize_optional_risk_quantity(name: str, value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or type(value).__name__ in ("bool", "bool_"):
        raise PaperTradingModelError(f"{name} must be an integer, not boolean.")
    if type(value) is not int:
        raise PaperTradingModelError(f"{name} must be a positive integer.")
    if value <= 0:
        raise PaperTradingModelError(f"{name} must be a positive integer.")
    return value


def _build_composite_guard_decision_provider(
    *,
    portfolio_risk_provider: Callable[[SimulatedOrder, SimulatedPortfolio], SimulatedPaperTradingGuardDecision],
    fixed_guard_decision: SimulatedPaperTradingGuardDecision | None = None,
    custom_guard_decision_provider: Callable[[SimulatedOrder, SimulatedPortfolio], SimulatedPaperTradingGuardDecision] | None = None,
) -> Callable[[SimulatedOrder, SimulatedPortfolio], SimulatedPaperTradingGuardDecision]:
    if not callable(portfolio_risk_provider):
        raise ValueError("portfolio_risk_provider must be callable.")
    if fixed_guard_decision is not None and not isinstance(fixed_guard_decision, SimulatedPaperTradingGuardDecision):
        raise ValueError("fixed_guard_decision must be a SimulatedPaperTradingGuardDecision or None.")
    if custom_guard_decision_provider is not None and not callable(custom_guard_decision_provider):
        raise ValueError("custom_guard_decision_provider must be callable or None.")

    if fixed_guard_decision is not None and custom_guard_decision_provider is not None:
        raise ValueError("Cannot provide both guard_decision and guard_decision_provider.")

    def composite_provider(order: SimulatedOrder, portfolio: SimulatedPortfolio) -> SimulatedPaperTradingGuardDecision:
        sources: list[tuple[str, Callable[[SimulatedOrder, SimulatedPortfolio], SimulatedPaperTradingGuardDecision]]] = []

        if fixed_guard_decision is not None:
            sources.append(("fixed_guard", lambda _ord, _port: fixed_guard_decision))

        sources.append(("portfolio_risk_guard", portfolio_risk_provider))

        if custom_guard_decision_provider is not None:
            sources.append(("custom_guard", custom_guard_decision_provider))

        decisions: list[tuple[str, SimulatedPaperTradingGuardDecision]] = []
        for name, provider in sources:
            dec = provider(order, portfolio)
            if not isinstance(dec, SimulatedPaperTradingGuardDecision):
                raise PaperTradingModelError(f"Guard provider '{name}' returned invalid decision type.")
            decisions.append((name, dec))

        all_allowed = all(dec.is_allowed for _, dec in decisions)

        combined_metadata: dict[str, Any] = {
            name: dict(dec.metadata)
            for name, dec in decisions
        }

        if all_allowed:
            return SimulatedPaperTradingGuardDecision.allow(metadata=combined_metadata)

        combined_reasons: list[str] = []
        seen_reasons: set[str] = set()
        for _, dec in decisions:
            if not dec.is_allowed and dec.reasons:
                for reason in dec.reasons:
                    if reason not in seen_reasons:
                        seen_reasons.add(reason)
                        combined_reasons.append(reason)

        return SimulatedPaperTradingGuardDecision.block(
            reasons=combined_reasons,
            metadata=combined_metadata,
        )

    return composite_provider


def run_simulated_portfolio_trading_result(
    dataframes: Mapping[str, pd.DataFrame],
    *,
    initial_cash: float,
    last_prices: Mapping[str, float],
    quantity_per_trade: int = 1000,
    fee_rate: float = 0.0,
    tax_rate: float = 0.0,
    slippage_per_share: float = 0.0,
    max_order_notional: float | None = None,
    max_position_quantity: int | None = None,
    max_position_notional: float | None = None,
    max_total_exposure: float | None = None,
    guard_decision: SimulatedPaperTradingGuardDecision | None = None,
    guard_decision_provider: Callable[
        [SimulatedOrder, SimulatedPortfolio],
        SimulatedPaperTradingGuardDecision,
    ] | None = None,
    strategy: str | None = None,
    strategy_metadata: Mapping[str, Any] | None = None,
    _after_timestamp: Callable[
        [Any, SimulatedPaperTradingRuntimeState, Mapping[str, Any]], None
    ] | None = None,
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
        _require_finite_number(f"last_price for '{sym}'", price, strictly_positive=True)

    init_cash_float = _require_finite_number("initial_cash", initial_cash, non_negative=True)

    if isinstance(quantity_per_trade, bool) or type(quantity_per_trade).__name__ in ("bool", "bool_") or type(quantity_per_trade) is not int:
        raise PaperTradingModelError("quantity_per_trade must be an integer.")
    if quantity_per_trade <= 0:
        raise PaperTradingModelError("quantity_per_trade must be a positive integer.")

    fee_rate_float = _require_finite_number("fee_rate", fee_rate, non_negative=True)
    tax_rate_float = _require_finite_number("tax_rate", tax_rate, non_negative=True)
    slippage_float = _require_finite_number("slippage_per_share", slippage_per_share, non_negative=True)

    max_order_notional_float = _normalize_optional_risk_notional("max_order_notional", max_order_notional)
    max_position_quantity_int = _normalize_optional_risk_quantity("max_position_quantity", max_position_quantity)
    max_position_notional_float = _normalize_optional_risk_notional("max_position_notional", max_position_notional)
    max_total_exposure_float = _normalize_optional_risk_notional("max_total_exposure", max_total_exposure)

    risk_enabled = any(
        v is not None
        for v in (
            max_order_notional_float,
            max_position_quantity_int,
            max_position_notional_float,
            max_total_exposure_float,
        )
    )

    portfolio = SimulatedPortfolio(cash=init_cash_float)
    runtime_state = SimulatedPaperTradingRuntimeState(portfolio=portfolio)

    if risk_enabled:
        risk_config = SimulatedPaperTradingRiskConfig(
            max_order_notional=max_order_notional_float,
            max_position_quantity=max_position_quantity_int,
            max_position_notional=max_position_notional_float,
            max_total_exposure=max_total_exposure_float,
        )
        guard_config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        ref_provider = MultiSymbolDataFrameReferencePriceProvider(dataframes, price_column="Open")

        exp_provider = (
            ChronologicalRuntimePortfolioExposureProvider(
                dataframes,
                runtime_state,
                price_column="Open",
            )
            if max_total_exposure_float is not None
            else None
        )

        built_risk_provider = build_guard_decision_provider_from_config(
            guard_config,
            reference_price_provider=ref_provider,
            portfolio_exposure_provider=exp_provider,
        )

        def portfolio_risk_provider(order: SimulatedOrder, port: SimulatedPortfolio) -> SimulatedPaperTradingGuardDecision:
            if not isinstance(order, SimulatedOrder):
                raise PaperTradingModelError("order must be a SimulatedOrder.")
            if not isinstance(port, SimulatedPortfolio):
                raise PaperTradingModelError("portfolio must be a SimulatedPortfolio.")
            if order.side == "SELL":
                return SimulatedPaperTradingGuardDecision.allow(
                    metadata={
                        "sell_bypass": True,
                        "side": "SELL",
                    }
                )
            return built_risk_provider(order, port)

        effective_guard_decision = None
        effective_guard_decision_provider = _build_composite_guard_decision_provider(
            portfolio_risk_provider=portfolio_risk_provider,
            fixed_guard_decision=guard_decision,
            custom_guard_decision_provider=guard_decision_provider,
        )
    else:
        effective_guard_decision = guard_decision
        effective_guard_decision_provider = guard_decision_provider

    run_chronological_multi_symbol_simulated_paper_trading(
        dataframes,
        runtime_state,
        quantity_per_trade=quantity_per_trade,
        fee_rate=fee_rate_float,
        tax_rate=tax_rate_float,
        slippage_per_share=slippage_float,
        guard_decision=effective_guard_decision,
        guard_decision_provider=effective_guard_decision_provider,
        strategy=strategy,
        strategy_metadata=strategy_metadata,
        _after_timestamp=_after_timestamp,
    )

    return build_simulated_portfolio_trading_result(
        runtime_state,
        initial_cash=init_cash_float,
        last_prices=last_prices,
    )
