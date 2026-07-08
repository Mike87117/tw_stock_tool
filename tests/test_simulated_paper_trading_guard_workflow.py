import unittest
import pandas as pd
from tw_stock_tool.simulated_paper_trading_guard.workflow import run_simulated_paper_trading_with_guard
from tw_stock_tool.simulated_paper_trading_guard.models import SimulatedPaperTradingGuardError
from tw_stock_tool.paper_trading.models import SimulatedPortfolio
from tw_stock_tool.kill_switch.models import KillSwitchState, activate_kill_switch
from tw_stock_tool.risk.models import RiskDecision
from datetime import datetime

class TestSimulatedPaperTradingGuardWorkflow(unittest.TestCase):
    def setUp(self):
        data = {
            "Date": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04"],
            "Open": [100.0, 102.0, 105.0, 106.0],
            "High": [105.0, 106.0, 110.0, 110.0],
            "Low": [95.0, 101.0, 104.0, 105.0],
            "Close": [102.0, 105.0, 108.0, 109.0],
            "Volume": [1000, 1500, 2000, 1000],
            "entry_signal": [True, False, False, False],
            "exit_signal": [False, False, True, False],
        }
        self.df = pd.DataFrame(data)
        self.df["Date"] = pd.to_datetime(self.df["Date"])
        self.symbol = "2330"
        self.initial_cash = 200000.0
        self.qty = 1000
        
        self.inactive_kill_switch = KillSwitchState()
        self.active_kill_switch = activate_kill_switch(KillSwitchState(), "System fault", datetime.now())

    def test_allowed_path(self):
        # Inactive KillSwitch, RiskDecision allows, explicit price provider
        def price_prov(order, portfolio): return 100.0
        def risk_prov(snapshot): return RiskDecision.allow()

        portfolio = run_simulated_paper_trading_with_guard(
            df=self.df,
            symbol=self.symbol,
            initial_cash=self.initial_cash,
            quantity_per_trade=self.qty,
            kill_switch_state=self.inactive_kill_switch,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov
        )
        
        self.assertIsInstance(portfolio, SimulatedPortfolio)
        # 1 buy, 1 sell expected based on the signal
        self.assertEqual(len(portfolio.trade_log.fills), 2)
        self.assertEqual(portfolio.trade_log.fills[0].side, "BUY")
        self.assertEqual(portfolio.trade_log.fills[1].side, "SELL")

    def test_risk_blocked_path(self):
        # RiskDecision rejects
        def price_prov(order, portfolio): return 100.0
        def risk_prov(snapshot): return RiskDecision.reject(["Position too large"])

        portfolio = run_simulated_paper_trading_with_guard(
            df=self.df,
            symbol=self.symbol,
            initial_cash=self.initial_cash,
            quantity_per_trade=self.qty,
            kill_switch_state=self.inactive_kill_switch,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov
        )
        
        # Signals existed, but guard blocked the order intent, so no orders/fills
        self.assertEqual(len(portfolio.trade_log.orders), 0)
        self.assertEqual(len(portfolio.trade_log.fills), 0)
        self.assertEqual(portfolio.cash, self.initial_cash)

    def test_kill_switch_blocked_path(self):
        # Active KillSwitch
        def price_prov(order, portfolio): return 100.0
        def risk_prov(snapshot): return RiskDecision.allow()

        portfolio = run_simulated_paper_trading_with_guard(
            df=self.df,
            symbol=self.symbol,
            initial_cash=self.initial_cash,
            quantity_per_trade=self.qty,
            kill_switch_state=self.active_kill_switch,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov
        )
        
        # Guard blocked, so no orders/fills
        self.assertEqual(len(portfolio.trade_log.orders), 0)
        self.assertEqual(len(portfolio.trade_log.fills), 0)
        self.assertEqual(portfolio.cash, self.initial_cash)

    def test_parameter_passthrough(self):
        def price_prov(order, portfolio): return 100.0
        def risk_prov(snapshot): return RiskDecision.allow()
        
        portfolio = run_simulated_paper_trading_with_guard(
            df=self.df,
            symbol=self.symbol,
            initial_cash=self.initial_cash,
            quantity_per_trade=self.qty,
            kill_switch_state=self.inactive_kill_switch,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov,
            fee_rate=0.001,
            tax_rate=0.003,
            slippage_per_share=0.5
        )
        
        # Fills should reflect the parameters
        self.assertEqual(len(portfolio.trade_log.fills), 2)
        # Initial cash: 200000.0
        # Buy 1000 at 102 (Open of 2023-01-02).
        # Cost = 102000 + fee (102) + slippage (500) = 102602.0
        # Remaining cash = 97398.0
        # Sell 1000 at 106 (Open of 2023-01-04).
        # Revenue = 106000 - fee (106) - tax (318) - slippage (500) = 105076.0
        # Final cash = 97398.0 + 105076.0 = 202474.0
        self.assertAlmostEqual(portfolio.cash, 202474.0)

    def test_dependency_injection(self):
        price_prov_called = False
        risk_prov_called = False
        
        def price_prov(order, portfolio):
            nonlocal price_prov_called
            price_prov_called = True
            return 100.0
            
        def risk_prov(snapshot):
            nonlocal risk_prov_called
            risk_prov_called = True
            return RiskDecision.allow()

        run_simulated_paper_trading_with_guard(
            df=self.df,
            symbol=self.symbol,
            initial_cash=self.initial_cash,
            quantity_per_trade=self.qty,
            kill_switch_state=self.inactive_kill_switch,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov
        )
        
        self.assertTrue(price_prov_called)
        self.assertTrue(risk_prov_called)

    def test_invalid_injected_dependency(self):
        with self.assertRaises(SimulatedPaperTradingGuardError):
            run_simulated_paper_trading_with_guard(
                df=self.df,
                symbol=self.symbol,
                initial_cash=self.initial_cash,
                quantity_per_trade=self.qty,
                kill_switch_state=self.inactive_kill_switch,
                reference_price_provider="not callable", # type: ignore
                risk_decision_provider=lambda s: RiskDecision.allow()
            )
            
        with self.assertRaises(SimulatedPaperTradingGuardError):
            run_simulated_paper_trading_with_guard(
                df=self.df,
                symbol=self.symbol,
                initial_cash=self.initial_cash,
                quantity_per_trade=self.qty,
                kill_switch_state=self.inactive_kill_switch,
                reference_price_provider=lambda o, p: 100.0,
                risk_decision_provider="not callable" # type: ignore
            )

    def test_public_api_export(self):
        import tw_stock_tool.simulated_paper_trading_guard as guard_pkg
        self.assertTrue(hasattr(guard_pkg, "run_simulated_paper_trading_with_guard"))
        self.assertIn("run_simulated_paper_trading_with_guard", guard_pkg.__all__)

if __name__ == '__main__':
    unittest.main()
