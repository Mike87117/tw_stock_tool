import unittest
from unittest.mock import patch
import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tw_stock_tool.cli import daily_report_cli
from tw_stock_tool.cli.daily_report_cli import _parse_args, main

class TestDailyReportCli(unittest.TestCase):

    def test_parse_args_defaults(self):
        args = _parse_args([])
        self.assertEqual(args.stocks, None)
        self.assertEqual(args.stock_market, "all")
        self.assertEqual(args.output_dir, "output")
        self.assertEqual(args.output_md, None)

    def test_parse_args_custom(self):
        args = _parse_args([
            "--stocks", "2330", "2317",
            "--output-md", "test.md"
        ])
        self.assertEqual(args.stocks, ["2330", "2317"])
        self.assertEqual(args.output_md, "test.md")

    @patch("tw_stock_tool.cli.daily_report_cli.render_daily_report_markdown")
    @patch("tw_stock_tool.cli.daily_report_cli.build_daily_report_data")
    @patch("tw_stock_tool.cli.daily_report_cli.build_data_limitations_from_ranking")
    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_report")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids")
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_e2e_mvp_execution_no_output_md(self, mock_open, mock_mkdir, mock_collect, mock_run_daily, mock_build_limitations, mock_build, mock_render):
        mock_collect.return_value = ["2330"]
        summary_df = pd.DataFrame([{"Stocks Scanned": 1}])
        candidates_df = pd.DataFrame([{"Stock": "2330", "Score": 5}])
        mock_run_daily.return_value = (summary_df, candidates_df, pd.DataFrame(), None)
        mock_build_limitations.return_value = ["limit1"]
        mock_build.return_value = {"dummy": "data"}
        mock_render.return_value = "# Markdown Report"

        test_args = ["--stocks", "2330"]
        with patch.object(sys, "argv", ["daily_report_cli.py"] + test_args):
            main()

        # Check build_data_limitations_from_ranking was called
        mock_build_limitations.assert_called_once()
        # Check that data_limitations was passed to build_daily_report_data
        called_kwargs = mock_build.call_args[1]
        self.assertEqual(called_kwargs.get("data_limitations"), ["limit1"])

        # output_md should default to output/daily_report.md
        mock_open.assert_called_once_with(Path("output/daily_report.md"), "w", encoding="utf-8")
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("tw_stock_tool.cli.daily_report_cli.render_daily_report_markdown")
    @patch("tw_stock_tool.cli.daily_report_cli.build_daily_report_data")
    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_report")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids")
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_e2e_mvp_execution_output_md_empty(self, mock_open, mock_mkdir, mock_collect, mock_run_daily, mock_build, mock_render):
        mock_collect.return_value = ["2330"]
        mock_run_daily.return_value = (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None)

        test_args = ["--stocks", "2330", "--output-md"]
        with patch.object(sys, "argv", ["daily_report_cli.py"] + test_args):
            main()

        mock_open.assert_called_once_with(Path("output/daily_report.md"), "w", encoding="utf-8")

    @patch("tw_stock_tool.cli.daily_report_cli.render_daily_report_markdown")
    @patch("tw_stock_tool.cli.daily_report_cli.build_daily_report_data")
    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_report")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids")
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_e2e_mvp_execution_output_dir(self, mock_open, mock_mkdir, mock_collect, mock_run_daily, mock_build, mock_render):
        mock_collect.return_value = ["2330"]
        mock_run_daily.return_value = (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None)

        test_args = ["--stocks", "2330", "--output-dir", "reports"]
        with patch.object(sys, "argv", ["daily_report_cli.py"] + test_args):
            main()

        mock_open.assert_called_once_with(Path("reports/daily_report.md"), "w", encoding="utf-8")

    @patch("tw_stock_tool.cli.daily_report_cli.render_daily_report_markdown")
    @patch("tw_stock_tool.cli.daily_report_cli.build_daily_report_data")
    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_report")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids")
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_e2e_mvp_execution_output_md_custom(self, mock_open, mock_mkdir, mock_collect, mock_run_daily, mock_build, mock_render):
        mock_collect.return_value = ["2330"]
        mock_run_daily.return_value = (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None)

        test_args = ["--stocks", "2330", "--output-md", "custom/report.md"]
        with patch.object(sys, "argv", ["daily_report_cli.py"] + test_args):
            main()

        mock_open.assert_called_once_with(Path("custom/report.md"), "w", encoding="utf-8")

    @patch("tw_stock_tool.cli.daily_report_cli.build_daily_report_data")
    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_report")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids")
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_daily_report_cli_smoke_offline(self, mock_open, mock_mkdir, mock_collect, mock_run_daily, mock_build):
        # Mocks collect_stock_ids, run_daily_report, and build_daily_report_data to ensure no live network calls
        mock_collect.return_value = ["2330"]
        mock_run_daily.return_value = (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None)
        mock_build.return_value = {"Report Date": "2023-01-01"}

        test_args = ["--stocks", "2330", "--output-md", "smoke_test.md"]
        with patch.object(sys, "argv", ["daily_report_cli.py"] + test_args):
            main()

        # Verify run_daily_report is called with output=None
        mock_run_daily.assert_called_once_with(
            stock_ids=["2330"],
            period='1y',
            interval='1d',
            signals=['BUY', 'WATCH'],
            min_score=4.0,
            top=20,
            force_refresh=False,
            auto_adjust=False,
            output=None,
            progress=True
        )

        # Verify Markdown file is written
        mock_open.assert_called_once_with(Path("smoke_test.md"), "w", encoding="utf-8")

        # Verify written content
        written_content = "".join(call.args[0] for call in mock_open().write.call_args_list)

        # Research-only disclaimer appears in generated Markdown
        self.assertIn("This report is for research purposes only and does not constitute investment advice.", written_content)

        # No banned investment recommendation wording appears
        banned_words = ["buy recommendation", "sell recommendation", "guaranteed", "profit opportunity", "best stocks to buy"]
        for word in banned_words:
            self.assertNotIn(word.lower(), written_content.lower())

    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids")
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_report")
    @patch("tw_stock_tool.cli.daily_report_cli.build_data_limitations_from_ranking")
    @patch("tw_stock_tool.cli.daily_report_cli.build_daily_report_data")
    @patch("tw_stock_tool.cli.daily_report_cli.render_daily_report_markdown")
    def test_e2e_mvp_execution_output_excel(self, mock_render, mock_build, mock_build_limitations, mock_run_daily, mock_open, mock_mkdir, mock_collect):
        mock_collect.return_value = ["2330"]
        summary_df = pd.DataFrame([{"Stocks Scanned": 1}])
        candidates_df = pd.DataFrame([{"Stock": "2330", "Score": 5}])
        mock_run_daily.return_value = (summary_df, candidates_df, pd.DataFrame(), None)
        mock_build_limitations.return_value = []
        mock_build.return_value = {"dummy": "data"}
        mock_render.return_value = "# Markdown Report"

        test_args = ["--stocks", "2330", "--output-excel", "custom_excel.xlsx"]
        with patch.object(sys, "argv", ["daily_report_cli.py"] + test_args):
            main()

        # output_excel should be passed to run_daily_report
        mock_run_daily.assert_called_once_with(
            stock_ids=["2330"],
            period='1y',
            interval='1d',
            signals=['BUY', 'WATCH'],
            min_score=4.0,
            top=20,
            force_refresh=False,
            auto_adjust=False,
            output="custom_excel.xlsx",
            progress=True
        )

    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids")
    def test_no_stocks_exits(self, mock_collect):
        mock_collect.return_value = []
        with patch.object(sys, "argv", ["daily_report_cli.py", "--stocks"]):
            result = main()
        self.assertEqual(result, 1)

    @patch("tw_stock_tool.cli.daily_report_cli.render_daily_report_markdown")
    @patch("tw_stock_tool.cli.daily_report_cli.build_daily_report_data")
    @patch("tw_stock_tool.cli.daily_report_cli.build_data_limitations_from_ranking")
    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_report")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids")
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_daily_report_cli_write_failure(self, mock_open, mock_mkdir, mock_collect, mock_run_daily, mock_build_limitations, mock_build, mock_render):
        from io import StringIO
        mock_collect.return_value = ["2330"]
        mock_run_daily.return_value = (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None)
        mock_build_limitations.return_value = []
        mock_build.return_value = {}
        mock_render.return_value = "# Report"

        mock_open.side_effect = PermissionError("locked")

        test_args = ["--stocks", "2330", "--output-md"]
        captured_output = StringIO()

        with patch.object(sys, "argv", ["daily_report_cli.py"] + test_args):
            with patch("sys.stdout", captured_output):
                result = main()

        self.assertEqual(result, 1)
        output_str = captured_output.getvalue()
        self.assertIn("Error:", output_str)
        self.assertIn("locked", output_str)

