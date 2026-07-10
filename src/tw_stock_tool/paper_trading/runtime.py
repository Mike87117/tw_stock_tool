"""Pure runtime-state models for simulated paper trading."""

from dataclasses import dataclass, field
import math
from numbers import Real

from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedOrder,
    SimulatedPortfolio,
)


@dataclass(slots=True)
class SimulatedPendingOrderState:
    """A pending simulated order and its accepted reference price."""

    order: SimulatedOrder
    reference_price: float

    def __post_init__(self) -> None:
        if not isinstance(self.order, SimulatedOrder):
            raise PaperTradingModelError("order must be a SimulatedOrder.")
        if isinstance(self.reference_price, bool) or not isinstance(
            self.reference_price, Real
        ):
            raise PaperTradingModelError("reference_price must be numeric.")

        price = float(self.reference_price)
        if not math.isfinite(price) or price <= 0.0:
            raise PaperTradingModelError(
                "reference_price must be finite and strictly positive."
            )
        self.reference_price = price

    @property
    def reserved_buy_notional(self) -> float:
        if self.order.side == "BUY":
            return float(self.order.quantity * self.reference_price)
        return 0.0


@dataclass(slots=True)
class SimulatedPaperTradingRuntimeState:
    """Shared simulated portfolio and per-symbol pending order state."""

    portfolio: SimulatedPortfolio
    pending_orders: dict[str, SimulatedPendingOrderState] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not isinstance(self.portfolio, SimulatedPortfolio):
            raise PaperTradingModelError("portfolio must be a SimulatedPortfolio.")
        if not isinstance(self.pending_orders, dict):
            raise PaperTradingModelError("pending_orders must be a dictionary.")

        for symbol, state in self.pending_orders.items():
            if not isinstance(symbol, str) or not symbol.strip():
                raise PaperTradingModelError(
                    "pending_orders keys must be non-blank strings."
                )
            if not isinstance(state, SimulatedPendingOrderState):
                raise PaperTradingModelError(
                    "pending_orders values must be SimulatedPendingOrderState objects."
                )
            if symbol != state.order.symbol:
                raise PaperTradingModelError(
                    "pending_orders key must match the pending order symbol."
                )

    @property
    def total_reserved_buy_notional(self) -> float:
        return float(
            sum(
                state.reserved_buy_notional
                for state in self.pending_orders.values()
            )
        )
