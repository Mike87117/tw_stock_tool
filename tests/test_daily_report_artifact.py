import copy
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tw_stock_tool.reports.daily_report import build_daily_report_data
from tw_stock_tool.reports.daily_report_artifact import build_daily_report_artifact_summary


EXPECTED_KEYS = [
    "Report Date", "Report Type", "Total Stocks", "Screening Summary Rows",
    "Watchlist Candidate Rows", "Backtest Highlight Rows",
    "Parameter Sweep Highlight Rows", "Walk Forward Highlight Rows",
    "Risk Note Count", "Data Limitation Count", "Next Research Action Count",
]


def _populated_report():
    return build_daily_report_data(
        report_date="2026-07-22",
        stock_universe=["2330", "2317"],
        screening_results=[{"Stocks Scanned": 2}, {"Stocks Scanned": 1}],
        watchlist_candidates=[{"Stock": "2330", "Signal": "BUY"}],
        backtest_highlights=[{"Stock": "2330"}],
        parameter_sweep_highlights=[{"Stock": "2330"}, {"Stock": "2317"}],
        walk_forward_highlights=[{"Stock": "2330"}],
        risk_notes=["custom risk"],
        data_limitations=["partial data"],
        next_research_actions=["review offline"],
    )


class DailyReportArtifactSummaryTests(unittest.TestCase):
    def test_populated_summary_has_exact_order_and_counts(self):
        report = _populated_report()
        summary = build_daily_report_artifact_summary(report)
        self.assertEqual(list(summary), EXPECTED_KEYS)
        self.assertEqual(summary, {
            "Report Date": "2026-07-22",
            "Report Type": "Daily Research Report",
            "Total Stocks": 2,
            "Screening Summary Rows": 2,
            "Watchlist Candidate Rows": 1,
            "Backtest Highlight Rows": 1,
            "Parameter Sweep Highlight Rows": 2,
            "Walk Forward Highlight Rows": 1,
            "Risk Note Count": 2,
            "Data Limitation Count": 1,
            "Next Research Action Count": 1,
        })

    def test_empty_canonical_report_uses_metadata_and_zero_table_counts(self):
        summary = build_daily_report_artifact_summary(build_daily_report_data())
        self.assertEqual(summary["Report Date"], "N/A")
        self.assertEqual(summary["Report Type"], "Daily Research Report")
        self.assertEqual(summary["Total Stocks"], 0)
        for key in EXPECTED_KEYS[3:8]:
            self.assertEqual(summary[key], 0)
        self.assertEqual(summary["Risk Note Count"], 1)
        self.assertEqual(summary["Data Limitation Count"], 1)
        self.assertEqual(summary["Next Research Action Count"], 0)

    def test_unicode_metadata_is_preserved_without_exposing_rows(self):
        report = _populated_report()
        report["Report Metadata"] = {
            "Date": "\u6c11\u570b115\u5e74",
            "Type": "\u6bcf\u65e5\u7814\u7a76\u5831\u544a",
        }
        summary = build_daily_report_artifact_summary(report)
        self.assertEqual(summary["Report Date"], "\u6c11\u570b115\u5e74")
        self.assertEqual(summary["Report Type"], "\u6bcf\u65e5\u7814\u7a76\u5831\u544a")
        rendered = repr(summary)
        for excluded in ("2330", "BUY", "custom risk"):
            self.assertNotIn(excluded, rendered)

    def test_input_is_not_mutated(self):
        report = _populated_report()
        before = copy.deepcopy(report)
        build_daily_report_artifact_summary(report)
        self.assertEqual(report, before)

    def test_lightweight_dependency_boundary(self):
        code = """
import sys
import tw_stock_tool.reports.daily_report_artifact
forbidden = (
    "pandas", "numpy", "tw_stock_tool.analysis", "tw_stock_tool.data",
    "tw_stock_tool.backtesting", "tw_stock_tool.paper_trading",
    "tw_stock_tool.ml", "yfinance", "sklearn", "shioaji",
)
found = sorted(name for name in sys.modules if any(
    name == prefix or name.startswith(prefix + ".") for prefix in forbidden
))
if found:
    print("forbidden modules: " + ", ".join(found))
    raise SystemExit(1)
"""
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
