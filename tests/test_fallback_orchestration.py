from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
import unittest
from unittest.mock import Mock, call

import pandas as pd

from tw_stock_tool.data import fallback_orchestration


@dataclass
class _Path:
    name: str
    present: bool = False

    def exists(self) -> bool:
        return self.present

    def __str__(self) -> str:
        return self.name


def _frame(value: int = 1) -> pd.DataFrame:
    return pd.DataFrame(
        {"Open": [value], "High": [value], "Low": [value], "Close": [value], "Volume": [value]},
        index=pd.to_datetime(["2024-01-01"]),
    )


class FallbackOrchestrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.candidates = [
            ("2330.TW", "2330", ".TW"),
            ("2330.TWO", "2330", ".TWO"),
        ]
        self.paths = {
            "2330.TW": _Path("cache/2330.TW.csv"),
            "2330.TWO": _Path("cache/2330.TWO.csv"),
        }

    def _deps(self) -> dict[str, object]:
        return {
            "validate_inputs": Mock(),
            "symbol_candidates": Mock(return_value=self.candidates),
            "build_cache_path": Mock(
                side_effect=lambda symbol, period, interval, auto_adjust: self.paths[symbol]
            ),
            "is_cache_fresh": Mock(return_value=False),
            "read_cache": Mock(),
            "prepare_ohlcv": Mock(side_effect=lambda frame, symbol: frame),
            "download_yfinance": Mock(return_value=pd.DataFrame()),
            "write_cache": Mock(),
            "download_official": Mock(side_effect=RuntimeError("official unavailable")),
            "get_cache_age_days": Mock(return_value=1.0),
            "format_no_data_error": Mock(
                side_effect=lambda original, tried, errors: RuntimeError("final no data")
            ),
            "default_auto_adjust": True,
            "max_stale_cache_days": 7,
        }

    def _run(self, deps: dict[str, object], **kwargs):
        return fallback_orchestration.download_tw_stock(
            kwargs.pop("stock_id", "2330"),
            kwargs.pop("period", "1y"),
            kwargs.pop("interval", "1d"),
            kwargs.pop("auto_adjust", None),
            kwargs.pop("force_refresh", False),
            kwargs.pop("verbose", False),
            **deps,
            **kwargs,
        )

    def test_fresh_cache_precedes_live_sources_and_uses_default_adjustment(self) -> None:
        deps = self._deps()
        cached = _frame(10)
        prepared = _frame(11)
        deps["is_cache_fresh"].side_effect = [True]
        deps["read_cache"].return_value = cached
        deps["prepare_ohlcv"].return_value = prepared
        stdout = StringIO()

        with redirect_stdout(stdout):
            actual, symbol = self._run(deps, verbose=True)

        self.assertIs(actual, prepared)
        self.assertEqual(symbol, "2330.TW")
        deps["validate_inputs"].assert_called_once_with("2330", "1y", "1d")
        deps["build_cache_path"].assert_called_once_with(
            "2330.TW", "1y", "1d", True
        )
        deps["read_cache"].assert_called_once_with(self.paths["2330.TW"])
        deps["prepare_ohlcv"].assert_called_once_with(cached, "2330.TW")
        deps["download_yfinance"].assert_not_called()
        deps["download_official"].assert_not_called()
        self.assertEqual(stdout.getvalue(), "2330.TW: From cache\n")

    def test_force_refresh_skips_fresh_and_stale_cache_checks(self) -> None:
        deps = self._deps()
        downloaded = _frame(20)
        prepared = _frame(21)
        self.paths["2330.TW"].present = True
        deps["download_yfinance"].return_value = downloaded
        deps["prepare_ohlcv"].return_value = prepared

        actual, symbol = self._run(deps, force_refresh=True)

        self.assertIs(actual, prepared)
        self.assertEqual(symbol, "2330.TW")
        deps["is_cache_fresh"].assert_not_called()
        deps["get_cache_age_days"].assert_not_called()
        deps["read_cache"].assert_not_called()
        deps["write_cache"].assert_called_once_with(
            prepared, self.paths["2330.TW"]
        )

    def test_fresh_cache_read_failure_falls_through_to_yahoo(self) -> None:
        deps = self._deps()
        deps["is_cache_fresh"].side_effect = [True]
        deps["read_cache"].side_effect = RuntimeError("bad cache")
        downloaded = _frame(30)
        deps["download_yfinance"].return_value = downloaded

        actual, symbol = self._run(deps)

        self.assertIs(actual, downloaded)
        self.assertEqual(symbol, "2330.TW")
        deps["download_yfinance"].assert_called_once_with(
            "2330.TW", "1y", "1d", True
        )

    def test_yahoo_candidates_are_tried_in_order_until_one_succeeds(self) -> None:
        deps = self._deps()
        second = _frame(40)
        deps["download_yfinance"].side_effect = [pd.DataFrame(), second]

        actual, symbol = self._run(deps)

        self.assertIs(actual, second)
        self.assertEqual(symbol, "2330.TWO")
        self.assertEqual(
            deps["download_yfinance"].call_args_list,
            [
                call("2330.TW", "1y", "1d", True),
                call("2330.TWO", "1y", "1d", True),
            ],
        )
        deps["write_cache"].assert_called_once_with(
            second, self.paths["2330.TWO"]
        )

    def test_cache_write_failure_does_not_discard_successful_live_data(self) -> None:
        deps = self._deps()
        downloaded = _frame(50)
        deps["download_yfinance"].return_value = downloaded
        deps["write_cache"].side_effect = RuntimeError("disk full")

        actual, symbol = self._run(deps)

        self.assertIs(actual, downloaded)
        self.assertEqual(symbol, "2330.TW")
        deps["format_no_data_error"].assert_not_called()

    def test_official_fallback_runs_after_all_yahoo_candidates_when_unadjusted(self) -> None:
        deps = self._deps()
        official = _frame(60)
        deps["download_official"].side_effect = [official]
        stdout = StringIO()

        with redirect_stdout(stdout):
            actual, symbol = self._run(
                deps,
                auto_adjust=False,
                verbose=True,
            )

        self.assertIs(actual, official)
        self.assertEqual(symbol, "2330.TW")
        self.assertEqual(deps["download_yfinance"].call_count, 2)
        deps["download_official"].assert_called_once_with(
            "2330", ".TW", "1y", "1d"
        )
        deps["write_cache"].assert_called_once_with(
            official, self.paths["2330.TW"]
        )
        self.assertIn("Downloaded from TWSE fallback", stdout.getvalue())

    def test_adjusted_mode_skips_official_fallback(self) -> None:
        deps = self._deps()

        with self.assertRaisesRegex(RuntimeError, "^final no data$"):
            self._run(deps, auto_adjust=True, force_refresh=True)

        deps["download_official"].assert_not_called()
        deps["format_no_data_error"].assert_called_once()

    def test_stale_cache_is_last_resort_and_emits_warning(self) -> None:
        deps = self._deps()
        self.paths["2330.TW"].present = True
        stale = _frame(70)
        prepared = _frame(71)
        deps["read_cache"].return_value = stale
        deps["prepare_ohlcv"].return_value = prepared
        deps["get_cache_age_days"].return_value = 2.5
        stderr = StringIO()
        stdout = StringIO()

        with redirect_stderr(stderr), redirect_stdout(stdout):
            actual, symbol = self._run(
                deps,
                auto_adjust=True,
                verbose=True,
            )

        self.assertIs(actual, prepared)
        self.assertEqual(symbol, "2330.TW")
        self.assertIn("2.5-day-old stale cached data", stderr.getvalue())
        self.assertIn("max stale age: 7 days", stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "2330.TW: From stale cache\n")

    def test_stale_cache_over_limit_is_rejected_and_recorded(self) -> None:
        deps = self._deps()
        self.paths["2330.TW"].present = True
        deps["get_cache_age_days"].return_value = 8.25

        with self.assertRaisesRegex(RuntimeError, "^final no data$"):
            self._run(deps, auto_adjust=True)

        errors = deps["format_no_data_error"].call_args.args[2]
        self.assertIn(
            "2330.TW stale cache rejected: 8.2 days old (exceeds 7 day limit)",
            errors,
        )
        deps["read_cache"].assert_not_called()

    def test_stale_mtime_and_read_failures_continue_to_later_candidates(self) -> None:
        deps = self._deps()
        for path in self.paths.values():
            path.present = True
        deps["get_cache_age_days"].side_effect = [
            RuntimeError("bad mtime"),
            1.0,
        ]
        deps["read_cache"].side_effect = RuntimeError("bad stale cache")

        with self.assertRaisesRegex(RuntimeError, "^final no data$"):
            self._run(deps, auto_adjust=True)

        errors = deps["format_no_data_error"].call_args.args[2]
        self.assertIn("2330.TW stale cache mtime read failed: bad mtime", errors)
        self.assertIn("2330.TWO stale cache read failed: bad stale cache", errors)

    def test_final_error_receives_tried_symbols_and_attempts_in_execution_order(self) -> None:
        deps = self._deps()
        deps["download_yfinance"].side_effect = [
            RuntimeError("tw yahoo"),
            pd.DataFrame(),
        ]
        deps["download_official"].side_effect = [
            RuntimeError("tw official"),
            RuntimeError("two official"),
        ]

        with self.assertRaisesRegex(RuntimeError, "^final no data$"):
            self._run(deps, auto_adjust=False, force_refresh=True)

        original, tried, errors = deps["format_no_data_error"].call_args.args
        self.assertEqual(original, "2330")
        self.assertEqual(tried, ["2330.TW", "2330.TWO"])
        self.assertEqual(
            errors,
            [
                "2330.TW yfinance failed: tw yahoo",
                "2330.TWO has no data",
                "2330.TW TWSE fallback failed: tw official",
                "2330.TWO TPEX fallback failed: two official",
            ],
        )


if __name__ == "__main__":
    unittest.main()
