import subprocess
import sys
import unittest
from pathlib import Path

class TestRootWrappers(unittest.TestCase):
    def test_parameter_sweep_wrapper_resolves_to_cli(self) -> None:
        repo_root = Path(__file__).parent.parent
        script = repo_root / "parameter_sweep.py"
        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            check=True
        )
        self.assertIn("--output-excel", result.stdout, "Root wrapper did not resolve to CLI module (missing --output-excel)")
        self.assertIn("Parameter Sweep Report CLI", result.stdout)

    def test_walk_forward_wrapper_resolves_to_cli(self) -> None:
        repo_root = Path(__file__).parent.parent
        script = repo_root / "walk_forward.py"
        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            check=True
        )
        self.assertIn("--output-excel", result.stdout, "Root wrapper did not resolve to CLI module (missing --output-excel)")
        self.assertIn("Walk Forward Report CLI", result.stdout)

    def test_parameter_sweep_report_wrapper_exists(self) -> None:
        repo_root = Path(__file__).parent.parent
        script = repo_root / "parameter_sweep_report.py"
        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            check=True
        )
        self.assertIn("--output-excel", result.stdout)
        self.assertIn("Parameter Sweep Report CLI", result.stdout)

    def test_walk_forward_report_wrapper_exists(self) -> None:
        repo_root = Path(__file__).parent.parent
        script = repo_root / "walk_forward_report.py"
        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            check=True
        )
        self.assertIn("--output-excel", result.stdout)
        self.assertIn("Walk Forward Report CLI", result.stdout)

    def test_backtest_report_wrapper_exists(self) -> None:
        repo_root = Path(__file__).parent.parent
        script = repo_root / "backtest_report.py"
        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            check=True
        )
        self.assertIn("--output-excel", result.stdout)
        self.assertIn("Backtest Report", result.stdout)

if __name__ == "__main__":
    unittest.main()
