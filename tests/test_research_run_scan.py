from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from tw_stock_tool.analysis import analysis as analysis_module
from tw_stock_tool.analysis.analysis import StockAnalysis, build_stock_analysis
from tw_stock_tool.analysis.scanner import ScanConfig
from tw_stock_tool.research_run import (
    DataSourceRecord,
    MarketDataLoadResult,
    ScanResearchRunError,
    load_run_manifest_json,
    run_scan_research,
)
from tw_stock_tool.research_run import market_data_adapter as adapter
from tw_stock_tool.research_run import scan as scan_module


def _df() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=130, freq="D")
    close = pd.Series(range(100, 230), index=index, dtype=float)
    return pd.DataFrame(
        {"Open": close - 1, "High": close + 2, "Low": close - 2, "Close": close, "Volume": 1000.0},
        index=index,
    )


def _analysis(stock_id: str, symbol: str | None = None) -> StockAnalysis:
    latest = pd.Series(
        {"Signal": "BUY", "Score": 5.0, "Close": 100.0, "MA5": 99.0, "MA20": 98.0, "MA60": 97.0,
         "RSI": 55.0, "MACD": 1.2, "MACD_Signal": 1.0, "K": 60.0, "D": 50.0, "BB_Upper": 110.0,
         "BB_Middle": 100.0, "BB_Lower": 90.0, "ATR": 2.0, "OBV": 10.0, "Volume_Ratio": 1.2,
         "Bullish_Stack": True, "MACD_Bull": True, "Volume_Burst": False, "Breakout_Upper": False,
         "Bearish_Stack": False, "Death_Cross": False, "MACD_Weak": False, "RSI_Hot": False,
         "Breakdown_Lower": False, "RSI_Cold": False}, name=pd.Timestamp("2024-05-09"))
    return StockAnalysis(stock_id, symbol or f"{stock_id}.TW", pd.DataFrame(), pd.DataFrame(), pd.DataFrame([latest]), latest, {"Analysis": "ok"})


def _record(requested: str, canonical: str, *, auto_adjust: bool = True, success: bool = True, provider: str = "yfinance", source_kind: str = "live", cache_state: str = "not_applicable", error: str | None = None) -> DataSourceRecord:
    return DataSourceRecord(canonical, requested, provider, "1y", "1d", auto_adjust, source_kind, cache_state, success, error)


def _loader(pairs: tuple[tuple[str, str], ...], failed: set[str] | None = None):
    failed = failed or set()
    frames = {requested: _df() for requested, _ in pairs}
    canonical = dict(pairs)

    def load(requested: str, period: str, interval: str, auto_adjust: bool, force_refresh: bool) -> MarketDataLoadResult:
        if requested in failed:
            error = ValueError(f"bad {requested}")
            return MarketDataLoadResult(None, _record(requested, canonical[requested], success=False, provider="data_loader", auto_adjust=auto_adjust, error=str(error)), error)
        return MarketDataLoadResult(frames[requested], _record(requested, canonical[requested], auto_adjust=auto_adjust))

    return load


class AnalysisBoundaryTests(unittest.TestCase):
    def test_build_stock_analysis_success(self):
        result = build_stock_analysis(stock_id="2330", symbol="2330.TW", raw_df=_df())
        self.assertEqual((result.stock_id, result.symbol), ("2330", "2330.TW"))
        self.assertFalse(result.signal_df.empty)

    def test_build_stock_analysis_preserves_raw_identity(self):
        raw = _df()
        self.assertIs(build_stock_analysis(stock_id="2330", symbol="2330.TW", raw_df=raw).raw_df, raw)

    def test_build_stock_analysis_does_not_mutate_input(self):
        raw = _df()
        before = raw.copy(deep=True)
        build_stock_analysis(stock_id="2330", symbol="2330.TW", raw_df=raw)
        pd.testing.assert_frame_equal(raw, before)

    def test_build_stock_analysis_preserves_insufficient_data_error(self):
        with self.assertRaises(Exception):
            build_stock_analysis(stock_id="2330", symbol="2330.TW", raw_df=_df().head(10))

    def test_analyze_stock_delegates_to_legacy_loader_once(self):
        raw = _df()
        expected = _analysis("2330", "2330.TW")
        with patch.object(analysis_module, "download_tw_stock", return_value=(raw, "2330.TW")) as loader, patch.object(analysis_module, "build_stock_analysis", return_value=expected) as boundary:
            self.assertIs(analysis_module.analyze_stock("2330"), expected)
        loader.assert_called_once()
        boundary.assert_called_once_with(stock_id="2330", symbol="2330.TW", raw_df=raw)


