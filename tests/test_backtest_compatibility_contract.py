import ast
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from tw_stock_tool.backtest.engine import BacktestEngine, BacktestResult as AlternateBacktestResult
from tw_stock_tool.backtesting import backtest, serialization, serialization_files
from tw_stock_tool.backtesting.backtest import run_backtest_result
from tw_stock_tool.backtesting.results import BacktestResult
from tw_stock_tool.paper_trading.backtest_converter import convert_backtest_result_to_simulated_paper_trading_result
from tw_stock_tool.paper_trading.models import PaperTradingModelError
from tw_stock_tool.strategies.base import BaseStrategy


class Signals(BaseStrategy):
    def generate_signals(self, df, params=None):
        return pd.DataFrame({"entry_signal": [True, False, False], "exit_signal": [False, True, False]}, index=df.index)


class BacktestCompatibilityContractTest(unittest.TestCase):
    def canonical(self):
        df = pd.DataFrame({"Open": [10., 11., 12.], "Close": [10., 11., 12.], "entry_signal": [True, False, False], "exit_signal": [False, True, False]}, index=pd.date_range("2024-01-01", periods=3))
        result = run_backtest_result(df, initial_capital=100, fee_rate=0, tax_rate=0)
        result.stock, result.strategy, result.parameters = "2330", "fixed", {"x": 1}
        result.profit_factor = 1.0
        return df, result

    def alternate(self, df):
        return BacktestEngine(df[["Open", "Close"]], Signals(), initial_cash=100).run()

    def test_canonical_result_identity_is_shared_and_alternate_is_distinct(self):
        from tw_stock_tool.paper_trading import backtest_converter
        self.assertIs(backtest.BacktestResult, BacktestResult)
        self.assertIs(serialization.BacktestResult, BacktestResult)
        self.assertIs(serialization_files.BacktestResult, BacktestResult)
        self.assertIs(backtest_converter.BacktestResult, BacktestResult)
        self.assertIsNot(AlternateBacktestResult, BacktestResult)

    def test_root_wrappers_redirect_only_to_canonical_modules(self):
        root = Path(__file__).resolve().parents[1]
        for code in ("import backtest; import tw_stock_tool.backtesting.backtest as c; assert backtest is c", "import strategies; import tw_stock_tool.backtesting.strategies as c; assert strategies is c"):
            subprocess.run([sys.executable, "-c", code], cwd=root, check=True)

    def test_retained_imports_and_cli_identity(self):
        from tw_stock_tool.cli import backtest_artifact_cli, backtest_result_export_cli
        from tw_stock_tool.backtesting.serialization_files import load_backtest_result_json_file
        from tw_stock_tool.backtesting.strategies import STRATEGIES
        from tw_stock_tool.paper_trading.backtest_converter import convert_backtest_result_to_simulated_paper_trading_result as convert
        self.assertTrue(issubclass(Signals, BaseStrategy))
        self.assertIs(backtest_result_export_cli.run_backtest_result, run_backtest_result)
        self.assertIs(backtest_result_export_cli.STRATEGIES, STRATEGIES)
        self.assertIs(backtest_artifact_cli.load_backtest_result_json_file, load_backtest_result_json_file)
        self.assertIs(backtest_artifact_cli.convert_backtest_result_to_simulated_paper_trading_result, convert)

    def test_artifact_roundtrip_and_type_boundaries(self):
        df, canonical = self.canonical(); alternate = self.alternate(df)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            serialization_files.export_backtest_result_json_file(canonical, path)
            loaded = serialization_files.load_backtest_result_json_file(path)
        self.assertIsInstance(loaded, BacktestResult); self.assertNotIsInstance(loaded, AlternateBacktestResult)
        self.assertEqual((loaded.stock, loaded.strategy, loaded.parameters), ("2330", "fixed", {"x": 1}))
        with self.assertRaisesRegex(serialization.BacktestResultSerializationError, "BacktestResult"):
            serialization.serialize_backtest_result(alternate)
        with self.assertRaisesRegex(PaperTradingModelError, "BacktestResult"):
            convert_backtest_result_to_simulated_paper_trading_result(alternate)

    def test_converter_accepts_canonical_and_production_consumers_avoid_alternate_imports(self):
        _, result = self.canonical()
        converted = convert_backtest_result_to_simulated_paper_trading_result(result)
        self.assertEqual((converted.symbol, converted.initial_cash, converted.final_cash), ("2330", 100, result.final_capital))
        files = ["src/tw_stock_tool/cli/backtest_result_export_cli.py", "src/tw_stock_tool/cli/backtest_artifact_cli.py", "src/tw_stock_tool/backtesting/serialization.py", "src/tw_stock_tool/paper_trading/backtest_converter.py"]
        for name in files:
            tree = ast.parse(Path(name).read_text(encoding="utf-8"))
            imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            self.assertNotIn("tw_stock_tool.backtest.engine", imports)
            self.assertNotIn("tw_stock_tool.strategies.base", imports)


if __name__ == "__main__":
    unittest.main()
