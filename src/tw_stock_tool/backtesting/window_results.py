"""Shared success and failure handling for evaluation results."""

import pandas as pd


def valid_window_rows(detail: pd.DataFrame) -> pd.DataFrame:
    """Keep successful evaluations, accepting legacy frames without Error."""
    if "Error" not in detail.columns:
        return detail.copy()
    return detail.loc[detail["Error"].eq("").fillna(False)].copy()


def window_outcome(
    detail: pd.DataFrame,
    *,
    empty_message: str = "No walk-forward windows were evaluated.",
) -> dict[str, object]:
    """Describe failed evaluations without converting missing metrics to zero."""
    valid_count = len(valid_window_rows(detail))
    error_count = len(detail) - valid_count
    status = "ERROR" if not valid_count else "PARTIAL" if error_count else "OK"
    error = ""
    if detail.empty:
        error = empty_message
    elif error_count:
        messages = detail.loc[~detail["Error"].eq("").fillna(False), "Error"].astype(str)
        error = "; ".join(dict.fromkeys(messages))
    return {"Status": status, "Valid Rows": valid_count, "Error Rows": error_count, "Error": error}
