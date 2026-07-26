"""
Unit tests for multi-symbol simulated portfolio trading CLI.
"""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd

from tw_stock_tool.analysis.analysis import StockAnalysis
from tw_stock_tool.cli import simulated_portfolio_artifact_cli
from tw_stock_tool.cli.simulated_portfolio_trading_cli import (
    _collect_stock_ids,
    _parse_args,
    main,
)
from tw_stock_tool.paper_trading.portfolio_results import SimulatedPortfolioTradingResult
from tw_stock_tool.paper_trading.portfolio_serialization import (
    load_simulated_portfolio_trading_result_json,
)


def _make_sample_df(signals: list[tuple[str, int, int]] | None = None, close_prices: list[float] | None = None) -> pd.DataFrame:
    if signals is None:
        signals = [("2026-01-02", 1, 0), ("2026-01-05", 0, 1), ("2026-01-06", 0, 0)]
    dates = [pd.Timestamp(s[0]) for s in signals]
    closes = close_prices if close_prices is not None else [100.0 + i for i in range(len(signals))]
    opens = [c - 1.0 for c in closes]
    entries = [bool(s[1]) for s in signals]
    exits = [bool(s[2]) for s in signals]

    return pd.DataFrame(
        {
            "Open": opens,
            "Close": closes,
            "entry_signal": entries,
            "exit_signal": exits,
        },
        index=dates,
    )


def _make_mock_analysis(stock_id: str, symbol: str | None = None, df: pd.DataFrame | None = None) -> MagicMock:
    resolved_symbol = symbol if symbol is not None else (f"{stock_id}.TW" if not stock_id.endswith((".TW", ".TWO")) else stock_id)
    indicator_df = df if df is not None else _make_sample_df()
    analysis = MagicMock(spec=StockAnalysis)
    analysis.stock_id = stock_id
    analysis.symbol = resolved_symbol
    analysis.indicator_df = indicator_df
    return analysis


