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

if __name__ == '__main__':
    unittest.main()
