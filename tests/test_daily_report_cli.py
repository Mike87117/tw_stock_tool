import unittest
from unittest.mock import patch
import sys
import pandas as pd
from pathlib import Path

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
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertEqual(cm.exception.code, 1)

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
                with self.assertRaises(SystemExit) as cm:
                    main()
                    
        self.assertEqual(cm.exception.code, 1)
        output_str = captured_output.getvalue()
        self.assertIn("Error:", output_str)
        self.assertIn("locked", output_str)

if __name__ == "__main__":
    unittest.main()
