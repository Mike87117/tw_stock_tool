"""Reviewed Phase 56.5D0.1 Fubon SANDBOX-only mutation envelope."""

from __future__ import annotations

from dataclasses import InitVar, dataclass
from decimal import Decimal
from enum import StrEnum

from tw_stock_tool.broker_adapters.fubon_neo.config import (
    FUBON_NEO_BROKER_ID,
    FUBON_NEO_TEST_ENDPOINT,
)
from tw_stock_tool.broker_adapters.fubon_neo.d0_readiness import (
    LostAckDisposition,
    ProviderOrderMatchState,
    derive_fubon_provider_correlation_tag,
)
from tw_stock_tool.broker_safety.d0_readiness import D0PrerequisiteName
from tw_stock_tool.broker_safety.durable_models import BrokerAccountScope
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
from tw_stock_tool.broker_safety.test_mutation_models import (
    TEST_AUTHORIZATION_ARTIFACT_TYPE,
    TEST_ENVELOPE_ARTIFACT_TYPE,
    TEST_MUTATION_SCHEMA_VERSION,
    TEST_POLICY_ARTIFACT_TYPE,
    BrokerTestExecutionAuthorization,
    BrokerTestMutationEnvelope,
    BrokerTestMutationModelError,
    BrokerTestMutationPolicy,
    BrokerTestOperatorOptIn,
    BrokerTestPreSubmitCommit,
    BrokerTestSubmissionRecord,
    DurableTestProviderTagBinding,
    TestLimitAuthority,
    test_mutation_artifact_sha256,
)
from tw_stock_tool.broker_safety.test_mutation_store import SQLiteBrokerTestMutationStore


FUBON_TEST_MUTATION_CONTRACT_VERSION = "fubon-neo-56.5d0.1-test-envelope-v1"
FUBON_TEST_MUTATION_REVIEW_VERSION = "official-fubon-test-docs-reviewed-2026-08-19-v1"
FUBON_TEST_MUTATION_READINESS_SCHEMA_VERSION = "fubon-test-mutation-readiness-v1"
FUBON_PROVIDER_OBSERVATION_SCHEMA_VERSION = "fubon-provider-order-observation-v1"
FUBON_PROVIDER_MATCH_SCHEMA_VERSION = "fubon-provider-order-match-v1"

FUBON_TEST_MUTATION_REVIEWED_SOURCE_URLS = (
    "https://www.fbs.com.tw/TradeAPI/docs/welcome/",
    "https://www.fbs.com.tw/TradeAPI/docs/trading/guide/advance/ping_pong/",
    "https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/trade/GetOrderResults/",
    "https://www.fbs.com.tw/TradeAPI/docs/download/download-sdk/",
    "https://www.fbs.com.tw/wcm/new_web/trade/trade_20250320_458309.html",
)


class TestMutationReadinessOutcome(StrEnum):
    READY_FOR_TEST_MUTATION_ADAPTER = "READY_FOR_TEST_MUTATION_ADAPTER"
    BLOCKED = "BLOCKED"


class D0BlockerTestClassification(StrEnum):
    REQUIRED_BEFORE_ANY_TEST_MUTATION = "REQUIRED_BEFORE_ANY_TEST_MUTATION"
    NOT_REQUIRED_FOR_NONPROMOTABLE_TEST_ENVELOPE = "NOT_REQUIRED_FOR_NONPROMOTABLE_TEST_ENVELOPE"
    REQUIRED_ONLY_FOR_LIVE_CAPABLE_AUTHORIZATION = "REQUIRED_ONLY_FOR_LIVE_CAPABLE_AUTHORIZATION"
    REPLACED_BY_TEST_ONLY_FAIL_CLOSED_RULE = "REPLACED_BY_TEST_ONLY_FAIL_CLOSED_RULE"


@dataclass(frozen=True, slots=True)
class D0BlockerTestDisposition:
    blocker: D0PrerequisiteName
    classification: D0BlockerTestClassification
    test_rule: str
    live_requirement_preserved: bool

    def __post_init__(self) -> None:
        if type(self.blocker) is not D0PrerequisiteName or type(self.classification) is not D0BlockerTestClassification:
            raise BrokerTestMutationModelError("D0 blocker disposition must use exact enums")
        _clean("test_rule", self.test_rule)
        if self.live_requirement_preserved is not True:
            raise BrokerTestMutationModelError("D0.1 cannot weaken a live D0 blocker")


