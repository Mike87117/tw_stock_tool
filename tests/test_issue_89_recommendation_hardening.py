from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
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
    serialize_recommendation_evidence,
)


EVALUATION_ID = "123e4567-e89b-42d3-a456-426614174000"
RECOMMENDATION_ID = "223e4567-e89b-42d3-a456-426614174000"
CREATED_AT = "2026-08-08T08:00:00Z"
GENERATED_AT = "2026-08-08T08:10:00Z"
OBSERVED_AT = "2026-08-08T08:05:00Z"


def _qualification(parameters):
    metrics = QualificationMetricSet(
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
    )
    request = StrategyQualificationRequest(
        evaluation_id=EVALUATION_ID,
        created_at=CREATED_AT,
        strategy=StrategyDescriptor(
            strategy_id="ma_cross",
            parameters=parameters,
        ),
        metrics=metrics,
        policy=TAIWAN_EQUITY_DAILY_V1,
    )
    return evaluate_strategy_qualification(request)


def _evidence(parameters):
    qualification = _qualification(parameters)
    snapshot = CurrentSignalSnapshot(
        symbol="2330",
        observed_at=OBSERVED_AT,
        signal="BUY",
        score=5.0,
        latest_close=1200.0,
    )
    return build_recommendation_evidence(
        recommendation_id=RECOMMENDATION_ID,
        generated_at=GENERATED_AT,
        qualification=qualification,
        signal_snapshot=snapshot,
    )


class ExactParameterProvenanceTests(unittest.TestCase):
    def test_direct_construction_rejects_bool_for_canonical_int(self):
        evidence = _evidence({"window": 1})
        with self.assertRaises(RecommendationModelError):
            replace(evidence, strategy_parameters={"window": True})

    def test_direct_construction_rejects_float_for_canonical_int(self):
        evidence = _evidence({"window": 1})
        with self.assertRaises(RecommendationModelError):
            replace(evidence, strategy_parameters={"window": 1.0})

    def test_nested_scalar_type_mismatch_is_rejected(self):
        evidence = _evidence({"nested": {"window": 1}, "values": [1, 2]})
        with self.assertRaises(RecommendationModelError):
            replace(
                evidence,
                strategy_parameters={
                    "nested": {"window": True},
                    "values": [1, 2],
                },
            )
        with self.assertRaises(RecommendationModelError):
            replace(
                evidence,
                strategy_parameters={
                    "nested": {"window": 1},
                    "values": [1.0, 2],
                },
            )

    def test_json_read_back_rejects_type_flipped_provenance(self):
        for forged_value in (True, 1.0):
            with self.subTest(forged_value=forged_value):
                payload = serialize_recommendation_evidence(
                    _evidence({"window": 1})
                )
                payload["strategy_parameters"]["window"] = forged_value
                with self.assertRaises(RecommendationSerializationError):
                    deserialize_recommendation_evidence(payload)


class DeepImmutabilityTests(unittest.TestCase):
    def test_nested_mapping_and_list_are_deeply_frozen(self):
        evidence = _evidence(
            {
                "nested": {"window": 1},
                "values": [1, {"flag": True}],
            }
        )
        self.assertIsInstance(evidence.strategy_parameters["values"], tuple)
        with self.assertRaises(TypeError):
            evidence.strategy_parameters["nested"]["window"] = 2
        with self.assertRaises(TypeError):
            evidence.strategy_parameters["values"][1]["flag"] = False

    def test_caller_mapping_alias_cannot_mutate_evidence(self):
        evidence = _evidence({"nested": {"window": 1}, "values": [1, 2]})
        supplied = {"nested": {"window": 1}, "values": [1, 2]}
        rebuilt = replace(evidence, strategy_parameters=supplied)

        supplied["nested"]["window"] = 99
        supplied["values"].append(3)

        self.assertEqual(rebuilt.strategy_parameters["nested"]["window"], 1)
        self.assertEqual(rebuilt.strategy_parameters["values"], (1, 2))


class ReadBackStrictnessTests(unittest.TestCase):
    def test_unsupported_schema_version_is_rejected(self):
        payload = serialize_recommendation_evidence(_evidence({"window": 1}))
        payload["schema_version"] = "2.0"
        with self.assertRaises(RecommendationSerializationError):
            deserialize_recommendation_evidence(payload)

    def test_wrong_artifact_type_is_rejected(self):
        payload = serialize_recommendation_evidence(_evidence({"window": 1}))
        payload["artifact_type"] = "other"
        with self.assertRaises(RecommendationSerializationError):
            deserialize_recommendation_evidence(payload)

    def test_missing_root_field_is_rejected(self):
        payload = serialize_recommendation_evidence(_evidence({"window": 1}))
        del payload["action"]
        with self.assertRaises(RecommendationSerializationError):
            deserialize_recommendation_evidence(payload)

    def test_missing_nested_signal_field_is_rejected(self):
        payload = serialize_recommendation_evidence(_evidence({"window": 1}))
        del payload["signal_snapshot"]["score"]
        with self.assertRaises(RecommendationSerializationError):
            deserialize_recommendation_evidence(payload)

    def test_embedded_qualification_still_owns_exact_field_validation(self):
        payload = serialize_recommendation_evidence(_evidence({"window": 1}))
        payload["qualification"]["extra"] = True
        with self.assertRaises(RecommendationSerializationError):
            deserialize_recommendation_evidence(payload)


class DependencyBoundaryHardeningTests(unittest.TestCase):
    def test_import_only_loads_allowed_internal_and_no_network_runtime(self):
        repo_root = Path(__file__).resolve().parents[1]
        command = "\n".join(
            [
                "import json, sys",
                "import tw_stock_tool.recommendation",
                "allowed = ('tw_stock_tool.qualification', 'tw_stock_tool.recommendation')",
                "internal = sorted(name for name in sys.modules if name.startswith('tw_stock_tool.') and not any(name == prefix or name.startswith(prefix + '.') for prefix in allowed))",
                "network_names = {'requests', 'yfinance', 'urllib.request', 'http.client', 'socket'}",
                "network = sorted(name for name in network_names if name in sys.modules)",
                "print(json.dumps({'internal': internal, 'network': network}, sort_keys=True))",
            ]
        )
        completed = subprocess.run(
            [sys.executable, "-c", command],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        observed = json.loads(completed.stdout)
        self.assertEqual(observed, {"internal": [], "network": []})


if __name__ == "__main__":
    unittest.main()
