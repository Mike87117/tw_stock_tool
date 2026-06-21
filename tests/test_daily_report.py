import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_collect_stock_ids_auto_stock_list_calls_updater_and_has_priority(self) -> None:
        updater_df = pd.DataFrame([{"Stock": "2330"}, {"Stock": "2454"}])
        with patch.object(
            daily_report.stock_list_updater_module,
            "update_stock_list",
            return_value=(updater_df, "stocks.txt"),
        ) as updater_mock:
            result = daily_report.collect_stock_ids(
                ["9999"],
                "ignored.txt",
                auto_stock_list=True,
                stock_market="twse",
                stock_list_output="stocks.txt",
                allow_partial_stock_list=True,
            )

        updater_mock.assert_called_once_with(
            market="twse",
            output="stocks.txt",
            allow_partial=True,
        )
        self.assertEqual(result, ["2330", "2454"])

    def test_parse_args_supports_auto_stock_list(self) -> None:
        args = daily_report._parse_args([
            "--auto-stock-list",
            "--stock-market",
            "tpex",
            "--stock-list-output",
            "stocks.txt",
            "--allow-partial-stock-list",
        ])

        self.assertTrue(args.auto_stock_list)
        self.assertEqual(args.stock_market, "tpex")
        self.assertEqual(args.stock_list_output, "stocks.txt")
        self.assertTrue(args.allow_partial_stock_list)

    def test_daily_report_updater_failure_does_not_run_report(self) -> None:
        args = daily_report._parse_args(["--auto-stock-list"])
        with patch.object(daily_report, "_parse_args", return_value=args):
            with patch.object(
                daily_report.stock_list_updater_module,
                "update_stock_list",
                side_effect=RuntimeError("updater down"),
            ):
                with patch.object(daily_report, "run_daily_report") as report_mock:
                    with patch("builtins.print"):
                        daily_report.main()

        report_mock.assert_not_called()

    def test_parse_args_supports_auto_adjust(self) -> None:
        args = daily_report._parse_args(["--file", "stocks.txt", "--auto-adjust"])

        self.assertTrue(args.auto_adjust)

    def test_parse_args_supports_no_auto_adjust(self) -> None:
        args = daily_report._parse_args(["--file", "stocks.txt", "--no-auto-adjust"])

        self.assertFalse(args.auto_adjust)


if __name__ == "__main__":
    unittest.main()
