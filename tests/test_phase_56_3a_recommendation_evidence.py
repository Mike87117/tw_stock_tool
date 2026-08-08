from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
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
    RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE,
    RECOMMENDATION_EVIDENCE_SCHEMA_VERSION,
    CurrentSignalSnapshot,
    RecommendationModelError,
    RecommendationSerializationError,
    build_recommendation_evidence,
    deserialize_recommendation_evidence,
    derive_recommendation_action,
    export_recommendation_evidence_json,
    load_recommendation_evidence_json,
    serialize_recommendation_evidence,
)


EVALUATION_ID = "123e4567-e89b-42d3-a456-426614174000"
RECOMMENDATION_ID = "223e4567-e89b-42d3-a456-426614174000"
OTHER_ID = "323e4567-e89b-42d3-a456-426614174000"
CREATED_AT = "2026-08-08T08:00:00Z"
GENERATED_AT = "2026-08-08T08:10:00Z"
OBSERVED_AT = "2026-08-08T08:05:00Z"


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


def qualification_with(*, metrics=None, parameters=None):
    request = StrategyQualificationRequest(
        evaluation_id=EVALUATION_ID,
        created_at=CREATED_AT,
        strategy=StrategyDescriptor(
            strategy_id="ma_cross",
            parameters=parameters
            or {
                "short_window": 5,
                "long_window": 20,
                "nested": {"a": 1, "z": 2},
            },
        ),
        metrics=metrics or passing_metrics(),
        policy=TAIWAN_EQUITY_DAILY_V1,
    )
    return evaluate_strategy_qualification(request)


def snapshot(signal="BUY", **changes):
    values = {
        "symbol": "2330",
        "observed_at": OBSERVED_AT,
        "signal": signal,
        "score": 5.0,
        "latest_close": 1200.0,
    }
    values.update(changes)
    return CurrentSignalSnapshot(**values)


def evidence_for(qualification, signal="BUY"):
    return build_recommendation_evidence(
        recommendation_id=RECOMMENDATION_ID,
        generated_at=GENERATED_AT,
        qualification=qualification,
        signal_snapshot=snapshot(signal),
    )


class ActionGateTests(unittest.TestCase):
    def test_rejected_cannot_enter(self):
        qualification = qualification_with(
            metrics=passing_metrics(evidence_scope="in_sample")
        )
        self.assertEqual(qualification.decision.state, "REJECTED")
        self.assertEqual(
            derive_recommendation_action(qualification, snapshot("BUY")),
            "NO_TRADE",
        )
        self.assertEqual(evidence_for(qualification).action, "NO_TRADE")

    def test_research_candidate_cannot_enter(self):
        qualification = qualification_with(
            metrics=passing_metrics(total_return_pct=5.0, benchmark_return_pct=10.0)
        )
        self.assertEqual(qualification.decision.state, "RESEARCH_CANDIDATE")
        self.assertEqual(evidence_for(qualification, "BUY").action, "WATCH")
        self.assertEqual(evidence_for(qualification, "WATCH").action, "WATCH")
        self.assertEqual(evidence_for(qualification, "HOLD").action, "NO_TRADE")
        self.assertEqual(evidence_for(qualification, "SELL").action, "NO_TRADE")

    def test_paper_ready_signal_mapping_is_closed_and_deterministic(self):
        qualification = qualification_with()
        self.assertEqual(qualification.decision.state, "PAPER_READY")
        expected = {
            "BUY": "ENTER",
            "WATCH": "WATCH",
            "HOLD": "HOLD",
            "SELL": "EXIT",
        }
        for signal, action in expected.items():
            with self.subTest(signal=signal):
                self.assertEqual(evidence_for(qualification, signal).action, action)

    def test_direct_forged_action_is_rejected(self):
        evidence = evidence_for(qualification_with())
        with self.assertRaises(RecommendationModelError):
            replace(evidence, action="NO_TRADE")


