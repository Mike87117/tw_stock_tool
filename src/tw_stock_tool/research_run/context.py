"""Research run market data context boundary."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
from threading import RLock, get_ident
from typing import TypeAlias

import pandas as pd

from tw_stock_tool.research_run.models import (
    DataSourceRecord,
)

MarketDataKey: TypeAlias = tuple[
    str,
    str,
    str,
    bool,
    bool,
]


class ResearchRunContextError(RuntimeError):
    """Raised when the per-run market-data context contract is violated."""


@dataclass(
    frozen=True,
    slots=True,
    eq=False,
)
class MarketDataLoadResult:
    data: pd.DataFrame | None
    source_record: DataSourceRecord
    error: Exception | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_record, DataSourceRecord):
            raise ResearchRunContextError(
                f"source_record must be an instance of DataSourceRecord, got {type(self.source_record).__name__}"
            )

        if self.source_record.success:
            if self.data is None:
                raise ResearchRunContextError(
                    "data cannot be None when source_record.success is True"
                )
            if type(self.data) is not pd.DataFrame and not isinstance(
                self.data, pd.DataFrame
            ):
                raise ResearchRunContextError(
                    f"data must be a pandas DataFrame when source_record.success is True, got {type(self.data).__name__}"
                )
            if self.error is not None:
                raise ResearchRunContextError(
                    "error must be None when source_record.success is True"
                )
        else:
            if self.data is not None:
                raise ResearchRunContextError(
                    "data must be None when source_record.success is False"
                )
            if self.error is None:
                raise ResearchRunContextError(
                    "error cannot be None when source_record.success is False"
                )
            if not isinstance(self.error, Exception):
                raise ResearchRunContextError(
                    f"error must be an Exception instance when source_record.success is False, got {type(self.error).__name__}"
                )


def _require_clean_string(name: str, value: object) -> str:
    if type(value) is not str:
        raise ResearchRunContextError(
            f"{name} must be an exact str, got {type(value).__name__}"
        )
    if not value:
        raise ResearchRunContextError(f"{name} cannot be empty")
    if value.strip() != value:
        raise ResearchRunContextError(
            f"{name} must not have leading or trailing whitespace, got {value!r}"
        )
    return value


def _require_exact_bool(name: str, value: object) -> bool:
    if type(value) is not bool:
        raise ResearchRunContextError(
            f"{name} must be an exact bool, got {type(value).__name__}"
        )
    return value


class ResearchRunContext:
    def __init__(
        self,
        loader: Callable[
            [str, str, str, bool, bool],
            MarketDataLoadResult,
        ],
    ) -> None:
        if not callable(loader):
            raise ResearchRunContextError(
                f"loader must be a callable, got {type(loader).__name__}"
            )
        self._loader = loader
        self._lock = RLock()
        self._in_flight: dict[
            MarketDataKey, tuple[int, Future[MarketDataLoadResult]]
        ] = {}
        self._outcomes: dict[MarketDataKey, MarketDataLoadResult] = {}
        self._request_order: list[MarketDataKey] = []

    def load_market_data(
        self,
        *,
        canonical_symbol: str,
        requested_symbol: str,
        period: str,
        interval: str,
        auto_adjust: bool,
        force_refresh: bool,
    ) -> pd.DataFrame:
        c_sym = _require_clean_string("canonical_symbol", canonical_symbol)
        r_sym = _require_clean_string("requested_symbol", requested_symbol)
        p_val = _require_clean_string("period", period)
        i_val = _require_clean_string("interval", interval)
        a_adj = _require_exact_bool("auto_adjust", auto_adjust)
        f_ref = _require_exact_bool("force_refresh", force_refresh)

        key: MarketDataKey = (c_sym, p_val, i_val, a_adj, f_ref)
        current_thread = get_ident()

        is_owner = False
        future: Future[MarketDataLoadResult]

        with self._lock:
            if key in self._outcomes:
                res = self._outcomes[key]
                if res.source_record.success:
                    assert res.data is not None
                    return res.data
                else:
                    assert res.error is not None
                    raise res.error

            if key in self._in_flight:
                owner_thread, fut = self._in_flight[key]
                if owner_thread == current_thread:
                    raise ResearchRunContextError(
                        f"Detected recursive same-key load for key {key} on thread {current_thread}"
                    )
                future = fut
            else:
                future = Future()
                self._in_flight[key] = (current_thread, future)
                self._request_order.append(key)
                is_owner = True

        if is_owner:
            try:
                res = self._loader(r_sym, p_val, i_val, a_adj, f_ref)
            except Exception as exc:
                with self._lock:
                    self._in_flight.pop(key, None)
                    if key in self._request_order:
                        self._request_order.remove(key)
                future.set_exception(exc)
                raise

            if not isinstance(res, MarketDataLoadResult):
                err = ResearchRunContextError(
                    f"loader must return a MarketDataLoadResult, got {type(res).__name__}"
                )
                with self._lock:
                    self._in_flight.pop(key, None)
                    if key in self._request_order:
                        self._request_order.remove(key)
                future.set_exception(err)
                raise err

            rec = res.source_record
            if (
                rec.canonical_symbol != c_sym
                or rec.requested_symbol != r_sym
                or rec.period != p_val
                or rec.interval != i_val
                or rec.auto_adjust is not a_adj
            ):
                err = ResearchRunContextError(
                    f"Loader returned DataSourceRecord with mismatched metadata for key {key}"
                )
                with self._lock:
                    self._in_flight.pop(key, None)
                    if key in self._request_order:
                        self._request_order.remove(key)
                future.set_exception(err)
                raise err

            with self._lock:
                self._outcomes[key] = res
                self._in_flight.pop(key, None)

            future.set_result(res)

            if res.source_record.success:
                assert res.data is not None
                return res.data
            else:
                assert res.error is not None
                raise res.error
        else:
            res = future.result()
            if res.source_record.success:
                assert res.data is not None
                return res.data
            else:
                assert res.error is not None
                raise res.error

    @property
    def data_sources(self) -> tuple[DataSourceRecord, ...]:
        with self._lock:
            return tuple(
                self._outcomes[k].source_record
                for k in self._request_order
                if k in self._outcomes
            )

    @property
    def resolved_keys(self) -> tuple[MarketDataKey, ...]:
        with self._lock:
            return tuple(k for k in self._request_order if k in self._outcomes)
