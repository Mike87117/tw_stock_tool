from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.data import cache_runtime


def _frame(value: float = 100.) -> pd.DataFrame:
    return pd.DataFrame({"Open": value, "High": value + 2, "Low": value - 1,
                         "Close": value + 1, "Volume": 1000},
                        index=pd.date_range("2026-01-01", periods=200).rename("Date"))


class AtomicCacheWriteTest(unittest.TestCase):
    def test_successful_write_replaces_entire_cache_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "nested" / "prices.csv"
            cache_runtime._write_cache(_frame(), path)
            cache_runtime._write_cache(_frame(200), path)
            pd.testing.assert_frame_equal(cache_runtime._read_cache(path), _frame(200), check_freq=False)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_interrupted_write_preserves_existing_bytes_and_timestamp(self):
        original_to_csv = pd.DataFrame.to_csv

        def interrupted_write(frame, destination):
            original_to_csv(frame.iloc[:80], destination)
            raise OSError("disk write interrupted")

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "prices.csv"
            cache_runtime._write_cache(_frame(), path)
            original = path.read_bytes()
            timestamp = path.stat().st_mtime_ns
            with patch.object(pd.DataFrame, "to_csv", interrupted_write):
                with self.assertRaisesRegex(OSError, "disk write interrupted"):
                    cache_runtime._write_cache(_frame(200), path)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(path.stat().st_mtime_ns, timestamp)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_failed_first_write_leaves_no_partial_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "prices.csv"
            with patch.object(pd.DataFrame, "to_csv", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    cache_runtime._write_cache(_frame(), path)
            self.assertEqual(list(path.parent.iterdir()), [])

    def test_replace_failure_preserves_old_cache_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "prices.csv"
            cache_runtime._write_cache(_frame(), path)
            original = path.read_bytes()
            with patch.object(cache_runtime.os, "replace", side_effect=PermissionError("file locked")):
                with self.assertRaises(PermissionError):
                    cache_runtime._write_cache(_frame(200), path)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_concurrent_writes_leave_one_complete_frame(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "prices.csv"
            frames = [_frame(value) for value in range(100, 104)]
            with ThreadPoolExecutor(max_workers=4) as executor:
                list(executor.map(lambda frame: cache_runtime._write_cache(frame, path), frames))
            actual = cache_runtime._read_cache(path)
            pd.testing.assert_frame_equal(actual, _frame(actual.iloc[0]["Open"]), check_freq=False)
            self.assertEqual(list(path.parent.iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
