"""
Simulated paper trading models.
Research-only simulated models.
"""

from dataclasses import dataclass, field
from enum import StrEnum
import json
import math
from numbers import Real
from types import MappingProxyType
from typing import Any, Literal, Mapping


class PaperTradingModelError(Exception):
    pass


class SimulatedTradeEventType(StrEnum):
    """Canonical simulated-order lifecycle event vocabulary."""

    CANDIDATE_CREATED = "candidate_created"
    RISK_EVALUATED = "risk_evaluated"
    ACCEPTED_PENDING = "accepted_pending"
    REJECTED = "rejected"
    FILLED = "filled"
    FILL_SKIPPED = "fill_skipped"
    FILL_FAILED = "fill_failed"
    EXECUTION_ERROR = "execution_error"


class SimulatedTradeStatus(StrEnum):
    """State reached by a canonical simulated trade-log event."""

    CANDIDATE = "candidate"
    RISK_ALLOWED = "risk_allowed"
    RISK_REJECTED = "risk_rejected"
    PENDING_NEXT_BAR_OPEN = "pending_next_bar_open"
    REJECTED = "rejected"
    FILLED = "filled"
    SKIPPED_INVALID_OPEN = "skipped_invalid_open"
    FAILED_PORTFOLIO_VALIDATION = "failed_portfolio_validation"
    EXECUTION_ERROR = "execution_error"


@dataclass(frozen=True, slots=True)
class SimulatedTradeLogRecord:
    """Immutable audit event for an offline simulated order lifecycle."""

    sequence: int
    record_id: str
    event_type: SimulatedTradeEventType
    status: SimulatedTradeStatus
    order_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: int
    signal_time: Any
    order_created_at: Any | None
    expected_execution_model: Literal["next_bar_open"] = "next_bar_open"
    fill_time: Any | None = None
    fill_price: float | None = None
    fee: float = 0.0
    tax: float = 0.0
    slippage: float = 0.0
    strategy_name: str | None = None
    strategy_metadata: Mapping[str, Any] = field(default_factory=dict)
    risk_allowed: bool | None = None
    risk_rejection_reasons: tuple[str, ...] = ()
    guard_metadata: Mapping[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence <= 0:
            raise PaperTradingModelError("Trade-log sequence must be a positive integer.")
        if not isinstance(self.record_id, str) or not self.record_id.strip():
            raise PaperTradingModelError("Trade-log record_id must not be blank.")
        if not isinstance(self.event_type, SimulatedTradeEventType):
            raise PaperTradingModelError("Invalid trade-log event type.")
        if not isinstance(self.status, SimulatedTradeStatus):
            raise PaperTradingModelError("Invalid trade-log status.")
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise PaperTradingModelError("Symbol must not be blank.")
        if self.side not in ("BUY", "SELL"):
            raise PaperTradingModelError(f"Invalid side: {self.side}")
        if isinstance(self.quantity, bool) or not isinstance(self.quantity, int) or self.quantity <= 0:
            raise PaperTradingModelError("Quantity must be a positive integer.")
        if self.expected_execution_model != "next_bar_open":
            raise PaperTradingModelError("Expected execution model must be next_bar_open.")
        for name in ("fill_price", "fee", "tax", "slippage"):
            value = getattr(self, name)
            if value is None and name == "fill_price":
                continue
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
                raise PaperTradingModelError(f"{name} must be finite numeric data.")
            if (name == "fill_price" and float(value) <= 0) or (name != "fill_price" and float(value) < 0):
                raise PaperTradingModelError(f"{name} has an invalid value.")
        if self.risk_allowed is not None and type(self.risk_allowed) is not bool:
            raise PaperTradingModelError("risk_allowed must be a bool or None.")
        if not isinstance(self.risk_rejection_reasons, tuple) or not all(
            isinstance(reason, str) and reason.strip() for reason in self.risk_rejection_reasons
        ):
            raise PaperTradingModelError("risk_rejection_reasons must contain non-blank strings.")
        for name in ("strategy_metadata", "guard_metadata"):
            value = getattr(self, name)
            if not isinstance(value, Mapping):
                raise PaperTradingModelError(f"{name} must be a mapping.")
            try:
                copied = json.loads(json.dumps(dict(value), allow_nan=False))
            except (TypeError, ValueError):
                raise PaperTradingModelError(f"{name} must be JSON serializable.") from None
            object.__setattr__(self, name, MappingProxyType(copied))


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
    records: list[SimulatedTradeLogRecord] = field(default_factory=list)

    def record_order(self, order: SimulatedOrder) -> None:
        self.orders.append(order)

    def record_fill(self, fill: SimulatedFill) -> None:
        self.fills.append(fill)

    def record_rejection(self, rejection: SimulatedOrderRejection) -> None:
        self.rejections.append(rejection)

    def record_event(
        self,
        order: SimulatedOrder,
        event_type: SimulatedTradeEventType,
        status: SimulatedTradeStatus,
        **details: Any,
    ) -> SimulatedTradeLogRecord:
        """Append one deterministically sequenced lifecycle event."""
        sequence = len(self.records) + 1
        record = SimulatedTradeLogRecord(
            sequence=sequence,
            record_id=f"audit-{sequence:06d}",
            event_type=event_type,
            status=status,
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            signal_time=order.signal_time,
            order_created_at=order.created_at,
            strategy_name=order.strategy,
            strategy_metadata=order.metadata,
            **details,
        )
        self.records.append(record)
        return record


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
