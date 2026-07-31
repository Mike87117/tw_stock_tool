import argparse
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from io import StringIO
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.application.research_run import SymbolRequest
from tw_stock_tool.cli import backtest_report, daily_report_cli, parameter_sweep_report
from tw_stock_tool.cli import simulated_paper_trading_cli, walk_forward_report
from tw_stock_tool.utils import doctor


def _namespace(**values):
    return argparse.Namespace(**values)


def _analysis_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [10.0],
            "Close": [11.0],
            "entry_signal": [False],
            "exit_signal": [False],
        },
        index=pd.to_datetime(["2026-01-01"]),
    )


def _paper_summary() -> dict[str, object]:
    return {
        "symbol": "2330",
        "initial_cash": 1000,
        "final_cash": 1000,
        "final_position_quantity": 0,
        "realized_pnl": 0,
        "unrealized_pnl": 0,
        "total_equity": 1000,
        "total_return": 0,
        "total_return_pct": 0,
        "order_count": 0,
        "fill_count": 0,
    }


CASES = (
    (
        "backtest_report",
        backtest_report,
        _namespace(
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
            max_hold_days=None,
            manifest_path=None,
        ),
        "run_backtest",
        [],
    ),
    (
        "daily_report_cli",
        daily_report_cli,
        _namespace(
            stocks=["2330"],
            file=None,
            auto_stock_list=False,
            stock_market="all",
            stock_list_output="stocks.txt",
            allow_partial_stock_list=False,
            stock_limit=None,
            stock_sample=None,
            random_state=42,
            period="1y",
            interval="1d",
            signals=["BUY"],
            min_score=4.0,
            top=20,
            force_refresh=False,
            auto_adjust=False,
            output_md=None,
            output_excel=None,
            output_json=None,
            output_dir="output",
            overwrite=False,
            manifest_path=None,
        ),
        "run_daily",
        ["--stock-market", "bad"],
    ),
    (
        "parameter_sweep_report",
        parameter_sweep_report,
        _namespace(
            stock="2330",
            strategy="ma_cross",
            period="1y",
            output_md=None,
            output_excel=None,
            output_dir="output",
            force_refresh=False,
            ma_short_windows=None,
            ma_long_windows=None,
            rsi_buy_below=None,
            rsi_sell_above=None,
            score_buy=None,
            score_sell=None,
            initial_capital=100000,
            fee_rate=0.001425,
            tax_rate=0.003,
            position_size=1.0,
            stop_loss_pct=None,
            take_profit_pct=None,
            max_hold_days=None,
        ),
        "run_parameter_sweep",
        [],
    ),
    (
        "simulated_paper_trading_cli",
        simulated_paper_trading_cli,
        _namespace(
            stock="2330",
            strategy="ma_cross",
            period="1y",
            initial_cash=1000,
            quantity_per_trade=10,
            fee_rate=0.001425,
            tax_rate=0.003,
            slippage_per_share=0.0,
            force_refresh=False,
            max_order_notional=None,
            max_position_quantity=None,
            max_position_notional=None,
        ),
        "analyze_stock",
        [],
    ),
    (
        "walk_forward_report",
        walk_forward_report,
        _namespace(
            stock="2330",
            strategy="ma_cross",
            period="1y",
            output_md=None,
            output_excel=None,
            output_dir="output",
            force_refresh=False,
            ma_short_windows=None,
            ma_long_windows=None,
            rsi_buy_below=None,
            rsi_sell_above=None,
            score_buy=None,
            score_sell=None,
            train_days=10,
            test_days=5,
            step_days=None,
            sort_by="Train Sharpe Ratio",
            initial_capital=100000,
            fee_rate=0.001425,
            tax_rate=0.003,
            position_size=1.0,
            stop_loss_pct=None,
            take_profit_pct=None,
            max_hold_days=None,
        ),
        "run_walk_forward",
        [],
    ),
    (
        "doctor",
        doctor,
        _namespace(live=False),
        "run_doctor",
        ["--unknown"],
    ),
)


EXPORTS = {
    "backtest_report": (
        "export_backtest_report_excel",
        "export_backtest_report_markdown",
    ),
    "parameter_sweep_report": (
        "export_parameter_sweep_report_excel",
        "export_parameter_sweep_report_markdown",
    ),
    "walk_forward_report": (
        "export_walk_forward_report_excel",
        "export_walk_forward_report_markdown",
    ),
}


def _research_result():
    return SimpleNamespace(
        domain_result={
            "Total Return %": 1,
            "Win Rate %": 1,
            "Trade Count": 1,
        },
        generated_artifacts=(),
    )


