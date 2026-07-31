from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from tw_stock_tool.data import data_loader


def _frame(value: int = 10) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [float(value)],
            "High": [float(value + 2)],
            "Low": [float(value - 1)],
            "Close": [float(value + 1)],
            "Volume": [1000],
        },
        index=pd.to_datetime(["2024-01-02"]),
    )


class DataLoaderFacadeTest(unittest.TestCase):
    def test_validate_inputs_rejects_blank_stock_id(self) -> None:
        for value in ("", "   "):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    data_loader.DataLoaderError,
                    "^Stock id cannot be blank\\.$",
                ):
                    data_loader._validate_inputs(value, "1y", "1d")

    def test_validate_inputs_rejects_non_numeric_stock_id(self) -> None:
        with self.assertRaisesRegex(
            data_loader.DataLoaderError,
            "^Invalid stock ID format: ABC$",
        ):
            data_loader._validate_inputs("ABC", "1y", "1d")

    def test_validate_inputs_rejects_invalid_period_and_interval(self) -> None:
        with self.assertRaisesRegex(
            data_loader.DataLoaderError,
            "^Invalid period: invalid\\.$",
        ):
            data_loader._validate_inputs("2330", "invalid", "1d")
        with self.assertRaisesRegex(
            data_loader.DataLoaderError,
            "^Invalid interval: invalid\\.$",
        ):
            data_loader._validate_inputs("2330", "1y", "invalid")

    def test_symbol_candidates_normalize_bare_and_explicit_suffixes(self) -> None:
        self.assertEqual(
            data_loader._symbol_candidates(" 2330 "),
            [
                ("2330.TW", "2330", ".TW"),
                ("2330.TWO", "2330", ".TWO"),
            ],
        )
        self.assertEqual(
            data_loader._symbol_candidates("2330.tw"),
            [("2330.TW", "2330", ".TW")],
        )
        self.assertEqual(
            data_loader._symbol_candidates("6488.two"),
            [("6488.TWO", "6488", ".TWO")],
        )

    def test_no_data_error_contains_symbols_guidance_and_attempt_details(self) -> None:
        error = data_loader._format_no_data_error(
            "2330",
            ["2330.TW", "2330.TWO"],
            ["2330.TW has no data", "2330.TWO yfinance failed: timeout"],
        )
        self.assertIsInstance(error, data_loader.DataLoaderError)
        message = str(error)
        self.assertIn("No price data found for 2330", message)
        self.assertIn("Tried: 2330.TW, 2330.TWO", message)
        self.assertIn("delisted", message)
        self.assertIn("rate-limited", message)
        self.assertIn(
            "Attempts: 2330.TW has no data | 2330.TWO yfinance failed: timeout",
            message,
        )

    def test_public_facade_forwards_exact_dependencies_and_defaults(self) -> None:
        expected = (_frame(), "2330.TW")
        with patch.object(
            data_loader._fallback_orchestration,
            "download_tw_stock",
            return_value=expected,
        ) as orchestrate:
            actual = data_loader.download_tw_stock(
                "2330",
                period="6mo",
                interval="1d",
                auto_adjust=False,
                force_refresh=True,
                verbose=True,
            )

        self.assertIs(actual, expected)
        orchestrate.assert_called_once_with(
            "2330",
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

    def test_cache_compatibility_seams_delegate_to_cache_runtime(self) -> None:
        path = Path("cache.csv")
        frame = _frame()
        with patch.object(
            data_loader._cache_runtime,
            "_cache_path",
            return_value=path,
        ) as cache_path:
            self.assertIs(
                data_loader._cache_path("2330.TW", "1y", "1d", True),
                path,
            )
        cache_path.assert_called_once_with(
            "2330.TW",
            "1y",
            "1d",
            True,
            cache_dir=data_loader.CACHE_DIR,
        )

        for name, args, expected in (
            ("_is_cache_fresh", (path,), True),
            ("_get_cache_age_days", (path,), 1.25),
            ("_read_cache", (path,), frame),
        ):
            with self.subTest(name=name):
                with patch.object(
                    data_loader._cache_runtime,
                    name,
                    return_value=expected,
                ) as dependency:
                    actual = getattr(data_loader, name)(*args)
                if isinstance(expected, pd.DataFrame):
                    self.assertIs(actual, expected)
                else:
                    self.assertEqual(actual, expected)
                dependency.assert_called_once_with(*args)

        with patch.object(data_loader._cache_runtime, "_write_cache") as write:
            data_loader._write_cache(frame, path)
        write.assert_called_once_with(frame, path)

    def test_prepare_ohlcv_seam_uses_owner_module_and_public_error_type(self) -> None:
        source = pd.DataFrame({"raw": [1]})
        expected = _frame()
        with patch.object(
            data_loader._ohlcv_normalization,
            "prepare_ohlcv",
            return_value=expected,
        ) as prepare:
            actual = data_loader._prepare_ohlcv(source, "2330.TW")

        self.assertIs(actual, expected)
        prepare.assert_called_once_with(
            source,
            "2330.TW",
            normalize_columns=data_loader._ohlcv_normalization.normalize_columns,
            error_type=data_loader.DataLoaderError,
        )

    def test_yfinance_seam_delegates_to_owner_provider(self) -> None:
        expected = _frame()
        with patch.object(
            data_loader.yfinance_provider,
            "download_yfinance_quiet",
            return_value=expected,
        ) as download:
            actual = data_loader._download_yfinance_quiet(
                "2330.TW",
                "1y",
                "1d",
                True,
            )

        self.assertIs(actual, expected)
        download.assert_called_once_with("2330.TW", "1y", "1d", True)

    def test_official_provider_seams_inject_owner_dependencies(self) -> None:
        expected = _frame()
        with patch.object(
            data_loader.twse_provider,
            "download_twse_stock",
            return_value=expected,
        ) as twse:
            self.assertIs(
                data_loader._download_twse_stock("2330", "1y", "1d"),
                expected,
            )
        twse.assert_called_once_with(
            "2330",
            "1y",
            "1d",
            period_start=data_loader._period_start,
            month_starts=data_loader._month_starts,
            parse_roc_date=data_loader._parse_roc_date,
            to_float=data_loader._to_float,
            to_int=data_loader._to_int,
            finalize_official_rows=data_loader._finalize_official_rows,
            error_type=data_loader.DataLoaderError,
        )

        with patch.object(
            data_loader.tpex_provider,
            "download_tpex_stock",
            return_value=expected,
        ) as tpex:
            self.assertIs(
                data_loader._download_tpex_stock("6488", "1y", "1d"),
                expected,
            )
        tpex.assert_called_once_with(
            "6488",
            "1y",
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

    def test_official_router_selects_exchange_and_rejects_unknown_suffix(self) -> None:
        twse_frame = _frame(10)
        tpex_frame = _frame(20)
        with patch.object(
            data_loader,
            "_download_twse_stock",
            return_value=twse_frame,
        ) as twse:
            self.assertIs(
                data_loader._download_official_stock("2330", ".TW", "1y", "1d"),
                twse_frame,
            )
        twse.assert_called_once_with("2330", "1y", "1d")

        with patch.object(
            data_loader,
            "_download_tpex_stock",
            return_value=tpex_frame,
        ) as tpex:
            self.assertIs(
                data_loader._download_official_stock("6488", ".TWO", "1y", "1d"),
                tpex_frame,
            )
        tpex.assert_called_once_with("6488", "1y", "1d")

        with self.assertRaisesRegex(
            data_loader.DataLoaderError,
            "^Unsupported official fallback suffix: \\.US$",
        ):
            data_loader._download_official_stock("AAPL", ".US", "1y", "1d")

    def test_public_download_writes_and_reuses_fresh_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(temp_dir)):
                with patch.object(
                    data_loader.yfinance_provider,
                    "download_yfinance_quiet",
                    return_value=_frame(),
                ) as download:
                    first, first_symbol = data_loader.download_tw_stock("2330")
                    second, second_symbol = data_loader.download_tw_stock("2330")

        self.assertEqual(first_symbol, "2330.TW")
        self.assertEqual(second_symbol, "2330.TW")
        self.assertEqual(download.call_count, 1)
        pd.testing.assert_frame_equal(first, second, check_freq=False)

    def test_force_refresh_redownloads_instead_of_using_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(temp_dir)):
                with patch.object(
                    data_loader.yfinance_provider,
                    "download_yfinance_quiet",
                    return_value=_frame(),
                ) as download:
                    data_loader.download_tw_stock("2330")
                    data_loader.download_tw_stock("2330", force_refresh=True)

        self.assertEqual(download.call_count, 2)

    def test_public_download_tries_two_suffix_after_tw_yahoo_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(temp_dir)):
                with patch.object(
                    data_loader.yfinance_provider,
                    "download_yfinance_quiet",
                    side_effect=[pd.DataFrame(), _frame(20)],
                ) as download:
                    frame, symbol = data_loader.download_tw_stock(
                        "6488",
                        auto_adjust=True,
                        force_refresh=True,
                    )

        self.assertEqual(symbol, "6488.TWO")
        self.assertEqual(float(frame.iloc[0]["Close"]), 21.0)
        self.assertEqual(
            [item.args[0] for item in download.call_args_list],
            ["6488.TW", "6488.TWO"],
        )

    def test_public_download_uses_official_fallback_only_when_unadjusted(self) -> None:
        official = _frame(30)
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(temp_dir)):
                with patch.object(
                    data_loader,
                    "_download_yfinance_quiet",
                    return_value=pd.DataFrame(),
                ):
                    with patch.object(
                        data_loader,
                        "_download_official_stock",
                        return_value=official,
                    ) as download_official:
                        actual, symbol = data_loader.download_tw_stock(
                            "2330",
                            auto_adjust=False,
                            force_refresh=True,
                        )

        self.assertIs(actual, official)
        self.assertEqual(symbol, "2330.TW")
        download_official.assert_called_once_with("2330", ".TW", "1y", "1d")

    def test_adjusted_public_download_skips_official_and_reports_all_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(temp_dir)):
                with patch.object(
                    data_loader,
                    "_download_yfinance_quiet",
                    return_value=pd.DataFrame(),
                ):
                    with patch.object(
                        data_loader,
                        "_download_official_stock",
                    ) as official:
                        with self.assertRaises(data_loader.DataLoaderError) as raised:
                            data_loader.download_tw_stock(
                                "2330",
                                auto_adjust=True,
                                force_refresh=True,
                            )

        official.assert_not_called()
        self.assertIn("Tried: 2330.TW, 2330.TWO", str(raised.exception))

    def test_explicit_suffix_limits_public_download_to_one_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(data_loader, "CACHE_DIR", Path(temp_dir)):
                with patch.object(
                    data_loader,
                    "_download_yfinance_quiet",
                    return_value=pd.DataFrame(),
                ) as yahoo:
                    with self.assertRaises(data_loader.DataLoaderError):
                        data_loader.download_tw_stock(
                            "6488.TWO",
                            auto_adjust=True,
                            force_refresh=True,
                        )

        yahoo.assert_called_once_with("6488.TWO", "1y", "1d", True)


if __name__ == "__main__":
    unittest.main()