class DailyReportValidationCliTest(unittest.TestCase):
    def test_validation_parser_defaults_and_invalid_values(self) -> None:
        args = _parse_args([])
        self.assertEqual(args.validate_top, 0)
        self.assertEqual(args.validation_strategy, "ma_cross")
        self.assertEqual(args.validation_initial_capital, 100000)
        self.assertEqual(args.validation_position_size, 1.0)
        for option in (
            ["--validate-top", "-1"],
            ["--validation-initial-capital", "0"],
            ["--validation-fee-rate", "-0.1"],
            ["--validation-tax-rate", "nan"],
            ["--validation-position-size", "1.1"],
            ["--validation-strategy", "invalid"],
        ):
            with self.assertRaises(SystemExit) as raised:
                _parse_args(option)
            self.assertEqual(raised.exception.code, 2)

    @patch("tw_stock_tool.cli.daily_report_cli.run_candidate_backtest_validation")
    @patch("tw_stock_tool.cli.daily_report_cli.render_daily_report_markdown", return_value="# Report")
    @patch("tw_stock_tool.cli.daily_report_cli.build_daily_report_data", return_value={})
    @patch("tw_stock_tool.cli.daily_report_cli.build_data_limitations_from_ranking", return_value=[])
    @patch("tw_stock_tool.cli.daily_report_cli.run_daily_report")
    @patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids", return_value=["2330"])
    @patch("tw_stock_tool.cli.daily_report_cli.Path.mkdir")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_enabled_validation_forwards_options_and_report_data(
        self,
        mock_open,
        mock_mkdir,
        mock_collect,
        mock_run_daily,
        mock_limitations,
        mock_build,
        mock_render,
        mock_validate,
    ) -> None:
        mock_run_daily.return_value = (pd.DataFrame(), pd.DataFrame([{"Stock": "2330"}]), pd.DataFrame(), None)
        highlights = pd.DataFrame([{"Status": "OK"}])
        mock_validate.return_value = (highlights, ["validation limit"])
        with patch.object(sys, "argv", [
            "daily_report_cli.py", "--stocks", "2330", "--validate-top", "1",
            "--validation-strategy", "score", "--validation-initial-capital", "200000",
            "--validation-fee-rate", "0", "--validation-tax-rate", "0.001",
            "--validation-position-size", "0.5",
        ]):
            result = main()

        self.assertIsNone(result)
        self.assertEqual(mock_validate.call_args.args[0]["Stock"].tolist(), ["2330"])
        self.assertEqual(mock_validate.call_args.kwargs["strategy"], "score")
        self.assertEqual(mock_validate.call_args.kwargs["initial_capital"], 200000.0)
        self.assertEqual(mock_validate.call_args.kwargs["position_size"], 0.5)
        self.assertEqual(mock_build.call_args.kwargs["backtest_highlights"].equals(highlights), True)
        self.assertIn("validation limit", mock_build.call_args.kwargs["data_limitations"])
        self.assertIn("next-bar Open execution assumptions", mock_build.call_args.kwargs["risk_notes"][0])

