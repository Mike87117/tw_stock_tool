from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tw_stock_tool.application.research_run import BacktestRunRequest, SymbolRequest
from tw_stock_tool.cli import backtest_report
from tw_stock_tool.cli.backtest_report import _normalize_result, _parse_args, main
from tw_stock_tool.research_run.models import ArtifactReference


def _result(*, markdown: bool = True, excel: bool = True):
    artifacts = []
    if markdown:
        artifacts.append(ArtifactReference("backtest_report_markdown", "reports/backtest.md", "text/markdown", None))
    if excel:
        artifacts.append(ArtifactReference("backtest_report_excel", "reports/backtest.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", None))
    return SimpleNamespace(
        generated_artifacts=tuple(artifacts),
        domain_result={"Total Return %": 5.0, "Win Rate %": 20.0, "Trade Count": 3},
    )


class TestBacktestReportCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.symbol = SymbolRequest("2330", "2330.TW")

    def _args(self, extra: list[str] | None = None):
        return _parse_args(["--stock", "2330", "--strategy", "ma_cross", *(extra or [])])

    def test_parse_args_manifest_default_custom_and_no_new_market_flags(self):
        self.assertIsNone(_parse_args(["--stock", "2330", "--strategy", "ma_cross"]).manifest_path)
        self.assertEqual(
            _parse_args(["--stock", "2330", "--strategy", "ma_cross", "--manifest-path", "custom/manifest.json"]).manifest_path,
            "custom/manifest.json",
        )
        with self.assertRaises(SystemExit):
            _parse_args(["--stock", "2330", "--strategy", "ma_cross", "--stock-market", "twse"])

    def test_normalize_result_legacy_helper_remains_compatible(self):
        result = _normalize_result({"Total Return %": 10.0}, "2330", "ma_cross", "2024-01-01", "2024-12-31", {"param": 1})
        self.assertEqual(result["Stock"], "2330")
        self.assertEqual(result["Parameters"], {"param": 1})

    def test_exact_request_original_strategy_and_stage_callback(self):
        args = self._args(["--output-md", "custom.md", "--output-excel", "custom.xlsx", "--manifest-path", "manifest.json", "--initial-capital", "200000", "--rsi-buy-below", "25"])
        args.strategy = "ma_cross"
        output = StringIO()
        with patch.object(backtest_report, "resolve_symbol_request", return_value=self.symbol) as resolve:
            with patch.object(backtest_report, "run_backtest", return_value=_result()) as run:
                with patch.object(backtest_report, "_parse_args", return_value=args):
                    with redirect_stdout(output):
                        self.assertIsNone(main())
        resolve.assert_called_once_with("2330", market_hint="all")
        run.assert_called_once()
        request = run.call_args.args[0]
        self.assertIsInstance(request, BacktestRunRequest)
        self.assertIs(request.symbol, self.symbol)
        self.assertEqual(request.strategy, "ma_cross")
        self.assertEqual(request.markdown_path, "custom.md")
        self.assertEqual(request.excel_path, "custom.xlsx")
        self.assertEqual(request.manifest_path, "manifest.json")
        callback = run.call_args.kwargs["stage_callback"]
        with redirect_stdout(output):
            callback("market_data")
            callback("strategy")
            callback("backtest")
        lines = [line for line in output.getvalue().splitlines() if line]
        self.assertEqual(lines[-3:], [
            "Fetching data for 2330 (period=1y)...",
            "Applying strategy ma_cross_strategy...",
            "Running backtest with initial capital 200000.0...",
        ])

    def test_output_defaults_and_artifact_messages(self):
        args = self._args(["--output-md", "", "--output-excel", ""])
        with patch.object(backtest_report, "resolve_symbol_request", return_value=self.symbol):
            with patch.object(backtest_report, "run_backtest", return_value=_result()) as run:
                with patch.object(backtest_report, "_parse_args", return_value=args):
                    output = StringIO()
                    with redirect_stdout(output):
                        self.assertIsNone(main())
        request = run.call_args.args[0]
        self.assertEqual(request.markdown_path, str(Path("output") / "backtest_report.md"))
        self.assertEqual(request.excel_path, str(Path("output") / "backtest_report.xlsx"))
        self.assertIn("Excel report: reports/backtest.xlsx", output.getvalue())
        self.assertIn("Markdown report: reports/backtest.md", output.getvalue())

    def test_no_output_uses_domain_summary(self):
        output = StringIO()
        with patch.object(backtest_report, "resolve_symbol_request", return_value=self.symbol):
            with patch.object(backtest_report, "run_backtest", return_value=_result(markdown=False, excel=False)):
                with patch.object(backtest_report, "_parse_args", return_value=self._args()):
                    with redirect_stdout(output):
                        self.assertIsNone(main())
        text = output.getvalue()
        self.assertIn("Backtest finished. Summary:", text)
        self.assertIn("Total Return: 5.0%", text)
        self.assertIn("Win Rate: 20.0%", text)
        self.assertIn("Trades: 3", text)

    def test_strategy_alias_parameter_mappings(self):
        for strategy, extra, expected in (
            ("ma_cross", [], {"short_window": 5, "long_window": 20}),
            ("rsi", ["--rsi-buy-below", "25", "--rsi-sell-above", "75"], {"buy_below": 25.0, "sell_above": 75.0}),
            ("score_strategy", ["--score-buy", "4.5", "--score-sell", "-1.5"], {"buy_score": 4.5, "sell_score": -1.5}),
        ):
            with self.subTest(strategy=strategy):
                args = _parse_args(["--stock", "2330", "--strategy", strategy, *extra])
                with patch.object(backtest_report, "resolve_symbol_request", return_value=self.symbol):
                    with patch.object(backtest_report, "run_backtest", return_value=_result(markdown=False, excel=False)) as run:
                        with patch.object(backtest_report, "_parse_args", return_value=args):
                            with redirect_stdout(StringIO()):
                                self.assertIsNone(main())
                self.assertEqual(dict(run.call_args.args[0].strategy_parameters), expected)
                self.assertEqual(run.call_args.args[0].strategy, strategy)

    def test_bare_symbol_resolves_all_market_and_explicit_suffix_skips_catalog(self):
        with patch.object(backtest_report, "resolve_symbol_request", return_value=self.symbol) as resolve:
            with patch.object(backtest_report, "run_backtest", return_value=_result(markdown=False, excel=False)):
                with patch.object(backtest_report, "_parse_args", return_value=self._args()):
                    with redirect_stdout(StringIO()):
                        main()
        resolve.assert_called_once_with("2330", market_hint="all")
        explicit = SymbolRequest("2330.TW", "2330.TW")
        args = _parse_args(["--stock", "2330.TW", "--strategy", "ma_cross"])
        with patch.object(backtest_report, "resolve_symbol_request", return_value=explicit) as resolve:
            with patch.object(backtest_report, "run_backtest", return_value=_result(markdown=False, excel=False)):
                with patch.object(backtest_report, "_parse_args", return_value=args):
                    with redirect_stdout(StringIO()):
                        main()
        resolve.assert_called_once_with("2330.TW", market_hint="all")

    def test_unknown_strategy_fails_before_resolution_or_service(self):
        args = _parse_args(["--stock", "2330", "--strategy", "unknown_strategy"])
        with patch.object(backtest_report, "resolve_symbol_request") as resolve:
            with patch.object(backtest_report, "run_backtest") as run:
                with patch.object(backtest_report, "_parse_args", return_value=args):
                    with redirect_stdout(StringIO()):
                        self.assertEqual(main(), 1)
        resolve.assert_not_called()
        run.assert_not_called()

    def test_runtime_error_returns_one(self):
        with patch.object(backtest_report, "resolve_symbol_request", return_value=self.symbol):
            with patch.object(backtest_report, "run_backtest", side_effect=RuntimeError("controlled failure")):
                with patch.object(backtest_report, "_parse_args", return_value=self._args()):
                    output = StringIO()
                    with redirect_stdout(output):
                        self.assertEqual(main(), 1)
        self.assertIn("Error: controlled failure", output.getvalue())

    def test_package_and_unified_process_failure_exit_one(self):
        package = subprocess.run([sys.executable, "-m", "tw_stock_tool.cli.backtest_report", "--stock", "2330", "--strategy", "unknown_strategy"], capture_output=True, text=True)
        self.assertEqual(package.returncode, 1)
        unified = subprocess.run([sys.executable, "-m", "tw_stock_tool.cli.twstock_cli", "backtest-report", "--stock", "2330", "--strategy", "unknown_strategy"], capture_output=True, text=True)
        self.assertEqual(unified.returncode, 1)


if __name__ == "__main__":
    unittest.main()
