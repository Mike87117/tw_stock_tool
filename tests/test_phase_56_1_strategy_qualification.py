from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from types import MappingProxyType
import json
import unittest

from tw_stock_tool.qualification import (
    STRATEGY_QUALIFICATION_SCHEMA_VERSION,
    TAIWAN_EQUITY_DAILY_V1,
    PromotionDecision,
    QualificationFinding,
    QualificationMetricSet,
    QualificationModelError,
    QualificationPolicyError,
    QualificationSerializationError,
    StrategyDescriptor,
    StrategyQualificationRequest,
    StrategyQualificationResult,
    deserialize_strategy_qualification_result,
    evaluate_strategy_qualification,
    export_strategy_qualification_json,
    load_strategy_qualification_json,
    normalize_findings,
    resolve_qualification_policy,
    serialize_strategy_qualification_result,
)


EVALUATION_ID = "123e4567-e89b-42d3-a456-426614174000"
CREATED_AT = "2026-08-02T14:00:00Z"


def passing_metrics(**changes):
    values = {
        "evidence_scope": "out_of_sample",
        "data_leakage_free": True,
        "oos_observations": 504,
        "completed_trades": 40,
        "evaluated_symbols": 10,
        "valid_windows": 8,
        "benchmark_available": True,
        "total_return_pct": 18.0,
        "benchmark_return_pct": 10.0,
        "cost_stress_pass": True,
        "stressed_return_pct": 12.0,
        "max_drawdown_pct": 15.0,
        "positive_window_ratio": 0.75,
        "symbol_concentration_pct": 30.0,
        "parameter_stable": True,
        "partial_failure_count": 0,
    }
    values.update(changes)
    return QualificationMetricSet(**values)


def request_with(metrics=None, policy=None):
    return StrategyQualificationRequest(
        evaluation_id=EVALUATION_ID,
        created_at=CREATED_AT,
        strategy=StrategyDescriptor(
            strategy_id="ma_cross",
            parameters={"short_window": 5, "long_window": 20, "nested": [1, 2]},
        ),
        metrics=metrics or passing_metrics(),
        policy=policy or TAIWAN_EQUITY_DAILY_V1,
    )


class QualificationModelsTests(unittest.TestCase):
    def test_models_are_frozen_and_parameters_are_deeply_frozen(self):
        request = request_with()
        with self.assertRaises(FrozenInstanceError):
            request.metrics.completed_trades = 1
        with self.assertRaises(TypeError):
            request.strategy.parameters["short_window"] = 10
        self.assertEqual(request.strategy.parameters["nested"], (1, 2))

    def test_non_finite_metrics_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(QualificationModelError):
                    passing_metrics(total_return_pct=value)

    def test_invalid_enum_is_rejected(self):
        with self.assertRaises(QualificationModelError):
            passing_metrics(evidence_scope="future")
        with self.assertRaises(QualificationModelError):
            PromotionDecision(state="APPROVED", reason_codes=())

    def test_policy_resolver_is_exact_and_fail_closed(self):
        self.assertIs(
            resolve_qualification_policy("taiwan_equity_daily_v1"),
            TAIWAN_EQUITY_DAILY_V1,
        )
        with self.assertRaises(QualificationPolicyError):
            resolve_qualification_policy("unknown")


class FindingTests(unittest.TestCase):
    def test_findings_are_deduplicated_and_sorted_deterministically(self):
        warning = QualificationFinding(
            code="underperforms_benchmark",
            severity="warning",
            scope="aggregate",
            message="warning",
        )
        blocking = QualificationFinding(
            code="benchmark_missing",
            severity="blocking",
            scope="aggregate",
            message="blocking",
        )
        self.assertEqual(
            normalize_findings((warning, blocking, warning)),
            (blocking, warning),
        )


