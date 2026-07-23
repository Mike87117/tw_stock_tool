import unittest

import pandas as pd

from tw_stock_tool.backtesting.strategies import macd_strategy, ma_cross_strategy, rsi_strategy, score_strategy


def _strategy_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Close": [10.0, 8.0, 12.0, 7.0],
            "Signal": ["HOLD", "BUY", "SELL", "HOLD"],
            "Score": [0.0, 5.0, -3.0, 2.0],
            "MA5": [8.0, 11.0, 9.0, 8.0],
            "MA20": [10.0, 10.0, 10.0, 10.0],
            "MACD": [0.0, 2.0, 0.0, 0.0],
            "MACD_Signal": [1.0, 1.0, 1.0, 1.0],
            "RSI": [50.0, 25.0, 75.0, 50.0],
        }
    )


class StrategyTest(unittest.TestCase):
    def test_score_strategy_uses_existing_signal(self) -> None:
        result = score_strategy(_strategy_frame())
        self.assertEqual(result["Signal"].tolist(), ["HOLD", "BUY", "SELL", "HOLD"])

    def test_score_strategy_accepts_score_thresholds(self) -> None:
        result = score_strategy(_strategy_frame(), buy_score=4, sell_score=-2)

        self.assertEqual(result["Signal"].tolist(), ["HOLD", "BUY", "SELL", "HOLD"])

    def test_score_strategy_rejects_missing_score_for_thresholds(self) -> None:
        df = _strategy_frame().drop(columns=["Score"])

        with self.assertRaises(ValueError):
            score_strategy(df, buy_score=4, sell_score=-2)

    def test_score_strategy_rejects_invalid_thresholds(self) -> None:
        with self.assertRaises(ValueError):
            score_strategy(_strategy_frame(), buy_score=-2, sell_score=4)

    def test_ma_cross_strategy(self) -> None:
        result = ma_cross_strategy(_strategy_frame(), short_window=1, long_window=2)
        self.assertEqual(result.iloc[2]["Signal"], "BUY")
        self.assertEqual(result.iloc[3]["Signal"], "SELL")

    def test_ma_cross_strategy_accepts_parameters(self) -> None:
        df = _strategy_frame()
        result = ma_cross_strategy(df, short_window=1, long_window=2)

        self.assertIn("Signal", result.columns)

    def test_macd_strategy(self) -> None:
        result = macd_strategy(_strategy_frame())
        self.assertEqual(result.iloc[1]["Signal"], "BUY")
        self.assertEqual(result.iloc[2]["Signal"], "SELL")

    def test_rsi_strategy(self) -> None:
        result = rsi_strategy(_strategy_frame())
        self.assertEqual(result.iloc[1]["Signal"], "BUY")
        self.assertEqual(result.iloc[2]["Signal"], "SELL")

    def test_rsi_strategy_accepts_parameters(self) -> None:
        result = rsi_strategy(_strategy_frame(), buy_below=40, sell_above=60)

        self.assertEqual(result.iloc[1]["Signal"], "BUY")
        self.assertEqual(result.iloc[2]["Signal"], "SELL")


if __name__ == "__main__":
    unittest.main()
