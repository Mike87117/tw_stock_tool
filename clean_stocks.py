"""Validate and clean Taiwan stock id lists."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from config import DEFAULT_AUTO_ADJUST, DEFAULT_INTERVAL, DEFAULT_PERIOD, OUTPUT_DIR
from data_loader import download_tw_stock

RESULT_COLUMNS = [
    "Row",
    "Stock",
    "Normalized Stock",
    "Symbol",
    "Status",
    "Error",
    "Start Date",
    "End Date",
    "Rows",
    "Source Note",
]
DUPLICATE_COLUMNS = ["Row", "Stock", "Normalized Stock", "First Row"]
SUMMARY_COLUMNS = [
    "File",
    "Total Input Lines",
    "Unique Stocks",
    "Valid Stocks",
    "Invalid Stocks",
    "Duplicate Rows",
    "Output Clean File",
]


@dataclass(frozen=True)
class StockEntry:
    """A non-empty, non-comment stock id entry from a text file."""

    row: int
    stock: str
    normalized_stock: str


@dataclass(frozen=True)
class DuplicateEntry:
    """A duplicate stock id row that should not be checked again."""

    row: int
    stock: str
    normalized_stock: str
    first_row: int


def normalize_stock_id(stock: str) -> str:
    """Normalize a stock id for de-duplication and output."""
    return stock.strip().upper()


def read_stock_file(file_path: str | Path) -> tuple[list[StockEntry], list[DuplicateEntry], int]:
    """Read stock ids, ignoring blank/comment lines and preserving duplicates."""
    path = Path(file_path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise ValueError(f"Stock file not found: {path}") from exc
    except OSError as exc:
        raise ValueError(f"Failed to read stock file: {path}. {exc}") from exc

    entries: list[StockEntry] = []
    duplicates: list[DuplicateEntry] = []
    first_rows: dict[str, int] = {}
    for row_number, line in enumerate(lines, start=1):
        stock = line.strip()
        if not stock or stock.startswith("#"):
            continue
        normalized = normalize_stock_id(stock)
        if normalized in first_rows:
            duplicates.append(
                DuplicateEntry(
                    row=row_number,
                    stock=stock,
                    normalized_stock=normalized,
                    first_row=first_rows[normalized],
                )
            )
            continue
        first_rows[normalized] = row_number
        entries.append(StockEntry(row=row_number, stock=stock, normalized_stock=normalized))

    if not entries:
        raise ValueError("No stock ids to check. Blank lines and comments are ignored.")
    return entries, duplicates, len(lines)


def _success_row(entry: StockEntry, df: pd.DataFrame, symbol: str) -> dict[str, object]:
    index = pd.to_datetime(df.index)
    return {
        "Row": entry.row,
        "Stock": entry.stock,
        "Normalized Stock": entry.normalized_stock,
        "Symbol": symbol,
        "Status": "OK",
        "Error": "",
        "Start Date": index.min().strftime("%Y-%m-%d") if len(index) else "",
        "End Date": index.max().strftime("%Y-%m-%d") if len(index) else "",
        "Rows": int(len(df)),
        "Source Note": f"Resolved symbol: {symbol}",
    }


def _error_row(entry: StockEntry, exc: Exception) -> dict[str, object]:
    return {
        "Row": entry.row,
        "Stock": entry.stock,
        "Normalized Stock": entry.normalized_stock,
        "Symbol": "",
        "Status": "ERROR",
        "Error": str(exc),
        "Start Date": "",
        "End Date": "",
        "Rows": 0,
        "Source Note": "",
    }


def check_stock_entries(
    entries: Iterable[StockEntry],
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    auto_adjust: bool = DEFAULT_AUTO_ADJUST,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Check each unique stock id with the existing data loader."""
    rows: list[dict[str, object]] = []
    for entry in entries:
        try:
            df, symbol = download_tw_stock(
                entry.normalized_stock,
                period=period,
                interval=interval,
                auto_adjust=auto_adjust,
                force_refresh=force_refresh,
            )
            rows.append(_success_row(entry, df, symbol))
        except Exception as exc:
            rows.append(_error_row(entry, exc))
    return pd.DataFrame(rows, columns=RESULT_COLUMNS)


def duplicates_to_frame(duplicates: Iterable[DuplicateEntry]) -> pd.DataFrame:
    """Convert duplicate entries to a DataFrame."""
    rows = [
        {
            "Row": item.row,
            "Stock": item.stock,
            "Normalized Stock": item.normalized_stock,
            "First Row": item.first_row,
        }
        for item in duplicates
    ]
    return pd.DataFrame(rows, columns=DUPLICATE_COLUMNS)


def build_summary(
    file_path: str | Path,
    total_input_lines: int,
    result_df: pd.DataFrame,
    duplicates_df: pd.DataFrame,
    clean_file_path: str | Path | None = None,
) -> pd.DataFrame:
    """Build the summary sheet for a clean stocks report."""
    valid_count = int((result_df["Status"] == "OK").sum()) if not result_df.empty else 0
    invalid_count = int((result_df["Status"] == "ERROR").sum()) if not result_df.empty else 0
    summary = {
        "File": str(file_path),
        "Total Input Lines": int(total_input_lines),
        "Unique Stocks": int(len(result_df)),
        "Valid Stocks": valid_count,
        "Invalid Stocks": invalid_count,
        "Duplicate Rows": int(len(duplicates_df)),
        "Output Clean File": str(clean_file_path or ""),
    }
    return pd.DataFrame([summary], columns=SUMMARY_COLUMNS)


