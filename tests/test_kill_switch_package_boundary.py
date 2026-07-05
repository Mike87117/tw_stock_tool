import unittest

import tw_stock_tool.kill_switch
from tw_stock_tool.kill_switch.models import (
    KillSwitchState as ModelsKillSwitchState,
    KillSwitchModelError as ModelsKillSwitchModelError,
    activate_kill_switch as models_activate_kill_switch,
    release_kill_switch as models_release_kill_switch,
)
from tw_stock_tool.kill_switch.decisions import (
    KillSwitchDecision as DecisionsKillSwitchDecision,
    evaluate_kill_switch as decisions_evaluate_kill_switch,
)


class TestKillSwitchPackageBoundary(unittest.TestCase):
    def test_all_exports_match_expected(self):
        expected_exports = [
            "KillSwitchState",
            "KillSwitchModelError",
            "activate_kill_switch",
            "release_kill_switch",
            "KillSwitchDecision",
            "evaluate_kill_switch",
        ]
        self.assertCountEqual(tw_stock_tool.kill_switch.__all__, expected_exports)

    def test_kill_switch_state_export(self):
        self.assertIs(
            tw_stock_tool.kill_switch.KillSwitchState,
            ModelsKillSwitchState
        )

    def test_kill_switch_model_error_export(self):
        self.assertIs(
            tw_stock_tool.kill_switch.KillSwitchModelError,
            ModelsKillSwitchModelError
        )

    def test_activate_kill_switch_export(self):
        self.assertIs(
            tw_stock_tool.kill_switch.activate_kill_switch,
            models_activate_kill_switch
        )

    def test_release_kill_switch_export(self):
        self.assertIs(
            tw_stock_tool.kill_switch.release_kill_switch,
            models_release_kill_switch
        )

    def test_kill_switch_decision_export(self):
        self.assertIs(
            tw_stock_tool.kill_switch.KillSwitchDecision,
            DecisionsKillSwitchDecision
        )

    def test_evaluate_kill_switch_export(self):
        self.assertIs(
            tw_stock_tool.kill_switch.evaluate_kill_switch,
            decisions_evaluate_kill_switch
        )

if __name__ == '__main__':
    unittest.main()
