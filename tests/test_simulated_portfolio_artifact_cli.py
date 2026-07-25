"""
Unit tests for offline simulated portfolio artifact CLI.
"""

import ast
import io

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tw_stock_tool.cli import simulated_portfolio_artifact_cli
from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedFill,
    SimulatedOrder,
    SimulatedOrderRejection,
    SimulatedTradeEventType,
    SimulatedTradeLogRecord,
    SimulatedTradeStatus,
)
from tw_stock_tool.paper_trading.portfolio_results import (
    SimulatedPortfolioPendingOrderResult,
    SimulatedPortfolioPositionResult,
    SimulatedPortfolioTradingResult,
)
from tw_stock_tool.paper_trading.portfolio_serialization import (
    export_simulated_portfolio_trading_result_json,
)
from tw_stock_tool.paper_trading.portfolio_serialization_files import (
    export_simulated_portfolio_trading_result_json_file,
)


def _make_sample_portfolio_result() -> SimulatedPortfolioTradingResult:
    pos1 = SimulatedPortfolioPositionResult(
        symbol="2330.TW",
        quantity=1000,
        average_cost=500.0,
        last_price=550.0,
        market_value=550000.0,
        realized_pnl=10000.0,
        unrealized_pnl=50000.0,
    )
    pending1 = SimulatedPortfolioPendingOrderResult(
        order_id="ORD_P1",
        symbol="2330.TW",
        side="BUY",
        quantity=500,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="ma_cross",
        reference_price=540.0,
        reserved_buy_notional=270000.0,
    )
    order1 = SimulatedOrder(
        order_id="ORD_1",
        symbol="2330.TW",
        side="BUY",
        quantity=1000,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="ma_cross",
    )
    fill1 = SimulatedFill(
        order_id="ORD_1",
        symbol="2330.TW",
        side="BUY",
        quantity=1000,
        price=500.0,
        filled_at="2026-01-02T09:00:01",
        fee=712.0,
        tax=0.0,
        slippage=0.0,
    )
    rejection1 = SimulatedOrderRejection(
        candidate_order=SimulatedOrder(
            order_id="ORD_R1",
            symbol="2454.TW",
            side="BUY",
            quantity=100,
            signal_time="2026-01-02",
            created_at="2026-01-02T09:00:00",
            strategy="rsi",
        ),
        reasons=("風控拒絕",),
    )
    rec1 = SimulatedTradeLogRecord(
        sequence=1,
        record_id="REC_1",
        event_type=SimulatedTradeEventType.ACCEPTED_PENDING,
        status=SimulatedTradeStatus.PENDING_NEXT_BAR_OPEN,
        order_id="ORD_1",
        symbol="2330.TW",
        side="BUY",
        quantity=1000,
        signal_time="2026-01-02",
        order_created_at="2026-01-02T09:00:00",
        expected_execution_model="next_bar_open",
        fill_time=None,
        fill_price=None,
        fee=0.0,
        tax=0.0,
        slippage=0.0,
        strategy_name="ma_cross",
        strategy_metadata={"window": 10},
        risk_allowed=True,
        risk_rejection_reasons=(),
        guard_metadata={"guard": "ok"},
        error_code=None,
        error_message=None,
    )

    return SimulatedPortfolioTradingResult(
        initial_cash=1000000.0,
        final_cash=1000000.0,
        total_market_value=550000.0,
        total_equity=1550000.0,
        realized_pnl=10000.0,
        unrealized_pnl=50000.0,
        total_return=550000.0,
        total_return_pct=0.55,
        open_position_count=1,
        order_count=1,
        fill_count=1,
        rejection_count=1,
        audit_record_count=1,
        positions=(pos1,),
        pending_orders=(pending1,),
        orders=(order1,),
        fills=(fill1,),
        rejections=(rejection1,),
        audit_log=(rec1,),
    )


