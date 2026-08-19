"""Reviewed Phase 56.5D0 pre-mutation gate for Fubon Neo securities TEST."""

from __future__ import annotations

from base64 import b32encode
from dataclasses import InitVar, dataclass
from enum import StrEnum
from hashlib import sha256
import re

from tw_stock_tool.broker_adapters.fubon_neo.account_readiness import (
    FubonNeo56_5DReadiness,
    current_fubon_neo_56_5d_readiness,
)
from tw_stock_tool.broker_adapters.fubon_neo.config import (
    FUBON_NEO_BROKER_ID,
    FUBON_NEO_SDK_VERSION,
    FUBON_NEO_SOURCE_VERSION,
    FUBON_NEO_TEST_ENDPOINT,
)
from tw_stock_tool.broker_safety.d0_readiness import (
    D0_READINESS_SCHEMA_VERSION,
    BrokerSafetyPathFact,
    CapitalAuthorityModel,
    CapitalAuthorityProof,
    D0BlockReason,
    D0PrerequisiteName,
    D0PrerequisiteStatus,
    D0ReadinessModelError,
    D0ReadinessOutcome,
    D0RequirementState,
    MinimumTestExecutionProfile,
    SafetyFactUsage,
    SafetyPathFact,
    derive_d0_outcome,
)
from tw_stock_tool.broker_safety.models import (
    BrokerEnvironment,
    OrderSide,
    OrderType,
    TimeInForce,
)


FUBON_NEO_D0_CONTRACT_VERSION = "fubon-neo-56.5d0-pre-mutation-v1"
FUBON_NEO_D0_REVIEW_VERSION = "official-fubon-docs-reviewed-2026-08-19-v1"
FUBON_PROVIDER_CORRELATION_TAG_VERSION = "fubon-user-def-tag-v1"
FUBON_PROVIDER_NAME = "FUBON_NEO_USER_DEF_V1"
_CANONICAL_CLIENT_ID = re.compile(r"twst1-[0-9a-f]{64}\Z")
_D0_AUTHORITY = object()

FUBON_NEO_D0_REVIEWED_SOURCE_URLS = (
    "https://www.fbs.com.tw/TradeAPI/docs/download/download-sdk/",
    "https://www.fbs.com.tw/TradeAPI/docs/trading/guide/error-codes/",
    "https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/Balance/",
    "https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/Inventories/",
    "https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/QuerySettlement/",
    "https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/UnrealizedPnLDetail/",
    "https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/trade/GetOrderResults/",
)


def _fact(
    fact: SafetyPathFact,
    usage: SafetyFactUsage,
    consumed_by: tuple[str, ...],
    safety_property: str,
) -> BrokerSafetyPathFact:
    return BrokerSafetyPathFact(fact, usage, consumed_by, safety_property)


