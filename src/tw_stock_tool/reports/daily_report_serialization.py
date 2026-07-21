"""JSON serialization boundary for daily research report artifacts."""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd


REPORT_SECTION_ORDER = (
    "Report Metadata",
    "Run Configuration",
    "Pipeline Run Summary",
    "Report Highlights",
    "Data Quality Notes",
    "Universe Summary",
    "Screening Summary",
    "Watchlist Candidates",
    "Backtest Highlights",
    "Parameter Sweep Highlights",
    "Walk Forward Highlights",
    "Risk Notes",
    "Data Limitations",
    "Next Research Actions",
)

_ARTIFACT_KEYS = (
    "schema_version",
    "result_type",
    "report",
    "metadata",
)
_METADATA_KEYS = (
    "source",
    "semantics",
)
_DICT_SECTIONS = frozenset(
    {
        "Report Metadata",
        "Run Configuration",
        "Pipeline Run Summary",
        "Universe Summary",
    }
)
_STRING_LIST_SECTIONS = frozenset(
    {
        "Report Highlights",
        "Data Quality Notes",
        "Risk Notes",
        "Data Limitations",
        "Next Research Actions",
    }
)
_RECORD_LIST_SECTIONS = frozenset(
    {
        "Screening Summary",
        "Watchlist Candidates",
        "Backtest Highlights",
        "Parameter Sweep Highlights",
        "Walk Forward Highlights",
    }
)


class DailyReportSerializationError(ValueError):
    """Raised when a daily report cannot be represented by schema v1."""


def _fail(path: str, message: str) -> None:
    raise DailyReportSerializationError(f"{path}: {message}")


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "expected a dictionary")
    return value


def _validate_exact_keys(
    value: dict[str, Any],
    expected: tuple[str, ...],
    path: str,
) -> None:
    keys = list(value)
    for key in keys:
        if not isinstance(key, str):
            _fail(path, f"dictionary key {key!r} must be a string")
    expected_set = set(expected)
    actual_set = set(keys)
    missing = [key for key in expected if key not in actual_set]
    unknown = [key for key in keys if key not in expected_set]
    if missing:
        _fail(path, f"missing field(s): {', '.join(missing)}")
    if unknown:
        _fail(path, f"unknown field(s): {', '.join(unknown)}")


def _value_path(path: str, key: str) -> str:
    return f"{path}.{key}"


def _normalize_value(value: Any, path: str) -> Any:
    if value is None or value is pd.NA or value is pd.NaT:
        return None

    if isinstance(value, pd.DataFrame):
        _fail(path, "DataFrame values are not supported")
    if isinstance(value, pd.Series):
        _fail(path, "Series values are not supported")
    if isinstance(value, np.ndarray):
        _fail(path, "ndarray values are not supported")
    if isinstance(value, (set, frozenset)):
        _fail(path, "set values are not supported")
    if callable(value):
        _fail(path, "callable values are not supported")

    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if math.isnan(number):
            return None
        if not math.isfinite(number):
            _fail(path, "infinite floats are not supported")
        return number
    if isinstance(value, np.datetime64):
        if np.isnat(value):
            return None
        return pd.Timestamp(value).isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                _fail(path, f"dictionary key {key!r} must be a string")
            normalized[key] = _normalize_value(item, _value_path(path, key))
        return normalized
    if isinstance(value, (list, tuple)):
        return [
            _normalize_value(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]

    _fail(path, f"unsupported value type: {type(value).__name__}")


def _canonicalize_report(report_data: Any, path: str) -> dict[str, Any]:
    report = _require_dict(report_data, path)
    _validate_exact_keys(report, REPORT_SECTION_ORDER, path)

    canonical: dict[str, Any] = {}
    for section in REPORT_SECTION_ORDER:
        section_path = _value_path(path, section)
        value = _normalize_value(report[section], section_path)

        if section in _DICT_SECTIONS:
            if not isinstance(value, dict):
                _fail(section_path, "expected a dictionary section")
        elif section in _STRING_LIST_SECTIONS:
            if not isinstance(value, list):
                _fail(section_path, "expected a list of strings")
            for index, item in enumerate(value):
                if not isinstance(item, str):
                    _fail(f"{section_path}[{index}]", "expected a string")
        elif section in _RECORD_LIST_SECTIONS:
            if not isinstance(value, list):
                _fail(section_path, "expected a list of dictionaries")
            for index, item in enumerate(value):
                if not isinstance(item, dict):
                    _fail(f"{section_path}[{index}]", "expected a dictionary")

        canonical[section] = value
    return canonical


def serialize_daily_report_data(report_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize report data into the deterministic schema v1 artifact."""
    report = _canonicalize_report(report_data, "$.report")
    return {
        "schema_version": 1,
        "result_type": "daily_research_report",
        "report": report,
        "metadata": {
            "source": "daily_report",
            "semantics": "offline_research_artifact",
        },
    }


def deserialize_daily_report_data(data: dict[str, Any]) -> dict[str, Any]:
    """Validate an artifact and return its canonical report dictionary."""
    artifact = _require_dict(data, "$")
    _validate_exact_keys(artifact, _ARTIFACT_KEYS, "$")

    if type(artifact["schema_version"]) is not int or artifact["schema_version"] != 1:
        _fail("$.schema_version", "must be integer schema version 1")
    if artifact["result_type"] != "daily_research_report":
        _fail("$.result_type", "must be daily_research_report")

    metadata = _require_dict(artifact["metadata"], "$.metadata")
    _validate_exact_keys(metadata, _METADATA_KEYS, "$.metadata")
    if metadata["source"] != "daily_report":
        _fail("$.metadata.source", "must be daily_report")
    if metadata["semantics"] != "offline_research_artifact":
        _fail("$.metadata.semantics", "must be offline_research_artifact")

    return _canonicalize_report(artifact["report"], "$.report")


def export_daily_report_json(report_data: dict[str, Any]) -> str:
    """Serialize report data as deterministic UTF-8 JSON text."""
    artifact = serialize_daily_report_data(report_data)
    return json.dumps(
        artifact,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )


def _reject_json_constant(value: str) -> None:
    raise DailyReportSerializationError(
        f"$: unsupported JSON constant {value}"
    )


def load_daily_report_json(content: str) -> dict[str, Any]:
    """Load schema v1 JSON text and return its canonical report dictionary."""
    if not isinstance(content, str):
        raise DailyReportSerializationError("$.content: expected a JSON string")
    try:
        data = json.loads(content, parse_constant=_reject_json_constant)
    except DailyReportSerializationError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise DailyReportSerializationError(
            f"$: invalid JSON: {exc}"
        ) from exc
    return deserialize_daily_report_data(data)
