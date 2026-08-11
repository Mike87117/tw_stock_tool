"""Read-only orchestration for Fubon Neo securities TEST observations."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Protocol

from tw_stock_tool.broker_adapters.fubon_neo.config import (
    FubonNeoTestConfig,
)
from tw_stock_tool.broker_adapters.fubon_neo.errors import (
    FubonNeoErrorCode,
    FubonNeoReadError,
)
from tw_stock_tool.broker_adapters.fubon_neo.mapper import (
    FubonNeoCashObservation,
    map_capabilities,
    map_cash,
    map_open_orders,
    map_positions,
    unwrap_provider_result,
)
from tw_stock_tool.broker_safety import (
    BrokerAccountSnapshot,
    BrokerCapabilities,
    BrokerOpenOrderSnapshot,
    BrokerPositionSnapshot,
)


class FubonNeoReadonlyPort(Protocol):
    """The complete provider surface reachable by this adapter."""

    def read_bank_remain(self) -> object: ...

    def read_inventories(self) -> object: ...

    def read_unrealized_pnl(self) -> object: ...

    def read_order_results(self) -> object: ...


@dataclass(frozen=True, slots=True)
class FubonNeoIncompleteAccountRead:
    """Safe observations that intentionally cannot masquerade as an A2 account."""

    capabilities: BrokerCapabilities
    cash: FubonNeoCashObservation
    positions: tuple[BrokerPositionSnapshot, ...]
    open_orders: tuple[BrokerOpenOrderSnapshot, ...]
    retrieved_at: str
    missing_mandatory_fields: tuple[str, ...] = ("buying_power", "equity")

    def require_complete_snapshot(self) -> BrokerAccountSnapshot:
        raise FubonNeoReadError(
            FubonNeoErrorCode.MANDATORY_ACCOUNT_FIELD_UNAVAILABLE,
            "authoritative buying_power and equity facts are unavailable",
        )


class FubonNeoReadonlyAdapter:
    def __init__(self, config: FubonNeoTestConfig, port: FubonNeoReadonlyPort) -> None:
        if type(config) is not FubonNeoTestConfig:
            raise FubonNeoReadError(
                FubonNeoErrorCode.ENVIRONMENT_NOT_TEST,
                "an exact reviewed TEST configuration is required",
            )
        self._config = config
        self._port = port

    @staticmethod
    def _read(reader) -> object:
        try:
            return reader()
        except FubonNeoReadError:
            raise
        except Exception:
            raise FubonNeoReadError(
                FubonNeoErrorCode.PROVIDER_READ_FAILED,
                "provider read raised a sanitized failure",
            ) from None

    def read_capabilities(
        self,
        *,
        capability_snapshot_id: str,
        observed_at: str,
    ) -> BrokerCapabilities:
        return map_capabilities(
            capability_snapshot_id=capability_snapshot_id,
            observed_at=observed_at,
        )

    def read_account_observations(
        self,
        *,
        capability_snapshot_id: str,
        retrieved_at: str,
    ) -> FubonNeoIncompleteAccountRead:
        capabilities = self.read_capabilities(
            capability_snapshot_id=capability_snapshot_id,
            observed_at=retrieved_at,
        )
        cash = map_cash(
            unwrap_provider_result(self._read(self._port.read_bank_remain), expect_list=False),
            self._config,
        )
        inventory = unwrap_provider_result(
            self._read(self._port.read_inventories), expect_list=True
        )
        unrealized = unwrap_provider_result(
            self._read(self._port.read_unrealized_pnl), expect_list=True
        )
        orders = unwrap_provider_result(
            self._read(self._port.read_order_results), expect_list=True
        )
        return FubonNeoIncompleteAccountRead(
            capabilities=capabilities,
            cash=cash,
            positions=map_positions(
                inventory,
                unrealized,
                self._config,
                retrieved_at=retrieved_at,
            ),
            open_orders=map_open_orders(
                orders,
                self._config,
                retrieved_at=retrieved_at,
            ),
            retrieved_at=retrieved_at,
        )

    def read_account_snapshot(
        self,
        *,
        capability_snapshot_id: str,
        retrieved_at: str,
    ) -> BrokerAccountSnapshot:
        return self.read_account_observations(
            capability_snapshot_id=capability_snapshot_id,
            retrieved_at=retrieved_at,
        ).require_complete_snapshot()


def require_fubon_neo_sdk() -> None:
    """Load the proprietary SDK only for an explicit operator request."""
    try:
        import_module("fubon_neo")
    except (ImportError, ModuleNotFoundError):
        raise FubonNeoReadError(
            FubonNeoErrorCode.OPTIONAL_DEPENDENCY_MISSING,
            "install the official Fubon Neo SDK wheel for explicit TEST use",
        ) from None


__all__ = [
    "FubonNeoIncompleteAccountRead",
    "FubonNeoReadonlyAdapter",
    "FubonNeoReadonlyPort",
    "require_fubon_neo_sdk",
]
