import math
import unittest

import pandas as pd

from tw_stock_tool.backtesting.results import BacktestResult
from backtest import BacktestError, run_backtest, run_backtest_result


def _backtest_frame(closes: list[float], signals: list[str], opens: list[float] | None = None) -> pd.DataFrame:
    if opens is None:
        opens = [c - 1.0 for c in closes]
    return pd.DataFrame(
        {"Open": opens, "Close": closes, "Signal": signals},
        index=pd.date_range("2024-01-01", periods=len(closes), freq="D"),
    )


def _interval_backtest_frame() -> pd.DataFrame:
    return _backtest_frame(
        closes=[100.0, 110.0, 99.0, 108.0, 91.8, 101.0],
        signals=["BUY", "HOLD", "HOLD", "HOLD", "HOLD", "HOLD"],
        opens=[100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
    )


class BacktestTest(unittest.TestCase):
    def test_buy_sell_basic_trade_executes_next_day(self) -> None:
        frame = _backtest_frame(
            closes=[100, 110, 120, 130],
            signals=["BUY", "HOLD", "SELL", "HOLD"],
            opens=[99, 105, 119, 125],
        )
        result = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
        )

        trades = result["Trades"]
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades.iloc[0]["Entry Date"], frame.index[1])
        self.assertEqual(trades.iloc[0]["Entry Price"], 105)
        self.assertEqual(trades.iloc[0]["Exit Date"], frame.index[3])
        self.assertEqual(trades.iloc[0]["Exit Price"], 125)
        self.assertEqual(trades.iloc[0]["Exit Reason"], "SELL")
        self.assertGreater(result["Final Capital"], 10000)

    def test_stop_loss_executes_next_day_after_trigger(self) -> None:
        frame = _backtest_frame(
            closes=[100, 100, 94, 93],
            signals=["BUY", "HOLD", "HOLD", "HOLD"],
            opens=[100, 100, 95, 92],
        )
        result = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
            stop_loss_pct=5,
        )

        trade = result["Trades"].iloc[0]
        self.assertEqual(trade["Exit Reason"], "SELL_STOP_LOSS")
        self.assertEqual(trade["Exit Date"], frame.index[3])
        self.assertEqual(trade["Exit Price"], 92)

    def test_take_profit_executes_next_day_after_trigger(self) -> None:
        frame = _backtest_frame(
            closes=[100, 100, 106, 108],
            signals=["BUY", "HOLD", "HOLD", "HOLD"],
            opens=[100, 100, 105, 107],
        )
        result = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
            take_profit_pct=5,
        )

        trade = result["Trades"].iloc[0]
        self.assertEqual(trade["Exit Reason"], "SELL_TAKE_PROFIT")
        self.assertEqual(trade["Exit Date"], frame.index[3])
        self.assertEqual(trade["Exit Price"], 107)

    def test_max_hold_days_executes_next_day_after_trigger(self) -> None:
        frame = _backtest_frame(
            closes=[100, 101, 102, 103],
            signals=["BUY", "HOLD", "HOLD", "HOLD"],
            opens=[100, 101, 102, 104],
        )
        result = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
            max_hold_days=1,
        )

        trade = result["Trades"].iloc[0]
        self.assertEqual(trade["Exit Reason"], "SELL_MAX_HOLD")
        self.assertEqual(trade["Exit Date"], frame.index[3])
        self.assertEqual(trade["Exit Price"], 104)

    def test_output_fields_exist(self) -> None:
        result = run_backtest(
            _backtest_frame([100, 110, 120], ["BUY", "SELL", "HOLD"]),
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
        )

        for field in [
            "Buy and Hold Return %",
            "CAGR %",
            "Exposure %",
            "Profit Factor",
            "Best Trade %",
            "Worst Trade %",
            "Avg Hold Days",
            "Sharpe Ratio",
            "Sortino Ratio",
            "Trades",
            "Equity Curve",
        ]:
            self.assertIn(field, result)

        for column in [
            "Entry Date",
            "Exit Date",
            "Entry Price",
            "Exit Price",
            "Shares",
            "PnL",
            "PnL_pct",
            "Hold Days",
            "Exit Reason",
        ]:
            self.assertIn(column, result["Trades"].columns)



    def test_buy_signal_day_equity_stays_in_cash_until_next_day(self) -> None:
        frame = _backtest_frame(
            closes=[100, 110, 120],
            signals=["BUY", "HOLD", "HOLD"],
            opens=[100, 105, 115],
        )
        result = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
        )

        equity = result["Equity Curve"]
        self.assertEqual(equity.iloc[0], 10000)
        self.assertEqual(result["Trades"].iloc[0]["Entry Date"], frame.index[1])
        self.assertEqual(result["Trades"].iloc[0]["Entry Price"], 105)

    def test_last_day_buy_signal_does_not_execute_same_day(self) -> None:
        result = run_backtest(
            _backtest_frame([100, 200], ["HOLD", "BUY"]),
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
        )

        self.assertEqual(result["Trade Count"], 0)
        self.assertTrue(result["Trades"].empty)
        self.assertEqual(result["Final Capital"], 10000)

    def test_no_same_day_round_trip_on_buy_and_sell_signals(self) -> None:
        frame = _backtest_frame(
            closes=[100, 110, 120, 130],
            signals=["BUY", "SELL", "HOLD", "HOLD"],
            opens=[99, 105, 119, 125],
        )
        result = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
        )

        trade = result["Trades"].iloc[0]
        self.assertEqual(trade["Entry Date"], frame.index[1])
        self.assertEqual(trade["Exit Date"], frame.index[2])
        self.assertEqual(trade["Entry Price"], 105)
        self.assertEqual(trade["Exit Price"], 119)

    def test_nonfinite_parameters_raise(self) -> None:
        for field in (
            "initial_capital",
            "fee_rate",
            "tax_rate",
            "position_size",
            "stop_loss_pct",
            "take_profit_pct",
        ):
            for value in (float("nan"), float("inf"), -float("inf")):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(BacktestError):
                        run_backtest(
                            _backtest_frame([100, 110], ["HOLD", "HOLD"]),
                            **{field: value},
                        )

    def test_scoped_parameters_reject_booleans_and_wrong_types(self) -> None:
        required = ("initial_capital", "fee_rate", "tax_rate", "position_size")
        for field in required:
            for value in (True, False, "1.0", None):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(BacktestError):
                        run_backtest(
                            _backtest_frame([100, 110], ["HOLD", "HOLD"]),
                            **{field: value},
                        )

        for field in ("stop_loss_pct", "take_profit_pct"):
            for value in (True, False, "1.0"):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(BacktestError):
                        run_backtest(
                            _backtest_frame([100, 110], ["HOLD", "HOLD"]),
                            **{field: value},
                        )

    def test_valid_finite_parameters_remain_accepted(self) -> None:
        frame = _backtest_frame([100, 110], ["HOLD", "HOLD"])
        result = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0.0,
            tax_rate=0.0,
            position_size=1.0,
            stop_loss_pct=None,
            take_profit_pct=None,
        )
        self.assertEqual(result["Final Capital"], 10000)

        negative_thresholds = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0.0,
            tax_rate=0.0,
            stop_loss_pct=-5.0,
            take_profit_pct=-5.0,
        )
        self.assertEqual(negative_thresholds["Final Capital"], 10000)

    def test_nonfinite_open_and_close_raise(self) -> None:
        for column in ("Open", "Close"):
            for value in (float("nan"), float("inf"), -float("inf")):
                with self.subTest(column=column, value=value):
                    frame = _backtest_frame(
                        [100, 110, 120],
                        ["HOLD", "HOLD", "HOLD"],
                    )
                    frame[column] = frame[column].astype(float)
                    frame.loc[frame.index[1], column] = value
                    with self.assertRaisesRegex(BacktestError, column):
                        run_backtest(frame)

    def test_price_columns_reject_booleans_and_wrong_types(self) -> None:
        for column in ("Open", "Close"):
            for value in (True, "invalid", None):
                with self.subTest(column=column, value=value):
                    frame = _backtest_frame(
                        [100, 110, 120],
                        ["HOLD", "HOLD", "HOLD"],
                    )
                    frame[column] = frame[column].astype(object)
                    frame.loc[frame.index[1], column] = value
                    with self.assertRaisesRegex(BacktestError, column):
                        run_backtest(frame)

    def test_nonfinite_open_price_raises(self) -> None:
        frame = _backtest_frame(
            closes=[100, 110, 120, 130],
            signals=["BUY", "HOLD", "HOLD", "HOLD"],
            opens=[100, float("nan"), 115, 125],
        )
        with self.assertRaises(BacktestError):
            run_backtest(frame, initial_capital=10000, fee_rate=0, tax_rate=0)

    def test_nonpositive_finite_open_price_skips_execution_safely(self) -> None:
        for open_price in (0.0, -10.0):
            with self.subTest(open_price=open_price):
                frame = _backtest_frame(
                    closes=[100, 110, 120],
                    signals=["BUY", "HOLD", "HOLD"],
                    opens=[100, open_price, 115],
                )
                result = run_backtest(
                    frame,
                    initial_capital=10000,
                    fee_rate=0,
                    tax_rate=0,
                )
                self.assertEqual(result["Trade Count"], 0)
                self.assertTrue(result["Trades"].empty)
                self.assertEqual(result["Final Capital"], 10000)
                self.assertTrue(result["Equity Curve"].map(math.isfinite).all())

    def test_run_backtest_result_shares_finite_validation(self) -> None:
        frame = _backtest_frame([100, 110, 120], ["HOLD", "HOLD", "HOLD"])
        with self.assertRaises(BacktestError):
            run_backtest_result(frame, initial_capital=float("nan"))

        invalid_price = frame.copy()
        invalid_price["Close"] = invalid_price["Close"].astype(float)
        invalid_price.loc[invalid_price.index[1], "Close"] = float("inf")
        with self.assertRaises(BacktestError):
            run_backtest_result(invalid_price)

    def test_interval_scaling_and_trading_results_are_invariant(self) -> None:
        frame = _interval_backtest_frame()
        results = {
            interval: run_backtest_result(
                frame,
                initial_capital=10000,
                fee_rate=0,
                tax_rate=0,
                interval=interval,
            )
            for interval in ("1d", "1wk", "1mo")
        }
        daily = results["1d"]
        weekly = results["1wk"]
        monthly = results["1mo"]

        self.assertAlmostEqual(daily.sharpe_ratio / weekly.sharpe_ratio, math.sqrt(252 / 52))
        self.assertAlmostEqual(weekly.sharpe_ratio / monthly.sharpe_ratio, math.sqrt(52 / 12))
        self.assertAlmostEqual(daily.sortino_ratio / weekly.sortino_ratio, math.sqrt(252 / 52))
        self.assertAlmostEqual(weekly.sortino_ratio / monthly.sortino_ratio, math.sqrt(52 / 12))

        invariant_fields = (
            "initial_capital",
            "final_capital",
            "total_return_pct",
            "buy_hold_return_pct",
            "cagr_pct",
            "exposure_pct",
            "trade_count",
            "win_rate_pct",
            "max_drawdown_pct",
            "profit_factor",
            "best_trade_pct",
            "worst_trade_pct",
            "avg_hold_days",
            "avg_profit",
            "avg_loss",
            "start_date",
            "end_date",
        )
        for candidate in (weekly, monthly):
            for field in invariant_fields:
                with self.subTest(interval=candidate, field=field):
                    self.assertEqual(getattr(candidate, field), getattr(daily, field))
            pd.testing.assert_frame_equal(candidate.trades, daily.trades)
            pd.testing.assert_series_equal(candidate.equity_curve, daily.equity_curve)

        self.assertNotEqual(daily.sharpe_ratio, weekly.sharpe_ratio)
        self.assertNotEqual(weekly.sharpe_ratio, monthly.sharpe_ratio)
        self.assertNotEqual(daily.sortino_ratio, weekly.sortino_ratio)
        self.assertNotEqual(weekly.sortino_ratio, monthly.sortino_ratio)

    def test_legacy_api_propagates_interval_exactly(self) -> None:
        frame = _interval_backtest_frame()
        expected = run_backtest_result(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
            interval="1wk",
        ).to_legacy_dict()
        actual = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
            interval="1wk",
        )
        for key in expected:
            if key == "Trades":
                pd.testing.assert_frame_equal(actual[key], expected[key])
            elif key == "Equity Curve":
                pd.testing.assert_series_equal(actual[key], expected[key])
            else:
                self.assertEqual(actual[key], expected[key])

    def test_backtest_apis_reject_invalid_intervals(self) -> None:
        frame = _interval_backtest_frame()
        for api in (run_backtest_result, run_backtest):
            for interval in (None, True, "", "daily", "5m"):
                with self.subTest(api=api.__name__, interval=interval):
                    with self.assertRaisesRegex(BacktestError, "interval"):
                        api(frame, interval=interval)

    def test_default_interval_matches_explicit_daily(self) -> None:
        frame = _interval_backtest_frame()
        implicit = run_backtest_result(frame, initial_capital=10000, fee_rate=0, tax_rate=0)
        explicit = run_backtest_result(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
            interval="1d",
        )
        for field in implicit.__dataclass_fields__:
            if field == "trades":
                pd.testing.assert_frame_equal(implicit.trades, explicit.trades)
            elif field == "equity_curve":
                pd.testing.assert_series_equal(implicit.equity_curve, explicit.equity_curve)
            else:
                self.assertEqual(getattr(implicit, field), getattr(explicit, field))

        implicit_legacy = run_backtest(frame, initial_capital=10000, fee_rate=0, tax_rate=0)
        explicit_legacy = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
            interval="1d",
        )
        for key in implicit_legacy:
            if key == "Trades":
                pd.testing.assert_frame_equal(implicit_legacy[key], explicit_legacy[key])
            elif key == "Equity Curve":
                pd.testing.assert_series_equal(implicit_legacy[key], explicit_legacy[key])
            else:
                self.assertEqual(implicit_legacy[key], explicit_legacy[key])

    def test_invalid_position_size_raises(self) -> None:
        with self.assertRaises(BacktestError):
            run_backtest(
                _backtest_frame([100, 110], ["BUY", "SELL"]),
                position_size=0,
            )

    def test_run_backtest_result_returns_structured_type(self) -> None:
        frame = _backtest_frame([100, 110, 120], ["BUY", "SELL", "HOLD"])
        result = run_backtest_result(
            frame,
            initial_capital=10000,
            fee_rate=0,
            tax_rate=0,
        )
        self.assertIsInstance(result, BacktestResult)
        self.assertIsInstance(result.trades, pd.DataFrame)
        self.assertIsInstance(result.equity_curve, pd.Series)
        self.assertGreaterEqual(result.trade_count, 0)
        self.assertGreater(result.final_capital, 0)
        self.assertEqual(result.start_date, frame.index[0])
        self.assertEqual(result.end_date, frame.index[-1])

    def test_backward_compatibility_matches_exactly(self) -> None:
        frame = _backtest_frame(
            closes=[100, 110, 120, 130],
            signals=["BUY", "HOLD", "SELL", "HOLD"],
            opens=[99, 105, 119, 125],
        )
        structured_result = run_backtest_result(
            frame,
            initial_capital=10000,
            fee_rate=0.001425,
            tax_rate=0.003,
        )
        legacy_result = run_backtest(
            frame,
            initial_capital=10000,
            fee_rate=0.001425,
            tax_rate=0.003,
        )
        
        legacy_from_structured = structured_result.to_legacy_dict()
        
        self.assertEqual(set(legacy_from_structured.keys()), set(legacy_result.keys()))
        
        self.assertEqual(legacy_from_structured["Initial Capital"], legacy_result["Initial Capital"])
        self.assertEqual(legacy_from_structured["Final Capital"], legacy_result["Final Capital"])
        self.assertEqual(legacy_from_structured["Trade Count"], legacy_result["Trade Count"])
        self.assertEqual(legacy_from_structured["Total Return %"], legacy_result["Total Return %"])
        self.assertEqual(legacy_from_structured["Max Drawdown %"], legacy_result["Max Drawdown %"])
        
        self.assertEqual(len(legacy_from_structured["Trades"]), len(legacy_result["Trades"]))
        self.assertEqual(len(legacy_from_structured["Equity Curve"]), len(legacy_result["Equity Curve"]))

    def test_run_backtest_result_invalid_position_size_raises(self) -> None:
        with self.assertRaises(BacktestError):
            run_backtest_result(
                _backtest_frame([100, 110], ["BUY", "SELL"]),
                position_size=0,
            )


if __name__ == "__main__":
    unittest.main()
