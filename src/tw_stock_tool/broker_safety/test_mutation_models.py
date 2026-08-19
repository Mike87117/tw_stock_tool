"""Non-promotable TEST-only broker mutation containment contracts."""

from __future__ import annotations

from dataclasses import InitVar, dataclass, fields, is_dataclass
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
import json
import re

from tw_stock_tool.broker_safety.models import (
    BrokerEnvironment,
    OrderSide,
    OrderType,
    TimeInForce,
    _clean,
    _decimal,
    _timestamp,
    _uuid4,
)


TEST_MUTATION_SCHEMA_VERSION = "broker-test-mutation-v1"
TEST_POLICY_ARTIFACT_TYPE = "broker_test_mutation_policy"
TEST_ENVELOPE_ARTIFACT_TYPE = "broker_test_mutation_envelope"
TEST_OPERATOR_OPT_IN_ARTIFACT_TYPE = "broker_test_operator_opt_in"
TEST_AUTHORIZATION_ARTIFACT_TYPE = "broker_test_mutation_authorization"
TEST_SUBMISSION_ARTIFACT_TYPE = "broker_test_submission"
TEST_PROVIDER_BINDING_SCHEMA_VERSION = "broker-test-provider-binding-v1"
TEST_PRE_SUBMIT_PERSISTENCE_VERSION = "broker-test-pre-submit-v1"

_CANONICAL_ID = re.compile(r"twst1-[0-9a-f]{64}\Z")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_TEST_BINDING_AUTHORITY = object()
_TEST_OPT_IN_AUTHORITY = object()


class BrokerTestMutationModelError(ValueError):
    """Raised when a TEST-only artifact is wider than the frozen envelope."""


class TestLimitAuthority(StrEnum):
    SYNTHETIC_SANDBOX_HARNESS_ONLY = "SYNTHETIC_SANDBOX_HARNESS_ONLY"


class TestSubmissionState(StrEnum):
    SUBMITTING = "SUBMITTING"
    PROVIDER_ACKNOWLEDGED = "PROVIDER_ACKNOWLEDGED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    UNKNOWN_SUBMISSION_STATE = "UNKNOWN_SUBMISSION_STATE"
    REJECTED = "REJECTED"


def _exact_positive(name: str, value: object) -> int:
    if type(value) is not int or value <= 0:
        raise BrokerTestMutationModelError(f"{name} must be an exact positive integer")
    return value


def _exact_sha(name: str, value: object) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise BrokerTestMutationModelError(f"{name} must be a lowercase SHA-256")
    return value


def _exact_date(name: str, value: object) -> str:
    if type(value) is not str or _DATE.fullmatch(value) is None:
        raise BrokerTestMutationModelError(f"{name} must be an exact ISO date")
    try:
        _timestamp(name, f"{value}T00:00:00Z")
    except ValueError as exc:
        raise BrokerTestMutationModelError(f"{name} must be a valid ISO date") from exc
    return value


