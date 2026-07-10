import math
import unittest

from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedOrder,
    SimulatedPortfolio,
)
from tw_stock_tool.paper_trading.runtime import (
    SimulatedPaperTradingRuntimeState,
    SimulatedPendingOrderState,
)


def make_order(symbol: str = "2330", side: str = "BUY") -> SimulatedOrder:
    return SimulatedOrder(
        order_id=f"{symbol}-{side}",
        symbol=symbol,
        side=side,  # type: ignore[arg-type]
        quantity=10,
        signal_time="2026-01-01",
    )


class TestSimulatedPendingOrderState(unittest.TestCase):
    def test_valid_buy(self) -> None:
        order = make_order()
        state = SimulatedPendingOrderState(order, 100.0)
        self.assertIs(state.order, order)

    def test_valid_sell(self) -> None:
        order = make_order(side="SELL")
        state = SimulatedPendingOrderState(order, 100.0)
        self.assertIs(state.order, order)

    def test_buy_reserved_notional(self) -> None:
        state = SimulatedPendingOrderState(make_order(), 100.0)
        self.assertEqual(state.reserved_buy_notional, 1000.0)

    def test_sell_reservation_is_zero(self) -> None:
        state = SimulatedPendingOrderState(make_order(side="SELL"), 100.0)
        self.assertEqual(state.reserved_buy_notional, 0.0)

    def test_int_price_is_normalized(self) -> None:
        state = SimulatedPendingOrderState(make_order(), 100)
        self.assertEqual(state.reference_price, 100.0)
        self.assertIs(type(state.reference_price), float)

    def test_float_price(self) -> None:
        state = SimulatedPendingOrderState(make_order(), 100.5)
        self.assertEqual(state.reference_price, 100.5)

    def test_non_order_is_rejected(self) -> None:
        with self.assertRaises(PaperTradingModelError):
            SimulatedPendingOrderState("not an order", 100.0)  # type: ignore[arg-type]

    def test_boolean_price_is_rejected(self) -> None:
        with self.assertRaises(PaperTradingModelError):
            SimulatedPendingOrderState(make_order(), True)

    def test_string_price_is_rejected(self) -> None:
        with self.assertRaises(PaperTradingModelError):
            SimulatedPendingOrderState(make_order(), "100")  # type: ignore[arg-type]

    def test_none_price_is_rejected(self) -> None:
        with self.assertRaises(PaperTradingModelError):
            SimulatedPendingOrderState(make_order(), None)  # type: ignore[arg-type]

    def test_zero_price_is_rejected(self) -> None:
        with self.assertRaises(PaperTradingModelError):
            SimulatedPendingOrderState(make_order(), 0.0)

    def test_negative_price_is_rejected(self) -> None:
        with self.assertRaises(PaperTradingModelError):
            SimulatedPendingOrderState(make_order(), -1.0)

    def test_nan_price_is_rejected(self) -> None:
        with self.assertRaises(PaperTradingModelError):
            SimulatedPendingOrderState(make_order(), math.nan)

    def test_positive_infinity_is_rejected(self) -> None:
        with self.assertRaises(PaperTradingModelError):
            SimulatedPendingOrderState(make_order(), math.inf)

    def test_negative_infinity_is_rejected(self) -> None:
        with self.assertRaises(PaperTradingModelError):
            SimulatedPendingOrderState(make_order(), -math.inf)


