"""Price checks shared by data loading, backtesting, and ML datasets."""

from collections.abc import Iterable
import math
from numbers import Real


def validate_close_prices(values: Iterable[object], *, error_type: type[Exception]) -> None:
    """Reject unusable closes before valuation or future-return calculation."""
    for value in values:
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not math.isfinite(float(value))
            or value <= 0
        ):
            raise error_type(f"Close must be a finite numeric value greater than 0; got {value!r}.")
