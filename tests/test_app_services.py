import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import app_services
from scanner import ScanConfig


class AppServicesTest(unittest.TestCase):
    def test_clean_stocks_service_calls_run_clean_stocks(self) -> None:
        frames = (pd.DataFrame([{"File": "stocks.txt"}]), pd.DataFrame(), pd.DataFrame(), Path("report.xlsx"), Path("clean.txt"))
        with patch.object(app_services.clean_stocks_module, "run_clean_stocks", return_value=frames) as mocked:
            result = app_services.clean_stocks_service(
                "stocks.txt",
                period="5y",
                interval="1d",
                auto_adjust=True,
                force_refresh=True,
                output="out.xlsx",
                clean_file="clean.txt",
            )

        mocked.assert_called_once_with(
            file_path="stocks.txt",
            period="5y",
            interval="1d",
            auto_adjust=True,
            force_refresh=True,
            output="out.xlsx",
            clean_file="clean.txt",
        )
        self.assertEqual(result["report_path"], Path("report.xlsx"))
        self.assertEqual(result["clean_path"], Path("clean.txt"))

    def test_daily_report_service_calls_run_daily_report(self) -> None:
        frames = (pd.DataFrame([{"Candidates": 1}]), pd.DataFrame(), pd.DataFrame(), Path("daily.xlsx"))
        with patch.object(app_services.daily_report_module, "run_daily_report", return_value=frames) as mocked:
            result = app_services.daily_report_service(
                ["2330"],
                period="5y",
                interval="1d",
                signals=("BUY",),
                min_score=5,
                top=10,
                force_refresh=True,
                auto_adjust=True,
                output="daily.xlsx",
                progress=False,
            )

        mocked.assert_called_once_with(
            stock_ids=["2330"],
            period="5y",
            interval="1d",
            signals=("BUY",),
            min_score=5,
            top=10,
            force_refresh=True,
            auto_adjust=True,
            output="daily.xlsx",
            progress=False,
        )
        self.assertEqual(result["output_path"], Path("daily.xlsx"))

    def test_scan_stocks_service_calls_scanner(self) -> None:
        expected = pd.DataFrame([{"Stock": "2330"}])
        config = ScanConfig(period="5y", max_workers=2)
        callback = lambda *_: None
        with patch.object(app_services.scanner_module, "scan_stocks", return_value=expected) as mocked:
            result = app_services.scan_stocks_service(["2330"], config=config, progress_callback=callback)

        mocked.assert_called_once_with(["2330"], config=config, progress_callback=callback)
        self.assertIs(result, expected)

    def test_scan_stocks_with_options_builds_config(self) -> None:
        expected = pd.DataFrame([{"Stock": "2330"}])
        with patch.object(app_services.scanner_module, "scan_stocks", return_value=expected) as mocked:
            result = app_services.scan_stocks_with_options_service(
                ["2330"],
                period="5y",
                max_workers=3,
                min_score=4,
                signals=("BUY", "WATCH"),
                top=5,
            )

        args, kwargs = mocked.call_args
        self.assertEqual(args[0], ["2330"])
        self.assertEqual(kwargs["config"].period, "5y")
        self.assertEqual(kwargs["config"].max_workers, 3)
        self.assertEqual(kwargs["config"].min_score, 4)
        self.assertEqual(kwargs["config"].signals, ("BUY", "WATCH"))
        self.assertEqual(kwargs["config"].top, 5)
        self.assertIs(result, expected)

    def test_ai_stock_scanner_service_calls_scan_and_export(self) -> None:
        ranking = pd.DataFrame([{"Stock": "2330"}])
        with patch.object(app_services.ai_stock_scanner_module, "scan_ai_stocks", return_value=ranking) as scan_mock:
            with patch.object(app_services.ai_stock_scanner_module, "export_ai_stock_ranking", return_value=Path("ai.xlsx")) as export_mock:
                result = app_services.ai_stock_scanner_service(
                    ["2330"],
                    period="5y",
                    horizon=5,
                    train_size=252,
                    test_size=63,
                    workers=2,
                    output="ai.xlsx",
                )

        scan_mock.assert_called_once_with(
            stock_ids=["2330"],
            period="5y",
            horizon=5,
            train_size=252,
            test_size=63,
            step_size=None,
            force_refresh=False,
            dropna=True,
            n_estimators=100,
            random_state=42,
            workers=2,
        )
        export_mock.assert_called_once_with(ranking, "ai.xlsx")
        self.assertEqual(result["output_path"], Path("ai.xlsx"))

    def test_ai_prediction_report_service_calls_report_and_export(self) -> None:
        frames = {
            "Summary": pd.DataFrame([{"Stock": "2330"}]),
            "Detail": pd.DataFrame(),
            "Errors": pd.DataFrame(),
        }
        with patch.object(app_services.ai_prediction_report_module, "run_ai_prediction_report", return_value=frames) as run_mock:
            with patch.object(app_services.ai_prediction_report_module, "export_ai_prediction_report_excel", return_value=Path("report.xlsx")) as export_mock:
                result = app_services.ai_prediction_report_service(
                    "2330",
                    period="5y",
                    horizon=5,
                    output="report.xlsx",
                )

        run_mock.assert_called_once_with(
            stock_id="2330",
            period="5y",
            horizon=5,
            train_size=252,
            test_size=63,
            step_size=None,
            force_refresh=False,
            dropna=True,
            n_estimators=100,
            random_state=42,
        )
        export_mock.assert_called_once_with(frames, stock_id="2330", output="report.xlsx")
        self.assertIs(result["summary"], frames["Summary"])
        self.assertEqual(result["output_path"], Path("report.xlsx"))

    def test_service_errors_are_wrapped_with_clear_message(self) -> None:
        with patch.object(app_services.clean_stocks_module, "run_clean_stocks", side_effect=ValueError("bad file")):
            with self.assertRaisesRegex(app_services.AppServiceError, "Clean stocks failed: bad file"):
                app_services.clean_stocks_service("missing.txt")


if __name__ == "__main__":
    unittest.main()
