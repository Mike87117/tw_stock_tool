import math
import unittest

import pandas as pd

from tw_stock_tool.backtesting.results import BacktestResult


class BacktestResultTest(unittest.TestCase):
    def test_to_legacy_dict_preserves_existing_keys_and_payload_types(self) -> None:
        trades = pd.DataFrame(
            [
                {
                    "Entry Date": pd.Timestamp("2024-01-01"),
                    "Exit Date": pd.Timestamp("2024-01-02"),
                    "Entry Price": 100,
                    "Exit Price": 110,
                    "Shares": 10,
                    "PnL": 100,
                    "PnL_pct": 10,
                    "Hold Days": 1,
                    "Exit Reason": "SELL",
                    "Type": "SELL",
                }
            ]
        )
        equity = pd.Series([10000, 10100], name="Equity")
        result = BacktestResult(
            initial_capital=10000,
            final_capital=10100,
            total_return_pct=1,
            buy_hold_return_pct=10,
            cagr_pct=12.345,
            exposure_pct=50,
            trade_count=1,
            win_rate_pct=100,
            max_drawdown_pct=-1.234,
            profit_factor=math.inf,
            best_trade_pct=10,
            worst_trade_pct=10,
            avg_hold_days=1,
            sharpe_ratio=1.234,
            sortino_ratio=2.345,
            avg_profit=100,
            avg_loss=0,
            trades=trades,
            equity_curve=equity,
        )

        legacy = result.to_legacy_dict()

        self.assertEqual(legacy["Initial Capital"], 10000)
        self.assertEqual(legacy["Final Capital"], 10100)
        self.assertEqual(legacy["Total Return %"], 1)
        self.assertEqual(legacy["CAGR %"], 12.35)
        self.assertEqual(legacy["Max Drawdown %"], -1.23)
        self.assertEqual(legacy["Profit Factor"], float("inf"))
        self.assertIs(legacy["Trades"], trades)
        self.assertIs(legacy["Equity Curve"], equity)
        self.assertEqual(
            set(legacy.keys()),
            {
                "Initial Capital",
                "Final Capital",
                "Total Return %",
                "Buy and Hold Return %",
                "CAGR %",
                "Exposure %",
                "Trade Count",
                "Win Rate %",
                "Max Drawdown %",
                "Profit Factor",
                "Best Trade %",
                "Worst Trade %",
                "Avg Hold Days",
                "Sharpe Ratio",
                "Sortino Ratio",
                "Avg Profit",
                "Avg Loss",
                "Trades",
                "Equity Curve",
            },
        )
        self.assertIsInstance(legacy["Trades"], pd.DataFrame)
        self.assertIsInstance(legacy["Equity Curve"], pd.Series)


if __name__ == "__main__":
    unittest.main()
