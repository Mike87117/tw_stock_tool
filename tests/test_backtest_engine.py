import unittest

import pandas as pd

from src.tw_stock_tool.backtest.engine import BacktestEngine, BacktestResult
from src.tw_stock_tool.strategies.base import BaseStrategy


class FixedSignalStrategy(BaseStrategy):
    name = "fixed"

    def __init__(self, entry_rows=None, exit_rows=None, mutate_original: bool = False):
        self.entry_rows = set(entry_rows or [])
        self.exit_rows = set(exit_rows or [])
        self.mutate_original = mutate_original

    def generate_signals(self, df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
        if self.mutate_original:
            df["mutated"] = True
        result = df.copy()
        result["entry_signal"] = [index in self.entry_rows for index in range(len(result))]
        result["exit_signal"] = [index in self.exit_rows for index in range(len(result))]
        result["entry_signal"] = result["entry_signal"].astype(bool)
        result["exit_signal"] = result["exit_signal"].astype(bool)
        return result


class BadLengthStrategy(FixedSignalStrategy):
    def generate_signals(self, df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
        result = super().generate_signals(df, params)
        return result.iloc[:-1]


class BacktestEngineTest(unittest.TestCase):
    def price_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "Open": [10.0, 11.0, 12.0, 13.0],
                "Close": [10.5, 11.5, 12.5, 13.5],
            },
            index=pd.date_range("2024-01-01", periods=4, freq="D"),
        )

    def test_entry_and_exit_execute_on_next_bar_open(self) -> None:
        engine = BacktestEngine(
            self.price_df(),
            FixedSignalStrategy(entry_rows=[0], exit_rows=[2]),
            initial_cash=1_000.0,
        )

        result = engine.run()

        self.assertIsInstance(result, BacktestResult)
        self.assertEqual(result.trade_count, 1)
        trade = result.trade_log.iloc[0]
        self.assertEqual(trade["Entry Date"], self.price_df().index[1])
        self.assertEqual(trade["Exit Date"], self.price_df().index[3])
        self.assertEqual(trade["Entry Price"], 11.0)
        self.assertEqual(trade["Exit Price"], 13.0)
        self.assertAlmostEqual(result.final_equity, 1_000.0 / 11.0 * 13.0)
        self.assertAlmostEqual(result.total_return, (1_000.0 / 11.0 * 13.0) / 1_000.0 - 1)
        self.assertEqual(result.win_rate, 1.0)

    def test_last_bar_entry_signal_does_not_execute(self) -> None:
        engine = BacktestEngine(
            self.price_df(),
            FixedSignalStrategy(entry_rows=[3]),
            initial_cash=1_000.0,
        )

        result = engine.run()

        self.assertEqual(result.trade_count, 0)
        self.assertEqual(result.final_equity, 1_000.0)
        self.assertTrue(result.trade_log.empty)

    def test_open_position_is_marked_to_market_at_final_close(self) -> None:
        engine = BacktestEngine(
            self.price_df(),
            FixedSignalStrategy(entry_rows=[0]),
            initial_cash=1_000.0,
        )

        result = engine.run()

        self.assertEqual(result.trade_count, 0)
        self.assertAlmostEqual(result.final_equity, 1_000.0 / 11.0 * 13.5)

    def test_commission_tax_and_slippage_are_applied(self) -> None:
        engine = BacktestEngine(
            self.price_df(),
            FixedSignalStrategy(entry_rows=[0], exit_rows=[2]),
            initial_cash=1_000.0,
            commission=0.001,
            tax=0.003,
            slippage=0.01,
        )

        result = engine.run()
        trade = result.trade_log.iloc[0]
        expected_entry_price = 11.0 * 1.01
        expected_exit_price = 13.0 * 0.99
        expected_shares = 1_000.0 / (expected_entry_price * 1.001)
        expected_final = expected_shares * expected_exit_price * (1 - 0.001 - 0.003)

        self.assertAlmostEqual(trade["Entry Price"], expected_entry_price)
        self.assertAlmostEqual(trade["Exit Price"], expected_exit_price)
        self.assertAlmostEqual(result.final_equity, expected_final)

    def test_trade_log_has_expected_columns(self) -> None:
        result = BacktestEngine(
            self.price_df(),
            FixedSignalStrategy(entry_rows=[0], exit_rows=[2]),
        ).run()

        self.assertEqual(
            list(result.trade_log.columns),
            ["Entry Date", "Exit Date", "Entry Price", "Exit Price", "Shares", "PnL", "PnL %"],
        )

    def test_result_can_be_converted_to_dict(self) -> None:
        result = BacktestEngine(self.price_df(), FixedSignalStrategy()).run()

        result_dict = result.to_dict()

        self.assertIn("total_return", result_dict)
        self.assertIn("max_drawdown", result_dict)
        self.assertIn("win_rate", result_dict)
        self.assertIn("trade_count", result_dict)
        self.assertIn("final_equity", result_dict)
        self.assertIn("trade_log", result_dict)

    def test_strategy_receives_copy_of_price_dataframe(self) -> None:
        price_df = self.price_df()
        strategy = FixedSignalStrategy(mutate_original=True)

        BacktestEngine(price_df, strategy).run()

        self.assertNotIn("mutated", price_df.columns)

    def test_invalid_signal_length_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "signal length must match"):
            BacktestEngine(self.price_df(), BadLengthStrategy()).run()

    def test_missing_price_columns_raise(self) -> None:
        with self.assertRaisesRegex(ValueError, "price_df missing required columns"):
            BacktestEngine(pd.DataFrame({"Close": [1, 2]}), FixedSignalStrategy())

    def test_negative_cost_settings_raise(self) -> None:
        for kwargs in ({"commission": -0.1}, {"tax": -0.1}, {"slippage": -0.1}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ValueError, "cannot be negative"):
                    BacktestEngine(self.price_df(), FixedSignalStrategy(), **kwargs)


if __name__ == "__main__":
    unittest.main()
