from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import logging
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, call, patch

import pandas as pd

from tw_stock_tool.data import data_loader, fallback_orchestration


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
                        with patch.object(
                            data_loader,
                            "_period_start",
                            return_value=pd.Timestamp("2026-06-01"),
                        ):
                            with patch.object(
                                data_loader,
                                "_month_starts",
                                return_value=[pd.Timestamp("2026-06-01")],
                            ):
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


    def test_cache_path_identity_uses_exact_format_and_patched_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            with patch.object(data_loader, "CACHE_DIR", root):
                self.assertEqual(data_loader._cache_path("A/B", "5d", "1wk", False), root / "A_B_5d_1wk_adjusted-False.csv")
                baseline = data_loader._cache_path("2330.TW", "1y", "1d", True)
                self.assertNotEqual(baseline, data_loader._cache_path("2330.TW", "5d", "1d", True))
                self.assertNotEqual(baseline, data_loader._cache_path("2330.TW", "1y", "1wk", True))
                self.assertNotEqual(baseline, Path(tmp_dir) / "2330.TW_1y_1d_adjusted-False.csv")

    def test_cache_age_round_trip_and_freshness_boundaries(self) -> None:
        class Stat:
            def __init__(self, value): self.st_mtime = value
        class FakePath:
            def __init__(self, value): self.value = value
            def exists(self): return self.value is not None
            def stat(self): return Stat(self.value.timestamp())
        now = pd.Timestamp("2024-01-02 14:30:00", tz="Asia/Taipei")
        with patch.object(data_loader.pd.Timestamp, "now", return_value=now):
            self.assertFalse(data_loader._is_cache_fresh(FakePath(None)))
            self.assertFalse(data_loader._is_cache_fresh(FakePath(pd.Timestamp("2024-01-01 15:00", tz="Asia/Taipei"))))
            self.assertFalse(data_loader._is_cache_fresh(FakePath(pd.Timestamp("2024-01-02 14:29:59", tz="Asia/Taipei"))))
            self.assertTrue(data_loader._is_cache_fresh(FakePath(pd.Timestamp("2024-01-02 14:30", tz="Asia/Taipei"))))
        with tempfile.TemporaryDirectory() as tmp_dir:
            frame = _download_df(); frame.index.name = "Date"; path = Path(tmp_dir) / "nested" / "cache.csv"
            data_loader._write_cache(frame, path); loaded = data_loader._read_cache(path)
            self.assertEqual(loaded.index.name, "Date"); pd.testing.assert_frame_equal(loaded, frame, check_freq=False)

    def test_force_refresh_bypasses_cache_reads_and_writes_live_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)), patch.object(data_loader, "_read_cache") as read, patch.object(data_loader, "_write_cache") as write, patch.object(data_loader.yf, "download", return_value=_download_df()):
                _, symbol = data_loader.download_tw_stock("2330", force_refresh=True)
        self.assertEqual(symbol, "2330.TW"); read.assert_not_called(); write.assert_called_once()

    def test_corrupt_stale_cache_raises_without_stale_success_warning(self) -> None:
        stdout, stderr = StringIO(), StringIO()
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)), patch.object(data_loader.yf, "download", return_value=pd.DataFrame()), patch.object(data_loader, "_is_cache_fresh", return_value=False), patch.object(data_loader, "_get_cache_age_days", return_value=1.0), patch.object(data_loader, "_read_cache", side_effect=ValueError("corrupt stale")):
                path = data_loader._cache_path("2330.TW", "1y", "1d", True); path.parent.mkdir(parents=True, exist_ok=True); path.write_text("x")
                with redirect_stdout(stdout), redirect_stderr(stderr), self.assertRaises(data_loader.DataLoaderError) as caught: data_loader.download_tw_stock("2330", auto_adjust=True)
        self.assertIn("stale cache read failed: corrupt stale", str(caught.exception)); self.assertNotIn("WARNING", stderr.getvalue())

    def test_prepare_ohlcv_and_finalize_official_rows(self) -> None:
        frame = pd.DataFrame({"Open":[1,None],"High":[2,2],"Low":[0,0],"Close":[1,1],"Volume":[None,1],"Extra":[9,9]}, index=["2024-01-01","2024-01-02"])
        result = data_loader._prepare_ohlcv(frame, "2330.TW")
        self.assertEqual(list(result.columns), ["Open","High","Low","Close","Volume"]); self.assertEqual(result.index.name, "Date")
        rows = [{"Date":pd.Timestamp(f"2024-01-{day:02d}"),"Open":day,"High":day+1,"Low":day-1,"Close":day,"Volume":day} for day in [3,1,2,3,4,5,6]]
        start = pd.Timestamp("2024-01-02")
        self.assertEqual(len(data_loader._finalize_official_rows(rows,"2330",".TW",start,"1d")), 1)
        self.assertEqual(len(data_loader._finalize_official_rows(rows,"2330",".TW",start,"5d")), 5)

    def test_tpex_wrapper_and_logger_contracts(self) -> None:
        class Response:
            def __init__(self, data): self.data=data
            def raise_for_status(self): pass
            def json(self): return self.data
        monthly={"stat":"ok","tables":[{"data":[["113/01/02","1,000","x","10","12","9","11"]]}]}
        with patch.object(data_loader,"_period_start",return_value=pd.Timestamp("2024-01-01")), patch.object(data_loader,"_month_starts",return_value=[pd.Timestamp("2024-01-01")]), patch.object(data_loader.requests,"get",return_value=Response(monthly)), patch.object(data_loader,"_download_tpex_latest_quote") as latest:
            self.assertEqual(float(data_loader._download_tpex_stock("6488","1mo","1d").iloc[0]["Volume"]),1000)
        latest.assert_not_called()
        logger=logging.getLogger("yfinance"); old=(logger.disabled,logger.level,logger.propagate); logger.disabled=False; logger.setLevel(logging.WARNING); logger.propagate=True; stdout=StringIO(); stderr=StringIO()
        try:
            with patch.object(data_loader.yf,"download",side_effect=RuntimeError("boom")), redirect_stdout(stdout), redirect_stderr(stderr):
                with self.assertRaisesRegex(RuntimeError,"boom"): data_loader._download_yfinance_quiet("2330.TW","1y","1d",True)
            self.assertEqual((logger.disabled,logger.level,logger.propagate),(False,logging.WARNING,True)); self.assertEqual(stdout.getvalue(),""); self.assertEqual(stderr.getvalue(),"")
        finally: logger.disabled,logger.level,logger.propagate=old
    def test_force_refresh_official_success_writes_resolved_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)), patch.object(data_loader, "_read_cache") as read, patch.object(data_loader, "_write_cache") as write, patch.object(data_loader.yf, "download", return_value=pd.DataFrame()), patch.object(data_loader, "_download_official_stock", return_value=_download_df()):
                _, symbol = data_loader.download_tw_stock("2330", auto_adjust=False, force_refresh=True)
        self.assertEqual(symbol, "2330.TW")
        read.assert_not_called()
        self.assertEqual(write.call_args.args[1], Path(tmp_dir) / "2330.TW_1y_1d_adjusted-False.csv")

    def test_corrupt_fresh_cache_falls_back_to_live_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)), patch.object(data_loader, "_is_cache_fresh", return_value=True), patch.object(data_loader, "_read_cache", side_effect=ValueError("corrupt fresh")), patch.object(data_loader.yf, "download", return_value=_download_df()):
                df, symbol = data_loader.download_tw_stock("2330")
        self.assertEqual(symbol, "2330.TW")
        self.assertEqual(float(df.iloc[0]["Close"]), 11.0)

    def test_verbose_yfinance_status_and_quiet_provider_output(self) -> None:
        stdout, stderr = StringIO(), StringIO()
        def noisy(*args, **kwargs):
            print("provider stdout")
            print("provider stderr", file=sys.stderr)
            return _download_df()
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)), patch.object(data_loader.yf, "download", side_effect=noisy), redirect_stdout(stdout), redirect_stderr(stderr):
                data_loader.download_tw_stock("2330", verbose=True)
        self.assertIn("2330.TW: Downloaded", stdout.getvalue())
        self.assertNotIn("provider stdout", stdout.getvalue())
        self.assertNotIn("provider stderr", stderr.getvalue())


    def test_cache_age_days_uses_utc_and_propagates_stat_error(self) -> None:
        class Stat:
            def __init__(self, stamp): self.st_mtime = stamp
        class FakePath:
            def __init__(self, stamp): self.stamp = stamp
            def stat(self): return Stat(self.stamp)
        now = pd.Timestamp("2024-01-03", tz="UTC")
        with patch.object(data_loader.pd.Timestamp, "now", return_value=now):
            self.assertAlmostEqual(data_loader._get_cache_age_days(FakePath(now.timestamp() - 86400)), 1.0)
            self.assertAlmostEqual(data_loader._get_cache_age_days(FakePath(now.timestamp() - 43200)), 0.5)
            self.assertEqual(data_loader._get_cache_age_days(FakePath(now.timestamp() + 1)), 0.0)
        class BrokenPath:
            def stat(self): raise OSError("mtime failure")
        with self.assertRaisesRegex(OSError, "mtime failure"): data_loader._get_cache_age_days(BrokenPath())

    def test_stale_mtime_failure_is_aggregated_without_cache_read(self) -> None:
        stderr = StringIO()
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)), patch.object(data_loader.yf, "download", return_value=pd.DataFrame()), patch.object(data_loader, "_is_cache_fresh", return_value=False), patch.object(data_loader, "_get_cache_age_days", side_effect=OSError("mtime failure")), patch.object(data_loader, "_read_cache") as read:
                path = data_loader._cache_path("2330.TW", "1y", "1d", True); path.parent.mkdir(parents=True, exist_ok=True); path.write_text("x")
                with redirect_stderr(stderr), self.assertRaises(data_loader.DataLoaderError) as caught: data_loader.download_tw_stock("2330", auto_adjust=True)
        self.assertIn("stale cache mtime read failed: mtime failure", str(caught.exception)); read.assert_not_called(); self.assertNotIn("WARNING", stderr.getvalue())

    def test_verbose_fresh_and_stale_cache_output_channels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)), patch.object(data_loader.yf, "download", return_value=_download_df()):
                data_loader.download_tw_stock("2330")
                out, err = StringIO(), StringIO()
                with redirect_stdout(out), redirect_stderr(err): data_loader.download_tw_stock("2330", verbose=True)
        self.assertIn("2330.TW: From cache", out.getvalue()); self.assertEqual(err.getvalue(), "")
        out, err = StringIO(), StringIO()
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)), patch.object(data_loader.yf, "download", return_value=pd.DataFrame()), patch.object(data_loader, "_is_cache_fresh", return_value=False), patch.object(data_loader, "_get_cache_age_days", return_value=2.0):
                path = data_loader._cache_path("2330.TW", "1y", "1d", True); data_loader._write_cache(_download_df(), path)
                with redirect_stdout(out), redirect_stderr(err): data_loader.download_tw_stock("2330", auto_adjust=True, verbose=True)
        self.assertIn("2330.TW: From stale cache", out.getvalue()); self.assertNotIn("WARNING", out.getvalue()); self.assertIn("[WARNING]", err.getvalue()); self.assertIn("2.0", err.getvalue()); self.assertIn("stale cached data", err.getvalue())

    def test_before_close_and_utc_to_taipei_freshness(self) -> None:
        class Stat:
            def __init__(self, stamp): self.st_mtime = stamp
        class FakePath:
            def __init__(self, stamp): self.stamp = stamp
            def exists(self): return True
            def stat(self): return Stat(self.stamp.timestamp())
        now = pd.Timestamp("2024-01-02 13:00:00", tz="Asia/Taipei")
        with patch.object(data_loader.pd.Timestamp, "now", return_value=now):
            self.assertTrue(data_loader._is_cache_fresh(FakePath(pd.Timestamp("2024-01-02 09:00:00", tz="Asia/Taipei"))))
            self.assertTrue(data_loader._is_cache_fresh(FakePath(pd.Timestamp("2024-01-01 16:30:00", tz="UTC"))))

    def test_write_cache_failure_and_malformed_read_propagate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "nested" / "cache.csv"
            with patch.object(pd.DataFrame, "to_csv", side_effect=OSError("csv failure")):
                with self.assertRaisesRegex(OSError, "csv failure"):
                    data_loader._write_cache(_download_df(), path)
            bad = Path(tmp_dir) / "bad.csv"
            bad.write_text('"unterminated', encoding="utf-8")
            with self.assertRaises(Exception): data_loader._read_cache(bad)

    def test_official_fallback_verbose_status(self) -> None:
        stdout, stderr = StringIO(), StringIO()
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)), patch.object(data_loader.yf, "download", return_value=pd.DataFrame()), patch.object(data_loader, "_download_official_stock", return_value=_download_df()):
                with redirect_stdout(stdout), redirect_stderr(stderr): data_loader.download_tw_stock("2330", auto_adjust=False, verbose=True)
        self.assertIn("2330.TW: Downloaded from TWSE fallback", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_verbose_false_returns_live_data_without_loader_or_provider_output(self) -> None:
        stdout, stderr = StringIO(), StringIO()
        def noisy(*args, **kwargs):
            print("provider stdout")
            print("provider stderr", file=sys.stderr)
            return _download_df()
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)), patch.object(data_loader.yf, "download", side_effect=noisy), redirect_stdout(stdout), redirect_stderr(stderr):
                df, symbol = data_loader.download_tw_stock("2330", verbose=False)
        self.assertEqual(symbol, "2330.TW")
        self.assertEqual(float(df.iloc[0]["Close"]), 11.0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_tpex_monthly_empty_calls_latest_quote_once(self) -> None:
        class Response:
            def raise_for_status(self): pass
            def json(self): return {"stat":"ok", "tables":[{"data":[]}]}
        start = pd.Timestamp("2024-01-01")
        expected = _download_df()
        with patch.object(data_loader, "_period_start", return_value=start), patch.object(data_loader, "_month_starts", return_value=[start]), patch.object(data_loader.requests, "get", return_value=Response()), patch.object(data_loader, "_download_tpex_latest_quote", return_value=expected) as latest:
            actual = data_loader._download_tpex_stock("6488", "1mo", "1d")
        latest.assert_called_once_with("6488", "1mo", start)
        self.assertIs(actual, expected)

    def test_tpex_latest_quote_success_and_no_match(self) -> None:
        class Response:
            def __init__(self, payload): self.payload = payload
            def raise_for_status(self): pass
            def json(self): return self.payload
        payload=[{"SecuritiesCompanyCode":"6488","Date":"113/01/03","Open":"10","High":"12","Low":"9","Close":"11","TradingShares":"1,234"}]
        with patch.object(data_loader.requests, "get", return_value=Response(payload)) as get:
            df = data_loader._download_tpex_latest_quote("6488", "1mo", pd.Timestamp("2024-01-01"))
        self.assertEqual(get.call_args.args[0], "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes")
        self.assertEqual(get.call_args.kwargs["headers"]["User-Agent"], "Mozilla/5.0")
        self.assertEqual(get.call_args.kwargs["timeout"], 20)
        self.assertEqual(list(df.columns), ["Open","High","Low","Close","Volume"])
        self.assertEqual(df.index.name, "Date")
        self.assertEqual(float(df.iloc[0]["Volume"]), 1234)
        with patch.object(data_loader.requests, "get", return_value=Response([])):
            with self.assertRaisesRegex(data_loader.DataLoaderError, "6488.TWO"): data_loader._download_tpex_latest_quote("6488", "1mo", pd.Timestamp("2024-01-01"))

    def test_cache_runtime_delegates_route_through_internal_module(self) -> None:
        with patch.object(data_loader._cache_runtime, "_cache_path", return_value=Path("delegate.csv")) as cache_path:
            self.assertEqual(data_loader._cache_path("2330.TW", "1y", "1d", True), Path("delegate.csv"))
        cache_path.assert_called_once_with("2330.TW", "1y", "1d", True, cache_dir=data_loader.CACHE_DIR)
        path = Path("cache.csv")
        with patch.object(data_loader._cache_runtime, "_is_cache_fresh", return_value=True) as fresh, patch.object(data_loader._cache_runtime, "_get_cache_age_days", return_value=1.0) as age, patch.object(data_loader._cache_runtime, "_read_cache", return_value=_download_df()) as read, patch.object(data_loader._cache_runtime, "_write_cache") as write:
            self.assertTrue(data_loader._is_cache_fresh(path))
            self.assertEqual(data_loader._get_cache_age_days(path), 1.0)
            self.assertIs(data_loader._read_cache(path), read.return_value)
            data_loader._write_cache(_download_df(), path)
        fresh.assert_called_once_with(path); age.assert_called_once_with(path); read.assert_called_once_with(path); write.assert_called_once()

    def test_yfinance_success_restores_logger_state(self) -> None:
        logger = logging.getLogger("yfinance")
        old_state = (logger.disabled, logger.level, logger.propagate)
        try:
            logger.disabled = False
            logger.setLevel(logging.WARNING)
            logger.propagate = True
            with patch.object(data_loader.yf, "download", return_value=_download_df()):
                df = data_loader._download_yfinance_quiet("2330.TW", "1y", "1d", True)
            self.assertEqual(float(df.iloc[-1]["Close"]), 12.0)
            self.assertEqual((logger.disabled, logger.level, logger.propagate), (False, logging.WARNING, True))
        finally:
            logger.disabled, logger.level, logger.propagate = old_state

    def test_yfinance_auto_adjust_false_is_forwarded_exactly(self) -> None:
        with patch.object(data_loader.yf, "download", return_value=_download_df()) as download:
            data_loader._download_yfinance_quiet("2330.TW", "6mo", "1d", False)
        download.assert_called_once_with(
            "2330.TW",
            period="6mo",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )

    def test_data_loader_yf_download_patch_surface_intercepts_helper(self) -> None:
        expected = _download_df()
        with patch.object(data_loader.yf, "download", return_value=expected) as download:
            df = data_loader._download_yfinance_quiet("2330.TW", "1y", "1d", True)
        self.assertEqual(download.call_count, 1)
        pd.testing.assert_frame_equal(df, expected, check_freq=False)

    def test_download_tw_stock_uses_patchable_yfinance_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(tmp_dir)):
                with patch.object(data_loader, "_download_yfinance_quiet", return_value=_download_df()) as helper:
                    with patch.object(data_loader, "_write_cache") as write_cache:
                        with patch.object(data_loader.yf, "download") as yf_download:
                            df, symbol = data_loader.download_tw_stock(
                                "2330",
                                period="1y",
                                interval="1d",
                                auto_adjust=True,
                                force_refresh=True,
                            )
        helper.assert_called_once_with("2330.TW", "1y", "1d", True)
        self.assertEqual(symbol, "2330.TW")
        self.assertEqual(float(df.iloc[-1]["Close"]), 12.0)
        yf_download.assert_not_called()
        write_cache.assert_called_once()

    def test_yfinance_exception_restores_state_and_suppresses_output(self) -> None:
        logger = logging.getLogger("yfinance")
        old_state = (logger.disabled, logger.level, logger.propagate)
        def noisy_failing_download(symbol: str, *args, **kwargs) -> pd.DataFrame:
            print("provider stdout")
            print("provider stderr", file=sys.stderr)
            raise RuntimeError("boom")

        stdout = StringIO()
        stderr = StringIO()
        try:
            logger.disabled = False
            logger.setLevel(logging.WARNING)
            logger.propagate = True
            with patch.object(data_loader.yf, "download", side_effect=noisy_failing_download):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    with self.assertRaisesRegex(RuntimeError, "boom"):
                        data_loader._download_yfinance_quiet("2330.TW", "1y", "1d", True)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual((logger.disabled, logger.level, logger.propagate), (False, logging.WARNING, True))
        finally:
            logger.disabled, logger.level, logger.propagate = old_state

    def test_yfinance_helper_can_run_again_after_exception(self) -> None:
        logger = logging.getLogger("yfinance")
        old_state = (logger.disabled, logger.level, logger.propagate)
        expected_state = (False, logging.WARNING, True)
        stdout = StringIO()
        stderr = StringIO()
        calls = 0

        def fail_then_succeed(symbol: str, *args, **kwargs) -> pd.DataFrame:
            nonlocal calls
            calls += 1
            print(f"provider stdout {calls}")
            print(f"provider stderr {calls}", file=sys.stderr)
            if calls == 1:
                raise RuntimeError("first failure")
            return _download_df()

        try:
            logger.disabled = expected_state[0]
            logger.setLevel(expected_state[1])
            logger.propagate = expected_state[2]

            with patch.object(
                data_loader.yf,
                "download",
                side_effect=fail_then_succeed,
            ) as download:
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    with self.assertRaisesRegex(RuntimeError, "first failure"):
                        data_loader._download_yfinance_quiet("2330.TW", "1y", "1d", True)

                    self.assertEqual(
                        (logger.disabled, logger.level, logger.propagate),
                        expected_state,
                    )

                    df = data_loader._download_yfinance_quiet("2330.TW", "1y", "1d", True)

            self.assertEqual(float(df.iloc[-1]["Close"]), 12.0)
            self.assertEqual(download.call_count, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(
                (logger.disabled, logger.level, logger.propagate),
                expected_state,
            )
        finally:
            logger.disabled, logger.level, logger.propagate = old_state

    def test_yfinance_helper_delegates_to_provider_module(self) -> None:
        expected = _download_df()

        with patch.object(
            data_loader.yfinance_provider,
            "download_yfinance_quiet",
            return_value=expected,
        ) as provider_download:
            actual = data_loader._download_yfinance_quiet(
                "2330.TW",
                "6mo",
                "1d",
                False,
            )

        provider_download.assert_called_once_with(
            "2330.TW",
            "6mo",
            "1d",
            False,
        )
        self.assertIs(actual, expected)

    def test_twse_requests_get_patch_surface_and_exact_request_contract(self) -> None:
        class Response:
            def __init__(self) -> None:
                self.raise_calls = 0

            def raise_for_status(self) -> None:
                self.raise_calls += 1

            def json(self) -> dict:
                return {
                    "stat": "OK",
                    "data": [
                        [
                            "113/01/02",
                            "1,000",
                            "10,000",
                            "10.00",
                            "12.00",
                            "9.00",
                            "11.00",
                            "+1.00",
                            "10",
                        ],
                    ],
                }

        response = Response()
        start = pd.Timestamp("2024-01-01")
        month = pd.Timestamp("2024-01-01")

        with patch.object(
            data_loader,
            "_period_start",
            return_value=start,
        ) as period_start:
            with patch.object(
                data_loader,
                "_month_starts",
                return_value=[month],
            ):
                with patch.object(
                    data_loader.requests,
                    "get",
                    return_value=response,
                ) as request_get:
                    result = data_loader._download_twse_stock(
                        "2330",
                        "1mo",
                        "1d",
                    )

        period_start.assert_called_once_with("1mo")
        request_get.assert_called_once_with(
            "https://www.twse.com.tw/exchangeReport/STOCK_DAY",
            params={
                "response": "json",
                "date": "20240101",
                "stockNo": "2330",
            },
            timeout=20,
        )
        self.assertEqual(response.raise_calls, 1)
        self.assertEqual(result.index[0], pd.Timestamp("2024-01-02"))
        self.assertEqual(int(result.iloc[0]["Volume"]), 1000)
        self.assertEqual(float(result.iloc[0]["Close"]), 11.0)

    def test_twse_non_ok_month_is_skipped_before_later_success(self) -> None:
        class Response:
            def __init__(self, payload: dict) -> None:
                self.payload = payload
                self.raise_calls = 0

            def raise_for_status(self) -> None:
                self.raise_calls += 1

            def json(self) -> dict:
                return self.payload

        resp1 = Response({"stat": "很抱歉，沒有符合條件的資料!", "data": []})
        resp2 = Response(
            {
                "stat": "OK",
                "data": [
                    [
                        "113/02/05",
                        "2,000",
                        "20,000",
                        "20.00",
                        "22.00",
                        "19.00",
                        "21.00",
                        "+1.00",
                        "20",
                    ],
                ],
            }
        )

        months = [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")]
        with patch.object(data_loader, "_period_start", return_value=pd.Timestamp("2024-01-01")):
            with patch.object(data_loader, "_month_starts", return_value=months):
                with patch.object(
                    data_loader.requests,
                    "get",
                    side_effect=[resp1, resp2],
                ) as request_get:
                    result = data_loader._download_twse_stock("2330", "2mo", "1d")

        self.assertEqual(request_get.call_count, 2)
        self.assertEqual(
            request_get.call_args_list[0][1]["params"]["date"],
            "20240101",
        )
        self.assertEqual(
            request_get.call_args_list[1][1]["params"]["date"],
            "20240201",
        )
        self.assertEqual(resp1.raise_calls, 1)
        self.assertEqual(resp2.raise_calls, 1)
        self.assertEqual(result.index[0], pd.Timestamp("2024-02-05"))
        self.assertEqual(float(result.iloc[0]["Close"]), 21.0)

    def test_twse_all_non_ok_months_raise_exact_no_data_error(self) -> None:
        class Response:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict:
                return {"stat": "很抱歉，沒有符合條件的資料!", "data": []}

        months = [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")]
        with patch.object(data_loader, "_period_start", return_value=pd.Timestamp("2024-01-01")):
            with patch.object(data_loader, "_month_starts", return_value=months):
                with patch.object(data_loader.requests, "get", return_value=Response()) as request_get:
                    with self.assertRaisesRegex(
                        data_loader.DataLoaderError,
                        r"^Official fallback has no data: 2330\.TW$",
                    ):
                        data_loader._download_twse_stock("2330", "2mo", "1d")

        self.assertEqual(request_get.call_count, 2)

    def test_twse_http_error_propagates_before_json_parsing(self) -> None:
        class Response:
            def __init__(self) -> None:
                self.json_calls = 0

            def raise_for_status(self) -> None:
                raise data_loader.requests.HTTPError("twse http failure")

            def json(self) -> dict:
                self.json_calls += 1
                return {"stat": "OK", "data": []}

        resp = Response()
        with patch.object(data_loader, "_period_start", return_value=pd.Timestamp("2024-01-01")):
            with patch.object(data_loader, "_month_starts", return_value=[pd.Timestamp("2024-01-01")]):
                with patch.object(data_loader, "_finalize_official_rows") as finalize:
                    with patch.object(data_loader.requests, "get", return_value=resp):
                        with self.assertRaisesRegex(
                            data_loader.requests.HTTPError,
                            "twse http failure",
                        ):
                            data_loader._download_twse_stock("2330", "1mo", "1d")

        self.assertEqual(resp.json_calls, 0)
        finalize.assert_not_called()

    def test_twse_non_daily_interval_rejects_before_network(self) -> None:
        with patch.object(data_loader.requests, "get") as request_get:
            with patch.object(data_loader, "_period_start") as period_start:
                with patch.object(data_loader, "_month_starts") as month_starts:
                    with self.assertRaisesRegex(
                        data_loader.DataLoaderError,
                        r"^TWSE fallback only supports 1d interval\.$",
                    ):
                        data_loader._download_twse_stock("2330", "1mo", "1wk")

        request_get.assert_not_called()
        period_start.assert_not_called()
        month_starts.assert_not_called()

    def test_official_dispatch_uses_patchable_twse_helper(self) -> None:
        expected = _download_df()

        with patch.object(
            data_loader,
            "_download_twse_stock",
            return_value=expected,
        ) as twse_download:
            actual = data_loader._download_official_stock(
                "2330",
                ".TW",
                "6mo",
                "1d",
            )

        twse_download.assert_called_once_with(
            "2330",
            "6mo",
            "1d",
        )
        self.assertIs(actual, expected)

    def test_twse_helper_delegates_to_provider_module(self) -> None:
        expected = _download_df()

        with patch.object(
            data_loader.twse_provider,
            "download_twse_stock",
            return_value=expected,
        ) as provider_download:
            actual = data_loader._download_twse_stock(
                "2330",
                "6mo",
                "1d",
            )

        provider_download.assert_called_once_with(
            "2330",
            "6mo",
            "1d",
            period_start=data_loader._period_start,
            month_starts=data_loader._month_starts,
            parse_roc_date=data_loader._parse_roc_date,
            to_float=data_loader._to_float,
            to_int=data_loader._to_int,
            finalize_official_rows=data_loader._finalize_official_rows,
            error_type=data_loader.DataLoaderError,
        )
        self.assertIs(actual, expected)

    def test_tpex_monthly_requests_get_patch_surface_and_exact_request_contract(self) -> None:
        class Response:
            def __init__(self) -> None:
                self.raise_calls = 0

            def raise_for_status(self) -> None:
                self.raise_calls += 1

            def json(self) -> dict:
                return {
                    "stat": "ok",
                    "tables": [
                        {
                            "data": [
                                [
                                    "113/01/02",
                                    "1,000",
                                    "ignored",
                                    "10.00",
                                    "12.00",
                                    "9.00",
                                    "11.00",
                                ],
                            ],
                        },
                    ],
                }

        response = Response()
        start = pd.Timestamp("2024-01-01")
        month = pd.Timestamp("2024-01-01")

        with patch.object(data_loader, "_period_start", return_value=start) as period_start:
            with patch.object(data_loader, "_month_starts", return_value=[month]):
                with patch.object(data_loader, "_download_tpex_latest_quote") as latest_quote:
                    with patch.object(data_loader.requests, "get", return_value=response) as request_get:
                        result = data_loader._download_tpex_stock(
                            "6488",
                            "1mo",
                            "1d",
                        )

        period_start.assert_called_once_with("1mo")
        request_get.assert_called_once_with(
            "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock",
            params={
                "response": "json",
                "date": "2024/01/01",
                "id": "6488",
            },
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        self.assertEqual(response.raise_calls, 1)
        latest_quote.assert_not_called()
        self.assertEqual(result.index[0], pd.Timestamp("2024-01-02"))
        self.assertEqual(int(result.iloc[0]["Volume"]), 1000)
        self.assertEqual(float(result.iloc[0]["Close"]), 11.0)

    def test_tpex_non_ok_month_is_skipped_before_later_success(self) -> None:
        class Response:
            def __init__(self, payload: dict) -> None:
                self.payload = payload
                self.raise_calls = 0

            def raise_for_status(self) -> None:
                self.raise_calls += 1

            def json(self) -> dict:
                return self.payload

        resp1 = Response({"stat": "not ok", "tables": []})
        resp2 = Response(
            {
                "stat": "OK",
                "tables": [
                    {
                        "data": [
                            [
                                "113/02/05",
                                "2,000",
                                "ignored",
                                "20.00",
                                "22.00",
                                "19.00",
                                "21.00",
                            ],
                        ],
                    },
                ],
            }
        )

        months = [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")]
        with patch.object(data_loader, "_period_start", return_value=pd.Timestamp("2024-01-01")):
            with patch.object(data_loader, "_month_starts", return_value=months):
                with patch.object(data_loader, "_download_tpex_latest_quote") as latest_quote:
                    with patch.object(
                        data_loader.requests,
                        "get",
                        side_effect=[resp1, resp2],
                    ) as request_get:
                        result = data_loader._download_tpex_stock("6488", "2mo", "1d")

        self.assertEqual(request_get.call_count, 2)
        self.assertEqual(
            request_get.call_args_list[0][1]["params"]["date"],
            "2024/01/01",
        )
        self.assertEqual(
            request_get.call_args_list[1][1]["params"]["date"],
            "2024/02/01",
        )
        self.assertEqual(resp1.raise_calls, 1)
        self.assertEqual(resp2.raise_calls, 1)
        latest_quote.assert_not_called()
        self.assertEqual(result.index[0], pd.Timestamp("2024-02-05"))
        self.assertEqual(float(result.iloc[0]["Close"]), 21.0)

    def test_tpex_short_rows_are_skipped_before_latest_quote(self) -> None:
        class Response:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict:
                return {
                    "stat": "ok",
                    "tables": [
                        {
                            "data": [
                                [
                                    "113/01/02",
                                    "1,000",
                                    "ignored",
                                    "10.00",
                                    "12.00",
                                    "9.00",
                                ],
                            ],
                        },
                    ],
                }

        expected = _download_df()
        start = pd.Timestamp("2024-01-01")

        with patch.object(data_loader, "_period_start", return_value=start):
            with patch.object(data_loader, "_month_starts", return_value=[start]):
                with patch.object(data_loader.requests, "get", return_value=Response()):
                    with patch.object(
                        data_loader,
                        "_download_tpex_latest_quote",
                        return_value=expected,
                    ) as latest:
                        actual = data_loader._download_tpex_stock("6488", "1mo", "1d")

        latest.assert_called_once_with("6488", "1mo", start)
        self.assertIs(actual, expected)

    def test_tpex_monthly_http_error_propagates_before_json_or_latest_quote(self) -> None:
        class Response:
            def __init__(self) -> None:
                self.json_calls = 0

            def raise_for_status(self) -> None:
                raise data_loader.requests.HTTPError("tpex monthly http failure")

            def json(self) -> dict:
                self.json_calls += 1
                return {"stat": "ok", "tables": []}

        resp = Response()
        with patch.object(data_loader, "_period_start", return_value=pd.Timestamp("2024-01-01")):
            with patch.object(data_loader, "_month_starts", return_value=[pd.Timestamp("2024-01-01")]):
                with patch.object(data_loader, "_download_tpex_latest_quote") as latest_quote:
                    with patch.object(data_loader, "_finalize_official_rows") as finalize:
                        with patch.object(data_loader.requests, "get", return_value=resp):
                            with self.assertRaisesRegex(
                                data_loader.requests.HTTPError,
                                "tpex monthly http failure",
                            ):
                                data_loader._download_tpex_stock("6488", "1mo", "1d")

        self.assertEqual(resp.json_calls, 0)
        latest_quote.assert_not_called()
        finalize.assert_not_called()

    def test_tpex_non_daily_interval_rejects_before_network(self) -> None:
        with patch.object(data_loader.requests, "get") as request_get:
            with patch.object(data_loader, "_period_start") as period_start:
                with patch.object(data_loader, "_month_starts") as month_starts:
                    with patch.object(data_loader, "_download_tpex_latest_quote") as latest_quote:
                        with self.assertRaisesRegex(
                            data_loader.DataLoaderError,
                            r"^TPEX fallback only supports 1d interval\.$",
                        ):
                            data_loader._download_tpex_stock("6488", "1mo", "1wk")

        request_get.assert_not_called()
        period_start.assert_not_called()
        month_starts.assert_not_called()
        latest_quote.assert_not_called()

    def test_parse_tpex_date_supports_all_current_formats(self) -> None:
        expected = pd.Timestamp("2024-01-02")

        self.assertEqual(
            data_loader._parse_tpex_date("113/01/02"),
            expected,
        )

        self.assertEqual(
            data_loader._parse_tpex_date(
                "01/02",
                pd.Timestamp("2024-01-01"),
            ),
            expected,
        )

        self.assertEqual(
            data_loader._parse_tpex_date("1130102"),
            expected,
        )

        self.assertEqual(
            data_loader._parse_tpex_date("20240102"),
            expected,
        )

        with self.assertRaisesRegex(
            ValueError,
            r"^Invalid TPEX date: invalid$",
        ):
            data_loader._parse_tpex_date("invalid")

    def test_tpex_latest_quote_exact_request_and_matching_contract(self) -> None:
        class Response:
            def __init__(self) -> None:
                self.raise_calls = 0

            def raise_for_status(self) -> None:
                self.raise_calls += 1

            def json(self) -> list[dict]:
                return [
                    {
                        "SecuritiesCompanyCode": "1234",
                        "Date": "20240103",
                        "Open": "1",
                        "High": "2",
                        "Low": "0",
                        "Close": "1",
                        "TradingShares": "10",
                    },
                    {
                        "SecuritiesCompanyCode": " 6488 ",
                        "Date": "20240103",
                        "Open": "10",
                        "High": "12",
                        "Low": "9",
                        "Close": "11",
                        "TradingShares": "1,234",
                    },
                ]

        response = Response()
        expected = _download_df()
        start = pd.Timestamp("2024-01-01")

        with patch.object(
            data_loader.requests,
            "get",
            return_value=response,
        ) as request_get:
            with patch.object(
                data_loader,
                "_finalize_official_rows",
                return_value=expected,
            ) as finalize:
                actual = data_loader._download_tpex_latest_quote(
                    "6488",
                    "1mo",
                    start,
                )

        request_get.assert_called_once_with(
            "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        self.assertEqual(response.raise_calls, 1)
        finalize.assert_called_once_with(
            [
                {
                    "Date": pd.Timestamp("2024-01-03"),
                    "Open": 10.0,
                    "High": 12.0,
                    "Low": 9.0,
                    "Close": 11.0,
                    "Volume": 1234,
                },
            ],
            "6488",
            ".TWO",
            start,
            "1mo",
        )
        self.assertIs(actual, expected)

    def test_tpex_latest_quote_http_error_propagates_before_json(self) -> None:
        class Response:
            def __init__(self) -> None:
                self.json_calls = 0

            def raise_for_status(self) -> None:
                raise data_loader.requests.HTTPError("tpex latest http failure")

            def json(self) -> list[dict]:
                self.json_calls += 1
                return []

        resp = Response()
        start = pd.Timestamp("2024-01-01")

        with patch.object(data_loader, "_finalize_official_rows") as finalize:
            with patch.object(data_loader.requests, "get", return_value=resp):
                with self.assertRaisesRegex(
                    data_loader.requests.HTTPError,
                    "tpex latest http failure",
                ):
                    data_loader._download_tpex_latest_quote(
                        "6488",
                        "1mo",
                        start,
                    )

        self.assertEqual(resp.json_calls, 0)
        finalize.assert_not_called()

    def test_tpex_latest_quote_no_match_raises_exact_error(self) -> None:
        class Response:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> list[dict]:
                return [
                    {
                        "SecuritiesCompanyCode": "1234",
                        "Date": "20240103",
                        "Open": "1",
                        "High": "2",
                        "Low": "0",
                        "Close": "1",
                        "TradingShares": "10",
                    },
                ]

        start = pd.Timestamp("2024-01-01")

        with patch.object(data_loader, "_finalize_official_rows") as finalize:
            with patch.object(data_loader.requests, "get", return_value=Response()):
                with self.assertRaisesRegex(
                    data_loader.DataLoaderError,
                    r"^TPEX fallback has no data: 6488\.TWO$",
                ):
                    data_loader._download_tpex_latest_quote(
                        "6488",
                        "1mo",
                        start,
                    )

        finalize.assert_not_called()

    def test_official_dispatch_uses_patchable_tpex_helper(self) -> None:
        expected = _download_df()

        with patch.object(
            data_loader,
            "_download_tpex_stock",
            return_value=expected,
        ) as tpex_download:
            actual = data_loader._download_official_stock(
                "6488",
                ".TWO",
                "6mo",
                "1d",
            )

        tpex_download.assert_called_once_with(
            "6488",
            "6mo",
            "1d",
        )
        self.assertIs(actual, expected)

    def test_tpex_stock_helper_delegates_to_provider_module(self) -> None:
        expected = _download_df()

        with patch.object(
            data_loader.tpex_provider,
            "download_tpex_stock",
            return_value=expected,
        ) as provider_download:
            actual = data_loader._download_tpex_stock(
                "6488",
                "6mo",
                "1d",
            )

        provider_download.assert_called_once_with(
            "6488",
            "6mo",
            "1d",
            period_start=data_loader._period_start,
            month_starts=data_loader._month_starts,
            parse_tpex_date=data_loader._parse_tpex_date,
            to_float=data_loader._to_float,
            to_int=data_loader._to_int,
            finalize_official_rows=data_loader._finalize_official_rows,
            download_latest_quote=data_loader._download_tpex_latest_quote,
            error_type=data_loader.DataLoaderError,
        )
        self.assertIs(actual, expected)

    def test_tpex_latest_quote_helper_delegates_to_provider_module(self) -> None:
        expected = _download_df()
        start = pd.Timestamp("2024-01-01")

        with patch.object(
            data_loader.tpex_provider,
            "download_tpex_latest_quote",
            return_value=expected,
        ) as provider_download:
            actual = data_loader._download_tpex_latest_quote(
                "6488",
                "6mo",
                start,
            )

        provider_download.assert_called_once_with(
            "6488",
            "6mo",
            start,
            parse_tpex_date=data_loader._parse_tpex_date,
            to_float=data_loader._to_float,
            to_int=data_loader._to_int,
            finalize_official_rows=data_loader._finalize_official_rows,
            error_type=data_loader.DataLoaderError,
        )
        self.assertIs(actual, expected)

    def test_normalize_columns_flattens_multiindex_and_preserves_identity(
        self,
    ) -> None:
        columns = pd.MultiIndex.from_tuples(
            [
                ("Open", "2330.TW"),
                ("High", "2330.TW"),
                ("Low", "2330.TW"),
                ("Close", "2330.TW"),
                ("Volume", "2330.TW"),
            ]
        )

        frame = pd.DataFrame(
            [[10.0, 12.0, 9.0, 11.0, 1000]],
            columns=columns,
        )

        actual = data_loader._normalize_columns(frame)

        self.assertIs(actual, frame)
        self.assertEqual(
            list(actual.columns),
            ["Open", "High", "Low", "Close", "Volume"],
        )

    def test_prepare_ohlcv_selects_exact_columns_drops_unusable_rows_and_converts_index(
        self,
    ) -> None:
        frame = pd.DataFrame(
            {
                "Volume": [None, 2000],
                "Close": [11.0, 21.0],
                "Open": [10.0, None],
                "Extra": ["keep-out", "keep-out"],
                "Low": [9.0, 19.0],
                "High": [12.0, 22.0],
            },
            index=[
                "2024-01-02",
                "2024-01-03",
            ],
        )

        actual = data_loader._prepare_ohlcv(
            frame,
            "2330.TW",
        )

        self.assertEqual(
            list(actual.columns),
            ["Open", "High", "Low", "Close", "Volume"],
        )
        self.assertEqual(len(actual), 1)
        self.assertIsInstance(actual.index, pd.DatetimeIndex)
        self.assertEqual(actual.index[0], pd.Timestamp("2024-01-02"))
        self.assertEqual(actual.index.name, "Date")
        self.assertTrue(pd.isna(actual.iloc[0]["Volume"]))
        self.assertNotIn("Extra", actual.columns)

    def test_prepare_ohlcv_missing_columns_raise_exact_error(
        self,
    ) -> None:
        frame = pd.DataFrame(
            {
                "Open": [10.0],
                "Low": [9.0],
                "Close": [11.0],
            },
            index=["2024-01-02"],
        )

        with self.assertRaises(data_loader.DataLoaderError) as caught:
            data_loader._prepare_ohlcv(frame, "2330.TW")

        self.assertEqual(
            str(caught.exception),
            "Missing data columns: ['High', 'Volume']",
        )

    def test_prepare_ohlcv_no_usable_ohlc_raises_exact_error(
        self,
    ) -> None:
        frame = pd.DataFrame(
            {
                "Open": [None, 10.0],
                "High": [12.0, None],
                "Low": [9.0, 9.0],
                "Close": [11.0, 11.0],
                "Volume": [1000, 1000],
            },
            index=["2024-01-02", "2024-01-03"],
        )

        with self.assertRaises(data_loader.DataLoaderError) as caught:
            data_loader._prepare_ohlcv(
                frame,
                "6488.TWO",
            )

        self.assertEqual(
            str(caught.exception),
            "6488.TWO has no usable OHLC data.",
        )

    def test_prepare_ohlcv_invalid_index_raises_exact_error(
        self,
    ) -> None:
        frame = pd.DataFrame(
            {
                "Open": [10.0],
                "High": [12.0],
                "Low": [9.0],
                "Close": [11.0],
                "Volume": [1000],
            },
            index=["not-a-date"],
        )

        with self.assertRaises(data_loader.DataLoaderError) as caught:
            data_loader._prepare_ohlcv(frame, "2330.TW")

        self.assertEqual(
            str(caught.exception),
            "2330.TW index is not a valid DatetimeIndex.",
        )

    def test_prepare_ohlcv_uses_patchable_normalize_columns_helper(
        self,
    ) -> None:
        source = pd.DataFrame(
            {"raw": [1]},
            index=["2024-01-02"],
        )

        normalized = pd.DataFrame(
            {
                "Open": [10.0],
                "High": [12.0],
                "Low": [9.0],
                "Close": [11.0],
                "Volume": [1000],
            },
            index=["2024-01-02"],
        )

        with patch.object(
            data_loader,
            "_normalize_columns",
            return_value=normalized,
        ) as normalize:
            actual = data_loader._prepare_ohlcv(
                source,
                "2330.TW",
            )

        normalize.assert_called_once_with(source)
        self.assertEqual(
            list(actual.columns),
            ["Open", "High", "Low", "Close", "Volume"],
        )
        self.assertIsInstance(actual.index, pd.DatetimeIndex)
        self.assertEqual(actual.index.name, "Date")

    def test_finalize_official_rows_empty_rows_raise_exact_error(
        self,
    ) -> None:
        with patch.object(data_loader, "_prepare_ohlcv") as prepare:
            with self.assertRaises(data_loader.DataLoaderError) as caught:
                data_loader._finalize_official_rows(
                    [],
                    "2330",
                    ".TW",
                    pd.Timestamp("2024-01-01"),
                    "1mo",
                )

        self.assertEqual(
            str(caught.exception),
            "Official fallback has no data: 2330.TW",
        )
        prepare.assert_not_called()

    def test_finalize_official_rows_deduplicates_sorts_filters_and_limits_periods(
        self,
    ) -> None:
        rows = [
            {
                "Date": pd.Timestamp("2024-01-03"),
                "Open": 10.0,
                "High": 12.0,
                "Low": 9.0,
                "Close": 30.0,
                "Volume": 1000,
            },
            {
                "Date": pd.Timestamp("2024-01-01"),
                "Open": 10.0,
                "High": 12.0,
                "Low": 9.0,
                "Close": 10.0,
                "Volume": 1000,
            },
            {
                "Date": pd.Timestamp("2024-01-02"),
                "Open": 10.0,
                "High": 12.0,
                "Low": 9.0,
                "Close": 20.0,
                "Volume": 1000,
            },
            {
                "Date": pd.Timestamp("2024-01-03"),
                "Open": 10.0,
                "High": 12.0,
                "Low": 9.0,
                "Close": 300.0,
                "Volume": 1000,
            },
            {
                "Date": pd.Timestamp("2024-01-04"),
                "Open": 10.0,
                "High": 12.0,
                "Low": 9.0,
                "Close": 40.0,
                "Volume": 1000,
            },
            {
                "Date": pd.Timestamp("2024-01-05"),
                "Open": 10.0,
                "High": 12.0,
                "Low": 9.0,
                "Close": 50.0,
                "Volume": 1000,
            },
            {
                "Date": pd.Timestamp("2024-01-06"),
                "Open": 10.0,
                "High": 12.0,
                "Low": 9.0,
                "Close": 60.0,
                "Volume": 1000,
            },
            {
                "Date": pd.Timestamp("2024-01-07"),
                "Open": 10.0,
                "High": 12.0,
                "Low": 9.0,
                "Close": 70.0,
                "Volume": 1000,
            },
        ]

        start = pd.Timestamp("2024-01-02")

        actual_1mo = data_loader._finalize_official_rows(
            rows,
            "2330",
            ".TW",
            start,
            "1mo",
        )

        expected_dates = [
            pd.Timestamp("2024-01-02"),
            pd.Timestamp("2024-01-03"),
            pd.Timestamp("2024-01-04"),
            pd.Timestamp("2024-01-05"),
            pd.Timestamp("2024-01-06"),
            pd.Timestamp("2024-01-07"),
        ]

        self.assertEqual(list(actual_1mo.index), expected_dates)
        self.assertEqual(actual_1mo.index.name, "Date")
        self.assertEqual(
            list(actual_1mo.columns),
            ["Open", "High", "Low", "Close", "Volume"],
        )
        self.assertEqual(actual_1mo.loc[pd.Timestamp("2024-01-03"), "Close"], 30.0)

        actual_1d = data_loader._finalize_official_rows(
            rows,
            "2330",
            ".TW",
            start,
            "1d",
        )
        self.assertEqual(list(actual_1d.index), [pd.Timestamp("2024-01-07")])

        actual_5d = data_loader._finalize_official_rows(
            rows,
            "2330",
            ".TW",
            start,
            "5d",
        )
        self.assertEqual(
            list(actual_5d.index),
            expected_dates[-5:],
        )

    def test_finalize_official_rows_uses_patchable_prepare_ohlcv_helper(
        self,
    ) -> None:
        rows = [
            {
                "Date": pd.Timestamp("2024-01-01"),
                "Open": 10.0,
                "High": 12.0,
                "Low": 9.0,
                "Close": 10.0,
                "Volume": 1000,
            },
            {
                "Date": pd.Timestamp("2024-01-02"),
                "Open": 10.0,
                "High": 12.0,
                "Low": 9.0,
                "Close": 20.0,
                "Volume": 1000,
            },
            {
                "Date": pd.Timestamp("2024-01-03"),
                "Open": 10.0,
                "High": 12.0,
                "Low": 9.0,
                "Close": 30.0,
                "Volume": 1000,
            },
        ]

        expected = _download_df()

        with patch.object(
            data_loader,
            "_prepare_ohlcv",
            return_value=expected,
        ) as prepare:
            actual = data_loader._finalize_official_rows(
                rows,
                "2330",
                ".TW",
                pd.Timestamp("2024-01-02"),
                "1d",
            )

        prepare.assert_called_once()
        call_args = prepare.call_args[0]
        passed_df = call_args[0]
        passed_symbol = call_args[1]

        self.assertIsInstance(passed_df, pd.DataFrame)
        self.assertEqual(passed_symbol, "2330.TW")
        self.assertEqual(passed_df.index.name, "Date")
        self.assertEqual(list(passed_df.index), [pd.Timestamp("2024-01-03")])
        self.assertEqual(len(passed_df), 1)
        self.assertIs(actual, expected)

    def test_normalize_columns_helper_delegates_to_normalization_module(
        self,
    ) -> None:
        frame = pd.DataFrame({"raw": [1]})
        expected = pd.DataFrame({"Open": [1]})

        with patch.object(
            data_loader._ohlcv_normalization,
            "normalize_columns",
            return_value=expected,
        ) as normalize:
            actual = data_loader._normalize_columns(frame)

        normalize.assert_called_once_with(frame)
        self.assertIs(actual, expected)

    def test_prepare_ohlcv_helper_delegates_to_normalization_module(
        self,
    ) -> None:
        frame = pd.DataFrame({"raw": [1]})
        expected = _download_df()

        with patch.object(
            data_loader._ohlcv_normalization,
            "prepare_ohlcv",
            return_value=expected,
        ) as prepare:
            actual = data_loader._prepare_ohlcv(
                frame,
                "2330.TW",
            )

        prepare.assert_called_once_with(
            frame,
            "2330.TW",
            normalize_columns=data_loader._normalize_columns,
            error_type=data_loader.DataLoaderError,
        )
        self.assertIs(actual, expected)

    def test_finalize_official_rows_helper_delegates_to_normalization_module(
        self,
    ) -> None:
        rows = [
            {
                "Date": pd.Timestamp("2024-01-02"),
                "Open": 10.0,
                "High": 12.0,
                "Low": 9.0,
                "Close": 11.0,
                "Volume": 1000,
            },
        ]
        start = pd.Timestamp("2024-01-01")
        expected = _download_df()

        with patch.object(
            data_loader._ohlcv_normalization,
            "finalize_official_rows",
            return_value=expected,
        ) as finalize:
            actual = data_loader._finalize_official_rows(
                rows,
                "2330",
                ".TW",
                start,
                "1mo",
            )

        finalize.assert_called_once_with(
            rows,
            "2330",
            ".TW",
            start,
            "1mo",
            prepare_ohlcv=data_loader._prepare_ohlcv,
            error_type=data_loader.DataLoaderError,
        )
        self.assertIs(actual, expected)

    def test_period_start_uses_normalized_today_and_current_month_mapping(
        self,
    ) -> None:
        with patch.object(
            data_loader.pd.Timestamp,
            "today",
            return_value=pd.Timestamp("2024-06-15 13:45:30"),
        ):
            expected = {
                "1d": pd.Timestamp("2024-05-15"),
                "5d": pd.Timestamp("2024-05-15"),
                "1mo": pd.Timestamp("2024-05-15"),
                "3mo": pd.Timestamp("2024-03-15"),
                "6mo": pd.Timestamp("2023-12-15"),
                "1y": pd.Timestamp("2023-06-15"),
                "2y": pd.Timestamp("2022-06-15"),
                "5y": pd.Timestamp("2019-06-15"),
                "10y": pd.Timestamp("2014-06-15"),
                "max": pd.Timestamp("2009-06-15"),
            }
            for period, expected_ts in expected.items():
                with self.subTest(period=period):
                    self.assertEqual(
                        data_loader._period_start(period),
                        expected_ts,
                    )

    def test_period_start_ytd_and_unknown_period_use_current_contract(
        self,
    ) -> None:
        with patch.object(
            data_loader.pd.Timestamp,
            "today",
            return_value=pd.Timestamp("2024-06-15 13:45:30"),
        ):
            self.assertEqual(
                data_loader._period_start("ytd"),
                pd.Timestamp("2024-01-01"),
            )
            self.assertEqual(
                data_loader._period_start("unexpected"),
                pd.Timestamp("2023-06-15"),
            )

    def test_month_starts_normalizes_to_first_and_is_inclusive_across_years(
        self,
    ) -> None:
        actual = data_loader._month_starts(
            pd.Timestamp("2023-12-31 22:30:00"),
            pd.Timestamp("2024-02-15 08:00:00"),
        )
        self.assertEqual(
            actual,
            [
                pd.Timestamp("2023-12-01"),
                pd.Timestamp("2024-01-01"),
                pd.Timestamp("2024-02-01"),
            ],
        )

    def test_month_starts_returns_empty_when_start_month_is_after_end_month(
        self,
    ) -> None:
        actual = data_loader._month_starts(
            pd.Timestamp("2024-03-10"),
            pd.Timestamp("2024-02-20"),
        )
        self.assertEqual(actual, [])

    def test_parse_roc_date_handles_whitespace_and_exact_malformed_error(
        self,
    ) -> None:
        actual = data_loader._parse_roc_date(" 113 / 01 / 02 ")
        self.assertEqual(actual, pd.Timestamp("2024-01-02"))

        with self.assertRaises(ValueError) as ctx:
            data_loader._parse_roc_date("113-01-02")
        self.assertEqual(str(ctx.exception), "Invalid ROC date: 113-01-02")

    def test_parse_tpex_date_uses_patchable_roc_date_helper_for_three_part_slash(
        self,
    ) -> None:
        expected = pd.Timestamp("2024-01-02")
        with patch.object(
            data_loader,
            "_parse_roc_date",
            return_value=expected,
        ) as parse_roc:
            actual = data_loader._parse_tpex_date("113/01/02")

        parse_roc.assert_called_once_with("113/01/02")
        self.assertIs(actual, expected)

    def test_parse_tpex_date_two_part_slash_requires_month(
        self,
    ) -> None:
        with self.assertRaises(ValueError) as ctx:
            data_loader._parse_tpex_date("01/02")
        self.assertEqual(str(ctx.exception), "Invalid TPEX date: 01/02")

    def test_to_float_preserves_current_numeric_cleaning_and_error_contracts(
        self,
    ) -> None:
        self.assertEqual(data_loader._to_float(" 1,234.50 "), 1234.5)
        self.assertEqual(data_loader._to_float(42), 42.0)

        self.assertTrue(pd.isna(data_loader._to_float("--")))
        self.assertTrue(pd.isna(data_loader._to_float("   ")))

        with self.assertRaises(ValueError):
            data_loader._to_float("not-a-number")

    def test_to_int_uses_patchable_to_float_helper_and_current_int_conversion(
        self,
    ) -> None:
        with patch.object(
            data_loader,
            "_to_float",
            return_value=12.9,
        ) as to_float:
            actual = data_loader._to_int("ignored")

        to_float.assert_called_once_with("ignored")
        self.assertEqual(actual, 12)

    def test_period_start_helper_delegates_to_official_parsing_module(
        self,
    ) -> None:
        expected = pd.Timestamp("2024-01-02")
        with patch.object(
            data_loader._official_parsing,
            "period_start",
            return_value=expected,
        ) as period_start:
            actual = data_loader._period_start("6mo")

        period_start.assert_called_once_with("6mo")
        self.assertIs(actual, expected)

    def test_month_starts_helper_delegates_to_official_parsing_module(
        self,
    ) -> None:
        start = pd.Timestamp("2024-01-15")
        end = pd.Timestamp("2024-03-20")
        expected = [pd.Timestamp("2024-01-01")]
        with patch.object(
            data_loader._official_parsing,
            "month_starts",
            return_value=expected,
        ) as month_starts:
            actual = data_loader._month_starts(start, end)

        month_starts.assert_called_once_with(start, end)
        self.assertIs(actual, expected)

    def test_parse_roc_date_helper_delegates_to_official_parsing_module(
        self,
    ) -> None:
        expected = pd.Timestamp("2024-01-02")
        with patch.object(
            data_loader._official_parsing,
            "parse_roc_date",
            return_value=expected,
        ) as parse_roc:
            actual = data_loader._parse_roc_date("113/01/02")

        parse_roc.assert_called_once_with("113/01/02")
        self.assertIs(actual, expected)

    def test_parse_tpex_date_helper_delegates_to_official_parsing_module(
        self,
    ) -> None:
        month = pd.Timestamp("2024-01-01")
        expected = pd.Timestamp("2024-01-02")
        with patch.object(
            data_loader._official_parsing,
            "parse_tpex_date",
            return_value=expected,
        ) as parse_tpex:
            actual = data_loader._parse_tpex_date("01/02", month)

        parse_tpex.assert_called_once_with(
            "01/02",
            month,
            parse_roc_date=data_loader._parse_roc_date,
        )
        self.assertIs(actual, expected)

    def test_to_float_helper_delegates_to_official_parsing_module(
        self,
    ) -> None:
        expected = float("1234.5")
        with patch.object(
            data_loader._official_parsing,
            "to_float",
            return_value=expected,
        ) as to_float:
            actual = data_loader._to_float("1,234.5")

        to_float.assert_called_once_with("1,234.5")
        self.assertIs(actual, expected)

    def test_to_int_helper_delegates_to_official_parsing_module(
        self,
    ) -> None:
        expected = int("987654321")
        with patch.object(
            data_loader._official_parsing,
            "to_int",
            return_value=expected,
        ) as to_int:
            actual = data_loader._to_int("987,654,321")

        to_int.assert_called_once_with(
            "987,654,321",
            to_float=data_loader._to_float,
        )
        self.assertIs(actual, expected)

    def test_orchestration_fresh_cache_short_circuits_live_sources(
        self,
    ) -> None:
        candidates = [
            ("2330.TW", "2330", ".TW"),
            ("2330.TWO", "2330", ".TWO"),
        ]
        cache_path = Path("fresh-2330-tw.csv")
        cached = pd.DataFrame({"raw": [1]})
        expected = _download_df()

        with patch.object(
            data_loader,
            "_validate_inputs",
        ) as validate_inputs, patch.object(
            data_loader,
            "_symbol_candidates",
            return_value=candidates,
        ) as symbol_candidates, patch.object(
            data_loader,
            "_cache_path",
            return_value=cache_path,
        ) as cache_path_helper, patch.object(
            data_loader,
            "_is_cache_fresh",
            return_value=True,
        ) as is_fresh, patch.object(
            data_loader,
            "_read_cache",
            return_value=cached,
        ) as read_cache, patch.object(
            data_loader,
            "_prepare_ohlcv",
            return_value=expected,
        ) as prepare, patch.object(
            data_loader,
            "_download_yfinance_quiet",
        ) as yahoo, patch.object(
            data_loader,
            "_download_official_stock",
        ) as official, patch.object(
            data_loader,
            "_write_cache",
        ) as write_cache, patch.object(
            data_loader,
            "_get_cache_age_days",
        ) as get_cache_age_days:
            actual_df, actual_symbol = data_loader.download_tw_stock(
                "2330",
                period="6mo",
                interval="1d",
                auto_adjust=False,
                force_refresh=False,
                verbose=False,
            )

        validate_inputs.assert_called_once_with(
            "2330",
            "6mo",
            "1d",
        )
        symbol_candidates.assert_called_once_with("2330")
        cache_path_helper.assert_called_once_with(
            "2330.TW",
            "6mo",
            "1d",
            False,
        )
        is_fresh.assert_called_once_with(cache_path)
        read_cache.assert_called_once_with(cache_path)
        prepare.assert_called_once_with(
            cached,
            "2330.TW",
        )
        self.assertIs(actual_df, expected)
        self.assertEqual(actual_symbol, "2330.TW")

        yahoo.assert_not_called()
        official.assert_not_called()
        write_cache.assert_not_called()
        get_cache_age_days.assert_not_called()

    def test_orchestration_yahoo_candidate_order_and_cache_write_contract(
        self,
    ) -> None:
        candidates = [
            ("6510.TW", "6510", ".TW"),
            ("6510.TWO", "6510", ".TWO"),
        ]
        tw_path = Path("6510-tw.csv")
        two_path = Path("6510-two.csv")
        raw_two = pd.DataFrame({"raw": [2]})
        expected = _download_df()

        with patch.object(
            data_loader,
            "_validate_inputs",
        ) as validate_inputs, patch.object(
            data_loader,
            "_symbol_candidates",
            return_value=candidates,
        ) as symbol_candidates, patch.object(
            data_loader,
            "_cache_path",
            side_effect=[tw_path, two_path],
        ) as cache_path_helper, patch.object(
            data_loader,
            "_is_cache_fresh",
            side_effect=[False, False],
        ) as is_fresh, patch.object(
            data_loader,
            "_read_cache",
        ) as read_cache, patch.object(
            data_loader,
            "_download_yfinance_quiet",
            side_effect=[pd.DataFrame(), raw_two],
        ) as yahoo, patch.object(
            data_loader,
            "_prepare_ohlcv",
            return_value=expected,
        ) as prepare, patch.object(
            data_loader,
            "_write_cache",
        ) as write_cache, patch.object(
            data_loader,
            "_download_official_stock",
        ) as official, patch.object(
            data_loader,
            "_get_cache_age_days",
        ) as get_cache_age_days:
            actual_df, actual_symbol = data_loader.download_tw_stock(
                "6510",
                period="1y",
                interval="1d",
                auto_adjust=True,
            )

        self.assertEqual(
            cache_path_helper.call_args_list,
            [
                call(
                    "6510.TW",
                    "1y",
                    "1d",
                    True,
                ),
                call(
                    "6510.TWO",
                    "1y",
                    "1d",
                    True,
                ),
            ],
        )
        self.assertEqual(
            yahoo.call_args_list,
            [
                call(
                    "6510.TW",
                    "1y",
                    "1d",
                    True,
                ),
                call(
                    "6510.TWO",
                    "1y",
                    "1d",
                    True,
                ),
            ],
        )
        prepare.assert_called_once_with(
            raw_two,
            "6510.TWO",
        )
        write_cache.assert_called_once_with(
            expected,
            two_path,
        )
        official.assert_not_called()
        read_cache.assert_not_called()
        get_cache_age_days.assert_not_called()

        self.assertIs(actual_df, expected)
        self.assertEqual(actual_symbol, "6510.TWO")

    def test_orchestration_default_auto_adjust_and_official_fallback_order(
        self,
    ) -> None:
        candidates = [
            ("6488.TW", "6488", ".TW"),
            ("6488.TWO", "6488", ".TWO"),
        ]
        tw_live_path = Path("6488-tw-live.csv")
        two_live_path = Path("6488-two-live.csv")
        tw_official_path = Path("6488-tw-official.csv")
        two_official_path = Path("6488-two-official.csv")
        expected = _download_df()

        with patch.object(
            data_loader,
            "DEFAULT_AUTO_ADJUST",
            False,
        ), patch.object(
            data_loader,
            "_validate_inputs",
        ) as validate_inputs, patch.object(
            data_loader,
            "_symbol_candidates",
            return_value=candidates,
        ) as symbol_candidates, patch.object(
            data_loader,
            "_cache_path",
            side_effect=[
                tw_live_path,
                two_live_path,
                tw_official_path,
                two_official_path,
            ],
        ) as cache_path_helper, patch.object(
            data_loader,
            "_is_cache_fresh",
            side_effect=[False, False],
        ) as is_fresh, patch.object(
            data_loader,
            "_read_cache",
        ) as read_cache, patch.object(
            data_loader,
            "_download_yfinance_quiet",
            side_effect=[pd.DataFrame(), pd.DataFrame()],
        ) as yahoo, patch.object(
            data_loader,
            "_download_official_stock",
            side_effect=[
                data_loader.DataLoaderError("TWSE unavailable"),
                expected,
            ],
        ) as official, patch.object(
            data_loader,
            "_prepare_ohlcv",
        ) as prepare, patch.object(
            data_loader,
            "_write_cache",
        ) as write_cache, patch.object(
            data_loader,
            "_get_cache_age_days",
        ) as get_cache_age_days:
            actual_df, actual_symbol = data_loader.download_tw_stock(
                " 6488 ",
                period="6mo",
                interval="1d",
                auto_adjust=None,
                force_refresh=False,
            )

        validate_inputs.assert_called_once_with(
            " 6488 ",
            "6mo",
            "1d",
        )
        symbol_candidates.assert_called_once_with("6488")
        self.assertEqual(
            yahoo.call_args_list,
            [
                call(
                    "6488.TW",
                    "6mo",
                    "1d",
                    False,
                ),
                call(
                    "6488.TWO",
                    "6mo",
                    "1d",
                    False,
                ),
            ],
        )
        self.assertEqual(
            official.call_args_list,
            [
                call(
                    "6488",
                    ".TW",
                    "6mo",
                    "1d",
                ),
                call(
                    "6488",
                    ".TWO",
                    "6mo",
                    "1d",
                ),
            ],
        )
        write_cache.assert_called_once_with(
            expected,
            two_official_path,
        )
        prepare.assert_not_called()
        read_cache.assert_not_called()
        get_cache_age_days.assert_not_called()

        self.assertIs(actual_df, expected)
        self.assertEqual(actual_symbol, "6488.TWO")

    def test_orchestration_stale_cache_runs_after_live_sources_and_warns(
        self,
    ) -> None:
        class FakePath:
            def __init__(self, label: str, exists: bool) -> None:
                self.label = label
                self._exists = exists

            def exists(self) -> bool:
                return self._exists

            def __str__(self) -> str:
                return self.label

        tw_path = FakePath("2330-tw-cache.csv", True)
        two_path = FakePath("2330-two-cache.csv", True)
        candidates = [
            ("2330.TW", "2330", ".TW"),
            ("2330.TWO", "2330", ".TWO"),
        ]
        cached_two = pd.DataFrame({"raw": [2]})
        expected = _download_df()
        stderr = StringIO()

        with patch.object(
            data_loader,
            "MAX_STALE_CACHE_DAYS",
            14,
        ), patch.object(
            data_loader,
            "_validate_inputs",
        ) as validate_inputs, patch.object(
            data_loader,
            "_symbol_candidates",
            return_value=candidates,
        ) as symbol_candidates, patch.object(
            data_loader,
            "_cache_path",
            side_effect=[
                tw_path,
                two_path,
                tw_path,
                two_path,
            ],
        ) as cache_path_helper, patch.object(
            data_loader,
            "_is_cache_fresh",
            side_effect=[False, False],
        ) as is_fresh, patch.object(
            data_loader,
            "_download_yfinance_quiet",
            side_effect=[
                RuntimeError("TW Yahoo failure"),
                pd.DataFrame(),
            ],
        ) as yahoo, patch.object(
            data_loader,
            "_download_official_stock",
        ) as official, patch.object(
            data_loader,
            "_get_cache_age_days",
            side_effect=[20.0, 2.0],
        ) as get_cache_age_days, patch.object(
            data_loader,
            "_read_cache",
            return_value=cached_two,
        ) as read_cache, patch.object(
            data_loader,
            "_prepare_ohlcv",
            return_value=expected,
        ) as prepare, patch.object(
            data_loader,
            "_write_cache",
        ) as write_cache:
            with redirect_stderr(stderr):
                actual_df, actual_symbol = data_loader.download_tw_stock(
                    "2330",
                    period="1y",
                    interval="1d",
                    auto_adjust=True,
                    force_refresh=False,
                    verbose=False,
                )

        official.assert_not_called()
        write_cache.assert_not_called()

        self.assertEqual(
            get_cache_age_days.call_args_list,
            [
                call(tw_path),
                call(two_path),
            ],
        )
        read_cache.assert_called_once_with(two_path)
        prepare.assert_called_once_with(
            cached_two,
            "2330.TWO",
        )

        expected_warning = (
            "[WARNING] All live data sources failed for 2330.TWO. "
            "Using 2.0-day-old stale cached data from 2330-two-cache.csv "
            "(max stale age: 14 days).\n"
        )
        self.assertEqual(stderr.getvalue(), expected_warning)
        self.assertIs(actual_df, expected)
        self.assertEqual(actual_symbol, "2330.TWO")

    def test_orchestration_force_refresh_skips_fresh_and_stale_cache_reads(
        self,
    ) -> None:
        candidates = [
            ("2330.TW", "2330", ".TW"),
        ]
        cache_path = Path("force-refresh.csv")
        raw = pd.DataFrame({"raw": [1]})
        expected = _download_df()

        with patch.object(
            data_loader,
            "_validate_inputs",
        ) as validate_inputs, patch.object(
            data_loader,
            "_symbol_candidates",
            return_value=candidates,
        ) as symbol_candidates, patch.object(
            data_loader,
            "_cache_path",
            return_value=cache_path,
        ) as cache_path_helper, patch.object(
            data_loader,
            "_is_cache_fresh",
        ) as is_fresh, patch.object(
            data_loader,
            "_read_cache",
        ) as read_cache, patch.object(
            data_loader,
            "_get_cache_age_days",
        ) as get_cache_age_days, patch.object(
            data_loader,
            "_download_yfinance_quiet",
            return_value=raw,
        ) as yahoo, patch.object(
            data_loader,
            "_prepare_ohlcv",
            return_value=expected,
        ) as prepare, patch.object(
            data_loader,
            "_write_cache",
        ) as write_cache, patch.object(
            data_loader,
            "_download_official_stock",
        ) as official:
            actual_df, actual_symbol = data_loader.download_tw_stock(
                "2330",
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=True,
            )

        cache_path_helper.assert_called_once_with(
            "2330.TW",
            "1y",
            "1d",
            True,
        )
        is_fresh.assert_not_called()
        read_cache.assert_not_called()
        get_cache_age_days.assert_not_called()
        official.assert_not_called()

        yahoo.assert_called_once_with(
            "2330.TW",
            "1y",
            "1d",
            True,
        )
        prepare.assert_called_once_with(
            raw,
            "2330.TW",
        )
        write_cache.assert_called_once_with(
            expected,
            cache_path,
        )

        self.assertIs(actual_df, expected)
        self.assertEqual(actual_symbol, "2330.TW")

    def test_orchestration_passes_exact_error_order_to_formatter(
        self,
    ) -> None:
        class FakePath:
            def __init__(self, label: str, exists: bool) -> None:
                self.label = label
                self._exists = exists

            def exists(self) -> bool:
                return self._exists

            def __str__(self) -> str:
                return self.label

        tw_path = FakePath("missing-tw.csv", False)
        two_path = FakePath("missing-two.csv", False)
        candidates = [
            ("2330.TW", "2330", ".TW"),
            ("2330.TWO", "2330", ".TWO"),
        ]
        sentinel = data_loader.DataLoaderError("sentinel")

        with patch.object(
            data_loader,
            "_validate_inputs",
        ) as validate_inputs, patch.object(
            data_loader,
            "_symbol_candidates",
            return_value=candidates,
        ) as symbol_candidates, patch.object(
            data_loader,
            "_cache_path",
            side_effect=[
                tw_path,
                two_path,
                tw_path,
                two_path,
                tw_path,
                two_path,
            ],
        ) as cache_path_helper, patch.object(
            data_loader,
            "_is_cache_fresh",
            side_effect=[False, False],
        ) as is_fresh, patch.object(
            data_loader,
            "_read_cache",
        ) as read_cache, patch.object(
            data_loader,
            "_get_cache_age_days",
        ) as get_cache_age_days, patch.object(
            data_loader,
            "_download_yfinance_quiet",
            side_effect=[
                RuntimeError("Yahoo TW failure"),
                pd.DataFrame(),
            ],
        ) as yahoo, patch.object(
            data_loader,
            "_download_official_stock",
            side_effect=[
                RuntimeError("Official TW failure"),
                RuntimeError("Official TWO failure"),
            ],
        ) as official, patch.object(
            data_loader,
            "_prepare_ohlcv",
        ) as prepare, patch.object(
            data_loader,
            "_write_cache",
        ) as write_cache, patch.object(
            data_loader,
            "_format_no_data_error",
            return_value=sentinel,
        ) as formatter:
            with self.assertRaises(data_loader.DataLoaderError) as caught:
                data_loader.download_tw_stock(
                    "2330",
                    period="1y",
                    interval="1d",
                    auto_adjust=False,
                    force_refresh=False,
                )

        self.assertEqual(
            yahoo.call_args_list,
            [
                call(
                    "2330.TW",
                    "1y",
                    "1d",
                    False,
                ),
                call(
                    "2330.TWO",
                    "1y",
                    "1d",
                    False,
                ),
            ],
        )
        self.assertEqual(
            official.call_args_list,
            [
                call(
                    "2330",
                    ".TW",
                    "1y",
                    "1d",
                ),
                call(
                    "2330",
                    ".TWO",
                    "1y",
                    "1d",
                ),
            ],
        )
        formatter.assert_called_once_with(
            "2330",
            [
                "2330.TW",
                "2330.TWO",
            ],
            [
                (
                    "2330.TW yfinance failed: "
                    "Yahoo TW failure"
                ),
                "2330.TWO has no data",
                (
                    "2330.TW TWSE fallback failed: "
                    "Official TW failure"
                ),
                (
                    "2330.TWO TPEX fallback failed: "
                    "Official TWO failure"
                ),
            ],
        )
        self.assertIs(
            caught.exception,
            sentinel,
        )
        read_cache.assert_not_called()
        get_cache_age_days.assert_not_called()
        prepare.assert_not_called()
        write_cache.assert_not_called()

    def test_download_tw_stock_facade_delegates_to_fallback_orchestration_module(
        self,
    ) -> None:
        expected = _download_df()

        with patch.object(
            data_loader._fallback_orchestration,
            "download_tw_stock",
            return_value=(
                expected,
                "2330.TW",
            ),
        ) as orchestrate:
            actual_df, actual_symbol = data_loader.download_tw_stock(
                " 2330 ",
                period="6mo",
                interval="1d",
                auto_adjust=False,
                force_refresh=True,
                verbose=True,
            )

        orchestrate.assert_called_once_with(
            " 2330 ",
            "6mo",
            "1d",
            False,
            True,
            True,
            validate_inputs=data_loader._validate_inputs,
            symbol_candidates=data_loader._symbol_candidates,
            build_cache_path=data_loader._cache_path,
            is_cache_fresh=data_loader._is_cache_fresh,
            read_cache=data_loader._read_cache,
            prepare_ohlcv=data_loader._prepare_ohlcv,
            download_yfinance=data_loader._download_yfinance_quiet,
            write_cache=data_loader._write_cache,
            download_official=data_loader._download_official_stock,
            get_cache_age_days=data_loader._get_cache_age_days,
            format_no_data_error=data_loader._format_no_data_error,
            default_auto_adjust=data_loader.DEFAULT_AUTO_ADJUST,
            max_stale_cache_days=data_loader.MAX_STALE_CACHE_DAYS,
        )
        self.assertIs(actual_df, expected)
        self.assertEqual(actual_symbol, "2330.TW")

    def test_fallback_orchestration_accepts_fully_injected_fake_dependencies(
        self,
    ) -> None:
        class FakePath:
            def __init__(self, label: str, exists: bool) -> None:
                self.label = label
                self._exists = exists

            def exists(self) -> bool:
                return self._exists

            def __str__(self) -> str:
                return self.label

        tw_path = FakePath("missing-tw.csv", False)
        two_path = FakePath("missing-two.csv", False)
        candidates = [
            ("2330.TW", "2330", ".TW"),
            ("2330.TWO", "2330", ".TWO"),
        ]
        sentinel = data_loader.DataLoaderError("sentinel")

        validate_inputs = Mock()
        symbol_candidates = Mock(return_value=candidates)
        build_cache_path = Mock(
            side_effect=[
                tw_path,
                two_path,
                tw_path,
                two_path,
                tw_path,
                two_path,
            ]
        )
        is_cache_fresh = Mock(side_effect=[False, False])
        read_cache = Mock()
        prepare_ohlcv = Mock()
        download_yfinance = Mock(
            side_effect=[
                RuntimeError("Yahoo TW failure"),
                pd.DataFrame(),
            ]
        )
        write_cache = Mock()
        download_official = Mock(
            side_effect=[
                RuntimeError("Official TW failure"),
                RuntimeError("Official TWO failure"),
            ]
        )
        get_cache_age_days = Mock()
        format_no_data_error = Mock(return_value=sentinel)

        with self.assertRaises(data_loader.DataLoaderError) as caught:
            fallback_orchestration.download_tw_stock(
                " 2330 ",
                period="1y",
                interval="1d",
                auto_adjust=False,
                force_refresh=False,
                verbose=False,
                validate_inputs=validate_inputs,
                symbol_candidates=symbol_candidates,
                build_cache_path=build_cache_path,
                is_cache_fresh=is_cache_fresh,
                read_cache=read_cache,
                prepare_ohlcv=prepare_ohlcv,
                download_yfinance=download_yfinance,
                write_cache=write_cache,
                download_official=download_official,
                get_cache_age_days=get_cache_age_days,
                format_no_data_error=format_no_data_error,
                default_auto_adjust=True,
                max_stale_cache_days=14,
            )

        validate_inputs.assert_called_once_with(" 2330 ", "1y", "1d")
        symbol_candidates.assert_called_once_with("2330")
        self.assertEqual(
            build_cache_path.call_args_list,
            [
                call("2330.TW", "1y", "1d", False),
                call("2330.TWO", "1y", "1d", False),
                call("2330.TW", "1y", "1d", False),
                call("2330.TWO", "1y", "1d", False),
                call("2330.TW", "1y", "1d", False),
                call("2330.TWO", "1y", "1d", False),
            ],
        )
        self.assertEqual(
            download_yfinance.call_args_list,
            [
                call("2330.TW", "1y", "1d", False),
                call("2330.TWO", "1y", "1d", False),
            ],
        )
        self.assertEqual(
            download_official.call_args_list,
            [
                call("2330", ".TW", "1y", "1d"),
                call("2330", ".TWO", "1y", "1d"),
            ],
        )
        format_no_data_error.assert_called_once_with(
            "2330",
            ["2330.TW", "2330.TWO"],
            [
                "2330.TW yfinance failed: Yahoo TW failure",
                "2330.TWO has no data",
                "2330.TW TWSE fallback failed: Official TW failure",
                "2330.TWO TPEX fallback failed: Official TWO failure",
            ],
        )
        self.assertIs(caught.exception, sentinel)
        read_cache.assert_not_called()
        prepare_ohlcv.assert_not_called()
        write_cache.assert_not_called()
        get_cache_age_days.assert_not_called()

if __name__ == "__main__":
    unittest.main()
