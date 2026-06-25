import unittest
import pandas as pd
import numpy as np
import warnings
from tw_stock_tool.backtesting.signals import (
    ensure_standard_signals,
    legacy_signal_to_standard,
    validate_standard_signals,
    has_standard_signals,
    has_legacy_signal
)

class TestSignalStandard(unittest.TestCase):
    def setUp(self):
        self.df_legacy = pd.DataFrame({
            "Close": [100, 101, 102, 103, 104, 105],
            "Signal": ["BUY", "HOLD", "SELL", "WATCH", None, np.nan]
        }, index=pd.date_range("2024-01-01", periods=6))

    def test_legacy_signal_conversion(self):
        df_out = legacy_signal_to_standard(self.df_legacy)
        self.assertTrue(df_out["entry_signal"].iloc[0])
        self.assertFalse(df_out["exit_signal"].iloc[0])

        self.assertFalse(df_out["entry_signal"].iloc[1])
        self.assertFalse(df_out["exit_signal"].iloc[1])

        self.assertFalse(df_out["entry_signal"].iloc[2])
        self.assertTrue(df_out["exit_signal"].iloc[2])

        self.assertFalse(df_out["entry_signal"].iloc[3])
        self.assertFalse(df_out["exit_signal"].iloc[3])

        self.assertFalse(df_out["entry_signal"].iloc[4])
        self.assertFalse(df_out["exit_signal"].iloc[4])

        self.assertFalse(df_out["entry_signal"].iloc[5])
        self.assertFalse(df_out["exit_signal"].iloc[5])

    def test_does_not_modify_original_dataframe(self):
        original_cols = list(self.df_legacy.columns)
        _ = ensure_standard_signals(self.df_legacy)
        self.assertEqual(list(self.df_legacy.columns), original_cols)
        self.assertNotIn("entry_signal", self.df_legacy.columns)

    def test_index_and_length_maintained(self):
        df_out = ensure_standard_signals(self.df_legacy)
        self.assertEqual(len(df_out), len(self.df_legacy))
        self.assertTrue(df_out.index.equals(self.df_legacy.index))

    def test_bool_dtype(self):
        df_out = ensure_standard_signals(self.df_legacy)
        self.assertTrue(pd.api.types.is_bool_dtype(df_out["entry_signal"]))
        self.assertTrue(pd.api.types.is_bool_dtype(df_out["exit_signal"]))
        validate_standard_signals(df_out)

    def test_existing_standard_signals(self):
        df = pd.DataFrame({
            "Close": [100, 101],
            "entry_signal": [True, False],
            "exit_signal": [None, True]
        }, index=[1, 2])
        
        df_out = ensure_standard_signals(df)
        self.assertTrue(df_out["entry_signal"].iloc[0])
        self.assertFalse(df_out["entry_signal"].iloc[1])
        self.assertFalse(df_out["exit_signal"].iloc[0])
        self.assertTrue(df_out["exit_signal"].iloc[1])
        
        validate_standard_signals(df_out)

    def test_missing_signals_raises(self):
        df = pd.DataFrame({"Close": [100, 101]})
        with self.assertRaises(ValueError):
            legacy_signal_to_standard(df)
        with self.assertRaises(ValueError):
            ensure_standard_signals(df)

    def test_legacy_conversion_does_not_override_existing_standard_signals(self):
        df = pd.DataFrame({
            "Close": [100, 101],
            "Signal": ["BUY", "SELL"],
            "entry_signal": [False, True],
            "exit_signal": [True, False],
        })

        df_out = legacy_signal_to_standard(df)
        self.assertFalse(df_out.loc[0, "entry_signal"])
        self.assertTrue(df_out.loc[0, "exit_signal"])
        self.assertTrue(df_out.loc[1, "entry_signal"])
        self.assertFalse(df_out.loc[1, "exit_signal"])
        self.assertTrue(df_out["Signal"].equals(df["Signal"]))

    def test_run_backtest_supports_standard_signals_without_legacy_signal(self):
        from backtest import run_backtest

        df = pd.DataFrame(
            {
                "Close": [100, 110, 120, 130],
                "entry_signal": [True, False, False, False],
                "exit_signal": [False, False, True, False],
            },
            index=pd.date_range("2024-01-01", periods=4, freq="D"),
        )

        result = run_backtest(df, initial_capital=10000, fee_rate=0, tax_rate=0)
        trades = result["Trades"]
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades.iloc[0]["Entry Date"], df.index[1])
        self.assertEqual(trades.iloc[0]["Exit Date"], df.index[3])
        self.assertEqual(trades.iloc[0]["Entry Price"], 110)
        self.assertEqual(trades.iloc[0]["Exit Price"], 130)

if __name__ == "__main__":
    unittest.main()
