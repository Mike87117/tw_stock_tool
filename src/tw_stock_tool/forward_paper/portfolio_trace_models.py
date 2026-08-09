"""Immutable same-pass portfolio observations for trusted forward replay."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from numbers import Real
import re
from uuid import UUID


class ForwardPortfolioTraceModelError(ValueError):
    """Raised when a forward portfolio trace violates schema 1.0."""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _clean_string(name: str, value: object) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ForwardPortfolioTraceModelError(
            f"{name} must be an exact clean non-empty string"
        )
    return value


def _uuid(name: str, value: object) -> str:
    clean = _clean_string(name, value)
    try:
        parsed = UUID(clean)
    except ValueError as exc:
        raise ForwardPortfolioTraceModelError(
            f"{name} must be a canonical lowercase UUID v4"
        ) from exc
    if parsed.version != 4 or str(parsed) != clean:
        raise ForwardPortfolioTraceModelError(
            f"{name} must be a canonical lowercase UUID v4"
        )
    return clean


def _sha(name: str, value: object) -> str:
    clean = _clean_string(name, value)
    if _SHA256.fullmatch(clean) is None:
        raise ForwardPortfolioTraceModelError(
            f"{name} must be a lowercase SHA-256"
        )
    return clean


def _timestamp(name: str, value: object) -> str:
    clean = _clean_string(name, value)
    try:
        parsed = datetime.strptime(clean, _TIMESTAMP_FORMAT)
    except ValueError as exc:
        raise ForwardPortfolioTraceModelError(
            f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
        ) from exc
    if parsed.strftime(_TIMESTAMP_FORMAT) != clean:
        raise ForwardPortfolioTraceModelError(
            f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
        )
    return clean


def _non_negative_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ForwardPortfolioTraceModelError(
            f"{name} must be finite numeric data"
        )
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ForwardPortfolioTraceModelError(
            f"{name} must be finite numeric data"
        ) from exc
    if not math.isfinite(number) or number < 0.0:
        raise ForwardPortfolioTraceModelError(
            f"{name} must be finite and non-negative"
        )
    return number


def _count(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ForwardPortfolioTraceModelError(
            f"{name} must be a non-negative exact int"
        )
    return value


@dataclass(frozen=True, slots=True)
class ForwardPortfolioPositionMark:
    symbol: str
    quantity: int
    mark_price: float
    market_value: float

    def __post_init__(self) -> None:
        _clean_string("symbol", self.symbol)
        if type(self.quantity) is not int or self.quantity <= 0:
            raise ForwardPortfolioTraceModelError(
                "quantity must be a positive exact int"
            )
        mark_price = _non_negative_number("mark_price", self.mark_price)
        if mark_price <= 0.0:
            raise ForwardPortfolioTraceModelError(
                "mark_price must be strictly positive"
            )
        market_value = _non_negative_number("market_value", self.market_value)
        if self.quantity * mark_price != market_value:
            raise ForwardPortfolioTraceModelError(
                "market_value must equal quantity * mark_price"
            )
        object.__setattr__(self, "mark_price", mark_price)
        object.__setattr__(self, "market_value", market_value)


@dataclass(frozen=True, slots=True)
class ForwardPortfolioObservation:
    observed_at: str
    cash: float
    total_market_value: float
    total_equity: float
    open_position_count: int
    pending_order_count: int
    reserved_buy_notional: float
    positions: tuple[ForwardPortfolioPositionMark, ...]

    def __post_init__(self) -> None:
        _timestamp("observed_at", self.observed_at)
        cash = _non_negative_number("cash", self.cash)
        market_value = _non_negative_number(
            "total_market_value", self.total_market_value
        )
        equity = _non_negative_number("total_equity", self.total_equity)
        reserved = _non_negative_number(
            "reserved_buy_notional", self.reserved_buy_notional
        )
        open_count = _count("open_position_count", self.open_position_count)
        pending_count = _count("pending_order_count", self.pending_order_count)
        if type(self.positions) is not tuple or any(
            type(item) is not ForwardPortfolioPositionMark for item in self.positions
        ):
            raise ForwardPortfolioTraceModelError(
                "positions must be an exact tuple of position marks"
            )
        symbols = tuple(item.symbol for item in self.positions)
        if symbols != tuple(sorted(symbols)) or len(set(symbols)) != len(symbols):
            raise ForwardPortfolioTraceModelError(
                "position symbols must be unique and canonically sorted"
            )
        if open_count != len(self.positions):
            raise ForwardPortfolioTraceModelError(
                "open_position_count must equal len(positions)"
            )
        if sum(item.market_value for item in self.positions) != market_value:
            raise ForwardPortfolioTraceModelError(
                "total_market_value must equal the position market-value sum"
            )
        if cash + market_value != equity:
            raise ForwardPortfolioTraceModelError(
                "total_equity must equal cash + total_market_value"
            )
        if pending_count == 0 and reserved != 0.0:
            raise ForwardPortfolioTraceModelError(
                "reserved_buy_notional requires a pending order"
            )
        object.__setattr__(self, "cash", cash)
        object.__setattr__(self, "total_market_value", market_value)
        object.__setattr__(self, "total_equity", equity)
        object.__setattr__(self, "reserved_buy_notional", reserved)


@dataclass(frozen=True, slots=True)
class ForwardPortfolioTrace:
    schema_version: str
    artifact_type: str
    activation_id: str
    qualification_evaluation_id: str
    qualification_sha256: str
    ledger_id: str
    ledger_sha256: str
    strategy_id: str
    initial_equity: float
    portfolio_result_sha256: str
    observations: tuple[ForwardPortfolioObservation, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise ForwardPortfolioTraceModelError("schema_version must be '1.0'")
        if self.artifact_type != "forward_portfolio_trace":
            raise ForwardPortfolioTraceModelError("artifact_type is not supported")
        for name in ("activation_id", "qualification_evaluation_id", "ledger_id"):
            _uuid(name, getattr(self, name))
        for name in (
            "qualification_sha256",
            "ledger_sha256",
            "portfolio_result_sha256",
        ):
            _sha(name, getattr(self, name))
        _clean_string("strategy_id", self.strategy_id)
        object.__setattr__(
            self,
            "initial_equity",
            _non_negative_number("initial_equity", self.initial_equity),
        )
        if type(self.observations) is not tuple or not self.observations or any(
            type(item) is not ForwardPortfolioObservation
            for item in self.observations
        ):
            raise ForwardPortfolioTraceModelError(
                "observations must be a non-empty exact tuple"
            )
        timestamps = tuple(item.observed_at for item in self.observations)
        if timestamps != tuple(sorted(timestamps)) or len(set(timestamps)) != len(
            timestamps
        ):
            raise ForwardPortfolioTraceModelError(
                "observation timestamps must be unique and strictly chronological"
            )


__all__ = [
    "ForwardPortfolioObservation",
    "ForwardPortfolioPositionMark",
    "ForwardPortfolioTrace",
    "ForwardPortfolioTraceModelError",
]
