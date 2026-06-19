import unittest
from unittest.mock import patch

import pandas as pd

import benchmark


class BenchmarkTest(unittest.TestCase):
    def test_run_benchmark_returns_summary_detail_and_errors(self) -> None:
        fake_scan = pd.DataFrame(
            [
                {"Stock": "2330", "Symbol": "2330.TW", "Status": "OK", "Error": ""},
                {"Stock": "9999", "Symbol": "", "Status": "ERROR", "Error": "bad stock"},
            ]
        )

        with patch.object(benchmark, "scan_stocks", return_value=fake_scan):
            result = benchmark.run_benchmark(["2330", "9999"], workers=2, repeat=2)

        self.assertIn("Avg Elapsed Seconds", result.summary.columns)
        self.assertIn("Success Rate %", result.detail.columns)
        self.assertEqual(len(result.detail), 2)
        self.assertEqual(result.detail.loc[0, "OK"], 1)
        self.assertEqual(result.detail.loc[0, "ERROR"], 1)
        self.assertEqual(result.errors.loc[0, "Stock"], "9999")
        self.assertEqual(result.errors.loc[0, "Error"], "bad stock")

    def test_run_benchmark_rejects_invalid_workers(self) -> None:
        with self.assertRaises(ValueError):
            benchmark.run_benchmark(["2330"], workers=0)

    def test_run_benchmark_rejects_invalid_repeat(self) -> None:
        with self.assertRaises(ValueError):
            benchmark.run_benchmark(["2330"], repeat=0)

    def test_output_paths_create_three_csv_names(self) -> None:
        paths = benchmark._output_paths("output/custom.csv")

        self.assertIsNotNone(paths)
        assert paths is not None
        self.assertEqual(paths["summary"].name, "custom_summary.csv")
        self.assertEqual(paths["detail"].name, "custom_detail.csv")
        self.assertEqual(paths["errors"].name, "custom_errors.csv")


if __name__ == "__main__":
    unittest.main()
