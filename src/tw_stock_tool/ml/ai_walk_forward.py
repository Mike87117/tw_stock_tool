"""Time-ordered walk-forward validation skeleton for ML datasets.

This module prepares train/test windows for future AI/ML experiments. It does
not train any model and never shuffles rows, so test data always occurs after
train data.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from tw_stock_tool.utils.config import DEFAULT_PERIOD
from tw_stock_tool.ml.ml_dataset import FEATURE_COLUMNS, build_ml_dataset

AI_WALK_FORWARD_COLUMNS = [
    "Window",
    "Train Start",
    "Train End",
    "Test Start",
    "Test End",
    "Train Rows",
    "Test Rows",
    "Feature Count",
    "Target Column",
    "Train Positive Rate %",
    "Test Positive Rate %",
    "Error",
]


def _validate_positive_int(name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0.")


def _target_column(horizon: int) -> str:
    _validate_positive_int("horizon", horizon)
    return f"Target_Up_{horizon}D"


def ml_feature_columns(dataset: pd.DataFrame) -> list[str]:
    """Return ML feature columns, excluding future-return and target columns."""
    return [
        column
        for column in FEATURE_COLUMNS
        if column in dataset.columns
        and not column.startswith("Future_Return_")
        and not column.startswith("Target_Up_")
    ]


def split_time_windows(
    dataset: pd.DataFrame,
    train_size: int,
    test_size: int,
    step_size: int | None = None,
    *,
    purge_size: int = 0,
) -> list[tuple[int, pd.DataFrame, pd.DataFrame]]:
    """Split a dataset into chronological train/test windows without shuffle."""
    _validate_positive_int("train_size", train_size)
    _validate_positive_int("test_size", test_size)
    actual_step_size = test_size if step_size is None else step_size
    _validate_positive_int("step_size", actual_step_size)
    if purge_size < 0:
        raise ValueError("purge_size must be greater than or equal to 0.")

    ordered = dataset.sort_index().copy()
    required_rows = train_size + purge_size + test_size
    windows: list[tuple[int, pd.DataFrame, pd.DataFrame]] = []
    start = 0
    window_number = 1
    while start + required_rows <= len(ordered):
        train_end = start + train_size
        test_start = train_end + purge_size
        test_end = test_start + test_size
        train = ordered.iloc[start:train_end].copy()
        test = ordered.iloc[test_start:test_end].copy()
        windows.append((window_number, train, test))
        start += actual_step_size
        window_number += 1

    if not windows:
        raise ValueError(
            "Not enough rows to build AI walk-forward windows: "
            f"need at least {required_rows}, got {len(ordered)}."
        )
    return windows


def _positive_rate(frame: pd.DataFrame, target_column: str) -> float:
    if frame.empty:
        return 0.0
    return round(float(frame[target_column].mean() * 100), 2)


def _window_row(
    window_number: int,
    train: pd.DataFrame,
    test: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
) -> dict[str, Any]:
    if train.index[-1] >= test.index[0]:
        raise ValueError("train data must end before test data starts.")
    return {
        "Window": window_number,
        "Train Start": train.index[0],
        "Train End": train.index[-1],
        "Test Start": test.index[0],
        "Test End": test.index[-1],
        "Train Rows": len(train),
        "Test Rows": len(test),
        "Feature Count": len(feature_columns),
        "Target Column": target_column,
        "Train Positive Rate %": _positive_rate(train, target_column),
        "Test Positive Rate %": _positive_rate(test, target_column),
        "Error": "",
    }


def run_ai_walk_forward(
    stock_id: str,
    period: str = DEFAULT_PERIOD,
    horizon: int = 5,
    train_size: int = 252,
    test_size: int = 63,
    step_size: int | None = None,
    force_refresh: bool = False,
    dropna: bool = True,
) -> pd.DataFrame:
    """Build a time-ordered ML validation skeleton for one stock."""
    if not stock_id.strip():
        raise ValueError("stock cannot be blank.")
    target = _target_column(horizon)
    dataset = build_ml_dataset(
        stock_id=stock_id.strip(),
        period=period,
        horizon=horizon,
        force_refresh=force_refresh,
        dropna=dropna,
    )
    if target not in dataset.columns:
        raise ValueError(f"dataset must contain target column: {target}.")
    features = ml_feature_columns(dataset)
    if not features:
        raise ValueError("dataset does not contain any supported feature columns.")

    rows = []
    for window_number, train, test in split_time_windows(
        dataset,
        train_size=train_size,
        test_size=test_size,
        step_size=step_size,
        purge_size=horizon,
    ):
        rows.append(_window_row(window_number, train, test, features, target))
    return pd.DataFrame(rows, columns=AI_WALK_FORWARD_COLUMNS)
