"""Immutable Phase 56.5A4 authorization, intent, and lifecycle facts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
import hashlib
import json
import re

from tw_stock_tool.broker_safety.models import (
    BrokerEnvironment,
    BrokerSafetyModelError,
    OrderSide,
    OrderType,
    TimeInForce,
    _canonical_tuple,
    _clean,
    _count,
    _date,
    _decimal,
    _exact_enum,
    _optional_clean,
    _timestamp,
    _uuid4,
)


A4_SCHEMA_VERSION = "1.0"
KILL_SWITCH_ARTIFACT_TYPE = "broker_kill_switch_snapshot"
AUTHORIZATION_ARTIFACT_TYPE = "broker_execution_authorization"
AUTHORIZATION_USE_ARTIFACT_TYPE = "broker_authorization_use_record"
ORDER_INTENT_ARTIFACT_TYPE = "broker_order_intent"
SUBMISSION_ARTIFACT_TYPE = "broker_submission_record"
EXECUTION_ARTIFACT_TYPE = "broker_execution_record"
INTENT_KEY_PREFIX = "broker_order_intent_key_v1:"
CLIENT_ORDER_ID_PREFIX = "twst1-"
CANONICAL_CLIENT_ORDER_ID_LENGTH = len(CLIENT_ORDER_ID_PREFIX) + 64
AUTHORIZATION_USE_PERSISTENCE_NOTICE = (
    "Pure authorization-use and submission transitions do not prove durable or "
    "cross-process uniqueness; the account-scoped constraint remains Phase 56.5C."
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class BrokerA4ModelError(BrokerSafetyModelError):
    """Raised when an A4 fact violates its frozen contract."""


class BrokerPersistentEncodingRequiredError(BrokerA4ModelError):
    """Raised when full client identity needs a future persistent encoding map."""


class KillSwitchState(StrEnum):
    UNKNOWN = "UNKNOWN"
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"


class AuthorizationUseState(StrEnum):
    RESERVED = "RESERVED"
    CONSUMED = "CONSUMED"
    ABANDONED = "ABANDONED"


class QuantityMode(StrEnum):
    QUANTITY = "QUANTITY"
    NOTIONAL = "NOTIONAL"


class BrokerSubmissionState(StrEnum):
    PREPARED = "PREPARED"
    AUTHORIZED = "AUTHORIZED"
    SUBMITTING = "SUBMITTING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNKNOWN_SUBMISSION_STATE = "UNKNOWN_SUBMISSION_STATE"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class BrokerSubmissionEvidence(StrEnum):
    AUTHORIZATION_GATE = "AUTHORIZATION_GATE"
    SUBMIT_REQUEST = "SUBMIT_REQUEST"
    BROKER_ACK = "BROKER_ACK"
    BROKER_REJECTION = "BROKER_REJECTION"
    AMBIGUOUS_OUTCOME = "AMBIGUOUS_OUTCOME"
    CANCEL_REQUEST = "CANCEL_REQUEST"
    BROKER_CANCELLATION = "BROKER_CANCELLATION"
    BROKER_EXPIRATION = "BROKER_EXPIRATION"


def _sha(name: str, value: object) -> str:
    text = _clean(name, value)
    if _SHA256.fullmatch(text) is None:
        raise BrokerA4ModelError(f"{name} must be a lowercase SHA-256")
    return text


def _optional_timestamp(name: str, value: str | None) -> None:
    if value is not None:
        _timestamp(name, value)


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _stable_key_digest(value: object) -> str:
    text = _clean("idempotency_key", value)
    if not text.startswith(INTENT_KEY_PREFIX):
        raise BrokerA4ModelError("idempotency_key has the wrong versioned prefix")
    return _sha("idempotency_key digest", text[len(INTENT_KEY_PREFIX):])


def _canonical_client_order_id(value: object) -> str:
    text = _clean("canonical_client_order_id", value)
    if not text.startswith(CLIENT_ORDER_ID_PREFIX):
        raise BrokerA4ModelError("canonical client order ID has the wrong prefix")
    _sha("canonical client order ID digest", text[len(CLIENT_ORDER_ID_PREFIX):])
    return text


@dataclass(frozen=True, slots=True)
class BrokerKillSwitchSnapshot:
    schema_version: str
    artifact_type: str
    kill_switch_version: str
    account_reference: str
    broker_id: str
    environment: BrokerEnvironment
    stop_new_orders_state: KillSwitchState
    cancel_open_orders_state: KillSwitchState
    liquidate_positions_state: KillSwitchState
    reason: str | None
    observed_at: str
    source_id: str

    def __post_init__(self) -> None:
        if self.schema_version != A4_SCHEMA_VERSION or self.artifact_type != KILL_SWITCH_ARTIFACT_TYPE:
            raise BrokerA4ModelError("unsupported kill-switch schema/artifact type")
        for name in ("kill_switch_version", "account_reference", "broker_id", "source_id"):
            _clean(name, getattr(self, name))
        _exact_enum("environment", self.environment, BrokerEnvironment)
        for name in (
            "stop_new_orders_state",
            "cancel_open_orders_state",
            "liquidate_positions_state",
        ):
            _exact_enum(name, getattr(self, name), KillSwitchState)
        _optional_clean("reason", self.reason)
        _timestamp("observed_at", self.observed_at)


@dataclass(frozen=True, slots=True)
class BrokerExecutionAuthorization:
    schema_version: str
    artifact_type: str
    authorization_id: str
    account_reference: str
    broker_id: str
    environment: BrokerEnvironment
    source_workspace_run_id: str
    publication_id: str
    publication_index_sha256: str
    activation_id: str
    qualification_evaluation_id: str
    strategy_id: str
    eligibility_id: str
    eligibility_policy_id: str
    eligibility_policy_version: str
    current_lineage_head_fingerprint: str
    progression_fingerprint: str
    ledger_id: str
    recommendation_id: str
    recommendation_sha256: str
    reconciliation_id: str
    snapshot_id: str
    local_state_version: str
    broker_safety_policy_id: str
    broker_safety_policy_version: str
    allowed_symbols: tuple[str, ...]
    allowed_side: OrderSide
    allowed_order_types: tuple[OrderType, ...]
    allowed_time_in_force: tuple[TimeInForce, ...]
    maximum_quantity: Decimal
    maximum_notional: Decimal
    currency: str
    session_date: str
    not_before: str
    expires_at: str
    approved_at: str
    approver_identity_ref: str
    kill_switch_version: str

    def __post_init__(self) -> None:
        if self.schema_version != A4_SCHEMA_VERSION or self.artifact_type != AUTHORIZATION_ARTIFACT_TYPE:
            raise BrokerA4ModelError("unsupported authorization schema/artifact type")
        for name in (
            "authorization_id",
            "source_workspace_run_id",
            "publication_id",
            "activation_id",
            "qualification_evaluation_id",
            "eligibility_id",
            "ledger_id",
            "recommendation_id",
            "reconciliation_id",
            "snapshot_id",
        ):
            _uuid4(name, getattr(self, name))
        for name in (
            "publication_index_sha256",
            "current_lineage_head_fingerprint",
            "progression_fingerprint",
            "recommendation_sha256",
        ):
            _sha(name, getattr(self, name))
        for name in (
            "account_reference",
            "broker_id",
            "strategy_id",
            "eligibility_policy_id",
            "eligibility_policy_version",
            "local_state_version",
            "broker_safety_policy_id",
            "broker_safety_policy_version",
            "approver_identity_ref",
            "kill_switch_version",
        ):
            _clean(name, getattr(self, name))
        _exact_enum("environment", self.environment, BrokerEnvironment)
        _canonical_tuple("allowed_symbols", self.allowed_symbols, str, allow_empty=False)
        if any(symbol != symbol.upper() for symbol in self.allowed_symbols):
            raise BrokerA4ModelError("allowed_symbols must be uppercase canonical symbols")
        _exact_enum("allowed_side", self.allowed_side, OrderSide)
        _canonical_tuple("allowed_order_types", self.allowed_order_types, OrderType, allow_empty=False)
        _canonical_tuple("allowed_time_in_force", self.allowed_time_in_force, TimeInForce, allow_empty=False)
        _decimal("maximum_quantity", self.maximum_quantity, positive=True)
        _decimal("maximum_notional", self.maximum_notional, positive=True)
        _clean("currency", self.currency, upper=True)
        _date("session_date", self.session_date)
        approved = _timestamp("approved_at", self.approved_at)
        not_before = _timestamp("not_before", self.not_before)
        expires = _timestamp("expires_at", self.expires_at)
        if not (approved <= not_before < expires):
            raise BrokerA4ModelError("authorization chronology must be approved_at <= not_before < expires_at")


@dataclass(frozen=True, slots=True)
class BrokerAuthorizationUseRecord:
    schema_version: str
    artifact_type: str
    authorization_use_id: str
    authorization_id: str
    account_reference: str
    environment: BrokerEnvironment
    economic_intent_id: str
    idempotency_key: str
    state: AuthorizationUseState
    reserved_at: str
    consumed_at: str | None
    abandoned_at: str | None
    reason: str | None

    def __post_init__(self) -> None:
        if self.schema_version != A4_SCHEMA_VERSION or self.artifact_type != AUTHORIZATION_USE_ARTIFACT_TYPE:
            raise BrokerA4ModelError("unsupported authorization-use schema/artifact type")
        for name in ("authorization_use_id", "authorization_id", "economic_intent_id"):
            _uuid4(name, getattr(self, name))
        _clean("account_reference", self.account_reference)
        _exact_enum("environment", self.environment, BrokerEnvironment)
        _stable_key_digest(self.idempotency_key)
        _exact_enum("state", self.state, AuthorizationUseState)
        reserved = _timestamp("reserved_at", self.reserved_at)
        _optional_timestamp("consumed_at", self.consumed_at)
        _optional_timestamp("abandoned_at", self.abandoned_at)
        _optional_clean("reason", self.reason)
        if self.state is AuthorizationUseState.RESERVED:
            if self.consumed_at is not None or self.abandoned_at is not None:
                raise BrokerA4ModelError("RESERVED use record cannot have a terminal timestamp")
        elif self.state is AuthorizationUseState.CONSUMED:
            if self.consumed_at is None or self.abandoned_at is not None:
                raise BrokerA4ModelError("CONSUMED use record requires only consumed_at")
            if _timestamp("consumed_at", self.consumed_at) < reserved:
                raise BrokerA4ModelError("consumed_at cannot precede reserved_at")
        elif self.abandoned_at is None or self.consumed_at is not None:
            raise BrokerA4ModelError("ABANDONED use record requires only abandoned_at")
        elif _timestamp("abandoned_at", self.abandoned_at) < reserved:
            raise BrokerA4ModelError("abandoned_at cannot precede reserved_at")


@dataclass(frozen=True, slots=True)
class BrokerOrderIntentKeyPayload:
    schema_version: str
    account_reference: str
    environment_identity: BrokerEnvironment
    publication_id: str
    publication_index_sha256: str
    current_lineage_head_fingerprint: str
    ledger_id: str
    recommendation_id: str
    recommendation_sha256: str
    canonical_symbol: str
    side: OrderSide
    quantity_mode: QuantityMode
    quantity_or_notional: Decimal
    order_type: OrderType
    limit_price_if_any: Decimal | None
    time_in_force: TimeInForce
    execution_session_date: str
    intent_revision: int

    def __post_init__(self) -> None:
        if self.schema_version != A4_SCHEMA_VERSION:
            raise BrokerA4ModelError("unsupported intent-key schema_version")
        _clean("account_reference", self.account_reference)
        _exact_enum("environment_identity", self.environment_identity, BrokerEnvironment)
        for name in ("publication_id", "ledger_id", "recommendation_id"):
            _uuid4(name, getattr(self, name))
        for name in (
            "publication_index_sha256",
            "current_lineage_head_fingerprint",
            "recommendation_sha256",
        ):
            _sha(name, getattr(self, name))
        _clean("canonical_symbol", self.canonical_symbol, upper=True)
        _exact_enum("side", self.side, OrderSide)
        _exact_enum("quantity_mode", self.quantity_mode, QuantityMode)
        _decimal("quantity_or_notional", self.quantity_or_notional, positive=True)
        _exact_enum("order_type", self.order_type, OrderType)
        if self.limit_price_if_any is not None:
            _decimal("limit_price_if_any", self.limit_price_if_any, positive=True)
        if self.order_type in (OrderType.STOP, OrderType.STOP_LIMIT):
            raise BrokerA4ModelError("STOP and STOP_LIMIT require a future trigger-price contract")
        if self.order_type is OrderType.LIMIT:
            if self.limit_price_if_any is None:
                raise BrokerA4ModelError("LIMIT keys require an exact price")
        elif self.limit_price_if_any is not None:
            raise BrokerA4ModelError("non-limit keys cannot carry a limit price")
        elif self.quantity_mode is QuantityMode.NOTIONAL:
            raise BrokerA4ModelError("unpriced NOTIONAL intent requires a future reviewed conversion contract")
        _exact_enum("time_in_force", self.time_in_force, TimeInForce)
        _date("execution_session_date", self.execution_session_date)
        _count("intent_revision", self.intent_revision)


def derive_broker_order_intent_key_v1(payload: BrokerOrderIntentKeyPayload) -> str:
    """Derive the exact stable economic key; no runtime metadata is accepted."""
    if type(payload) is not BrokerOrderIntentKeyPayload:
        raise BrokerA4ModelError("payload must be exact BrokerOrderIntentKeyPayload")
    canonical = {
        "account_reference": payload.account_reference,
        "canonical_symbol": payload.canonical_symbol,
        "current_lineage_head_fingerprint": payload.current_lineage_head_fingerprint,
        "environment_identity": payload.environment_identity.value,
        "execution_session_date": payload.execution_session_date,
        "intent_revision": payload.intent_revision,
        "ledger_id": payload.ledger_id,
        "limit_price_if_any": None if payload.limit_price_if_any is None else _decimal_text(payload.limit_price_if_any),
        "order_type": payload.order_type.value,
        "publication_id": payload.publication_id,
        "publication_index_sha256": payload.publication_index_sha256,
        "quantity_mode": payload.quantity_mode.value,
        "quantity_or_notional": _decimal_text(payload.quantity_or_notional),
        "recommendation_id": payload.recommendation_id,
        "recommendation_sha256": payload.recommendation_sha256,
        "schema_version": payload.schema_version,
        "side": payload.side.value,
        "time_in_force": payload.time_in_force.value,
    }
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return INTENT_KEY_PREFIX + hashlib.sha256(encoded).hexdigest()


def canonical_broker_client_order_id(
    idempotency_key: str,
    *,
    broker_max_length: int | None = None,
) -> str:
    """Return the full canonical ID or require a future persistent encoding map."""
    digest = _stable_key_digest(idempotency_key)
    if broker_max_length is not None:
        if type(broker_max_length) is not int or broker_max_length <= 0:
            raise BrokerA4ModelError("broker_max_length must be an exact positive int")
        if broker_max_length < CANONICAL_CLIENT_ORDER_ID_LENGTH:
            raise BrokerPersistentEncodingRequiredError(
                "PERSISTENT_ENCODING_REQUIRED: broker maximum cannot fit the full canonical client ID"
            )
    return CLIENT_ORDER_ID_PREFIX + digest


@dataclass(frozen=True, slots=True)
class BrokerOrderIntent:
    schema_version: str
    artifact_type: str
    economic_intent_id: str
    idempotency_key: str
    canonical_client_order_id: str
    authorization_id: str
    source_workspace_run_id: str
    publication_id: str
    publication_index_sha256: str
    current_lineage_head_fingerprint: str
    progression_fingerprint: str
    ledger_id: str
    recommendation_id: str
    recommendation_sha256: str
    account_reference: str
    broker_id: str
    environment: BrokerEnvironment
    session_date: str
    canonical_symbol: str
    side: OrderSide
    quantity_mode: QuantityMode
    quantity: Decimal
    notional: Decimal
    order_type: OrderType
    time_in_force: TimeInForce
    limit_price: Decimal | None
    currency: str
    created_at: str
    intent_revision: int

    def __post_init__(self) -> None:
        if self.schema_version != A4_SCHEMA_VERSION or self.artifact_type != ORDER_INTENT_ARTIFACT_TYPE:
            raise BrokerA4ModelError("unsupported order-intent schema/artifact type")
        for name in (
            "economic_intent_id",
            "authorization_id",
            "source_workspace_run_id",
            "publication_id",
            "ledger_id",
            "recommendation_id",
        ):
            _uuid4(name, getattr(self, name))
        for name in (
            "publication_index_sha256",
            "current_lineage_head_fingerprint",
            "progression_fingerprint",
            "recommendation_sha256",
        ):
            _sha(name, getattr(self, name))
        _clean("account_reference", self.account_reference)
        _clean("broker_id", self.broker_id)
        _exact_enum("environment", self.environment, BrokerEnvironment)
        _date("session_date", self.session_date)
        _clean("canonical_symbol", self.canonical_symbol, upper=True)
        _exact_enum("side", self.side, OrderSide)
        _exact_enum("quantity_mode", self.quantity_mode, QuantityMode)
        _decimal("quantity", self.quantity, positive=True)
        _decimal("notional", self.notional, positive=True)
        _exact_enum("order_type", self.order_type, OrderType)
        _exact_enum("time_in_force", self.time_in_force, TimeInForce)
        if self.limit_price is not None:
            _decimal("limit_price", self.limit_price, positive=True)
        if self.order_type in (OrderType.STOP, OrderType.STOP_LIMIT):
            raise BrokerA4ModelError("STOP and STOP_LIMIT require a future trigger-price contract")
        if self.order_type is OrderType.LIMIT:
            if self.limit_price is None:
                raise BrokerA4ModelError("LIMIT intents require limit_price")
            if self.notional != self.quantity * self.limit_price:
                raise BrokerA4ModelError("priced intent notional must equal quantity times limit price")
        elif self.limit_price is not None:
            raise BrokerA4ModelError("non-limit intent cannot carry limit_price")
        elif self.quantity_mode is QuantityMode.NOTIONAL:
            raise BrokerA4ModelError("unpriced NOTIONAL intent requires a future reviewed conversion contract")
        _clean("currency", self.currency, upper=True)
        _timestamp("created_at", self.created_at)
        _count("intent_revision", self.intent_revision)
        payload = BrokerOrderIntentKeyPayload(
            schema_version=A4_SCHEMA_VERSION,
            account_reference=self.account_reference,
            environment_identity=self.environment,
            publication_id=self.publication_id,
            publication_index_sha256=self.publication_index_sha256,
            current_lineage_head_fingerprint=self.current_lineage_head_fingerprint,
            ledger_id=self.ledger_id,
            recommendation_id=self.recommendation_id,
            recommendation_sha256=self.recommendation_sha256,
            canonical_symbol=self.canonical_symbol,
            side=self.side,
            quantity_mode=self.quantity_mode,
            quantity_or_notional=(
                self.quantity
                if self.quantity_mode is QuantityMode.QUANTITY
                else self.notional
            ),
            order_type=self.order_type,
            limit_price_if_any=self.limit_price,
            time_in_force=self.time_in_force,
            execution_session_date=self.session_date,
            intent_revision=self.intent_revision,
        )
        expected_key = derive_broker_order_intent_key_v1(payload)
        if self.idempotency_key != expected_key:
            raise BrokerA4ModelError("idempotency_key does not match canonical economic facts")
        expected_client_id = canonical_broker_client_order_id(expected_key)
        if self.canonical_client_order_id != expected_client_id:
            raise BrokerA4ModelError("canonical_client_order_id does not match idempotency key")


@dataclass(frozen=True, slots=True)
class BrokerSubmissionRecord:
    schema_version: str
    artifact_type: str
    intent_id: str
    attempt_id: str
    state: BrokerSubmissionState
    stable_client_order_id: str
    broker_order_id: str | None
    pre_submit_persistence_version: str | None
    request_timestamp: str | None
    ack_timestamp: str | None
    sanitized_outcome: str | None
    last_reconciliation_id: str | None
    cumulative_filled_quantity: Decimal
    remaining_quantity: Decimal
    execution_ids: tuple[str, ...]
    recorded_at: str

    def __post_init__(self) -> None:
        if self.schema_version != A4_SCHEMA_VERSION or self.artifact_type != SUBMISSION_ARTIFACT_TYPE:
            raise BrokerA4ModelError("unsupported submission schema/artifact type")
        _uuid4("intent_id", self.intent_id)
        _uuid4("attempt_id", self.attempt_id)
        _exact_enum("state", self.state, BrokerSubmissionState)
        _canonical_client_order_id(self.stable_client_order_id)
        _optional_clean("broker_order_id", self.broker_order_id)
        _optional_clean("pre_submit_persistence_version", self.pre_submit_persistence_version)
        _optional_timestamp("request_timestamp", self.request_timestamp)
        _optional_timestamp("ack_timestamp", self.ack_timestamp)
        _optional_clean("sanitized_outcome", self.sanitized_outcome)
        if self.last_reconciliation_id is not None:
            _uuid4("last_reconciliation_id", self.last_reconciliation_id)
        filled = _decimal("cumulative_filled_quantity", self.cumulative_filled_quantity, nonnegative=True)
        remaining = _decimal("remaining_quantity", self.remaining_quantity, nonnegative=True)
        if filled + remaining <= 0:
            raise BrokerA4ModelError("submission total quantity must be positive")
        _canonical_tuple("execution_ids", self.execution_ids, str)
        for execution_id in self.execution_ids:
            _clean("execution_id", execution_id)
        if (filled == 0) != (not self.execution_ids):
            raise BrokerA4ModelError("execution IDs must exactly reflect whether fills exist")
        recorded = _timestamp("recorded_at", self.recorded_at)
        if self.request_timestamp is not None and _timestamp("request_timestamp", self.request_timestamp) > recorded:
            raise BrokerA4ModelError("request timestamp cannot exceed recorded_at")
        if self.ack_timestamp is not None:
            ack = _timestamp("ack_timestamp", self.ack_timestamp)
            if self.request_timestamp is None or ack < _timestamp("request_timestamp", self.request_timestamp) or ack > recorded:
                raise BrokerA4ModelError("ack timestamp must follow request and not exceed recorded_at")
        before_submit = self.state in (BrokerSubmissionState.PREPARED, BrokerSubmissionState.AUTHORIZED)
        if before_submit:
            if any(value is not None for value in (self.broker_order_id, self.pre_submit_persistence_version, self.request_timestamp, self.ack_timestamp)):
                raise BrokerA4ModelError("pre-submit states cannot contain submit/ack evidence")
        elif self.pre_submit_persistence_version is None or self.request_timestamp is None:
            raise BrokerA4ModelError("submitted states require persistence version and request timestamp")
        broker_known_states = (
            BrokerSubmissionState.ACKNOWLEDGED,
            BrokerSubmissionState.PARTIALLY_FILLED,
            BrokerSubmissionState.FILLED,
            BrokerSubmissionState.CANCEL_PENDING,
            BrokerSubmissionState.CANCELLED,
            BrokerSubmissionState.EXPIRED,
        )
        if self.state in broker_known_states and (self.broker_order_id is None or self.ack_timestamp is None):
            raise BrokerA4ModelError("broker-correlated states require broker ID and ack timestamp")
        if self.state in (BrokerSubmissionState.PREPARED, BrokerSubmissionState.AUTHORIZED, BrokerSubmissionState.SUBMITTING, BrokerSubmissionState.ACKNOWLEDGED, BrokerSubmissionState.REJECTED) and filled != 0:
            raise BrokerA4ModelError("state cannot carry cumulative fills")
        if self.state is BrokerSubmissionState.PARTIALLY_FILLED and (filled == 0 or remaining == 0):
            raise BrokerA4ModelError("PARTIALLY_FILLED requires positive filled and remaining quantities")
        if self.state is BrokerSubmissionState.FILLED and (filled == 0 or remaining != 0):
            raise BrokerA4ModelError("FILLED requires positive cumulative fill and zero remaining")
        if self.state is BrokerSubmissionState.CANCEL_PENDING and remaining == 0:
            raise BrokerA4ModelError("CANCEL_PENDING must retain remaining exposure")


@dataclass(frozen=True, slots=True)
class BrokerExecutionRecord:
    schema_version: str
    artifact_type: str
    broker_order_id: str
    execution_id: str
    intent_id: str
    attempt_id: str
    fill_quantity: Decimal
    fill_price: Decimal
    fill_time: str
    incremental_fee: Decimal | None
    incremental_tax: Decimal | None
    cumulative_quantity: Decimal
    received_at: str

    def __post_init__(self) -> None:
        if self.schema_version != A4_SCHEMA_VERSION or self.artifact_type != EXECUTION_ARTIFACT_TYPE:
            raise BrokerA4ModelError("unsupported execution schema/artifact type")
        _clean("broker_order_id", self.broker_order_id)
        _clean("execution_id", self.execution_id)
        _uuid4("intent_id", self.intent_id)
        _uuid4("attempt_id", self.attempt_id)
        _decimal("fill_quantity", self.fill_quantity, positive=True)
        _decimal("fill_price", self.fill_price, positive=True)
        filled_at = _timestamp("fill_time", self.fill_time)
        for name in ("incremental_fee", "incremental_tax"):
            value = getattr(self, name)
            if value is not None:
                _decimal(name, value, nonnegative=True)
        _decimal("cumulative_quantity", self.cumulative_quantity, positive=True)
        if self.cumulative_quantity < self.fill_quantity:
            raise BrokerA4ModelError("cumulative_quantity cannot be below incremental fill")
        if _timestamp("received_at", self.received_at) < filled_at:
            raise BrokerA4ModelError("received_at cannot precede fill_time")


__all__ = [
    "A4_SCHEMA_VERSION", "AUTHORIZATION_ARTIFACT_TYPE",
    "AUTHORIZATION_USE_ARTIFACT_TYPE", "AUTHORIZATION_USE_PERSISTENCE_NOTICE",
    "CANONICAL_CLIENT_ORDER_ID_LENGTH", "CLIENT_ORDER_ID_PREFIX",
    "EXECUTION_ARTIFACT_TYPE", "INTENT_KEY_PREFIX", "KILL_SWITCH_ARTIFACT_TYPE",
    "ORDER_INTENT_ARTIFACT_TYPE", "SUBMISSION_ARTIFACT_TYPE",
    "AuthorizationUseState", "BrokerA4ModelError", "BrokerAuthorizationUseRecord",
    "BrokerExecutionAuthorization", "BrokerExecutionRecord", "BrokerKillSwitchSnapshot",
    "BrokerOrderIntent", "BrokerOrderIntentKeyPayload", "BrokerPersistentEncodingRequiredError",
    "BrokerSubmissionEvidence", "BrokerSubmissionRecord", "BrokerSubmissionState",
    "KillSwitchState", "QuantityMode", "canonical_broker_client_order_id",
    "derive_broker_order_intent_key_v1",
]
