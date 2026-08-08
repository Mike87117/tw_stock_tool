from __future__ import annotations

import json
import unittest

from tests.test_phase_56_3c1_strategy_bound_recommendation import (
    GENERATED_AT,
    OBSERVED_AT,
    RECOMMENDATION_ID,
    _evidence,
    _qualification,
)
from tw_stock_tool.recommendation import (
    CurrentSignalSnapshot,
    RecommendationArtifactSerializationError,
    RecommendationEvidence,
    StrategyBoundRecommendationEvidence,
    build_recommendation_evidence,
    export_recommendation_artifact_json,
    export_recommendation_evidence_json,
    export_strategy_bound_recommendation_evidence_json,
    load_recommendation_artifact_json,
)


class RecommendationArtifactDispatchTests(unittest.TestCase):
    def test_dispatch_loads_and_exports_schema_10_without_changing_bytes(self):
        legacy = build_recommendation_evidence(
            recommendation_id=RECOMMENDATION_ID,
            generated_at=GENERATED_AT,
            qualification=_qualification(),
            signal_snapshot=CurrentSignalSnapshot(
                symbol="2330",
                observed_at=OBSERVED_AT,
                signal="BUY",
                score=5.0,
                latest_close=1200.0,
            ),
        )
        original = export_recommendation_evidence_json(legacy)
        loaded = load_recommendation_artifact_json(original)
        self.assertIsInstance(loaded, RecommendationEvidence)
        self.assertEqual(export_recommendation_artifact_json(loaded), original)

    def test_dispatch_loads_and_exports_schema_11_without_changing_bytes(self):
        evidence = _evidence()
        original = export_strategy_bound_recommendation_evidence_json(evidence)
        loaded = load_recommendation_artifact_json(original)
        self.assertIsInstance(loaded, StrategyBoundRecommendationEvidence)
        self.assertEqual(export_recommendation_artifact_json(loaded), original)

    def test_dispatch_rejects_unknown_schema_version(self):
        payload = json.loads(
            export_strategy_bound_recommendation_evidence_json(_evidence())
        )
        payload["schema_version"] = "9.9"
        with self.assertRaisesRegex(
            RecommendationArtifactSerializationError,
            "unsupported schema version",
        ):
            load_recommendation_artifact_json(json.dumps(payload))

    def test_dispatch_rejects_duplicate_schema_version_before_dispatch(self):
        text = export_strategy_bound_recommendation_evidence_json(_evidence())
        duplicate = text.replace(
            '"schema_version": "1.1",',
            '"schema_version": "1.1",\n  "schema_version": "1.1",',
            1,
        )
        with self.assertRaisesRegex(
            RecommendationArtifactSerializationError,
            "duplicate JSON field",
        ):
            load_recommendation_artifact_json(duplicate)


if __name__ == "__main__":
    unittest.main()
