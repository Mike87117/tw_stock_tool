"""Read-only orchestration for Fubon Neo securities TEST observations."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version as distribution_version
from typing import Protocol

from tw_stock_tool.broker_adapters.fubon_neo.account_readiness import (
    FubonNeoAccountFactReadiness,
    current_fubon_neo_account_fact_readiness,
)
from tw_stock_tool.broker_adapters.fubon_neo.config import (
    FUBON_NEO_SDK_VERSION,
    FUBON_NEO_TEST_CONNECTION_IDENTITY,
    FubonNeoInstrumentCatalog,
    FubonNeoReadConnectionIdentity,
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
    ProviderReadinessState,
)


class FubonNeoReadonlyPort(Protocol):
    """The complete provider surface reachable by this adapter."""

    connection_identity: FubonNeoReadConnectionIdentity

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
    account_fact_readiness: FubonNeoAccountFactReadiness
    retrieved_at: str
    missing_mandatory_fields: tuple[str, ...] = ("buying_power", "equity")

    def __post_init__(self) -> None:
        if (
            type(self.account_fact_readiness) is not FubonNeoAccountFactReadiness
            or self.account_fact_readiness != current_fubon_neo_account_fact_readiness()
            or self.account_fact_readiness.overall is not ProviderReadinessState.BLOCKED
        ):
            raise FubonNeoReadError(
                FubonNeoErrorCode.MANDATORY_ACCOUNT_FIELD_UNAVAILABLE,
                "account observations require the exact reviewed BLOCKED readiness result",
            )
        if self.missing_mandatory_fields != ("buying_power", "equity"):
            raise FubonNeoReadError(
                FubonNeoErrorCode.MANDATORY_ACCOUNT_FIELD_UNAVAILABLE,
                "mandatory account fields cannot be overridden",
            )

    def require_complete_snapshot(self) -> BrokerAccountSnapshot:
        raise FubonNeoReadError(
            FubonNeoErrorCode.MANDATORY_ACCOUNT_FIELD_UNAVAILABLE,
            "authoritative buying_power and equity facts are unavailable",
        )


class FubonNeoReadonlyAdapter:
    def __init__(
        self,
        config: FubonNeoTestConfig,
        port: FubonNeoReadonlyPort,
        instrument_catalog: FubonNeoInstrumentCatalog,
    ) -> None:
        if type(config) is not FubonNeoTestConfig:
            raise FubonNeoReadError(
                FubonNeoErrorCode.ENVIRONMENT_NOT_TEST,
                "an exact reviewed TEST configuration is required",
            )
        self._assert_provenance(port)
        if type(instrument_catalog) is not FubonNeoInstrumentCatalog:
            raise FubonNeoReadError(
                FubonNeoErrorCode.INSTRUMENT_CLASSIFICATION_UNTRUSTED,
                "an exact authoritative instrument catalog is required",
            )
        self._config = config
        self._port = port
        self._instrument_catalog = instrument_catalog

    @staticmethod
    def _assert_provenance(port: FubonNeoReadonlyPort) -> None:
        try:
            identity = getattr(port, "connection_identity", None)
        except Exception:
            identity = None
        if type(identity) is not FubonNeoReadConnectionIdentity or identity != FUBON_NEO_TEST_CONNECTION_IDENTITY:
            raise FubonNeoReadError(
                FubonNeoErrorCode.SESSION_PROVENANCE_MISMATCH,
                "provider session provenance does not match the reviewed TEST contract",
            )

    def _read(self, reader) -> object:
        self._assert_provenance(self._port)
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
        self._assert_provenance(self._port)
        return map_capabilities(
            capability_snapshot_id=capability_snapshot_id,
            observed_at=observed_at,
        )

    def read_account_fact_readiness(self) -> FubonNeoAccountFactReadiness:
        """Expose the reviewed semantic gate without reading or mutating the broker."""

        self._assert_provenance(self._port)
        return current_fubon_neo_account_fact_readiness()

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
        inventory = unwrap_provider_result(self._read(self._port.read_inventories), expect_list=True)
        unrealized = unwrap_provider_result(self._read(self._port.read_unrealized_pnl), expect_list=True)
        orders = unwrap_provider_result(self._read(self._port.read_order_results), expect_list=True)
        return FubonNeoIncompleteAccountRead(
            capabilities=capabilities,
            cash=cash,
            positions=map_positions(
                inventory,
                unrealized,
                self._config,
                instrument_catalog=self._instrument_catalog,
                retrieved_at=retrieved_at,
            ),
            open_orders=map_open_orders(
                orders,
                self._config,
                retrieved_at=retrieved_at,
            ),
            account_fact_readiness=self.read_account_fact_readiness(),
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
    """Load and version-check the proprietary SDK for explicit TEST use."""
    try:
        import_module("fubon_neo")
        installed_version = distribution_version("fubon_neo")
    except (ImportError, ModuleNotFoundError, PackageNotFoundError):
        raise FubonNeoReadError(
            FubonNeoErrorCode.OPTIONAL_DEPENDENCY_MISSING,
            "install the official Fubon Neo SDK wheel for explicit TEST use",
        ) from None
    if installed_version != FUBON_NEO_SDK_VERSION:
        raise FubonNeoReadError(
            FubonNeoErrorCode.SESSION_PROVENANCE_MISMATCH,
            "installed Fubon Neo SDK version is outside the reviewed TEST contract",
        )


__all__ = [
    "FubonNeoIncompleteAccountRead",
    "FubonNeoReadonlyAdapter",
    "FubonNeoReadonlyPort",
    "require_fubon_neo_sdk",
]
