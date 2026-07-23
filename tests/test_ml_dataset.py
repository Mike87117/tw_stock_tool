import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.ml import ml_dataset
from tw_stock_tool.analysis.analysis import StockAnalysis


def _sample_signal_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Close": [100.0, 110.0, 121.0, 115.0, 120.0, 132.0, 126.0],
            "MA5": [99.0, 105.0, 110.0, 112.0, 116.0, 120.0, 124.0],
            "MA20": [98.0, 100.0, 102.0, 104.0, 106.0, 108.0, 110.0],
            "MA60": [95.0, 96.0, 97.0, 98.0, 99.0, 100.0, 101.0],
            "RSI": [45.0, 50.0, 55.0, 48.0, 52.0, 60.0, 58.0],
            "MACD": [0.1, 0.2, 0.3, 0.2, 0.4, 0.5, 0.3],
            "MACD_Signal": [0.0, 0.1, 0.2, 0.2, 0.3, 0.4, 0.4],
            "MACD_Hist": [0.1, 0.1, 0.1, 0.0, 0.1, 0.1, -0.1],
            "K": [40.0, 45.0, 50.0, 48.0, 53.0, 60.0, 57.0],
            "D": [38.0, 42.0, 47.0, 48.0, 50.0, 56.0, 58.0],
            "BB_Upper": [120.0, 122.0, 124.0, 126.0, 128.0, 130.0, 132.0],
            "BB_Middle": [100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 112.0],
            "BB_Lower": [80.0, 82.0, 84.0, 86.0, 88.0, 90.0, 92.0],
            "ATR": [2.0, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6],
            "OBV": [1000, 1200, 1500, 1300, 1600, 1800, 1700],
            "Volume_Ratio": [1.0, 1.2, 1.4, 0.9, 1.1, 1.6, 0.8],
            "Score": [1, 2, 3, 0, 4, 5, -1],
            "Signal": ["HOLD", "BUY", "HOLD", "SELL", "BUY", "HOLD", "SELL"],
        },
        index=pd.date_range("2024-01-01", periods=7, freq="D"),
    )


class MLDatasetTest(unittest.TestCase):
    def test_future_return_matches_close_shift(self) -> None:
        df = _sample_signal_df()
        result = ml_dataset.build_ml_dataset_from_signal_df(df, horizon=5, dropna=False)

        expected = df.iloc[5]["Close"] / df.iloc[0]["Close"] - 1
        self.assertAlmostEqual(result.iloc[0]["Future_Return_5D"], expected)

    def test_target_up_matches_future_return_positive(self) -> None:
        result = ml_dataset.build_ml_dataset_from_signal_df(
            _sample_signal_df(),
            horizon=5,
            dropna=False,
        )

        expected = result["Future_Return_5D"] > 0
        pd.testing.assert_series_equal(result["Target_Up_5D"], expected, check_names=False)

    def test_last_horizon_rows_are_removed(self) -> None:
        df = _sample_signal_df()
        result = ml_dataset.build_ml_dataset_from_signal_df(df, horizon=5, dropna=False)

        self.assertEqual(len(result), len(df) - 5)
        self.assertEqual(result.index[-1], df.index[-6])

    def test_feature_columns_do_not_include_future_or_target(self) -> None:
        features = ml_dataset.available_feature_columns(_sample_signal_df())

        self.assertTrue(features)
        self.assertFalse(any("Future_Return" in column for column in features))
        self.assertFalse(any("Target" in column for column in features))

    def test_dataset_columns_do_not_create_future_features(self) -> None:
        result = ml_dataset.build_ml_dataset_from_signal_df(
            _sample_signal_df(),
            horizon=5,
            dropna=False,
        )
        feature_columns = [
            column
            for column in result.columns
            if not column.startswith("Future_Return_") and not column.startswith("Target_Up_")
        ]

        self.assertEqual(feature_columns, ml_dataset.available_feature_columns(_sample_signal_df()))

    def test_horizon_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            ml_dataset.build_ml_dataset_from_signal_df(_sample_signal_df(), horizon=0)

    def test_build_ml_dataset_uses_analyze_stock(self) -> None:
        signal_df = _sample_signal_df()
        analysis = StockAnalysis(
            stock_id="2330",
            symbol="2330.TW",
            raw_df=pd.DataFrame(),
            indicator_df=pd.DataFrame(),
            signal_df=signal_df,
            latest=signal_df.iloc[-1],
            summary={},
        )

        with patch.object(ml_dataset, "analyze_stock", return_value=analysis) as mocked:
            result = ml_dataset.build_ml_dataset(
                "2330",
                period="5y",
                horizon=5,
                force_refresh=True,
                dropna=False,
            )

        mocked.assert_called_once_with(stock_id="2330", period="5y", force_refresh=True)
        self.assertEqual(len(result), len(signal_df) - 5)

    def test_output_csv_can_be_created(self) -> None:
        dataset = ml_dataset.build_ml_dataset_from_signal_df(
            _sample_signal_df(),
            horizon=5,
            dropna=False,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "dataset.csv"
            result = ml_dataset.export_ml_dataset(dataset, "2330", 5, str(output_path))

            self.assertEqual(result, output_path)
            self.assertTrue(output_path.exists())
            self.assertIn("Future_Return_5D", output_path.read_text(encoding="utf-8-sig"))

    def test_parse_args_uses_output_csv_flag(self) -> None:
        args = ml_dataset._parse_args(["--stock", "2330", "--horizon", "5", "--output-csv"])
        self.assertEqual(args.output_csv, "")

    def test_old_output_flag_is_rejected(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            ml_dataset._parse_args(["--stock", "2330", "--output"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
