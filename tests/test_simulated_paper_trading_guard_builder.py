import unittest
from tw_stock_tool.simulated_paper_trading_guard.builder import build_guard_decision_provider_from_config
from tw_stock_tool.simulated_paper_trading_guard.config import SimulatedPaperTradingGuardConfig, GuardConfigError
from tw_stock_tool.risk.config import SimulatedPaperTradingRiskConfig
from tw_stock_tool.paper_trading.models import SimulatedOrder, SimulatedPortfolio, SimulatedPosition
from datetime import datetime

class TestGuardBuilder(unittest.TestCase):
    def setUp(self):
        self.order = SimulatedOrder(
            symbol="2330",
            side="BUY",
            quantity=10,
            signal_time=datetime(2023, 1, 1),
            order_id="test_order"
        )
        self.portfolio = SimulatedPortfolio(
            cash=10000.0,
            positions={"2330": SimulatedPosition(symbol="2330", quantity=5, average_cost=90.0)}
        )
        self.price_provider = lambda o, p: 100.0

    def test_builder_accepts_none_config(self):
        provider = build_guard_decision_provider_from_config(None)
        decision = provider(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

    def test_builder_accepts_empty_config(self):
        config = SimulatedPaperTradingGuardConfig()
        provider = build_guard_decision_provider_from_config(config)
        decision = provider(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

    def test_builder_accepts_explicit_none_fields(self):
        config = SimulatedPaperTradingGuardConfig(risk=None, kill_switch_enabled=None)
        provider = build_guard_decision_provider_from_config(config)
        decision = provider(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

    def test_builder_accepts_kill_switch_false(self):
        config = SimulatedPaperTradingGuardConfig(kill_switch_enabled=False)
        provider = build_guard_decision_provider_from_config(config)
        decision = provider(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

    def test_empty_config_with_provider_allows(self):
        config = SimulatedPaperTradingGuardConfig()
        provider = build_guard_decision_provider_from_config(config, reference_price_provider=self.price_provider)
        decision = provider(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

    def test_empty_config_with_failing_provider_allows(self):
        def failing_provider(o, p):
            raise ValueError("Provider should not be called!")
        config = SimulatedPaperTradingGuardConfig()
        provider = build_guard_decision_provider_from_config(config, reference_price_provider=failing_provider)
        # Should allow and NOT call the provider
        decision = provider(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

    def test_risk_none_with_failing_provider_allows(self):
        def failing_provider(o, p):
            raise ValueError("Provider should not be called!")
        config = SimulatedPaperTradingGuardConfig(risk=None, kill_switch_enabled=False)
        provider = build_guard_decision_provider_from_config(config, reference_price_provider=failing_provider)
        # Should allow and NOT call the provider
        decision = provider(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

    def test_kill_switch_true_raises_error(self):
        config = SimulatedPaperTradingGuardConfig(kill_switch_enabled=True)
        with self.assertRaises(GuardConfigError):
            build_guard_decision_provider_from_config(config)

    def test_invalid_builder_input_raises_error(self):
        with self.assertRaises(GuardConfigError):
            build_guard_decision_provider_from_config("not a config") # type: ignore

    def test_config_not_mutated(self):
        risk_config = SimulatedPaperTradingRiskConfig(max_order_notional=2000.0)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        _ = build_guard_decision_provider_from_config(config, reference_price_provider=self.price_provider)
        self.assertEqual(config.risk.max_order_notional, 2000.0)

    def test_non_empty_risk_config_without_provider_raises_error(self):
        risk_config = SimulatedPaperTradingRiskConfig(max_order_notional=2000.0)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        with self.assertRaises(GuardConfigError):
            build_guard_decision_provider_from_config(config)

    def test_risk_only_config_allows_under_limit(self):
        # order is 10 * 100 = 1000 notional
        risk_config = SimulatedPaperTradingRiskConfig(max_order_notional=2000.0)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        provider = build_guard_decision_provider_from_config(config, reference_price_provider=self.price_provider)
        decision = provider(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

    def test_risk_only_config_blocks_over_max_order_notional(self):
        # order is 10 * 100 = 1000 notional
        risk_config = SimulatedPaperTradingRiskConfig(max_order_notional=500.0)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        provider = build_guard_decision_provider_from_config(config, reference_price_provider=self.price_provider)
        decision = provider(self.order, self.portfolio)
        self.assertFalse(decision.is_allowed)
        self.assertTrue(any("notional" in r.lower() for r in decision.reasons))

    def test_risk_only_config_blocks_over_max_position_quantity(self):
        # projected is 5 + 10 = 15
        risk_config = SimulatedPaperTradingRiskConfig(max_position_quantity=10)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        provider = build_guard_decision_provider_from_config(config, reference_price_provider=self.price_provider)
        decision = provider(self.order, self.portfolio)
        self.assertFalse(decision.is_allowed)
        self.assertTrue(any("quantity" in r.lower() for r in decision.reasons))

    def test_risk_only_config_blocks_over_max_position_notional(self):
        # projected is 15 * 100 = 1500
        risk_config = SimulatedPaperTradingRiskConfig(max_position_notional=1000.0)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        provider = build_guard_decision_provider_from_config(config, reference_price_provider=self.price_provider)
        decision = provider(self.order, self.portfolio)
        self.assertFalse(decision.is_allowed)
        self.assertTrue(any("notional" in r.lower() for r in decision.reasons))

    def test_combined_risk_failures_aggregate_reasons(self):
        risk_config = SimulatedPaperTradingRiskConfig(
            max_order_notional=500.0,
            max_position_quantity=10,
            max_position_notional=1000.0
        )
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        provider = build_guard_decision_provider_from_config(config, reference_price_provider=self.price_provider)
        decision = provider(self.order, self.portfolio)
        self.assertFalse(decision.is_allowed)
        self.assertEqual(len(decision.reasons), 3)

if __name__ == "__main__":
    unittest.main()
