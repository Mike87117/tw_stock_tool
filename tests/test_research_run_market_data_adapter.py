from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from tw_stock_tool.research_run import (
    DataSourceRecord,
    MarketDataLoadResult,
    ResearchRunContext,
    ResearchRunContextError,
)
from tw_stock_tool.research_run import market_data_adapter as adapter


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {"Open": [10.0], "High": [12.0], "Low": [9.0], "Close": [11.0], "Volume": [1000]},
        index=pd.date_range("2024-01-01", periods=1, freq="D"),
    )


def _record(
    canonical: str,
    requested: str,
    *,
    provider: str = "fake",
    source_kind: str = "live",
    cache_state: str = "not_applicable",
    success: bool = True,
    period: str = "1y",
    interval: str = "1d",
    auto_adjust: bool = True,
    error: str | None = None,
) -> DataSourceRecord:
    return DataSourceRecord(
        canonical,
        requested,
        provider,
        period,
        interval,
        auto_adjust,
        source_kind,
        cache_state,
        success,
        error,
    )


class MarketDataAdapterTests(unittest.TestCase):
    def test_resolved_canonical_is_passed_for_bare_and_explicit_requests(self):
        for requested, expected in (("2330", "2330.TW"), ("6488", "6488.TWO"), ("2330.TW", "2330.TW"), ("6488.TWO", "6488.TWO")):
            with self.subTest(requested=requested):
                with patch.object(
                    adapter.fallback_orchestration,
                    "download_tw_stock",
                    return_value=(_df(), expected),
                ) as download:
                    result = adapter.build_legacy_market_data_loader({requested: expected})(
                        requested, "1y", "1d", True, False
                    )
                self.assertEqual(download.call_args.args[0], expected)
                self.assertEqual(result.source_record.canonical_symbol, expected)

    def test_requested_provenance_and_actual_canonical_are_preserved(self):
        with patch.object(
            adapter.fallback_orchestration,
            "download_tw_stock",
            return_value=(_df(), "ACTUAL.TWO"),
        ):
            result = adapter.build_legacy_market_data_loader({"6488": "6488.TWO"})(
                "6488", "6m", "1wk", False, True
            )
        self.assertEqual(result.source_record.requested_symbol, "6488")
        self.assertEqual(result.source_record.canonical_symbol, "ACTUAL.TWO")
        self.assertEqual(
            (result.source_record.period, result.source_record.interval, result.source_record.auto_adjust),
            ("6m", "1wk", False),
        )

    def test_actual_canonical_mismatch_fails_through_context(self):
        loader = adapter.build_legacy_market_data_loader({"6488": "6488.TWO"})
        with patch.object(
            adapter.fallback_orchestration,
            "download_tw_stock",
            return_value=(_df(), "6488.TW"),
        ):
            result = loader("6488", "1y", "1d", True, False)
        self.assertEqual(result.source_record.canonical_symbol, "6488.TW")
        context = ResearchRunContext(lambda *args: result)
        with self.assertRaises(ResearchRunContextError):
            context.load_market_data(
                canonical_symbol="6488.TWO",
                requested_symbol="6488",
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
            )

    def test_failure_record_uses_expected_canonical_and_original_request(self):
        error = ValueError("down")
        with patch.object(adapter.fallback_orchestration, "download_tw_stock", side_effect=error):
            result = adapter.build_legacy_market_data_loader({"6488": "6488.TWO"})(
                "6488", "1y", "1d", True, False
            )
        self.assertIs(result.error, error)
        self.assertEqual(
            (result.source_record.requested_symbol, result.source_record.canonical_symbol),
            ("6488", "6488.TWO"),
        )
        self.assertFalse(result.source_record.success)

    def _actual_loader_result(
        self,
        expected: str,
        *,
        requested: str = "6488",
        auto_adjust: bool = True,
        force_refresh: bool = False,
        fresh: bool = False,
        stale: bool = False,
        yfinance: Mock | None = None,
        official: Mock | None = None,
    ) -> tuple[MarketDataLoadResult, Mock, Mock, Mock]:
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cache_path = Path(tmp.name) / "cache.csv"
        if stale:
            cache_path.write_text("cached", encoding="utf-8")
        base = expected.removesuffix(".TW").removesuffix(".TWO")
        suffix = ".TWO" if expected.endswith(".TWO") else ".TW"
        candidates = Mock(return_value=[(expected, base, suffix)])
        yfinance = yfinance or Mock(return_value=_df())
        official = official or Mock(return_value=_df())
        patches = patch.multiple(
            adapter.data_loader,
            _symbol_candidates=candidates,
            _cache_path=Mock(return_value=cache_path),
            _is_cache_fresh=Mock(return_value=fresh),
            _read_cache=Mock(return_value=_df()),
            _prepare_ohlcv=lambda frame, symbol: frame,
            _download_yfinance_quiet=yfinance,
            _write_cache=Mock(return_value=None),
            _download_official_stock=official,
            _get_cache_age_days=Mock(return_value=1.0),
            _format_no_data_error=Mock(side_effect=lambda *args: ValueError("no data")),
        )
        with patches:
            result = adapter.build_legacy_market_data_loader({requested: expected})(
                requested, "1y", "1d", auto_adjust, force_refresh
            )
        return result, candidates, yfinance, official

    def test_no_opposite_market_candidate_is_attempted(self):
        result, candidates, yfinance, _ = self._actual_loader_result("6488.TWO")
        self.assertTrue(result.source_record.success)
        candidates.assert_called_once_with("6488.TWO")
        yfinance.assert_called_once_with("6488.TWO", "1y", "1d", True)

    def test_yfinance_live_metadata_is_unchanged(self):
        result, _, _, _ = self._actual_loader_result("2330.TW", requested="2330")
        self.assertEqual(
            (result.source_record.provider, result.source_record.source_kind, result.source_record.cache_state),
            ("yfinance", "live", "not_applicable"),
        )

    def test_official_provider_metadata_is_unchanged(self):
        result, _, yfinance, official = self._actual_loader_result(
            "6488.TWO",
            auto_adjust=False,
            yfinance=Mock(side_effect=ValueError("down")),
        )
        self.assertTrue(result.source_record.success)
        self.assertEqual(result.source_record.provider, "tpex")
        yfinance.assert_called_once()
        official.assert_called_once_with("6488", ".TWO", "1y", "1d")

    def test_fresh_and_stale_cache_metadata_is_unchanged(self):
        fresh, _, yfinance, _ = self._actual_loader_result("2330.TW", fresh=True)
        self.assertEqual((fresh.source_record.provider, fresh.source_record.cache_state), ("cache", "fresh"))
        yfinance.assert_not_called()

        stale, _, yfinance, _ = self._actual_loader_result(
            "2330.TW",
            fresh=False,
            stale=True,
            yfinance=Mock(side_effect=ValueError("down")),
        )
        self.assertEqual((stale.source_record.provider, stale.source_record.cache_state), ("cache", "stale"))
        yfinance.assert_called_once()


if __name__ == "__main__":
    unittest.main()
