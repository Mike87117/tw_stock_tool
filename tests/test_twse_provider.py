import unittest
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.data.providers import twse_provider


class TwseProviderTest(unittest.TestCase):
    def test_monthly_request_and_row_parsing(self) -> None:
        class Response:
            def raise_for_status(self): pass
            def json(self): return {"stat": "OK", "data": [["113/01/02", "1,000", "", "10", "12", "9", "11"]]}
        final = pd.DataFrame({"Close": [11]})
        with patch.object(twse_provider.requests, "get", return_value=Response()) as get:
            actual = twse_provider.download_twse_stock("2330", "1mo", "1d", period_start=lambda _: pd.Timestamp("2024-01-01"), month_starts=lambda *_: [pd.Timestamp("2024-01-01")], parse_roc_date=lambda _: pd.Timestamp("2024-01-02"), to_float=float, to_int=lambda x: int(str(x).replace(",", "")), finalize_official_rows=lambda *args: final, error_type=RuntimeError)
        self.assertIs(actual, final)
        get.assert_called_once_with("https://www.twse.com.tw/exchangeReport/STOCK_DAY", params={"response": "json", "date": "20240101", "stockNo": "2330"}, timeout=20)

    def test_non_daily_interval_is_rejected_before_network(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "only supports 1d"):
            twse_provider.download_twse_stock("2330", "1mo", "1wk", period_start=lambda _: None, month_starts=lambda *_: [], parse_roc_date=lambda _: None, to_float=float, to_int=int, finalize_official_rows=lambda *_: None, error_type=RuntimeError)