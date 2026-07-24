import json
from typing import Any

from tw_stock_tool.paper_trading.models import PaperTradingModelError
from tw_stock_tool.paper_trading.portfolio_results import (
    SimulatedPortfolioPositionResult,
    SimulatedPortfolioPendingOrderResult,
    SimulatedPortfolioTradingResult,
)
from tw_stock_tool.paper_trading.serialization import (
    _serialize_datetime_like,
    _enforce_numeric,
    _serialize_simulated_order,
    _deserialize_simulated_order,
    _serialize_simulated_fill,
    _deserialize_simulated_fill,
    _serialize_simulated_rejection,
    _deserialize_simulated_rejection,
    _serialize_trade_log_record,
    _deserialize_trade_log_record,
)


def _strict_enforce_numeric(val: Any, t: type, name: str) -> Any:
    if isinstance(val, str):
        raise PaperTradingModelError(f"Field {name} cannot be a string.")
    return _enforce_numeric(val, t, name)

def serialize_simulated_portfolio_trading_result(
    result: SimulatedPortfolioTradingResult,
) -> dict[str, Any]:
    if not isinstance(result, SimulatedPortfolioTradingResult):
        raise PaperTradingModelError("Input must be a SimulatedPortfolioTradingResult.")
    positions = []
    for i, p in enumerate(result.positions):
        positions.append({
            "symbol": str(p.symbol),
            "quantity": _strict_enforce_numeric(p.quantity, int, f"positions[{i}].quantity"),
            "average_cost": _strict_enforce_numeric(p.average_cost, float, f"positions[{i}].average_cost"),
            "last_price": None if p.last_price is None else _strict_enforce_numeric(p.last_price, float, f"positions[{i}].last_price"),
            "market_value": _strict_enforce_numeric(p.market_value, float, f"positions[{i}].market_value"),
            "realized_pnl": _strict_enforce_numeric(p.realized_pnl, float, f"positions[{i}].realized_pnl"),
            "unrealized_pnl": _strict_enforce_numeric(p.unrealized_pnl, float, f"positions[{i}].unrealized_pnl"),
        })
    
    pending_orders = []
    for i, po in enumerate(result.pending_orders):
        pending_orders.append({
            "order_id": str(po.order_id),
            "symbol": str(po.symbol),
            "side": str(po.side),
            "quantity": _strict_enforce_numeric(po.quantity, int, f"pending_orders[{i}].quantity"),
            "signal_time": _serialize_datetime_like(po.signal_time),
            "created_at": _serialize_datetime_like(po.created_at),
            "strategy": str(po.strategy) if po.strategy is not None else None,
            "reference_price": _strict_enforce_numeric(po.reference_price, float, f"pending_orders[{i}].reference_price"),
            "reserved_buy_notional": _strict_enforce_numeric(po.reserved_buy_notional, float, f"pending_orders[{i}].reserved_buy_notional"),
        })

    orders = [_serialize_simulated_order(o, i) for i, o in enumerate(result.orders)]
    fills = [_serialize_simulated_fill(f, i) for i, f in enumerate(result.fills)]
    rejections = [_serialize_simulated_rejection(r, i) for i, r in enumerate(result.rejections)]
    audit_log = [_serialize_trade_log_record(record, i) for i, record in enumerate(result.audit_log)]

    return {
        "schema_version": 1,
        "result_type": "simulated_portfolio_trading_result",
        "initial_cash": _strict_enforce_numeric(result.initial_cash, float, "initial_cash"),
        "final_cash": _strict_enforce_numeric(result.final_cash, float, "final_cash"),
        "total_market_value": _strict_enforce_numeric(result.total_market_value, float, "total_market_value"),
        "total_equity": _strict_enforce_numeric(result.total_equity, float, "total_equity"),
        "realized_pnl": _strict_enforce_numeric(result.realized_pnl, float, "realized_pnl"),
        "unrealized_pnl": _strict_enforce_numeric(result.unrealized_pnl, float, "unrealized_pnl"),
        "total_return": _strict_enforce_numeric(result.total_return, float, "total_return"),
        "total_return_pct": None if result.total_return_pct is None else _strict_enforce_numeric(result.total_return_pct, float, "total_return_pct"),
        "open_position_count": _strict_enforce_numeric(result.open_position_count, int, "open_position_count"),
        "order_count": _strict_enforce_numeric(result.order_count, int, "order_count"),
        "fill_count": _strict_enforce_numeric(result.fill_count, int, "fill_count"),
        "rejection_count": _strict_enforce_numeric(result.rejection_count, int, "rejection_count"),
        "audit_record_count": _strict_enforce_numeric(result.audit_record_count, int, "audit_record_count"),
        "positions": positions,
        "pending_orders": pending_orders,
        "orders": orders,
        "fills": fills,
        "rejections": rejections,
        "audit_log": audit_log,
    }


