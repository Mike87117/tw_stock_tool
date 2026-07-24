import json
import math
from typing import Any

from tw_stock_tool.paper_trading.models import (
    SimulatedOrder,
    SimulatedFill,
    SimulatedOrderRejection,
    SimulatedTradeEventType,
    SimulatedTradeLogRecord,
    SimulatedTradeStatus,
    PaperTradingModelError,
)
from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult


def _serialize_datetime_like(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat") and callable(value.isoformat):
        return value.isoformat()
    return str(value)


def _serialize_trade_log_record(record: SimulatedTradeLogRecord, index: int) -> dict[str, Any]:
    return {
        "sequence": _enforce_numeric(record.sequence, int, f"audit_log[{index}].sequence"),
        "record_id": record.record_id,
        "event_type": record.event_type.value,
        "status": record.status.value,
        "order_id": record.order_id,
        "symbol": record.symbol,
        "side": record.side,
        "quantity": _enforce_numeric(record.quantity, int, f"audit_log[{index}].quantity"),
        "signal_time": _serialize_datetime_like(record.signal_time),
        "order_created_at": _serialize_datetime_like(record.order_created_at),
        "expected_execution_model": record.expected_execution_model,
        "fill_time": _serialize_datetime_like(record.fill_time),
        "fill_price": None if record.fill_price is None else _enforce_numeric(record.fill_price, float, f"audit_log[{index}].fill_price"),
        "fee": _enforce_numeric(record.fee, float, f"audit_log[{index}].fee"),
        "tax": _enforce_numeric(record.tax, float, f"audit_log[{index}].tax"),
        "slippage": _enforce_numeric(record.slippage, float, f"audit_log[{index}].slippage"),
        "strategy_name": record.strategy_name,
        "strategy_metadata": dict(record.strategy_metadata),
        "risk_allowed": record.risk_allowed,
        "risk_rejection_reasons": list(record.risk_rejection_reasons),
        "guard_metadata": dict(record.guard_metadata),
        "error_code": record.error_code,
        "error_message": record.error_message,
    }


def _deserialize_trade_log_record(data: Any, index: int) -> SimulatedTradeLogRecord:
    if not isinstance(data, dict):
        raise PaperTradingModelError(f"Audit record at index {index} must be a dict.")
    fields = {
        "sequence", "record_id", "event_type", "status", "order_id", "symbol", "side",
        "quantity", "signal_time", "order_created_at", "expected_execution_model", "fill_time",
        "fill_price", "fee", "tax", "slippage", "strategy_name", "strategy_metadata",
        "risk_allowed", "risk_rejection_reasons", "guard_metadata", "error_code", "error_message",
    }
    missing = fields - set(data)
    extra = set(data) - fields
    if missing:
        raise PaperTradingModelError(f"Audit record {index} missing fields: {missing}")
    if extra:
        raise PaperTradingModelError(f"Audit record {index} extra fields: {extra}")
    if not isinstance(data["risk_rejection_reasons"], list):
        raise PaperTradingModelError(f"Audit record {index} risk_rejection_reasons must be a list.")
    try:
        return SimulatedTradeLogRecord(
            sequence=_enforce_numeric(data["sequence"], int, f"audit_log[{index}].sequence"),
            record_id=str(data["record_id"]),
            event_type=SimulatedTradeEventType(data["event_type"]),
            status=SimulatedTradeStatus(data["status"]),
            order_id=str(data["order_id"]),
            symbol=str(data["symbol"]),
            side=str(data["side"]),
            quantity=_enforce_numeric(data["quantity"], int, f"audit_log[{index}].quantity"),
            signal_time=data["signal_time"],
            order_created_at=data["order_created_at"],
            expected_execution_model=data["expected_execution_model"],
            fill_time=data["fill_time"],
            fill_price=None if data["fill_price"] is None else _enforce_numeric(data["fill_price"], float, f"audit_log[{index}].fill_price"),
            fee=_enforce_numeric(data["fee"], float, f"audit_log[{index}].fee"),
            tax=_enforce_numeric(data["tax"], float, f"audit_log[{index}].tax"),
            slippage=_enforce_numeric(data["slippage"], float, f"audit_log[{index}].slippage"),
            strategy_name=None if data["strategy_name"] is None else str(data["strategy_name"]),
            strategy_metadata=data["strategy_metadata"],
            risk_allowed=data["risk_allowed"],
            risk_rejection_reasons=tuple(data["risk_rejection_reasons"]),
            guard_metadata=data["guard_metadata"],
            error_code=None if data["error_code"] is None else str(data["error_code"]),
            error_message=None if data["error_message"] is None else str(data["error_message"]),
        )
    except (ValueError, TypeError) as exc:
        raise PaperTradingModelError(f"Audit record {index} invalid: {exc}") from exc


def _serialize_simulated_order(o: SimulatedOrder, index: int | str) -> dict[str, Any]:
    if not isinstance(o.metadata, dict):
        raise PaperTradingModelError(f"Order {index} metadata must be a dict.")
    try:
        json.dumps(o.metadata)
    except (TypeError, ValueError):
        raise PaperTradingModelError(f"Order {index} metadata is not JSON serializable.")

    return {
        "order_id": str(o.order_id),
        "symbol": str(o.symbol),
        "side": str(o.side),
        "quantity": _enforce_numeric(o.quantity, int, f"orders[{index}].quantity"),
        "signal_time": _serialize_datetime_like(o.signal_time),
        "created_at": _serialize_datetime_like(o.created_at),
        "strategy": str(o.strategy) if o.strategy is not None else None,
        "metadata": dict(o.metadata),
    }


def _serialize_simulated_fill(f: SimulatedFill, index: int | str) -> dict[str, Any]:
    return {
        "order_id": str(f.order_id),
        "symbol": str(f.symbol),
        "side": str(f.side),
        "quantity": _enforce_numeric(f.quantity, int, f"fills[{index}].quantity"),
        "price": _enforce_numeric(f.price, float, f"fills[{index}].price"),
        "filled_at": _serialize_datetime_like(f.filled_at),
        "fee": _enforce_numeric(f.fee, float, f"fills[{index}].fee"),
        "tax": _enforce_numeric(f.tax, float, f"fills[{index}].tax"),
        "slippage": _enforce_numeric(f.slippage, float, f"fills[{index}].slippage"),
    }


def _serialize_simulated_rejection(r: SimulatedOrderRejection, index: int | str) -> dict[str, Any]:
    c_ord = r.candidate_order
    return {
        "candidate_order": {
            "order_id": str(c_ord.order_id),
            "symbol": str(c_ord.symbol),
            "side": str(c_ord.side),
            "quantity": _enforce_numeric(c_ord.quantity, int, f"rejections[{index}].candidate_order.quantity"),
            "signal_time": _serialize_datetime_like(c_ord.signal_time),
            "created_at": _serialize_datetime_like(c_ord.created_at),
            "strategy": str(c_ord.strategy) if c_ord.strategy is not None else None,
            "metadata": dict(c_ord.metadata),
        },
        "reasons": list(r.reasons),
    }


def serialize_simulated_paper_trading_result(result: SimulatedPaperTradingResult) -> dict[str, Any]:
    orders = [_serialize_simulated_order(o, i) for i, o in enumerate(result.orders)]
    fills = [_serialize_simulated_fill(f, i) for i, f in enumerate(result.fills)]
    rejections = [_serialize_simulated_rejection(r, i) for i, r in enumerate(result.rejections)]
    audit_log = [_serialize_trade_log_record(record, i) for i, record in enumerate(result.audit_log)]

    return {
        "schema_version": 3,
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
        "audit_log": audit_log,
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


def _deserialize_simulated_order(o: Any, index: int | str) -> SimulatedOrder:
    if not isinstance(o, dict):
        raise PaperTradingModelError(f"Order at index {index} must be a dict.")
    o_allowed = {"order_id", "symbol", "side", "quantity", "signal_time", "created_at", "strategy", "metadata"}
    o_missing = o_allowed - set(o.keys())
    if o_missing:
        raise PaperTradingModelError(f"Order {index} missing fields: {o_missing}")
    o_extra = set(o.keys()) - o_allowed
    if o_extra:
        raise PaperTradingModelError(f"Order {index} extra fields: {o_extra}")

    if not isinstance(o["metadata"], dict):
        raise PaperTradingModelError(f"Order {index} metadata must be a dict.")

    try:
        json.dumps(o["metadata"])
    except (TypeError, ValueError):
        raise PaperTradingModelError(f"Order {index} metadata is not JSON serializable.")

    qty = _enforce_numeric(o["quantity"], int, f"orders[{index}].quantity")

    try:
        return SimulatedOrder(
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
        raise PaperTradingModelError(f"Order {index} invalid: {e}")


def _deserialize_simulated_fill(f: Any, index: int | str) -> SimulatedFill:
    if not isinstance(f, dict):
        raise PaperTradingModelError(f"Fill at index {index} must be a dict.")
    f_allowed = {"order_id", "symbol", "side", "quantity", "price", "filled_at", "fee", "tax", "slippage"}
    f_missing = f_allowed - set(f.keys())
    if f_missing:
        raise PaperTradingModelError(f"Fill {index} missing fields: {f_missing}")
    f_extra = set(f.keys()) - f_allowed
    if f_extra:
        raise PaperTradingModelError(f"Fill {index} extra fields: {f_extra}")

    qty = _enforce_numeric(f["quantity"], int, f"fills[{index}].quantity")
    price = _enforce_numeric(f["price"], float, f"fills[{index}].price")
    fee = _enforce_numeric(f["fee"], float, f"fills[{index}].fee")
    tax = _enforce_numeric(f["tax"], float, f"fills[{index}].tax")
    slippage = _enforce_numeric(f["slippage"], float, f"fills[{index}].slippage")

    try:
        return SimulatedFill(
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
        raise PaperTradingModelError(f"Fill {index} invalid: {e}")


def _deserialize_simulated_rejection(r: Any, index: int | str) -> SimulatedOrderRejection:
    if not isinstance(r, dict):
        raise PaperTradingModelError(f"Rejection at index {index} must be a dict.")
    r_allowed = {"candidate_order", "reasons"}
    r_missing = r_allowed - set(r.keys())
    if r_missing:
        raise PaperTradingModelError(f"Rejection {index} missing fields: {r_missing}")
    r_extra = set(r.keys()) - r_allowed
    if r_extra:
        raise PaperTradingModelError(f"Rejection {index} extra fields: {r_extra}")

    c_ord = r["candidate_order"]
    if not isinstance(c_ord, dict):
        raise PaperTradingModelError(f"Rejection {index} candidate_order must be a dict.")

    c_allowed = {"order_id", "symbol", "side", "quantity", "signal_time", "created_at", "strategy", "metadata"}
    c_missing = c_allowed - set(c_ord.keys())
    if c_missing:
        raise PaperTradingModelError(f"Rejection {index} candidate_order missing fields: {c_missing}")

    qty = _enforce_numeric(c_ord["quantity"], int, f"rejections[{index}].candidate_order.quantity")
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
            raise PaperTradingModelError(f"Rejection {index} reasons must be a list.")
        reasons = tuple(str(x) for x in r["reasons"])
        return SimulatedOrderRejection(
            candidate_order=candidate_obj,
            reasons=reasons,
        )
    except Exception as e:
        raise PaperTradingModelError(f"Rejection {index} invalid: {e}")


def deserialize_simulated_paper_trading_result(data: dict[str, Any]) -> SimulatedPaperTradingResult:
    if not isinstance(data, dict):
        raise PaperTradingModelError("Top-level data must be a dict.")

    schema_version = data.get("schema_version")
    if schema_version not in (1, 2, 3):
        raise PaperTradingModelError(f"Unsupported schema_version: {schema_version}")

    allowed_keys = {
        "schema_version", "result_type", "symbol", "initial_cash", "final_cash",
        "final_position_quantity", "average_cost", "realized_pnl", "unrealized_pnl",
        "total_equity", "order_count", "fill_count", "open_position_count",
        "orders", "fills"
    }
    if schema_version >= 2:
        allowed_keys.add("rejections")
    if schema_version >= 3:
        allowed_keys.add("audit_log")

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

    parsed_orders = [_deserialize_simulated_order(o, i) for i, o in enumerate(data["orders"])]
    parsed_fills = [_deserialize_simulated_fill(f, i) for i, f in enumerate(data["fills"])]

    parsed_rejections = []
    if "rejections" in data:
        if not isinstance(data["rejections"], list):
            raise PaperTradingModelError("Field 'rejections' must be a list.")
        parsed_rejections = [_deserialize_simulated_rejection(r, i) for i, r in enumerate(data["rejections"])]

    parsed_audit_log = []
    if schema_version >= 3:
        if not isinstance(data["audit_log"], list):
            raise PaperTradingModelError("Field 'audit_log' must be a list.")
        parsed_audit_log = [_deserialize_trade_log_record(record, i) for i, record in enumerate(data["audit_log"])]

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
            audit_log=tuple(parsed_audit_log),
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
