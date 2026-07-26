"""Freeze existing trading CLI scalar parser behavior before deduplication."""

from __future__ import annotations

import io
import unittest
from collections.abc import Callable
from unittest.mock import patch

from tw_stock_tool.cli import simulated_paper_trading_cli as paper_cli
from tw_stock_tool.cli import simulated_portfolio_trading_cli as portfolio_cli


Parser = Callable[[list[str] | None], object]

PAPER_BASE = [
    "--stock", "2330", "--strategy", "ma_cross",
    "--initial-cash", "1000", "--quantity-per-trade", "1000",
]
PORTFOLIO_BASE = [
    "--stocks", "2330", "--strategy", "ma_cross",
    "--initial-cash", "1000", "--output-json", "out.json",
]


def _with_scalar(base: list[str], flag: str, value: str, *, attached: bool = False) -> list[str]:
    args = list(base)
    if flag in args:
        index = args.index(flag)
        del args[index:index + 2]
    args.append(f"{flag}={value}" if attached else flag)
    if not attached:
        args.append(value)
    return args


class TestCliScalarValidatorContracts(unittest.TestCase):
    def assert_rejected(
        self,
        parser: Parser,
        args: list[str],
        expected_fragment: str,
    ) -> None:
        stderr = io.StringIO()
        with patch("sys.stderr", new=stderr):
            with self.assertRaises(SystemExit) as context:
                parser(args)
        self.assertEqual(context.exception.code, 2)
        self.assertIn(expected_fragment, stderr.getvalue())

    def assert_scalar(
        self,
        parser: Parser,
        args: list[str],
        attribute: str,
        expected: object,
        expected_type: type,
    ) -> None:
        parsed = parser(args)
        actual = getattr(parsed, attribute)
        self.assertEqual(actual, expected)
        self.assertIs(type(actual), expected_type)

    def test_required_and_default_contracts(self) -> None:
        paper = paper_cli._parse_args(PAPER_BASE)
        for attribute in ("fee_rate", "tax_rate", "slippage_per_share"):
            self.assertEqual(getattr(paper, attribute), 0.0)
            self.assertIs(type(getattr(paper, attribute)), float)
        for attribute in ("max_order_notional", "max_position_quantity", "max_position_notional"):
            self.assertIsNone(getattr(paper, attribute))

        portfolio = portfolio_cli._parse_args(PORTFOLIO_BASE)
        self.assertEqual(portfolio.quantity_per_trade, 1000)
        self.assertIs(type(portfolio.quantity_per_trade), int)
        for attribute in ("fee_rate", "tax_rate", "slippage_per_share"):
            self.assertEqual(getattr(portfolio, attribute), 0.0)
            self.assertIs(type(getattr(portfolio, attribute)), float)
        for attribute in (
            "max_order_notional",
            "max_position_quantity",
            "max_position_notional",
            "max_total_exposure",
        ):
            self.assertIsNone(getattr(portfolio, attribute))

        self.assert_rejected(
            paper_cli._parse_args,
            ["--stock", "2330", "--strategy", "ma_cross", "--quantity-per-trade", "1000"],
            "the following arguments are required: --initial-cash",
        )
        self.assert_rejected(
            paper_cli._parse_args,
            ["--stock", "2330", "--strategy", "ma_cross", "--initial-cash", "1000"],
            "the following arguments are required: --quantity-per-trade",
        )
        self.assert_rejected(
            portfolio_cli._parse_args,
            ["--stocks", "2330", "--strategy", "ma_cross", "--output-json", "out.json"],
            "the following arguments are required: --initial-cash",
        )

    def test_valid_scalar_forms_and_exact_types(self) -> None:
        float_forms = [("0", 0.0), ("1000", 1000.0), ("1000.5", 1000.5), ("1e3", 1000.0), (" 1000 ", 1000.0)]
        for parser, base in (
            (paper_cli._parse_args, PAPER_BASE),
            (portfolio_cli._parse_args, PORTFOLIO_BASE),
        ):
            for value, expected in float_forms:
                with self.subTest(parser=parser.__module__, flag="--initial-cash", value=value):
                    self.assert_scalar(parser, _with_scalar(base, "--initial-cash", value), "initial_cash", expected, float)
            for value in ("1000", " 1000 "):
                with self.subTest(parser=parser.__module__, flag="--quantity-per-trade", value=value):
                    self.assert_scalar(parser, _with_scalar(base, "--quantity-per-trade", value), "quantity_per_trade", 1000, int)

        for parser, base, notional_flags in (
            (paper_cli._parse_args, PAPER_BASE, ("--max-order-notional", "--max-position-notional")),
            (portfolio_cli._parse_args, PORTFOLIO_BASE, ("--max-order-notional", "--max-position-notional", "--max-total-exposure")),
        ):
            for flag, attribute in (
                ("--fee-rate", "fee_rate"),
                ("--tax-rate", "tax_rate"),
                ("--slippage-per-share", "slippage_per_share"),
            ):
                for value, expected in (("0", 0.0), ("1e-3", 0.001), (" 0.5 ", 0.5)):
                    with self.subTest(parser=parser.__module__, flag=flag, value=value):
                        self.assert_scalar(parser, _with_scalar(base, flag, value), attribute, expected, float)
            for flag in notional_flags:
                attribute = flag[2:].replace("-", "_")
                for value, expected in (("1", 1.0), ("1000.5", 1000.5), ("1e3", 1000.0), (" 1000 ", 1000.0)):
                    with self.subTest(parser=parser.__module__, flag=flag, value=value):
                        self.assert_scalar(parser, _with_scalar(base, flag, value), attribute, expected, float)
            for value in ("1000", " 1000 "):
                self.assert_scalar(
                    parser,
                    _with_scalar(base, "--max-position-quantity", value),
                    "max_position_quantity",
                    1000,
                    int,
                )

    def test_initial_cash_rejection_contracts_differ(self) -> None:
        finite = "initial_cash must be a finite non-negative number."
        shared = [("-1", finite, False), ("nan", finite, False), ("inf", finite, False), ("-inf", finite, True)]
        for value, fragment, attached in shared:
            self.assert_rejected(paper_cli._parse_args, _with_scalar(PAPER_BASE, "--initial-cash", value, attached=attached), fragment)
            self.assert_rejected(portfolio_cli._parse_args, _with_scalar(PORTFOLIO_BASE, "--initial-cash", value, attached=attached), fragment)
        for value in ("true", "false"):
            self.assert_rejected(paper_cli._parse_args, _with_scalar(PAPER_BASE, "--initial-cash", value), "initial_cash must be numeric.")
            self.assert_rejected(portfolio_cli._parse_args, _with_scalar(PORTFOLIO_BASE, "--initial-cash", value), "initial_cash must be numeric.")
        self.assert_rejected(
            paper_cli._parse_args,
            _with_scalar(PAPER_BASE, "--initial-cash", "nonnumeric"),
            "invalid check_initial_cash value: 'nonnumeric'",
        )
        self.assert_rejected(
            portfolio_cli._parse_args,
            _with_scalar(PORTFOLIO_BASE, "--initial-cash", "nonnumeric"),
            "initial_cash must be numeric.",
        )

    def test_quantity_rejection_contracts_differ(self) -> None:
        for value in ("0", "-1"):
            for parser, base in ((paper_cli._parse_args, PAPER_BASE), (portfolio_cli._parse_args, PORTFOLIO_BASE)):
                self.assert_rejected(parser, _with_scalar(base, "--quantity-per-trade", value), "quantity_per_trade must be a positive integer.")
        for value in ("1000.0", "1.5"):
            for parser, base in ((paper_cli._parse_args, PAPER_BASE), (portfolio_cli._parse_args, PORTFOLIO_BASE)):
                self.assert_rejected(parser, _with_scalar(base, "--quantity-per-trade", value), "quantity_per_trade must be an integer.")
        for value, attached in (("nan", False), ("inf", False), ("-inf", True), ("true", False), ("false", False), ("nonnumeric", False), ("1e3", False)):
            self.assert_rejected(
                paper_cli._parse_args,
                _with_scalar(PAPER_BASE, "--quantity-per-trade", value, attached=attached),
                f"invalid check_quantity value: '{value}'",
            )
            self.assert_rejected(
                portfolio_cli._parse_args,
                _with_scalar(PORTFOLIO_BASE, "--quantity-per-trade", value, attached=attached),
                "quantity_per_trade must be an integer.",
            )

    def test_rate_rejection_contracts_differ(self) -> None:
        for flag in ("--fee-rate", "--tax-rate", "--slippage-per-share"):
            for value, attached in (("-0.1", False), ("nan", False), ("inf", False), ("-inf", True)):
                for parser, base in ((paper_cli._parse_args, PAPER_BASE), (portfolio_cli._parse_args, PORTFOLIO_BASE)):
                    self.assert_rejected(parser, _with_scalar(base, flag, value, attached=attached), "Rate must be a finite non-negative number.")
            for value in ("true", "false", "nonnumeric"):
                self.assert_rejected(paper_cli._parse_args, _with_scalar(PAPER_BASE, flag, value), f"invalid check_rate value: '{value}'")
                self.assert_rejected(portfolio_cli._parse_args, _with_scalar(PORTFOLIO_BASE, flag, value), "Rate must be numeric.")

    def test_notional_rejection_contracts_match(self) -> None:
        for parser, base, flags in (
            (paper_cli._parse_args, PAPER_BASE, ("--max-order-notional", "--max-position-notional")),
            (portfolio_cli._parse_args, PORTFOLIO_BASE, ("--max-order-notional", "--max-position-notional", "--max-total-exposure")),
        ):
            for flag in flags:
                for value, attached in (("0", False), ("-1", False), ("nan", False), ("inf", False), ("-inf", True)):
                    self.assert_rejected(parser, _with_scalar(base, flag, value, attached=attached), "Notional must be a finite strictly positive number.")
                for value in ("true", "false", "nonnumeric"):
                    self.assert_rejected(parser, _with_scalar(base, flag, value), "Notional must be numeric.")

    def test_max_position_quantity_rejection_contracts_differ(self) -> None:
        for value in ("1000.0", "1.5"):
            for parser, base in ((paper_cli._parse_args, PAPER_BASE), (portfolio_cli._parse_args, PORTFOLIO_BASE)):
                self.assert_rejected(parser, _with_scalar(base, "--max-position-quantity", value), "Quantity must be a strict integer.")
        for value in ("0", "-1"):
            for parser, base in ((paper_cli._parse_args, PAPER_BASE), (portfolio_cli._parse_args, PORTFOLIO_BASE)):
                self.assert_rejected(parser, _with_scalar(base, "--max-position-quantity", value), "Quantity must be a strictly positive integer.")
        for value, attached in (("nan", False), ("inf", False), ("-inf", True), ("true", False), ("false", False), ("nonnumeric", False)):
            self.assert_rejected(
                paper_cli._parse_args,
                _with_scalar(PAPER_BASE, "--max-position-quantity", value, attached=attached),
                "Quantity must be a positive integer.",
            )
            self.assert_rejected(
                portfolio_cli._parse_args,
                _with_scalar(PORTFOLIO_BASE, "--max-position-quantity", value, attached=attached),
                "Quantity must be a strictly positive integer.",
            )

    def test_negative_infinity_tokenization_and_unsupported_flag(self) -> None:
        self.assert_rejected(
            portfolio_cli._parse_args,
            PORTFOLIO_BASE + ["--fee-rate=-inf"],
            "Rate must be a finite non-negative number.",
        )
        self.assert_rejected(
            portfolio_cli._parse_args,
            PORTFOLIO_BASE + ["--fee-rate", "-inf"],
            "argument --fee-rate: expected one argument",
        )
        self.assert_rejected(
            paper_cli._parse_args,
            PAPER_BASE + ["--max-total-exposure", "1000"],
            "unrecognized arguments: --max-total-exposure",
        )

    def test_invalid_parser_input_never_invokes_engines(self) -> None:
        with patch.object(paper_cli, "run_simulated_paper_trading_result") as paper_engine:
            self.assert_rejected(
                paper_cli.main,
                _with_scalar(PAPER_BASE, "--initial-cash", "true"),
                "initial_cash must be numeric.",
            )
        paper_engine.assert_not_called()

        with patch.object(portfolio_cli, "run_simulated_portfolio_trading_result") as portfolio_engine:
            self.assert_rejected(
                portfolio_cli.main,
                _with_scalar(PORTFOLIO_BASE, "--initial-cash", "true"),
                "initial_cash must be numeric.",
            )
        portfolio_engine.assert_not_called()


if __name__ == "__main__":
    unittest.main()
