import importlib
import unittest


class CiImportsTest(unittest.TestCase):
    def test_cli_modules_import(self) -> None:
        for module_name in [
            "main",
            "scan_stocks",
            "strategy_compare",
            "benchmark",
            "cache_manager",
            "parameter_sweep",
            "walk_forward",
            "daily_report",
            "clean_stocks",
            "ml_dataset",
            "ai_walk_forward",
        ]:
            with self.subTest(module=module_name):
                self.assertIsNotNone(importlib.import_module(module_name))


if __name__ == "__main__":
    unittest.main()
