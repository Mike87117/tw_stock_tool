"""Strict deterministic JSON for Phase 56.5A2-A3 broker-safety artifacts."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import json
import types
from typing import Any, NoReturn, Union, get_args, get_origin, get_type_hints

from tw_stock_tool.broker_safety.models import (
    ACCOUNT_ARTIFACT_TYPE,
    CAPABILITIES_ARTIFACT_TYPE,
    EXPECTATION_ARTIFACT_TYPE,
    LIMIT_REQUEST_ARTIFACT_TYPE,
    OPEN_ORDER_ARTIFACT_TYPE,
    POLICY_ARTIFACT_TYPE,
    POSITION_ARTIFACT_TYPE,
    RECONCILIATION_ARTIFACT_TYPE,
    SESSION_ARTIFACT_TYPE,
    BrokerAccountSnapshot,
    BrokerCapabilities,
    BrokerLimitRequest,
    BrokerLocalExpectation,
    BrokerOpenOrderSnapshot,
    BrokerPositionSnapshot,
    BrokerReconciliationResult,
    BrokerSafetyModelError,
    BrokerSafetyPolicy,
    TradingSessionSnapshot,
)


class BrokerSafetySerializationError(ValueError):
    """Raised when broker-safety JSON is not exact and canonical."""


_ARTIFACTS = {
    CAPABILITIES_ARTIFACT_TYPE: BrokerCapabilities,
    POSITION_ARTIFACT_TYPE: BrokerPositionSnapshot,
    OPEN_ORDER_ARTIFACT_TYPE: BrokerOpenOrderSnapshot,
    ACCOUNT_ARTIFACT_TYPE: BrokerAccountSnapshot,
    SESSION_ARTIFACT_TYPE: TradingSessionSnapshot,
    POLICY_ARTIFACT_TYPE: BrokerSafetyPolicy,
    EXPECTATION_ARTIFACT_TYPE: BrokerLocalExpectation,
    RECONCILIATION_ARTIFACT_TYPE: BrokerReconciliationResult,
    LIMIT_REQUEST_ARTIFACT_TYPE: BrokerLimitRequest,
}
_TOP_LEVEL_TYPES = tuple(_ARTIFACTS.values())


def _decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise BrokerSafetySerializationError("non-finite Decimal is not serializable")
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _encode(value: Any) -> Any:
    if type(value) is Decimal:
        return _decimal_text(value)
    if isinstance(value, StrEnum):
        return value.value
    if type(value) is tuple:
        return [_encode(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _encode(getattr(value, item.name)) for item in fields(value)}
    if value is None or type(value) in (str, int, bool):
        return value
    raise BrokerSafetySerializationError(
        f"unsupported broker-safety value type: {type(value).__name__}"
    )


def serialize_broker_safety_artifact(value: Any) -> dict[str, Any]:
    if type(value) not in _TOP_LEVEL_TYPES:
        raise BrokerSafetySerializationError(
            "expected an exact registered broker-safety artifact"
        )
    encoded = _encode(value)
    assert type(encoded) is dict
    return encoded


def _strict_object(value: Any, expected_type: type, path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise BrokerSafetySerializationError(f"{path}: expected an exact object")
    names = tuple(item.name for item in fields(expected_type))
    missing = tuple(name for name in names if name not in value)
    unknown = tuple(name for name in value if name not in names)
    if missing or unknown:
        raise BrokerSafetySerializationError(
            f"{path}: missing={missing}, unknown={unknown}"
        )
    return value


def _decode(value: Any, annotation: Any, path: str) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (types.UnionType, Union):
        if value is None and type(None) in args:
            return None
        candidates = tuple(item for item in args if item is not type(None))
        if len(candidates) != 1:
            raise BrokerSafetySerializationError(f"{path}: unsupported union")
        return _decode(value, candidates[0], path)
    if origin is tuple:
        if type(value) is not list or len(args) != 2 or args[1] is not Ellipsis:
            raise BrokerSafetySerializationError(f"{path}: expected an exact array")
        return tuple(
            _decode(item, args[0], f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    if annotation is Decimal:
        if type(value) is not str:
            raise BrokerSafetySerializationError(
                f"{path}: Decimal must be a canonical fixed-point string"
            )
        try:
            result = Decimal(value)
        except InvalidOperation as exc:
            raise BrokerSafetySerializationError(f"{path}: invalid Decimal") from exc
        if not result.is_finite() or _decimal_text(result) != value:
            raise BrokerSafetySerializationError(
                f"{path}: Decimal string is noncanonical or non-finite"
            )
        return result
    if isinstance(annotation, type) and issubclass(annotation, StrEnum):
        if type(value) is not str:
            raise BrokerSafetySerializationError(f"{path}: expected enum string")
        try:
            return annotation(value)
        except ValueError as exc:
            raise BrokerSafetySerializationError(
                f"{path}: unsupported {annotation.__name__} value"
            ) from exc
    if isinstance(annotation, type) and is_dataclass(annotation):
        payload = _strict_object(value, annotation, path)
        hints = get_type_hints(annotation)
        kwargs = {
            item.name: _decode(payload[item.name], hints[item.name], f"{path}.{item.name}")
            for item in fields(annotation)
        }
        try:
            return annotation(**kwargs)
        except (BrokerSafetyModelError, TypeError, ValueError) as exc:
            raise BrokerSafetySerializationError(
                f"{path}: model validation failed: {exc}"
            ) from exc
    if annotation in (str, int, bool):
        if type(value) is not annotation:
            raise BrokerSafetySerializationError(
                f"{path}: expected exact {annotation.__name__}"
            )
        return value
    raise BrokerSafetySerializationError(f"{path}: unsupported field annotation")


def deserialize_broker_safety_artifact(data: dict[str, Any]) -> Any:
    if type(data) is not dict:
        raise BrokerSafetySerializationError("$: expected an exact object")
    artifact_type = data.get("artifact_type")
    if type(artifact_type) is not str or artifact_type not in _ARTIFACTS:
        raise BrokerSafetySerializationError("$: unknown or missing artifact_type")
    return _decode(data, _ARTIFACTS[artifact_type], "$")


def export_broker_safety_artifact_json(value: Any) -> str:
    try:
        return json.dumps(
            serialize_broker_safety_artifact(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        if isinstance(exc, BrokerSafetySerializationError):
            raise
        raise BrokerSafetySerializationError(str(exc)) from exc


def _constant(value: str) -> NoReturn:
    raise BrokerSafetySerializationError(
        f"$: non-finite JSON constant is not allowed: {value}"
    )


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BrokerSafetySerializationError(f"$: duplicate JSON key: {key}")
        result[key] = value
    return result


def load_broker_safety_artifact_json(text: str) -> Any:
    if type(text) is not str:
        raise BrokerSafetySerializationError("JSON input must be an exact string")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_pairs,
            parse_constant=_constant,
        )
    except BrokerSafetySerializationError:
        raise
    except json.JSONDecodeError as exc:
        raise BrokerSafetySerializationError(
            f"$: invalid JSON: {exc.msg}"
        ) from exc
    return deserialize_broker_safety_artifact(value)


__all__ = [
    "BrokerSafetySerializationError",
    "deserialize_broker_safety_artifact",
    "export_broker_safety_artifact_json",
    "load_broker_safety_artifact_json",
    "serialize_broker_safety_artifact",
]
