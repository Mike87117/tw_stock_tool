"""Strict no-I/O JSON boundary for forward metrics evidence."""

from __future__ import annotations

import json
from typing import Any

from tw_stock_tool.forward_paper.metrics_models import (
    ForwardAppliedCostMetrics,
    ForwardExecutionHealthMetrics,
    ForwardMetricsEvidence,
    ForwardMetricsEvidenceModelError,
    ForwardPortfolioMetrics,
    ForwardQualificationReference,
)


class ForwardMetricsEvidenceSerializationError(ValueError):
    """Raised when forward metrics evidence JSON is not exact and canonical."""


_ROOT_FIELDS = (
    "schema_version", "artifact_type", "metrics_id", "created_at",
    "activation_id", "activation_sha256", "qualification_evaluation_id",
    "qualification_sha256", "ledger_id", "ledger_sha256",
    "execution_evidence_id", "execution_evidence_sha256",
    "portfolio_result_sha256", "portfolio_trace_sha256", "strategy_id",
    "execution_health", "applied_costs", "portfolio_metrics",
    "qualification_reference",
)
_HEALTH_FIELDS = (
    "total_decisions", "actionable_decisions", "enter_decisions",
    "exit_decisions", "non_action_decisions", "no_candidate_count",
    "candidate_count", "rejected_count", "accepted_count", "pending_count",
    "filled_count", "skipped_invalid_open_count",
    "failed_portfolio_validation_count", "terminal_attempt_count",
    "candidate_rate", "rejection_rate", "terminal_fill_success_rate",
    "invalid_open_rate", "portfolio_validation_failure_rate", "pending_rate",
)
_COST_FIELDS = (
    "filled_quantity", "filled_gross_notional", "applied_fee", "applied_tax",
    "applied_slippage", "applied_total_cost", "applied_cost_bps",
    "effective_slippage_per_share",
)
_PORTFOLIO_FIELDS = (
    "observation_count", "observation_start", "observation_end",
    "initial_equity", "final_equity", "total_return_pct", "max_drawdown_pct",
    "max_open_position_count", "max_pending_order_count",
    "max_reserved_buy_notional", "max_market_exposure_pct",
    "max_single_symbol_market_value_share_pct",
)
_REFERENCE_FIELDS = (
    "qualification_total_return_pct", "qualification_max_drawdown_pct",
    "qualification_completed_trades", "qualification_valid_windows",
    "qualification_benchmark_return_pct", "qualification_return_basis",
    "qualification_drawdown_basis", "forward_return_basis",
    "forward_drawdown_basis",
)


