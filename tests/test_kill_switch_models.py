import unittest
from datetime import datetime

from tw_stock_tool.kill_switch.models import KillSwitchState, KillSwitchModelError, activate_kill_switch, release_kill_switch

class TestKillSwitchModels(unittest.TestCase):
    def test_default_state_is_inactive(self):
        state = KillSwitchState()
        self.assertFalse(state.is_active)
        
    def test_inactive_state_has_no_reason(self):
        state = KillSwitchState()
        self.assertIsNone(state.reason)
        
    def test_inactive_state_has_no_activated_at(self):
        state = KillSwitchState()
        self.assertIsNone(state.activated_at)
        
    def test_active_state_valid(self):
        dt = datetime.now()
        state = KillSwitchState(is_active=True, reason="Manual intervention", activated_at=dt)
        self.assertTrue(state.is_active)
        self.assertEqual(state.reason, "Manual intervention")
        self.assertEqual(state.activated_at, dt)
        
    def test_active_state_exposes_is_active(self):
        dt = datetime.now()
        state = KillSwitchState(is_active=True, reason="Manual intervention", activated_at=dt)
        self.assertTrue(state.is_active)
        
    def test_inactive_state_exposes_is_inactive(self):
        state = KillSwitchState()
        self.assertTrue(state.is_inactive)
        
    def test_active_state_blank_reason_raises(self):
        dt = datetime.now()
        with self.assertRaises(KillSwitchModelError):
            KillSwitchState(is_active=True, reason="", activated_at=dt)
            
    def test_active_state_whitespace_reason_raises(self):
        dt = datetime.now()
        with self.assertRaises(KillSwitchModelError):
            KillSwitchState(is_active=True, reason="   ", activated_at=dt)
            
    def test_active_state_missing_reason_raises(self):
        dt = datetime.now()
        with self.assertRaises(KillSwitchModelError):
            KillSwitchState(is_active=True, activated_at=dt)
            
    def test_active_state_missing_activated_at_raises(self):
        with self.assertRaises(KillSwitchModelError):
            KillSwitchState(is_active=True, reason="Testing")
            
    def test_active_state_string_timestamp_raises(self):
        with self.assertRaises(KillSwitchModelError):
            KillSwitchState(is_active=True, reason="Testing", activated_at="2023-01-01T00:00:00") # type: ignore
            
    def test_active_state_numeric_timestamp_raises(self):
        with self.assertRaises(KillSwitchModelError):
            KillSwitchState(is_active=True, reason="Testing", activated_at=1672531200) # type: ignore
            
    def test_active_state_bool_timestamp_raises(self):
        with self.assertRaises(KillSwitchModelError):
            KillSwitchState(is_active=True, reason="Testing", activated_at=True) # type: ignore
            
    def test_inactive_state_with_reason_raises(self):
        with self.assertRaises(KillSwitchModelError):
            KillSwitchState(reason="Should fail")
            
    def test_inactive_state_with_activated_at_raises(self):
        dt = datetime.now()
        with self.assertRaises(KillSwitchModelError):
            KillSwitchState(activated_at=dt)
            
    def test_non_bool_is_active_raises(self):
        with self.assertRaises(KillSwitchModelError):
            KillSwitchState(is_active="True") # type: ignore
            
    def test_activate_kill_switch_returns_active(self):
        state = KillSwitchState()
        dt = datetime.now()
        new_state = activate_kill_switch(state, "Emergency stop", dt)
        self.assertTrue(new_state.is_active)
        self.assertEqual(new_state.reason, "Emergency stop")
        self.assertEqual(new_state.activated_at, dt)
        
    def test_activate_kill_switch_does_not_mutate(self):
        state = KillSwitchState()
        dt = datetime.now()
        activate_kill_switch(state, "Emergency stop", dt)
        self.assertFalse(state.is_active)
        
    def test_activate_kill_switch_rejects_non_state(self):
        dt = datetime.now()
        with self.assertRaises(KillSwitchModelError):
            activate_kill_switch("not a state", "Emergency stop", dt) # type: ignore
            
    def test_release_kill_switch_returns_inactive(self):
        dt = datetime.now()
        state = KillSwitchState(is_active=True, reason="Emergency stop", activated_at=dt)
        new_state = release_kill_switch(state)
        self.assertFalse(new_state.is_active)
        self.assertIsNone(new_state.reason)
        self.assertIsNone(new_state.activated_at)
        
    def test_release_kill_switch_clears_reason_and_timestamp(self):
        dt = datetime.now()
        state = KillSwitchState(is_active=True, reason="Emergency stop", activated_at=dt)
        new_state = release_kill_switch(state)
        self.assertIsNone(new_state.reason)
        self.assertIsNone(new_state.activated_at)
        
    def test_release_kill_switch_does_not_mutate(self):
        dt = datetime.now()
        state = KillSwitchState(is_active=True, reason="Emergency stop", activated_at=dt)
        release_kill_switch(state)
        self.assertTrue(state.is_active)
        self.assertEqual(state.reason, "Emergency stop")
        
    def test_release_kill_switch_rejects_non_state(self):
        with self.assertRaises(KillSwitchModelError):
            release_kill_switch("not a state") # type: ignore
            
    def test_public_import_works(self):
        from tw_stock_tool.kill_switch import KillSwitchState as KSS
        from tw_stock_tool.kill_switch import KillSwitchModelError as KSME
        from tw_stock_tool.kill_switch import activate_kill_switch as aks
        from tw_stock_tool.kill_switch import release_kill_switch as rks
        
        self.assertEqual(KSS, KillSwitchState)
        self.assertEqual(KSME, KillSwitchModelError)
        self.assertEqual(aks, activate_kill_switch)
        self.assertEqual(rks, release_kill_switch)

if __name__ == '__main__':
    unittest.main()
