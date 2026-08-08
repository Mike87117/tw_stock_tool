"""Local environment checker for tw_stock_tool.

This is an end-user environment checker first: it must produce a correct
verdict for an installed distribution that has no source checkout at all.
Source-checkout-only checks are therefore added only when a checkout is
actually detected, never assumed.

By default this checks only local Python/runtime prerequisites. Use --live to
also run live external data-source smoke checks.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import sys
import tomllib
from pathlib import Path
from typing import Iterable

from tw_stock_tool.utils.config import CACHE_DIR, OUTPUT_DIR
from tw_stock_tool.cli import price_data_smoke_check
from tw_stock_tool.cli import stock_list_smoke_check

PASS = "PASS"
WARNING = "WARNING"
FAIL = "FAIL"

DISTRIBUTION_NAME = "tw-stock-tool"

REQUIRED_IMPORTS = {
    "yfinance": "yfinance",
    "pandas": "pandas",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "mplfinance": "mplfinance",
    "openpyxl": "openpyxl",
    "requests": "requests",
    "sklearn": "sklearn",
}


def _row(name: str, status: str, message: str = "") -> dict[str, str]:
    return {"Check": name, "Status": status, "Message": message}


def find_repository_root(start: str | Path | None = None) -> Path | None:
    """Return the source-checkout root for this module, or None when installed.

    A checkout is identified by the two markers that define this project's
    src-layout: a top-level ``pyproject.toml`` next to ``src/tw_stock_tool``.
    An installed distribution matches neither, so callers can distinguish the
    two contexts instead of guessing a parent index.
    """
    base = Path(start) if start is not None else Path(__file__)
    base = base.resolve()
    for candidate in base.parents:
        if (candidate / "pyproject.toml").is_file() and (candidate / "src" / "tw_stock_tool").is_dir():
            return candidate
    return None


def _pyproject_version(repository_root: Path) -> str | None:
    try:
        with (repository_root / "pyproject.toml").open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    version = data.get("project", {}).get("version")
    return version if isinstance(version, str) and version.strip() else None


def check_python_version(version_info: tuple[int, int, int] | None = None) -> dict[str, str]:
    """Check the current Python version and warn when it is below 3.11."""
    version = version_info or (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    version_text = ".".join(str(part) for part in version[:3])
    if version < (3, 11, 0):
        return _row("Python version", WARNING, f"Python {version_text}; recommended >= 3.11")
    return _row("Python version", PASS, f"Python {version_text}")


def check_imports(required_imports: dict[str, str] | None = None) -> list[dict[str, str]]:
    """Check that required Python packages can be imported."""
    packages = required_imports or REQUIRED_IMPORTS
    rows: list[dict[str, str]] = []
    for display_name, module_name in packages.items():
        try:
            importlib.import_module(module_name)
            rows.append(_row(f"Import {display_name}", PASS, module_name))
        except Exception as exc:
            rows.append(_row(f"Import {display_name}", FAIL, str(exc)))
    return rows


def check_directory_writable(path: str | Path) -> dict[str, str]:
    """Ensure a directory exists and can write/delete a temporary file."""
    directory = Path(path)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".doctor_write_test.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return _row(f"Writable directory {directory}", PASS, str(directory))
    except Exception as exc:
        return _row(f"Writable directory {directory}", FAIL, str(exc))


def check_directories(paths: Iterable[str | Path] | None = None) -> list[dict[str, str]]:
    """Check required writable directories."""
    return [check_directory_writable(path) for path in (paths or [CACHE_DIR, OUTPUT_DIR])]


def check_package_version() -> dict[str, str]:
    """Check that this tool's own version resolves in the current context.

    Replaces the removed root-wrapper file inventory: the wrappers it listed
    were retired in full (see docs/archive/root-wrapper-removal.md), so the
    meaningful question is no longer "are the root scripts present" but "is
    tw-stock-tool itself resolvable here".
    """
    try:
        installed = importlib.metadata.version(DISTRIBUTION_NAME)
    except importlib.metadata.PackageNotFoundError:
        installed = None
    if installed is not None:
        return _row("Package version", PASS, f"{DISTRIBUTION_NAME} {installed} (installed distribution)")

    repository_root = find_repository_root()
    if repository_root is None:
        return _row(
            "Package version",
            FAIL,
            f"{DISTRIBUTION_NAME} is not installed and no source checkout was found",
        )
    declared = _pyproject_version(repository_root)
    if declared is None:
        return _row(
            "Package version",
            FAIL,
            f"Cannot read project version from {repository_root / 'pyproject.toml'}",
        )
    return _row("Package version", PASS, f"{DISTRIBUTION_NAME} {declared} (source checkout: {repository_root})")


def check_repository_requirements(repository_root: str | Path) -> dict[str, str]:
    """Check requirements.txt in a source checkout.

    Only meaningful for a checkout; ``requirements.txt`` is a development file
    and is not shipped in the wheel, so run_doctor() calls this only when
    find_repository_root() actually locates a checkout.
    """
    path = Path(repository_root) / "requirements.txt"
    if path.is_file():
        return _row("requirements.txt", PASS, str(path))
    return _row("requirements.txt", FAIL, f"Missing: {path}")


def check_live_sources() -> list[dict[str, str]]:
    """Run optional live API smoke checks."""
    rows: list[dict[str, str]] = []
    try:
        stock_list_smoke_check.run_smoke_check()
        rows.append(_row("Live stock list smoke check", PASS, "TWSE / TPEx stock list sources OK"))
    except Exception as exc:
        rows.append(_row("Live stock list smoke check", FAIL, str(exc)))

    try:
        price_data_smoke_check.run_smoke_check()
        rows.append(_row("Live price data smoke check", PASS, "Price data sources OK"))
    except Exception as exc:
        rows.append(_row("Live price data smoke check", FAIL, str(exc)))
    return rows


def run_doctor(live: bool = False) -> list[dict[str, str]]:
    """Run local environment checks, optionally including live API checks."""
    rows = [check_python_version()]
    rows.extend(check_imports())
    rows.extend(check_directories())
    rows.append(check_package_version())
    repository_root = find_repository_root()
    if repository_root is not None:
        rows.append(check_repository_requirements(repository_root))
    if live:
        rows.extend(check_live_sources())
    return rows


def summarize(rows: list[dict[str, str]]) -> dict[str, int]:
    """Count PASS / WARNING / FAIL rows."""
    return {
        PASS: sum(row["Status"] == PASS for row in rows),
        WARNING: sum(row["Status"] == WARNING for row in rows),
        FAIL: sum(row["Status"] == FAIL for row in rows),
    }


def has_failures(rows: list[dict[str, str]]) -> bool:
    """Return True when any check failed."""
    return any(row["Status"] == FAIL for row in rows)


def print_report(rows: list[dict[str, str]]) -> None:
    """Print a human-readable doctor report."""
    print("=================================")
    print("tw_stock_tool Doctor")
    print("=================================")
    for row in rows:
        message = f" - {row['Message']}" if row["Message"] else ""
        print(f"[{row['Status']}] {row['Check']}{message}")
    summary = summarize(rows)
    print("=================================")
    print(
        f"Summary: PASS={summary[PASS]}, "
        f"WARNING={summary[WARNING]}, FAIL={summary[FAIL]}"
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local tw_stock_tool environment")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also run live external data-source smoke checks",
    )
    return parser.parse_args(argv)


def main() -> int | None:
    args = _parse_args()
    rows = run_doctor(live=args.live)
    print_report(rows)
    if has_failures(rows):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
