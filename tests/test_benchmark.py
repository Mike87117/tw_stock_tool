import unittest
from unittest.mock import patch

import pandas as pd

import benchmark


class BenchmarkTest(unittest.TestCase):
    def test_run_benchmark_returns_summary(self) -> None:
        fake_scan = pd.DataFrame(
            [
                {"Stock": "2330", "Status": "OK"},
                {"Stock": "9999", "Status": "ERROR"},
            ]
        )

        with patch.object(benchmark, "scan_stocks", return_value=fake_scan):
            result = benchmark.run_benchmark(["2330", "9999"], workers=2)

        self.assertEqual(result.loc[0, "Stocks"], 2)
        self.assertEqual(result.loc[0, "OK"], 1)
        self.assertEqual(result.loc[0, "ERROR"], 1)
        self.assertIn("Elapsed Seconds", result.columns)


if __name__ == "__main__":
    unittest.main()
