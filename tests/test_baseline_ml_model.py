import unittest
from unittest.mock import patch

import pandas as pd

import baseline_ml_model


def _sample_dataset(rows: int = 18) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="D")
    return pd.DataFrame(
        {
            "Close": [100.0 + i for i in range(rows)],
            "MA5": [99.0 + i for i in range(rows)],
            "RSI": [45.0 + (i % 10) for i in range(rows)],
            "Score": [float(i % 6) for i in range(rows)],
            "Future_Return_5D": [0.01 if i % 2 == 0 else -0.01 for i in range(rows)],
            "Target_Up_5D": [i % 2 == 0 for i in range(rows)],
        },
        index=index,
    )


class BaselineMLModelTest(unittest.TestCase):
    def test_run_uses_mocked_dataset_without_network(self) -> None:
        dataset = _sample_dataset()
        with patch.object(baseline_ml_model, "build_ml_dataset", return_value=dataset) as mocked:
            result = baseline_ml_model.run_baseline_ml_model(
                "2330",
                period="5y",
                horizon=5,
                train_size=8,
                test_size=4,
                step_size=4,
                force_refresh=True,
                dropna=False,
                n_estimators=5,
                random_state=7,
            )

        mocked.assert_called_once_with(
            stock_id="2330",
            period="5y",
            horizon=5,
            force_refresh=True,
            dropna=False,
        )
        self.assertFalse(result.empty)

    def test_train_test_do_not_overlap(self) -> None:
        with patch.object(baseline_ml_model, "build_ml_dataset", return_value=_sample_dataset()):
            result = baseline_ml_model.run_baseline_ml_model(
                "2330",
                train_size=8,
                test_size=4,
                step_size=4,
                n_estimators=5,
            )

        self.assertTrue((result["Train End"] < result["Test Start"]).all())

    def test_split_is_chronological_and_not_shuffled(self) -> None:
        shuffled = _sample_dataset(14).sample(frac=1.0, random_state=11)
        with patch.object(baseline_ml_model, "build_ml_dataset", return_value=shuffled):
            result = baseline_ml_model.run_baseline_ml_model(
                "2330",
                train_size=6,
                test_size=3,
                n_estimators=5,
            )

        self.assertEqual(result.iloc[0]["Train Start"], pd.Timestamp("2024-01-01"))
        self.assertLess(result.iloc[0]["Train End"], result.iloc[0]["Test Start"])

    def test_feature_columns_exclude_future_and_target(self) -> None:
        dataset = _sample_dataset()
        features = baseline_ml_model.ml_feature_columns(dataset)

        self.assertTrue(features)
        self.assertFalse(any(column.startswith("Future_Return_") for column in features))
        self.assertFalse(any(column.startswith("Target_Up_") for column in features))

    def test_result_contains_classification_metrics(self) -> None:
        with patch.object(baseline_ml_model, "build_ml_dataset", return_value=_sample_dataset()):
            result = baseline_ml_model.run_baseline_ml_model(
                "2330",
                train_size=8,
                test_size=4,
                n_estimators=5,
            )

        for column in ["Accuracy", "Precision", "Recall", "F1"]:
            self.assertIn(column, result.columns)
            self.assertTrue(result[column].notna().all())

    def test_horizon_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            baseline_ml_model.run_baseline_ml_model("2330", horizon=0)

    def test_not_enough_rows_raises_value_error(self) -> None:
        with patch.object(baseline_ml_model, "build_ml_dataset", return_value=_sample_dataset(5)):
            with self.assertRaises(ValueError):
                baseline_ml_model.run_baseline_ml_model(
                    "2330",
                    train_size=4,
                    test_size=2,
                )

    def test_parse_args(self) -> None:
        args = baseline_ml_model._parse_args(
            [
                "--stock",
                "2330",
                "--period",
                "5y",
                "--horizon",
                "5",
                "--train-size",
                "8",
                "--test-size",
                "4",
                "--step-size",
                "4",
                "--n-estimators",
                "5",
                "--random-state",
                "7",
                "--no-dropna",
            ]
        )

        self.assertEqual(args.stock, "2330")
        self.assertEqual(args.period, "5y")
        self.assertEqual(args.horizon, 5)
        self.assertEqual(args.train_size, 8)
        self.assertEqual(args.test_size, 4)
        self.assertEqual(args.step_size, 4)
        self.assertEqual(args.n_estimators, 5)
        self.assertEqual(args.random_state, 7)
        self.assertFalse(args.dropna)


if __name__ == "__main__":
    unittest.main()