FUBON_NEO_D0_SAFETY_PATH_MATRIX = tuple(
    sorted(
        (
            _fact(
                SafetyPathFact.CASH,
                SafetyFactUsage.UNUSED_IN_CURRENT_GATE,
                ("BrokerAccountSnapshot.__post_init__",),
                "The v1 snapshot validates cash but preflight, limits, A4, and pre-submit do not consume it as BUY capital authority.",
            ),
            _fact(
                SafetyPathFact.BUYING_POWER,
                SafetyFactUsage.UNUSED_IN_CURRENT_GATE,
                ("BrokerAccountSnapshot.__post_init__",),
                "The v1 snapshot requires a nonnegative value but the current safety decision never compares an order to it.",
            ),
            _fact(
                SafetyPathFact.EQUITY,
                SafetyFactUsage.UNUSED_IN_CURRENT_GATE,
                ("BrokerAccountSnapshot.__post_init__",),
                "The v1 snapshot requires equity but no current percentage sizing or limit calculation consumes it.",
            ),
            _fact(
                SafetyPathFact.POSITIONS_QUANTITY,
                SafetyFactUsage.REQUIRED_FOR_SAFETY_DECISION,
                ("evaluate_broker_limits", "reconcile_broker_account"),
                "Position quantity bounds per-symbol projected quantity and must reconcile to local state.",
            ),
            _fact(
                SafetyPathFact.POSITIONS_AVAILABLE_QUANTITY,
                SafetyFactUsage.REQUIRED_FOR_SAFETY_DECISION,
                ("evaluate_broker_limits",),
                "Available owned quantity is the fail-closed boundary preventing an ordinary SELL from becoming short exposure.",
            ),
            _fact(
                SafetyPathFact.POSITIONS_MARKET_VALUE,
                SafetyFactUsage.REQUIRED_FOR_SAFETY_DECISION,
                ("evaluate_broker_limits",),
                "Every position needs reliable current value before account and symbol notional exposure can be bounded.",
            ),
            _fact(
                SafetyPathFact.OPEN_ORDERS,
                SafetyFactUsage.REQUIRED_FOR_SAFETY_DECISION,
                ("evaluate_broker_limits", "reconcile_broker_account"),
                "All broker nonterminal orders must reconcile and contribute quantity, notional, and simultaneous-order exposure.",
            ),
            _fact(
                SafetyPathFact.CAPABILITIES,
                SafetyFactUsage.REQUIRED_FOR_SAFETY_DECISION,
                ("evaluate_broker_limits", "evaluate_broker_preflight"),
                "Market, currency, order support, fee support, and trading permission are fail-closed preflight inputs.",
            ),
            _fact(
                SafetyPathFact.SESSION,
                SafetyFactUsage.REQUIRED_FOR_SAFETY_DECISION,
                ("build_broker_execution_authorization", "evaluate_broker_preflight", "transition_broker_submission"),
                "A fresh exact market-date session must permit the bounded submission at authorization and atomic pre-submit.",
            ),
            _fact(
                SafetyPathFact.RECONCILIATION,
                SafetyFactUsage.REQUIRED_FOR_SAFETY_DECISION,
                ("build_broker_execution_authorization", "evaluate_broker_preflight", "transition_broker_submission"),
                "A fresh matching reconciliation with no findings is required at authorization and again before SUBMITTING.",
            ),
            _fact(
                SafetyPathFact.LOCAL_RESERVED_EXPOSURE,
                SafetyFactUsage.REQUIRED_FOR_SAFETY_DECISION,
                ("SQLiteBrokerSafetyStore.commit_pre_submit", "evaluate_broker_limits"),
                "Durable open-order and uncertain-submission reservations are included and one-shot consumed under a fence.",
            ),
            _fact(
                SafetyPathFact.DAILY_SUBMITTED_NOTIONAL,
                SafetyFactUsage.REQUIRED_FOR_SAFETY_DECISION,
                ("evaluate_broker_limits",),
                "Trusted local daily notional plus all reservations and the candidate order must remain under an absolute cap.",
            ),
            _fact(
                SafetyPathFact.DAILY_LOSS,
                SafetyFactUsage.REQUIRED_FOR_SAFETY_DECISION,
                ("evaluate_broker_limits",),
                "When the absolute daily-loss cap is enabled, a reliable independently sourced loss amount is mandatory.",
            ),
            _fact(
                SafetyPathFact.FEES_TAXES,
                SafetyFactUsage.REQUIRED_FOR_SAFETY_DECISION,
                ("build_broker_execution_authorization", "evaluate_broker_limits"),
                "Conservative charges are added to authorization and order, account, symbol, daily, and allocation notionals.",
            ),
        ),
        key=lambda item: item.fact.value,
    )
)


FUBON_NEO_MINIMUM_TEST_PROFILE = MinimumTestExecutionProfile(
    environment=BrokerEnvironment.SANDBOX,
    endpoint=FUBON_NEO_TEST_ENDPOINT,
    product="TW_SECURITIES",
    trade_mode="CASH_STOCK",
    allowed_sides=(OrderSide.BUY, OrderSide.SELL),
    sell_rule="OWNED_AVAILABLE_QUANTITY_ONLY",
    lot_mode="COMMON_LOT",
    allowed_order_types=(OrderType.LIMIT,),
    allowed_time_in_force=(TimeInForce.DAY,),
    forbidden_features=(
        "DAY_TRADE",
        "LIVE_ENDPOINT",
        "MARGIN",
        "ODD_LOT",
        "SBL",
        "SHORT",
        "UNATTENDED_RETRY",
        "UNCOVERED_SHORT",
    ),
)


FUBON_NEO_CAPITAL_AUTHORITY = CapitalAuthorityProof(
    model=CapitalAuthorityModel.UNPROVEN,
    same_account_twd_cash=D0RequirementState.PROVEN,
    settlements_complete_without_double_counting=D0RequirementState.BLOCKED,
    broker_open_buy_exposure_complete=D0RequirementState.PROVEN,
    local_unresolved_reservations_complete=D0RequirementState.PROVEN,
    conservative_fees_and_taxes=D0RequirementState.BLOCKED,
    no_credit_assumptions=D0RequirementState.PROVEN,
    anomalies_fail_closed=D0RequirementState.PROVEN,
    cannot_overstate_available_capital=D0RequirementState.BLOCKED,
    formula="UNPROVEN: no reviewed securities identity can combine cash, settlements, open exposure, and charges without possible overstatement.",
)


