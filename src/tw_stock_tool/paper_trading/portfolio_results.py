"""
Multi-symbol simulated portfolio results.
"""

from dataclasses import dataclass
import math
from numbers import Real
from typing import Any, Literal, Mapping

from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedFill,
    SimulatedOrder,
    SimulatedOrderRejection,
    SimulatedPosition,
    SimulatedTradeLogRecord,
    SimulatedPortfolio,
    SimulatedTradeLog,
)
from tw_stock_tool.paper_trading.runtime import (
    SimulatedPaperTradingRuntimeState,
    SimulatedPendingOrderState,
)


@dataclass(frozen=True, slots=True)
class SimulatedPortfolioPositionResult:
    symbol: str
    quantity: int
    average_cost: float
    last_price: float | None
    market_value: float
    realized_pnl: float
    unrealized_pnl: float


@dataclass(frozen=True, slots=True)
class SimulatedPortfolioPendingOrderResult:
    order_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: int
    signal_time: Any
    created_at: Any | None
    strategy: str | None
    reference_price: float
    reserved_buy_notional: float


@dataclass(frozen=True, slots=True)
class SimulatedPortfolioTradingResult:
    initial_cash: float
    final_cash: float
    total_market_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    total_return: float
    total_return_pct: float | None
    open_position_count: int
    order_count: int
    fill_count: int
    rejection_count: int
    audit_record_count: int
    positions: tuple[SimulatedPortfolioPositionResult, ...]
    pending_orders: tuple[SimulatedPortfolioPendingOrderResult, ...]
    orders: tuple[SimulatedOrder, ...]
    fills: tuple[SimulatedFill, ...]
    rejections: tuple[SimulatedOrderRejection, ...]
    audit_log: tuple[SimulatedTradeLogRecord, ...]


