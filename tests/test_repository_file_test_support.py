from pathlib import Path
import tempfile
import unittest

from tests.repository_file_test_support import iter_repository_files


class RepositoryFileAuditTest(unittest.TestCase):
    def test_environment_binaries_are_excluded_but_repository_binaries_remain_visible(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = [
                ".git/private.p12",
                ".venv/pyvenv.cfg", ".venv/Lib/site-packages/pip/vendor.whl",
                "tools/custom-environment/pyvenv.cfg", "tools/custom-environment/certifi/ca.pem",
                "src/client.pfx", "tests/fixtures/vendor.whl", ".hidden/client.p12",
                "venv-without-marker/client.pem", "src/module.py",
            ]
            for name in paths:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture", encoding="utf-8")

            scanned = {path.relative_to(root).as_posix() for path in iter_repository_files(root)}
            self.assertEqual(scanned, {
                "src/client.pfx", "tests/fixtures/vendor.whl", ".hidden/client.p12",
                "venv-without-marker/client.pem", "src/module.py",
            })


if __name__ == "__main__":
    unittest.main()
