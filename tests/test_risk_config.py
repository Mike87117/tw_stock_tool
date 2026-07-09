import unittest
import math
from tw_stock_tool.risk.config import SimulatedPaperTradingRiskConfig, RiskConfigError

class TestSimulatedPaperTradingRiskConfig(unittest.TestCase):
    def test_default_config_fields_none(self):
        cfg = SimulatedPaperTradingRiskConfig()
        self.assertIsNone(cfg.max_order_notional)
        self.assertIsNone(cfg.max_position_quantity)
        self.assertIsNone(cfg.max_position_notional)

    def test_valid_positive_values_accepted(self):
        cfg = SimulatedPaperTradingRiskConfig(
            max_order_notional=100.5,
            max_position_quantity=10,
            max_position_notional=2000.0
        )
        self.assertEqual(cfg.max_order_notional, 100.5)
        self.assertEqual(cfg.max_position_quantity, 10)
        self.assertEqual(cfg.max_position_notional, 2000.0)

    def test_config_is_frozen(self):
        cfg = SimulatedPaperTradingRiskConfig()
        with self.assertRaises(Exception):
            cfg.max_order_notional = 10 # type: ignore

    def test_max_order_notional_rejects_zero_and_negative(self):
        with self.assertRaisesRegex(RiskConfigError, "strictly positive"):
            SimulatedPaperTradingRiskConfig(max_order_notional=0)
        with self.assertRaisesRegex(RiskConfigError, "strictly positive"):
            SimulatedPaperTradingRiskConfig(max_order_notional=-10.5)

    def test_max_order_notional_rejects_infinity(self):
        with self.assertRaisesRegex(RiskConfigError, "finite"):
            SimulatedPaperTradingRiskConfig(max_order_notional=float("inf"))

    def test_max_order_notional_rejects_nan(self):
        with self.assertRaisesRegex(RiskConfigError, "finite"):
            SimulatedPaperTradingRiskConfig(max_order_notional=float("nan"))

    def test_max_order_notional_rejects_bool(self):
        with self.assertRaisesRegex(RiskConfigError, "cannot be a boolean"):
            SimulatedPaperTradingRiskConfig(max_order_notional=True)

    def test_max_order_notional_rejects_numeric_string(self):
        with self.assertRaisesRegex(RiskConfigError, "must be numeric"):
            SimulatedPaperTradingRiskConfig(max_order_notional="100") # type: ignore

    def test_max_position_notional_rejects_zero_and_negative(self):
        with self.assertRaisesRegex(RiskConfigError, "strictly positive"):
            SimulatedPaperTradingRiskConfig(max_position_notional=0)
        with self.assertRaisesRegex(RiskConfigError, "strictly positive"):
            SimulatedPaperTradingRiskConfig(max_position_notional=-10.5)

    def test_max_position_notional_rejects_infinity(self):
        with self.assertRaisesRegex(RiskConfigError, "finite"):
            SimulatedPaperTradingRiskConfig(max_position_notional=float("inf"))

    def test_max_position_notional_rejects_nan(self):
        with self.assertRaisesRegex(RiskConfigError, "finite"):
            SimulatedPaperTradingRiskConfig(max_position_notional=float("nan"))

    def test_max_position_notional_rejects_bool(self):
        with self.assertRaisesRegex(RiskConfigError, "cannot be a boolean"):
            SimulatedPaperTradingRiskConfig(max_position_notional=True)

    def test_max_position_notional_rejects_numeric_string(self):
        with self.assertRaisesRegex(RiskConfigError, "must be numeric"):
            SimulatedPaperTradingRiskConfig(max_position_notional="100") # type: ignore

    def test_max_position_quantity_rejects_zero_and_negative(self):
        with self.assertRaisesRegex(RiskConfigError, "strictly positive"):
            SimulatedPaperTradingRiskConfig(max_position_quantity=0)
        with self.assertRaisesRegex(RiskConfigError, "strictly positive"):
            SimulatedPaperTradingRiskConfig(max_position_quantity=-10)

    def test_max_position_quantity_rejects_infinity(self):
        with self.assertRaisesRegex(RiskConfigError, "finite"):
            SimulatedPaperTradingRiskConfig(max_position_quantity=float("inf"))

    def test_max_position_quantity_rejects_nan(self):
        with self.assertRaisesRegex(RiskConfigError, "finite"):
            SimulatedPaperTradingRiskConfig(max_position_quantity=float("nan"))

    def test_max_position_quantity_rejects_bool(self):
        with self.assertRaisesRegex(RiskConfigError, "cannot be a boolean"):
            SimulatedPaperTradingRiskConfig(max_position_quantity=True)

    def test_max_position_quantity_rejects_numeric_string(self):
        with self.assertRaisesRegex(RiskConfigError, "must be numeric"):
            SimulatedPaperTradingRiskConfig(max_position_quantity="100") # type: ignore

    def test_max_position_quantity_rejects_fractional(self):
        with self.assertRaisesRegex(RiskConfigError, "integer"):
            SimulatedPaperTradingRiskConfig(max_position_quantity=10.5) # type: ignore

    def test_no_builder_exposed(self):
        import tw_stock_tool.risk.config as risk_config
        self.assertFalse(hasattr(risk_config, "build_decision_provider"))
        self.assertFalse(hasattr(risk_config, "build_guard_decision_provider"))
        self.assertFalse(hasattr(risk_config, "from_json"))
        self.assertFalse(hasattr(risk_config, "from_file"))
        self.assertFalse(hasattr(risk_config, "from_cli_args"))
        self.assertFalse(hasattr(risk_config, "load_config"))
        self.assertFalse(hasattr(risk_config, "parse_config"))

if __name__ == "__main__":
    unittest.main()
