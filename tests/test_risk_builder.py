import unittest
from tw_stock_tool.risk.builder import build_risk_decision_provider_from_config
from tw_stock_tool.risk.config import SimulatedPaperTradingRiskConfig, RiskConfigError
from tw_stock_tool.risk.models import RiskInputSnapshot, RiskDecision

class TestRiskBuilder(unittest.TestCase):
    def setUp(self):
        self.snapshot = RiskInputSnapshot(
            symbol="2330",
            side="BUY",
            quantity=10,
            price=100.0,
            cash=10000.0,
            current_position_quantity=5,
            current_position_notional=500.0,
            total_exposure=500.0,
            current_open_positions=1
        )

    def test_builder_accepts_none_config(self):
        provider = build_risk_decision_provider_from_config(None)
        decision = provider(self.snapshot)
        self.assertTrue(decision.allowed)

    def test_builder_accepts_empty_config(self):
        config = SimulatedPaperTradingRiskConfig()
        provider = build_risk_decision_provider_from_config(config)
        decision = provider(self.snapshot)
        self.assertTrue(decision.allowed)

    def test_invalid_builder_input_raises_error(self):
        with self.assertRaises(RiskConfigError):
            build_risk_decision_provider_from_config("not a config") # type: ignore

    def test_snapshot_not_mutated(self):
        config = SimulatedPaperTradingRiskConfig(max_order_notional=2000.0)
        provider = build_risk_decision_provider_from_config(config)
        _ = provider(self.snapshot)
        self.assertEqual(self.snapshot.symbol, "2330")
        self.assertEqual(self.snapshot.total_exposure, 500.0)

    def test_config_not_mutated(self):
        config = SimulatedPaperTradingRiskConfig(max_order_notional=2000.0)
        _ = build_risk_decision_provider_from_config(config)
        self.assertEqual(config.max_order_notional, 2000.0)

    def test_max_order_notional_allows(self):
        config = SimulatedPaperTradingRiskConfig(max_order_notional=2000.0)
        provider = build_risk_decision_provider_from_config(config)
        decision = provider(self.snapshot)
        self.assertTrue(decision.allowed)

    def test_max_order_notional_blocks(self):
        config = SimulatedPaperTradingRiskConfig(max_order_notional=500.0)
        provider = build_risk_decision_provider_from_config(config)
        decision = provider(self.snapshot)
        self.assertFalse(decision.allowed)
        self.assertTrue(any("notional" in r.lower() for r in decision.reasons))

    def test_max_position_quantity_allows(self):
        config = SimulatedPaperTradingRiskConfig(max_position_quantity=20)
        provider = build_risk_decision_provider_from_config(config)
        decision = provider(self.snapshot)
        self.assertTrue(decision.allowed)

    def test_max_position_quantity_blocks(self):
        config = SimulatedPaperTradingRiskConfig(max_position_quantity=10)
        provider = build_risk_decision_provider_from_config(config)
        decision = provider(self.snapshot)
        self.assertFalse(decision.allowed)
        self.assertTrue(any("quantity" in r.lower() for r in decision.reasons))

    def test_max_position_notional_allows(self):
        config = SimulatedPaperTradingRiskConfig(max_position_notional=2000.0)
        provider = build_risk_decision_provider_from_config(config)
        decision = provider(self.snapshot)
        self.assertTrue(decision.allowed)

    def test_max_position_notional_blocks(self):
        config = SimulatedPaperTradingRiskConfig(max_position_notional=1000.0)
        provider = build_risk_decision_provider_from_config(config)
        decision = provider(self.snapshot)
        self.assertFalse(decision.allowed)
        self.assertTrue(any("notional" in r.lower() for r in decision.reasons))

    def test_max_total_exposure_allows(self):
        # Current total exposure (500) + candidate notional (10*100=1000) = 1500
        config = SimulatedPaperTradingRiskConfig(max_total_exposure=2000.0)
        provider = build_risk_decision_provider_from_config(config)
        decision = provider(self.snapshot)
        self.assertTrue(decision.allowed)

    def test_max_total_exposure_blocks(self):
        config = SimulatedPaperTradingRiskConfig(max_total_exposure=1000.0)
        provider = build_risk_decision_provider_from_config(config)
        decision = provider(self.snapshot)
        self.assertFalse(decision.allowed)
        self.assertTrue(any("projected_total_exposure exceeds max_total_exposure" in r for r in decision.reasons))

    def test_max_total_exposure_sell_semantics(self):
        # SELL subtracts notional
        sell_snapshot = RiskInputSnapshot(
            symbol="2330",
            side="SELL",
            quantity=5,
            price=100.0,
            cash=10000.0,
            current_position_quantity=5,
            current_position_notional=500.0,
            total_exposure=500.0,
            current_open_positions=1
        )
        # Current exposure (500) - sell notional (500) = 0
        config = SimulatedPaperTradingRiskConfig(max_total_exposure=100.0)
        provider = build_risk_decision_provider_from_config(config)
        decision = provider(sell_snapshot)
        self.assertTrue(decision.allowed)

    def test_combined_config_aggregates_reasons(self):
        config = SimulatedPaperTradingRiskConfig(
            max_order_notional=500.0,
            max_position_quantity=10,
            max_position_notional=1000.0,
            max_total_exposure=1000.0
        )
        provider = build_risk_decision_provider_from_config(config)
        decision = provider(self.snapshot)
        self.assertFalse(decision.allowed)
        self.assertEqual(len(decision.reasons), 4)

        self.assertIn("exceeds max_order_notional", decision.reasons[0])
        self.assertIn("exceeds max_position_quantity", decision.reasons[1])
        self.assertIn("exceeds max_position_notional", decision.reasons[2])
        self.assertIn("exceeds max_total_exposure", decision.reasons[3])

if __name__ == "__main__":
    unittest.main()
