import unittest
from unittest.mock import Mock, call, patch

import pandas as pd

from tw_stock_tool.data import official_parsing
from tw_stock_tool.data.providers import twse_provider


class _Response:
    def __init__(self, payload, *, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.raise_calls = 0
        self.json_calls = 0

    def raise_for_status(self) -> None:
        self.raise_calls += 1
        if self.error is not None:
            raise self.error

    def json(self):
        self.json_calls += 1
        return self.payload


class TwseProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.start = pd.Timestamp("2024-01-01")
        self.months = [
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2024-02-01"),
        ]

    def _download(self, *, responses, months=None, finalize=None):
        if finalize is None:
            finalize = Mock(return_value=pd.DataFrame({"Close": [11.0]}))
        with patch.object(
            twse_provider.requests,
            "get",
            side_effect=responses,
        ) as request_get:
            result = twse_provider.download_twse_stock(
                "2330",
                "2mo",
                "1d",
                period_start=Mock(return_value=self.start),
                month_starts=Mock(return_value=self.months if months is None else months),
                parse_roc_date=official_parsing.parse_roc_date,
                to_float=official_parsing.to_float,
                to_int=lambda value: official_parsing.to_int(
                    value,
                    to_float=official_parsing.to_float,
                ),
                finalize_official_rows=finalize,
                error_type=RuntimeError,
            )
        return result, request_get, finalize

    def test_requests_each_month_and_maps_rows_before_finalizing(self) -> None:
        first = _Response({"stat": "not ok", "data": []})
        second = _Response(
            {
                "stat": "OK",
                "data": [
                    [
                        "113/02/05",
                        "1,234",
                        "ignored",
                        "10.5",
                        "12",
                        "9",
                        "11.5",
                    ]
                ],
            }
        )
        expected = pd.DataFrame({"Close": [11.5]})
        finalize = Mock(return_value=expected)

        actual, request_get, finalize = self._download(
            responses=[first, second],
            finalize=finalize,
        )

        self.assertIs(actual, expected)
        self.assertEqual(first.raise_calls, 1)
        self.assertEqual(second.raise_calls, 1)
        self.assertEqual(
            request_get.call_args_list,
            [
                call(
                    "https://www.twse.com.tw/exchangeReport/STOCK_DAY",
                    params={
                        "response": "json",
                        "date": "20240101",
                        "stockNo": "2330",
                    },
                    timeout=20,
                ),
                call(
                    "https://www.twse.com.tw/exchangeReport/STOCK_DAY",
                    params={
                        "response": "json",
                        "date": "20240201",
                        "stockNo": "2330",
                    },
                    timeout=20,
                ),
            ],
        )
        rows, stock_id, suffix, start, period = finalize.call_args.args
        self.assertEqual(stock_id, "2330")
        self.assertEqual(suffix, ".TW")
        self.assertEqual(start, self.start)
        self.assertEqual(period, "2mo")
        self.assertEqual(
            rows,
            [
                {
                    "Date": pd.Timestamp("2024-02-05"),
                    "Open": 10.5,
                    "High": 12.0,
                    "Low": 9.0,
                    "Close": 11.5,
                    "Volume": 1234,
                }
            ],
        )

    def test_non_ok_months_are_skipped_and_empty_rows_reach_finalizer(self) -> None:
        responses = [
            _Response({"stat": "FAIL"}),
            _Response({"stat": "no data"}),
        ]
        finalize = Mock(side_effect=RuntimeError("no official rows"))

        with self.assertRaisesRegex(RuntimeError, "^no official rows$"):
            self._download(responses=responses, finalize=finalize)

        finalize.assert_called_once_with([], "2330", ".TW", self.start, "2mo")

    def test_http_error_propagates_before_json_and_finalization(self) -> None:
        response = _Response({}, error=RuntimeError("http failure"))
        finalize = Mock()

        with self.assertRaisesRegex(RuntimeError, "^http failure$"):
            self._download(
                responses=[response],
                months=[self.months[0]],
                finalize=finalize,
            )

        self.assertEqual(response.raise_calls, 1)
        self.assertEqual(response.json_calls, 0)
        finalize.assert_not_called()

    def test_non_daily_interval_is_rejected_before_any_dependency(self) -> None:
        dependencies = {
            "period_start": Mock(),
            "month_starts": Mock(),
            "parse_roc_date": Mock(),
            "to_float": Mock(),
            "to_int": Mock(),
            "finalize_official_rows": Mock(),
        }

        with patch.object(twse_provider.requests, "get") as request_get:
            with self.assertRaisesRegex(
                RuntimeError,
                "^TWSE fallback only supports 1d interval\\.$",
            ):
                twse_provider.download_twse_stock(
                    "2330",
                    "1mo",
                    "1wk",
                    error_type=RuntimeError,
                    **dependencies,
                )

        request_get.assert_not_called()
        for dependency in dependencies.values():
            dependency.assert_not_called()


if __name__ == "__main__":
    unittest.main()
