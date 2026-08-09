"""Strict no-I/O JSON boundary for forward eligibility evidence."""

from __future__ import annotations

import json
from typing import Any

from tw_stock_tool.forward_paper.eligibility_models import (
    ForwardEligibilityEvidence,
    ForwardEligibilityFinding,
    ForwardEligibilityModelError,
    ForwardEligibilitySeverity,
    ForwardEligibilityState,
)


class ForwardEligibilitySerializationError(ValueError):
    """Raised when forward eligibility JSON is not exact and canonical."""


_ROOT_FIELDS = (
    "schema_version",
    "artifact_type",
    "eligibility_id",
    "created_at",
    "activation_id",
    "activation_sha256",
    "qualification_evaluation_id",
    "qualification_sha256",
    "ledger_id",
    "ledger_sha256",
    "metrics_id",
    "metrics_sha256",
    "strategy_id",
    "policy_id",
    "policy_version",
    "state",
    "findings",
)
_FINDING_FIELDS = (
    "code",
    "severity",
    "metric_name",
    "observed_value",
    "threshold_value",
    "message",
)


def _strict_object(value: Any, fields: tuple[str, ...], path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ForwardEligibilitySerializationError(
            f"{path} must be an exact object"
        )
    missing = [field for field in fields if field not in value]
    unknown = [field for field in value if field not in fields]
    if missing or unknown:
        raise ForwardEligibilitySerializationError(
            f"{path} fields mismatch: missing={missing}, unknown={unknown}"
        )
    return value


def serialize_forward_eligibility_evidence(
    artifact: ForwardEligibilityEvidence,
) -> dict[str, Any]:
    if type(artifact) is not ForwardEligibilityEvidence:
        raise ForwardEligibilitySerializationError(
            "expected an exact ForwardEligibilityEvidence"
        )
    return {
        "schema_version": artifact.schema_version,
        "artifact_type": artifact.artifact_type,
        "eligibility_id": artifact.eligibility_id,
        "created_at": artifact.created_at,
        "activation_id": artifact.activation_id,
        "activation_sha256": artifact.activation_sha256,
        "qualification_evaluation_id": artifact.qualification_evaluation_id,
        "qualification_sha256": artifact.qualification_sha256,
        "ledger_id": artifact.ledger_id,
        "ledger_sha256": artifact.ledger_sha256,
        "metrics_id": artifact.metrics_id,
        "metrics_sha256": artifact.metrics_sha256,
        "strategy_id": artifact.strategy_id,
        "policy_id": artifact.policy_id,
        "policy_version": artifact.policy_version,
        "state": artifact.state.value,
        "findings": [
            {
                "code": item.code,
                "severity": item.severity.value,
                "metric_name": item.metric_name,
                "observed_value": item.observed_value,
                "threshold_value": item.threshold_value,
                "message": item.message,
            }
            for item in artifact.findings
        ],
    }


def export_forward_eligibility_evidence_json(
    artifact: ForwardEligibilityEvidence,
) -> str:
    try:
        return json.dumps(
            serialize_forward_eligibility_evidence(artifact),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise ForwardEligibilitySerializationError(str(exc)) from exc


def deserialize_forward_eligibility_evidence(
    data: dict[str, Any],
) -> ForwardEligibilityEvidence:
    root = _strict_object(data, _ROOT_FIELDS, "$")
    raw_findings = root["findings"]
    if type(raw_findings) is not list:
        raise ForwardEligibilitySerializationError("$.findings must be an exact array")
    findings: list[ForwardEligibilityFinding] = []
    try:
        for index, value in enumerate(raw_findings):
            item = _strict_object(value, _FINDING_FIELDS, f"$.findings[{index}]")
            findings.append(
                ForwardEligibilityFinding(
                    code=item["code"],
                    severity=ForwardEligibilitySeverity(item["severity"]),
                    metric_name=item["metric_name"],
                    observed_value=item["observed_value"],
                    threshold_value=item["threshold_value"],
                    message=item["message"],
                )
            )
        return ForwardEligibilityEvidence(
            schema_version=root["schema_version"],
            artifact_type=root["artifact_type"],
            eligibility_id=root["eligibility_id"],
            created_at=root["created_at"],
            activation_id=root["activation_id"],
            activation_sha256=root["activation_sha256"],
            qualification_evaluation_id=root["qualification_evaluation_id"],
            qualification_sha256=root["qualification_sha256"],
            ledger_id=root["ledger_id"],
            ledger_sha256=root["ledger_sha256"],
            metrics_id=root["metrics_id"],
            metrics_sha256=root["metrics_sha256"],
            strategy_id=root["strategy_id"],
            policy_id=root["policy_id"],
            policy_version=root["policy_version"],
            state=ForwardEligibilityState(root["state"]),
            findings=tuple(findings),
        )
    except (TypeError, ValueError, ForwardEligibilityModelError) as exc:
        raise ForwardEligibilitySerializationError(
            f"$ model validation failed: {exc}"
        ) from exc


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ForwardEligibilitySerializationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ForwardEligibilitySerializationError(
        f"non-finite JSON constant is not allowed: {value}"
    )


def load_forward_eligibility_evidence_json(
    text: str,
) -> ForwardEligibilityEvidence:
    if type(text) is not str:
        raise ForwardEligibilitySerializationError(
            "JSON input must be an exact string"
        )
    try:
        payload = json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except ForwardEligibilitySerializationError:
        raise
    except json.JSONDecodeError as exc:
        raise ForwardEligibilitySerializationError(
            f"invalid JSON: {exc.msg}"
        ) from exc
    return deserialize_forward_eligibility_evidence(payload)


__all__ = [
    "ForwardEligibilitySerializationError",
    "deserialize_forward_eligibility_evidence",
    "export_forward_eligibility_evidence_json",
    "load_forward_eligibility_evidence_json",
    "serialize_forward_eligibility_evidence",
]
