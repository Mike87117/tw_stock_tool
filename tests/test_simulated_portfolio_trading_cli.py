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
from tw_stock_tool.cli.simulated_portfolio_trading_cli import (
    _collect_stock_ids,
    _parse_args,
    main,
)
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

    def test_collect_stock_ids_combining_and_deduplication(self):
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
    def test_canonical_resolved_symbol_mapping_and_collision(self, mock_analyze):
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        a2 = _make_mock_analysis("2330.TW", symbol="2330.TW")
        mock_analyze.side_effect = [a1, a2]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"
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
            # Ensure pre-write failure creates no output file
            self.assertFalse(out_file.exists())

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
            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: df}):
                with patch("sys.stdout", new=stdout_capture):
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

            # Read back artifact and verify schema compliance
            content = out_file.read_text(encoding="utf-8")
            result = load_simulated_portfolio_trading_result_json(content)
            self.assertEqual(result.initial_cash, 500000.0)
            self.assertEqual(result.fill_count, 2)

            output_str = stdout_capture.getvalue()
            self.assertIn("Simulated portfolio trading finished. Summary:", output_str)
            self.assertIn("Initial Cash: 500000.0", output_str)
            self.assertIn(f"Output JSON Path: {out_file}", output_str)

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_single_stock_analysis_failure_fails_entire_run_no_output(self, mock_analyze):
        a1 = _make_mock_analysis("2330", symbol="2330.TW")
        mock_analyze.side_effect = [a1, ValueError("Market data network error")]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"

            ret = main(
                [
                    "--stocks",
                    "2330",
                    "2317",
                    "--strategy",
                    "ma_cross",
                    "--initial-cash",
                    "500000",
                    "--output-json",
                    str(out_file),
                ]
            )

            self.assertEqual(ret, 1)
            self.assertFalse(out_file.exists())

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_missing_open_close_or_signals_fails_run_no_output(self, mock_analyze):
        bad_df = pd.DataFrame({"Open": [100.0], "Close": [105.0]})  # Missing signals
        a1 = _make_mock_analysis("2330", symbol="2330.TW", df=bad_df)
        mock_analyze.side_effect = [a1]

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.json"

            with patch.dict("tw_stock_tool.cli.simulated_portfolio_trading_cli.STRATEGIES", {"ma_cross_strategy": lambda df: bad_df}):
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
            self.assertFalse(out_file.exists())

    @patch("tw_stock_tool.cli.simulated_portfolio_trading_cli.analyze_stock")
    def test_existing_output_without_overwrite_fails_and_leaves_file_unchanged(self, mock_analyze):
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
                ]
            )

            self.assertEqual(ret, 1)
            self.assertEqual(out_file.read_text(encoding="utf-8"), '{"original": "data"}')

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


if __name__ == "__main__":
    unittest.main()
