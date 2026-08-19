"""Phase 56.5D0 broker-neutral pre-mutation readiness contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from tw_stock_tool.broker_safety.models import (
    BrokerEnvironment,
    OrderSide,
    OrderType,
    TimeInForce,
)


D0_READINESS_SCHEMA_VERSION = "broker-test-execution-readiness-v1"


class D0ReadinessModelError(ValueError):
    """Raised when a D0 audit or readiness result is not exact and canonical."""


class D0ReadinessOutcome(StrEnum):
    READY_FOR_56_5D = "READY_FOR_56_5D"
    BLOCKED = "BLOCKED"


class D0RequirementState(StrEnum):
    PROVEN = "PROVEN"
    BLOCKED = "BLOCKED"


class SafetyFactUsage(StrEnum):
    REQUIRED_FOR_SAFETY_DECISION = "REQUIRED_FOR_SAFETY_DECISION"
    REQUIRED_FOR_RECONCILIATION_ONLY = "REQUIRED_FOR_RECONCILIATION_ONLY"
    OPTIONAL_OBSERVABILITY = "OPTIONAL_OBSERVABILITY"
    UNUSED_IN_CURRENT_GATE = "UNUSED_IN_CURRENT_GATE"


class SafetyPathFact(StrEnum):
    CASH = "cash"
    BUYING_POWER = "buying_power"
    EQUITY = "equity"
    POSITIONS_QUANTITY = "positions.quantity"
    POSITIONS_AVAILABLE_QUANTITY = "positions.available_quantity"
    POSITIONS_MARKET_VALUE = "positions.market_value"
    OPEN_ORDERS = "open_orders"
    CAPABILITIES = "capabilities"
    SESSION = "session"
    RECONCILIATION = "reconciliation"
    LOCAL_RESERVED_EXPOSURE = "local_reserved_exposure"
    DAILY_SUBMITTED_NOTIONAL = "daily_submitted_notional"
    DAILY_LOSS = "daily_loss"
    FEES_TAXES = "fees_taxes"


class D0PrerequisiteName(StrEnum):
    OFFICIAL_TEST_PROVENANCE = "OFFICIAL_TEST_PROVENANCE"
    REVIEWED_SDK_PROVIDER_CONTRACT = "REVIEWED_SDK_PROVIDER_CONTRACT"
    ACCOUNT_CAPITAL_AUTHORITY = "ACCOUNT_CAPITAL_AUTHORITY"
    POSITION_OPEN_ORDER_RECONCILIATION = "POSITION_OPEN_ORDER_RECONCILIATION"
    POSITION_VALUATION_EXPOSURE_AUTHORITY = "POSITION_VALUATION_EXPOSURE_AUTHORITY"
    TRADING_PERMISSION_PROOF = "TRADING_PERMISSION_PROOF"
    FEE_TAX_AUTHORITY = "FEE_TAX_AUTHORITY"
    CLIENT_CORRELATION_LOST_ACK_SAFETY = "CLIENT_CORRELATION_LOST_ACK_SAFETY"
    SESSION_PROOF = "SESSION_PROOF"
    DURABLE_ONE_SHOT_PRE_SUBMIT = "DURABLE_ONE_SHOT_PRE_SUBMIT"
    NO_LIVE_ENDPOINT = "NO_LIVE_ENDPOINT"


class CapitalAuthorityModel(StrEnum):
    PROVIDER_BUYING_POWER = "PROVIDER_BUYING_POWER"
    CONSERVATIVE_SPENDABLE_CASH_LOWER_BOUND = "CONSERVATIVE_SPENDABLE_CASH_LOWER_BOUND"
    UNPROVEN = "UNPROVEN"


class D0BlockReason(StrEnum):
    ACCOUNT_CAPITAL_AUTHORITY_UNPROVEN = "ACCOUNT_CAPITAL_AUTHORITY_UNPROVEN"
    POSITION_VALUATION_AUTHORITY_UNPROVEN = "POSITION_VALUATION_AUTHORITY_UNPROVEN"
    TRADING_PERMISSION_UNPROVEN = "TRADING_PERMISSION_UNPROVEN"
    FEE_TAX_AUTHORITY_UNPROVEN = "FEE_TAX_AUTHORITY_UNPROVEN"
    CLIENT_CORRELATION_QUERY_UNPROVEN = "CLIENT_CORRELATION_QUERY_UNPROVEN"
    SESSION_PROOF_UNPROVEN = "SESSION_PROOF_UNPROVEN"


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise D0ReadinessModelError(f"{name} must be an exact non-empty string")
    return value


def _enum(name: str, value: object, expected: type[StrEnum]) -> None:
    if type(value) is not expected:
        raise D0ReadinessModelError(f"{name} must be exact {expected.__name__}")


def _canonical_tuple(name: str, value: object, expected: type) -> tuple:
    if type(value) is not tuple or not value or any(type(item) is not expected for item in value):
        raise D0ReadinessModelError(f"{name} must be a non-empty exact tuple of {expected.__name__}")
    if expected is str or issubclass(expected, StrEnum):
        keys = tuple(item.value if isinstance(item, StrEnum) else item for item in value)
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise D0ReadinessModelError(f"{name} must be unique and canonically ordered")
    elif len(set(value)) != len(value):
        raise D0ReadinessModelError(f"{name} must not contain exact duplicates")
    return value


@dataclass(frozen=True, slots=True)
class BrokerSafetyPathFact:
    """One verified field traversal through the existing v1 safety path."""

    fact: SafetyPathFact
    usage: SafetyFactUsage
    consumed_by: tuple[str, ...]
    safety_property: str

    def __post_init__(self) -> None:
        _enum("fact", self.fact, SafetyPathFact)
        _enum("usage", self.usage, SafetyFactUsage)
        _canonical_tuple("consumed_by", self.consumed_by, str)
        _text("safety_property", self.safety_property)


@dataclass(frozen=True, slots=True)
class D0PrerequisiteStatus:
    """Reviewed authority state for one indivisible pre-mutation requirement."""

    name: D0PrerequisiteName
    state: D0RequirementState
    authority: str
    reason: str

    def __post_init__(self) -> None:
        _enum("name", self.name, D0PrerequisiteName)
        _enum("state", self.state, D0RequirementState)
        _text("authority", self.authority)
        _text("reason", self.reason)


@dataclass(frozen=True, slots=True)
class CapitalAuthorityProof:
    """Exact obligations for any conservative BUY capital authority."""

    model: CapitalAuthorityModel
    same_account_twd_cash: D0RequirementState
    settlements_complete_without_double_counting: D0RequirementState
    broker_open_buy_exposure_complete: D0RequirementState
    local_unresolved_reservations_complete: D0RequirementState
    conservative_fees_and_taxes: D0RequirementState
    no_credit_assumptions: D0RequirementState
    anomalies_fail_closed: D0RequirementState
    cannot_overstate_available_capital: D0RequirementState
    formula: str

    def __post_init__(self) -> None:
        _enum("model", self.model, CapitalAuthorityModel)
        states = (
            self.same_account_twd_cash,
            self.settlements_complete_without_double_counting,
            self.broker_open_buy_exposure_complete,
            self.local_unresolved_reservations_complete,
            self.conservative_fees_and_taxes,
            self.no_credit_assumptions,
            self.anomalies_fail_closed,
            self.cannot_overstate_available_capital,
        )
        if any(type(item) is not D0RequirementState for item in states):
            raise D0ReadinessModelError("capital obligations must be exact typed states")
        _text("formula", self.formula)
        all_proven = all(item is D0RequirementState.PROVEN for item in states)
        if (self.model is CapitalAuthorityModel.UNPROVEN) == all_proven:
            raise D0ReadinessModelError("capital model must agree with every proof obligation")

    @property
    def state(self) -> D0RequirementState:
        return (
            D0RequirementState.BLOCKED
            if self.model is CapitalAuthorityModel.UNPROVEN
            else D0RequirementState.PROVEN
        )


@dataclass(frozen=True, slots=True)
class MinimumTestExecutionProfile:
    """Narrow broker-neutral candidate profile; this grants no mutation authority."""

    environment: BrokerEnvironment
    endpoint: str
    product: str
    trade_mode: str
    allowed_sides: tuple[OrderSide, ...]
    sell_rule: str
    lot_mode: str
    allowed_order_types: tuple[OrderType, ...]
    allowed_time_in_force: tuple[TimeInForce, ...]
    forbidden_features: tuple[str, ...]

    def __post_init__(self) -> None:
        _enum("environment", self.environment, BrokerEnvironment)
        for name in ("endpoint", "product", "trade_mode", "sell_rule", "lot_mode"):
            _text(name, getattr(self, name))
        _canonical_tuple("allowed_sides", self.allowed_sides, OrderSide)
        _canonical_tuple("allowed_order_types", self.allowed_order_types, OrderType)
        _canonical_tuple("allowed_time_in_force", self.allowed_time_in_force, TimeInForce)
        _canonical_tuple("forbidden_features", self.forbidden_features, str)
        if self.environment is not BrokerEnvironment.SANDBOX:
            raise D0ReadinessModelError("the D0 candidate profile must be SANDBOX-only")

    def accepts(
        self,
        *,
        product: str,
        trade_mode: str,
        side: OrderSide,
        lot_mode: str,
        order_type: OrderType,
        time_in_force: TimeInForce,
        owned_available_quantity: bool,
    ) -> bool:
        """Return whether economic facts remain inside the frozen profile."""

        return (
            product == self.product
            and trade_mode == self.trade_mode
            and type(side) is OrderSide
            and side in self.allowed_sides
            and lot_mode == self.lot_mode
            and type(order_type) is OrderType
            and order_type in self.allowed_order_types
            and type(time_in_force) is TimeInForce
            and time_in_force in self.allowed_time_in_force
            and (side is not OrderSide.SELL or owned_available_quantity is True)
        )


def derive_d0_outcome(
    prerequisites: tuple[D0PrerequisiteStatus, ...],
) -> D0ReadinessOutcome:
    """Derive readiness only from a complete, unique typed prerequisite set."""

    _canonical_tuple("prerequisites", prerequisites, D0PrerequisiteStatus)
    names = tuple(item.name for item in prerequisites)
    expected = tuple(sorted(D0PrerequisiteName, key=lambda item: item.value))
    if names != expected:
        raise D0ReadinessModelError("prerequisites must cover the exact D0 requirement set")
    return (
        D0ReadinessOutcome.READY_FOR_56_5D
        if all(item.state is D0RequirementState.PROVEN for item in prerequisites)
        else D0ReadinessOutcome.BLOCKED
    )


__all__ = [
    "D0_READINESS_SCHEMA_VERSION",
    "BrokerSafetyPathFact",
    "CapitalAuthorityModel",
    "CapitalAuthorityProof",
    "D0BlockReason",
    "D0PrerequisiteName",
    "D0PrerequisiteStatus",
    "D0ReadinessModelError",
    "D0ReadinessOutcome",
    "D0RequirementState",
    "MinimumTestExecutionProfile",
    "SafetyFactUsage",
    "SafetyPathFact",
    "derive_d0_outcome",
]
