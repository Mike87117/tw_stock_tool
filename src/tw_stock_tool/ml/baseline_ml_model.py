"""Baseline Random Forest model for ML walk-forward validation.

This module trains a simple baseline classifier on time-ordered windows. It is
intended as a first benchmark only; it does not use XGBoost, LightGBM, or any
complex model stack.
"""

from __future__ import annotations

import argparse
from typing import Any

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from tw_stock_tool.ml.ai_walk_forward import ml_feature_columns, split_time_windows
from tw_stock_tool.utils.config import DEFAULT_PERIOD
from tw_stock_tool.ml.ml_dataset import build_ml_dataset

BASELINE_RESULT_COLUMNS = [
    "Window",
    "Train Start",
    "Train End",
    "Test Start",
    "Test End",
    "Train Rows",
    "Test Rows",
    "Feature Count",
    "Target Column",
    "Accuracy",
    "Precision",
    "Recall",
    "F1",
    "Train Positive Rate %",
    "Test Positive Rate %",
    "Predicted Positive Rate %",
    "Error",
]


def _validate_positive_int(name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0.")


def _target_column(horizon: int) -> str:
    _validate_positive_int("horizon", horizon)
    return f"Target_Up_{horizon}D"


def _positive_rate(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    return round(float(values.astype(bool).mean() * 100), 2)


def _error_row(
    window_number: int,
    train: pd.DataFrame,
    test: pd.DataFrame,
    feature_count: int,
    target_column: str,
    error: Exception,
) -> dict[str, Any]:
    return {
        "Window": window_number,
        "Train Start": train.index[0] if not train.empty else None,
        "Train End": train.index[-1] if not train.empty else None,
        "Test Start": test.index[0] if not test.empty else None,
        "Test End": test.index[-1] if not test.empty else None,
        "Train Rows": len(train),
        "Test Rows": len(test),
        "Feature Count": feature_count,
        "Target Column": target_column,
        "Accuracy": None,
        "Precision": None,
        "Recall": None,
        "F1": None,
        "Train Positive Rate %": None,
        "Test Positive Rate %": None,
        "Predicted Positive Rate %": None,
        "Error": str(error),
    }


def _evaluate_window(
    window_number: int,
    train: pd.DataFrame,
    test: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
    n_estimators: int,
    random_state: int,
) -> dict[str, Any]:
    if train.index[-1] >= test.index[0]:
        raise ValueError("train data must end before test data starts.")

    x_train = train[feature_columns]
    y_train = train[target_column].astype(bool)
    x_test = test[feature_columns]
    y_test = test[target_column].astype(bool)

    model = RandomForestClassifier(
        n_estimators=n_estimators,
        random_state=random_state,
    )
    model.fit(x_train, y_train)
    predictions = pd.Series(model.predict(x_test), index=test.index).astype(bool)

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
        "Accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "Precision": round(float(precision_score(y_test, predictions, zero_division=0)), 4),
        "Recall": round(float(recall_score(y_test, predictions, zero_division=0)), 4),
        "F1": round(float(f1_score(y_test, predictions, zero_division=0)), 4),
        "Train Positive Rate %": _positive_rate(y_train),
        "Test Positive Rate %": _positive_rate(y_test),
        "Predicted Positive Rate %": _positive_rate(predictions),
        "Error": "",
    }


def run_baseline_ml_model(
    stock_id: str,
    period: str = DEFAULT_PERIOD,
    horizon: int = 5,
    train_size: int = 252,
    test_size: int = 63,
    step_size: int | None = None,
    force_refresh: bool = False,
    dropna: bool = True,
    n_estimators: int = 100,
    random_state: int = 42,
) -> pd.DataFrame:
    """Train a RandomForest baseline over chronological walk-forward windows."""
    if not stock_id.strip():
        raise ValueError("stock cannot be blank.")
    _validate_positive_int("n_estimators", n_estimators)
    target_column = _target_column(horizon)
    dataset = build_ml_dataset(
        stock_id=stock_id.strip(),
        period=period,
        horizon=horizon,
        force_refresh=force_refresh,
        dropna=dropna,
    )
    if target_column not in dataset.columns:
        raise ValueError(f"dataset must contain target column: {target_column}.")
    feature_columns = ml_feature_columns(dataset)
    if not feature_columns:
        raise ValueError("dataset does not contain any supported feature columns.")

    rows: list[dict[str, Any]] = []
    for window_number, train, test in split_time_windows(
        dataset,
        train_size=train_size,
        test_size=test_size,
        step_size=step_size,
    ):
        try:
            rows.append(
                _evaluate_window(
                    window_number=window_number,
                    train=train,
                    test=test,
                    feature_columns=feature_columns,
                    target_column=target_column,
                    n_estimators=n_estimators,
                    random_state=random_state,
                )
            )
        except Exception as exc:
            rows.append(
                _error_row(
                    window_number=window_number,
                    train=train,
                    test=test,
                    feature_count=len(feature_columns),
                    target_column=target_column,
                    error=exc,
                )
            )
    return pd.DataFrame(rows, columns=BASELINE_RESULT_COLUMNS)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Baseline RandomForest ML model")
    parser.add_argument("--stock", required=True, help="Stock id, for example 2330")
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--train-size", type=int, default=252)
    parser.add_argument("--test-size", type=int, default=63)
    parser.add_argument("--step-size", type=int)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument(
        "--dropna",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Drop rows with missing values when building the ML dataset",
    )
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args(argv)


def main() -> None:
    try:
        args = _parse_args()
        result = run_baseline_ml_model(
            stock_id=args.stock,
            period=args.period,
            horizon=args.horizon,
            train_size=args.train_size,
            test_size=args.test_size,
            step_size=args.step_size,
            force_refresh=args.force_refresh,
            dropna=args.dropna,
            n_estimators=args.n_estimators,
            random_state=args.random_state,
        )
        print(result.to_string(index=False))
        print("\nBaseline model is for research only and is not investment advice.")
    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
