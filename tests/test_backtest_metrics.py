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


if __name__ == "__main__":
    unittest.main()
