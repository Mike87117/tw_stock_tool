import unittest
import sys
import tempfile
from pathlib import Path
import pandas as pd

from tw_stock_tool.backtesting.results import BacktestResult
from tw_stock_tool.paper_trading import (
    convert_backtest_result_to_simulated_paper_trading_result,
)
from tw_stock_tool.paper_trading.serialization import (
    export_simulated_paper_trading_result_json,
    load_simulated_paper_trading_result_json,
)
from tw_stock_tool.paper_trading.serialization_files import (
    export_simulated_paper_trading_result_json_file,
    load_simulated_paper_trading_result_json_file,
)


class TestBacktestConverterRoundtrip(unittest.TestCase):
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
            equity_curve=pd.Series(),
            stock="2330",
            strategy="IntegrationTestStrategy"
        )

    def test_public_converter_to_json_string_roundtrip(self):
        # 1. Convert BacktestResult to SimulatedPaperTradingResult (retrospective offline mapping)
        paper_trading_result = convert_backtest_result_to_simulated_paper_trading_result(
            self.backtest_result
        )

        # 2. Serialize to JSON string
        json_string = export_simulated_paper_trading_result_json(paper_trading_result)

        # 3. Deserialize from JSON string
        loaded_result = load_simulated_paper_trading_result_json(json_string)

        # Assert equivalent structure and values
        self.assertEqual(loaded_result.symbol, "2330")
        self.assertEqual(loaded_result.initial_cash, 100000.0)
        self.assertEqual(loaded_result.final_cash, 110000.0)
        self.assertEqual(loaded_result.realized_pnl, 10000.0)
        self.assertEqual(len(loaded_result.orders), 2)
        self.assertEqual(len(loaded_result.fills), 2)
        
        # Order details survive
        buy_order = loaded_result.orders[0]
        sell_order = loaded_result.orders[1]
        self.assertEqual(buy_order.order_id, "backtest-000000-buy")
        self.assertEqual(buy_order.side, "BUY")
        self.assertEqual(sell_order.order_id, "backtest-000000-sell")
        self.assertEqual(sell_order.side, "SELL")

        # Fill prices survive
        buy_fill = loaded_result.fills[0]
        sell_fill = loaded_result.fills[1]
        self.assertEqual(buy_fill.price, 100.0)
        self.assertEqual(sell_fill.price, 110.0)

        # Semantics safety metadata
        self.assertEqual(buy_order.metadata["semantics"], "retrospective_offline_mapping")
        self.assertEqual(sell_order.metadata["semantics"], "retrospective_offline_mapping")

    def test_user_metadata_survives_json_roundtrip_safely(self):
        caller_metadata = {
            "source": "malicious_source",
            "semantics": "live_signal",
            "note": "roundtrip-test",
        }
        
        paper_trading_result = convert_backtest_result_to_simulated_paper_trading_result(
            self.backtest_result, metadata=caller_metadata
        )
        json_string = export_simulated_paper_trading_result_json(paper_trading_result)
        loaded_result = load_simulated_paper_trading_result_json(json_string)

        first_order_metadata = loaded_result.orders[0].metadata

        # Root metadata overrides prevented
        self.assertEqual(first_order_metadata["source"], "backtest_result")
        self.assertEqual(first_order_metadata["semantics"], "retrospective_offline_mapping")

        # Caller metadata is nested correctly
        self.assertIn("user_metadata", first_order_metadata)
        self.assertEqual(first_order_metadata["user_metadata"]["semantics"], "live_signal")
        self.assertEqual(first_order_metadata["user_metadata"]["source"], "malicious_source")
        self.assertEqual(first_order_metadata["user_metadata"]["note"], "roundtrip-test")

    def test_file_json_roundtrip(self):
        paper_trading_result = convert_backtest_result_to_simulated_paper_trading_result(
            self.backtest_result
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / "roundtrip.json"
            
            # Export to file
            export_simulated_paper_trading_result_json_file(
                paper_trading_result, temp_path, overwrite=True
            )
            
            # Load from file
            loaded_result = load_simulated_paper_trading_result_json_file(temp_path)

            self.assertEqual(loaded_result.symbol, "2330")
            self.assertEqual(len(loaded_result.orders), 2)
            self.assertEqual(len(loaded_result.fills), 2)
            self.assertEqual(loaded_result.orders[0].order_id, "backtest-000000-buy")
            self.assertEqual(loaded_result.fills[0].price, 100.0)
            self.assertEqual(loaded_result.orders[0].metadata["semantics"], "retrospective_offline_mapping")

    def test_no_live_data_or_broker_modules_imported(self):
        # We ensure that this roundtrip test module does not require forbidden dependencies
        forbidden_modules = [
            "shioaji",
            "yfinance",
            "tw_stock_tool.data",
            "tw_stock_tool.data_loader",
            "tw_stock_tool.cli",
            "tw_stock_tool.broker",
        ]
        
        for forbidden in forbidden_modules:
            # We check if they were imported as a side-effect. Since this test runs 
            # after imports, if they were required, they would be in sys.modules
            self.assertNotIn(
                forbidden, 
                sys.modules, 
                f"Forbidden module {forbidden} was loaded during backtest artifact roundtrip test"
            )

if __name__ == "__main__":
    unittest.main()
