from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

import pandas as pd

from tw_stock_tool.reports.daily_pipeline import DailyPipelineConfig, DailyPipelineResult
from tw_stock_tool.research_run import (
    DailyReportResearchRunError,
    DataSourceRecord,
    MarketDataLoadResult,
    load_run_manifest_json,
    run_daily_report_research,
)
from tw_stock_tool.research_run import daily as daily_module


def _df(rows=None):
    return pd.DataFrame(rows or [])


def _report(summary=None, date="2026-07-29"):
    return {
        "Report Metadata": {"Date": date, "Type": "Daily Research Report"},
        "Run Configuration": {},
        "Pipeline Run Summary": summary or {},
        "Report Highlights": [],
        "Data Quality Notes": [],
        "Universe Summary": {"Total Stocks": 1, "Universe": ["2330"]},
        "Screening Summary": [],
        "Watchlist Candidates": [],
        "Backtest Highlights": [],
        "Parameter Sweep Highlights": [],
        "Walk Forward Highlights": [],
        "Risk Notes": [],
        "Data Limitations": [],
        "Next Research Actions": [],
    }


def _result(summary=None, ranking=None, backtest=None, sweep=None, walk=None, limitations=None):
    return DailyPipelineResult(
        summary_df=_df([{"Report Date": "2026-07-29"}]),
        candidates_df=_df([{"Stock": "2330"}]),
        ranking_df=ranking if ranking is not None else _df(),
        backtest_highlights=backtest if backtest is not None else _df(),
        parameter_sweep_highlights=sweep if sweep is not None else _df(),
        walk_forward_highlights=walk if walk is not None else _df(),
        risk_notes=[],
        data_limitations=limitations or [],
        report_data=_report(summary),
        markdown="# report",
    )


def _loader(calls):
    def load(requested, period, interval, auto_adjust, force_refresh):
        calls.append((requested, period, interval, auto_adjust, force_refresh))
        record = DataSourceRecord(
            requested + ".TW", requested, "fake", period, interval, auto_adjust,
            "live", "not_applicable", True, None,
        )
        return MarketDataLoadResult(pd.DataFrame({"Close": [100.0]}), record)
    return load


def _run(tmp, loader, **kwargs):
    config = kwargs.pop("config", DailyPipelineConfig(progress=False))
    output_dir = kwargs.pop("output_dir", tmp)
    market_data_loader = kwargs.pop("market_data_loader", loader)
    return run_daily_report_research(
        (("2330", "2330.TW"),),
        universe="twse",
        config=config,
        output_dir=output_dir,
        market_data_loader=market_data_loader,
        **kwargs,
    )


