"""Shared CLI adapters for typed Research Run application services."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tw_stock_tool.analysis.scanner import load_stock_ids_from_file, normalize_stock_ids
from tw_stock_tool.analysis.stock_selection import apply_stock_selection
from tw_stock_tool.application.research_run import SymbolRequest
from tw_stock_tool.application.symbol_resolution import (
    MarketHint,
    resolve_symbol_requests,
)
from tw_stock_tool.data.stock_list_updater import (
    load_stock_market_catalog,
    update_stock_list,
)
from tw_stock_tool.research_run.models import ResearchRunResult


def collect_symbol_requests(
    *,
    stocks: list[str] | None,
    file_path: str | None,
    auto_stock_list: bool,
    stock_market: MarketHint,
    stock_list_output: str | Path,
    allow_partial_stock_list: bool,
    stock_limit: int | None,
    stock_sample: int | None,
    random_state: int,
    interactive_supplier: Callable[[], list[str]] | None = None,
) -> tuple[SymbolRequest, ...]:
    """Collect, select, and resolve CLI symbols through one shared boundary."""
    catalog = None
    if auto_stock_list:
        catalog = load_stock_market_catalog(
            market=stock_market,
            allow_partial=allow_partial_stock_list,
        )
        normalized_output, _ = update_stock_list(
            market=stock_market,
            output=stock_list_output,
            allow_partial=allow_partial_stock_list,
            _preloaded_catalog=catalog,
        )
        values = normalize_stock_ids(normalized_output["Stock"].astype(str).tolist())
    else:
        values: list[str] = []
        if file_path:
            values.extend(load_stock_ids_from_file(file_path))
        if stocks:
            values.extend(stocks)
        if not values and interactive_supplier is not None:
            values.extend(interactive_supplier())
        values = normalize_stock_ids(values)

    if not values:
        raise ValueError("No stock ids provided. Use --stocks, --file, or --auto-stock-list.")

    selected = apply_stock_selection(
        values,
        stock_limit=stock_limit,
        stock_sample=stock_sample,
        random_state=random_state,
    )
    return resolve_symbol_requests(
        tuple(selected),
        market_hint=stock_market,
        catalog=catalog,
        allow_partial_catalog=allow_partial_stock_list,
    )


def find_exception_cause(
    exc: BaseException,
    exception_types: type[BaseException] | tuple[type[BaseException], ...],
) -> BaseException | None:
    """Find a matching explicit cause without looping through cycles."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, exception_types):
            return current
        seen.add(id(current))
        current = current.__cause__
    return None


def artifact_path(result: ResearchRunResult, artifact_type: str) -> str | None:
    """Return the path for one exact artifact type, rejecting duplicates."""
    matches = [
        artifact.path
        for artifact in result.generated_artifacts
        if artifact.artifact_type == artifact_type
    ]
    if len(matches) > 1:
        raise ValueError(f"Duplicate generated artifact type: {artifact_type}")
    return matches[0] if matches else None
