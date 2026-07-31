"""Catalog-backed symbol resolution for canonical Taiwan market symbols."""

from __future__ import annotations

import re
from typing import Literal, TypeAlias

import pandas as pd

from tw_stock_tool.application.research_run import SymbolRequest
from tw_stock_tool.data.stock_list_updater import (
    CATALOG_COLUMNS,
    load_stock_market_catalog,
)

MarketHint: TypeAlias = Literal["all", "twse", "tpex"]


class SymbolResolutionError(ValueError):
    """Raised when a requested symbol cannot be resolved unambiguously."""


_MARKET_HINTS = frozenset(("all", "twse", "tpex"))
_SUFFIX_RE = re.compile(r"^(?P<base>.+)\.(?P<suffix>TWO|TW)$", re.IGNORECASE)


def _validate_market_hint(market_hint: object) -> MarketHint:
    if type(market_hint) is not str or market_hint not in _MARKET_HINTS:
        raise SymbolResolutionError(
            "market_hint must be exactly one of: all, twse, tpex"
        )
    return market_hint  # type: ignore[return-value]


def _validate_requested_symbol(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise SymbolResolutionError(f"{name} must be a clean exact string")
    return value


def _validate_catalog(catalog: object) -> pd.DataFrame:
    if not isinstance(catalog, pd.DataFrame):
        raise SymbolResolutionError(
            f"catalog must be a pandas DataFrame, got {type(catalog).__name__}"
        )
    missing = [column for column in CATALOG_COLUMNS if column not in catalog.columns]
    if missing:
        raise SymbolResolutionError(
            f"catalog is missing required columns: {', '.join(missing)}"
        )
    return catalog.loc[:, CATALOG_COLUMNS].copy(deep=True)


def _explicit_canonical(requested_symbol: str) -> str | None:
    if "." not in requested_symbol:
        return None
    match = _SUFFIX_RE.fullmatch(requested_symbol)
    if match is None or "." in match.group("base"):
        raise SymbolResolutionError(
            f"Unsupported or malformed Taiwan market suffix: {requested_symbol}"
        )
    base = match.group("base")
    if not base:
        raise SymbolResolutionError("Explicit market suffix requires a nonblank base symbol")
    return f"{base}.{match.group('suffix').upper()}"


def _resolve_bare_from_catalog(
    requested_symbol: str,
    catalog: pd.DataFrame,
) -> str:
    stock_values = catalog["Stock"].astype(str).str.strip()
    matches = catalog.loc[stock_values == requested_symbol]
    if matches.empty:
        raise SymbolResolutionError(
            f"Unknown symbol in catalog: {requested_symbol}"
        )

    markets = {str(value).strip().upper() for value in matches["Market"]}
    if not markets or not markets.issubset({"TWSE", "TPEX"}):
        raise SymbolResolutionError(
            f"Unknown market metadata for symbol: {requested_symbol}"
        )
    if len(markets) != 1:
        raise SymbolResolutionError(
            f"Ambiguous symbol across markets: {requested_symbol}"
        )
    suffix = ".TW" if "TWSE" in markets else ".TWO"
    return f"{requested_symbol}{suffix}"


def resolve_symbol_requests(
    requested_symbols: tuple[str, ...],
    *,
    market_hint: MarketHint = "all",
    catalog: pd.DataFrame | None = None,
    allow_partial_catalog: bool = False,
) -> tuple[SymbolRequest, ...]:
    """Resolve a batch of requested symbols in input order."""
    if type(requested_symbols) is not tuple or not requested_symbols:
        raise SymbolResolutionError("requested_symbols must be a nonempty exact tuple")
    for index, requested_symbol in enumerate(requested_symbols):
        _validate_requested_symbol(f"requested_symbols[{index}]", requested_symbol)
    if len(set(requested_symbols)) != len(requested_symbols):
        raise SymbolResolutionError("Duplicate requested symbols are not allowed")
    selected_hint = _validate_market_hint(market_hint)
    if type(allow_partial_catalog) is not bool:
        raise SymbolResolutionError("allow_partial_catalog must be an exact bool")
    catalog_frame = None if catalog is None else _validate_catalog(catalog)

    resolved_canonicals: list[str | None] = [None] * len(requested_symbols)
    bare_indexes: list[int] = []
    for index, requested_symbol in enumerate(requested_symbols):
        explicit = _explicit_canonical(requested_symbol)
        if explicit is not None:
            resolved_canonicals[index] = explicit
        elif selected_hint == "twse":
            resolved_canonicals[index] = f"{requested_symbol}.TW"
        elif selected_hint == "tpex":
            resolved_canonicals[index] = f"{requested_symbol}.TWO"
        else:
            bare_indexes.append(index)

    if bare_indexes:
        if catalog_frame is None:
            catalog_frame = load_stock_market_catalog(
                market="all",
                allow_partial=allow_partial_catalog,
            )
            catalog_frame = _validate_catalog(catalog_frame)
        for index in bare_indexes:
            resolved_canonicals[index] = _resolve_bare_from_catalog(
                requested_symbols[index], catalog_frame
            )

    canonicals = tuple(canonical for canonical in resolved_canonicals if canonical is not None)
    if len(canonicals) != len(set(canonicals)):
        raise SymbolResolutionError("Duplicate canonical symbols are not allowed")
    return tuple(
        SymbolRequest(requested_symbol, canonical)
        for requested_symbol, canonical in zip(requested_symbols, canonicals)
    )


def resolve_symbol_request(
    requested_symbol: str,
    *,
    market_hint: MarketHint = "all",
    catalog: pd.DataFrame | None = None,
    allow_partial_catalog: bool = False,
) -> SymbolRequest:
    """Resolve one requested symbol using the canonical batch boundary."""
    return resolve_symbol_requests(
        (requested_symbol,),
        market_hint=market_hint,
        catalog=catalog,
        allow_partial_catalog=allow_partial_catalog,
    )[0]
