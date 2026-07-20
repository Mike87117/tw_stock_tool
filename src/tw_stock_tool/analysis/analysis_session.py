from collections.abc import Callable
from threading import Lock

from tw_stock_tool.analysis.analysis import StockAnalysis, analyze_stock


class AnalysisSession:
    """Memoize one analysis result (or failure) per stock for one pipeline run."""

    def __init__(
        self,
        *,
        period: str,
        interval: str,
        auto_adjust: bool,
        force_refresh: bool,
        analyzer: Callable[..., StockAnalysis] | None = None,
    ) -> None:
        self.period = period
        self.interval = interval
        self.auto_adjust = auto_adjust
        self.force_refresh = force_refresh
        self._analyzer = analyzer if analyzer is not None else analyze_stock
        self._cache: dict[str, StockAnalysis | Exception] = {}
        self._locks: dict[str, Lock] = {}
        self._locks_guard = Lock()

    def get(self, stock_id: str) -> StockAnalysis:
        key = str(stock_id).strip()
        with self._locks_guard:
            lock = self._locks.setdefault(key, Lock())
        with lock:
            cached = self._cache.get(key)
            if cached is not None:
                if isinstance(cached, Exception):
                    raise cached
                return cached
            try:
                result = self._analyzer(
                    stock_id=key,
                    period=self.period,
                    interval=self.interval,
                    auto_adjust=self.auto_adjust,
                    force_refresh=self.force_refresh,
                )
            except Exception as exc:
                self._cache[key] = exc
                raise
            self._cache[key] = result
            return result
