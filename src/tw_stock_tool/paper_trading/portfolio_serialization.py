import json
import math
import numbers
from typing import Any

from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedOrder,
    SimulatedFill,
    SimulatedOrderRejection,
    SimulatedTradeLogRecord,
)
from tw_stock_tool.paper_trading.portfolio_results import (
    SimulatedPortfolioPositionResult,
    SimulatedPortfolioPendingOrderResult,
    SimulatedPortfolioTradingResult,
)
from tw_stock_tool.paper_trading.serialization import (
    _serialize_datetime_like,
    _serialize_simulated_order,
    _deserialize_simulated_order,
    _serialize_simulated_fill,
    _deserialize_simulated_fill,
    _serialize_simulated_rejection,
    _deserialize_simulated_rejection,
    _serialize_trade_log_record,
    _deserialize_trade_log_record,
)


def _require_non_blank_string(name: str, value: object) -> str:
    if type(value) is not str:
        raise PaperTradingModelError(f"Field {name} must be exactly a string.")
    if value.strip() == "":
        raise PaperTradingModelError(f"Field {name} cannot be empty or whitespace.")
    return value


def _require_exact_int(name: str, value: object, *, minimum: int = 0) -> int:
    if type(value) is not int:
        raise PaperTradingModelError(f"Field {name} must be an exact int.")
    if value < minimum:
        raise PaperTradingModelError(f"Field {name} cannot be less than {minimum}.")
    return value


def _require_finite_float(
    name: str,
    value: object,
    *,
    non_negative: bool = False,
    strictly_positive: bool = False,
) -> float:
    if not isinstance(value, numbers.Real) or isinstance(value, bool):
        raise PaperTradingModelError(f"Field {name} must be a real number.")
    try:
        f_val = float(value)
    except (TypeError, ValueError, OverflowError) as e:
        raise PaperTradingModelError(f"Field {name} conversion error: {e}")
    if not math.isfinite(f_val):
        raise PaperTradingModelError(f"Field {name} must be finite.")
    if non_negative and f_val < 0.0:
        raise PaperTradingModelError(f"Field {name} cannot be negative.")
    if strictly_positive and f_val <= 0.0:
        raise PaperTradingModelError(f"Field {name} must be strictly positive.")
    return f_val


def _require_optional_string(name: str, value: object) -> str | None:
    if value is not None:
        if type(value) is not str:
            raise PaperTradingModelError(f"Field {name} must be a str or None.")
        if value.strip() == "":
            raise PaperTradingModelError(f"Field {name} cannot be empty or whitespace.")
    return value


def _require_timestamp_string_or_none(name: str, value: object) -> str | None:
    if value is not None and type(value) is not str:
        raise PaperTradingModelError(f"Field {name} must be a str or None.")
    return value


