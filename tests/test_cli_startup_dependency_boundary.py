"""Startup dependency boundary for the unified CLI.

`sklearn` and `mplfinance` are only reachable from the ML and chart routes, but
both used to be imported at module scope on the unified CLI's import path. That
made every `twstock ...` invocation -- and every CLI contract test that starts a
child interpreter -- pay ~1.5s to build model and plotting machinery it never
touched.

These tests pin the boundary so a future top-level import cannot quietly
reintroduce the cost. They assert reachability, not timing, so they do not
depend on machine speed.
"""

import subprocess
import sys
import unittest

# Heavy, and only needed once an ML or chart route actually runs.
DEFERRED_DEPENDENCIES = ("sklearn", "matplotlib", "mplfinance")


def _module_present_after_import(imported_module: str, candidates: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    # A clean child process: the parent test run has already imported much of
    # the world, so sys.modules here would prove nothing.
    code = f"""
import importlib
import sys
importlib.import_module({imported_module!r})
found = sorted(
    name
    for name in sys.modules
    if any(name == prefix or name.startswith(prefix + ".") for prefix in {candidates!r})
)
if found:
    print("unexpectedly imported: " + ", ".join(found))
    raise SystemExit(1)
"""
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)


class CliStartupDependencyBoundaryTest(unittest.TestCase):
    def test_unified_cli_import_does_not_pull_in_model_or_plotting_stack(self) -> None:
        result = _module_present_after_import("tw_stock_tool.cli.twstock_cli", DEFERRED_DEPENDENCIES)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_baseline_ml_model_import_does_not_pull_in_sklearn(self) -> None:
        result = _module_present_after_import("tw_stock_tool.ml.baseline_ml_model", ("sklearn",))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_plotter_import_does_not_pull_in_matplotlib(self) -> None:
        result = _module_present_after_import("tw_stock_tool.reports.plotter", ("matplotlib", "mplfinance"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_deferred_dependencies_are_still_reachable_where_they_are_used(self) -> None:
        """The imports moved, so confirm they still resolve when the code runs.

        A deferred import that no longer resolves would only surface the first
        time someone trains a model or renders a chart.
        """
        from tw_stock_tool.ml import baseline_ml_model
        from tw_stock_tool.reports import plotter

        self.assertTrue(callable(baseline_ml_model._evaluate_window))
        self.assertTrue(callable(plotter.plot_stock_chart))

        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
        import mplfinance

        for dependency in (
            RandomForestClassifier,
            accuracy_score,
            f1_score,
            precision_score,
            recall_score,
            mplfinance.make_addplot,
        ):
            self.assertTrue(callable(dependency))


if __name__ == "__main__":
    unittest.main()
