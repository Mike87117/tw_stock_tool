"""Versioned Fubon Neo securities account-fact evidence and readiness gate."""

from __future__ import annotations

from dataclasses import InitVar, dataclass
from hashlib import sha256
import json

from tw_stock_tool.broker_adapters.fubon_neo.config import (
    FUBON_NEO_BROKER_ID,
    FUBON_NEO_SDK_VERSION,
    FUBON_NEO_SOURCE_VERSION,
    FUBON_NEO_TEST_CONNECTION_IDENTITY,
)
from tw_stock_tool.broker_safety import (
    PROVIDER_READINESS_SCHEMA_VERSION,
    BrokerAccountFact,
    BrokerEnvironment,
    ProviderAccountFactEvidence,
    ProviderAccountFactStatus,
    ProviderFactScope,
    ProviderMappingClassification,
    ProviderProductScope,
    ProviderReadinessBlockReason,
    ProviderReadinessCheckState,
    ProviderReadinessModelError,
    ProviderReadinessState,
)


FUBON_NEO_ACCOUNT_FACT_CONTRACT_VERSION = "fubon-neo-securities-account-facts-v1"
FUBON_NEO_ACCOUNT_EVIDENCE_VERSION = "official-fubon-docs-reviewed-2026-08-19-v1"
_READINESS_AUTHORITY = object()

_BALANCE_URL = "https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/Balance/"
_SETTLEMENT_URL = "https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/QuerySettlement/"
_INVENTORIES_URL = "https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/Inventories/"
_UNREALIZED_URL = "https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/UnrealizedPnLDetail/"
_REALIZED_URL = "https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/RealizedPnLDetail/"
_REALIZED_SUMMARY_URL = "https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/RealizedPnLSum/"
_MAINTENANCE_URL = "https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/Maintenance/"
_MARGIN_QUOTA_URL = "https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/trade/MarginQuota/"
_ORDER_RESULTS_URL = "https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/trade/GetOrderResults/"
_FUTOPT_EQUITY_URL = "https://www.fbs.com.tw/TradeAPI/docs/trading-future/guide/account_example/"


def _evidence(
    observation_identity: str,
    documented_meaning: str,
    candidate_fact: BrokerAccountFact,
    classification: ProviderMappingClassification,
    product_scope: ProviderProductScope,
    fact_scope: ProviderFactScope,
    source_url: str,
    reason: str,
) -> ProviderAccountFactEvidence:
    return ProviderAccountFactEvidence(
        observation_identity=observation_identity,
        documented_meaning=documented_meaning,
        candidate_fact=candidate_fact,
        classification=classification,
        product_scope=product_scope,
        fact_scope=fact_scope,
        source_url=source_url,
        source_version=FUBON_NEO_ACCOUNT_EVIDENCE_VERSION,
        reason=reason,
    )


