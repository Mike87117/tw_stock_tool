import unittest
import tempfile
from pathlib import Path
from tw_stock_tool.utils.output.writers import write_text_report, write_csv_bundle

class TestOutputWriters(unittest.TestCase):

    def test_write_text_report(self):
        with tempfile.TemporaryDirectory() as tempdir:
            temp_path = Path(tempdir) / "nested" / "test_report.md"
            content = "# Title\nTest content"

            # 1. Writes exact content and creates parent dirs
            result_path = write_text_report(content, temp_path)

            # 2. Returns a Path
            self.assertIsInstance(result_path, Path)

            # 3. Points to an existing file
            self.assertTrue(result_path.exists())
            self.assertTrue(result_path.is_absolute())

            with open(result_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), content)

            # 4. Raises FileExistsError when file exists and overwrite=False
            with self.assertRaises(FileExistsError):
                write_text_report("New content", result_path, overwrite=False)

            # 5. Overwrites existing file when overwrite=True
            write_text_report("New content", result_path, overwrite=True)
            with open(result_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "New content")

    def test_write_csv_bundle(self):
        with tempfile.TemporaryDirectory() as tempdir:
            temp_dir_path = Path(tempdir) / "nested_out"
            bundle = {
                "summary": "metric,value\na,1\n",
                "orders": "id,side\n1,BUY\n",
                "fills": "id,price\n1,10.0\n",
            }

            result_paths = write_csv_bundle(bundle, temp_dir_path, basename="test_run")

            # 7. Returns dict keys exactly
            self.assertEqual(set(result_paths.keys()), {"summary", "orders", "fills"})

            # 6. Writes exactly three files
            self.assertTrue((temp_dir_path / "test_run_summary.csv").exists())
            self.assertTrue((temp_dir_path / "test_run_orders.csv").exists())
            self.assertTrue((temp_dir_path / "test_run_fills.csv").exists())

            for p in result_paths.values():
                self.assertIsInstance(p, Path)
                self.assertTrue(p.is_absolute())

            # 8. CSV file contents exactly match input strings
            with open(result_paths["summary"], "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), bundle["summary"])

            # 11. Raises FileExistsError when any target exists and overwrite=False
            with self.assertRaises(FileExistsError):
                write_csv_bundle(bundle, temp_dir_path, basename="test_run", overwrite=False)

            # 12. Overwrites existing files when overwrite=True
            new_bundle = {k: v + "new" for k, v in bundle.items()}
            write_csv_bundle(new_bundle, temp_dir_path, basename="test_run", overwrite=True)
            with open(result_paths["summary"], "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), bundle["summary"] + "new")

    def test_write_csv_bundle_invalid_keys(self):
        with tempfile.TemporaryDirectory() as tempdir:
            # 9. Raises ValueError for missing keys
            with self.assertRaises(ValueError):
                write_csv_bundle({"summary": "", "orders": ""}, tempdir)

            # 10. Raises ValueError for extra keys
            with self.assertRaises(ValueError):
                write_csv_bundle({"summary": "", "orders": "", "fills": "", "extra": ""}, tempdir)

if __name__ == "__main__":
    unittest.main()
