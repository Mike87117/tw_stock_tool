import unittest
import pandas as pd
from tw_stock_tool.reports.daily_report import build_daily_report_data

class TestDailyReportBuilder(unittest.TestCase):

    def test_minimal_empty_input(self):
        result = build_daily_report_data()

        self.assertEqual(result["Report Metadata"]["Date"], "N/A")
        self.assertEqual(result["Universe Summary"]["Total Stocks"], 0)
        self.assertEqual(result["Universe Summary"]["Universe"], [])
        self.assertEqual(result["Screening Summary"], [])
        self.assertEqual(result["Watchlist Candidates"], [])
        self.assertEqual(result["Backtest Highlights"], [])
        self.assertEqual(result["Parameter Sweep Highlights"], [])
        self.assertEqual(result["Walk Forward Highlights"], [])

        # Risk notes must contain standard research disclaimer
        self.assertIn("This report is for research purposes only and does not constitute investment advice.", result["Risk Notes"])

        # Empty inputs should trigger a data limitation warning
        self.assertTrue(any("No screening data" in note for note in result["Data Limitations"]))
        self.assertEqual(result["Next Research Actions"], [])

    def test_stock_universe_summary(self):
        universe = ["2330", "2317", "2454"]
        result = build_daily_report_data(stock_universe=universe)

        self.assertEqual(result["Universe Summary"]["Total Stocks"], 3)
        self.assertEqual(result["Universe Summary"]["Universe"], universe)
        self.assertFalse(any("No screening data" in note for note in result["Data Limitations"]))

    def test_watchlist_candidates_normalization_from_list(self):
        candidates = [{"Stock": "2330", "Score": 5}, {"Stock": "2317", "Score": 3}]
        result = build_daily_report_data(watchlist_candidates=candidates)

        self.assertEqual(len(result["Watchlist Candidates"]), 2)
        self.assertEqual(result["Watchlist Candidates"][0]["Stock"], "2330")

    def test_dataframe_normalization(self):
        df = pd.DataFrame({"Stock": ["2330", "2454"], "Close": [1000, 1500]})
        result = build_daily_report_data(screening_results=df)

        screening = result["Screening Summary"]
        self.assertEqual(len(screening), 2)
        self.assertEqual(screening[0]["Stock"], "2330")
        self.assertEqual(screening[0]["Close"], 1000)

    def test_highlight_passthrough(self):
        bt_highlights = [{"Strategy": "MA Cross", "WinRate": 0.5}]
        ps_highlights = pd.DataFrame([{"Strategy": "MA Cross", "BestParam": "5,20"}])
        wf_highlights = [{"Strategy": "MA Cross", "Robustness": "High"}]

        result = build_daily_report_data(
            backtest_highlights=bt_highlights,
            parameter_sweep_highlights=ps_highlights,
            walk_forward_highlights=wf_highlights
        )

        self.assertEqual(result["Backtest Highlights"], bt_highlights)
        self.assertEqual(len(result["Parameter Sweep Highlights"]), 1)
        self.assertEqual(result["Parameter Sweep Highlights"][0]["BestParam"], "5,20")
        self.assertEqual(result["Walk Forward Highlights"], wf_highlights)

    def test_empty_dataframe_handling(self):
        df = pd.DataFrame()
        result = build_daily_report_data(watchlist_candidates=df)
        self.assertEqual(result["Watchlist Candidates"], [])

if __name__ == '__main__':
    unittest.main()
