import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.subprocess_test_support import run_repo_python
from tw_stock_tool.utils import doctor


class DoctorTest(unittest.TestCase):
    def test_import_check_pass(self) -> None:
        with patch.object(doctor.importlib, "import_module", return_value=object()) as mocked:
            rows = doctor.check_imports({"pandas": "pandas"})

        mocked.assert_called_once_with("pandas")
        self.assertEqual(rows[0]["Status"], doctor.PASS)

    def test_missing_package_fails(self) -> None:
        with patch.object(doctor.importlib, "import_module", side_effect=ImportError("missing")):
            rows = doctor.check_imports({"missing-package": "missing_package"})

        self.assertEqual(rows[0]["Status"], doctor.FAIL)
        self.assertIn("missing", rows[0]["Message"])

    def test_python_version_below_311_warns(self) -> None:
        row = doctor.check_python_version((3, 10, 9))

        self.assertEqual(row["Status"], doctor.WARNING)
        self.assertIn("recommended >= 3.11", row["Message"])

    def test_directory_writable_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "cache"
            row = doctor.check_directory_writable(path)

            self.assertEqual(row["Status"], doctor.PASS)
            self.assertTrue(path.exists())
            self.assertFalse((path / ".doctor_write_test.tmp").exists())

    def test_live_calls_smoke_checks_when_enabled(self) -> None:
        with patch.object(doctor.stock_list_smoke_check, "run_smoke_check", return_value={}) as stock_mock:
            with patch.object(doctor.price_data_smoke_check, "run_smoke_check", return_value=[]) as price_mock:
                rows = doctor.check_live_sources()

        stock_mock.assert_called_once_with()
        price_mock.assert_called_once_with()
        self.assertTrue(all(row["Status"] == doctor.PASS for row in rows))

    def test_run_doctor_without_live_does_not_call_smoke_checks(self) -> None:
        # Only the live boundary is mocked. Path resolution, package-version
        # resolution and requirements discovery all run for real, so a broken
        # repository-layout contract fails this test instead of hiding behind
        # a stub (Issue #84 B1 test blind spot).
        with patch.object(doctor, "check_imports", return_value=[]):
            with patch.object(doctor, "check_directories", return_value=[]):
                with patch.object(doctor, "check_live_sources") as live_mock:
                    rows = doctor.run_doctor(live=False)

        live_mock.assert_not_called()
        self.assertTrue(rows)
        self.assertFalse(
            doctor.has_failures(rows),
            f"doctor must pass in this development checkout: {[row for row in rows if row['Status'] == doctor.FAIL]}",
        )

    def test_run_doctor_with_live_calls_smoke_checks(self) -> None:
        with patch.object(doctor, "check_imports", return_value=[]):
            with patch.object(doctor, "check_directories", return_value=[]):
                with patch.object(doctor, "check_live_sources", return_value=[{"Check": "live", "Status": doctor.PASS, "Message": ""}]) as live_mock:
                    rows = doctor.run_doctor(live=True)

        live_mock.assert_called_once_with()
        self.assertEqual(rows[-1]["Check"], "live")

    def test_cli_args_parsing(self) -> None:
        args = doctor._parse_args(["--live"])

        self.assertTrue(args.live)


