import unittest
from unittest.mock import Mock, patch

import pandas as pd

from tw_stock_tool.data import official_parsing


class OfficialParsingTest(unittest.TestCase):
    def test_period_start_uses_expected_month_offsets(self) -> None:
        today = pd.Timestamp("2026-07-31")
        expected_months = {
            "1d": 1,
            "5d": 1,
            "1mo": 1,
            "3mo": 3,
            "6mo": 6,
            "1y": 12,
            "2y": 24,
            "5y": 60,
            "10y": 120,
            "max": 180,
            "unknown": 12,
        }
        with patch.object(
            official_parsing.pd.Timestamp,
            "today",
            return_value=today,
        ):
            for period, months in expected_months.items():
                with self.subTest(period=period):
                    self.assertEqual(
                        official_parsing.period_start(period),
                        today - pd.DateOffset(months=months),
                    )

    def test_period_start_ytd_returns_first_day_of_current_year(self) -> None:
        with patch.object(
            official_parsing.pd.Timestamp,
            "today",
            return_value=pd.Timestamp("2026-07-31 18:30:00"),
        ):
            self.assertEqual(
                official_parsing.period_start("ytd"),
                pd.Timestamp("2026-01-01"),
            )

    def test_month_starts_are_inclusive_and_normalized_to_first_day(self) -> None:
        self.assertEqual(
            official_parsing.month_starts(
                pd.Timestamp("2024-01-15"),
                pd.Timestamp("2024-03-31"),
            ),
            [
                pd.Timestamp("2024-01-01"),
                pd.Timestamp("2024-02-01"),
                pd.Timestamp("2024-03-01"),
            ],
        )
        self.assertEqual(
            official_parsing.month_starts(
                pd.Timestamp("2024-03-20"),
                pd.Timestamp("2024-03-21"),
            ),
            [pd.Timestamp("2024-03-01")],
        )
        self.assertEqual(
            official_parsing.month_starts(
                pd.Timestamp("2024-04-01"),
                pd.Timestamp("2024-03-31"),
            ),
            [],
        )

    def test_parse_roc_date_accepts_whitespace_and_converts_year(self) -> None:
        self.assertEqual(
            official_parsing.parse_roc_date(" 113 / 01 / 02 "),
            pd.Timestamp("2024-01-02"),
        )

    def test_parse_roc_date_rejects_wrong_part_count_with_exact_message(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "^Invalid ROC date: 1130102$",
        ):
            official_parsing.parse_roc_date("1130102")

    def test_parse_tpex_date_supports_all_current_formats(self) -> None:
        parse_roc = Mock(return_value=pd.Timestamp("2024-01-02"))
        self.assertEqual(
            official_parsing.parse_tpex_date(
                "113/01/02",
                parse_roc_date=parse_roc,
            ),
            pd.Timestamp("2024-01-02"),
        )
        parse_roc.assert_called_once_with("113/01/02")
        self.assertEqual(
            official_parsing.parse_tpex_date(
                "01/03",
                pd.Timestamp("2024-01-01"),
                parse_roc_date=official_parsing.parse_roc_date,
            ),
            pd.Timestamp("2024-01-03"),
        )
        self.assertEqual(
            official_parsing.parse_tpex_date(
                "1130104",
                parse_roc_date=official_parsing.parse_roc_date,
            ),
            pd.Timestamp("2024-01-04"),
        )
        self.assertEqual(
            official_parsing.parse_tpex_date(
                "20240105",
                parse_roc_date=official_parsing.parse_roc_date,
            ),
            pd.Timestamp("2024-01-05"),
        )

    def test_parse_tpex_date_rejects_unsupported_formats_exactly(self) -> None:
        for value in ("01/02", "invalid", "123456"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValueError,
                    f"^Invalid TPEX date: {value}$",
                ):
                    official_parsing.parse_tpex_date(
                        value,
                        parse_roc_date=official_parsing.parse_roc_date,
                    )

    def test_to_float_cleans_commas_dashes_and_blank_values(self) -> None:
        self.assertEqual(official_parsing.to_float("1,234.5"), 1234.5)
        self.assertEqual(official_parsing.to_float(" -12.5 "), -12.5)
        self.assertTrue(pd.isna(official_parsing.to_float("--")))
        self.assertTrue(pd.isna(official_parsing.to_float("  ")))

    def test_to_float_propagates_invalid_numeric_error(self) -> None:
        with self.assertRaises(ValueError):
            official_parsing.to_float("not-a-number")

    def test_to_int_uses_injected_float_parser_and_truncates(self) -> None:
        to_float = Mock(return_value=1234.9)
        self.assertEqual(
            official_parsing.to_int("ignored", to_float=to_float),
            1234,
        )
        to_float.assert_called_once_with("ignored")


if __name__ == "__main__":
    unittest.main()