class TestSimulatedPaperTradingRuntimeState(unittest.TestCase):
    def test_valid_empty_runtime(self) -> None:
        state = SimulatedPaperTradingRuntimeState(SimulatedPortfolio(cash=1000.0))
        self.assertIsInstance(state, SimulatedPaperTradingRuntimeState)

    def test_exact_portfolio_identity(self) -> None:
        portfolio = SimulatedPortfolio(cash=1000.0)
        state = SimulatedPaperTradingRuntimeState(portfolio)
        self.assertIs(state.portfolio, portfolio)

    def test_default_pending_mapping_is_empty(self) -> None:
        state = SimulatedPaperTradingRuntimeState(SimulatedPortfolio(cash=1000.0))
        self.assertEqual(state.pending_orders, {})

    def test_default_pending_mapping_is_not_shared(self) -> None:
        first = SimulatedPaperTradingRuntimeState(SimulatedPortfolio(cash=1000.0))
        second = SimulatedPaperTradingRuntimeState(SimulatedPortfolio(cash=1000.0))
        self.assertIsNot(first.pending_orders, second.pending_orders)

    def test_valid_multiple_symbol_pending_mapping(self) -> None:
        first = SimulatedPendingOrderState(make_order("2330"), 100.0)
        second = SimulatedPendingOrderState(make_order("2317"), 50.0)
        pending = {"2330": first, "2317": second}
        state = SimulatedPaperTradingRuntimeState(
            SimulatedPortfolio(cash=1000.0), pending
        )
        self.assertIs(state.pending_orders, pending)
        self.assertIs(state.pending_orders["2330"], first)
        self.assertIs(state.pending_orders["2317"], second)

    def test_mapping_key_must_match_order_symbol(self) -> None:
        pending = {"2317": SimulatedPendingOrderState(make_order("2330"), 100.0)}
        with self.assertRaises(PaperTradingModelError):
            SimulatedPaperTradingRuntimeState(
                SimulatedPortfolio(cash=1000.0), pending
            )

    def test_blank_key_is_rejected(self) -> None:
        pending = {" ": SimulatedPendingOrderState(make_order(), 100.0)}
        with self.assertRaises(PaperTradingModelError):
            SimulatedPaperTradingRuntimeState(
                SimulatedPortfolio(cash=1000.0), pending
            )

    def test_non_string_key_is_rejected(self) -> None:
        pending = {2330: SimulatedPendingOrderState(make_order(), 100.0)}
        with self.assertRaises(PaperTradingModelError):
            SimulatedPaperTradingRuntimeState(
                SimulatedPortfolio(cash=1000.0), pending  # type: ignore[arg-type]
            )

    def test_invalid_state_value_is_rejected(self) -> None:
        with self.assertRaises(PaperTradingModelError):
            SimulatedPaperTradingRuntimeState(
                SimulatedPortfolio(cash=1000.0),
                {"2330": make_order()},  # type: ignore[dict-item]
            )

    def test_non_dictionary_mapping_is_rejected(self) -> None:
        with self.assertRaises(PaperTradingModelError):
            SimulatedPaperTradingRuntimeState(
                SimulatedPortfolio(cash=1000.0), []  # type: ignore[arg-type]
            )

    def test_total_reservation_across_multiple_buy_orders(self) -> None:
        pending = {
            "2330": SimulatedPendingOrderState(make_order("2330"), 100.0),
            "2317": SimulatedPendingOrderState(make_order("2317"), 50.0),
        }
        state = SimulatedPaperTradingRuntimeState(
            SimulatedPortfolio(cash=1000.0), pending
        )
        self.assertEqual(state.total_reserved_buy_notional, 1500.0)

    def test_mixed_buy_and_sell_reservation(self) -> None:
        pending = {
            "2330": SimulatedPendingOrderState(make_order("2330"), 100.0),
            "2317": SimulatedPendingOrderState(
                make_order("2317", side="SELL"), 50.0
            ),
        }
        state = SimulatedPaperTradingRuntimeState(
            SimulatedPortfolio(cash=1000.0), pending
        )
        self.assertEqual(state.total_reserved_buy_notional, 1000.0)

    def test_empty_reservation_total_is_zero(self) -> None:
        state = SimulatedPaperTradingRuntimeState(SimulatedPortfolio(cash=1000.0))
        self.assertEqual(state.total_reserved_buy_notional, 0.0)

    def test_reservation_total_type_is_float(self) -> None:
        state = SimulatedPaperTradingRuntimeState(SimulatedPortfolio(cash=1000.0))
        self.assertIs(type(state.total_reserved_buy_notional), float)

    def test_non_portfolio_is_rejected(self) -> None:
        with self.assertRaises(PaperTradingModelError):
            SimulatedPaperTradingRuntimeState("not a portfolio")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
