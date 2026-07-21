import unittest
from unittest.mock import patch
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tw_stock_tool.reports import daily_pipeline
from tw_stock_tool.reports.daily_pipeline import build_daily_pipeline_run_summary
from tw_stock_tool.reports.daily_report import build_daily_report_data, render_daily_report_markdown


class DailyPipelineRunSummaryTest(unittest.TestCase):
    def test_mixed_status_snapshot_has_exact_order_and_python_ints(self):
        summary = build_daily_pipeline_run_summary(
            [" 2330", "2330", "# ignored", "2317"],
            pd.DataFrame({"Status": [" OK ", "error", None]}),
            pd.DataFrame([{}, {}]),
            pd.DataFrame({"Status": ["ok", " FAILED ", "unknown"]}),
            pd.DataFrame({"Status": [" PARTIAL ", "ok", "error", None]}),
            pd.DataFrame({"Status": ["partial", " OK "]}),
        )
        expected = {
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
        self.assertEqual(summary, expected)
        self.assertEqual(list(summary), list(expected))
        self.assertTrue(all(type(value) is int for value in summary.values()))

    def test_empty_and_missing_status_schemas_fail_closed(self):
        empty = pd.DataFrame(columns=["Status"])
        missing = pd.DataFrame(index=[0, 1])
        summary = build_daily_pipeline_run_summary(
            [], missing, empty, missing, empty, missing
        )
        self.assertEqual(summary["Stocks Requested"], 0)
        self.assertEqual(summary["Stocks Scanned"], 2)
        self.assertEqual(summary["Scan OK"], 0)
        self.assertEqual(summary["Scan Failed"], 2)
        self.assertEqual(summary["Backtest Failed"], 2)
        self.assertEqual(summary["Walk Forward Failed"], 2)

    def test_report_builder_copies_summary_and_renderer_preserves_order(self):
        source = {"Stocks Requested": 2, "Scan OK": 1}
        report = build_daily_report_data(pipeline_run_summary=source)
        source["Scan OK"] = 99
        self.assertEqual(report["Pipeline Run Summary"], {"Stocks Requested": 2, "Scan OK": 1})
        markdown = render_daily_report_markdown(report)
        self.assertEqual(markdown.count("## Pipeline Run Summary"), 1)
        self.assertLess(markdown.index("## Run Configuration"), markdown.index("## Pipeline Run Summary"))
        self.assertLess(markdown.index("## Pipeline Run Summary"), markdown.index("## Report Highlights"))
        self.assertIn("- **Stocks Requested**: 2", markdown)


    def test_status_normalization_is_fail_closed_without_mutation(self):
        ranking = pd.DataFrame({"Status": [" ok ", "", None, "unknown", "OK"]})
        candidates = pd.DataFrame([{"Stock": "2330"}])
        backtest = pd.DataFrame({"Status": [" OK ", " partial ", "ERROR"]})
        sweep = pd.DataFrame({"Status": ["partial", " ok ", "unknown", None]})
        walk_forward = pd.DataFrame({"Status": [" OK ", "PARTIAL", ""]})
        before = [frame.copy(deep=True) for frame in (ranking, candidates, backtest, sweep, walk_forward)]

        summary = build_daily_pipeline_run_summary(
            ["2330"], ranking, candidates, backtest, sweep, walk_forward
        )

        self.assertEqual(summary["Scan OK"], 2)
        self.assertEqual(summary["Scan Failed"], 3)
        self.assertEqual(summary["Backtest OK"], 1)
        self.assertEqual(summary["Backtest Failed"], 2)
        self.assertEqual(summary["Parameter Sweep OK"], 1)
        self.assertEqual(summary["Parameter Sweep Partial"], 1)
        self.assertEqual(summary["Parameter Sweep Failed"], 2)
        self.assertEqual(summary["Walk Forward OK"], 1)
        self.assertEqual(summary["Walk Forward Partial"], 1)
        self.assertEqual(summary["Walk Forward Failed"], 1)
        for actual, expected in zip(
            (ranking, candidates, backtest, sweep, walk_forward), before
        ):
            pd.testing.assert_frame_equal(actual, expected)

    def test_none_summary_is_an_empty_dict(self):
        report = daily_pipeline.build_daily_report_data(pipeline_run_summary=None)
        self.assertEqual(report["Pipeline Run Summary"], {})

    def test_result_keeps_the_original_ten_fields(self):
        self.assertEqual(
            list(daily_pipeline.DailyPipelineResult.__dataclass_fields__),
            [
                "summary_df",
                "candidates_df",
                "ranking_df",
                "backtest_highlights",
                "parameter_sweep_highlights",
                "walk_forward_highlights",
                "risk_notes",
                "data_limitations",
                "report_data",
                "markdown",
            ],
        )

    def test_summary_builder_is_pure_and_does_not_call_services(self):
        with patch.object(daily_pipeline, "AnalysisSession") as session, \
             patch.object(daily_pipeline, "run_daily_report") as scan, \
             patch.object(daily_pipeline, "run_candidate_backtest_validation") as backtest, \
             patch.object(daily_pipeline, "run_candidate_parameter_sweep_validation") as sweep, \
             patch.object(daily_pipeline, "run_candidate_walk_forward_validation") as walk_forward, \
             patch.object(daily_pipeline, "build_daily_report_data") as build, \
             patch.object(daily_pipeline, "render_daily_report_markdown") as render, \
             patch.object(daily_pipeline, "analyze_stock", create=True) as analyzer:
            build_daily_pipeline_run_summary(
                [],
                pd.DataFrame(columns=["Status"]),
                pd.DataFrame(),
                pd.DataFrame(columns=["Status"]),
                pd.DataFrame(columns=["Status"]),
                pd.DataFrame(columns=["Status"]),
            )
        session.assert_not_called()
        scan.assert_not_called()
        backtest.assert_not_called()
        sweep.assert_not_called()
        walk_forward.assert_not_called()
        build.assert_not_called()
        render.assert_not_called()
        analyzer.assert_not_called()

    def test_pipeline_report_data_contains_exact_summary(self):
        summary_df = pd.DataFrame(
            [{"Stocks Scanned": 2, "Candidates": 1, "BUY Count": 1, "WATCH Count": 0}]
        )
        candidates_df = pd.DataFrame([{"Stock": "2330", "Signal": "BUY", "Score": 5}])
        ranking_df = pd.DataFrame(
            [{"Stock": "2330", "Status": " OK "}, {"Stock": "2317", "Status": "error"}]
        )
        expected = {
            "Stocks Requested": 2,
            "Stocks Scanned": 2,
            "Scan OK": 1,
            "Scan Failed": 1,
            "Candidates Selected": 1,
            "Backtest Selected": 0,
            "Backtest OK": 0,
            "Backtest Failed": 0,
            "Parameter Sweep Selected": 0,
            "Parameter Sweep OK": 0,
            "Parameter Sweep Partial": 0,
            "Parameter Sweep Failed": 0,
            "Walk Forward Selected": 0,
            "Walk Forward OK": 0,
            "Walk Forward Partial": 0,
            "Walk Forward Failed": 0,
        }

        with patch.object(
            daily_pipeline,
            "run_daily_report",
            return_value=(summary_df, candidates_df, ranking_df, None),
        ):
            result = daily_pipeline.run_daily_research_pipeline(
                [" 2330", "2330", "# ignored", "2317"],
                daily_pipeline.DailyPipelineConfig(progress=False),
                analysis_provider=lambda stock_id: None,
            )

        self.assertEqual(result.report_data["Pipeline Run Summary"], expected)

    def test_empty_summary_markdown_section_is_explicit(self):
        markdown = render_daily_report_markdown(
            build_daily_report_data(pipeline_run_summary=None)
        )
        start = markdown.index("## Pipeline Run Summary")
        end = markdown.index("## Report Highlights")
        section = markdown[start:end]

        self.assertEqual(markdown.count("## Pipeline Run Summary"), 1)
        self.assertIn("No data provided.", section)
        self.assertEqual(section.count("No data provided."), 1)
        self.assertLess(start, end)

if __name__ == "__main__":
    unittest.main()
