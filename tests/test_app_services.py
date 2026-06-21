import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

import app_services
from scanner import ScanConfig


class AppServicesTest(unittest.TestCase):
    def test_doctor_service_returns_rows_summary_and_failure_flag(self) -> None:
        rows = [{"Check": "Python", "Status": "PASS", "Message": "ok"}]
        summary = {"PASS": 1, "WARNING": 0, "FAIL": 0}
        with patch.object(app_services.doctor_module, "run_doctor", return_value=rows) as run_mock:
            with patch.object(app_services.doctor_module, "summarize", return_value=summary) as summary_mock:
                with patch.object(app_services.doctor_module, "has_failures", return_value=False) as fail_mock:
                    result = app_services.doctor_service(live=True)

        run_mock.assert_called_once_with(live=True)
        summary_mock.assert_called_once_with(rows)
        fail_mock.assert_called_once_with(rows)
        self.assertEqual(result["rows"], rows)
        self.assertEqual(result["summary"], summary)
        self.assertFalse(result["has_failures"])

    def test_stock_list_smoke_check_service_returns_result(self) -> None:
        expected = {"status": "PASS", "twse_count": 900}
        with patch.object(app_services.stock_list_smoke_check_module, "run_smoke_check", return_value=expected) as mocked:
            result = app_services.stock_list_smoke_check_service(min_twse=10, min_tpex=20, min_all=30)

        mocked.assert_called_once_with(min_twse=10, min_tpex=20, min_all=30)
        self.assertIs(result, expected)

    def test_price_data_smoke_check_service_returns_results(self) -> None:
        rows = [{"Check": "yfinance TWSE", "Status": "PASS"}]
        with patch.object(app_services.price_data_smoke_check_module, "run_smoke_check", return_value=rows) as mocked:
            result = app_services.price_data_smoke_check_service(
                twse_stock="2330",
                tpex_stock="8069",
                period="1mo",
                interval="1d",
            )

        mocked.assert_called_once_with(
            twse_stock="2330",
            tpex_stock="8069",
            period="1mo",
            interval="1d",
        )
        self.assertEqual(result["results"], rows)
        self.assertFalse(result["failed"])

    def test_single_stock_analysis_service_calls_analysis_and_backtest(self) -> None:
        signal_df = pd.DataFrame({"Close": [100, 101], "Signal": ["HOLD", "BUY"]})
        summary = {"Latest Close": 101, "Signal": "BUY"}
        analysis_result = SimpleNamespace(signal_df=signal_df, summary=summary, symbol="2330.TW")
        backtest_result = {"Total Return %": 1.2}
        with patch.object(app_services.analysis_module, "analyze_stock", return_value=analysis_result) as analysis_mock:
            with patch.object(app_services.backtest_module, "run_backtest", return_value=backtest_result) as backtest_mock:
                result = app_services.single_stock_analysis_service(
                    "2330",
                    period="2y",
                    interval="1d",
                    auto_adjust=True,
                    force_refresh=True,
                    stop_loss_pct=8,
                    take_profit_pct=20,
                    max_hold_days=30,
                    position_size=0.5,
                )

        analysis_mock.assert_called_once_with(
            "2330",
            period="2y",
            interval="1d",
            auto_adjust=True,
            force_refresh=True,
        )
        backtest_mock.assert_called_once()
        backtest_kwargs = backtest_mock.call_args.kwargs
        self.assertEqual(backtest_kwargs["stop_loss_pct"], 8)
        self.assertEqual(backtest_kwargs["take_profit_pct"], 20)
        self.assertEqual(backtest_kwargs["max_hold_days"], 30)
        self.assertEqual(backtest_kwargs["position_size"], 0.5)
        self.assertIs(result["analysis"], analysis_result)
        self.assertIs(result["signal"], signal_df)
        self.assertEqual(result["summary"], summary)
        self.assertEqual(result["backtest"], backtest_result)
        self.assertEqual(result["symbol"], "2330.TW")
        self.assertIsNone(result["excel_path"])
        self.assertIsNone(result["chart_path"])

    def test_single_stock_analysis_service_exports_excel_and_chart(self) -> None:
        signal_df = pd.DataFrame({"Close": [100]})
        summary = {"Latest Close": 100}
        analysis_result = SimpleNamespace(signal_df=signal_df, summary=summary, symbol="2330.TW")
        with patch.object(app_services.analysis_module, "analyze_stock", return_value=analysis_result):
            with patch.object(app_services.backtest_module, "run_backtest", return_value={"Total Return %": 0}):
                with patch.object(app_services.plotter_module, "plot_stock_chart") as chart_mock:
                    with patch.object(app_services.report_module, "export_excel_report", return_value=Path("output/report.xlsx")) as report_mock:
                        result = app_services.single_stock_analysis_service(
                            "2330",
                            export_excel=True,
                            save_chart=True,
                        )

        chart_mock.assert_called_once()
        report_mock.assert_called_once()
        self.assertEqual(result["chart_path"], app_services.OUTPUT_DIR / "2330_chart.png")
        self.assertEqual(result["excel_path"], Path("output/report.xlsx"))

    def test_cache_summary_service_returns_summary(self) -> None:
        summary = pd.DataFrame([{"File": "cache.csv"}])
        with patch.object(app_services.cache_manager_module, "cache_summary", return_value=summary) as mocked:
            result = app_services.cache_summary_service()

        mocked.assert_called_once_with()
        self.assertIs(result["summary"], summary)
        self.assertEqual(result["count"], 1)
        self.assertFalse(result["empty"])

    def test_cache_clear_service_returns_count(self) -> None:
        with patch.object(app_services.cache_manager_module, "clear_cache", return_value=3) as mocked:
            result = app_services.cache_clear_service()

        mocked.assert_called_once_with()
        self.assertEqual(result["cleared"], 3)

    def test_new_service_errors_are_wrapped_with_clear_messages(self) -> None:
        error_cases = [
            ("Doctor", lambda: app_services.doctor_service(), app_services.doctor_module, "run_doctor"),
            (
                "Stock list smoke check",
                lambda: app_services.stock_list_smoke_check_service(),
                app_services.stock_list_smoke_check_module,
                "run_smoke_check",
            ),
            (
                "Price data smoke check",
                lambda: app_services.price_data_smoke_check_service(),
                app_services.price_data_smoke_check_module,
                "run_smoke_check",
            ),
            (
                "Single stock analysis",
                lambda: app_services.single_stock_analysis_service("2330"),
                app_services.analysis_module,
                "analyze_stock",
            ),
            ("Cache summary", lambda: app_services.cache_summary_service(), app_services.cache_manager_module, "cache_summary"),
            ("Cache clear", lambda: app_services.cache_clear_service(), app_services.cache_manager_module, "clear_cache"),
        ]
        for action, caller, module, function_name in error_cases:
            with self.subTest(action=action):
                with patch.object(module, function_name, side_effect=RuntimeError("boom")):
                    with self.assertRaisesRegex(app_services.AppServiceError, f"{action} failed: boom"):
                        caller()

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

    def test_stock_list_updater_service_calls_update_stock_list(self) -> None:
        stocks = pd.DataFrame([{"Stock": "2330"}, {"Stock": "8069"}])
        with patch.object(
            app_services.stock_list_updater_module,
            "update_stock_list",
            return_value=(stocks, Path("stocks.txt")),
        ) as mocked:
            result = app_services.stock_list_updater_service(
                market="all",
                output="stocks.txt",
                allow_partial=True,
                min_common_stocks=10,
            )

        mocked.assert_called_once_with(
            market="all",
            output="stocks.txt",
            allow_partial=True,
            min_common_stocks=10,
        )
        self.assertIs(result["stocks"], stocks)
        self.assertEqual(result["output_path"], Path("stocks.txt"))
        self.assertEqual(result["count"], 2)

    def test_stock_list_updater_service_omits_none_min_common_stocks(self) -> None:
        stocks = pd.DataFrame([{"Stock": "2330"}])
        with patch.object(
            app_services.stock_list_updater_module,
            "update_stock_list",
            return_value=(stocks, Path("stocks.txt")),
        ) as mocked:
            app_services.stock_list_updater_service()

        mocked.assert_called_once_with(
            market="all",
            output="stocks.txt",
            allow_partial=False,
        )

    def test_stock_list_updater_service_wraps_errors(self) -> None:
        with patch.object(
            app_services.stock_list_updater_module,
            "update_stock_list",
            side_effect=RuntimeError("official API down"),
        ):
            with self.assertRaisesRegex(
                app_services.AppServiceError,
                "Stock list updater failed: official API down",
            ):
                app_services.stock_list_updater_service()

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