FUBON_TEST_D0_BLOCKER_DISPOSITIONS = tuple(
    sorted(
        (
            D0BlockerTestDisposition(
                D0PrerequisiteName.ACCOUNT_CAPITAL_AUTHORITY,
                D0BlockerTestClassification.REPLACED_BY_TEST_ONLY_FAIL_CLOSED_RULE,
                "SYNTHETIC_TEST_COMMAND_NOTIONAL_CAP_WITH_NO_CAPITAL_CLAIM",
                True,
            ),
            D0BlockerTestDisposition(
                D0PrerequisiteName.POSITION_VALUATION_EXPOSURE_AUTHORITY,
                D0BlockerTestClassification.REQUIRED_ONLY_FOR_LIVE_CAPABLE_AUTHORIZATION,
                "BUY_ONLY_ONE_COMMON_LOT_NO_PORTFOLIO_EXPOSURE_CLAIM",
                True,
            ),
            D0BlockerTestDisposition(
                D0PrerequisiteName.TRADING_PERMISSION_PROOF,
                D0BlockerTestClassification.REPLACED_BY_TEST_ONLY_FAIL_CLOSED_RULE,
                "EXACT_OFFICIAL_TEST_PROVENANCE_PLUS_EXPLICIT_ONE_SHOT_OPERATOR_OPT_IN",
                True,
            ),
            D0BlockerTestDisposition(
                D0PrerequisiteName.FEE_TAX_AUTHORITY,
                D0BlockerTestClassification.REQUIRED_ONLY_FOR_LIVE_CAPABLE_AUTHORIZATION,
                "SYNTHETIC_TEST_COMMAND_CAP_IS_NOT_A_FEE_OR_CAPITAL_CALCULATION",
                True,
            ),
            D0BlockerTestDisposition(
                D0PrerequisiteName.CLIENT_CORRELATION_LOST_ACK_SAFETY,
                D0BlockerTestClassification.REQUIRED_BEFORE_ANY_TEST_MUTATION,
                "BLOCKED_UNTIL_SEALED_PROVIDER_READ_AND_PHASE_C_TEST_MAPPING_EXIST",
                True,
            ),
            D0BlockerTestDisposition(
                D0PrerequisiteName.SESSION_PROOF,
                D0BlockerTestClassification.REPLACED_BY_TEST_ONLY_FAIL_CLOSED_RULE,
                "SAME_DATE_EXPIRING_OPERATOR_OPT_IN_WITH_PROVIDER_REJECTION_FAIL_CLOSED",
                True,
            ),
        ),
        key=lambda item: item.blocker.value,
    )
)


FUBON_TEST_MUTATION_POLICY = BrokerTestMutationPolicy(
    schema_version=TEST_MUTATION_SCHEMA_VERSION,
    artifact_type=TEST_POLICY_ARTIFACT_TYPE,
    broker_id=FUBON_NEO_BROKER_ID,
    environment=BrokerEnvironment.SANDBOX,
    endpoint=FUBON_NEO_TEST_ENDPOINT,
    product="TW_SECURITIES",
    trade_mode="CASH_STOCK",
    lot_mode="COMMON_LOT",
    allowed_side=OrderSide.BUY,
    order_type=OrderType.LIMIT,
    time_in_force=TimeInForce.DAY,
    maximum_active_test_orders=1,
    maximum_unresolved_submissions=1,
    maximum_order_quantity=1000,
    maximum_order_notional=Decimal("1000000"),
    maximum_session_submitted_notional=Decimal("1000000"),
    limit_authority=TestLimitAuthority.SYNTHETIC_SANDBOX_HARNESS_ONLY,
    explicit_operator_opt_in_required=True,
    unattended_retry_allowed=False,
    forbidden_features=(
        "DAY_TRADE",
        "LIVE_ENDPOINT",
        "MARGIN",
        "ODD_LOT",
        "SBL",
        "SELL",
        "SHORT",
        "UNATTENDED_RETRY",
    ),
)


_READINESS_AUTHORITY = object()
_MATCH_AUTHORITY = object()
_OBSERVATION_AUTHORITY = object()


