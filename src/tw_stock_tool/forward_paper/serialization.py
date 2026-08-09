"""Strict schema 1.0 serialization for forward-paper activation."""

from __future__ import annotations

import json
from typing import Any

from tw_stock_tool.forward_paper.models import ForwardPaperActivation


_ACTIVATION_FIELDS = (
    "schema_version",
    "artifact_type",
    "activation_id",
    "created_at",
    "qualification_evaluation_id",
    "qualification_artifact_type",
    "qualification_schema_version",
    "qualification_sha256",
    "strategy_id",
    "policy_id",
    "policy_version",
    "qualification_cutoff",
    "qualified_symbols",
)


class ForwardPaperSerializationError(ValueError):
    """Raised when activation JSON violates strict schema 1.0."""


def serialize_forward_paper_activation(
    activation: ForwardPaperActivation,
) -> dict[str, Any]:
    if type(activation) is not ForwardPaperActivation:
        raise ForwardPaperSerializationError("expected a ForwardPaperActivation")
    return {
        "schema_version": activation.schema_version,
        "artifact_type": activation.artifact_type,
        "activation_id": activation.activation_id,
        "created_at": activation.created_at,
        "qualification_evaluation_id": activation.qualification_evaluation_id,
        "qualification_artifact_type": activation.qualification_artifact_type,
        "qualification_schema_version": activation.qualification_schema_version,
        "qualification_sha256": activation.qualification_sha256,
        "strategy_id": activation.strategy_id,
        "policy_id": activation.policy_id,
        "policy_version": activation.policy_version,
        "qualification_cutoff": activation.qualification_cutoff,
        "qualified_symbols": list(activation.qualified_symbols),
    }


def export_forward_paper_activation_json(
    activation: ForwardPaperActivation,
) -> str:
    return json.dumps(
        serialize_forward_paper_activation(activation),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"


def deserialize_forward_paper_activation(data: dict[str, Any]) -> ForwardPaperActivation:
    if type(data) is not dict:
        raise ForwardPaperSerializationError("$: expected an exact object")
    missing = [key for key in _ACTIVATION_FIELDS if key not in data]
    unknown = [key for key in data if key not in _ACTIVATION_FIELDS]
    if missing or unknown:
        raise ForwardPaperSerializationError(f"$: missing={missing}, unknown={unknown}")
    if type(data["qualified_symbols"]) is not list:
        raise ForwardPaperSerializationError("$.qualified_symbols: expected an exact list")
    try:
        return ForwardPaperActivation(
            schema_version=data["schema_version"],
            artifact_type=data["artifact_type"],
            activation_id=data["activation_id"],
            created_at=data["created_at"],
            qualification_evaluation_id=data["qualification_evaluation_id"],
            qualification_artifact_type=data["qualification_artifact_type"],
            qualification_schema_version=data["qualification_schema_version"],
            qualification_sha256=data["qualification_sha256"],
            strategy_id=data["strategy_id"],
            policy_id=data["policy_id"],
            policy_version=data["policy_version"],
            qualification_cutoff=data["qualification_cutoff"],
            qualified_symbols=tuple(data["qualified_symbols"]),
        )
    except (TypeError, ValueError) as exc:
        raise ForwardPaperSerializationError(f"$: model validation failed: {exc}") from exc


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ForwardPaperSerializationError(f"$: duplicate JSON field {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ForwardPaperSerializationError(f"$: invalid JSON numeric constant {value}")


def load_forward_paper_activation_json(text: str) -> ForwardPaperActivation:
    if type(text) is not str:
        raise ForwardPaperSerializationError("JSON input must be an exact string")
    try:
        payload = json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except ForwardPaperSerializationError:
        raise
    except json.JSONDecodeError as exc:
        raise ForwardPaperSerializationError(f"$: invalid JSON: {exc.msg}") from exc
    return deserialize_forward_paper_activation(payload)


__all__ = [
    "ForwardPaperSerializationError",
    "deserialize_forward_paper_activation",
    "export_forward_paper_activation_json",
    "load_forward_paper_activation_json",
    "serialize_forward_paper_activation",
]
