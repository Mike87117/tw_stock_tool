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

    def test_differing_dates_and_same_timestamp_entry_signals(self):
        df1 = _make_sample_df(
            [
                ("2026-01-02", 1, 0),
                ("2026-01-05", 0, 0),
            ]
        )
        df2 = _make_sample_df(
            [
                ("2026-01-02", 1, 0),
                ("2026-01-06", 0, 0),
            ]
        )

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

    def test_insufficient_shared_cash_and_rejections(self):
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
        # Bar 1 (01-02): entry signal -> pending BUY created
        # Bar 2 (01-05): pending BUY fills at 104.0; exit signal -> pending SELL created
        # Bar 3 (01-06): pending SELL fills at 119.0 -> position closed!
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

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=True, last_prices=last_prices)

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=float("nan"), last_prices=last_prices)

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=float("inf"), last_prices=last_prices)

    def test_invalid_quantity_per_trade_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 100.0}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices, quantity_per_trade=0)

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices, quantity_per_trade=-100)

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices, quantity_per_trade=True)

    def test_invalid_rates_rejected(self):
        df1 = _make_sample_df([("2026-01-02", 0, 0)])
        dataframes = {"2330.TW": df1}
        last_prices = {"2330.TW": 100.0}

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices, fee_rate=-0.01)

        with self.assertRaises(PaperTradingModelError):
            run_simulated_portfolio_trading_result(dataframes, initial_cash=100000.0, last_prices=last_prices, tax_rate=True)

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


if __name__ == "__main__":
    unittest.main()