FUBON_NEO_ACCOUNT_FACT_EVIDENCE = (
    _evidence(
        "accounting.bank_remain.balance",
        "Bank balance for the selected securities account and currency.",
        BrokerAccountFact.CASH,
        ProviderMappingClassification.EXACT_AUTHORITATIVE,
        ProviderProductScope.SECURITIES,
        ProviderFactScope.ACCOUNT,
        _BALANCE_URL,
        "The documented balance field is the authoritative settled cash observation used by the existing adapter.",
    ),
    _evidence(
        "accounting.bank_remain.available_balance",
        "Available bank balance for the selected securities account and currency.",
        BrokerAccountFact.BUYING_POWER,
        ProviderMappingClassification.UNCLASSIFIED,
        ProviderProductScope.SECURITIES,
        ProviderFactScope.ACCOUNT,
        _BALANCE_URL,
        "The securities documentation does not define exact equivalence to account-wide trading buying power or reserved open-order exposure.",
    ),
    _evidence(
        "accounting.query_settlement.details[*]",
        "Dated buy, sell, fee, tax, and net receivable/payable settlement amounts.",
        BrokerAccountFact.BUYING_POWER,
        ProviderMappingClassification.UNCLASSIFIED,
        ProviderProductScope.SECURITIES,
        ProviderFactScope.ACCOUNT,
        _SETTLEMENT_URL,
        "Settlement rows do not document a complete purchasing-power identity and may overlap effects already reflected in bank balances.",
    ),
    _evidence(
        "accounting.inventories[*]",
        "Per-symbol securities inventory quantities, trading mode, and tradable quantity.",
        BrokerAccountFact.POSITIONS,
        ProviderMappingClassification.EXACT_AUTHORITATIVE,
        ProviderProductScope.SECURITIES,
        ProviderFactScope.POSITION,
        _INVENTORIES_URL,
        "The existing strict mapper accepts only same-account, same-date cash-stock common-lot inventory with exact quantity accounting.",
    ),
    _evidence(
        "accounting.unrealized_gains_and_loses[*]",
        "Per-position cost price, quantity, and unrealized profit or loss.",
        BrokerAccountFact.POSITIONS,
        ProviderMappingClassification.EXACT_AUTHORITATIVE,
        ProviderProductScope.SECURITIES,
        ProviderFactScope.POSITION,
        _UNREALIZED_URL,
        "The existing strict mapper reconciles same-account and same-date rows to inventory and does not treat P/L as account equity.",
    ),
    _evidence(
        "accounting.realized_gains_and_loses[*]",
        "Per-symbol realized profit and realized loss for filled securities trades.",
        BrokerAccountFact.EQUITY,
        ProviderMappingClassification.UNCLASSIFIED,
        ProviderProductScope.SECURITIES,
        ProviderFactScope.POSITION,
        _REALIZED_URL,
        "Realized P/L is not a documented complete account-equity field or accounting identity.",
    ),
    _evidence(
        "accounting.realized_gains_and_loses_summary[*]",
        "Per-symbol realized profit-and-loss summary over a documented date range.",
        BrokerAccountFact.EQUITY,
        ProviderMappingClassification.UNCLASSIFIED,
        ProviderProductScope.SECURITIES,
        ProviderFactScope.POSITION,
        _REALIZED_SUMMARY_URL,
        "A realized P/L summary does not include all assets, liabilities, unsettled effects, and positions required for account equity.",
    ),
    _evidence(
        "accounting.maintenance",
        "Account and position maintenance ratios, financed values, collateral, loans, and interest for margin or short positions.",
        BrokerAccountFact.EQUITY,
        ProviderMappingClassification.UNCLASSIFIED,
        ProviderProductScope.SECURITIES,
        ProviderFactScope.ACCOUNT,
        _MAINTENANCE_URL,
        "The additional official securities endpoint documents maintenance components, not a complete securities account-equity identity.",
    ),
    _evidence(
        "stock.margin_quota(account,stock_no)",
        "Per-symbol margin and short original/tradable quota and ratios.",
        BrokerAccountFact.BUYING_POWER,
        ProviderMappingClassification.UNCLASSIFIED,
        ProviderProductScope.SECURITIES,
        ProviderFactScope.SYMBOL,
        _MARGIN_QUOTA_URL,
        "Symbol-specific financing and short quotas cannot establish account-wide securities buying power.",
    ),
    _evidence(
        "stock.get_order_results(account)",
        "Current securities order result rows including status and exact remaining/fill quantities.",
        BrokerAccountFact.OPEN_ORDERS,
        ProviderMappingClassification.EXACT_AUTHORITATIVE,
        ProviderProductScope.SECURITIES,
        ProviderFactScope.ORDER,
        _ORDER_RESULTS_URL,
        "The existing strict mapper retains only supported nonterminal securities exposure and rejects ambiguous status histories.",
    ),
    _evidence(
        "futopt_accounting.query_margin_equity",
        "Futures/options margin equity, available margin, and withholding fields.",
        BrokerAccountFact.EQUITY,
        ProviderMappingClassification.UNAVAILABLE,
        ProviderProductScope.FUTURES_OPTIONS,
        ProviderFactScope.ACCOUNT,
        _FUTOPT_EQUITY_URL,
        "A futures/options accounting object is the wrong product scope and cannot authorize a securities account-equity fact.",
    ),
)


def _evidence_digest(evidence: tuple[ProviderAccountFactEvidence, ...]) -> str:
    payload = [
        {
            "candidate_fact": item.candidate_fact.value,
            "classification": item.classification.value,
            "documented_meaning": item.documented_meaning,
            "derivation_proof": None,
            "fact_scope": item.fact_scope.value,
            "observation_identity": item.observation_identity,
            "product_scope": item.product_scope.value,
            "reason": item.reason,
            "source_url": item.source_url,
            "source_version": item.source_version,
        }
        for item in evidence
    ]
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


FUBON_NEO_ACCOUNT_EVIDENCE_SHA256 = "f34931c057487b4571462826de1d569cefe65fb096a8066ac0a4a8bd595f754b"
if _evidence_digest(FUBON_NEO_ACCOUNT_FACT_EVIDENCE) != FUBON_NEO_ACCOUNT_EVIDENCE_SHA256:
    raise RuntimeError("Fubon Neo account-fact evidence differs from its reviewed digest")