@dataclass(frozen=True, slots=True)
class FubonNeoTestMutationReadiness:
    schema_version: str
    contract_version: str
    reviewed_evidence_version: str
    broker_id: str
    environment: BrokerEnvironment
    endpoint: str
    policy: BrokerTestMutationPolicy
    d0_blocker_dispositions: tuple[D0BlockerTestDisposition, ...]
    outcome: TestMutationReadinessOutcome
    reviewed_source_urls: tuple[str, ...]
    _authority: InitVar[object]

    def __post_init__(self, _authority: object) -> None:
        if _authority is not _READINESS_AUTHORITY:
            raise BrokerTestMutationModelError("TEST readiness must come from the reviewed frozen contract")
        if (
            self.schema_version,
            self.contract_version,
            self.reviewed_evidence_version,
            self.broker_id,
            self.environment,
            self.endpoint,
            self.policy,
            self.d0_blocker_dispositions,
            self.outcome,
            self.reviewed_source_urls,
        ) != (
            FUBON_TEST_MUTATION_READINESS_SCHEMA_VERSION,
            FUBON_TEST_MUTATION_CONTRACT_VERSION,
            FUBON_TEST_MUTATION_REVIEW_VERSION,
            FUBON_NEO_BROKER_ID,
            BrokerEnvironment.SANDBOX,
            FUBON_NEO_TEST_ENDPOINT,
            FUBON_TEST_MUTATION_POLICY,
            FUBON_TEST_D0_BLOCKER_DISPOSITIONS,
            TestMutationReadinessOutcome.BLOCKED,
            FUBON_TEST_MUTATION_REVIEWED_SOURCE_URLS,
        ):
            raise BrokerTestMutationModelError("TEST readiness differs from the frozen reviewed result")


_CURRENT_READINESS = FubonNeoTestMutationReadiness(
    FUBON_TEST_MUTATION_READINESS_SCHEMA_VERSION,
    FUBON_TEST_MUTATION_CONTRACT_VERSION,
    FUBON_TEST_MUTATION_REVIEW_VERSION,
    FUBON_NEO_BROKER_ID,
    BrokerEnvironment.SANDBOX,
    FUBON_NEO_TEST_ENDPOINT,
    FUBON_TEST_MUTATION_POLICY,
    FUBON_TEST_D0_BLOCKER_DISPOSITIONS,
    TestMutationReadinessOutcome.BLOCKED,
    FUBON_TEST_MUTATION_REVIEWED_SOURCE_URLS,
    _READINESS_AUTHORITY,
)


def current_fubon_neo_test_mutation_readiness() -> FubonNeoTestMutationReadiness:
    return _CURRENT_READINESS


def build_fubon_test_mutation_envelope(
    *,
    envelope_id: str,
    economic_intent_id: str,
    idempotency_key: str,
    canonical_client_order_id: str,
    account_reference: str,
    trading_date: str,
    sequence: int,
    symbol: str,
    quantity: int,
    limit_price: Decimal,
    created_at: str,
    expires_at: str,
) -> BrokerTestMutationEnvelope:
    policy = FUBON_TEST_MUTATION_POLICY
    notional = limit_price * quantity if type(limit_price) is Decimal and type(quantity) is int else Decimal("-1")
    if notional > policy.maximum_order_notional:
        raise BrokerTestMutationModelError("synthetic TEST maximum order notional exceeded")
    return BrokerTestMutationEnvelope(
        TEST_MUTATION_SCHEMA_VERSION,
        TEST_ENVELOPE_ARTIFACT_TYPE,
        envelope_id,
        economic_intent_id,
        idempotency_key,
        canonical_client_order_id,
        FUBON_NEO_BROKER_ID,
        BrokerEnvironment.SANDBOX,
        FUBON_NEO_TEST_ENDPOINT,
        account_reference,
        trading_date,
        sequence,
        symbol,
        OrderSide.BUY,
        quantity,
        limit_price,
        notional,
        "TW_SECURITIES",
        "CASH_STOCK",
        "COMMON_LOT",
        OrderType.LIMIT,
        TimeInForce.DAY,
        created_at,
        expires_at,
        test_mutation_artifact_sha256(policy),
    )


