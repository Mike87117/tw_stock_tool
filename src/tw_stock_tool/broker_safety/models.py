"""Immutable broker-neutral observation and pre-authorization safety facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
import re
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SCHEMA_VERSION = "1.0"
CAPABILITIES_ARTIFACT_TYPE = "broker_capabilities"
POSITION_ARTIFACT_TYPE = "broker_position_snapshot"
OPEN_ORDER_ARTIFACT_TYPE = "broker_open_order_snapshot"
ACCOUNT_ARTIFACT_TYPE = "broker_account_snapshot"
SESSION_ARTIFACT_TYPE = "trading_session_snapshot"
POLICY_ARTIFACT_TYPE = "broker_safety_policy"
EXPECTATION_ARTIFACT_TYPE = "broker_local_expectation"
RECONCILIATION_ARTIFACT_TYPE = "broker_reconciliation_result"
LIMIT_REQUEST_ARTIFACT_TYPE = "broker_limit_request"


class BrokerSafetyModelError(ValueError):
    """Raised when broker-safety facts violate their frozen contract."""


class SupportState(StrEnum):
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"
    SUPPORTED = "SUPPORTED"


class BrokerEnvironment(StrEnum):
    SANDBOX = "SANDBOX"
    LIVE = "LIVE"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class TimeInForce(StrEnum):
    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


class TradingPermission(StrEnum):
    UNKNOWN = "UNKNOWN"
    DISABLED = "DISABLED"
    ENABLED = "ENABLED"


class CancelReplaceSemantics(StrEnum):
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"
    CANCEL_THEN_NEW = "CANCEL_THEN_NEW"
    ATOMIC_REPLACE = "ATOMIC_REPLACE"


class AccountDataFreshness(StrEnum):
    UNKNOWN = "UNKNOWN"
    POLLING = "POLLING"
    STREAMING = "STREAMING"


class FieldReliability(StrEnum):
    UNAVAILABLE = "UNAVAILABLE"
    UNRELIABLE = "UNRELIABLE"
    RELIABLE = "RELIABLE"


class BrokerOrderStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    PENDING_SUBMIT = "PENDING_SUBMIT"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TradingSessionState(StrEnum):
    REGULAR = "REGULAR"
    AUCTION_OR_PREOPEN = "AUCTION_OR_PREOPEN"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class PermissionState(StrEnum):
    UNKNOWN = "UNKNOWN"
    NOT_PERMITTED = "NOT_PERMITTED"
    PERMITTED = "PERMITTED"


class CapabilityName(StrEnum):
    CLIENT_ORDER_ID = "CLIENT_ORDER_ID"
    QUERY_BY_CLIENT_ID = "QUERY_BY_CLIENT_ID"
    FRACTIONAL_QUANTITY = "FRACTIONAL_QUANTITY"
    PARTIAL_FILL_REPORTING = "PARTIAL_FILL_REPORTING"
    CANCEL_REPLACE = "CANCEL_REPLACE"
    ACCOUNT_DATA_FRESHNESS = "ACCOUNT_DATA_FRESHNESS"
    TRADING_PERMISSION = "TRADING_PERMISSION"
    SHORT_SELLING = "SHORT_SELLING"
    BORROW_AVAILABILITY = "BORROW_AVAILABILITY"
    FEE_ESTIMATE = "FEE_ESTIMATE"


class FindingSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class FindingSubjectType(StrEnum):
    ACCOUNT = "ACCOUNT"
    CAPABILITY = "CAPABILITY"
    SESSION = "SESSION"
    POSITION = "POSITION"
    OPEN_ORDER = "OPEN_ORDER"
    SUBMISSION = "SUBMISSION"
    RECONCILIATION = "RECONCILIATION"
    LIMIT = "LIMIT"
    POLICY = "POLICY"


class FindingCode(StrEnum):
    BROKER_NOT_ALLOWED = "BROKER_NOT_ALLOWED"
    ACCOUNT_NOT_ALLOWED = "ACCOUNT_NOT_ALLOWED"
    ENVIRONMENT_NOT_ALLOWED = "ENVIRONMENT_NOT_ALLOWED"
    MARKET_NOT_ALLOWED = "MARKET_NOT_ALLOWED"
    ORDER_TYPE_NOT_ALLOWED = "ORDER_TYPE_NOT_ALLOWED"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    BALANCE_MISSING = "BALANCE_MISSING"
    SNAPSHOT_STALE = "SNAPSHOT_STALE"
    CAPABILITY_UNKNOWN = "CAPABILITY_UNKNOWN"
    CAPABILITY_UNSUPPORTED = "CAPABILITY_UNSUPPORTED"
    TRADING_PERMISSION_UNKNOWN = "TRADING_PERMISSION_UNKNOWN"
    TRADING_PERMISSION_DISABLED = "TRADING_PERMISSION_DISABLED"
    SESSION_UNKNOWN = "SESSION_UNKNOWN"
    SESSION_NOT_PERMITTED = "SESSION_NOT_PERMITTED"
    POSITION_MISMATCH = "POSITION_MISMATCH"
    UNKNOWN_BROKER_OPEN_ORDER = "UNKNOWN_BROKER_OPEN_ORDER"
    UNRESOLVED_LOCAL_ORDER = "UNRESOLVED_LOCAL_ORDER"
    UNRESOLVED_SUBMISSION = "UNRESOLVED_SUBMISSION"
    CLIENT_ORDER_ID_CONFLICT = "CLIENT_ORDER_ID_CONFLICT"
    RECONCILIATION_STALE = "RECONCILIATION_STALE"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    ORDER_NOTIONAL_LIMIT = "ORDER_NOTIONAL_LIMIT"
    ACCOUNT_EXPOSURE_LIMIT = "ACCOUNT_EXPOSURE_LIMIT"
    SYMBOL_EXPOSURE_LIMIT = "SYMBOL_EXPOSURE_LIMIT"
    SYMBOL_QUANTITY_LIMIT = "SYMBOL_QUANTITY_LIMIT"
    OPEN_ORDER_LIMIT = "OPEN_ORDER_LIMIT"
    DAILY_NOTIONAL_LIMIT = "DAILY_NOTIONAL_LIMIT"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    DAILY_LOSS_UNRELIABLE = "DAILY_LOSS_UNRELIABLE"
    INITIAL_ALLOCATION_LIMIT = "INITIAL_ALLOCATION_LIMIT"
    INSUFFICIENT_LIMIT_INPUT = "INSUFFICIENT_LIMIT_INPUT"


_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def _clean(name: str, value: object, *, upper: bool = False) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise BrokerSafetyModelError(f"{name} must be an exact non-empty string")
    if upper and value != value.upper():
        raise BrokerSafetyModelError(f"{name} must be uppercase canonical text")
    return value


def _optional_clean(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _clean(name, value)


def _uuid4(name: str, value: object) -> str:
    text = _clean(name, value)
    try:
        parsed = UUID(text)
    except ValueError as exc:
        raise BrokerSafetyModelError(f"{name} must be a canonical UUID") from exc
    if parsed.version != 4 or str(parsed) != text:
        raise BrokerSafetyModelError(f"{name} must be a canonical UUIDv4")
    return text


def _timestamp(name: str, value: object) -> datetime:
    text = _clean(name, value)
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise BrokerSafetyModelError(
            f"{name} must be canonical UTC second timestamp"
        ) from exc


def _date(name: str, value: object) -> str:
    text = _clean(name, value)
    if _DATE.fullmatch(text) is None:
        raise BrokerSafetyModelError(f"{name} must be canonical YYYY-MM-DD")
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise BrokerSafetyModelError(f"{name} must be a real calendar date") from exc
    return text


def _decimal(
    name: str,
    value: object,
    *,
    nonnegative: bool = False,
    positive: bool = False,
) -> Decimal:
    if type(value) is not Decimal or not value.is_finite():
        raise BrokerSafetyModelError(f"{name} must be an exact finite Decimal")
    if nonnegative and value < 0:
        raise BrokerSafetyModelError(f"{name} must be non-negative")
    if positive and value <= 0:
        raise BrokerSafetyModelError(f"{name} must be positive")
    return value


def _count(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise BrokerSafetyModelError(f"{name} must be an exact non-negative int")
    return value


def _exact_enum(name: str, value: object, expected: type[StrEnum]) -> None:
    if type(value) is not expected:
        raise BrokerSafetyModelError(f"{name} must be an exact {expected.__name__}")


def _canonical_tuple(
    name: str,
    value: object,
    item_type: type,
    *,
    allow_empty: bool = True,
) -> tuple:
    if type(value) is not tuple or any(type(item) is not item_type for item in value):
        raise BrokerSafetyModelError(
            f"{name} must be an exact tuple of {item_type.__name__}"
        )
    if not allow_empty and not value:
        raise BrokerSafetyModelError(f"{name} must not be empty")
    if item_type is str or issubclass(item_type, StrEnum):
        keys = tuple(item.value if isinstance(item, StrEnum) else item for item in value)
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise BrokerSafetyModelError(f"{name} must be unique and canonically ordered")
    elif len(set(value)) != len(value):
        raise BrokerSafetyModelError(f"{name} must not contain exact duplicates")
    return value


def _reliable_decimal(
    name: str,
    value: Decimal | None,
    reliability: FieldReliability,
) -> None:
    _exact_enum(f"{name}_reliability", reliability, FieldReliability)
    if value is not None:
        _decimal(name, value)
    if reliability is FieldReliability.RELIABLE and value is None:
        raise BrokerSafetyModelError(f"reliable {name} requires a value")
    if reliability is FieldReliability.UNAVAILABLE and value is not None:
        raise BrokerSafetyModelError(f"unavailable {name} must remain None")


@dataclass(frozen=True, slots=True)
class BrokerCapabilities:
    schema_version: str
    artifact_type: str
    capability_snapshot_id: str
    broker_id: str
    environment: BrokerEnvironment
    market: str
    currency: str
    client_order_id_support: SupportState
    client_order_id_max_length: int | None
    query_by_client_id_support: SupportState
    fractional_quantity_support: SupportState
    supported_order_types: tuple[OrderType, ...]
    supported_time_in_force: tuple[TimeInForce, ...]
    partial_fill_reporting: SupportState
    cancel_replace_semantics: CancelReplaceSemantics
    account_data_freshness: AccountDataFreshness
    trading_permission: TradingPermission
    short_selling_support: SupportState
    borrow_availability_support: SupportState
    fee_estimate_support: SupportState
    observed_at: str
    source_version: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION or self.artifact_type != CAPABILITIES_ARTIFACT_TYPE:
            raise BrokerSafetyModelError("unsupported capabilities schema/artifact type")
        _uuid4("capability_snapshot_id", self.capability_snapshot_id)
        _clean("broker_id", self.broker_id)
        _exact_enum("environment", self.environment, BrokerEnvironment)
        _clean("market", self.market, upper=True)
        _clean("currency", self.currency, upper=True)
        for name in (
            "client_order_id_support",
            "query_by_client_id_support",
            "fractional_quantity_support",
            "partial_fill_reporting",
            "short_selling_support",
            "borrow_availability_support",
            "fee_estimate_support",
        ):
            _exact_enum(name, getattr(self, name), SupportState)
        if self.client_order_id_support is SupportState.SUPPORTED:
            if type(self.client_order_id_max_length) is not int or self.client_order_id_max_length <= 0:
                raise BrokerSafetyModelError(
                    "supported client order IDs require a positive exact max length"
                )
        elif self.client_order_id_max_length is not None:
            raise BrokerSafetyModelError(
                "non-supported client order IDs require unknown max length"
            )
        if (
            self.query_by_client_id_support is SupportState.SUPPORTED
            and self.client_order_id_support is not SupportState.SUPPORTED
        ):
            raise BrokerSafetyModelError(
                "query by client ID requires supported client order IDs"
            )
        _canonical_tuple("supported_order_types", self.supported_order_types, OrderType, allow_empty=False)
        _canonical_tuple("supported_time_in_force", self.supported_time_in_force, TimeInForce, allow_empty=False)
        _exact_enum("cancel_replace_semantics", self.cancel_replace_semantics, CancelReplaceSemantics)
        _exact_enum("account_data_freshness", self.account_data_freshness, AccountDataFreshness)
        _exact_enum("trading_permission", self.trading_permission, TradingPermission)
        _timestamp("observed_at", self.observed_at)
        _clean("source_version", self.source_version)

    def capability_state(self, name: CapabilityName) -> SupportState:
        _exact_enum("capability", name, CapabilityName)
        direct = {
            CapabilityName.CLIENT_ORDER_ID: self.client_order_id_support,
            CapabilityName.QUERY_BY_CLIENT_ID: self.query_by_client_id_support,
            CapabilityName.FRACTIONAL_QUANTITY: self.fractional_quantity_support,
            CapabilityName.PARTIAL_FILL_REPORTING: self.partial_fill_reporting,
            CapabilityName.SHORT_SELLING: self.short_selling_support,
            CapabilityName.BORROW_AVAILABILITY: self.borrow_availability_support,
            CapabilityName.FEE_ESTIMATE: self.fee_estimate_support,
        }
        if name in direct:
            return direct[name]
        if name is CapabilityName.CANCEL_REPLACE:
            if self.cancel_replace_semantics is CancelReplaceSemantics.UNKNOWN:
                return SupportState.UNKNOWN
            if self.cancel_replace_semantics is CancelReplaceSemantics.UNSUPPORTED:
                return SupportState.UNSUPPORTED
            return SupportState.SUPPORTED
        if name is CapabilityName.ACCOUNT_DATA_FRESHNESS:
            return (
                SupportState.UNKNOWN
                if self.account_data_freshness is AccountDataFreshness.UNKNOWN
                else SupportState.SUPPORTED
            )
        return {
            TradingPermission.UNKNOWN: SupportState.UNKNOWN,
            TradingPermission.DISABLED: SupportState.UNSUPPORTED,
            TradingPermission.ENABLED: SupportState.SUPPORTED,
        }[self.trading_permission]


@dataclass(frozen=True, slots=True)
class BrokerPositionSnapshot:
    schema_version: str
    artifact_type: str
    canonical_symbol: str
    broker_symbol: str
    quantity: Decimal
    available_quantity: Decimal
    average_cost: Decimal | None
    average_cost_reliability: FieldReliability
    market_value: Decimal | None
    market_value_reliability: FieldReliability
    realized_pnl: Decimal | None
    realized_pnl_reliability: FieldReliability
    unrealized_pnl: Decimal | None
    unrealized_pnl_reliability: FieldReliability
    as_of: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION or self.artifact_type != POSITION_ARTIFACT_TYPE:
            raise BrokerSafetyModelError("unsupported position schema/artifact type")
        _clean("canonical_symbol", self.canonical_symbol, upper=True)
        _clean("broker_symbol", self.broker_symbol)
        _decimal("quantity", self.quantity)
        _decimal("available_quantity", self.available_quantity, nonnegative=True)
        if self.quantity >= 0 and self.available_quantity > self.quantity:
            raise BrokerSafetyModelError("available quantity cannot exceed long quantity")
        if self.quantity < 0 and self.available_quantity != 0:
            raise BrokerSafetyModelError("short quantity requires zero available quantity")
        _reliable_decimal("average_cost", self.average_cost, self.average_cost_reliability)
        _reliable_decimal("market_value", self.market_value, self.market_value_reliability)
        _reliable_decimal("realized_pnl", self.realized_pnl, self.realized_pnl_reliability)
        _reliable_decimal("unrealized_pnl", self.unrealized_pnl, self.unrealized_pnl_reliability)
        if self.average_cost is not None and self.average_cost < 0:
            raise BrokerSafetyModelError("average_cost must be non-negative")
        _timestamp("as_of", self.as_of)


@dataclass(frozen=True, slots=True)
class BrokerOpenOrderSnapshot:
    schema_version: str
    artifact_type: str
    broker_order_id: str
    client_order_id: str | None
    economic_intent_id: str | None
    canonical_symbol: str
    broker_symbol: str
    side: OrderSide
    order_type: OrderType
    time_in_force: TimeInForce
    original_quantity: Decimal
    cumulative_filled_quantity: Decimal
    remaining_quantity: Decimal
    status: BrokerOrderStatus
    submitted_at: str
    last_broker_update: str
    fees: Decimal | None
    taxes: Decimal | None

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION or self.artifact_type != OPEN_ORDER_ARTIFACT_TYPE:
            raise BrokerSafetyModelError("unsupported open-order schema/artifact type")
        _clean("broker_order_id", self.broker_order_id)
        _optional_clean("client_order_id", self.client_order_id)
        _optional_clean("economic_intent_id", self.economic_intent_id)
        _clean("canonical_symbol", self.canonical_symbol, upper=True)
        _clean("broker_symbol", self.broker_symbol)
        _exact_enum("side", self.side, OrderSide)
        _exact_enum("order_type", self.order_type, OrderType)
        _exact_enum("time_in_force", self.time_in_force, TimeInForce)
        original = _decimal("original_quantity", self.original_quantity, positive=True)
        filled = _decimal("cumulative_filled_quantity", self.cumulative_filled_quantity, nonnegative=True)
        remaining = _decimal("remaining_quantity", self.remaining_quantity, nonnegative=True)
        if filled > original or remaining != original - filled:
            raise BrokerSafetyModelError("open-order quantities violate exact accounting")
        _exact_enum("status", self.status, BrokerOrderStatus)
        submitted = _timestamp("submitted_at", self.submitted_at)
        updated = _timestamp("last_broker_update", self.last_broker_update)
        if updated < submitted:
            raise BrokerSafetyModelError("last broker update cannot precede submission")
        for name in ("fees", "taxes"):
            value = getattr(self, name)
            if value is not None:
                _decimal(name, value, nonnegative=True)


@dataclass(frozen=True, slots=True)
class BrokerAccountSnapshot:
    schema_version: str
    artifact_type: str
    snapshot_id: str
    account_reference: str
    broker_id: str
    environment: BrokerEnvironment
    retrieved_at: str
    currency: str
    cash: Decimal
    buying_power: Decimal
    equity: Decimal
    capabilities: BrokerCapabilities
    positions: tuple[BrokerPositionSnapshot, ...]
    open_orders: tuple[BrokerOpenOrderSnapshot, ...]
    broker_data_version: str | None
    broker_data_cursor: str | None

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION or self.artifact_type != ACCOUNT_ARTIFACT_TYPE:
            raise BrokerSafetyModelError("unsupported account schema/artifact type")
        _uuid4("snapshot_id", self.snapshot_id)
        _clean("account_reference", self.account_reference)
        _clean("broker_id", self.broker_id)
        _exact_enum("environment", self.environment, BrokerEnvironment)
        retrieved = _timestamp("retrieved_at", self.retrieved_at)
        _clean("currency", self.currency, upper=True)
        _decimal("cash", self.cash)
        _decimal("buying_power", self.buying_power, nonnegative=True)
        _decimal("equity", self.equity)
        if type(self.capabilities) is not BrokerCapabilities:
            raise BrokerSafetyModelError("capabilities must be exact BrokerCapabilities")
        if (
            self.broker_id != self.capabilities.broker_id
            or self.environment is not self.capabilities.environment
            or self.currency != self.capabilities.currency
        ):
            raise BrokerSafetyModelError("account identities must match capabilities")
        if _timestamp("capabilities.observed_at", self.capabilities.observed_at) > retrieved:
            raise BrokerSafetyModelError("capabilities cannot be newer than account retrieval")
        _canonical_tuple("positions", self.positions, BrokerPositionSnapshot)
        _canonical_tuple("open_orders", self.open_orders, BrokerOpenOrderSnapshot)
        position_symbols = tuple(item.canonical_symbol for item in self.positions)
        if position_symbols != tuple(sorted(position_symbols)) or len(set(position_symbols)) != len(position_symbols):
            raise BrokerSafetyModelError("positions must be ordered by canonical symbol")
        broker_order_ids = tuple(item.broker_order_id for item in self.open_orders)
        if broker_order_ids != tuple(sorted(broker_order_ids)) or len(set(broker_order_ids)) != len(broker_order_ids):
            raise BrokerSafetyModelError("open orders must be ordered by broker order ID")
        client_ids = tuple(
            item.client_order_id for item in self.open_orders if item.client_order_id is not None
        )
        if len(set(client_ids)) != len(client_ids):
            raise BrokerSafetyModelError("non-null client order IDs must be unique")
        if any(_timestamp("position.as_of", item.as_of) > retrieved for item in self.positions):
            raise BrokerSafetyModelError("position timestamp cannot exceed retrieval")
        if any(
            _timestamp("order.last_broker_update", item.last_broker_update) > retrieved
            for item in self.open_orders
        ):
            raise BrokerSafetyModelError("open-order update cannot exceed retrieval")
        _optional_clean("broker_data_version", self.broker_data_version)
        _optional_clean("broker_data_cursor", self.broker_data_cursor)


@dataclass(frozen=True, slots=True)
class TradingSessionSnapshot:
    schema_version: str
    artifact_type: str
    session_snapshot_id: str
    market: str
    timezone_id: str
    session_date: str
    state: TradingSessionState
    submission_permissions: PermissionState
    cancel_permissions: PermissionState
    is_holiday: bool
    is_special_closure: bool
    is_early_close: bool
    source_id: str
    source_version: str
    as_of: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION or self.artifact_type != SESSION_ARTIFACT_TYPE:
            raise BrokerSafetyModelError("unsupported session schema/artifact type")
        _uuid4("session_snapshot_id", self.session_snapshot_id)
        _clean("market", self.market, upper=True)
        timezone_id = _clean("timezone_id", self.timezone_id)
        try:
            ZoneInfo(timezone_id)
        except ZoneInfoNotFoundError as exc:
            raise BrokerSafetyModelError("timezone_id must identify an installed timezone") from exc
        _date("session_date", self.session_date)
        _exact_enum("state", self.state, TradingSessionState)
        _exact_enum("submission_permissions", self.submission_permissions, PermissionState)
        _exact_enum("cancel_permissions", self.cancel_permissions, PermissionState)
        for name in ("is_holiday", "is_special_closure", "is_early_close"):
            if type(getattr(self, name)) is not bool:
                raise BrokerSafetyModelError(f"{name} must be an exact bool")
        if self.state in (TradingSessionState.UNKNOWN, TradingSessionState.CLOSED):
            if self.submission_permissions is PermissionState.PERMITTED:
                raise BrokerSafetyModelError("unknown/closed sessions cannot permit submission")
        if (self.is_holiday or self.is_special_closure) and self.state is not TradingSessionState.CLOSED:
            raise BrokerSafetyModelError("holiday/special closure requires CLOSED state")
        _clean("source_id", self.source_id)
        _clean("source_version", self.source_version)
        _timestamp("as_of", self.as_of)

    @property
    def submit_allowed(self) -> bool:
        return (
            self.state in (TradingSessionState.REGULAR, TradingSessionState.AUCTION_OR_PREOPEN)
            and self.submission_permissions is PermissionState.PERMITTED
        )


@dataclass(frozen=True, slots=True)
class BrokerSafetyPolicy:
    schema_version: str
    artifact_type: str
    policy_id: str
    policy_version: str
    currency: str
    allowed_broker_ids: tuple[str, ...]
    allowed_environments: tuple[BrokerEnvironment, ...]
    allowed_account_references: tuple[str, ...]
    allowed_markets: tuple[str, ...]
    allowed_order_types: tuple[OrderType, ...]
    maximum_order_notional: Decimal
    maximum_post_fill_account_exposure: Decimal
    maximum_per_symbol_exposure: Decimal
    maximum_per_symbol_quantity: Decimal
    maximum_simultaneous_open_orders: int
    maximum_daily_submitted_notional: Decimal
    maximum_daily_loss: Decimal
    snapshot_ttl_seconds: int
    reconciliation_ttl_seconds: int
    authorization_ttl_seconds: int
    initial_allocation_ceiling: Decimal
    required_capabilities: tuple[CapabilityName, ...]

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION or self.artifact_type != POLICY_ARTIFACT_TYPE:
            raise BrokerSafetyModelError("unsupported policy schema/artifact type")
        _clean("policy_id", self.policy_id)
        _clean("policy_version", self.policy_version)
        _clean("currency", self.currency, upper=True)
        _canonical_tuple("allowed_broker_ids", self.allowed_broker_ids, str)
        _canonical_tuple("allowed_environments", self.allowed_environments, BrokerEnvironment)
        _canonical_tuple("allowed_account_references", self.allowed_account_references, str)
        _canonical_tuple("allowed_markets", self.allowed_markets, str)
        _canonical_tuple("allowed_order_types", self.allowed_order_types, OrderType)
        _canonical_tuple("required_capabilities", self.required_capabilities, CapabilityName)
        for name in (
            "maximum_order_notional",
            "maximum_post_fill_account_exposure",
            "maximum_per_symbol_exposure",
            "maximum_per_symbol_quantity",
            "maximum_daily_submitted_notional",
            "maximum_daily_loss",
            "initial_allocation_ceiling",
        ):
            _decimal(name, getattr(self, name), nonnegative=True)
        for name in (
            "maximum_simultaneous_open_orders",
            "snapshot_ttl_seconds",
            "reconciliation_ttl_seconds",
            "authorization_ttl_seconds",
        ):
            _count(name, getattr(self, name))

    @classmethod
    def deny_all(
        cls,
        *,
        policy_id: str,
        policy_version: str,
        currency: str,
    ) -> BrokerSafetyPolicy:
        zero = Decimal("0")
        return cls(
            SCHEMA_VERSION,
            POLICY_ARTIFACT_TYPE,
            policy_id,
            policy_version,
            currency,
            (),
            (),
            (),
            (),
            (),
            zero,
            zero,
            zero,
            zero,
            0,
            zero,
            zero,
            0,
            0,
            0,
            zero,
            (),
        )


@dataclass(frozen=True, slots=True)
class BrokerSafetyFinding:
    code: FindingCode
    severity: FindingSeverity
    subject_type: FindingSubjectType
    subject_id: str
    observed: str | None
    expected: str | None
    message: str
    blocking: bool

    def __post_init__(self) -> None:
        _exact_enum("code", self.code, FindingCode)
        _exact_enum("severity", self.severity, FindingSeverity)
        _exact_enum("subject_type", self.subject_type, FindingSubjectType)
        _clean("subject_id", self.subject_id)
        _optional_clean("observed", self.observed)
        _optional_clean("expected", self.expected)
        _clean("message", self.message)
        if type(self.blocking) is not bool:
            raise BrokerSafetyModelError("blocking must be an exact bool")
        if self.blocking != (self.severity is FindingSeverity.ERROR):
            raise BrokerSafetyModelError("ERROR findings alone must be blocking")


@dataclass(frozen=True, slots=True)
class ExpectedPosition:
    canonical_symbol: str
    quantity: Decimal

    def __post_init__(self) -> None:
        _clean("canonical_symbol", self.canonical_symbol, upper=True)
        _decimal("quantity", self.quantity)


@dataclass(frozen=True, slots=True)
class ExpectedOpenOrder:
    broker_order_id: str | None
    client_order_id: str | None
    economic_intent_id: str
    canonical_symbol: str
    side: OrderSide
    original_quantity: Decimal

    def __post_init__(self) -> None:
        _optional_clean("broker_order_id", self.broker_order_id)
        _optional_clean("client_order_id", self.client_order_id)
        if self.broker_order_id is None and self.client_order_id is None:
            raise BrokerSafetyModelError("expected open order needs broker or client ID")
        _clean("economic_intent_id", self.economic_intent_id)
        _clean("canonical_symbol", self.canonical_symbol, upper=True)
        _exact_enum("side", self.side, OrderSide)
        _decimal("original_quantity", self.original_quantity, positive=True)


@dataclass(frozen=True, slots=True)
class ExpectedSubmission:
    local_submission_id: str
    client_order_id: str
    economic_intent_id: str
    canonical_symbol: str
    side: OrderSide
    original_quantity: Decimal
    reserved_notional: Decimal

    def __post_init__(self) -> None:
        _clean("local_submission_id", self.local_submission_id)
        _clean("client_order_id", self.client_order_id)
        _clean("economic_intent_id", self.economic_intent_id)
        _clean("canonical_symbol", self.canonical_symbol, upper=True)
        _exact_enum("side", self.side, OrderSide)
        _decimal("original_quantity", self.original_quantity, positive=True)
        _decimal("reserved_notional", self.reserved_notional, nonnegative=True)


@dataclass(frozen=True, slots=True)
class BrokerLocalExpectation:
    schema_version: str
    artifact_type: str
    local_state_version: str
    account_reference: str
    broker_id: str
    environment: BrokerEnvironment
    expected_positions: tuple[ExpectedPosition, ...]
    expected_open_orders: tuple[ExpectedOpenOrder, ...]
    expected_nonterminal_submissions: tuple[ExpectedSubmission, ...]
    daily_submitted_notional: Decimal
    daily_loss: Decimal | None
    daily_loss_reliability: FieldReliability
    last_reconciled_cursor: str | None

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION or self.artifact_type != EXPECTATION_ARTIFACT_TYPE:
            raise BrokerSafetyModelError("unsupported expectation schema/artifact type")
        _clean("local_state_version", self.local_state_version)
        _clean("account_reference", self.account_reference)
        _clean("broker_id", self.broker_id)
        _exact_enum("environment", self.environment, BrokerEnvironment)
        _canonical_tuple("expected_positions", self.expected_positions, ExpectedPosition)
        _canonical_tuple("expected_open_orders", self.expected_open_orders, ExpectedOpenOrder)
        _canonical_tuple(
            "expected_nonterminal_submissions",
            self.expected_nonterminal_submissions,
            ExpectedSubmission,
        )
        expected_symbols = tuple(item.canonical_symbol for item in self.expected_positions)
        if expected_symbols != tuple(sorted(expected_symbols)) or len(set(expected_symbols)) != len(expected_symbols):
            raise BrokerSafetyModelError("expected positions must be symbol ordered")
        open_keys = tuple(
            (item.client_order_id or "", item.broker_order_id or "")
            for item in self.expected_open_orders
        )
        if open_keys != tuple(sorted(open_keys)) or len(set(open_keys)) != len(open_keys):
            raise BrokerSafetyModelError("expected open orders must be unique and ordered")
        submission_ids = tuple(
            item.local_submission_id for item in self.expected_nonterminal_submissions
        )
        if submission_ids != tuple(sorted(submission_ids)) or len(set(submission_ids)) != len(submission_ids):
            raise BrokerSafetyModelError("expected submissions must be unique and ordered")
        client_ids = tuple(
            item.client_order_id
            for item in (*self.expected_open_orders, *self.expected_nonterminal_submissions)
            if item.client_order_id is not None
        )
        if len(client_ids) != len(set(client_ids)):
            raise BrokerSafetyModelError("known client order IDs must map once")
        _decimal("daily_submitted_notional", self.daily_submitted_notional, nonnegative=True)
        _reliable_decimal("daily_loss", self.daily_loss, self.daily_loss_reliability)
        if self.daily_loss is not None and self.daily_loss < 0:
            raise BrokerSafetyModelError("daily_loss must be a non-negative loss amount")
        _optional_clean("last_reconciled_cursor", self.last_reconciled_cursor)


@dataclass(frozen=True, slots=True)
class BrokerReconciliationResult:
    schema_version: str
    artifact_type: str
    reconciliation_id: str
    snapshot_id: str
    local_state_version: str
    account_reference: str
    broker_id: str
    environment: BrokerEnvironment
    findings: tuple[BrokerSafetyFinding, ...]
    completed_at: str
    is_reconciled: bool

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION or self.artifact_type != RECONCILIATION_ARTIFACT_TYPE:
            raise BrokerSafetyModelError("unsupported reconciliation schema/artifact type")
        _uuid4("reconciliation_id", self.reconciliation_id)
        _uuid4("snapshot_id", self.snapshot_id)
        _clean("local_state_version", self.local_state_version)
        _clean("account_reference", self.account_reference)
        _clean("broker_id", self.broker_id)
        _exact_enum("environment", self.environment, BrokerEnvironment)
        _canonical_tuple("findings", self.findings, BrokerSafetyFinding)
        finding_keys = tuple(
            (
                item.code.value,
                item.subject_type.value,
                item.subject_id,
                item.observed or "",
                item.expected or "",
                item.message,
            )
            for item in self.findings
        )
        if finding_keys != tuple(sorted(finding_keys)):
            raise BrokerSafetyModelError("findings must be canonically ordered")
        _timestamp("completed_at", self.completed_at)
        if type(self.is_reconciled) is not bool:
            raise BrokerSafetyModelError("is_reconciled must be an exact bool")
        if self.is_reconciled != (not any(item.blocking for item in self.findings)):
            raise BrokerSafetyModelError("is_reconciled must equal absence of blocking findings")


@dataclass(frozen=True, slots=True)
class BrokerLimitRequest:
    schema_version: str
    artifact_type: str
    canonical_symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    reference_price: Decimal
    projected_order_notional: Decimal
    current_daily_submitted_notional: Decimal
    current_daily_loss: Decimal | None
    daily_loss_reliability: FieldReliability
    broker_open_order_reserved_notional: Decimal
    unknown_submission_reserved_notional: Decimal
    unresolved_submission_count: int
    estimated_fees: Decimal | None
    estimated_taxes: Decimal | None
    currency: str
    is_initial_allocation: bool

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION or self.artifact_type != LIMIT_REQUEST_ARTIFACT_TYPE:
            raise BrokerSafetyModelError("unsupported limit-request schema/artifact type")
        _clean("canonical_symbol", self.canonical_symbol, upper=True)
        _exact_enum("side", self.side, OrderSide)
        _exact_enum("order_type", self.order_type, OrderType)
        quantity = _decimal("quantity", self.quantity, positive=True)
        price = _decimal("reference_price", self.reference_price, positive=True)
        notional = _decimal("projected_order_notional", self.projected_order_notional, positive=True)
        if notional != quantity * price:
            raise BrokerSafetyModelError("projected_order_notional must equal quantity * price")
        _decimal("current_daily_submitted_notional", self.current_daily_submitted_notional, nonnegative=True)
        _reliable_decimal("current_daily_loss", self.current_daily_loss, self.daily_loss_reliability)
        if self.current_daily_loss is not None and self.current_daily_loss < 0:
            raise BrokerSafetyModelError("current_daily_loss must be non-negative")
        _decimal(
            "broker_open_order_reserved_notional",
            self.broker_open_order_reserved_notional,
            nonnegative=True,
        )
        _decimal(
            "unknown_submission_reserved_notional",
            self.unknown_submission_reserved_notional,
            nonnegative=True,
        )
        _count("unresolved_submission_count", self.unresolved_submission_count)
        for name in ("estimated_fees", "estimated_taxes"):
            value = getattr(self, name)
            if value is not None:
                _decimal(name, value, nonnegative=True)
        _clean("currency", self.currency, upper=True)
        if type(self.is_initial_allocation) is not bool:
            raise BrokerSafetyModelError("is_initial_allocation must be an exact bool")


__all__ = [name for name in globals() if not name.startswith("_")]
