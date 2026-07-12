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
        self.assertEqual((loaded.initial_capital, loaded.final_capital, loaded.trade_count), (canonical.initial_capital, canonical.final_capital, canonical.trade_count))
        self.assertEqual((loaded.start_date, loaded.end_date), (canonical.start_date.isoformat(), canonical.end_date.isoformat()))
        self.assertFalse(loaded.trades.empty)
        self.assertEqual(list(loaded.trades[["Entry Date", "Exit Date", "Entry Price", "Exit Price", "Shares", "PnL"]].iloc[0]), [canonical.trades.iloc[0]["Entry Date"].isoformat(), canonical.trades.iloc[0]["Exit Date"].isoformat(), canonical.trades.iloc[0]["Entry Price"], canonical.trades.iloc[0]["Exit Price"], canonical.trades.iloc[0]["Shares"], canonical.trades.iloc[0]["PnL"]])
        self.assertEqual(len(loaded.equity_curve), len(canonical.equity_curve))
        for actual, expected in zip(loaded.equity_curve, canonical.equity_curve): self.assertAlmostEqual(actual, expected)
        self.assertEqual(list(loaded.equity_curve.index), [item.isoformat() for item in canonical.equity_curve.index])
        with self.assertRaisesRegex(serialization.BacktestResultSerializationError, "BacktestResult"):
            serialization.serialize_backtest_result(alternate)
        with self.assertRaisesRegex(PaperTradingModelError, "BacktestResult"):
            convert_backtest_result_to_simulated_paper_trading_result(alternate)

    def test_converter_accepts_canonical_and_production_consumers_avoid_alternate_imports(self):
        _, result = self.canonical()
        converted = convert_backtest_result_to_simulated_paper_trading_result(result)
        self.assertEqual((converted.symbol, converted.initial_cash, converted.final_cash, converted.total_equity), ("2330", 100, result.final_capital, result.final_capital))
        self.assertEqual((len(converted.orders), len(converted.fills)), (2, 2))
        self.assertEqual([order.side for order in converted.orders], ["BUY", "SELL"])
        self.assertEqual([order.quantity for order in converted.orders], [result.trades.iloc[0]["Shares"]] * 2)
        self.assertEqual([fill.quantity for fill in converted.fills], [result.trades.iloc[0]["Shares"]] * 2)
        self.assertEqual([fill.price for fill in converted.fills], [result.trades.iloc[0]["Entry Price"], result.trades.iloc[0]["Exit Price"]])
        self.assertEqual([order.order_id for order in converted.orders], ["backtest-000000-buy", "backtest-000000-sell"])
        self.assertEqual([fill.order_id for fill in converted.fills], ["backtest-000000-buy", "backtest-000000-sell"])
        self.assertEqual((converted.open_position_count, converted.final_position_quantity), (0, 0))
        documented_consumers = {
            "src/tw_stock_tool/cli/backtest_result_export_cli.py", "src/tw_stock_tool/cli/backtest_artifact_cli.py", "src/tw_stock_tool/cli/backtest_report.py", "src/tw_stock_tool/backtesting/serialization.py", "src/tw_stock_tool/backtesting/serialization_files.py", "src/tw_stock_tool/backtesting/parameter_sweep.py", "src/tw_stock_tool/backtesting/strategy_compare.py", "src/tw_stock_tool/backtesting/walk_forward.py", "src/tw_stock_tool/gui/app_services.py", "src/tw_stock_tool/cli/main.py", "src/tw_stock_tool/paper_trading/backtest_converter.py",
        }
        expected_imports = {
            "src/tw_stock_tool/cli/backtest_result_export_cli.py": {"tw_stock_tool.backtesting.backtest", "tw_stock_tool.backtesting.serialization", "tw_stock_tool.backtesting.serialization_files", "tw_stock_tool.backtesting.strategies"},
            "src/tw_stock_tool/cli/backtest_artifact_cli.py": {"tw_stock_tool.backtesting.serialization", "tw_stock_tool.backtesting.serialization_files", "tw_stock_tool.paper_trading"},
            "src/tw_stock_tool/cli/backtest_report.py": {"tw_stock_tool.backtesting.backtest", "tw_stock_tool.backtesting.strategies"},
            "src/tw_stock_tool/backtesting/serialization.py": {"tw_stock_tool.backtesting.results"},
            "src/tw_stock_tool/backtesting/serialization_files.py": {"tw_stock_tool.backtesting.results", "tw_stock_tool.backtesting.serialization"},
            "src/tw_stock_tool/backtesting/parameter_sweep.py": {"tw_stock_tool.backtesting.backtest", "tw_stock_tool.backtesting.strategies"},
            "src/tw_stock_tool/backtesting/strategy_compare.py": {"tw_stock_tool.backtesting.backtest", "tw_stock_tool.backtesting.strategies"},
            "src/tw_stock_tool/backtesting/walk_forward.py": {"tw_stock_tool.backtesting.backtest", "tw_stock_tool.backtesting.parameter_sweep", "tw_stock_tool.backtesting.strategies"},
            "src/tw_stock_tool/gui/app_services.py": {"tw_stock_tool.backtesting.backtest"}, "src/tw_stock_tool/cli/main.py": {"tw_stock_tool.backtesting.backtest"}, "src/tw_stock_tool/paper_trading/backtest_converter.py": {"tw_stock_tool.backtesting.results"},
        }
        self.assertEqual(set(expected_imports), documented_consumers); self.assertEqual(len(expected_imports), 11)
        def imported_modules(path):
            modules = set()
            for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import): modules.update(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    base = node.module or ""; modules.add(base) if base else None
                    modules.update(f"{base}.{a.name}" for a in node.names if base and a.name != "*")
            return modules
        for name in documented_consumers:
            imports = imported_modules(name)
            self.assertTrue(expected_imports[name].issubset(imports), f"{name}: expected {expected_imports[name]}, found {imports}")
            self.assertNotIn("tw_stock_tool.backtest.engine", imports); self.assertNotIn("tw_stock_tool.strategies.base", imports)

if __name__ == "__main__":
    unittest.main()