def _patch_success(stack: ExitStack, case):
    name, module, args, _, _ = case
    stack.enter_context(patch.object(module, "_parse_args", return_value=args))
    if name == "backtest_report":
        stack.enter_context(
            patch.object(
                module,
                "resolve_symbol_request",
                return_value=SymbolRequest("2330", "2330.TW"),
            )
        )
        stack.enter_context(
            patch.object(module, "run_backtest", return_value=_research_result())
        )
        stack.enter_context(patch.object(module, "analyze_stock"))
        stack.enter_context(patch.object(module, "legacy_run_backtest"))
        for exporter in EXPORTS[name]:
            stack.enter_context(patch.object(module, exporter))
    elif name == "daily_report_cli":
        stack.enter_context(
            patch.object(
                module,
                "collect_symbol_requests",
                return_value=(SymbolRequest("2330", "2330.TW"),),
            )
        )
        stack.enter_context(
            patch.object(module, "run_daily", return_value=_research_result())
        )
        stack.enter_context(patch.object(module, "collect_stock_ids"))
        stack.enter_context(patch.object(module, "run_daily_research_pipeline"))
        stack.enter_context(patch.object(module, "export_daily_report_json_file"))
        stack.enter_context(patch("builtins.open"))
        stack.enter_context(patch.object(__import__("pathlib").Path, "mkdir"))
    elif name == "parameter_sweep_report":
        stack.enter_context(
            patch.object(
                module,
                "run_parameter_sweep",
                return_value=pd.DataFrame({"Result": [1]}),
            )
        )
        stack.enter_context(
            patch.object(
                module,
                "build_parameter_sweep_report_data",
                return_value={"Best Row": {}},
            )
        )
    elif name == "simulated_paper_trading_cli":
        stack.enter_context(
            patch.object(module, "STRATEGIES", {"ma_cross_strategy": lambda df: df})
        )
        stack.enter_context(
            patch.object(
                module,
                "analyze_stock",
                return_value=SimpleNamespace(
                    symbol="2330",
                    indicator_df=_analysis_frame(),
                ),
            )
        )
        stack.enter_context(
            patch.object(module, "run_simulated_paper_trading_result", return_value=object())
        )
        stack.enter_context(
            patch.object(
                module,
                "build_simulated_paper_trading_summary",
                return_value=_paper_summary(),
            )
        )
    elif name == "walk_forward_report":
        stack.enter_context(
            patch.object(module, "run_walk_forward", return_value=pd.DataFrame())
        )
        stack.enter_context(
            patch.object(
                module,
                "build_walk_forward_report_data",
                return_value={"Best Window": {}},
            )
        )
    else:
        stack.enter_context(
            patch.object(
                module,
                "run_doctor",
                return_value=[
                    {"Status": module.PASS, "Check": "local", "Message": ""}
                ],
            )
        )
        stack.enter_context(patch.object(module, "print_report"))


def _patch_failure(stack: ExitStack, case):
    name, module, args, boundary, _ = case
    stack.enter_context(patch.object(module, "_parse_args", return_value=args))
    if name == "doctor":
        return stack.enter_context(
            patch.object(
                module,
                "run_doctor",
                return_value=[
                    {
                        "Status": module.FAIL,
                        "Check": "offline",
                        "Message": "controlled failure",
                    }
                ],
            )
        )
    if name == "backtest_report":
        stack.enter_context(
            patch.object(
                module,
                "resolve_symbol_request",
                return_value=SymbolRequest("2330", "2330.TW"),
            )
        )
    if name == "daily_report_cli":
        stack.enter_context(
            patch.object(
                module,
                "collect_symbol_requests",
                return_value=(SymbolRequest("2330", "2330.TW"),),
            )
        )
    failure = stack.enter_context(
        patch.object(
            module,
            boundary,
            side_effect=RuntimeError("controlled failure"),
        )
    )
    for exporter in EXPORTS.get(name, ()):
        stack.enter_context(patch.object(module, exporter))
    return failure


class CliExitContractsTest(unittest.TestCase):
    def test_direct_success_returns_none(self) -> None:
        for case in CASES:
            with self.subTest(target=case[0]):
                output = StringIO()
                with ExitStack() as stack:
                    _patch_success(stack, case)
                    with redirect_stdout(output):
                        result = case[1].main()
                self.assertIsNone(result)
                if case[0] != "doctor":
                    self.assertNotIn("Error:", output.getvalue())

    def test_direct_failures_return_one_without_traceback(self) -> None:
        for case in CASES:
            with self.subTest(target=case[0]):
                output = StringIO()
                errors = StringIO()
                with ExitStack() as stack:
                    boundary = _patch_failure(stack, case)
                    with redirect_stdout(output), redirect_stderr(errors):
                        result = case[1].main()
                self.assertEqual(result, 1)
                combined = output.getvalue() + errors.getvalue()
                self.assertNotIn("Traceback", combined)
                self.assertNotIn("successfully", output.getvalue().lower())
                if case[0] == "doctor":
                    self.assertIn("FAIL", output.getvalue())
                else:
                    self.assertIn("Error: controlled failure", output.getvalue())
                    boundary.assert_called_once()

    def test_daily_no_stock_returns_one_without_runtime_call(self) -> None:
        case = next(item for item in CASES if item[0] == "daily_report_cli")
        output = StringIO()
        with patch.object(case[1], "_parse_args", return_value=case[2]):
            with patch.object(
                case[1],
                "collect_symbol_requests",
                side_effect=ValueError("No stocks provided."),
            ):
                with patch.object(case[1], "run_daily") as run_daily:
                    with redirect_stdout(output):
                        result = case[1].main()

        self.assertEqual(result, 1)
        self.assertEqual(output.getvalue(), "Error: No stocks provided.\n")
        run_daily.assert_not_called()

    def test_parser_help_and_usage_codes_are_preserved(self) -> None:
        for name, module, _, _, invalid_args in CASES:
            with self.subTest(target=name, mode="help"):
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        module._parse_args(["--help"])
                self.assertEqual(raised.exception.code, 0)
            with self.subTest(target=name, mode="usage"):
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        module._parse_args(invalid_args)
                self.assertEqual(raised.exception.code, 2)

    def test_simulated_parser_system_exit_is_reraised_by_main(self) -> None:
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as raised:
                simulated_paper_trading_cli.main(["--invalid"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
