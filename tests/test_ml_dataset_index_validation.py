import unittest

import pandas as pd

from tw_stock_tool.ml.ml_dataset import MLDatasetError, build_ml_dataset_from_signal_df


def _prices() -> pd.DataFrame:
    return pd.DataFrame({"Close": [100., 110., 120., 130.]},
                        index=pd.date_range("2026-01-01", periods=4))


class MLDatasetIndexValidationTest(unittest.TestCase):
    def test_descending_and_shuffled_dates_are_rejected_before_labeling(self):
        for df in (_prices().iloc[::-1], _prices().iloc[[0, 2, 1, 3]]):
            for dropna in (True, False):
                original = df.copy(deep=True)
                with self.subTest(index=df.index, dropna=dropna):
                    with self.assertRaisesRegex(MLDatasetError, "chronological order"):
                        build_ml_dataset_from_signal_df(df, horizon=1, dropna=dropna)
                    pd.testing.assert_frame_equal(df, original)

    def test_duplicate_dates_are_rejected(self):
        df = _prices()
        df.index = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-02", "2026-01-04"])
        with self.assertRaisesRegex(MLDatasetError, "unique"):
            build_ml_dataset_from_signal_df(df, horizon=1)

    def test_missing_dates_are_rejected(self):
        df = _prices()
        df.index = pd.to_datetime(["2026-01-01", "2026-01-02", None, "2026-01-04"])
        with self.assertRaisesRegex(MLDatasetError, "NaT"):
            build_ml_dataset_from_signal_df(df, horizon=1)

    def test_ordered_dates_preserve_future_labels_and_input(self):
        df = _prices()
        original = df.copy(deep=True)
        result = build_ml_dataset_from_signal_df(df, horizon=1)
        self.assertTrue(result["Target_Up_1D"].all())
        pd.testing.assert_index_equal(result.index, df.index[:-1])
        expected = (df["Close"].shift(-1) / df["Close"] - 1).iloc[:-1]
        pd.testing.assert_series_equal(result["Future_Return_1D"], expected, check_names=False)
        pd.testing.assert_frame_equal(df, original)

    def test_ordered_timezone_and_numeric_indices_remain_supported(self):
        for index in (_prices().index.tz_localize("Asia/Taipei"), pd.RangeIndex(4)):
            df = _prices()
            df.index = index
            result = build_ml_dataset_from_signal_df(df, horizon=1)
            pd.testing.assert_index_equal(result.index, index[:-1])
            self.assertTrue(result["Target_Up_1D"].all())


if __name__ == "__main__":
    unittest.main()
