import unittest
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.cli import price_data_smoke_check


def _price_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [101.0, 102.0],
            "Volume": [1000, 1200],
        }
    )


class PriceDataSmokeCheckTest(unittest.TestCase):
    def test_pass_scenario(self) -> None:
        def fake_download(stock_id: str, **kwargs):
            suffix = ".TWO" if stock_id == "8069" else ".TW"
            return _price_df(), f"{stock_id}{suffix}"

        with patch.object(price_data_smoke_check.data_loader, "download_tw_stock", side_effect=fake_download) as mocked:
            result = price_data_smoke_check.run_smoke_check()

        self.assertEqual(mocked.call_count, 4)
        self.assertTrue(all(row["Status"] == "PASS" for row in result))
        self.assertEqual([row["Rows"] for row in result], [2, 2, 2, 2])

    def test_empty_dataframe_fails(self) -> None:
        with self.assertRaisesRegex(price_data_smoke_check.PriceDataSmokeCheckError, "empty"):
            price_data_smoke_check._validate_price_data(pd.DataFrame(), "2330.TW")

    def test_missing_required_column_fails(self) -> None:
        df = _price_df().drop(columns=["Volume"])

        with self.assertRaisesRegex(price_data_smoke_check.PriceDataSmokeCheckError, "missing required columns"):
            price_data_smoke_check._validate_price_data(df, "2330.TW")

    def test_single_check_failure_makes_overall_fail(self) -> None:
        def fake_download(stock_id: str, **kwargs):
            if stock_id == "8069" and kwargs.get("auto_adjust") is True:
                raise RuntimeError("source down")
            suffix = ".TWO" if stock_id == "8069" else ".TW"
            return _price_df(), f"{stock_id}{suffix}"

        with patch.object(price_data_smoke_check.data_loader, "download_tw_stock", side_effect=fake_download):
            with self.assertRaisesRegex(price_data_smoke_check.PriceDataSmokeCheckError, "source down"):
                price_data_smoke_check.run_smoke_check()

    def test_run_one_check_returns_fail_row(self) -> None:
        with patch.object(
            price_data_smoke_check.data_loader,
            "download_tw_stock",
            side_effect=RuntimeError("boom"),
        ):
            row = price_data_smoke_check.run_one_check("test", "2330")

        self.assertEqual(row["Status"], "FAIL")
        self.assertIn("boom", row["Error"])

    def test_parse_args(self) -> None:
        args = price_data_smoke_check._parse_args(
            [
                "--twse-stock",
                "2317",
                "--tpex-stock",
                "8299",
                "--period",
                "3mo",
                "--interval",
                "1wk",
            ]
        )

        self.assertEqual(args.twse_stock, "2317")
        self.assertEqual(args.tpex_stock, "8299")
        self.assertEqual(args.period, "3mo")
        self.assertEqual(args.interval, "1wk")


if __name__ == "__main__":
    unittest.main()