class TestSimulatedPortfolioTradingCLI(unittest.TestCase):
    def test_parse_args_required_and_defaults(self):
        args = _parse_args(
            [
                "--stocks",
                "2330",
                "2317",
                "--strategy",
                "ma_cross",
                "--initial-cash",
                "1000000",
                "--output-json",
                "out.json",
            ]
        )
        self.assertEqual(args.stocks, ["2330", "2317"])
        self.assertEqual(args.strategy, "ma_cross")
        self.assertEqual(args.initial_cash, 1000000.0)
        self.assertEqual(args.quantity_per_trade, 1000)
        self.assertEqual(args.fee_rate, 0.0)
        self.assertEqual(args.tax_rate, 0.0)
        self.assertEqual(args.slippage_per_share, 0.0)
        self.assertFalse(args.force_refresh)
        self.assertFalse(args.overwrite)
        self.assertEqual(args.output_json, "out.json")

    def test_parse_args_invalid_initial_cash(self):
        with patch("sys.stderr", new=io.StringIO()):
            with self.assertRaises(SystemExit):
                _parse_args(["--strategy", "ma_cross", "--initial-cash", "-100", "--output-json", "out.json"])

            with self.assertRaises(SystemExit):
                _parse_args(["--strategy", "ma_cross", "--initial-cash", "true", "--output-json", "out.json"])

            with self.assertRaises(SystemExit):
                _parse_args(["--strategy", "ma_cross", "--initial-cash", "nan", "--output-json", "out.json"])

            with self.assertRaises(SystemExit):
                _parse_args(["--strategy", "ma_cross", "--initial-cash", "inf", "--output-json", "out.json"])

    def test_parse_args_invalid_rates_and_quantity(self):
        with patch("sys.stderr", new=io.StringIO()):
            with self.assertRaises(SystemExit):
                _parse_args(["--strategy", "ma_cross", "--initial-cash", "100000", "--fee-rate", "-0.01", "--output-json", "out.json"])

            with self.assertRaises(SystemExit):
                _parse_args(["--strategy", "ma_cross", "--initial-cash", "100000", "--tax-rate", "nan", "--output-json", "out.json"])

            with self.assertRaises(SystemExit):
                _parse_args(["--strategy", "ma_cross", "--initial-cash", "100000", "--slippage-per-share", "inf", "--output-json", "out.json"])

            with self.assertRaises(SystemExit):
                _parse_args(["--strategy", "ma_cross", "--initial-cash", "100000", "--quantity-per-trade", "1000.5", "--output-json", "out.json"])

            with self.assertRaises(SystemExit):
                _parse_args(["--strategy", "ma_cross", "--initial-cash", "100000", "--quantity-per-trade", "0", "--output-json", "out.json"])

    def test_parse_args_zero_initial_cash_accepted(self):
        args = _parse_args(
            [
                "--stocks",
                "2330",
                "--strategy",
                "ma_cross",
                "--initial-cash",
                "0",
                "--output-json",
                "out.json",
            ]
        )
        self.assertEqual(args.initial_cash, 0.0)

    def test_collect_stock_ids_stocks_only(self):
        args = _parse_args(
            [
                "--stocks",
                "2330",
                "2317",
                "--strategy",
                "ma_cross",
                "--initial-cash",
                "100000",
                "--output-json",
                "out.json",
            ]
        )
        stock_ids = _collect_stock_ids(args)
        self.assertEqual(stock_ids, ["2330", "2317"])

    def test_collect_stock_ids_file_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "stocks.txt"
            file_path.write_text("2330\n2317\n", encoding="utf-8")

            args = _parse_args(
                [
                    "--file",
                    str(file_path),
                    "--strategy",
                    "ma_cross",
                    "--initial-cash",
                    "100000",
                    "--output-json",
                    "out.json",
                ]
            )

            stock_ids = _collect_stock_ids(args)
            self.assertEqual(stock_ids, ["2330", "2317"])

    def test_collect_stock_ids_combining_stocks_precedes_file_and_deduplication(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "stocks.txt"
            file_path.write_text("2317\n# comment\n 2454 \n\n", encoding="utf-8")

            args = _parse_args(
                [
                    "--stocks",
                    "2330",
                    "2317",
                    "--file",
                    str(file_path),
                    "--strategy",
                    "ma_cross",
                    "--initial-cash",
                    "100000",
                    "--output-json",
                    "out.json",
                ]
            )

            stock_ids = _collect_stock_ids(args)
            self.assertEqual(stock_ids, ["2330", "2317", "2454"])

    def test_collect_stock_ids_blank_cli_item_rejected(self):
        args = _parse_args(
            [
                "--stocks",
                "2330",
                "  ",
                "--strategy",
                "ma_cross",
                "--initial-cash",
                "100000",
                "--output-json",
                "out.json",
            ]
        )
        with self.assertRaises(ValueError) as ctx:
            _collect_stock_ids(args)
        self.assertIn("Blank CLI stock item", str(ctx.exception))

    def test_collect_stock_ids_missing_both_inputs_rejected(self):
        args = _parse_args(
            [
                "--strategy",
                "ma_cross",
                "--initial-cash",
                "100000",
                "--output-json",
                "out.json",
            ]
        )
        with self.assertRaises(ValueError) as ctx:
            _collect_stock_ids(args)
        self.assertIn("At least one of --stocks or --file must be provided", str(ctx.exception))

    def test_collect_stock_ids_empty_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "empty.txt"
            file_path.write_text("# comment only\n   \n", encoding="utf-8")

            args = _parse_args(
                [
                    "--file",
                    str(file_path),
                    "--strategy",
                    "ma_cross",
                    "--initial-cash",
                    "100000",
                    "--output-json",
                    "out.json",
                ]
            )
            with self.assertRaises(ValueError) as ctx:
                _collect_stock_ids(args)
            self.assertIn("Final stock list is empty", str(ctx.exception))

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_canonical_resolved_symbol_mapping_and_collision_error_formatting(self, mock_analyze):
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        a2 = _make_mock_analysis("2330.TW", symbol="2330.TW")
        mock_analyze.side_effect = [a1, a2]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"
            stdout_cap = io.StringIO()
            stderr_cap = io.StringIO()
            with patch("sys.stdout", new=stdout_cap), patch("sys.stderr", new=stderr_cap):
                ret = main(
                    [
                        "--stocks",
                        "2330",
                        "2330.TW",
                        "--strategy",
                        "ma_cross",
                        "--initial-cash",
                        "100000",
                        "--output-json",
                        str(out_file),
                    ]
                )

            self.assertEqual(ret, 1)
            self.assertFalse(out_file.exists())

            # Stderr checks
            err_text = stderr_cap.getvalue()
            self.assertTrue(err_text.startswith("error: "))
            self.assertIn("2330", err_text)
            self.assertIn("2330.TW", err_text)
            self.assertIn("Canonical symbol collision detected", err_text)

            # Stdout checks (empty)
            self.assertEqual(stdout_cap.getvalue(), "")

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_bare_tw_and_tpex_resolved_symbols_passed_to_facade(self, mock_analyze):
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        a2 = _make_mock_analysis("8069", symbol="8069.TWO")
        mock_analyze.side_effect = [a1, a2]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"

            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: df}):
                with patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.run_simulated_portfolio_trading_result") as mock_facade:
                    mock_facade.return_value = MagicMock(spec=SimulatedPortfolioTradingResult)
                    ret = main(
                        [
                            "--stocks",
                            "2330",
                            "8069",
                            "--strategy",
                            "ma_cross",
                            "--initial-cash",
                            "500000",
                            "--output-json",
                            str(out_file),
                        ]
                    )

            mock_facade.assert_called_once()
            call_args = mock_facade.call_args
            dataframes = call_args.args[0]
            last_prices = call_args.kwargs["last_prices"]

            self.assertEqual(set(dataframes.keys()), {"2330.TW", "8069.TWO"})
            self.assertEqual(set(last_prices.keys()), {"2330.TW", "8069.TWO"})

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_explicit_tw_symbol_is_preserved(self, mock_analyze):
        a1 = _make_mock_analysis("2330.TW", symbol="2330.TW")
        mock_analyze.side_effect = [a1]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"
            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: df}):
                with patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.run_simulated_portfolio_trading_result") as mock_facade:
                    mock_facade.return_value = MagicMock(spec=SimulatedPortfolioTradingResult)
                    ret = main(["--stocks", "2330.TW", "--strategy", "ma_cross", "--initial-cash", "500000", "--output-json", str(out_file)])

            mock_facade.assert_called_once()
            dataframes = mock_facade.call_args.args[0]
            last_prices = mock_facade.call_args.kwargs["last_prices"]
            self.assertEqual(list(dataframes.keys()), ["2330.TW"])
            self.assertEqual(list(last_prices.keys()), ["2330.TW"])

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_explicit_two_symbol_is_preserved(self, mock_analyze):
        a1 = _make_mock_analysis("8069.TWO", symbol="8069.TWO")
        mock_analyze.side_effect = [a1]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"
            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: df}):
                with patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.run_simulated_portfolio_trading_result") as mock_facade:
                    mock_facade.return_value = MagicMock(spec=SimulatedPortfolioTradingResult)
                    ret = main(["--stocks", "8069.TWO", "--strategy", "ma_cross", "--initial-cash", "500000", "--output-json", str(out_file)])

            mock_facade.assert_called_once()
            dataframes = mock_facade.call_args.args[0]
            last_prices = mock_facade.call_args.kwargs["last_prices"]
            self.assertEqual(list(dataframes.keys()), ["8069.TWO"])
            self.assertEqual(list(last_prices.keys()), ["8069.TWO"])

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_successful_two_symbol_cli_execution_and_summary(self, mock_analyze):
        df1 = _make_sample_df([("2026-01-02", 1, 0), ("2026-01-05", 0, 0)], close_prices=[100.0, 110.0])
        df2 = _make_sample_df([("2026-01-02", 1, 0), ("2026-01-05", 0, 0)], close_prices=[50.0, 52.0])

        a1 = _make_mock_analysis("2330", symbol="2330.TW", df=df1)
        a2 = _make_mock_analysis("2317", symbol="2317.TW", df=df2)
        mock_analyze.side_effect = [a1, a2]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "portfolio.json"

            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: df}):
                with patch("sys.stdout", new=stdout_capture), patch("sys.stderr", new=stderr_capture):
                    ret = main(
                        [
                            "--stocks",
                            "2330",
                            "2317",
                            "--strategy",
                            "ma_cross",
                            "--initial-cash",
                            "500000",
                            "--quantity-per-trade",
                            "1000",
                            "--output-json",
                            str(out_file),
                        ]
                    )

            self.assertIsNone(ret)
            self.assertTrue(out_file.exists())

            # Stderr must be completely empty on clean execution
            self.assertEqual(stderr_capture.getvalue(), "")

            content = out_file.read_text(encoding="utf-8")
            result = load_simulated_portfolio_trading_result_json(content)
            self.assertEqual(result.initial_cash, 500000.0)

            # Strict 14 domain summary labels + separate Output JSON Path line assertions
            raw_stdout = stdout_capture.getvalue()
            lines = raw_stdout.splitlines()

            self.assertIn("Simulated portfolio trading finished. Summary:", lines[0])

            expected_label_prefixes = [
                "  Initial Cash:",
                "  Final Cash:",
                "  Total Market Value:",
                "  Total Equity:",
                "  Realized PnL:",
                "  Unrealized PnL:",
                "  Total Return:",
                "  Total Return %:",
                "  Open Position Count:",
                "  Pending Order Count:",
                "  Order Count:",
                "  Fill Count:",
                "  Rejection Count:",
                "  Audit Record Count:",
            ]

            for prefix in expected_label_prefixes:
                matches = [l for l in lines if l.startswith(prefix)]
                self.assertEqual(len(matches), 1, f"Label prefix '{prefix}' must appear exactly once.")

            # Separate output JSON path line
            json_path_lines = [l for l in lines if l.startswith("  Output JSON Path:")]
            self.assertEqual(len(json_path_lines), 1)
            self.assertEqual(json_path_lines[0], f"  Output JSON Path: {out_file}")

    # Strategy & DataFrame Fail-Closed Tests (Separate test methods for missing columns & indices)
    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_strategy_raises_exception_fails_run_no_output(self, mock_analyze):
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        mock_analyze.side_effect = [a1]

        def bad_strategy(df):
            raise RuntimeError("Strategy error")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"
            stderr_cap = io.StringIO()
            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": bad_strategy}):
                with patch("sys.stderr", new=stderr_cap):
                    ret = main(["--stocks", "2330", "--strategy", "ma_cross", "--initial-cash", "500000", "--output-json", str(out_file)])

            self.assertEqual(ret, 1)
            self.assertFalse(out_file.exists())
            self.assertTrue(stderr_cap.getvalue().startswith("error: "))

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_strategy_returns_empty_dataframe_fails_run_no_output(self, mock_analyze):
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        mock_analyze.side_effect = [a1]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"
            stderr_cap = io.StringIO()
            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: pd.DataFrame()}):
                with patch("sys.stderr", new=stderr_cap):
                    ret = main(["--stocks", "2330", "--strategy", "ma_cross", "--initial-cash", "500000", "--output-json", str(out_file)])

            self.assertEqual(ret, 1)
            self.assertFalse(out_file.exists())
            self.assertTrue(stderr_cap.getvalue().startswith("error: "))

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_missing_open_column_fails_closed_before_write(self, mock_analyze):
        bad_df = pd.DataFrame({"Close": [100.0], "entry_signal": [True], "exit_signal": [False]}, index=[pd.Timestamp("2026-01-02")])
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        mock_analyze.side_effect = [a1]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"
            stderr_cap = io.StringIO()
            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: bad_df}):
                with patch("sys.stderr", new=stderr_cap):
                    ret = main(["--stocks", "2330", "--strategy", "ma_cross", "--initial-cash", "500000", "--output-json", str(out_file)])

            self.assertEqual(ret, 1)
            self.assertFalse(out_file.exists())
            err_msg = stderr_cap.getvalue()
            self.assertTrue(err_msg.startswith("error: "))
            self.assertIn("Open", err_msg)

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_missing_close_column_fails_closed_before_write(self, mock_analyze):
        bad_df = pd.DataFrame({"Open": [100.0], "entry_signal": [True], "exit_signal": [False]}, index=[pd.Timestamp("2026-01-02")])
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        mock_analyze.side_effect = [a1]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"
            stderr_cap = io.StringIO()
            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: bad_df}):
                with patch("sys.stderr", new=stderr_cap):
                    ret = main(["--stocks", "2330", "--strategy", "ma_cross", "--initial-cash", "500000", "--output-json", str(out_file)])

            self.assertEqual(ret, 1)
            self.assertFalse(out_file.exists())
            err_msg = stderr_cap.getvalue()
            self.assertTrue(err_msg.startswith("error: "))
            self.assertIn("Close", err_msg)

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_missing_entry_signal_column_fails_closed_before_write(self, mock_analyze):
        bad_df = pd.DataFrame({"Open": [100.0], "Close": [105.0], "exit_signal": [False]}, index=[pd.Timestamp("2026-01-02")])
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        mock_analyze.side_effect = [a1]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"
            stderr_cap = io.StringIO()
            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: bad_df}):
                with patch("sys.stderr", new=stderr_cap):
                    ret = main(["--stocks", "2330", "--strategy", "ma_cross", "--initial-cash", "500000", "--output-json", str(out_file)])

            self.assertEqual(ret, 1)
            self.assertFalse(out_file.exists())
            err_msg = stderr_cap.getvalue()
            self.assertTrue(err_msg.startswith("error: "))
            self.assertIn("standard signals", err_msg)

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_missing_exit_signal_column_fails_closed_before_write(self, mock_analyze):
        bad_df = pd.DataFrame({"Open": [100.0], "Close": [105.0], "entry_signal": [True]}, index=[pd.Timestamp("2026-01-02")])
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        mock_analyze.side_effect = [a1]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"
            stderr_cap = io.StringIO()
            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: bad_df}):
                with patch("sys.stderr", new=stderr_cap):
                    ret = main(["--stocks", "2330", "--strategy", "ma_cross", "--initial-cash", "500000", "--output-json", str(out_file)])

            self.assertEqual(ret, 1)
            self.assertFalse(out_file.exists())
            err_msg = stderr_cap.getvalue()
            self.assertTrue(err_msg.startswith("error: "))
            self.assertIn("standard signals", err_msg)

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_duplicate_index_fails_closed_before_write(self, mock_analyze):
        dates = [pd.Timestamp("2026-01-02"), pd.Timestamp("2026-01-02")]
        dup_df = pd.DataFrame({"Open": [100.0, 101.0], "Close": [105.0, 106.0], "entry_signal": [True, False], "exit_signal": [False, False]}, index=dates)
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        mock_analyze.side_effect = [a1]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"
            stderr_cap = io.StringIO()
            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: dup_df}):
                with patch("sys.stderr", new=stderr_cap):
                    ret = main(["--stocks", "2330", "--strategy", "ma_cross", "--initial-cash", "500000", "--output-json", str(out_file)])

            self.assertEqual(ret, 1)
            self.assertFalse(out_file.exists())
            err_msg = stderr_cap.getvalue()
            self.assertTrue(err_msg.startswith("error: "))
            self.assertIn("unique", err_msg.lower())

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_non_monotonic_index_fails_closed_before_write(self, mock_analyze):
        dates = [pd.Timestamp("2026-01-05"), pd.Timestamp("2026-01-02")]
        non_mono_df = pd.DataFrame({"Open": [100.0, 101.0], "Close": [105.0, 106.0], "entry_signal": [True, False], "exit_signal": [False, False]}, index=dates)
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        mock_analyze.side_effect = [a1]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"
            stderr_cap = io.StringIO()
            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: non_mono_df}):
                with patch("sys.stderr", new=stderr_cap):
                    ret = main(["--stocks", "2330", "--strategy", "ma_cross", "--initial-cash", "500000", "--output-json", str(out_file)])

            self.assertEqual(ret, 1)
            self.assertFalse(out_file.exists())
            err_msg = stderr_cap.getvalue()
            self.assertTrue(err_msg.startswith("error: "))

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_final_close_invalid_types_and_values_fails_run_no_output(self, mock_analyze):
        cases = [
            ("bool", pd.DataFrame({"Open": [100.0], "Close": [True], "entry_signal": [True], "exit_signal": [False]}, index=[pd.Timestamp("2026-01-02")])),
            ("string", pd.DataFrame({"Open": [100.0], "Close": ["105.0"], "entry_signal": [True], "exit_signal": [False]}, index=[pd.Timestamp("2026-01-02")])),
            ("nan", pd.DataFrame({"Open": [100.0], "Close": [float("nan")], "entry_signal": [True], "exit_signal": [False]}, index=[pd.Timestamp("2026-01-02")])),
            ("inf", pd.DataFrame({"Open": [100.0], "Close": [float("inf")], "entry_signal": [True], "exit_signal": [False]}, index=[pd.Timestamp("2026-01-02")])),
            ("-inf", pd.DataFrame({"Open": [100.0], "Close": [float("-inf")], "entry_signal": [True], "exit_signal": [False]}, index=[pd.Timestamp("2026-01-02")])),
            ("zero", pd.DataFrame({"Open": [100.0], "Close": [0.0], "entry_signal": [True], "exit_signal": [False]}, index=[pd.Timestamp("2026-01-02")])),
            ("negative", pd.DataFrame({"Open": [100.0], "Close": [-10.0], "entry_signal": [True], "exit_signal": [False]}, index=[pd.Timestamp("2026-01-02")])),
        ]

        for case_name, bad_df in cases:
            with self.subTest(case_name=case_name):
                a1 = _make_mock_analysis("2330", symbol="2330.TW")
                mock_analyze.side_effect = [a1]

                with tempfile.TemporaryDirectory() as tmpdir:
                    out_file = Path(tmpdir) / "out.json"
                    stderr_cap = io.StringIO()
                    with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: bad_df}):
                        with patch("sys.stderr", new=stderr_cap):
                            ret = main(["--stocks", "2330", "--strategy", "ma_cross", "--initial-cash", "500000", "--output-json", str(out_file)])

                    self.assertEqual(ret, 1)
                    self.assertFalse(out_file.exists())
                    self.assertTrue(stderr_cap.getvalue().startswith("error: "))

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_existing_output_without_overwrite_fails_and_leaves_file_unchanged(self, mock_analyze):
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        mock_analyze.side_effect = [a1]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "existing.json"
            out_file.write_text('{"original": "data"}', encoding="utf-8")

            stderr_cap = io.StringIO()
            with patch("sys.stderr", new=stderr_cap):
                ret = main(
                    [
                        "--stocks",
                        "2330",
                        "--strategy",
                        "ma_cross",
                        "--initial-cash",
                        "500000",
                        "--output-json",
                        str(out_file),
                    ]
                )

            self.assertEqual(ret, 1)
            self.assertEqual(out_file.read_text(encoding="utf-8"), '{"original": "data"}')
            self.assertTrue(stderr_cap.getvalue().startswith("error: "))

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_existing_output_with_overwrite_succeeds(self, mock_analyze):
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        mock_analyze.side_effect = [a1]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "existing.json"
            out_file.write_text('{"original": "data"}', encoding="utf-8")

            ret = main(
                [
                    "--stocks",
                    "2330",
                    "--strategy",
                    "ma_cross",
                    "--initial-cash",
                    "500000",
                    "--output-json",
                    str(out_file),
                    "--overwrite",
                ]
            )

            self.assertIsNone(ret)
            self.assertNotIn('{"original": "data"}', out_file.read_text(encoding="utf-8"))

    # Write & Read-Back Boundary Tests
    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_json_write_failure_returns_1_and_skips_read_back(self, mock_analyze):
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        mock_analyze.side_effect = [a1]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"

            stderr_cap = io.StringIO()
            stdout_cap = io.StringIO()
            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: df}):
                with patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.export_simulated_portfolio_trading_result_json_file", side_effect=PermissionError("disk write permission denied")):
                    with patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.load_simulated_portfolio_trading_result_json_file") as mock_loader:
                        with patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.build_simulated_portfolio_trading_summary") as mock_summary_builder:
                            with patch("sys.stdout", new=stdout_cap), patch("sys.stderr", new=stderr_cap):
                                ret = main(["--stocks", "2330", "--strategy", "ma_cross", "--initial-cash", "500000", "--output-json", str(out_file)])

            self.assertEqual(ret, 1)
            err_msg = stderr_cap.getvalue()
            self.assertTrue(err_msg.startswith("error: "))
            self.assertIn("disk write permission denied", err_msg)
            mock_loader.assert_not_called()
            mock_summary_builder.assert_not_called()
            self.assertNotIn("Simulated portfolio trading finished. Summary:", stdout_cap.getvalue())

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_read_back_failure_returns_1_uses_stderr_and_does_not_delete_written_artifact(self, mock_analyze):
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        mock_analyze.side_effect = [a1]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"

            stderr_cap = io.StringIO()
            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: df}):
                with patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.load_simulated_portfolio_trading_result_json_file", side_effect=ValueError("Corrupted artifact read-back")):
                    with patch("sys.stderr", new=stderr_cap):
                        ret = main(["--stocks", "2330", "--strategy", "ma_cross", "--initial-cash", "500000", "--output-json", str(out_file)])

            self.assertEqual(ret, 1)
            # Written artifact must NOT be deleted
            self.assertTrue(out_file.exists())
            self.assertTrue(stderr_cap.getvalue().startswith("error: "))
            self.assertIn("Corrupted artifact read-back", stderr_cap.getvalue())

    # Summary Boundary Tests (Identity Test)
    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_summary_builder_receives_loader_returned_object_identity(self, mock_analyze):
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        mock_analyze.side_effect = [a1]

        mock_pre_write_obj = MagicMock(name="PreWriteObj")
        mock_loaded_obj = MagicMock(name="LoadedObj")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"

            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: df}):
                with patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.run_simulated_portfolio_trading_result", return_value=mock_pre_write_obj):
                    with patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.export_simulated_portfolio_trading_result_json_file", return_value=str(out_file)):
                        with patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.load_simulated_portfolio_trading_result_json_file", return_value=mock_loaded_obj) as mock_loader:
                            with patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.build_simulated_portfolio_trading_summary") as mock_summary_builder:
                                mock_summary_builder.return_value = {
                                    "initial_cash": 500000.0,
                                    "final_cash": 500000.0,
                                    "total_market_value": 0.0,
                                    "total_equity": 500000.0,
                                    "realized_pnl": 0.0,
                                    "unrealized_pnl": 0.0,
                                    "total_return": 0.0,
                                    "total_return_pct": 0.0,
                                    "open_position_count": 0,
                                    "pending_order_count": 0,
                                    "order_count": 0,
                                    "fill_count": 0,
                                    "rejection_count": 0,
                                    "audit_record_count": 0,
                                }
                                ret = main(["--stocks", "2330", "--strategy", "ma_cross", "--initial-cash", "500000", "--output-json", str(out_file)])

            self.assertIsNone(ret)
            mock_loader.assert_called_once_with(str(out_file))
            # Critical identity assertion: summary builder received loaded_obj (B), NOT pre_write_obj (A)!
            mock_summary_builder.assert_called_once_with(mock_loaded_obj)

    # Offline Artifact Compatibility Integration Test
    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_offline_artifact_cli_compatibility_integration(self, mock_analyze):
        df1 = _make_sample_df([("2026-01-02", 1, 0), ("2026-01-05", 0, 0)], close_prices=[100.0, 110.0])
        a1 = _make_mock_analysis("2330", symbol="2330.TW", df=df1)
        mock_analyze.side_effect = [a1]

        with tempfile.TemporaryDirectory() as tmpdir:
            json_file = Path(tmpdir) / "portfolio.json"
            md_file = Path(tmpdir) / "portfolio.md"
            csv_dir = Path(tmpdir) / "csv_out"

            # 1. Execute CLI to produce JSON artifact
            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: df}):
                ret = main(["--stocks", "2330", "--strategy", "ma_cross", "--initial-cash", "500000", "--output-json", str(json_file)])

            self.assertIsNone(ret)
            self.assertTrue(json_file.exists())

            # 2. Operate offline artifact CLI on generated JSON artifact
            # 2a. Validate
            val_ret = simulated_portfolio_artifact_cli.main(["validate", str(json_file)])
            self.assertIsNone(val_ret)

            # 2b. Inspect
            stdout_cap = io.StringIO()
            with patch("sys.stdout", new=stdout_cap):
                insp_ret = simulated_portfolio_artifact_cli.main(["inspect", str(json_file)])
            self.assertIsNone(insp_ret)
            self.assertIn("Simulated Portfolio Trading Artifact Summary", stdout_cap.getvalue())

            # 2c. Export Markdown
            md_ret = simulated_portfolio_artifact_cli.main(["export-markdown", str(json_file), "--output-markdown", str(md_file)])
            self.assertIsNone(md_ret)
            self.assertTrue(md_file.exists())

            # 2d. Export CSV Bundle (Exact 7 CSV files verification)
            csv_ret = simulated_portfolio_artifact_cli.main(["export-csv", str(json_file), "--output-csv-dir", str(csv_dir)])
            self.assertIsNone(csv_ret)
            self.assertTrue(csv_dir.exists())

            csv_files = list(csv_dir.glob("*.csv"))
            self.assertEqual(len(csv_files), 7, f"Exact CSV file count must be 7, found {len(csv_files)}")

            expected_csv_names = {
                "simulated_portfolio_trading_summary.csv",
                "simulated_portfolio_trading_positions.csv",
                "simulated_portfolio_trading_pending_orders.csv",
                "simulated_portfolio_trading_orders.csv",
                "simulated_portfolio_trading_fills.csv",
                "simulated_portfolio_trading_rejections.csv",
                "simulated_portfolio_trading_trade_log.csv",
            }
            actual_csv_names = {f.name for f in csv_files}
            self.assertEqual(actual_csv_names, expected_csv_names)

            summary_csv_path = csv_dir / "simulated_portfolio_trading_summary.csv"
            self.assertGreater(len(summary_csv_path.read_text(encoding="utf-8").strip()), 0)


if __name__ == "__main__":
    unittest.main()
