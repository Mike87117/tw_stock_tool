import math
import sys
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

from tw_stock_tool.cli import simulated_paper_trading_cli
from tw_stock_tool.cli.simulated_paper_trading_cli import _extract_final_close

class TestSimulatedPaperTradingCLI(unittest.TestCase):
    def test_extract_final_close_valid(self):
        df = pd.DataFrame({"Close": [10.0, 15.5]})
        self.assertEqual(_extract_final_close(df), 15.5)

    def test_extract_final_close_missing_column(self):
        df = pd.DataFrame({"Open": [10.0]})
        with self.assertRaisesRegex(ValueError, "missing 'Close' column"):
            _extract_final_close(df)

    def test_extract_final_close_empty(self):
        df = pd.DataFrame({"Close": []})
        with self.assertRaisesRegex(ValueError, "empty"):
            _extract_final_close(df)

    def test_extract_final_close_nan(self):
        df = pd.DataFrame({"Close": [float("nan")]})
        with self.assertRaisesRegex(ValueError, "finite"):
            _extract_final_close(df)

    def test_extract_final_close_inf(self):
        df = pd.DataFrame({"Close": [float("inf")]})
        with self.assertRaisesRegex(ValueError, "finite"):
            _extract_final_close(df)

    def test_extract_final_close_boolean(self):
        df = pd.DataFrame({"Close": [True]})
        with self.assertRaisesRegex(ValueError, "boolean"):
            _extract_final_close(df)

    def test_extract_final_close_non_numeric(self):
        df = pd.DataFrame({"Close": ["abc"]})
        with self.assertRaisesRegex(ValueError, "numeric"):
            _extract_final_close(df)

    def test_extract_final_close_zero(self):
        df = pd.DataFrame({"Close": [0.0]})
        with self.assertRaisesRegex(ValueError, "positive"):
            _extract_final_close(df)

    def test_extract_final_close_negative(self):
        df = pd.DataFrame({"Close": [-5.0]})
        with self.assertRaisesRegex(ValueError, "positive"):
            _extract_final_close(df)

    @patch("tw_stock_tool.cli.simulated_paper_trading_cli.STRATEGIES")
    @patch("tw_stock_tool.cli.simulated_paper_trading_cli.analyze_stock")
    @patch("tw_stock_tool.cli.simulated_paper_trading_cli.run_simulated_paper_trading_result")
    @patch("tw_stock_tool.cli.simulated_paper_trading_cli.build_simulated_paper_trading_summary")
    @patch("sys.stdout")
    def test_valid_required_arguments(self, mock_stdout, mock_build_summary, mock_run, mock_analyze, mock_strats):
        mock_analyze.return_value = MagicMock(symbol="TSMC", indicator_df=pd.DataFrame({"Close": [100.0, 105.0]}))
        mock_strat_func = MagicMock()
        mock_strat_func.return_value = pd.DataFrame({"Open": [100, 105], "Close": [100.0, 105.0], "entry_signal": [False, True], "exit_signal": [False, False]})
        mock_strats.__getitem__.return_value = mock_strat_func
        mock_build_summary.return_value = {
            "symbol": "2330",
            "initial_cash": 100000,
            "final_cash": 105000,
            "final_position_quantity": 0,
            "realized_pnl": 5000,
            "unrealized_pnl": 0,
            "total_equity": 105000,
            "total_return": 5000,
            "total_return_pct": 0.05,
            "order_count": 2,
            "fill_count": 2,
        }
        
        args = ["--stock", "2330", "--strategy", "ma_cross", "--initial-cash", "100000", "--quantity-per-trade", "1000"]
        simulated_paper_trading_cli.main(args)
        
        mock_analyze.assert_called_once()
        mock_run.assert_called_once()
        self.assertEqual(mock_run.call_args[1]["guard_decision_provider"], None)

    def test_strategy_is_required(self):
        # argparse would catch this in real usage, test our direct fallback if any
        # But we can test parsing directly
        with patch.object(sys, "argv", ["prog", "--stock", "2330", "--initial-cash", "1000", "--quantity-per-trade", "1"]):
            with self.assertRaises(SystemExit) as cm:
                simulated_paper_trading_cli._parse_args()
            self.assertEqual(cm.exception.code, 2)

    def test_strategy_choices(self):
        with patch.object(sys, "argv", ["prog", "--stock", "2330", "--strategy", "invalid_strat", "--initial-cash", "1000", "--quantity-per-trade", "1"]):
            with self.assertRaises(SystemExit) as cm:
                simulated_paper_trading_cli._parse_args()
            self.assertEqual(cm.exception.code, 2)

        with patch.object(sys, "argv", ["prog", "--stock", "2330", "--strategy", "score", "--initial-cash", "1000", "--quantity-per-trade", "1"]):
            with self.assertRaises(SystemExit):
                simulated_paper_trading_cli._parse_args()

        with patch.object(sys, "argv", ["prog", "--stock", "2330", "--strategy", "score_strategy", "--initial-cash", "1000", "--quantity-per-trade", "1"]):
            with self.assertRaises(SystemExit):
                simulated_paper_trading_cli._parse_args()

    @patch("builtins.print")
    def test_blank_stock_rejected(self, mock_print):
        args = ["--stock", "   ", "--strategy", "ma_cross", "--initial-cash", "1000", "--quantity-per-trade", "10"]
        with self.assertRaises(SystemExit) as cm:
            simulated_paper_trading_cli.main(args)
        self.assertEqual(cm.exception.code, 1)
        mock_print.assert_called_with("Error: Stock symbol cannot be blank.")

    def test_initial_cash_validation(self):
        bad_values = ["-100", "nan", "inf", "-inf", "True"]
        for val in bad_values:
            with patch.object(sys, "argv", ["prog", "--stock", "2330", "--strategy", "ma_cross", "--initial-cash", val, "--quantity-per-trade", "10"]):
                with self.assertRaises(SystemExit):
                    simulated_paper_trading_cli._parse_args()

    def test_quantity_validation(self):
        bad_values = ["0", "-10", "1.5"]
        for val in bad_values:
            with patch.object(sys, "argv", ["prog", "--stock", "2330", "--strategy", "ma_cross", "--initial-cash", "1000", "--quantity-per-trade", val]):
                with self.assertRaises(SystemExit):
                    simulated_paper_trading_cli._parse_args()

    def test_rates_validation(self):
        bad_values = ["-0.1", "nan", "inf"]
        for val in bad_values:
            with patch.object(sys, "argv", ["prog", "--stock", "2330", "--strategy", "ma_cross", "--initial-cash", "1000", "--quantity-per-trade", "10", "--fee-rate", val]):
                with self.assertRaises(SystemExit):
                    simulated_paper_trading_cli._parse_args()

    @patch("tw_stock_tool.cli.simulated_paper_trading_cli.analyze_stock")
    @patch("tw_stock_tool.cli.simulated_paper_trading_cli.STRATEGIES")
    @patch("builtins.print")
    def test_strategy_receives_indicator_df(self, mock_print, mock_strats, mock_analyze):
        mock_strat_func = MagicMock()
        mock_strat_func.return_value = pd.DataFrame({"Open": [10], "Close": [10], "entry_signal": [True], "exit_signal": [False]})
        mock_strats.__getitem__.return_value = mock_strat_func
        
        mock_analyze.return_value = MagicMock(indicator_df="MAGIC_DF")
        
        args = ["--stock", "2330", "--strategy", "ma_cross", "--initial-cash", "1000", "--quantity-per-trade", "10"]
        with patch("tw_stock_tool.cli.simulated_paper_trading_cli.run_simulated_paper_trading_result"):
            with patch("tw_stock_tool.cli.simulated_paper_trading_cli.build_simulated_paper_trading_summary", return_value={"symbol": "x", "initial_cash": 0, "final_cash": 0, "final_position_quantity": 0, "realized_pnl": 0, "unrealized_pnl": 0, "total_equity": 0, "total_return": 0, "total_return_pct": 0, "order_count": 0, "fill_count": 0}):
                simulated_paper_trading_cli.main(args)
                
        mock_strat_func.assert_called_once_with("MAGIC_DF")

    @patch("tw_stock_tool.cli.simulated_paper_trading_cli.analyze_stock")
    @patch("tw_stock_tool.cli.simulated_paper_trading_cli.STRATEGIES")
    @patch("builtins.print")
    def test_missing_open_or_signals_rejected(self, mock_print, mock_strats, mock_analyze):
        mock_analyze.return_value = MagicMock(symbol="S")
        args = ["--stock", "2330", "--strategy", "ma_cross", "--initial-cash", "1000", "--quantity-per-trade", "10"]
        
        # Missing Open
        mock_strats.__getitem__.return_value = MagicMock(return_value=pd.DataFrame({"Close": [10], "entry_signal": [True], "exit_signal": [False]}))
        with self.assertRaises(SystemExit):
            simulated_paper_trading_cli.main(args)
            
        # Missing entry_signal
        mock_strats.__getitem__.return_value = MagicMock(return_value=pd.DataFrame({"Open": [10], "Close": [10], "exit_signal": [False]}))
        with self.assertRaises(SystemExit):
            simulated_paper_trading_cli.main(args)

    @patch("tw_stock_tool.cli.simulated_paper_trading_cli.STRATEGIES")
    @patch("tw_stock_tool.cli.simulated_paper_trading_cli.analyze_stock")
    @patch("tw_stock_tool.cli.simulated_paper_trading_cli.run_simulated_paper_trading_result")
    @patch("tw_stock_tool.cli.simulated_paper_trading_cli.build_simulated_paper_trading_summary")
    @patch("sys.stdout")
    def test_zero_cash_na_pct(self, mock_stdout, mock_build, mock_run, mock_analyze, mock_strats):
        mock_analyze.return_value = MagicMock(symbol="TSMC")
        mock_strat_func = MagicMock()
        mock_strat_func.return_value = pd.DataFrame({"Open": [10], "Close": [10], "entry_signal": [True], "exit_signal": [False]})
        mock_strats.__getitem__.return_value = mock_strat_func
        mock_build.return_value = {
            "symbol": "2330",
            "initial_cash": 0,
            "final_cash": 0,
            "final_position_quantity": 0,
            "realized_pnl": 0,
            "unrealized_pnl": 0,
            "total_equity": 0,
            "total_return": 0,
            "total_return_pct": None,
            "order_count": 0,
            "fill_count": 0,
        }
        args = ["--stock", "2330", "--strategy", "ma_cross", "--initial-cash", "0", "--quantity-per-trade", "1000"]
        
        with patch("builtins.print") as mock_print:
            simulated_paper_trading_cli.main(args)
            mock_print.assert_any_call("  Total Return %: N/A")

if __name__ == '__main__':
    unittest.main()
