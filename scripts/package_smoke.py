"""Prove the *installed* tw-stock-tool distribution works outside the checkout.

The repository root ships ``tw_stock_tool/__init__.py``, a compatibility
namespace shim that appends ``src/tw_stock_tool`` to ``__path__``. Any smoke
check executed from the checkout therefore imports the working tree, because
the working directory is on ``sys.path`` -- it proves nothing about the wheel
that was just installed (Issue #84 B9).

This script closes that hole. It relocates to a temporary directory, strips the
repository from the child import path, and asserts that every resolved import
path lies outside the checkout before exercising the console entrypoint, the
module entrypoint, and per-command ``--help`` output.

Usage::

    python scripts/package_smoke.py --repository-root .

Run it *after* ``pip install .`` and from any working directory; it never
imports project code from the source tree.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

DISTRIBUTION_NAME = "tw-stock-tool"
PACKAGE_NAME = "tw_stock_tool"

# Each entry pins one public route to a string only its underlying parser can
# emit. Exit code 0 alone cannot distinguish real help from the option-less
# wrapper stub described in Issue #84 B2, so CI asserts the marker instead.
HELP_MARKERS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("doctor",), "--live"),
    (("run",), "inspect"),
    (("run", "list"), "--workspace"),
    (("run", "inspect"), "--workspace"),
    (("scan",), "--min-volume-ratio"),
    (("daily",), "--validation-strategy"),
    (("daily-report-artifact",), "export-markdown"),
    (("stock-list",), "{update,smoke-check,clean}"),
    (("stock-list", "update"), "--add-suffix"),
    (("stock-list", "smoke-check"), "--min-tpex"),
    (("stock-list", "clean"), "--write-clean-file"),
    (("price-smoke-check",), "--tpex-stock"),
    (("ai-scan",), "--n-estimators"),
    (("ai-report",), "--n-estimators"),
    (("ml-dataset",), "--output-csv"),
    (("gui",), "Takes no arguments"),
    (("cache",), "--summary"),
    (("benchmark",), "--warmup"),
    (("analyze",), "--save-chart"),
    (("strategy-compare",), "--score-sell"),
    (("parameter-sweep",), "--output-excel"),
    (("backtest-report",), "--manifest-path"),
    (("walk-forward",), "--train-days"),
    (("simulated-paper-trading",), "--slippage-per-share"),
    (("simulated-paper-trading-export",), "--output-csv-dir"),
    (("backtest-artifact",), "convert-to-simulated-paper-trading"),
    (("backtest-result-export",), "--output-json"),
    (("simulated-portfolio-artifact",), "export-csv"),
    (("simulated-portfolio-trading",), "--quantity-per-trade"),
)


def _pyproject_version(repository_root: Path) -> str:
    with (repository_root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def _isolated_environment(repository_root: Path) -> dict[str, str]:
    """Child env with the checkout removed from the import path."""
    environment = os.environ.copy()
    entries = environment.get("PYTHONPATH", "").split(os.pathsep)
    kept = [
        entry
        for entry in entries
        if entry and not _is_inside(Path(entry), repository_root)
    ]
    if kept:
        environment["PYTHONPATH"] = os.pathsep.join(kept)
    else:
        environment.pop("PYTHONPATH", None)
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def _is_inside(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root)
    except (OSError, ValueError):
        return False
    return True


def _run(command: list[str], environment: dict[str, str], workdir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=workdir,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def check_import_isolation(repository_root: Path) -> list[str]:
    """The imported package must not resolve to the repository shim."""
    failures: list[str] = []
    module = importlib.import_module(PACKAGE_NAME)

    module_file = getattr(module, "__file__", None)
    if module_file is None:
        failures.append(f"{PACKAGE_NAME}.__file__ is None (namespace package, not an installed distribution)")
    elif _is_inside(Path(module_file), repository_root):
        failures.append(f"{PACKAGE_NAME}.__file__ resolves inside the checkout: {module_file}")

    for entry in list(getattr(module, "__path__", [])):
        if _is_inside(Path(entry), repository_root):
            failures.append(f"{PACKAGE_NAME}.__path__ contains a checkout entry: {entry}")

    cli = importlib.import_module(f"{PACKAGE_NAME}.cli.twstock_cli")
    cli_file = getattr(cli, "__file__", None)
    if cli_file is None or _is_inside(Path(cli_file), repository_root):
        failures.append(f"twstock_cli resolves inside the checkout: {cli_file}")

    if not failures:
        print(f"[OK] import isolation: {module_file}")
    return failures


def check_distribution_version(expected: str) -> list[str]:
    try:
        installed = importlib.metadata.version(DISTRIBUTION_NAME)
    except importlib.metadata.PackageNotFoundError:
        return [f"{DISTRIBUTION_NAME} is not an installed distribution"]
    if installed != expected:
        return [f"installed version {installed!r} != pyproject version {expected!r}"]
    print(f"[OK] distribution version: {installed}")
    return []


def check_entrypoints(environment: dict[str, str], workdir: Path) -> list[str]:
    failures: list[str] = []
    invocations = (
        (["twstock", "--help"], "console entrypoint"),
        ([sys.executable, "-m", f"{PACKAGE_NAME}.cli.twstock_cli", "--help"], "module entrypoint"),
    )
    for command, label in invocations:
        completed = _run(command, environment, workdir)
        if completed.returncode != 0:
            failures.append(f"{label} exited {completed.returncode}: {completed.stderr.strip()}")
        elif "usage:" not in completed.stdout:
            failures.append(f"{label} produced no usage output")
        else:
            print(f"[OK] {label}")
    return failures


def check_command_help(environment: dict[str, str], workdir: Path) -> list[str]:
    failures: list[str] = []
    for tokens, marker in HELP_MARKERS:
        completed = _run(["twstock", *tokens, "--help"], environment, workdir)
        name = " ".join(tokens)
        if completed.returncode != 0:
            failures.append(f"twstock {name} --help exited {completed.returncode}: {completed.stderr.strip()}")
        elif marker not in completed.stdout:
            failures.append(
                f"twstock {name} --help lost its command-specific help (missing {marker!r}); "
                "this is the wrapper-only stub regression from Issue #84 B2"
            )
    if not failures:
        print(f"[OK] command help forwarding: {len(HELP_MARKERS)} routes")
    return failures


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--repository-root",
        default=".",
        help="Path to the repository checkout that must NOT shadow the installed distribution",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repository_root = Path(args.repository_root).resolve()
    expected_version = _pyproject_version(repository_root)
    environment = _isolated_environment(repository_root)

    original_directory = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="tw-stock-tool-smoke-") as temporary:
        workdir = Path(temporary).resolve()
        try:
            os.chdir(workdir)
            print(f"Running installed-package smoke from {workdir} (checkout: {repository_root})")

            failures: list[str] = []
            failures.extend(check_import_isolation(repository_root))
            failures.extend(check_distribution_version(expected_version))
            failures.extend(check_entrypoints(environment, workdir))
            failures.extend(check_command_help(environment, workdir))
        finally:
            # Windows cannot remove a directory that is still the process cwd.
            os.chdir(original_directory)

    if failures:
        print("\nInstalled-package smoke FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("\nInstalled-package smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
