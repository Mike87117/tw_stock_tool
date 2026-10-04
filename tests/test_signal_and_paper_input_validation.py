from io import StringIO
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from tw_stock_tool.backtesting.backtest import run_backtest, run_backtest_result
from tw_stock_tool.backtesting.signals import ensure_standard_signals, legacy_signal_to_standard
from tw_stock_tool.paper_trading import engine


def _bars() -> pd.DataFrame:
    return pd.DataFrame({
        "Open": [100.] * 5, "Close": [100.] * 5,
        "entry_signal": [True, False, False, False, False],
        "exit_signal": [False, False, True, False, False],
    }, index=pd.date_range("2026-01-01", periods=5))


class SignalParsingRegressionTest(unittest.TestCase):
    def test_false_strings_cannot_create_trades_in_either_backtest_api(self):
        bars = _bars()
        bars["entry_signal"] = "False"
        bars["exit_signal"] = "False"
        original = bars.copy(deep=True)
        self.assertEqual(run_backtest(bars, fee_rate=0, tax_rate=0)["Trade Count"], 0)
        self.assertEqual(run_backtest_result(bars, fee_rate=0, tax_rate=0).trade_count, 0)
        pd.testing.assert_frame_equal(bars, original)

    def test_string_signals_produce_same_trades_as_boolean_signals(self):
        bars = _bars()
        expected = run_backtest_result(bars, fee_rate=0, tax_rate=0)
        strings = bars.copy()
        strings["entry_signal"] = strings["entry_signal"].map({True: "True", False: "False"})
        strings["exit_signal"] = strings["exit_signal"].map({True: "True", False: "False"})
        actual = run_backtest_result(strings, fee_rate=0, tax_rate=0)
        pd.testing.assert_frame_equal(actual.trades, expected.trades)
        pd.testing.assert_series_equal(actual.equity_curve, expected.equity_curve)

    def test_both_conversion_paths_parse_supported_representations(self):
        values = [True, False, np.bool_(True), 0, 1, 0., 1., np.int64(1),
                  "True", "False", " true ", " FALSE ", "0", "1", None, np.nan, pd.NA]
        expected = [True, False, True, False, True, False, True, True,
                    True, False, True, False, False, True, False, False, False]
        frame = pd.DataFrame({"entry_signal": values, "exit_signal": values,
                              "Signal": ["SELL"] * len(values)},
                             index=pd.date_range("2026-01-01", periods=len(values)))
        original = frame.copy(deep=True)
        for convert in (ensure_standard_signals, legacy_signal_to_standard):
            with self.subTest(convert=convert.__name__):
                actual = convert(frame)
                self.assertEqual(actual["entry_signal"].tolist(), expected)
                self.assertEqual(actual["exit_signal"].tolist(), expected)
                self.assertEqual(actual["entry_signal"].dtype, bool)
                pd.testing.assert_index_equal(actual.index, frame.index)
                pd.testing.assert_series_equal(actual["Signal"], frame["Signal"])
                pd.testing.assert_frame_equal(frame, original)

    def test_unknown_signal_values_are_rejected_by_both_conversion_paths(self):
        for convert in (ensure_standard_signals, legacy_signal_to_standard):
            for column in ("entry_signal", "exit_signal"):
                for value in ("BUY", "SELL", "unknown", "", 2, -1, .5, float("inf"), [False], {}):
                    with self.subTest(convert=convert.__name__, column=column, value=value):
                        bars = _bars()
                        bars[column] = bars[column].astype(object)
                        bars.at[bars.index[2], column] = value
                        with self.assertRaisesRegex(ValueError, column):
                            convert(bars)

    def test_unknown_signal_value_fails_before_backtest_trading(self):
        bars = _bars()
        bars["exit_signal"] = "unknown"
        with self.assertRaisesRegex(ValueError, "exit_signal"):
            run_backtest_result(bars)

    def test_nullable_boolean_and_missing_values_remain_supported(self):
        bars = _bars().iloc[:3].copy()
        bars["entry_signal"] = pd.array([True, pd.NA, False], dtype="boolean")
        bars["exit_signal"] = pd.array([False, pd.NA, True], dtype="boolean")
        normalized = ensure_standard_signals(bars)
        self.assertEqual(normalized["entry_signal"].tolist(), [True, False, False])
        self.assertEqual(normalized["exit_signal"].tolist(), [False, False, True])

    def test_csv_string_columns_with_whitespace_do_not_trigger_false_signals(self):
        text = "Date,Open,Close,entry_signal,exit_signal\n2026-01-01,100,100, False ,false\n2026-01-02,100,100,false, False \n"
        bars = pd.read_csv(StringIO(text), index_col=0, parse_dates=True)
        result = run_backtest_result(bars, fee_rate=0, tax_rate=0)
        self.assertEqual(result.trade_count, 0)


