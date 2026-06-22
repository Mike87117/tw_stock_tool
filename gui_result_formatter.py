"""Human-readable formatting for GUI task results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

MAX_PREVIEW_ROWS = 20


def format_task_result(task_name: str, result: Any) -> str:
    """Format a completed GUI task result for display in the result pane."""
    if isinstance(result, pd.DataFrame):
        return _format_dataframe(result, task_name)
    if not isinstance(result, dict):
        return _format_value(task_name, result)

    if task_name == "Update Stock List":
        return _format_stock_list_update(result)
    if task_name == "Run Scan":
        return _format_run_scan(result)
    if task_name == "Run Daily Report":
        return _format_daily_report(result)
    if task_name == "Run Single Stock Analysis":
        return _format_single_stock_analysis(result)
    if task_name == "Cache Summary":
        return _format_cache_summary(result)
    if task_name == "Clear Cache":
        return _format_clear_cache(result)
    if task_name in {"Run Doctor", "Run Doctor --live"}:
        return _format_doctor(result)
    if task_name == "Check Stock List Source":
        return _format_stock_list_source(result)
    if task_name == "Check Price Data Source":
        return _format_price_data_source(result)
    return _format_dict(result, task_name)


def _format_stock_list_update(result: dict[str, Any]) -> str:
    lines = ["Stock list update:"]
    lines.append(f"- count: {_stringify(result.get('count', ''))}")
    lines.append(f"- output_path: {_stringify(result.get('output_path', ''))}")
    if isinstance(result.get("stocks"), pd.DataFrame):
        lines.append(_format_dataframe(result["stocks"], "stocks"))
    return "\n".join(lines)


def _format_run_scan(result: dict[str, Any]) -> str:
    if len(result) == 1:
        only_value = next(iter(result.values()))
        if isinstance(only_value, pd.DataFrame):
            return _format_dataframe(only_value, "Run Scan")
    return _format_dict(result, "Run Scan")


def _format_daily_report(result: dict[str, Any]) -> str:
    lines = ["Daily report:"]
    for key in ("summary", "candidates", "ranking"):
        value = result.get(key)
        if isinstance(value, pd.DataFrame):
            lines.append(f"- {key} rows: {len(value)}")
            lines.append(f"- {key} columns: {len(value.columns)}")
        elif value is not None:
            lines.append(_format_value(key, value))
    if "output_path" in result:
        lines.append(f"- output_path: {_stringify(result.get('output_path'))}")
    return "\n".join(lines)


def _format_single_stock_analysis(result: dict[str, Any]) -> str:
    lines = ["Single stock analysis:"]
    for key in ("symbol", "summary", "backtest", "excel_path", "chart_path"):
        if key in result:
            lines.append(_format_value(key, result[key]))
    signal = result.get("signal")
    if isinstance(signal, pd.DataFrame):
        lines.append("- signal:")
        lines.append(f"  rows: {len(signal)}")
        lines.append(f"  columns: {len(signal.columns)}")
    elif signal is not None:
        lines.append(_format_value("signal", signal))
    return "\n".join(lines)


def _format_cache_summary(result: dict[str, Any]) -> str:
    lines = ["Cache summary:"]
    lines.append(f"- count: {_stringify(result.get('count', ''))}")
    lines.append(f"- empty: {_stringify(result.get('empty', ''))}")
    summary = result.get("summary")
    if isinstance(summary, pd.DataFrame):
        lines.append(_format_dataframe(summary, "summary"))
    elif summary is not None:
        lines.append(_format_value("summary", summary))
    return "\n".join(lines)


def _format_clear_cache(result: dict[str, Any]) -> str:
    if "cleared" in result:
        return f"Clear cache:\n- cleared: {_stringify(result['cleared'])}"
    return _format_dict(result, "Clear cache")


def _format_doctor(result: dict[str, Any]) -> str:
    lines = ["Doctor:"]
    if "summary" in result:
        lines.append(_format_value("summary", result["summary"]))
    if "has_failures" in result:
        lines.append(f"has_failures: {_stringify(result['has_failures'])}")
    if "rows" in result:
        lines.append(_format_value("rows", result["rows"]))
    return "\n".join(lines)


def _format_stock_list_source(result: dict[str, Any]) -> str:
    lines = ["Stock list source:"]
    for key in ("twse_count", "tpex_count", "all_count", "missing_expected_stocks", "status"):
        if key in result:
            lines.append(_format_value(key, result[key]))
    return "\n".join(lines)


def _format_price_data_source(result: dict[str, Any]) -> str:
    lines = ["Price data source:"]
    if "failed" in result:
        lines.append(f"failed: {_stringify(result['failed'])}")
    if "results" in result:
        lines.append(_format_value("results", result["results"]))
    return "\n".join(lines)


def _format_dict(data: dict[str, Any], title: str = "Result") -> str:
    lines = [f"{title}:"]
    for key, value in data.items():
        lines.append(_format_value(str(key), value))
    return "\n".join(lines)


def _format_value(label: str, value: Any) -> str:
    if isinstance(value, pd.DataFrame):
        return _format_dataframe(value, label)
    if isinstance(value, dict):
        return _format_dict(value, label)
    if isinstance(value, list):
        return _format_list(value, label)
    return f"{label}: {_stringify(value)}"


def _format_dataframe(df: pd.DataFrame, label: str = "DataFrame") -> str:
    lines = [
        f"{label}:",
        f"- rows: {len(df)}",
        f"- columns: {len(df.columns)}",
    ]
    if df.empty:
        lines.append("- preview: <empty>")
        return "\n".join(lines)

    preview_rows = min(len(df), MAX_PREVIEW_ROWS)
    lines.append(f"- preview (first {preview_rows} rows):")
    lines.append(df.head(MAX_PREVIEW_ROWS).to_string(index=False))
    return "\n".join(lines)


def _format_list(values: list[Any], label: str = "List") -> str:
    lines = [f"{label}:", f"- count: {len(values)}"]
    for index, value in enumerate(values[:MAX_PREVIEW_ROWS], start=1):
        lines.append(f"{index}. {_stringify(value)}")
    remaining = len(values) - MAX_PREVIEW_ROWS
    if remaining > 0:
        lines.append(f"... ({remaining} more)")
    return "\n".join(lines)


def _stringify(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)
