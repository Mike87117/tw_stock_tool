import json
import math
from typing import Any

from tw_stock_tool.paper_trading.models import (
    SimulatedOrder,
    SimulatedFill,
    SimulatedOrderRejection,
    PaperTradingModelError,
)
from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult


def _serialize_datetime_like(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat") and callable(value.isoformat):
        return value.isoformat()
    return str(value)


def serialize_simulated_paper_trading_result(result: SimulatedPaperTradingResult) -> dict[str, Any]:
    orders = []
    for i, o in enumerate(result.orders):
        if not isinstance(o.metadata, dict):
            raise PaperTradingModelError(f"Order {i} metadata must be a dict.")
        try:
            json.dumps(o.metadata)
        except (TypeError, ValueError):
            raise PaperTradingModelError(f"Order {i} metadata is not JSON serializable.")

        orders.append({
            "order_id": str(o.order_id),
            "symbol": str(o.symbol),
            "side": str(o.side),
            "quantity": _enforce_numeric(o.quantity, int, f"orders[{i}].quantity"),
            "signal_time": _serialize_datetime_like(o.signal_time),
            "created_at": _serialize_datetime_like(o.created_at),
            "strategy": str(o.strategy) if o.strategy is not None else None,
            "metadata": dict(o.metadata),
        })
    
    fills = []
    for i, f in enumerate(result.fills):
        fills.append({
            "order_id": str(f.order_id),
            "symbol": str(f.symbol),
            "side": str(f.side),
            "quantity": _enforce_numeric(f.quantity, int, f"fills[{i}].quantity"),
            "price": _enforce_numeric(f.price, float, f"fills[{i}].price"),
            "filled_at": _serialize_datetime_like(f.filled_at),
            "fee": _enforce_numeric(f.fee, float, f"fills[{i}].fee"),
            "tax": _enforce_numeric(f.tax, float, f"fills[{i}].tax"),
            "slippage": _enforce_numeric(f.slippage, float, f"fills[{i}].slippage"),
        })

    rejections = []
    for i, r in enumerate(result.rejections):
        c_ord = r.candidate_order
        rejections.append({
            "candidate_order": {
                "order_id": str(c_ord.order_id),
                "symbol": str(c_ord.symbol),
                "side": str(c_ord.side),
                "quantity": _enforce_numeric(c_ord.quantity, int, f"rejections[{i}].candidate_order.quantity"),
                "signal_time": _serialize_datetime_like(c_ord.signal_time),
                "created_at": _serialize_datetime_like(c_ord.created_at),
                "strategy": str(c_ord.strategy) if c_ord.strategy is not None else None,
                "metadata": dict(c_ord.metadata),
            },
            "reasons": list(r.reasons),
        })

    return {
        "schema_version": 2,
        "result_type": "simulated_paper_trading_result",
        "symbol": str(result.symbol),
        "initial_cash": _enforce_numeric(result.initial_cash, float, "initial_cash"),
        "final_cash": _enforce_numeric(result.final_cash, float, "final_cash"),
        "final_position_quantity": _enforce_numeric(result.final_position_quantity, int, "final_position_quantity"),
        "average_cost": _enforce_numeric(result.average_cost, float, "average_cost"),
        "realized_pnl": _enforce_numeric(result.realized_pnl, float, "realized_pnl"),
        "unrealized_pnl": _enforce_numeric(result.unrealized_pnl, float, "unrealized_pnl"),
        "total_equity": _enforce_numeric(result.total_equity, float, "total_equity"),
        "order_count": _enforce_numeric(result.order_count, int, "order_count"),
        "fill_count": _enforce_numeric(result.fill_count, int, "fill_count"),
        "open_position_count": _enforce_numeric(result.open_position_count, int, "open_position_count"),
        "orders": orders,
        "fills": fills,
        "rejections": rejections,
    }


def _enforce_numeric(val: Any, t: type, name: str) -> Any:
    if isinstance(val, bool):
        raise PaperTradingModelError(f"Field {name} cannot be a boolean.")
    
    if t is int:
        if isinstance(val, float):
            if not math.isfinite(val):
                raise PaperTradingModelError(f"Field {name} must be finite.")
            if not val.is_integer():
                raise PaperTradingModelError(f"Field {name} must be an integer, got fractional value.")

    try:
        converted = t(val)
    except (ValueError, TypeError, OverflowError):
        raise PaperTradingModelError(f"Field {name} must be convertible to {t.__name__}.")
        
    if t is float and not math.isfinite(converted):
        raise PaperTradingModelError(f"Field {name} must be finite.")
        
    return converted


def deserialize_simulated_paper_trading_result(data: dict[str, Any]) -> SimulatedPaperTradingResult:
    if not isinstance(data, dict):
        raise PaperTradingModelError("Top-level data must be a dict.")

    schema_version = data.get("schema_version")
    if schema_version not in (1, 2):
        raise PaperTradingModelError(f"Unsupported schema_version: {schema_version}")

    allowed_keys = {
        "schema_version", "result_type", "symbol", "initial_cash", "final_cash",
        "final_position_quantity", "average_cost", "realized_pnl", "unrealized_pnl",
        "total_equity", "order_count", "fill_count", "open_position_count",
        "orders", "fills"
    }
    if schema_version >= 2:
        allowed_keys.add("rejections")

    missing = allowed_keys - set(data.keys())
    if missing:
        raise PaperTradingModelError(f"Missing required top-level fields: {missing}")
    
    extra = set(data.keys()) - allowed_keys
    if extra:
        raise PaperTradingModelError(f"Extra unknown top-level fields: {extra}")
    
    if data["result_type"] != "simulated_paper_trading_result":
        raise PaperTradingModelError(f"Unsupported result_type: {data['result_type']}")

    if not isinstance(data["orders"], list):
        raise PaperTradingModelError("Field 'orders' must be a list.")
    if not isinstance(data["fills"], list):
        raise PaperTradingModelError("Field 'fills' must be a list.")

    parsed_orders = []
    for i, o in enumerate(data["orders"]):
        if not isinstance(o, dict):
            raise PaperTradingModelError(f"Order at index {i} must be a dict.")
        o_allowed = {"order_id", "symbol", "side", "quantity", "signal_time", "created_at", "strategy", "metadata"}
        o_missing = o_allowed - set(o.keys())
        if o_missing:
            raise PaperTradingModelError(f"Order {i} missing fields: {o_missing}")
        o_extra = set(o.keys()) - o_allowed
        if o_extra:
            raise PaperTradingModelError(f"Order {i} extra fields: {o_extra}")
        
        if not isinstance(o["metadata"], dict):
            raise PaperTradingModelError(f"Order {i} metadata must be a dict.")
        
        try:
            json.dumps(o["metadata"])
        except (TypeError, ValueError):
            raise PaperTradingModelError(f"Order {i} metadata is not JSON serializable.")

        qty = _enforce_numeric(o["quantity"], int, f"orders[{i}].quantity")

        try:
            order_obj = SimulatedOrder(
                order_id=str(o["order_id"]),
                symbol=str(o["symbol"]),
                side=str(o["side"]),  # type check implicitly in SimulatedOrder
                quantity=qty,
                signal_time=str(o["signal_time"]) if o["signal_time"] is not None else None,
                created_at=str(o["created_at"]) if o["created_at"] is not None else None,
                strategy=str(o["strategy"]) if o["strategy"] is not None else None,
                metadata=dict(o["metadata"]),
            )
        except Exception as e:
            raise PaperTradingModelError(f"Order {i} invalid: {e}")
        parsed_orders.append(order_obj)
        
    parsed_fills = []
    for i, f in enumerate(data["fills"]):
        if not isinstance(f, dict):
            raise PaperTradingModelError(f"Fill at index {i} must be a dict.")
        f_allowed = {"order_id", "symbol", "side", "quantity", "price", "filled_at", "fee", "tax", "slippage"}
        f_missing = f_allowed - set(f.keys())
        if f_missing:
            raise PaperTradingModelError(f"Fill {i} missing fields: {f_missing}")
        f_extra = set(f.keys()) - f_allowed
        if f_extra:
            raise PaperTradingModelError(f"Fill {i} extra fields: {f_extra}")
        
        qty = _enforce_numeric(f["quantity"], int, f"fills[{i}].quantity")
        price = _enforce_numeric(f["price"], float, f"fills[{i}].price")
        fee = _enforce_numeric(f["fee"], float, f"fills[{i}].fee")
        tax = _enforce_numeric(f["tax"], float, f"fills[{i}].tax")
        slippage = _enforce_numeric(f["slippage"], float, f"fills[{i}].slippage")
        
        try:
            fill_obj = SimulatedFill(
                order_id=str(f["order_id"]),
                symbol=str(f["symbol"]),
                side=str(f["side"]),
                quantity=qty,
                price=price,
                filled_at=str(f["filled_at"]) if f["filled_at"] is not None else None,
                fee=fee,
                tax=tax,
                slippage=slippage,
            )
        except Exception as e:
            raise PaperTradingModelError(f"Fill {i} invalid: {e}")
        parsed_fills.append(fill_obj)

    parsed_rejections = []
    if "rejections" in data:
        if not isinstance(data["rejections"], list):
            raise PaperTradingModelError("Field 'rejections' must be a list.")
        for i, r in enumerate(data["rejections"]):
            if not isinstance(r, dict):
                raise PaperTradingModelError(f"Rejection at index {i} must be a dict.")
            r_allowed = {"candidate_order", "reasons"}
            r_missing = r_allowed - set(r.keys())
            if r_missing:
                raise PaperTradingModelError(f"Rejection {i} missing fields: {r_missing}")
            r_extra = set(r.keys()) - r_allowed
            if r_extra:
                raise PaperTradingModelError(f"Rejection {i} extra fields: {r_extra}")
            
            c_ord = r["candidate_order"]
            if not isinstance(c_ord, dict):
                raise PaperTradingModelError(f"Rejection {i} candidate_order must be a dict.")
            
            c_allowed = {"order_id", "symbol", "side", "quantity", "signal_time", "created_at", "strategy", "metadata"}
            c_missing = c_allowed - set(c_ord.keys())
            if c_missing:
                raise PaperTradingModelError(f"Rejection {i} candidate_order missing fields: {c_missing}")
            
            qty = _enforce_numeric(c_ord["quantity"], int, f"rejections[{i}].candidate_order.quantity")
            try:
                candidate_obj = SimulatedOrder(
                    order_id=str(c_ord["order_id"]),
                    symbol=str(c_ord["symbol"]),
                    side=str(c_ord["side"]),
                    quantity=qty,
                    signal_time=str(c_ord["signal_time"]) if c_ord["signal_time"] is not None else None,
                    created_at=str(c_ord["created_at"]) if c_ord["created_at"] is not None else None,
                    strategy=str(c_ord["strategy"]) if c_ord["strategy"] is not None else None,
                    metadata=dict(c_ord["metadata"]) if "metadata" in c_ord else {},
                )
                
                if not isinstance(r["reasons"], list):
                    raise PaperTradingModelError(f"Rejection {i} reasons must be a list.")
                reasons = tuple(str(x) for x in r["reasons"])
                rejection_obj = SimulatedOrderRejection(
                    candidate_order=candidate_obj,
                    reasons=reasons,
                )
            except Exception as e:
                raise PaperTradingModelError(f"Rejection {i} invalid: {e}")
            parsed_rejections.append(rejection_obj)

    try:
        return SimulatedPaperTradingResult(
            symbol=str(data["symbol"]),
            initial_cash=_enforce_numeric(data["initial_cash"], float, "initial_cash"),
            final_cash=_enforce_numeric(data["final_cash"], float, "final_cash"),
            final_position_quantity=_enforce_numeric(data["final_position_quantity"], int, "final_position_quantity"),
            average_cost=_enforce_numeric(data["average_cost"], float, "average_cost"),
            realized_pnl=_enforce_numeric(data["realized_pnl"], float, "realized_pnl"),
            unrealized_pnl=_enforce_numeric(data["unrealized_pnl"], float, "unrealized_pnl"),
            total_equity=_enforce_numeric(data["total_equity"], float, "total_equity"),
            order_count=_enforce_numeric(data["order_count"], int, "order_count"),
            fill_count=_enforce_numeric(data["fill_count"], int, "fill_count"),
            open_position_count=_enforce_numeric(data["open_position_count"], int, "open_position_count"),
            orders=tuple(parsed_orders),
            fills=tuple(parsed_fills),
            rejections=tuple(parsed_rejections),
        )
    except PaperTradingModelError:
        raise
    except Exception as e:
        raise PaperTradingModelError(f"Error creating SimulatedPaperTradingResult: {e}")


def export_simulated_paper_trading_result_json(result: SimulatedPaperTradingResult) -> str:
    data = serialize_simulated_paper_trading_result(result)
    try:
        return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    except (TypeError, ValueError) as e:
        raise PaperTradingModelError(f"JSON export failed: {e}")


def load_simulated_paper_trading_result_json(content: str) -> SimulatedPaperTradingResult:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise PaperTradingModelError(f"Invalid JSON content: {e}")
    return deserialize_simulated_paper_trading_result(data)
