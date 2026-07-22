"""Offline summary boundary for canonical daily report artifacts."""

from __future__ import annotations

from typing import Any


def build_daily_report_artifact_summary(
    report_data: dict[str, Any],
) -> dict[str, Any]:
    """Return deterministic metadata and section counts without exposing rows."""
    metadata = report_data["Report Metadata"]
    return {
        "Report Date": metadata.get("Date"),
        "Report Type": metadata.get("Type"),
        "Total Stocks": report_data["Universe Summary"].get("Total Stocks", 0),
        "Screening Summary Rows": len(report_data["Screening Summary"]),
        "Watchlist Candidate Rows": len(report_data["Watchlist Candidates"]),
        "Backtest Highlight Rows": len(report_data["Backtest Highlights"]),
        "Parameter Sweep Highlight Rows": len(report_data["Parameter Sweep Highlights"]),
        "Walk Forward Highlight Rows": len(report_data["Walk Forward Highlights"]),
        "Risk Note Count": len(report_data["Risk Notes"]),
        "Data Limitation Count": len(report_data["Data Limitations"]),
        "Next Research Action Count": len(report_data["Next Research Actions"]),
    }
