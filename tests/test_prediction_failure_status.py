from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from openpyxl import load_workbook

from tw_stock_tool.cli import twstock_cli
from tw_stock_tool.ml import ai_stock_scanner, baseline_ml_model
from tw_stock_tool.ml.ml_dataset import FEATURE_COLUMNS
from tw_stock_tool.reports import ai_prediction_report


def _frames(errors: list[str]) -> dict[str, pd.DataFrame]:
    detail = pd.DataFrame([
        {"Window": i, "Accuracy": 0.75 if not error else None,
         "F1": 0.6 if not error else None, "Error": error}
        for i, error in enumerate(errors, 1)
    ], columns=["Window", "Accuracy", "F1", "Error"])
    return ai_prediction_report.build_report_frames(
        detail, stock_id="2330", period="1y", horizon=1,
        train_size=10, test_size=5, step_size=None,
    )


class PredictionFailureStatusTest(unittest.TestCase):
    def test_summary_distinguishes_success_partial_failure_and_no_windows(self):
        for errors, expected in ((["", ""], "OK"), (["", "model failed"], "PARTIAL"),
                                 (["model failed", "model failed"], "ERROR"), ([], "ERROR")):
            with self.subTest(errors=errors):
                frames = _frames(errors)
                summary = frames["Summary"].iloc[0]
                self.assertEqual(summary["Status"], expected)
                self.assertEqual(summary["Windows"], len(errors))
                self.assertEqual(summary["Error Windows"], sum(bool(error) for error in errors))
                if expected == "ERROR":
                    self.assertTrue(pd.isna(summary["Avg Accuracy"]))
                    self.assertTrue(pd.isna(summary["Avg F1"]))
                    self.assertTrue(summary["Error"])
                else:
                    self.assertEqual(summary["Avg Accuracy"], 0.75)
                if expected == "PARTIAL":
                    self.assertIn("model failed", summary["Error"])
                    self.assertEqual(len(frames["Errors"]), 1)

    def test_failed_stock_has_no_rank_and_partial_stock_keeps_valid_metrics(self):
        rows = [ai_stock_scanner._summary_to_row(stock, _frames(errors)["Summary"])
                for stock, errors in (("failed", ["model failed"]),
                                      ("partial", ["", "model failed"]), ("ok", [""]))]
        result = ai_stock_scanner.rank_ai_stock_results(rows).set_index("Stock")
        self.assertTrue(pd.isna(result.loc["failed", "Rank"]))
        self.assertTrue(pd.isna(result.loc["failed", "Avg F1"]))
        self.assertEqual(result.loc["failed", "Status"], "ERROR")
        self.assertIn("model failed", result.loc["failed", "Error"])
        self.assertEqual(result.loc["partial", "Status"], "PARTIAL")
        self.assertEqual(result.loc["partial", "Avg F1"], 0.6)
        self.assertEqual(result.loc["ok", "Rank"], 1)
        self.assertEqual(result.loc["partial", "Rank"], 2)

    def test_empty_report_is_unranked_error(self):
        row = ai_stock_scanner._summary_to_row("2330", _frames([])["Summary"])
        result = ai_stock_scanner.rank_ai_stock_results([row])
        self.assertEqual(result.iloc[0]["Status"], "ERROR")
        self.assertTrue(pd.isna(result.iloc[0]["Rank"]))

    def test_real_model_failure_propagates_to_report_and_scanner_cli(self):
        dataset = pd.DataFrame({FEATURE_COLUMNS[0]: range(30), "Target_Up_1D": [True, False] * 15},
                               index=pd.date_range("2026-01-01", periods=30))
        shared = ["--horizon", "1", "--train-size", "10", "--test-size", "5",
                  "--n-estimators", "2", "--random-state", "-1"]
        with tempfile.TemporaryDirectory() as temporary:
            report_path = Path(temporary) / "report.xlsx"
            ranking_path = Path(temporary) / "ranking.xlsx"
            for route, destination in ((["ai-report", "--stock", "2330", *shared, "--output-excel"], report_path),
                                       (["ai-scan", "--stocks", "2330", *shared, "--output"], ranking_path)):
                with self.subTest(route=route[0]), patch.object(baseline_ml_model, "build_ml_dataset", return_value=dataset):
                    with redirect_stdout(StringIO()) as output:
                        status = twstock_cli.main([*route, str(destination)])
                    self.assertEqual(status, 1)
                    self.assertIn("Error:", output.getvalue())
                    self.assertTrue(destination.exists())
            workbook = load_workbook(report_path, read_only=True)
            try:
                summary_rows = list(workbook["Summary"].values)
                summary = dict(zip(summary_rows[0], summary_rows[1]))
                self.assertEqual(summary["Windows"], 3)
                self.assertEqual(summary["Error Windows"], 3)
                self.assertEqual(summary["Status"], "ERROR")
                self.assertIsNone(summary["Avg Accuracy"])
                self.assertIn("random_state", summary["Error"])
            finally:
                workbook.close()

    def test_partial_prediction_cli_succeeds_with_visible_warning(self):
        args = ai_prediction_report._parse_args(["--stock", "2330"])
        with patch.object(ai_prediction_report, "_parse_args", return_value=args), \
             patch.object(ai_prediction_report, "run_ai_prediction_report", return_value=_frames(["", "model failed"])), \
             redirect_stdout(StringIO()) as output:
            self.assertIsNone(ai_prediction_report.main())
        self.assertIn("Warning:", output.getvalue())
        self.assertIn("model failed", output.getvalue())

    def test_partial_scanner_cli_succeeds_with_visible_warning(self):
        args = ai_stock_scanner._parse_args(["--stocks", "2330"])
        row = ai_stock_scanner._summary_to_row("2330", _frames(["", "model failed"])["Summary"])
        with patch.object(ai_stock_scanner, "_parse_args", return_value=args), \
             patch.object(ai_stock_scanner, "scan_ai_stocks", return_value=ai_stock_scanner.rank_ai_stock_results([row])), \
             redirect_stdout(StringIO()) as output:
            self.assertIsNone(ai_stock_scanner.main())
        self.assertIn("Warning:", output.getvalue())


if __name__ == "__main__":
    unittest.main()
