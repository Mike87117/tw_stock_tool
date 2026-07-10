import unittest
from tw_stock_tool.paper_trading.models import SimulatedOrder, SimulatedPortfolio, SimulatedFill
from tw_stock_tool.risk.models import RiskDecision, RiskInputSnapshot
from tw_stock_tool.kill_switch.models import KillSwitchState, activate_kill_switch
from datetime import datetime
from tw_stock_tool.simulated_paper_trading_guard.models import SimulatedPaperTradingGuardDecision, SimulatedPaperTradingGuardError
from tw_stock_tool.simulated_paper_trading_guard import SimulatedPaperTradingGuardAdapter


class TestSimulatedPaperTradingGuardAdapter(unittest.TestCase):
    def setUp(self):
        self.order = SimulatedOrder(
            order_id="test-1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            signal_time="2023-01-01",
        )
        self.portfolio = SimulatedPortfolio(cash=100000.0)
        self.portfolio.apply_fill(SimulatedFill(
            order_id="setup-1",
            symbol="2330",
            side="BUY",
            quantity=500,
            price=100.0,
            filled_at="setup",
        ))
        # Portfolio now has 500 shares of 2330

        self.kill_switch_inactive = KillSwitchState()

        self.kill_switch_active = activate_kill_switch(KillSwitchState(), "System fault", datetime.now())

    def test_allowed_path(self):
        def price_prov(o, p): return 110.0
        def risk_prov(s): return RiskDecision.allow()

        adapter = SimulatedPaperTradingGuardAdapter(
            kill_switch_state=self.kill_switch_inactive,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov
        )

        decision = adapter(self.order, self.portfolio)
        self.assertIsInstance(decision, SimulatedPaperTradingGuardDecision)
        self.assertTrue(decision.is_allowed)
        self.assertFalse(decision.is_blocked)

    def test_risk_rejected_path(self):
        def price_prov(o, p): return 110.0
        def risk_prov(s): return RiskDecision.reject(["Position too large"])

        adapter = SimulatedPaperTradingGuardAdapter(
            kill_switch_state=self.kill_switch_inactive,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov
        )

        decision = adapter(self.order, self.portfolio)
        self.assertFalse(decision.is_allowed)
        self.assertTrue(decision.is_blocked)
        self.assertIn("Position too large", decision.reasons)

    def test_kill_switch_blocked_path(self):
        def price_prov(o, p): return 110.0
        def risk_prov(s): return RiskDecision.allow()

        adapter = SimulatedPaperTradingGuardAdapter(
            kill_switch_state=self.kill_switch_active,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov
        )

        decision = adapter(self.order, self.portfolio)
        self.assertFalse(decision.is_allowed)
        self.assertIn("System fault", decision.reasons)

    def test_both_blocked_path(self):
        def price_prov(o, p): return 110.0
        def risk_prov(s): return RiskDecision.reject(["Risk fail"])

        adapter = SimulatedPaperTradingGuardAdapter(
            kill_switch_state=self.kill_switch_active,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov
        )

        decision = adapter(self.order, self.portfolio)
        self.assertFalse(decision.is_allowed)
        self.assertIn("System fault", decision.reasons)
        self.assertIn("Risk fail", decision.reasons)

    def test_snapshot_construction(self):
        captured_snapshot = []
        def price_prov(o, p): return 105.0
        def risk_prov(s):
            captured_snapshot.append(s)
            return RiskDecision.allow()

        adapter = SimulatedPaperTradingGuardAdapter(
            kill_switch_state=self.kill_switch_inactive,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov
        )

        adapter(self.order, self.portfolio)

        self.assertEqual(len(captured_snapshot), 1)
        s = captured_snapshot[0]
        self.assertIsInstance(s, RiskInputSnapshot)
        self.assertEqual(s.symbol, "2330")
        self.assertEqual(s.side, "BUY")
        self.assertEqual(s.quantity, 1000)
        self.assertEqual(s.price, 105.0)
        self.assertEqual(s.cash, 50000.0) # 100k - (500*100)
        self.assertEqual(s.current_position_quantity, 500)
        self.assertEqual(s.current_position_notional, 52500.0) # 500 * 105
        self.assertEqual(s.total_exposure, 52500.0)
        self.assertEqual(s.current_open_positions, 1)

    def test_invalid_order_type(self):
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 100.0,
            lambda s: RiskDecision.allow()
        )
        with self.assertRaises(SimulatedPaperTradingGuardError):
            adapter("not an order", self.portfolio) # type: ignore

    def test_invalid_portfolio_type(self):
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 100.0,
            lambda s: RiskDecision.allow()
        )
        with self.assertRaises(SimulatedPaperTradingGuardError):
            adapter(self.order, "not a portfolio") # type: ignore

    def test_invalid_reference_price_provider(self):
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: -10.0, # invalid price
            lambda s: RiskDecision.allow()
        )
        with self.assertRaises(SimulatedPaperTradingGuardError):
            adapter(self.order, self.portfolio)

        adapter2 = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: "not a number", # invalid price
            lambda s: RiskDecision.allow()
        )
        with self.assertRaises(SimulatedPaperTradingGuardError):
            adapter2(self.order, self.portfolio)

    def test_invalid_risk_decision_provider(self):
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 100.0,
            lambda s: "not a decision" # type: ignore
        )
        with self.assertRaises(SimulatedPaperTradingGuardError):
            adapter(self.order, self.portfolio)

    def test_explicit_provider_valid_exposure(self):
        captured_snapshot = []
        def price_prov(o, p): return 105.0
        def risk_prov(s):
            captured_snapshot.append(s)
            return RiskDecision.allow()

        provider_calls = []
        def exp_prov(o, p):
            provider_calls.append((o, p))
            return 200000.0

        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            price_prov,
            risk_prov,
            portfolio_exposure_provider=exp_prov
        )

        adapter(self.order, self.portfolio)

        # Called exactly once
        self.assertEqual(len(provider_calls), 1)
        # Exact order and portfolio
        self.assertIs(provider_calls[0][0], self.order)
        self.assertIs(provider_calls[0][1], self.portfolio)

        self.assertEqual(len(captured_snapshot), 1)
        s = captured_snapshot[0]
        # Validates explicit exposure is used
        self.assertEqual(s.total_exposure, 200000.0)
        # Candidate notional is not added, still 200000.0
        # price and current pos notional still from ref price
        self.assertEqual(s.price, 105.0)
        self.assertEqual(s.current_position_notional, 52500.0)

    def test_explicit_provider_zero_exposure(self):
        captured_snapshot = []
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 105.0,
            lambda s: captured_snapshot.append(s) or RiskDecision.allow(),
            portfolio_exposure_provider=lambda o, p: 0
        )
        adapter(self.order, self.portfolio)
        self.assertEqual(captured_snapshot[0].total_exposure, 0.0)
        self.assertIsInstance(captured_snapshot[0].total_exposure, float)

    def test_explicit_provider_decimal_exposure(self):
        captured_snapshot = []
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 105.0,
            lambda s: captured_snapshot.append(s) or RiskDecision.allow(),
            portfolio_exposure_provider=lambda o, p: 12345.67
        )
        adapter(self.order, self.portfolio)
        self.assertEqual(captured_snapshot[0].total_exposure, 12345.67)

    def test_explicit_provider_sell_candidate_behavior(self):
        sell_order = SimulatedOrder(
            order_id="test-sell", symbol="2330", side="SELL", quantity=100, signal_time="2023-01-01"
        )
        captured_snapshot = []
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 105.0,
            lambda s: captured_snapshot.append(s) or RiskDecision.allow(),
            portfolio_exposure_provider=lambda o, p: 200000.0
        )
        adapter(sell_order, self.portfolio)
        # Should remain exactly 200000.0, no subtraction
        self.assertEqual(captured_snapshot[0].total_exposure, 200000.0)

    def test_constructor_validation_non_callable_provider(self):
        with self.assertRaises(SimulatedPaperTradingGuardError) as cm:
            SimulatedPaperTradingGuardAdapter(
                self.kill_switch_inactive,
                lambda o, p: 105.0,
                lambda s: RiskDecision.allow(),
                portfolio_exposure_provider="not a callable" # type: ignore
            )
        self.assertIn("callable or None", str(cm.exception))

    def test_runtime_validation_rejects_boolean(self):
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 105.0,
            lambda s: RiskDecision.allow(),
            portfolio_exposure_provider=lambda o, p: True # type: ignore
        )
        with self.assertRaises(SimulatedPaperTradingGuardError) as cm:
            adapter(self.order, self.portfolio)
        self.assertIn("boolean", str(cm.exception))

    def test_runtime_validation_rejects_string(self):
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 105.0,
            lambda s: RiskDecision.allow(),
            portfolio_exposure_provider=lambda o, p: "100" # type: ignore
        )
        with self.assertRaises(SimulatedPaperTradingGuardError) as cm:
            adapter(self.order, self.portfolio)
        self.assertIn("numeric", str(cm.exception))

    def test_runtime_validation_rejects_none(self):
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 105.0,
            lambda s: RiskDecision.allow(),
            portfolio_exposure_provider=lambda o, p: None # type: ignore
        )
        with self.assertRaises(SimulatedPaperTradingGuardError) as cm:
            adapter(self.order, self.portfolio)
        self.assertIn("numeric", str(cm.exception))

    def test_runtime_validation_rejects_nan(self):
        import math
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 105.0,
            lambda s: RiskDecision.allow(),
            portfolio_exposure_provider=lambda o, p: float("nan")
        )
        with self.assertRaises(SimulatedPaperTradingGuardError) as cm:
            adapter(self.order, self.portfolio)
        self.assertIn("finite", str(cm.exception))

    def test_runtime_validation_rejects_inf(self):
        import math
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 105.0,
            lambda s: RiskDecision.allow(),
            portfolio_exposure_provider=lambda o, p: float("inf")
        )
        with self.assertRaises(SimulatedPaperTradingGuardError) as cm:
            adapter(self.order, self.portfolio)
        self.assertIn("finite", str(cm.exception))

    def test_runtime_validation_rejects_neg_inf(self):
        import math
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 105.0,
            lambda s: RiskDecision.allow(),
            portfolio_exposure_provider=lambda o, p: float("-inf")
        )
        with self.assertRaises(SimulatedPaperTradingGuardError) as cm:
            adapter(self.order, self.portfolio)
        self.assertIn("finite", str(cm.exception))

    def test_runtime_validation_rejects_negative(self):
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 105.0,
            lambda s: RiskDecision.allow(),
            portfolio_exposure_provider=lambda o, p: -100.0
        )
        with self.assertRaises(SimulatedPaperTradingGuardError) as cm:
            adapter(self.order, self.portfolio)
        self.assertIn("non-negative", str(cm.exception))

    def test_invalid_order_fails_before_provider(self):
        calls = []
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 105.0,
            lambda s: RiskDecision.allow(),
            portfolio_exposure_provider=lambda o, p: calls.append(1) or 100.0
        )
        with self.assertRaises(SimulatedPaperTradingGuardError):
            adapter("not order", self.portfolio) # type: ignore
        self.assertEqual(len(calls), 0)

    def test_invalid_portfolio_fails_before_provider(self):
        calls = []
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 105.0,
            lambda s: RiskDecision.allow(),
            portfolio_exposure_provider=lambda o, p: calls.append(1) or 100.0
        )
        with self.assertRaises(SimulatedPaperTradingGuardError):
            adapter(self.order, "not portfolio") # type: ignore
        self.assertEqual(len(calls), 0)

    def test_provider_error_propagates_and_risk_not_called(self):
        risk_calls = []
        def exp_prov(o, p):
            raise SimulatedPaperTradingGuardError("provider custom error")

        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 105.0,
            lambda s: risk_calls.append(1) or RiskDecision.allow(),
            portfolio_exposure_provider=exp_prov
        )
        with self.assertRaises(SimulatedPaperTradingGuardError) as cm:
            adapter(self.order, self.portfolio)
        self.assertIn("provider custom error", str(cm.exception))
        self.assertEqual(len(risk_calls), 0)

    def test_three_positional_args_backward_compatibility(self):
        adapter = SimulatedPaperTradingGuardAdapter(
            self.kill_switch_inactive,
            lambda o, p: 105.0,
            lambda s: RiskDecision.allow()
        )
        decision = adapter(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

    def test_three_keyword_args_backward_compatibility(self):
        adapter = SimulatedPaperTradingGuardAdapter(
            kill_switch_state=self.kill_switch_inactive,
            reference_price_provider=lambda o, p: 105.0,
            risk_decision_provider=lambda s: RiskDecision.allow()
        )
        decision = adapter(self.order, self.portfolio)
        self.assertTrue(decision.is_allowed)

if __name__ == '__main__':
    unittest.main()