class EvaluatorTests(unittest.TestCase):
    def test_passing_evidence_is_paper_ready(self):
        result = evaluate_strategy_qualification(request_with())
        self.assertEqual(result.decision.state, "PAPER_READY")
        self.assertEqual(result.findings, ())
        self.assertEqual(result.decision.reason_codes, ())

    def test_threshold_shortfalls_are_research_candidate(self):
        result = evaluate_strategy_qualification(
            request_with(
                metrics=passing_metrics(
                    oos_observations=10,
                    completed_trades=2,
                    evaluated_symbols=1,
                    valid_windows=1,
                    total_return_pct=5.0,
                    cost_stress_pass=False,
                    max_drawdown_pct=40.0,
                    positive_window_ratio=0.25,
                    symbol_concentration_pct=90.0,
                    parameter_stable=False,
                )
            )
        )
        self.assertEqual(result.decision.state, "REJECTED")
        self.assertEqual(
            result.decision.reason_codes,
            (
                "cost_stress_failure",
                "insufficient_oos_observations",
                "insufficient_symbols",
                "insufficient_trades",
                "insufficient_valid_windows",
                "max_drawdown_exceeded",
                "parameter_instability",
                "symbol_concentration",
                "window_instability",
                "underperforms_benchmark",
            ),
        )

    def test_in_sample_only_evidence_is_rejected(self):
        result = evaluate_strategy_qualification(
            request_with(metrics=passing_metrics(evidence_scope="in_sample"))
        )
        self.assertEqual(result.decision.state, "REJECTED")
        self.assertEqual(result.decision.reason_codes, ("data_leakage_risk",))

    def test_declared_leakage_is_rejected(self):
        result = evaluate_strategy_qualification(
            request_with(metrics=passing_metrics(data_leakage_free=False))
        )
        self.assertEqual(result.decision.state, "REJECTED")
        self.assertEqual(result.decision.reason_codes, ("data_leakage_risk",))

    def test_missing_benchmark_is_rejected(self):
        result = evaluate_strategy_qualification(
            request_with(
                metrics=passing_metrics(
                    benchmark_available=False,
                    benchmark_return_pct=None,
                )
            )
        )
        self.assertEqual(result.decision.state, "REJECTED")
        self.assertIn("benchmark_missing", result.decision.reason_codes)

    def test_partial_failures_are_rejected(self):
        result = evaluate_strategy_qualification(
            request_with(metrics=passing_metrics(partial_failure_count=1))
        )
        self.assertEqual(result.decision.state, "REJECTED")
        self.assertIn("partial_data_failure", result.decision.reason_codes)

    def test_modified_registered_policy_is_rejected(self):
        unsupported = replace(TAIWAN_EQUITY_DAILY_V1, minimum_completed_trades=1)
        result = evaluate_strategy_qualification(request_with(policy=unsupported))
        self.assertEqual(result.decision.state, "REJECTED")
        self.assertEqual(result.decision.reason_codes, ("unsupported_policy",))

    def test_same_input_produces_equal_result(self):
        request = request_with()
        self.assertEqual(
            evaluate_strategy_qualification(request),
            evaluate_strategy_qualification(request),
        )


