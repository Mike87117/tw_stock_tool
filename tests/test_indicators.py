import unittest

import pandas as pd

from indicators import IndicatorError, _rsi, add_indicators


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


    @unittest.expectedFailure
    def test_rsi_continuous_gains_reaches_100_after_warmup(self) -> None:
        # Track C1 confirmed defect. Expected failure must be removed in Track C2.
        rsi = _rsi(pd.Series(range(100, 140), dtype=float))
        self.assertTrue((rsi.iloc[14:] == 100).all())

    def test_rsi_continuous_losses_reaches_0_after_warmup(self) -> None:
        # Track C1 NOT_REPRODUCED: continuous losses correctly reach RSI 0.
        rsi = _rsi(pd.Series(range(140, 100, -1), dtype=float))
        self.assertTrue((rsi.iloc[14:] == 0).all())

    def test_rsi_flat_series_currently_remains_nan_after_warmup(self) -> None:
        rsi = _rsi(pd.Series([100.0] * 40))
        self.assertTrue(rsi.iloc[14:].isna().all())

if __name__ == "__main__":
    unittest.main()
