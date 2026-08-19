"""Strict JSON namespace for non-promotable TEST-only mutation artifacts."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import json
import types
from typing import Any, NoReturn, Union, get_args, get_origin, get_type_hints

from tw_stock_tool.broker_safety.test_mutation_models import (
    TEST_AUTHORIZATION_ARTIFACT_TYPE,
    TEST_ENVELOPE_ARTIFACT_TYPE,
    TEST_POLICY_ARTIFACT_TYPE,
    TEST_SUBMISSION_ARTIFACT_TYPE,
    BrokerTestExecutionAuthorization,
    BrokerTestMutationEnvelope,
    BrokerTestMutationModelError,
    BrokerTestMutationPolicy,
    BrokerTestSubmissionRecord,
)


class BrokerTestMutationSerializationError(ValueError):
    """Raised when TEST JSON is inexact or belongs to the live artifact family."""


_ARTIFACTS = {
    TEST_POLICY_ARTIFACT_TYPE: BrokerTestMutationPolicy,
    TEST_ENVELOPE_ARTIFACT_TYPE: BrokerTestMutationEnvelope,
    TEST_AUTHORIZATION_ARTIFACT_TYPE: BrokerTestExecutionAuthorization,
    TEST_SUBMISSION_ARTIFACT_TYPE: BrokerTestSubmissionRecord,
}
_TOP_LEVEL_TYPES = tuple(_ARTIFACTS.values())


def _decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise BrokerTestMutationSerializationError("non-finite Decimal is not serializable")
    return "0" if value == 0 else format(value.normalize(), "f")


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
    raise BrokerTestMutationSerializationError(
        f"unsupported TEST mutation value type: {type(value).__name__}"
    )


def serialize_test_mutation_artifact(value: Any) -> dict[str, Any]:
    if type(value) not in _TOP_LEVEL_TYPES:
        raise BrokerTestMutationSerializationError(
            "expected an exact registered TEST-only mutation artifact"
        )
    encoded = _encode(value)
    assert type(encoded) is dict
    return encoded


def _strict_object(value: Any, expected_type: type, path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise BrokerTestMutationSerializationError(f"{path}: expected an exact object")
    names = tuple(item.name for item in fields(expected_type))
    missing = tuple(name for name in names if name not in value)
    unknown = tuple(name for name in value if name not in names)
    if missing or unknown:
        raise BrokerTestMutationSerializationError(
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
            raise BrokerTestMutationSerializationError(f"{path}: unsupported union")
        return _decode(value, candidates[0], path)
    if origin is tuple:
        if type(value) is not list or len(args) != 2 or args[1] is not Ellipsis:
            raise BrokerTestMutationSerializationError(f"{path}: expected an exact array")
        return tuple(_decode(item, args[0], f"{path}[{index}]") for index, item in enumerate(value))
    if annotation is Decimal:
        if type(value) is not str:
            raise BrokerTestMutationSerializationError(f"{path}: Decimal must be a string")
        try:
            result = Decimal(value)
        except InvalidOperation as exc:
            raise BrokerTestMutationSerializationError(f"{path}: invalid Decimal") from exc
        if not result.is_finite() or _decimal_text(result) != value:
            raise BrokerTestMutationSerializationError(f"{path}: Decimal is noncanonical")
        return result
    if isinstance(annotation, type) and issubclass(annotation, StrEnum):
        if type(value) is not str:
            raise BrokerTestMutationSerializationError(f"{path}: expected enum string")
        try:
            return annotation(value)
        except ValueError as exc:
            raise BrokerTestMutationSerializationError(f"{path}: unsupported enum value") from exc
    if isinstance(annotation, type) and is_dataclass(annotation):
        payload = _strict_object(value, annotation, path)
        hints = get_type_hints(annotation)
        try:
            return annotation(
                **{
                    item.name: _decode(payload[item.name], hints[item.name], f"{path}.{item.name}")
                    for item in fields(annotation)
                }
            )
        except (BrokerTestMutationModelError, TypeError, ValueError) as exc:
            raise BrokerTestMutationSerializationError(f"{path}: model validation failed: {exc}") from exc
    if annotation in (str, int, bool):
        if type(value) is not annotation:
            raise BrokerTestMutationSerializationError(f"{path}: expected exact {annotation.__name__}")
        return value
    raise BrokerTestMutationSerializationError(f"{path}: unsupported field annotation")


def deserialize_test_mutation_artifact(data: dict[str, Any]) -> Any:
    if type(data) is not dict:
        raise BrokerTestMutationSerializationError("$: expected an exact object")
    artifact_type = data.get("artifact_type")
    if type(artifact_type) is not str or artifact_type not in _ARTIFACTS:
        raise BrokerTestMutationSerializationError("$: unknown or non-TEST artifact_type")
    return _decode(data, _ARTIFACTS[artifact_type], "$")


def export_test_mutation_artifact_json(value: Any) -> str:
    try:
        return json.dumps(
            serialize_test_mutation_artifact(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        if isinstance(exc, BrokerTestMutationSerializationError):
            raise
        raise BrokerTestMutationSerializationError(str(exc)) from exc


def _constant(value: str) -> NoReturn:
    raise BrokerTestMutationSerializationError(f"$: non-finite JSON constant: {value}")


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BrokerTestMutationSerializationError(f"$: duplicate JSON key: {key}")
        result[key] = value
    return result


def load_test_mutation_artifact_json(text: str) -> Any:
    if type(text) is not str:
        raise BrokerTestMutationSerializationError("JSON input must be an exact string")
    try:
        data = json.loads(text, object_pairs_hook=_object_pairs, parse_constant=_constant)
    except BrokerTestMutationSerializationError:
        raise
    except json.JSONDecodeError as exc:
        raise BrokerTestMutationSerializationError(f"$: invalid JSON: {exc.msg}") from exc
    return deserialize_test_mutation_artifact(data)


__all__ = [
    "BrokerTestMutationSerializationError",
    "deserialize_test_mutation_artifact",
    "export_test_mutation_artifact_json",
    "load_test_mutation_artifact_json",
    "serialize_test_mutation_artifact",
]