@dataclass(frozen=True, slots=True)
class FubonNeoAccountFactReadiness:
    """Complete reviewed readiness result for the securities A2 account facts."""

    schema_version: str
    broker_id: str
    environment: BrokerEnvironment
    provider_contract_version: str
    account_fact_contract_version: str
    sdk_version: str
    reviewed_evidence_version: str
    cash: ProviderAccountFactStatus
    buying_power: ProviderAccountFactStatus
    equity: ProviderAccountFactStatus
    positions: ProviderAccountFactStatus
    open_orders: ProviderAccountFactStatus
    overall: ProviderReadinessState
    blocking_reasons: tuple[ProviderReadinessBlockReason, ...]
    evidence_digest: str
    _authority: InitVar[object]

    def __post_init__(self, _authority: object) -> None:
        if _authority is not _READINESS_AUTHORITY:
            raise ProviderReadinessModelError("Fubon readiness must be built from reviewed evidence")
        if self.schema_version != PROVIDER_READINESS_SCHEMA_VERSION:
            raise ProviderReadinessModelError("unsupported provider-readiness schema")
        if self.broker_id != FUBON_NEO_BROKER_ID or self.environment is not BrokerEnvironment.SANDBOX:
            raise ProviderReadinessModelError("readiness broker/environment is outside the reviewed TEST scope")
        if self.provider_contract_version != FUBON_NEO_SOURCE_VERSION or self.sdk_version != FUBON_NEO_SDK_VERSION:
            raise ProviderReadinessModelError("readiness provider/SDK version is not reviewed")
        if self.account_fact_contract_version != FUBON_NEO_ACCOUNT_FACT_CONTRACT_VERSION:
            raise ProviderReadinessModelError("account-fact contract version is not reviewed")
        if self.reviewed_evidence_version != FUBON_NEO_ACCOUNT_EVIDENCE_VERSION:
            raise ProviderReadinessModelError("readiness evidence version is not reviewed")
        expected_facts = (
            BrokerAccountFact.CASH,
            BrokerAccountFact.BUYING_POWER,
            BrokerAccountFact.EQUITY,
            BrokerAccountFact.POSITIONS,
            BrokerAccountFact.OPEN_ORDERS,
        )
        statuses = (self.cash, self.buying_power, self.equity, self.positions, self.open_orders)
        if any(type(item) is not ProviderAccountFactStatus for item in statuses):
            raise ProviderReadinessModelError("all fact statuses must be exact typed results")
        if tuple(item.fact for item in statuses) != expected_facts:
            raise ProviderReadinessModelError("fact statuses do not cover the exact mandatory A2 facts")
        expected_overall = (
            ProviderReadinessState.READY
            if all(item.is_ready for item in statuses)
            else ProviderReadinessState.BLOCKED
        )
        if type(self.overall) is not ProviderReadinessState or self.overall is not expected_overall:
            raise ProviderReadinessModelError("overall readiness does not match mandatory fact readiness")
        expected_reasons = () if expected_overall is ProviderReadinessState.READY else (
            ProviderReadinessBlockReason.BUYING_POWER_SEMANTICS_UNCLASSIFIED,
            ProviderReadinessBlockReason.EQUITY_UNAVAILABLE,
            ProviderReadinessBlockReason.ACCOUNT_FACTS_INCOMPLETE,
        )
        if self.blocking_reasons != expected_reasons:
            raise ProviderReadinessModelError("blocking reasons are incomplete or noncanonical")
        if self.evidence_digest != FUBON_NEO_ACCOUNT_EVIDENCE_SHA256:
            raise ProviderReadinessModelError("readiness evidence digest is not the reviewed matrix")


def _status(
    fact: BrokerAccountFact,
    classification: ProviderMappingClassification,
    identities: tuple[str, ...],
    reason: str,
) -> ProviderAccountFactStatus:
    return ProviderAccountFactStatus(
        fact=fact,
        classification=classification,
        evidence_identities=identities,
        reason=reason,
    )


