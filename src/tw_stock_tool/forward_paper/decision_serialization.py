"""Strict deterministic serialization for forward decision ledgers."""

from __future__ import annotations

import json
from typing import Any

from tw_stock_tool.forward_paper.decision_models import (
    ForwardDecisionLedger,
    ForwardDecisionRecord,
)
from tw_stock_tool.forward_paper.serialization import (
    ForwardPaperSerializationError,
    _reject_duplicate_json_keys,
    _reject_json_constant,
)


_LEDGER_FIELDS = (
    "schema_version",
    "artifact_type",
    "ledger_id",
    "created_at",
    "activation_id",
    "activation_sha256",
    "qualification_evaluation_id",
    "qualification_sha256",
    "strategy_id",
    "decisions",
)
_RECORD_FIELDS = (
    "recommendation_id",
    "recommendation_sha256",
    "observed_at",
    "generated_at",
    "symbol",
    "signal",
    "action",
    "qualification_evaluation_id",
    "strategy_id",
    "selected_parameters",
)


def _strict_object(
    value: Any, expected: tuple[str, ...], path: str
) -> dict[str, Any]:
    if type(value) is not dict:
        raise ForwardPaperSerializationError(f"{path}: expected an exact object")
    missing = [key for key in expected if key not in value]
    unknown = [key for key in value if key not in expected]
    if missing or unknown:
        raise ForwardPaperSerializationError(
            f"{path}: missing={missing}, unknown={unknown}"
        )
    return value


def _record_payload(record: ForwardDecisionRecord) -> dict[str, Any]:
    return {
        "recommendation_id": record.recommendation_id,
        "recommendation_sha256": record.recommendation_sha256,
        "observed_at": record.observed_at,
        "generated_at": record.generated_at,
        "symbol": record.symbol,
        "signal": record.signal,
        "action": record.action,
        "qualification_evaluation_id": record.qualification_evaluation_id,
        "strategy_id": record.strategy_id,
        "selected_parameters": dict(record.selected_parameters),
    }


def serialize_forward_decision_ledger(
    ledger: ForwardDecisionLedger,
) -> dict[str, Any]:
    if type(ledger) is not ForwardDecisionLedger:
        raise ForwardPaperSerializationError("expected a ForwardDecisionLedger")
    return {
        "schema_version": ledger.schema_version,
        "artifact_type": ledger.artifact_type,
        "ledger_id": ledger.ledger_id,
        "created_at": ledger.created_at,
        "activation_id": ledger.activation_id,
        "activation_sha256": ledger.activation_sha256,
        "qualification_evaluation_id": ledger.qualification_evaluation_id,
        "qualification_sha256": ledger.qualification_sha256,
        "strategy_id": ledger.strategy_id,
        "decisions": [_record_payload(item) for item in ledger.decisions],
    }


def export_forward_decision_ledger_json(ledger: ForwardDecisionLedger) -> str:
    return json.dumps(
        serialize_forward_decision_ledger(ledger),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"


def deserialize_forward_decision_ledger(data: dict[str, Any]) -> ForwardDecisionLedger:
    root = _strict_object(data, _LEDGER_FIELDS, "$")
    if type(root["decisions"]) is not list:
        raise ForwardPaperSerializationError("$.decisions: expected an exact list")
    decisions: list[ForwardDecisionRecord] = []
    for index, value in enumerate(root["decisions"]):
        path = f"$.decisions[{index}]"
        record = _strict_object(value, _RECORD_FIELDS, path)
        if type(record["selected_parameters"]) is not dict:
            raise ForwardPaperSerializationError(
                f"{path}.selected_parameters: expected an exact object"
            )
        try:
            decisions.append(
                ForwardDecisionRecord(
                    recommendation_id=record["recommendation_id"],
                    recommendation_sha256=record["recommendation_sha256"],
                    observed_at=record["observed_at"],
                    generated_at=record["generated_at"],
                    symbol=record["symbol"],
                    signal=record["signal"],
                    action=record["action"],
                    qualification_evaluation_id=record[
                        "qualification_evaluation_id"
                    ],
                    strategy_id=record["strategy_id"],
                    selected_parameters=record["selected_parameters"],
                )
            )
        except (TypeError, ValueError) as exc:
            raise ForwardPaperSerializationError(
                f"{path}: model validation failed: {exc}"
            ) from exc
    try:
        return ForwardDecisionLedger(
            schema_version=root["schema_version"],
            artifact_type=root["artifact_type"],
            ledger_id=root["ledger_id"],
            created_at=root["created_at"],
            activation_id=root["activation_id"],
            activation_sha256=root["activation_sha256"],
            qualification_evaluation_id=root["qualification_evaluation_id"],
            qualification_sha256=root["qualification_sha256"],
            strategy_id=root["strategy_id"],
            decisions=tuple(decisions),
        )
    except (TypeError, ValueError) as exc:
        raise ForwardPaperSerializationError(
            f"$: model validation failed: {exc}"
        ) from exc


def load_forward_decision_ledger_json(text: str) -> ForwardDecisionLedger:
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
    return deserialize_forward_decision_ledger(payload)


__all__ = [
    "deserialize_forward_decision_ledger",
    "export_forward_decision_ledger_json",
    "load_forward_decision_ledger_json",
    "serialize_forward_decision_ledger",
]
