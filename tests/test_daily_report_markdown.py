import copy
import subprocess
import sys
import unittest

import pandas as pd

from tw_stock_tool.reports.daily_report import (
    build_daily_report_data,
    render_daily_report_markdown as legacy_renderer,
)
from tw_stock_tool.reports.daily_report_markdown import (
    _format_markdown_table_cell,
    render_daily_report_markdown as lightweight_renderer,
)

render_daily_report_markdown = legacy_renderer

class TestDailyReportMarkdown(unittest.TestCase):

    def test_minimal_empty_report(self):
        data = build_daily_report_data()
        markdown = render_daily_report_markdown(data)
        
        # Test title
        self.assertIn("# Daily Research Report", markdown)
        
        # Test standard disclaimer
        self.assertIn("This report is for research purposes only and does not constitute investment advice.", markdown)
        
        # Test empty list placeholder
        self.assertIn("No data provided.", markdown)
        
        # Section heading stability
        sections = [
            "## Report Metadata",
            "## Run Configuration",
            "## Pipeline Run Summary",
            "## Report Highlights",
            "## Data Quality Notes",
            "## Universe Summary",
            "## Screening Summary",
            "## Watchlist Candidates for Further Review",
            "## Backtest Highlights",
            "## Parameter Sweep Highlights",
            "## Walk Forward Highlights",
            "## Risk Notes",
            "## Data Limitations",
            "## Next Research Actions",
        ]
        
        for section in sections:
            self.assertIn(section, markdown)
            
        # Ensure correct order
        indices = [markdown.find(sec) for sec in sections]
        self.assertEqual(indices, sorted(indices), "Sections are out of order")

    def test_build_data_contract(self):
        data = build_daily_report_data()
        expected_keys = [
            "Report Metadata",
            "Run Configuration",
            "Pipeline Run Summary",
            "Report Highlights",
            "Data Quality Notes",
            "Universe Summary",
            "Screening Summary",
            "Watchlist Candidates",
            "Backtest Highlights",
            "Parameter Sweep Highlights",
            "Walk Forward Highlights",
            "Risk Notes",
            "Data Limitations",
            "Next Research Actions",
        ]
        self.assertEqual(list(data.keys()), expected_keys, "Data contract keys or order do not match expected structure.")

    def test_watchlist_candidates_table(self):
        candidates = [{"Stock": "2330", "Score": 5}, {"Stock": "2317", "Score": 3}]
        data = build_daily_report_data(watchlist_candidates=candidates)
        markdown = render_daily_report_markdown(data)
        
        # Ensure it renders as table
        self.assertIn("| Stock | Score |", markdown)
        self.assertIn("|---|---|", markdown)
        self.assertIn("| 2330 | 5 |", markdown)
        self.assertIn("| 2317 | 3 |", markdown)

    def test_no_banned_wording(self):
        data = build_daily_report_data()
        markdown = render_daily_report_markdown(data).lower()
        
        banned_words = [
            "stocks to buy",
            "recommended stocks", 
            "buy recommendation", 
            "sell recommendation", 
            "best opportunities",
            "high-potential stocks",
            "should buy",
            "safe to invest",
            "guaranteed return", 
            "profit opportunity",
            "investment recommendation",
            "investment opportunity",
            "guaranteed profit",
            "guaranteed latest data"
        ]
        
        for word in banned_words:
            self.assertNotIn(word, markdown)
            
    def test_renderer_does_not_mutate_input(self):
        input_data = build_daily_report_data()
        
        # Snapshot state
        original_risk_notes_len = len(input_data["Risk Notes"])
        original_data_limitations_len = len(input_data["Data Limitations"])
        
        render_daily_report_markdown(input_data)
        
        self.assertEqual(len(input_data["Risk Notes"]), original_risk_notes_len)
        self.assertEqual(len(input_data["Data Limitations"]), original_data_limitations_len)

    def test_table_renders_union_headers_for_inconsistent_rows(self):
        data = build_daily_report_data(
            watchlist_candidates=[
                {"Stock": "2330", "Score": 5},
                {"Stock": "2317", "RSI": 62},
            ]
        )

        markdown = render_daily_report_markdown(data)

        self.assertIn("| Stock | Score | RSI |", markdown)
        self.assertIn("| 2330 | 5 |  |", markdown)
        self.assertIn("| 2317 |  | 62 |", markdown)

    def test_data_limitations_renders_correctly(self) -> None:
        limitations = ["9999: ERROR - bad stock", "8888: ERROR - no data"]
        data = build_daily_report_data(data_limitations=limitations)
        markdown = render_daily_report_markdown(data)

        self.assertIn("## Data Limitations", markdown)
        self.assertIn("- 9999: ERROR - bad stock", markdown)
        self.assertIn("- 8888: ERROR - no data", markdown)

    def test_highlights_with_screening_data(self):
        screening_data = [{"Stocks Scanned": 1500, "Candidates": 50, "BUY Count": 10, "WATCH Count": 40}]
        data = build_daily_report_data(screening_results=screening_data)
        markdown = render_daily_report_markdown(data)
        
        self.assertIn("Report generation summary: 1500 symbols included.", markdown)
        self.assertIn("Notable observations: 50 candidates met the criteria.", markdown)
        self.assertIn("Strategy signal counts from existing computed metrics: 10 BUY labels, 40 WATCH labels.", markdown)
        self.assertIn("Generated from available computed metrics.", markdown)

    def test_highlights_empty_state(self):
        data = build_daily_report_data()
        markdown = render_daily_report_markdown(data)
        self.assertIn("No screening summary data was provided, so highlights are limited for this report.", markdown)

    def test_data_quality_notes_empty(self):
        data = build_daily_report_data()
        markdown = render_daily_report_markdown(data)
        
        self.assertIn("## Data Quality Notes", markdown)
        self.assertIn("Data quality summary: 0 symbols were included in the configured universe.", markdown)
        self.assertIn("No screening summary data was provided for this report.", markdown)
        self.assertIn("Data limitations recorded: 1 item(s).", markdown) # empty state adds 1 limitation automatically
        self.assertIn("Some symbols may be absent due to upstream data availability or scan errors.", markdown)

    def test_data_quality_notes_populated(self):
        screening_data = [{"Stocks Scanned": 1500, "Candidates": 50, "BUY Count": 10, "WATCH Count": 40}]
        universe = ["2330", "2317", "2454"]
        limitations = ["9999: ERROR - bad stock", "8888: ERROR - no data"]
        
        data = build_daily_report_data(
            stock_universe=universe, 
            screening_results=screening_data,
            data_limitations=limitations
        )
        markdown = render_daily_report_markdown(data)
        
        self.assertIn("## Data Quality Notes", markdown)
        self.assertIn("Data quality summary: 3 symbols were included in the configured universe.", markdown)
        self.assertIn("Screening summary rows available: 1.", markdown)
        self.assertIn("Data limitations recorded: 2 item(s).", markdown)
        self.assertIn("Some symbols may be absent due to upstream data availability or scan errors.", markdown)


