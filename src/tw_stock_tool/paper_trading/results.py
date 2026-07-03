import math
from dataclasses import dataclass
from tw_stock_tool.paper_trading.models import SimulatedPortfolio, SimulatedOrder, SimulatedFill, PaperTradingModelError

@dataclass(frozen=True, slots=True)
class SimulatedPaperTradingResult:
    """Research-only result boundary for simulated paper trading."""
    symbol: str
    initial_cash: float
    final_cash: float
    final_position_quantity: int
    average_cost: float
    realized_pnl: float
    unrealized_pnl: float
    total_equity: float
    order_count: int
    fill_count: int
    open_position_count: int
    orders: tuple[SimulatedOrder, ...]
    fills: tuple[SimulatedFill, ...]

def build_simulated_paper_trading_result(
    portfolio: SimulatedPortfolio,
    symbol: str,
    initial_cash: float,
    last_price: float | None = None,
) -> SimulatedPaperTradingResult:
    """Build a stable summary object from a completed SimulatedPortfolio."""
    if not symbol or not symbol.strip():
        raise PaperTradingModelError("Symbol must not be blank.")
    if not math.isfinite(initial_cash) or initial_cash < 0:
        raise PaperTradingModelError("initial_cash must be finite and non-negative.")

    position = portfolio.position_for(symbol)
    final_cash = portfolio.cash
    final_position_quantity = position.quantity
    average_cost = position.average_cost
    realized_pnl = position.realized_pnl

    if position.quantity == 0:
        unrealized_pnl = 0.0
        total_equity = portfolio.cash
    else:
        if last_price is None:
            raise PaperTradingModelError("last_price is required for an open position.")
        if not math.isfinite(last_price) or last_price <= 0:
            raise PaperTradingModelError("last_price must be finite and positive.")
        unrealized_pnl = position.unrealized_pnl(last_price)
        total_equity = portfolio.total_equity({symbol: last_price})

    order_count = len(portfolio.trade_log.orders)
    fill_count = len(portfolio.trade_log.fills)
    open_position_count = sum(1 for pos in portfolio.positions.values() if pos.quantity > 0)

    return SimulatedPaperTradingResult(
        symbol=symbol,
        initial_cash=initial_cash,
        final_cash=final_cash,
        final_position_quantity=final_position_quantity,
        average_cost=average_cost,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        total_equity=total_equity,
        order_count=order_count,
        fill_count=fill_count,
        open_position_count=open_position_count,
        orders=tuple(portfolio.trade_log.orders),
        fills=tuple(portfolio.trade_log.fills),
    )
