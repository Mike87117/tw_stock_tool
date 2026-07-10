import math
import unittest
import pandas as pd

from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedOrder,
    SimulatedPortfolio,
    SimulatedFill,
)
from tw_stock_tool.paper_trading.runtime import (
    SimulatedPaperTradingRuntimeState,
    SimulatedPendingOrderState,
)
from tw_stock_tool.simulated_paper_trading_guard.models import (
    SimulatedPaperTradingGuardDecision,
)
from tw_stock_tool.paper_trading.stepper import step_simulated_symbol_bar


class TestSimulatedPaperTradingStepper(unittest.TestCase):
    def setUp(self) -> None:
        self.portfolio = SimulatedPortfolio(cash=100000.0)
        self.runtime_state = SimulatedPaperTradingRuntimeState(portfolio=self.portfolio)

    def test_stepper_validation_runtime_state(self):
        with self.assertRaisesRegex(PaperTradingModelError, "runtime_state must be a SimulatedPaperTradingRuntimeState"):
            step_simulated_symbol_bar(
                runtime_state="not_a_state",  # type: ignore
                symbol="AAPL",
                bar_position=0,
                index_label="2023-01-01",
                open_price=150.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=100,
            )

    def test_stepper_validation_symbol(self):
        with self.assertRaisesRegex(PaperTradingModelError, "Symbol must not be blank"):
            step_simulated_symbol_bar(
                runtime_state=self.runtime_state,
                symbol="   ",
                bar_position=0,
                index_label="2023-01-01",
                open_price=150.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=100,
            )

    def test_stepper_validation_bar_position(self):
        with self.assertRaisesRegex(PaperTradingModelError, "bar_position must be a non-negative integer"):
            step_simulated_symbol_bar(
                runtime_state=self.runtime_state,
                symbol="AAPL",
                bar_position=-1,
                index_label="2023-01-01",
                open_price=150.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=100,
            )

        with self.assertRaisesRegex(PaperTradingModelError, "bar_position must be a non-negative integer"):
            step_simulated_symbol_bar(
                runtime_state=self.runtime_state,
                symbol="AAPL",
                bar_position=True,  # type: ignore
                index_label="2023-01-01",
                open_price=150.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=100,
            )

    def test_stepper_validation_quantity(self):
        with self.assertRaisesRegex(PaperTradingModelError, "quantity_per_trade must be a positive integer"):
            step_simulated_symbol_bar(
                runtime_state=self.runtime_state,
                symbol="AAPL",
                bar_position=0,
                index_label="2023-01-01",
                open_price=150.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=0,
            )

        with self.assertRaisesRegex(PaperTradingModelError, "quantity_per_trade must be a positive integer"):
            step_simulated_symbol_bar(
                runtime_state=self.runtime_state,
                symbol="AAPL",
                bar_position=0,
                index_label="2023-01-01",
                open_price=150.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=True,  # type: ignore
            )

    def test_stepper_validation_costs(self):
        with self.assertRaisesRegex(PaperTradingModelError, "fee_rate, tax_rate, and slippage_per_share must be non-negative"):
            step_simulated_symbol_bar(
                runtime_state=self.runtime_state,
                symbol="AAPL",
                bar_position=0,
                index_label="2023-01-01",
                open_price=150.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=100,
                fee_rate=-0.01,
            )

    def test_stepper_validation_guards(self):
        with self.assertRaisesRegex(PaperTradingModelError, "Cannot provide both guard_decision and guard_decision_provider"):
            step_simulated_symbol_bar(
                runtime_state=self.runtime_state,
                symbol="AAPL",
                bar_position=0,
                index_label="2023-01-01",
                open_price=150.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=100,
                guard_decision=SimulatedPaperTradingGuardDecision.allow(),
                guard_decision_provider=lambda o, p: SimulatedPaperTradingGuardDecision.allow(),
            )

        with self.assertRaisesRegex(PaperTradingModelError, "guard_decision must be a SimulatedPaperTradingGuardDecision"):
            step_simulated_symbol_bar(
                runtime_state=self.runtime_state,
                symbol="AAPL",
                bar_position=0,
                index_label="2023-01-01",
                open_price=150.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=100,
                guard_decision="allow",  # type: ignore
            )

        with self.assertRaisesRegex(PaperTradingModelError, "guard_decision_provider must be callable"):
            step_simulated_symbol_bar(
                runtime_state=self.runtime_state,
                symbol="AAPL",
                bar_position=0,
                index_label="2023-01-01",
                open_price=150.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=100,
                guard_decision_provider="not_callable",  # type: ignore
            )

    def test_buy_path_valid_open(self):
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=1,
            index_label="2023-01-01",
            open_price=100.0,
            entry_signal=True,
            exit_signal=False,
            quantity_per_trade=50,
        )

        self.assertIn("AAPL", self.runtime_state.pending_orders)
        pending = self.runtime_state.pending_orders["AAPL"]
        self.assertEqual(pending.reference_price, 100.0)
        self.assertEqual(pending.reserved_buy_notional, 5000.0)
        self.assertEqual(pending.order.order_id, "AAPL-BUY-1")

        self.assertEqual(len(self.portfolio.trade_log.orders), 1)
        self.assertIs(self.portfolio.trade_log.orders[0], pending.order)

        # Next bar open fills the order
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=2,
            index_label="2023-01-02",
            open_price=105.0,
            entry_signal=False,
            exit_signal=False,
            quantity_per_trade=50,
            fee_rate=0.01,
            slippage_per_share=0.5,
        )

        self.assertNotIn("AAPL", self.runtime_state.pending_orders)
        self.assertEqual(len(self.portfolio.trade_log.fills), 1)
        fill = self.portfolio.trade_log.fills[0]
        self.assertEqual(fill.price, 105.0)
        self.assertEqual(fill.fee, 50 * 105.0 * 0.01)
        self.assertEqual(fill.slippage, 50 * 0.5)
        
        pos = self.portfolio.position_for("AAPL")
        self.assertEqual(pos.quantity, 50)
        self.assertEqual(self.portfolio.cash, 100000.0 - (50 * 105.0 + fill.fee + fill.slippage))

    def test_sell_path(self):
        # Force a position
        self.portfolio.cash = 100000.0
        self.portfolio.apply_fill(
            SimulatedFill(order_id="TEST", symbol="AAPL", side="BUY", quantity=50, price=100.0, filled_at="2023-01-01")
        )

        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=2,
            index_label="2023-01-02",
            open_price=110.0,
            entry_signal=False,
            exit_signal=True,
            quantity_per_trade=100,  # Should use current shares (50), not this
        )

        self.assertIn("AAPL", self.runtime_state.pending_orders)
        pending = self.runtime_state.pending_orders["AAPL"]
        self.assertEqual(pending.order.side, "SELL")
        self.assertEqual(pending.order.quantity, 50)
        self.assertEqual(pending.reserved_buy_notional, 0.0)

        # Fill SELL next bar
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=3,
            index_label="2023-01-03",
            open_price=120.0,
            entry_signal=False,
            exit_signal=False,
            quantity_per_trade=100,
            tax_rate=0.01,
        )

        self.assertNotIn("AAPL", self.runtime_state.pending_orders)
        pos = self.portfolio.position_for("AAPL")
        self.assertEqual(pos.quantity, 0)
        
        fill = self.portfolio.trade_log.fills[1] # first was force BUY
        self.assertEqual(fill.side, "SELL")
        self.assertEqual(fill.tax, 50 * 120.0 * 0.01)

    def test_invalid_open_clears_pending(self):
        for invalid_open in [float('nan'), float('inf'), float('-inf'), 0.0, -10.0]:
            with self.subTest(invalid_open=invalid_open):
                self.setUp()
                step_simulated_symbol_bar(
                    runtime_state=self.runtime_state,
                    symbol="AAPL",
                    bar_position=1,
                    index_label="1",
                    open_price=100.0,
                    entry_signal=True,
                    exit_signal=False,
                    quantity_per_trade=10,
                )
                self.assertIn("AAPL", self.runtime_state.pending_orders)

                step_simulated_symbol_bar(
                    runtime_state=self.runtime_state,
                    symbol="AAPL",
                    bar_position=2,
                    index_label="2",
                    open_price=invalid_open,
                    entry_signal=False,
                    exit_signal=False,
                    quantity_per_trade=10,
                )
                self.assertNotIn("AAPL", self.runtime_state.pending_orders)
                self.assertEqual(len(self.portfolio.trade_log.fills), 0)

    def test_invalid_signal_open_fails_closed(self):
        for invalid_open in [float('nan'), float('inf'), float('-inf'), 0.0, -10.0]:
            with self.subTest(invalid_open=invalid_open):
                self.setUp()
                step_simulated_symbol_bar(
                    runtime_state=self.runtime_state,
                    symbol="AAPL",
                    bar_position=1,
                    index_label="1",
                    open_price=invalid_open,
                    entry_signal=True,
                    exit_signal=False,
                    quantity_per_trade=10,
                )
                self.assertNotIn("AAPL", self.runtime_state.pending_orders)
                self.assertEqual(len(self.portfolio.trade_log.orders), 0)

    def test_static_guard_allow(self):
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=1,
            index_label="1",
            open_price=100.0,
            entry_signal=True,
            exit_signal=False,
            quantity_per_trade=10,
            guard_decision=SimulatedPaperTradingGuardDecision.allow()
        )
        self.assertIn("AAPL", self.runtime_state.pending_orders)

    def test_static_guard_block(self):
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=1,
            index_label="1",
            open_price=100.0,
            entry_signal=True,
            exit_signal=False,
            quantity_per_trade=10,
            guard_decision=SimulatedPaperTradingGuardDecision.block(reasons=["Blocked by static"])
        )
        self.assertNotIn("AAPL", self.runtime_state.pending_orders)
        self.assertEqual(len(self.portfolio.trade_log.rejections), 1)
        self.assertEqual(self.portfolio.trade_log.rejections[0].reasons, ("Blocked by static",))

    def test_dynamic_guard_provider(self):
        def my_provider(order, portfolio):
            self.assertIsInstance(order, SimulatedOrder)
            self.assertIs(portfolio, self.portfolio)
            return SimulatedPaperTradingGuardDecision.block(reasons=["Blocked dynamically"])

        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=1,
            index_label="1",
            open_price=100.0,
            entry_signal=True,
            exit_signal=False,
            quantity_per_trade=10,
            guard_decision_provider=my_provider
        )
        self.assertNotIn("AAPL", self.runtime_state.pending_orders)
        self.assertEqual(len(self.portfolio.trade_log.rejections), 1)
        self.assertEqual(self.portfolio.trade_log.rejections[0].reasons, ("Blocked dynamically",))

    def test_dynamic_guard_provider_wrong_return(self):
        with self.assertRaisesRegex(PaperTradingModelError, "guard_decision_provider must return SimulatedPaperTradingGuardDecision."):
            step_simulated_symbol_bar(
                runtime_state=self.runtime_state,
                symbol="AAPL",
                bar_position=1,
                index_label="1",
                open_price=100.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=10,
                guard_decision_provider=lambda o, p: "not a decision"  # type: ignore
            )

    def test_dynamic_guard_provider_raises(self):
        with self.assertRaisesRegex(PaperTradingModelError, "guard_decision_provider must return SimulatedPaperTradingGuardDecision"):
            step_simulated_symbol_bar(
                runtime_state=self.runtime_state,
                symbol="AAPL",
                bar_position=1,
                index_label="1",
                open_price=100.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=10,
                guard_decision_provider=lambda o, p: "not a decision"  # type: ignore
            )

    def test_existing_engine_semantics_flat_exit(self):
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=1,
            index_label="1",
            open_price=100.0,
            entry_signal=False,
            exit_signal=True,
            quantity_per_trade=10,
        )
        self.assertNotIn("AAPL", self.runtime_state.pending_orders)
        self.assertEqual(len(self.portfolio.trade_log.orders), 0)

    def test_existing_engine_semantics_double_entry(self):
        # Force position
        self.portfolio.apply_fill(
            SimulatedFill(order_id="TEST", symbol="AAPL", side="BUY", quantity=10, price=100.0, filled_at="2023-01-01")
        )
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=1,
            index_label="1",
            open_price=100.0,
            entry_signal=True,
            exit_signal=False,
            quantity_per_trade=10,
        )
        self.assertNotIn("AAPL", self.runtime_state.pending_orders)

    def test_insufficient_cash_buy_clears_pending(self):
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=1,
            index_label="1",
            open_price=100.0,
            entry_signal=True,
            exit_signal=False,
            quantity_per_trade=2000, # 2000 * 100 = 200,000 > 100,000
        )
        self.assertIn("AAPL", self.runtime_state.pending_orders)
        
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=2,
            index_label="2",
            open_price=100.0,
            entry_signal=False,
            exit_signal=False,
            quantity_per_trade=10,
        )
        # Should clear pending and skip fill
        self.assertNotIn("AAPL", self.runtime_state.pending_orders)
        self.assertEqual(len(self.portfolio.trade_log.fills), 0)
