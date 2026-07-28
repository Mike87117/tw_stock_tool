"""Tests for Research Run per-run market-data context boundary."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event
import unittest
from unittest.mock import Mock

import pandas as pd

from tw_stock_tool.research_run import (
    DataSourceRecord,
    MarketDataLoadResult,
    ResearchRunContext,
    ResearchRunContextError,
)
import tw_stock_tool.research_run as research_run_pkg


class _StringSubclass(str):
    pass


def _make_sample_df() -> pd.DataFrame:
    return pd.DataFrame({"Close": [100.0, 101.0]})


def _make_source_record(
    canonical_symbol: str = "2330.TW",
    requested_symbol: str = "2330",
    provider: str = "yfinance",
    period: str = "1y",
    interval: str = "1d",
    auto_adjust: bool = True,
    source_kind: str = "live",
    cache_state: str = "not_applicable",
    success: bool = True,
    error: str | None = None,
) -> DataSourceRecord:
    return DataSourceRecord(
        canonical_symbol=canonical_symbol,
        requested_symbol=requested_symbol,
        provider=provider,
        period=period,
        interval=interval,
        auto_adjust=auto_adjust,
        source_kind=source_kind,
        cache_state=cache_state,
        success=success,
        error=error,
    )


class TestResearchRunContext(unittest.TestCase):
    # A. MarketDataLoadResult: 6 tests

    def test_market_data_load_result_accepts_live_dataframe(self) -> None:
        df = _make_sample_df()
        rec = _make_source_record(source_kind="live", cache_state="not_applicable")
        res = MarketDataLoadResult(data=df, source_record=rec, error=None)
        self.assertIs(res.data, df)
        self.assertEqual(res.source_record, rec)
        self.assertIsNone(res.error)

    def test_market_data_load_result_accepts_fresh_cache_dataframe(self) -> None:
        df = _make_sample_df()
        rec = _make_source_record(source_kind="cache", cache_state="fresh")
        res = MarketDataLoadResult(data=df, source_record=rec, error=None)
        self.assertIs(res.data, df)
        self.assertEqual(res.source_record.cache_state, "fresh")

    def test_market_data_load_result_accepts_stale_cache_dataframe(self) -> None:
        df = _make_sample_df()
        rec = _make_source_record(source_kind="cache", cache_state="stale")
        res = MarketDataLoadResult(data=df, source_record=rec, error=None)
        self.assertIs(res.data, df)
        self.assertEqual(res.source_record.cache_state, "stale")

    def test_market_data_load_result_accepts_expected_failure(self) -> None:
        exc = RuntimeError("network error")
        rec = _make_source_record(success=False, error="network error")
        res = MarketDataLoadResult(data=None, source_record=rec, error=exc)
        self.assertIsNone(res.data)
        self.assertEqual(res.source_record, rec)
        self.assertIs(res.error, exc)

    def test_market_data_load_result_rejects_invalid_success_shape(self) -> None:
        rec = _make_source_record(success=True)

        with self.assertRaises(ResearchRunContextError):
            MarketDataLoadResult(data=None, source_record=rec, error=None)

        with self.assertRaises(ResearchRunContextError):
            MarketDataLoadResult(data="not_df", source_record=rec, error=None)  # type: ignore[arg-type]

        with self.assertRaises(ResearchRunContextError):
            MarketDataLoadResult(
                data=_make_sample_df(),
                source_record=rec,
                error=RuntimeError("err"),
            )

    def test_market_data_load_result_rejects_invalid_failure_shape(self) -> None:
        rec = _make_source_record(success=False, error="err")

        with self.assertRaises(ResearchRunContextError):
            MarketDataLoadResult(
                data=_make_sample_df(),
                source_record=rec,
                error=RuntimeError("err"),
            )

        with self.assertRaises(ResearchRunContextError):
            MarketDataLoadResult(data=None, source_record=rec, error=None)

        with self.assertRaises(ResearchRunContextError):
            MarketDataLoadResult(data=None, source_record=rec, error="not_an_exception")  # type: ignore[arg-type]

    # B. Context initialization and input validation: 6 tests

    def test_research_run_context_accepts_callable_loader(self) -> None:
        loader = Mock()
        ctx = ResearchRunContext(loader)
        self.assertEqual(ctx.data_sources, ())
        self.assertEqual(ctx.resolved_keys, ())

    def test_research_run_context_rejects_non_callable_loader(self) -> None:
        for bad_loader in ["not_a_callable", 123, None, []]:
            with self.assertRaises(ResearchRunContextError):
                ResearchRunContext(bad_loader)  # type: ignore[arg-type]

    def test_load_market_data_validates_canonical_symbol(self) -> None:
        ctx = ResearchRunContext(Mock())

        for bad_sym in ["", " 2330.TW ", "2330.TW ", 123, _StringSubclass("2330.TW")]:
            with self.assertRaises(ResearchRunContextError):
                ctx.load_market_data(
                    canonical_symbol=bad_sym,  # type: ignore[arg-type]
                    requested_symbol="2330",
                    period="1y",
                    interval="1d",
                    auto_adjust=True,
                    force_refresh=False,
                )

    def test_load_market_data_validates_requested_symbol(self) -> None:
        ctx = ResearchRunContext(Mock())

        for bad_sym in ["", " 2330 ", "2330 ", 123, _StringSubclass("2330")]:
            with self.assertRaises(ResearchRunContextError):
                ctx.load_market_data(
                    canonical_symbol="2330.TW",
                    requested_symbol=bad_sym,  # type: ignore[arg-type]
                    period="1y",
                    interval="1d",
                    auto_adjust=True,
                    force_refresh=False,
                )

    def test_load_market_data_validates_period_and_interval(self) -> None:
        ctx = ResearchRunContext(Mock())

        for bad_str in ["", " 1y ", 123, _StringSubclass("1y")]:
            with self.assertRaises(ResearchRunContextError):
                ctx.load_market_data(
                    canonical_symbol="2330.TW",
                    requested_symbol="2330",
                    period=bad_str,  # type: ignore[arg-type]
                    interval="1d",
                    auto_adjust=True,
                    force_refresh=False,
                )

            with self.assertRaises(ResearchRunContextError):
                ctx.load_market_data(
                    canonical_symbol="2330.TW",
                    requested_symbol="2330",
                    period="1y",
                    interval=bad_str,  # type: ignore[arg-type]
                    auto_adjust=True,
                    force_refresh=False,
                )

    def test_load_market_data_requires_exact_booleans_and_key(self) -> None:
        ctx = ResearchRunContext(Mock())

        for bad_bool in [1, 0, "True", 1.0, None]:
            with self.assertRaises(ResearchRunContextError):
                ctx.load_market_data(
                    canonical_symbol="2330.TW",
                    requested_symbol="2330",
                    period="1y",
                    interval="1d",
                    auto_adjust=bad_bool,  # type: ignore[arg-type]
                    force_refresh=False,
                )

            with self.assertRaises(ResearchRunContextError):
                ctx.load_market_data(
                    canonical_symbol="2330.TW",
                    requested_symbol="2330",
                    period="1y",
                    interval="1d",
                    auto_adjust=True,
                    force_refresh=bad_bool,  # type: ignore[arg-type]
                )

    # C. Sequential dedup: 10 tests

    def test_same_key_loads_only_once_sequentially(self) -> None:
        df = _make_sample_df()
        loader = Mock(
            return_value=MarketDataLoadResult(
                data=df,
                source_record=_make_source_record(),
            )
        )
        ctx = ResearchRunContext(loader)

        res1 = ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )
        res2 = ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )

        self.assertIs(res1, df)
        self.assertIs(res2, df)
        loader.assert_called_once()

    def test_same_key_returns_same_dataframe_identity(self) -> None:
        df = _make_sample_df()
        loader = Mock(
            return_value=MarketDataLoadResult(
                data=df,
                source_record=_make_source_record(),
            )
        )
        ctx = ResearchRunContext(loader)

        df1 = ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )
        df2 = ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )

        self.assertIs(df1, df)
        self.assertIs(df2, df1)

    def test_requested_symbol_is_not_part_of_dedup_key(self) -> None:
        df = _make_sample_df()
        loader = Mock(
            return_value=MarketDataLoadResult(
                data=df,
                source_record=_make_source_record(requested_symbol="2330"),
            )
        )
        ctx = ResearchRunContext(loader)

        df1 = ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )
        df2 = ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330.TW",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )

        self.assertIs(df1, df2)
        loader.assert_called_once()
        self.assertEqual(ctx.data_sources[0].requested_symbol, "2330")

    def test_different_canonical_symbol_loads_separately(self) -> None:
        df1 = _make_sample_df()
        df2 = _make_sample_df()

        def loader(
            requested_symbol: str,
            period: str,
            interval: str,
            auto_adjust: bool,
            force_refresh: bool,
        ) -> MarketDataLoadResult:
            if requested_symbol == "2330":
                return MarketDataLoadResult(
                    data=df1,
                    source_record=_make_source_record(
                        canonical_symbol="2330.TW", requested_symbol="2330"
                    ),
                )
            return MarketDataLoadResult(
                data=df2,
                source_record=_make_source_record(
                    canonical_symbol="2317.TW", requested_symbol="2317"
                ),
            )

        ctx = ResearchRunContext(loader)
        res1 = ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )
        res2 = ctx.load_market_data(
            canonical_symbol="2317.TW",
            requested_symbol="2317",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )

        self.assertIs(res1, df1)
        self.assertIs(res2, df2)
        self.assertEqual(len(ctx.data_sources), 2)

    def test_different_period_loads_separately(self) -> None:
        calls = []

        def loader(
            requested_symbol: str,
            period: str,
            interval: str,
            auto_adjust: bool,
            force_refresh: bool,
        ) -> MarketDataLoadResult:
            calls.append(period)
            return MarketDataLoadResult(
                data=_make_sample_df(),
                source_record=_make_source_record(period=period),
            )

        ctx = ResearchRunContext(loader)
        ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )
        ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="6m",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )

        self.assertEqual(calls, ["1y", "6m"])

    def test_different_interval_loads_separately(self) -> None:
        calls = []

        def loader(
            requested_symbol: str,
            period: str,
            interval: str,
            auto_adjust: bool,
            force_refresh: bool,
        ) -> MarketDataLoadResult:
            calls.append(interval)
            return MarketDataLoadResult(
                data=_make_sample_df(),
                source_record=_make_source_record(interval=interval),
            )

        ctx = ResearchRunContext(loader)
        ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )
        ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1wk",
            auto_adjust=True,
            force_refresh=False,
        )

        self.assertEqual(calls, ["1d", "1wk"])

    def test_different_auto_adjust_loads_separately(self) -> None:
        calls = []

        def loader(
            requested_symbol: str,
            period: str,
            interval: str,
            auto_adjust: bool,
            force_refresh: bool,
        ) -> MarketDataLoadResult:
            calls.append(auto_adjust)
            return MarketDataLoadResult(
                data=_make_sample_df(),
                source_record=_make_source_record(auto_adjust=auto_adjust),
            )

        ctx = ResearchRunContext(loader)
        ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )
        ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=False,
            force_refresh=False,
        )

        self.assertEqual(calls, [True, False])

    def test_different_force_refresh_loads_separately(self) -> None:
        calls = []

        def loader(
            requested_symbol: str,
            period: str,
            interval: str,
            auto_adjust: bool,
            force_refresh: bool,
        ) -> MarketDataLoadResult:
            calls.append(force_refresh)
            return MarketDataLoadResult(
                data=_make_sample_df(),
                source_record=_make_source_record(),
            )

        ctx = ResearchRunContext(loader)
        ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )
        ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=True,
        )

        self.assertEqual(calls, [False, True])

    def test_separate_contexts_do_not_share_cache(self) -> None:
        calls = []

        def loader(
            requested_symbol: str,
            period: str,
            interval: str,
            auto_adjust: bool,
            force_refresh: bool,
        ) -> MarketDataLoadResult:
            calls.append(1)
            return MarketDataLoadResult(
                data=_make_sample_df(),
                source_record=_make_source_record(),
            )

        ctx1 = ResearchRunContext(loader)
        ctx2 = ResearchRunContext(loader)

        kwargs = {
            "canonical_symbol": "2330.TW",
            "requested_symbol": "2330",
            "period": "1y",
            "interval": "1d",
            "auto_adjust": True,
            "force_refresh": False,
        }

        df1 = ctx1.load_market_data(**kwargs)
        df2 = ctx2.load_market_data(**kwargs)

        self.assertIsNot(df1, df2)
        self.assertEqual(len(calls), 2)

    def test_loader_receives_exact_resolved_arguments(self) -> None:
        loader = Mock(
            return_value=MarketDataLoadResult(
                data=_make_sample_df(),
                source_record=_make_source_record(),
            )
        )
        ctx = ResearchRunContext(loader)

        ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )

        loader.assert_called_once_with("2330", "1y", "1d", True, False)

    # D. DataSourceRecord collection: 6 tests

    def test_live_source_record_is_collected(self) -> None:
        rec = _make_source_record(source_kind="live", cache_state="not_applicable")
        loader = Mock(return_value=MarketDataLoadResult(data=_make_sample_df(), source_record=rec))
        ctx = ResearchRunContext(loader)

        ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )

        self.assertEqual(ctx.data_sources, (rec,))
        self.assertEqual(ctx.resolved_keys, (("2330.TW", "1y", "1d", True, False),))

    def test_fresh_cache_source_record_is_collected(self) -> None:
        rec = _make_source_record(source_kind="cache", cache_state="fresh")
        loader = Mock(return_value=MarketDataLoadResult(data=_make_sample_df(), source_record=rec))
        ctx = ResearchRunContext(loader)

        ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )

        self.assertEqual(ctx.data_sources, (rec,))

    def test_stale_cache_source_record_is_collected(self) -> None:
        rec = _make_source_record(source_kind="cache", cache_state="stale")
        loader = Mock(return_value=MarketDataLoadResult(data=_make_sample_df(), source_record=rec))
        ctx = ResearchRunContext(loader)

        ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )

        self.assertEqual(ctx.data_sources, (rec,))

    def test_expected_failure_source_record_is_collected(self) -> None:
        rec = _make_source_record(success=False, error="network failure")
        exc = RuntimeError("network failure")
        loader = Mock(return_value=MarketDataLoadResult(data=None, source_record=rec, error=exc))
        ctx = ResearchRunContext(loader)

        with self.assertRaises(RuntimeError):
            ctx.load_market_data(
                canonical_symbol="2330.TW",
                requested_symbol="2330",
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
            )

        self.assertEqual(ctx.data_sources, (rec,))
        self.assertEqual(ctx.resolved_keys, (("2330.TW", "1y", "1d", True, False),))

    def test_deduplicated_request_records_source_once(self) -> None:
        rec = _make_source_record()
        loader = Mock(return_value=MarketDataLoadResult(data=_make_sample_df(), source_record=rec))
        ctx = ResearchRunContext(loader)

        for _ in range(3):
            ctx.load_market_data(
                canonical_symbol="2330.TW",
                requested_symbol="2330",
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
            )

        self.assertEqual(len(ctx.data_sources), 1)

    def test_data_sources_and_resolved_keys_follow_first_request_order(self) -> None:
        df_a = _make_sample_df()
        df_b = _make_sample_df()
        rec_a = _make_source_record(canonical_symbol="2330.TW", requested_symbol="2330")
        rec_b = _make_source_record(canonical_symbol="2317.TW", requested_symbol="2317")
        key_a = ("2330.TW", "1y", "1d", True, False)
        key_b = ("2317.TW", "1y", "1d", True, False)

        key_a_entered = Event()
        key_b_entered = Event()
        release_key_b = Event()
        release_key_a = Event()
        key_b_finished = Event()

        def loader(
            requested_symbol: str,
            period: str,
            interval: str,
            auto_adjust: bool,
            force_refresh: bool,
        ) -> MarketDataLoadResult:
            if requested_symbol == "2330":
                key_a_entered.set()
                self.assertTrue(release_key_a.wait(timeout=5.0))
                return MarketDataLoadResult(data=df_a, source_record=rec_a)

            key_b_entered.set()
            self.assertTrue(release_key_b.wait(timeout=5.0))
            res_b = MarketDataLoadResult(data=df_b, source_record=rec_b)
            key_b_finished.set()
            return res_b

        ctx = ResearchRunContext(loader)

        def load_a() -> pd.DataFrame:
            return ctx.load_market_data(
                canonical_symbol="2330.TW",
                requested_symbol="2330",
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
            )

        def load_b() -> pd.DataFrame:
            return ctx.load_market_data(
                canonical_symbol="2317.TW",
                requested_symbol="2317",
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            # 1. Key A becomes owner first
            fut_a = pool.submit(load_a)
            self.assertTrue(key_a_entered.wait(timeout=5.0))

            # 2. Key B becomes owner second
            fut_b = pool.submit(load_b)
            self.assertTrue(key_b_entered.wait(timeout=5.0))

            # 3. Key B is deliberately allowed to complete first
            release_key_b.set()
            self.assertTrue(key_b_finished.wait(timeout=5.0))
            self.assertIs(fut_b.result(), df_b)

            # 4. Key A completes afterward
            release_key_a.set()
            self.assertIs(fut_a.result(), df_a)

        # Assert ordering follows first owner request order (A then B)
        self.assertEqual(ctx.resolved_keys, (key_a, key_b))
        self.assertEqual(ctx.data_sources, (rec_a, rec_b))

    # E. Validation, failure, and concurrency: 7 tests

    def test_context_rejects_mismatched_source_record_metadata(self) -> None:
        valid_df = _make_sample_df()
        valid_rec = _make_source_record(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
        )

        mismatched_records = [
            _make_source_record(canonical_symbol="WRONG.TW", requested_symbol="2330", period="1y", interval="1d", auto_adjust=True),
            _make_source_record(canonical_symbol="2330.TW", requested_symbol="WRONG", period="1y", interval="1d", auto_adjust=True),
            _make_source_record(canonical_symbol="2330.TW", requested_symbol="2330", period="6m", interval="1d", auto_adjust=True),
            _make_source_record(canonical_symbol="2330.TW", requested_symbol="2330", period="1y", interval="1wk", auto_adjust=True),
            _make_source_record(canonical_symbol="2330.TW", requested_symbol="2330", period="1y", interval="1d", auto_adjust=False),
        ]

        # Repair 1A: Prove retry after each metadata mismatch field
        for bad_rec in mismatched_records:
            calls = 0

            def loader(
                requested_symbol: str,
                period: str,
                interval: str,
                auto_adjust: bool,
                force_refresh: bool,
            ) -> MarketDataLoadResult:
                nonlocal calls
                calls += 1
                if calls == 1:
                    return MarketDataLoadResult(data=valid_df, source_record=bad_rec)
                return MarketDataLoadResult(data=valid_df, source_record=valid_rec)

            ctx = ResearchRunContext(loader)

            with self.assertRaises(ResearchRunContextError):
                ctx.load_market_data(
                    canonical_symbol="2330.TW",
                    requested_symbol="2330",
                    period="1y",
                    interval="1d",
                    auto_adjust=True,
                    force_refresh=False,
                )

            self.assertEqual(ctx.data_sources, ())
            self.assertEqual(ctx.resolved_keys, ())

            res_df = ctx.load_market_data(
                canonical_symbol="2330.TW",
                requested_symbol="2330",
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
            )
            self.assertIs(res_df, valid_df)

            self.assertEqual(calls, 2)
            self.assertEqual(ctx.data_sources, (valid_rec,))
            self.assertEqual(
                ctx.resolved_keys, (("2330.TW", "1y", "1d", True, False),)
            )

        # Repair 1B: Prove retry after invalid loader return types
        invalid_returns = ["not_a_result", 123, None, []]
        for bad_ret in invalid_returns:
            calls = 0

            def bad_type_loader(
                requested_symbol: str,
                period: str,
                interval: str,
                auto_adjust: bool,
                force_refresh: bool,
            ) -> MarketDataLoadResult:
                nonlocal calls
                calls += 1
                if calls == 1:
                    return bad_ret  # type: ignore[return-value]
                return MarketDataLoadResult(data=valid_df, source_record=valid_rec)

            ctx = ResearchRunContext(bad_type_loader)

            with self.assertRaises(ResearchRunContextError):
                ctx.load_market_data(
                    canonical_symbol="2330.TW",
                    requested_symbol="2330",
                    period="1y",
                    interval="1d",
                    auto_adjust=True,
                    force_refresh=False,
                )

            self.assertEqual(ctx.data_sources, ())
            self.assertEqual(ctx.resolved_keys, ())

            res_df = ctx.load_market_data(
                canonical_symbol="2330.TW",
                requested_symbol="2330",
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
            )
            self.assertIs(res_df, valid_df)
            self.assertEqual(calls, 2)
            self.assertEqual(ctx.data_sources, (valid_rec,))
            self.assertEqual(
                ctx.resolved_keys, (("2330.TW", "1y", "1d", True, False),)
            )

    def test_unexpected_loader_exception_is_propagated_and_not_cached(self) -> None:
        exc = ValueError("unexpected exception")
        calls = 0

        def loader(
            requested_symbol: str,
            period: str,
            interval: str,
            auto_adjust: bool,
            force_refresh: bool,
        ) -> MarketDataLoadResult:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise exc
            return MarketDataLoadResult(
                data=_make_sample_df(),
                source_record=_make_source_record(),
            )

        ctx = ResearchRunContext(loader)

        with self.assertRaises(ValueError) as err_ctx:
            ctx.load_market_data(
                canonical_symbol="2330.TW",
                requested_symbol="2330",
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
            )
        self.assertIs(err_ctx.exception, exc)
        self.assertEqual(ctx.data_sources, ())
        self.assertEqual(ctx.resolved_keys, ())

        # Retry succeeds
        df_ok = ctx.load_market_data(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
        )
        self.assertIsNotNone(df_ok)
        self.assertEqual(len(ctx.data_sources), 1)

    def test_expected_failure_is_cached_and_reused(self) -> None:
        exc = KeyError("expected missing stock")
        rec = _make_source_record(success=False, error="expected missing stock")
        loader = Mock(return_value=MarketDataLoadResult(data=None, source_record=rec, error=exc))
        ctx = ResearchRunContext(loader)

        for _ in range(2):
            with self.assertRaises(KeyError) as err_ctx:
                ctx.load_market_data(
                    canonical_symbol="2330.TW",
                    requested_symbol="2330",
                    period="1y",
                    interval="1d",
                    auto_adjust=True,
                    force_refresh=False,
                )
            self.assertIs(err_ctx.exception, exc)

        loader.assert_called_once()
        self.assertEqual(ctx.data_sources, (rec,))

    def test_concurrent_same_key_is_single_flight_and_shares_identity(self) -> None:
        num_callers = 5
        df = _make_sample_df()
        loader_calls = 0

        owner_inside_loader = Event()
        release_loader = Event()

        def loader(
            requested_symbol: str,
            period: str,
            interval: str,
            auto_adjust: bool,
            force_refresh: bool,
        ) -> MarketDataLoadResult:
            nonlocal loader_calls
            loader_calls += 1
            owner_inside_loader.set()
            self.assertTrue(release_loader.wait(timeout=5.0))
            return MarketDataLoadResult(
                data=df,
                source_record=_make_source_record(),
            )

        ctx = ResearchRunContext(loader)

        def worker_owner() -> pd.DataFrame:
            return ctx.load_market_data(
                canonical_symbol="2330.TW",
                requested_symbol="2330",
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
            )

        def worker_follower() -> pd.DataFrame:
            return ctx.load_market_data(
                canonical_symbol="2330.TW",
                requested_symbol="2330",
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
            )

        with ThreadPoolExecutor(max_workers=num_callers) as pool:
            # Submit owner worker
            fut_owner = pool.submit(worker_owner)

            # Wait until owner thread is inside blocked loader
            self.assertTrue(owner_inside_loader.wait(timeout=5.0))

            # Submit followers while owner is blocked inside loader
            futs_followers = [pool.submit(worker_follower) for _ in range(num_callers - 1)]

            # Release loader only after all followers have been submitted
            release_loader.set()

            all_futures = [fut_owner] + futs_followers
            results = [f.result(timeout=5.0) for f in all_futures]

        self.assertEqual(loader_calls, 1)
        for res in results:
            self.assertIs(res, df)

        self.assertEqual(len(ctx.data_sources), 1)
        self.assertEqual(len(ctx.resolved_keys), 1)

    def test_concurrent_expected_failure_is_single_flight(self) -> None:
        num_callers = 5
        exc = RuntimeError("concurrent failure")
        rec = _make_source_record(success=False, error="concurrent failure")
        loader_calls = 0

        owner_inside_loader = Event()
        release_loader = Event()

        def loader(
            requested_symbol: str,
            period: str,
            interval: str,
            auto_adjust: bool,
            force_refresh: bool,
        ) -> MarketDataLoadResult:
            nonlocal loader_calls
            loader_calls += 1
            owner_inside_loader.set()
            self.assertTrue(release_loader.wait(timeout=5.0))
            return MarketDataLoadResult(data=None, source_record=rec, error=exc)

        ctx = ResearchRunContext(loader)

        def worker_owner() -> Exception:
            try:
                ctx.load_market_data(
                    canonical_symbol="2330.TW",
                    requested_symbol="2330",
                    period="1y",
                    interval="1d",
                    auto_adjust=True,
                    force_refresh=False,
                )
            except RuntimeError as e:
                return e
            raise AssertionError("expected exception")

        def worker_follower() -> Exception:
            try:
                ctx.load_market_data(
                    canonical_symbol="2330.TW",
                    requested_symbol="2330",
                    period="1y",
                    interval="1d",
                    auto_adjust=True,
                    force_refresh=False,
                )
            except RuntimeError as e:
                return e
            raise AssertionError("expected exception")

        with ThreadPoolExecutor(max_workers=num_callers) as pool:
            fut_owner = pool.submit(worker_owner)
            self.assertTrue(owner_inside_loader.wait(timeout=5.0))

            futs_followers = [pool.submit(worker_follower) for _ in range(num_callers - 1)]

            release_loader.set()

            all_futures = [fut_owner] + futs_followers
            results = [f.result(timeout=5.0) for f in all_futures]

        self.assertEqual(loader_calls, 1)
        for res in results:
            self.assertIs(res, exc)

        self.assertEqual(ctx.data_sources, (rec,))
        self.assertEqual(ctx.resolved_keys, (("2330.TW", "1y", "1d", True, False),))

    def test_different_keys_can_load_concurrently(self) -> None:
        event_a_started = Event()
        event_b_started = Event()
        release_all = Event()

        def loader(
            requested_symbol: str,
            period: str,
            interval: str,
            auto_adjust: bool,
            force_refresh: bool,
        ) -> MarketDataLoadResult:
            if requested_symbol == "2330":
                event_a_started.set()
            elif requested_symbol == "2317":
                event_b_started.set()
            release_all.wait()
            return MarketDataLoadResult(
                data=_make_sample_df(),
                source_record=_make_source_record(
                    canonical_symbol=f"{requested_symbol}.TW",
                    requested_symbol=requested_symbol,
                ),
            )

        ctx = ResearchRunContext(loader)

        def load_a() -> pd.DataFrame:
            return ctx.load_market_data(
                canonical_symbol="2330.TW",
                requested_symbol="2330",
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
            )

        def load_b() -> pd.DataFrame:
            return ctx.load_market_data(
                canonical_symbol="2317.TW",
                requested_symbol="2317",
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_a = pool.submit(load_a)
            self.assertTrue(event_a_started.wait(timeout=2.0))

            fut_b = pool.submit(load_b)
            self.assertTrue(event_b_started.wait(timeout=2.0))

            release_all.set()
            res_a = fut_a.result()
            res_b = fut_b.result()

        self.assertIsNotNone(res_a)
        self.assertIsNotNone(res_b)

    def test_recursive_same_key_load_is_rejected(self) -> None:
        ctx: ResearchRunContext | None = None

        def loader(
            requested_symbol: str,
            period: str,
            interval: str,
            auto_adjust: bool,
            force_refresh: bool,
        ) -> MarketDataLoadResult:
            assert ctx is not None
            ctx.load_market_data(
                canonical_symbol="2330.TW",
                requested_symbol="2330",
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
            )
            return MarketDataLoadResult(
                data=_make_sample_df(),
                source_record=_make_source_record(),
            )

        ctx = ResearchRunContext(loader)

        with self.assertRaises(ResearchRunContextError) as err_ctx:
            ctx.load_market_data(
                canonical_symbol="2330.TW",
                requested_symbol="2330",
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
            )
        self.assertIn("recursive", str(err_ctx.exception).lower())

    # F. Public exports: 1 test

    def test_research_run_package_exports_context_boundary(self) -> None:
        expected_context_exports = {
            "MarketDataKey",
            "MarketDataLoadResult",
            "ResearchRunContext",
            "ResearchRunContextError",
        }
        expected_model_exports = {
            "RUN_MANIFEST_SCHEMA_VERSION",
            "ArtifactReference",
            "CacheState",
            "DataSourceRecord",
            "ResearchRunModelError",
            "ResearchRunResult",
            "RunConfig",
            "RunManifest",
            "RunStatus",
            "SourceKind",
        }
        expected_serialization_exports = {
            "ResearchRunSerializationError",
            "deserialize_run_manifest",
            "export_run_manifest_json",
            "load_run_manifest_json",
            "serialize_run_manifest",
        }

        actual_exports = set(research_run_pkg.__all__)

        self.assertTrue(expected_context_exports.issubset(actual_exports))
        self.assertTrue(expected_model_exports.issubset(actual_exports))
        self.assertTrue(expected_serialization_exports.issubset(actual_exports))

        for name in expected_context_exports:
            self.assertTrue(hasattr(research_run_pkg, name))

        self.assertNotIn("_require_clean_string", actual_exports)
        self.assertNotIn("_require_exact_bool", actual_exports)


if __name__ == "__main__":
    unittest.main()
