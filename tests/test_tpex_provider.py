import unittest
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.data.providers import tpex_provider


class TpexProviderTest(unittest.TestCase):
    def test_empty_months_use_latest_quote_fallback(self) -> None:
        class Response:
            def raise_for_status(self): pass
            def json(self): return {"stat": "not ok"}
        expected = pd.DataFrame({"Close": [11]})
        with patch.object(tpex_provider.requests, "get", return_value=Response()) as get:
            actual = tpex_provider.download_tpex_stock("6488", "1mo", "1d", period_start=lambda _: pd.Timestamp("2024-01-01"), month_starts=lambda *_: [pd.Timestamp("2024-01-01")], parse_tpex_date=lambda *_: None, to_float=float, to_int=int, finalize_official_rows=lambda *_: None, download_latest_quote=lambda *_: expected, error_type=RuntimeError)
        self.assertIs(actual, expected)
        self.assertEqual(get.call_args.kwargs["params"]["id"], "6488")

    def test_non_daily_interval_is_rejected_before_network(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "only supports 1d"):
            tpex_provider.download_tpex_stock("6488", "1mo", "1wk", period_start=lambda _: None, month_starts=lambda *_: [], parse_tpex_date=lambda *_: None, to_float=float, to_int=int, finalize_official_rows=lambda *_: None, download_latest_quote=lambda *_: None, error_type=RuntimeError)