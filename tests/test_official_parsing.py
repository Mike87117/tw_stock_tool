import unittest

import pandas as pd

from tw_stock_tool.data import official_parsing


class OfficialParsingTest(unittest.TestCase):
    def test_period_month_date_and_numeric_contracts(self) -> None:
        self.assertEqual(official_parsing.parse_roc_date("113/01/02"), pd.Timestamp("2024-01-02"))
        self.assertEqual(official_parsing.parse_tpex_date("1130102", parse_roc_date=official_parsing.parse_roc_date), pd.Timestamp("2024-01-02"))
        self.assertEqual(official_parsing.parse_tpex_date("01/02", pd.Timestamp("2024-01-01"), parse_roc_date=official_parsing.parse_roc_date), pd.Timestamp("2024-01-02"))
        self.assertEqual(official_parsing.to_float("1,234.5"), 1234.5)
        self.assertTrue(pd.isna(official_parsing.to_float("--")))
        self.assertEqual(official_parsing.to_int("1,234.9", to_float=official_parsing.to_float), 1234)
        self.assertEqual(official_parsing.month_starts(pd.Timestamp("2024-01-15"), pd.Timestamp("2024-03-01")), [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01"), pd.Timestamp("2024-03-01")])