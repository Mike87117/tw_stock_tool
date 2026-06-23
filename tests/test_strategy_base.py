import unittest

import pandas as pd

from src.tw_stock_tool.strategies.base import BaseStrategy


class ExampleStrategy(BaseStrategy):
    name = "example"

    def generate_signals(self, df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
        result = df.copy()
        result["entry_signal"] = result["Close"] > result["Close"].rolling(2).mean()
        result["exit_signal"] = result["Close"] < result["Close"].rolling(2).mean()
        result["entry_signal"] = result["entry_signal"].fillna(False).astype(bool)
        result["exit_signal"] = result["exit_signal"].fillna(False).astype(bool)
        return result


class StrategyBaseTest(unittest.TestCase):
    def test_base_strategy_is_abstract(self) -> None:
        with self.assertRaises(TypeError):
            BaseStrategy()

    def test_class_has_name_attribute(self) -> None:
        self.assertEqual(BaseStrategy.name, "base")
        self.assertEqual(ExampleStrategy.name, "example")

    def test_generate_signals_returns_valid_bool_columns(self) -> None:
        df = pd.DataFrame({"Close": [10, 11, 9, 12]})
        strategy = ExampleStrategy()

        result = strategy.generate_signals(df)
        strategy.validate_signals(result)

        self.assertIn("entry_signal", result.columns)
        self.assertIn("exit_signal", result.columns)
        self.assertTrue(pd.api.types.is_bool_dtype(result["entry_signal"]))
        self.assertTrue(pd.api.types.is_bool_dtype(result["exit_signal"]))
        self.assertEqual(len(result), len(df))

    def test_strategy_does_not_need_to_modify_original_dataframe(self) -> None:
        df = pd.DataFrame({"Close": [10, 11, 9, 12]})
        original_columns = list(df.columns)

        ExampleStrategy().generate_signals(df)

        self.assertEqual(list(df.columns), original_columns)
        self.assertNotIn("entry_signal", df.columns)
        self.assertNotIn("exit_signal", df.columns)

    def test_validate_signals_requires_entry_signal(self) -> None:
        df = pd.DataFrame({"exit_signal": [False, True]})

        with self.assertRaisesRegex(ValueError, "Missing required signal column: entry_signal"):
            ExampleStrategy().validate_signals(df)

    def test_validate_signals_requires_exit_signal(self) -> None:
        df = pd.DataFrame({"entry_signal": [True, False]})

        with self.assertRaisesRegex(ValueError, "Missing required signal column: exit_signal"):
            ExampleStrategy().validate_signals(df)

    def test_validate_signals_requires_bool_entry_signal(self) -> None:
        df = pd.DataFrame(
            {
                "entry_signal": [1, 0],
                "exit_signal": [False, True],
            }
        )

        with self.assertRaisesRegex(ValueError, "Signal column must be bool: entry_signal"):
            ExampleStrategy().validate_signals(df)

    def test_validate_signals_requires_bool_exit_signal(self) -> None:
        df = pd.DataFrame(
            {
                "entry_signal": [True, False],
                "exit_signal": ["yes", "no"],
            }
        )

        with self.assertRaisesRegex(ValueError, "Signal column must be bool: exit_signal"):
            ExampleStrategy().validate_signals(df)


if __name__ == "__main__":
    unittest.main()