class TestDailyReportMarkdownLightweightBoundary(unittest.TestCase):
    def test_legacy_and_lightweight_imports_are_same_function(self):
        self.assertIs(legacy_renderer, lightweight_renderer)

    def test_table_cell_formatter_handles_all_required_values(self):
        cases = [
            (None, ""),
            ("data | source", r"data \| source"),
            ("a\r\nb", "a<br>b"),
            ("a\rb", "a<br>b"),
            ("a\nb", "a<br>b"),
            ("a\r\n|\rb\nc", r"a<br>\|<br>b<br>c"),
            (42, "42"),
            (True, "True"),
            ("\u53f0\u7063", "\u53f0\u7063"),
            ({"a": 1}, "{'a': 1}"),
            ([1, 2], "[1, 2]"),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(_format_markdown_table_cell(value), expected)

    def test_table_headers_and_cells_are_hardened_in_first_seen_order(self):
        report = build_daily_report_data(
            watchlist_candidates=[
                {"Stock|Code": "2330", "Note": "a|b\r\nc", "Optional": None},
                {"Stock|Code": "2317", "New\nKey": True},
            ]
        )
        before = copy.deepcopy(report)
        markdown = lightweight_renderer(report)
        self.assertIn(r"| Stock\|Code | Note | Optional | New<br>Key |", markdown)
        self.assertIn(r"| 2330 | a\|b<br>c |  |  |", markdown)
        self.assertIn("| 2317 |  |  | True |", markdown)
        self.assertEqual(report, before)

    def test_lightweight_renderer_dependency_boundary(self):
        code = """
import sys
import tw_stock_tool.reports.daily_report_markdown
forbidden = (
    "pandas", "numpy", "tw_stock_tool.analysis", "tw_stock_tool.data",
    "tw_stock_tool.backtesting", "tw_stock_tool.paper_trading",
    "tw_stock_tool.ml", "tw_stock_tool.cli", "yfinance", "sklearn", "shioaji",
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


if __name__ == '__main__':
    unittest.main()
