"""File-system helpers for daily research report JSON artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tw_stock_tool.reports.daily_report_serialization import (
    export_daily_report_json,
    load_daily_report_json,
)
from tw_stock_tool.utils.output import write_text_report


def export_daily_report_json_file(
    report_data: dict[str, Any],
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Serialize report data before writing it to a UTF-8 JSON file."""
    content = export_daily_report_json(report_data)
    return write_text_report(content, path, overwrite=overwrite)


def load_daily_report_json_file(
    path: str | Path,
) -> dict[str, Any]:
    """Read a UTF-8 JSON artifact and return its canonical report data."""
    file_path = Path(path)
    if file_path.is_dir():
        raise IsADirectoryError(f"Is a directory: {file_path}")
    content = file_path.read_text(encoding="utf-8")
    return load_daily_report_json(content)
