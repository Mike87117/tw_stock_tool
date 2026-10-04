import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.paper_trading.coordinator import (
    run_chronological_multi_symbol_simulated_paper_trading as run_coordinator,
)
from tw_stock_tool.paper_trading.models import PaperTradingModelError, SimulatedPortfolio
from tw_stock_tool.paper_trading.portfolio_export_files import (
    export_simulated_portfolio_trading_csv_files,
)
from tw_stock_tool.paper_trading.portfolio_exporters import (
    export_simulated_portfolio_trading_csv_bundle,
)
from tw_stock_tool.paper_trading.portfolio_results import build_simulated_portfolio_trading_result
from tw_stock_tool.paper_trading.runtime import SimulatedPaperTradingRuntimeState
from tw_stock_tool.paper_trading.stepper import step_simulated_symbol_bar
from tw_stock_tool.utils.output import writers


class TestTradingContinuation(unittest.TestCase):
    def state(self):
        return SimulatedPaperTradingRuntimeState(SimulatedPortfolio(1000.0))

    def frame(self, index, entries, exits):
        return pd.DataFrame(
            {"Open": [10.0] * len(index), "entry_signal": entries, "exit_signal": exits},
            index=index,
        )

    def test_reversed_or_repeated_continuation_without_pending_is_rejected_before_mutation(self):
        for index in ([1, 2], [4, 5], ["incomparable"]):
            with self.subTest(index=index):
                state = self.state()
                run_coordinator({"TEST": self.frame([3, 4], [True, False], [False, False])},
                                state, quantity_per_trade=1)
                self.assertFalse(state.pending_orders)
                original_orders = list(state.portfolio.trade_log.orders)
                original_fills = list(state.portfolio.trade_log.fills)
                original_records = list(state.portfolio.trade_log.records)
                original_times = dict(state.last_processed_times)
                original_positions = dict(state.next_bar_positions)
                invalid = self.frame(index, [False] * len(index), [True] * len(index))
                with self.assertRaises(PaperTradingModelError):
                    run_coordinator({"TEST": invalid}, state, quantity_per_trade=1)
                self.assertEqual(state.portfolio.cash, 990.0)
                self.assertEqual(state.portfolio.position_for("TEST").quantity, 1)
                self.assertEqual(state.portfolio.trade_log.orders, original_orders)
                self.assertEqual(state.portfolio.trade_log.fills, original_fills)
                self.assertEqual(state.portfolio.trade_log.records, original_records)
                self.assertEqual(state.last_processed_times, original_times)
                self.assertEqual(state.next_bar_positions, original_positions)

    def test_new_symbol_cannot_go_back_before_existing_history(self):
        state = self.state()
        run_coordinator({"TEST": self.frame([3, 4], [False, False], [False, False])}, state)
        with self.assertRaises(PaperTradingModelError):
            run_coordinator({"OTHER": self.frame([2], [True], [False])}, state)
        self.assertFalse(state.pending_orders)
        self.assertFalse(state.portfolio.trade_log.records)

    def test_stepper_tracks_time_after_pending_is_filled(self):
        state = self.state()
        for time, entry in ((3, True), (4, False)):
            step_simulated_symbol_bar(state, symbol="TEST", bar_position=0, index_label=time,
                                      open_price=10, entry_signal=entry, exit_signal=False,
                                      quantity_per_trade=1)
        for time in (2, 4):
            with self.subTest(time=time), self.assertRaises(PaperTradingModelError):
                step_simulated_symbol_bar(state, symbol="TEST", bar_position=0, index_label=time,
                                          open_price=10, entry_signal=False, exit_signal=True,
                                          quantity_per_trade=1)
        self.assertEqual(len(state.portfolio.trade_log.fills), 1)
        self.assertFalse(state.pending_orders)

    def test_chunked_history_matches_full_history_including_order_ids(self):
        indexes = (
            list(range(8)),
            pd.date_range("2026-01-01", periods=8, tz="Asia/Taipei"),
        )
        for index in indexes:
            with self.subTest(index_type=type(index).__name__):
                data = self.frame(index, [False, True, False, False, False, True, False, False],
                                  [False, False, False, True, False, False, False, False])
                full, chunked = self.state(), self.state()
                run_coordinator({"TEST": data}, full, quantity_per_trade=1)
                for start, end in ((0, 1), (1, 2), (2, 4), (4, 6), (6, 8)):
                    run_coordinator({"TEST": data.iloc[start:end]}, chunked, quantity_per_trade=1)
                self.assertEqual(chunked, full)
                ids = [order.order_id for order in chunked.portfolio.trade_log.orders]
                self.assertEqual(ids, ["TEST-BUY-1", "TEST-SELL-3", "TEST-BUY-5"])
                self.assertEqual(len(set(ids)), len(ids))

    def test_stepper_repeated_local_positions_still_produce_unique_orders(self):
        state = self.state()
        for time in range(6):
            step_simulated_symbol_bar(state, symbol="TEST", bar_position=0, index_label=time,
                                      open_price=10, entry_signal=time in (0, 4),
                                      exit_signal=time == 2, quantity_per_trade=1)
        ids = [order.order_id for order in state.portfolio.trade_log.orders]
        self.assertEqual(ids, ["TEST-BUY-0", "TEST-SELL-2", "TEST-BUY-4"])