_CURRENT_ACCOUNT_FACT_READINESS = FubonNeoAccountFactReadiness(
    schema_version=PROVIDER_READINESS_SCHEMA_VERSION,
    broker_id=FUBON_NEO_BROKER_ID,
    environment=BrokerEnvironment.SANDBOX,
    provider_contract_version=FUBON_NEO_SOURCE_VERSION,
    account_fact_contract_version=FUBON_NEO_ACCOUNT_FACT_CONTRACT_VERSION,
    sdk_version=FUBON_NEO_SDK_VERSION,
    reviewed_evidence_version=FUBON_NEO_ACCOUNT_EVIDENCE_VERSION,
    cash=_status(
        BrokerAccountFact.CASH,
        ProviderMappingClassification.EXACT_AUTHORITATIVE,
        ("accounting.bank_remain.balance",),
        "The selected-account TWD bank balance is an authoritative settled cash observation.",
    ),
    buying_power=_status(
        BrokerAccountFact.BUYING_POWER,
        ProviderMappingClassification.UNCLASSIFIED,
        (
            "accounting.bank_remain.available_balance",
            "accounting.query_settlement.details[*]",
            "stock.margin_quota(account,stock_no)",
        ),
        "No reviewed securities field or complete accounting identity proves account-wide buying power without possible overstatement.",
    ),
    equity=_status(
        BrokerAccountFact.EQUITY,
        ProviderMappingClassification.UNAVAILABLE,
        (
            "accounting.maintenance",
            "accounting.realized_gains_and_loses[*]",
            "accounting.realized_gains_and_loses_summary[*]",
            "futopt_accounting.query_margin_equity",
        ),
        "Official securities surfaces expose components and P/L but no complete account equity; futures/options equity is out of scope.",
    ),
    positions=_status(
        BrokerAccountFact.POSITIONS,
        ProviderMappingClassification.EXACT_AUTHORITATIVE,
        (
            "accounting.inventories[*]",
            "accounting.unrealized_gains_and_loses[*]",
        ),
        "Strict same-account, same-date inventory and unrealized rows prove the supported cash-stock position projection.",
    ),
    open_orders=_status(
        BrokerAccountFact.OPEN_ORDERS,
        ProviderMappingClassification.EXACT_AUTHORITATIVE,
        ("stock.get_order_results(account)",),
        "Strict current order-result reconciliation proves supported nonterminal open-order exposure.",
    ),
    overall=ProviderReadinessState.BLOCKED,
    blocking_reasons=(
        ProviderReadinessBlockReason.BUYING_POWER_SEMANTICS_UNCLASSIFIED,
        ProviderReadinessBlockReason.EQUITY_UNAVAILABLE,
        ProviderReadinessBlockReason.ACCOUNT_FACTS_INCOMPLETE,
    ),
    evidence_digest=FUBON_NEO_ACCOUNT_EVIDENCE_SHA256,
    _authority=_READINESS_AUTHORITY,
)


def current_fubon_neo_account_fact_readiness() -> FubonNeoAccountFactReadiness:
    """Return the immutable reviewed result; runtime observations cannot override it."""

    return _CURRENT_ACCOUNT_FACT_READINESS


