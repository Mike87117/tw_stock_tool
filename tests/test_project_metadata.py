import tomllib
import unittest
from pathlib import Path


class ProjectMetadataTest(unittest.TestCase):
    def _metadata(self) -> dict:
        path = Path("pyproject.toml")
        self.assertTrue(path.exists())
        return tomllib.loads(path.read_text(encoding="utf-8"))

    def test_pyproject_exists(self) -> None:
        self.assertTrue(Path("pyproject.toml").exists())

    def test_console_script(self) -> None:
        metadata = self._metadata()

        self.assertEqual(metadata["project"]["scripts"]["twstock"], "twstock_cli:main")

    def test_requires_python(self) -> None:
        metadata = self._metadata()

        self.assertEqual(metadata["project"]["requires-python"], ">=3.11")

    def test_main_dependencies_exist(self) -> None:
        metadata = self._metadata()
        dependencies = set(metadata["project"]["dependencies"])

        expected = {
            "yfinance>=0.2,<0.3",
            "pandas>=2.1,<3.0",
            "numpy>=1.26,<3.0",
            "matplotlib>=3.8,<4.0",
            "mplfinance>=0.12,<0.13",
            "openpyxl>=3.1,<4.0",
            "requests>=2.31,<3.0",
            "scikit-learn>=1.3,<2.0",
        }
        self.assertTrue(expected.issubset(dependencies))


if __name__ == "__main__":
    unittest.main()
