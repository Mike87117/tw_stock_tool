import unittest
import pandas as pd
from tw_stock_tool.reports.daily_report import build_daily_report_data, render_daily_report_markdown

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
            "## Report Highlights",
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
            "recommended stocks", 
            "buy recommendation", 
            "sell recommendation", 
            "guaranteed return", 
            "profit opportunity"
        ]
        
        for word in banned_words:
            self.assertNotIn(word, markdown)
            
    def test_renderer_does_not_mutate_input(self):
        input_data = build_daily_report_data()
        
        # Create a deep-ish copy manually just for test tracking since dict has nested dicts/lists
        original_risk_notes_len = len(input_data["Risk Notes"])
        
        render_daily_report_markdown(input_data)
        
        self.assertEqual(len(input_data["Risk Notes"]), original_risk_notes_len)

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


if __name__ == '__main__':
    unittest.main()