def build_fubon_test_execution_authorization(
    envelope: BrokerTestMutationEnvelope,
    operator_opt_in: BrokerTestOperatorOptIn,
    *,
    authorization_id: str,
    issued_at: str,
    expires_at: str,
) -> BrokerTestExecutionAuthorization:
    if type(envelope) is not BrokerTestMutationEnvelope or (
        envelope.broker_id,
        envelope.environment,
        envelope.endpoint,
        envelope.policy_sha256,
    ) != (
        FUBON_NEO_BROKER_ID,
        BrokerEnvironment.SANDBOX,
        FUBON_NEO_TEST_ENDPOINT,
        test_mutation_artifact_sha256(FUBON_TEST_MUTATION_POLICY),
    ):
        raise BrokerTestMutationModelError("authorization requires the exact reviewed Fubon TEST envelope")
    if type(operator_opt_in) is not BrokerTestOperatorOptIn or (
        operator_opt_in.envelope_id,
        operator_opt_in.envelope_sha256,
        operator_opt_in.policy_sha256,
        operator_opt_in.environment,
        operator_opt_in.endpoint,
        operator_opt_in.account_reference,
    ) != (
        envelope.envelope_id,
        test_mutation_artifact_sha256(envelope),
        envelope.policy_sha256,
        envelope.environment,
        envelope.endpoint,
        envelope.account_reference,
    ):
        raise BrokerTestMutationModelError("authorization requires the exact bounded operator opt-in")
    if _timestamp("issued_at", issued_at) < _timestamp("envelope.created_at", envelope.created_at) or _timestamp("expires_at", expires_at) > _timestamp("envelope.expires_at", envelope.expires_at):
        raise BrokerTestMutationModelError("authorization lifetime must be inside its TEST envelope")
    return BrokerTestExecutionAuthorization(
        TEST_MUTATION_SCHEMA_VERSION,
        TEST_AUTHORIZATION_ARTIFACT_TYPE,
        authorization_id,
        envelope.envelope_id,
        test_mutation_artifact_sha256(envelope),
        envelope.policy_sha256,
        operator_opt_in.operator_opt_in_id,
        test_mutation_artifact_sha256(operator_opt_in),
        envelope.broker_id,
        envelope.environment,
        envelope.endpoint,
        envelope.account_reference,
        issued_at,
        expires_at,
        True,
        TestLimitAuthority.SYNTHETIC_SANDBOX_HARNESS_ONLY,
    )


def persist_fubon_test_provider_tag_binding(
    store: SQLiteBrokerTestMutationStore,
    scope: BrokerAccountScope,
    envelope: BrokerTestMutationEnvelope,
    *,
    owner_id: str,
    fencing_token: int,
    now: str,
    actor_reference: str,
) -> DurableTestProviderTagBinding:
    """Persist the deterministic noncanonical tag under the current TEST fence."""

    if type(store) is not SQLiteBrokerTestMutationStore:
        raise BrokerTestMutationModelError("Fubon TEST tag binding requires the exact TEST store")
    return store.map_test_provider_tag(
        scope,
        FUBON_TEST_MUTATION_POLICY,
        envelope,
        provider_name="FUBON_NEO_USER_DEF_V1",
        provider_tag=derive_fubon_provider_correlation_tag(envelope.canonical_client_order_id),
        owner_id=owner_id,
        fencing_token=fencing_token,
        now=now,
        actor_reference=actor_reference,
    )


def issue_fubon_test_operator_opt_in(
    store: SQLiteBrokerTestMutationStore,
    scope: BrokerAccountScope,
    envelope: BrokerTestMutationEnvelope,
    *,
    operator_opt_in_id: str,
    issued_at: str,
    expires_at: str,
    operator_reference: str,
    owner_id: str,
    fencing_token: int,
    actor_reference: str,
) -> BrokerTestOperatorOptIn:
    if type(store) is not SQLiteBrokerTestMutationStore:
        raise BrokerTestMutationModelError("Fubon TEST opt-in requires the exact TEST store")
    return store.issue_test_operator_opt_in(
        scope,
        FUBON_TEST_MUTATION_POLICY,
        envelope,
        operator_opt_in_id=operator_opt_in_id,
        issued_at=issued_at,
        expires_at=expires_at,
        operator_reference=operator_reference,
        owner_id=owner_id,
        fencing_token=fencing_token,
        actor_reference=actor_reference,
    )


def commit_fubon_test_pre_submit(
    store: SQLiteBrokerTestMutationStore,
    scope: BrokerAccountScope,
    operator_opt_in: BrokerTestOperatorOptIn,
    authorization: BrokerTestExecutionAuthorization,
    envelope: BrokerTestMutationEnvelope,
    *,
    attempt_id: str,
    occurred_at: str,
    owner_id: str,
    fencing_token: int,
    actor_reference: str,
    fail_before_commit: bool = False,
) -> BrokerTestPreSubmitCommit:
    """Enter atomic TEST SUBMITTING state without performing a provider call."""

    if type(store) is not SQLiteBrokerTestMutationStore:
        raise BrokerTestMutationModelError("Fubon TEST pre-submit requires the exact TEST store")
    return store.commit_test_pre_submit(
        scope,
        FUBON_TEST_MUTATION_POLICY,
        operator_opt_in,
        authorization,
        envelope,
        provider_name="FUBON_NEO_USER_DEF_V1",
        provider_tag=derive_fubon_provider_correlation_tag(envelope.canonical_client_order_id),
        attempt_id=attempt_id,
        occurred_at=occurred_at,
        owner_id=owner_id,
        fencing_token=fencing_token,
        actor_reference=actor_reference,
        fail_before_commit=fail_before_commit,
    )


