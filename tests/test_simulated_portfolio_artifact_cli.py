"""
Unit tests for offline simulated portfolio artifact CLI.
"""

import ast
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tw_stock_tool.cli import simulated_portfolio_artifact_cli
from tw_stock_tool.paper_trading.models import (
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

    def test_parser_help_and_subcommands(self) -> None:
        parser = simulated_portfolio_artifact_cli.build_parser()

        # Help exit code 0
        with self.assertRaises(SystemExit) as cm:
            with patch("sys.stdout", new_callable=io.StringIO):
                parser.parse_args(["--help"])
        self.assertEqual(cm.exception.code, 0)

        # Unapproved subcommands absent
        unapproved = ["export-json", "run", "execute", "trade", "scan", "analyze", "backtest", "recommend"]
        for sub in unapproved:
            with self.assertRaises(SystemExit) as cm:
                with patch("sys.stderr", new_callable=io.StringIO):
                    parser.parse_args([sub])
            self.assertEqual(cm.exception.code, 2)

    def test_validate_subcommand_success_and_failures(self) -> None:
        # Success stdout & exit code
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
            ret = simulated_portfolio_artifact_cli.main(["validate", str(self.valid_json_path)])
        self.assertTrue(ret is None or ret == 0)
        self.assertEqual(
            out_buf.getvalue().strip(),
            f"Simulated Portfolio Trading artifact is valid: {self.valid_json_path}",
        )
        self.assertEqual(err_buf.getvalue(), "")

        # Failure: malformed JSON
        bad_json_path = self.temp_dir / "bad.json"
        bad_json_path.write_text("{bad json}", encoding="utf-8")
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
            ret = simulated_portfolio_artifact_cli.main(["validate", str(bad_json_path)])
        self.assertEqual(ret, 1)
        self.assertEqual(out_buf.getvalue(), "")
        self.assertIn("error:", err_buf.getvalue())

    def test_inspect_subcommand_exact_output_format(self) -> None:
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
            ret = simulated_portfolio_artifact_cli.main(["inspect", str(self.valid_json_path)])
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
        self.assertEqual(output.strip().splitlines(), expected_lines)

        # Confirm no symbols, order IDs, or record IDs present in output
        for forbidden in ["2330.TW", "ORD_P1", "ORD_1", "ORD_R1", "REC_1"]:
            self.assertNotIn(forbidden, output)

    def test_export_markdown_subcommand(self) -> None:
        md_out = self.temp_dir / "out.md"
        out_buf = io.StringIO()
        err_buf = io.StringIO()

        with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
            ret = simulated_portfolio_artifact_cli.main([
                "export-markdown",
                str(self.valid_json_path),
                "--output-markdown",
                str(md_out),
            ])
        self.assertTrue(ret is None or ret == 0)
        self.assertIn(f"Simulated Portfolio Trading Markdown written: {md_out.resolve()}", out_buf.getvalue())
        self.assertTrue(md_out.is_file())

        # Duplicate export without --overwrite fails cleanly
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
            ret = simulated_portfolio_artifact_cli.main([
                "export-markdown",
                str(self.valid_json_path),
                "--output-markdown",
                str(md_out),
            ])
        self.assertEqual(ret, 1)
        self.assertEqual(out_buf.getvalue(), "")
        self.assertIn("error:", err_buf.getvalue())
        self.assertIn("Use --overwrite", err_buf.getvalue())

    def test_export_csv_subcommand(self) -> None:
        csv_dir = self.temp_dir / "csv_out"
        out_buf = io.StringIO()
        err_buf = io.StringIO()

        with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
            ret = simulated_portfolio_artifact_cli.main([
                "export-csv",
                str(self.valid_json_path),
                "--output-csv-dir",
                str(csv_dir),
            ])
        self.assertTrue(ret is None or ret == 0)

        output = out_buf.getvalue()
        self.assertIn("Simulated Portfolio Trading CSV files written:", output)

        expected_keys = [
            "summary",
            "positions",
            "pending_orders",
            "orders",
            "fills",
            "rejections",
            "trade_log",
        ]
        for key in expected_keys:
            self.assertIn(f"{key}: {csv_dir.resolve() / f'simulated_portfolio_trading_{key}.csv'}", output)
            self.assertTrue((csv_dir / f"simulated_portfolio_trading_{key}.csv").is_file())

    def test_ast_and_subprocess_dependency_boundaries(self) -> None:
        # AST check on simulated_portfolio_artifact_cli.py
        cli_file = Path(simulated_portfolio_artifact_cli.__file__)
        tree = ast.parse(cli_file.read_text(encoding="utf-8"))

        forbidden_prefixes = (
            "tw_stock_tool.data",
            "tw_stock_tool.strategies",
            "tw_stock_tool.backtesting",
            "tw_stock_tool.coordinator",
            "tw_stock_tool.risk",
            "tw_stock_tool.kill_switch",
            "tw_stock_tool.gui",
            "tw_stock_tool.ml",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_prefixes:
                        self.assertFalse(alias.name.startswith(forbidden), f"AST import forbidden: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in forbidden_prefixes:
                        self.assertFalse(node.module.startswith(forbidden), f"AST import-from forbidden: {node.module}")

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
