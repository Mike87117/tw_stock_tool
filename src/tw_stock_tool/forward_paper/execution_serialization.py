"""Strict JSON boundary for forward execution evidence."""

from __future__ import annotations

import json
from typing import Any

from tw_stock_tool.forward_paper.execution_models import (
    ForwardExecutionDecisionEvidence,
    ForwardExecutionEvidence,
    ForwardExecutionEvidenceModelError,
    ForwardExecutionOutcome,
)


class ForwardExecutionEvidenceSerializationError(ValueError):
    """Raised when execution evidence JSON is not exact and canonical."""


_ROOT_FIELDS = (
    "schema_version", "artifact_type", "evidence_id", "created_at",
    "activation_id", "activation_sha256", "qualification_evaluation_id",
    "qualification_sha256", "ledger_id", "ledger_sha256",
    "portfolio_result_sha256", "strategy_id", "decisions",
)
_DECISION_FIELDS = (
    "recommendation_id", "recommendation_sha256", "observed_at", "symbol",
    "action", "expected_side", "outcome", "order_id", "order_quantity",
    "pending_reference_price", "fill_time", "fill_price", "fee", "tax",
    "slippage", "risk_rejection_reasons", "audit_record_ids",
)


def _strict_object(value: Any, fields: tuple[str, ...], path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ForwardExecutionEvidenceSerializationError(f"{path} must be an exact object")
    missing = [field for field in fields if field not in value]
    unknown = [field for field in value if field not in fields]
    if missing or unknown:
        raise ForwardExecutionEvidenceSerializationError(
            f"{path} fields mismatch: missing={missing}, unknown={unknown}"
        )
    return value


def _decision_payload(item: ForwardExecutionDecisionEvidence) -> dict[str, Any]:
    return {
        "recommendation_id": item.recommendation_id,
        "recommendation_sha256": item.recommendation_sha256,
        "observed_at": item.observed_at,
        "symbol": item.symbol,
        "action": item.action,
        "expected_side": item.expected_side,
        "outcome": item.outcome.value,
        "order_id": item.order_id,
        "order_quantity": item.order_quantity,
        "pending_reference_price": item.pending_reference_price,
        "fill_time": item.fill_time,
        "fill_price": item.fill_price,
        "fee": item.fee,
        "tax": item.tax,
        "slippage": item.slippage,
        "risk_rejection_reasons": list(item.risk_rejection_reasons),
        "audit_record_ids": list(item.audit_record_ids),
    }


def serialize_forward_execution_evidence(
    artifact: ForwardExecutionEvidence,
) -> dict[str, Any]:
    if type(artifact) is not ForwardExecutionEvidence:
        raise ForwardExecutionEvidenceSerializationError(
            "expected an exact ForwardExecutionEvidence"
        )
    return {
        "schema_version": artifact.schema_version,
        "artifact_type": artifact.artifact_type,
        "evidence_id": artifact.evidence_id,
        "created_at": artifact.created_at,
        "activation_id": artifact.activation_id,
        "activation_sha256": artifact.activation_sha256,
        "qualification_evaluation_id": artifact.qualification_evaluation_id,
        "qualification_sha256": artifact.qualification_sha256,
        "ledger_id": artifact.ledger_id,
        "ledger_sha256": artifact.ledger_sha256,
        "portfolio_result_sha256": artifact.portfolio_result_sha256,
        "strategy_id": artifact.strategy_id,
        "decisions": [_decision_payload(item) for item in artifact.decisions],
    }


def export_forward_execution_evidence_json(
    artifact: ForwardExecutionEvidence,
) -> str:
    try:
        return json.dumps(
            serialize_forward_execution_evidence(artifact),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise ForwardExecutionEvidenceSerializationError(str(exc)) from exc


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ForwardExecutionEvidenceSerializationError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ForwardExecutionEvidenceSerializationError(
        f"non-finite JSON constant is not allowed: {value}"
    )


def deserialize_forward_execution_evidence(
    data: dict[str, Any],
) -> ForwardExecutionEvidence:
    root = _strict_object(data, _ROOT_FIELDS, "$")
    if type(root["decisions"]) is not list:
        raise ForwardExecutionEvidenceSerializationError("$.decisions must be an exact list")
    decisions: list[ForwardExecutionDecisionEvidence] = []
    for index, value in enumerate(root["decisions"]):
        path = f"$.decisions[{index}]"
        item = _strict_object(value, _DECISION_FIELDS, path)
        if type(item["risk_rejection_reasons"]) is not list:
            raise ForwardExecutionEvidenceSerializationError(
                f"{path}.risk_rejection_reasons must be an exact list"
            )
        if type(item["audit_record_ids"]) is not list:
            raise ForwardExecutionEvidenceSerializationError(
                f"{path}.audit_record_ids must be an exact list"
            )
        try:
            decisions.append(
                ForwardExecutionDecisionEvidence(
                    recommendation_id=item["recommendation_id"],
                    recommendation_sha256=item["recommendation_sha256"],
                    observed_at=item["observed_at"],
                    symbol=item["symbol"],
                    action=item["action"],
                    expected_side=item["expected_side"],
                    outcome=ForwardExecutionOutcome(item["outcome"]),
                    order_id=item["order_id"],
                    order_quantity=item["order_quantity"],
                    pending_reference_price=item["pending_reference_price"],
                    fill_time=item["fill_time"],
                    fill_price=item["fill_price"],
                    fee=item["fee"],
                    tax=item["tax"],
                    slippage=item["slippage"],
                    risk_rejection_reasons=tuple(item["risk_rejection_reasons"]),
                    audit_record_ids=tuple(item["audit_record_ids"]),
                )
            )
        except (TypeError, ValueError, ForwardExecutionEvidenceModelError) as exc:
            raise ForwardExecutionEvidenceSerializationError(
                f"{path} model validation failed: {exc}"
            ) from exc
    try:
        return ForwardExecutionEvidence(
            schema_version=root["schema_version"],
            artifact_type=root["artifact_type"],
            evidence_id=root["evidence_id"],
            created_at=root["created_at"],
            activation_id=root["activation_id"],
            activation_sha256=root["activation_sha256"],
            qualification_evaluation_id=root["qualification_evaluation_id"],
            qualification_sha256=root["qualification_sha256"],
            ledger_id=root["ledger_id"],
            ledger_sha256=root["ledger_sha256"],
            portfolio_result_sha256=root["portfolio_result_sha256"],
            strategy_id=root["strategy_id"],
            decisions=tuple(decisions),
        )
    except (TypeError, ValueError, ForwardExecutionEvidenceModelError) as exc:
        raise ForwardExecutionEvidenceSerializationError(
            f"$ model validation failed: {exc}"
        ) from exc


def load_forward_execution_evidence_json(text: str) -> ForwardExecutionEvidence:
    if type(text) is not str:
        raise ForwardExecutionEvidenceSerializationError("JSON input must be an exact string")
    try:
        payload = json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except ForwardExecutionEvidenceSerializationError:
        raise
    except json.JSONDecodeError as exc:
        raise ForwardExecutionEvidenceSerializationError(f"invalid JSON: {exc.msg}") from exc
    return deserialize_forward_execution_evidence(payload)


__all__ = [
    "deserialize_forward_execution_evidence",
    "export_forward_execution_evidence_json",
    "ForwardExecutionEvidenceSerializationError",
    "load_forward_execution_evidence_json",
    "serialize_forward_execution_evidence",
]
