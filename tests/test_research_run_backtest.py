from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import math
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from tw_stock_tool.analysis.analysis import StockAnalysis
from tw_stock_tool.research_run import (
    BacktestResearchRunError,
    DataSourceRecord,
    MarketDataLoadResult,
    load_run_manifest_json,
    run_backtest_research,
)
from tw_stock_tool.research_run import backtest as backtest_module


def _df(periods: int = 130) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=periods, freq="D")
    close = pd.Series(range(100, 100 + periods), index=index, dtype=float)
    return pd.DataFrame(
        {
            "Open": close - 1,
            "High": close + 2,
            "Low": close - 2,
            "Close": close,
            "Volume": 1000.0,
        },
        index=index,
    )


def _loader(calls: list[tuple], *, error: Exception | None = None):
    frame = _df()

    def load(requested, period, interval, auto_adjust, force_refresh):
        calls.append((requested, period, interval, auto_adjust, force_refresh))
        if error is not None:
            record = DataSourceRecord(
                "2330.TW", requested, "fake", period, interval, auto_adjust,
                "live", "not_applicable", False, str(error) or type(error).__name__,
            )
            return MarketDataLoadResult(None, record, error)
        record = DataSourceRecord(
            "2330.TW", requested, "fake", period, interval, auto_adjust,
            "live", "not_applicable", True, None,
        )
        return MarketDataLoadResult(frame, record)

    return load


def _run(tmp: str, loader, **kwargs):
    return run_backtest_research(
        ("2330", "2330.TW"),
        strategy="ma_cross",
        output_dir=tmp,
        market_data_loader=loader,
        **kwargs,
    )