def deserialize_simulated_portfolio_trading_result(
    data: dict[str, Any],
) -> SimulatedPortfolioTradingResult:
    if not isinstance(data, dict):
        raise PaperTradingModelError("Top-level data must be a dict.")

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version != 1:
        raise PaperTradingModelError(f"Unsupported schema_version: {schema_version}")

    result_type = data.get("result_type")
    if result_type != "simulated_portfolio_trading_result":
        raise PaperTradingModelError(f"Unsupported result_type: {result_type}")

    allowed_keys = {
        "schema_version",
        "result_type",
        "initial_cash",
        "final_cash",
        "total_market_value",
        "total_equity",
        "realized_pnl",
        "unrealized_pnl",
        "total_return",
        "total_return_pct",
        "open_position_count",
        "order_count",
        "fill_count",
        "rejection_count",
        "audit_record_count",
        "positions",
        "pending_orders",
        "orders",
        "fills",
        "rejections",
        "audit_log",
    }
    missing = allowed_keys - set(data.keys())
    if missing:
        raise PaperTradingModelError(f"Missing required top-level fields: {missing}")
    extra = set(data.keys()) - allowed_keys
    if extra:
        raise PaperTradingModelError(f"Extra unknown top-level fields: {extra}")

    if not isinstance(data["positions"], list):
        raise PaperTradingModelError("Field 'positions' must be a list.")
    if not isinstance(data["pending_orders"], list):
        raise PaperTradingModelError("Field 'pending_orders' must be a list.")
    if not isinstance(data["orders"], list):
        raise PaperTradingModelError("Field 'orders' must be a list.")
    if not isinstance(data["fills"], list):
        raise PaperTradingModelError("Field 'fills' must be a list.")
    if not isinstance(data["rejections"], list):
        raise PaperTradingModelError("Field 'rejections' must be a list.")
    if not isinstance(data["audit_log"], list):
        raise PaperTradingModelError("Field 'audit_log' must be a list.")

    parsed_positions = []
    last_symbol = None
    for i, p in enumerate(data["positions"]):
        if not isinstance(p, dict):
            raise PaperTradingModelError(f"Position at index {i} must be a dict.")
        p_allowed = {"symbol", "quantity", "average_cost", "last_price", "market_value", "realized_pnl", "unrealized_pnl"}
        p_missing = p_allowed - set(p.keys())
        if p_missing:
            raise PaperTradingModelError(f"Position {i} missing fields: {p_missing}")
        p_extra = set(p.keys()) - p_allowed
        if p_extra:
            raise PaperTradingModelError(f"Position {i} extra fields: {p_extra}")
        
        symbol = str(p["symbol"])
        if not symbol:
            raise PaperTradingModelError(f"Position {i} symbol cannot be empty.")
        if last_symbol is not None and symbol <= last_symbol:
            raise PaperTradingModelError(f"Positions are not canonically sorted (got {symbol} after {last_symbol}).")
        last_symbol = symbol

        qty = _strict_enforce_numeric(p["quantity"], int, f"positions[{i}].quantity")
        if qty < 0:
            raise PaperTradingModelError(f"Position {i} quantity cannot be negative.")
            
        avg_cost = _strict_enforce_numeric(p["average_cost"], float, f"positions[{i}].average_cost")
        if avg_cost < 0:
            raise PaperTradingModelError(f"Position {i} average_cost cannot be negative.")

        last_price = None if p["last_price"] is None else _strict_enforce_numeric(p["last_price"], float, f"positions[{i}].last_price")
        if last_price is not None and last_price <= 0:
            raise PaperTradingModelError(f"Position {i} last_price must be positive if present.")
            
        market_value = _strict_enforce_numeric(p["market_value"], float, f"positions[{i}].market_value")
        if market_value < 0:
            raise PaperTradingModelError(f"Position {i} market_value cannot be negative.")

        realized_pnl = _strict_enforce_numeric(p["realized_pnl"], float, f"positions[{i}].realized_pnl")
        unrealized_pnl = _strict_enforce_numeric(p["unrealized_pnl"], float, f"positions[{i}].unrealized_pnl")

        if qty > 0:
            if avg_cost <= 0:
                raise PaperTradingModelError(f"Open position {i} must have positive average_cost.")
            if last_price is None:
                raise PaperTradingModelError(f"Open position {i} must have last_price.")
        else:
            if avg_cost != 0.0:
                raise PaperTradingModelError(f"Closed position {i} must have average_cost == 0.0.")
            if last_price is not None:
                raise PaperTradingModelError(f"Closed position {i} must have last_price is None.")
            if market_value != 0.0:
                raise PaperTradingModelError(f"Closed position {i} must have market_value == 0.0.")
            if unrealized_pnl != 0.0:
                raise PaperTradingModelError(f"Closed position {i} must have unrealized_pnl == 0.0.")

        try:
            parsed_positions.append(SimulatedPortfolioPositionResult(
                symbol=symbol,
                quantity=qty,
                average_cost=avg_cost,
                last_price=last_price,
                market_value=market_value,
                realized_pnl=realized_pnl,
                unrealized_pnl=unrealized_pnl,
            ))
        except Exception as e:
            raise PaperTradingModelError(f"Position {i} invalid: {e}")

    parsed_pending_orders = []
    last_pending_key = None
    for i, po in enumerate(data["pending_orders"]):
        if not isinstance(po, dict):
            raise PaperTradingModelError(f"Pending order at index {i} must be a dict.")
        po_allowed = {"order_id", "symbol", "side", "quantity", "signal_time", "created_at", "strategy", "reference_price", "reserved_buy_notional"}
        po_missing = po_allowed - set(po.keys())
        if po_missing:
            raise PaperTradingModelError(f"Pending order {i} missing fields: {po_missing}")
        po_extra = set(po.keys()) - po_allowed
        if po_extra:
            raise PaperTradingModelError(f"Pending order {i} extra fields: {po_extra}")

        order_id = str(po["order_id"])
        symbol = str(po["symbol"])
        if not order_id:
            raise PaperTradingModelError(f"Pending order {i} order_id cannot be empty.")
        if not symbol:
            raise PaperTradingModelError(f"Pending order {i} symbol cannot be empty.")
            
        pending_key = (symbol, order_id)
        if last_pending_key is not None and pending_key <= last_pending_key:
            raise PaperTradingModelError(f"Pending orders are not canonically sorted (got {pending_key} after {last_pending_key}).")
        last_pending_key = pending_key

        side = str(po["side"])
        if side not in ("BUY", "SELL"):
            raise PaperTradingModelError(f"Pending order {i} invalid side: {side}")

        qty = _strict_enforce_numeric(po["quantity"], int, f"pending_orders[{i}].quantity")
        if qty <= 0:
            raise PaperTradingModelError(f"Pending order {i} quantity must be positive.")

        strategy = po["strategy"]
        if strategy is not None and not isinstance(strategy, str):
            raise PaperTradingModelError(f"Pending order {i} strategy must be str or None.")
            
        ref_price = _strict_enforce_numeric(po["reference_price"], float, f"pending_orders[{i}].reference_price")
        if ref_price <= 0:
            raise PaperTradingModelError(f"Pending order {i} reference_price must be positive.")
            
        reserved_buy_notional = _strict_enforce_numeric(po["reserved_buy_notional"], float, f"pending_orders[{i}].reserved_buy_notional")
        if reserved_buy_notional < 0:
            raise PaperTradingModelError(f"Pending order {i} reserved_buy_notional cannot be negative.")
        if side == "SELL" and reserved_buy_notional != 0.0:
            raise PaperTradingModelError(f"Pending SELL order {i} must have reserved_buy_notional == 0.0.")

        try:
            parsed_pending_orders.append(SimulatedPortfolioPendingOrderResult(
                order_id=order_id,
                symbol=symbol,
                side=side,
                quantity=qty,
                signal_time=str(po["signal_time"]) if po["signal_time"] is not None else None,
                created_at=str(po["created_at"]) if po["created_at"] is not None else None,
                strategy=strategy,
                reference_price=ref_price,
                reserved_buy_notional=reserved_buy_notional,
            ))
        except Exception as e:
            raise PaperTradingModelError(f"Pending order {i} invalid: {e}")

    parsed_orders = [_deserialize_simulated_order(o, i) for i, o in enumerate(data["orders"])]
    parsed_fills = [_deserialize_simulated_fill(f, i) for i, f in enumerate(data["fills"])]
    parsed_rejections = [_deserialize_simulated_rejection(r, i) for i, r in enumerate(data["rejections"])]
    parsed_audit_log = [_deserialize_trade_log_record(record, i) for i, record in enumerate(data["audit_log"])]

    # Validate counts
    open_position_count = _strict_enforce_numeric(data["open_position_count"], int, "open_position_count")
    if open_position_count < 0:
        raise PaperTradingModelError("open_position_count cannot be negative.")
    actual_open = sum(1 for p in parsed_positions if p.quantity > 0)
    if open_position_count != actual_open:
        raise PaperTradingModelError(f"open_position_count {open_position_count} does not match actual open positions {actual_open}.")

    order_count = _strict_enforce_numeric(data["order_count"], int, "order_count")
    if order_count < 0:
        raise PaperTradingModelError("order_count cannot be negative.")
    if order_count != len(parsed_orders):
        raise PaperTradingModelError(f"order_count {order_count} does not match len(orders) {len(parsed_orders)}.")

    fill_count = _strict_enforce_numeric(data["fill_count"], int, "fill_count")
    if fill_count < 0:
        raise PaperTradingModelError("fill_count cannot be negative.")
    if fill_count != len(parsed_fills):
        raise PaperTradingModelError(f"fill_count {fill_count} does not match len(fills) {len(parsed_fills)}.")

    rejection_count = _strict_enforce_numeric(data["rejection_count"], int, "rejection_count")
    if rejection_count < 0:
        raise PaperTradingModelError("rejection_count cannot be negative.")
    if rejection_count != len(parsed_rejections):
        raise PaperTradingModelError(f"rejection_count {rejection_count} does not match len(rejections) {len(parsed_rejections)}.")

    audit_record_count = _strict_enforce_numeric(data["audit_record_count"], int, "audit_record_count")
    if audit_record_count < 0:
        raise PaperTradingModelError("audit_record_count cannot be negative.")
    if audit_record_count != len(parsed_audit_log):
        raise PaperTradingModelError(f"audit_record_count {audit_record_count} does not match len(audit_log) {len(parsed_audit_log)}.")

    try:
        return SimulatedPortfolioTradingResult(
            initial_cash=_strict_enforce_numeric(data["initial_cash"], float, "initial_cash"),
            final_cash=_strict_enforce_numeric(data["final_cash"], float, "final_cash"),
            total_market_value=_strict_enforce_numeric(data["total_market_value"], float, "total_market_value"),
            total_equity=_strict_enforce_numeric(data["total_equity"], float, "total_equity"),
            realized_pnl=_strict_enforce_numeric(data["realized_pnl"], float, "realized_pnl"),
            unrealized_pnl=_strict_enforce_numeric(data["unrealized_pnl"], float, "unrealized_pnl"),
            total_return=_strict_enforce_numeric(data["total_return"], float, "total_return"),
            total_return_pct=None if data["total_return_pct"] is None else _strict_enforce_numeric(data["total_return_pct"], float, "total_return_pct"),
            open_position_count=open_position_count,
            order_count=order_count,
            fill_count=fill_count,
            rejection_count=rejection_count,
            audit_record_count=audit_record_count,
            positions=tuple(parsed_positions),
            pending_orders=tuple(parsed_pending_orders),
            orders=tuple(parsed_orders),
            fills=tuple(parsed_fills),
            rejections=tuple(parsed_rejections),
            audit_log=tuple(parsed_audit_log),
        )
    except PaperTradingModelError:
        raise
    except Exception as e:
        raise PaperTradingModelError(f"Error creating SimulatedPortfolioTradingResult: {e}")


def export_simulated_portfolio_trading_result_json(
    result: SimulatedPortfolioTradingResult,
) -> str:
    data = serialize_simulated_portfolio_trading_result(result)
    try:
        return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    except (TypeError, ValueError) as e:
        raise PaperTradingModelError(f"JSON export failed: {e}")


def load_simulated_portfolio_trading_result_json(
    content: str,
) -> SimulatedPortfolioTradingResult:
    if not isinstance(content, str):
        raise PaperTradingModelError("content must be a string.")
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise PaperTradingModelError(f"Invalid JSON content: {e}")
    return deserialize_simulated_portfolio_trading_result(data)
