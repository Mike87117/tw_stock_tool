from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import unittest

from tw_stock_tool.cli import backtest_report, parameter_sweep_report, walk_forward_report


PARSERS = (
    ("backtest", backtest_report._parse_args),
    ("parameter sweep", parameter_sweep_report._parse_args),
    ("walk forward", walk_forward_report._parse_args),
)
MINIMUM_ARGS = ["--stock", "2330", "--strategy", "ma_cross"]
COMMON_DEFAULTS = {
    "initial_capital": 100000.0,
    "fee_rate": 0.001425,
    "tax_rate": 0.003,
    "position_size": 1.0,
    "stop_loss_pct": None,
    "take_profit_pct": None,
    "max_hold_days": None,
}
REQUIRED_HELP_OPTIONS = (
    "--stock",
    "--strategy",
    "--output-md",
    "--output-excel",
    "--initial-capital",
    "--fee-rate",
    "--tax-rate",
    "--position-size",
    "--stop-loss-pct",
    "--take-profit-pct",
    "--max-hold-days",
)


class ReportCliParserTest(unittest.TestCase):
    def test_required_arguments_and_shared_engine_defaults(self) -> None:
        for name, parse_args in PARSERS:
            with self.subTest(cli=name):
                parsed = parse_args(MINIMUM_ARGS)
                self.assertEqual(parsed.stock, "2330")
                self.assertEqual(parsed.strategy, "ma_cross")
                self.assertEqual(
                    {field: getattr(parsed, field) for field in COMMON_DEFAULTS},
                    COMMON_DEFAULTS,
                )

    def test_report_outputs_support_omitted_bare_and_explicit_values(self) -> None:
        for name, parse_args in PARSERS:
            for option, explicit in (
                ("--output-md", "report.md"),
                ("--output-excel", "report.xlsx"),
            ):
                with self.subTest(cli=name, option=option):
                    field = option[2:].replace("-", "_")
                    self.assertIsNone(getattr(parse_args(MINIMUM_ARGS), field))
                    self.assertEqual(
                        getattr(parse_args([*MINIMUM_ARGS, option]), field),
                        "",
                    )
                    self.assertEqual(
                        getattr(
                            parse_args([*MINIMUM_ARGS, option, explicit]),
                            field,
                        ),
                        explicit,
                    )

    def test_range_parsers_accept_tuples_and_negative_scores(self) -> None:
        options = [
            "--ma-short-windows",
            " 5, 10 ,20 ",
            "--ma-long-windows",
            "30",
            "--rsi-buy-below",
            "25",
            "--rsi-sell-above",
            "65, 75",
            "--score-buy",
            "4,6",
            "--score-sell=-2, -4",
        ]
        for name, parse_args in PARSERS[1:]:
            with self.subTest(cli=name):
                parsed = parse_args([*MINIMUM_ARGS, *options])
                self.assertEqual(parsed.ma_short_windows, (5, 10, 20))
                self.assertEqual(parsed.ma_long_windows, (30,))
                self.assertEqual(parsed.rsi_buy_below, (25,))
                self.assertEqual(parsed.rsi_sell_above, (65, 75))
                self.assertEqual(parsed.score_buy, (4, 6))
                self.assertEqual(parsed.score_sell, (-2, -4))

    def test_invalid_values_exit_two_before_runtime(self) -> None:
        cases = (
            (
                "backtest",
                backtest_report._parse_args,
                [*MINIMUM_ARGS, "--short-window", "bad"],
            ),
            (
                "parameter sweep",
                parameter_sweep_report._parse_args,
                [*MINIMUM_ARGS, "--ma-short-windows", "5,bad"],
            ),
            (
                "walk forward",
                walk_forward_report._parse_args,
                [*MINIMUM_ARGS, "--fee-rate", "bad"],
            ),
        )
        for name, parse_args, argv in cases:
            with self.subTest(cli=name), redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    parse_args(argv)
            self.assertEqual(raised.exception.code, 2)

    def test_help_exposes_public_report_and_engine_options(self) -> None:
        for name, parse_args in PARSERS:
            output = StringIO()
            with self.subTest(cli=name), redirect_stdout(output):
                with self.assertRaises(SystemExit) as raised:
                    parse_args(["--help"])
            self.assertEqual(raised.exception.code, 0)
            help_text = output.getvalue()
            for option in REQUIRED_HELP_OPTIONS:
                self.assertIn(option, help_text)


if __name__ == "__main__":
    unittest.main()
