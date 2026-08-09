import unittest

from tw_stock_tool.recommendation import (
    RecommendationEvidence,
    StrategyBoundRecommendationError,
    StrategyBoundRecommendationEvidence,
    require_strategy_bound_recommendation_evidence,
)


class StrategyBoundRecommendationDomainGuardTests(unittest.TestCase):
    def test_accepts_strategy_bound_evidence_by_identity(self):
        evidence = object.__new__(StrategyBoundRecommendationEvidence)
        self.assertIs(require_strategy_bound_recommendation_evidence(evidence), evidence)

    def test_rejects_legacy_recommendation_evidence(self):
        legacy = object.__new__(RecommendationEvidence)
        with self.assertRaisesRegex(StrategyBoundRecommendationError, "schema 1.1"):
            require_strategy_bound_recommendation_evidence(legacy)

    def test_rejects_non_evidence_values(self):
        for value in (None, {}, "1.1", 1, object()):
            with self.subTest(value=value):
                with self.assertRaisesRegex(StrategyBoundRecommendationError, "schema 1.1"):
                    require_strategy_bound_recommendation_evidence(value)


if __name__ == "__main__":
    unittest.main()
