"""Typed broker-neutral evidence and provider-readiness contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


PROVIDER_READINESS_SCHEMA_VERSION = "provider-account-readiness-v1"


class ProviderReadinessModelError(ValueError):
    """Raised when provider evidence or readiness is not exact and canonical."""


class BrokerAccountFact(StrEnum):
    CASH = "CASH"
    BUYING_POWER = "BUYING_POWER"
    EQUITY = "EQUITY"
    POSITIONS = "POSITIONS"
    OPEN_ORDERS = "OPEN_ORDERS"


class ProviderMappingClassification(StrEnum):
    EXACT_AUTHORITATIVE = "EXACT_AUTHORITATIVE"
    DERIVED_AUTHORITATIVE = "DERIVED_AUTHORITATIVE"
    UNCLASSIFIED = "UNCLASSIFIED"
    UNAVAILABLE = "UNAVAILABLE"
    CONTRADICTORY = "CONTRADICTORY"


class ProviderProductScope(StrEnum):
    SECURITIES = "SECURITIES"
    FUTURES_OPTIONS = "FUTURES_OPTIONS"


class ProviderFactScope(StrEnum):
    ACCOUNT = "ACCOUNT"
    POSITION = "POSITION"
    SYMBOL = "SYMBOL"
    ORDER = "ORDER"


class ProviderReadinessState(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"


class ProviderReadinessCheckState(StrEnum):
    PROVEN = "PROVEN"
    BLOCKED = "BLOCKED"


class ProviderReadinessBlockReason(StrEnum):
    BUYING_POWER_UNAVAILABLE = "BUYING_POWER_UNAVAILABLE"
    BUYING_POWER_SEMANTICS_UNCLASSIFIED = "BUYING_POWER_SEMANTICS_UNCLASSIFIED"
    EQUITY_UNAVAILABLE = "EQUITY_UNAVAILABLE"
    ACCOUNT_FACTS_INCOMPLETE = "ACCOUNT_FACTS_INCOMPLETE"
    TEST_PROVENANCE_UNPROVEN = "TEST_PROVENANCE_UNPROVEN"
    SDK_VERSION_MISMATCH = "SDK_VERSION_MISMATCH"
    COMPLETE_ACCOUNT_SNAPSHOT_UNPROVEN = "COMPLETE_ACCOUNT_SNAPSHOT_UNPROVEN"
    RECONCILIATION_INPUTS_INCOMPLETE = "RECONCILIATION_INPUTS_INCOMPLETE"


def _exact_text(name: str, value: object) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ProviderReadinessModelError(f"{name} must be an exact non-empty string")
    return value


def _exact_enum(name: str, value: object, expected: type[StrEnum]) -> None:
    if type(value) is not expected:
        raise ProviderReadinessModelError(f"{name} must be exact {expected.__name__}")


def _canonical_text_tuple(name: str, value: object) -> tuple[str, ...]:
    if type(value) is not tuple or not value:
        raise ProviderReadinessModelError(f"{name} must be a non-empty immutable tuple")
    for item in value:
        _exact_text(name, item)
    if value != tuple(sorted(value)) or len(set(value)) != len(value):
        raise ProviderReadinessModelError(f"{name} must be unique and canonically ordered")
    return value


@dataclass(frozen=True, slots=True)
class ProviderDerivationProof:
    """Complete proof required before a provider fact may be derived."""

    accounting_identity: str
    input_observation_identities: tuple[str, ...]
    account_scope: str
    currency: str
    freshness_rule: str
    settlement_rule: str
    open_order_exposure_rule: str
    instrument_mode_rule: str
    missing_duplicate_contradiction_rule: str
    inputs_authoritative: bool
    complete_accounting_identity: bool
    same_account: bool
    same_currency: bool
    sufficiently_fresh: bool
    settlement_complete: bool
    open_orders_complete: bool
    instrument_modes_complete: bool
    no_market_estimate: bool
    missing_duplicate_contradiction_fail_closed: bool
    cannot_overstate_available_capital: bool

    def __post_init__(self) -> None:
        for name in (
            "accounting_identity",
            "account_scope",
            "currency",
            "freshness_rule",
            "settlement_rule",
            "open_order_exposure_rule",
            "instrument_mode_rule",
            "missing_duplicate_contradiction_rule",
        ):
            _exact_text(name, getattr(self, name))
        _canonical_text_tuple(
            "input_observation_identities",
            self.input_observation_identities,
        )
        required_proofs = (
            "inputs_authoritative",
            "complete_accounting_identity",
            "same_account",
            "same_currency",
            "sufficiently_fresh",
            "settlement_complete",
            "open_orders_complete",
            "instrument_modes_complete",
            "no_market_estimate",
            "missing_duplicate_contradiction_fail_closed",
            "cannot_overstate_available_capital",
        )
        if any(type(getattr(self, name)) is not bool or not getattr(self, name) for name in required_proofs):
            raise ProviderReadinessModelError(
                "every exact derivation obligation must be explicitly proven"
            )


@dataclass(frozen=True, slots=True)
class ProviderAccountFactEvidence:
    """One documented provider observation classified against one A2 fact."""

    observation_identity: str
    documented_meaning: str
    candidate_fact: BrokerAccountFact
    classification: ProviderMappingClassification
    product_scope: ProviderProductScope
    fact_scope: ProviderFactScope
    source_url: str
    source_version: str
    reason: str
    derivation_proof: ProviderDerivationProof | None = None

    def __post_init__(self) -> None:
        for name in (
            "observation_identity",
            "documented_meaning",
            "source_url",
            "source_version",
            "reason",
        ):
            _exact_text(name, getattr(self, name))
        _exact_enum("candidate_fact", self.candidate_fact, BrokerAccountFact)
        _exact_enum("classification", self.classification, ProviderMappingClassification)
        _exact_enum("product_scope", self.product_scope, ProviderProductScope)
        _exact_enum("fact_scope", self.fact_scope, ProviderFactScope)
        if not self.source_url.startswith("https://"):
            raise ProviderReadinessModelError("source_url must be an HTTPS primary source")
        if self.classification is ProviderMappingClassification.DERIVED_AUTHORITATIVE:
            if type(self.derivation_proof) is not ProviderDerivationProof:
                raise ProviderReadinessModelError(
                    "derived authority requires a complete typed accounting proof"
                )
        elif self.derivation_proof is not None:
            raise ProviderReadinessModelError(
                "only derived authoritative evidence may carry a derivation proof"
            )


@dataclass(frozen=True, slots=True)
class ProviderAccountFactStatus:
    """Typed readiness for one mandatory broker-neutral account fact."""

    fact: BrokerAccountFact
    classification: ProviderMappingClassification
    evidence_identities: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        _exact_enum("fact", self.fact, BrokerAccountFact)
        _exact_enum("classification", self.classification, ProviderMappingClassification)
        _canonical_text_tuple("evidence_identities", self.evidence_identities)
        _exact_text("reason", self.reason)

    @property
    def is_ready(self) -> bool:
        return self.classification in (
            ProviderMappingClassification.EXACT_AUTHORITATIVE,
            ProviderMappingClassification.DERIVED_AUTHORITATIVE,
        )


__all__ = [
    "PROVIDER_READINESS_SCHEMA_VERSION",
    "BrokerAccountFact",
    "ProviderAccountFactEvidence",
    "ProviderAccountFactStatus",
    "ProviderDerivationProof",
    "ProviderFactScope",
    "ProviderMappingClassification",
    "ProviderProductScope",
    "ProviderReadinessBlockReason",
    "ProviderReadinessCheckState",
    "ProviderReadinessModelError",
    "ProviderReadinessState",
]
