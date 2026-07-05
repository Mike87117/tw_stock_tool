import unittest
from tw_stock_tool.risk import RiskDecision, RiskModelError, RiskInputSnapshot, check_max_order_notional

class TestRiskRules(unittest.TestCase):
    def setUp(self):
        self.snapshot = RiskInputSnapshot(
            symbol="2330",
            side="BUY",
            quantity=1000,
            price=100.0,
            cash=1000000.0
        )
        # order_notional = 100000.0

    def test_max_order_notional_allowed_below(self):
        decision = check_max_order_notional(self.snapshot, 200000.0)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.metadata["symbol"], "2330")
        self.assertEqual(decision.metadata["side"], "BUY")
        self.assertEqual(decision.metadata["order_notional"], 100000.0)
        self.assertEqual(decision.metadata["max_order_notional"], 200000.0)

    def test_max_order_notional_allowed_equal(self):
        decision = check_max_order_notional(self.snapshot, 100000.0)
        self.assertTrue(decision.allowed)

    def test_max_order_notional_rejected_exceeds(self):
        decision = check_max_order_notional(self.snapshot, 50000.0)
        self.assertTrue(decision.is_rejected)
        self.assertIn("order_notional exceeds max_order_notional", decision.reasons)
        self.assertEqual(decision.metadata["order_notional"], 100000.0)
        self.assertEqual(decision.metadata["max_order_notional"], 50000.0)

    def test_invalid_snapshot_raises(self):
        with self.assertRaises(RiskModelError):
            check_max_order_notional("not a snapshot", 100000.0) # type: ignore

    def test_zero_limit_raises(self):
        with self.assertRaises(RiskModelError):
            check_max_order_notional(self.snapshot, 0.0)

    def test_negative_limit_raises(self):
        with self.assertRaises(RiskModelError):
            check_max_order_notional(self.snapshot, -100.0)

    def test_bool_limit_raises(self):
        with self.assertRaises(RiskModelError):
            check_max_order_notional(self.snapshot, True) # type: ignore

    def test_non_number_limit_raises(self):
        with self.assertRaises(RiskModelError):
            check_max_order_notional(self.snapshot, "1000") # type: ignore

    def test_public_import(self):
        from tw_stock_tool.risk import check_max_order_notional as cmon
        self.assertEqual(cmon, check_max_order_notional)

    def test_max_position_quantity_allowed_below(self):
        snapshot = RiskInputSnapshot("2330", "BUY", 1000, 100.0, 100000.0, 1000) # projected = 2000
        from tw_stock_tool.risk.rules import check_max_position_quantity
        decision = check_max_position_quantity(snapshot, 3000)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.metadata["symbol"], "2330")
        self.assertEqual(decision.metadata["side"], "BUY")
        self.assertEqual(decision.metadata["quantity"], 1000)
        self.assertEqual(decision.metadata["current_position_quantity"], 1000)
        self.assertEqual(decision.metadata["projected_position_quantity"], 2000)
        self.assertEqual(decision.metadata["max_position_quantity"], 3000)

    def test_max_position_quantity_allowed_equal(self):
        snapshot = RiskInputSnapshot("2330", "BUY", 1000, 100.0, 100000.0, 1000) # projected = 2000
        from tw_stock_tool.risk.rules import check_max_position_quantity
        decision = check_max_position_quantity(snapshot, 2000)
        self.assertTrue(decision.allowed)

    def test_max_position_quantity_rejected_exceeds(self):
        snapshot = RiskInputSnapshot("2330", "BUY", 1000, 100.0, 100000.0, 1000) # projected = 2000
        from tw_stock_tool.risk.rules import check_max_position_quantity
        decision = check_max_position_quantity(snapshot, 1500)
        self.assertTrue(decision.is_rejected)
        self.assertIn("projected_position_quantity exceeds max_position_quantity", decision.reasons)
        self.assertEqual(decision.metadata["projected_position_quantity"], 2000)
        self.assertEqual(decision.metadata["max_position_quantity"], 1500)

    def test_max_position_quantity_sell_allowed(self):
        snapshot = RiskInputSnapshot("2330", "SELL", 1000, 100.0, 100000.0, 1000) # projected = 0
        from tw_stock_tool.risk.rules import check_max_position_quantity
        decision = check_max_position_quantity(snapshot, 2000)
        self.assertTrue(decision.allowed)

    def test_max_position_quantity_invalid_snapshot(self):
        from tw_stock_tool.risk.rules import check_max_position_quantity
        with self.assertRaises(RiskModelError):
            check_max_position_quantity("not a snapshot", 1000) # type: ignore

    def test_max_position_quantity_zero_limit(self):
        from tw_stock_tool.risk.rules import check_max_position_quantity
        with self.assertRaises(RiskModelError):
            check_max_position_quantity(self.snapshot, 0)

    def test_max_position_quantity_negative_limit(self):
        from tw_stock_tool.risk.rules import check_max_position_quantity
        with self.assertRaises(RiskModelError):
            check_max_position_quantity(self.snapshot, -100)

    def test_max_position_quantity_bool_limit(self):
        from tw_stock_tool.risk.rules import check_max_position_quantity
        with self.assertRaises(RiskModelError):
            check_max_position_quantity(self.snapshot, True) # type: ignore

    def test_max_position_quantity_non_int_limit(self):
        from tw_stock_tool.risk.rules import check_max_position_quantity
        with self.assertRaises(RiskModelError):
            check_max_position_quantity(self.snapshot, 1000.0) # type: ignore

    def test_max_position_quantity_public_import(self):
        from tw_stock_tool.risk import check_max_position_quantity as cmpq
        from tw_stock_tool.risk.rules import check_max_position_quantity
        self.assertEqual(cmpq, check_max_position_quantity)

    def test_max_position_notional_allowed_below(self):
        snapshot = RiskInputSnapshot("2330", "BUY", 1000, 100.0, 1000000.0, 1000, 100000.0) # projected = 200000.0
        from tw_stock_tool.risk.rules import check_max_position_notional
        decision = check_max_position_notional(snapshot, 300000.0)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.metadata["symbol"], "2330")
        self.assertEqual(decision.metadata["side"], "BUY")
        self.assertEqual(decision.metadata["quantity"], 1000)
        self.assertEqual(decision.metadata["price"], 100.0)
        self.assertEqual(decision.metadata["order_notional"], 100000.0)
        self.assertEqual(decision.metadata["current_position_notional"], 100000.0)
        self.assertEqual(decision.metadata["projected_position_notional"], 200000.0)
        self.assertEqual(decision.metadata["max_position_notional"], 300000.0)

    def test_max_position_notional_allowed_equal(self):
        snapshot = RiskInputSnapshot("2330", "BUY", 1000, 100.0, 1000000.0, 1000, 100000.0) # projected = 200000.0
        from tw_stock_tool.risk.rules import check_max_position_notional
        decision = check_max_position_notional(snapshot, 200000.0)
        self.assertTrue(decision.allowed)

    def test_max_position_notional_rejected_exceeds(self):
        snapshot = RiskInputSnapshot("2330", "BUY", 1000, 100.0, 1000000.0, 1000, 100000.0) # projected = 200000.0
        from tw_stock_tool.risk.rules import check_max_position_notional
        decision = check_max_position_notional(snapshot, 150000.0)
        self.assertTrue(decision.is_rejected)
        self.assertIn("projected_position_notional exceeds max_position_notional", decision.reasons)
        self.assertEqual(decision.metadata["projected_position_notional"], 200000.0)
        self.assertEqual(decision.metadata["max_position_notional"], 150000.0)

    def test_max_position_notional_sell_allowed(self):
        snapshot = RiskInputSnapshot("2330", "SELL", 1000, 100.0, 1000000.0, 1000, 100000.0) # projected = 0.0
        from tw_stock_tool.risk.rules import check_max_position_notional
        decision = check_max_position_notional(snapshot, 200000.0)
        self.assertTrue(decision.allowed)

    def test_max_position_notional_invalid_snapshot(self):
        from tw_stock_tool.risk.rules import check_max_position_notional
        with self.assertRaises(RiskModelError):
            check_max_position_notional("not a snapshot", 100000.0) # type: ignore

    def test_max_position_notional_zero_limit(self):
        from tw_stock_tool.risk.rules import check_max_position_notional
        with self.assertRaises(RiskModelError):
            check_max_position_notional(self.snapshot, 0.0)

    def test_max_position_notional_negative_limit(self):
        from tw_stock_tool.risk.rules import check_max_position_notional
        with self.assertRaises(RiskModelError):
            check_max_position_notional(self.snapshot, -100.0)

    def test_max_position_notional_bool_limit(self):
        from tw_stock_tool.risk.rules import check_max_position_notional
        with self.assertRaises(RiskModelError):
            check_max_position_notional(self.snapshot, True) # type: ignore

    def test_max_position_notional_non_number_limit(self):
        from tw_stock_tool.risk.rules import check_max_position_notional
        with self.assertRaises(RiskModelError):
            check_max_position_notional(self.snapshot, "1000") # type: ignore

    def test_max_position_notional_public_import(self):
        from tw_stock_tool.risk import check_max_position_notional as cmpn
        from tw_stock_tool.risk.rules import check_max_position_notional
        self.assertEqual(cmpn, check_max_position_notional)

    def test_max_total_exposure_allowed_below(self):
        snapshot = RiskInputSnapshot("2330", "BUY", 1000, 100.0, 1000000.0, 1000, 100000.0, total_exposure=1000000.0) # order_notional = 100000.0, total_exposure = 1000000.0, projected = 1100000.0
        from tw_stock_tool.risk.rules import check_max_total_exposure
        decision = check_max_total_exposure(snapshot, 1500000.0)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.metadata["symbol"], "2330")
        self.assertEqual(decision.metadata["side"], "BUY")
        self.assertEqual(decision.metadata["quantity"], 1000)
        self.assertEqual(decision.metadata["price"], 100.0)
        self.assertEqual(decision.metadata["order_notional"], 100000.0)
        self.assertEqual(decision.metadata["total_exposure"], 1000000.0)
        self.assertEqual(decision.metadata["projected_total_exposure"], 1100000.0)
        self.assertEqual(decision.metadata["max_total_exposure"], 1500000.0)

    def test_max_total_exposure_allowed_equal(self):
        snapshot = RiskInputSnapshot("2330", "BUY", 1000, 100.0, 1000000.0, 1000, 100000.0, total_exposure=1000000.0) # projected = 1100000.0
        from tw_stock_tool.risk.rules import check_max_total_exposure
        decision = check_max_total_exposure(snapshot, 1100000.0)
        self.assertTrue(decision.allowed)

    def test_max_total_exposure_rejected_exceeds(self):
        snapshot = RiskInputSnapshot("2330", "BUY", 1000, 100.0, 1000000.0, 1000, 100000.0, total_exposure=1000000.0) # projected = 1100000.0
        from tw_stock_tool.risk.rules import check_max_total_exposure
        decision = check_max_total_exposure(snapshot, 1050000.0)
        self.assertTrue(decision.is_rejected)
        self.assertIn("projected_total_exposure exceeds max_total_exposure", decision.reasons)
        self.assertEqual(decision.metadata["projected_total_exposure"], 1100000.0)
        self.assertEqual(decision.metadata["max_total_exposure"], 1050000.0)

    def test_max_total_exposure_sell_allowed(self):
        snapshot = RiskInputSnapshot("2330", "SELL", 1000, 100.0, 1000000.0, 1000, 100000.0, total_exposure=1000000.0) # projected = 900000.0
        from tw_stock_tool.risk.rules import check_max_total_exposure
        decision = check_max_total_exposure(snapshot, 1000000.0)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.metadata["projected_total_exposure"], 900000.0)

    def test_max_total_exposure_sell_clamped(self):
        snapshot = RiskInputSnapshot("2330", "SELL", 15000, 100.0, 1000000.0, 1000, 100000.0, total_exposure=1000000.0) # order_notional = 1500000.0, projected = max(0, 1000000 - 1500000) = 0.0
        from tw_stock_tool.risk.rules import check_max_total_exposure
        decision = check_max_total_exposure(snapshot, 500000.0)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.metadata["projected_total_exposure"], 0.0)

    def test_max_total_exposure_invalid_snapshot(self):
        from tw_stock_tool.risk.rules import check_max_total_exposure
        with self.assertRaises(RiskModelError):
            check_max_total_exposure("not a snapshot", 100000.0) # type: ignore

    def test_max_total_exposure_zero_limit(self):
        from tw_stock_tool.risk.rules import check_max_total_exposure
        with self.assertRaises(RiskModelError):
            check_max_total_exposure(self.snapshot, 0.0)

    def test_max_total_exposure_negative_limit(self):
        from tw_stock_tool.risk.rules import check_max_total_exposure
        with self.assertRaises(RiskModelError):
            check_max_total_exposure(self.snapshot, -100.0)

    def test_max_total_exposure_bool_limit(self):
        from tw_stock_tool.risk.rules import check_max_total_exposure
        with self.assertRaises(RiskModelError):
            check_max_total_exposure(self.snapshot, True) # type: ignore

    def test_max_total_exposure_non_number_limit(self):
        from tw_stock_tool.risk.rules import check_max_total_exposure
        with self.assertRaises(RiskModelError):
            check_max_total_exposure(self.snapshot, "1000") # type: ignore

    def test_max_total_exposure_public_import(self):
        from tw_stock_tool.risk import check_max_total_exposure as cmte
        from tw_stock_tool.risk.rules import check_max_total_exposure
        self.assertEqual(cmte, check_max_total_exposure)

    def test_combine_risk_decisions_all_allowed(self):
        from tw_stock_tool.risk.rules import combine_risk_decisions
        from tw_stock_tool.risk.models import RiskDecision
        d1 = RiskDecision.allow()
        d2 = RiskDecision.allow()
        combined = combine_risk_decisions([d1, d2])
        self.assertTrue(combined.allowed)
        self.assertEqual(combined.metadata["decision_count"], 2)
        self.assertEqual(combined.metadata["allowed_count"], 2)
        self.assertEqual(combined.metadata["rejected_count"], 0)
        self.assertTrue(combined.metadata["all_allowed"])

    def test_combine_risk_decisions_any_rejected(self):
        from tw_stock_tool.risk.rules import combine_risk_decisions
        from tw_stock_tool.risk.models import RiskDecision
        d1 = RiskDecision.allow()
        d2 = RiskDecision.reject(reasons=["r1"])
        d3 = RiskDecision.allow()
        combined = combine_risk_decisions([d1, d2, d3])
        self.assertTrue(combined.is_rejected)
        self.assertEqual(combined.reasons, ("r1",))
        self.assertEqual(combined.metadata["decision_count"], 3)
        self.assertEqual(combined.metadata["allowed_count"], 2)
        self.assertEqual(combined.metadata["rejected_count"], 1)
        self.assertFalse(combined.metadata["all_allowed"])

    def test_combine_risk_decisions_multiple_rejected(self):
        from tw_stock_tool.risk.rules import combine_risk_decisions
        from tw_stock_tool.risk.models import RiskDecision
        d1 = RiskDecision.reject(reasons=["r1"])
        d2 = RiskDecision.reject(reasons=["r2", "r3"])
        combined = combine_risk_decisions((d1, d2))
        self.assertTrue(combined.is_rejected)
        self.assertEqual(combined.reasons, ("r1", "r2", "r3"))
        self.assertEqual(combined.metadata["decision_count"], 2)
        self.assertEqual(combined.metadata["allowed_count"], 0)
        self.assertEqual(combined.metadata["rejected_count"], 2)
        self.assertFalse(combined.metadata["all_allowed"])

    def test_combine_risk_decisions_empty_raises(self):
        from tw_stock_tool.risk.rules import combine_risk_decisions
        with self.assertRaises(RiskModelError):
            combine_risk_decisions([])

    def test_combine_risk_decisions_non_sequence_raises(self):
        from tw_stock_tool.risk.rules import combine_risk_decisions
        from tw_stock_tool.risk.models import RiskDecision
        with self.assertRaises(RiskModelError):
            combine_risk_decisions(RiskDecision.allow()) # type: ignore

    def test_combine_risk_decisions_string_raises(self):
        from tw_stock_tool.risk.rules import combine_risk_decisions
        with self.assertRaises(RiskModelError):
            combine_risk_decisions("allowed") # type: ignore

    def test_combine_risk_decisions_bytes_raises(self):
        from tw_stock_tool.risk.rules import combine_risk_decisions
        with self.assertRaises(RiskModelError):
            combine_risk_decisions(b"allowed") # type: ignore

    def test_combine_risk_decisions_non_decision_item_raises(self):
        from tw_stock_tool.risk.rules import combine_risk_decisions
        from tw_stock_tool.risk.models import RiskDecision
        d1 = RiskDecision.allow()
        with self.assertRaises(RiskModelError):
            combine_risk_decisions([d1, "not a decision"]) # type: ignore

    def test_combine_risk_decisions_public_import(self):
        from tw_stock_tool.risk import combine_risk_decisions as crd
        from tw_stock_tool.risk.rules import combine_risk_decisions
        self.assertEqual(crd, combine_risk_decisions)

    def test_combine_risk_rule_evaluations_all_allowed(self):
        from tw_stock_tool.risk.rules import combine_risk_rule_evaluations
        from tw_stock_tool.risk.models import RiskRuleEvaluation, RiskDecision
        e1 = RiskRuleEvaluation(rule_name="rule1", decision=RiskDecision.allow())
        e2 = RiskRuleEvaluation(rule_name="rule2", decision=RiskDecision.allow())
        combined = combine_risk_rule_evaluations([e1, e2])
        self.assertTrue(combined.allowed)
        self.assertEqual(combined.metadata["evaluation_count"], 2)
        self.assertEqual(combined.metadata["allowed_count"], 2)
        self.assertEqual(combined.metadata["rejected_count"], 0)
        self.assertTrue(combined.metadata["all_allowed"])
        self.assertEqual(combined.metadata["rule_names"], ["rule1", "rule2"])
        self.assertEqual(combined.metadata["rejected_rule_names"], [])

    def test_combine_risk_rule_evaluations_any_rejected(self):
        from tw_stock_tool.risk.rules import combine_risk_rule_evaluations
        from tw_stock_tool.risk.models import RiskRuleEvaluation, RiskDecision
        e1 = RiskRuleEvaluation(rule_name="rule1", decision=RiskDecision.allow())
        e2 = RiskRuleEvaluation(rule_name="rule2", decision=RiskDecision.reject(reasons=["r1"]))
        e3 = RiskRuleEvaluation(rule_name="rule3", decision=RiskDecision.allow())
        combined = combine_risk_rule_evaluations([e1, e2, e3])
        self.assertTrue(combined.is_rejected)
        self.assertEqual(combined.reasons, ("rule2: r1",))
        self.assertEqual(combined.metadata["evaluation_count"], 3)
        self.assertEqual(combined.metadata["allowed_count"], 2)
        self.assertEqual(combined.metadata["rejected_count"], 1)
        self.assertFalse(combined.metadata["all_allowed"])
        self.assertEqual(combined.metadata["rule_names"], ["rule1", "rule2", "rule3"])
        self.assertEqual(combined.metadata["rejected_rule_names"], ["rule2"])

    def test_combine_risk_rule_evaluations_multiple_rejected(self):
        from tw_stock_tool.risk.rules import combine_risk_rule_evaluations
        from tw_stock_tool.risk.models import RiskRuleEvaluation, RiskDecision
        e1 = RiskRuleEvaluation(rule_name="rule1", decision=RiskDecision.reject(reasons=["r1"]))
        e2 = RiskRuleEvaluation(rule_name="rule2", decision=RiskDecision.reject(reasons=["r2", "r3"]))
        combined = combine_risk_rule_evaluations((e1, e2))
        self.assertTrue(combined.is_rejected)
        self.assertEqual(combined.reasons, ("rule1: r1", "rule2: r2", "rule2: r3"))
        self.assertEqual(combined.metadata["evaluation_count"], 2)
        self.assertEqual(combined.metadata["allowed_count"], 0)
        self.assertEqual(combined.metadata["rejected_count"], 2)
        self.assertFalse(combined.metadata["all_allowed"])
        self.assertEqual(combined.metadata["rule_names"], ["rule1", "rule2"])
        self.assertEqual(combined.metadata["rejected_rule_names"], ["rule1", "rule2"])

    def test_combine_risk_rule_evaluations_empty_raises(self):
        from tw_stock_tool.risk.rules import combine_risk_rule_evaluations
        with self.assertRaises(RiskModelError):
            combine_risk_rule_evaluations([])

    def test_combine_risk_rule_evaluations_non_sequence_raises(self):
        from tw_stock_tool.risk.rules import combine_risk_rule_evaluations
        from tw_stock_tool.risk.models import RiskRuleEvaluation, RiskDecision
        e1 = RiskRuleEvaluation(rule_name="rule1", decision=RiskDecision.allow())
        with self.assertRaises(RiskModelError):
            combine_risk_rule_evaluations(e1) # type: ignore

    def test_combine_risk_rule_evaluations_string_raises(self):
        from tw_stock_tool.risk.rules import combine_risk_rule_evaluations
        with self.assertRaises(RiskModelError):
            combine_risk_rule_evaluations("evals") # type: ignore

    def test_combine_risk_rule_evaluations_bytes_raises(self):
        from tw_stock_tool.risk.rules import combine_risk_rule_evaluations
        with self.assertRaises(RiskModelError):
            combine_risk_rule_evaluations(b"evals") # type: ignore

    def test_combine_risk_rule_evaluations_non_eval_item_raises(self):
        from tw_stock_tool.risk.rules import combine_risk_rule_evaluations
        from tw_stock_tool.risk.models import RiskRuleEvaluation, RiskDecision
        e1 = RiskRuleEvaluation(rule_name="rule1", decision=RiskDecision.allow())
        with self.assertRaises(RiskModelError):
            combine_risk_rule_evaluations([e1, "not an eval"]) # type: ignore

    def test_combine_risk_rule_evaluations_public_import(self):
        from tw_stock_tool.risk import combine_risk_rule_evaluations as crre
        from tw_stock_tool.risk.rules import combine_risk_rule_evaluations
        self.assertEqual(crre, combine_risk_rule_evaluations)

if __name__ == "__main__":
    unittest.main()
