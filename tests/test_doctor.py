import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            for file_name in doctor.REQUIRED_CLI_FILES + ["requirements.txt"]:
                (root / file_name).write_text("", encoding="utf-8")
            with patch.object(doctor, "check_imports", return_value=[]):
                with patch.object(doctor, "check_directories", return_value=[]):
                    with patch.object(doctor, "check_required_files", return_value=[]):
                        with patch.object(doctor, "check_requirements_file", return_value={"Check": "requirements.txt", "Status": doctor.PASS, "Message": ""}):
                            with patch.object(doctor, "check_live_sources") as live_mock:
                                rows = doctor.run_doctor(live=False)

        live_mock.assert_not_called()
        self.assertTrue(rows)

    def test_run_doctor_with_live_calls_smoke_checks(self) -> None:
        with patch.object(doctor, "check_imports", return_value=[]):
            with patch.object(doctor, "check_directories", return_value=[]):
                with patch.object(doctor, "check_required_files", return_value=[]):
                    with patch.object(doctor, "check_requirements_file", return_value={"Check": "requirements.txt", "Status": doctor.PASS, "Message": ""}):
                        with patch.object(doctor, "check_live_sources", return_value=[{"Check": "live", "Status": doctor.PASS, "Message": ""}]) as live_mock:
                            rows = doctor.run_doctor(live=True)

        live_mock.assert_called_once_with()
        self.assertEqual(rows[-1]["Check"], "live")

    def test_cli_args_parsing(self) -> None:
        args = doctor._parse_args(["--live"])

        self.assertTrue(args.live)


if __name__ == "__main__":
    unittest.main()
