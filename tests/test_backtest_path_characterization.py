import unittest

import pandas as pd

from tw_stock_tool.backtesting.backtest import BacktestError, run_backtest, run_backtest_result


class BacktestPathCharacterizationTest(unittest.TestCase):
    def frame(self, entry=(True, False, False), exit=(False, True, False)):
        index = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
        return pd.DataFrame(
            {"Open": [10.0, 12.0, 14.0], "Close": [11.0, 13.0, 15.0], "entry_signal": entry, "exit_signal": exit},
            index=index,
        )

    def test_next_bar_open_and_final_signal_do_not_execute(self):
        df = self.frame()
        result = run_backtest_result(df, initial_capital=100.0, fee_rate=0, tax_rate=0)
        self.assertEqual(result.trades.iloc[0]["Entry Date"], df.index[1])
        self.assertEqual(result.trades.iloc[0]["Entry Price"], 12.0)
        last = self.frame(entry=(False, False, True), exit=(False, False, False))
        self.assertEqual(run_backtest_result(last, fee_rate=0, tax_rate=0).trade_count, 0)

    def test_integer_sizing_and_position_size(self):
        df = self.frame(exit=(False, False, False))
        result = run_backtest_result(df, initial_capital=100.0, fee_rate=0, tax_rate=0, position_size=0.5)
        self.assertEqual(result.trades.iloc[0]["Shares"], 4)

    def test_eod_close_has_expected_trade_log(self):
        df = self.frame(exit=(False, False, False))
        result = run_backtest_result(df, initial_capital=100.0, fee_rate=0, tax_rate=0)
        self.assertEqual(result.trades.iloc[0]["Exit Reason"], "SELL_EOD")
        self.assertEqual(result.trade_count, 1)

    def test_cost_result_and_trade_schema(self):
        df = self.frame()
        result = run_backtest_result(df, initial_capital=100.0, fee_rate=0.01, tax_rate=0.02)
        self.assertIn("PnL_pct", result.trades.columns)
        self.assertIn("Exit Reason", result.trades.columns)
        self.assertIn("Final Capital", run_backtest(df, initial_capital=100.0, fee_rate=0, tax_rate=0))

    def test_signal_and_validation_contracts(self):
        df = self.frame()
        legacy = df[["Open", "Close"]].assign(Signal=[1, 0, 0])
        self.assertIsInstance(run_backtest(legacy, fee_rate=0, tax_rate=0), dict)
        with self.assertRaises(BacktestError):
            run_backtest_result(df, position_size=0)


class BacktestCanonicalPathCharacterizationTest(unittest.TestCase):
    def prices(self, opens=(10.0, 12.0, 14.0, 16.0), closes=(11.0, 13.0, 15.0, 17.0)):
        return pd.DataFrame({"Open": opens, "Close": closes}, index=pd.date_range("2024-01-01", periods=len(opens)))

    def signals(self, df, entry=(True, False, False, False), exit=(False, False, True, False)):
        return df.assign(entry_signal=entry, exit_signal=exit)

    def test_full_next_open_lifecycle_has_dates_prices_and_count(self):
        df = self.prices()
        result = run_backtest_result(self.signals(df), initial_capital=100, fee_rate=0, tax_rate=0)
        self.assertEqual(list(result.trades[["Entry Date", "Exit Date"]].iloc[0]), [df.index[1], df.index[3]])
        self.assertEqual(list(result.trades[["Entry Price", "Exit Price"]].iloc[0]), [12.0, 16.0])
        self.assertEqual(result.trade_count, 1)

    def test_final_bar_signal_has_no_execution(self):
        df = self.prices()
        signals = self.signals(df, entry=(False, False, False, True), exit=(False, False, False, False))
        self.assertEqual(run_backtest_result(signals, fee_rate=0, tax_rate=0).trade_count, 0)

    def test_sizing_and_position_size(self):
        df = self.prices(opens=(9.0, 12.0, 12.0, 12.0), closes=(9.0, 12.0, 12.0, 12.0))
        signals = self.signals(df, exit=(False, False, False, False))
        result = run_backtest_result(signals, initial_capital=100, fee_rate=0, tax_rate=0)
        self.assertEqual(result.trades.iloc[0]["Shares"], 8)
        self.assertEqual(result.final_capital, 100.0)
        half = run_backtest_result(signals, initial_capital=100, fee_rate=0, tax_rate=0, position_size=0.5)
        self.assertEqual(half.trades.iloc[0]["Shares"], 4)

    def test_cost_formulas_and_exact_trade_columns(self):
        df = self.prices()
        result = run_backtest_result(self.signals(df), initial_capital=100, fee_rate=.01, tax_rate=.02)
        self.assertEqual(list(result.trades.columns), ["Entry Date", "Exit Date", "Entry Price", "Exit Price", "Shares", "PnL", "PnL_pct", "Hold Days", "Exit Reason", "Type"])
        self.assertEqual(result.trades.iloc[0]["Shares"], 8)
        self.assertAlmostEqual(result.final_capital, 100 - 8 * 12 * 1.01 + 8 * 16 * (1 - .01 - .02))

    def test_result_contract_and_legacy_mapping(self):
        df = self.prices()
        result = run_backtest_result(self.signals(df), fee_rate=0, tax_rate=0)
        fields = {"initial_capital", "final_capital", "total_return_pct", "buy_hold_return_pct", "cagr_pct", "exposure_pct", "trade_count", "win_rate_pct", "max_drawdown_pct", "profit_factor", "best_trade_pct", "worst_trade_pct", "avg_hold_days", "sharpe_ratio", "sortino_ratio", "avg_profit", "avg_loss", "trades", "equity_curve", "stock", "strategy", "parameters", "start_date", "end_date"}
        self.assertTrue(fields.issubset(set(result.__dataclass_fields__)))
        self.assertIn("Final Capital", result.to_legacy_dict())

    def test_invalid_open_raises(self):
        df = self.prices(opens=(10.0, float("nan"), 14.0, 16.0))
        with self.assertRaises(BacktestError):
            run_backtest_result(self.signals(df), fee_rate=0, tax_rate=0)

    def test_exit_controls_use_next_open(self):
        df = self.prices(opens=(10, 10, 8, 7), closes=(10, 9, 7, 7))
        signals = self.signals(df, exit=(False, False, False, False))
        for kwargs, reason in (({"stop_loss_pct": 10}, "SELL_STOP_LOSS"), ({"max_hold_days": 1}, "SELL_MAX_HOLD")):
            result = run_backtest_result(signals, fee_rate=0, tax_rate=0, **kwargs)
            self.assertEqual(result.trades.iloc[0]["Exit Reason"], reason)
        profit = self.prices(opens=(10, 10, 12, 13), closes=(10, 11, 13, 13))
        result = run_backtest_result(self.signals(profit, exit=(False, False, False, False)), fee_rate=0, tax_rate=0, take_profit_pct=10)
        self.assertEqual(result.trades.iloc[0]["Exit Reason"], "SELL_TAKE_PROFIT")

    def test_required_columns_and_position_size_validation(self):
        df = self.prices()
        for bad in (pd.DataFrame(), df.drop(columns="Open"), df.drop(columns="Close"), df):
            with self.assertRaises(BacktestError):
                run_backtest_result(bad)
        for size in (0, 1.1):
            with self.assertRaises(BacktestError):
                run_backtest_result(self.signals(df), position_size=size)


if __name__ == "__main__":
    unittest.main()
