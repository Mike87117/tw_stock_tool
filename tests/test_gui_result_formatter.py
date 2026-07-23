from pathlib import Path
import unittest

import pandas as pd

from tw_stock_tool.gui.gui_result_formatter import format_task_result


class GuiResultFormatterTest(unittest.TestCase):
    def test_dataframe_preview_is_limited(self) -> None:
        df = pd.DataFrame(
            {
                "id": list(range(25)),
                "label": [f"row_{index}" for index in range(25)],
            }
        )

        output = format_task_result("Run Scan", df)

        self.assertIn("rows: 25", output)
        self.assertIn("columns: 2", output)
        self.assertIn("preview (first 20 rows)", output)
        self.assertIn("row_19", output)
        self.assertNotIn("row_24", output)

    def test_update_stock_list_contains_count_and_output_path(self) -> None:
        output = format_task_result(
            "Update Stock List",
            {
                "count": 2,
                "output_path": Path("stocks.txt"),
                "stocks": pd.DataFrame({"Stock": ["2330", "8069"]}),
            },
        )

        self.assertIn("count: 2", output)
        self.assertIn("output_path: stocks.txt", output)

    def test_daily_report_contains_summary_candidates_ranking_and_output(self) -> None:
        output = format_task_result(
            "Run Daily Report",
            {
                "summary": pd.DataFrame({"Candidates": [2]}),
                "candidates": pd.DataFrame({"Stock": ["2330", "2317"]}),
                "ranking": pd.DataFrame({"Stock": ["2330", "2317", "2454"]}),
                "output_path": "output/daily_report.xlsx",
            },
        )

        self.assertIn("summary rows: 1", output)
        self.assertIn("candidates rows: 2", output)
        self.assertIn("ranking rows: 3", output)
        self.assertIn("output_path: output/daily_report.xlsx", output)

    def test_single_stock_analysis_skips_analysis_object(self) -> None:
        class AnalysisObject:
            def __str__(self) -> str:
                return "ANALYSIS_OBJECT_SHOULD_NOT_PRINT"

        output = format_task_result(
            "Run Single Stock Analysis",
            {
                "analysis": AnalysisObject(),
                "signal": pd.DataFrame({"Signal": ["BUY", "HOLD"]}),
                "summary": {"Signal": "BUY"},
                "backtest": {"Total Return %": 10.5},
                "symbol": "2330.TW",
                "excel_path": "output/2330_analysis.xlsx",
                "chart_path": "output/2330_chart.png",
            },
        )

        self.assertIn("symbol: 2330.TW", output)
        self.assertIn("summary:", output)
        self.assertIn("backtest:", output)
        self.assertIn("excel_path: output/2330_analysis.xlsx", output)
        self.assertIn("chart_path: output/2330_chart.png", output)
        self.assertIn("signal:", output)
        self.assertIn("rows: 2", output)
        self.assertNotIn("ANALYSIS_OBJECT_SHOULD_NOT_PRINT", output)

    def test_cache_summary_contains_count_and_empty(self) -> None:
        output = format_task_result(
            "Cache Summary",
            {
                "count": 1,
                "empty": False,
                "summary": pd.DataFrame({"File": ["cache.csv"]}),
            },
        )

        self.assertIn("count: 1", output)
        self.assertIn("empty: False", output)
        self.assertIn("summary:", output)

    def test_clear_cache_contains_cleared(self) -> None:
        output = format_task_result("Clear Cache", {"cleared": 3})

        self.assertIn("cleared: 3", output)

    def test_doctor_contains_summary_and_has_failures(self) -> None:
        output = format_task_result(
            "Run Doctor",
            {
                "summary": {"PASS": 8, "FAIL": 0},
                "has_failures": False,
                "rows": [{"check": "Python", "status": "PASS"}],
            },
        )

        self.assertIn("summary:", output)
        self.assertIn("has_failures: False", output)
        self.assertIn("rows:", output)

    def test_price_smoke_check_contains_results(self) -> None:
        output = format_task_result(
            "Check Price Data Source",
            {
                "failed": False,
                "results": [{"check": "yfinance 2330", "status": "PASS"}],
            },
        )

        self.assertIn("failed: False", output)
        self.assertIn("results:", output)


if __name__ == "__main__":
    unittest.main()
