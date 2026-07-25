"""
Multi-symbol simulated portfolio trading report data builder.
"""

from typing import Any

from tw_stock_tool.paper_trading.models import PaperTradingModelError
from tw_stock_tool.paper_trading.portfolio_results import SimulatedPortfolioTradingResult


def _require_portfolio_result(result: Any) -> None:
    if not isinstance(result, SimulatedPortfolioTradingResult):
        raise PaperTradingModelError("result must be a SimulatedPortfolioTradingResult.")


def build_simulated_portfolio_trading_summary(result: SimulatedPortfolioTradingResult) -> dict[str, Any]:
    _require_portfolio_result(result)
    return {
        "initial_cash": result.initial_cash,
        "final_cash": result.final_cash,
        "total_market_value": result.total_market_value,
        "total_equity": result.total_equity,
        "realized_pnl": result.realized_pnl,
        "unrealized_pnl": result.unrealized_pnl,
        "total_return": result.total_return,
        "total_return_pct": result.total_return_pct,
        "open_position_count": result.open_position_count,
        "pending_order_count": len(result.pending_orders),
        "order_count": result.order_count,
        "fill_count": result.fill_count,
        "rejection_count": result.rejection_count,
        "audit_record_count": result.audit_record_count,
    }


def build_simulated_portfolio_position_rows(result: SimulatedPortfolioTradingResult) -> list[dict[str, Any]]:
    _require_portfolio_result(result)
    rows = []
    for pos in result.positions:
        rows.append({
            "symbol": pos.symbol,
            "quantity": pos.quantity,
            "average_cost": pos.average_cost,
            "last_price": pos.last_price,
            "market_value": pos.market_value,
            "realized_pnl": pos.realized_pnl,
            "unrealized_pnl": pos.unrealized_pnl,
        })
    return rows


def build_simulated_portfolio_pending_order_rows(result: SimulatedPortfolioTradingResult) -> list[dict[str, Any]]:
    _require_portfolio_result(result)
    rows = []
    for po in result.pending_orders:
        rows.append({
            "order_id": po.order_id,
            "symbol": po.symbol,
            "side": po.side,
            "quantity": po.quantity,
            "signal_time": po.signal_time,
            "created_at": po.created_at,
            "strategy": po.strategy,
            "reference_price": po.reference_price,
            "reserved_buy_notional": po.reserved_buy_notional,
        })
    return rows


def build_simulated_portfolio_order_rows(result: SimulatedPortfolioTradingResult) -> list[dict[str, Any]]:
    _require_portfolio_result(result)
    rows = []
    for o in result.orders:
        rows.append({
            "order_id": o.order_id,
            "symbol": o.symbol,
            "side": o.side,
            "quantity": o.quantity,
            "signal_time": o.signal_time,
            "created_at": o.created_at,
            "strategy": o.strategy,
        })
    return rows


def build_simulated_portfolio_fill_rows(result: SimulatedPortfolioTradingResult) -> list[dict[str, Any]]:
    _require_portfolio_result(result)
    rows = []
    for f in result.fills:
        rows.append({
            "order_id": f.order_id,
            "symbol": f.symbol,
            "side": f.side,
            "quantity": f.quantity,
            "price": f.price,
            "filled_at": f.filled_at,
            "fee": f.fee,
            "tax": f.tax,
            "slippage": f.slippage,
            "gross_amount": f.gross_amount,
            "net_cash_effect": f.net_cash_effect,
        })
    return rows


def build_simulated_portfolio_rejection_rows(result: SimulatedPortfolioTradingResult) -> list[dict[str, Any]]:
    _require_portfolio_result(result)
    rows = []
    for r in result.rejections:
        c_ord = r.candidate_order
        rows.append({
            "order_id": c_ord.order_id,
            "symbol": c_ord.symbol,
            "side": c_ord.side,
            "quantity": c_ord.quantity,
            "signal_time": c_ord.signal_time,
            "created_at": c_ord.created_at,
            "strategy": c_ord.strategy,
            "reasons": " | ".join(r.reasons),
        })
    return rows


def build_simulated_portfolio_trade_log_rows(result: SimulatedPortfolioTradingResult) -> list[dict[str, Any]]:
    _require_portfolio_result(result)
    rows = []
    for record in result.audit_log:
        rows.append({
            "sequence": record.sequence,
            "record_id": record.record_id,
            "event_type": record.event_type.value,
            "status": record.status.value,
            "order_id": record.order_id,
            "symbol": record.symbol,
            "side": record.side,
            "quantity": record.quantity,
            "signal_time": record.signal_time,
            "order_created_at": record.order_created_at,
            "expected_execution_model": record.expected_execution_model,
            "fill_time": record.fill_time,
            "fill_price": record.fill_price,
            "fee": record.fee,
            "tax": record.tax,
            "slippage": record.slippage,
            "strategy_name": record.strategy_name,
            "strategy_metadata": dict(record.strategy_metadata),
            "risk_allowed": record.risk_allowed,
            "risk_rejection_reasons": " | ".join(record.risk_rejection_reasons),
            "guard_metadata": dict(record.guard_metadata),
            "error_code": record.error_code,
            "error_message": record.error_message,
        })
    return rows


def build_simulated_portfolio_trading_report_data(result: SimulatedPortfolioTradingResult) -> dict[str, Any]:
    _require_portfolio_result(result)
    return {
        "summary": build_simulated_portfolio_trading_summary(result),
        "position_rows": build_simulated_portfolio_position_rows(result),
        "pending_order_rows": build_simulated_portfolio_pending_order_rows(result),
        "order_rows": build_simulated_portfolio_order_rows(result),
        "fill_rows": build_simulated_portfolio_fill_rows(result),
        "rejection_rows": build_simulated_portfolio_rejection_rows(result),
        "trade_log_rows": build_simulated_portfolio_trade_log_rows(result),
    }
