import unittest

import pandas as pd

from tw_stock_tool.backtest.engine import BacktestEngine
from tw_stock_tool.backtesting.backtest import BacktestError, run_backtest, run_backtest_result
from tw_stock_tool.strategies.base import BaseStrategy


class FixedSignals(BaseStrategy):
    name = "fixed"

    def __init__(self, entry, exit):
        self.entry = entry
        self.exit = exit

    def generate_signals(self, df, params=None):
        return pd.DataFrame(
            {"entry_signal": self.entry, "exit_signal": self.exit}, index=df.index
        )


class BacktestPathCharacterizationTest(unittest.TestCase):
    def frame(self, entry=(True, False, False), exit=(False, True, False)):
        index = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
        return pd.DataFrame(
            {"Open": [10.0, 12.0, 14.0], "Close": [11.0, 13.0, 15.0], "entry_signal": entry, "exit_signal": exit},
            index=index,
        )

    def alternate(self, df, **kwargs):
        return BacktestEngine(df[["Open", "Close"]], FixedSignals(df.entry_signal, df.exit_signal), initial_cash=100.0, **kwargs).run()

    def test_next_bar_open_and_final_signal_do_not_execute(self):
        df = self.frame()
        canonical = run_backtest_result(df, initial_capital=100.0, fee_rate=0, tax_rate=0)
        alternate = self.alternate(df)
        self.assertEqual(canonical.trades.iloc[0]["Entry Date"], df.index[1])
        self.assertEqual(canonical.trades.iloc[0]["Entry Price"], 12.0)
        self.assertEqual(alternate.trade_log.iloc[0]["Entry Date"], df.index[1])
        self.assertEqual(alternate.trade_log.iloc[0]["Exit Price"], 14.0)
        last = self.frame(entry=(False, False, True), exit=(False, False, False))
        self.assertEqual(run_backtest_result(last, fee_rate=0, tax_rate=0).trade_count, 0)
        self.assertEqual(self.alternate(last).trade_count, 0)

    def test_integer_canonical_and_fractional_alternate_sizing(self):
        df = self.frame(exit=(False, False, False))
        canonical = run_backtest_result(df, initial_capital=100.0, fee_rate=0, tax_rate=0, position_size=0.5)
        alternate = self.alternate(df)
        self.assertEqual(canonical.trades.iloc[0]["Shares"], 4)
        self.assertAlmostEqual(alternate.final_equity, 125.0)
        self.assertNotEqual(canonical.final_capital, alternate.final_equity)

    def test_eod_close_and_mark_to_market_have_distinct_trade_logs(self):
        df = self.frame(exit=(False, False, False))
        canonical = run_backtest_result(df, initial_capital=100.0, fee_rate=0, tax_rate=0)
        alternate = self.alternate(df)
        self.assertEqual(canonical.trades.iloc[0]["Exit Reason"], "SELL_EOD")
        self.assertEqual(canonical.trade_count, 1)
        self.assertEqual(alternate.trade_count, 0)
        self.assertTrue(alternate.trade_log.empty)

    def test_cost_result_and_trade_schema_differences_are_intentional(self):
        df = self.frame()
        canonical = run_backtest_result(df, initial_capital=100.0, fee_rate=0.01, tax_rate=0.02)
        alternate = self.alternate(df, commission=0.01, tax=0.02, slippage=0.1)
        self.assertIn("PnL_pct", canonical.trades.columns)
        self.assertIn("Exit Reason", canonical.trades.columns)
        self.assertIn("PnL %", alternate.trade_log.columns)
        self.assertNotIn("Exit Reason", alternate.trade_log.columns)
        self.assertIn("Final Capital", run_backtest(df, initial_capital=100.0, fee_rate=0, tax_rate=0))
        self.assertIn("final_equity", alternate.to_dict())
        self.assertNotEqual(canonical.final_capital, alternate.final_equity)

    def test_signal_and_validation_contracts_differ(self):
        df = self.frame()
        legacy = df[["Open", "Close"]].assign(Signal=[1, 0, 0])
        self.assertIsInstance(run_backtest(legacy, fee_rate=0, tax_rate=0), dict)
        with self.assertRaises(BacktestError):
            run_backtest_result(df, position_size=0)
        with self.assertRaises(ValueError):
            BacktestEngine(pd.DataFrame(), FixedSignals([], []))
        with self.assertRaises(ValueError):
            BacktestEngine(df[["Open", "Close"]], FixedSignals([1, 0, 0], [0, 0, 0])).run()
        with self.assertRaises(ValueError):
            BacktestEngine(df[["Open", "Close"]], FixedSignals(df.entry_signal, df.exit_signal), commission=-0.1)


