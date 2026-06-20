import unittest
from unittest.mock import patch

import pandas as pd

import ai_walk_forward


def _sample_dataset(rows: int = 12) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="D")
    return pd.DataFrame(
        {
            "Close": [100.0 + i for i in range(rows)],
            "MA5": [99.0 + i for i in range(rows)],
            "RSI": [45.0 + (i % 10) for i in range(rows)],
            "Score": [i % 6 for i in range(rows)],
            "Future_Return_5D": [0.01 if i % 2 == 0 else -0.01 for i in range(rows)],
            "Target_Up_5D": [i % 2 == 0 for i in range(rows)],
        },
        index=index,
    )


class AIWalkForwardTest(unittest.TestCase):
    def test_split_time_windows_keeps_chronological_order(self) -> None:
        dataset = _sample_dataset(10)
        windows = ai_walk_forward.split_time_windows(
            dataset,
            train_size=4,
            test_size=2,
            step_size=2,
        )

        self.assertEqual(len(windows), 3)
        for _, train, test in windows:
            self.assertLess(train.index[-1], test.index[0])
            self.assertTrue(set(train.index).isdisjoint(set(test.index)))

    def test_split_time_windows_sorts_by_time_without_shuffle(self) -> None:
        dataset = _sample_dataset(8).sample(frac=1.0, random_state=7)
        windows = ai_walk_forward.split_time_windows(dataset, train_size=3, test_size=2)
        _, train, test = windows[0]

        self.assertEqual(list(train.index), sorted(train.index))
        self.assertEqual(list(test.index), sorted(test.index))
        self.assertLess(train.index[-1], test.index[0])
    def test_run_ai_walk_forward_uses_build_ml_dataset(self) -> None:
        dataset = _sample_dataset(12)
        with patch.object(ai_walk_forward, "build_ml_dataset", return_value=dataset) as mocked:
            result = ai_walk_forward.run_ai_walk_forward(
                "2330",
                period="5y",
                horizon=5,
                train_size=4,
                test_size=2,
                step_size=2,
                force_refresh=True,
                dropna=False,
            )

        mocked.assert_called_once_with(
            stock_id="2330",
            period="5y",
            horizon=5,
            force_refresh=True,
            dropna=False,
        )
        self.assertFalse(result.empty)
        self.assertEqual(result.iloc[0]["Train Rows"], 4)
        self.assertEqual(result.iloc[0]["Test Rows"], 2)

    def test_run_ai_walk_forward_train_test_do_not_overlap(self) -> None:
        with patch.object(ai_walk_forward, "build_ml_dataset", return_value=_sample_dataset(12)):
            result = ai_walk_forward.run_ai_walk_forward(
                "2330",
                train_size=4,
                test_size=2,
                step_size=2,
            )

        self.assertTrue((result["Train End"] < result["Test Start"]).all())

    def test_feature_columns_exclude_future_and_target(self) -> None:
        features = ai_walk_forward.ml_feature_columns(_sample_dataset())

        self.assertTrue(features)
        self.assertFalse(any(column.startswith("Future_Return_") for column in features))
        self.assertFalse(any(column.startswith("Target_Up_") for column in features))

    def test_horizon_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            ai_walk_forward.run_ai_walk_forward("2330", horizon=0)

    def test_not_enough_rows_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            ai_walk_forward.split_time_windows(_sample_dataset(5), train_size=4, test_size=2)

    def test_missing_target_column_raises_value_error(self) -> None:
        dataset = _sample_dataset(10).drop(columns=["Target_Up_5D"])
        with patch.object(ai_walk_forward, "build_ml_dataset", return_value=dataset):
            with self.assertRaises(ValueError):
                ai_walk_forward.run_ai_walk_forward("2330", train_size=4, test_size=2)

    def test_parse_args(self) -> None:
        args = ai_walk_forward._parse_args(
            [
                "--stock",
                "2330",
                "--period",
                "5y",
                "--horizon",
                "5",
                "--train-size",
                "4",
                "--test-size",
                "2",
                "--step-size",
                "2",
                "--no-dropna",
            ]
        )

        self.assertEqual(args.stock, "2330")
        self.assertEqual(args.period, "5y")
        self.assertEqual(args.horizon, 5)
        self.assertEqual(args.train_size, 4)
        self.assertEqual(args.test_size, 2)
        self.assertEqual(args.step_size, 2)
        self.assertFalse(args.dropna)


if __name__ == "__main__":
    unittest.main()