class ValidationTests(unittest.TestCase):
    def test_valid_pair_resolves_strategy_and_engine_defaults(self):
        calls = []
        with TemporaryDirectory() as tmp:
            result = _run(tmp, _loader(calls))
        config = result.manifest.config
        self.assertEqual(config.workflow, "backtest")
        self.assertEqual(config.strategy, "ma_cross_strategy")
        self.assertEqual(config.canonical_symbols, ("2330.TW",))
        self.assertEqual(config.backtest["interval"], "1d")
        self.assertEqual(config.backtest["initial_capital"], 100000)

    def test_symbol_request_must_be_exact_tuple(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(BacktestResearchRunError):
                run_backtest_research(["2330", "2330.TW"], strategy="ma_cross", output_dir=tmp)

    def test_symbol_request_must_have_two_items(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(BacktestResearchRunError):
                run_backtest_research(("2330",), strategy="ma_cross", output_dir=tmp)

    def test_dirty_blank_and_subclass_strings_are_rejected(self):
        class Symbol(str):
            pass

        cases = [(" 2330", "2330.TW"), ("2330", ""), (Symbol("2330"), "2330.TW")]
        for pair in cases:
            with TemporaryDirectory() as tmp, self.subTest(pair=pair):
                with self.assertRaises(BacktestResearchRunError):
                    run_backtest_research(pair, strategy="ma_cross", output_dir=tmp)

    def test_invalid_strategy_period_and_interval_are_rejected(self):
        for kwargs in ({"strategy": "missing"}, {"strategy": "ma_cross", "period": "2d"}, {"strategy": "ma_cross", "interval": "2h"}):
            with TemporaryDirectory() as tmp, self.subTest(kwargs=kwargs):
                with self.assertRaises(BacktestResearchRunError):
                    run_backtest_research(("2330", "2330.TW"), output_dir=tmp, **kwargs)

    def test_bool_subclasses_and_ints_are_rejected(self):
        class BoolInt(int):
            pass

        for value in (1, BoolInt(1)):
            with TemporaryDirectory() as tmp, self.subTest(value=value):
                with self.assertRaises(BacktestResearchRunError):
                    run_backtest_research(("2330", "2330.TW"), strategy="ma_cross", output_dir=tmp, auto_adjust=value)

    def test_non_json_safe_parameters_are_rejected_before_loader(self):
        bad_values = [float("nan"), float("inf"), Path("x"), {"x"}, pd.DataFrame()]
        for value in bad_values:
            calls = []
            with TemporaryDirectory() as tmp, self.subTest(value=type(value).__name__):
                with self.assertRaises(BacktestResearchRunError):
                    _run(tmp, _loader(calls), strategy_parameters={"bad": value})
            self.assertEqual(calls, [])

    def test_unknown_engine_parameter_and_interval_conflict_are_rejected(self):
        for params in ({"unknown": 1}, {"interval": "1wk"}):
            with TemporaryDirectory() as tmp, self.subTest(params=params):
                with self.assertRaises(BacktestResearchRunError):
                    _run(tmp, _loader([]), backtest_parameters=params)

    def test_output_paths_are_validated_before_loader(self):
        for name, value in (("output_dir", "   "), ("markdown_path", ""), ("excel_path", b"x")):
            calls = []
            with TemporaryDirectory() as tmp, self.subTest(name=name):
                kwargs = {name: value}
                if name == "output_dir":
                    kwargs["output_dir"] = value
                    with self.assertRaises(BacktestResearchRunError):
                        run_backtest_research(("2330", "2330.TW"), strategy="ma_cross", market_data_loader=_loader(calls), **kwargs)
                else:
                    with self.assertRaises(BacktestResearchRunError):
                        _run(tmp, _loader(calls), **kwargs)
            self.assertEqual(calls, [])

    def test_caller_parameter_mutation_does_not_change_manifest(self):
        strategy_parameters = {"short_window": 3, "long_window": 20}
        backtest_parameters = {"fee_rate": 0.01}
        with TemporaryDirectory() as tmp:
            result = _run(tmp, _loader([]), strategy_parameters=strategy_parameters, backtest_parameters=backtest_parameters)
        strategy_parameters["short_window"] = 99
        backtest_parameters["fee_rate"] = 0.9
        self.assertEqual(result.manifest.config.workflow_options["strategy_parameters"]["short_window"], 3)
        self.assertEqual(result.manifest.config.workflow_options["strategy_parameters"]["long_window"], 20)
        self.assertEqual(result.manifest.config.backtest["fee_rate"], 0.01)


class SuccessTests(unittest.TestCase):
    def test_real_strategy_and_backtest_use_fake_loader_and_record_provenance(self):
        calls = []
        with TemporaryDirectory() as tmp:
            result = _run(tmp, _loader(calls), strategy_parameters={"short_window": 3, "long_window": 10})
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], ("2330", "1y", "1d", False, False))
        self.assertEqual(result.manifest.status, "success")
        self.assertEqual((result.manifest.success_count, result.manifest.failure_count, result.manifest.partial_count), (1, 0, 0))
        self.assertEqual(result.manifest.data_sources[0].provider, "fake")
        self.assertEqual(result.domain_result["Stock"], "2330")
        self.assertEqual(result.domain_result["Strategy"], "ma_cross")
        self.assertEqual(result.domain_result["Parameters"]["strategy"]["short_window"], 3)

    def test_no_report_output_still_writes_success_manifest(self):
        with TemporaryDirectory() as tmp:
            result = _run(tmp, _loader([]))
            manifest_path = Path(tmp) / "backtest_run_manifest.json"
            self.assertTrue(manifest_path.exists())
        self.assertEqual(result.manifest.artifacts, ())

    def test_markdown_and_excel_are_independently_exported_in_order(self):
        with TemporaryDirectory() as tmp:
            markdown = Path(tmp) / "report.md"
            excel = Path(tmp) / "report.xlsx"
            with patch.object(backtest_module, "export_backtest_report_markdown", return_value=markdown) as md, patch.object(backtest_module, "export_backtest_report_excel", return_value=excel) as xlsx:
                result = _run(tmp, _loader([]), markdown_path=markdown, excel_path=excel)
        self.assertEqual([a.artifact_type for a in result.manifest.artifacts], ["backtest_report_markdown", "backtest_report_excel"])
        self.assertEqual([a.media_type for a in result.generated_artifacts], ["text/markdown", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"])
        self.assertEqual(result.generated_artifacts, result.manifest.artifacts)
        md.assert_called_once()
        xlsx.assert_called_once()

    def test_markdown_only_and_excel_only(self):
        for option, artifact_type in (("markdown_path", "backtest_report_markdown"), ("excel_path", "backtest_report_excel")):
            with TemporaryDirectory() as tmp, self.subTest(option=option):
                path = Path(tmp) / ("report.md" if option == "markdown_path" else "report.xlsx")
                with patch.object(backtest_module, "export_backtest_report_markdown", return_value=path), patch.object(backtest_module, "export_backtest_report_excel", return_value=path):
                    result = _run(tmp, _loader([]), **{option: path})
            self.assertEqual([a.artifact_type for a in result.manifest.artifacts], [artifact_type])

    def test_manifest_round_trip_and_utf8(self):
        with TemporaryDirectory() as tmp:
            result = _run(tmp, _loader([]))
            raw = Path(tmp, "backtest_run_manifest.json").read_bytes()
            loaded = load_run_manifest_json(raw.decode("utf-8"))
        self.assertEqual(loaded, result.manifest)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertNotIn(b"\r\n", raw)

    def test_tool_version_installed_and_source_fallback(self):
        with patch.object(backtest_module.importlib.metadata, "version", return_value="9.9.9") as version:
            with TemporaryDirectory() as tmp:
                result = _run(tmp, _loader([]))
        self.assertEqual(result.manifest.tool_version, "9.9.9")
        version.assert_called_once_with("tw-stock-tool")

        with patch.object(backtest_module.importlib.metadata, "version", side_effect=backtest_module.importlib.metadata.PackageNotFoundError), patch.object(backtest_module, "_source_tree_tool_version", return_value="0.4.0") as fallback:
            with TemporaryDirectory() as tmp:
                result = _run(tmp, _loader([]))
        self.assertEqual(result.manifest.tool_version, "0.4.0")
        fallback.assert_called_once_with()

    def test_analysis_receives_context_frame_strategy_and_backtest_are_resolved(self):
        raw = _df()
        analysis = StockAnalysis("2330", "2330.TW", raw, raw, raw, raw.iloc[-1], {})
        strategy_frame = raw.copy()
        strategy_frame["Signal"] = "HOLD"
        strategy_frame["entry_signal"] = False
        strategy_frame["exit_signal"] = False
        fake_strategy = Mock(return_value=strategy_frame)
        fake_result = {"Initial Capital": 100000}
        with TemporaryDirectory() as tmp:
            with patch.object(backtest_module, "build_stock_analysis", return_value=analysis) as build, patch.object(backtest_module, "STRATEGIES", {"ma_cross_strategy": fake_strategy}), patch.object(backtest_module, "run_backtest", return_value=fake_result) as run:
                result = _run(tmp, _loader([]), strategy_parameters={"short_window": 4, "long_window": 12}, backtest_parameters={"fee_rate": 0.02}, interval="1wk")
        build.assert_called_once()
        pd.testing.assert_frame_equal(build.call_args.kwargs["raw_df"], raw)
        fake_strategy.assert_called_once_with(raw, short_window=4, long_window=12)
        self.assertEqual(run.call_args.kwargs["interval"], "1wk")
        self.assertEqual(run.call_args.kwargs["fee_rate"], 0.02)
        self.assertEqual(result.domain_result["Start Date"], "2024-01-01")


class FailureTests(unittest.TestCase):
    def test_real_exporters_write_markdown_and_excel(self):
        with TemporaryDirectory() as tmp:
            markdown = Path(tmp) / "report.md"
            excel = Path(tmp) / "report.xlsx"
            result = _run(tmp, _loader([]), markdown_path=markdown, excel_path=excel)
            self.assertTrue(markdown.exists())
            self.assertTrue(excel.exists())
        self.assertEqual(
            [artifact.artifact_type for artifact in result.manifest.artifacts],
            ["backtest_report_markdown", "backtest_report_excel"],
        )

    def test_market_data_failure_writes_failure_manifest_and_preserves_cause(self):
        original = ValueError("資料失敗")
        with TemporaryDirectory() as tmp:
            with self.assertRaises(BacktestResearchRunError) as raised:
                _run(tmp, _loader([], error=original))
            manifest = load_run_manifest_json(Path(tmp, "backtest_run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest.status, "failure")
        self.assertEqual(manifest.errors, ("market_data: 資料失敗",))
        self.assertIs(raised.exception.__cause__, original)

    def test_analysis_strategy_and_backtest_failures_are_staged(self):
        cases = [("analysis", ValueError("分析失敗")), ("strategy", ValueError("策略失敗")), ("backtest", ValueError("回測失敗"))]
        for stage, error in cases:
            with TemporaryDirectory() as tmp, self.subTest(stage=stage):
                patches = []
                if stage == "analysis":
                    patches.append(patch.object(backtest_module, "build_stock_analysis", side_effect=error))
                elif stage == "strategy":
                    patches.append(patch.object(backtest_module, "STRATEGIES", {"ma_cross_strategy": Mock(side_effect=error)}))
                else:
                    patches.append(patch.object(backtest_module, "run_backtest", side_effect=error))
                with patches[0]:
                    with self.assertRaises(BacktestResearchRunError) as raised:
                        _run(tmp, _loader([]))
                manifest = load_run_manifest_json(Path(tmp, "backtest_run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest.errors, (f"{stage}: {error}",))
            self.assertIs(raised.exception.__cause__, error)

    def test_exporters_are_independent_and_successful_artifact_is_retained(self):
        with TemporaryDirectory() as tmp:
            md = Path(tmp) / "report.md"
            excel = Path(tmp) / "report.xlsx"
            with patch.object(backtest_module, "export_backtest_report_markdown", side_effect=ValueError("Markdown 錯誤")), patch.object(backtest_module, "export_backtest_report_excel", return_value=excel) as xlsx:
                with self.assertRaises(BacktestResearchRunError):
                    _run(tmp, _loader([]), markdown_path=md, excel_path=excel)
            manifest = load_run_manifest_json(Path(tmp, "backtest_run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest.status, "partial")
        self.assertEqual((manifest.success_count, manifest.failure_count, manifest.partial_count), (1, 0, 1))
        self.assertEqual([a.artifact_type for a in manifest.artifacts], ["backtest_report_excel"])
        self.assertEqual(manifest.errors, ("markdown_export: Markdown 錯誤",))
        xlsx.assert_called_once()

    def test_both_exporters_fail_and_all_errors_are_recorded(self):
        with TemporaryDirectory() as tmp:
            with patch.object(backtest_module, "export_backtest_report_markdown", side_effect=ValueError("md")), patch.object(backtest_module, "export_backtest_report_excel", side_effect=ValueError("xlsx")):
                with self.assertRaises(BacktestResearchRunError):
                    _run(tmp, _loader([]), markdown_path=Path(tmp) / "a.md", excel_path=Path(tmp) / "a.xlsx")
            manifest = load_run_manifest_json(Path(tmp, "backtest_run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest.errors, ("markdown_export: md", "excel_export: xlsx"))
        self.assertEqual(manifest.artifacts, ())

    def test_blank_exception_message_uses_exception_class(self):
        with TemporaryDirectory() as tmp:
            with patch.object(backtest_module, "run_backtest", side_effect=ValueError("")):
                with self.assertRaises(BacktestResearchRunError):
                    _run(tmp, _loader([]))
            manifest = load_run_manifest_json(Path(tmp, "backtest_run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest.errors, ("backtest: ValueError",))

    def test_manifest_write_failure_has_manifest_prefix(self):
        with TemporaryDirectory() as tmp:
            with patch.object(backtest_module, "_write_manifest", side_effect=OSError("磁碟失敗")):
                with self.assertRaises(BacktestResearchRunError) as raised:
                    _run(tmp, _loader([]))
        self.assertEqual(str(raised.exception), "manifest: 磁碟失敗")

    def test_manifest_write_failure_after_domain_failure_keeps_original_cause(self):
        original = ValueError("backtest down")
        with TemporaryDirectory() as tmp:
            with patch.object(backtest_module, "run_backtest", side_effect=original), patch.object(backtest_module, "_write_manifest", side_effect=OSError("cannot write")):
                with self.assertRaises(BacktestResearchRunError) as raised:
                    _run(tmp, _loader([]))
        self.assertEqual(str(raised.exception), "manifest: cannot write")
        self.assertIs(raised.exception.__cause__, original)


if __name__ == "__main__":
    unittest.main()