class SerializationTests(unittest.TestCase):
    def test_round_trip_and_deterministic_json(self):
        result = evaluate_strategy_qualification(request_with())
        payload = serialize_strategy_qualification_result(result)
        self.assertEqual(deserialize_strategy_qualification_result(payload), result)
        text_one = export_strategy_qualification_json(result)
        text_two = export_strategy_qualification_json(result)
        self.assertEqual(text_one, text_two)
        self.assertTrue(text_one.endswith("\n"))
        self.assertEqual(load_strategy_qualification_json(text_one), result)

    def test_unknown_field_is_rejected(self):
        payload = serialize_strategy_qualification_result(
            evaluate_strategy_qualification(request_with())
        )
        payload["unknown"] = 1
        with self.assertRaises(QualificationSerializationError):
            deserialize_strategy_qualification_result(payload)

    def test_unknown_nested_field_is_rejected(self):
        payload = serialize_strategy_qualification_result(
            evaluate_strategy_qualification(request_with())
        )
        payload["request"]["metrics"]["unknown"] = 1
        with self.assertRaises(QualificationSerializationError):
            deserialize_strategy_qualification_result(payload)

    def test_unsupported_finding_code_is_rejected(self):
        result = evaluate_strategy_qualification(
            request_with(metrics=passing_metrics(completed_trades=1))
        )
        payload = serialize_strategy_qualification_result(result)
        payload["findings"][0]["code"] = "unknown_code"
        payload["decision"]["reason_codes"][0] = "unknown_code"
        with self.assertRaises(QualificationSerializationError):
            deserialize_strategy_qualification_result(payload)

    def test_noncanonical_finding_order_is_rejected(self):
        result = evaluate_strategy_qualification(
            request_with(
                metrics=passing_metrics(
                    completed_trades=1,
                    valid_windows=1,
                )
            )
        )
        payload = serialize_strategy_qualification_result(result)
        payload["findings"].reverse()
        with self.assertRaises(QualificationSerializationError):
            deserialize_strategy_qualification_result(payload)

    def test_unsupported_schema_is_rejected(self):
        payload = serialize_strategy_qualification_result(
            evaluate_strategy_qualification(request_with())
        )
        payload["schema_version"] = "2.0"
        with self.assertRaises(QualificationSerializationError):
            deserialize_strategy_qualification_result(payload)

    def test_invalid_decision_enum_is_rejected(self):
        payload = serialize_strategy_qualification_result(
            evaluate_strategy_qualification(request_with())
        )
        payload["decision"]["state"] = "APPROVED"
        with self.assertRaises(QualificationSerializationError):
            deserialize_strategy_qualification_result(payload)

    def test_non_finite_json_constant_is_rejected(self):
        text = export_strategy_qualification_json(
            evaluate_strategy_qualification(request_with())
        )
        payload = json.loads(text)
        payload["request"]["metrics"]["total_return_pct"] = float("nan")
        bad_text = json.dumps(payload, allow_nan=True)
        with self.assertRaises(QualificationSerializationError):
            load_strategy_qualification_json(bad_text)

    def test_duplicate_json_field_is_rejected(self):
        text = (
            '{"schema_version":"1.0","schema_version":"1.0",'
            '"artifact_type":"strategy_qualification","request":{},'
            '"findings":[],"decision":{}}'
        )
        with self.assertRaises(QualificationSerializationError):
            load_strategy_qualification_json(text)

    def test_export_uses_expected_schema(self):
        payload = serialize_strategy_qualification_result(
            evaluate_strategy_qualification(request_with())
        )
        self.assertEqual(payload["schema_version"], STRATEGY_QUALIFICATION_SCHEMA_VERSION)
        self.assertEqual(payload["artifact_type"], "strategy_qualification")


    def test_direct_result_rejects_inconsistent_findings_and_decision(self):
        result = evaluate_strategy_qualification(request_with())
        with self.assertRaises(QualificationModelError):
            type(result)(
                schema_version=result.schema_version,
                artifact_type=result.artifact_type,
                request=result.request,
                findings=(
                    QualificationFinding(
                        code="benchmark_missing",
                        severity="blocking",
                        scope="aggregate",
                        message="forged",
                    ),
                ),
                decision=result.decision,
            )

    def test_direct_result_rejects_paper_ready_for_invalid_evidence(self):
        invalid_requests = (
            request_with(policy=replace(TAIWAN_EQUITY_DAILY_V1, policy_id="unknown")),
            request_with(
                policy=replace(TAIWAN_EQUITY_DAILY_V1, policy_version="2.0")
            ),
            request_with(
                policy=replace(TAIWAN_EQUITY_DAILY_V1, minimum_completed_trades=1)
            ),
            request_with(metrics=passing_metrics(evidence_scope="in_sample")),
            request_with(metrics=passing_metrics(partial_failure_count=1)),
            request_with(metrics=passing_metrics(completed_trades=1)),
            request_with(
                metrics=passing_metrics(
                    benchmark_available=False,
                    benchmark_return_pct=None,
                )
            ),
        )
        for request in invalid_requests:
            with self.subTest(request=request):
                with self.assertRaises(QualificationModelError):
                    StrategyQualificationResult(
                        schema_version=STRATEGY_QUALIFICATION_SCHEMA_VERSION,
                        artifact_type="strategy_qualification",
                        request=request,
                        findings=(),
                        decision=PromotionDecision(
                            state="PAPER_READY",
                            reason_codes=(),
                        ),
                    )

    def test_policy_severity_mapping_is_immutable_and_exact(self):
        self.assertIsInstance(TAIWAN_EQUITY_DAILY_V1.finding_severities, MappingProxyType)
        with self.assertRaises(TypeError):
            TAIWAN_EQUITY_DAILY_V1.finding_severities["benchmark_missing"] = "info"
        missing = dict(TAIWAN_EQUITY_DAILY_V1.finding_severities)
        missing.pop("benchmark_missing")
        with self.assertRaises(QualificationModelError):
            replace(TAIWAN_EQUITY_DAILY_V1, finding_severities=missing)
        unknown = dict(TAIWAN_EQUITY_DAILY_V1.finding_severities)
        unknown["unknown_code"] = "blocking"
        with self.assertRaises(QualificationModelError):
            replace(TAIWAN_EQUITY_DAILY_V1, finding_severities=unknown)

    def test_supported_findings_use_policy_severity(self):
        self.assertEqual(
            TAIWAN_EQUITY_DAILY_V1.finding_severities["benchmark_missing"],
            "blocking",
        )
        result = evaluate_strategy_qualification(
            request_with(
                metrics=passing_metrics(
                    benchmark_available=False,
                    benchmark_return_pct=None,
                )
            )
        )
        self.assertEqual(result.findings[0].severity, "blocking")
        self.assertEqual(result.decision.state, "REJECTED")

    def test_duplicate_findings_are_rejected_at_result_boundary(self):
        result = evaluate_strategy_qualification(
            request_with(metrics=passing_metrics(completed_trades=1))
        )
        with self.assertRaises(QualificationModelError):
            StrategyQualificationResult(
                schema_version=result.schema_version,
                artifact_type=result.artifact_type,
                request=result.request,
                findings=result.findings + (result.findings[0],),
                decision=result.decision,
            )

    def test_normalization_preserves_scope_metric_symbol_and_window_identity(self):
        findings = (
            QualificationFinding(
                code="underperforms_benchmark",
                severity="warning",
                scope="symbol",
                message="same",
                metric_name="return",
                symbol="2330",
                window=1,
            ),
            QualificationFinding(
                code="underperforms_benchmark",
                severity="warning",
                scope="symbol",
                message="same",
                metric_name="return",
                symbol="2317",
                window=1,
            ),
            QualificationFinding(
                code="underperforms_benchmark",
                severity="warning",
                scope="window",
                message="same",
                metric_name="return",
                window=1,
            ),
        )
        self.assertEqual(len(normalize_findings(findings)), 3)

    def test_parameter_mapping_order_is_canonical_recursively(self):
        first = replace(
            request_with(),
            strategy=StrategyDescriptor(
                strategy_id="ma_cross",
                parameters={
                    "b": 2,
                    "a": 1,
                    "nested": {"z": 3, "a": 1},
                },
            ),
        )
        second = replace(
            request_with(),
            strategy=StrategyDescriptor(
                strategy_id="ma_cross",
                parameters={
                    "nested": {"a": 1, "z": 3},
                    "a": 1,
                    "b": 2,
                },
            ),
        )
        self.assertEqual(
            export_strategy_qualification_json(
                evaluate_strategy_qualification(first)
            ),
            export_strategy_qualification_json(
                evaluate_strategy_qualification(second)
            ),
        )

    def test_direct_numeric_overflow_is_a_model_error_with_path(self):
        for value in (10**10000, -(10**10000)):
            with self.subTest(value="overflow"):
                with self.assertRaisesRegex(
                    QualificationModelError, "total_return_pct"
                ):
                    passing_metrics(total_return_pct=value)

    def test_json_numeric_overflow_is_a_serialization_error(self):
        payload = serialize_strategy_qualification_result(
            evaluate_strategy_qualification(request_with())
        )
        payload["request"]["metrics"]["total_return_pct"] = 10**10000
        with self.assertRaisesRegex(
            QualificationSerializationError, "total_return_pct"
        ):
            deserialize_strategy_qualification_result(payload)

    def test_json_read_back_rejects_forged_paper_ready_metrics(self):
        invalid_metrics = (
            {"evidence_scope": "in_sample"},
            {"partial_failure_count": 1},
            {"completed_trades": 1},
            {"benchmark_available": False, "benchmark_return_pct": None},
        )
        for changes in invalid_metrics:
            with self.subTest(changes=changes):
                payload = serialize_strategy_qualification_result(
                    evaluate_strategy_qualification(request_with())
                )
                payload["request"]["metrics"].update(changes)
                with self.assertRaises(QualificationSerializationError):
                    deserialize_strategy_qualification_result(payload)

    def test_json_read_back_rejects_severity_downgrade(self):
        payload = serialize_strategy_qualification_result(
            evaluate_strategy_qualification(
                request_with(
                    metrics=passing_metrics(
                        benchmark_available=False,
                        benchmark_return_pct=None,
                    )
                )
            )
        )
        payload["findings"][0]["severity"] = "info"
        with self.assertRaises(QualificationSerializationError):
            deserialize_strategy_qualification_result(payload)

    def test_json_read_back_rejects_duplicate_and_noncanonical_findings(self):
        result = evaluate_strategy_qualification(
            request_with(
                metrics=passing_metrics(
                    completed_trades=1,
                    valid_windows=1,
                )
            )
        )
        payload = serialize_strategy_qualification_result(result)
        payload["findings"].append(dict(payload["findings"][0]))
        with self.assertRaises(QualificationSerializationError):
            deserialize_strategy_qualification_result(payload)

        payload = serialize_strategy_qualification_result(result)
        payload["findings"].reverse()
        with self.assertRaises(QualificationSerializationError):
            deserialize_strategy_qualification_result(payload)


if __name__ == "__main__":
    unittest.main()
