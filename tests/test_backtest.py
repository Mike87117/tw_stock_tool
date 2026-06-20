import unittest

import pandas as pd

from backtest import BacktestError, run_backtest


def _backtest_frame(closes: list[float], signals: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {"Close": closes, "Signal": signals},
        index=pd.date_range("2024-01-01", periods=len(closes), freq="D"),
    )


class BacktestTest(unittest.TestCase):
    def test_buy_sell_basic_trade_executes_next_day(self) -> None:
        frame = _backtest_frame(
            [100, 110, 120, 130],
            ["BUY", "HOLD", "SELL", "HOLD"],
        )
        result = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
        )

        trades = result["Trades"]
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades.iloc[0]["Entry Date"], frame.index[1])
        self.assertEqual(trades.iloc[0]["Entry Price"], 110)
        self.assertEqual(trades.iloc[0]["Exit Date"], frame.index[3])
        self.assertEqual(trades.iloc[0]["Exit Price"], 130)
        self.assertEqual(trades.iloc[0]["Exit Reason"], "SELL")
        self.assertGreater(result["Final Capital"], 10000)

    def test_stop_loss_executes_next_day_after_trigger(self) -> None:
        frame = _backtest_frame([100, 100, 94, 93], ["BUY", "HOLD", "HOLD", "HOLD"])
        result = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
            stop_loss_pct=5,
        )

        trade = result["Trades"].iloc[0]
        self.assertEqual(trade["Exit Reason"], "SELL_STOP_LOSS")
        self.assertEqual(trade["Exit Date"], frame.index[3])
        self.assertEqual(trade["Exit Price"], 93)

    def test_take_profit_executes_next_day_after_trigger(self) -> None:
        frame = _backtest_frame([100, 100, 106, 108], ["BUY", "HOLD", "HOLD", "HOLD"])
        result = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
            take_profit_pct=5,
        )

        trade = result["Trades"].iloc[0]
        self.assertEqual(trade["Exit Reason"], "SELL_TAKE_PROFIT")
        self.assertEqual(trade["Exit Date"], frame.index[3])
        self.assertEqual(trade["Exit Price"], 108)

    def test_max_hold_days_executes_next_day_after_trigger(self) -> None:
        frame = _backtest_frame([100, 101, 102, 103], ["BUY", "HOLD", "HOLD", "HOLD"])
        result = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
            max_hold_days=1,
        )

        trade = result["Trades"].iloc[0]
        self.assertEqual(trade["Exit Reason"], "SELL_MAX_HOLD")
        self.assertEqual(trade["Exit Date"], frame.index[3])
        self.assertEqual(trade["Exit Price"], 103)

    def test_output_fields_exist(self) -> None:
        result = run_backtest(
            _backtest_frame([100, 110, 120], ["BUY", "SELL", "HOLD"]),
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



    def test_buy_signal_day_equity_stays_in_cash_until_next_day(self) -> None:
        frame = _backtest_frame([100, 110, 120], ["BUY", "HOLD", "HOLD"])
        result = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
        )

        equity = result["Equity Curve"]
        self.assertEqual(equity.iloc[0], 10000)
        self.assertEqual(result["Trades"].iloc[0]["Entry Date"], frame.index[1])
        self.assertEqual(result["Trades"].iloc[0]["Entry Price"], 110)

    def test_last_day_buy_signal_does_not_execute_same_day(self) -> None:
        result = run_backtest(
            _backtest_frame([100, 200], ["HOLD", "BUY"]),
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
        )

        self.assertEqual(result["Trade Count"], 0)
        self.assertTrue(result["Trades"].empty)
        self.assertEqual(result["Final Capital"], 10000)

    def test_no_same_day_round_trip_on_buy_and_sell_signals(self) -> None:
        frame = _backtest_frame(
            [100, 110, 120, 130],
            ["BUY", "SELL", "HOLD", "HOLD"],
        )
        result = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
        )

        trade = result["Trades"].iloc[0]
        self.assertEqual(trade["Entry Date"], frame.index[1])
        self.assertEqual(trade["Exit Date"], frame.index[2])
        self.assertEqual(trade["Entry Price"], 110)
        self.assertEqual(trade["Exit Price"], 120)

    def test_invalid_position_size_raises(self) -> None:
        with self.assertRaises(BacktestError):
            run_backtest(
                _backtest_frame([100, 110], ["BUY", "SELL"]),
                position_size=0,
            )


if __name__ == "__main__":
    unittest.main()