class ProviderOrderMatchState(StrEnum):
    MATCHED = "MATCHED"
    NO_MATCH = "NO_MATCH"
    AMBIGUOUS = "AMBIGUOUS"


class LostAckDisposition(StrEnum):
    RECONCILED_EXISTING_ORDER = "RECONCILED_EXISTING_ORDER"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    UNKNOWN_SUBMISSION_STATE = "UNKNOWN_SUBMISSION_STATE"


class ProviderTagCollisionError(D0ReadinessModelError):
    """Raised before use when one short provider tag maps to another canonical ID."""


def derive_fubon_provider_correlation_tag(canonical_client_order_id: str) -> str:
    """Derive the versioned 10-character correlation tag; it is never identity."""

    if type(canonical_client_order_id) is not str or _CANONICAL_CLIENT_ID.fullmatch(canonical_client_order_id) is None:
        raise D0ReadinessModelError("canonical client order ID must remain full twst1-<64 lowercase hex>")
    material = f"{FUBON_PROVIDER_CORRELATION_TAG_VERSION}\0{canonical_client_order_id}"
    encoded = b32encode(sha256(material.encode("ascii")).digest()).decode("ascii")
    return "F" + encoded[:9]


def require_unambiguous_provider_tag_binding(
    provider_tag: str,
    canonical_client_order_id: str,
    existing_canonical_client_order_id: str | None,
) -> None:
    """Fail closed before Phase C persists a short-tag-to-full-ID mapping."""

    expected = derive_fubon_provider_correlation_tag(canonical_client_order_id)
    if provider_tag != expected:
        raise ProviderTagCollisionError("provider tag is not the deterministic tag for the canonical ID")
    if existing_canonical_client_order_id not in (None, canonical_client_order_id):
        raise ProviderTagCollisionError("provider tag collision requires reconciliation and blocks submission")


def resolve_fubon_lost_ack(match_state: ProviderOrderMatchState) -> LostAckDisposition:
    """Return a terminal/reconciliation disposition; absence never means retry."""

    if type(match_state) is not ProviderOrderMatchState:
        raise D0ReadinessModelError("provider match state must be exact")
    return {
        ProviderOrderMatchState.MATCHED: LostAckDisposition.RECONCILED_EXISTING_ORDER,
        ProviderOrderMatchState.NO_MATCH: LostAckDisposition.RECONCILIATION_REQUIRED,
        ProviderOrderMatchState.AMBIGUOUS: LostAckDisposition.UNKNOWN_SUBMISSION_STATE,
    }[match_state]


def _prerequisite(
    name: D0PrerequisiteName,
    state: D0RequirementState,
    authority: str,
    reason: str,
) -> D0PrerequisiteStatus:
    return D0PrerequisiteStatus(name, state, authority, reason)


