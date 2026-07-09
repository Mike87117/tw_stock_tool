"""
Simulated paper trading models.
Research-only simulated models.
"""

from dataclasses import dataclass, field
from typing import Any, Literal


class PaperTradingModelError(Exception):
    pass


@dataclass(slots=True)
class SimulatedOrder:
    """Research-only simulated order intent. Does not connect to a broker."""
    order_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: int
    signal_time: Any
    created_at: Any | None = None
    strategy: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.symbol or not self.symbol.strip():
            raise PaperTradingModelError("Symbol must not be blank.")
        if self.side not in ("BUY", "SELL"):
            raise PaperTradingModelError(f"Invalid side: {self.side}")
        if self.quantity <= 0:
            raise PaperTradingModelError("Quantity must be positive.")


@dataclass(slots=True)
class SimulatedOrderRejection:
    """Research-only rejected simulated order intent."""
    candidate_order: SimulatedOrder
    reasons: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class SimulatedFill:
    """Deterministic simulated fill. Does not represent real execution."""
    order_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: int
    price: float
    filled_at: Any
    fee: float = 0.0
    tax: float = 0.0
    slippage: float = 0.0

    def __post_init__(self) -> None:
        if not self.symbol or not self.symbol.strip():
            raise PaperTradingModelError("Symbol must not be blank.")
        if self.side not in ("BUY", "SELL"):
            raise PaperTradingModelError(f"Invalid side: {self.side}")
        if self.quantity <= 0:
            raise PaperTradingModelError("Quantity must be positive.")
        if self.price <= 0:
            raise PaperTradingModelError("Price must be positive.")
        if self.fee < 0 or self.tax < 0 or self.slippage < 0:
            raise PaperTradingModelError("Fee, tax, and slippage must be non-negative.")

    @property
    def gross_amount(self) -> float:
        return self.quantity * self.price

    @property
    def net_cash_effect(self) -> float:
        """
        BUY consumes cash: quantity * price + fee + slippage
        SELL adds cash: quantity * price - fee - tax - slippage
        Returns negative if cash decreases, positive if cash increases.
        """
        if self.side == "BUY":
            return -(self.gross_amount + self.fee + self.slippage)
        return self.gross_amount - self.fee - self.tax - self.slippage


@dataclass(slots=True)
class SimulatedPosition:
    """Track simulated holdings for one symbol."""
    symbol: str
    quantity: int = 0
    average_cost: float = 0.0
    realized_pnl: float = 0.0

    def apply_fill(self, fill: SimulatedFill) -> None:
        if fill.symbol != self.symbol:
            raise PaperTradingModelError(f"Fill symbol {fill.symbol} does not match position symbol {self.symbol}.")

        if fill.side == "BUY":
            buy_cost = fill.gross_amount + fill.fee + fill.slippage
            total_cost = (self.quantity * self.average_cost) + buy_cost
            self.quantity += fill.quantity
            self.average_cost = total_cost / self.quantity
        else:
            if fill.quantity > self.quantity:
                raise PaperTradingModelError("Cannot sell more than current quantity.")

            proceeds = fill.net_cash_effect
            cost_basis = fill.quantity * self.average_cost
            self.realized_pnl += (proceeds - cost_basis)

            self.quantity -= fill.quantity
            if self.quantity == 0:
                self.average_cost = 0.0

    def market_value(self, last_price: float) -> float:
        return self.quantity * last_price

    def unrealized_pnl(self, last_price: float) -> float:
        return self.market_value(last_price) - (self.quantity * self.average_cost)


@dataclass(slots=True)
class SimulatedTradeLog:
    """Store simulated orders and fills for traceability."""
    orders: list[SimulatedOrder] = field(default_factory=list)
    fills: list[SimulatedFill] = field(default_factory=list)
    rejections: list[SimulatedOrderRejection] = field(default_factory=list)

    def record_order(self, order: SimulatedOrder) -> None:
        self.orders.append(order)

    def record_fill(self, fill: SimulatedFill) -> None:
        self.fills.append(fill)

    def record_rejection(self, rejection: SimulatedOrderRejection) -> None:
        self.rejections.append(rejection)


@dataclass(slots=True)
class SimulatedPortfolio:
    """Track simulated cash, positions, and trade log."""
    cash: float
    positions: dict[str, SimulatedPosition] = field(default_factory=dict)
    trade_log: SimulatedTradeLog = field(default_factory=SimulatedTradeLog)

    def __post_init__(self) -> None:
        if self.cash < 0:
            raise PaperTradingModelError("Initial cash must be non-negative.")

    def apply_fill(self, fill: SimulatedFill) -> None:
        if fill.side == "BUY":
            cash_needed = -fill.net_cash_effect
            if self.cash < cash_needed:
                raise PaperTradingModelError("Insufficient simulated cash for BUY fill.")
        else:
            pos = self.positions.get(fill.symbol)
            if not pos or pos.quantity < fill.quantity:
                raise PaperTradingModelError("Insufficient simulated shares for SELL fill.")

        self.cash += fill.net_cash_effect

        if fill.symbol not in self.positions:
            self.positions[fill.symbol] = SimulatedPosition(symbol=fill.symbol)

        self.positions[fill.symbol].apply_fill(fill)
        self.trade_log.record_fill(fill)

    def position_for(self, symbol: str) -> SimulatedPosition:
        return self.positions.get(symbol, SimulatedPosition(symbol=symbol))

    def total_position_value(self, last_prices: dict[str, float]) -> float:
        total = 0.0
        for symbol, pos in self.positions.items():
            if pos.quantity > 0:
                if symbol not in last_prices:
                    raise PaperTradingModelError(f"Missing last price for open position: {symbol}")
                total += pos.market_value(last_prices[symbol])
        return total

    def total_equity(self, last_prices: dict[str, float]) -> float:
        return self.cash + self.total_position_value(last_prices)
