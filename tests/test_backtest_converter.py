import unittest
import math
import sys
import pandas as pd

from tw_stock_tool.backtesting.results import BacktestResult
from tw_stock_tool.paper_trading.models import PaperTradingModelError
from tw_stock_tool.paper_trading.backtest_converter import convert_backtest_result_to_simulated_paper_trading_result
from tw_stock_tool.paper_trading.serialization import serialize_simulated_paper_trading_result


class TestBacktestConverter(unittest.TestCase):
    def setUp(self):
        self.empty_df = pd.DataFrame()
        
        self.one_trade_df = pd.DataFrame([
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

        self.multi_trade_df = pd.DataFrame([
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
            },
            {
                "Entry Date": "2024-02-01",
                "Exit Date": "2024-02-10",
                "Entry Price": 110.0,
                "Exit Price": 105.0,
                "Shares": 2000,
                "PnL": -10000.0,
                "PnL_pct": -0.045,
                "Hold Days": 9,
                "Exit Reason": "Stop",
                "Type": "Long"
            }
        ])

    def test_successful_conversion_with_one_closed_trade(self):
        br = BacktestResult(
            initial_capital=100000.0,
            final_capital=110000.0,
            total_return_pct=10.0,
            buy_hold_return_pct=5.0,
            cagr_pct=10.0,
            exposure_pct=10.0,
            trade_count=1,
            win_rate_pct=100.0,
            max_drawdown_pct=0.0,
            profit_factor=0.0,
            best_trade_pct=10.0,
            worst_trade_pct=10.0,
            avg_hold_days=4.0,
            sharpe_ratio=1.0,
            sortino_ratio=1.0,
            avg_profit=10000.0,
            avg_loss=0.0,
            trades=self.one_trade_df,
            equity_curve=pd.Series(),
            stock="2330",
            strategy="Test"
        )
        res = convert_backtest_result_to_simulated_paper_trading_result(br)
        self.assertEqual(res.symbol, "2330")
        self.assertEqual(res.initial_cash, 100000.0)
        self.assertEqual(res.final_cash, 110000.0)
        self.assertEqual(res.realized_pnl, 10000.0)
        self.assertEqual(res.unrealized_pnl, 0.0)
        self.assertEqual(res.total_equity, 110000.0)
        self.assertEqual(res.order_count, 2)
        self.assertEqual(res.fill_count, 2)
        
        # Check explicit BUY/SELL mapping (13)
        self.assertEqual(res.orders[0].side, "BUY")
        self.assertEqual(res.orders[0].quantity, 1000)
        self.assertEqual(res.fills[0].price, 100.0)
        self.assertEqual(res.orders[0].signal_time, "2024-01-01")
        
        self.assertEqual(res.orders[1].side, "SELL")
        self.assertEqual(res.orders[1].quantity, 1000)
        self.assertEqual(res.fills[1].price, 110.0)
        self.assertEqual(res.orders[1].signal_time, "2024-01-05")
        
        # Generated order IDs deterministic (12)
        self.assertEqual(res.orders[0].order_id, "backtest-000000-buy")
        self.assertEqual(res.orders[1].order_id, "backtest-000000-sell")

    def test_successful_conversion_with_multiple_closed_trades(self):
        br = BacktestResult(
            initial_capital=100000.0,
            final_capital=100000.0,
            total_return_pct=0.0,
            buy_hold_return_pct=0.0,
            cagr_pct=0.0,
            exposure_pct=0.0,
            trade_count=2,
            win_rate_pct=50.0,
            max_drawdown_pct=0.0,
            profit_factor=0.0,
            best_trade_pct=0.0,
            worst_trade_pct=0.0,
            avg_hold_days=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            avg_profit=0.0,
            avg_loss=0.0,
            trades=self.multi_trade_df,
            equity_curve=pd.Series(),
            stock="2330",
            strategy="Test"
        )
        res = convert_backtest_result_to_simulated_paper_trading_result(br)
        self.assertEqual(res.order_count, 4)
        self.assertEqual(res.realized_pnl, 0.0) # 10000 - 10000
        
        self.assertEqual(res.orders[2].order_id, "backtest-000001-buy")
        self.assertEqual(res.orders[3].order_id, "backtest-000001-sell")

    def test_successful_conversion_with_no_trades(self):
        br = BacktestResult(
            initial_capital=100000.0,
            final_capital=100000.0,
            total_return_pct=0.0,
            buy_hold_return_pct=0.0,
            cagr_pct=0.0,
            exposure_pct=0.0,
            trade_count=0,
            win_rate_pct=0.0,
            max_drawdown_pct=0.0,
            profit_factor=0.0,
            best_trade_pct=0.0,
            worst_trade_pct=0.0,
            avg_hold_days=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            avg_profit=0.0,
            avg_loss=0.0,
            trades=self.empty_df,
            equity_curve=pd.Series(),
            stock="2330",
            strategy="Test"
        )
        res = convert_backtest_result_to_simulated_paper_trading_result(br)
        self.assertEqual(res.order_count, 0)
        self.assertEqual(res.realized_pnl, 0.0)

    def test_stock_none_or_blank_rejected(self):
        br = BacktestResult(
            initial_capital=100.0, final_capital=100.0,
            total_return_pct=0, buy_hold_return_pct=0, cagr_pct=0, exposure_pct=0,
            trade_count=0, win_rate_pct=0, max_drawdown_pct=0, profit_factor=0,
            best_trade_pct=0, worst_trade_pct=0, avg_hold_days=0, sharpe_ratio=0, sortino_ratio=0,
            avg_profit=0, avg_loss=0, trades=self.empty_df, equity_curve=pd.Series(),
            stock="", strategy="Test"
        )
        with self.assertRaisesRegex(PaperTradingModelError, "stock must be present"):
            convert_backtest_result_to_simulated_paper_trading_result(br)
            
        br.stock = None
        with self.assertRaisesRegex(PaperTradingModelError, "stock must be present"):
            convert_backtest_result_to_simulated_paper_trading_result(br)

    def test_invalid_capital_rejected(self):
        br = BacktestResult(
            initial_capital=float('nan'), final_capital=100.0,
            total_return_pct=0, buy_hold_return_pct=0, cagr_pct=0, exposure_pct=0,
            trade_count=0, win_rate_pct=0, max_drawdown_pct=0, profit_factor=0,
            best_trade_pct=0, worst_trade_pct=0, avg_hold_days=0, sharpe_ratio=0, sortino_ratio=0,
            avg_profit=0, avg_loss=0, trades=self.empty_df, equity_curve=pd.Series(),
            stock="2330", strategy="Test"
        )
        with self.assertRaisesRegex(PaperTradingModelError, "initial_capital must be finite"):
            convert_backtest_result_to_simulated_paper_trading_result(br)

        br.initial_capital = 100.0
        br.final_capital = -10.0
        with self.assertRaisesRegex(PaperTradingModelError, "final_capital must be finite and non-negative"):
            convert_backtest_result_to_simulated_paper_trading_result(br)

    def test_missing_trade_columns_rejected(self):
        bad_df = pd.DataFrame([{"Entry Date": "2024", "Shares": 100}]) # missing PnL, Prices
        br = BacktestResult(
            initial_capital=100.0, final_capital=100.0,
            total_return_pct=0, buy_hold_return_pct=0, cagr_pct=0, exposure_pct=0,
            trade_count=1, win_rate_pct=0, max_drawdown_pct=0, profit_factor=0,
            best_trade_pct=0, worst_trade_pct=0, avg_hold_days=0, sharpe_ratio=0, sortino_ratio=0,
            avg_profit=0, avg_loss=0, trades=bad_df, equity_curve=pd.Series(),
            stock="2330", strategy="Test"
        )
        with self.assertRaisesRegex(PaperTradingModelError, "Missing required trade column"):
            convert_backtest_result_to_simulated_paper_trading_result(br)

    def test_non_finite_trade_price_rejected(self):
        df = self.one_trade_df.copy()
        df.loc[0, "Entry Price"] = float('nan')
        br = BacktestResult(
            initial_capital=100.0, final_capital=100.0,
            total_return_pct=0, buy_hold_return_pct=0, cagr_pct=0, exposure_pct=0,
            trade_count=1, win_rate_pct=0, max_drawdown_pct=0, profit_factor=0,
            best_trade_pct=0, worst_trade_pct=0, avg_hold_days=0, sharpe_ratio=0, sortino_ratio=0,
            avg_profit=0, avg_loss=0, trades=df, equity_curve=pd.Series(),
            stock="2330", strategy="Test"
        )
        with self.assertRaisesRegex(PaperTradingModelError, "Entry Price must be finite and positive"):
            convert_backtest_result_to_simulated_paper_trading_result(br)

    def test_non_finite_pnl_rejected(self):
        df = self.one_trade_df.copy()
        df.loc[0, "PnL"] = float('inf')
        br = BacktestResult(
            initial_capital=100.0, final_capital=100.0,
            total_return_pct=0, buy_hold_return_pct=0, cagr_pct=0, exposure_pct=0,
            trade_count=1, win_rate_pct=0, max_drawdown_pct=0, profit_factor=0,
            best_trade_pct=0, worst_trade_pct=0, avg_hold_days=0, sharpe_ratio=0, sortino_ratio=0,
            avg_profit=0, avg_loss=0, trades=df, equity_curve=pd.Series(),
            stock="2330", strategy="Test"
        )
        with self.assertRaisesRegex(PaperTradingModelError, "PnL must be finite"):
            convert_backtest_result_to_simulated_paper_trading_result(br)

    def test_fractional_shares_rejected(self):
        df = self.one_trade_df.copy()
        df.loc[0, "Shares"] = 10.5
        br = BacktestResult(
            initial_capital=100.0, final_capital=100.0,
            total_return_pct=0, buy_hold_return_pct=0, cagr_pct=0, exposure_pct=0,
            trade_count=1, win_rate_pct=0, max_drawdown_pct=0, profit_factor=0,
            best_trade_pct=0, worst_trade_pct=0, avg_hold_days=0, sharpe_ratio=0, sortino_ratio=0,
            avg_profit=0, avg_loss=0, trades=df, equity_curve=pd.Series(),
            stock="2330", strategy="Test"
        )
        with self.assertRaisesRegex(PaperTradingModelError, "Shares must be a strict positive integer"):
            convert_backtest_result_to_simulated_paper_trading_result(br)

    def test_bool_shares_rejected(self):
        df = self.one_trade_df.copy()
        df.loc[0, "Shares"] = True
        br = BacktestResult(
            initial_capital=100.0, final_capital=100.0,
            total_return_pct=0, buy_hold_return_pct=0, cagr_pct=0, exposure_pct=0,
            trade_count=1, win_rate_pct=0, max_drawdown_pct=0, profit_factor=0,
            best_trade_pct=0, worst_trade_pct=0, avg_hold_days=0, sharpe_ratio=0, sortino_ratio=0,
            avg_profit=0, avg_loss=0, trades=df, equity_curve=pd.Series(),
            stock="2330", strategy="Test"
        )
        with self.assertRaisesRegex(PaperTradingModelError, "Shares must be a strict positive integer"):
            convert_backtest_result_to_simulated_paper_trading_result(br)

    def test_metadata_must_be_json_serializable(self):
        br = BacktestResult(
            initial_capital=100.0, final_capital=100.0,
            total_return_pct=0, buy_hold_return_pct=0, cagr_pct=0, exposure_pct=0,
            trade_count=0, win_rate_pct=0, max_drawdown_pct=0, profit_factor=0,
            best_trade_pct=0, worst_trade_pct=0, avg_hold_days=0, sharpe_ratio=0, sortino_ratio=0,
            avg_profit=0, avg_loss=0, trades=self.empty_df, equity_curve=pd.Series(),
            stock="2330", strategy="Test"
        )
        with self.assertRaisesRegex(PaperTradingModelError, "metadata must be JSON serializable"):
            convert_backtest_result_to_simulated_paper_trading_result(br, metadata={"obj": object()})

    def test_compatible_with_phase29_json_exporter(self):
        br = BacktestResult(
            initial_capital=100000.0,
            final_capital=110000.0,
            total_return_pct=10.0,
            buy_hold_return_pct=5.0,
            cagr_pct=10.0,
            exposure_pct=10.0,
            trade_count=1,
            win_rate_pct=100.0,
            max_drawdown_pct=0.0,
            profit_factor=0.0,
            best_trade_pct=10.0,
            worst_trade_pct=10.0,
            avg_hold_days=4.0,
            sharpe_ratio=1.0,
            sortino_ratio=1.0,
            avg_profit=10000.0,
            avg_loss=0.0,
            trades=self.one_trade_df,
            equity_curve=pd.Series(),
            stock="2330",
            strategy="Test"
        )
        res = convert_backtest_result_to_simulated_paper_trading_result(br)
        json_dict = serialize_simulated_paper_trading_result(res)
        
        self.assertEqual(json_dict["schema_version"], 1)
        self.assertEqual(json_dict["symbol"], "2330")
        self.assertEqual(len(json_dict["orders"]), 2)

    def test_no_live_data_or_broker_imports(self):
        import tw_stock_tool.paper_trading.backtest_converter as conv
        # Check that sys.modules doesn't contain forbidden modules that might have been imported
        # We know we shouldn't see shioaji or live fetchers
        forbidden = ["shioaji", "yfinance", "twstock.live", "broker"]
        for f in forbidden:
            # We just do a substring search for strictness
            has_forbidden = any(f in m for m in sys.modules)
            self.assertFalse(has_forbidden, f"Forbidden module {f} was loaded")

if __name__ == "__main__":
    unittest.main()
