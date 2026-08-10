"""Strict deterministic JSON for Phase 56.5A1 source contracts."""

from __future__ import annotations

import json
from typing import Any, NoReturn

from tw_stock_tool.broker_safety.source_models import (
    BrokerSafetySourceHandoff,
    BrokerSafetySourceModelError,
    ForwardEligibilityDecisionAnchor,
    ForwardEligibilityHighWaterMark,
    ForwardEligibilityLineageKey,
    ForwardEligibilityProgression,
)
from tw_stock_tool.forward_paper.eligibility_models import ForwardEligibilityState


class BrokerSafetySourceSerializationError(ValueError):
    """Raised when broker-safety source JSON is not strict and canonical."""


_LINEAGE_FIELDS = (
    "activation_id",
    "strategy_id",
    "policy_id",
    "policy_version",
)
_ANCHOR_FIELDS = (
    "recommendation_id",
    "recommendation_sha256",
    "observed_at",
    "symbol",
    "decision_sha256",
)
_PROGRESSION_FIELDS = (
    "schema_version",
    "artifact_type",
    "lineage_key",
    "run_id",
    "publication_id",
    "publication_index_sha256",
    "qualification_evaluation_id",
    "eligibility_id",
    "eligibility_state",
    "eligibility_sha256",
    "metrics_id",
    "metrics_sha256",
    "ledger_id",
    "ledger_sha256",
    "decision_count",
    "last_observed_at",
    "recommendation_anchors",
    "progression_fingerprint",
)
_HANDOFF_FIELDS = (
    "schema_version",
    "artifact_type",
    "workspace_run_id",
    "publication_id",
    "publication_index_sha256",
    "activation_id",
    "qualification_evaluation_id",
    "strategy_id",
    "eligibility_id",
    "eligibility_state",
    "policy_id",
    "policy_version",
    "qualified_symbols",
    "qualified_symbols_sha256",
    "ledger_id",
    "ledger_sha256",
    "recommendation_id",
    "recommendation_sha256",
    "decision_symbol",
    "decision_observed_at",
    "decision_signal",
    "decision_action",
    "selected_parameters_sha256",
    "lineage_key",
    "progression_fingerprint",
)
_HIGH_WATER_FIELDS = (
    "schema_version",
    "artifact_type",
    "lineage_key",
    "accepted_progression_fingerprint",
    "accepted_run_id",
    "accepted_publication_id",
    "accepted_publication_index_sha256",
    "accepted_qualification_evaluation_id",
    "accepted_eligibility_id",
    "accepted_state",
    "accepted_eligibility_sha256",
    "accepted_metrics_id",
    "accepted_metrics_sha256",
    "accepted_ledger_id",
    "accepted_ledger_sha256",
    "accepted_decision_count",
    "accepted_last_observed_at",
    "accepted_recommendation_anchors",
)