class AdapterTests(unittest.TestCase):
    def _configured(self, *, cache_fresh=False, cache_df=None, yf=None, official=None, candidates=None, cache_path=None, write=None, age=1.0):
        path = cache_path or Path("cache.csv")
        values = {
            "_validate_inputs": lambda *args: None,
            "_symbol_candidates": candidates or (lambda stock: [(f"{stock}.TW", stock, ".TW")]),
            "_cache_path": lambda *args: path,
            "_is_cache_fresh": lambda p: cache_fresh,
            "_read_cache": lambda p: cache_df if cache_df is not None else _df(),
            "_prepare_ohlcv": lambda frame, symbol: frame,
            "_download_yfinance_quiet": yf or (lambda *args: _df()),
            "_write_cache": write or (lambda *args: None),
            "_download_official_stock": official or (lambda *args: _df()),
            "_get_cache_age_days": lambda p: age,
            "_format_no_data_error": lambda *args: ValueError("no data"),
        }
        return patch.multiple(adapter.data_loader, **values)

    def test_fresh_cache_provenance(self):
        with self._configured(cache_fresh=True):
            result = adapter.build_legacy_market_data_loader({"2330": "2330.TW"})("2330", "1y", "1d", True, False)
        self.assertEqual((result.source_record.provider, result.source_record.cache_state), ("cache", "fresh"))

    def test_yahoo_live_provenance(self):
        with self._configured(cache_fresh=False):
            result = adapter.build_legacy_market_data_loader({"2330": "2330.TW"})("2330", "1y", "1d", True, False)
        self.assertEqual((result.source_record.provider, result.source_record.source_kind), ("yfinance", "live"))

    def test_twse_live_provenance(self):
        with self._configured(yf=Mock(side_effect=ValueError("down"))):
            result = adapter.build_legacy_market_data_loader({"2330": "2330.TW"})("2330", "1y", "1d", False, False)
        self.assertEqual(result.source_record.provider, "twse")

    def test_tpex_live_provenance(self):
        def official(base, suffix, period, interval):
            if suffix == ".TW":
                raise ValueError("twse down")
            return _df()
        with self._configured(yf=Mock(side_effect=ValueError("down")), official=official, candidates=lambda stock: [("2330.TW", stock, ".TW"), ("2330.TWO", stock, ".TWO")]):
            result = adapter.build_legacy_market_data_loader({"2330": "2330.TWO"})("2330", "1y", "1d", False, False)
        self.assertEqual(result.source_record.provider, "tpex")

    def test_stale_cache_provenance(self):
        with TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache.csv"
            cache.write_text("x", encoding="utf-8")
            with self._configured(cache_fresh=False, cache_path=cache, yf=Mock(side_effect=ValueError("down"))):
                result = adapter.build_legacy_market_data_loader({"2330": "2330.TW"})("2330", "1y", "1d", True, False)
        self.assertEqual((result.source_record.provider, result.source_record.cache_state), ("cache", "stale"))

    def test_force_refresh_bypasses_fresh_cache(self):
        fresh = Mock(side_effect=AssertionError("fresh cache must not be checked"))
        with self._configured(yf=Mock(return_value=_df())):
            with patch.object(adapter.data_loader, "_is_cache_fresh", fresh):
                result = adapter.build_legacy_market_data_loader({"2330": "2330.TW"})("2330", "1y", "1d", True, True)
        self.assertEqual(result.source_record.provider, "yfinance")
        fresh.assert_not_called()
    def test_expected_loader_failure_shape(self):
        with self._configured(yf=Mock(side_effect=ValueError("bad"))):
            result = adapter.build_legacy_market_data_loader({"2330": "2330.TW"})("2330", "1y", "1d", True, True)
        self.assertIsNone(result.data)
        self.assertFalse(result.source_record.success)
        self.assertIsInstance(result.error, ValueError)

    def test_failure_preserves_exception_identity(self):
        exc = ValueError("bad")
        with patch.object(adapter.fallback_orchestration, "download_tw_stock", side_effect=exc):
            result = adapter.build_legacy_market_data_loader({"2330": "2330.TW"})("2330", "1y", "1d", True, True)
        self.assertIs(result.error, exc)
    def test_failure_uses_expected_canonical_symbol(self):
        with self._configured(yf=Mock(side_effect=ValueError("bad"))):
            result = adapter.build_legacy_market_data_loader({"2330": "EXPECTED.TW"})("2330", "1y", "1d", True, True)
        self.assertEqual(result.source_record.canonical_symbol, "EXPECTED.TW")

    def test_loader_arguments_and_actual_success_symbol(self):
        yf = Mock(return_value=_df())
        with self._configured(yf=yf, candidates=lambda stock: [("ACTUAL.TW", stock, ".TW")]):
            result = adapter.build_legacy_market_data_loader({"2330": "ACTUAL.TW"})("2330", "6m", "1wk", False, True)
        self.assertEqual(result.source_record.canonical_symbol, "ACTUAL.TW")
        yf.assert_called_once_with("ACTUAL.TW", "6m", "1wk", False)

    def test_cache_write_failure_keeps_live_success(self):
        with self._configured(write=Mock(side_effect=OSError("disk"))):
            result = adapter.build_legacy_market_data_loader({"2330": "2330.TW"})("2330", "1y", "1d", True, False)
        self.assertTrue(result.source_record.success)
        self.assertIsNotNone(result.data)

    def test_failed_fresh_read_then_stale_success_is_stale(self):
        with TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache.csv"
            cache.write_text("x", encoding="utf-8")
            first = True

            def read(path):
                nonlocal first
                if first:
                    first = False
                    raise OSError("fresh read")
                return _df()

            with self._configured(cache_fresh=True, cache_path=cache, yf=Mock(side_effect=ValueError("down"))):
                with patch.object(adapter.data_loader, "_read_cache", side_effect=read):
                    result = adapter.build_legacy_market_data_loader({"2330": "2330.TW"})("2330", "1y", "1d", True, False)
        self.assertEqual(result.source_record.cache_state, "stale")