FUBON_NEO_D0_PREREQUISITES = tuple(
    sorted(
        (
            _prerequisite(
                D0PrerequisiteName.OFFICIAL_TEST_PROVENANCE,
                D0RequirementState.PROVEN,
                "FUBON_NEO_TEST_CONNECTION_IDENTITY",
                "The existing closed configuration permits only the exact official TEST endpoint and SANDBOX environment.",
            ),
            _prerequisite(
                D0PrerequisiteName.REVIEWED_SDK_PROVIDER_CONTRACT,
                D0RequirementState.PROVEN,
                f"{FUBON_NEO_SOURCE_VERSION}/{FUBON_NEO_SDK_VERSION}",
                "The read-only adapter remains pinned to the reviewed SDK/provider projection and rejects version drift.",
            ),
            _prerequisite(
                D0PrerequisiteName.ACCOUNT_CAPITAL_AUTHORITY,
                D0RequirementState.BLOCKED,
                "FUBON_NEO_CAPITAL_AUTHORITY",
                "Buying power remains semantically unclassified and no complete conservative spendable-cash identity is proven.",
            ),
            _prerequisite(
                D0PrerequisiteName.POSITION_OPEN_ORDER_RECONCILIATION,
                D0RequirementState.PROVEN,
                "strict inventories/unrealized/get_order_results mapping plus Phase 56.5C reservations",
                "Same-account positions and supported nonterminal order exposure reconcile fail closed with local durable facts.",
            ),
            _prerequisite(
                D0PrerequisiteName.POSITION_VALUATION_EXPOSURE_AUTHORITY,
                D0RequirementState.BLOCKED,
                "BrokerPositionSnapshot.market_value",
                "Fubon mapping intentionally leaves market value unavailable and no reviewed valuation snapshot is bound.",
            ),
            _prerequisite(
                D0PrerequisiteName.TRADING_PERMISSION_PROOF,
                D0RequirementState.BLOCKED,
                "BrokerCapabilities.trading_permission",
                "Official read-only Neo securities documentation reviewed here does not prove exact account permission for the profile.",
            ),
            _prerequisite(
                D0PrerequisiteName.FEE_TAX_AUTHORITY,
                D0RequirementState.BLOCKED,
                "BrokerCapabilities.fee_estimate_support",
                "No provider estimate or complete versioned conservative Fubon fee/tax schedule is reviewed for this profile.",
            ),
            _prerequisite(
                D0PrerequisiteName.CLIENT_CORRELATION_LOST_ACK_SAFETY,
                D0RequirementState.BLOCKED,
                "user_def tag plus get_order_results",
                "The short tag is collision-checked and never canonical, but exact provider scan/query completeness is undocumented.",
            ),
            _prerequisite(
                D0PrerequisiteName.SESSION_PROOF,
                D0RequirementState.BLOCKED,
                "TradingSessionSnapshot",
                "No reviewed read-only source proves exact TEST calendar, state, permission, timezone TTL, and live distinction together.",
            ),
            _prerequisite(
                D0PrerequisiteName.DURABLE_ONE_SHOT_PRE_SUBMIT,
                D0RequirementState.PROVEN,
                "SQLiteBrokerSafetyStore.commit_pre_submit",
                "Phase 56.5C atomically consumes one authorization use under lease fencing with high-water and audit binding.",
            ),
            _prerequisite(
                D0PrerequisiteName.NO_LIVE_ENDPOINT,
                D0RequirementState.PROVEN,
                "FubonNeoTestConfig",
                "The candidate profile and adapter have no selectable production endpoint.",
            ),
        ),
        key=lambda item: item.name.value,
    )
)


_BLOCK_REASON_BY_PREREQUISITE = {
    D0PrerequisiteName.ACCOUNT_CAPITAL_AUTHORITY: D0BlockReason.ACCOUNT_CAPITAL_AUTHORITY_UNPROVEN,
    D0PrerequisiteName.POSITION_VALUATION_EXPOSURE_AUTHORITY: D0BlockReason.POSITION_VALUATION_AUTHORITY_UNPROVEN,
    D0PrerequisiteName.TRADING_PERMISSION_PROOF: D0BlockReason.TRADING_PERMISSION_UNPROVEN,
    D0PrerequisiteName.FEE_TAX_AUTHORITY: D0BlockReason.FEE_TAX_AUTHORITY_UNPROVEN,
    D0PrerequisiteName.CLIENT_CORRELATION_LOST_ACK_SAFETY: D0BlockReason.CLIENT_CORRELATION_QUERY_UNPROVEN,
    D0PrerequisiteName.SESSION_PROOF: D0BlockReason.SESSION_PROOF_UNPROVEN,
}


def _blocking_reasons(
    prerequisites: tuple[D0PrerequisiteStatus, ...],
) -> tuple[D0BlockReason, ...]:
    try:
        reasons = tuple(
            _BLOCK_REASON_BY_PREREQUISITE[item.name]
            for item in prerequisites
            if item.state is D0RequirementState.BLOCKED
        )
    except KeyError as exc:
        raise D0ReadinessModelError("a blocked prerequisite lacks a canonical reason") from exc
    return tuple(sorted(reasons, key=lambda item: item.value))


