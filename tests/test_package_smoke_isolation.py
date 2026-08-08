"""Regressions for Issue #84 B9: installed-package smoke must not be fooled.

The repository root ships a compatibility namespace shim, so any smoke check
executed with the checkout on ``sys.path`` imports the working tree instead of
the installed distribution. These tests pin the isolation contract and keep the
CI smoke inventory in sync with the unified CLI's public routes.

The full end-to-end proof (``pip install .`` then run outside the tree) lives in
the package-smoke CI job; here we prove the detection logic actually fires and
that CI is wired to the isolated entrypoint rather than the old in-tree form.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.subprocess_test_support import run_repo_python
from tests.test_track_p2_1_unified_cli_passthrough_registration_characterization import ROUTES


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPOSITORY_ROOT / "scripts" / "package_smoke.py"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "python-tests.yml"


def _load_smoke_module():
    spec = importlib.util.spec_from_file_location("_package_smoke_under_test", SMOKE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackageSmokeIsolationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.smoke = _load_smoke_module()

    def test_repository_root_shim_still_shadows_an_in_tree_import(self) -> None:
        """Characterizes the hazard the CI smoke has to survive.

        If this ever stops being true the shim was removed, and the isolation
        assertions below become trivially satisfiable rather than meaningful.
        """
        completed = run_repo_python(
            "-c",
            "import tw_stock_tool; print(tw_stock_tool.__file__)",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        resolved = Path(completed.stdout.strip())
        self.assertEqual(resolved, REPOSITORY_ROOT / "tw_stock_tool" / "__init__.py")

    def test_isolation_check_rejects_a_checkout_resolved_import(self) -> None:
        failures = self.smoke.check_import_isolation(REPOSITORY_ROOT)

        # This test process imports tw_stock_tool from the checkout, so every
        # isolation assertion must fire. A vacuous check would return [].
        self.assertTrue(failures)
        joined = "\n".join(failures)
        self.assertIn("__file__ resolves inside the checkout", joined)
        self.assertIn("twstock_cli resolves inside the checkout", joined)

    def test_isolation_check_accepts_an_out_of_tree_import(self) -> None:
        elsewhere = REPOSITORY_ROOT.parent / "definitely-not-this-checkout"

        self.assertEqual(self.smoke.check_import_isolation(elsewhere), [])

    def test_distribution_version_mismatch_is_reported(self) -> None:
        failures = self.smoke.check_distribution_version("0.0.0-not-a-real-version")

        self.assertTrue(failures)
        self.assertRegex(failures[0], r"(!=|is not an installed distribution)")

    def test_isolated_environment_strips_checkout_entries_from_pythonpath(self) -> None:
        polluted = os.pathsep.join(
            [
                str(REPOSITORY_ROOT),
                str(REPOSITORY_ROOT / "src"),
                str(REPOSITORY_ROOT.parent / "unrelated"),
            ]
        )
        with patch.dict(os.environ, {"PYTHONPATH": polluted}):
            environment = self.smoke._isolated_environment(REPOSITORY_ROOT)

        self.assertNotIn(str(REPOSITORY_ROOT), environment.get("PYTHONPATH", ""))
        self.assertNotIn(str(REPOSITORY_ROOT / "src"), environment.get("PYTHONPATH", ""))
        self.assertIn(str(REPOSITORY_ROOT.parent / "unrelated"), environment["PYTHONPATH"])
        self.assertEqual(environment["PYTHONIOENCODING"], "utf-8")

    def test_smoke_help_inventory_covers_every_public_route(self) -> None:
        """CI must assert help for every route the unified CLI exposes."""
        smoke_routes = {tokens for tokens, _ in self.smoke.HELP_MARKERS}
        cli_routes = {route.tokens for route in ROUTES}
        # "stock-list" is a wrapper-owned grouping node and is not a Route.
        cli_routes.add(("stock-list",))

        missing = cli_routes - smoke_routes
        self.assertEqual(missing, set(), f"scripts/package_smoke.py does not cover: {sorted(missing)}")

    def test_smoke_help_markers_match_the_cli_route_table(self) -> None:
        smoke_markers = dict(self.smoke.HELP_MARKERS)
        for route in ROUTES:
            with self.subTest(route=route.name):
                self.assertEqual(smoke_markers[route.tokens], route.help_marker)


class PackageSmokeWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_ci_runs_the_isolated_smoke_entrypoint(self) -> None:
        self.assertIn("python scripts/package_smoke.py --repository-root .", self.workflow)

    def test_ci_no_longer_relies_on_in_tree_import_assertions(self) -> None:
        # These forms passed while resolving the repository shim, so they can
        # never come back as the package-smoke evidence (Issue #84 B9).
        for retired in (
            'python -c "import tw_stock_tool"',
            'python -c "from tw_stock_tool.cli import twstock_cli"',
        ):
            self.assertNotIn(retired, self.workflow)

    def test_ci_verifies_doctor_against_the_installed_distribution(self) -> None:
        self.assertIn("twstock doctor", self.workflow)


if __name__ == "__main__":
    unittest.main()
