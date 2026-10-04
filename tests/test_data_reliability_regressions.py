from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from tw_stock_tool.data import data_loader


def _prices(value=100.):
    return pd.DataFrame({"Open": value, "High": value + 2, "Low": value - 1,
                         "Close": value + 1, "Volume": 1000},
                        index=pd.date_range("2026-01-01", periods=200).rename("Date"))


class DataReliabilityRegressionTest(unittest.TestCase):
    def test_interrupted_refresh_returns_live_data_but_preserves_complete_cache(self):
        original_to_csv = pd.DataFrame.to_csv

        def interrupted_write(frame, destination):
            original_to_csv(frame.iloc[:80], destination)
            raise OSError("disk write interrupted")

        with tempfile.TemporaryDirectory() as temporary, patch.object(data_loader, "CACHE_DIR", Path(temporary)):
            path = data_loader._cache_path("2330.TW", "1y", "1d", True)
            data_loader._write_cache(_prices(), path)
            with patch.object(data_loader, "_download_yfinance_quiet", return_value=_prices(200)), \
                 patch.object(pd.DataFrame, "to_csv", interrupted_write), redirect_stderr(StringIO()) as stderr:
                live, _ = data_loader.download_tw_stock("2330.TW", auto_adjust=True, force_refresh=True)
            self.assertEqual(len(live), 200)
            self.assertEqual(live.iloc[0]["Open"], 200)
            self.assertIn("cache write failed", stderr.getvalue())
            with patch.object(data_loader, "_download_yfinance_quiet", side_effect=AssertionError("unexpected download")) as provider:
                cached, _ = data_loader.download_tw_stock("2330.TW", auto_adjust=True)
            provider.assert_not_called()
            pd.testing.assert_frame_equal(cached, _prices(), check_freq=False)

    def test_failed_official_month_does_not_cache_partial_data_or_replace_old_cache(self):
        months = list(pd.date_range("2026-08-01", periods=3, freq="MS"))
        for symbol, provider_name in (("2330.TW", "TWSE"), ("6488.TWO", "TPEX")):
            for failed_month in (1, 2):
                with self.subTest(symbol=symbol, failed_month=failed_month), tempfile.TemporaryDirectory() as temporary:
                    payloads = []
                    for i, month in enumerate(months):
                        row = [f"115/{month.month:02d}/03", "1000", "", "100", "102", "99", "101"]
                        payloads.append({"stat": "upstream service error"} if i == failed_month else
                                        {"stat": "OK", "data": [row]} if provider_name == "TWSE" else
                                        {"stat": "OK", "tables": [{"data": [row]}]})
                    responses = [Mock(**{"json.return_value": payload}) for payload in payloads]
                    with patch.object(data_loader, "CACHE_DIR", Path(temporary)), \
                         patch.object(data_loader, "_period_start", return_value=months[0]), \
                         patch.object(data_loader, "_month_starts", return_value=months), \
                         patch.object(data_loader, "_download_yfinance_quiet", return_value=pd.DataFrame()), \
                         patch.object(data_loader.requests, "get", side_effect=responses):
                        path = data_loader._cache_path(symbol, "1y", "1d", False)
                        data_loader._write_cache(_prices(), path)
                        original = path.read_bytes()
                        with patch.object(data_loader, "_write_cache", wraps=data_loader._write_cache) as write:
                            with self.assertRaisesRegex(data_loader.DataLoaderError,
                                                        f"{provider_name} {months[failed_month]:%Y-%m} request failed"):
                                data_loader.download_tw_stock(symbol, auto_adjust=False, force_refresh=True)
                        write.assert_not_called()
                        self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
