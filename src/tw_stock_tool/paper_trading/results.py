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

def build_simulated_paper_trading_summary(
    result: SimulatedPaperTradingResult,
) -> dict[str, object]:
    """Convert a SimulatedPaperTradingResult into a flat summary dictionary."""
    total_return = result.total_equity - result.initial_cash

    if result.initial_cash == 0:
        total_return_pct = None
    else:
        total_return_pct = total_return / result.initial_cash

    return {
        "symbol": result.symbol,
        "initial_cash": result.initial_cash,
        "final_cash": result.final_cash,
        "final_position_quantity": result.final_position_quantity,
        "average_cost": result.average_cost,
        "realized_pnl": result.realized_pnl,
        "unrealized_pnl": result.unrealized_pnl,
        "total_equity": result.total_equity,
        "order_count": result.order_count,
        "fill_count": result.fill_count,
        "open_position_count": result.open_position_count,
        "total_return": total_return,
        "total_return_pct": total_return_pct,
    }

def build_simulated_order_rows(
    result: SimulatedPaperTradingResult,
) -> list[dict[str, object]]:
    """Convert a SimulatedPaperTradingResult's orders into a list of flat dictionaries."""
    rows = []
    for order in result.orders:
        rows.append({
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "signal_time": order.signal_time,
            "created_at": order.created_at,
            "strategy": order.strategy,
        })
    return rows

def build_simulated_fill_rows(
    result: SimulatedPaperTradingResult,
) -> list[dict[str, object]]:
    """Convert a SimulatedPaperTradingResult's fills into a list of flat dictionaries."""
    rows = []
    for fill in result.fills:
        rows.append({
            "order_id": fill.order_id,
            "symbol": fill.symbol,
            "side": fill.side,
            "quantity": fill.quantity,
            "price": fill.price,
            "filled_at": fill.filled_at,
            "fee": fill.fee,
            "tax": fill.tax,
            "slippage": fill.slippage,
            "gross_amount": fill.gross_amount,
            "net_cash_effect": fill.net_cash_effect,
        })
    return rows

def build_simulated_paper_trading_report_data(
    result: SimulatedPaperTradingResult,
) -> dict[str, object]:
    """Bundle summary and trade logs into a single flat report payload."""
    return {
        "summary": build_simulated_paper_trading_summary(result),
        "order_rows": build_simulated_order_rows(result),
        "fill_rows": build_simulated_fill_rows(result),
    }
