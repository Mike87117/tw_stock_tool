import unittest
from tw_stock_tool.risk.config import SimulatedPaperTradingRiskConfig
from tw_stock_tool.simulated_paper_trading_guard.config import SimulatedPaperTradingGuardConfig, GuardConfigError

class TestSimulatedPaperTradingGuardConfig(unittest.TestCase):
    def test_default_config_fields_none(self):
        cfg = SimulatedPaperTradingGuardConfig()
        self.assertIsNone(cfg.risk)
        self.assertIsNone(cfg.kill_switch_enabled)

    def test_valid_risk_config_accepted(self):
        risk_cfg = SimulatedPaperTradingRiskConfig(max_order_notional=100.0)
        cfg = SimulatedPaperTradingGuardConfig(risk=risk_cfg)
        self.assertIs(cfg.risk, risk_cfg)
        
    def test_valid_kill_switch_enabled_true_accepted(self):
        cfg = SimulatedPaperTradingGuardConfig(kill_switch_enabled=True)
        self.assertTrue(cfg.kill_switch_enabled)
        
    def test_valid_kill_switch_enabled_false_accepted(self):
        cfg = SimulatedPaperTradingGuardConfig(kill_switch_enabled=False)
        self.assertFalse(cfg.kill_switch_enabled)

    def test_invalid_risk_object_rejected(self):
        with self.assertRaisesRegex(GuardConfigError, "must be a SimulatedPaperTradingRiskConfig"):
            SimulatedPaperTradingGuardConfig(risk="not a risk config") # type: ignore

    def test_invalid_kill_switch_values_rejected_string(self):
        with self.assertRaisesRegex(GuardConfigError, "must be a boolean"):
            SimulatedPaperTradingGuardConfig(kill_switch_enabled="True") # type: ignore

    def test_invalid_kill_switch_values_rejected_integer(self):
        with self.assertRaisesRegex(GuardConfigError, "must be a boolean"):
            SimulatedPaperTradingGuardConfig(kill_switch_enabled=1) # type: ignore

    def test_invalid_kill_switch_values_rejected_float(self):
        with self.assertRaisesRegex(GuardConfigError, "must be a boolean"):
            SimulatedPaperTradingGuardConfig(kill_switch_enabled=1.0) # type: ignore

    def test_config_is_frozen(self):
        cfg = SimulatedPaperTradingGuardConfig()
        with self.assertRaises(Exception):
            cfg.kill_switch_enabled = True # type: ignore

    def test_no_builder_exposed(self):
        import tw_stock_tool.simulated_paper_trading_guard.config as guard_config
        self.assertFalse(hasattr(guard_config, "build_decision_provider"))
        self.assertFalse(hasattr(guard_config, "build_guard_decision_provider"))
        self.assertFalse(hasattr(guard_config, "from_json"))
        self.assertFalse(hasattr(guard_config, "from_file"))
        self.assertFalse(hasattr(guard_config, "from_cli_args"))
        self.assertFalse(hasattr(guard_config, "load_config"))
        self.assertFalse(hasattr(guard_config, "parse_config"))

if __name__ == "__main__":
    unittest.main()
