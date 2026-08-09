"""Strict no-I/O JSON boundary for forward portfolio traces."""

from __future__ import annotations

import json
from typing import Any

from tw_stock_tool.forward_paper.portfolio_trace_models import (
    ForwardPortfolioObservation,
    ForwardPortfolioPositionMark,
    ForwardPortfolioTrace,
    ForwardPortfolioTraceModelError,
)


class ForwardPortfolioTraceSerializationError(ValueError):
    """Raised when forward portfolio trace JSON is not exact and canonical."""


_ROOT_FIELDS = (
    "schema_version",
    "artifact_type",
    "activation_id",
    "qualification_evaluation_id",
    "qualification_sha256",
    "ledger_id",
    "ledger_sha256",
    "strategy_id",
    "initial_equity",
    "portfolio_result_sha256",
    "observations",
)
_OBSERVATION_FIELDS = (
    "observed_at",
    "cash",
    "total_market_value",
    "total_equity",
    "open_position_count",
    "pending_order_count",
    "reserved_buy_notional",
    "positions",
)
_POSITION_FIELDS = ("symbol", "quantity", "mark_price", "market_value")


def _strict_object(value: Any, fields: tuple[str, ...], path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ForwardPortfolioTraceSerializationError(
            f"{path} must be an exact object"
        )
    missing = [field for field in fields if field not in value]
    unknown = [field for field in value if field not in fields]
    if missing or unknown:
        raise ForwardPortfolioTraceSerializationError(
            f"{path} fields mismatch: missing={missing}, unknown={unknown}"
        )
    return value


def serialize_forward_portfolio_trace(
    trace: ForwardPortfolioTrace,
) -> dict[str, Any]:
    if type(trace) is not ForwardPortfolioTrace:
        raise ForwardPortfolioTraceSerializationError(
            "expected an exact ForwardPortfolioTrace"
        )
    return {
        "schema_version": trace.schema_version,
        "artifact_type": trace.artifact_type,
        "activation_id": trace.activation_id,
        "qualification_evaluation_id": trace.qualification_evaluation_id,
        "qualification_sha256": trace.qualification_sha256,
        "ledger_id": trace.ledger_id,
        "ledger_sha256": trace.ledger_sha256,
        "strategy_id": trace.strategy_id,
        "initial_equity": trace.initial_equity,
        "portfolio_result_sha256": trace.portfolio_result_sha256,
        "observations": [
            {
                "observed_at": item.observed_at,
                "cash": item.cash,
                "total_market_value": item.total_market_value,
                "total_equity": item.total_equity,
                "open_position_count": item.open_position_count,
                "pending_order_count": item.pending_order_count,
                "reserved_buy_notional": item.reserved_buy_notional,
                "positions": [
                    {
                        "symbol": position.symbol,
                        "quantity": position.quantity,
                        "mark_price": position.mark_price,
                        "market_value": position.market_value,
                    }
                    for position in item.positions
                ],
            }
            for item in trace.observations
        ],
    }


def export_forward_portfolio_trace_json(trace: ForwardPortfolioTrace) -> str:
    try:
        return json.dumps(
            serialize_forward_portfolio_trace(trace),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise ForwardPortfolioTraceSerializationError(str(exc)) from exc


def deserialize_forward_portfolio_trace(data: dict[str, Any]) -> ForwardPortfolioTrace:
    root = _strict_object(data, _ROOT_FIELDS, "$")
    if type(root["observations"]) is not list:
        raise ForwardPortfolioTraceSerializationError(
            "$.observations must be an exact list"
        )
    observations: list[ForwardPortfolioObservation] = []
    for observation_index, value in enumerate(root["observations"]):
        path = f"$.observations[{observation_index}]"
        item = _strict_object(value, _OBSERVATION_FIELDS, path)
        if type(item["positions"]) is not list:
            raise ForwardPortfolioTraceSerializationError(
                f"{path}.positions must be an exact list"
            )
        positions: list[ForwardPortfolioPositionMark] = []
        for position_index, position_value in enumerate(item["positions"]):
            position_path = f"{path}.positions[{position_index}]"
            position = _strict_object(
                position_value, _POSITION_FIELDS, position_path
            )
            try:
                positions.append(ForwardPortfolioPositionMark(**position))
            except (TypeError, ValueError, ForwardPortfolioTraceModelError) as exc:
                raise ForwardPortfolioTraceSerializationError(
                    f"{position_path} model validation failed: {exc}"
                ) from exc
        try:
            observations.append(
                ForwardPortfolioObservation(
                    observed_at=item["observed_at"],
                    cash=item["cash"],
                    total_market_value=item["total_market_value"],
                    total_equity=item["total_equity"],
                    open_position_count=item["open_position_count"],
                    pending_order_count=item["pending_order_count"],
                    reserved_buy_notional=item["reserved_buy_notional"],
                    positions=tuple(positions),
                )
            )
        except (TypeError, ValueError, ForwardPortfolioTraceModelError) as exc:
            raise ForwardPortfolioTraceSerializationError(
                f"{path} model validation failed: {exc}"
            ) from exc
    try:
        return ForwardPortfolioTrace(
            schema_version=root["schema_version"],
            artifact_type=root["artifact_type"],
            activation_id=root["activation_id"],
            qualification_evaluation_id=root["qualification_evaluation_id"],
            qualification_sha256=root["qualification_sha256"],
            ledger_id=root["ledger_id"],
            ledger_sha256=root["ledger_sha256"],
            strategy_id=root["strategy_id"],
            initial_equity=root["initial_equity"],
            portfolio_result_sha256=root["portfolio_result_sha256"],
            observations=tuple(observations),
        )
    except (TypeError, ValueError, ForwardPortfolioTraceModelError) as exc:
        raise ForwardPortfolioTraceSerializationError(
            f"$ model validation failed: {exc}"
        ) from exc


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ForwardPortfolioTraceSerializationError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ForwardPortfolioTraceSerializationError(
        f"non-finite JSON constant is not allowed: {value}"
    )


def load_forward_portfolio_trace_json(text: str) -> ForwardPortfolioTrace:
    if type(text) is not str:
        raise ForwardPortfolioTraceSerializationError(
            "JSON input must be an exact string"
        )
    try:
        payload = json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except ForwardPortfolioTraceSerializationError:
        raise
    except json.JSONDecodeError as exc:
        raise ForwardPortfolioTraceSerializationError(
            f"invalid JSON: {exc.msg}"
        ) from exc
    return deserialize_forward_portfolio_trace(payload)


__all__ = [
    "deserialize_forward_portfolio_trace",
    "export_forward_portfolio_trace_json",
    "ForwardPortfolioTraceSerializationError",
    "load_forward_portfolio_trace_json",
    "serialize_forward_portfolio_trace",
]