@dataclass(frozen=True, slots=True)
class FubonNeo56_5DReadiness:
    """Pure gate that must be READY before any separately authorized 56.5D work."""

    schema_version: str
    broker_id: str
    environment: BrokerEnvironment
    provider_contract_version: str
    account_fact_contract_version: str
    sdk_version: str
    official_test_provenance: ProviderReadinessCheckState
    sdk_version_match: ProviderReadinessCheckState
    complete_account_snapshot_capability: ProviderReadinessCheckState
    position_open_order_reconciliation: ProviderReadinessCheckState
    provider_account_fact_readiness: FubonNeoAccountFactReadiness
    overall: ProviderReadinessState
    blocking_reasons: tuple[ProviderReadinessBlockReason, ...]
    _authority: InitVar[object]

    def __post_init__(self, _authority: object) -> None:
        if _authority is not _READINESS_AUTHORITY:
            raise ProviderReadinessModelError("56.5D readiness must be built from reviewed evidence")
        if (
            self.schema_version != PROVIDER_READINESS_SCHEMA_VERSION
            or self.broker_id != FUBON_NEO_BROKER_ID
            or self.environment is not BrokerEnvironment.SANDBOX
            or self.provider_contract_version != FUBON_NEO_SOURCE_VERSION
            or self.account_fact_contract_version != FUBON_NEO_ACCOUNT_FACT_CONTRACT_VERSION
            or self.sdk_version != FUBON_NEO_SDK_VERSION
        ):
            raise ProviderReadinessModelError("56.5D gate provenance is not the reviewed TEST contract")
        checks = (
            self.official_test_provenance,
            self.sdk_version_match,
            self.complete_account_snapshot_capability,
            self.position_open_order_reconciliation,
        )
        if any(type(item) is not ProviderReadinessCheckState for item in checks):
            raise ProviderReadinessModelError("56.5D gate checks must be exact typed states")
        if type(self.provider_account_fact_readiness) is not FubonNeoAccountFactReadiness:
            raise ProviderReadinessModelError("56.5D gate requires exact provider account-fact readiness")
        expected_overall = (
            ProviderReadinessState.READY
            if all(item is ProviderReadinessCheckState.PROVEN for item in checks)
            and self.provider_account_fact_readiness.overall is ProviderReadinessState.READY
            else ProviderReadinessState.BLOCKED
        )
        if type(self.overall) is not ProviderReadinessState or self.overall is not expected_overall:
            raise ProviderReadinessModelError("56.5D overall result does not match its prerequisites")
        expected_reasons = self.provider_account_fact_readiness.blocking_reasons
        if self.complete_account_snapshot_capability is ProviderReadinessCheckState.BLOCKED:
            expected_reasons += (ProviderReadinessBlockReason.COMPLETE_ACCOUNT_SNAPSHOT_UNPROVEN,)
        if self.official_test_provenance is ProviderReadinessCheckState.BLOCKED:
            expected_reasons += (ProviderReadinessBlockReason.TEST_PROVENANCE_UNPROVEN,)
        if self.sdk_version_match is ProviderReadinessCheckState.BLOCKED:
            expected_reasons += (ProviderReadinessBlockReason.SDK_VERSION_MISMATCH,)
        if self.position_open_order_reconciliation is ProviderReadinessCheckState.BLOCKED:
            expected_reasons += (ProviderReadinessBlockReason.RECONCILIATION_INPUTS_INCOMPLETE,)
        if self.blocking_reasons != expected_reasons:
            raise ProviderReadinessModelError("56.5D blocking reasons are incomplete or noncanonical")


_CURRENT_56_5D_READINESS = FubonNeo56_5DReadiness(
    schema_version=PROVIDER_READINESS_SCHEMA_VERSION,
    broker_id=FUBON_NEO_BROKER_ID,
    environment=BrokerEnvironment.SANDBOX,
    provider_contract_version=FUBON_NEO_SOURCE_VERSION,
    account_fact_contract_version=FUBON_NEO_ACCOUNT_FACT_CONTRACT_VERSION,
    sdk_version=FUBON_NEO_SDK_VERSION,
    official_test_provenance=(
        ProviderReadinessCheckState.PROVEN
        if FUBON_NEO_TEST_CONNECTION_IDENTITY.provider_contract_version == FUBON_NEO_SOURCE_VERSION
        and FUBON_NEO_TEST_CONNECTION_IDENTITY.environment is BrokerEnvironment.SANDBOX
        else ProviderReadinessCheckState.BLOCKED
    ),
    sdk_version_match=(
        ProviderReadinessCheckState.PROVEN
        if FUBON_NEO_TEST_CONNECTION_IDENTITY.sdk_version == FUBON_NEO_SDK_VERSION
        else ProviderReadinessCheckState.BLOCKED
    ),
    complete_account_snapshot_capability=ProviderReadinessCheckState.BLOCKED,
    position_open_order_reconciliation=ProviderReadinessCheckState.PROVEN,
    provider_account_fact_readiness=_CURRENT_ACCOUNT_FACT_READINESS,
    overall=ProviderReadinessState.BLOCKED,
    blocking_reasons=_CURRENT_ACCOUNT_FACT_READINESS.blocking_reasons
    + (ProviderReadinessBlockReason.COMPLETE_ACCOUNT_SNAPSHOT_UNPROVEN,),
    _authority=_READINESS_AUTHORITY,
)


def current_fubon_neo_56_5d_readiness() -> FubonNeo56_5DReadiness:
    """Return the immutable prerequisite gate; this function performs no broker I/O."""

    return _CURRENT_56_5D_READINESS


__all__ = [
    "FUBON_NEO_ACCOUNT_EVIDENCE_SHA256",
    "FUBON_NEO_ACCOUNT_EVIDENCE_VERSION",
    "FUBON_NEO_ACCOUNT_FACT_CONTRACT_VERSION",
    "FUBON_NEO_ACCOUNT_FACT_EVIDENCE",
    "FubonNeo56_5DReadiness",
    "FubonNeoAccountFactReadiness",
    "current_fubon_neo_56_5d_readiness",
    "current_fubon_neo_account_fact_readiness",
]