def serialize_simulated_portfolio_trading_result(
    result: SimulatedPortfolioTradingResult,
) -> dict[str, Any]:
    if not isinstance(result, SimulatedPortfolioTradingResult):
        raise PaperTradingModelError("Input must be a SimulatedPortfolioTradingResult.")

    if type(result.positions) is not tuple:
        raise PaperTradingModelError("Field positions must be a tuple.")
    if type(result.pending_orders) is not tuple:
        raise PaperTradingModelError("Field pending_orders must be a tuple.")
    if type(result.orders) is not tuple:
        raise PaperTradingModelError("Field orders must be a tuple.")
    if type(result.fills) is not tuple:
        raise PaperTradingModelError("Field fills must be a tuple.")
    if type(result.rejections) is not tuple:
        raise PaperTradingModelError("Field rejections must be a tuple.")
    if type(result.audit_log) is not tuple:
        raise PaperTradingModelError("Field audit_log must be a tuple.")

    positions = []
    last_symbol = None
    open_position_count = 0
    for i, p in enumerate(result.positions):
        if type(p) is not SimulatedPortfolioPositionResult:
            raise PaperTradingModelError(f"positions[{i}] must be SimulatedPortfolioPositionResult.")
        
        sym = _require_non_blank_string(f"positions[{i}].symbol", p.symbol)
        if last_symbol is not None and sym <= last_symbol:
            raise PaperTradingModelError(f"Positions are not canonically sorted (got {sym} after {last_symbol}).")
        last_symbol = sym

        qty = _require_exact_int(f"positions[{i}].quantity", p.quantity, minimum=0)
        avg_cost = _require_finite_float(f"positions[{i}].average_cost", p.average_cost, non_negative=(qty > 0))
        
        last_price = p.last_price
        if last_price is not None:
            last_price = _require_finite_float(f"positions[{i}].last_price", last_price, strictly_positive=True)
            
        market_value = _require_finite_float(f"positions[{i}].market_value", p.market_value, non_negative=True)
        realized_pnl = _require_finite_float(f"positions[{i}].realized_pnl", p.realized_pnl)
        unrealized_pnl = _require_finite_float(f"positions[{i}].unrealized_pnl", p.unrealized_pnl)

        if qty > 0:
            if avg_cost <= 0:
                raise PaperTradingModelError(f"Open position {i} must have positive average_cost.")
            if last_price is None:
                raise PaperTradingModelError(f"Open position {i} must have last_price.")
            open_position_count += 1
        else:
            if avg_cost != 0.0:
                raise PaperTradingModelError(f"Closed position {i} must have average_cost == 0.0.")
            if last_price is not None:
                raise PaperTradingModelError(f"Closed position {i} must have last_price is None.")
            if market_value != 0.0:
                raise PaperTradingModelError(f"Closed position {i} must have market_value == 0.0.")
            if unrealized_pnl != 0.0:
                raise PaperTradingModelError(f"Closed position {i} must have unrealized_pnl == 0.0.")

        positions.append({
            "symbol": sym,
            "quantity": qty,
            "average_cost": avg_cost,
            "last_price": last_price,
            "market_value": market_value,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
        })

    if _require_exact_int("open_position_count", result.open_position_count) != open_position_count:
        raise PaperTradingModelError(f"open_position_count {result.open_position_count} does not match actual {open_position_count}.")

    pending_orders = []
    last_pending_key = None
    for i, po in enumerate(result.pending_orders):
        if type(po) is not SimulatedPortfolioPendingOrderResult:
            raise PaperTradingModelError(f"pending_orders[{i}] must be SimulatedPortfolioPendingOrderResult.")

        order_id = _require_non_blank_string(f"pending_orders[{i}].order_id", po.order_id)
        sym = _require_non_blank_string(f"pending_orders[{i}].symbol", po.symbol)
        
        pending_key = (sym, order_id)
        if last_pending_key is not None and pending_key <= last_pending_key:
            raise PaperTradingModelError(f"Pending orders not canonically sorted (got {pending_key} after {last_pending_key}).")
        last_pending_key = pending_key

        side = _require_non_blank_string(f"pending_orders[{i}].side", po.side)
        if side not in ("BUY", "SELL"):
            raise PaperTradingModelError(f"pending_orders[{i}].side must be BUY or SELL.")

        qty = _require_exact_int(f"pending_orders[{i}].quantity", po.quantity, minimum=1)
        strategy = _require_optional_string(f"pending_orders[{i}].strategy", po.strategy)
        ref_price = _require_finite_float(f"pending_orders[{i}].reference_price", po.reference_price, strictly_positive=True)
        reserved_buy_notional = _require_finite_float(f"pending_orders[{i}].reserved_buy_notional", po.reserved_buy_notional, non_negative=True)

        if side == "SELL" and reserved_buy_notional != 0.0:
            raise PaperTradingModelError(f"Pending SELL order {i} must have reserved_buy_notional == 0.0.")

        pending_orders.append({
            "order_id": order_id,
            "symbol": sym,
            "side": side,
            "quantity": qty,
            "signal_time": _serialize_datetime_like(po.signal_time),
            "created_at": _serialize_datetime_like(po.created_at),
            "strategy": strategy,
            "reference_price": ref_price,
            "reserved_buy_notional": reserved_buy_notional,
        })

    orders = []
    for i, o in enumerate(result.orders):
        if type(o) is not SimulatedOrder:
            raise PaperTradingModelError(f"orders[{i}] must be SimulatedOrder.")
        _require_non_blank_string(f"orders[{i}].order_id", o.order_id)
        _require_non_blank_string(f"orders[{i}].symbol", o.symbol)
        side = _require_non_blank_string(f"orders[{i}].side", o.side)
        if side not in ("BUY", "SELL"):
            raise PaperTradingModelError(f"orders[{i}].side must be BUY or SELL.")
        _require_exact_int(f"orders[{i}].quantity", o.quantity, minimum=1)
        _require_optional_string(f"orders[{i}].strategy", o.strategy)
        if type(o.metadata) is not dict:
            raise PaperTradingModelError(f"orders[{i}].metadata must be dict.")
        try:
            json.dumps(o.metadata, allow_nan=False)
        except (TypeError, ValueError) as e:
            raise PaperTradingModelError(f"orders[{i}].metadata must be JSON serializable without NaN: {e}")
        orders.append(_serialize_simulated_order(o, i))

    fills = []
    for i, f in enumerate(result.fills):
        if type(f) is not SimulatedFill:
            raise PaperTradingModelError(f"fills[{i}] must be SimulatedFill.")
        _require_non_blank_string(f"fills[{i}].order_id", f.order_id)
        _require_non_blank_string(f"fills[{i}].symbol", f.symbol)
        side = _require_non_blank_string(f"fills[{i}].side", f.side)
        if side not in ("BUY", "SELL"):
            raise PaperTradingModelError(f"fills[{i}].side must be BUY or SELL.")
        _require_exact_int(f"fills[{i}].quantity", f.quantity, minimum=1)
        _require_finite_float(f"fills[{i}].price", f.price, strictly_positive=True)
        _require_finite_float(f"fills[{i}].fee", f.fee, non_negative=True)
        _require_finite_float(f"fills[{i}].tax", f.tax, non_negative=True)
        _require_finite_float(f"fills[{i}].slippage", f.slippage, non_negative=True)
        fills.append(_serialize_simulated_fill(f, i))

    rejections = []
    for i, r in enumerate(result.rejections):
        if type(r) is not SimulatedOrderRejection:
            raise PaperTradingModelError(f"rejections[{i}] must be SimulatedOrderRejection.")
        if type(r.candidate_order) is not SimulatedOrder:
            raise PaperTradingModelError(f"rejections[{i}].candidate_order must be SimulatedOrder.")
        _require_non_blank_string(f"rejections[{i}].candidate_order.order_id", r.candidate_order.order_id)
        _require_non_blank_string(f"rejections[{i}].candidate_order.symbol", r.candidate_order.symbol)
        side = _require_non_blank_string(f"rejections[{i}].candidate_order.side", r.candidate_order.side)
        if side not in ("BUY", "SELL"):
            raise PaperTradingModelError(f"rejections[{i}].candidate_order.side must be BUY or SELL.")
        _require_exact_int(f"rejections[{i}].candidate_order.quantity", r.candidate_order.quantity, minimum=1)
        _require_optional_string(f"rejections[{i}].candidate_order.strategy", r.candidate_order.strategy)
        if type(r.candidate_order.metadata) is not dict:
            raise PaperTradingModelError(f"rejections[{i}].candidate_order.metadata must be dict.")
        try:
            json.dumps(r.candidate_order.metadata, allow_nan=False)
        except (TypeError, ValueError) as e:
            raise PaperTradingModelError(f"rejections[{i}].candidate_order.metadata must be JSON serializable without NaN: {e}")
        
        if type(r.reasons) is not tuple:
            raise PaperTradingModelError(f"rejections[{i}].reasons must be tuple.")
        for j, reason in enumerate(r.reasons):
            _require_non_blank_string(f"rejections[{i}].reasons[{j}]", reason)
        rejections.append(_serialize_simulated_rejection(r, i))

    audit_log = []
    for i, record in enumerate(result.audit_log):
        if type(record) is not SimulatedTradeLogRecord:
            raise PaperTradingModelError(f"audit_log[{i}] must be SimulatedTradeLogRecord.")
        audit_log.append(_serialize_trade_log_record(record, i))

    if _require_exact_int("order_count", result.order_count) != len(orders):
        raise PaperTradingModelError(f"order_count {result.order_count} != {len(orders)}.")
    if _require_exact_int("fill_count", result.fill_count) != len(fills):
        raise PaperTradingModelError(f"fill_count {result.fill_count} != {len(fills)}.")
    if _require_exact_int("rejection_count", result.rejection_count) != len(rejections):
        raise PaperTradingModelError(f"rejection_count {result.rejection_count} != {len(rejections)}.")
    if _require_exact_int("audit_record_count", result.audit_record_count) != len(audit_log):
        raise PaperTradingModelError(f"audit_record_count {result.audit_record_count} != {len(audit_log)}.")

    total_return_pct = result.total_return_pct
    if total_return_pct is not None:
        total_return_pct = _require_finite_float("total_return_pct", total_return_pct)

    return {
        "schema_version": 1,
        "result_type": "simulated_portfolio_trading_result",
        "initial_cash": _require_finite_float("initial_cash", result.initial_cash, non_negative=True),
        "final_cash": _require_finite_float("final_cash", result.final_cash, non_negative=True),
        "total_market_value": _require_finite_float("total_market_value", result.total_market_value, non_negative=True),
        "total_equity": _require_finite_float("total_equity", result.total_equity, non_negative=True),
        "realized_pnl": _require_finite_float("realized_pnl", result.realized_pnl),
        "unrealized_pnl": _require_finite_float("unrealized_pnl", result.unrealized_pnl),
        "total_return": _require_finite_float("total_return", result.total_return),
        "total_return_pct": total_return_pct,
        "open_position_count": open_position_count,
        "order_count": len(orders),
        "fill_count": len(fills),
        "rejection_count": len(rejections),
        "audit_record_count": len(audit_log),
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
    if type(data) is not dict:
        raise PaperTradingModelError("Top-level data must be exactly a dict.")

    schema_version = data.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        raise PaperTradingModelError(f"Unsupported schema_version: {schema_version}")

    result_type = data.get("result_type")
    if type(result_type) is not str or result_type != "simulated_portfolio_trading_result":
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

    if type(data["positions"]) is not list:
        raise PaperTradingModelError("Field 'positions' must be exactly a list.")
    if type(data["pending_orders"]) is not list:
        raise PaperTradingModelError("Field 'pending_orders' must be exactly a list.")
    if type(data["orders"]) is not list:
        raise PaperTradingModelError("Field 'orders' must be exactly a list.")
    if type(data["fills"]) is not list:
        raise PaperTradingModelError("Field 'fills' must be exactly a list.")
    if type(data["rejections"]) is not list:
        raise PaperTradingModelError("Field 'rejections' must be exactly a list.")
    if type(data["audit_log"]) is not list:
        raise PaperTradingModelError("Field 'audit_log' must be exactly a list.")

    parsed_positions = []
    last_symbol = None
    actual_open = 0
    for i, p in enumerate(data["positions"]):
        if type(p) is not dict:
            raise PaperTradingModelError(f"Position at index {i} must be exactly a dict.")
        p_allowed = {"symbol", "quantity", "average_cost", "last_price", "market_value", "realized_pnl", "unrealized_pnl"}
        p_missing = p_allowed - set(p.keys())
        if p_missing:
            raise PaperTradingModelError(f"Position {i} missing fields: {p_missing}")
        p_extra = set(p.keys()) - p_allowed
        if p_extra:
            raise PaperTradingModelError(f"Position {i} extra fields: {p_extra}")
        
        symbol = _require_non_blank_string(f"positions[{i}].symbol", p["symbol"])
        if last_symbol is not None and symbol <= last_symbol:
            raise PaperTradingModelError(f"Positions are not canonically sorted (got {symbol} after {last_symbol}).")
        last_symbol = symbol

        qty = _require_exact_int(f"positions[{i}].quantity", p["quantity"], minimum=0)
        avg_cost = _require_finite_float(f"positions[{i}].average_cost", p["average_cost"], non_negative=(qty > 0))
        
        last_price = p["last_price"]
        if last_price is not None:
            last_price = _require_finite_float(f"positions[{i}].last_price", last_price, strictly_positive=True)
            
        market_value = _require_finite_float(f"positions[{i}].market_value", p["market_value"], non_negative=True)
        realized_pnl = _require_finite_float(f"positions[{i}].realized_pnl", p["realized_pnl"])
        unrealized_pnl = _require_finite_float(f"positions[{i}].unrealized_pnl", p["unrealized_pnl"])

        if qty > 0:
            if avg_cost <= 0:
                raise PaperTradingModelError(f"Open position {i} must have positive average_cost.")
            if last_price is None:
                raise PaperTradingModelError(f"Open position {i} must have last_price.")
            actual_open += 1
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
        if type(po) is not dict:
            raise PaperTradingModelError(f"Pending order at index {i} must be exactly a dict.")
        po_allowed = {"order_id", "symbol", "side", "quantity", "signal_time", "created_at", "strategy", "reference_price", "reserved_buy_notional"}
        po_missing = po_allowed - set(po.keys())
        if po_missing:
            raise PaperTradingModelError(f"Pending order {i} missing fields: {po_missing}")
        po_extra = set(po.keys()) - po_allowed
        if po_extra:
            raise PaperTradingModelError(f"Pending order {i} extra fields: {po_extra}")

        order_id = _require_non_blank_string(f"pending_orders[{i}].order_id", po["order_id"])
        symbol = _require_non_blank_string(f"pending_orders[{i}].symbol", po["symbol"])
        
        pending_key = (symbol, order_id)
        if last_pending_key is not None and pending_key <= last_pending_key:
            raise PaperTradingModelError(f"Pending orders are not canonically sorted (got {pending_key} after {last_pending_key}).")
        last_pending_key = pending_key

        side = _require_non_blank_string(f"pending_orders[{i}].side", po["side"])
        if side not in ("BUY", "SELL"):
            raise PaperTradingModelError(f"Pending order {i} invalid side: {side}")

        qty = _require_exact_int(f"pending_orders[{i}].quantity", po["quantity"], minimum=1)
        
        signal_time = _require_timestamp_string_or_none(f"pending_orders[{i}].signal_time", po["signal_time"])
        created_at = _require_timestamp_string_or_none(f"pending_orders[{i}].created_at", po["created_at"])
        strategy = _require_optional_string(f"pending_orders[{i}].strategy", po["strategy"])
            
        ref_price = _require_finite_float(f"pending_orders[{i}].reference_price", po["reference_price"], strictly_positive=True)
        reserved_buy_notional = _require_finite_float(f"pending_orders[{i}].reserved_buy_notional", po["reserved_buy_notional"], non_negative=True)
        if side == "SELL" and reserved_buy_notional != 0.0:
            raise PaperTradingModelError(f"Pending SELL order {i} must have reserved_buy_notional == 0.0.")

        try:
            parsed_pending_orders.append(SimulatedPortfolioPendingOrderResult(
                order_id=order_id,
                symbol=symbol,
                side=side,
                quantity=qty,
                signal_time=signal_time,
                created_at=created_at,
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

    open_position_count = _require_exact_int("open_position_count", data["open_position_count"])
    if open_position_count != actual_open:
        raise PaperTradingModelError(f"open_position_count {open_position_count} does not match actual open positions {actual_open}.")

    order_count = _require_exact_int("order_count", data["order_count"])
    if order_count != len(parsed_orders):
        raise PaperTradingModelError(f"order_count {order_count} does not match len(orders) {len(parsed_orders)}.")

    fill_count = _require_exact_int("fill_count", data["fill_count"])
    if fill_count != len(parsed_fills):
        raise PaperTradingModelError(f"fill_count {fill_count} does not match len(fills) {len(parsed_fills)}.")

    rejection_count = _require_exact_int("rejection_count", data["rejection_count"])
    if rejection_count != len(parsed_rejections):
        raise PaperTradingModelError(f"rejection_count {rejection_count} does not match len(rejections) {len(parsed_rejections)}.")

    audit_record_count = _require_exact_int("audit_record_count", data["audit_record_count"])
    if audit_record_count != len(parsed_audit_log):
        raise PaperTradingModelError(f"audit_record_count {audit_record_count} does not match len(audit_log) {len(parsed_audit_log)}.")

    total_return_pct = data["total_return_pct"]
    if total_return_pct is not None:
        total_return_pct = _require_finite_float("total_return_pct", total_return_pct)

    try:
        return SimulatedPortfolioTradingResult(
            initial_cash=_require_finite_float("initial_cash", data["initial_cash"], non_negative=True),
            final_cash=_require_finite_float("final_cash", data["final_cash"], non_negative=True),
            total_market_value=_require_finite_float("total_market_value", data["total_market_value"], non_negative=True),
            total_equity=_require_finite_float("total_equity", data["total_equity"], non_negative=True),
            realized_pnl=_require_finite_float("realized_pnl", data["realized_pnl"]),
            unrealized_pnl=_require_finite_float("unrealized_pnl", data["unrealized_pnl"]),
            total_return=_require_finite_float("total_return", data["total_return"]),
            total_return_pct=total_return_pct,
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
    if type(content) is not str:
        raise PaperTradingModelError("content must be exactly a string.")
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise PaperTradingModelError(f"Invalid JSON content: {e}")
    return deserialize_simulated_portfolio_trading_result(data)
