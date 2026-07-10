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


    def test_portfolio_exposure_provider_dependency_injection(self):
        portfolio_prov_called = 0
        received_order = None
        received_portfolio = None

        def price_prov(order, portfolio): return 100.0
        def risk_prov(snapshot): return RiskDecision.reject(["blocked"])

        def portfolio_prov(order, portfolio):
            nonlocal portfolio_prov_called, received_order, received_portfolio
            portfolio_prov_called += 1
            received_order = order
            received_portfolio = portfolio
            return 2000.0

        portfolio = run_simulated_paper_trading_with_guard(
            df=self.df,
            symbol=self.symbol,
            initial_cash=self.initial_cash,
            quantity_per_trade=self.qty,
            kill_switch_state=self.inactive_kill_switch,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov,
            portfolio_exposure_provider=portfolio_prov
        )

        self.assertEqual(portfolio_prov_called, 1)
        self.assertIs(received_portfolio, portfolio)
        self.assertEqual(len(portfolio.trade_log.rejections), 1)
        self.assertIs(received_order, portfolio.trade_log.rejections[0].candidate_order)
        self.assertIsNotNone(received_order)
        self.assertEqual(received_order.symbol, self.symbol)
        self.assertEqual(received_order.side, "BUY")
        self.assertIsNotNone(received_portfolio)
        self.assertIsInstance(received_portfolio, SimulatedPortfolio)

    def test_portfolio_exposure_critical_anti_fallback(self):
        from tw_stock_tool.risk.config import SimulatedPaperTradingRiskConfig
        from tw_stock_tool.risk.builder import build_risk_decision_provider_from_config

        risk_config = SimulatedPaperTradingRiskConfig(max_total_exposure=2500.0)
        risk_prov = build_risk_decision_provider_from_config(risk_config)

        qty = 10

        def price_prov(order, portfolio): return 100.0
        def portfolio_prov(order, portfolio): return 2000.0

        portfolio = run_simulated_paper_trading_with_guard(
            df=self.df,
            symbol=self.symbol,
            initial_cash=self.initial_cash,
            quantity_per_trade=qty,
            kill_switch_state=self.inactive_kill_switch,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov,
            portfolio_exposure_provider=portfolio_prov
        )

        self.assertEqual(len(portfolio.trade_log.fills), 0)
        self.assertEqual(len(portfolio.trade_log.orders), 0)
        self.assertEqual(len(portfolio.trade_log.rejections), 1)
        self.assertTrue(any("max_total_exposure" in reason for reason in portfolio.trade_log.rejections[0].reasons))

    def test_portfolio_exposure_provider_runtime_failure(self):
        def price_prov(order, portfolio): return 100.0
        def risk_prov(snapshot): return RiskDecision.allow()
        def portfolio_prov(order, portfolio):
            raise ValueError("Provider failure")

        with self.assertRaises(ValueError):
            run_simulated_paper_trading_with_guard(
                df=self.df,
                symbol=self.symbol,
                initial_cash=self.initial_cash,
                quantity_per_trade=self.qty,
                kill_switch_state=self.inactive_kill_switch,
                reference_price_provider=price_prov,
                risk_decision_provider=risk_prov,
                portfolio_exposure_provider=portfolio_prov
            )

    def test_portfolio_exposure_provider_invalid_injected(self):
        with self.assertRaises(SimulatedPaperTradingGuardError):
            run_simulated_paper_trading_with_guard(
                df=self.df,
                symbol=self.symbol,
                initial_cash=self.initial_cash,
                quantity_per_trade=self.qty,
                kill_switch_state=self.inactive_kill_switch,
                reference_price_provider=lambda o, p: 100.0,
                risk_decision_provider=lambda s: RiskDecision.allow(),
                portfolio_exposure_provider="not callable" # type: ignore
            )

    def test_positional_compatibility(self):
        def price_prov(order, portfolio): return 100.0
        def risk_prov(snapshot): return RiskDecision.allow()

        portfolio = run_simulated_paper_trading_with_guard(
            self.df,
            self.symbol,
            self.initial_cash,
            self.qty,
            self.inactive_kill_switch,
            price_prov,
            risk_prov,
            0.001,
            0.003,
            0.5
        )
        self.assertEqual(len(portfolio.trade_log.fills), 2)

        with self.assertRaises(TypeError):
            run_simulated_paper_trading_with_guard(
                self.df,
                self.symbol,
                self.initial_cash,
                self.qty,
                self.inactive_kill_switch,
                price_prov,
                risk_prov,
                0.0,
                0.0,
                0.0,
                lambda o, p: 0.0
            )


    def test_portfolio_exposure_provider_explicit_none(self):
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
            portfolio_exposure_provider=None
        )
        self.assertEqual(len(portfolio.trade_log.fills), 2)

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
        self.assertTrue(hasattr(guard_pkg, "run_simulated_paper_trading_result_with_guard"))
        self.assertIn("run_simulated_paper_trading_result_with_guard", guard_pkg.__all__)

    def test_result_allowed_path(self):
        from tw_stock_tool.simulated_paper_trading_guard.workflow import run_simulated_paper_trading_result_with_guard
        from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult

        def price_prov(order, portfolio): return 100.0
        def risk_prov(snapshot): return RiskDecision.allow()

        result = run_simulated_paper_trading_result_with_guard(
            df=self.df,
            symbol=self.symbol,
            initial_cash=self.initial_cash,
            quantity_per_trade=self.qty,
            kill_switch_state=self.inactive_kill_switch,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov
        )

        self.assertIsInstance(result, SimulatedPaperTradingResult)
        self.assertEqual(result.order_count, 2)
        self.assertEqual(result.fill_count, 2)

    def test_result_risk_blocked_path(self):
        from tw_stock_tool.simulated_paper_trading_guard.workflow import run_simulated_paper_trading_result_with_guard
        from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult

        def price_prov(order, portfolio): return 100.0
        def risk_prov(snapshot): return RiskDecision.reject(["Position too large"])

        result = run_simulated_paper_trading_result_with_guard(
            df=self.df,
            symbol=self.symbol,
            initial_cash=self.initial_cash,
            quantity_per_trade=self.qty,
            kill_switch_state=self.inactive_kill_switch,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov
        )

        self.assertIsInstance(result, SimulatedPaperTradingResult)
        self.assertEqual(result.order_count, 0)
        self.assertEqual(result.fill_count, 0)
        self.assertEqual(len(result.rejections), 1)

    def test_result_kill_switch_blocked_path(self):
        from tw_stock_tool.simulated_paper_trading_guard.workflow import run_simulated_paper_trading_result_with_guard
        from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult

        def price_prov(order, portfolio): return 100.0
        def risk_prov(snapshot): return RiskDecision.allow()

        result = run_simulated_paper_trading_result_with_guard(
            df=self.df,
            symbol=self.symbol,
            initial_cash=self.initial_cash,
            quantity_per_trade=self.qty,
            kill_switch_state=self.active_kill_switch,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov
        )

        self.assertIsInstance(result, SimulatedPaperTradingResult)
        self.assertEqual(result.order_count, 0)
        self.assertEqual(result.fill_count, 0)
        self.assertEqual(len(result.rejections), 1)

    def test_result_parameter_passthrough(self):
        from tw_stock_tool.simulated_paper_trading_guard.workflow import run_simulated_paper_trading_result_with_guard

        def price_prov(order, portfolio): return 100.0
        def risk_prov(snapshot): return RiskDecision.allow()

        result = run_simulated_paper_trading_result_with_guard(
            df=self.df,
            symbol=self.symbol,
            initial_cash=self.initial_cash,
            quantity_per_trade=self.qty,
            kill_switch_state=self.inactive_kill_switch,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov,
            fee_rate=0.001,
            tax_rate=0.003,
            slippage_per_share=0.5,
            last_price=109.0
        )

        # Fills should reflect the parameters
        self.assertEqual(result.fill_count, 2)
        self.assertAlmostEqual(result.final_cash, 202474.0)

        # final_cash = 202474.0, final_position_quantity = 0.
        # total_equity = 202474.0 + 0 = 202474.0.
        self.assertAlmostEqual(result.total_equity, 202474.0)

    def test_result_dependency_injection(self):
        from tw_stock_tool.simulated_paper_trading_guard.workflow import run_simulated_paper_trading_result_with_guard
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

        run_simulated_paper_trading_result_with_guard(
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


    def test_result_portfolio_exposure_provider_dependency_injection(self):
        from tw_stock_tool.simulated_paper_trading_guard.workflow import run_simulated_paper_trading_result_with_guard
        from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult

        portfolio_prov_called = 0
        received_order = None
        received_portfolio = None

        def price_prov(order, portfolio): return 100.0
        def risk_prov(snapshot): return RiskDecision.reject(["blocked"])

        def portfolio_prov(order, portfolio):
            nonlocal portfolio_prov_called, received_order, received_portfolio
            portfolio_prov_called += 1
            received_order = order
            received_portfolio = portfolio
            return 2000.0

        result = run_simulated_paper_trading_result_with_guard(
            df=self.df,
            symbol=self.symbol,
            initial_cash=self.initial_cash,
            quantity_per_trade=self.qty,
            kill_switch_state=self.inactive_kill_switch,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov,
            portfolio_exposure_provider=portfolio_prov
        )

        self.assertEqual(portfolio_prov_called, 1)
        self.assertIsNotNone(received_order)
        self.assertIsInstance(received_portfolio, SimulatedPortfolio)
        self.assertEqual(len(result.rejections), 1)
        self.assertIs(received_order, result.rejections[0].candidate_order)
        self.assertIsInstance(result, SimulatedPaperTradingResult)
        self.assertEqual(result.fill_count, 0)

    def test_result_portfolio_exposure_critical_anti_fallback(self):
        from tw_stock_tool.risk.config import SimulatedPaperTradingRiskConfig
        from tw_stock_tool.risk.builder import build_risk_decision_provider_from_config
        from tw_stock_tool.simulated_paper_trading_guard.workflow import run_simulated_paper_trading_result_with_guard

        risk_config = SimulatedPaperTradingRiskConfig(max_total_exposure=2500.0)
        risk_prov = build_risk_decision_provider_from_config(risk_config)

        qty = 10

        def price_prov(order, portfolio): return 100.0
        def portfolio_prov(order, portfolio): return 2000.0

        result = run_simulated_paper_trading_result_with_guard(
            df=self.df,
            symbol=self.symbol,
            initial_cash=self.initial_cash,
            quantity_per_trade=qty,
            kill_switch_state=self.inactive_kill_switch,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov,
            portfolio_exposure_provider=portfolio_prov
        )

        self.assertEqual(result.fill_count, 0)
        self.assertEqual(result.order_count, 0)
        self.assertTrue(any(any("max_total_exposure" in reason for reason in r.reasons) for r in result.rejections))

    def test_result_portfolio_exposure_provider_runtime_failure(self):
        from tw_stock_tool.simulated_paper_trading_guard.workflow import run_simulated_paper_trading_result_with_guard
        def price_prov(order, portfolio): return 100.0
        def risk_prov(snapshot): return RiskDecision.allow()
        def portfolio_prov(order, portfolio):
            raise ValueError("Provider failure")

        with self.assertRaises(ValueError):
            run_simulated_paper_trading_result_with_guard(
                df=self.df,
                symbol=self.symbol,
                initial_cash=self.initial_cash,
                quantity_per_trade=self.qty,
                kill_switch_state=self.inactive_kill_switch,
                reference_price_provider=price_prov,
                risk_decision_provider=risk_prov,
                portfolio_exposure_provider=portfolio_prov
            )

    def test_result_portfolio_exposure_provider_invalid_injected(self):
        from tw_stock_tool.simulated_paper_trading_guard.workflow import run_simulated_paper_trading_result_with_guard
        with self.assertRaises(SimulatedPaperTradingGuardError):
            run_simulated_paper_trading_result_with_guard(
                df=self.df,
                symbol=self.symbol,
                initial_cash=self.initial_cash,
                quantity_per_trade=self.qty,
                kill_switch_state=self.inactive_kill_switch,
                reference_price_provider=lambda o, p: 100.0,
                risk_decision_provider=lambda s: RiskDecision.allow(),
                portfolio_exposure_provider="not callable" # type: ignore
            )

    def test_result_positional_compatibility(self):
        from tw_stock_tool.simulated_paper_trading_guard.workflow import run_simulated_paper_trading_result_with_guard
        def price_prov(order, portfolio): return 100.0
        def risk_prov(snapshot): return RiskDecision.allow()

        result = run_simulated_paper_trading_result_with_guard(
            self.df,
            self.symbol,
            self.initial_cash,
            self.qty,
            self.inactive_kill_switch,
            price_prov,
            risk_prov,
            0.001,
            0.003,
            0.5,
            109.0
        )
        self.assertEqual(result.fill_count, 2)

        with self.assertRaises(TypeError):
            run_simulated_paper_trading_result_with_guard(
                self.df,
                self.symbol,
                self.initial_cash,
                self.qty,
                self.inactive_kill_switch,
                price_prov,
                risk_prov,
                0.0,
                0.0,
                0.0,
                109.0,
                lambda o, p: 0.0
            )

    def test_result_portfolio_exposure_provider_explicit_none(self):
        from tw_stock_tool.simulated_paper_trading_guard.workflow import run_simulated_paper_trading_result_with_guard
        def price_prov(order, portfolio): return 100.0
        def risk_prov(snapshot): return RiskDecision.allow()

        result = run_simulated_paper_trading_result_with_guard(
            df=self.df,
            symbol=self.symbol,
            initial_cash=self.initial_cash,
            quantity_per_trade=self.qty,
            kill_switch_state=self.inactive_kill_switch,
            reference_price_provider=price_prov,
            risk_decision_provider=risk_prov,
            portfolio_exposure_provider=None
        )
        self.assertEqual(result.fill_count, 2)
        self.assertEqual(result.order_count, 2)

    def test_result_invalid_injected_dependency(self):
        from tw_stock_tool.simulated_paper_trading_guard.workflow import run_simulated_paper_trading_result_with_guard
        with self.assertRaises(SimulatedPaperTradingGuardError):
            run_simulated_paper_trading_result_with_guard(
                df=self.df,
                symbol=self.symbol,
                initial_cash=self.initial_cash,
                quantity_per_trade=self.qty,
                kill_switch_state=self.inactive_kill_switch,
                reference_price_provider="not callable", # type: ignore
                risk_decision_provider=lambda s: RiskDecision.allow()
            )

        with self.assertRaises(SimulatedPaperTradingGuardError):
            run_simulated_paper_trading_result_with_guard(
                df=self.df,
                symbol=self.symbol,
                initial_cash=self.initial_cash,
                quantity_per_trade=self.qty,
                kill_switch_state=self.inactive_kill_switch,
                reference_price_provider=lambda o, p: 100.0,
                risk_decision_provider="not callable" # type: ignore
            )

if __name__ == '__main__':
    unittest.main()
