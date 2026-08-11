"""Minimal read-only boundaries for future broker observation adapters."""

from typing import Protocol

from tw_stock_tool.broker_safety.models import (
    BrokerAccountSnapshot,
    BrokerCapabilities,
    TradingSessionSnapshot,
)


class BrokerCapabilitiesReader(Protocol):
    def read_capabilities(self) -> BrokerCapabilities: ...


class BrokerAccountSnapshotReader(Protocol):
    def read_account_snapshot(self) -> BrokerAccountSnapshot: ...


class TradingSessionReader(Protocol):
    def read_trading_session(self) -> TradingSessionSnapshot: ...


__all__ = [
    "BrokerAccountSnapshotReader",
    "BrokerCapabilitiesReader",
    "TradingSessionReader",
]