def export_clean_report(
    summary_df: pd.DataFrame,
    result_df: pd.DataFrame,
    duplicates_df: pd.DataFrame,
    output: str | Path | None,
) -> Path | None:
    """Export the clean stocks report to Excel when requested."""
    if output is None:
        return None

    output_path = OUTPUT_DIR / "clean_stocks_report.xlsx" if str(output) == "" else Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    valid_df = result_df[result_df["Status"] == "OK"].copy()
    invalid_df = result_df[result_df["Status"] == "ERROR"].copy()
    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            summary_df.to_excel(writer, index=False, sheet_name="Summary")
            valid_df.to_excel(writer, index=False, sheet_name="Valid")
            invalid_df.to_excel(writer, index=False, sheet_name="Invalid")
            duplicates_df.to_excel(writer, index=False, sheet_name="Duplicates")
            result_df.to_excel(writer, index=False, sheet_name="All")
    except PermissionError as exc:
        raise ValueError(
            f"Failed to write Excel file: {output_path}. "
            "Please close the Excel file if it is open."
        ) from exc
    except Exception as exc:
        raise ValueError(f"Failed to write Excel file: {output_path}. {exc}") from exc
    return output_path


def write_clean_file(result_df: pd.DataFrame, output: str | Path | None) -> Path | None:
    """Write valid normalized stock ids to a clean txt file."""
    if output is None:
        return None

    output_path = OUTPUT_DIR / "stocks_clean.txt" if str(output) == "" else Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    valid = result_df[result_df["Status"] == "OK"]
    lines = [str(value) for value in valid["Normalized Stock"].tolist()]
    try:
        output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Failed to write clean stock file: {output_path}. {exc}") from exc
    return output_path


def run_clean_stocks(
    file_path: str | Path,
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    auto_adjust: bool = DEFAULT_AUTO_ADJUST,
    force_refresh: bool = False,
    output: str | Path | None = None,
    clean_file: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Path | None, Path | None]:
    """Run stock list validation and optional exports."""
    entries, duplicates, total_lines = read_stock_file(file_path)
    result_df = check_stock_entries(
        entries,
        period=period,
        interval=interval,
        auto_adjust=auto_adjust,
        force_refresh=force_refresh,
    )
    duplicates_df = duplicates_to_frame(duplicates)
    clean_path = write_clean_file(result_df, clean_file)
    summary_df = build_summary(file_path, total_lines, result_df, duplicates_df, clean_path)
    report_path = export_clean_report(summary_df, result_df, duplicates_df, output)
    return summary_df, result_df, duplicates_df, report_path, clean_path


def print_summary(
    summary_df: pd.DataFrame,
    result_df: pd.DataFrame,
    report_path: Path | None,
    clean_path: Path | None,
) -> None:
    """Print a compact terminal summary."""
    summary = summary_df.iloc[0]
    invalid_df = result_df[result_df["Status"] == "ERROR"]
    print("\n=================================")
    print("Clean Stocks")
    print("=================================")
    print(f"File: {summary['File']}")
    print(f"Total input lines: {summary['Total Input Lines']}")
    print(f"Unique stocks: {summary['Unique Stocks']}")
    print(f"Valid stocks: {summary['Valid Stocks']}")
    print(f"Invalid stocks: {summary['Invalid Stocks']}")
    print(f"Duplicate rows: {summary['Duplicate Rows']}")
    if invalid_df.empty:
        print("\nInvalid: none")
    else:
        print("\nInvalid:")
        for _, row in invalid_df.iterrows():
            print(f"- {row['Normalized Stock']}: {row['Error']}")
    if report_path:
        print(f"\nExcel:\n{report_path}")
    if clean_path:
        print(f"\nClean file:\n{clean_path}")
    print("=================================")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and clean a Taiwan stock list")
    parser.add_argument("--file", required=True, help="Stock list txt file")
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--interval", default=DEFAULT_INTERVAL)
    parser.add_argument(
        "--auto-adjust",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_AUTO_ADJUST,
        help="Use yfinance adjusted prices",
    )
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument(
        "--output",
        nargs="?",
        const="",
        help="Export Excel report; omit path for default output",
    )
    parser.add_argument(
        "--write-clean-file",
        nargs="?",
        const="",
        help="Write valid stock ids to txt; omit path for default output",
    )
    return parser.parse_args(argv)


def main() -> None:
    try:
        args = _parse_args()
        summary_df, result_df, _, report_path, clean_path = run_clean_stocks(
            file_path=args.file,
            period=args.period,
            interval=args.interval,
            auto_adjust=args.auto_adjust,
            force_refresh=args.force_refresh,
            output=args.output,
            clean_file=args.write_clean_file,
        )
        print_summary(summary_df, result_df, report_path, clean_path)
    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
