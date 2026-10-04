import unittest

import pandas as pd

from tw_stock_tool.backtesting.backtest import BacktestError, run_backtest, run_backtest_result


def _bars() -> pd.DataFrame:
    return pd.DataFrame({"Open": [100.] * 4, "Close": [100.] * 4,
                         "entry_signal": [True, False, False, False],
                         "exit_signal": [False, False, True, False]},
                        index=pd.date_range("2026-01-01", periods=4))


class BacktestInputValidationTest(unittest.TestCase):
    def test_invalid_capital_and_negative_costs_are_rejected_by_both_apis(self):
        for runner in (run_backtest, run_backtest_result):
            for name, values in (("initial_capital", (0., -100.)),
                                 ("fee_rate", (-.01, -1., -2.)), ("tax_rate", (-.003, -1.))):
                for value in values:
                    with self.subTest(runner=runner.__name__, name=name, value=value):
                        with self.assertRaisesRegex(BacktestError, name):
                            runner(_bars(), **{name: value})

    def test_constant_price_with_zero_costs_has_zero_return(self):
        result = run_backtest_result(_bars(), fee_rate=0., tax_rate=0.)
        self.assertEqual(result.trade_count, 1)
        self.assertEqual(result.total_return_pct, 0.)
        self.assertEqual(result.final_capital, result.initial_capital)

    def test_normal_positive_costs_reduce_capital(self):
        result = run_backtest_result(_bars(), fee_rate=.001425, tax_rate=.003)
        self.assertEqual(result.trade_count, 1)
        self.assertLess(result.total_return_pct, 0.)
        self.assertLess(result.final_capital, result.initial_capital)

    def test_reversed_and_out_of_order_dates_are_rejected_without_mutation(self):
        for runner in (run_backtest, run_backtest_result):
            for positions in ((3, 2, 1, 0), (0, 2, 1, 3)):
                with self.subTest(runner=runner.__name__, positions=positions):
                    bars = _bars()
                    bars.index = bars.index[list(positions)]
                    original = bars.copy(deep=True)
                    with self.assertRaisesRegex(BacktestError, "遞增排序"):
                        runner(bars)
                    pd.testing.assert_frame_equal(bars, original)

    def test_duplicate_dates_are_rejected_by_both_apis(self):
        for runner in (run_backtest, run_backtest_result):
            with self.subTest(runner=runner.__name__):
                bars = _bars()
                bars.index = bars.index[[0, 1, 1, 3]]
                with self.assertRaisesRegex(BacktestError, "重複"):
                    runner(bars)

    def test_nat_is_rejected_even_for_single_bar(self):
        for runner in (run_backtest, run_backtest_result):
            for length in (1, 4):
                with self.subTest(runner=runner.__name__, length=length):
                    bars = _bars().iloc[:length].copy()
                    bars.index = pd.DatetimeIndex([pd.NaT, *bars.index[1:]])
                    with self.assertRaisesRegex(BacktestError, "NaT"):
                        runner(bars)

    def test_ordered_bar_numbers_and_timezone_dates_remain_supported(self):
        baseline = run_backtest_result(_bars(), fee_rate=0., tax_rate=0.)
        for index in (pd.RangeIndex(4), _bars().index.tz_localize("Asia/Taipei")):
            with self.subTest(index=index):
                bars = _bars()
                bars.index = index
                result = run_backtest_result(bars, fee_rate=0., tax_rate=0.)
                self.assertEqual(result.trade_count, baseline.trade_count)
                self.assertEqual(result.final_capital, baseline.final_capital)
                self.assertEqual(result.trades.iloc[0]["Entry Date"], index[1])
                self.assertEqual(result.trades.iloc[0]["Exit Date"], index[3])


if __name__ == "__main__":
    unittest.main()
