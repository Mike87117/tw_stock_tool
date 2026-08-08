from __future__ import annotations

from dataclasses import replace
import json
import math
import unittest

from tw_stock_tool.qualification import (
    QualificationMetricSet,
    StrategyDescriptor,
    StrategyQualificationRequest,
    TAIWAN_EQUITY_DAILY_V1,
    evaluate_strategy_qualification,
)
from tw_stock_tool.recommendation import (
    CurrentSignalSnapshot,
    StrategyBoundRecommendationError,
    StrategyBoundSerializationError,
    StrategyBoundSignalSnapshot,
    StrategySignalProvenance,
    build_recommendation_evidence,
    build_strategy_bound_recommendation_evidence,
    export_recommendation_evidence_json,
    export_strategy_bound_recommendation_evidence_json,
    load_recommendation_evidence_json,
    load_strategy_bound_recommendation_evidence_json,
)

EVALUATION_ID = "123e4567-e89b-42d3-a456-426614174000"
RECOMMENDATION_ID = "223e4567-e89b-42d3-a456-426614174000"
CREATED_AT = "2025-04-01T00:00:00Z"
TRAIN_START = "2025-03-20T00:00:00Z"
TRAIN_END = "2025-04-01T00:00:00Z"
OBSERVED_AT = "2025-04-02T00:00:00Z"
GENERATED_AT = "2025-04-03T00:00:00Z"
SELECTION_METRIC = "Train Sharpe Ratio"


def _strategy_parameters(*, signed_zero: float = -0.0) -> dict:
    return {
        "selection": SELECTION_METRIC,
        "train_days": 10,
        "test_days": 10,
        "step_days": 10,
        "signed_zero": signed_zero,
        "resolved_configuration": {
            "strategy": "ma_cross",
            "parameter_grid": (
                {"long_window": 4, "short_window": 2},
                {"long_window": 4, "short_window": 3},
            ),
            "sort_by": SELECTION_METRIC,
            "train_days": 10,
        },
    }


def _metrics(*, paper_ready: bool = True) -> QualificationMetricSet:
    return QualificationMetricSet(
        evidence_scope="out_of_sample",
        data_leakage_free=True,
        oos_observations=300 if paper_ready else 10,
        completed_trades=30 if paper_ready else 1,
        evaluated_symbols=5 if paper_ready else 1,
        valid_windows=5 if paper_ready else 1,
        benchmark_available=True,
        total_return_pct=12.0,
        benchmark_return_pct=5.0,
        cost_stress_pass=True,
        stressed_return_pct=8.0,
        max_drawdown_pct=10.0,
        positive_window_ratio=0.8,
        symbol_concentration_pct=25.0,
        parameter_stable=True,
        partial_failure_count=0,
    )


def _qualification(*, paper_ready: bool = True, signed_zero: float = -0.0):
    request = StrategyQualificationRequest(
        evaluation_id=EVALUATION_ID,
        created_at=CREATED_AT,
        strategy=StrategyDescriptor(
            strategy_id="ma_cross",
            parameters=_strategy_parameters(signed_zero=signed_zero),
        ),
        metrics=_metrics(paper_ready=paper_ready),
        policy=TAIWAN_EQUITY_DAILY_V1,
    )
    return evaluate_strategy_qualification(request)


def _provenance(**overrides) -> StrategySignalProvenance:
    values = {
        "qualification_evaluation_id": EVALUATION_ID,
        "strategy_id": "ma_cross",
        "selected_parameters": {"long_window": 4, "short_window": 2},
        "selection_rule": "train_only_parameter_search_v1",
        "selection_metric": SELECTION_METRIC,
        "selection_train_start": TRAIN_START,
        "selection_train_end": TRAIN_END,
        "selection_train_rows": 10,
    }
    values.update(overrides)
    return StrategySignalProvenance(**values)


