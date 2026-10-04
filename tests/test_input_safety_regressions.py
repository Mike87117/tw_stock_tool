from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from tw_stock_tool.backtesting import parameter_sweep
from tw_stock_tool.backtesting.backtest import BacktestError, run_backtest, run_backtest_result
from tw_stock_tool.cli import twstock_cli
from tw_stock_tool.data import cache_runtime, data_loader
from tw_stock_tool.ml.ml_dataset import MLDatasetError, build_ml_dataset_from_signal_df


def _prices() -> pd.DataFrame:
    return pd.DataFrame({
        "Open": [100.] * 5, "High": [101.] * 5, "Low": [99.] * 5,
        "Close": [100.] * 5, "Volume": [1000.] * 5,
        "entry_signal": [True, False, False, False, False], "exit_signal": [False] * 5,
    }, index=pd.date_range("2026-01-01", periods=5))


class CachePathSafetyTest(unittest.TestCase):
    def test_public_loader_rejects_path_like_symbols_before_io(self):
        for stock in (r"..\2330", "../2330", r"D:\2330", r"\2330", r"\\server\2330",
                      "2330/../../1", "2330.TW.TW", "2330:stream", "2330\n1", "２３３０", 2330):
            with self.subTest(stock=stock), \
                 patch.object(data_loader, "_cache_path") as cache_path, \
                 patch.object(data_loader, "_read_cache") as reader, \
                 patch.object(data_loader, "_write_cache") as writer, \
                 patch.object(data_loader, "_download_yfinance_quiet") as download, \
                 patch.object(data_loader, "_download_official_stock") as official:
                with self.assertRaisesRegex(data_loader.DataLoaderError, "Invalid stock ID format"):
                    data_loader.download_tw_stock(stock)
                for boundary in (cache_path, reader, writer, download, official):
                    boundary.assert_not_called()

    def test_valid_stocks_and_etf_suffixes_keep_existing_cache_names(self):
        root = Path.cwd() / "cache"
        for stock in ("2330", " 2330.tw ", "6488.two", "0050", "00632R.TW", "00679b"):
            with self.subTest(stock=stock):
                data_loader._validate_inputs(stock, "1y", "1d")
                for symbol, _, _ in data_loader._symbol_candidates(stock):
                    path = cache_runtime._cache_path(symbol, "1y", "1d", False, cache_dir=root)
                    self.assertEqual(path.name, f"{symbol}_1y_1d_adjusted-False.csv")
                    self.assertTrue(path.resolve().is_relative_to(root.resolve()))

    def test_cache_builder_rejects_unsafe_components_even_without_loader(self):
        for name in ("symbol", "period", "interval"):
            for value in (r"..\2330", "../2330", r"D:\2330", "/2330", "2330:stream", "2330\n1"):
                with self.subTest(name=name, value=value):
                    keys = {"symbol": "2330.TW", "period": "1y", "interval": "1d"}
                    keys[name] = value
                    with self.assertRaisesRegex(ValueError, name):
                        cache_runtime._cache_path(**keys, auto_adjust=False, cache_dir=Path.cwd() / "cache")

    def test_resolved_cache_file_must_remain_inside_root(self):
        root = Path.cwd() / "cache"
        escaped = Path.cwd() / "outside.csv"
        original_resolve = Path.resolve

        def resolve(path, *args, **kwargs):
            if path.name == "2330.TW_1y_1d_adjusted-False.csv":
                return escaped
            return original_resolve(path, *args, **kwargs)

        with patch.object(Path, "resolve", resolve):
            with self.assertRaisesRegex(ValueError, "within cache_dir"):
                cache_runtime._cache_path("2330.TW", "1y", "1d", False, cache_dir=root)