def _canonical(value: object) -> bytes:
    def encode(item: object) -> object:
        if type(item) is Decimal:
            return "0" if item == 0 else format(item.normalize(), "f")
        if isinstance(item, StrEnum):
            return item.value
        if type(item) is tuple:
            return [encode(value) for value in item]
        if is_dataclass(item) and not isinstance(item, type):
            return {
                field.name: encode(getattr(item, field.name))
                for field in fields(item)
            }
        return item

    return json.dumps(
        encode(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def test_mutation_artifact_sha256(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class BrokerTestMutationPolicy:
    """Synthetic containment only; never an account-capital assertion."""

    schema_version: str
    artifact_type: str
    broker_id: str
    environment: BrokerEnvironment
    endpoint: str
    product: str
    trade_mode: str
    lot_mode: str
    allowed_side: OrderSide
    order_type: OrderType
    time_in_force: TimeInForce
    maximum_active_test_orders: int
    maximum_unresolved_submissions: int
    maximum_order_quantity: int
    maximum_order_notional: Decimal
    maximum_session_submitted_notional: Decimal
    limit_authority: TestLimitAuthority
    explicit_operator_opt_in_required: bool
    unattended_retry_allowed: bool
    forbidden_features: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != TEST_MUTATION_SCHEMA_VERSION or self.artifact_type != TEST_POLICY_ARTIFACT_TYPE:
            raise BrokerTestMutationModelError("unknown TEST policy version")
        _clean("broker_id", self.broker_id)
        _clean("endpoint", self.endpoint)
        if type(self.environment) is not BrokerEnvironment or self.environment is not BrokerEnvironment.SANDBOX:
            raise BrokerTestMutationModelError("TEST mutation policy structurally rejects LIVE")
        if (
            self.product,
            self.trade_mode,
            self.lot_mode,
            self.allowed_side,
            self.order_type,
            self.time_in_force,
        ) != (
            "TW_SECURITIES",
            "CASH_STOCK",
            "COMMON_LOT",
            OrderSide.BUY,
            OrderType.LIMIT,
            TimeInForce.DAY,
        ):
            raise BrokerTestMutationModelError("TEST policy is wider than BUY-only cash common-lot LIMIT DAY")
        if self.maximum_active_test_orders != 1 or self.maximum_unresolved_submissions != 1:
            raise BrokerTestMutationModelError("TEST policy permits exactly one active and unresolved submission")
        quantity = _exact_positive("maximum_order_quantity", self.maximum_order_quantity)
        if quantity != 1000:
            raise BrokerTestMutationModelError("first TEST envelope permits one common lot only")
        _decimal("maximum_order_notional", self.maximum_order_notional, positive=True)
        _decimal(
            "maximum_session_submitted_notional",
            self.maximum_session_submitted_notional,
            positive=True,
        )
        if self.maximum_session_submitted_notional < self.maximum_order_notional:
            raise BrokerTestMutationModelError("session harness cap cannot be below the order cap")
        if type(self.limit_authority) is not TestLimitAuthority or self.limit_authority is not TestLimitAuthority.SYNTHETIC_SANDBOX_HARNESS_ONLY:
            raise BrokerTestMutationModelError("TEST limits must never claim capital authority")
        if self.explicit_operator_opt_in_required is not True or self.unattended_retry_allowed is not False:
            raise BrokerTestMutationModelError("explicit opt-in and no unattended retry are mandatory")
        expected = (
            "DAY_TRADE",
            "LIVE_ENDPOINT",
            "MARGIN",
            "ODD_LOT",
            "SBL",
            "SELL",
            "SHORT",
            "UNATTENDED_RETRY",
        )
        if self.forbidden_features != expected:
            raise BrokerTestMutationModelError("forbidden TEST features are not exact")


@dataclass(frozen=True, slots=True)
class BrokerTestMutationEnvelope:
    schema_version: str
    artifact_type: str
    envelope_id: str
    economic_intent_id: str
    idempotency_key: str
    canonical_client_order_id: str
    broker_id: str
    environment: BrokerEnvironment
    endpoint: str
    account_reference: str
    trading_date: str
    sequence: int
    symbol: str
    side: OrderSide
    quantity: int
    limit_price: Decimal
    order_notional: Decimal
    product: str
    trade_mode: str
    lot_mode: str
    order_type: OrderType
    time_in_force: TimeInForce
    created_at: str
    expires_at: str
    policy_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != TEST_MUTATION_SCHEMA_VERSION or self.artifact_type != TEST_ENVELOPE_ARTIFACT_TYPE:
            raise BrokerTestMutationModelError("unknown TEST envelope version")
        _uuid4("envelope_id", self.envelope_id)
        _exact_sha("economic_intent_id", self.economic_intent_id)
        _clean("idempotency_key", self.idempotency_key)
        if type(self.canonical_client_order_id) is not str or _CANONICAL_ID.fullmatch(self.canonical_client_order_id) is None:
            raise BrokerTestMutationModelError("canonical identity must remain full twst1-<64hex>")
        _clean("broker_id", self.broker_id)
        _clean("endpoint", self.endpoint)
        _clean("account_reference", self.account_reference)
        _exact_date("trading_date", self.trading_date)
        _exact_positive("sequence", self.sequence)
        if type(self.environment) is not BrokerEnvironment or self.environment is not BrokerEnvironment.SANDBOX:
            raise BrokerTestMutationModelError("TEST envelope structurally rejects LIVE")
        if type(self.symbol) is not str or re.fullmatch(r"[0-9]{4}", self.symbol) is None:
            raise BrokerTestMutationModelError("symbol must be an exact reviewed Taiwan stock symbol")
        if (
            self.product,
            self.trade_mode,
            self.lot_mode,
            self.side,
            self.order_type,
            self.time_in_force,
        ) != (
            "TW_SECURITIES",
            "CASH_STOCK",
            "COMMON_LOT",
            OrderSide.BUY,
            OrderType.LIMIT,
            TimeInForce.DAY,
        ):
            raise BrokerTestMutationModelError("TEST envelope is wider than the frozen profile")
        if _exact_positive("quantity", self.quantity) != 1000:
            raise BrokerTestMutationModelError("quantity must be exactly one common lot")
        price = _decimal("limit_price", self.limit_price, positive=True)
        notional = _decimal("order_notional", self.order_notional, positive=True)
        if notional != price * self.quantity:
            raise BrokerTestMutationModelError("order_notional must exactly equal price times quantity")
        created = _timestamp("created_at", self.created_at)
        expires = _timestamp("expires_at", self.expires_at)
        if created >= expires or self.created_at[:10] != self.trading_date or self.expires_at[:10] != self.trading_date:
            raise BrokerTestMutationModelError("TEST envelope must expire on its exact trading date")
        _exact_sha("policy_sha256", self.policy_sha256)


@dataclass(frozen=True, slots=True)
class BrokerTestOperatorOptIn:
    """Store-issued, expiring authority for one exact SANDBOX envelope."""

    schema_version: str
    artifact_type: str
    operator_opt_in_id: str
    broker_id: str
    environment: BrokerEnvironment
    endpoint: str
    account_reference: str
    envelope_id: str
    envelope_sha256: str
    policy_sha256: str
    trading_date: str
    issued_at: str
    expires_at: str
    operator_reference: str
    one_shot: bool
    _authority: InitVar[object]

    def __post_init__(self, _authority: object) -> None:
        if _authority is not _TEST_OPT_IN_AUTHORITY:
            raise BrokerTestMutationModelError(
                "TEST operator opt-in must be issued under the Phase C controller fence"
            )
        if (
            self.schema_version != TEST_MUTATION_SCHEMA_VERSION
            or self.artifact_type != TEST_OPERATOR_OPT_IN_ARTIFACT_TYPE
        ):
            raise BrokerTestMutationModelError("unknown TEST operator opt-in version")
        _uuid4("operator_opt_in_id", self.operator_opt_in_id)
        _clean("broker_id", self.broker_id)
        _clean("endpoint", self.endpoint)
        _clean("account_reference", self.account_reference)
        _uuid4("envelope_id", self.envelope_id)
        _exact_sha("envelope_sha256", self.envelope_sha256)
        _exact_sha("policy_sha256", self.policy_sha256)
        _exact_date("trading_date", self.trading_date)
        issued = _timestamp("issued_at", self.issued_at)
        expires = _timestamp("expires_at", self.expires_at)
        _clean("operator_reference", self.operator_reference)
        if (
            type(self.environment) is not BrokerEnvironment
            or self.environment is not BrokerEnvironment.SANDBOX
        ):
            raise BrokerTestMutationModelError("TEST operator opt-in structurally rejects LIVE")
        if (
            issued >= expires
            or self.issued_at[:10] != self.trading_date
            or self.expires_at[:10] != self.trading_date
        ):
            raise BrokerTestMutationModelError(
                "TEST operator opt-in must be expiring and same-date"
            )
        if self.one_shot is not True:
            raise BrokerTestMutationModelError("TEST operator opt-in must be one-shot")


@dataclass(frozen=True, slots=True)
class BrokerTestExecutionAuthorization:
    schema_version: str
    artifact_type: str
    authorization_id: str
    envelope_id: str
    envelope_sha256: str
    policy_sha256: str
    operator_opt_in_id: str
    operator_opt_in_sha256: str
    broker_id: str
    environment: BrokerEnvironment
    endpoint: str
    account_reference: str
    issued_at: str
    expires_at: str
    one_shot: bool
    limit_authority: TestLimitAuthority

    def __post_init__(self) -> None:
        if self.schema_version != TEST_MUTATION_SCHEMA_VERSION or self.artifact_type != TEST_AUTHORIZATION_ARTIFACT_TYPE:
            raise BrokerTestMutationModelError("unknown TEST authorization version")
        _uuid4("authorization_id", self.authorization_id)
        _uuid4("envelope_id", self.envelope_id)
        _exact_sha("envelope_sha256", self.envelope_sha256)
        _exact_sha("policy_sha256", self.policy_sha256)
        _uuid4("operator_opt_in_id", self.operator_opt_in_id)
        _exact_sha("operator_opt_in_sha256", self.operator_opt_in_sha256)
        _clean("broker_id", self.broker_id)
        _clean("endpoint", self.endpoint)
        _clean("account_reference", self.account_reference)
        issued = _timestamp("issued_at", self.issued_at)
        expires = _timestamp("expires_at", self.expires_at)
        if issued >= expires:
            raise BrokerTestMutationModelError("TEST authorization expiry must follow issuance")
        if type(self.environment) is not BrokerEnvironment or self.environment is not BrokerEnvironment.SANDBOX:
            raise BrokerTestMutationModelError("TEST authorization structurally rejects LIVE")
        if self.one_shot is not True or self.limit_authority is not TestLimitAuthority.SYNTHETIC_SANDBOX_HARNESS_ONLY:
            raise BrokerTestMutationModelError("TEST authorization must be one-shot and synthetic-only")


@dataclass(frozen=True, slots=True)
class BrokerTestSubmissionRecord:
    schema_version: str
    artifact_type: str
    envelope_id: str
    attempt_id: str
    canonical_client_order_id: str
    provider_tag: str
    state: TestSubmissionState
    version: int
    recorded_at: str
    provider_order_id: str | None
    sanitized_outcome: str

    def __post_init__(self) -> None:
        if self.schema_version != TEST_MUTATION_SCHEMA_VERSION or self.artifact_type != TEST_SUBMISSION_ARTIFACT_TYPE:
            raise BrokerTestMutationModelError("unknown TEST submission version")
        _uuid4("envelope_id", self.envelope_id)
        _uuid4("attempt_id", self.attempt_id)
        if type(self.canonical_client_order_id) is not str or _CANONICAL_ID.fullmatch(self.canonical_client_order_id) is None:
            raise BrokerTestMutationModelError("submission must retain full canonical identity")
        _clean("provider_tag", self.provider_tag)
        if type(self.state) is not TestSubmissionState:
            raise BrokerTestMutationModelError("submission state must be exact")
        _exact_positive("version", self.version)
        _timestamp("recorded_at", self.recorded_at)
        if self.provider_order_id is not None:
            _clean("provider_order_id", self.provider_order_id)
        _clean("sanitized_outcome", self.sanitized_outcome)
        if self.state is TestSubmissionState.SUBMITTING and self.provider_order_id is not None:
            raise BrokerTestMutationModelError("SUBMITTING cannot claim a provider acknowledgement")


@dataclass(frozen=True, slots=True)
class DurableTestProviderTagBinding:
    schema_version: str
    broker_id: str
    environment: BrokerEnvironment
    endpoint: str
    account_reference: str
    envelope_id: str
    provider_name: str
    provider_tag: str
    canonical_client_order_id: str
    fencing_token: int
    mapped_at: str
    mapping_audit_sequence: int
    _authority: InitVar[object]

    def __post_init__(self, _authority: object) -> None:
        if _authority is not _TEST_BINDING_AUTHORITY:
            raise BrokerTestMutationModelError(
                "provider tag binding must come from the fenced durable TEST store"
            )
        if self.schema_version != TEST_PROVIDER_BINDING_SCHEMA_VERSION:
            raise BrokerTestMutationModelError("unknown provider binding version")
        if self.environment is not BrokerEnvironment.SANDBOX:
            raise BrokerTestMutationModelError("TEST provider binding rejects LIVE")
        for name in ("broker_id", "endpoint", "account_reference", "provider_name", "provider_tag"):
            _clean(name, getattr(self, name))
        _uuid4("envelope_id", self.envelope_id)
        if type(self.canonical_client_order_id) is not str or _CANONICAL_ID.fullmatch(self.canonical_client_order_id) is None:
            raise BrokerTestMutationModelError("provider binding must preserve full canonical identity")
        _exact_positive("fencing_token", self.fencing_token)
        _timestamp("mapped_at", self.mapped_at)
        _exact_positive("mapping_audit_sequence", self.mapping_audit_sequence)


@dataclass(frozen=True, slots=True)
class BrokerTestPreSubmitCommit:
    schema_version: str
    persistence_version: str
    envelope_id: str
    authorization_id: str
    attempt_id: str
    request_sha256: str
    submission_sha256: str
    audit_sequence: int
    audit_root_digest: str
    fencing_token: int
    submission: BrokerTestSubmissionRecord

    def __post_init__(self) -> None:
        if self.schema_version != TEST_MUTATION_SCHEMA_VERSION or self.persistence_version != TEST_PRE_SUBMIT_PERSISTENCE_VERSION:
            raise BrokerTestMutationModelError("unknown TEST pre-submit persistence version")
        for name in ("envelope_id", "authorization_id", "attempt_id"):
            _uuid4(name, getattr(self, name))
        _exact_sha("request_sha256", self.request_sha256)
        _exact_sha("submission_sha256", self.submission_sha256)
        _exact_sha("audit_root_digest", self.audit_root_digest)
        _exact_positive("audit_sequence", self.audit_sequence)
        _exact_positive("fencing_token", self.fencing_token)
        if type(self.submission) is not BrokerTestSubmissionRecord or (
            self.submission.envelope_id,
            self.submission.attempt_id,
            self.submission.state,
        ) != (self.envelope_id, self.attempt_id, TestSubmissionState.SUBMITTING):
            raise BrokerTestMutationModelError("TEST commit must bind its exact SUBMITTING record")


__all__ = [
    "BrokerTestExecutionAuthorization",
    "BrokerTestMutationEnvelope",
    "BrokerTestMutationModelError",
    "BrokerTestMutationPolicy",
    "BrokerTestOperatorOptIn",
    "BrokerTestPreSubmitCommit",
    "BrokerTestSubmissionRecord",
    "DurableTestProviderTagBinding",
    "TEST_AUTHORIZATION_ARTIFACT_TYPE",
    "TEST_ENVELOPE_ARTIFACT_TYPE",
    "TEST_MUTATION_SCHEMA_VERSION",
    "TEST_OPERATOR_OPT_IN_ARTIFACT_TYPE",
    "TEST_POLICY_ARTIFACT_TYPE",
    "TEST_PRE_SUBMIT_PERSISTENCE_VERSION",
    "TEST_PROVIDER_BINDING_SCHEMA_VERSION",
    "TEST_SUBMISSION_ARTIFACT_TYPE",
    "TestLimitAuthority",
    "TestSubmissionState",
    "test_mutation_artifact_sha256",
]
