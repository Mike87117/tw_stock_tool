import unittest

class TestBacktestConverterPublicApi(unittest.TestCase):
    def test_public_import_path(self):
        # Import from the public package
        from tw_stock_tool.paper_trading import (
            convert_backtest_result_to_simulated_paper_trading_result as public_converter,
        )
        # Import directly from the module
        from tw_stock_tool.paper_trading.backtest_converter import (
            convert_backtest_result_to_simulated_paper_trading_result as direct_converter,
        )
        
        # Verify that they are exactly the same callable
        self.assertIs(public_converter, direct_converter)

if __name__ == "__main__":
    unittest.main()
