"""Markdown file export boundary for canonical daily report artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tw_stock_tool.reports.daily_report_markdown import render_daily_report_markdown
from tw_stock_tool.utils.output import write_text_report


def export_daily_report_markdown_file(
    report_data: dict[str, Any],
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Render completely before delegating file I/O to the shared writer."""
    markdown = render_daily_report_markdown(report_data)
    return write_text_report(markdown, path, overwrite=overwrite)
