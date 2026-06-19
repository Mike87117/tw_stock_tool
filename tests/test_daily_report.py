import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

import daily_report


def _ranking_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Rank": 1,
                "Stock": "2330",
                "Signal": "BUY",
                "Score": 6.0,
                "Close": 900.0,
                "Volume_Ratio": 1.8,
                "RSI": 62.0,
                "Analysis": "strong",
                "Status": "OK",
                "Error": "",
            },
            {
                "Rank": 2,
                "Stock": "2454",
                "Signal": "BUY",
                "Score": 6.0,
                "Close": 1200.0,
                "Volume_Ratio": 2.5,
                "RSI": 58.0,
                "Analysis": "volume",
                "Status": "OK",
                "Error": "",
            },
            {
                "Rank": 3,
                "Stock": "2317",
                "Signal": "WATCH",
                "Score": 5.0,
                "Close": 180.0,
                "Volume_Ratio": 1.2,
                "RSI": 54.0,
                "Analysis": "watch",
                "Status": "OK",
                "Error": "",
            },
            {
                "Rank": 4,
                "Stock": "2308",
                "Signal": "HOLD",
                "Score": 8.0,
                "Close": 300.0,
                "Volume_Ratio": 4.0,
                "RSI": 70.0,
                "Analysis": "hold",
                "Status": "OK",
                "Error": "",
            },
            {
                "Rank": None,
                "Stock": "9999",
                "Signal": "",
                "Score": None,
                "Close": None,
                "Volume_Ratio": None,
                "RSI": None,
                "Analysis": "",
                "Status": "ERROR",
                "Error": "bad stock",
            },
        ]
    )


class DailyReportTest(unittest.TestCase):
    def test_build_summary(self) -> None:
        ranking = _ranking_df()
        candidates = daily_report.filter_candidates(ranking, min_score=4, top=20)

        summary = daily_report.build_summary(ranking, candidates, report_date="2026-06-19")

        self.assertEqual(summary.loc[0, "Report Date"], "2026-06-19")
        self.assertEqual(summary.loc[0, "Stocks Scanned"], 5)
        self.assertEqual(summary.loc[0, "Candidates"], 3)
        self.assertEqual(summary.loc[0, "BUY Count"], 2)
        self.assertEqual(summary.loc[0, "WATCH Count"], 1)
        self.assertEqual(summary.loc[0, "Average Score"], 5.67)

    def test_candidate_filter(self) -> None:
        result = daily_report.filter_candidates(
            _ranking_df(),
            signals=("BUY", "WATCH"),
            min_score=5,
            top=20,
        )

        self.assertEqual(result["Stock"].tolist(), ["2454", "2330", "2317"])
        self.assertNotIn("2308", result["Stock"].tolist())
        self.assertEqual(result["Rank"].tolist(), [1, 2, 3])

    def test_sorting_by_score_then_volume_ratio(self) -> None:
        result = daily_report.filter_candidates(_ranking_df(), min_score=4, top=2)

        self.assertEqual(result["Stock"].tolist(), ["2454", "2330"])

    def test_error_sheet_contains_failed_rows(self) -> None:
        ranking = _ranking_df()
        candidates = daily_report.filter_candidates(ranking)
        summary = daily_report.build_summary(ranking, candidates, report_date="2026-06-19")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "daily_report.xlsx"
            output = daily_report.export_daily_report(summary, candidates, ranking, str(path))
            workbook = load_workbook(output, read_only=True)
            rows = list(workbook["Errors"].iter_rows(values_only=True))
            workbook.close()

        self.assertGreaterEqual(len(rows), 2)
        self.assertIn("9999", rows[1])

    def test_export_excel_creates_expected_sheets(self) -> None:
        ranking = _ranking_df()
        candidates = daily_report.filter_candidates(ranking)
        summary = daily_report.build_summary(ranking, candidates, report_date="2026-06-19")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "daily_report.xlsx"
            output = daily_report.export_daily_report(summary, candidates, ranking, str(path))
            workbook = load_workbook(output, read_only=True)
            sheetnames = workbook.sheetnames
            workbook.close()

        self.assertIn("Summary", sheetnames)
        self.assertIn("Candidates", sheetnames)
        self.assertIn("All", sheetnames)
        self.assertIn("Errors", sheetnames)


if __name__ == "__main__":
    unittest.main()
