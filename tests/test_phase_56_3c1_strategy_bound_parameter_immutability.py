from __future__ import annotations

import unittest

from tests.test_phase_56_3c1_strategy_bound_recommendation import _evidence
from tw_stock_tool.recommendation import (
    export_strategy_bound_recommendation_evidence_json,
    load_strategy_bound_recommendation_evidence_json,
)


class StrategyBoundParameterImmutabilityTests(unittest.TestCase):
    def test_json_readback_uses_canonical_immutable_strategy_parameters(self):
        loaded = load_strategy_bound_recommendation_evidence_json(
            export_strategy_bound_recommendation_evidence_json(_evidence())
        )
        self.assertIs(
            loaded.strategy_parameters,
            loaded.qualification.request.strategy.parameters,
        )
        with self.assertRaises(TypeError):
            loaded.strategy_parameters["selection"] = "forged"


if __name__ == "__main__":
    unittest.main()
