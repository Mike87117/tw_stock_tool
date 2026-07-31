import unittest
from unittest.mock import Mock, call, patch

import pandas as pd

from tw_stock_tool.data import official_parsing
from tw_stock_tool.data.providers import tpex_provider


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


def _parse_tpex(value, month=None):
    return official_parsing.parse_tpex_date(
        value,
        month,
        parse_roc_date=official_parsing.parse_roc_date,
    )


def _to_int(value):
    return official_parsing.to_int(
        value,
        to_float=official_parsing.to_float,
    )


class TpexProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.start = pd.Timestamp("2024-01-01")
        self.months = [
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2024-02-01"),
        ]

    def _download_monthly(
        self,
        *,
        responses,
        months=None,
        finalize=None,
        latest=None,
    ):
        if finalize is None:
            finalize = Mock(return_value=pd.DataFrame({"Close": [11.0]}))
        if latest is None:
            latest = Mock(return_value=pd.DataFrame({"Close": [12.0]}))
        with patch.object(
            tpex_provider.requests,
            "get",
            side_effect=responses,
        ) as request_get:
            result = tpex_provider.download_tpex_stock(
                "6488",
                "2mo",
                "1d",
                period_start=Mock(return_value=self.start),
                month_starts=Mock(return_value=self.months if months is None else months),
                parse_tpex_date=_parse_tpex,
                to_float=official_parsing.to_float,
                to_int=_to_int,
                finalize_official_rows=finalize,
                download_latest_quote=latest,
                error_type=RuntimeError,
            )
        return result, request_get, finalize, latest

    def test_monthly_requests_map_rows_and_finalize_without_latest_fallback(self) -> None:
        first = _Response({"stat": "not ok"})
        second = _Response(
            {
                "stat": "ok",
                "tables": [
                    {
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
                        ]
                    }
                ],
            }
        )
        expected = pd.DataFrame({"Close": [11.5]})
        finalize = Mock(return_value=expected)
        latest = Mock()

        actual, request_get, finalize, latest = self._download_monthly(
            responses=[first, second],
            finalize=finalize,
            latest=latest,
        )

        self.assertIs(actual, expected)
        self.assertEqual(
            request_get.call_args_list,
            [
                call(
                    "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock",
                    params={
                        "response": "json",
                        "date": "2024/01/01",
                        "id": "6488",
                    },
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=20,
                ),
                call(
                    "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock",
                    params={
                        "response": "json",
                        "date": "2024/02/01",
                        "id": "6488",
                    },
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=20,
                ),
            ],
        )
        rows, stock_id, suffix, start, period = finalize.call_args.args
        self.assertEqual(stock_id, "6488")
        self.assertEqual(suffix, ".TWO")
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
        latest.assert_not_called()

    def test_non_ok_empty_tables_and_short_rows_fall_back_to_latest_quote(self) -> None:
        responses = [
            _Response({"stat": "fail"}),
            _Response(
                {
                    "stat": "OK",
                    "tables": [{"data": [["113/02/05", "1", "too short"]]}],
                }
            ),
        ]
        expected = pd.DataFrame({"Close": [12.0]})
        latest = Mock(return_value=expected)
        finalize = Mock()

        actual, _, finalize, latest = self._download_monthly(
            responses=responses,
            finalize=finalize,
            latest=latest,
        )

        self.assertIs(actual, expected)
        finalize.assert_not_called()
        latest.assert_called_once_with("6488", "2mo", self.start)

    def test_monthly_http_error_propagates_before_json_or_latest_fallback(self) -> None:
        response = _Response({}, error=RuntimeError("monthly http failure"))
        finalize = Mock()
        latest = Mock()

        with self.assertRaisesRegex(RuntimeError, "^monthly http failure$"):
            self._download_monthly(
                responses=[response],
                months=[self.months[0]],
                finalize=finalize,
                latest=latest,
            )

        self.assertEqual(response.raise_calls, 1)
        self.assertEqual(response.json_calls, 0)
        finalize.assert_not_called()
        latest.assert_not_called()

    def test_non_daily_interval_is_rejected_before_any_dependency(self) -> None:
        dependencies = {
            "period_start": Mock(),
            "month_starts": Mock(),
            "parse_tpex_date": Mock(),
            "to_float": Mock(),
            "to_int": Mock(),
            "finalize_official_rows": Mock(),
            "download_latest_quote": Mock(),
        }

        with patch.object(tpex_provider.requests, "get") as request_get:
            with self.assertRaisesRegex(
                RuntimeError,
                "^TPEX fallback only supports 1d interval\\.$",
            ):
                tpex_provider.download_tpex_stock(
                    "6488",
                    "1mo",
                    "1wk",
                    error_type=RuntimeError,
                    **dependencies,
                )

        request_get.assert_not_called()
        for dependency in dependencies.values():
            dependency.assert_not_called()

    def test_latest_quote_request_matches_symbol_and_finalizes_exact_row(self) -> None:
        response = _Response(
            [
                {"SecuritiesCompanyCode": "9999"},
                {
                    "SecuritiesCompanyCode": " 6488 ",
                    "Date": "1130103",
                    "Open": "10",
                    "High": "12",
                    "Low": "9",
                    "Close": "11",
                    "TradingShares": "1,234",
                },
            ]
        )
        expected = pd.DataFrame({"Close": [11.0]})
        finalize = Mock(return_value=expected)

        with patch.object(
            tpex_provider.requests,
            "get",
            return_value=response,
        ) as request_get:
            actual = tpex_provider.download_tpex_latest_quote(
                "6488",
                "1mo",
                self.start,
                parse_tpex_date=_parse_tpex,
                to_float=official_parsing.to_float,
                to_int=_to_int,
                finalize_official_rows=finalize,
                error_type=RuntimeError,
            )

        self.assertIs(actual, expected)
        request_get.assert_called_once_with(
            "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        finalize.assert_called_once_with(
            [
                {
                    "Date": pd.Timestamp("2024-01-03"),
                    "Open": 10.0,
                    "High": 12.0,
                    "Low": 9.0,
                    "Close": 11.0,
                    "Volume": 1234,
                }
            ],
            "6488",
            ".TWO",
            self.start,
            "1mo",
        )

    def test_latest_quote_no_match_raises_exact_error(self) -> None:
        response = _Response([{"SecuritiesCompanyCode": "9999"}])
        with patch.object(tpex_provider.requests, "get", return_value=response):
            with self.assertRaisesRegex(
                RuntimeError,
                "^TPEX fallback has no data: 6488\\.TWO$",
            ):
                tpex_provider.download_tpex_latest_quote(
                    "6488",
                    "1mo",
                    self.start,
                    parse_tpex_date=_parse_tpex,
                    to_float=official_parsing.to_float,
                    to_int=_to_int,
                    finalize_official_rows=Mock(),
                    error_type=RuntimeError,
                )

    def test_latest_quote_http_error_propagates_before_json_and_finalization(self) -> None:
        response = _Response({}, error=RuntimeError("latest http failure"))
        finalize = Mock()
        with patch.object(tpex_provider.requests, "get", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "^latest http failure$"):
                tpex_provider.download_tpex_latest_quote(
                    "6488",
                    "1mo",
                    self.start,
                    parse_tpex_date=_parse_tpex,
                    to_float=official_parsing.to_float,
                    to_int=_to_int,
                    finalize_official_rows=finalize,
                    error_type=RuntimeError,
                )

        self.assertEqual(response.raise_calls, 1)
        self.assertEqual(response.json_calls, 0)
        finalize.assert_not_called()


if __name__ == "__main__":
    unittest.main()
