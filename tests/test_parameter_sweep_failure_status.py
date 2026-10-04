from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd
from openpyxl import load_workbook

from tw_stock_tool.backtesting import parameter_sweep
from tw_stock_tool.backtesting.backtest import run_backtest
from tw_stock_tool.cli import parameter_sweep_report, twstock_cli
from tw_stock_tool.reports.parameter_sweep_report import build_parameter_sweep_report_data


def _detail(errors: list[str]) -> pd.DataFrame:
    return pd.DataFrame([
        {"Strategy": "ma_cross", "Parameters": f"short={i}", "Error": error,
         "Sharpe Ratio": 99. if error else 1., "Total Return %": 99. if error else 5.}
        for i, error in enumerate(errors, 1)
    ], columns=["Strategy", "Parameters", "Error", "Sharpe Ratio", "Total Return %"])


class ParameterSweepFailureStatusTest(unittest.TestCase):
    def test_all_failed_results_cannot_select_a_best_row(self):
        detail = _detail(["backtest failed", "backtest failed"])
        data = build_parameter_sweep_report_data(detail)
        self.assertEqual(data["Summary"], {
            "Status": "ERROR", "Valid Rows": 0, "Error Rows": 2, "Error": "backtest failed",
        })
        self.assertIsNone(data["Best Row"])
        self.assertTrue(data["Top Results"].empty)
        pd.testing.assert_frame_equal(data["Results"], detail)

    def test_partial_failure_cannot_outrank_success(self):
        detail = _detail(["backtest failed", ""])
        original = detail.copy(deep=True)
        data = build_parameter_sweep_report_data(detail)
        self.assertEqual(data["Summary"]["Status"], "PARTIAL")
        self.assertEqual(data["Summary"]["Valid Rows"], 1)
        self.assertEqual(data["Summary"]["Error Rows"], 1)
        self.assertEqual(data["Best Row"]["Parameters"], "short=2")
        self.assertEqual(len(data["Top Results"]), 1)
        pd.testing.assert_frame_equal(detail, original)

    def test_empty_and_absent_results_are_errors(self):
        for result in (None, {}, pd.DataFrame(), {"Results": []}):
            with self.subTest(result=type(result)):
                data = build_parameter_sweep_report_data(result)
                self.assertEqual(data["Summary"]["Status"], "ERROR")
                self.assertIn("No parameter combinations", data["Summary"]["Error"])
                self.assertIsNone(data["Best Row"])

    def test_missing_or_invalid_ranking_metrics_do_not_select_a_best_row(self):
        for metric in (float("nan"), "invalid"):
            detail = _detail([""])
            detail["Sharpe Ratio"] = metric
            data = build_parameter_sweep_report_data(detail)
            self.assertIsNone(data["Best Row"])
            self.assertTrue(data["Top Results"].empty)

    def test_duplicate_dataframe_indices_do_not_duplicate_ranked_rows(self):
        detail = _detail(["", ""])
        detail.index = [0, 0]
        detail["Sharpe Ratio"] = ["1", "2"]
        data = build_parameter_sweep_report_data(detail)
        self.assertEqual(len(data["Top Results"]), 2)
        self.assertEqual(data["Best Row"]["Parameters"], "short=2")

    def test_successful_and_legacy_frames_remain_supported(self):
        for detail in (_detail(["", ""]), _detail(["", ""]).drop(columns="Error")):
            data = build_parameter_sweep_report_data(detail)
            self.assertEqual(data["Summary"]["Status"], "OK")
            self.assertEqual(data["Summary"]["Error Rows"], 0)
            self.assertEqual(len(data["Top Results"]), 2)

    def test_real_invalid_fee_fails_unified_cli_and_exports_diagnostics(self):
        prices = pd.DataFrame({"Open": [100.] * 30, "Close": [100.] * 30},
                              index=pd.date_range("2026-01-01", periods=30))
        with tempfile.TemporaryDirectory() as temporary:
            markdown = Path(temporary) / "report.md"
            excel = Path(temporary) / "report.xlsx"
            with patch.object(parameter_sweep, "analyze_stock", return_value=SimpleNamespace(signal_df=prices)), \
                 redirect_stdout(StringIO()) as output:
                status = twstock_cli.main([
                    "parameter-sweep", "--stock", "2330", "--strategy", "ma_cross",
                    "--fee-rate", "-0.01", "--ma-short-windows", "2", "--ma-long-windows", "5",
                    "--output-md", str(markdown), "--output-excel", str(excel),
                ])
            self.assertEqual(status, 1)
            self.assertIn("No valid parameter combinations", output.getvalue())
            self.assertIn("fee_rate must be greater than or equal to 0", output.getvalue())
            self.assertNotIn("Parameter sweep finished", output.getvalue())
            text = markdown.read_text(encoding="utf-8")
            self.assertIn("Status: ERROR", text)
            self.assertIn("No parameter sweep results.", text)
            self.assertIn("fee_rate must be greater than or equal to 0", text)
            workbook = load_workbook(excel, read_only=True)
            try:
                summary = dict(list(workbook["Summary"].values)[1:])
                self.assertEqual(summary["Status"], "ERROR")
                self.assertEqual(summary["Error Rows"], 1)
                self.assertEqual(len(list(workbook["Top Results"].values)), 1)
                self.assertEqual(len(list(workbook["Full Results"].values)), 2)
            finally:
                workbook.close()

    def test_both_cli_entrypoints_report_all_failure_and_empty_results(self):
        report_args = parameter_sweep_report._parse_args(["--stock", "2330", "--strategy", "ma_cross"])
        with patch("sys.argv", ["parameter_sweep", "--stock", "2330"]):
            legacy_args = parameter_sweep._parse_args()
        for module, args in ((parameter_sweep_report, report_args), (parameter_sweep, legacy_args)):
            for detail in (_detail(["backtest failed"]), _detail([])):
                with self.subTest(module=module.__name__, rows=len(detail)):
                    with patch.object(module, "_parse_args", return_value=args), \
                         patch.object(module, "run_parameter_sweep", return_value=detail), \
                         redirect_stdout(StringIO()) as output:
                        self.assertEqual(module.main(), 1)
                    self.assertIn("Error:", output.getvalue())
                    self.assertNotIn("Top In-Sample Strategy:", output.getvalue())
                    self.assertNotIn("Parameter sweep finished", output.getvalue())

    def test_both_cli_entrypoints_preserve_partial_and_successful_results(self):
        report_args = parameter_sweep_report._parse_args(["--stock", "2330", "--strategy", "ma_cross"])
        with patch("sys.argv", ["parameter_sweep", "--stock", "2330"]):
            legacy_args = parameter_sweep._parse_args()
        for module, args in ((parameter_sweep_report, report_args), (parameter_sweep, legacy_args)):
            for errors in (["", "backtest failed"], ["", ""]):
                with self.subTest(module=module.__name__, errors=errors):
                    with patch.object(module, "_parse_args", return_value=args), \
                         patch.object(module, "run_parameter_sweep", return_value=_detail(errors)), \
                         redirect_stdout(StringIO()) as output:
                        self.assertIsNone(module.main())
                    self.assertEqual("Warning:" in output.getvalue(), bool(errors[1]))

    def test_cli_help_explains_percentage_units(self):
        with redirect_stdout(StringIO()) as output, self.assertRaises(SystemExit) as caught:
            parameter_sweep_report._parse_args(["--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("5 for 5%", output.getvalue())
        self.assertNotIn("0.05 for 5%", output.getvalue())

    def test_cli_five_percent_stop_does_not_exit_on_point_one_percent_loss(self):
        prices = pd.DataFrame({
            "Open": [100., 100., 100., 99.9, 100.], "Close": [100., 100., 99.9, 100., 100.],
            "entry_signal": [True, False, False, False, False], "exit_signal": [False] * 5,
        }, index=pd.date_range("2026-01-01", periods=5))
        for value, reason in (("5", "SELL_EOD"), ("0.05", "SELL_STOP_LOSS")):
            args = parameter_sweep_report._parse_args(["--stock", "2330", "--strategy", "ma_cross", "--stop-loss-pct", value])
            result = run_backtest(prices, fee_rate=0, tax_rate=0, stop_loss_pct=args.stop_loss_pct)
            self.assertEqual(result["Trades"].iloc[0]["Exit Reason"], reason)


if __name__ == "__main__":
    unittest.main()
