"""Strict JSON serialization for StrategyQualificationResult artifacts."""

from __future__ import annotations

from collections.abc import Mapping
import json
import math
from typing import Any, NoReturn

from tw_stock_tool.qualification.findings import (
    SUPPORTED_FINDING_CODES,
    normalize_findings,
)
from tw_stock_tool.qualification.models import (
    STRATEGY_QUALIFICATION_ARTIFACT_TYPE,
    STRATEGY_QUALIFICATION_SCHEMA_VERSION,
    PromotionDecision,
    QualificationFinding,
    QualificationMetricSet,
    QualificationModelError,
    QualificationPolicy,
    StrategyDescriptor,
    StrategyQualificationRequest,
    StrategyQualificationResult,
)


class QualificationSerializationError(ValueError):
    """Raised when a qualification artifact cannot be serialized or loaded."""


_RESULT_KEYS = ("schema_version", "artifact_type", "request", "findings", "decision")
_REQUEST_KEYS = ("evaluation_id", "created_at", "strategy", "metrics", "policy")
_STRATEGY_KEYS = ("strategy_id", "parameters")
_POLICY_KEYS = (
    "policy_id",
    "policy_version",
    "minimum_oos_observations",
    "minimum_completed_trades",
    "minimum_evaluated_symbols",
    "minimum_valid_windows",
    "require_benchmark",
    "minimum_excess_return_pct",
    "require_cost_stress",
    "maximum_drawdown_pct",
    "minimum_positive_window_ratio",
    "maximum_symbol_concentration_pct",
    "require_parameter_stability",
    "finding_severities",
)
_METRIC_KEYS = (
    "evidence_scope",
    "data_leakage_free",
    "oos_observations",
    "completed_trades",
    "evaluated_symbols",
    "valid_windows",
    "benchmark_available",
    "total_return_pct",
    "benchmark_return_pct",
    "cost_stress_pass",
    "stressed_return_pct",
    "max_drawdown_pct",
    "positive_window_ratio",
    "symbol_concentration_pct",
    "parameter_stable",
    "partial_failure_count",
)
_FINDING_KEYS = (
    "code",
    "severity",
    "scope",
    "message",
    "metric_name",
    "observed_value",
    "threshold_value",
    "symbol",
    "window",
)
_DECISION_KEYS = ("state", "reason_codes")


def _fail(path: str, message: str) -> NoReturn:
    raise QualificationSerializationError(f"{path}: {message}")


