import unittest
from unittest.mock import Mock

import pandas as pd

from tw_stock_tool.data import ohlcv_normalization


class OhlcvNormalizationTest(unittest.TestCase):
    def test_normalize_columns_preserves_flat_frame_identity(self) -> None:
        frame = pd.DataFrame({"Close": [1.0]})
        self.assertIs(ohlcv_normalization.normalize_columns(frame), frame)
        self.assertEqual(list(frame.columns), ["Close"])

    def test_normalize_columns_flattens_multiindex_in_place(self) -> None:
        frame = pd.DataFrame(
            [[10, 12, 9, 11, 1000]],
            columns=pd.MultiIndex.from_tuples(
                [
                    (name, "2330.TW")
                    for name in ("Open", "High", "Low", "Close", "Volume")
                ]
            ),
        )

        actual = ohlcv_normalization.normalize_columns(frame)

        self.assertIs(actual, frame)
        self.assertEqual(
            list(actual.columns),
            ["Open", "High", "Low", "Close", "Volume"],
        )

    def test_prepare_selects_exact_columns_drops_bad_ohlc_and_preserves_volume_nan(self) -> None:
        frame = pd.DataFrame(
            {
                "Volume": [None, 2],
                "Close": [11, 21],
                "Open": [10, None],
                "Extra": [1, 2],
                "Low": [9, 19],
                "High": [12, 22],
            },
            index=["2024-01-02", "2024-01-03"],
        )

        actual = ohlcv_normalization.prepare_ohlcv(
            frame,
            "2330.TW",
            normalize_columns=ohlcv_normalization.normalize_columns,
            error_type=RuntimeError,
        )

        self.assertEqual(
            list(actual.columns),
            ["Open", "High", "Low", "Close", "Volume"],
        )
        self.assertEqual(len(actual), 1)
        self.assertIsInstance(actual.index, pd.DatetimeIndex)
        self.assertEqual(actual.index.name, "Date")
        self.assertTrue(pd.isna(actual.iloc[0]["Volume"]))

    def test_prepare_rejects_missing_columns_with_exact_list(self) -> None:
        frame = pd.DataFrame(
            {"Open": [1], "Low": [1], "Close": [1]},
            index=["2024-01-01"],
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "^Missing data columns: \\['High', 'Volume'\\]$",
        ):
            ohlcv_normalization.prepare_ohlcv(
                frame,
                "2330.TW",
                normalize_columns=ohlcv_normalization.normalize_columns,
                error_type=RuntimeError,
            )

    def test_prepare_rejects_all_unusable_ohlc_rows(self) -> None:
        frame = pd.DataFrame(
            {
                "Open": [None],
                "High": [12],
                "Low": [9],
                "Close": [11],
                "Volume": [1000],
            },
            index=["2024-01-01"],
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "^2330\\.TW has no usable OHLC data\\.$",
        ):
            ohlcv_normalization.prepare_ohlcv(
                frame,
                "2330.TW",
                normalize_columns=ohlcv_normalization.normalize_columns,
                error_type=RuntimeError,
            )

    def test_prepare_rejects_invalid_datetime_index_exactly(self) -> None:
        frame = pd.DataFrame(
            {
                name: [1]
                for name in ("Open", "High", "Low", "Close", "Volume")
            },
            index=["not-a-date"],
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "^2330\\.TW index is not a valid DatetimeIndex\\.$",
        ):
            ohlcv_normalization.prepare_ohlcv(
                frame,
                "2330.TW",
                normalize_columns=ohlcv_normalization.normalize_columns,
                error_type=RuntimeError,
            )

    def test_prepare_sorts_reverse_chronological_prices(self) -> None:
        frame = pd.DataFrame(
            {"Open": [12, 11], "High": [13, 12], "Low": [11, 10],
             "Close": [12, 11], "Volume": [120, 110]},
            index=["2024-01-03", "2024-01-02"],
        )

        actual = ohlcv_normalization.prepare_ohlcv(
            frame, "2330.TW",
            normalize_columns=ohlcv_normalization.normalize_columns,
            error_type=RuntimeError,
        )

        self.assertEqual(actual.index.tolist(), [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")])
        self.assertEqual(actual["Close"].tolist(), [11, 12])

    def test_prepare_rejects_duplicate_or_missing_dates(self) -> None:
        for index, message in (
            (["2024-01-02", "2024-01-02"], "duplicate dates"),
            (["2024-01-02", None], "not a valid DatetimeIndex"),
        ):
            with self.subTest(index=index):
                frame = pd.DataFrame(
                    {name: [1, 2] for name in ("Open", "High", "Low", "Close", "Volume")},
                    index=index,
                )
                with self.assertRaisesRegex(RuntimeError, message):
                    ohlcv_normalization.prepare_ohlcv(
                        frame, "2330.TW",
                        normalize_columns=ohlcv_normalization.normalize_columns,
                        error_type=RuntimeError,
                    )

    def test_finalize_rejects_empty_rows_with_exact_symbol(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "^Official fallback has no data: 6488\\.TWO$",
        ):
            ohlcv_normalization.finalize_official_rows(
                [],
                "6488",
                ".TWO",
                pd.Timestamp("2024-01-01"),
                "1mo",
                prepare_ohlcv=Mock(),
                error_type=RuntimeError,
            )

    def _valid_price_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {"Open": [10., 11.], "High": [12., 13.], "Low": [9., 10.],
             "Close": [11., 12.], "Volume": [100., 200.]},
            index=pd.date_range("2026-01-01", periods=2),
        )

    def test_prepare_rejects_nonfinite_nonpositive_or_nonnumeric_prices(self) -> None:
        for column in ("Open", "High", "Low"):
            for value in (float("inf"), float("-inf"), 0., -1., True, "10"):
                with self.subTest(column=column, value=value):
                    frame = self._valid_price_frame()
                    frame[column] = frame[column].astype(object)
                    frame.at[frame.index[-1], column] = value
                    original = frame.copy(deep=True)
                    with self.assertRaisesRegex(RuntimeError, column):
                        ohlcv_normalization.prepare_ohlcv(
                            frame, "2330.TW", normalize_columns=ohlcv_normalization.normalize_columns,
                            error_type=RuntimeError,
                        )
                    pd.testing.assert_frame_equal(frame, original)

    def test_prepare_rejects_invalid_volume_but_preserves_zero_and_missing(self) -> None:
        for value in (float("inf"), float("-inf"), -1., True, "100"):
            with self.subTest(value=value):
                frame = self._valid_price_frame()
                frame["Volume"] = frame["Volume"].astype(object)
                frame.at[frame.index[-1], "Volume"] = value
                with self.assertRaisesRegex(RuntimeError, "Volume"):
                    ohlcv_normalization.prepare_ohlcv(
                        frame, "2330.TW", normalize_columns=ohlcv_normalization.normalize_columns,
                        error_type=RuntimeError,
                    )
        frame = self._valid_price_frame()
        frame["Volume"] = [0., float("nan")]
        result = ohlcv_normalization.prepare_ohlcv(
            frame, "2330.TW", normalize_columns=ohlcv_normalization.normalize_columns,
            error_type=RuntimeError,
        )
        self.assertEqual(result["Volume"].iloc[0], 0.)
        self.assertTrue(pd.isna(result["Volume"].iloc[1]))

    def test_prepare_rejects_numeric_and_mixed_date_indexes(self) -> None:
        for index in (pd.RangeIndex(2), [0., 1.], [True, False],
                      pd.Index(["2026-01-01", 1], dtype=object),
                      pd.Index([0, 1], dtype=object)):
            with self.subTest(index=index):
                frame = self._valid_price_frame()
                frame.index = index
                with self.assertRaisesRegex(RuntimeError, "not a valid DatetimeIndex"):
                    ohlcv_normalization.prepare_ohlcv(
                        frame, "2330.TW", normalize_columns=ohlcv_normalization.normalize_columns,
                        error_type=RuntimeError,
                    )

    def test_prepare_preserves_timezone_aware_and_calendar_date_indexes(self) -> None:
        for index in (pd.date_range("2026-01-01", periods=2, tz="Asia/Taipei"),
                      ["20260101", "20260102"],
                      pd.date_range("2026-01-01", periods=2).date):
            with self.subTest(index=index):
                frame = self._valid_price_frame()
                frame.index = index
                result = ohlcv_normalization.prepare_ohlcv(
                    frame, "2330.TW", normalize_columns=ohlcv_normalization.normalize_columns,
                    error_type=RuntimeError,
                )
                pd.testing.assert_index_equal(result.index, pd.DatetimeIndex(pd.to_datetime(index), name="Date"))

    def test_finalize_deduplicates_sorts_filters_and_passes_exact_symbol(self) -> None:
        rows = [
            {
                "Date": pd.Timestamp("2024-01-03"),
                "Open": 3,
                "High": 4,
                "Low": 2,
                "Close": 3,
                "Volume": 30,
            },
            {
                "Date": pd.Timestamp("2024-01-01"),
                "Open": 1,
                "High": 2,
                "Low": 0,
                "Close": 1,
                "Volume": 10,
            },
            {
                "Date": pd.Timestamp("2024-01-03"),
                "Open": 99,
                "High": 99,
                "Low": 99,
                "Close": 99,
                "Volume": 99,
            },
            {
                "Date": pd.Timestamp("2024-01-02"),
                "Open": 2,
                "High": 3,
                "Low": 1,
                "Close": 2,
                "Volume": 20,
            },
        ]
        expected = pd.DataFrame({"Close": [2, 3]})
        prepare = Mock(return_value=expected)

        actual = ohlcv_normalization.finalize_official_rows(
            rows,
            "2330",
            ".TW",
            pd.Timestamp("2024-01-02"),
            "1mo",
            prepare_ohlcv=prepare,
            error_type=RuntimeError,
        )

        self.assertIs(actual, expected)
        passed_frame, passed_symbol = prepare.call_args.args
        self.assertEqual(passed_symbol, "2330.TW")
        self.assertEqual(
            list(passed_frame.index),
            [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")],
        )
        self.assertEqual(float(passed_frame.iloc[-1]["Close"]), 3.0)

    def test_finalize_limits_one_and_five_day_periods(self) -> None:
        rows = [
            {
                "Date": pd.Timestamp(f"2024-01-{day:02d}"),
                "Open": day,
                "High": day + 1,
                "Low": day - 1,
                "Close": day,
                "Volume": day,
            }
            for day in range(1, 8)
        ]

        for period, expected_length, first_day in (
            ("1d", 1, 7),
            ("5d", 5, 3),
        ):
            with self.subTest(period=period):
                prepare = Mock(side_effect=lambda frame, symbol: frame)
                actual = ohlcv_normalization.finalize_official_rows(
                    rows,
                    "2330",
                    ".TW",
                    pd.Timestamp("2024-01-01"),
                    period,
                    prepare_ohlcv=prepare,
                    error_type=RuntimeError,
                )
                self.assertEqual(len(actual), expected_length)
                self.assertEqual(actual.index[0].day, first_day)


if __name__ == "__main__":
    unittest.main()
