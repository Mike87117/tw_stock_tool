import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.paper_trading.coordinator import run_chronological_multi_symbol_simulated_paper_trading
from tw_stock_tool.paper_trading.engine import run_simulated_paper_trading
from tw_stock_tool.paper_trading.models import PaperTradingModelError, SimulatedPortfolio
from tw_stock_tool.paper_trading.runtime import SimulatedPaperTradingRuntimeState
from tw_stock_tool.paper_trading.stepper import process_simulated_pending_fill, step_simulated_symbol_bar
from tw_stock_tool.utils.output.writers import write_csv_bundle, write_text_report


class TestRevisionRegressions(unittest.TestCase):
    def pending_state(self):
        state = SimulatedPaperTradingRuntimeState(portfolio=SimulatedPortfolio(cash=1000))
        step_simulated_symbol_bar(state, symbol="TEST", bar_position=0, index_label=2,
                                  open_price=10, entry_signal=True, exit_signal=False,
                                  quantity_per_trade=1)
        return state

    def test_bad_time_preserves_pending_and_audit(self):
        for label in (1, 2, "incomparable"):
            with self.subTest(label=label):
                state = self.pending_state()
                pending = state.pending_orders["TEST"]
                records = list(state.portfolio.trade_log.records)
                with self.assertRaises(PaperTradingModelError):
                    process_simulated_pending_fill(state, symbol="TEST", open_price=10, index_label=label)
                self.assertIs(state.pending_orders["TEST"], pending)
                self.assertEqual(state.portfolio.trade_log.records, records)
                self.assertEqual(state.portfolio.cash, 1000)
                process_simulated_pending_fill(state, symbol="TEST", open_price=10, index_label=3)
                self.assertEqual(len(state.portfolio.trade_log.fills), 1)

    def test_invalid_costs_preserve_pending(self):
        for name in ("fee_rate", "tax_rate", "slippage_per_share"):
            for value in (float("nan"), float("inf"), True, "0.1"):
                with self.subTest(name=name, value=value):
                    state = self.pending_state()
                    pending = state.pending_orders["TEST"]
                    with self.assertRaises(PaperTradingModelError):
                        process_simulated_pending_fill(state, symbol="TEST", open_price=10,
                                                       index_label=3, **{name: value})
                    self.assertIs(state.pending_orders["TEST"], pending)
                    self.assertEqual(state.portfolio.cash, 1000)

    def test_coordinator_rejects_reversed_continuation(self):
        state = self.pending_state()
        df = pd.DataFrame({"Open": [10], "entry_signal": [False], "exit_signal": [False]}, index=[1])
        with self.assertRaises(PaperTradingModelError):
            run_chronological_multi_symbol_simulated_paper_trading({"TEST": df}, state)
        self.assertIn("TEST", state.pending_orders)

    def test_engine_validates_costs_without_signals(self):
        df = pd.DataFrame({"Open": [10], "entry_signal": [False], "exit_signal": [False]})
        for name in ("fee_rate", "tax_rate", "slippage_per_share"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                run_simulated_paper_trading(df, "TEST", 1000, **{name: float("nan")})

    def test_concurrent_no_overwrite_has_one_winner(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.md"
            barrier = Barrier(2)
            original_exists = Path.exists

            def synchronized_exists(path):
                result = original_exists(path)
                if path == target:
                    barrier.wait(timeout=10)
                return result

            def write(content):
                try:
                    write_text_report(content, target)
                    return True
                except FileExistsError:
                    return False

            with patch.object(Path, "exists", synchronized_exists), ThreadPoolExecutor(2) as pool:
                results = list(pool.map(write, ("first", "second")))
            self.assertEqual(sorted(results), [False, True])
            self.assertIn(target.read_text(), ("first", "second"))

    def test_csv_basename_cannot_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            bundle = dict.fromkeys(("summary", "orders", "fills"), "data")
            for basename in ("../escaped", "..\\escaped", "C:escaped", "", ".."):
                with self.subTest(basename=basename), self.assertRaises(ValueError):
                    write_csv_bundle(bundle, output, basename=basename)
            self.assertFalse(output.exists())
