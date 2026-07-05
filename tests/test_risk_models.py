import unittest
from tw_stock_tool.risk import RiskDecision, RiskModelError, RiskInputSnapshot

class TestRiskModels(unittest.TestCase):
    def test_allow_default(self):
        decision = RiskDecision.allow()
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.is_rejected)
        self.assertEqual(decision.reasons, ())
        self.assertEqual(decision.metadata, {})

    def test_reject_with_reasons(self):
        decision = RiskDecision.reject(reasons=["Too risky", "Exceeds max exposure"])
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.is_rejected)
        self.assertEqual(decision.reasons, ("Too risky", "Exceeds max exposure"))

    def test_reject_empty_reasons_raises(self):
        with self.assertRaises(RiskModelError):
            RiskDecision.reject(reasons=[])

    def test_non_bool_allowed_raises(self):
        with self.assertRaises(RiskModelError):
            RiskDecision(allowed="True") # type: ignore

    def test_non_string_reason_raises(self):
        with self.assertRaises(RiskModelError):
            RiskDecision.reject(reasons=[123]) # type: ignore

    def test_blank_reason_raises(self):
        with self.assertRaises(RiskModelError):
            RiskDecision.reject(reasons=["   "])
            
    def test_empty_string_reason_raises(self):
        with self.assertRaises(RiskModelError):
            RiskDecision.reject(reasons=[""])

    def test_non_dict_metadata_raises(self):
        with self.assertRaises(RiskModelError):
            RiskDecision.allow(metadata=["not a dict"]) # type: ignore

    def test_public_import_works(self):
        from tw_stock_tool.risk import RiskDecision as RD, RiskModelError as RME
        self.assertEqual(RD, RiskDecision)
        self.assertEqual(RME, RiskModelError)

    def test_normalize_list_reasons(self):
        decision = RiskDecision.allow(reasons=["ok reason"])
        self.assertIsInstance(decision.reasons, tuple)
        self.assertEqual(decision.reasons, ("ok reason",))

    def test_reject_string_reason_raises(self):
        with self.assertRaises(RiskModelError):
            RiskDecision.reject(reasons="too risky") # type: ignore
            
    def test_allow_string_reason_raises(self):
        with self.assertRaises(RiskModelError):
            RiskDecision.allow(reasons="ok") # type: ignore

    def test_valid_buy_snapshot(self):
        snapshot = RiskInputSnapshot(
            symbol="2330",
            side="BUY",
            quantity=1000,
            price=100.0,
            cash=100000.0
        )
        self.assertEqual(snapshot.symbol, "2330")
        self.assertEqual(snapshot.side, "BUY")
        self.assertEqual(snapshot.order_notional, 100000.0)
        self.assertEqual(snapshot.projected_position_quantity, 1000)
        self.assertEqual(snapshot.projected_position_notional, 100000.0)

    def test_invalid_metadata_type(self):
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(
                symbol="2330",
                side="BUY",
                quantity=1000,
                price=500.0,
                cash=100000.0,
                current_position_quantity=0,
                current_position_notional=0.0,
                total_exposure=0.0,
                metadata="invalid" # type: ignore
            )

    def test_valid_sell_snapshot(self):
        snapshot = RiskInputSnapshot(
            symbol="2330",
            side="SELL",
            quantity=1000,
            price=100.0,
            cash=100000.0,
            current_position_quantity=2000,
            current_position_notional=200000.0
        )
        self.assertEqual(snapshot.order_notional, 100000.0)
        self.assertEqual(snapshot.projected_position_quantity, 1000)
        self.assertEqual(snapshot.projected_position_notional, 100000.0)
        
    def test_snapshot_blank_symbol(self):
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol=" ", side="BUY", quantity=1000, price=100.0, cash=10000.0)
            
    def test_snapshot_invalid_side(self):
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="HOLD", quantity=1000, price=100.0, cash=10000.0) # type: ignore
            
    def test_snapshot_negative_quantity(self):
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="BUY", quantity=-1000, price=100.0, cash=10000.0)
            
    def test_snapshot_zero_quantity(self):
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="BUY", quantity=0, price=100.0, cash=10000.0)
            
    def test_snapshot_negative_price(self):
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="BUY", quantity=1000, price=-100.0, cash=10000.0)
            
    def test_snapshot_zero_price(self):
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="BUY", quantity=1000, price=0.0, cash=10000.0)
            
    def test_snapshot_negative_cash(self):
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="BUY", quantity=1000, price=100.0, cash=-10000.0)
            
    def test_snapshot_negative_current_position_quantity(self):
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="BUY", quantity=1000, price=100.0, cash=10000.0, current_position_quantity=-10)
            
    def test_snapshot_negative_current_position_notional(self):
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="BUY", quantity=1000, price=100.0, cash=10000.0, current_position_notional=-10.0)
            
    def test_snapshot_negative_total_exposure(self):
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="BUY", quantity=1000, price=100.0, cash=10000.0, total_exposure=-10.0)
            
    def test_snapshot_non_dict_metadata(self):
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="BUY", quantity=1000, price=100.0, cash=10000.0, metadata=["list"]) # type: ignore

    def test_snapshot_bool_numeric_fields(self):
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="BUY", quantity=True, price=100.0, cash=10000.0) # type: ignore
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="BUY", quantity=1000, price=True, cash=10000.0) # type: ignore
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="BUY", quantity=1000, price=100.0, cash=True) # type: ignore
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="BUY", quantity=1000, price=100.0, cash=10000.0, current_position_quantity=True) # type: ignore
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="BUY", quantity=1000, price=100.0, cash=10000.0, current_position_notional=True) # type: ignore
        with self.assertRaises(RiskModelError):
            RiskInputSnapshot(symbol="2330", side="BUY", quantity=1000, price=100.0, cash=10000.0, total_exposure=True) # type: ignore

    def test_snapshot_public_import(self):
        from tw_stock_tool.risk import RiskInputSnapshot as RIS
        self.assertEqual(RIS, RiskInputSnapshot)

