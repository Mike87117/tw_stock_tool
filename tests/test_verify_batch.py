import unittest
import pandas as pd
from pathlib import Path
import tempfile
from unittest.mock import patch
from tw_stock_tool.utils.verify_batch import write_report

class TestVerifyBatch(unittest.TestCase):
    @patch("tw_stock_tool.utils.verify_batch.pd.ExcelWriter")
    def test_export_excel_permission_error(self, mock_writer):
        mock_writer.side_effect = PermissionError("locked")
        with tempfile.TemporaryDirectory() as d:
            out_path = Path(d) / "test.xlsx"
            with self.assertRaisesRegex(ValueError, "Failed to write Excel file.*Please close the file if it is open"):
                write_report(pd.DataFrame(), [], "", "", out_path)

if __name__ == "__main__":
    unittest.main()