class SingleSymbolPaperIndexRegressionTest(unittest.TestCase):
    def test_invalid_dates_fail_before_orders_or_guard_callbacks(self):
        indices = [
            (_bars().index[::-1], "monotonic increasing"),
            (_bars().index[[0, 2, 1, 3, 4]], "monotonic increasing"),
            (_bars().index[[0, 1, 1, 3, 4]], "unique"),
            (pd.DatetimeIndex([*_bars().index[:4], pd.NaT]), "NaT"),
        ]
        for runner in (engine.run_simulated_paper_trading, engine.run_simulated_paper_trading_result):
            for index, message in indices:
                with self.subTest(runner=runner.__name__, index=index):
                    bars = _bars()
                    bars.index = index
                    original = bars.copy(deep=True)
                    with patch.object(engine, "step_simulated_symbol_bar") as step, \
                         patch.object(engine, "SimulatedPortfolio") as portfolio:
                        with self.assertRaisesRegex(ValueError, message):
                            runner(bars, "2330.TW", initial_cash=1000., quantity_per_trade=1)
                        step.assert_not_called()
                        portfolio.assert_not_called()
                    pd.testing.assert_frame_equal(bars, original)

    def test_single_nat_bar_is_rejected(self):
        bars = _bars().iloc[:1].copy()
        bars.index = pd.DatetimeIndex([pd.NaT])
        with self.assertRaisesRegex(ValueError, "NaT"):
            engine.run_simulated_paper_trading(bars, "2330.TW", initial_cash=1000.)

    def test_duplicate_numeric_and_string_indices_are_rejected(self):
        for index in ([0, 1, 1, 3, 4], ["2026-01-01"] * 5):
            bars = _bars()
            bars.index = index
            with self.assertRaisesRegex(ValueError, "unique"):
                engine.run_simulated_paper_trading(bars, "2330.TW", initial_cash=1000.)

    def test_ordered_dates_fill_after_signal_and_preserve_input(self):
        bars = _bars()
        original = bars.copy(deep=True)
        portfolio = engine.run_simulated_paper_trading(bars, "2330.TW", initial_cash=1000., quantity_per_trade=1)
        self.assertEqual(len(portfolio.trade_log.fills), 2)
        for order, fill in zip(portfolio.trade_log.orders, portfolio.trade_log.fills):
            self.assertGreater(fill.filled_at, order.signal_time)
        self.assertEqual(portfolio.cash, 1000.)
        pd.testing.assert_frame_equal(bars, original)

    def test_ordered_bar_numbers_timezone_dates_and_strings_remain_supported(self):
        for index in (pd.RangeIndex(5), _bars().index.tz_localize("Asia/Taipei"), _bars().index.strftime("%Y-%m-%d")):
            with self.subTest(index=index):
                bars = _bars()
                bars.index = index
                result = engine.run_simulated_paper_trading_result(
                    bars, "2330.TW", initial_cash=1000., quantity_per_trade=1, last_price=100.,
                )
                self.assertEqual(result.fill_count, 2)
                self.assertEqual(result.total_equity, 1000.)
                self.assertEqual(result.fills[0].filled_at, index[1])


if __name__ == "__main__":
    unittest.main()
