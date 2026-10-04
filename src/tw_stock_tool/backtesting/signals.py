from numbers import Real

import numpy as np
import pandas as pd
import warnings


def _normalize_signal_column(values: pd.Series) -> pd.Series:
    """Parse supported boolean representations without string truthiness."""
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool)

    tokens = {"true": True, "false": False, "1": True, "0": False}
    parsed = []
    for value in values:
        if pd.api.types.is_scalar(value) and pd.isna(value):
            parsed.append(False)
        elif isinstance(value, (bool, np.bool_)):
            parsed.append(bool(value))
        elif isinstance(value, str) and value.strip().lower() in tokens:
            parsed.append(tokens[value.strip().lower()])
        elif isinstance(value, Real) and value in (0, 1):
            parsed.append(bool(value))
        else:
            raise ValueError(
                f"'{values.name}' must contain booleans, 0/1, true/false strings, or missing values; got {value!r}."
            )
    return pd.Series(parsed, index=values.index, name=values.name, dtype=bool)


def has_standard_signals(df: pd.DataFrame) -> bool:
    """Check if standard signal columns exist."""
    return "entry_signal" in df.columns and "exit_signal" in df.columns

def has_legacy_signal(df: pd.DataFrame) -> bool:
    """Check if legacy Signal column exists."""
    return "Signal" in df.columns

def legacy_signal_to_standard(df: pd.DataFrame) -> pd.DataFrame:
    """Convert legacy Signal column to standard boolean signals."""
    if has_standard_signals(df):
        out = df.copy()
        out["entry_signal"] = _normalize_signal_column(out["entry_signal"])
        out["exit_signal"] = _normalize_signal_column(out["exit_signal"])
        return out

    if not has_legacy_signal(df):
        raise ValueError("Dataframe is missing both legacy 'Signal' and standard 'entry_signal'/'exit_signal' columns.")

    out = df.copy()
    signal_col = out["Signal"]
    out["entry_signal"] = (signal_col == "BUY").astype(bool)
    out["exit_signal"] = (signal_col == "SELL").astype(bool)
    return out

def ensure_standard_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure dataframe has standard boolean entry_signal and exit_signal columns."""
    out = df.copy()
    if has_standard_signals(out):
        out["entry_signal"] = _normalize_signal_column(out["entry_signal"])
        out["exit_signal"] = _normalize_signal_column(out["exit_signal"])
    elif has_legacy_signal(out):
        out = legacy_signal_to_standard(out)
    else:
        raise ValueError("Dataframe must contain either standard signals or legacy 'Signal' column.")
    return out

def validate_standard_signals(df: pd.DataFrame) -> None:
    """Validate standard signal columns."""
    if "entry_signal" not in df.columns:
        raise ValueError("Missing 'entry_signal' column.")
    if "exit_signal" not in df.columns:
        raise ValueError("Missing 'exit_signal' column.")
    
    if not pd.api.types.is_bool_dtype(df["entry_signal"]):
        raise ValueError("'entry_signal' must be boolean dtype.")
    if not pd.api.types.is_bool_dtype(df["exit_signal"]):
        raise ValueError("'exit_signal' must be boolean dtype.")
    
    conflict_mask = df["entry_signal"] & df["exit_signal"]
    if conflict_mask.any():
        warnings.warn("Simultaneous entry and exit signals detected.", UserWarning)
