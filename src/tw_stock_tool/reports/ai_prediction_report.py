"""Excel reporting for baseline ML prediction validation.

The report wraps ``baseline_ml_model.run_baseline_ml_model`` and organizes the
result into Summary, Detail, and Errors sheets. It does not train any additional
model beyond the baseline module.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from tw_stock_tool.ml.baseline_ml_model import BASELINE_RESULT_COLUMNS, run_baseline_ml_model
from tw_stock_tool.utils.config import DEFAULT_PERIOD, OUTPUT_DIR

SUMMARY_COLUMNS = [
    "Stock",
    "Period",
    "Horizon",
    "Train Size",
    "Test Size",
    "Step Size",
    "Windows",
    "Avg Accuracy",
    "Avg Precision",
    "Avg Recall",
    "Avg F1",
    "Avg Test Positive Rate %",
    "Avg Predicted Positive Rate %",
    "Error Windows",
]


class AIPredictionReportError(Exception):
    """Raised when an AI prediction report cannot be exported."""


def _ok_rows(detail_df: pd.DataFrame) -> pd.DataFrame:
    if detail_df.empty or "Error" not in detail_df.columns:
        return detail_df.copy()
    return detail_df[detail_df["Error"].astype(str) == ""].copy()


def _error_rows(detail_df: pd.DataFrame) -> pd.DataFrame:
    if detail_df.empty or "Error" not in detail_df.columns:
        return detail_df.iloc[0:0].copy()
    return detail_df[detail_df["Error"].astype(str) != ""].copy()


def _mean_numeric(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    value = pd.to_numeric(df[column], errors="coerce").mean()
    if pd.isna(value):
        return 0.0
    return round(float(value), 4)


def build_summary(
    detail_df: pd.DataFrame,
    stock_id: str,
    period: str,
    horizon: int,
    train_size: int,
    test_size: int,
    step_size: int | None,
) -> pd.DataFrame:
    """Build one-row summary statistics from baseline ML detail results."""
    ok = _ok_rows(detail_df)
    errors = _error_rows(detail_df)
    row = {
        "Stock": stock_id,
        "Period": period,
        "Horizon": horizon,
        "Train Size": train_size,
        "Test Size": test_size,
        "Step Size": test_size if step_size is None else step_size,
        "Windows": int(detail_df["Window"].nunique()) if "Window" in detail_df.columns else 0,
        "Avg Accuracy": _mean_numeric(ok, "Accuracy"),
        "Avg Precision": _mean_numeric(ok, "Precision"),
        "Avg Recall": _mean_numeric(ok, "Recall"),
        "Avg F1": _mean_numeric(ok, "F1"),
        "Avg Test Positive Rate %": _mean_numeric(ok, "Test Positive Rate %"),
        "Avg Predicted Positive Rate %": _mean_numeric(ok, "Predicted Positive Rate %"),
        "Error Windows": len(errors),
    }
    return pd.DataFrame([row], columns=SUMMARY_COLUMNS)


def build_report_frames(
    detail_df: pd.DataFrame,
    stock_id: str,
    period: str,
    horizon: int,
    train_size: int,
    test_size: int,
    step_size: int | None,
) -> dict[str, pd.DataFrame]:
    """Create Summary, Detail, and Errors frames for the report."""
    detail = detail_df.reindex(columns=BASELINE_RESULT_COLUMNS)
    return {
        "Summary": build_summary(
            detail,
            stock_id=stock_id,
            period=period,
            horizon=horizon,
            train_size=train_size,
            test_size=test_size,
            step_size=step_size,
        ),
        "Detail": detail,
        "Errors": _error_rows(detail).reindex(columns=BASELINE_RESULT_COLUMNS),
    }


def run_ai_prediction_report(
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
) -> dict[str, pd.DataFrame]:
    """Run the baseline model and return report frames."""
    detail = run_baseline_ml_model(
        stock_id=stock_id,
        period=period,
        horizon=horizon,
        train_size=train_size,
        test_size=test_size,
        step_size=step_size,
        force_refresh=force_refresh,
        dropna=dropna,
        n_estimators=n_estimators,
        random_state=random_state,
    )
    return build_report_frames(
        detail,
        stock_id=stock_id,
        period=period,
        horizon=horizon,
        train_size=train_size,
        test_size=test_size,
        step_size=step_size,
    )


def export_ai_prediction_report_excel(
    frames: dict[str, pd.DataFrame],
    stock_id: str,
    output: str | None,
) -> Path | None:
    """Export Summary, Detail, and Errors sheets to Excel."""
    if output is None:
        return None
    output_path = OUTPUT_DIR / f"{stock_id}_ai_prediction_report.xlsx" if output == "" else Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            frames["Summary"].to_excel(writer, index=False, sheet_name="Summary")
            frames["Detail"].to_excel(writer, index=False, sheet_name="Detail")
            frames["Errors"].to_excel(writer, index=False, sheet_name="Errors")
    except PermissionError as exc:
        raise AIPredictionReportError(
            f"Failed to write Excel file: {output_path}. Please close the file if it is open."
        ) from exc
    except Exception as exc:
        raise AIPredictionReportError(f"Failed to write Excel file: {output_path}. {exc}") from exc
    return output_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI prediction report for baseline ML model")
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
    parser.add_argument("--output", nargs="?", const="", help="Export Excel; omit path for default output")
    return parser.parse_args(argv)


def main() -> None:
    try:
        args = _parse_args()
        frames = run_ai_prediction_report(
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
        print("Summary")
        print(frames["Summary"].to_string(index=False))
        print("\nDetail")
        print(frames["Detail"].to_string(index=False))
        output_path = export_ai_prediction_report_excel(frames, args.stock, args.output)
        if output_path:
            print(f"\nAI prediction report exported: {output_path}")
        print("\nBaseline ML report is for research only and is not investment advice.")
    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