class DoctorRepositoryContractTest(unittest.TestCase):
    """Real-filesystem regressions for Issue #84 B1.

    These deliberately avoid mocking path resolution: the original defect was
    that check_required_files()/check_requirements_file() resolved repository
    files from src/tw_stock_tool/utils/, and every run_doctor() test stubbed
    both checks out.
    """

    def test_find_repository_root_locates_this_checkout_from_the_module(self) -> None:
        expected = Path(doctor.__file__).resolve().parents[3]
        root = doctor.find_repository_root()

        self.assertEqual(root, expected)
        self.assertTrue((root / "pyproject.toml").is_file())
        self.assertTrue((root / "src" / "tw_stock_tool").is_dir())
        self.assertTrue((root / "requirements.txt").is_file())

    def test_find_repository_root_returns_none_outside_a_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            installed_like = Path(tmp_dir) / "site-packages" / "tw_stock_tool" / "utils"
            installed_like.mkdir(parents=True)
            module_path = installed_like / "doctor.py"
            module_path.write_text("", encoding="utf-8")

            self.assertIsNone(doctor.find_repository_root(module_path))

    def test_find_repository_root_requires_both_layout_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "pyproject.toml").write_text("", encoding="utf-8")
            probe = root / "src" / "tw_stock_tool" / "utils" / "doctor.py"
            probe.parent.mkdir(parents=True)
            probe.write_text("", encoding="utf-8")
            self.assertEqual(doctor.find_repository_root(probe), root)

            (root / "pyproject.toml").unlink()
            self.assertIsNone(doctor.find_repository_root(probe))

    def test_requirements_check_reports_real_presence_and_absence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            missing = doctor.check_repository_requirements(root)
            self.assertEqual(missing["Status"], doctor.FAIL)
            self.assertIn("requirements.txt", missing["Message"])

            (root / "requirements.txt").write_text("pandas\n", encoding="utf-8")
            present = doctor.check_repository_requirements(root)
            self.assertEqual(present["Status"], doctor.PASS)
            self.assertEqual(present["Message"], str(root / "requirements.txt"))

    def test_package_version_passes_from_this_source_checkout(self) -> None:
        with patch.object(
            doctor.importlib.metadata,
            "version",
            side_effect=doctor.importlib.metadata.PackageNotFoundError(doctor.DISTRIBUTION_NAME),
        ):
            row = doctor.check_package_version()

        expected_root = doctor.find_repository_root()
        self.assertEqual(row["Status"], doctor.PASS)
        self.assertIn("source checkout", row["Message"])
        self.assertIn(str(expected_root), row["Message"])

    def test_package_version_passes_from_an_installed_distribution(self) -> None:
        with patch.object(doctor.importlib.metadata, "version", return_value="9.9.9") as version_mock:
            row = doctor.check_package_version()

        version_mock.assert_called_once_with(doctor.DISTRIBUTION_NAME)
        self.assertEqual(row["Status"], doctor.PASS)
        self.assertIn("9.9.9", row["Message"])
        self.assertIn("installed distribution", row["Message"])

    def test_installed_context_skips_repository_only_checks_instead_of_failing(self) -> None:
        with patch.object(doctor, "check_imports", return_value=[]):
            with patch.object(doctor, "check_directories", return_value=[]):
                with patch.object(doctor, "find_repository_root", return_value=None):
                    with patch.object(doctor.importlib.metadata, "version", return_value="0.4.0"):
                        rows = doctor.run_doctor(live=False)

        checks = [row["Check"] for row in rows]
        self.assertNotIn("requirements.txt", checks)
        self.assertIn("Package version", checks)
        self.assertFalse(doctor.has_failures(rows))

    def test_removed_root_wrapper_inventory_is_not_reintroduced(self) -> None:
        # docs/archive/root-wrapper-removal.md records 42 root entries removed
        # and 0 remaining; doctor must not require any of them again.
        for removed in ("REQUIRED_CLI_FILES", "check_required_files", "check_requirements_file"):
            self.assertFalse(hasattr(doctor, removed), f"{removed} should have been removed")

        source = Path(doctor.__file__).read_text(encoding="utf-8")
        for wrapper in ("scan_stocks.py", "daily_report.py", "ai_stock_scanner.py", "ai_prediction_report.py"):
            self.assertNotIn(wrapper, source)

    def test_doctor_exits_zero_in_this_checkout_via_the_unified_cli(self) -> None:
        completed = run_repo_python("-m", "tw_stock_tool.cli.twstock_cli", "doctor")

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("FAIL=0", completed.stdout)
        self.assertIn("Package version", completed.stdout)


if __name__ == "__main__":
    unittest.main()
