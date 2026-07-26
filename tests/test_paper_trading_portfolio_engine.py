"""
Unit tests for multi-symbol simulated portfolio trading engine facade.
"""

import unittest
import pandas as pd

from tw_stock_tool.paper_trading.models import PaperTradingModelError
from tw_stock_tool.paper_trading.portfolio_engine import (
    run_simulated_portfolio_trading_result,
)
from tw_stock_tool.paper_trading.portfolio_results import SimulatedPortfolioTradingResult
from tw_stock_tool.simulated_paper_trading_guard.adapter import (
    SimulatedPaperTradingGuardDecision,
)


def _make_sample_df(signals: list[tuple[str, int, int]], close_prices: list[float] | None = None) -> pd.DataFrame:
    dates = [pd.Timestamp(s[0]) for s in signals]
    closes = close_prices if close_prices is not None else [100.0 + i for i in range(len(signals))]
    opens = [c - 1.0 for c in closes]
    entries = [bool(s[1]) for s in signals]
    exits = [bool(s[2]) for s in signals]

    return pd.DataFrame(
        {
            "Open": opens,
            "Close": closes,
            "entry_signal": entries,
            "exit_signal": exits,
        },
        index=dates,
    )


class TestPortfolioEngineFacade(unittest.TestCase):
    def test_successful_two_symbol_execution(self):
        df1 = _make_sample_df(
            [
                ("2026-01-02", 1, 0),
                ("2026-01-05", 0, 0),
                ("2026-01-06", 0, 1),
                ("2026-01-07", 0, 0),
            ],
            close_prices=[100.0, 105.0, 110.0, 112.0],
        )
        df2 = _make_sample_df(
            [
                ("2026-01-02", 0, 0),
                ("2026-01-05", 1, 0),
                ("2026-01-06", 0, 0),
                ("2026-01-07", 0, 0),
            ],
            close_prices=[50.0, 52.0, 55.0, 56.0],
        )

        dataframes = {"2330.TW": df1, "2317.TW": df2}
        last_prices = {"2330.TW": 112.0, "2317.TW": 56.0}

        res = run_simulated_portfolio_trading_result(
            dataframes,
            initial_cash=200000.0,
            last_prices=last_prices,
            quantity_per_trade=1000,
            strategy="ma_cross",
            strategy_metadata={"period": "1y"},
        )

        self.assertIsInstance(res, SimulatedPortfolioTradingResult)
        self.assertEqual(res.initial_cash, 200000.0)
        self.assertGreater(len(res.audit_log), 0)

    def test_two_symbols_compete_for_shared_cash_deterministically(self):
        # Two symbols generate BUY signal at the exact same timestamp ("2026-01-02").
        # Shared cash = 120,000. Trade quantity = 1,000 @ Open 100.0 -> requires 100,000 per fill.
        # Combined required = 200,000 > 120,000. Single fill (100,000) <= 120,000.
        # Coordinator lexical symbol ordering processes "2317.TW" before "2330.TW".
        df1 = _make_sample_df([("2026-01-02", 1, 0), ("2026-01-05", 0, 0)], close_prices=[100.0, 101.0])
        df2 = _make_sample_df([("2026-01-02", 1, 0), ("2026-01-05", 0, 0)], close_prices=[100.0, 101.0])

        dataframes = {"2330.TW": df1, "2317.TW": df2}
        last_prices = {"2330.TW": 101.0, "2317.TW": 101.0}

        res = run_simulated_portfolio_trading_result(
            dataframes,
            initial_cash=120000.0,
            last_prices=last_prices,
            quantity_per_trade=1000,
        )

        # 2317.TW filled first; 2330.TW fill failed due to insufficient shared cash
        self.assertEqual(res.fill_count, 1)
        self.assertEqual(res.fills[0].symbol, "2317.TW")
        self.assertEqual(res.final_cash, 20000.0)
        self.assertEqual(res.open_position_count, 1)

        failed_fills = [r for r in res.audit_log if r.event_type == "fill_failed"]
        self.assertEqual(len(failed_fills), 1)
        self.assertEqual(failed_fills[0].symbol, "2330.TW")

    def test_same_timestamp_orders_follow_deterministic_symbol_order(self):
        # Both symbols generate BUY signal at timestamp "2026-01-02" with sufficient cash (500,000).
        df1 = _make_sample_df([("2026-01-02", 1, 0), ("2026-01-05", 0, 0)])
        df2 = _make_sample_df([("2026-01-02", 1, 0), ("2026-01-05", 0, 0)])

        dataframes = {"2330.TW": df1, "2317.TW": df2}
        last_prices = {"2330.TW": 102.0, "2317.TW": 102.0}

        res1 = run_simulated_portfolio_trading_result(dataframes, initial_cash=500000.0, last_prices=last_prices, quantity_per_trade=1000)
        res2 = run_simulated_portfolio_trading_result(dataframes, initial_cash=500000.0, last_prices=last_prices, quantity_per_trade=1000)

        # Lexical symbol ordering ("2317.TW" < "2330.TW")
        self.assertEqual(len(res1.orders), 2)
        self.assertEqual(res1.orders[0].symbol, "2317.TW")
        self.assertEqual(res1.orders[1].symbol, "2330.TW")

        # Deterministic sequence on repeated run
        self.assertEqual([o.symbol for o in res1.orders], [o.symbol for o in res2.orders])

    def test_differing_dates_and_same_timestamp_entry_signals(self):
        df1 = _make_sample_df([("2026-01-02", 1, 0), ("2026-01-05", 0, 0)])
        df2 = _make_sample_df([("2026-01-02", 1, 0), ("2026-01-06", 0, 0)])

        dataframes = {"2330.TW": df1, "2317.TW": df2}
        last_prices = {"2330.TW": 102.0, "2317.TW": 102.0}

        res = run_simulated_portfolio_trading_result(
            dataframes,
            initial_cash=500000.0,
            last_prices=last_prices,
            quantity_per_trade=1000,
        )

        self.assertIsInstance(res, SimulatedPortfolioTradingResult)
        self.assertGreater(len(res.orders), 0)

    def test_guard_decision_rejection(self):
        df1 = _make_sample_df([("2026-01-02", 1, 0), ("2026-01-05", 0, 0)], close_prices=[100.0, 102.0])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 102.0}

        guard_decision = SimulatedPaperTradingGuardDecision(is_allowed=False, reasons=("test_rejection",))

        res = run_simulated_portfolio_trading_result(
            dataframes,
            initial_cash=120000.0,
            last_prices=last_prices,
            quantity_per_trade=1000,
            guard_decision=guard_decision,
        )

        self.assertGreater(res.rejection_count, 0)

    def test_open_and_closed_positions(self):
        df1 = _make_sample_df(
            [
                ("2026-01-02", 1, 0),
                ("2026-01-05", 0, 1),
                ("2026-01-06", 0, 0),
            ],
            close_prices=[100.0, 105.0, 120.0],
        )

        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 120.0}

        res = run_simulated_portfolio_trading_result(
            dataframes,
            initial_cash=150000.0,
            last_prices=last_prices,
            quantity_per_trade=1000,
        )

        self.assertEqual(res.open_position_count, 0)
        self.assertGreater(res.realized_pnl, 0)

    def test_terminal_pending_orders(self):
        df1 = _make_sample_df(
            [("2026-01-02", 1, 0)],
            close_prices=[100.0],
        )

        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 100.0}

        res = run_simulated_portfolio_trading_result(
            dataframes,
            initial_cash=200000.0,
            last_prices=last_prices,
            quantity_per_trade=1000,
        )

        self.assertEqual(len(res.pending_orders), 1)

    def test_terminal_exit_signal_leaves_pending_sell(self):
        # Bar 1 (01-02): BUY signal -> pending BUY created
        # Bar 2 (01-05): pending BUY fills -> position created. exit_signal=1 -> pending SELL created
        # No Bar 3! Pending SELL order remains at terminal.
        df1 = _make_sample_df(
            [
                ("2026-01-02", 1, 0),
                ("2026-01-05", 0, 1),
            ],
            close_prices=[100.0, 105.0],
        )

        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 105.0}

        res = run_simulated_portfolio_trading_result(
            dataframes,
            initial_cash=200000.0,
            last_prices=last_prices,
            quantity_per_trade=1000,
        )

        self.assertEqual(len(res.pending_orders), 1)
        self.assertEqual(res.pending_orders[0].side, "SELL")
        self.assertEqual(res.pending_orders[0].symbol, "2330.TW")
        self.assertEqual(res.pending_orders[0].quantity, 1000)
        self.assertEqual(res.open_position_count, 1)

    def test_zero_initial_cash_accepted(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)], close_prices=[100.0])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 100.0}

        res = run_simulated_portfolio_trading_result(
            dataframes,
            initial_cash=0.0,
            last_prices=last_prices,
        )

        self.assertEqual(res.initial_cash, 0.0)
        self.assertIsNone(res.total_return_pct)

    def test_invalid_initial_cash_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 100.0}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=-1.0, last_prices=last_prices)

    def test_initial_cash_numeric_string_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 100.0}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash="100000", last_prices=last_prices)

    def test_fee_rate_numeric_string_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 100.0}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices, fee_rate="0.001425")

    def test_tax_rate_numeric_string_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 100.0}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices, tax_rate="0.003")

    def test_slippage_per_share_numeric_string_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 100.0}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices, slippage_per_share="1.5")

    def test_last_price_numeric_string_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": "100.0"}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices)

    def test_quantity_numeric_string_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 100.0}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices, quantity_per_trade="1000")

    def test_quantity_float_form_integer_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 100.0}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices, quantity_per_trade=1000.0)

    def test_last_price_bool_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": True}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices)

    def test_last_price_nan_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": float("nan")}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices)

    def test_last_price_positive_infinity_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": float("inf")}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices)

    def test_last_price_negative_infinity_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": float("-inf")}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices)

    def test_rate_nan_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 100.0}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices, fee_rate=float("nan"))

    def test_rate_infinity_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 100.0}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices, fee_rate=float("inf"))

    def test_dataframes_and_last_prices_validation(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result([], initial_cash=100000.0, last_prices={"2330.TW": 100.0})

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result({}, initial_cash=100000.0, last_prices={})

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result({" ": df1}, initial_cash=100000.0, last_prices={" ": 100.0})

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result({"2330.TW": "not_a_df"}, initial_cash=100000.0, last_prices={"2330.TW": 100.0})

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result({"2330.TW": df1}, initial_cash=100000.0, last_prices={"2330.TW": -50.0})

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result({"2330.TW": df1}, initial_cash=100000.0, last_prices={"2330.TW": 100.0, "2317.TW": 50.0})

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result({"2330.TW": df1, "2317.TW": df1}, initial_cash=100000.0, last_prices={"2330.TW": 100.0})

    def test_caller_mutation_protection(self):
        df1 = _make_sample_df([("2026-01-02", 1, 0)], close_prices=[100.0])
        df1_copy = df1.copy()
        dataframes = {"2330.TW": df1}
        dataframes_keys = list(dataframes.keys())
        last_prices = {"2330.TW": 100.0}

        run_simulated_portfolio_trading_result(
            dataframes,
            initial_cash=200000.0,
            last_prices=last_prices,
        )

        self.assertEqual(list(dataframes.keys()), dataframes_keys)
        pd.testing.assert_frame_equal(dataframes["2330.TW"], df1_copy)


from decimal import Decimal
from fractions import Fraction
import numpy as np

from tw_stock_tool.paper_trading.models import PaperTradingModelError, SimulatedOrder, SimulatedPortfolio, SimulatedPosition
from tw_stock_tool.paper_trading.portfolio_engine import (
    run_simulated_portfolio_trading_result,
    _normalize_optional_risk_notional,
    _normalize_optional_risk_quantity,
    _build_composite_guard_decision_provider,
)
from tw_stock_tool.paper_trading.portfolio_results import SimulatedPortfolioTradingResult
from tw_stock_tool.simulated_paper_trading_guard.adapter import (
    SimulatedPaperTradingGuardDecision,
)


class TestPortfolioEngineRiskFlags(unittest.TestCase):
    def setUp(self):
        self.df1 = _make_sample_df(
            [
                ("2026-01-02", 1, 0),
                ("2026-01-05", 0, 0),
                ("2026-01-06", 0, 1),
            ],
            close_prices=[100.0, 105.0, 110.0],
        )
        self.df2 = _make_sample_df(
            [
                ("2026-01-02", 1, 0),
                ("2026-01-05", 0, 0),
                ("2026-01-06", 0, 0),
            ],
            close_prices=[200.0, 205.0, 210.0],
        )
        self.dataframes = {"2330.TW": self.df1, "2317.TW": self.df2}
        self.last_prices = {"2330.TW": 110.0, "2317.TW": 210.0}

    # ------------------------------------------------------------------
    # Validation Unit Tests
    # ------------------------------------------------------------------

    def test_normalize_optional_risk_notional_valid(self):
        self.assertIsNone(_normalize_optional_risk_notional("test", None))
        self.assertEqual(_normalize_optional_risk_notional("test", 100), 100.0)
        self.assertEqual(_normalize_optional_risk_notional("test", 100.5), 100.5)

    def test_normalize_optional_risk_notional_invalid(self):
        for invalid in [0, 0.0, -10, -10.5, True, False, np.bool_(True), "100", float("nan"), float("inf"), float("-inf"), Decimal("100"), Fraction(1, 2)]:
            with self.assertRaises(PaperTradingModelError):
                _normalize_optional_risk_notional("test", invalid)

    def test_normalize_optional_risk_quantity_valid(self):
        self.assertIsNone(_normalize_optional_risk_quantity("test", None))
        self.assertEqual(_normalize_optional_risk_quantity("test", 1000), 1000)

    def test_normalize_optional_risk_quantity_invalid(self):
        for invalid in [0, -10, True, False, np.bool_(True), 1000.0, 1000.5, "1000", Decimal("1000"), Fraction(1000, 1)]:
            with self.assertRaises(PaperTradingModelError):
                _normalize_optional_risk_quantity("test", invalid)

    def test_facade_notional_flag_invalid_types_raise(self):
        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(self.dataframes, initial_cash=500000.0, last_prices=self.last_prices, max_order_notional="100000")

    def test_facade_quantity_flag_invalid_types_raise(self):
        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(self.dataframes, initial_cash=500000.0, last_prices=self.last_prices, max_position_quantity=1000.0)  # type: ignore

    # ------------------------------------------------------------------
    # Individual Risk Limits Tests
    # ------------------------------------------------------------------

    def test_max_order_notional_limit(self):
        # Quantity = 1000, signal time Open = 99.0 -> Order notional = 99,000
        res_allowed = run_simulated_portfolio_trading_result(
            self.dataframes,
            initial_cash=500000.0,
            last_prices=self.last_prices,
            quantity_per_trade=1000,
            max_order_notional=100000.0,
        )
        self.assertGreater(res_allowed.fill_count, 0)

        # Cap at 50,000 -> 99,000 > 50,000 -> Blocked
        res_blocked = run_simulated_portfolio_trading_result(
            self.dataframes,
            initial_cash=500000.0,
            last_prices=self.last_prices,
            quantity_per_trade=1000,
            max_order_notional=50000.0,
        )
        self.assertEqual(res_blocked.fill_count, 0)
        self.assertGreater(res_blocked.rejection_count, 0)
        self.assertIn("order_notional exceeds max_order_notional", res_blocked.rejections[0].reasons)

    def test_max_position_quantity_limit(self):
        res_blocked = run_simulated_portfolio_trading_result(
            self.dataframes,
            initial_cash=500000.0,
            last_prices=self.last_prices,
            quantity_per_trade=1000,
            max_position_quantity=500,
        )
        self.assertEqual(res_blocked.fill_count, 0)
        self.assertGreater(res_blocked.rejection_count, 0)
        self.assertIn("projected_position_quantity exceeds max_position_quantity", res_blocked.rejections[0].reasons)

    def test_max_position_notional_limit(self):
        res_blocked = run_simulated_portfolio_trading_result(
            self.dataframes,
            initial_cash=500000.0,
            last_prices=self.last_prices,
            quantity_per_trade=1000,
            max_position_notional=50000.0,
        )
        self.assertEqual(res_blocked.fill_count, 0)
        self.assertGreater(res_blocked.rejection_count, 0)
        self.assertIn("projected_position_notional exceeds max_position_notional", res_blocked.rejections[0].reasons)

    def test_max_total_exposure_limit(self):
        res_blocked = run_simulated_portfolio_trading_result(
            self.dataframes,
            initial_cash=500000.0,
            last_prices=self.last_prices,
            quantity_per_trade=1000,
            max_total_exposure=50000.0,
        )
        self.assertEqual(res_blocked.fill_count, 0)
        self.assertGreater(res_blocked.rejection_count, 0)
        self.assertIn("projected_total_exposure exceeds max_total_exposure", res_blocked.rejections[0].reasons)

    # ------------------------------------------------------------------
    # Shared Total Exposure & Reservation Lifecycle
    # ------------------------------------------------------------------

    def test_shared_total_exposure_between_same_timestamp_symbols(self):
        # Both 2330.TW (Open 99.0, notional 99k) and 2317.TW (Open 199.0, notional 199k) BUY on 2026-01-02.
        # Lexical order: 2317.TW evaluated first. 199k <= 250k exposure -> Accepted.
        # 2317.TW reserved 199k. Next 2330.TW evaluated: 199k + 99k = 298k > 250k -> Blocked.
        res = run_simulated_portfolio_trading_result(
            self.dataframes,
            initial_cash=1000000.0,
            last_prices=self.last_prices,
            quantity_per_trade=1000,
            max_total_exposure=250000.0,
        )
        rej = res.rejections
        self.assertEqual(len(rej), 1)
        self.assertEqual(rej[0].candidate_order.symbol, "2330.TW")
        self.assertIn("projected_total_exposure exceeds max_total_exposure", rej[0].reasons)



    def test_reservation_lifecycle_and_terminal_pending_reservation(self):
        # BUY signal on last row ("2026-01-06") -> order accepted and stays in pending state at simulation end.
        df_terminal = _make_sample_df(
            [
                ("2026-01-02", 0, 0),
                ("2026-01-05", 0, 0),
                ("2026-01-06", 1, 0),
            ],
            close_prices=[100.0, 105.0, 110.0],
        )
        res = run_simulated_portfolio_trading_result(
            {"2330.TW": df_terminal},
            initial_cash=500000.0,
            last_prices={"2330.TW": 110.0},
            quantity_per_trade=1000,
            max_total_exposure=150000.0,
        )
        self.assertEqual(len(res.pending_orders), 1)
        self.assertEqual(res.pending_orders[0].reserved_buy_notional, 109000.0)

    # ------------------------------------------------------------------
    # SELL Portfolio-Risk Bypass
    # ------------------------------------------------------------------

    def test_sell_order_bypasses_portfolio_risk(self):
        # 2330.TW BUY on day 1 (99k notional, allowed under 100k cap).
        # On day 3, SELL signal (Open 109.0, notional 109k > 100k cap).
        # SELL passes risk guard cleanly via sell_bypass.
        df_sell = _make_sample_df(
            [
                ("2026-01-02", 1, 0),
                ("2026-01-05", 0, 0),
                ("2026-01-06", 0, 1),
                ("2026-01-07", 0, 0),
            ],
            close_prices=[100.0, 105.0, 110.0, 112.0],
        )
        res = run_simulated_portfolio_trading_result(
            {"2330.TW": df_sell},
            initial_cash=500000.0,
            last_prices={"2330.TW": 112.0},
            quantity_per_trade=1000,
            max_order_notional=100000.0,
        )
        self.assertEqual(res.fill_count, 2)  # BUY fill + SELL fill
        self.assertEqual(res.rejection_count, 0)

    # ------------------------------------------------------------------
    # Caller Guard Composition
    # ------------------------------------------------------------------

    def test_composite_guard_decision_provider_fixed_and_custom_together_rejected(self):
        risk_prov = lambda _o, _p: SimulatedPaperTradingGuardDecision.allow()
        fixed = SimulatedPaperTradingGuardDecision.allow()
        custom = lambda _o, _p: SimulatedPaperTradingGuardDecision.allow()
        with self.assertRaises(ValueError):
            _build_composite_guard_decision_provider(
                portfolio_risk_provider=risk_prov,
                fixed_guard_decision=fixed,
                custom_guard_decision_provider=custom,
            )

    def test_composite_guard_decision_provider_evaluates_all_sources_and_namespaces_metadata(self):
        risk_prov = lambda _o, _p: SimulatedPaperTradingGuardDecision.allow(metadata={"r": 1})
        custom_prov = lambda _o, _p: SimulatedPaperTradingGuardDecision.allow(metadata={"c": 2})

        comp = _build_composite_guard_decision_provider(
            portfolio_risk_provider=risk_prov,
            custom_guard_decision_provider=custom_prov,
        )
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=1)
        port = SimulatedPortfolio(cash=1000.0)

        dec = comp(order, port)
        self.assertTrue(dec.is_allowed)
        self.assertEqual(dec.metadata, {"portfolio_risk_guard": {"r": 1}, "custom_guard": {"c": 2}})

    def test_composite_guard_decision_provider_combines_reasons_in_order_and_deduplicates(self):
        fixed = SimulatedPaperTradingGuardDecision.block(reasons=["r1", "r2"], metadata={"f": 1})
        risk_prov = lambda _o, _p: SimulatedPaperTradingGuardDecision.block(reasons=["r2", "r3"])

        comp = _build_composite_guard_decision_provider(
            portfolio_risk_provider=risk_prov,
            fixed_guard_decision=fixed,
        )
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=1)
        port = SimulatedPortfolio(cash=1000.0)

        dec = comp(order, port)
        self.assertFalse(dec.is_allowed)
        self.assertEqual(dec.reasons, ("r1", "r2", "r3"))

    def test_sell_order_does_not_bypass_fixed_guard_block(self):
        fixed = SimulatedPaperTradingGuardDecision.block(reasons=["fixed_blocked"])

        res = run_simulated_portfolio_trading_result(
            {"2330.TW": self.df1},
            initial_cash=500000.0,
            last_prices={"2330.TW": 110.0},
            max_order_notional=100000.0,
            guard_decision=fixed,
        )
        self.assertEqual(res.fill_count, 0)
        self.assertGreater(res.rejection_count, 0)
        self.assertIn("fixed_blocked", res.rejections[0].reasons)

    def test_sell_order_does_not_bypass_custom_guard_block(self):
        def custom(order, _portfolio):
            return (SimulatedPaperTradingGuardDecision.block(reasons=["custom_sell_blocked"])
                    if order.side == "SELL" else SimulatedPaperTradingGuardDecision.allow())
        res = run_simulated_portfolio_trading_result(
            {"2330.TW": self.df1}, initial_cash=500000.0,
            last_prices={"2330.TW": 110.0}, max_order_notional=100000.0,
            guard_decision_provider=custom,
        )
        self.assertEqual(res.fill_count, 1)
        self.assertIn("custom_sell_blocked", res.rejections[0].reasons)

    def test_risk_notional_overflow_is_model_error_in_helper_and_facade(self):
        with self.assertRaises(PaperTradingModelError):
            _normalize_optional_risk_notional("max_order_notional", 10 ** 10000)
        for name in ("max_order_notional", "max_position_notional", "max_total_exposure"):
            with self.subTest(name=name), self.assertRaises(PaperTradingModelError):
                run_simulated_portfolio_trading_result(
                    self.dataframes, initial_cash=500000.0, last_prices=self.last_prices,
                    **{name: 10 ** 10000},
                )

    def test_each_risk_limit_allows_below_and_equal_and_blocks_above(self):
        # Signal Open is 100.0, so order/projected notional is 100,000 and quantity is 1,000.
        df = _make_sample_df([("2026-01-02", 1, 0), ("2026-01-05", 0, 0)], [101.0, 101.0])
        cases = (
            ("max_order_notional", (100001.0, 100000.0, 99999.0), "order_notional exceeds max_order_notional"),
            ("max_position_quantity", (1001, 1000, 999), "projected_position_quantity exceeds max_position_quantity"),
            ("max_position_notional", (100001.0, 100000.0, 99999.0), "projected_position_notional exceeds max_position_notional"),
            ("max_total_exposure", (100001.0, 100000.0, 99999.0), "projected_total_exposure exceeds max_total_exposure"),
        )
        for name, (below, equal, above), reason in cases:
            for limit in (below, equal):
                with self.subTest(name=name, limit=limit):
                    res = run_simulated_portfolio_trading_result({"2330.TW": df}, initial_cash=500000.0, last_prices={"2330.TW": 100.0}, quantity_per_trade=1000, **{name: limit})
                    self.assertEqual(res.rejection_count, 0)
            with self.subTest(name=name, limit=above):
                res = run_simulated_portfolio_trading_result({"2330.TW": df}, initial_cash=500000.0, last_prices={"2330.TW": 100.0}, quantity_per_trade=1000, **{name: above})
                self.assertEqual(res.rejection_count, 1)
                self.assertIn(reason, res.rejections[0].reasons)

    def test_composite_guard_empty_metadata_and_full_matrix(self):
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=1)
        port = SimulatedPortfolio(cash=1000.0)
        allow = SimulatedPaperTradingGuardDecision.allow()
        block = SimulatedPaperTradingGuardDecision.block(reasons=["blocked"])
        for fixed_decision, risk_decision, expected in ((allow, allow, True), (block, allow, False), (allow, block, False), (block, block, False)):
            calls = []
            def risk(_o, _p, decision=risk_decision):
                calls.append("risk")
                return decision
            dec = _build_composite_guard_decision_provider(portfolio_risk_provider=risk, fixed_guard_decision=fixed_decision)(order, port)
            self.assertEqual(dec.is_allowed, expected)
            self.assertEqual(calls, ["risk"])
            self.assertEqual(dec.metadata, {"fixed_guard": {}, "portfolio_risk_guard": {}})
        for risk_decision, custom_decision, expected in ((allow, allow, True), (block, allow, False), (allow, block, False), (block, block, False)):
            calls = []
            def risk(_o, _p, decision=risk_decision):
                calls.append("risk")
                return decision
            def custom(_o, _p, decision=custom_decision):
                calls.append("custom")
                return decision
            dec = _build_composite_guard_decision_provider(portfolio_risk_provider=risk, custom_guard_decision_provider=custom)(order, port)
            self.assertEqual(dec.is_allowed, expected)
            self.assertEqual(calls, ["risk", "custom"])
            self.assertEqual(dec.metadata, {"portfolio_risk_guard": {}, "custom_guard": {}})
        self.assertEqual(_build_composite_guard_decision_provider(portfolio_risk_provider=lambda _o, _p: allow)(order, port).metadata, {"portfolio_risk_guard": {}})
        blocked = _build_composite_guard_decision_provider(portfolio_risk_provider=lambda _o, _p: block)(order, port)
        self.assertEqual(blocked.metadata, {"portfolio_risk_guard": {}})
        self.assertEqual(blocked.reasons, ("blocked",))
        dedup = _build_composite_guard_decision_provider(
            portfolio_risk_provider=lambda _o, _p: SimulatedPaperTradingGuardDecision.block(reasons=["duplicate", "risk_only"]),
            custom_guard_decision_provider=lambda _o, _p: SimulatedPaperTradingGuardDecision.block(reasons=["duplicate", "custom_only"]),
        )(order, port)
        self.assertEqual(dedup.reasons, ("duplicate", "risk_only", "custom_only"))

    def test_composite_guard_invalid_and_exception_contracts(self):
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=1)
        port = SimulatedPortfolio(cash=1000.0)
        with self.assertRaises(PaperTradingModelError):
            _build_composite_guard_decision_provider(portfolio_risk_provider=lambda _o, _p: SimulatedPaperTradingGuardDecision.allow(), custom_guard_decision_provider=lambda _o, _p: object())(order, port)
        for risk in (SimulatedPaperTradingGuardDecision.allow(), SimulatedPaperTradingGuardDecision.block(reasons=["risk_block"])):
            with self.subTest(risk_allowed=risk.is_allowed), self.assertRaisesRegex(RuntimeError, "custom failure"):
                _build_composite_guard_decision_provider(portfolio_risk_provider=lambda _o, _p, decision=risk: decision, custom_guard_decision_provider=lambda _o, _p: (_ for _ in ()).throw(RuntimeError("custom failure")))(order, port)

    def test_as_of_cross_symbol_exposure_and_mapping_order_invariance(self):
        a = _make_sample_df([("2026-01-02", 1, 0), ("2026-01-05", 0, 0), ("2026-01-06", 0, 0), ("2026-01-08", 0, 0), ("2026-01-09", 0, 0)], [101.0, 101.0, 121.0, 121.0, 10001.0])
        b = _make_sample_df([("2026-01-08", 1, 0), ("2026-01-09", 0, 0)], [51.0, 51.0])
        kwargs = dict(initial_cash=500000.0, last_prices={"2330.TW": 10000.0, "2317.TW": 50.0}, quantity_per_trade=1000, max_total_exposure=170000.0)
        first = run_simulated_portfolio_trading_result({"2330.TW": a, "2317.TW": b}, **kwargs)
        second = run_simulated_portfolio_trading_result({"2317.TW": b, "2330.TW": a}, **kwargs)
        self.assertEqual(first.rejection_count, 0)
        self.assertEqual([x.symbol for x in first.orders], [x.symbol for x in second.orders])
        self.assertEqual([(x.candidate_order.symbol, x.reasons) for x in first.rejections], [(x.candidate_order.symbol, x.reasons) for x in second.rejections])
        self.assertEqual(first.pending_orders, second.pending_orders)
        self.assertEqual([fill.symbol for fill in first.fills], ["2330.TW", "2317.TW"])
        self.assertEqual([order.symbol for order in first.orders].count("2317.TW"), 1)
        same_a = _make_sample_df([("2026-02-02", 1, 0), ("2026-02-03", 0, 0)], [101.0, 101.0])
        same_b = _make_sample_df([("2026-02-02", 1, 0), ("2026-02-03", 0, 0)], [201.0, 201.0])
        shared = dict(initial_cash=1000000.0, last_prices={"2330.TW": 100.0, "2317.TW": 200.0}, quantity_per_trade=1000, max_total_exposure=250000.0)
        ordered = run_simulated_portfolio_trading_result({"2330.TW": same_a, "2317.TW": same_b}, **shared)
        reversed_order = run_simulated_portfolio_trading_result({"2317.TW": same_b, "2330.TW": same_a}, **shared)
        self.assertEqual([order.symbol for order in ordered.orders], [order.symbol for order in reversed_order.orders])
        self.assertEqual([(rejection.candidate_order.symbol, rejection.reasons) for rejection in ordered.rejections], [(rejection.candidate_order.symbol, rejection.reasons) for rejection in reversed_order.rejections])
        self.assertEqual(ordered.pending_orders, reversed_order.pending_orders)

    def test_reservation_lifecycle_releases_on_fill_skip_and_failure(self):
        a = _make_sample_df([("2026-01-02", 1, 0), ("2026-01-05", 0, 0)], [41.0, 41.0])
        b = _make_sample_df([("2026-01-05", 1, 0)], [51.0])
        success = run_simulated_portfolio_trading_result({"2330.TW": a, "2317.TW": b}, initial_cash=500000.0, last_prices={"2330.TW": 40.0, "2317.TW": 50.0}, quantity_per_trade=1000, max_total_exposure=90000.0)
        self.assertEqual(success.rejection_count, 0)
        invalid_a = a.copy(); invalid_a.iloc[1, invalid_a.columns.get_loc("Open")] = float("nan")
        skipped = run_simulated_portfolio_trading_result({"2330.TW": invalid_a, "2317.TW": b}, initial_cash=500000.0, last_prices={"2330.TW": 40.0, "2317.TW": 50.0}, quantity_per_trade=1000, max_total_exposure=50000.0)
        self.assertEqual(skipped.open_position_count, 0)
        self.assertEqual([x.symbol for x in skipped.pending_orders], ["2317.TW"])
        failed = run_simulated_portfolio_trading_result({"2330.TW": a, "2317.TW": b}, initial_cash=1000.0, last_prices={"2330.TW": 40.0, "2317.TW": 50.0}, quantity_per_trade=1000, max_total_exposure=50000.0)
        self.assertEqual([x.symbol for x in failed.pending_orders], ["2317.TW"])
        self.assertEqual([x.event_type for x in failed.audit_log].count("fill_failed"), 1)

    def test_rejected_candidate_never_pending_and_terminal_sell_reserves_zero(self):
        terminal_buy = _make_sample_df([("2026-01-02", 1, 0)], [101.0])
        rejected = run_simulated_portfolio_trading_result({"2330.TW": terminal_buy}, initial_cash=500000.0, last_prices={"2330.TW": 100.0}, quantity_per_trade=1000, max_total_exposure=99999.0)
        self.assertEqual((rejected.rejection_count, len(rejected.pending_orders), rejected.order_count), (1, 0, 0))
        terminal_sell = _make_sample_df([("2026-01-02", 1, 0), ("2026-01-05", 0, 1)], [101.0, 101.0])
        sell = run_simulated_portfolio_trading_result({"2330.TW": terminal_sell}, initial_cash=500000.0, last_prices={"2330.TW": 100.0}, quantity_per_trade=1000)
        self.assertEqual(sell.pending_orders[0].reserved_buy_notional, 0.0)

if __name__ == "__main__":
    unittest.main()
