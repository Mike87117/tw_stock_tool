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

    def test_total_exposure_without_reference_provider_raises_error(self):
        risk_config = SimulatedPaperTradingRiskConfig(max_total_exposure=2000.0)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        with self.assertRaisesRegex(GuardConfigError, "reference_price_provider is required"):
            build_guard_decision_provider_from_config(config)

    def test_total_exposure_without_portfolio_provider_raises_error(self):
        risk_config = SimulatedPaperTradingRiskConfig(max_total_exposure=2000.0)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        with self.assertRaisesRegex(GuardConfigError, "portfolio_exposure_provider is required"):
            build_guard_decision_provider_from_config(config, reference_price_provider=self.price_provider)

    def test_total_exposure_with_both_providers_builds_and_allows(self):
        risk_config = SimulatedPaperTradingRiskConfig(max_total_exposure=2000.0)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        provider = build_guard_decision_provider_from_config(
            config,
            reference_price_provider=self.price_provider,
            portfolio_exposure_provider=lambda o, p: 500.0
        )
        decision = provider(self.order, self.portfolio) # 500 + 1000 = 1500 <= 2000
        self.assertTrue(decision.is_allowed)

    def test_total_exposure_with_both_providers_blocks(self):
        risk_config = SimulatedPaperTradingRiskConfig(max_total_exposure=2000.0)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        provider = build_guard_decision_provider_from_config(
            config,
            reference_price_provider=self.price_provider,
            portfolio_exposure_provider=lambda o, p: 1500.0
        )
        decision = provider(self.order, self.portfolio) # 1500 + 1000 = 2500 > 2000
        self.assertFalse(decision.is_allowed)
        self.assertTrue(any("max_total_exposure" in r for r in decision.reasons))

    def test_portfolio_provider_receives_exact_arguments_and_called_once(self):
        calls = []
        def track_calls(o, p):
            calls.append((o, p))
            return 500.0

        risk_config = SimulatedPaperTradingRiskConfig(max_total_exposure=2000.0)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        provider = build_guard_decision_provider_from_config(
            config,
            reference_price_provider=self.price_provider,
            portfolio_exposure_provider=track_calls
        )
        provider(self.order, self.portfolio)
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][0], self.order)
        self.assertIs(calls[0][1], self.portfolio)

    def test_total_exposure_zero_provider_remains_valid(self):
        risk_config = SimulatedPaperTradingRiskConfig(max_total_exposure=2000.0)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        provider = build_guard_decision_provider_from_config(
            config,
            reference_price_provider=self.price_provider,
            portfolio_exposure_provider=lambda o, p: 0.0
        )
        decision = provider(self.order, self.portfolio) # 0 + 1000 = 1000
        self.assertTrue(decision.is_allowed)

    def test_total_exposure_provider_runtime_error_propagates(self):
        def error_provider(o, p):
            raise RuntimeError("Provider failed")
        risk_config = SimulatedPaperTradingRiskConfig(max_total_exposure=2000.0)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        provider = build_guard_decision_provider_from_config(
            config,
            reference_price_provider=self.price_provider,
            portfolio_exposure_provider=error_provider
        )
        with self.assertRaisesRegex(RuntimeError, "Provider failed"):
            provider(self.order, self.portfolio)

    def test_critical_anti_fallback_integration(self):
        # Order is BUY 10 @ 100 = 1000 notional.
        # Single symbol fallback would see 5 * 90 (avg cost)? Actually fallback gets current_position_notional from somewhere else, wait: it uses average_cost maybe? Wait, adapter uses `portfolio.positions.get(symbol).quantity * reference_price` if no portfolio provider.
        # Legacy fallback is: 5 * 100 = 500. 500 + 1000 = 1500.
        # Real provider returns 2000. 2000 + 1000 = 3000.
        # 3000 > 2500 -> must reject. Proves real provider was used.
        risk_config = SimulatedPaperTradingRiskConfig(max_total_exposure=2500.0)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        provider = build_guard_decision_provider_from_config(
            config,
            reference_price_provider=self.price_provider,
            portfolio_exposure_provider=lambda o, p: 2000.0
        )
        decision = provider(self.order, self.portfolio)
        self.assertFalse(decision.is_allowed)
        self.assertTrue(any("max_total_exposure" in r for r in decision.reasons))

    def test_empty_config_with_failing_portfolio_provider_allows(self):
        def failing_provider(o, p):
            raise ValueError("Should not be called")
        config = SimulatedPaperTradingGuardConfig()
        provider = build_guard_decision_provider_from_config(
            config,
            reference_price_provider=self.price_provider,
            portfolio_exposure_provider=failing_provider
        )
        decision = provider(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

    def test_risk_none_with_failing_portfolio_provider_allows(self):
        def failing_provider(o, p):
            raise ValueError("Should not be called")
        config = SimulatedPaperTradingGuardConfig(risk=None)
        provider = build_guard_decision_provider_from_config(
            config,
            reference_price_provider=self.price_provider,
            portfolio_exposure_provider=failing_provider
        )
        decision = provider(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

    def test_max_order_notional_with_failing_portfolio_provider_allows(self):
        def failing_provider(o, p):
            raise ValueError("Should not be called")
        risk_config = SimulatedPaperTradingRiskConfig(max_order_notional=2000.0)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        provider = build_guard_decision_provider_from_config(
            config,
            reference_price_provider=self.price_provider,
            portfolio_exposure_provider=failing_provider
        )
        decision = provider(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

    def test_max_position_quantity_with_failing_portfolio_provider_allows(self):
        def failing_provider(o, p):
            raise ValueError("Should not be called")
        risk_config = SimulatedPaperTradingRiskConfig(max_position_quantity=20)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        provider = build_guard_decision_provider_from_config(
            config,
            reference_price_provider=self.price_provider,
            portfolio_exposure_provider=failing_provider
        )
        decision = provider(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

    def test_max_position_notional_with_failing_portfolio_provider_allows(self):
        def failing_provider(o, p):
            raise ValueError("Should not be called")
        risk_config = SimulatedPaperTradingRiskConfig(max_position_notional=2000.0)
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        provider = build_guard_decision_provider_from_config(
            config,
            reference_price_provider=self.price_provider,
            portfolio_exposure_provider=failing_provider
        )
        decision = provider(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

    def test_combined_first_three_risk_config_with_failing_portfolio_provider_allows(self):
        def failing_provider(o, p):
            raise ValueError("Should not be called")
        risk_config = SimulatedPaperTradingRiskConfig(
            max_order_notional=2000.0,
            max_position_quantity=20,
            max_position_notional=2000.0
        )
        config = SimulatedPaperTradingGuardConfig(risk=risk_config)
        provider = build_guard_decision_provider_from_config(
            config,
            reference_price_provider=self.price_provider,
            portfolio_exposure_provider=failing_provider
        )
        decision = provider(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

if __name__ == "__main__":
    unittest.main()