class DailyReportValidationCliStructureTest(unittest.TestCase):
    def _run_main(self, argv, validation_result=None, scan_limits=None):
        from io import StringIO

        with patch.object(sys, "argv", ["daily_report_cli.py", *argv]), patch.object(
            sys, "stdout", StringIO()
        ) as stdout, patch("tw_stock_tool.cli.daily_report_cli.collect_stock_ids", return_value=["2330"]), patch(
            "tw_stock_tool.cli.daily_report_cli.run_daily_report",
            return_value=(pd.DataFrame(), pd.DataFrame([{"Stock": "2330"}]), pd.DataFrame(), None),
        ), patch(
            "tw_stock_tool.cli.daily_report_cli.build_data_limitations_from_ranking",
            return_value=scan_limits if scan_limits is not None else [],
        ), patch("tw_stock_tool.cli.daily_report_cli.build_daily_report_data", return_value={}) as build, patch(
            "tw_stock_tool.cli.daily_report_cli.render_daily_report_markdown", return_value="# Report"
        ), patch("tw_stock_tool.cli.daily_report_cli.run_candidate_backtest_validation") as validate, patch(
            "tw_stock_tool.cli.daily_report_cli.Path.mkdir"
        ), patch("builtins.open", new_callable=unittest.mock.mock_open):
            if validation_result is not None:
                validate.return_value = validation_result
            result = main()
        return result, build, validate, stdout.getvalue()

    def test_default_path_is_scan_only_with_empty_highlights_and_no_validation_risk(self) -> None:
        result, build, validate, _ = self._run_main(["--stocks", "2330"])
        self.assertIsNone(result)
        validate.assert_not_called()
        self.assertEqual(build.call_args.kwargs["backtest_highlights"], [])
        self.assertEqual(build.call_args.kwargs["risk_notes"], [])

    def test_enabled_empty_validation_forwards_every_option_and_preserves_limits(self) -> None:
        empty = pd.DataFrame(columns=["Status"])
        result, build, validate, output = self._run_main(
            [
                "--stocks", "2330", "--validate-top", "4", "--validation-strategy", "score",
                "--period", "2y", "--interval", "1wk", "--auto-adjust", "--force-refresh",
                "--validation-initial-capital", "200000", "--validation-fee-rate", "0.001",
                "--validation-tax-rate", "0.002", "--validation-position-size", "0.5",
            ],
            validation_result=(empty, ["validation limit"]),
            scan_limits=["scan limit"],
        )
        self.assertIsNone(result)
        self.assertEqual(validate.call_args.args[0]["Stock"].tolist(), ["2330"])
        self.assertEqual(validate.call_args.kwargs, {
            "validate_top": 4, "strategy": "score", "period": "2y", "interval": "1wk",
            "auto_adjust": True, "force_refresh": True, "initial_capital": 200000.0,
            "fee_rate": 0.001, "tax_rate": 0.002, "position_size": 0.5,
        })
        self.assertEqual(build.call_args.kwargs["backtest_highlights"].columns.tolist(), ["Status"])
        self.assertEqual(build.call_args.kwargs["data_limitations"], ["scan limit", "validation limit"])
        self.assertIn("selected 0, success 0, failed 0", output)
        self.assertIn("next-bar Open execution assumptions", build.call_args.kwargs["risk_notes"][0])