class TestSimulatedPortfolioArtifactCLI(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.result = _make_sample_portfolio_result()
        self.valid_json_path = self.temp_dir / "valid_portfolio.json"
        export_simulated_portfolio_trading_result_json_file(
            self.result,
            self.valid_json_path,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cli_help_code_zero_and_parser_errors(self) -> None:
        help_commands = [
            ["--help"],
            ["validate", "--help"],
            ["inspect", "--help"],
            ["export-markdown", "--help"],
            ["export-csv", "--help"],
        ]

        for args in help_commands:
            with self.subTest(args=args):
                out_buf = io.StringIO()
                with patch("sys.stdout", out_buf), self.assertRaises(SystemExit) as cm:
                    simulated_portfolio_artifact_cli.main(args)
                self.assertEqual(cm.exception.code, 0)

        # Root help contains all 11 required safety phrases
        root_buf = io.StringIO()
        with patch("sys.stdout", root_buf), self.assertRaises(SystemExit):
            simulated_portfolio_artifact_cli.main(["--help"])
        root_text = root_buf.getvalue()

        safety_phrases = [
            "existing offline simulated portfolio trading JSON artifact",
            "Does not fetch market data",
            "run analysis",
            "execute strategies or backtests",
            "execute simulated trading",
            "run the portfolio coordinator",
            "connect to brokers",
            "place orders",
            "produce live signals",
            "recommend stocks",
            "provide investment advice",
        ]
        for phrase in safety_phrases:
            self.assertIn(phrase, root_text, f"Safety phrase missing: {phrase}")

        # Parser error code 2
        invalid_args_list = [
            [],
            ["validate"],
            ["inspect"],
            ["export-markdown", str(self.valid_json_path)],
            ["export-csv", str(self.valid_json_path)],
            ["unapproved-subcommand"],
        ]
        for inv_args in invalid_args_list:
            with self.subTest(invalid_args=inv_args):
                err_buf = io.StringIO()
                with patch("sys.stderr", err_buf), self.assertRaises(SystemExit) as cm:
                    simulated_portfolio_artifact_cli.main(inv_args)
                self.assertEqual(cm.exception.code, 2)

    def test_validate_subcommand_failure_matrix_and_exact_success(self) -> None:
        # Success exact output format (exact newline, no strip)
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
            ret = simulated_portfolio_artifact_cli.main(["validate", str(self.valid_json_path)])

        self.assertTrue(ret is None or ret == 0)
        self.assertEqual(
            out_buf.getvalue(),
            f"Simulated Portfolio Trading artifact is valid: {self.valid_json_path}\n",
        )
        self.assertEqual(err_buf.getvalue(), "")

        # Failure matrix
        failures = []

        # 1. Malformed JSON
        p1 = self.temp_dir / "f1.json"
        p1.write_text("{bad json}", encoding="utf-8")
        failures.append(p1)

        # 2. Unsupported schema version
        p2 = self.temp_dir / "f2.json"
        d2 = json.loads(export_simulated_portfolio_trading_result_json(self.result))
        d2["schema_version"] = "v999"
        p2.write_text(json.dumps(d2), encoding="utf-8")
        failures.append(p2)

        # 3. Missing required field
        p3 = self.temp_dir / "f3.json"
        d3 = json.loads(export_simulated_portfolio_trading_result_json(self.result))
        del d3["schema_version"]
        p3.write_text(json.dumps(d3), encoding="utf-8")
        failures.append(p3)

        # 4. Extra field
        p4 = self.temp_dir / "f4.json"
        d4 = json.loads(export_simulated_portfolio_trading_result_json(self.result))
        d4["unexpected_extra"] = True
        p4.write_text(json.dumps(d4), encoding="utf-8")
        failures.append(p4)

        # 5. Malformed UTF-8 bytes
        p5 = self.temp_dir / "f5.json"
        p5.write_bytes(b"\x80\x81\x82")
        failures.append(p5)

        # 6. Missing file
        p6 = self.temp_dir / "missing_file.json"
        failures.append(p6)

        # 7. Directory path
        p7 = self.temp_dir / "dir_path"
        p7.mkdir()
        failures.append(p7)

        for path_arg in failures:
            with self.subTest(path=str(path_arg)):
                out_buf = io.StringIO()
                err_buf = io.StringIO()
                with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
                    ret = simulated_portfolio_artifact_cli.main(["validate", str(path_arg)])

                self.assertEqual(ret, 1)
                self.assertEqual(out_buf.getvalue(), "")
                err_text = err_buf.getvalue()
                self.assertTrue(err_text.startswith("error: "))
                self.assertNotIn("Traceback", err_text)

        # 8. Mocked PermissionError during load
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        with patch(
            "tw_stock_tool.cli.simulated_portfolio_artifact_cli.load_simulated_portfolio_trading_result_json_file",
            side_effect=PermissionError("Permission denied loading artifact"),
        ):
            with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
                ret = simulated_portfolio_artifact_cli.main(["validate", str(self.valid_json_path)])

            self.assertEqual(ret, 1)
            self.assertEqual(out_buf.getvalue(), "")
            err_text = err_buf.getvalue()
            self.assertTrue(err_text.startswith("error: "))
            self.assertIn("Permission denied loading artifact", err_text)
            self.assertNotIn("Traceback", err_text)

    def test_inspect_subcommand_call_contract_and_exact_stdout(self) -> None:
        mock_loaded_result = MagicMock(spec=SimulatedPortfolioTradingResult)
        mock_summary = {
            "initial_cash": 1000000.0,
            "final_cash": 1000000.0,
            "total_market_value": 550000.0,
            "total_equity": 1550000.0,
            "realized_pnl": 10000.0,
            "unrealized_pnl": 50000.0,
            "total_return": 550000.0,
            "total_return_pct": 0.55,
            "open_position_count": 1,
            "pending_order_count": 1,
            "order_count": 1,
            "fill_count": 1,
            "rejection_count": 1,
            "audit_record_count": 1,
        }

        out_buf = io.StringIO()
        err_buf = io.StringIO()

        with patch(
            "tw_stock_tool.cli.simulated_portfolio_artifact_cli.load_simulated_portfolio_trading_result_json_file",
            return_value=mock_loaded_result,
        ) as mock_loader, patch(
            "tw_stock_tool.cli.simulated_portfolio_artifact_cli.build_simulated_portfolio_trading_summary",
            return_value=mock_summary,
        ) as mock_builder:
            with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
                ret = simulated_portfolio_artifact_cli.main(["inspect", str(self.valid_json_path)])

            mock_loader.assert_called_once_with(str(self.valid_json_path))
            mock_builder.assert_called_once()
            self.assertIs(mock_builder.call_args[0][0], mock_loaded_result)

        self.assertTrue(ret is None or ret == 0)
        self.assertEqual(err_buf.getvalue(), "")

        output = out_buf.getvalue()
        expected_lines = [
            "Simulated Portfolio Trading Artifact Summary",
            "--------------------------------------------",
            "Initial Cash: 1000000.0",
            "Final Cash: 1000000.0",
            "Total Market Value: 550000.0",
            "Total Equity: 1550000.0",
            "Realized PnL: 10000.0",
            "Unrealized PnL: 50000.0",
            "Total Return: 550000.0",
            "Total Return Pct: 0.55",
            "Open Position Count: 1",
            "Pending Order Count: 1",
            "Order Count: 1",
            "Fill Count: 1",
            "Rejection Count: 1",
            "Audit Record Count: 1",
        ]
        self.assertEqual(output.splitlines(), expected_lines)

        # Forbidden fields absent
        forbidden_strings = ["2330.TW", "ORD_P1", "ORD_1", "ORD_R1", "REC_1", "schema_version", "v1"]
        for s in forbidden_strings:
            self.assertNotIn(s, output)

        # Raw total_return_pct string test
        self.assertIn("Total Return Pct: 0.55", output)
        self.assertNotIn("55%", output)

    def test_export_markdown_subcommand_call_contract_and_failures(self) -> None:
        mock_loaded_result = MagicMock(spec=SimulatedPortfolioTradingResult)
        returned_path = Path("/mock/dir/portfolio.md").resolve()

        out_buf = io.StringIO()
        err_buf = io.StringIO()

        with patch(
            "tw_stock_tool.cli.simulated_portfolio_artifact_cli.load_simulated_portfolio_trading_result_json_file",
            return_value=mock_loaded_result,
        ) as mock_loader, patch(
            "tw_stock_tool.cli.simulated_portfolio_artifact_cli.export_simulated_portfolio_trading_markdown_file",
            return_value=returned_path,
        ) as mock_exporter:
            with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
                ret = simulated_portfolio_artifact_cli.main([
                    "export-markdown",
                    str(self.valid_json_path),
                    "--output-markdown",
                    "out.md",
                    "--overwrite",
                ])

            mock_loader.assert_called_once_with(str(self.valid_json_path))
            mock_exporter.assert_called_once_with(mock_loaded_result, "out.md", overwrite=True)

        self.assertTrue(ret is None or ret == 0)
        self.assertEqual(err_buf.getvalue(), "")
        self.assertEqual(
            out_buf.getvalue(),
            f"Simulated Portfolio Trading Markdown written: {returned_path}\n",
        )

        # Real filesystem test: input JSON bytes preserved
        real_md_out = self.temp_dir / "real_out.md"
        input_bytes_before = self.valid_json_path.read_bytes()
        with patch("sys.stdout", io.StringIO()):
            simulated_portfolio_artifact_cli.main([
                "export-markdown",
                str(self.valid_json_path),
                "--output-markdown",
                str(real_md_out),
            ])
        self.assertEqual(self.valid_json_path.read_bytes(), input_bytes_before)
        self.assertTrue(real_md_out.is_file())


        # Failure cases: FileExistsError, PermissionError, PaperTradingModelError
        failure_mocks = [
            FileExistsError("File exists"),
            PermissionError("Permission denied"),
            PaperTradingModelError("Invalid model"),
        ]

        for exc in failure_mocks:
            with self.subTest(exception=type(exc).__name__):
                out_buf = io.StringIO()
                err_buf = io.StringIO()
                with patch(
                    "tw_stock_tool.cli.simulated_portfolio_artifact_cli.export_simulated_portfolio_trading_markdown_file",
                    side_effect=exc,
                ):
                    with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
                        ret = simulated_portfolio_artifact_cli.main([
                            "export-markdown",
                            str(self.valid_json_path),
                            "--output-markdown",
                            str(real_md_out),
                        ])

                self.assertEqual(ret, 1)
                self.assertEqual(out_buf.getvalue(), "")
                err_text = err_buf.getvalue()
                self.assertTrue(err_text.startswith("error: "))
                self.assertNotIn("Traceback", err_text)
                if isinstance(exc, FileExistsError):
                    self.assertIn("Use --overwrite", err_text)

    def test_export_csv_subcommand_call_contract_and_failures(self) -> None:
        mock_loaded_result = MagicMock(spec=SimulatedPortfolioTradingResult)
        expected_keys = (
            "summary",
            "positions",
            "pending_orders",
            "orders",
            "fills",
            "rejections",
            "trade_log",
        )
        mock_paths_dict = {k: Path(f"/mock/dir/sim_{k}.csv").resolve() for k in expected_keys}

        out_buf = io.StringIO()
        err_buf = io.StringIO()

        with patch(
            "tw_stock_tool.cli.simulated_portfolio_artifact_cli.load_simulated_portfolio_trading_result_json_file",
            return_value=mock_loaded_result,
        ) as mock_loader, patch(
            "tw_stock_tool.cli.simulated_portfolio_artifact_cli.export_simulated_portfolio_trading_csv_files",
            return_value=mock_paths_dict,
        ) as mock_exporter:
            with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
                ret = simulated_portfolio_artifact_cli.main([
                    "export-csv",
                    str(self.valid_json_path),
                    "--output-csv-dir",
                    "csv_dir",
                    "--basename",
                    "custom_base",
                    "--overwrite",
                ])

            mock_loader.assert_called_once_with(str(self.valid_json_path))
            mock_exporter.assert_called_once_with(
                mock_loaded_result,
                "csv_dir",
                basename="custom_base",
                overwrite=True,
            )

        self.assertTrue(ret is None or ret == 0)
        self.assertEqual(err_buf.getvalue(), "")

        expected_stdout_lines = [
            "Simulated Portfolio Trading CSV files written:",
            *[f"{k}: {mock_paths_dict[k]}" for k in expected_keys],
        ]
        self.assertEqual(out_buf.getvalue().splitlines(), expected_stdout_lines)

        # Failure cases: FileExistsError, ValueError, PermissionError, PaperTradingModelError
        failure_exceptions = [
            FileExistsError("CSV target exists"),
            ValueError("Invalid basename"),
            PermissionError("CSV write denied"),
            PaperTradingModelError("Model error"),
        ]

        csv_out_dir = self.temp_dir / "real_csv_dir"

        for exc in failure_exceptions:
            with self.subTest(exception=type(exc).__name__):
                out_buf = io.StringIO()
                err_buf = io.StringIO()
                with patch(
                    "tw_stock_tool.cli.simulated_portfolio_artifact_cli.export_simulated_portfolio_trading_csv_files",
                    side_effect=exc,
                ):
                    with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
                        ret = simulated_portfolio_artifact_cli.main([
                            "export-csv",
                            str(self.valid_json_path),
                            "--output-csv-dir",
                            str(csv_out_dir),
                        ])

                self.assertEqual(ret, 1)
                self.assertEqual(out_buf.getvalue(), "")
                err_text = err_buf.getvalue()
                self.assertTrue(err_text.startswith("error: "))
                self.assertNotIn("Traceback", err_text)
                if isinstance(exc, FileExistsError):
                    self.assertIn("Use --overwrite", err_text)

        # Real filesystem export: input JSON bytes preserved
        input_bytes_before = self.valid_json_path.read_bytes()
        with patch("sys.stdout", io.StringIO()):
            simulated_portfolio_artifact_cli.main([
                "export-csv",
                str(self.valid_json_path),
                "--output-csv-dir",
                str(csv_out_dir),
            ])
        self.assertEqual(self.valid_json_path.read_bytes(), input_bytes_before)
        self.assertTrue((csv_out_dir / "simulated_portfolio_trading_summary.csv").is_file())


    def test_ast_and_subprocess_dependency_boundaries(self) -> None:
        cli_file = Path(simulated_portfolio_artifact_cli.__file__)
        tree = ast.parse(cli_file.read_text(encoding="utf-8"))

        forbidden_prefixes = (
            "tw_stock_tool.data",
            "tw_stock_tool.strategies",
            "tw_stock_tool.backtesting",
            "tw_stock_tool.ml",
            "tw_stock_tool.gui",
            "tw_stock_tool.paper_trading.engine",
            "tw_stock_tool.paper_trading.portfolio_coordinator",
            "tw_stock_tool.paper_trading.coordinator",
            "tw_stock_tool.paper_trading.risk_manager",
            "tw_stock_tool.paper_trading.risk",
            "tw_stock_tool.paper_trading.kill_switch",
        )

        forbidden_basenames = (
            "data",
            "strategies",
            "backtesting",
            "ml",
            "gui",
            "engine",
            "portfolio_coordinator",
            "coordinator",
            "risk_manager",
            "risk",
            "kill_switch",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_prefixes:
                        self.assertFalse(alias.name.startswith(forbidden), f"AST import forbidden: {alias.name}")
                    for base in forbidden_basenames:
                        self.assertNotEqual(alias.name.split(".")[-1], base, f"AST import basename forbidden: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in forbidden_prefixes:
                        self.assertFalse(node.module.startswith(forbidden), f"AST import-from forbidden: {node.module}")
                    for base in forbidden_basenames:
                        self.assertNotEqual(node.module.split(".")[-1], base, f"AST import-from basename forbidden: {node.module}")

        # Subprocess clean import check
        cmd = [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import tw_stock_tool.cli.simulated_portfolio_artifact_cli; "
                "forbidden=['tw_stock_tool.data', 'tw_stock_tool.strategies', 'tw_stock_tool.ml', "
                "'tw_stock_tool.gui', 'yfinance', 'sklearn', 'matplotlib', 'mplfinance', 'shioaji']; "
                "loaded=[m for m in forbidden if m in sys.modules]; "
                "print(loaded)"
            ),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        self.assertEqual(proc.stdout.strip(), "[]")


if __name__ == "__main__":
    unittest.main()