def _json_value(value: Any, path: str) -> Any:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            _fail(path, "non-finite float values are not supported")
        return value
    if isinstance(value, (list, tuple)):
        return [_json_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key in sorted(value):
            item = value[key]
            if type(key) is not str or not key or key.strip() != key:
                _fail(path, "mapping keys must be clean exact strings")
            output[key] = _json_value(item, f"{path}.{key}")
        return output
    _fail(path, f"unsupported value type: {type(value).__name__}")


def serialize_strategy_qualification_result(
    result: StrategyQualificationResult,
) -> dict[str, Any]:
    """Serialize one validated result into a deterministic dictionary."""
    if not isinstance(result, StrategyQualificationResult):
        _fail("$", "expected a StrategyQualificationResult instance")
    request = result.request
    strategy = request.strategy
    metrics = request.metrics
    policy = request.policy
    return {
        "schema_version": result.schema_version,
        "artifact_type": result.artifact_type,
        "request": {
            "evaluation_id": request.evaluation_id,
            "created_at": request.created_at,
            "strategy": {
                "strategy_id": strategy.strategy_id,
                "parameters": _json_value(strategy.parameters, "$.request.strategy.parameters"),
            },
            "metrics": {
                "evidence_scope": metrics.evidence_scope,
                "data_leakage_free": metrics.data_leakage_free,
                "oos_observations": metrics.oos_observations,
                "completed_trades": metrics.completed_trades,
                "evaluated_symbols": metrics.evaluated_symbols,
                "valid_windows": metrics.valid_windows,
                "benchmark_available": metrics.benchmark_available,
                "total_return_pct": metrics.total_return_pct,
                "benchmark_return_pct": metrics.benchmark_return_pct,
                "cost_stress_pass": metrics.cost_stress_pass,
                "stressed_return_pct": metrics.stressed_return_pct,
                "max_drawdown_pct": metrics.max_drawdown_pct,
                "positive_window_ratio": metrics.positive_window_ratio,
                "symbol_concentration_pct": metrics.symbol_concentration_pct,
                "parameter_stable": metrics.parameter_stable,
                "partial_failure_count": metrics.partial_failure_count,
            },
            "policy": {
                "policy_id": policy.policy_id,
                "policy_version": policy.policy_version,
                "minimum_oos_observations": policy.minimum_oos_observations,
                "minimum_completed_trades": policy.minimum_completed_trades,
                "minimum_evaluated_symbols": policy.minimum_evaluated_symbols,
                "minimum_valid_windows": policy.minimum_valid_windows,
                "require_benchmark": policy.require_benchmark,
                "minimum_excess_return_pct": policy.minimum_excess_return_pct,
                "require_cost_stress": policy.require_cost_stress,
                "maximum_drawdown_pct": policy.maximum_drawdown_pct,
                "minimum_positive_window_ratio": policy.minimum_positive_window_ratio,
                "maximum_symbol_concentration_pct": policy.maximum_symbol_concentration_pct,
                "require_parameter_stability": policy.require_parameter_stability,
                "finding_severities": _json_value(
                    policy.finding_severities,
                    "$.request.policy.finding_severities",
                ),
            },
        },
        "findings": [
            {
                "code": finding.code,
                "severity": finding.severity,
                "scope": finding.scope,
                "message": finding.message,
                "metric_name": finding.metric_name,
                "observed_value": finding.observed_value,
                "threshold_value": finding.threshold_value,
                "symbol": finding.symbol,
                "window": finding.window,
            }
            for finding in result.findings
        ],
        "decision": {
            "state": result.decision.state,
            "reason_codes": list(result.decision.reason_codes),
        },
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
        return [_native_json(item, f"{path}[{index}]") for index, item in enumerate(value)]
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
    except QualificationModelError as exc:
        raise QualificationSerializationError(
            f"{path}: model validation failed: {exc}"
        ) from exc


def deserialize_strategy_qualification_result(
    data: dict[str, Any],
) -> StrategyQualificationResult:
    """Deserialize a strict dictionary payload into a validated result."""
    root = _dict(data, "$", _RESULT_KEYS)
    if root["schema_version"] != STRATEGY_QUALIFICATION_SCHEMA_VERSION:
        _fail("$.schema_version", f"unsupported schema version {root['schema_version']!r}")
    if root["artifact_type"] != STRATEGY_QUALIFICATION_ARTIFACT_TYPE:
        _fail("$.artifact_type", f"unsupported artifact type {root['artifact_type']!r}")

    request_raw = _dict(root["request"], "$.request", _REQUEST_KEYS)
    strategy_raw = _dict(request_raw["strategy"], "$.request.strategy", _STRATEGY_KEYS)
    parameters_raw = _dict(
        strategy_raw["parameters"],
        "$.request.strategy.parameters",
        tuple(strategy_raw["parameters"].keys()) if type(strategy_raw["parameters"]) is dict else (),
    )
    parameters = _native_json(parameters_raw, "$.request.strategy.parameters")
    strategy = _construct(
        "$.request.strategy",
        StrategyDescriptor,
        strategy_id=strategy_raw["strategy_id"],
        parameters=parameters,
    )

    metrics_raw = _dict(request_raw["metrics"], "$.request.metrics", _METRIC_KEYS)
    metrics = _construct(
        "$.request.metrics",
        QualificationMetricSet,
        **metrics_raw,
    )
    policy_raw = _dict(request_raw["policy"], "$.request.policy", _POLICY_KEYS)
    policy_severities_raw = _dict(
        policy_raw["finding_severities"],
        "$.request.policy.finding_severities",
        tuple(policy_raw["finding_severities"].keys())
        if type(policy_raw["finding_severities"]) is dict
        else (),
    )
    policy_kwargs = dict(policy_raw)
    policy_kwargs["finding_severities"] = _native_json(
        policy_severities_raw,
        "$.request.policy.finding_severities",
    )
    policy = _construct(
        "$.request.policy",
        QualificationPolicy,
        **policy_kwargs,
    )
    request = _construct(
        "$.request",
        StrategyQualificationRequest,
        evaluation_id=request_raw["evaluation_id"],
        created_at=request_raw["created_at"],
        strategy=strategy,
        metrics=metrics,
        policy=policy,
    )

    findings_raw = _list(root["findings"], "$.findings")
    findings: list[QualificationFinding] = []
    for index, item in enumerate(findings_raw):
        path = f"$.findings[{index}]"
        finding_raw = _dict(item, path, _FINDING_KEYS)
        finding = _construct(path, QualificationFinding, **finding_raw)
        if finding.code not in SUPPORTED_FINDING_CODES:
            _fail(f"{path}.code", f"unsupported finding code {finding.code!r}")
        findings.append(finding)

    try:
        normalized_findings = normalize_findings(findings, request.policy)
    except QualificationModelError as exc:
        _fail("$.findings", str(exc))
    if tuple(findings) != normalized_findings:
        _fail("$.findings", "findings must be deduplicated and in canonical order")

    decision_raw = _dict(root["decision"], "$.decision", _DECISION_KEYS)
    reason_codes_raw = _list(decision_raw["reason_codes"], "$.decision.reason_codes")
    decision = _construct(
        "$.decision",
        PromotionDecision,
        state=decision_raw["state"],
        reason_codes=tuple(reason_codes_raw),
    )
    return _construct(
        "$",
        StrategyQualificationResult,
        schema_version=root["schema_version"],
        artifact_type=root["artifact_type"],
        request=request,
        findings=normalized_findings,
        decision=decision,
    )


def export_strategy_qualification_json(
    result: StrategyQualificationResult,
) -> str:
    """Export deterministic UTF-8 JSON text with a trailing newline."""
    return (
        json.dumps(
            serialize_strategy_qualification_result(result),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
            sort_keys=True,
        )
        + "\n"
    )


def _reject_constant(value: str) -> NoReturn:
    raise QualificationSerializationError(f"$: invalid JSON numeric constant {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise QualificationSerializationError(f"$: duplicate JSON field {key!r}")
        result[key] = value
    return result


def load_strategy_qualification_json(text: str) -> StrategyQualificationResult:
    """Load strict JSON text without accepting NaN, Infinity, or duplicate keys."""
    if type(text) is not str:
        _fail("$", "JSON input must be an exact string")
    try:
        payload = json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_strict_object,
        )
    except QualificationSerializationError:
        raise
    except json.JSONDecodeError as exc:
        raise QualificationSerializationError(f"$: invalid JSON: {exc.msg}") from exc
    if type(payload) is not dict:
        _fail("$", "expected a JSON object")
    return deserialize_strategy_qualification_result(payload)


__all__ = [
    "QualificationSerializationError",
    "deserialize_strategy_qualification_result",
    "export_strategy_qualification_json",
    "load_strategy_qualification_json",
    "serialize_strategy_qualification_result",
]