class TestRecoverableCsvExports(unittest.TestCase):
    def bundle(self, text="new"):
        return dict.fromkeys(("summary", "orders", "fills"), text)

    def contents(self, directory):
        return {path.name: path.read_bytes() for path in directory.iterdir()}

    def test_staging_failure_leaves_no_partial_bundle_and_retry_succeeds(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            original = writers.write_text_report

            def fail_second(content, path, **kwargs):
                if Path(path).name.endswith("_orders.csv"):
                    raise OSError("disk write failed")
                return original(content, path, **kwargs)

            with patch.object(writers, "write_text_report", side_effect=fail_second):
                with self.assertRaisesRegex(OSError, "disk write failed"):
                    writers.write_csv_bundle(self.bundle(), directory)
            self.assertEqual(self.contents(directory), {})
            paths = writers.write_csv_bundle(self.bundle(), directory)
            self.assertEqual(len(paths), 3)

    def test_staging_failure_preserves_existing_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            writers.write_csv_bundle(self.bundle("original"), directory)
            expected = self.contents(directory)
            with patch.object(writers, "write_text_report", side_effect=OSError("disk write failed")):
                with self.assertRaises(OSError):
                    writers.write_csv_bundle(self.bundle(), directory, overwrite=True)
            self.assertEqual(self.contents(directory), expected)

    def test_publication_collision_removes_own_files_and_preserves_competing_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            original = os.link

            def competing_link(source, destination):
                if Path(destination).name.endswith("_orders.csv"):
                    Path(destination).write_text("other exporter", encoding="utf-8")
                return original(source, destination)

            with patch.object(writers.os, "link", side_effect=competing_link):
                with self.assertRaises(FileExistsError):
                    writers.write_csv_bundle(self.bundle(), directory)
            self.assertEqual(self.contents(directory),
                             {"simulated_paper_trading_orders.csv": b"other exporter"})

    def test_failed_overwrite_restores_original_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            writers.write_csv_bundle(self.bundle("original"), directory)
            expected = self.contents(directory)
            original = os.replace

            def fail_second(source, destination):
                if Path(destination).name.endswith("_orders.csv"):
                    raise OSError("publication failed")
                return original(source, destination)

            with patch.object(writers.os, "replace", side_effect=fail_second):
                with self.assertRaisesRegex(OSError, "publication failed"):
                    writers.write_csv_bundle(self.bundle(), directory, overwrite=True)
            self.assertEqual(self.contents(directory), expected)

    def test_public_portfolio_csv_export_preserves_embedded_newlines(self):
        state = SimulatedPaperTradingRuntimeState(SimulatedPortfolio(1000.0))
        data = pd.DataFrame({"Open": [10.0, 10.0], "entry_signal": [True, False],
                             "exit_signal": [False, False]}, index=[0, 1])
        strategy = 'first\r\nsecond\nthird\rfourth,"quoted"'
        run_coordinator({"TEST": data}, state, quantity_per_trade=1, strategy=strategy)
        result = build_simulated_portfolio_trading_result(
            state, initial_cash=1000, last_prices={"TEST": 10})
        with tempfile.TemporaryDirectory() as temporary:
            paths = export_simulated_portfolio_trading_csv_files(result, temporary)
            expected = export_simulated_portfolio_trading_csv_bundle(result)
            for key, path in paths.items():
                self.assertEqual(path.read_bytes(), expected[key].encode("utf-8"))
            with paths["orders"].open(encoding="utf-8", newline="") as stream:
                self.assertEqual(list(csv.DictReader(stream))[0]["strategy"], strategy)
