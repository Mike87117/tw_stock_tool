import pandas as pd
import warnings

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
        out["entry_signal"] = out["entry_signal"].fillna(False).astype(bool)
        out["exit_signal"] = out["exit_signal"].fillna(False).astype(bool)
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
        out["entry_signal"] = out["entry_signal"].fillna(False).astype(bool)
        out["exit_signal"] = out["exit_signal"].fillna(False).astype(bool)
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
