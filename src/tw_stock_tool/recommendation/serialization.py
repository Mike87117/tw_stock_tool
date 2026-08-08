"""Strict deterministic JSON serialization for RecommendationEvidence."""

from __future__ import annotations

from collections.abc import Mapping
import json
import math
from typing import Any, NoReturn

from tw_stock_tool.qualification import (
    QualificationSerializationError,
    deserialize_strategy_qualification_result,
    serialize_strategy_qualification_result,
)
from tw_stock_tool.recommendation.models import (
    RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE,
    RECOMMENDATION_EVIDENCE_SCHEMA_VERSION,
    CurrentSignalSnapshot,
    RecommendationEvidence,
    RecommendationModelError,
)


class RecommendationSerializationError(ValueError):
    """Raised when recommendation evidence cannot be serialized or loaded."""


_ROOT_KEYS = (
    "schema_version",
    "artifact_type",
    "recommendation_id",
    "generated_at",
    "source_qualification_evaluation_id",
    "promotion_state",
    "strategy_id",
    "strategy_parameters",
    "qualification_finding_codes",
    "signal_snapshot",
    "action",
    "qualification",
)
_SIGNAL_KEYS = ("symbol", "observed_at", "signal", "score", "latest_close")


def _fail(path: str, message: str) -> NoReturn:
    raise RecommendationSerializationError(f"{path}: {message}")


