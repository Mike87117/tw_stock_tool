import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tw_stock_tool.reports.daily_pipeline import DailyPipelineResult
from tw_stock_tool.reports.daily_report import build_daily_report_data, render_daily_report_markdown
from tw_stock_tool.reports.daily_report_serialization import (
    DailyReportSerializationError,
    export_daily_report_json,
)
from tw_stock_tool.reports.daily_report_serialization_files import (
    export_daily_report_json_file,
    load_daily_report_json_file,
)


def _report():
    return build_daily_report_data()


class DailyReportJsonFileHelperTests(unittest.TestCase):
    def test_empty_report_round_trip_and_absolute_path(self):
        with tempfile.TemporaryDirectory() as tempdir:
            target = Path(tempdir) / "nested" / "report.json"
            result = export_daily_report_json_file(_report(), target)
            self.assertEqual(result, target.resolve())
            self.assertTrue(result.is_absolute())
            self.assertEqual(load_daily_report_json_file(result), _report())

    def test_populated_unicode_report_round_trip_and_exact_content(self):
        report = _report()
        report["Report Highlights"] = ["台積電 — offline research"]
        report["Risk Notes"] = ["This is not investment advice."]
        expected = export_daily_report_json(report)
        with tempfile.TemporaryDirectory() as tempdir:
            result = export_daily_report_json_file(report, str(Path(tempdir) / "report.json"))
            self.assertEqual(result.read_text(encoding="utf-8"), expected)
            self.assertFalse(result.read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertFalse(result.read_bytes().endswith(b"\n"))
            self.assertEqual(load_daily_report_json_file(result), report)

    def test_nested_parent_creation_and_path_types(self):
        with tempfile.TemporaryDirectory() as tempdir:
            target = Path(tempdir) / "a" / "b" / "report.json"
            result = export_daily_report_json_file(_report(), str(target))
            self.assertEqual(result, target.resolve())
            self.assertEqual(load_daily_report_json_file(str(target)), _report())

    def test_overwrite_policy_and_existing_content_preservation(self):
        with tempfile.TemporaryDirectory() as tempdir:
            target = Path(tempdir) / "report.json"
            target.write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                export_daily_report_json_file(_report(), target)
            self.assertEqual(target.read_text(encoding="utf-8"), "existing")
            export_daily_report_json_file(_report(), target, overwrite=True)
            self.assertEqual(target.read_text(encoding="utf-8"), export_daily_report_json(_report()))

    def test_invalid_report_serializes_before_any_file_io(self):
        invalid = _report()
        invalid["Report Metadata"] = {"bad": object()}
        with tempfile.TemporaryDirectory() as tempdir:
            target = Path(tempdir) / "missing" / "report.json"
            with self.assertRaises(DailyReportSerializationError):
                export_daily_report_json_file(invalid, target)
            self.assertFalse(target.exists())
            self.assertFalse(target.parent.exists())

            existing = Path(tempdir) / "existing.json"
            existing.write_text("keep", encoding="utf-8")
            with self.assertRaises(DailyReportSerializationError):
                export_daily_report_json_file(invalid, existing, overwrite=True)
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep")

    def test_writer_receives_serialized_content_and_options(self):
        report = _report()
        target = Path("report.json")
        with patch(
            "tw_stock_tool.reports.daily_report_serialization_files.export_daily_report_json",
            return_value="content",
        ) as serializer, patch(
            "tw_stock_tool.reports.daily_report_serialization_files.write_text_report",
            return_value=target.resolve(),
        ) as writer:
            result = export_daily_report_json_file(report, target, overwrite=True)
        serializer.assert_called_once_with(report)
        writer.assert_called_once_with("content", target, overwrite=True)
        self.assertEqual(result, target.resolve())

    def test_invalid_json_schema_and_constants_rejected(self):
        with tempfile.TemporaryDirectory() as tempdir:
            target = Path(tempdir) / "report.json"
            for content in ("{", '{"x": NaN}', '{"x": Infinity}', '{"x": -Infinity}'):
                target.write_text(content, encoding="utf-8")
                with self.assertRaises(DailyReportSerializationError):
                    load_daily_report_json_file(target)

            artifact = json.loads(export_daily_report_json(_report()))
            artifact["schema_version"] = 2
            target.write_text(json.dumps(artifact), encoding="utf-8")
            with self.assertRaises(DailyReportSerializationError):
                load_daily_report_json_file(target)

    def test_filesystem_errors_are_preserved(self):
        with tempfile.TemporaryDirectory() as tempdir:
            missing = Path(tempdir) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                load_daily_report_json_file(missing)
            directory = Path(tempdir) / "directory"
            directory.mkdir()
            with self.assertRaises(IsADirectoryError):
                load_daily_report_json_file(directory)
            invalid_utf8 = Path(tempdir) / "invalid.json"
            invalid_utf8.write_bytes(b"\xff")
            with self.assertRaises(UnicodeDecodeError):
                load_daily_report_json_file(invalid_utf8)

    def test_report_input_is_not_mutated(self):
        report = _report()
        before = copy.deepcopy(report)
        with tempfile.TemporaryDirectory() as tempdir:
            export_daily_report_json_file(report, Path(tempdir) / "report.json")
        self.assertEqual(report, before)

    def test_canonical_sections_configuration_summary_and_disclaimer(self):
        summary = {
            "Stocks Requested": 2,
            "Stocks Scanned": 3,
            "Scan OK": 1,
            "Scan Failed": 2,
            "Candidates Selected": 2,
            "Backtest Selected": 3,
            "Backtest OK": 1,
            "Backtest Failed": 2,
            "Parameter Sweep Selected": 4,
            "Parameter Sweep OK": 1,
            "Parameter Sweep Partial": 1,
            "Parameter Sweep Failed": 2,
            "Walk Forward Selected": 2,
            "Walk Forward OK": 1,
            "Walk Forward Partial": 1,
            "Walk Forward Failed": 0,
        }
        report = build_daily_report_data(
            run_configuration={"Candidate Top": None, "Walk Forward Enabled": True},
            pipeline_run_summary=summary,
            next_research_actions=["Continue offline research."],
        )
        with tempfile.TemporaryDirectory() as tempdir:
            loaded = load_daily_report_json_file(
                export_daily_report_json_file(report, Path(tempdir) / "report.json")
            )
        self.assertEqual(list(loaded), [
            "Report Metadata", "Run Configuration", "Pipeline Run Summary",
            "Report Highlights", "Data Quality Notes", "Universe Summary",
            "Screening Summary", "Watchlist Candidates", "Backtest Highlights",
            "Parameter Sweep Highlights", "Walk Forward Highlights", "Risk Notes",
            "Data Limitations", "Next Research Actions",
        ])
        self.assertEqual(loaded["Run Configuration"], report["Run Configuration"])
        self.assertEqual(loaded["Pipeline Run Summary"], summary)
        self.assertIn("research purposes only", " ".join(loaded["Risk Notes"]))
        self.assertEqual(len(loaded["Pipeline Run Summary"]), 16)

    def test_dependency_boundary_in_clean_subprocess(self):
        code = """
import sys
from tw_stock_tool.reports.daily_report_serialization_files import (
    export_daily_report_json_file,
    load_daily_report_json_file,
)
forbidden = (
    "tw_stock_tool.reports.daily_pipeline",
    "tw_stock_tool.reports.daily_report",
    "tw_stock_tool.analysis",
    "tw_stock_tool.data",
    "tw_stock_tool.cli",
    "tw_stock_tool.backtesting",
    "tw_stock_tool.paper_trading",
    "tw_stock_tool.broker",
    "yfinance",
    "shioaji",
)
found = [
    module for module in sys.modules
    if any(module == prefix or module.startswith(prefix + ".") for prefix in forbidden)
]
if found:
    print("forbidden modules: " + ", ".join(found))
    raise SystemExit(1)
"""
        env = os.environ.copy()
        src = str(Path(__file__).resolve().parents[1] / "src")
        env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_daily_pipeline_result_and_existing_behavior_unchanged(self):
        self.assertEqual(
            list(DailyPipelineResult.__dataclass_fields__),
            [
                "summary_df", "candidates_df", "ranking_df", "backtest_highlights",
                "parameter_sweep_highlights", "walk_forward_highlights", "risk_notes",
                "data_limitations", "report_data", "markdown",
            ],
        )
        self.assertIn("## Pipeline Run Summary", render_daily_report_markdown(_report()))


if __name__ == "__main__":
    unittest.main()