if __name__ == "__main__":
    unittest.main()

class SignalDouble(BaseStrategy):
    name = "double"

    def __init__(self, frame):
        self.frame = frame
        self.called = False

    def generate_signals(self, df, params=None):
        self.called = True
        return self.frame


class ExpandedBacktestPathCharacterizationTest(unittest.TestCase):
    def prices(self, opens=(10.0, 12.0, 14.0, 16.0), closes=(11.0, 13.0, 15.0, 17.0)):
        return pd.DataFrame({"Open": opens, "Close": closes}, index=pd.date_range("2024-01-01", periods=len(opens)))

    def signals(self, df, entry=(True, False, False, False), exit=(False, False, True, False)):
        return df.assign(entry_signal=entry, exit_signal=exit)

    def alternate(self, df, entry, exit, **kwargs):
        strategy = SignalDouble(pd.DataFrame({"entry_signal": entry, "exit_signal": exit}, index=df.index))
        return BacktestEngine(df, strategy, initial_cash=100.0, **kwargs).run(), strategy

    def test_full_next_open_lifecycle_has_dates_prices_and_count(self):
        df = self.prices(); signals = self.signals(df)
        canonical = run_backtest_result(signals, initial_capital=100, fee_rate=0, tax_rate=0)
        alternate, _ = self.alternate(df, signals.entry_signal, signals.exit_signal)
        for log in (canonical.trades, alternate.trade_log):
            self.assertEqual(list(log[["Entry Date", "Exit Date"]].iloc[0]), [df.index[1], df.index[3]])
            self.assertEqual(list(log[["Entry Price", "Exit Price"]].iloc[0]), [12.0, 16.0])
        self.assertEqual((canonical.trade_count, alternate.trade_count), (1, 1))

    def test_final_bar_signal_has_no_execution_for_each_path(self):
        df = self.prices(); signals = self.signals(df, entry=(False, False, False, True), exit=(False, False, False, False))
        self.assertEqual(run_backtest_result(signals, fee_rate=0, tax_rate=0).trade_count, 0)
        self.assertEqual(self.alternate(df, signals.entry_signal, signals.exit_signal)[0].trade_count, 0)

    def test_sizing_is_integer_vs_fractional_and_position_size_is_canonical_only(self):
        df = self.prices(opens=(9.0, 12.0, 12.0, 12.0), closes=(9.0, 12.0, 12.0, 12.0)); signals = self.signals(df, exit=(False, False, False, False))
        canonical = run_backtest_result(signals, initial_capital=100, fee_rate=0, tax_rate=0)
        alternate, _ = self.alternate(df, signals.entry_signal, signals.exit_signal)
        self.assertEqual(canonical.trades.iloc[0]["Shares"], 8); self.assertEqual(canonical.final_capital, 100.0)
        self.assertAlmostEqual(alternate.final_equity, 100.0)
        half = run_backtest_result(signals, initial_capital=100, fee_rate=0, tax_rate=0, position_size=.5)
        self.assertEqual(half.trades.iloc[0]["Shares"], 4)

    def test_cost_formulas_and_exact_trade_columns(self):
        df = self.prices(); signals = self.signals(df)
        canonical = run_backtest_result(signals, initial_capital=100, fee_rate=.01, tax_rate=.02)
        alt, _ = self.alternate(df, signals.entry_signal, signals.exit_signal, commission=.01, tax=.02, slippage=.1)
        self.assertEqual(list(canonical.trades.columns), ["Entry Date", "Exit Date", "Entry Price", "Exit Price", "Shares", "PnL", "PnL_pct", "Hold Days", "Exit Reason", "Type"])
        self.assertEqual(list(alt.trade_log.columns), ["Entry Date", "Exit Date", "Entry Price", "Exit Price", "Shares", "PnL", "PnL %"])
        self.assertEqual(canonical.trades.iloc[0]["Shares"], 8)
        self.assertAlmostEqual(canonical.final_capital, 100 - 8*12*1.01 + 8*16*(1-.01-.02))
        self.assertAlmostEqual(alt.trade_log.iloc[0]["Entry Price"], 13.2)
        self.assertAlmostEqual(alt.trade_log.iloc[0]["Exit Price"], 14.4)
        self.assertAlmostEqual(alt.final_equity, 100 / (13.2*1.01) * 14.4 * .97)

    def test_result_contracts_and_mutability_differ(self):
        df = self.prices(); signals = self.signals(df); canonical = run_backtest_result(signals, fee_rate=0, tax_rate=0); alt, _ = self.alternate(df, signals.entry_signal, signals.exit_signal)
        fields = {"initial_capital","final_capital","total_return_pct","buy_hold_return_pct","cagr_pct","exposure_pct","trade_count","win_rate_pct","max_drawdown_pct","profit_factor","best_trade_pct","worst_trade_pct","avg_hold_days","sharpe_ratio","sortino_ratio","avg_profit","avg_loss","trades","equity_curve","stock","strategy","parameters","start_date","end_date"}
        self.assertTrue(fields.issubset(set(canonical.__dataclass_fields__)))
        self.assertIn("Final Capital", canonical.to_legacy_dict()); self.assertEqual(set(alt.to_dict()), {"total_return","max_drawdown","win_rate","trade_count","final_equity","trade_log"})
        canonical.stock = "x"
        with self.assertRaises(Exception): alt.final_equity = 0

    def test_canonical_invalid_open_skips_while_alternate_marks_nan(self):
        df = self.prices(opens=(10.0, float("nan"), 14.0, 16.0)); signals = self.signals(df)
        canonical = run_backtest_result(signals, fee_rate=0, tax_rate=0); alt, _ = self.alternate(df, signals.entry_signal, signals.exit_signal)
        self.assertEqual(canonical.trade_count, 0); self.assertTrue(pd.isna(alt.final_equity))

    def test_canonical_controls_exit_next_open(self):
        df = self.prices(opens=(10, 10, 8, 7), closes=(10, 9, 7, 7)); signals = self.signals(df, exit=(False, False, False, False))
        for kwargs, reason in (({"stop_loss_pct": 10}, "SELL_STOP_LOSS"), ({"max_hold_days": 1}, "SELL_MAX_HOLD")):
            result = run_backtest_result(signals, fee_rate=0, tax_rate=0, **kwargs)
            self.assertEqual(result.trades.iloc[0]["Exit Reason"], reason)
        profit = self.prices(opens=(10,10,12,13), closes=(10,11,13,13)); result = run_backtest_result(self.signals(profit, exit=(False,False,False,False)), fee_rate=0, tax_rate=0, take_profit_pct=10)
        self.assertEqual(result.trades.iloc[0]["Exit Reason"], "SELL_TAKE_PROFIT")

    def test_validation_and_signal_doubles(self):
        df = self.prices();
        for bad in (pd.DataFrame(), df.drop(columns="Open"), df.drop(columns="Close"), df):
            with self.assertRaises(BacktestError): run_backtest_result(bad)
        for size in (0, 1.1):
            with self.assertRaises(BacktestError): run_backtest_result(self.signals(df), position_size=size)
        missing = SignalDouble(pd.DataFrame({"entry_signal": [True]*4}, index=df.index))
        nonbool = SignalDouble(pd.DataFrame({"entry_signal": [1]*4, "exit_signal": [0]*4}, index=df.index))
        wrongindex = SignalDouble(pd.DataFrame({"entry_signal": [True]*4, "exit_signal": [False]*4}, index=pd.RangeIndex(4)))
        for strategy in (missing, nonbool, wrongindex):
            with self.assertRaises(ValueError): BacktestEngine(df, strategy).run()
        self.assertTrue(missing.called)
