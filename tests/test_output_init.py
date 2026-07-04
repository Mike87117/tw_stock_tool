import unittest

from tw_stock_tool.utils.output import write_text_report
from tw_stock_tool.utils.output import write_csv_bundle
from tw_stock_tool.utils.output import __all__ as output_all
from tw_stock_tool.utils.output.writers import write_text_report as src_write_text_report
from tw_stock_tool.utils.output.writers import write_csv_bundle as src_write_csv_bundle

class TestOutputInit(unittest.TestCase):
    def test_exposed_functions(self):
        self.assertTrue(callable(write_text_report))
        self.assertTrue(callable(write_csv_bundle))
        self.assertIn("write_text_report", output_all)
        self.assertIn("write_csv_bundle", output_all)
        self.assertIs(write_text_report, src_write_text_report)
        self.assertIs(write_csv_bundle, src_write_csv_bundle)

if __name__ == "__main__":
    unittest.main()