def _require_finite_number(name: str, value: object, *, non_negative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise PaperTradingModelError(f"{name} must be finite numeric data.")
    val_float = float(value)
    if not math.isfinite(val_float):
        raise PaperTradingModelError(f"{name} must be finite numeric data.")
    if non_negative and val_float < 0:
        raise PaperTradingModelError(f"{name} must be >= 0.")
    return val_float


def build_simulated_portfolio_trading_result(
    runtime_state: SimulatedPaperTradingRuntimeState,
    *,
    initial_cash: float,
    last_prices: Mapping[str, float],
) -> SimulatedPortfolioTradingResult:
    if not isinstance(runtime_state, SimulatedPaperTradingRuntimeState):
        raise PaperTradingModelError("runtime_state must be a SimulatedPaperTradingRuntimeState.")

    init_cash_float = _require_finite_number("initial_cash", initial_cash, non_negative=True)

    portfolio = runtime_state.portfolio
    if not isinstance(portfolio, SimulatedPortfolio):
        raise PaperTradingModelError("runtime_state.portfolio must be a SimulatedPortfolio.")
    if not isinstance(portfolio.positions, dict):
        raise PaperTradingModelError("portfolio.positions must be a dictionary.")
    if not isinstance(portfolio.trade_log, SimulatedTradeLog):
        raise PaperTradingModelError("portfolio.trade_log must be a SimulatedTradeLog.")
    
    if not isinstance(portfolio.trade_log.orders, list):
        raise PaperTradingModelError("trade_log.orders must be a list.")
    if not isinstance(portfolio.trade_log.fills, list):
        raise PaperTradingModelError("trade_log.fills must be a list.")
    if not isinstance(portfolio.trade_log.rejections, list):
        raise PaperTradingModelError("trade_log.rejections must be a list.")
    if not isinstance(portfolio.trade_log.records, list):
        raise PaperTradingModelError("trade_log.records must be a list.")

    final_cash = _require_finite_number("portfolio cash", portfolio.cash, non_negative=True)

    if not isinstance(last_prices, Mapping):
        raise PaperTradingModelError("last_prices must be a Mapping.")

    validated_prices = {}
    for k, v in last_prices.items():
        if not isinstance(k, str) or not k.strip():
            raise PaperTradingModelError("last_prices keys must be non-blank strings.")
        validated_prices[k] = _require_finite_number("last_prices values", v)
        if validated_prices[k] <= 0:
            raise PaperTradingModelError("last_prices values must be > 0.")

    position_results = []
    for symbol_key, pos in portfolio.positions.items():
        if not isinstance(symbol_key, str) or not symbol_key.strip():
            raise PaperTradingModelError("portfolio.positions key must be a non-blank string.")
        if not isinstance(pos, SimulatedPosition):
            raise PaperTradingModelError("position must be a SimulatedPosition.")
        if not isinstance(pos.symbol, str) or not pos.symbol.strip():
            raise PaperTradingModelError("position.symbol must be a non-blank string.")
        if symbol_key != pos.symbol:
            raise PaperTradingModelError("portfolio.positions key must match position.symbol.")

        if isinstance(pos.quantity, bool) or not isinstance(pos.quantity, int):
            raise PaperTradingModelError("position.quantity must be an integer.")
        if pos.quantity < 0:
            raise PaperTradingModelError("position.quantity must be >= 0.")

        avg_cost = _require_finite_number("position.average_cost", pos.average_cost, non_negative=True)
        if pos.quantity > 0 and avg_cost <= 0:
            raise PaperTradingModelError("open position average_cost must be > 0.")
        if pos.quantity == 0 and avg_cost != 0.0:
            raise PaperTradingModelError("closed position average_cost must be 0.")

        realized_pnl = _require_finite_number("position.realized_pnl", pos.realized_pnl)

        if pos.quantity > 0:
            if pos.symbol not in validated_prices:
                raise PaperTradingModelError(f"Missing last price for open position: {pos.symbol}")
            last_price = validated_prices[pos.symbol]
            market_val = _require_finite_number("position market_value", float(pos.quantity * last_price), non_negative=True)
            cost_basis = _require_finite_number("position cost_basis", float(pos.quantity * avg_cost), non_negative=True)
            unrealized_pnl = _require_finite_number("position unrealized_pnl", market_val - cost_basis)
        else:
            last_price = None
            market_val = 0.0
            unrealized_pnl = 0.0

        position_results.append(SimulatedPortfolioPositionResult(
            symbol=pos.symbol,
            quantity=pos.quantity,
            average_cost=avg_cost,
            last_price=last_price,
            market_value=market_val,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
        ))

    position_results.sort(key=lambda x: x.symbol)
    positions_tuple = tuple(position_results)

    if not isinstance(runtime_state.pending_orders, dict):
        raise PaperTradingModelError("pending_orders must be a dictionary.")

    pending_results = []
    for symbol_key, state in runtime_state.pending_orders.items():
        if not isinstance(symbol_key, str) or not symbol_key.strip():
            raise PaperTradingModelError("pending_orders keys must be non-blank strings.")
        if not isinstance(state, SimulatedPendingOrderState):
            raise PaperTradingModelError("pending_orders values must be SimulatedPendingOrderState.")
        
        order = getattr(state, "order", None)
        if not isinstance(order, SimulatedOrder):
            raise PaperTradingModelError("pending state order must be SimulatedOrder.")
        
        if symbol_key != order.symbol:
            raise PaperTradingModelError("pending_orders key must match the pending order symbol.")

        if not isinstance(order.order_id, str) or not order.order_id.strip():
            raise PaperTradingModelError("order_id must be a non-blank string.")
        if not isinstance(order.symbol, str) or not order.symbol.strip():
            raise PaperTradingModelError("order symbol must be a non-blank string.")
        if order.side not in ("BUY", "SELL"):
            raise PaperTradingModelError("order side must be BUY or SELL.")
        if isinstance(order.quantity, bool) or not isinstance(order.quantity, int) or order.quantity <= 0:
            raise PaperTradingModelError("order quantity must be a positive integer.")

        ref_price = _require_finite_number("pending reference_price", state.reference_price, non_negative=True)
        if ref_price <= 0:
            raise PaperTradingModelError("pending reference_price must be > 0.")

        reserved_buy_notional = float(order.quantity * ref_price) if order.side == "BUY" else 0.0
        reserved_buy_notional = _require_finite_number("reserved buy notional", reserved_buy_notional, non_negative=True)

        pending_results.append(SimulatedPortfolioPendingOrderResult(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            signal_time=order.signal_time,
            created_at=order.created_at,
            strategy=order.strategy,
            reference_price=ref_price,
            reserved_buy_notional=reserved_buy_notional,
        ))

    pending_results.sort(key=lambda x: (x.symbol, x.order_id))
    pending_tuple = tuple(pending_results)

    total_market_value = _require_finite_number("total_market_value", sum(p.market_value for p in positions_tuple), non_negative=True)
    total_equity = _require_finite_number("total_equity", final_cash + total_market_value, non_negative=True)
    realized_pnl = _require_finite_number("realized_pnl", sum(p.realized_pnl for p in positions_tuple))
    unrealized_pnl = _require_finite_number("unrealized_pnl", sum(p.unrealized_pnl for p in positions_tuple if p.quantity > 0))

    total_return = _require_finite_number("total_return", total_equity - init_cash_float)
    
    if init_cash_float == 0:
        total_return_pct = None
    else:
        total_return_pct = _require_finite_number("total_return_pct", total_return / init_cash_float)

    open_position_count = sum(1 for p in positions_tuple if p.quantity > 0)

    order_count = len(portfolio.trade_log.orders)
    fill_count = len(portfolio.trade_log.fills)
    rejection_count = len(portfolio.trade_log.rejections)
    audit_record_count = len(portfolio.trade_log.records)

    return SimulatedPortfolioTradingResult(
        initial_cash=init_cash_float,
        final_cash=final_cash,
        total_market_value=total_market_value,
        total_equity=total_equity,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        total_return=total_return,
        total_return_pct=total_return_pct,
        open_position_count=open_position_count,
        order_count=order_count,
        fill_count=fill_count,
        rejection_count=rejection_count,
        audit_record_count=audit_record_count,
        positions=positions_tuple,
        pending_orders=pending_tuple,
        orders=tuple(portfolio.trade_log.orders),
        fills=tuple(portfolio.trade_log.fills),
        rejections=tuple(portfolio.trade_log.rejections),
        audit_log=tuple(portfolio.trade_log.records),
    )

