"""Base strategy contract for signal generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype


class BaseStrategy(ABC):
    """Base class for strategies that only generate and validate signals."""

    name: str = "base"

    @abstractmethod
    def generate_signals(
        self,
        df: pd.DataFrame,
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Return a DataFrame containing entry_signal and exit_signal columns."""

    def validate_signals(self, result_df: pd.DataFrame) -> None:
        """Validate strategy output against the project signal standard."""
        required_columns = ("entry_signal", "exit_signal")
        for column in required_columns:
            if column not in result_df.columns:
                raise ValueError(f"Missing required signal column: {column}")
            if len(result_df[column]) != len(result_df):
                raise ValueError(f"Signal column length mismatch: {column}")
            if not is_bool_dtype(result_df[column]):
                raise ValueError(f"Signal column must be bool: {column}")
