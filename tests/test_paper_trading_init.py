import unittest

import tw_stock_tool.paper_trading as pt
from tw_stock_tool.paper_trading import export_simulated_paper_trading_markdown_file
from tw_stock_tool.paper_trading import export_simulated_paper_trading_csv_files
from tw_stock_tool.paper_trading.export_files import (
    export_simulated_paper_trading_markdown_file as orig_markdown_file,
    export_simulated_paper_trading_csv_files as orig_csv_files,
)

class TestPaperTradingInit(unittest.TestCase):
    def test_exports(self):
        # 1. Callable
        self.assertTrue(callable(export_simulated_paper_trading_markdown_file))
        self.assertTrue(callable(export_simulated_paper_trading_csv_files))

        # 2. Present in __all__
        self.assertIn("export_simulated_paper_trading_markdown_file", pt.__all__)
        self.assertIn("export_simulated_paper_trading_csv_files", pt.__all__)

        # 3. Same objects as underlying implementations
        self.assertIs(export_simulated_paper_trading_markdown_file, orig_markdown_file)
        self.assertIs(export_simulated_paper_trading_csv_files, orig_csv_files)

if __name__ == "__main__":
    unittest.main()
