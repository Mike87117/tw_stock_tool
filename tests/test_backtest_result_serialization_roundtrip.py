import unittest
import sys
import json
import pandas as pd
import numpy as np

from tw_stock_tool.backtesting.results import BacktestResult
from tw_stock_tool.backtesting.serialization import (
    serialize_backtest_result,
    deserialize_backtest_result,
    export_backtest_result_json,
    load_backtest_result_json,
)
from tw_stock_tool.paper_trading import convert_backtest_result_to_simulated_paper_trading_result
from tw_stock_tool.paper_trading.serialization import (
    export_simulated_paper_trading_result_json,
    load_simulated_paper_trading_result_json,
)


class TestBacktestResultSerializationRoundtrip(unittest.TestCase):
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
            strategy="IntegrationTestStrategy",
            parameters={"param1": 1, "param2": "b"},
            start_date="2024-01-01",
            end_date="2024-01-05"
        )

    def test_backtest_result_json_string_roundtrip(self):
        json_str = export_backtest_result_json(self.backtest_result)
        loaded = load_backtest_result_json(json_str)

        self.assertIsInstance(loaded, BacktestResult)
        self.assertEqual(loaded.stock, "2330")
        self.assertEqual(loaded.strategy, "IntegrationTestStrategy")
        self.assertEqual(loaded.parameters, {"param1": 1, "param2": "b"})
        self.assertEqual(loaded.start_date, "2024-01-01")
        self.assertEqual(loaded.end_date, "2024-01-05")
        
        # Scalar summary fields
        self.assertEqual(loaded.initial_capital, 100000.0)
        self.assertEqual(loaded.final_capital, 110000.0)
        self.assertEqual(loaded.trade_count, 1)

        # Trades check
        self.assertIsInstance(loaded.trades, pd.DataFrame)
        self.assertEqual(len(loaded.trades), 1)
        self.assertEqual(loaded.trades.iloc[0]["Entry Price"], 100.0)
        self.assertEqual(loaded.trades.iloc[0]["Shares"], 1000)

        # Equity curve check
        self.assertIsInstance(loaded.equity_curve, pd.Series)
        self.assertEqual(len(loaded.equity_curve), 3)
        self.assertEqual(loaded.equity_curve.name, "Equity")
        self.assertEqual(loaded.equity_curve.iloc[-1], 110000.0)

    def test_backtest_result_artifact_dict_roundtrip(self):
        data = serialize_backtest_result(self.backtest_result)
        
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["result_type"], "backtest_result")
        self.assertCountEqual(
            list(data.keys()),
            ["schema_version", "result_type", "summary", "trades", "equity_curve", "metadata"]
        )
        
        loaded = deserialize_backtest_result(data)
        self.assertIsInstance(loaded, BacktestResult)
        self.assertIsInstance(loaded.trades, pd.DataFrame)
        self.assertIsInstance(loaded.equity_curve, pd.Series)

    def test_stable_json_safety(self):
        json_str = export_backtest_result_json(self.backtest_result)
        
        # Valid JSON parseable
        data = json.loads(json_str)
        
        self.assertEqual(data["result_type"], "backtest_result")
        
        # Ensure no NaN or Infinity strings
        self.assertNotIn("NaN", json_str)
        self.assertNotIn("Infinity", json_str)

    def test_empty_artifact_roundtrip(self):
        empty_br = BacktestResult(
            initial_capital=100000.0, final_capital=100000.0, total_return_pct=0.0,
            buy_hold_return_pct=0.0, cagr_pct=0.0, exposure_pct=0.0, trade_count=0,
            win_rate_pct=0.0, max_drawdown_pct=0.0, profit_factor=0.0, best_trade_pct=0.0,
            worst_trade_pct=0.0, avg_hold_days=0.0, sharpe_ratio=0.0, sortino_ratio=0.0,
            avg_profit=0.0, avg_loss=0.0, trades=pd.DataFrame(), equity_curve=pd.Series(),
            stock="2330", strategy="Test"
        )
        
        json_str = export_backtest_result_json(empty_br)
        loaded = load_backtest_result_json(json_str)
        
        self.assertTrue(loaded.trades.empty)
        self.assertTrue(loaded.equity_curve.empty)
        self.assertEqual(loaded.trade_count, 0)

    def test_converter_chain_safety(self):
        # BacktestResult -> JSON -> BacktestResult
        json_str = export_backtest_result_json(self.backtest_result)
        loaded_br = load_backtest_result_json(json_str)
        
        # BacktestResult -> SimulatedPaperTradingResult
        simulated_result = convert_backtest_result_to_simulated_paper_trading_result(loaded_br)
        
        # SimulatedPaperTradingResult -> JSON -> SimulatedPaperTradingResult
        simulated_json_str = export_simulated_paper_trading_result_json(simulated_result)
        loaded_simulated_result = load_simulated_paper_trading_result_json(simulated_json_str)
        
        self.assertEqual(loaded_simulated_result.symbol, "2330")
        
        # Mapped 1 trade -> 1 buy order + 1 sell order (2 orders, 2 fills)
        self.assertEqual(loaded_simulated_result.order_count, 2)
        self.assertEqual(loaded_simulated_result.fill_count, 2)
        self.assertEqual(len(loaded_simulated_result.orders), 2)
        
        buy_order = loaded_simulated_result.orders[0]
        sell_order = loaded_simulated_result.orders[1]
        
        # order ids survive
        self.assertEqual(buy_order.order_id, "backtest-000000-buy")
        self.assertEqual(sell_order.order_id, "backtest-000000-sell")
        
        # BUY / SELL sides survive
        self.assertEqual(buy_order.side, "BUY")
        self.assertEqual(sell_order.side, "SELL")
        
        # safety metadata remains retrospective_offline_mapping
        self.assertEqual(buy_order.metadata["semantics"], "retrospective_offline_mapping")
        self.assertEqual(sell_order.metadata["semantics"], "retrospective_offline_mapping")
        
        # nested metadata["backtest"]["strategy"] matches
        self.assertEqual(buy_order.metadata["backtest"]["strategy"], "IntegrationTestStrategy")
        self.assertEqual(sell_order.metadata["backtest"]["strategy"], "IntegrationTestStrategy")
        
        # nested metadata["backtest"]["parameters"] matches
        self.assertEqual(buy_order.metadata["backtest"]["parameters"], {"param1": 1, "param2": "b"})
        self.assertEqual(sell_order.metadata["backtest"]["parameters"], {"param1": 1, "param2": "b"})

    def test_forbidden_dependency_sanity(self):
        import subprocess
        import sys
        import textwrap
        
        script = textwrap.dedent("""
            import sys
            from tw_stock_tool.backtesting.serialization import export_backtest_result_json, load_backtest_result_json
            from tw_stock_tool.paper_trading import convert_backtest_result_to_simulated_paper_trading_result
            from tw_stock_tool.paper_trading.serialization import export_simulated_paper_trading_result_json, load_simulated_paper_trading_result_json
            
            forbidden = [
                "shioaji",
                "yfinance",
                "tw_stock_tool.data",
                "tw_stock_tool.data_loader",
                "tw_stock_tool.cli",
                "tw_stock_tool.broker"
            ]
            
            found = [m for m in forbidden if m in sys.modules]
            if found:
                print(f"Forbidden modules found: {found}", file=sys.stderr)
                sys.exit(1)
        """)
        
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"Subprocess failed:\n{result.stderr}")

if __name__ == "__main__":
    unittest.main()