def apply_fubon_test_lost_ack(
    store: SQLiteBrokerTestMutationStore,
    scope: BrokerAccountScope,
    envelope: BrokerTestMutationEnvelope,
    validated_match: ValidatedProviderOrderMatch,
    *,
    attempt_id: str,
    owner_id: str,
    fencing_token: int,
    recorded_at: str,
    actor_reference: str,
) -> BrokerTestSubmissionRecord:
    """Persist the validated lost-ACK outcome without exposing any retry action."""

    if type(store) is not SQLiteBrokerTestMutationStore or type(validated_match) is not ValidatedProviderOrderMatch:
        raise BrokerTestMutationModelError("lost-ACK persistence requires exact reviewed TEST types")
    return store.apply_validated_test_lost_ack(
        scope,
        envelope,
        validated_match,
        attempt_id=attempt_id,
        owner_id=owner_id,
        fencing_token=fencing_token,
        recorded_at=recorded_at,
        actor_reference=actor_reference,
    )


@dataclass(frozen=True, slots=True)
class FubonProviderOrderObservation:
    schema_version: str
    environment: BrokerEnvironment
    endpoint: str
    account_reference: str
    trading_date: str
    provider_order_id: str
    provider_tag: str
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    time_in_force: TimeInForce
    limit_price: Decimal
    _authority: InitVar[object]

    def __post_init__(self, _authority: object) -> None:
        if _authority is not _OBSERVATION_AUTHORITY:
            raise BrokerTestMutationModelError(
                "provider observations must originate at a sealed reviewed provider-read boundary"
            )
        if self.schema_version != FUBON_PROVIDER_OBSERVATION_SCHEMA_VERSION or self.environment is not BrokerEnvironment.SANDBOX or self.endpoint != FUBON_NEO_TEST_ENDPOINT:
            raise BrokerTestMutationModelError("provider observation must come from exact Fubon TEST provenance")
        for name in ("account_reference", "trading_date", "provider_order_id", "provider_tag", "symbol"):
            _clean(name, getattr(self, name))
        if type(self.side) is not OrderSide or type(self.order_type) is not OrderType or type(self.time_in_force) is not TimeInForce:
            raise BrokerTestMutationModelError("provider order facts must use exact enums")
        if type(self.quantity) is not int or self.quantity <= 0:
            raise BrokerTestMutationModelError("provider quantity must be exact and positive")
        _decimal("limit_price", self.limit_price, positive=True)


@dataclass(frozen=True, slots=True)
class ValidatedProviderOrderMatch:
    schema_version: str
    match_state: ProviderOrderMatchState
    envelope_id: str
    canonical_client_order_id: str
    provider_tag: str
    provider_order_id: str | None
    observed_at: str
    _authority: InitVar[object]

    def __post_init__(self, _authority: object) -> None:
        if _authority is not _MATCH_AUTHORITY:
            raise BrokerTestMutationModelError("provider match state cannot be manufactured by caller code")
        if self.schema_version != FUBON_PROVIDER_MATCH_SCHEMA_VERSION or type(self.match_state) is not ProviderOrderMatchState:
            raise BrokerTestMutationModelError("provider match result version or state is invalid")
        _uuid4("envelope_id", self.envelope_id)
        _clean("canonical_client_order_id", self.canonical_client_order_id)
        _clean("provider_tag", self.provider_tag)
        _timestamp("observed_at", self.observed_at)
        if (self.match_state is ProviderOrderMatchState.MATCHED) != (self.provider_order_id is not None):
            raise BrokerTestMutationModelError("only a validated MATCHED result carries one provider order ID")
        if self.provider_order_id is not None:
            _clean("provider_order_id", self.provider_order_id)