class ClosePriceSafetyTest(unittest.TestCase):
    def test_data_loader_rejects_nonpositive_and_nonfinite_closes(self):
        for value in (0., -1., float("inf"), -float("inf"), True, "invalid"):
            with self.subTest(value=value):
                frame = _prices()
                frame["Close"] = frame["Close"].astype(object)
                frame.loc[frame.index[2], "Close"] = value
                original = frame.copy(deep=True)
                with self.assertRaisesRegex(data_loader.DataLoaderError, "Close"):
                    data_loader._prepare_ohlcv(frame, "2330.TW")
                pd.testing.assert_frame_equal(frame, original)

    def test_invalid_live_close_never_reaches_cache_writer(self):
        invalid = _prices()
        invalid.loc[invalid.index[2], "Close"] = -1.
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(data_loader, "CACHE_DIR", Path(temporary)), \
             patch.object(data_loader, "_download_yfinance_quiet", return_value=invalid), \
             patch.object(data_loader, "_write_cache") as writer:
            with self.assertRaisesRegex(data_loader.DataLoaderError, "Close"):
                data_loader.download_tw_stock("2330", force_refresh=True, auto_adjust=True)
            writer.assert_not_called()
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_negative_or_zero_close_is_rejected_by_both_backtest_apis(self):
        for runner in (run_backtest, run_backtest_result):
            for value in (0., -1.):
                for position in (0, 2, 4):
                    with self.subTest(runner=runner.__name__, value=value, position=position):
                        frame = _prices()
                        frame.loc[frame.index[position], "Close"] = value
                        with self.assertRaisesRegex(BacktestError, "Close.*greater than 0"):
                            runner(frame, fee_rate=0, tax_rate=0)

    def test_ml_rejects_invalid_close_before_future_return_with_either_dropna_option(self):
        for value in (0., -1., float("nan"), float("inf"), -float("inf"), True, "invalid"):
            for dropna in (True, False):
                with self.subTest(value=value, dropna=dropna):
                    frame = _prices()
                    frame["Close"] = frame["Close"].astype(object)
                    frame.loc[frame.index[-1], "Close"] = value
                    with self.assertRaisesRegex(MLDatasetError, "Close.*greater than 0"):
                        build_ml_dataset_from_signal_df(frame, horizon=1, dropna=dropna)

    def test_valid_prices_preserve_returns_and_do_not_mutate_input(self):
        frame = _prices()
        frame["Close"] = [100., 110., 120., 130., 140.]
        original = frame.copy(deep=True)
        normalized = data_loader._prepare_ohlcv(frame, "2330.TW")
        self.assertEqual(normalized["Close"].tolist(), frame["Close"].tolist())
        result = run_backtest_result(frame, fee_rate=0, tax_rate=0)
        self.assertEqual(result.total_return_pct, 40.)
        dataset = build_ml_dataset_from_signal_df(frame, horizon=1)
        self.assertTrue(dataset["Target_Up_1D"].all())
        self.assertTrue(np.isfinite(dataset["Future_Return_1D"]).all())
        pd.testing.assert_frame_equal(frame, original)


class HoldingPeriodSafetyTest(unittest.TestCase):
    def test_invalid_holding_limits_are_rejected_by_both_backtest_apis(self):
        for runner in (run_backtest, run_backtest_result):
            for value in (0, -1, float("nan"), float("inf"), -float("inf"), 1.5, 2., True, False, "2"):
                with self.subTest(runner=runner.__name__, value=value):
                    with self.assertRaisesRegex(BacktestError, "max_hold_days.*positive integer"):
                        runner(_prices(), max_hold_days=value)

    def test_valid_integer_limit_triggers_next_open_exit(self):
        for value in (1, np.int64(1)):
            result = run_backtest_result(_prices(), fee_rate=0, tax_rate=0, max_hold_days=value)
            self.assertEqual(result.trade_count, 1)
            self.assertEqual(result.trades.iloc[0]["Exit Reason"], "SELL_MAX_HOLD")
            self.assertEqual(result.trades.iloc[0]["Exit Date"], _prices().index[3])

    def test_none_limit_preserves_end_of_data_exit(self):
        result = run_backtest_result(_prices(), fee_rate=0, tax_rate=0, max_hold_days=None)
        self.assertEqual(result.trades.iloc[0]["Exit Reason"], "SELL_EOD")

    def test_unified_parameter_sweep_cli_rejects_negative_holding_limit(self):
        with patch.object(parameter_sweep, "analyze_stock", return_value=SimpleNamespace(signal_df=_prices())), \
             redirect_stdout(StringIO()) as output:
            status = twstock_cli.main([
                "parameter-sweep", "--stock", "2330", "--strategy", "ma_cross",
                "--ma-short-windows", "2", "--ma-long-windows", "3", "--max-hold-days", "-1",
            ])
        self.assertEqual(status, 1)
        self.assertIn("max_hold_days must", output.getvalue())
        self.assertNotIn("Parameter sweep finished", output.getvalue())


if __name__ == "__main__":
    unittest.main()
