import math
import unittest

import pandas as pd

from tw_stock_tool.analysis.indicators import IndicatorError, _rsi, add_indicators


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

    def test_rsi_continuous_gains_reaches_100_after_warmup(self) -> None:
        rsi = _rsi(pd.Series(range(100, 140), dtype=float))
        self.assertTrue(rsi.iloc[:14].isna().all())
        self.assertTrue((rsi.iloc[14:] == 100.0).all())
        self.assertTrue(rsi.iloc[14:].map(math.isfinite).all())

    def test_rsi_continuous_losses_reaches_0_after_warmup(self) -> None:
        rsi = _rsi(pd.Series(range(140, 100, -1), dtype=float))
        self.assertTrue(rsi.iloc[:14].isna().all())
        self.assertTrue((rsi.iloc[14:] == 0.0).all())
        self.assertTrue(rsi.iloc[14:].map(math.isfinite).all())

    def test_rsi_flat_series_is_neutral_50_after_warmup(self) -> None:
        rsi = _rsi(pd.Series([100.0] * 40))
        self.assertTrue(rsi.iloc[:14].isna().all())
        self.assertTrue((rsi.iloc[14:] == 50.0).all())
        self.assertTrue(rsi.iloc[14:].map(math.isfinite).all())

    def test_rsi_mixed_movement_uses_formula_with_bounded_finite_values(self) -> None:
        rsi = _rsi(pd.Series([100.0, 102.0, 101.0, 104.0, 102.0] * 10))
        warmed = rsi.iloc[14:]

        self.assertTrue(warmed.map(math.isfinite).all())
        self.assertTrue(warmed.between(0.0, 100.0).all())
        self.assertFalse(warmed.isin([0.0, 50.0, 100.0]).all())

    def test_rsi_preserves_input_index_length_and_values(self) -> None:
        close = pd.Series(
            [100.0, 102.0, 101.0, 103.0] * 10,
            index=pd.date_range("2024-01-01", periods=40, freq="D"),
        )
        original = close.copy()

        rsi = _rsi(close)

        self.assertTrue(rsi.index.equals(close.index))
        self.assertEqual(len(rsi), len(close))
        pd.testing.assert_series_equal(close, original)

if __name__ == "__main__":
    unittest.main()