@dataclass(frozen=True, slots=True)
class FubonNeo56_5D0Readiness:
    """Complete non-forgeable Fubon pre-mutation readiness decision."""

    schema_version: str
    contract_version: str
    reviewed_evidence_version: str
    broker_id: str
    environment: BrokerEnvironment
    sdk_version: str
    prior_56_5d_gate: FubonNeo56_5DReadiness
    safety_path_matrix: tuple[BrokerSafetyPathFact, ...]
    minimum_test_profile: MinimumTestExecutionProfile
    capital_authority: CapitalAuthorityProof
    prerequisites: tuple[D0PrerequisiteStatus, ...]
    outcome: D0ReadinessOutcome
    blocking_reasons: tuple[D0BlockReason, ...]
    reviewed_source_urls: tuple[str, ...]
    _authority: InitVar[object]

    def __post_init__(self, _authority: object) -> None:
        if _authority is not _D0_AUTHORITY:
            raise D0ReadinessModelError("Fubon D0 readiness must come from the reviewed frozen contract")
        if (
            self.schema_version != D0_READINESS_SCHEMA_VERSION
            or self.contract_version != FUBON_NEO_D0_CONTRACT_VERSION
            or self.reviewed_evidence_version != FUBON_NEO_D0_REVIEW_VERSION
            or self.broker_id != FUBON_NEO_BROKER_ID
            or self.environment is not BrokerEnvironment.SANDBOX
            or self.sdk_version != FUBON_NEO_SDK_VERSION
        ):
            raise D0ReadinessModelError("Fubon D0 provenance differs from the reviewed TEST contract")
        if self.prior_56_5d_gate != current_fubon_neo_56_5d_readiness():
            raise D0ReadinessModelError("D0 must retain the exact #144 prerequisite result")
        if self.safety_path_matrix != FUBON_NEO_D0_SAFETY_PATH_MATRIX:
            raise D0ReadinessModelError("D0 path matrix differs from the field-by-field audit")
        if self.minimum_test_profile != FUBON_NEO_MINIMUM_TEST_PROFILE:
            raise D0ReadinessModelError("D0 profile is wider than the frozen candidate")
        if self.capital_authority != FUBON_NEO_CAPITAL_AUTHORITY:
            raise D0ReadinessModelError("capital authority differs from the reviewed proof")
        expected_outcome = derive_d0_outcome(self.prerequisites)
        if self.prerequisites != FUBON_NEO_D0_PREREQUISITES or self.outcome is not expected_outcome:
            raise D0ReadinessModelError("D0 outcome does not match every reviewed prerequisite")
        if self.blocking_reasons != _blocking_reasons(self.prerequisites):
            raise D0ReadinessModelError("D0 blocking reasons are incomplete or noncanonical")
        if self.reviewed_source_urls != FUBON_NEO_D0_REVIEWED_SOURCE_URLS:
            raise D0ReadinessModelError("D0 source set differs from the reviewed official documentation")


_CURRENT_FUBON_NEO_D0_READINESS = FubonNeo56_5D0Readiness(
    schema_version=D0_READINESS_SCHEMA_VERSION,
    contract_version=FUBON_NEO_D0_CONTRACT_VERSION,
    reviewed_evidence_version=FUBON_NEO_D0_REVIEW_VERSION,
    broker_id=FUBON_NEO_BROKER_ID,
    environment=BrokerEnvironment.SANDBOX,
    sdk_version=FUBON_NEO_SDK_VERSION,
    prior_56_5d_gate=current_fubon_neo_56_5d_readiness(),
    safety_path_matrix=FUBON_NEO_D0_SAFETY_PATH_MATRIX,
    minimum_test_profile=FUBON_NEO_MINIMUM_TEST_PROFILE,
    capital_authority=FUBON_NEO_CAPITAL_AUTHORITY,
    prerequisites=FUBON_NEO_D0_PREREQUISITES,
    outcome=D0ReadinessOutcome.BLOCKED,
    blocking_reasons=_blocking_reasons(FUBON_NEO_D0_PREREQUISITES),
    reviewed_source_urls=FUBON_NEO_D0_REVIEWED_SOURCE_URLS,
    _authority=_D0_AUTHORITY,
)


def current_fubon_neo_56_5d0_readiness() -> FubonNeo56_5D0Readiness:
    """Return the immutable reviewed result without broker or network I/O."""

    return _CURRENT_FUBON_NEO_D0_READINESS


__all__ = [
    "FUBON_NEO_CAPITAL_AUTHORITY",
    "FUBON_NEO_D0_CONTRACT_VERSION",
    "FUBON_NEO_D0_PREREQUISITES",
    "FUBON_NEO_D0_REVIEWED_SOURCE_URLS",
    "FUBON_NEO_D0_REVIEW_VERSION",
    "FUBON_NEO_D0_SAFETY_PATH_MATRIX",
    "FUBON_NEO_MINIMUM_TEST_PROFILE",
    "FUBON_PROVIDER_CORRELATION_TAG_VERSION",
    "FUBON_PROVIDER_NAME",
    "FubonNeo56_5D0Readiness",
    "LostAckDisposition",
    "ProviderOrderMatchState",
    "ProviderTagCollisionError",
    "current_fubon_neo_56_5d0_readiness",
    "derive_fubon_provider_correlation_tag",
    "require_unambiguous_provider_tag_binding",
    "resolve_fubon_lost_ack",
]