def _snapshot(**overrides) -> StrategyBoundSignalSnapshot:
    values = {
        "symbol": "2330",
        "observed_at": OBSERVED_AT,
        "signal": "BUY",
        "latest_close": 1200.0,
        "provenance": _provenance(),
    }
    values.update(overrides)
    return StrategyBoundSignalSnapshot(**values)


def _evidence(*, paper_ready: bool = True):
    return build_strategy_bound_recommendation_evidence(
        recommendation_id=RECOMMENDATION_ID,
        generated_at=GENERATED_AT,
        qualification=_qualification(paper_ready=paper_ready),
        signal_snapshot=_snapshot(),
    )


class StrategyBoundRecommendationDomainTests(unittest.TestCase):
    def test_schema_10_round_trip_remains_byte_stable(self):
        qualification = _qualification()
        legacy = build_recommendation_evidence(
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
        first = export_recommendation_evidence_json(legacy)
        loaded = load_recommendation_evidence_json(first)
        second = export_recommendation_evidence_json(loaded)
        self.assertEqual(first, second)
        self.assertEqual(loaded, legacy)
        self.assertEqual(loaded.schema_version, "1.0")

    def test_valid_schema_11_round_trip_is_deterministic(self):
        evidence = _evidence()
        self.assertEqual(evidence.schema_version, "1.1")
        self.assertEqual(evidence.action, "ENTER")
        first = export_strategy_bound_recommendation_evidence_json(evidence)
        loaded = load_strategy_bound_recommendation_evidence_json(first)
        second = export_strategy_bound_recommendation_evidence_json(loaded)
        self.assertEqual(first, second)
        self.assertEqual(loaded, evidence)

    def test_signal_provenance_evaluation_id_mismatch_fails_closed(self):
        snapshot = _snapshot(
            provenance=_provenance(
                qualification_evaluation_id=(
                    "323e4567-e89b-42d3-a456-426614174000"
                )
            )
        )
        with self.assertRaisesRegex(
            StrategyBoundRecommendationError, "evaluation_id"
        ):
            build_strategy_bound_recommendation_evidence(
                recommendation_id=RECOMMENDATION_ID,
                generated_at=GENERATED_AT,
                qualification=_qualification(),
                signal_snapshot=snapshot,
            )

    def test_signal_provenance_strategy_id_mismatch_fails_closed(self):
        snapshot = _snapshot(provenance=_provenance(strategy_id="rsi"))
        with self.assertRaisesRegex(
            StrategyBoundRecommendationError, "strategy_id"
        ):
            build_strategy_bound_recommendation_evidence(
                recommendation_id=RECOMMENDATION_ID,
                generated_at=GENERATED_AT,
                qualification=_qualification(),
                signal_snapshot=snapshot,
            )

    def test_selected_parameters_must_belong_to_qualified_grid(self):
        snapshot = _snapshot(
            provenance=_provenance(
                selected_parameters={"long_window": 9, "short_window": 2}
            )
        )
        with self.assertRaisesRegex(
            StrategyBoundRecommendationError, "qualified parameter grid"
        ):
            build_strategy_bound_recommendation_evidence(
                recommendation_id=RECOMMENDATION_ID,
                generated_at=GENERATED_AT,
                qualification=_qualification(),
                signal_snapshot=snapshot,
            )

    def test_selected_parameters_require_exact_integer_types(self):
        for bad in (
            {"long_window": 4, "short_window": True},
            {"long_window": 4, "short_window": 2.0},
        ):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(
                    StrategyBoundRecommendationError, "exact int"
                ):
                    _provenance(selected_parameters=bad)

    def test_selection_metric_and_train_rows_must_match_qualification(self):
        cases = (
            (
                _provenance(selection_metric="Train Total Return %"),
                "selection_metric",
            ),
            (
                _provenance(selection_train_rows=9),
                "selection_train_rows",
            ),
        )
        for provenance, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    StrategyBoundRecommendationError, message
                ):
                    build_strategy_bound_recommendation_evidence(
                        recommendation_id=RECOMMENDATION_ID,
                        generated_at=GENERATED_AT,
                        qualification=_qualification(),
                        signal_snapshot=_snapshot(provenance=provenance),
                    )

    def test_selection_train_end_must_strictly_predate_observation(self):
        for end in (OBSERVED_AT, "2025-04-03T00:00:00Z"):
            with self.subTest(end=end):
                with self.assertRaisesRegex(
                    StrategyBoundRecommendationError, "strictly predate"
                ):
                    _snapshot(
                        provenance=_provenance(selection_train_end=end)
                    )

    def test_forged_action_and_promotion_still_fail_closed(self):
        evidence = _evidence()
        with self.assertRaisesRegex(
            StrategyBoundRecommendationError, "canonical derived action"
        ):
            replace(evidence, action="NO_TRADE")
        with self.assertRaisesRegex(
            StrategyBoundRecommendationError, "promotion_state"
        ):
            replace(evidence, promotion_state="REJECTED")

    def test_rejected_qualification_cannot_enter(self):
        evidence = _evidence(paper_ready=False)
        self.assertEqual(evidence.promotion_state, "REJECTED")
        self.assertEqual(evidence.action, "NO_TRADE")

    def test_schema_11_rejects_unknown_missing_and_duplicate_fields(self):
        text = export_strategy_bound_recommendation_evidence_json(_evidence())

        unknown = json.loads(text)
        unknown["extra"] = 1
        with self.assertRaisesRegex(
            StrategyBoundSerializationError, "unknown field"
        ):
            load_strategy_bound_recommendation_evidence_json(
                json.dumps(unknown)
            )

        missing = json.loads(text)
        del missing["signal_snapshot"]["provenance"]["selection_metric"]
        with self.assertRaisesRegex(
            StrategyBoundSerializationError, "missing field"
        ):
            load_strategy_bound_recommendation_evidence_json(
                json.dumps(missing)
            )

        duplicate = text.replace(
            '"schema_version": "1.1",',
            '"schema_version": "1.1",\n  "schema_version": "1.1",',
            1,
        )
        with self.assertRaisesRegex(
            StrategyBoundSerializationError, "duplicate JSON field"
        ):
            load_strategy_bound_recommendation_evidence_json(duplicate)

    def test_schema_11_rejects_wrong_schema_and_artifact_type(self):
        text = export_strategy_bound_recommendation_evidence_json(_evidence())
        for key, value in (
            ("schema_version", "1.0"),
            ("artifact_type", "other"),
        ):
            payload = json.loads(text)
            payload[key] = value
            with self.subTest(key=key):
                with self.assertRaises(StrategyBoundSerializationError):
                    load_strategy_bound_recommendation_evidence_json(
                        json.dumps(payload)
                    )

    def test_top_level_strategy_parameters_keep_exact_signed_zero(self):
        evidence = _evidence()
        text = export_strategy_bound_recommendation_evidence_json(evidence)
        payload = json.loads(text)
        self.assertLess(
            math.copysign(
                1.0, payload["strategy_parameters"]["signed_zero"]
            ),
            0.0,
        )
        payload["strategy_parameters"]["signed_zero"] = 0.0
        with self.assertRaisesRegex(
            StrategyBoundSerializationError,
            "strategy_parameters",
        ):
            load_strategy_bound_recommendation_evidence_json(
                json.dumps(payload)
            )

    def test_nested_provenance_is_immutable(self):
        source = {"long_window": 4, "short_window": 2}
        provenance = _provenance(selected_parameters=source)
        source["short_window"] = 99
        self.assertEqual(provenance.selected_parameters["short_window"], 2)
        with self.assertRaises(TypeError):
            provenance.selected_parameters["short_window"] = 3


if __name__ == "__main__":
    unittest.main()
