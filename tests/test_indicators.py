import unittest

import pandas as pd

from indicators import IndicatorError, add_indicators


def _sample_ohlcv(rows: int = 80) -> pd.DataFrame:
    close = pd.Series(range(100, 100 + rows), dtype=float)
    return pd.DataFrame(
        {
            "Open": close - 1,
            "High": close + 2,
            "Low": close - 2,
            "Close": close,
            "Volume": [1000 + i for i in range(rows)],
        },
        index=pd.date_range("2024-01-01", periods=rows, freq="D"),
    )


class IndicatorTest(unittest.TestCase):
    def test_add_indicators_creates_expected_columns(self) -> None:
        result = add_indicators(_sample_ohlcv())

        for column in [
            "MA5",
            "MA20",
            "MA60",
            "RSI",
            "MACD",
            "MACD_Signal",
            "MACD_Hist",
            "K",
            "D",
            "BB_Upper",
            "BB_Middle",
            "BB_Lower",
            "ATR",
            "OBV",
            "Volume_MA20",
            "Volume_Ratio",
        ]:
            self.assertIn(column, result.columns)

    def test_add_indicators_rejects_insufficient_data(self) -> None:
        with self.assertRaises(IndicatorError):
            add_indicators(_sample_ohlcv(rows=10))


if __name__ == "__main__":
    unittest.main()
