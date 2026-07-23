import unittest
from unittest.mock import Mock, patch

import pandas as pd

from tw_stock_tool.cli import stock_list_smoke_check


def _frame(stocks: list[str], market: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Stock": stock, "Name": f"Name {stock}", "Market": market, "Type": "stock"}
            for stock in stocks
        ]
    )


class StockListSmokeCheckTest(unittest.TestCase):
    def _patch_sources(self, twse_stocks: list[str], tpex_stocks: list[str]):
        return patch.multiple(
            stock_list_smoke_check.stock_list_updater,
            fetch_twse_stock_list=Mock(return_value=_frame(twse_stocks, "TWSE")),
            fetch_tpex_stock_list=Mock(return_value=_frame(tpex_stocks, "TPEX")),
        )

    def test_pass_scenario(self) -> None:
        twse = ["2330", "2317", "1101"]
        tpex = ["8069", "8299"]
        with self._patch_sources(twse, tpex):
            result = stock_list_smoke_check.run_smoke_check(
                min_twse=3,
                min_tpex=2,
                min_all=5,
            )

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["twse_count"], 3)
        self.assertEqual(result["tpex_count"], 2)
        self.assertEqual(result["all_count"], 5)
        self.assertEqual(result["missing_expected_stocks"], [])

    def test_twse_count_too_low_fails(self) -> None:
        with self._patch_sources(["2330", "2317"], ["8069", "8299"]):
            with self.assertRaisesRegex(stock_list_smoke_check.StockListSmokeCheckError, "TWSE count too low"):
                stock_list_smoke_check.run_smoke_check(min_twse=3, min_tpex=2, min_all=4)

    def test_tpex_count_too_low_fails(self) -> None:
        with self._patch_sources(["2330", "2317", "1101"], ["8069"]):
            with self.assertRaisesRegex(stock_list_smoke_check.StockListSmokeCheckError, "TPEx count too low"):
                stock_list_smoke_check.run_smoke_check(min_twse=3, min_tpex=2, min_all=4)

    def test_all_count_too_low_fails(self) -> None:
        with self._patch_sources(["2330", "2317"], ["8069"]):
            with self.assertRaisesRegex(stock_list_smoke_check.StockListSmokeCheckError, "All count too low"):
                stock_list_smoke_check.run_smoke_check(min_twse=2, min_tpex=1, min_all=4)

    def test_missing_expected_stock_fails(self) -> None:
        with self._patch_sources(["2330", "2317"], ["8299"]):
            with self.assertRaisesRegex(stock_list_smoke_check.StockListSmokeCheckError, "Missing expected stocks: 8069"):
                stock_list_smoke_check.run_smoke_check(min_twse=2, min_tpex=1, min_all=3)

    def test_parse_args(self) -> None:
        args = stock_list_smoke_check._parse_args([
            "--min-twse",
            "120",
            "--min-tpex",
            "130",
            "--min-all",
            "600",
        ])

        self.assertEqual(args.min_twse, 120)
        self.assertEqual(args.min_tpex, 130)
        self.assertEqual(args.min_all, 600)


if __name__ == "__main__":
    unittest.main()