def _strict_object(value: Any, fields: tuple[str, ...], path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ForwardMetricsEvidenceSerializationError(
            f"{path} must be an exact object"
        )
    missing = [field for field in fields if field not in value]
    unknown = [field for field in value if field not in fields]
    if missing or unknown:
        raise ForwardMetricsEvidenceSerializationError(
            f"{path} fields mismatch: missing={missing}, unknown={unknown}"
        )
    return value


def serialize_forward_metrics_evidence(
    artifact: ForwardMetricsEvidence,
) -> dict[str, Any]:
    if type(artifact) is not ForwardMetricsEvidence:
        raise ForwardMetricsEvidenceSerializationError(
            "expected an exact ForwardMetricsEvidence"
        )
    health = artifact.execution_health
    costs = artifact.applied_costs
    portfolio = artifact.portfolio_metrics
    reference = artifact.qualification_reference
    return {
        "schema_version": artifact.schema_version,
        "artifact_type": artifact.artifact_type,
        "metrics_id": artifact.metrics_id,
        "created_at": artifact.created_at,
        "activation_id": artifact.activation_id,
        "activation_sha256": artifact.activation_sha256,
        "qualification_evaluation_id": artifact.qualification_evaluation_id,
        "qualification_sha256": artifact.qualification_sha256,
        "ledger_id": artifact.ledger_id,
        "ledger_sha256": artifact.ledger_sha256,
        "execution_evidence_id": artifact.execution_evidence_id,
        "execution_evidence_sha256": artifact.execution_evidence_sha256,
        "portfolio_result_sha256": artifact.portfolio_result_sha256,
        "portfolio_trace_sha256": artifact.portfolio_trace_sha256,
        "strategy_id": artifact.strategy_id,
        "execution_health": {
            field: getattr(health, field) for field in _HEALTH_FIELDS
        },
        "applied_costs": {
            field: getattr(costs, field) for field in _COST_FIELDS
        },
        "portfolio_metrics": {
            field: getattr(portfolio, field) for field in _PORTFOLIO_FIELDS
        },
        "qualification_reference": {
            field: getattr(reference, field) for field in _REFERENCE_FIELDS
        },
    }


def export_forward_metrics_evidence_json(artifact: ForwardMetricsEvidence) -> str:
    try:
        return json.dumps(
            serialize_forward_metrics_evidence(artifact),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise ForwardMetricsEvidenceSerializationError(str(exc)) from exc


def deserialize_forward_metrics_evidence(data: dict[str, Any]) -> ForwardMetricsEvidence:
    root = _strict_object(data, _ROOT_FIELDS, "$")
    health = _strict_object(root["execution_health"], _HEALTH_FIELDS, "$.execution_health")
    costs = _strict_object(root["applied_costs"], _COST_FIELDS, "$.applied_costs")
    portfolio = _strict_object(root["portfolio_metrics"], _PORTFOLIO_FIELDS, "$.portfolio_metrics")
    reference = _strict_object(root["qualification_reference"], _REFERENCE_FIELDS, "$.qualification_reference")
    try:
        return ForwardMetricsEvidence(
            schema_version=root["schema_version"],
            artifact_type=root["artifact_type"],
            metrics_id=root["metrics_id"],
            created_at=root["created_at"],
            activation_id=root["activation_id"],
            activation_sha256=root["activation_sha256"],
            qualification_evaluation_id=root["qualification_evaluation_id"],
            qualification_sha256=root["qualification_sha256"],
            ledger_id=root["ledger_id"],
            ledger_sha256=root["ledger_sha256"],
            execution_evidence_id=root["execution_evidence_id"],
            execution_evidence_sha256=root["execution_evidence_sha256"],
            portfolio_result_sha256=root["portfolio_result_sha256"],
            portfolio_trace_sha256=root["portfolio_trace_sha256"],
            strategy_id=root["strategy_id"],
            execution_health=ForwardExecutionHealthMetrics(**health),
            applied_costs=ForwardAppliedCostMetrics(**costs),
            portfolio_metrics=ForwardPortfolioMetrics(**portfolio),
            qualification_reference=ForwardQualificationReference(**reference),
        )
    except (TypeError, ValueError, ForwardMetricsEvidenceModelError) as exc:
        raise ForwardMetricsEvidenceSerializationError(
            f"$ model validation failed: {exc}"
        ) from exc


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ForwardMetricsEvidenceSerializationError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ForwardMetricsEvidenceSerializationError(
        f"non-finite JSON constant is not allowed: {value}"
    )


def load_forward_metrics_evidence_json(text: str) -> ForwardMetricsEvidence:
    if type(text) is not str:
        raise ForwardMetricsEvidenceSerializationError(
            "JSON input must be an exact string"
        )
    try:
        payload = json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except ForwardMetricsEvidenceSerializationError:
        raise
    except json.JSONDecodeError as exc:
        raise ForwardMetricsEvidenceSerializationError(
            f"invalid JSON: {exc.msg}"
        ) from exc
    return deserialize_forward_metrics_evidence(payload)


__all__ = [
    "deserialize_forward_metrics_evidence",
    "export_forward_metrics_evidence_json",
    "ForwardMetricsEvidenceSerializationError",
    "load_forward_metrics_evidence_json",
    "serialize_forward_metrics_evidence",
]
