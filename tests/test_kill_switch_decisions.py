import unittest
from datetime import datetime

from tw_stock_tool.kill_switch.models import KillSwitchState, KillSwitchModelError
from tw_stock_tool.kill_switch.decisions import KillSwitchDecision, evaluate_kill_switch

class TestKillSwitchDecisions(unittest.TestCase):
    def test_inactive_state_evaluates_to_allowed(self):
        state = KillSwitchState()
        decision = evaluate_kill_switch(state)
        self.assertTrue(decision.is_allowed)
        
    def test_allowed_decision_has_no_reason(self):
        decision = KillSwitchDecision(is_allowed=True)
        self.assertIsNone(decision.reason)
        
    def test_active_state_evaluates_to_blocked(self):
        dt = datetime.now()
        state = KillSwitchState(is_active=True, reason="Manual intervention", activated_at=dt)
        decision = evaluate_kill_switch(state)
        self.assertFalse(decision.is_allowed)
        
    def test_blocked_decision_carries_active_reason(self):
        dt = datetime.now()
        state = KillSwitchState(is_active=True, reason="Manual intervention", activated_at=dt)
        decision = evaluate_kill_switch(state)
        self.assertEqual(decision.reason, "Manual intervention")
        
    def test_allowed_decision_with_reason_raises(self):
        with self.assertRaises(KillSwitchModelError):
            KillSwitchDecision(is_allowed=True, reason="Should fail")
            
    def test_blocked_decision_with_no_reason_raises(self):
        with self.assertRaises(KillSwitchModelError):
            KillSwitchDecision(is_allowed=False, reason=None)
            
    def test_blocked_decision_with_blank_reason_raises(self):
        with self.assertRaises(KillSwitchModelError):
            KillSwitchDecision(is_allowed=False, reason="")
            
    def test_blocked_decision_with_whitespace_reason_raises(self):
        with self.assertRaises(KillSwitchModelError):
            KillSwitchDecision(is_allowed=False, reason="   ")
            
    def test_non_bool_is_allowed_raises(self):
        with self.assertRaises(KillSwitchModelError):
            KillSwitchDecision(is_allowed="True") # type: ignore
            
    def test_is_blocked_returns_false_for_allowed(self):
        decision = KillSwitchDecision(is_allowed=True)
        self.assertFalse(decision.is_blocked)
        
    def test_is_blocked_returns_true_for_blocked(self):
        decision = KillSwitchDecision(is_allowed=False, reason="Test")
        self.assertTrue(decision.is_blocked)
        
    def test_evaluate_kill_switch_does_not_mutate(self):
        state = KillSwitchState()
        evaluate_kill_switch(state)
        self.assertFalse(state.is_active)
        
    def test_evaluate_kill_switch_rejects_non_state(self):
        with self.assertRaises(KillSwitchModelError):
            evaluate_kill_switch("not a state") # type: ignore
            
    def test_public_import_works(self):
        from tw_stock_tool.kill_switch import KillSwitchDecision as KSD
        from tw_stock_tool.kill_switch import evaluate_kill_switch as eks
        
        self.assertEqual(KSD, KillSwitchDecision)
        self.assertEqual(eks, evaluate_kill_switch)

if __name__ == '__main__':
    unittest.main()
