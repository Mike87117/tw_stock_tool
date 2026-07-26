import argparse
import math


def parse_int_tuple(value: str) -> tuple[int, ...]:
    if not value.strip():
        raise argparse.ArgumentTypeError("range cannot be empty")
    try:
        return tuple(int(x.strip()) for x in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer list: '{value}'") from exc


def parse_finite_float(
    value: str,
    *,
    allow_zero: bool,
    boolean_error: str | None,
    numeric_error: str | None,
    range_error: str,
) -> float:
    """Parse a finite float while preserving caller-specific argparse errors."""
    if boolean_error is not None and value.lower() in ("true", "false"):
        raise argparse.ArgumentTypeError(boolean_error)

    try:
        parsed = float(value)
    except ValueError:
        if numeric_error is None:
            raise
        raise argparse.ArgumentTypeError(numeric_error)

    outside_range = parsed < 0 if allow_zero else parsed <= 0
    if not math.isfinite(parsed) or outside_range:
        raise argparse.ArgumentTypeError(range_error)
    return parsed


def parse_positive_integer(
    value: str,
    *,
    boolean_error: str | None,
    decimal_error: str,
    invalid_error: str | None,
    nonpositive_error: str,
) -> int:
    """Parse a positive integer while preserving caller-specific errors."""
    if boolean_error is not None and value.lower() in ("true", "false"):
        raise argparse.ArgumentTypeError(boolean_error)
    if "." in value:
        raise argparse.ArgumentTypeError(decimal_error)

    try:
        parsed = int(value)
    except ValueError:
        if invalid_error is None:
            raise
        raise argparse.ArgumentTypeError(invalid_error)

    if parsed <= 0:
        raise argparse.ArgumentTypeError(nonpositive_error)
    return parsed


def parse_positive_notional(value: str) -> float:
    """Parse a finite, strictly positive notional value."""
    return parse_finite_float(
        value,
        allow_zero=False,
        boolean_error="Notional must be numeric.",
        numeric_error="Notional must be numeric.",
        range_error="Notional must be a finite strictly positive number.",
    )
