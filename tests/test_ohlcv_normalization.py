import unittest

import pandas as pd

from tw_stock_tool.data import data_loader
from tw_stock_tool.data import ohlcv_normalization


class OhlcvNormalizationTest(unittest.TestCase):
    def test_flattens_multiindex_and_keeps_frame(self) -> None:
        frame = pd.DataFrame(
            [[10, 12, 9, 11, 1000]],
            columns=pd.MultiIndex.from_tuples([(name, "2330.TW") for name in ("Open", "High", "Low", "Close", "Volume")]),
        )
        self.assertIs(ohlcv_normalization.normalize_columns(frame), frame)
        self.assertEqual(list(frame.columns), ["Open", "High", "Low", "Close", "Volume"])

    def test_prepares_ohlcv_and_preserves_missing_volume(self) -> None:
        frame = pd.DataFrame({"Volume": [None, 2], "Close": [11, 21], "Open": [10, None], "Extra": [1, 2], "Low": [9, 19], "High": [12, 22]}, index=["2024-01-02", "2024-01-03"])
        actual = ohlcv_normalization.prepare_ohlcv(frame, "2330.TW", normalize_columns=ohlcv_normalization.normalize_columns, error_type=data_loader.DataLoaderError)
        self.assertEqual(list(actual.columns), ["Open", "High", "Low", "Close", "Volume"])
        self.assertEqual(len(actual), 1)
        self.assertIsInstance(actual.index, pd.DatetimeIndex)
        self.assertTrue(pd.isna(actual.iloc[0]["Volume"]))

    def test_prepare_rejects_missing_columns_and_invalid_index(self) -> None:
        with self.assertRaisesRegex(data_loader.DataLoaderError, "Missing data columns: \\['High', 'Volume'\\]"):
            ohlcv_normalization.prepare_ohlcv(pd.DataFrame({"Open": [1], "Low": [1], "Close": [1]}), "2330.TW", normalize_columns=ohlcv_normalization.normalize_columns, error_type=data_loader.DataLoaderError)
        frame = pd.DataFrame({name: [1] for name in ("Open", "High", "Low", "Close", "Volume")}, index=["bad"])
        with self.assertRaisesRegex(data_loader.DataLoaderError, "2330.TW index is not a valid DatetimeIndex"):
            ohlcv_normalization.prepare_ohlcv(frame, "2330.TW", normalize_columns=ohlcv_normalization.normalize_columns, error_type=data_loader.DataLoaderError)


if __name__ == "__main__":
    unittest.main()