class TestRiskRuleEvaluation(unittest.TestCase):
    def test_valid_allowed_evaluation(self):
        from tw_stock_tool.risk.models import RiskRuleEvaluation, RiskDecision
        decision = RiskDecision.allow()
        eval_item = RiskRuleEvaluation(rule_name="rule1", decision=decision)
        self.assertEqual(eval_item.rule_name, "rule1")
        self.assertTrue(eval_item.decision.allowed)
        self.assertEqual(eval_item.metadata, {})

    def test_valid_rejected_evaluation(self):
        from tw_stock_tool.risk.models import RiskRuleEvaluation, RiskDecision
        decision = RiskDecision.reject(reasons=["r1"])
        eval_item = RiskRuleEvaluation(rule_name="rule2", decision=decision)
        self.assertEqual(eval_item.rule_name, "rule2")
        self.assertTrue(eval_item.decision.is_rejected)

    def test_blank_rule_name_raises(self):
        from tw_stock_tool.risk.models import RiskRuleEvaluation, RiskDecision, RiskModelError
        decision = RiskDecision.allow()
        with self.assertRaises(RiskModelError):
            RiskRuleEvaluation(rule_name="", decision=decision)
        with self.assertRaises(RiskModelError):
            RiskRuleEvaluation(rule_name="   ", decision=decision)

    def test_non_string_rule_name_raises(self):
        from tw_stock_tool.risk.models import RiskRuleEvaluation, RiskDecision, RiskModelError
        decision = RiskDecision.allow()
        with self.assertRaises(RiskModelError):
            RiskRuleEvaluation(rule_name=123, decision=decision) # type: ignore

    def test_non_decision_decision_raises(self):
        from tw_stock_tool.risk.models import RiskRuleEvaluation, RiskModelError
        with self.assertRaises(RiskModelError):
            RiskRuleEvaluation(rule_name="rule1", decision="allowed") # type: ignore

    def test_non_dict_metadata_raises(self):
        from tw_stock_tool.risk.models import RiskRuleEvaluation, RiskDecision, RiskModelError
        decision = RiskDecision.allow()
        with self.assertRaises(RiskModelError):
            RiskRuleEvaluation(rule_name="rule1", decision=decision, metadata="not a dict") # type: ignore

    def test_metadata_preserved(self):
        from tw_stock_tool.risk.models import RiskRuleEvaluation, RiskDecision
        decision = RiskDecision.allow()
        eval_item = RiskRuleEvaluation(rule_name="rule1", decision=decision, metadata={"key": "val"})
        self.assertEqual(eval_item.metadata, {"key": "val"})

    def test_public_import(self):
        from tw_stock_tool.risk import RiskRuleEvaluation as rre
        from tw_stock_tool.risk.models import RiskRuleEvaluation
        self.assertEqual(rre, RiskRuleEvaluation)

if __name__ == "__main__":
    unittest.main()
