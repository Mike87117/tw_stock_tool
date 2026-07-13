import math
import unittest
from datetime import datetime

from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedFill,
    SimulatedOrder,
    SimulatedPortfolio,
    SimulatedPosition,
    SimulatedTradeLog,
)


class TestPaperTradingModels(unittest.TestCase):
    def test_simulated_order_validation(self) -> None:
        order = SimulatedOrder(
            order_id="1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            signal_time=datetime(2026, 1, 1),
        )
        self.assertEqual(order.symbol, "2330")

        with self.assertRaises(PaperTradingModelError):
            SimulatedOrder(order_id="2", symbol="", side="BUY", quantity=1000, signal_time=None)
        with self.assertRaises(PaperTradingModelError):
            SimulatedOrder(order_id="3", symbol="2330", side="INVALID", quantity=1000, signal_time=None)  # type: ignore
        with self.assertRaises(PaperTradingModelError):
            SimulatedOrder(order_id="4", symbol="2330", side="BUY", quantity=0, signal_time=None)

    def test_simulated_fill_validation(self) -> None:
        fill = SimulatedFill(
            order_id="1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            price=100.0,
            filled_at=datetime(2026, 1, 1),
            fee=142.0,
            tax=0.0,
            slippage=0.0,
        )
        self.assertEqual(fill.gross_amount, 100000.0)
        self.assertEqual(fill.net_cash_effect, -100142.0)

        with self.assertRaises(PaperTradingModelError):
            SimulatedFill(order_id="2", symbol="2330", side="BUY", quantity=1000, price=0.0, filled_at=None)
        with self.assertRaises(PaperTradingModelError):
            SimulatedFill(order_id="3", symbol="2330", side="BUY", quantity=1000, price=100.0, filled_at=None, fee=-1.0)

        sell_fill = SimulatedFill(
            order_id="4",
            symbol="2330",
            side="SELL",
            quantity=1000,
            price=100.0,
            filled_at=None,
            fee=142.0,
            tax=300.0,
            slippage=0.0,
        )
        self.assertEqual(sell_fill.net_cash_effect, 100000.0 - 142.0 - 300.0)

    def test_simulated_fill_rejects_nonfinite_monetary_fields(self) -> None:
        for field in ("price", "fee", "tax", "slippage"):
            for value in (float("nan"), float("inf"), -float("inf")):
                with self.subTest(field=field, value=value):
                    values = dict(
                        order_id="matrix",
                        symbol="2330",
                        side="BUY",
                        quantity=1,
                        price=100.0,
                        filled_at=None,
                    )
                    values[field] = value
                    with self.assertRaises(PaperTradingModelError):
                        SimulatedFill(**values)

    def test_simulated_fill_rejects_booleans_and_wrong_types(self) -> None:
        for field in ("price", "fee", "tax", "slippage"):
            for value in (True, False, "invalid", None):
                with self.subTest(field=field, value=value):
                    values = dict(
                        order_id="types",
                        symbol="2330",
                        side="BUY",
                        quantity=1,
                        price=100.0,
                        filled_at=None,
                    )
                    values[field] = value
                    with self.assertRaises(PaperTradingModelError):
                        SimulatedFill(**values)

    def test_simulated_fill_accepts_valid_monetary_boundaries(self) -> None:
        integer_price = SimulatedFill("int", "2330", "BUY", 1, 100, None)
        float_price_and_costs = SimulatedFill(
            "float",
            "2330",
            "BUY",
            1,
            100.5,
            None,
            fee=1.0,
            tax=2.5,
            slippage=0.25,
        )

        self.assertEqual(integer_price.price, 100)
        self.assertEqual((integer_price.fee, integer_price.tax, integer_price.slippage), (0.0, 0.0, 0.0))
        self.assertEqual(float_price_and_costs.price, 100.5)
        self.assertEqual(
            (float_price_and_costs.fee, float_price_and_costs.tax, float_price_and_costs.slippage),
            (1.0, 2.5, 0.25),
        )

    def test_simulated_portfolio_validates_initial_cash(self) -> None:
        for value in (True, float("nan"), float("inf"), -float("inf"), -1.0, "1000", None):
            with self.subTest(value=value):
                with self.assertRaises(PaperTradingModelError):
                    SimulatedPortfolio(cash=value)

        for value in (0, 0.0, 1000, 1000.5):
            with self.subTest(value=value):
                self.assertEqual(SimulatedPortfolio(cash=value).cash, value)

    def test_simulated_portfolio_rejects_mutated_fill_before_state_changes(self) -> None:
        portfolio = SimulatedPortfolio(cash=1000.0)
        fill = SimulatedFill("o", "2330", "BUY", 1, 100.0, None)
        fill.price = float("nan")
        initial_cash = portfolio.cash
        initial_positions = dict(portfolio.positions)
        initial_fills = list(portfolio.trade_log.fills)

        with self.assertRaises(PaperTradingModelError):
            portfolio.apply_fill(fill)

        self.assertEqual(portfolio.cash, initial_cash)
        self.assertEqual(portfolio.cash, 1000.0)
        self.assertTrue(math.isfinite(portfolio.cash))
        self.assertEqual(portfolio.positions, initial_positions)
        self.assertEqual(portfolio.position_for("2330").quantity, 0)
        self.assertEqual(portfolio.trade_log.fills, initial_fills)
        self.assertEqual(len(portfolio.trade_log.fills), 0)

    def test_simulated_position_rejects_mutated_fill_before_state_changes(self) -> None:
        position = SimulatedPosition(symbol="2330")
        position.apply_fill(SimulatedFill("first", "2330", "BUY", 2, 100.0, None))
        fill = SimulatedFill("second", "2330", "BUY", 1, 200.0, None)
        fill.fee = float("inf")
        initial_state = (position.quantity, position.average_cost, position.realized_pnl)

        with self.assertRaises(PaperTradingModelError):
            position.apply_fill(fill)

        self.assertEqual(
            (position.quantity, position.average_cost, position.realized_pnl),
            initial_state,
        )

    def test_simulated_position(self) -> None:
        pos = SimulatedPosition(symbol="2330")

        # BUY
        fill1 = SimulatedFill(order_id="1", symbol="2330", side="BUY", quantity=1000, price=100.0, filled_at=None)
        pos.apply_fill(fill1)
        self.assertEqual(pos.quantity, 1000)
        self.assertEqual(pos.average_cost, 100.0)

        # Second BUY updates weighted average cost
        fill2 = SimulatedFill(order_id="2", symbol="2330", side="BUY", quantity=1000, price=200.0, filled_at=None)
        pos.apply_fill(fill2)
        self.assertEqual(pos.quantity, 2000)
        self.assertEqual(pos.average_cost, 150.0)

        # SELL
        sell_fill = SimulatedFill(order_id="3", symbol="2330", side="SELL", quantity=1000, price=300.0, filled_at=None, fee=0.0, tax=0.0)
        pos.apply_fill(sell_fill)
        self.assertEqual(pos.quantity, 1000)
        # Realized PnL = (1000 * 300) - (1000 * 150) = 150000
        self.assertEqual(pos.realized_pnl, 150000.0)

        # Oversell error
        bad_sell = SimulatedFill(order_id="4", symbol="2330", side="SELL", quantity=2000, price=300.0, filled_at=None)
        with self.assertRaises(PaperTradingModelError):
            pos.apply_fill(bad_sell)

        # Market value and unrealized
        self.assertEqual(pos.market_value(400.0), 400000.0)
        self.assertEqual(pos.unrealized_pnl(400.0), 400000.0 - 150000.0)

    def test_simulated_position_buy_cost(self) -> None:
        pos = SimulatedPosition(symbol="2330")
        fill = SimulatedFill(
            order_id="1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            price=100.0,
            filled_at=None,
            fee=142.0,
            slippage=8.0,
        )
        pos.apply_fill(fill)
        self.assertEqual(pos.average_cost, 100.15)

    def test_simulated_position_realized_pnl(self) -> None:
        pos = SimulatedPosition(symbol="2330")
        # BUY 1000 @ 100, fee 142, slippage 8
        # cost basis = 100000 + 142 + 8 = 100150
        fill_buy = SimulatedFill(
            order_id="1", symbol="2330", side="BUY", quantity=1000, price=100.0, filled_at=None, fee=142.0, slippage=8.0
        )
        pos.apply_fill(fill_buy)
        self.assertEqual(pos.average_cost, 100.15)

        # SELL 1000 @ 110, fee 157, tax 330, slippage 13
        # net proceeds = 110000 - 157 - 330 - 13 = 109500
        fill_sell = SimulatedFill(
            order_id="2", symbol="2330", side="SELL", quantity=1000, price=110.0, filled_at=None, fee=157.0, tax=330.0, slippage=13.0
        )
        pos.apply_fill(fill_sell)
        # realized_pnl = 109500 - 100150 = 9350
        self.assertEqual(pos.realized_pnl, 9350.0)

    def test_simulated_trade_log(self) -> None:
        log = SimulatedTradeLog()
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1000, signal_time=None)
        fill = SimulatedFill(order_id="1", symbol="2330", side="BUY", quantity=1000, price=100.0, filled_at=None)

        log.record_order(order)
        log.record_fill(fill)

        self.assertEqual(len(log.orders), 1)
        self.assertEqual(len(log.fills), 1)
        self.assertEqual(len(log.rejections), 0)

    def test_simulated_order_rejection(self) -> None:
        from tw_stock_tool.paper_trading.models import SimulatedOrderRejection
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1000, signal_time=None)
        rejection = SimulatedOrderRejection(candidate_order=order, reasons=("Risk limit exceeded",))
        
        self.assertEqual(rejection.candidate_order.order_id, "1")
        self.assertEqual(rejection.reasons, ("Risk limit exceeded",))
        
        log = SimulatedTradeLog()
        log.record_rejection(rejection)
        self.assertEqual(len(log.rejections), 1)
        self.assertEqual(log.rejections[0], rejection)

    def test_simulated_portfolio(self) -> None:
        portfolio = SimulatedPortfolio(cash=200000.0)
        fill_buy = SimulatedFill(order_id="1", symbol="2330", side="BUY", quantity=1000, price=100.0, filled_at=None)

        portfolio.apply_fill(fill_buy)
        self.assertEqual(portfolio.cash, 100000.0)
        self.assertEqual(portfolio.position_for("2330").quantity, 1000)
        self.assertEqual(len(portfolio.trade_log.fills), 1)

        fill_sell = SimulatedFill(order_id="2", symbol="2330", side="SELL", quantity=500, price=200.0, filled_at=None)
        portfolio.apply_fill(fill_sell)
        self.assertEqual(portfolio.cash, 200000.0)
        self.assertEqual(portfolio.position_for("2330").quantity, 500)

        # Insufficient cash
        bad_buy = SimulatedFill(order_id="3", symbol="2330", side="BUY", quantity=3000, price=100.0, filled_at=None)
        with self.assertRaises(PaperTradingModelError):
            portfolio.apply_fill(bad_buy)

        # Insufficient shares
        bad_sell = SimulatedFill(order_id="4", symbol="2330", side="SELL", quantity=1000, price=100.0, filled_at=None)
        with self.assertRaises(PaperTradingModelError):
            portfolio.apply_fill(bad_sell)

        # Equity calculation
        self.assertEqual(portfolio.total_equity({"2330": 200.0}), 200000.0 + 100000.0)

        # Missing price raises error
        with self.assertRaises(PaperTradingModelError):
            portfolio.total_equity({"2317": 100.0})

    def test_simulated_portfolio_reconciliation(self) -> None:
        initial_cash = 200000.0
        portfolio = SimulatedPortfolio(cash=initial_cash)

        fill_buy = SimulatedFill(
            order_id="1", symbol="2330", side="BUY", quantity=1000, price=100.0, filled_at=None, fee=142.0, slippage=8.0
        )
        portfolio.apply_fill(fill_buy)
        self.assertEqual(portfolio.cash, 99850.0)

        fill_sell = SimulatedFill(
            order_id="2", symbol="2330", side="SELL", quantity=1000, price=110.0, filled_at=None, fee=157.0, tax=330.0, slippage=13.0
        )
        portfolio.apply_fill(fill_sell)
        self.assertEqual(portfolio.cash, 209350.0)

        pos = portfolio.position_for("2330")
        self.assertEqual(pos.realized_pnl, 9350.0)
        self.assertEqual(portfolio.cash - initial_cash, pos.realized_pnl)

    def test_safety_wording_not_present(self) -> None:
        banned_phrases = (
            "broker api",
            "real order",
            "order execution",
            "auto trading",
            "semi-auto trading",
            "investment recommendation",
            "guaranteed profit",
            "guaranteed return",
            "safe to invest",
        )

        import tw_stock_tool.paper_trading.models as models

        docstrings = [
            models.__doc__,
            models.SimulatedOrder.__doc__,
            models.SimulatedFill.__doc__,
            models.SimulatedPosition.__doc__,
            models.SimulatedPortfolio.__doc__,
            models.SimulatedTradeLog.__doc__,
        ]

        for doc in docstrings:
            if doc:
                text = doc.lower()
                for phrase in banned_phrases:
                    self.assertNotIn(phrase, text)