class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.config = ScanConfig(max_workers=1)
        self.loader = _loader((("2330", "2330.TW"),))

    def run_valid(self, **kwargs):
        options = dict(universe="tw", config=self.config, output_dir=TemporaryDirectory().name, market_data_loader=self.loader)
        options.update(kwargs)
        return options

    def test_valid_pairs_produce_expected_run_config(self):
        with patch.object(scan_module.importlib.metadata, "version", return_value="9.9.9") as metadata, patch.object(scan_module, "_source_tree_tool_version", return_value="0.4.0") as fallback:
            with TemporaryDirectory() as tmp:
                result = run_scan_research((("2330", "2330.TW"),), universe="tw", config=self.config, output_dir=tmp, market_data_loader=self.loader)
        self.assertEqual(result.manifest.config.workflow, "scan")
        self.assertEqual(result.manifest.config.canonical_symbols, ("2330.TW",))
        self.assertNotIn("analysis_provider", result.manifest.config.workflow_options)
        self.assertEqual(result.manifest.tool_version, "9.9.9")
        metadata.assert_called_once_with("tw-stock-tool")
        fallback.assert_not_called()

        with patch.object(scan_module.importlib.metadata, "version", side_effect=scan_module.importlib.metadata.PackageNotFoundError), patch.object(scan_module, "_source_tree_tool_version", return_value="0.4.0") as fallback:
            with TemporaryDirectory() as tmp:
                result = run_scan_research((("2330", "2330.TW"),), universe="tw", config=self.config, output_dir=tmp, market_data_loader=self.loader)
        self.assertEqual(result.manifest.tool_version, "0.4.0")
        fallback.assert_called_once_with()
    def test_symbol_requests_must_be_exact_tuple(self):
        with self.assertRaises(ScanResearchRunError):
            run_scan_research([("2330", "2330.TW")], **self.run_valid())

    def test_each_pair_must_be_exact_two_item_tuple(self):
        with self.assertRaises(ScanResearchRunError):
            run_scan_research((("2330",),), **self.run_valid())

    def test_dirty_blank_and_subclass_values_rejected(self):
        class S(str): pass
        for pairs in (((" 2330", "2330.TW"),), (("2330", ""),), ((S("2330"), "2330.TW"),)):
            with self.subTest(pairs=pairs), self.assertRaises(ScanResearchRunError):
                run_scan_research(pairs, **self.run_valid())

    def test_duplicate_requested_symbols_rejected(self):
        with self.assertRaises(ScanResearchRunError):
            run_scan_research((("2330", "2330.TW"), ("2330", "2317.TW")), **self.run_valid())

    def test_duplicate_canonical_symbols_rejected(self):
        with self.assertRaises(ScanResearchRunError):
            run_scan_research((("2330", "2330.TW"), ("2317", "2330.TW")), **self.run_valid())

    def test_caller_analysis_provider_rejected(self):
        with self.assertRaises(ScanResearchRunError):
            run_scan_research((("2330", "2330.TW"),), universe="tw", config=ScanConfig(analysis_provider=lambda _: _analysis("2330")), output_dir=TemporaryDirectory().name, market_data_loader=self.loader)

    def test_invalid_universe_boolean_callback_loader_or_path_rejected(self):
        cases = [dict(universe=" tw"), dict(sheet_by_signal=1), dict(log_errors=0), dict(progress_callback=1), dict(market_data_loader=1), dict(output_dir="   ")]
        for case in cases:
            options = dict(universe="tw", config=self.config, output_dir=TemporaryDirectory().name, market_data_loader=self.loader)
            options.update(case)
            with self.subTest(case=case), self.assertRaises(ScanResearchRunError):
                run_scan_research((("2330", "2330.TW"),), **options)


