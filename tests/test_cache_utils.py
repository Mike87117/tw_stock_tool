from pathlib import Path
import tempfile
import unittest

from cache_utils import cache_summary, clear_cache, list_cache_files


class CacheUtilsTest(unittest.TestCase):
    def test_list_summary_and_clear_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir)
            (cache_dir / "a.csv").write_text("x\n", encoding="utf-8")
            (cache_dir / "b.txt").write_text("x\n", encoding="utf-8")

            files = list_cache_files(cache_dir)
            summary = cache_summary(cache_dir)
            cleared = clear_cache(cache_dir)

        self.assertEqual([path.name for path in files], ["a.csv"])
        self.assertEqual(len(summary), 1)
        self.assertEqual(cleared, 1)


if __name__ == "__main__":
    unittest.main()