class ValidationTests(TestCase):
    def test_symbol_requests_are_exact_nonempty_unique_clean_tuples(self):
        cases = (
            [], ((["2330", "2330.TW"],),), (["2330", "2330.TW"],),
            ((" 2330", "2330.TW"),), (("2330", "2330.TW"), ("2330", "x")),
            (("2330", "2330.TW"), ("2317", "2330.TW")),
        )
        for value in cases:
            with self.subTest(value=value), TemporaryDirectory() as tmp:
                with self.assertRaises(DailyReportResearchRunError):
                    run_daily_report_research(
                        value, universe=None, config=DailyPipelineConfig(),
                        output_dir=tmp, market_data_loader=_loader([]),
                    )

    def test_invalid_boundary_inputs_do_not_load_or_write_manifest(self):
        cases = (
            {"json_overwrite": 1},
            {"status_callback": 1},
            {"market_data_loader": 1},
            {"output_dir": ""},
            {"markdown_path": ""},
            {"json_path": ""},
            {"manifest_path": ""},
        )
        for kwargs in cases:
            calls = []
            with self.subTest(kwargs=kwargs), TemporaryDirectory() as tmp:
                call_kwargs = dict(kwargs)
                call_kwargs.setdefault("output_dir", tmp)
                call_kwargs.setdefault("market_data_loader", _loader(calls))
                with self.assertRaises(DailyReportResearchRunError):
                    run_daily_report_research(
                        (("2330", "2330.TW"),), universe=None,
                        config=DailyPipelineConfig(), **call_kwargs,
                    )
                self.assertFalse(Path(tmp, "daily_report_run_manifest.json").exists())
            self.assertEqual(calls, [])

    def test_invalid_period_and_config_are_rejected(self):
        for config in (DailyPipelineConfig(period="invalid"), DailyPipelineConfig(interval="2h")):
            with TemporaryDirectory() as tmp:
                with self.assertRaises(DailyReportResearchRunError):
                    _run(tmp, _loader([]), config=config)

    def test_empty_report_date_is_preserved(self):
        result = _result()
        result.report_data["Report Metadata"]["Date"] = ""
        with patch.object(daily_module, "run_daily_research_pipeline", return_value=result),              patch.object(daily_module, "export_daily_report_markdown_file", return_value=Path("daily_report.md")):
            with TemporaryDirectory() as tmp:
                _run(tmp, _loader([]), config=DailyPipelineConfig(report_date=""))
        self.assertEqual(result.report_data["Report Metadata"]["Date"], "")

    def test_resolved_config_contains_all_snapshots_and_does_not_mutate_caller(self):
        config = DailyPipelineConfig(
            validate_top=2, validation_initial_capital=200000,
            parameter_sweep_top=1, walk_forward_top=1,
            walk_forward_train_days=10, walk_forward_test_days=5,
            output_excel=None, report_date="2026-01-02", progress=False,
        )
        result = _result(summary={"Scan OK": 1})
        with patch.object(daily_module, "run_daily_research_pipeline", return_value=result),              patch.object(daily_module, "export_daily_report_markdown_file", return_value=Path("daily_report.md")):
            with TemporaryDirectory() as tmp:
                output = run_daily_report_research(
                    (("2330", "2330.TW"),), universe="twse", config=config,
                    output_dir=tmp, json_path=Path(tmp, "report.json"), market_data_loader=_loader([]),
                )
        self.assertEqual(config.report_date, "2026-01-02")
        self.assertEqual(output.manifest.config.workflow, "daily")
        self.assertEqual(output.manifest.config.backtest["initial_capital"], 200000)
        self.assertTrue(output.manifest.config.parameter_sweep["enabled"])
        self.assertEqual(output.manifest.config.walk_forward["step_days"], 5)
        options = output.manifest.config.workflow_options
        self.assertEqual(options["signals"], ("BUY", "WATCH"))
        self.assertEqual(options["json_path"], Path(tmp, "report.json").as_posix())
        self.assertIsNone(options["excel_path"])

    def test_pipeline_order_callback_and_shared_context(self):
        calls = []
        result = _result(summary={"Scan OK": 1})
        captured = {}

        def pipeline(symbols, config, *, analysis_provider, status_callback):
            captured["symbols"] = symbols
            captured["config"] = config
            captured["provider"] = analysis_provider
            status_callback("event")
            analysis_provider("2330")
            analysis_provider("2330")
            return result

        with patch.object(daily_module, "build_stock_analysis", return_value=Mock()),              patch.object(daily_module, "run_daily_research_pipeline", side_effect=pipeline),              patch.object(daily_module, "export_daily_report_markdown_file", return_value=Path("daily_report.md")):
            with TemporaryDirectory() as tmp:
                output = run_daily_report_research(
                    (("2330", "2330.TW"),), universe=None,
                    config=DailyPipelineConfig(report_date="2026-01-02"),
                    output_dir=tmp, status_callback=captured.setdefault("events", []).append,
                    market_data_loader=_loader(calls),
                )
        self.assertEqual(captured["symbols"], ["2330"])
        self.assertEqual(captured["config"].report_date, "2026-01-02")
        self.assertEqual(captured["events"], ["event"])
        self.assertEqual(len(calls), 1)
        self.assertIs(output.domain_result, result)
        self.assertEqual(len(output.manifest.data_sources), 1)

    def test_report_date_none_uses_one_resolved_value(self):
        result = _result()
        captured = {}

        def pipeline(symbols, config, **kwargs):
            captured["date"] = config.report_date
            return result

        with patch.object(daily_module, "datetime") as clock,              patch.object(daily_module, "_created_at", return_value="2026-07-29T00:00:00Z"),              patch.object(daily_module, "run_daily_research_pipeline", side_effect=pipeline),              patch.object(daily_module, "export_daily_report_markdown_file", return_value=Path("daily_report.md")):
            clock.now.return_value.strftime.return_value = "2026-07-29"
            with TemporaryDirectory() as tmp:
                output = _run(tmp, _loader([]))
        self.assertEqual(captured["date"], "2026-07-29")
        self.assertEqual(output.manifest.config.workflow_options["report_date"], "2026-07-29")

    def test_counts_statuses_errors_and_limitations_are_deterministic(self):
        result = _result(
            summary={"Scan OK": 1, "Scan Failed": 1, "Backtest Failed": 1,
                     "Parameter Sweep Partial": 1, "Walk Forward OK": 1},
            ranking=_df([{"Stock": "2330", "Status": "OK"},
                         {"Stock": "2317", "Status": "ERROR", "Error": "download failed"}]),
            backtest=_df([{"Stock": "2330", "Status": "ERROR", "Error": "backtest failed"}]),
            sweep=_df([{"Stock": "2330", "Status": "PARTIAL", "Error": None}]),
            limitations=["limit", "limit"],
        )
        with patch.object(daily_module, "run_daily_research_pipeline", return_value=result),              patch.object(daily_module, "export_daily_report_markdown_file", return_value=Path("daily_report.md")):
            with TemporaryDirectory() as tmp:
                output = _run(tmp, _loader([]))
        self.assertEqual(output.manifest.status, "partial")
        self.assertEqual((output.manifest.success_count, output.manifest.failure_count, output.manifest.partial_count), (2, 2, 1))
        self.assertEqual(output.manifest.errors, (
            "scan: 2317: download failed",
            "backtest: 2330: backtest failed",
            "parameter_sweep: 2330: PARTIAL",
        ))
        self.assertEqual(output.manifest.limitations, ("limit",))

    def test_zero_outcomes_are_failure_and_all_domain_failures_return(self):
        with patch.object(daily_module, "run_daily_research_pipeline", return_value=_result()),              patch.object(daily_module, "export_daily_report_markdown_file", return_value=Path("daily_report.md")):
            with TemporaryDirectory() as tmp:
                output = _run(tmp, _loader([]))
        self.assertEqual(output.manifest.status, "failure")
        self.assertEqual(output.manifest.errors, ("daily_pipeline: no stage outcomes recorded",))

        result = _result(summary={"Scan Failed": 1}, ranking=_df([{"Stock": "2330", "Status": "FAILED", "Error": "unavailable"}]))
        with patch.object(daily_module, "run_daily_research_pipeline", return_value=result),              patch.object(daily_module, "export_daily_report_markdown_file", return_value=Path("daily_report.md")):
            with TemporaryDirectory() as tmp:
                output = _run(tmp, _loader([]))
        self.assertEqual(output.manifest.status, "failure")
        self.assertEqual(output.manifest.errors, ("scan: 2330: unavailable",))

    def test_artifact_order_and_schema_version(self):
        result = _result(summary={"Scan OK": 1})
        order = []
        with patch.object(daily_module, "run_daily_research_pipeline", return_value=result),              patch.object(daily_module, "export_daily_report_markdown_file", side_effect=lambda *a, **k: order.append("md") or Path("daily_report.md")),              patch.object(daily_module, "export_daily_report_json_file", side_effect=lambda *a, **k: order.append("json") or Path("daily_report.json")),              patch.object(daily_module, "export_daily_report", side_effect=lambda *a, **k: order.append("excel") or Path("daily_report.xlsx")):
            with TemporaryDirectory() as tmp:
                output = run_daily_report_research(
                    (("2330", "2330.TW"),), universe=None,
                    config=DailyPipelineConfig(output_excel="report.xlsx"),
                    output_dir=tmp, json_path="report.json", market_data_loader=_loader([]),
                )
        self.assertEqual(order, ["md", "json", "excel"])
        self.assertEqual([a.artifact_type for a in output.manifest.artifacts], [
            "daily_report_markdown", "daily_report_json", "daily_report_excel",
        ])
        self.assertEqual(output.manifest.artifacts[1].schema_version, 1)

    def test_export_failures_continue_and_chain_first(self):
        result = _result(summary={"Scan OK": 1})
        markdown_error = ValueError("markdown failed")
        excel_error = ValueError("excel failed")
        with patch.object(daily_module, "run_daily_research_pipeline", return_value=result),              patch.object(daily_module, "export_daily_report_markdown_file", side_effect=markdown_error),              patch.object(daily_module, "export_daily_report_json_file", return_value=Path("report.json")),              patch.object(daily_module, "export_daily_report", side_effect=excel_error):
            with TemporaryDirectory() as tmp:
                with self.assertRaises(DailyReportResearchRunError) as raised:
                    run_daily_report_research(
                        (("2330", "2330.TW"),), universe=None,
                        config=DailyPipelineConfig(output_excel="report.xlsx"),
                        output_dir=tmp, json_path="report.json", market_data_loader=_loader([]),
                    )
                manifest = load_run_manifest_json(Path(tmp, "daily_report_run_manifest.json").read_text(encoding="utf-8"))
        self.assertIs(raised.exception.__cause__, markdown_error)
        self.assertEqual(manifest.status, "partial")
        self.assertEqual(manifest.errors, ("markdown_export: markdown failed", "excel_export: excel failed"))
        self.assertEqual([a.artifact_type for a in manifest.artifacts], ["daily_report_json"])

    def test_fatal_and_manifest_write_failures(self):
        original = RuntimeError("pipeline failed")
        with patch.object(daily_module, "run_daily_research_pipeline", side_effect=original):
            with TemporaryDirectory() as tmp:
                with self.assertRaises(DailyReportResearchRunError) as raised:
                    _run(tmp, _loader([]))
                manifest = load_run_manifest_json(Path(tmp, "daily_report_run_manifest.json").read_text(encoding="utf-8"))
        self.assertIs(raised.exception.__cause__, original)
        self.assertEqual(manifest.errors, ("daily_pipeline: pipeline failed",))

        result = _result(summary={"Scan OK": 1})
        with patch.object(daily_module, "run_daily_research_pipeline", return_value=result),              patch.object(daily_module, "export_daily_report_markdown_file", return_value=Path("daily_report.md")),              patch.object(daily_module, "_write_manifest", side_effect=OSError("disk full")):
            with TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(DailyReportResearchRunError, "manifest: disk full"):
                    _run(tmp, _loader([]))

    def test_manifest_round_trip_utf8_and_result_artifacts(self):
        result = _result(summary={"Scan OK": 1}, limitations=["資料受限"])
        with patch.object(daily_module, "run_daily_research_pipeline", return_value=result),              patch.object(daily_module, "export_daily_report_markdown_file", return_value=Path("daily_report.md")):
            with TemporaryDirectory() as tmp:
                output = _run(tmp, _loader([]))
                raw = Path(tmp, "daily_report_run_manifest.json").read_bytes()
                loaded = load_run_manifest_json(raw.decode("utf-8"))
        self.assertEqual(loaded, output.manifest)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertNotIn(b"\r\n", raw)
        self.assertEqual(output.generated_artifacts, output.manifest.artifacts)


if __name__ == "__main__":
    import unittest
    unittest.main()