def correlate_fubon_provider_observations(
    envelope: BrokerTestMutationEnvelope,
    binding: DurableTestProviderTagBinding,
    observations: tuple[FubonProviderOrderObservation, ...],
    *,
    observed_at: str,
) -> ValidatedProviderOrderMatch:
    """The sole MATCHED authority: exact provider facts plus durable tag binding."""

    if type(envelope) is not BrokerTestMutationEnvelope or type(binding) is not DurableTestProviderTagBinding:
        raise BrokerTestMutationModelError("correlation requires exact TEST envelope and durable binding")
    if type(observations) is not tuple or any(type(item) is not FubonProviderOrderObservation for item in observations):
        raise BrokerTestMutationModelError("provider observations must be an exact immutable tuple")
    expected_tag = derive_fubon_provider_correlation_tag(envelope.canonical_client_order_id)
    if (
        binding.broker_id,
        binding.environment,
        binding.endpoint,
        binding.account_reference,
        binding.envelope_id,
        binding.provider_tag,
        binding.canonical_client_order_id,
    ) != (
        envelope.broker_id,
        envelope.environment,
        envelope.endpoint,
        envelope.account_reference,
        envelope.envelope_id,
        expected_tag,
        envelope.canonical_client_order_id,
    ):
        raise BrokerTestMutationModelError("durable provider tag binding does not match the exact envelope")
    matching: list[FubonProviderOrderObservation] = []
    conflicting = False
    for item in observations:
        same_tag = item.provider_tag == expected_tag
        facts_match = (
            item.environment,
            item.endpoint,
            item.account_reference,
            item.trading_date,
            item.symbol,
            item.side,
            item.quantity,
            item.order_type,
            item.time_in_force,
            item.limit_price,
        ) == (
            envelope.environment,
            envelope.endpoint,
            envelope.account_reference,
            envelope.trading_date,
            envelope.symbol,
            envelope.side,
            envelope.quantity,
            envelope.order_type,
            envelope.time_in_force,
            envelope.limit_price,
        )
        if same_tag and facts_match:
            matching.append(item)
        elif same_tag:
            conflicting = True
    state = (
        ProviderOrderMatchState.MATCHED
        if len(matching) == 1 and not conflicting
        else ProviderOrderMatchState.NO_MATCH
        if not matching and not conflicting
        else ProviderOrderMatchState.AMBIGUOUS
    )
    return ValidatedProviderOrderMatch(
        FUBON_PROVIDER_MATCH_SCHEMA_VERSION,
        state,
        envelope.envelope_id,
        envelope.canonical_client_order_id,
        expected_tag,
        matching[0].provider_order_id if state is ProviderOrderMatchState.MATCHED else None,
        observed_at,
        _MATCH_AUTHORITY,
    )


def resolve_validated_fubon_lost_ack(result: ValidatedProviderOrderMatch) -> LostAckDisposition:
    if type(result) is not ValidatedProviderOrderMatch:
        raise BrokerTestMutationModelError("lost-ACK resolution requires validated provider correlation")
    return {
        ProviderOrderMatchState.MATCHED: LostAckDisposition.RECONCILED_EXISTING_ORDER,
        ProviderOrderMatchState.NO_MATCH: LostAckDisposition.RECONCILIATION_REQUIRED,
        ProviderOrderMatchState.AMBIGUOUS: LostAckDisposition.UNKNOWN_SUBMISSION_STATE,
    }[result.match_state]


__all__ = [
    "D0BlockerTestClassification",
    "D0BlockerTestDisposition",
    "FUBON_PROVIDER_MATCH_SCHEMA_VERSION",
    "FUBON_PROVIDER_OBSERVATION_SCHEMA_VERSION",
    "FUBON_TEST_D0_BLOCKER_DISPOSITIONS",
    "FUBON_TEST_MUTATION_CONTRACT_VERSION",
    "FUBON_TEST_MUTATION_POLICY",
    "FUBON_TEST_MUTATION_READINESS_SCHEMA_VERSION",
    "FUBON_TEST_MUTATION_REVIEWED_SOURCE_URLS",
    "FUBON_TEST_MUTATION_REVIEW_VERSION",
    "FubonNeoTestMutationReadiness",
    "FubonProviderOrderObservation",
    "TestMutationReadinessOutcome",
    "ValidatedProviderOrderMatch",
    "build_fubon_test_execution_authorization",
    "build_fubon_test_mutation_envelope",
    "issue_fubon_test_operator_opt_in",
    "apply_fubon_test_lost_ack",
    "commit_fubon_test_pre_submit",
    "correlate_fubon_provider_observations",
    "current_fubon_neo_test_mutation_readiness",
    "persist_fubon_test_provider_tag_binding",
    "resolve_validated_fubon_lost_ack",
]
