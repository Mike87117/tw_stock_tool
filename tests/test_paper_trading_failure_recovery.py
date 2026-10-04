import os
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.paper_trading.coordinator import (
    run_chronological_multi_symbol_simulated_paper_trading,
)
from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError, SimulatedFill, SimulatedOrder, SimulatedPortfolio,
    SimulatedPosition, SimulatedTradeStatus,
)
from tw_stock_tool.paper_trading.portfolio_results import build_simulated_portfolio_trading_result
from tw_stock_tool.paper_trading.runtime import SimulatedPaperTradingRuntimeState
from tw_stock_tool.utils.output import writers
from tw_stock_tool.cli import simulated_paper_trading_export_cli, simulated_portfolio_artifact_cli


class TestStrictTradingQuantities(unittest.TestCase):
    invalid_quantities = (True, False, 0, -1, 1.0, 0.5, float("nan"), float("inf"), "1", None)

    def test_orders_and_fills_reject_invalid_quantities(self):
        for quantity in self.invalid_quantities:
            for model in (SimulatedOrder, SimulatedFill):
                with self.subTest(quantity=quantity, model=model.__name__):
                    values = dict(order_id="test", symbol="TEST", side="BUY", quantity=quantity)
                    if model is SimulatedOrder:
                        values["signal_time"] = 0
                    else:
                        values.update(price=10, filled_at=0)
                    with self.assertRaises(PaperTradingModelError):
                        model(**values)

    def test_mutated_quantity_cannot_change_portfolio_or_position(self):
        for quantity in self.invalid_quantities:
            for side in ("BUY", "SELL"):
                with self.subTest(quantity=quantity, side=side):
                    portfolio = SimulatedPortfolio(1000)
                    portfolio.apply_fill(SimulatedFill("seed", "TEST", "BUY", 2, 10, 0))
                    before = (portfolio.cash, portfolio.position_for("TEST").quantity,
                              portfolio.position_for("TEST").average_cost,
                              portfolio.position_for("TEST").realized_pnl)
                    fills = list(portfolio.trade_log.fills)
                    fill = SimulatedFill("bad", "TEST", side, 1, 10, 1)
                    fill.quantity = quantity
                    with self.assertRaises(PaperTradingModelError):
                        portfolio.apply_fill(fill)
                    with self.assertRaises(PaperTradingModelError):
                        portfolio.position_for("TEST").apply_fill(fill)
                    self.assertEqual((portfolio.cash, portfolio.position_for("TEST").quantity,
                                      portfolio.position_for("TEST").average_cost,
                                      portfolio.position_for("TEST").realized_pnl), before)
                    self.assertEqual(portfolio.trade_log.fills, fills)


class TestSellCashValidation(unittest.TestCase):
    def test_sell_overdraft_is_rejected_before_state_changes(self):
        portfolio = SimulatedPortfolio(11)
        portfolio.apply_fill(SimulatedFill("buy", "TEST", "BUY", 1, 10, 0, slippage=1))
        for cost in ("fee", "tax", "slippage"):
            with self.subTest(cost=cost):
                fill = SimulatedFill("sell", "TEST", "SELL", 1, 1, 1, **{cost: 2})
                with self.assertRaisesRegex(PaperTradingModelError, "Insufficient simulated cash for SELL"):
                    portfolio.apply_fill(fill)
                self.assertEqual(portfolio.cash, 0)
                self.assertEqual(portfolio.positions["TEST"], SimulatedPosition("TEST", 1, 11, 0))
                self.assertEqual(len(portfolio.trade_log.fills), 1)

    def test_sell_can_use_available_cash_for_costs_and_finish_at_zero(self):
        portfolio = SimulatedPortfolio(11)
        portfolio.apply_fill(SimulatedFill("buy", "TEST", "BUY", 1, 10, 0))
        portfolio.apply_fill(SimulatedFill("sell", "TEST", "SELL", 1, 1, 1, slippage=2))
        self.assertEqual(portfolio.cash, 0)
        self.assertEqual(portfolio.position_for("TEST").quantity, 0)
        self.assertEqual(len(portfolio.trade_log.fills), 2)

    def test_failed_sell_is_audited_and_result_can_be_built(self):
        state = SimulatedPaperTradingRuntimeState(SimulatedPortfolio(100))
        data = pd.DataFrame({"Open": [10, 10, 0.1, 0.1],
                             "entry_signal": [True, False, False, False],
                             "exit_signal": [False, False, True, False]})
        run_chronological_multi_symbol_simulated_paper_trading(
            {"TEST": data}, state, quantity_per_trade=9, slippage_per_share=1)
        self.assertEqual(state.portfolio.cash, 1)
        self.assertEqual(state.portfolio.position_for("TEST").quantity, 9)
        self.assertEqual(len(state.portfolio.trade_log.fills), 1)
        self.assertFalse(state.pending_orders)
        self.assertEqual(state.portfolio.trade_log.records[-1].status,
                         SimulatedTradeStatus.FAILED_PORTFOLIO_VALIDATION)
        result = build_simulated_portfolio_trading_result(
            state, initial_cash=100, last_prices={"TEST": 0.1})
        self.assertAlmostEqual(result.total_equity, 1.9)


