import copy
import json
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tw_stock_tool.reports import daily_pipeline
from tw_stock_tool.reports.daily_pipeline import (
    DailyPipelineConfig,
    DailyPipelineResult,
    run_daily_research_pipeline,
)
from tw_stock_tool.reports.daily_report import (
    build_daily_report_data,
    render_daily_report_markdown,
)
from tw_stock_tool.reports.daily_report_serialization import (
    DailyReportSerializationError,
    REPORT_SECTION_ORDER,
    deserialize_daily_report_data,
    export_daily_report_json,
    load_daily_report_json,
    serialize_daily_report_data,
)


def _report():
    return build_daily_report_data()


def _artifact(report=None):
    return serialize_daily_report_data(_report() if report is None else report)


class DailyReportSerializationTests(unittest.TestCase):
    def test_exact_artifact_schema_and_order(self):
        artifact = _artifact()
        self.assertEqual(list(artifact), ["schema_version", "result_type", "report", "metadata"])
        self.assertEqual(artifact["schema_version"], 1)
        self.assertEqual(artifact["result_type"], "daily_research_report")
        self.assertEqual(list(artifact["report"]), list(REPORT_SECTION_ORDER))
        self.assertEqual(list(artifact["metadata"]), ["source", "semantics"])
        self.assertEqual(artifact["metadata"], {
            "source": "daily_report",
            "semantics": "offline_research_artifact",
        })

    def test_empty_builder_round_trip(self):
        report = _report()
        self.assertEqual(load_daily_report_json(export_daily_report_json(report)), report)

    def test_populated_round_trip_and_disclaimer(self):
        report = _report()
        report["Report Highlights"] = ["研究用途，不是交易建議。"]
        report["Risk Notes"] = ["不可作為投資推薦。"]
        report["Next Research Actions"] = ["繼續離線研究"]
        self.assertEqual(load_daily_report_json(export_daily_report_json(report)), report)

    def test_actual_pipeline_report_data_round_trip(self):
        empty = pd.DataFrame()
        with patch.object(daily_pipeline, "run_daily_report", return_value=(empty, empty, empty, None)):
            result = run_daily_research_pipeline(
                ["2330"],
                DailyPipelineConfig(
                    progress=False,
                    validate_top=0,
                    parameter_sweep_top=0,
                    walk_forward_top=0,
                ),
                analysis_provider=lambda _: None,
            )
        self.assertEqual(load_daily_report_json(export_daily_report_json(result.report_data)), result.report_data)

    def test_daily_pipeline_result_keeps_exact_ten_fields(self):
        self.assertEqual(
            list(DailyPipelineResult.__dataclass_fields__),
            [
                "summary_df", "candidates_df", "ranking_df", "backtest_highlights",
                "parameter_sweep_highlights", "walk_forward_highlights", "risk_notes",
                "data_limitations", "report_data", "markdown",
            ],
        )

    def test_numpy_missing_and_datetime_normalization(self):
        report = _report()
        report["Report Metadata"] = {
            "count": np.int64(2),
            "score": np.float64(1.25),
            "enabled": np.bool_(True),
            "missing": pd.NA,
            "nan": np.nan,
            "nat": pd.NaT,
            "day": date(2025, 1, 2),
            "moment": datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            "timestamp": pd.Timestamp("2025-01-02 03:04:05"),
            "tuple": (np.int64(3), "台積電"),
        }
        normalized = serialize_daily_report_data(report)["report"]["Report Metadata"]
        self.assertEqual(normalized, {
            "count": 2, "score": 1.25, "enabled": True, "missing": None,
            "nan": None, "nat": None, "day": "2025-01-02",
            "moment": "2025-01-02T03:04:05+00:00",
            "timestamp": "2025-01-02T03:04:05",
            "tuple": [3, "台積電"],
        })

    def test_infinite_values_rejected(self):
        for value in (float("inf"), float("-inf"), np.float64("inf"), np.float64("-inf")):
            report = _report()
            report["Report Metadata"] = {"bad": value}
            with self.assertRaisesRegex(DailyReportSerializationError, r"\$\.report\.Report Metadata\.bad"):
                serialize_daily_report_data(report)

    def test_unsupported_values_and_nested_paths_rejected(self):
        for value in (pd.DataFrame(), pd.Series(dtype=float), np.array([1]), {1}, object(), lambda: None):
            report = _report()
            report["Report Metadata"] = {"nested": [{"bad": value}]}
            with self.assertRaisesRegex(DailyReportSerializationError, r"\$\.report\.Report Metadata\.nested\[0\]\.bad"):
                serialize_daily_report_data(report)

        report = _report()
        report["Report Metadata"] = {"nested": {1: "bad"}}
        with self.assertRaisesRegex(DailyReportSerializationError, r"Report Metadata.*must be a string"):
            serialize_daily_report_data(report)

    def test_exact_container_types(self):
        cases = {
            "Report Metadata": [],
            "Report Highlights": {},
            "Screening Summary": {},
        }
        for section, value in cases.items():
            report = _report()
            report[section] = value
            with self.assertRaises(DailyReportSerializationError):
                serialize_daily_report_data(report)

    def test_no_mutation_and_deterministic_unicode_json(self):
        report = _report()
        report["Report Highlights"] = ["台積電 — offline"]
        before = copy.deepcopy(report)
        first = export_daily_report_json(report)
        second = export_daily_report_json(report)
        self.assertEqual(first, second)
        self.assertEqual(report, before)
        self.assertIn("台積電", first)
        self.assertNotRegex(first, r"(?:NaN|Infinity|-Infinity)")
        artifact = _artifact(report)
        artifact_before = copy.deepcopy(artifact)
        deserialize_daily_report_data(artifact)
        self.assertEqual(artifact, artifact_before)

    def test_invalid_json_and_json_constants_rejected(self):
        for content in ("{", '{"x": NaN}', '{"x": Infinity}', '{"x": -Infinity}'):
            with self.assertRaises(DailyReportSerializationError):
                load_daily_report_json(content)

    def test_top_level_schema_metadata_and_section_validation(self):
        artifact = _artifact()
        for key in ("missing", "unknown"):
            changed = copy.deepcopy(artifact)
            if key == "missing":
                changed.pop("report")
            else:
                changed["unknown"] = None
            with self.assertRaises(DailyReportSerializationError):
                deserialize_daily_report_data(changed)

        for key, value in (("schema_version", 2), ("result_type", "other")):
            changed = copy.deepcopy(artifact)
            changed[key] = value
            with self.assertRaises(DailyReportSerializationError):
                deserialize_daily_report_data(changed)

        changed = copy.deepcopy(artifact)
        changed["metadata"]["source"] = "other"
        with self.assertRaises(DailyReportSerializationError):
            deserialize_daily_report_data(changed)

        for change in (lambda report: report.pop(REPORT_SECTION_ORDER[0]), lambda report: report.__setitem__("Unknown", [])):
            changed = copy.deepcopy(artifact)
            change(changed["report"])
            with self.assertRaises(DailyReportSerializationError):
                deserialize_daily_report_data(changed)

    def test_dependency_boundary_is_explicit(self):
        source = Path(__file__).resolve().parents[1] / "src/tw_stock_tool/reports/daily_report_serialization.py"
        text = source.read_text(encoding="utf-8")
        for forbidden in (
            "daily_pipeline", "daily_report", "AnalysisSession", "analyze_stock", "scanner",
            "tw_stock_tool.data", "yfinance", "cli", "broker", "paper trading",
        ):
            if forbidden == "daily_report":
                continue
            self.assertNotIn(f"import {forbidden}", text)
            self.assertNotIn(f"from {forbidden}", text)



    def test_empty_pipeline_summary_markdown_section_is_explicit(self):
        markdown = render_daily_report_markdown(_report())
        start = markdown.index("## Pipeline Run Summary")
        end = markdown.find("\n## ", start + 1)
        section = markdown[start:] if end == -1 else markdown[start:end]
        self.assertEqual(markdown.count("## Pipeline Run Summary"), 1)
        self.assertIn("No data provided.", section)
        self.assertLess(markdown.index("## Run Configuration"), start)

    def test_existing_markdown_rendering_remains_unchanged(self):
        markdown = render_daily_report_markdown(_report())
        self.assertEqual(markdown.count("## Pipeline Run Summary"), 1)
        self.assertIn("No data provided.", markdown)

if __name__ == "__main__":
    unittest.main()
