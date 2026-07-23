import unittest
from contextlib import redirect_stdout
from io import StringIO

from tw_stock_tool.cli.backtest_report import _parse_args as parse_backtest_report
from tw_stock_tool.cli.parameter_sweep_report import _parse_args as parse_parameter_sweep
from tw_stock_tool.cli.walk_forward_report import _parse_args as parse_walk_forward


COMMON_OPTIONS = (
    "--initial-capital",
    "--fee-rate",
    "--tax-rate",
    "--position-size",
    "--stop-loss-pct",
    "--take-profit-pct",
    "--max-hold-days",
)

CLI_CASES = (
    (
        "backtest report",
        parse_backtest_report,
        {"initial_capital": 100000.0, "fee_rate": 0.001425, "tax_rate": 0.003,
         "position_size": 1.0, "stop_loss_pct": None, "take_profit_pct": None,
         "max_hold_days": None},
    ),
    (
        "parameter sweep",
        parse_parameter_sweep,
        {"initial_capital": 100000.0, "fee_rate": 0.001425, "tax_rate": 0.003,
         "position_size": 1.0, "stop_loss_pct": None, "take_profit_pct": None,
         "max_hold_days": None},
    ),
    (
        "walk forward",
        parse_walk_forward,
        {"initial_capital": 100000.0, "fee_rate": 0.001425, "tax_rate": 0.003,
         "position_size": 1.0, "stop_loss_pct": None, "take_profit_pct": None,
         "max_hold_days": None},
    ),
)


class SharedBacktestCliParameterContractsTest(unittest.TestCase):
    def test_shared_engine_parameter_defaults(self):
        for name, parse_args, expected in CLI_CASES:
            with self.subTest(cli=name):
                args = parse_args(["--stock", "2330", "--strategy", "ma_cross"])
                self.assertEqual(
                    {field: getattr(args, field) for field in expected},
                    expected,
                )

    def test_shared_engine_options_are_visible_in_help(self):
        for name, parse_args, _ in CLI_CASES:
            with self.subTest(cli=name):
                output = StringIO()
                with redirect_stdout(output):
                    with self.assertRaises(SystemExit) as raised:
                        parse_args(["--help"])
                self.assertEqual(raised.exception.code, 0)
                for option in COMMON_OPTIONS:
                    self.assertIn(option, output.getvalue())


if __name__ == "__main__":
    unittest.main()
