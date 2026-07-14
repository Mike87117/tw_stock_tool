import math
import unittest

import pandas as pd

from tw_stock_tool.backtesting.metrics import (
    calculate_avg_hold_days,
    calculate_buy_hold_return,
    calculate_cagr,
    calculate_exposure,
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_sharpe,
    calculate_sortino,
    calculate_total_return,
    calculate_win_rate,
)


def _interval_equity() -> pd.Series:
    return pd.Series([100.0, 110.0, 99.0, 108.0, 91.8, 101.0])


class BacktestMetricsTest(unittest.TestCase):
    def test_return_metrics(self) -> None:
        index = pd.date_range("2024-01-01", periods=366, freq="D")
        frame = pd.DataFrame({"Close": [100, 125]}, index=index[:2])

        self.assertEqual(calculate_total_return(10000, 12500), 25)
        self.assertEqual(calculate_buy_hold_return(frame), 25)
        self.assertAlmostEqual(calculate_cagr(10000, 12100, index), 21.0, places=1)
        self.assertEqual(calculate_exposure(3, 4), 75)

    def test_trade_metrics(self) -> None:
        trades = [
            {"PnL": 100, "Hold Days": 2},
            {"PnL": -50, "Hold Days": 4},
        ]

        self.assertEqual(calculate_win_rate(trades), 50)
        self.assertEqual(calculate_profit_factor(trades), 2)
        self.assertEqual(calculate_avg_hold_days(trades), 3)

    def test_profit_factor_without_loss_is_infinite(self) -> None:
        self.assertTrue(math.isinf(calculate_profit_factor([{"PnL": 100}])))

    def test_equity_curve_metrics(self) -> None:
        equity = pd.Series([100, 120, 90, 130])

        self.assertEqual(calculate_max_drawdown(equity), -25)
        self.assertIsInstance(calculate_sharpe(equity), float)
        self.assertIsInstance(calculate_sortino(equity), float)

    def test_metrics_handle_empty_or_short_inputs(self) -> None:
        empty_equity = pd.Series(dtype="float64")
        short_index = pd.Index([pd.Timestamp("2024-01-01")])

        self.assertEqual(calculate_buy_hold_return([]), 0.0)
        self.assertEqual(calculate_cagr(10000, 11000, short_index), 0.0)
        self.assertEqual(calculate_win_rate([]), 0.0)
        self.assertEqual(calculate_profit_factor([]), 0.0)
        self.assertEqual(calculate_avg_hold_days([]), 0.0)
        self.assertEqual(calculate_max_drawdown(empty_equity), 0.0)
        self.assertEqual(calculate_sharpe(empty_equity), 0.0)
        self.assertEqual(calculate_sortino(empty_equity), 0.0)

    def test_metrics_handle_flat_and_lossless_cases(self) -> None:
        flat_equity = pd.Series([100.0, 100.0, 100.0])
        gain_only_trades = [{"PnL": 10.0, "Hold Days": 2}]

        self.assertEqual(calculate_total_return(10000, 10000), 0.0)
        self.assertEqual(calculate_buy_hold_return([100.0, 100.0]), 0.0)
        self.assertTrue(math.isinf(calculate_profit_factor(gain_only_trades)))
        self.assertEqual(calculate_sharpe(flat_equity), 0.0)
        self.assertEqual(calculate_sortino(flat_equity), 0.0)

    def test_interval_specific_sharpe_and_sortino(self) -> None:
        equity = _interval_equity()
        returns = equity.pct_change().dropna()
        sharpe_base = returns.mean() / returns.std(ddof=0)
        downside = returns[returns < 0]
        sortino_base = returns.mean() / downside.std(ddof=0)

        for interval, periods_per_year in (("1d", 252), ("1wk", 52), ("1mo", 12)):
            with self.subTest(metric="sharpe", interval=interval):
                self.assertAlmostEqual(
                    calculate_sharpe(equity, interval),
                    sharpe_base * math.sqrt(periods_per_year),
                )
            with self.subTest(metric="sortino", interval=interval):
                self.assertAlmostEqual(
                    calculate_sortino(equity, interval),
                    sortino_base * math.sqrt(periods_per_year),
                )

    def test_interval_scaling_relationships(self) -> None:
        equity = _interval_equity()
        for metric in (calculate_sharpe, calculate_sortino):
            with self.subTest(metric=metric.__name__):
                daily = metric(equity, "1d")
                weekly = metric(equity, "1wk")
                monthly = metric(equity, "1mo")
                self.assertAlmostEqual(daily / weekly, math.sqrt(252 / 52))
                self.assertAlmostEqual(weekly / monthly, math.sqrt(52 / 12))

    def test_default_interval_matches_daily(self) -> None:
        equity = _interval_equity()
        self.assertEqual(calculate_sharpe(equity), calculate_sharpe(equity, "1d"))
        self.assertEqual(calculate_sortino(equity), calculate_sortino(equity, "1d"))

    def test_invalid_intervals_raise_even_for_empty_equity(self) -> None:
        empty = pd.Series(dtype="float64")
        for metric in (calculate_sharpe, calculate_sortino):
            for interval in (None, True, "", "daily", "5m", object()):
                with self.subTest(metric=metric.__name__, interval=repr(interval), data="sample"):
                    with self.assertRaises(ValueError):
                        metric(_interval_equity(), interval)
                with self.subTest(metric=metric.__name__, interval=repr(interval), data="empty"):
                    with self.assertRaises(ValueError):
                        metric(empty, interval)

    def test_interval_edge_cases_preserve_existing_results(self) -> None:
        empty = pd.Series(dtype="float64")
        flat = pd.Series([100.0, 100.0, 100.0])
        lossless = pd.Series([100.0, 110.0, 121.0])
        for interval in ("1d", "1wk", "1mo"):
            with self.subTest(interval=interval):
                self.assertEqual(calculate_sharpe(empty, interval), 0.0)
                self.assertEqual(calculate_sortino(empty, interval), 0.0)
                self.assertEqual(calculate_sharpe(flat, interval), 0.0)
                self.assertEqual(calculate_sortino(flat, interval), 0.0)
                self.assertEqual(calculate_sortino(lossless, interval), 0.0)


if __name__ == "__main__":
    unittest.main()
