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

    def test_validation_non_string_symbol(self):
        with self.assertRaises(PaperTradingModelError):
            step_simulated_symbol_bar(
                runtime_state=self.runtime_state,
                symbol=123,
                bar_position=1,
                index_label="1",
                open_price=100.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=10,
            )

    def test_validation_negative_quantity(self):
        with self.assertRaises(PaperTradingModelError):
            step_simulated_symbol_bar(
                runtime_state=self.runtime_state,
                symbol="AAPL",
                bar_position=1,
                index_label="1",
                open_price=100.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=-10,
            )

    def test_validation_negative_tax_rate(self):
        with self.assertRaises(PaperTradingModelError):
            step_simulated_symbol_bar(
                runtime_state=self.runtime_state,
                symbol="AAPL",
                bar_position=1,
                index_label="1",
                open_price=100.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=10,
                tax_rate=-0.01,
            )

    def test_validation_negative_slippage(self):
        with self.assertRaises(PaperTradingModelError):
            step_simulated_symbol_bar(
                runtime_state=self.runtime_state,
                symbol="AAPL",
                bar_position=1,
                index_label="1",
                open_price=100.0,
                entry_signal=True,
                exit_signal=False,
                quantity_per_trade=10,
                slippage_per_share=-0.5,
            )

    def test_dynamic_guard_allow_identity(self):
        captured_candidate = []
        def my_provider(order, portfolio):
            captured_candidate.append(order)
            self.assertIs(portfolio, self.portfolio)
            return SimulatedPaperTradingGuardDecision.allow()

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
        self.assertEqual(len(captured_candidate), 1)
        self.assertIn("AAPL", self.runtime_state.pending_orders)
        pending = self.runtime_state.pending_orders["AAPL"]
        self.assertIs(pending.order, captured_candidate[0])
        self.assertEqual(len(self.portfolio.trade_log.orders), 1)
        self.assertIs(self.portfolio.trade_log.orders[0], captured_candidate[0])

    def test_invalid_signal_open_does_not_call_guard(self):
        for invalid_open in [float('nan'), float('inf'), float('-inf'), 0.0, -10.0]:
            with self.subTest(invalid_open=invalid_open):
                self.setUp()
                call_count = [0]
                def my_provider(order, portfolio):
                    call_count[0] += 1
                    return SimulatedPaperTradingGuardDecision.allow()
                    
                step_simulated_symbol_bar(
                    runtime_state=self.runtime_state,
                    symbol="AAPL",
                    bar_position=1,
                    index_label="1",
                    open_price=invalid_open,
                    entry_signal=True,
                    exit_signal=False,
                    quantity_per_trade=10,
                    guard_decision_provider=my_provider
                )
                self.assertEqual(call_count[0], 0)
                self.assertNotIn("AAPL", self.runtime_state.pending_orders)
                self.assertEqual(len(self.portfolio.trade_log.orders), 0)
                self.assertEqual(len(self.portfolio.trade_log.rejections), 0)

    def test_invalid_fill_bar_with_same_bar_signal(self):
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
        self.assertEqual(len(self.portfolio.trade_log.orders), 1)

        call_count = [0]
        def my_provider(order, portfolio):
            call_count[0] += 1
            return SimulatedPaperTradingGuardDecision.allow()

        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=2,
            index_label="2",
            open_price=float('nan'),
            entry_signal=True,
            exit_signal=False,
            quantity_per_trade=10,
            guard_decision_provider=my_provider
        )
        self.assertNotIn("AAPL", self.runtime_state.pending_orders)
        self.assertEqual(len(self.portfolio.trade_log.fills), 0)
        self.assertEqual(len(self.portfolio.trade_log.orders), 1)
        self.assertEqual(call_count[0], 0)

    def test_blocked_candidate_is_not_accepted(self):
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=1,
            index_label="1",
            open_price=100.0,
            entry_signal=True,
            exit_signal=False,
            quantity_per_trade=10,
            guard_decision=SimulatedPaperTradingGuardDecision.block(reasons=("Static Block",))
        )
        self.assertNotIn("AAPL", self.runtime_state.pending_orders)
        self.assertEqual(len(self.portfolio.trade_log.rejections), 1)
        self.assertEqual(self.portfolio.trade_log.rejections[0].reasons, ("Static Block",))
        self.assertEqual(len(self.portfolio.trade_log.orders), 0)

        def my_provider(order, portfolio):
            return SimulatedPaperTradingGuardDecision.block(reasons=("Dynamic Block",))

        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=2,
            index_label="2",
            open_price=100.0,
            entry_signal=True,
            exit_signal=False,
            quantity_per_trade=10,
            guard_decision_provider=my_provider
        )
        self.assertNotIn("AAPL", self.runtime_state.pending_orders)
        self.assertEqual(len(self.portfolio.trade_log.rejections), 2)
        self.assertEqual(self.portfolio.trade_log.rejections[1].reasons, ("Dynamic Block",))
        self.assertEqual(len(self.portfolio.trade_log.orders), 0)

    def test_failed_sell_fill(self):
        # Create a real smaller current position
        self.portfolio.apply_fill(
            SimulatedFill(order_id="TEST_BUY", symbol="AAPL", side="BUY", quantity=10, price=100.0, filled_at="2023-01-01")
        )
        
        # Pending SELL exceeds holdings
        sell_order = SimulatedOrder(
            order_id="TEST_SELL", symbol="AAPL", side="SELL", quantity=20, signal_time="2023-01-02", created_at="2023-01-02"
        )
        self.runtime_state.pending_orders["AAPL"] = SimulatedPendingOrderState(order=sell_order, reference_price=100.0)
        
        initial_cash = self.portfolio.cash
        
        # Process next valid bar
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=3,
            index_label="2023-01-03",
            open_price=110.0,
            entry_signal=False,
            exit_signal=False,
            quantity_per_trade=10,
        )
        
        # PaperTradingModelError is swallowed
        self.assertNotIn("AAPL", self.runtime_state.pending_orders)
        self.assertEqual(len(self.portfolio.trade_log.fills), 1) # Only the initial BUY fill exists
        self.assertEqual(self.portfolio.cash, initial_cash)
        self.assertEqual(self.portfolio.position_for("AAPL").quantity, 10)

    def test_pending_fill_before_current_signal_buy_then_exit(self):
        # Start with pending BUY
        buy_order = SimulatedOrder(
            order_id="AAPL-BUY-1", symbol="AAPL", side="BUY", quantity=10, signal_time="1", created_at="1"
        )
        self.runtime_state.pending_orders["AAPL"] = SimulatedPendingOrderState(order=buy_order, reference_price=100.0)
        self.portfolio.trade_log.record_order(buy_order)

        # Next valid bar: exit_signal=True
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=2,
            index_label="2",
            open_price=110.0,
            entry_signal=False,
            exit_signal=True,
            quantity_per_trade=10,
        )
        
        # Verify BUY fills first, position becomes open, same bar creates pending SELL
        self.assertEqual(len(self.portfolio.trade_log.fills), 1)
        self.assertEqual(self.portfolio.trade_log.fills[0].side, "BUY")
        
        self.assertIn("AAPL", self.runtime_state.pending_orders)
        pending = self.runtime_state.pending_orders["AAPL"]
        self.assertEqual(pending.order.side, "SELL")
        self.assertEqual(pending.order.quantity, 10) # filled qty
        self.assertEqual(pending.order.order_id, "AAPL-SELL-2")

    def test_pending_fill_before_current_signal_sell_then_entry(self):
        # Start with open position and pending SELL
        self.portfolio.apply_fill(
            SimulatedFill(order_id="TEST_BUY", symbol="AAPL", side="BUY", quantity=10, price=100.0, filled_at="0")
        )
        sell_order = SimulatedOrder(
            order_id="AAPL-SELL-1", symbol="AAPL", side="SELL", quantity=10, signal_time="1", created_at="1"
        )
        self.runtime_state.pending_orders["AAPL"] = SimulatedPendingOrderState(order=sell_order, reference_price=110.0)
        self.portfolio.trade_log.record_order(sell_order)

        # Next valid bar: entry_signal=True
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=2,
            index_label="2",
            open_price=110.0,
            entry_signal=True,
            exit_signal=False,
            quantity_per_trade=15,
        )
        
        # Verify SELL fills first, position becomes flat, same bar creates pending BUY
        self.assertEqual(len(self.portfolio.trade_log.fills), 2)
        self.assertEqual(self.portfolio.trade_log.fills[1].side, "SELL")
        
        self.assertIn("AAPL", self.runtime_state.pending_orders)
        pending = self.runtime_state.pending_orders["AAPL"]
        self.assertEqual(pending.order.side, "BUY")
        self.assertEqual(pending.order.quantity, 15) # quantity_per_trade
        self.assertEqual(pending.order.order_id, "AAPL-BUY-2")

    def test_complete_cost_and_pnl_reconciliation(self):
        initial_cash = self.portfolio.cash
        
        # 1. Create pending BUY
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
        
        # 2. Fill BUY with fee 0.01, slippage 0.5
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=2,
            index_label="2",
            open_price=100.0,
            entry_signal=False,
            exit_signal=False,
            quantity_per_trade=10,
            fee_rate=0.01,
            slippage_per_share=0.5,
        )
        self.assertNotIn("AAPL", self.runtime_state.pending_orders)
        self.assertEqual(len(self.portfolio.trade_log.fills), 1)
        buy_fill = self.portfolio.trade_log.fills[0]
        self.assertEqual(buy_fill.fee, 10 * 100.0 * 0.01) # 10.0
        self.assertEqual(buy_fill.slippage, 10 * 0.5) # 5.0
        self.assertEqual(buy_fill.tax, 0.0)
        
        buy_cost = (10 * 100.0) + 10.0 + 5.0 # 1000 + 15 = 1015
        self.assertEqual(self.portfolio.cash, initial_cash - buy_cost)
        self.assertEqual(self.portfolio.position_for("AAPL").quantity, 10)
        self.assertEqual(self.portfolio.position_for("AAPL").average_cost, 1015 / 10) # 101.5
        
        # 3. Create pending SELL
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=3,
            index_label="3",
            open_price=110.0,
            entry_signal=False,
            exit_signal=True,
            quantity_per_trade=10,
        )
        self.assertIn("AAPL", self.runtime_state.pending_orders)
        
        # 4. Fill SELL with fee 0.01, tax 0.003, slippage 0.5
        step_simulated_symbol_bar(
            runtime_state=self.runtime_state,
            symbol="AAPL",
            bar_position=4,
            index_label="4",
            open_price=120.0,
            entry_signal=False,
            exit_signal=False,
            quantity_per_trade=10,
            fee_rate=0.01,
            tax_rate=0.003,
            slippage_per_share=0.5,
        )
        self.assertNotIn("AAPL", self.runtime_state.pending_orders)
        self.assertEqual(len(self.portfolio.trade_log.fills), 2)
        sell_fill = self.portfolio.trade_log.fills[1]
        
        sell_value = 10 * 120.0 # 1200
        sell_fee = 1200 * 0.01 # 12.0
        sell_tax = 1200 * 0.003 # 3.6
        sell_slippage = 10 * 0.5 # 5.0
        
        self.assertEqual(sell_fill.fee, sell_fee)
        self.assertEqual(sell_fill.tax, sell_tax)
        self.assertEqual(sell_fill.slippage, sell_slippage)
        
        sell_proceeds = sell_value - sell_fee - sell_tax - sell_slippage # 1200 - 12 - 3.6 - 5 = 1179.4
        self.assertEqual(self.portfolio.cash, initial_cash - buy_cost + sell_proceeds)
        self.assertEqual(self.portfolio.position_for("AAPL").quantity, 0)
        self.assertEqual(self.portfolio.position_for("AAPL").average_cost, 0.0)
        
        expected_realized_pnl = sell_proceeds - buy_cost # 1179.4 - 1015 = 164.4
        self.assertAlmostEqual(self.portfolio.position_for("AAPL").realized_pnl, expected_realized_pnl)
