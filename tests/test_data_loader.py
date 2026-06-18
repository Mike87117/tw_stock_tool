from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

import data_loader


def _download_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [10.0, 11.0],
            "High": [12.0, 13.0],
            "Low": [9.0, 10.0],
            "Close": [11.0, 12.0],
            "Volume": [1000, 1100],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="D"),
    )


class DataLoaderTest(unittest.TestCase):
    def test_download_writes_and_reads_today_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(
                    data_loader.yf,
                    "download",
                    return_value=_download_df(),
                ) as download:
                    first_df, first_symbol = data_loader.download_tw_stock("2330", period="1y")
                    second_df, second_symbol = data_loader.download_tw_stock("2330", period="1y")

        self.assertEqual(first_symbol, "2330.TW")
        self.assertEqual(second_symbol, "2330.TW")
        self.assertEqual(download.call_count, 1)
        pd.testing.assert_frame_equal(first_df, second_df, check_freq=False)

    def test_force_refresh_ignores_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(
                    data_loader.yf,
                    "download",
                    return_value=_download_df(),
                ) as download:
                    data_loader.download_tw_stock("2330", period="1y")
                    data_loader.download_tw_stock("2330", period="1y", force_refresh=True)

        self.assertEqual(download.call_count, 2)

    def test_twse_fallback_when_yfinance_has_no_data(self) -> None:
        twse_payload = {
            "stat": "OK",
            "data": [
                ["115/06/18", "1,000", "10,000", "10.00", "12.00", "9.00", "11.00", "+1.00", "10"],
            ],
        }

        class FakeResponse:
            def json(self):
                return twse_payload

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader.yf, "download", return_value=pd.DataFrame()):
                    with patch.object(data_loader.requests, "get", return_value=FakeResponse()):
                        df, symbol = data_loader.download_tw_stock("2330", period="1mo")

        self.assertEqual(symbol, "2330.TW")
        self.assertEqual(float(df.iloc[0]["Close"]), 11.0)


if __name__ == "__main__":
    unittest.main()
