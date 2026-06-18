import unittest

import pandas as pd

from signals import generate_signals


def _neutral_frame(rows: int = 4) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Close": [10.0] * rows,
            "MA5": [10.0] * rows,
            "MA20": [10.0] * rows,
            "MA60": [10.0] * rows,
            "MACD": [1.0] * rows,
            "MACD_Signal": [1.0] * rows,
            "RSI": [50.0] * rows,
            "Volume": [1000.0] * rows,
            "Volume_MA20": [1000.0] * rows,
            "BB_Upper": [20.0] * rows,
            "BB_Lower": [5.0] * rows,
        }
    )


class SignalTest(unittest.TestCase):
    def test_individual_score_weights(self) -> None:
        cases = [
            ("bullish_stack", {"Close": 12.0, "MA20": 10.0, "MA60": 8.0}, 2.0),
            ("golden_cross", {"MA5": [8.0, 11.0], "MA20": [10.0, 10.0]}, 2.0),
            ("macd_bull", {"MACD": 2.0, "MACD_Signal": 1.0}, 1.0),
            ("volume_burst", {"Volume": 1600.0, "Volume_MA20": 1000.0}, 1.0),
            ("rsi_hot", {"RSI": 71.0}, -1.0),
            ("bearish_stack", {"Close": 7.0, "MA20": 8.0, "MA60": 9.0}, -2.0),
            ("death_cross", {"MA5": [12.0, 9.0], "MA20": [10.0, 10.0]}, -2.0),
            ("macd_weak", {"MACD": 0.0, "MACD_Signal": 1.0}, -1.0),
            ("break_lower", {"Close": 4.0, "BB_Lower": 5.0}, -1.0),
        ]

        for name, updates, expected in cases:
            with self.subTest(name=name):
                df = _neutral_frame(rows=2)
                for column, value in updates.items():
                    df[column] = value
                result = generate_signals(df)
                self.assertEqual(result.iloc[-1]["Score"], expected)

    def test_signal_thresholds(self) -> None:
        scores = [
            (
                "BUY",
                {
                    "Close": 12.0,
                    "MA20": 10.0,
                    "MA60": 8.0,
                    "MACD": 2.0,
                    "MACD_Signal": 1.0,
                    "Volume": 1600.0,
                },
            ),
            ("WATCH", {"Close": 12.0, "MA20": 10.0, "MA60": 8.0}),
            ("HOLD", {"MACD": 0.0, "MACD_Signal": 1.0}),
            ("SELL", {"Close": 7.0, "MA20": 8.0, "MA60": 9.0}),
        ]

        for expected_signal, updates in scores:
            with self.subTest(signal=expected_signal):
                df = _neutral_frame()
                for column, value in updates.items():
                    df[column] = value
                result = generate_signals(df)
                self.assertEqual(result.iloc[-1]["Signal"], expected_signal)

    def test_cross_columns(self) -> None:
        df = _neutral_frame()
        df["MA5"] = [8.0, 11.0, 11.0, 7.0]
        df["MA20"] = [10.0, 10.0, 10.0, 10.0]

        result = generate_signals(df)

        self.assertTrue(result.iloc[1]["Golden_Cross"])
        self.assertTrue(result.iloc[3]["Death_Cross"])


if __name__ == "__main__":
    unittest.main()
