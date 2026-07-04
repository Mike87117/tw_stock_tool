import unittest
import sys
import pandas as pd
import numpy as np

from tw_stock_tool.backtesting.results import BacktestResult
from tw_stock_tool.backtesting.serialization import (
    BacktestResultSerializationError,
    serialize_backtest_result,
    deserialize_backtest_result,
    export_backtest_result_json,
    load_backtest_result_json,
)


class TestBacktestResultSerialization(unittest.TestCase):
    def setUp(self):
        self.trades_df = pd.DataFrame([
            {
                "Entry Date": "2024-01-01",
                "Exit Date": "2024-01-05",
                "Entry Price": 100.0,
                "Exit Price": 110.0,
                "Shares": 1000,
                "PnL": 10000.0,
                "PnL_pct": 0.1,
                "Hold Days": 4,
                "Exit Reason": "Target",
                "Type": "Long"
            }
        ])
        
        self.equity_curve = pd.Series(
            [100000.0, 105000.0, 110000.0],
            index=["2024-01-01", "2024-01-03", "2024-01-05"],
            name="Equity"
        )

        self.backtest_result = BacktestResult(
            initial_capital=100000.0,
            final_capital=110000.0,
            total_return_pct=0.1,
            buy_hold_return_pct=0.05,
            cagr_pct=0.1,
            exposure_pct=0.5,
            trade_count=1,
            win_rate_pct=1.0,
            max_drawdown_pct=0.0,
            profit_factor=0.0,
            best_trade_pct=0.1,
            worst_trade_pct=0.1,
            avg_hold_days=4.0,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            avg_profit=10000.0,
            avg_loss=0.0,
            trades=self.trades_df,
            equity_curve=self.equity_curve,
            stock="2330",
            strategy="TestStrategy",
            parameters={"param1": 1, "param2": "b"},
            start_date="2024-01-01",
            end_date="2024-01-05"
        )

    def test_serialize_deserialize_roundtrip(self):
        json_str = export_backtest_result_json(self.backtest_result)
        loaded = load_backtest_result_json(json_str)

        self.assertIsInstance(loaded, BacktestResult)
        self.assertEqual(loaded.stock, "2330")
        self.assertEqual(loaded.initial_capital, 100000.0)
        self.assertEqual(loaded.final_capital, 110000.0)
        self.assertEqual(loaded.trade_count, 1)
        self.assertEqual(loaded.strategy, "TestStrategy")
        self.assertEqual(loaded.parameters, {"param1": 1, "param2": "b"})
        
        self.assertIsInstance(loaded.trades, pd.DataFrame)
        self.assertEqual(len(loaded.trades), 1)
        self.assertEqual(loaded.trades.iloc[0]["Entry Price"], 100.0)

        self.assertIsInstance(loaded.equity_curve, pd.Series)
        self.assertEqual(len(loaded.equity_curve), 3)
        self.assertEqual(loaded.equity_curve.name, "Equity")
        self.assertEqual(loaded.equity_curve.iloc[-1], 110000.0)

    def test_empty_trades_and_equity_curve_preserved(self):
        empty_br = BacktestResult(
            initial_capital=100000.0, final_capital=100000.0, total_return_pct=0.0,
            buy_hold_return_pct=0.0, cagr_pct=0.0, exposure_pct=0.0, trade_count=0,
            win_rate_pct=0.0, max_drawdown_pct=0.0, profit_factor=0.0, best_trade_pct=0.0,
            worst_trade_pct=0.0, avg_hold_days=0.0, sharpe_ratio=0.0, sortino_ratio=0.0,
            avg_profit=0.0, avg_loss=0.0, trades=pd.DataFrame(), equity_curve=pd.Series(),
            stock="2330", strategy="Test"
        )
        data = serialize_backtest_result(empty_br)
        self.assertEqual(data["trades"], [])
        self.assertEqual(data["equity_curve"], [])

        loaded = deserialize_backtest_result(data)
        self.assertTrue(loaded.trades.empty)
        self.assertTrue(loaded.equity_curve.empty)

    def test_non_dict_parameters_rejected(self):
        self.backtest_result.parameters = "not-a-dict"
        with self.assertRaisesRegex(BacktestResultSerializationError, "parameters must be a dict"):
            serialize_backtest_result(self.backtest_result)

    def test_non_json_serializable_parameters_rejected(self):
        class Unserializable:
            pass
        self.backtest_result.parameters = {"bad": Unserializable()}
        with self.assertRaisesRegex(BacktestResultSerializationError, "parameters must be JSON serializable"):
            serialize_backtest_result(self.backtest_result)

    def test_nan_numeric_values_rejected(self):
        self.backtest_result.initial_capital = float("nan")
        with self.assertRaisesRegex(BacktestResultSerializationError, "must be finite"):
            serialize_backtest_result(self.backtest_result)

    def test_inf_numeric_values_rejected(self):
        self.backtest_result.final_capital = float("inf")
        with self.assertRaisesRegex(BacktestResultSerializationError, "must be finite"):
            serialize_backtest_result(self.backtest_result)

    def test_bool_numeric_fields_rejected(self):
        self.backtest_result.trade_count = True
        with self.assertRaisesRegex(BacktestResultSerializationError, "trade_count must be an integer"):
            serialize_backtest_result(self.backtest_result)

    def test_unsupported_schema_version_rejected(self):
        data = serialize_backtest_result(self.backtest_result)
        data["schema_version"] = 2
        with self.assertRaisesRegex(BacktestResultSerializationError, "Unsupported schema_version"):
            deserialize_backtest_result(data)

    def test_unsupported_result_type_rejected(self):
        data = serialize_backtest_result(self.backtest_result)
        data["result_type"] = "invalid_type"
        with self.assertRaisesRegex(BacktestResultSerializationError, "Unsupported result_type"):
            deserialize_backtest_result(data)

    def test_missing_top_level_fields_rejected(self):
        data = serialize_backtest_result(self.backtest_result)
        del data["summary"]
        with self.assertRaisesRegex(BacktestResultSerializationError, "Missing top-level fields"):
            deserialize_backtest_result(data)

    def test_unknown_top_level_fields_rejected(self):
        data = serialize_backtest_result(self.backtest_result)
        data["unknown_field"] = "value"
        with self.assertRaisesRegex(BacktestResultSerializationError, "Unknown top-level fields"):
            deserialize_backtest_result(data)

    def test_non_list_trades_rejected(self):
        data = serialize_backtest_result(self.backtest_result)
        data["trades"] = {}
        with self.assertRaisesRegex(BacktestResultSerializationError, "trades must be a list"):
            deserialize_backtest_result(data)

    def test_non_list_equity_curve_rejected(self):
        data = serialize_backtest_result(self.backtest_result)
        data["equity_curve"] = {}
        with self.assertRaisesRegex(BacktestResultSerializationError, "equity_curve must be a list"):
            deserialize_backtest_result(data)

    def test_no_forbidden_dependencies_imported(self):
        forbidden = [
            "shioaji",
            "yfinance",
            "tw_stock_tool.data",
            "tw_stock_tool.data_loader",
            "tw_stock_tool.cli",
            "tw_stock_tool.broker"
        ]
        for mod in forbidden:
            self.assertNotIn(mod, sys.modules, f"Forbidden module {mod} was imported.")

if __name__ == "__main__":
    unittest.main()
