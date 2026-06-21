"""Local environment checker for tw_stock_tool.

By default this checks only local Python/runtime prerequisites. Use --live to
also run live external data-source smoke checks.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import Any, Iterable

from config import CACHE_DIR, OUTPUT_DIR
import price_data_smoke_check
import stock_list_smoke_check

PASS = "PASS"
WARNING = "WARNING"
FAIL = "FAIL"

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

REQUIRED_CLI_FILES = [
    "main.py",
    "scan_stocks.py",
    "daily_report.py",
    "stock_list_updater.py",
    "stock_list_smoke_check.py",
    "price_data_smoke_check.py",
    "ai_prediction_report.py",
    "ai_stock_scanner.py",
]


def _row(name: str, status: str, message: str = "") -> dict[str, str]:
    return {"Check": name, "Status": status, "Message": message}


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


def check_required_files(
    files: Iterable[str | Path] | None = None,
    base_dir: str | Path | None = None,
) -> list[dict[str, str]]:
    """Check that required project files exist."""
    root = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent
    rows: list[dict[str, str]] = []
    for file_path in files or REQUIRED_CLI_FILES:
        path = root / file_path
        if path.exists():
            rows.append(_row(f"File {file_path}", PASS, str(path)))
        else:
            rows.append(_row(f"File {file_path}", FAIL, f"Missing: {path}"))
    return rows


def check_requirements_file(base_dir: str | Path | None = None) -> dict[str, str]:
    """Check requirements.txt exists."""
    root = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent
    path = root / "requirements.txt"
    if path.exists():
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
    rows.extend(check_required_files())
    rows.append(check_requirements_file())
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


def main() -> None:
    args = _parse_args()
    rows = run_doctor(live=args.live)
    print_report(rows)
    if has_failures(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