class TestCsvRollbackFailure(unittest.TestCase):
    def test_export_clis_report_failure_and_recovery_path(self):
        cases = (
            (simulated_paper_trading_export_cli, "load_simulated_paper_trading_result_json_file",
             "export_simulated_paper_trading_csv_files", ["input.json", "--output-csv-dir", "output"]),
            (simulated_portfolio_artifact_cli, "load_simulated_portfolio_trading_result_json_file",
             "export_simulated_portfolio_trading_csv_files",
             ["export-csv", "input.json", "--output-csv-dir", "output"]),
        )
        with tempfile.TemporaryDirectory() as temporary:
            recovery = Path(temporary) / "recovery"
            error = writers.CsvExportRecoveryError(recovery, OSError("write failed"),
                                                   [(Path("summary.csv"), PermissionError("locked"))])
            for module, loader, exporter, argv in cases:
                with self.subTest(module=module.__name__):
                    stderr, stdout = io.StringIO(), io.StringIO()
                    with patch.object(module, loader, return_value=object()), \
                            patch.object(module, exporter, side_effect=error), \
                            redirect_stderr(stderr), redirect_stdout(stdout):
                        self.assertEqual(module.main(argv), 1)
                    self.assertIn(str(recovery), stderr.getvalue())
                    self.assertEqual(stdout.getvalue(), "")

    def test_failed_restore_preserves_backup_and_reports_recovery_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            old = dict.fromkeys(("summary", "orders", "fills"), "original")
            paths = writers.write_csv_bundle(old, directory, basename="test")
            original_replace = os.replace

            def fail_publication_and_restore(source, destination):
                if Path(destination).name == "test_orders.csv" or Path(source).suffix == ".backup":
                    raise PermissionError("file locked")
                return original_replace(source, destination)

            with patch.object(writers.os, "replace", side_effect=fail_publication_and_restore):
                with self.assertRaises(writers.CsvExportRecoveryError) as caught:
                    writers.write_csv_bundle(dict.fromkeys(old, "new"), directory,
                                             basename="test", overwrite=True)
            error = caught.exception
            self.assertIsInstance(error.__cause__, PermissionError)
            self.assertEqual(len(error.rollback_errors), 1)
            self.assertEqual(error.recovery_directory.parent, directory)
            self.assertIn(str(error.recovery_directory), str(error))
            backup = error.recovery_directory / "summary.backup"
            self.assertEqual(backup.read_bytes(), b"original")
            original_replace(backup, paths["summary"])
            self.assertTrue(all(path.read_text() == "original" for path in paths.values()))

    def test_other_files_are_restored_even_when_one_restore_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            old = dict.fromkeys(("summary", "orders", "fills"), "original")
            paths = writers.write_csv_bundle(old, directory, basename="test")
            original_replace = os.replace

            def fail_one_restore(source, destination):
                if Path(destination).name == "test_fills.csv" or Path(source).name == "orders.backup":
                    raise PermissionError("file locked")
                return original_replace(source, destination)

            with patch.object(writers.os, "replace", side_effect=fail_one_restore):
                with self.assertRaises(writers.CsvExportRecoveryError) as caught:
                    writers.write_csv_bundle(dict.fromkeys(old, "new"), directory,
                                             basename="test", overwrite=True)
            self.assertEqual(paths["summary"].read_text(), "original")
            self.assertEqual(paths["fills"].read_text(), "original")
            self.assertEqual(paths["orders"].read_text(), "new")
            self.assertEqual((caught.exception.recovery_directory / "orders.backup").read_bytes(),
                             b"original")
