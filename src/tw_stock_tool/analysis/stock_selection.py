"""Helpers for safely selecting a subset of stock ids."""

from __future__ import annotations

import random


def apply_stock_selection(
    stock_ids: list[str],
    stock_limit: int | None = None,
    stock_sample: int | None = None,
    random_state: int = 42,
) -> list[str]:
    """Apply limit or deterministic random sampling to stock ids."""
    if stock_limit is not None and stock_sample is not None:
        raise ValueError("Use either --stock-limit or --stock-sample, not both.")
    if stock_limit is not None:
        if stock_limit <= 0:
            raise ValueError("--stock-limit must be greater than 0.")
        return stock_ids[:stock_limit]
    if stock_sample is not None:
        if stock_sample <= 0:
            raise ValueError("--stock-sample must be greater than 0.")
        sample_size = min(stock_sample, len(stock_ids))
        return random.Random(random_state).sample(stock_ids, sample_size)
    return stock_ids
