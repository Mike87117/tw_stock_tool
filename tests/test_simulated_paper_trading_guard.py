import unittest

import tw_stock_tool.simulated_paper_trading_guard
from tw_stock_tool.simulated_paper_trading_guard import (
    SimulatedPaperTradingGuardDecision,
    SimulatedPaperTradingGuardError,
    evaluate_simulated_paper_trading_guard,
)
from tw_stock_tool.risk.models import RiskDecision
from tw_stock_tool.kill_switch.decisions import KillSwitchDecision


class TestSimulatedPaperTradingGuard(unittest.TestCase):
    def test_allowed_risk_and_kill_switch_returns_allowed(self):
        risk = RiskDecision.allow()
        kill_switch = KillSwitchDecision(is_allowed=True)
        decision = evaluate_simulated_paper_trading_guard(risk, kill_switch)
        self.assertTrue(decision.is_allowed)
        self.assertFalse(decision.is_blocked)
        self.assertEqual(decision.reasons, ())

    def test_rejected_risk_and_allowed_kill_switch_returns_blocked(self):
        risk = RiskDecision.reject(["Risk rejected."])
        kill_switch = KillSwitchDecision(is_allowed=True)
        decision = evaluate_simulated_paper_trading_guard(risk, kill_switch)
        self.assertTrue(decision.is_blocked)
        self.assertEqual(decision.reasons, ("Risk rejected.",))

    def test_allowed_risk_and_blocked_kill_switch_returns_blocked(self):
        risk = RiskDecision.allow()
        kill_switch = KillSwitchDecision(is_allowed=False, reason="Kill switch active.")
        decision = evaluate_simulated_paper_trading_guard(risk, kill_switch)
        self.assertTrue(decision.is_blocked)
        self.assertEqual(decision.reasons, ("Kill switch active.",))

    def test_rejected_risk_and_blocked_kill_switch_returns_blocked_with_both_reasons(self):
        risk = RiskDecision.reject(["Risk rejected."])
        kill_switch = KillSwitchDecision(is_allowed=False, reason="Kill switch active.")
        decision = evaluate_simulated_paper_trading_guard(risk, kill_switch)
        self.assertTrue(decision.is_blocked)
        self.assertEqual(decision.reasons, ("Kill switch active.", "Risk rejected."))

    def test_guard_decision_normalizes_list_to_tuple(self):
        decision = SimulatedPaperTradingGuardDecision.block(reasons=["A", "B"])
        self.assertIsInstance(decision.reasons, tuple)
        self.assertEqual(decision.reasons, ("A", "B"))

    def test_blocked_guard_decision_requires_at_least_one_reason(self):
        with self.assertRaises(SimulatedPaperTradingGuardError):
            SimulatedPaperTradingGuardDecision.block(reasons=[])

    def test_blank_reason_raises(self):
        with self.assertRaises(SimulatedPaperTradingGuardError):
            SimulatedPaperTradingGuardDecision.block(reasons=[""])

    def test_whitespace_only_reason_raises(self):
        with self.assertRaises(SimulatedPaperTradingGuardError):
            SimulatedPaperTradingGuardDecision.block(reasons=["   "])

    def test_non_bool_is_allowed_raises(self):
        with self.assertRaises(SimulatedPaperTradingGuardError):
            SimulatedPaperTradingGuardDecision(is_allowed="True") # type: ignore

    def test_non_dict_metadata_raises(self):
        with self.assertRaises(SimulatedPaperTradingGuardError):
            SimulatedPaperTradingGuardDecision(is_allowed=True, metadata="meta") # type: ignore

    def test_metadata_is_copied(self):
        meta = {"key": "value"}
        decision = SimulatedPaperTradingGuardDecision.allow(metadata=meta)
        meta["key"] = "new_value"
        self.assertEqual(decision.metadata["key"], "value")

    def test_is_blocked_property(self):
        self.assertFalse(SimulatedPaperTradingGuardDecision.allow().is_blocked)
        self.assertTrue(SimulatedPaperTradingGuardDecision.block(["reason"]).is_blocked)

    def test_evaluator_rejects_non_risk_decision(self):
        kill_switch = KillSwitchDecision(is_allowed=True)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            evaluate_simulated_paper_trading_guard("not risk", kill_switch) # type: ignore

    def test_evaluator_rejects_non_kill_switch_decision(self):
        risk = RiskDecision.allow()
        with self.assertRaises(SimulatedPaperTradingGuardError):
            evaluate_simulated_paper_trading_guard(risk, "not kill switch") # type: ignore

    def test_metadata_contents_are_correct(self):
        risk = RiskDecision.reject(["Risk rejected."])
        kill_switch = KillSwitchDecision(is_allowed=False, reason="Kill switch active.")
        decision = evaluate_simulated_paper_trading_guard(risk, kill_switch)

        expected_meta = {
            "risk_allowed": False,
            "kill_switch_allowed": False,
            "risk_reason_count": 1,
            "kill_switch_blocked": True,
        }
        self.assertEqual(decision.metadata, expected_meta)

    def test_public_imports_work(self):
        self.assertTrue(hasattr(tw_stock_tool.simulated_paper_trading_guard, "SimulatedPaperTradingGuardDecision"))
        self.assertTrue(hasattr(tw_stock_tool.simulated_paper_trading_guard, "SimulatedPaperTradingGuardError"))
        self.assertTrue(hasattr(tw_stock_tool.simulated_paper_trading_guard, "evaluate_simulated_paper_trading_guard"))

    def test_all_contains_expected_api(self):
        expected = [
            "SimulatedPaperTradingGuardDecision",
            "SimulatedPaperTradingGuardError",
            "evaluate_simulated_paper_trading_guard",
            "SimulatedPaperTradingGuardAdapter",
            "ReferencePriceProvider",
            "RiskDecisionProvider",
            "PortfolioExposureProvider",
            "run_simulated_paper_trading_with_guard",
            "run_simulated_paper_trading_result_with_guard",
        ]
        self.assertCountEqual(tw_stock_tool.simulated_paper_trading_guard.__all__, expected)

if __name__ == '__main__':
    unittest.main()