def _strict_object(value: Any, fields: tuple[str, ...], path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise BrokerSafetySourceSerializationError(
            f"{path}: expected an exact object"
        )
    missing = [name for name in fields if name not in value]
    unknown = [name for name in value if name not in fields]
    if missing or unknown:
        raise BrokerSafetySourceSerializationError(
            f"{path}: missing={missing}, unknown={unknown}"
        )
    return value


def _lineage(value: ForwardEligibilityLineageKey) -> dict[str, Any]:
    if type(value) is not ForwardEligibilityLineageKey:
        raise BrokerSafetySourceSerializationError(
            "expected an exact ForwardEligibilityLineageKey"
        )
    return {name: getattr(value, name) for name in _LINEAGE_FIELDS}


def _anchor(value: ForwardEligibilityDecisionAnchor) -> dict[str, Any]:
    if type(value) is not ForwardEligibilityDecisionAnchor:
        raise BrokerSafetySourceSerializationError(
            "expected an exact ForwardEligibilityDecisionAnchor"
        )
    return {name: getattr(value, name) for name in _ANCHOR_FIELDS}


def serialize_forward_eligibility_progression(
    value: ForwardEligibilityProgression,
) -> dict[str, Any]:
    if type(value) is not ForwardEligibilityProgression:
        raise BrokerSafetySourceSerializationError(
            "expected an exact ForwardEligibilityProgression"
        )
    result = {name: getattr(value, name) for name in _PROGRESSION_FIELDS}
    result["lineage_key"] = _lineage(value.lineage_key)
    result["eligibility_state"] = value.eligibility_state.value
    result["recommendation_anchors"] = [
        _anchor(item) for item in value.recommendation_anchors
    ]
    return result


def serialize_broker_safety_source_handoff(
    value: BrokerSafetySourceHandoff,
) -> dict[str, Any]:
    if type(value) is not BrokerSafetySourceHandoff:
        raise BrokerSafetySourceSerializationError(
            "expected an exact BrokerSafetySourceHandoff"
        )
    result = {name: getattr(value, name) for name in _HANDOFF_FIELDS}
    result["eligibility_state"] = value.eligibility_state.value
    result["qualified_symbols"] = list(value.qualified_symbols)
    result["lineage_key"] = _lineage(value.lineage_key)
    return result


def serialize_forward_eligibility_high_water_mark(
    value: ForwardEligibilityHighWaterMark,
) -> dict[str, Any]:
    if type(value) is not ForwardEligibilityHighWaterMark:
        raise BrokerSafetySourceSerializationError(
            "expected an exact ForwardEligibilityHighWaterMark"
        )
    result = {name: getattr(value, name) for name in _HIGH_WATER_FIELDS}
    result["lineage_key"] = _lineage(value.lineage_key)
    result["accepted_state"] = value.accepted_state.value
    result["accepted_recommendation_anchors"] = [
        _anchor(item) for item in value.accepted_recommendation_anchors
    ]
    return result


def _construct(path: str, constructor, **kwargs):
    try:
        return constructor(**kwargs)
    except (BrokerSafetySourceModelError, TypeError, ValueError) as exc:
        raise BrokerSafetySourceSerializationError(
            f"{path}: model validation failed: {exc}"
        ) from exc


def _deserialize_lineage(value: Any, path: str) -> ForwardEligibilityLineageKey:
    payload = _strict_object(value, _LINEAGE_FIELDS, path)
    return _construct(path, ForwardEligibilityLineageKey, **payload)


def _deserialize_anchors(value: Any, path: str) -> tuple[ForwardEligibilityDecisionAnchor, ...]:
    if type(value) is not list:
        raise BrokerSafetySourceSerializationError(f"{path}: expected an exact array")
    return tuple(
        _construct(
            f"{path}[{index}]",
            ForwardEligibilityDecisionAnchor,
            **_strict_object(item, _ANCHOR_FIELDS, f"{path}[{index}]"),
        )
        for index, item in enumerate(value)
    )


def _state(value: Any, path: str) -> ForwardEligibilityState:
    if type(value) is not str:
        raise BrokerSafetySourceSerializationError(f"{path}: expected an exact string")
    try:
        return ForwardEligibilityState(value)
    except ValueError as exc:
        raise BrokerSafetySourceSerializationError(
            f"{path}: unsupported eligibility state {value!r}"
        ) from exc


def deserialize_forward_eligibility_progression(
    data: dict[str, Any],
) -> ForwardEligibilityProgression:
    root = _strict_object(data, _PROGRESSION_FIELDS, "$")
    values = dict(root)
    values["lineage_key"] = _deserialize_lineage(root["lineage_key"], "$.lineage_key")
    values["eligibility_state"] = _state(root["eligibility_state"], "$.eligibility_state")
    values["recommendation_anchors"] = _deserialize_anchors(
        root["recommendation_anchors"], "$.recommendation_anchors"
    )
    return _construct("$", ForwardEligibilityProgression, **values)


def deserialize_broker_safety_source_handoff(
    data: dict[str, Any],
) -> BrokerSafetySourceHandoff:
    root = _strict_object(data, _HANDOFF_FIELDS, "$")
    values = dict(root)
    symbols = root["qualified_symbols"]
    if type(symbols) is not list:
        raise BrokerSafetySourceSerializationError(
            "$.qualified_symbols: expected an exact array"
        )
    values["qualified_symbols"] = tuple(symbols)
    values["eligibility_state"] = _state(root["eligibility_state"], "$.eligibility_state")
    values["lineage_key"] = _deserialize_lineage(root["lineage_key"], "$.lineage_key")
    return _construct("$", BrokerSafetySourceHandoff, **values)


def deserialize_forward_eligibility_high_water_mark(
    data: dict[str, Any],
) -> ForwardEligibilityHighWaterMark:
    root = _strict_object(data, _HIGH_WATER_FIELDS, "$")
    values = dict(root)
    values["lineage_key"] = _deserialize_lineage(root["lineage_key"], "$.lineage_key")
    values["accepted_state"] = _state(root["accepted_state"], "$.accepted_state")
    values["accepted_recommendation_anchors"] = _deserialize_anchors(
        root["accepted_recommendation_anchors"],
        "$.accepted_recommendation_anchors",
    )
    return _construct("$", ForwardEligibilityHighWaterMark, **values)


def _export(value: dict[str, Any]) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise BrokerSafetySourceSerializationError(str(exc)) from exc


def export_forward_eligibility_progression_json(
    value: ForwardEligibilityProgression,
) -> str:
    return _export(serialize_forward_eligibility_progression(value))


def export_broker_safety_source_handoff_json(
    value: BrokerSafetySourceHandoff,
) -> str:
    return _export(serialize_broker_safety_source_handoff(value))


def export_forward_eligibility_high_water_mark_json(
    value: ForwardEligibilityHighWaterMark,
) -> str:
    return _export(serialize_forward_eligibility_high_water_mark(value))


def _constant(value: str) -> NoReturn:
    raise BrokerSafetySourceSerializationError(
        f"$: non-finite JSON constant is not allowed: {value}"
    )


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BrokerSafetySourceSerializationError(
                f"$: duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _load(text: str) -> dict[str, Any]:
    if type(text) is not str:
        raise BrokerSafetySourceSerializationError(
            "JSON input must be an exact string"
        )
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_pairs,
            parse_constant=_constant,
        )
    except BrokerSafetySourceSerializationError:
        raise
    except json.JSONDecodeError as exc:
        raise BrokerSafetySourceSerializationError(
            f"$: invalid JSON: {exc.msg}"
        ) from exc
    if type(value) is not dict:
        raise BrokerSafetySourceSerializationError("$: expected an exact object")
    return value


def load_forward_eligibility_progression_json(
    text: str,
) -> ForwardEligibilityProgression:
    return deserialize_forward_eligibility_progression(_load(text))


def load_broker_safety_source_handoff_json(
    text: str,
) -> BrokerSafetySourceHandoff:
    return deserialize_broker_safety_source_handoff(_load(text))


def load_forward_eligibility_high_water_mark_json(
    text: str,
) -> ForwardEligibilityHighWaterMark:
    return deserialize_forward_eligibility_high_water_mark(_load(text))


__all__ = [
    "BrokerSafetySourceSerializationError",
    "deserialize_broker_safety_source_handoff",
    "deserialize_forward_eligibility_high_water_mark",
    "deserialize_forward_eligibility_progression",
    "export_broker_safety_source_handoff_json",
    "export_forward_eligibility_high_water_mark_json",
    "export_forward_eligibility_progression_json",
    "load_broker_safety_source_handoff_json",
    "load_forward_eligibility_high_water_mark_json",
    "load_forward_eligibility_progression_json",
    "serialize_broker_safety_source_handoff",
    "serialize_forward_eligibility_high_water_mark",
    "serialize_forward_eligibility_progression",
]
