import importlib
import unittest


class CiImportsTest(unittest.TestCase):
    def test_cli_modules_import(self) -> None:
        for module_name in [
            "tw_stock_tool.cli.main",
            "tw_stock_tool.cli.scan_stocks",
            "tw_stock_tool.backtesting.strategy_compare",
            "tw_stock_tool.cli.benchmark",
            "tw_stock_tool.data.cache_manager",
            "tw_stock_tool.backtesting.parameter_sweep",
            "tw_stock_tool.backtesting.walk_forward",
            "tw_stock_tool.reports.daily_report",
            "tw_stock_tool.cli.clean_stocks",
            "tw_stock_tool.ml.ml_dataset",
            "tw_stock_tool.ml.ai_walk_forward",
            "tw_stock_tool.ml.baseline_ml_model",
            "tw_stock_tool.reports.ai_prediction_report",
            "tw_stock_tool.ml.ai_stock_scanner",
            "tw_stock_tool.gui.app_services",
            "tw_stock_tool.data.stock_list_updater",
            "tw_stock_tool.analysis.stock_selection",
            "tw_stock_tool.cli.stock_list_smoke_check",
            "tw_stock_tool.cli.price_data_smoke_check",
            "tw_stock_tool.utils.doctor",
            "tw_stock_tool.cli.twstock_cli",
        ]:
            with self.subTest(module=module_name):
                self.assertIsNotNone(importlib.import_module(module_name))


if __name__ == "__main__":
    unittest.main()
