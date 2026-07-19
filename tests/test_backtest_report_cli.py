import unittest
import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path

from tw_stock_tool.cli.backtest_report import _parse_args, _normalize_result, main


class TestBacktestReportCLI(unittest.TestCase):

    def test_parse_args(self):
        args = _parse_args(["--stock", "2330", "--strategy", "ma_cross"])
        self.assertEqual(args.stock, "2330")
        self.assertEqual(args.strategy, "ma_cross")
        self.assertIsNone(args.output_md)
        self.assertIsNone(args.output_excel)

        args = _parse_args(["--stock", "2330", "--strategy", "ma_cross", "--output-md", "--output-excel"])
        self.assertEqual(args.output_md, "")
        self.assertEqual(args.output_excel, "")

    def test_normalize_result_adds_fields(self):
        raw = {"Total Return %": 10.0}
        norm = _normalize_result(raw, "2330", "test_strat", "2023-01-01", "2023-12-31", {"param": 1})
        self.assertEqual(norm["Stock"], "2330")
        self.assertEqual(norm["Strategy"], "test_strat")
        self.assertEqual(norm["Start Date"], "2023-01-01")
        self.assertEqual(norm["End Date"], "2023-12-31")
        self.assertEqual(norm["Parameters"], {"param": 1})
        self.assertEqual(norm["Total Return %"], 10.0)

    @patch("tw_stock_tool.cli.backtest_report.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_report.run_backtest")
    @patch("tw_stock_tool.cli.backtest_report.export_backtest_report_markdown")
    @patch("tw_stock_tool.cli.backtest_report.export_backtest_report_excel")
    @patch("tw_stock_tool.cli.backtest_report._parse_args")
    def test_main_outputs_both_reports(self, mock_parse, mock_export_excel, mock_export_md, mock_run, mock_analyze):
        mock_parse.return_value = MagicMock(
            stock="2330",
            strategy="ma_cross",
            period="1y",
            initial_capital=100000,
            output_md="",
            output_excel="",
            output_dir="output",
            force_refresh=False,
            short_window=5,
            long_window=20,
            rsi_buy_below=30.0,
            rsi_sell_above=70.0,
            score_buy=None,
            score_sell=None,
            fee_rate=0.001425,
            tax_rate=0.003,
            position_size=1.0,
            stop_loss_pct=None,
            take_profit_pct=None,
            max_hold_days=None
        )
        mock_run.return_value = {"Total Return %": 5.0}

        mock_strat = MagicMock()
        mock_strat.return_value = pd.DataFrame(index=pd.date_range("2023-01-01", "2023-01-10"))
        with patch.dict("tw_stock_tool.cli.backtest_report.STRATEGIES", {"ma_cross_strategy": mock_strat}):
            main()

        mock_export_md.assert_called_once()
        mock_export_excel.assert_called_once()

        # Verify default paths
        md_path = mock_export_md.call_args[0][1]
        self.assertEqual(Path(md_path).parts[-2:], ("output", "backtest_report.md"))

        ex_path = mock_export_excel.call_args[0][1]
        self.assertEqual(Path(ex_path).parts[-2:], ("output", "backtest_report.xlsx"))

    @patch("tw_stock_tool.cli.backtest_report.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_report.run_backtest")
    @patch("tw_stock_tool.cli.backtest_report.export_backtest_report_markdown")
    @patch("tw_stock_tool.cli.backtest_report.export_backtest_report_excel")
    @patch("tw_stock_tool.cli.backtest_report._parse_args")
    def test_main_custom_output_paths(self, mock_parse, mock_export_excel, mock_export_md, mock_run, mock_analyze):
        mock_parse.return_value = MagicMock(
            stock="2330",
            strategy="ma_cross",
            period="1y",
            initial_capital=100000,
            output_md="output/custom.md",
            output_excel="output/custom.xlsx",
            output_dir="output",
            force_refresh=False,
            short_window=5,
            long_window=20,
            rsi_buy_below=30.0,
            rsi_sell_above=70.0,
            score_buy=None,
            score_sell=None,
            fee_rate=0.001425,
            tax_rate=0.003,
            position_size=1.0,
            stop_loss_pct=None,
            take_profit_pct=None,
            max_hold_days=None
        )
        mock_run.return_value = {"Total Return %": 5.0}

        mock_strat = MagicMock()
        mock_strat.return_value = pd.DataFrame(index=pd.date_range("2023-01-01", "2023-01-10"))
        with patch.dict("tw_stock_tool.cli.backtest_report.STRATEGIES", {"ma_cross_strategy": mock_strat}):
            main()

        mock_export_md.assert_called_once()
        mock_export_excel.assert_called_once()

        self.assertEqual(mock_export_md.call_args[0][1], "output/custom.md")
        self.assertEqual(mock_export_excel.call_args[0][1], "output/custom.xlsx")

    @patch("tw_stock_tool.cli.backtest_report.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_report.run_backtest")
    @patch("tw_stock_tool.cli.backtest_report.export_backtest_report_markdown")
    @patch("tw_stock_tool.cli.backtest_report.export_backtest_report_excel")
    @patch("tw_stock_tool.cli.backtest_report._parse_args")
    def test_main_no_output_specified(self, mock_parse, mock_export_excel, mock_export_md, mock_run, mock_analyze):
        mock_parse.return_value = MagicMock(
            stock="2330",
            strategy="ma_cross",
            period="1y",
            initial_capital=100000,
            output_md=None,
            output_excel=None,
            output_dir="output",
            force_refresh=False,
            short_window=5,
            long_window=20,
            rsi_buy_below=30.0,
            rsi_sell_above=70.0,
            score_buy=None,
            score_sell=None,
            fee_rate=0.001425,
            tax_rate=0.003,
            position_size=1.0,
            stop_loss_pct=None,
            take_profit_pct=None,
            max_hold_days=None
        )
        mock_run.return_value = {"Total Return %": 5.0}

        mock_strat = MagicMock()
        mock_strat.return_value = pd.DataFrame(index=pd.date_range("2023-01-01", "2023-01-10"))
        with patch.dict("tw_stock_tool.cli.backtest_report.STRATEGIES", {"ma_cross_strategy": mock_strat}):
            main()

        mock_export_md.assert_not_called()
        mock_export_excel.assert_not_called()

    @patch("tw_stock_tool.cli.backtest_report.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_report._parse_args")
    def test_main_unrecoverable_error_exits_with_1(self, mock_parse, mock_analyze):
        mock_parse.return_value = MagicMock(
            stock="2330",
            strategy="ma_cross",
            period="1y",
            initial_capital=100000,
            output_md=None,
            output_excel=None,
            output_dir="output",
            force_refresh=False,
            short_window=5,
            long_window=20,
            rsi_buy_below=30.0,
            rsi_sell_above=70.0,
            score_buy=None,
            score_sell=None,
            fee_rate=0.001425,
            tax_rate=0.003,
            position_size=1.0,
            stop_loss_pct=None,
            take_profit_pct=None,
            max_hold_days=None
        )
        mock_analyze.side_effect = Exception("Network Error")

        result = main()

        self.assertEqual(result, 1)

    @patch("tw_stock_tool.cli.backtest_report.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_report.run_backtest")
    @patch("tw_stock_tool.cli.backtest_report.export_backtest_report_markdown")
    @patch("tw_stock_tool.cli.backtest_report.export_backtest_report_excel")
    @patch("tw_stock_tool.cli.backtest_report._parse_args")
    def test_unsupported_strategy_exits_with_1(self, mock_parse, mock_export_excel, mock_export_md, mock_run, mock_analyze):
        mock_parse.return_value = MagicMock(
            stock="2330",
            strategy="unknown_strategy",
            period="1y",
            initial_capital=100000,
            output_md=None,
            output_excel=None,
            output_dir="output",
            force_refresh=False,
            short_window=5,
            long_window=20,
            rsi_buy_below=30.0,
            rsi_sell_above=70.0,
            score_buy=None,
            score_sell=None,
            fee_rate=0.001425,
            tax_rate=0.003,
            position_size=1.0,
            stop_loss_pct=None,
            take_profit_pct=None,
            max_hold_days=None
        )

        result = main()

        self.assertEqual(result, 1)
        mock_analyze.assert_not_called()
        mock_run.assert_not_called()
        mock_export_md.assert_not_called()
        mock_export_excel.assert_not_called()

    @patch("tw_stock_tool.cli.backtest_report.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_report.run_backtest")
    @patch("tw_stock_tool.cli.backtest_report._parse_args")
    def test_main_passes_rsi_params(self, mock_parse, mock_run, mock_analyze):
        mock_parse.return_value = MagicMock(
            stock="2330", strategy="rsi_strategy", period="1y",
            initial_capital=100000, output_md=None, output_excel=None, output_dir="output", force_refresh=False,
            short_window=5, long_window=20, rsi_buy_below=25.0, rsi_sell_above=75.0,
            score_buy=None, score_sell=None, fee_rate=0.0, tax_rate=0.0, position_size=1.0,
            stop_loss_pct=None, take_profit_pct=None, max_hold_days=None
        )
        mock_run.return_value = {"Total Return %": 5.0}

        mock_strat = MagicMock()
        mock_strat.return_value = pd.DataFrame(index=pd.date_range("2023-01-01", "2023-01-10"))
        with patch.dict("tw_stock_tool.cli.backtest_report.STRATEGIES", {"rsi_strategy": mock_strat}):
            main()

        mock_strat.assert_called_once()
        self.assertEqual(mock_strat.call_args[1]["buy_below"], 25.0)
        self.assertEqual(mock_strat.call_args[1]["sell_above"], 75.0)

    @patch("tw_stock_tool.cli.backtest_report.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_report.run_backtest")
    @patch("tw_stock_tool.cli.backtest_report._parse_args")
    def test_main_passes_score_params(self, mock_parse, mock_run, mock_analyze):
        mock_parse.return_value = MagicMock(
            stock="2330", strategy="score_strategy", period="1y",
            initial_capital=100000, output_md=None, output_excel=None, output_dir="output", force_refresh=False,
            short_window=5, long_window=20, rsi_buy_below=30.0, rsi_sell_above=70.0,
            score_buy=4.5, score_sell=-1.5, fee_rate=0.0, tax_rate=0.0, position_size=1.0,
            stop_loss_pct=None, take_profit_pct=None, max_hold_days=None
        )
        mock_run.return_value = {"Total Return %": 5.0}

        mock_strat = MagicMock()
        mock_strat.return_value = pd.DataFrame(index=pd.date_range("2023-01-01", "2023-01-10"))
        with patch.dict("tw_stock_tool.cli.backtest_report.STRATEGIES", {"score_strategy": mock_strat}):
            main()

        mock_strat.assert_called_once()
        self.assertEqual(mock_strat.call_args[1]["buy_score"], 4.5)
        self.assertEqual(mock_strat.call_args[1]["sell_score"], -1.5)

    @patch("tw_stock_tool.cli.backtest_report.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_report.run_backtest")
    @patch("tw_stock_tool.cli.backtest_report._parse_args")
    def test_main_passes_backtest_engine_params(self, mock_parse, mock_run, mock_analyze):
        mock_parse.return_value = MagicMock(
            stock="2330", strategy="ma_cross", period="1y",
            initial_capital=200000, output_md=None, output_excel=None, output_dir="output", force_refresh=False,
            short_window=5, long_window=20, rsi_buy_below=30.0, rsi_sell_above=70.0,
            score_buy=None, score_sell=None, fee_rate=0.001, tax_rate=0.002, position_size=0.5,
            stop_loss_pct=0.1, take_profit_pct=0.2, max_hold_days=10
        )
        mock_run.return_value = {"Total Return %": 5.0}

        mock_strat = MagicMock()
        mock_strat.return_value = pd.DataFrame(index=pd.date_range("2023-01-01", "2023-01-10"))
        with patch.dict("tw_stock_tool.cli.backtest_report.STRATEGIES", {"ma_cross_strategy": mock_strat}):
            main()

        mock_run.assert_called_once()
        bt_kwargs = mock_run.call_args[1]
        self.assertEqual(bt_kwargs["initial_capital"], 200000)
        self.assertEqual(bt_kwargs["fee_rate"], 0.001)
        self.assertEqual(bt_kwargs["tax_rate"], 0.002)
        self.assertEqual(bt_kwargs["position_size"], 0.5)
        self.assertEqual(bt_kwargs["stop_loss_pct"], 0.1)
        self.assertEqual(bt_kwargs["take_profit_pct"], 0.2)
        self.assertEqual(bt_kwargs["max_hold_days"], 10)

    @patch("tw_stock_tool.cli.backtest_report.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_report.run_backtest")
    @patch("tw_stock_tool.cli.backtest_report.export_backtest_report_markdown")
    @patch("tw_stock_tool.cli.backtest_report._parse_args")
    def test_main_report_parameters_include_nested_metadata(self, mock_parse, mock_export_md, mock_run, mock_analyze):
        mock_parse.return_value = MagicMock(
            stock="2330", strategy="ma_cross", period="1y",
            initial_capital=100000, output_md="output.md", output_excel=None, output_dir="output", force_refresh=False,
            short_window=5, long_window=20, rsi_buy_below=30.0, rsi_sell_above=70.0,
            score_buy=None, score_sell=None, fee_rate=0.001425, tax_rate=0.003, position_size=1.0,
            stop_loss_pct=None, take_profit_pct=None, max_hold_days=None
        )
        mock_run.return_value = {"Total Return %": 5.0}

        mock_strat = MagicMock()
        mock_strat.return_value = pd.DataFrame(index=pd.date_range("2023-01-01", "2023-01-10"))
        with patch.dict("tw_stock_tool.cli.backtest_report.STRATEGIES", {"ma_cross_strategy": mock_strat}):
            main()

        mock_export_md.assert_called_once()
        result_passed = mock_export_md.call_args[0][0]
        self.assertIn("Parameters", result_passed)
        params = result_passed["Parameters"]

        self.assertIn("strategy", params)
        self.assertIn("backtest", params)

        self.assertEqual(params["strategy"]["short_window"], 5)
        self.assertEqual(params["strategy"]["long_window"], 20)
        self.assertEqual(params["backtest"]["initial_capital"], 100000)
        self.assertEqual(params["backtest"]["fee_rate"], 0.001425)

    @patch("tw_stock_tool.cli.backtest_report.analyze_stock")
    @patch("tw_stock_tool.cli.backtest_report.run_backtest")
    @patch("tw_stock_tool.cli.backtest_report._parse_args")
    def test_no_banned_wording_in_cli_stdout(self, mock_parse, mock_run, mock_analyze):
        mock_parse.return_value = MagicMock(
            stock="2330", strategy="ma_cross", period="1y",
            initial_capital=100000, output_md=None, output_excel=None, output_dir="output", force_refresh=False,
            short_window=5, long_window=20, rsi_buy_below=30.0, rsi_sell_above=70.0,
            score_buy=None, score_sell=None, fee_rate=0.001425, tax_rate=0.003, position_size=1.0,
            stop_loss_pct=None, take_profit_pct=None, max_hold_days=None
        )
        mock_run.return_value = {"Total Return %": 5.0, "Win Rate %": 40.0, "Trade Count": 10}

        mock_strat = MagicMock()
        mock_strat.return_value = pd.DataFrame(index=pd.date_range("2023-01-01", "2023-01-10"))

        from io import StringIO
        captured_output = StringIO()

        with patch.dict("tw_stock_tool.cli.backtest_report.STRATEGIES", {"ma_cross_strategy": mock_strat}):
            with patch("sys.stdout", captured_output):
                main()

        out = captured_output.getvalue().lower()

        # Positive assertions
        self.assertIn("total return", out)
        self.assertIn("win rate", out)
        self.assertIn("trades", out)

        # Negative assertions
        banned_phrases = [
            "best strategy",
            "best parameters",
            "best result",
            "best trade",
            "best trade %",
            "worst trade",
            "worst trade %",
            "recommended stocks",
            "buy recommendation",
            "sell recommendation",
            "investment recommendation",
            "investment opportunity",
            "best stocks to buy",
            "should buy",
            "safe to invest",
            "guaranteed profit",
            "guaranteed return",
            "guaranteed latest data"
        ]
        for phrase in banned_phrases:
            self.assertNotIn(phrase.lower(), out)

