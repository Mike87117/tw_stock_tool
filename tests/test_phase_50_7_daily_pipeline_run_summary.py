import unittest
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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


if __name__ == "__main__":
    unittest.main()