class OutcomeTests(unittest.TestCase):
    def run_scan(self, pairs, failed=None, **kwargs):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config_keys = {"period", "interval", "auto_adjust", "force_refresh", "max_workers", "min_score", "min_volume_ratio", "min_close", "max_close", "signals", "sort_by", "top", "errors_only"}
        config_kwargs = {key: value for key, value in kwargs.items() if key in config_keys}
        run_kwargs = {key: value for key, value in kwargs.items() if key in {"sheet_by_signal", "log_errors", "progress_callback"}}
        return run_scan_research(pairs, universe="tw", config=ScanConfig(max_workers=1, **config_kwargs), output_dir=tmp.name, market_data_loader=_loader(pairs, failed), **run_kwargs)
    def test_all_success_manifest_and_counts(self):
        result = self.run_scan((("2330", "2330.TW"), ("2317", "2317.TW")))
        self.assertEqual((result.manifest.status, result.manifest.success_count, result.manifest.failure_count), ("success", 2, 0))

    def test_mixed_partial_manifest_and_counts(self):
        result = self.run_scan((("2330", "2330.TW"), ("2317", "2317.TW")), {"2317"})
        self.assertEqual((result.manifest.status, result.manifest.success_count, result.manifest.failure_count), ("partial", 1, 1))
        self.assertEqual(result.manifest.errors, ("2317: bad 2317",))

    def test_all_failure_manifest_and_counts(self):
        result = self.run_scan((("2330", "2330.TW"),), {"2330"})
        self.assertEqual((result.manifest.status, result.manifest.success_count, result.manifest.failure_count), ("failure", 0, 1))

    def test_filtered_success_still_counts(self):
        result = self.run_scan((("2330", "2330.TW"),), min_score=99)
        self.assertEqual(result.manifest.success_count, 1)
        self.assertTrue(result.manifest.limitations)

    def test_top_omitted_success_still_counts(self):
        result = self.run_scan((("2330", "2330.TW"), ("2317", "2317.TW")), top=1)
        self.assertEqual(result.manifest.success_count, 2)

    def test_errors_only_preserves_success_count(self):
        result = self.run_scan((("2330", "2330.TW"), ("2317", "2317.TW")), {"2317"}, errors_only=True)
        self.assertEqual(result.manifest.success_count, 1)

    def test_data_sources_follow_context_owner_order(self):
        pairs = (("2330", "2330.TW"), ("2317", "2317.TW"))
        result = self.run_scan(pairs)
        self.assertEqual(result.manifest.data_sources, tuple(result.manifest.data_sources))
        self.assertEqual([r.requested_symbol for r in result.manifest.data_sources], ["2330", "2317"])

    def test_external_progress_receives_exact_values(self):
        progress = []
        pairs = (("2330", "2330.TW"),)
        with TemporaryDirectory() as tmp:
            run_scan_research(pairs, universe="tw", config=ScanConfig(max_workers=1), output_dir=tmp, market_data_loader=_loader(pairs), progress_callback=lambda *args: progress.append(args))
        self.assertEqual(progress, [(1, 1, "2330", "OK")])

    def test_domain_result_preserves_scanner_identity(self):
        ranking = pd.DataFrame([{"Status": "OK", "Stock": "2330", "Error": ""}])
        def fake_scan(stocks, config, progress_callback):
            progress_callback(1, 1, "2330", "OK")
            return ranking
        with TemporaryDirectory() as tmp, patch.object(scan_module, "scan_stocks", side_effect=fake_scan), patch.object(scan_module, "export_stock_ranking", return_value={"excel": Path(tmp) / "a.xlsx", "csv": Path(tmp) / "a.csv", "html": Path(tmp) / "a.html"}):
            result = run_scan_research((("2330", "2330.TW"),), universe="tw", config=ScanConfig(), output_dir=tmp, market_data_loader=_loader((("2330", "2330.TW"),)))
        self.assertIs(result.domain_result, ranking)

    def test_artifact_references_have_exact_order_and_types(self):
        result = self.run_scan((("2330", "2330.TW"),))
        self.assertEqual([a.artifact_type for a in result.manifest.artifacts], ["scan_ranking_excel", "scan_ranking_csv", "scan_ranking_html"])
        self.assertEqual([a.media_type for a in result.manifest.artifacts], ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "text/csv", "text/html"])
        self.assertTrue(all("\\" not in a.path for a in result.manifest.artifacts))

    def test_optional_error_log_content_and_omission(self):
        result = self.run_scan((("2330", "2330.TW"),), {"2330"}, log_errors=True)
        log = Path(next(a.path for a in result.manifest.artifacts if a.artifact_type == "scan_error_log"))
        self.assertEqual(log.read_text(encoding="utf-8"), "2330: bad 2330\n")
        result2 = self.run_scan((("2330", "2330.TW"),), log_errors=False)
        self.assertNotIn("scan_error_log", [a.artifact_type for a in result2.manifest.artifacts])

        pairs = (("2330", "2330.TW"), ("2317", "2317.TW"))
        with TemporaryDirectory() as tmp, patch.object(scan_module, "_write_error_log", side_effect=OSError("cannot write error log")):
            with self.assertRaises(ScanResearchRunError):
                run_scan_research(pairs, universe="tw", config=ScanConfig(max_workers=1), output_dir=tmp, market_data_loader=_loader(pairs, {"2317"}), log_errors=True)
            manifest = load_run_manifest_json(Path(tmp, "scan_run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest.status, "partial")
        self.assertEqual((manifest.success_count, manifest.failure_count, manifest.partial_count), (1, 1, 1))
        self.assertIn("error_log: cannot write error log", manifest.errors)
        self.assertEqual([artifact.artifact_type for artifact in manifest.artifacts], ["scan_ranking_excel", "scan_ranking_csv", "scan_ranking_html"])
        self.assertNotIn("scan_error_log", [artifact.artifact_type for artifact in manifest.artifacts])

class PersistenceAndBoundaryTests(unittest.TestCase):
    def test_manifest_round_trip(self):
        with TemporaryDirectory() as tmp:
            result = run_scan_research((("2330", "2330.TW"),), universe="tw", config=ScanConfig(), output_dir=tmp, market_data_loader=_loader((("2330", "2330.TW"),)))
            loaded = load_run_manifest_json(Path(tmp, "scan_run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(loaded, result.manifest)

    def test_default_manifest_filename_utf8_and_single_newline(self):
        with TemporaryDirectory() as tmp:
            run_scan_research((("2330", "2330.TW"),), universe="tw", config=ScanConfig(), output_dir=tmp, market_data_loader=_loader((("2330", "2330.TW"),)))
            raw = Path(tmp, "scan_run_manifest.json").read_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        self.assertFalse(raw.endswith(b"\n\n"))
        self.assertNotIn(b"\r\n", raw)

    def test_ranking_export_failure_persists_and_raises(self):
        with TemporaryDirectory() as tmp, patch.object(scan_module, "export_stock_ranking", side_effect=RuntimeError("export down")):
            with self.assertRaises(ScanResearchRunError):
                run_scan_research((("2330", "2330.TW"),), universe="tw", config=ScanConfig(), output_dir=tmp, market_data_loader=_loader((("2330", "2330.TW"),)))
            manifest = load_run_manifest_json(Path(tmp, "scan_run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest.status, "partial")
        self.assertIn("ranking_export: export down", manifest.errors)

    def test_unexpected_scanner_failure_persists_and_raises(self):
        with TemporaryDirectory() as tmp, patch.object(scan_module, "scan_stocks", side_effect=RuntimeError("scan down")):
            with self.assertRaises(ScanResearchRunError):
                run_scan_research((("2330", "2330.TW"),), universe="tw", config=ScanConfig(), output_dir=tmp, market_data_loader=_loader((("2330", "2330.TW"),)))
            manifest = load_run_manifest_json(Path(tmp, "scan_run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest.errors, ("scan: scan down",))

    def test_manifest_write_failure_is_propagated(self):
        with TemporaryDirectory() as tmp, patch.object(scan_module, "_write_manifest", side_effect=OSError("cannot write")):
            with self.assertRaises(ScanResearchRunError) as raised:
                run_scan_research((("2330", "2330.TW"),), universe="tw", config=ScanConfig(), output_dir=tmp, market_data_loader=_loader((("2330", "2330.TW"),)))
        self.assertIn("manifest: cannot write", str(raised.exception))

    def test_public_exports_include_only_new_boundary_items(self):
        import tw_stock_tool.research_run as package
        self.assertIn("ScanResearchRunError", package.__all__)
        self.assertIn("run_scan_research", package.__all__)
        self.assertNotIn("build_legacy_market_data_loader", package.__all__)


if __name__ == "__main__":
    unittest.main()