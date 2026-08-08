from __future__ import annotations

from dataclasses import replace
import unittest

from tw_stock_tool.qualification import (
    TAIWAN_EQUITY_DAILY_V1,
    QualificationMetricSet,
    StrategyDescriptor,
    StrategyQualificationRequest,
    evaluate_strategy_qualification,
)
from tw_stock_tool.recommendation import (
    CurrentSignalSnapshot,
    RecommendationModelError,
    RecommendationSerializationError,
    build_recommendation_evidence,
    deserialize_recommendation_evidence,
    export_recommendation_evidence_json,
    serialize_recommendation_evidence,
)

EVALUATION_ID = "123e4567-e89b-42d3-a456-426614174000"
RECOMMENDATION_ID = "223e4567-e89b-42d3-a456-426614174000"
CREATED_AT = "2026-08-08T08:00:00Z"
GENERATED_AT = "2026-08-08T08:10:00Z"
OBSERVED_AT = "2026-08-08T08:05:00Z"


def _evidence(parameters):
    request = StrategyQualificationRequest(
        evaluation_id=EVALUATION_ID,
        created_at=CREATED_AT,
        strategy=StrategyDescriptor(strategy_id="ma_cross", parameters=parameters),
        metrics=QualificationMetricSet(
            evidence_scope="out_of_sample",
            data_leakage_free=True,
            oos_observations=504,
            completed_trades=40,
            evaluated_symbols=10,
            valid_windows=8,
            benchmark_available=True,
            total_return_pct=18.0,
            benchmark_return_pct=10.0,
            cost_stress_pass=True,
            stressed_return_pct=12.0,
            max_drawdown_pct=15.0,
            positive_window_ratio=0.75,
            symbol_concentration_pct=30.0,
            parameter_stable=True,
            partial_failure_count=0,
        ),
        policy=TAIWAN_EQUITY_DAILY_V1,
    )
    qualification = evaluate_strategy_qualification(request)
    return build_recommendation_evidence(
        recommendation_id=RECOMMENDATION_ID,
        generated_at=GENERATED_AT,
        qualification=qualification,
        signal_snapshot=CurrentSignalSnapshot(
            symbol="2330",
            observed_at=OBSERVED_AT,
            signal="BUY",
            score=5.0,
            latest_close=1200.0,
        ),
    )


class SignedZeroProvenanceTests(unittest.TestCase):
    def test_direct_construction_rejects_negative_zero_for_positive_zero(self):
        evidence = _evidence({"w": 0.0})
        with self.assertRaises(RecommendationModelError):
            replace(evidence, strategy_parameters={"w": -0.0})

    def test_direct_construction_rejects_positive_zero_for_negative_zero(self):
        evidence = _evidence({"w": -0.0})
        with self.assertRaises(RecommendationModelError):
            replace(evidence, strategy_parameters={"w": 0.0})

    def test_nested_json_read_back_rejects_signed_zero_flip(self):
        evidence = _evidence({"nested": {"w": 0.0}})
        payload = serialize_recommendation_evidence(evidence)
        payload["strategy_parameters"]["nested"]["w"] = -0.0
        with self.assertRaises(RecommendationSerializationError):
            deserialize_recommendation_evidence(payload)

    def test_same_signed_zero_remains_deterministic(self):
        for value in (0.0, -0.0):
            with self.subTest(value=value):
                evidence = _evidence({"w": value})
                rebuilt = deserialize_recommendation_evidence(
                    serialize_recommendation_evidence(evidence)
                )
                self.assertEqual(
                    export_recommendation_evidence_json(rebuilt),
                    export_recommendation_evidence_json(evidence),
                )


if __name__ == "__main__":
    unittest.main()