class ModelTests(unittest.TestCase):
    def test_models_are_frozen(self):
        current = snapshot()
        evidence = evidence_for(qualification_with())
        with self.assertRaises(FrozenInstanceError):
            current.score = 1.0
        with self.assertRaises(FrozenInstanceError):
            evidence.action = "NO_TRADE"
        with self.assertRaises(TypeError):
            evidence.strategy_parameters["short_window"] = 10

    def test_non_finite_signal_values_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(field="score", value=value):
                with self.assertRaises(RecommendationModelError):
                    snapshot(score=value)
            with self.subTest(field="latest_close", value=value):
                with self.assertRaises(RecommendationModelError):
                    snapshot(latest_close=value)

    def test_unknown_signal_and_action_are_rejected(self):
        with self.assertRaises(RecommendationModelError):
            snapshot("STRONG_BUY")
        evidence = evidence_for(qualification_with())
        with self.assertRaises(RecommendationModelError):
            replace(evidence, action="BUY")

    def test_provenance_fields_must_match_qualification(self):
        evidence = evidence_for(qualification_with())
        with self.assertRaises(RecommendationModelError):
            replace(evidence, source_qualification_evaluation_id=OTHER_ID)
        with self.assertRaises(RecommendationModelError):
            replace(evidence, promotion_state="REJECTED")
        with self.assertRaises(RecommendationModelError):
            replace(evidence, strategy_id="rsi")
        with self.assertRaises(RecommendationModelError):
            replace(evidence, strategy_parameters={"other": 1})
        with self.assertRaises(RecommendationModelError):
            replace(evidence, qualification_finding_codes=("forged",))

    def test_qualification_finding_codes_are_preserved_canonically(self):
        rejected = evidence_for(
            qualification_with(metrics=passing_metrics(evidence_scope="in_sample"))
        )
        self.assertEqual(rejected.qualification_finding_codes, ("data_leakage_risk",))


class SerializationTests(unittest.TestCase):
    def test_round_trip_and_expected_schema(self):
        evidence = evidence_for(qualification_with())
        payload = serialize_recommendation_evidence(evidence)
        self.assertEqual(
            payload["schema_version"], RECOMMENDATION_EVIDENCE_SCHEMA_VERSION
        )
        self.assertEqual(
            payload["artifact_type"], RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE
        )
        self.assertEqual(deserialize_recommendation_evidence(payload), evidence)
        text = export_recommendation_evidence_json(evidence)
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(load_recommendation_evidence_json(text), evidence)

    def test_forged_json_action_and_provenance_are_rejected(self):
        payload = serialize_recommendation_evidence(evidence_for(qualification_with()))
        payload["action"] = "NO_TRADE"
        with self.assertRaises(RecommendationSerializationError):
            deserialize_recommendation_evidence(payload)

        payload = serialize_recommendation_evidence(evidence_for(qualification_with()))
        payload["source_qualification_evaluation_id"] = OTHER_ID
        with self.assertRaises(RecommendationSerializationError):
            deserialize_recommendation_evidence(payload)

    def test_unknown_field_is_rejected(self):
        payload = serialize_recommendation_evidence(evidence_for(qualification_with()))
        payload["unknown"] = True
        with self.assertRaises(RecommendationSerializationError):
            deserialize_recommendation_evidence(payload)

    def test_unknown_nested_signal_field_is_rejected(self):
        payload = serialize_recommendation_evidence(evidence_for(qualification_with()))
        payload["signal_snapshot"]["unknown"] = True
        with self.assertRaises(RecommendationSerializationError):
            deserialize_recommendation_evidence(payload)

    def test_duplicate_json_field_is_rejected(self):
        text = export_recommendation_evidence_json(evidence_for(qualification_with()))
        duplicate = text.replace(
            '"action": "ENTER",',
            '"action": "ENTER",\n  "action": "ENTER",',
            1,
        )
        with self.assertRaises(RecommendationSerializationError):
            load_recommendation_evidence_json(duplicate)

    def test_non_finite_json_constant_is_rejected(self):
        payload = serialize_recommendation_evidence(evidence_for(qualification_with()))
        payload["signal_snapshot"]["score"] = float("nan")
        text = json.dumps(payload, allow_nan=True)
        with self.assertRaises(RecommendationSerializationError):
            load_recommendation_evidence_json(text)

    def test_semantically_equal_parameter_mappings_produce_identical_json(self):
        first_qualification = qualification_with(
            parameters={
                "short_window": 5,
                "long_window": 20,
                "nested": {"z": 2, "a": 1},
            }
        )
        second_qualification = qualification_with(
            parameters={
                "nested": {"a": 1, "z": 2},
                "long_window": 20,
                "short_window": 5,
            }
        )
        first = evidence_for(first_qualification)
        second = evidence_for(second_qualification)
        self.assertEqual(first, second)
        self.assertEqual(
            export_recommendation_evidence_json(first),
            export_recommendation_evidence_json(second),
        )


class DependencyBoundaryTests(unittest.TestCase):
    def test_import_does_not_load_trading_or_network_runtime(self):
        repo_root = Path(__file__).resolve().parents[1]
        command = (
            "import sys; import tw_stock_tool.recommendation; "
            "blocked=[name for name in sys.modules "
            "if name.startswith('tw_stock_tool.paper_trading') "
            "or name.startswith('tw_stock_tool.simulated_paper_trading') "
            "or name == 'requests']; "
            "print('|'.join(sorted(blocked)))"
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
        self.assertEqual(completed.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