class DailyReportWalkForwardCliTest(unittest.TestCase):
    def test_walk_forward_defaults_and_custom_options(self) -> None:
        defaults = _parse_args([])
        self.assertEqual(defaults.walk_forward_top, 0)
        self.assertEqual(defaults.walk_forward_train_days, 126)
        self.assertEqual(defaults.walk_forward_test_days, 63)
        self.assertIsNone(defaults.walk_forward_step_days)
        self.assertEqual(defaults.walk_forward_sort_by, "Train Sharpe Ratio")

        args = _parse_args([
            "--validate-top", "3", "--walk-forward-top", "2",
            "--walk-forward-train-days", "10", "--walk-forward-test-days", "5",
            "--walk-forward-step-days", "3", "--walk-forward-sort-by", "Train CAGR %",
        ])
        self.assertEqual(args.walk_forward_top, 2)
        self.assertEqual(args.walk_forward_train_days, 10)
        self.assertEqual(args.walk_forward_test_days, 5)
        self.assertEqual(args.walk_forward_step_days, 3)
        self.assertEqual(args.walk_forward_sort_by, "Train CAGR %")

    def test_walk_forward_parser_rejects_invalid_global_configuration(self) -> None:
        invalid = [
            ["--walk-forward-top", "-1"],
            ["--walk-forward-train-days", "0"],
            ["--walk-forward-test-days", "0"],
            ["--walk-forward-step-days", "0"],
            ["--walk-forward-sort-by", "Test Sharpe Ratio"],
            ["--walk-forward-top", "1"],
            ["--validate-top", "1", "--walk-forward-top", "2"],
            ["--validate-top", "1", "--walk-forward-top", "1", "--validation-strategy", "macd"],
        ]
        for argv in invalid:
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as raised:
                _parse_args(argv)
            self.assertEqual(raised.exception.code, 2)
        self.assertEqual(_parse_args(["--validate-top", "1", "--validation-strategy", "macd"]).validation_strategy, "macd")

    def test_walk_forward_enabled_forwards_options_and_report_data(self) -> None:
        wf = pd.DataFrame([{"Stock": "2330", "Status": "PARTIAL", "Windows": 2}])
        with patch.object(
            daily_report_cli, "run_candidate_walk_forward_validation", return_value=(wf, ["wf limit"])
        ) as run_wf:
            result, build, validate, output = DailyReportValidationCliStructureTest()._run_main(
                [
                    "--stocks", "2330", "--validate-top", "2", "--walk-forward-top", "1",
                    "--validation-strategy", "score", "--period", "2y", "--interval", "1wk",
                    "--auto-adjust", "--force-refresh", "--walk-forward-train-days", "10",
                    "--walk-forward-test-days", "5", "--walk-forward-step-days", "3",
                    "--walk-forward-sort-by", "Train CAGR %", "--validation-initial-capital", "200000",
                    "--validation-fee-rate", "0.001", "--validation-tax-rate", "0.002",
                    "--validation-position-size", "0.5",
                ],
                validation_result=(pd.DataFrame([{"Status": "OK"}]), ["backtest limit"]),
                scan_limits=["scan limit"],
            )
        self.assertIsNone(result)
        self.assertEqual(run_wf.call_args.kwargs, {
            "walk_forward_top": 1, "strategy": "score", "period": "2y", "interval": "1wk",
            "auto_adjust": True, "force_refresh": True, "train_days": 10, "test_days": 5,
            "step_days": 3, "sort_by": "Train CAGR %", "initial_capital": 200000.0,
            "fee_rate": 0.001, "tax_rate": 0.002, "position_size": 0.5,
        })
        self.assertTrue(build.call_args.kwargs["walk_forward_highlights"].equals(wf))
        self.assertEqual(build.call_args.kwargs["data_limitations"], ["scan limit", "backtest limit", "wf limit"])
        self.assertIn("out-of-sample", " ".join(build.call_args.kwargs["risk_notes"]))
        self.assertIn("selected 1, OK 0, PARTIAL 1, ERROR 0", output)

    def test_empty_walk_forward_reports_zero_counts(self) -> None:
        empty = pd.DataFrame(columns=["Status"])
        with patch.object(
            daily_report_cli, "run_candidate_walk_forward_validation", return_value=(empty, ["skip limit"])
        ):
            result, build, _, output = DailyReportValidationCliStructureTest()._run_main(
                ["--stocks", "2330", "--validate-top", "1", "--walk-forward-top", "1"],
                validation_result=(pd.DataFrame([{"Status": "ERROR"}]), []),
            )
        self.assertIsNone(result)
        self.assertEqual(build.call_args.kwargs["walk_forward_highlights"].columns.tolist(), ["Status"])
        self.assertIn("selected 0, OK 0, PARTIAL 0, ERROR 0", output)

if __name__ == "__main__":
    unittest.main()
