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

    def test_tpex_fallback_when_twse_has_no_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader.yf, "download", return_value=pd.DataFrame()):
                    with patch.object(
                        data_loader,
                        "_download_twse_stock",
                        side_effect=data_loader.DataLoaderError("no twse data"),
                    ):
                        with patch.object(
                            data_loader,
                            "_download_tpex_stock",
                            return_value=_download_df(),
                        ) as tpex:
                            df, symbol = data_loader.download_tw_stock("6488", period="1y")

        self.assertEqual(symbol, "6488.TWO")
        self.assertEqual(tpex.call_count, 1)
        self.assertEqual(float(df.iloc[-1]["Close"]), 12.0)

    def test_numeric_symbol_tries_two_after_tw_yfinance_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(
                    data_loader.yf,
                    "download",
                    side_effect=[pd.DataFrame(), _download_df()],
                ) as download:
                    df, symbol = data_loader.download_tw_stock(
                        "6510",
                        period="1y",
                        auto_adjust=True,
                    )

        self.assertEqual(symbol, "6510.TWO")
        self.assertEqual(float(df.iloc[-1]["Close"]), 12.0)
        called_symbols = [args.args[0] for args in download.call_args_list]
        self.assertEqual(called_symbols, ["6510.TW", "6510.TWO"])

    def test_numeric_symbol_returns_two_when_two_yfinance_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(
                    data_loader.yf,
                    "download",
                    side_effect=[pd.DataFrame(), _download_df()],
                ):
                    _, symbol = data_loader.download_tw_stock(
                        "8069",
                        period="1y",
                        auto_adjust=True,
                    )

        self.assertEqual(symbol, "8069.TWO")

    def test_explicit_tw_does_not_try_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(
                    data_loader.yf,
                    "download",
                    return_value=pd.DataFrame(),
                ) as download:
                    with self.assertRaises(data_loader.DataLoaderError):
                        data_loader.download_tw_stock(
                            "6510.TW",
                            period="1y",
                            auto_adjust=True,
                        )

        self.assertEqual(download.call_count, 1)
        self.assertEqual(download.call_args.args[0], "6510.TW")

    def test_explicit_two_does_not_try_tw(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(
                    data_loader.yf,
                    "download",
                    return_value=pd.DataFrame(),
                ) as download:
                    with self.assertRaises(data_loader.DataLoaderError):
                        data_loader.download_tw_stock(
                            "6510.TWO",
                            period="1y",
                            auto_adjust=True,
                        )

        self.assertEqual(download.call_count, 1)
        self.assertEqual(download.call_args.args[0], "6510.TWO")

    def test_no_data_error_lists_tried_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader.yf, "download", return_value=pd.DataFrame()):
                    with self.assertRaises(data_loader.DataLoaderError) as context:
                        data_loader.download_tw_stock(
                            "8299",
                            period="1y",
                            auto_adjust=True,
                        )

        message = str(context.exception)
        self.assertIn("No price data found for 8299", message)
        self.assertIn("Tried: 8299.TW, 8299.TWO", message)
        self.assertIn("delisted", message)
        self.assertIn("rate-limited", message)

    def test_auto_adjust_false_calls_official_after_yfinance_candidates_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(
                    data_loader.yf,
                    "download",
                    return_value=pd.DataFrame(),
                ) as download:
                    with patch.object(
                        data_loader,
                        "_download_official_stock",
                        return_value=_download_df(),
                    ) as official:
                        _, symbol = data_loader.download_tw_stock(
                            "2888",
                            period="1y",
                            auto_adjust=False,
                        )

        self.assertEqual(symbol, "2888.TW")
        self.assertEqual(download.call_count, 2)
        official.assert_called_once_with("2888", ".TW", "1y", "1d")

    def test_auto_adjust_skips_official_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader.yf, "download", return_value=pd.DataFrame()):
                    with patch.object(data_loader, "_download_twse_stock") as twse:
                        with patch.object(data_loader, "_download_tpex_stock") as tpex:
                            with self.assertRaises(data_loader.DataLoaderError):
                                data_loader.download_tw_stock(
                                    "2330",
                                    period="1y",
                                    auto_adjust=True,
                                )

        twse.assert_not_called()
        tpex.assert_not_called()


if __name__ == "__main__":
    unittest.main()
