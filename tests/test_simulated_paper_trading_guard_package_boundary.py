"""
Tests for the Simulated Paper Trading Guard package public boundary.
"""
import unittest

import tw_stock_tool.simulated_paper_trading_guard as guard_pkg
import tw_stock_tool.simulated_paper_trading_guard.models as models_module
import tw_stock_tool.simulated_paper_trading_guard.evaluator as evaluator_module


class TestSimulatedPaperTradingGuardPackageBoundary(unittest.TestCase):
    def test_package_all_exports(self):
        expected_exports = [
            "SimulatedPaperTradingGuardDecision",
            "SimulatedPaperTradingGuardError",
            "evaluate_simulated_paper_trading_guard",
            "SimulatedPaperTradingGuardAdapter",
            "ReferencePriceProvider",
            "RiskDecisionProvider",
            "run_simulated_paper_trading_with_guard",
            "run_simulated_paper_trading_result_with_guard",
        ]
        self.assertCountEqual(guard_pkg.__all__, expected_exports)

    def test_decision_model_identity(self):
        self.assertIs(
            guard_pkg.SimulatedPaperTradingGuardDecision,
            models_module.SimulatedPaperTradingGuardDecision,
        )

    def test_error_model_identity(self):
        self.assertIs(
            guard_pkg.SimulatedPaperTradingGuardError,
            models_module.SimulatedPaperTradingGuardError,
        )

    def test_evaluator_identity(self):
        self.assertIs(
            guard_pkg.evaluate_simulated_paper_trading_guard,
            evaluator_module.evaluate_simulated_paper_trading_guard,
        )

if __name__ == '__main__':
    unittest.main()
