from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import logging
import unittest
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.data.providers import yfinance_provider


def _frame(value: int = 1) -> pd.DataFrame:
    return pd.DataFrame({"Close": [value]})


class YfinanceProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        logger = logging.getLogger("yfinance")
        self.logger = logger
        self.logger_state = (logger.disabled, logger.level, logger.propagate)

    def tearDown(self) -> None:
        disabled, level, propagate = self.logger_state
        self.logger.disabled = disabled
        self.logger.setLevel(level)
        self.logger.propagate = propagate

    def test_forwards_exact_arguments_and_returns_provider_frame(self) -> None:
        expected = _frame()
        with patch.object(
            yfinance_provider.yf,
            "download",
            return_value=expected,
        ) as download:
            actual = yfinance_provider.download_yfinance_quiet(
                "2330.TW",
                "1y",
                "1d",
                False,
            )

        self.assertIs(actual, expected)
        download.assert_called_once_with(
            "2330.TW",
            period="1y",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )

    def test_suppresses_provider_stdout_and_stderr(self) -> None:
        def noisy_download(*args, **kwargs):
            print("provider stdout")
            print("provider stderr", file=__import__("sys").stderr)
            return _frame()

        stdout = StringIO()
        stderr = StringIO()
        with patch.object(
            yfinance_provider.yf,
            "download",
            side_effect=noisy_download,
        ):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                actual = yfinance_provider.download_yfinance_quiet(
                    "2330.TW",
                    "1mo",
                    "1d",
                    True,
                )

        self.assertEqual(float(actual.iloc[0]["Close"]), 1.0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_restores_logger_state_after_success(self) -> None:
        self.logger.disabled = False
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = True
        expected_state = (
            self.logger.disabled,
            self.logger.level,
            self.logger.propagate,
        )

        with patch.object(
            yfinance_provider.yf,
            "download",
            return_value=_frame(),
        ):
            yfinance_provider.download_yfinance_quiet(
                "2330.TW",
                "1y",
                "1d",
                True,
            )

        self.assertEqual(
            (
                self.logger.disabled,
                self.logger.level,
                self.logger.propagate,
            ),
            expected_state,
        )

    def test_restores_logger_state_and_propagates_provider_exception(self) -> None:
        self.logger.disabled = True
        self.logger.setLevel(logging.WARNING)
        self.logger.propagate = False
        expected_state = (
            self.logger.disabled,
            self.logger.level,
            self.logger.propagate,
        )

        with patch.object(
            yfinance_provider.yf,
            "download",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaisesRegex(RuntimeError, "^boom$"):
                yfinance_provider.download_yfinance_quiet(
                    "2330.TW",
                    "1y",
                    "1d",
                    True,
                )

        self.assertEqual(
            (
                self.logger.disabled,
                self.logger.level,
                self.logger.propagate,
            ),
            expected_state,
        )

    def test_concurrent_calls_are_serialized_and_console_noise_stays_hidden(self) -> None:
        def noisy_download(symbol, *args, **kwargs):
            print(f"stdout:{symbol}")
            print(f"stderr:{symbol}", file=__import__("sys").stderr)
            return _frame(int(symbol.split(".")[0]))

        symbols = [f"800{index}.TW" for index in range(6)]
        stdout = StringIO()
        stderr = StringIO()
        with patch.object(
            yfinance_provider.yf,
            "download",
            side_effect=noisy_download,
        ):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                with ThreadPoolExecutor(max_workers=3) as executor:
                    results = list(
                        executor.map(
                            lambda symbol: yfinance_provider.download_yfinance_quiet(
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

    def test_exception_does_not_leave_console_lock_held(self) -> None:
        with patch.object(
            yfinance_provider.yf,
            "download",
            side_effect=[RuntimeError("first"), _frame(2)],
        ):
            with self.assertRaisesRegex(RuntimeError, "^first$"):
                yfinance_provider.download_yfinance_quiet(
                    "2330.TW",
                    "1y",
                    "1d",
                    True,
                )
            actual = yfinance_provider.download_yfinance_quiet(
                "2330.TW",
                "1y",
                "1d",
                True,
            )

        self.assertEqual(float(actual.iloc[0]["Close"]), 2.0)


if __name__ == "__main__":
    unittest.main()