def _json_value(value: Any, path: str) -> Any:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            _fail(path, "non-finite float values are not supported")
        return value
    if isinstance(value, (list, tuple)):
        return [
            _json_value(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key in sorted(value):
            if type(key) is not str or not key or key.strip() != key:
                _fail(path, "mapping keys must be clean exact strings")
            output[key] = _json_value(value[key], f"{path}.{key}")
        return output
    _fail(path, f"unsupported value type: {type(value).__name__}")


def serialize_recommendation_evidence(
    evidence: RecommendationEvidence,
) -> dict[str, Any]:
    """Serialize one validated RecommendationEvidence to a deterministic dictionary."""
    if not isinstance(evidence, RecommendationEvidence):
        _fail("$", "expected a RecommendationEvidence instance")
    snapshot = evidence.signal_snapshot
    return {
        "schema_version": evidence.schema_version,
        "artifact_type": evidence.artifact_type,
        "recommendation_id": evidence.recommendation_id,
        "generated_at": evidence.generated_at,
        "source_qualification_evaluation_id": (
            evidence.source_qualification_evaluation_id
        ),
        "promotion_state": evidence.promotion_state,
        "strategy_id": evidence.strategy_id,
        "strategy_parameters": _json_value(
            evidence.strategy_parameters,
            "$.strategy_parameters",
        ),
        "qualification_finding_codes": list(evidence.qualification_finding_codes),
        "signal_snapshot": {
            "symbol": snapshot.symbol,
            "observed_at": snapshot.observed_at,
            "signal": snapshot.signal,
            "score": snapshot.score,
            "latest_close": snapshot.latest_close,
        },
        "action": evidence.action,
        "qualification": serialize_strategy_qualification_result(
            evidence.qualification
        ),
    }


def _exact_keys(value: dict[str, Any], expected: tuple[str, ...], path: str) -> None:
    missing = [key for key in expected if key not in value]
    unknown = [key for key in value if key not in expected]
    if missing:
        _fail(path, f"missing field(s): {', '.join(missing)}")
    if unknown:
        _fail(path, f"unknown field(s): {', '.join(unknown)}")


def _dict(value: Any, path: str, expected: tuple[str, ...]) -> dict[str, Any]:
    if type(value) is not dict:
        _fail(path, "expected an exact dictionary")
    _exact_keys(value, expected, path)
    return value


def _list(value: Any, path: str) -> list[Any]:
    if type(value) is not list:
        _fail(path, "expected a list")
    return value


def _native_json(value: Any, path: str) -> Any:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            _fail(path, "non-finite float values are not supported")
        return value
    if type(value) is list:
        return [
            _native_json(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if type(value) is dict:
        output: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str or not key or key.strip() != key:
                _fail(path, "mapping keys must be clean exact strings")
            output[key] = _native_json(item, f"{path}.{key}")
        return output
    _fail(path, f"unsupported value type: {type(value).__name__}")


def _construct(path: str, constructor, **kwargs):
    try:
        return constructor(**kwargs)
    except RecommendationModelError as exc:
        raise RecommendationSerializationError(
            f"{path}: model validation failed: {exc}"
        ) from exc


def deserialize_recommendation_evidence(
    data: dict[str, Any],
) -> RecommendationEvidence:
    """Deserialize a strict dictionary payload and revalidate canonical action."""
    root = _dict(data, "$", _ROOT_KEYS)
    if root["schema_version"] != RECOMMENDATION_EVIDENCE_SCHEMA_VERSION:
        _fail(
            "$.schema_version",
            f"unsupported schema version {root['schema_version']!r}",
        )
    if root["artifact_type"] != RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE:
        _fail(
            "$.artifact_type",
            f"unsupported artifact type {root['artifact_type']!r}",
        )

    qualification_raw = root["qualification"]
    if type(qualification_raw) is not dict:
        _fail("$.qualification", "expected an exact dictionary")
    try:
        qualification = deserialize_strategy_qualification_result(
            qualification_raw
        )
    except QualificationSerializationError as exc:
        raise RecommendationSerializationError(
            f"$.qualification: {exc}"
        ) from exc

    snapshot_raw = _dict(root["signal_snapshot"], "$.signal_snapshot", _SIGNAL_KEYS)
    snapshot = _construct(
        "$.signal_snapshot",
        CurrentSignalSnapshot,
        **snapshot_raw,
    )

    parameters_raw = root["strategy_parameters"]
    if type(parameters_raw) is not dict:
        _fail("$.strategy_parameters", "expected an exact dictionary")
    parameters = _native_json(parameters_raw, "$.strategy_parameters")
    codes = _list(
        root["qualification_finding_codes"],
        "$.qualification_finding_codes",
    )
    return _construct(
        "$",
        RecommendationEvidence,
        schema_version=root["schema_version"],
        artifact_type=root["artifact_type"],
        recommendation_id=root["recommendation_id"],
        generated_at=root["generated_at"],
        source_qualification_evaluation_id=(
            root["source_qualification_evaluation_id"]
        ),
        promotion_state=root["promotion_state"],
        strategy_id=root["strategy_id"],
        strategy_parameters=parameters,
        qualification_finding_codes=tuple(codes),
        signal_snapshot=snapshot,
        action=root["action"],
        qualification=qualification,
    )


def export_recommendation_evidence_json(
    evidence: RecommendationEvidence,
) -> str:
    """Export deterministic UTF-8 JSON text with a trailing newline."""
    return (
        json.dumps(
            serialize_recommendation_evidence(evidence),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
            sort_keys=True,
        )
        + "\n"
    )


def _reject_constant(value: str) -> NoReturn:
    raise RecommendationSerializationError(
        f"$: invalid JSON numeric constant {value}"
    )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RecommendationSerializationError(
                f"$: duplicate JSON field {key!r}"
            )
        result[key] = value
    return result


def load_recommendation_evidence_json(text: str) -> RecommendationEvidence:
    """Load strict JSON without NaN, Infinity, duplicate, or forged fields."""
    if type(text) is not str:
        _fail("$", "JSON input must be an exact string")
    try:
        payload = json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_strict_object,
        )
    except RecommendationSerializationError:
        raise
    except json.JSONDecodeError as exc:
        raise RecommendationSerializationError(
            f"$: invalid JSON: {exc.msg}"
        ) from exc
    if type(payload) is not dict:
        _fail("$", "expected a JSON object")
    return deserialize_recommendation_evidence(payload)


__all__ = [
    "RecommendationSerializationError",
    "deserialize_recommendation_evidence",
    "export_recommendation_evidence_json",
    "load_recommendation_evidence_json",
    "serialize_recommendation_evidence",
]
