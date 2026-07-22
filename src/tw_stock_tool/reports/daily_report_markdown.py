"""Lightweight Markdown renderer for canonical daily research reports."""

from __future__ import annotations

from typing import Any


DAILY_REPORT_SECTION_ORDER = [
    ("Report Metadata", "Report Metadata", "dict"),
    ("Run Configuration", "Run Configuration", "dict"),
    ("Pipeline Run Summary", "Pipeline Run Summary", "dict"),
    ("Report Highlights", "Report Highlights", "list"),
    ("Data Quality Notes", "Data Quality Notes", "list"),
    ("Universe Summary", "Universe Summary", "dict"),
    ("Screening Summary", "Screening Summary", "table"),
    ("Watchlist Candidates for Further Review", "Watchlist Candidates", "table"),
    ("Backtest Highlights", "Backtest Highlights", "table"),
    ("Parameter Sweep Highlights", "Parameter Sweep Highlights", "table"),
    ("Walk Forward Highlights", "Walk Forward Highlights", "table"),
    ("Risk Notes", "Risk Notes", "list_risk_notes"),
    ("Data Limitations", "Data Limitations", "list"),
    ("Next Research Actions", "Next Research Actions", "list"),
]


def _format_markdown_table_cell(value: Any) -> str:
    """Format one value without mutating it or applying unrelated HTML escaping."""
    if value is None:
        return ""
    return (
        str(value)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "<br>")
        .replace("|", r"\|")
    )


def render_daily_report_markdown(report_data: dict[str, Any]) -> str:
    """Render canonical daily report data in deterministic section order."""
    lines = ["# Daily Research Report\n"]

    def render_dict(data: dict[str, Any]) -> list[str]:
        if not data:
            return ["No data provided.\n"]
        output = []
        for key, value in data.items():
            if isinstance(value, list) and not value:
                output.append(f"- **{key}**: None")
            elif isinstance(value, list):
                output.append(f"- **{key}**: {', '.join(str(item) for item in value)}")
            else:
                output.append(f"- **{key}**: {value}")
        output.append("")
        return output

    def render_list(items: list[str]) -> list[str]:
        if not items:
            return ["No data provided.\n"]
        return [*(f"- {item}" for item in items), ""]

    def render_table(records: list[dict[str, Any]]) -> list[str]:
        if not records:
            return ["No data provided.\n"]
        headers = []
        for record in records:
            for key in record:
                if key not in headers:
                    headers.append(key)
        formatted_headers = [_format_markdown_table_cell(header) for header in headers]
        output = [
            "| " + " | ".join(formatted_headers) + " |",
            "|" + "|".join(["---"] * len(headers)) + "|",
        ]
        for record in records:
            values = [_format_markdown_table_cell(record.get(header, "")) for header in headers]
            output.append("| " + " | ".join(values) + " |")
        output.append("")
        return output

    for heading, data_key, renderer_type in DAILY_REPORT_SECTION_ORDER:
        lines.append(f"## {heading}\n")
        if renderer_type == "dict":
            lines.extend(render_dict(report_data.get(data_key, {})))
        elif renderer_type == "list":
            lines.extend(render_list(report_data.get(data_key, [])))
        elif renderer_type == "table":
            lines.extend(render_table(report_data.get(data_key, [])))
        elif renderer_type == "list_risk_notes":
            risk_notes = report_data.get(data_key, [])
            disclaimer = "This report is for research purposes only and does not constitute investment advice."
            if disclaimer not in risk_notes:
                risk_notes = risk_notes.copy()
                risk_notes.append(disclaimer)
            lines.extend(render_list(risk_notes))

    return "\n".join(lines)
