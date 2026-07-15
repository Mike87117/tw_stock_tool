import inspect
import math
import unittest
import warnings
from unittest.mock import patch

import numpy as np
import pandas as pd

from tw_stock_tool.analysis import analysis
from tw_stock_tool.ml import ml_dataset
from tw_stock_tool.ml.ai_walk_forward import ml_feature_columns, split_time_windows


def _ohlcv(kind: str, rows: int = 160) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="D")
    if kind == "rising":
        close = pd.Series([100.0 + i for i in range(rows)], index=index)
    elif kind == "flat":
        close = pd.Series([100.0] * rows, index=index)
    else:
        cycle = (0.0, 2.0, 5.0, 3.0, 1.0, -2.0, -4.0, -1.0, 3.0, 1.0)
        close = pd.Series(
            [100.0 + cycle[i % len(cycle)] + i // len(cycle) * 0.1 for i in range(rows)],
            index=index,
        )
    zero_range = kind == "flat"
    return pd.DataFrame(
        {
            "Open": close,
            "High": close if zero_range else close + 1.0,
            "Low": close if zero_range else close - 1.0,
            "Close": close,
            "Volume": [1000.0] * rows,
        },
        index=index,
    )


def _signal_frame(rows: int = 8) -> pd.DataFrame:
    return pd.DataFrame(
        {"Close": [100.0 + i for i in range(rows)]},
        index=pd.date_range("2024-01-01", periods=rows, freq="D"),
    )


class TrackC32MLDatasetCorrectnessTest(unittest.TestCase):
    def test_continuous_rise_builds_finite_real_ml_dataset(self) -> None:
        source = _ohlcv("rising")
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(source, "2330.TW"),
        ):
            analyzed = analysis.analyze_stock("2330")
            dataset = ml_dataset.build_ml_dataset("2330", horizon=5)

        self.assertFalse(dataset.empty)
        self.assertEqual(list(dataset.columns[:-2]), ml_dataset.FEATURE_COLUMNS)
        self.assertIn("Future_Return_5D", dataset.columns)
        self.assertIn("Target_Up_5D", dataset.columns)
        self.assertTrue(dataset["RSI"].eq(100.0).all())
        self.assertTrue(np.isfinite(dataset[["K", "D"]].to_numpy(dtype=float)).all())
        self.assertTrue(
            np.isfinite(dataset[ml_dataset.FEATURE_COLUMNS].to_numpy(dtype=float)).all()
        )
        self.assertFalse(
            any(
                column.startswith(("Future_Return_", "Target_Up_"))
                for column in ml_dataset.FEATURE_COLUMNS
            )
        )
        self.assertEqual(dataset.index.tolist(), analyzed.signal_df.index[:-5].tolist())
        self.assertTrue(dataset.index.is_monotonic_increasing)
        self.assertTrue(dataset.index.is_unique)

    def test_flat_default_dropna_is_empty_only_because_k_and_d_are_nan(self) -> None:
        source = _ohlcv("flat")
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(source, "2317.TW"),
        ):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                dataset = ml_dataset.build_ml_dataset("2317", horizon=5, dropna=True)
            analyzed = analysis.analyze_stock("2317")

        retained_without_drop = ml_dataset.build_ml_dataset_from_signal_df(
            analyzed.signal_df,
            horizon=5,
            dropna=False,
        )
        retained_without_kd = ml_dataset.build_ml_dataset_from_signal_df(
            analyzed.signal_df.drop(columns=["K", "D"]),
            horizon=5,
            dropna=True,
        )
        other_features = [
            column for column in ml_dataset.FEATURE_COLUMNS if column not in {"K", "D"}
        ]

        self.assertTrue(dataset.empty)
        self.assertEqual(caught, [])
        self.assertTrue(retained_without_drop[["K", "D"]].isna().all().all())
        self.assertTrue(
            np.isfinite(retained_without_drop[other_features].to_numpy(dtype=float)).all()
        )
        self.assertTrue(retained_without_drop["Future_Return_5D"].eq(0.0).all())
        self.assertFalse(retained_without_drop["Target_Up_5D"].any())
        self.assertEqual(len(retained_without_kd), len(retained_without_drop))

    def test_flat_no_dropna_preserves_horizon_trimmed_rows_and_nan_kd(self) -> None:
        source = _ohlcv("flat")
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(source, "2317.TW"),
        ):
            analyzed = analysis.analyze_stock("2317")
            dataset = ml_dataset.build_ml_dataset("2317", horizon=5, dropna=False)

        self.assertEqual(len(dataset), len(analyzed.signal_df) - 5)
        self.assertEqual(dataset.index.tolist(), analyzed.signal_df.index[:-5].tolist())
        self.assertTrue(dataset.index.is_monotonic_increasing)
        self.assertTrue(dataset[["K", "D"]].isna().all().all())
        self.assertTrue(dataset["Future_Return_5D"].eq(0.0).all())
        self.assertEqual(dataset["Target_Up_5D"].dtype, bool)
        self.assertFalse(dataset["Target_Up_5D"].any())

    def test_future_return_and_target_align_with_real_analysis_dates(self) -> None:
        horizon = 5
        source = _ohlcv("oscillating")
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(source, "2454.TW"),
        ):
            analyzed = analysis.analyze_stock("2454")
            dataset = ml_dataset.build_ml_dataset("2454", horizon=horizon)

        expected_returns = []
        for date, row in dataset.iterrows():
            position = analyzed.signal_df.index.get_loc(date)
            current_close = float(analyzed.signal_df.iloc[position]["Close"])
            future_close = float(analyzed.signal_df.iloc[position + horizon]["Close"])
            expected = future_close / current_close - 1
            expected_returns.append(expected)
            self.assertAlmostEqual(float(row["Future_Return_5D"]), expected)
            self.assertEqual(bool(row["Target_Up_5D"]), expected > 0)
            self.assertEqual(float(row["Close"]), current_close)

        self.assertTrue(any(value > 0 for value in expected_returns))
        self.assertTrue(any(value <= 0 for value in expected_returns))
        self.assertEqual(dataset.index.tolist(), analyzed.signal_df.index[:-horizon].tolist())
        self.assertEqual(dataset["Target_Up_5D"].dtype, bool)

    def test_dropna_isolates_supported_feature_missingness_from_tail_and_extras(self) -> None:
        source = _ohlcv("rising")
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(source, "2330.TW"),
        ):
            signal_df = analysis.analyze_stock("2330").signal_df.copy()

        horizon = 5
        missing_date = signal_df.index[10]
        signal_df.loc[missing_date, "RSI"] = np.nan
        signal_df["Unsupported_NaN"] = np.nan
        kept = ml_dataset.build_ml_dataset_from_signal_df(
            signal_df,
            horizon=horizon,
            dropna=False,
        )
        dropped = ml_dataset.build_ml_dataset_from_signal_df(
            signal_df,
            horizon=horizon,
            dropna=True,
        )

        self.assertEqual(len(kept), len(signal_df) - horizon)
        self.assertEqual(len(dropped), len(kept) - 1)
        self.assertIn(missing_date, kept.index)
        self.assertNotIn(missing_date, dropped.index)
        self.assertNotIn("Unsupported_NaN", kept.columns)
        self.assertTrue(kept["Future_Return_5D"].notna().all())
        self.assertTrue(kept["Target_Up_5D"].notna().all())
        self.assertTrue(set(signal_df.index[-horizon:]).isdisjoint(kept.index))

    def test_small_horizon_returns_only_rows_with_real_future_values(self) -> None:
        signal_df = _signal_frame()
        result = ml_dataset.build_ml_dataset_from_signal_df(
            signal_df,
            horizon=2,
            dropna=False,
        )

        self.assertEqual(len(result), len(signal_df) - 2)
        self.assertEqual(result.index.tolist(), signal_df.index[:-2].tolist())
        self.assertTrue(result["Future_Return_2D"].notna().all())

    def test_equal_length_horizon_returns_empty_structured_dataset(self) -> None:
        signal_df = _signal_frame()
        result = ml_dataset.build_ml_dataset_from_signal_df(
            signal_df,
            horizon=len(signal_df),
            dropna=False,
        )

        self.assertTrue(result.empty)
        self.assertEqual(
            result.columns.tolist(),
            ["Close", "Future_Return_8D", "Target_Up_8D"],
        )

    def test_oversized_horizon_returns_empty_structured_dataset(self) -> None:
        signal_df = _signal_frame()
        result = ml_dataset.build_ml_dataset_from_signal_df(
            signal_df,
            horizon=len(signal_df) + 1,
            dropna=False,
        )

        self.assertTrue(result.empty)
        self.assertEqual(
            result.columns.tolist(),
            ["Close", "Future_Return_9D", "Target_Up_9D"],
        )

    def test_zero_and_negative_horizons_raise_explicit_value_error(self) -> None:
        deviations = []
        for horizon in (0, -1):
            try:
                ml_dataset.build_ml_dataset_from_signal_df(
                    _signal_frame(),
                    horizon=horizon,
                )
            except ValueError as exc:
                if "greater than 0" not in str(exc):
                    deviations.append(f"{horizon}: unclear error {exc}")
            except Exception as exc:
                deviations.append(f"{horizon}: wrong exception {type(exc).__name__}: {exc}")
            else:
                deviations.append(f"{horizon}: accepted")
        self.assertEqual(deviations, [])

    def test_normal_dataset_features_and_purged_windows_remain_chronological(self) -> None:
        source = _ohlcv("rising")
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(source, "2330.TW"),
        ):
            dataset = ml_dataset.build_ml_dataset("2330", horizon=5)

        features = ml_feature_columns(dataset)
        self.assertEqual(features, ml_dataset.FEATURE_COLUMNS)
        self.assertIn("K", features)
        self.assertIn("D", features)
        self.assertNotIn("K", ml_feature_columns(dataset.drop(columns=["K", "D"])))
        self.assertFalse(
            any(column.startswith(("Future_Return_", "Target_Up_")) for column in features)
        )
        _, train, test = split_time_windows(
            dataset,
            train_size=20,
            test_size=10,
            purge_size=5,
        )[0]
        self.assertEqual(train.index.tolist(), dataset.index[:20].tolist())
        self.assertEqual(test.index.tolist(), dataset.index[25:35].tolist())
        self.assertLess(dataset.index[24], test.index[0])
        self.assertTrue(train.index.is_monotonic_increasing)
        self.assertTrue(test.index.is_monotonic_increasing)

    def test_empty_flat_dataset_reports_features_but_rejects_fake_window(self) -> None:
        source = _ohlcv("flat")
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(source, "2317.TW"),
        ):
            dataset = ml_dataset.build_ml_dataset("2317", horizon=5, dropna=True)

        self.assertTrue(dataset.empty)
        self.assertEqual(ml_feature_columns(dataset), ml_dataset.FEATURE_COLUMNS)
        with self.assertRaisesRegex(
            ValueError,
            "Not enough rows.*need at least 7, got 0",
        ):
            split_time_windows(dataset, train_size=1, test_size=1, purge_size=5)

    def test_public_parameters_propagate_and_interval_is_not_applicable(self) -> None:
        calls: list[tuple[str, dict[str, object]]] = []

        def download(stock_id: str, **kwargs: object) -> tuple[pd.DataFrame, str]:
            calls.append((stock_id, kwargs))
            return _ohlcv("flat"), f"{stock_id}.TW"

        with patch.object(analysis, "download_tw_stock", side_effect=download):
            dataset = ml_dataset.build_ml_dataset(
                " 2330 ",
                period="5y",
                horizon=3,
                force_refresh=True,
                dropna=False,
            )

        self.assertEqual(len(calls), 1)
        stock_id, kwargs = calls[0]
        self.assertEqual(stock_id, "2330")
        self.assertEqual(kwargs["period"], "5y")
        self.assertTrue(kwargs["force_refresh"])
        self.assertIn("Future_Return_3D", dataset.columns)
        self.assertTrue(dataset[["K", "D"]].isna().all().all())
        self.assertNotIn("interval", inspect.signature(ml_dataset.build_ml_dataset).parameters)


if __name__ == "__main__":
    unittest.main()
