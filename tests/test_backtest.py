import unittest

import pandas as pd

from backtest import BacktestError, run_backtest


def _backtest_frame(closes: list[float], signals: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {"Close": closes, "Signal": signals},
        index=pd.date_range("2024-01-01", periods=len(closes), freq="D"),
    )


class BacktestTest(unittest.TestCase):
    def test_buy_sell_basic_trade(self) -> None:
        result = run_backtest(
            _backtest_frame([100, 110, 120], ["BUY", "HOLD", "SELL"]),
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
        )

        trades = result["Trades"]
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades.iloc[0]["Exit Reason"], "SELL")
        self.assertGreater(result["Final Capital"], 10000)

    def test_stop_loss(self) -> None:
        result = run_backtest(
            _backtest_frame([100, 94, 93], ["BUY", "HOLD", "HOLD"]),
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
            stop_loss_pct=5,
        )

        self.assertEqual(result["Trades"].iloc[0]["Exit Reason"], "SELL_STOP_LOSS")

    def test_take_profit(self) -> None:
        result = run_backtest(
            _backtest_frame([100, 106, 108], ["BUY", "HOLD", "HOLD"]),
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
            take_profit_pct=5,
        )

        self.assertEqual(result["Trades"].iloc[0]["Exit Reason"], "SELL_TAKE_PROFIT")

    def test_max_hold_days(self) -> None:
        result = run_backtest(
            _backtest_frame([100, 101, 102], ["BUY", "HOLD", "HOLD"]),
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
            max_hold_days=1,
        )

        self.assertEqual(result["Trades"].iloc[0]["Exit Reason"], "SELL_MAX_HOLD")

    def test_output_fields_exist(self) -> None:
        result = run_backtest(
            _backtest_frame([100, 110], ["BUY", "SELL"]),
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
        )

        for field in [
            "Buy and Hold Return %",
            "CAGR %",
            "Exposure %",
            "Profit Factor",
            "Best Trade %",
            "Worst Trade %",
            "Avg Hold Days",
            "Sharpe Ratio",
            "Sortino Ratio",
            "Trades",
            "Equity Curve",
        ]:
            self.assertIn(field, result)

        for column in [
            "Entry Date",
            "Exit Date",
            "Entry Price",
            "Exit Price",
            "Shares",
            "PnL",
            "PnL_pct",
            "Hold Days",
            "Exit Reason",
        ]:
            self.assertIn(column, result["Trades"].columns)

    def test_invalid_position_size_raises(self) -> None:
        with self.assertRaises(BacktestError):
            run_backtest(
                _backtest_frame([100, 110], ["BUY", "SELL"]),
                position_size=0,
            )


if __name__ == "__main__":
    unittest.main()
