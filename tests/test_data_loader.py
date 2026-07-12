from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import logging
from pathlib import Path
import sys
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



    def test_download_yfinance_quiet_calls_yfinance_download(self) -> None:
        with patch.object(
            data_loader.yf,
            "download",
            return_value=_download_df(),
        ) as download:
            df = data_loader._download_yfinance_quiet(
                "2330.TW",
                "1y",
                "1d",
                True,
            )

        self.assertEqual(float(df.iloc[-1]["Close"]), 12.0)
        download.assert_called_once_with(
            "2330.TW",
            period="1y",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )

    def test_download_yfinance_quiet_suppresses_output(self) -> None:
        def noisy_download(symbol: str, *args, **kwargs) -> pd.DataFrame:
            print(f"HTTP Error 404: {symbol}")
            print(f"1 Failed download: {symbol}", file=sys.stderr)
            return _download_df()

        stdout = StringIO()
        stderr = StringIO()
        with patch.object(data_loader.yf, "download", side_effect=noisy_download):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                df = data_loader._download_yfinance_quiet(
                    "8069.TW",
                    "1y",
                    "1d",
                    True,
                )

        self.assertEqual(float(df.iloc[-1]["Close"]), 12.0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_download_yfinance_quiet_is_thread_safe(self) -> None:
        def noisy_download(symbol: str, *args, **kwargs) -> pd.DataFrame:
            print(f"HTTP Error 404: {symbol}")
            print(f"possibly delisted: {symbol}", file=sys.stderr)
            return _download_df()

        symbols = [f"800{i}.TW" for i in range(8)]
        stdout = StringIO()
        stderr = StringIO()
        with patch.object(data_loader.yf, "download", side_effect=noisy_download):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                with ThreadPoolExecutor(max_workers=4) as executor:
                    results = list(
                        executor.map(
                            lambda symbol: data_loader._download_yfinance_quiet(
                                symbol,
                                "1y",
                                "1d",
                                True,
                            ),
                            symbols,
                        )
                    )

        self.assertEqual(len(results), len(symbols))
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_numeric_tw_failure_two_success_is_quiet(self) -> None:
        def noisy_download(symbol: str, *args, **kwargs) -> pd.DataFrame:
            if symbol.endswith(".TW"):
                print("HTTP Error 404")
                print("possibly delisted", file=sys.stderr)
                return pd.DataFrame()
            return _download_df()

        stdout = StringIO()
        stderr = StringIO()
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader.yf, "download", side_effect=noisy_download):
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        _, symbol = data_loader.download_tw_stock(
                            "8069",
                            period="1y",
                            auto_adjust=True,
                        )

        self.assertEqual(symbol, "8069.TWO")
        self.assertNotIn("HTTP Error 404", stdout.getvalue())
        self.assertNotIn("possibly delisted", stderr.getvalue())

    def test_all_yfinance_failures_are_quiet_until_unified_error(self) -> None:
        def noisy_empty_download(symbol: str, *args, **kwargs) -> pd.DataFrame:
            print(f"1 Failed download: {symbol}")
            print("possibly delisted", file=sys.stderr)
            return pd.DataFrame()

        stdout = StringIO()
        stderr = StringIO()
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader.yf, "download", side_effect=noisy_empty_download):
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        with self.assertRaises(data_loader.DataLoaderError) as context:
                            data_loader.download_tw_stock(
                                "8299",
                                period="1y",
                                auto_adjust=True,
                            )

        message = str(context.exception)
        self.assertIn("No price data found for 8299", message)
        self.assertIn("Tried: 8299.TW, 8299.TWO", message)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

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

    def test_cache_read_failure_falls_back_to_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader, "_is_cache_fresh", return_value=True):
                    with patch.object(data_loader, "_read_cache", side_effect=Exception("Read error")):
                        with patch.object(data_loader.yf, "download", return_value=_download_df()) as download:
                            df, symbol = data_loader.download_tw_stock("2330", period="1y")

        self.assertEqual(download.call_count, 1)
        self.assertEqual(symbol, "2330.TW")

    def test_prepare_ohlcv_rejects_invalid_index(self) -> None:
        df = pd.DataFrame(
            {
                "Open": [10.0],
                "High": [12.0],
                "Low": [9.0],
                "Close": [11.0],
                "Volume": [1000],
            },
            index=["not_a_date"],
        )
        with self.assertRaises(data_loader.DataLoaderError) as context:
            data_loader._prepare_ohlcv(df, "2330.TW")
        self.assertIn("not a valid DatetimeIndex", str(context.exception))

    def test_is_cache_fresh_considers_market_close_time(self) -> None:
        # Mock Path and its stat
        class MockStat:
            def __init__(self, mtime: float):
                self.st_mtime = mtime

        class MockPath:
            def __init__(self, mtime: float):
                self.mtime = mtime

            def exists(self) -> bool:
                return True

            def stat(self) -> MockStat:
                return MockStat(self.mtime)

        # Simulate 15:00 TST today
        mock_now = pd.Timestamp("2024-01-01 15:00:00", tz="Asia/Taipei")

        # Scenario 1: Cache from 14:00 TST today (before close). Should be stale at 15:00.
        cache_before_close = pd.Timestamp("2024-01-01 14:00:00", tz="Asia/Taipei")
        path_before = MockPath(cache_before_close.timestamp())

        # Scenario 2: Cache from 14:45 TST today (after close). Should be fresh at 15:00.
        cache_after_close = pd.Timestamp("2024-01-01 14:45:00", tz="Asia/Taipei")
        path_after = MockPath(cache_after_close.timestamp())

        with patch.object(data_loader.pd.Timestamp, "now", return_value=mock_now):
            self.assertFalse(data_loader._is_cache_fresh(path_before))
            self.assertTrue(data_loader._is_cache_fresh(path_after))

    def test_validate_inputs_rejects_invalid_stock_id_format(self) -> None:
        with self.assertRaisesRegex(data_loader.DataLoaderError, "Invalid stock ID format"):
            data_loader._validate_inputs("ABCD", "1y", "1d")

        with self.assertRaisesRegex(data_loader.DataLoaderError, "Invalid stock ID format"):
            data_loader._validate_inputs("!@#$", "1y", "1d")

        # These should pass validation
        try:
            data_loader._validate_inputs("2330", "1y", "1d")
            data_loader._validate_inputs("2330.TW", "1y", "1d")
            data_loader._validate_inputs("0050", "1y", "1d")
            data_loader._validate_inputs("00632R", "1y", "1d")
        except Exception as e:
            self.fail(f"Valid stock IDs raised an exception: {e}")

    def test_yfinance_cache_write_failure_is_non_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader.yf, "download", return_value=_download_df()):
                    with patch.object(data_loader, "_write_cache", side_effect=Exception("Write error")):
                        df, symbol = data_loader.download_tw_stock("2330", period="1y")

        self.assertEqual(symbol, "2330.TW")
        self.assertEqual(float(df.iloc[0]["Close"]), 11.0)

    def test_official_fallback_cache_write_failure_is_non_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader.yf, "download", return_value=pd.DataFrame()):
                    with patch.object(data_loader, "_download_official_stock", return_value=_download_df()):
                        with patch.object(data_loader, "_write_cache", side_effect=Exception("Write error")):
                            df, symbol = data_loader.download_tw_stock("2888", period="1mo", auto_adjust=False)

        self.assertEqual(symbol, "2888.TW")
        self.assertEqual(float(df.iloc[0]["Close"]), 11.0)

    def test_official_fallback_interval_limitation_is_in_error_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader.yf, "download", return_value=pd.DataFrame()):
                    with self.assertRaises(data_loader.DataLoaderError) as context:
                        data_loader.download_tw_stock("2888", period="1mo", interval="1wk", auto_adjust=False)

        message = str(context.exception)
        self.assertIn("1d", message)
        self.assertIn("interval", message.lower())

    @patch("sys.stderr", new_callable=StringIO)
    def test_download_falls_back_to_stale_cache_when_live_fetch_fails(self, mock_stderr: StringIO) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader.yf, "download", return_value=pd.DataFrame()):
                    with patch.object(data_loader, "_is_cache_fresh", return_value=False):
                        with patch.object(data_loader, "_get_cache_age_days", return_value=2.0):
                            cache_path = data_loader._cache_path("2330.TW", "1y", "1d", True)
                            data_loader._write_cache(_download_df(), cache_path)

                            df, symbol = data_loader.download_tw_stock("2330", period="1y", auto_adjust=True)

        self.assertEqual(symbol, "2330.TW")
        self.assertEqual(float(df.iloc[-1]["Close"]), 12.0)
        self.assertIn("WARNING", mock_stderr.getvalue())
        self.assertIn("stale cached data", mock_stderr.getvalue())
        self.assertIn("2330.TW", mock_stderr.getvalue())

        banned_phrases = (
            "guaranteed latest data",
            "guaranteed complete",
            "guaranteed accurate",
            "always latest",
            "real-time guaranteed",
            "refresh always succeeds",
            "fallback data is current",
            "official stock list is complete",
            "investment-grade data",
            "safe to invest",
            "best stocks to buy",
            "investment recommendation",
            "recommended stocks",
            "guaranteed profit",
            "guaranteed return",
        )
        output = mock_stderr.getvalue().lower()
        for phrase in banned_phrases:
            self.assertNotIn(phrase, output)

    @patch("sys.stderr", new_callable=StringIO)
    def test_stale_cache_within_threshold_is_used(self, mock_stderr: StringIO) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader.yf, "download", return_value=pd.DataFrame()):
                    with patch.object(data_loader, "_is_cache_fresh", return_value=False):
                        with patch.object(data_loader, "_get_cache_age_days", return_value=10.0):
                            cache_path = data_loader._cache_path("2330.TW", "1y", "1d", True)
                            data_loader._write_cache(_download_df(), cache_path)

                            df, symbol = data_loader.download_tw_stock("2330", period="1y", auto_adjust=True)

        self.assertEqual(symbol, "2330.TW")
        self.assertIn("WARNING", mock_stderr.getvalue())
        self.assertIn("stale cached data", mock_stderr.getvalue())
        self.assertIn("2330.TW", mock_stderr.getvalue())
        self.assertIn("10.0", mock_stderr.getvalue())

    def test_stale_cache_older_than_threshold_is_rejected_and_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader.yf, "download", return_value=pd.DataFrame()):
                    with patch.object(data_loader, "_is_cache_fresh", return_value=False):
                        with patch.object(data_loader, "_get_cache_age_days", return_value=20.0):
                            cache_path = data_loader._cache_path("2330.TW", "1y", "1d", True)
                            data_loader._write_cache(_download_df(), cache_path)

                            with self.assertRaises(data_loader.DataLoaderError) as context:
                                data_loader.download_tw_stock("2330", period="1y", auto_adjust=True)

        self.assertIn("stale cache rejected", str(context.exception))
        self.assertIn("20.0", str(context.exception))

    def test_force_refresh_bypasses_stale_cache_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader.yf, "download", return_value=pd.DataFrame()):
                    with patch.object(data_loader, "_is_cache_fresh", return_value=False):
                        with patch.object(data_loader, "_get_cache_age_days", return_value=2.0):
                            cache_path = data_loader._cache_path("2330.TW", "1y", "1d", True)
                            data_loader._write_cache(_download_df(), cache_path)

                            with self.assertRaises(data_loader.DataLoaderError) as context:
                                data_loader.download_tw_stock("2330", period="1y", auto_adjust=True, force_refresh=True)

        self.assertIn("No price data found", str(context.exception))

    def test_download_raises_data_loader_error_when_live_fetch_fails_and_no_cache_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader.yf, "download", return_value=pd.DataFrame()):
                    with self.assertRaises(data_loader.DataLoaderError) as context:
                        data_loader.download_tw_stock("2330", period="1y", auto_adjust=True)

        self.assertIn("No price data found", str(context.exception))


    def test_cache_runtime_identity_freshness_age_and_round_trip(self) -> None:
        class Stat:
            def __init__(self, value): self.st_mtime=value
        class FakePath:
            def __init__(self, value): self.value=value
            def exists(self): return self.value is not None
            def stat(self): return Stat(self.value.timestamp())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(data_loader, "CACHE_DIR", root):
                self.assertEqual(data_loader._cache_path("A/B", "5d", "1wk", False), root / "A_B_5d_1wk_adjusted-False.csv")
                self.assertNotEqual(data_loader._cache_path("2330.TW","1y","1d",True), data_loader._cache_path("2330.TW","1y","1d",False))
                frame=_download_df(); frame.index.name="Date"; path=root/"nested"/"cache.csv"; data_loader._write_cache(frame,path); loaded=data_loader._read_cache(path)
                self.assertEqual(loaded.index.name,"Date"); pd.testing.assert_frame_equal(loaded,frame,check_freq=False)
        now=pd.Timestamp("2024-01-02 14:30:00",tz="Asia/Taipei")
        with patch.object(data_loader.pd.Timestamp,"now",return_value=now):
            self.assertFalse(data_loader._is_cache_fresh(FakePath(None)))
            self.assertFalse(data_loader._is_cache_fresh(FakePath(pd.Timestamp("2024-01-01 15:00",tz="Asia/Taipei"))))
            self.assertFalse(data_loader._is_cache_fresh(FakePath(pd.Timestamp("2024-01-02 14:29:59",tz="Asia/Taipei"))))
            self.assertTrue(data_loader._is_cache_fresh(FakePath(pd.Timestamp("2024-01-02 14:30",tz="Asia/Taipei"))))
            self.assertFalse(data_loader._is_cache_fresh(FakePath(pd.Timestamp("2024-01-01 16:30",tz="UTC"))))
        utc=pd.Timestamp("2024-01-03",tz="UTC")
        with patch.object(data_loader.pd.Timestamp,"now",return_value=utc):
            self.assertAlmostEqual(data_loader._get_cache_age_days(FakePath(utc-pd.Timedelta(days=1))),1.0); self.assertEqual(data_loader._get_cache_age_days(FakePath(utc+pd.Timedelta(days=1))),0.0)

    def test_force_refresh_and_corrupt_cache_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(data_loader,"CACHE_DIR",Path(tmp)), patch.object(data_loader,"_read_cache") as read, patch.object(data_loader,"_write_cache") as write, patch.object(data_loader.yf,"download",return_value=_download_df()):
                _,symbol=data_loader.download_tw_stock("2330",force_refresh=True); self.assertEqual(symbol,"2330.TW"); read.assert_not_called(); write.assert_called_once()
        out,err=StringIO(),StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(data_loader,"CACHE_DIR",Path(tmp)), patch.object(data_loader.yf,"download",return_value=pd.DataFrame()), patch.object(data_loader,"_is_cache_fresh",return_value=False), patch.object(data_loader,"_get_cache_age_days",return_value=1.0), patch.object(data_loader,"_read_cache",side_effect=ValueError("corrupt stale")):
                path=data_loader._cache_path("2330.TW","1y","1d",True); path.parent.mkdir(parents=True,exist_ok=True); path.write_text("x")
                with redirect_stdout(out),redirect_stderr(err),self.assertRaises(data_loader.DataLoaderError) as caught: data_loader.download_tw_stock("2330",auto_adjust=True)
        self.assertIn("stale cache read failed: corrupt stale",str(caught.exception)); self.assertNotIn("WARNING",err.getvalue())

    def test_prepare_and_finalize_official_rows(self) -> None:
        frame=pd.DataFrame({"Open":[1,None],"High":[2,2],"Low":[0,0],"Close":[1,1],"Volume":[None,1],"Extra":[9,9]},index=["2024-01-01","2024-01-02"])
        result=data_loader._prepare_ohlcv(frame,"2330.TW"); self.assertEqual(list(result.columns),["Open","High","Low","Close","Volume"]); self.assertEqual(result.index.name,"Date"); self.assertTrue(pd.isna(result.iloc[0]["Volume"]))
        multi=_download_df(); multi.columns=pd.MultiIndex.from_tuples([(c,"x") for c in multi.columns]); self.assertEqual(list(data_loader._normalize_columns(multi).columns),["Open","High","Low","Close","Volume"])
        rows=[{"Date":pd.Timestamp(f"2024-01-{d:02d}"),"Open":d,"High":d+1,"Low":d-1,"Close":d,"Volume":d} for d in [3,1,2,3,4,5,6]]
        start=pd.Timestamp("2024-01-02"); self.assertEqual(len(data_loader._finalize_official_rows(rows,"2330",".TW",start,"1d")),1); self.assertEqual(len(data_loader._finalize_official_rows(rows,"2330",".TW",start,"5d")),5); self.assertEqual(len(data_loader._finalize_official_rows(rows,"2330",".TW",start,"1mo")),5)

    def test_tpex_monthly_latest_quote_and_wrapper_patch(self) -> None:
        class Response:
            def __init__(self,data): self.data=data
            def raise_for_status(self): pass
            def json(self): return self.data
        monthly={"stat":"ok","tables":[{"data":[["113/01/02","1,000","x","10","12","9","11"]]}]}
        with patch.object(data_loader,"_period_start",return_value=pd.Timestamp("2024-01-01")),patch.object(data_loader,"_month_starts",return_value=[pd.Timestamp("2024-01-01")]),patch.object(data_loader.requests,"get",return_value=Response(monthly)) as get,patch.object(data_loader,"_download_tpex_latest_quote") as latest:
            result=data_loader._download_tpex_stock("6488","1mo","1d")
        self.assertEqual(float(result.iloc[0]["Volume"]),1000); self.assertEqual(get.call_args.kwargs["params"]["id"],"6488"); latest.assert_not_called()
        quote=[{"SecuritiesCompanyCode":"6488","Date":"113/01/03","Open":"10","High":"12","Low":"9","Close":"11","TradingShares":"1234"}]
        with patch.object(data_loader.requests,"get",return_value=Response(quote)): self.assertEqual(float(data_loader._download_tpex_latest_quote("6488","1mo",pd.Timestamp("2024-01-01")).iloc[0]["Volume"]),1234)
        import tw_stock_tool.data.data_loader as package_loader; self.assertIs(data_loader,package_loader)

    def test_quiet_yfinance_restores_logger_on_exception(self) -> None:
        logger=logging.getLogger("yfinance"); old=(logger.disabled,logger.level,logger.propagate); logger.disabled=False; logger.setLevel(logging.WARNING); logger.propagate=True
        try:
            with patch.object(data_loader.yf,"download",side_effect=RuntimeError("boom")),redirect_stdout(StringIO()),redirect_stderr(StringIO()):
                with self.assertRaisesRegex(RuntimeError,"boom"): data_loader._download_yfinance_quiet("2330.TW","1y","1d",True)
            self.assertEqual((logger.disabled,logger.level,logger.propagate),(False,logging.WARNING,True))
        finally: logger.disabled,logger.level,logger.propagate=old

if __name__ == "__main__":
    unittest.main()
