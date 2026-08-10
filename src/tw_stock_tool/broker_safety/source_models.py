"""Immutable Phase 56.5A1 source, progression, and anti-rollback models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import hashlib
import json
import re
from typing import Any
from uuid import UUID

from tw_stock_tool.forward_paper.eligibility_models import ForwardEligibilityState


SOURCE_SCHEMA_VERSION = "1.0"
PROGRESSION_ARTIFACT_TYPE = "forward_eligibility_progression"
HANDOFF_ARTIFACT_TYPE = "broker_safety_source_handoff"
HIGH_WATER_MARK_ARTIFACT_TYPE = "forward_eligibility_high_water_mark"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class BrokerSafetySourceModelError(ValueError):
    """Raised when a broker-safety source contract is invalid."""


def _clean(name: str, value: Any) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise BrokerSafetySourceModelError(
            f"{name} must be an exact clean non-empty string"
        )
    return value


def _uuid(name: str, value: Any) -> str:
    value = _clean(name, value)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise BrokerSafetySourceModelError(
            f"{name} must be a canonical lowercase UUID v4"
        ) from exc
    if parsed.version != 4 or str(parsed) != value:
        raise BrokerSafetySourceModelError(
            f"{name} must be a canonical lowercase UUID v4"
        )
    return value


def _sha(name: str, value: Any) -> str:
    value = _clean(name, value)
    if _SHA256.fullmatch(value) is None:
        raise BrokerSafetySourceModelError(f"{name} must be a lowercase SHA-256")
    return value


def _timestamp(name: str, value: Any, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    value = _clean(name, value)
    try:
        parsed = datetime.strptime(value, _TIMESTAMP_FORMAT)
    except ValueError as exc:
        raise BrokerSafetySourceModelError(
            f"{name} must use YYYY-MM-DDTHH:MM:SSZ"
        ) from exc
    if parsed.strftime(_TIMESTAMP_FORMAT) != value:
        raise BrokerSafetySourceModelError(
            f"{name} must use YYYY-MM-DDTHH:MM:SSZ"
        )
    return value


def _count(name: str, value: Any) -> int:
    if type(value) is not int or value < 0:
        raise BrokerSafetySourceModelError(
            f"{name} must be an exact non-negative int"
        )
    return value


def _canonical_sha256(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BrokerSafetySourceModelError(
            f"canonical digest input is invalid: {exc}"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ForwardEligibilityLineageKey:
    activation_id: str
    strategy_id: str
    policy_id: str
    policy_version: str

    def __post_init__(self) -> None:
        _uuid("activation_id", self.activation_id)
        for name in ("strategy_id", "policy_id", "policy_version"):
            _clean(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class ForwardEligibilityDecisionAnchor:
    recommendation_id: str
    recommendation_sha256: str
    observed_at: str
    symbol: str
    decision_sha256: str

    def __post_init__(self) -> None:
        _uuid("recommendation_id", self.recommendation_id)
        _sha("recommendation_sha256", self.recommendation_sha256)
        _timestamp("observed_at", self.observed_at)
        _clean("symbol", self.symbol)
        _sha("decision_sha256", self.decision_sha256)


def _lineage_payload(value: ForwardEligibilityLineageKey) -> dict[str, Any]:
    return {
        "activation_id": value.activation_id,
        "strategy_id": value.strategy_id,
        "policy_id": value.policy_id,
        "policy_version": value.policy_version,
    }


def _anchor_payload(value: ForwardEligibilityDecisionAnchor) -> dict[str, Any]:
    return {
        "recommendation_id": value.recommendation_id,
        "recommendation_sha256": value.recommendation_sha256,
        "observed_at": value.observed_at,
        "symbol": value.symbol,
        "decision_sha256": value.decision_sha256,
    }


def _progression_payload(
    *,
    lineage_key: ForwardEligibilityLineageKey,
    run_id: str,
    publication_id: str,
    publication_index_sha256: str,
    qualification_evaluation_id: str,
    eligibility_id: str,
    eligibility_state: ForwardEligibilityState,
    eligibility_sha256: str,
    metrics_id: str,
    metrics_sha256: str,
    ledger_id: str,
    ledger_sha256: str,
    decision_count: int,
    last_observed_at: str | None,
    recommendation_anchors: tuple[ForwardEligibilityDecisionAnchor, ...],
) -> dict[str, Any]:
    return {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "artifact_type": PROGRESSION_ARTIFACT_TYPE,
        "lineage_key": _lineage_payload(lineage_key),
        "run_id": run_id,
        "publication_id": publication_id,
        "publication_index_sha256": publication_index_sha256,
        "qualification_evaluation_id": qualification_evaluation_id,
        "eligibility_id": eligibility_id,
        "eligibility_state": eligibility_state.value,
        "eligibility_sha256": eligibility_sha256,
        "metrics_id": metrics_id,
        "metrics_sha256": metrics_sha256,
        "ledger_id": ledger_id,
        "ledger_sha256": ledger_sha256,
        "decision_count": decision_count,
        "last_observed_at": last_observed_at,
        "recommendation_anchors": [
            _anchor_payload(item) for item in recommendation_anchors
        ],
    }


def progression_fingerprint(**facts: Any) -> str:
    """Return the frozen correlation digest for one complete progression."""
    return _canonical_sha256(_progression_payload(**facts))


@dataclass(frozen=True, slots=True)
class ForwardEligibilityProgression:
    schema_version: str
    artifact_type: str
    lineage_key: ForwardEligibilityLineageKey
    run_id: str
    publication_id: str
    publication_index_sha256: str
    qualification_evaluation_id: str
    eligibility_id: str
    eligibility_state: ForwardEligibilityState
    eligibility_sha256: str
    metrics_id: str
    metrics_sha256: str
    ledger_id: str
    ledger_sha256: str
    decision_count: int
    last_observed_at: str | None
    recommendation_anchors: tuple[ForwardEligibilityDecisionAnchor, ...]
    progression_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != SOURCE_SCHEMA_VERSION:
            raise BrokerSafetySourceModelError("unsupported progression schema_version")
        if self.artifact_type != PROGRESSION_ARTIFACT_TYPE:
            raise BrokerSafetySourceModelError("unsupported progression artifact_type")
        if type(self.lineage_key) is not ForwardEligibilityLineageKey:
            raise BrokerSafetySourceModelError(
                "lineage_key must be an exact ForwardEligibilityLineageKey"
            )
        for name in (
            "run_id",
            "publication_id",
            "qualification_evaluation_id",
            "eligibility_id",
            "metrics_id",
            "ledger_id",
        ):
            _uuid(name, getattr(self, name))
        for name in (
            "publication_index_sha256",
            "eligibility_sha256",
            "metrics_sha256",
            "ledger_sha256",
            "progression_fingerprint",
        ):
            _sha(name, getattr(self, name))
        if type(self.eligibility_state) is not ForwardEligibilityState:
            raise BrokerSafetySourceModelError(
                "eligibility_state must be ForwardEligibilityState"
            )
        _count("decision_count", self.decision_count)
        _timestamp("last_observed_at", self.last_observed_at, optional=True)
        if type(self.recommendation_anchors) is not tuple or any(
            type(item) is not ForwardEligibilityDecisionAnchor
            for item in self.recommendation_anchors
        ):
            raise BrokerSafetySourceModelError(
                "recommendation_anchors must be an exact decision-anchor tuple"
            )
        if self.decision_count != len(self.recommendation_anchors):
            raise BrokerSafetySourceModelError(
                "decision_count must equal recommendation_anchors length"
            )
        keys = tuple(
            (item.observed_at, item.symbol) for item in self.recommendation_anchors
        )
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise BrokerSafetySourceModelError(
                "recommendation_anchors must use unique canonical decision order"
            )
        for name in (
            "recommendation_id",
            "recommendation_sha256",
            "decision_sha256",
        ):
            values = tuple(
                getattr(item, name) for item in self.recommendation_anchors
            )
            if len(set(values)) != len(values):
                raise BrokerSafetySourceModelError(f"{name} values must be unique")
        expected_last = (
            None
            if not self.recommendation_anchors
            else self.recommendation_anchors[-1].observed_at
        )
        if self.last_observed_at != expected_last:
            raise BrokerSafetySourceModelError(
                "last_observed_at must match the final decision anchor"
            )
        facts = {
            name: getattr(self, name)
            for name in (
                "lineage_key",
                "run_id",
                "publication_id",
                "publication_index_sha256",
                "qualification_evaluation_id",
                "eligibility_id",
                "eligibility_state",
                "eligibility_sha256",
                "metrics_id",
                "metrics_sha256",
                "ledger_id",
                "ledger_sha256",
                "decision_count",
                "last_observed_at",
                "recommendation_anchors",
            )
        }
        if self.progression_fingerprint != progression_fingerprint(**facts):
            raise BrokerSafetySourceModelError(
                "progression_fingerprint does not match canonical source facts"
            )


@dataclass(frozen=True, slots=True)
class BrokerSafetySourceHandoff:
    schema_version: str
    artifact_type: str
    workspace_run_id: str
    publication_id: str
    publication_index_sha256: str
    activation_id: str
    qualification_evaluation_id: str
    strategy_id: str
    eligibility_id: str
    eligibility_state: ForwardEligibilityState
    policy_id: str
    policy_version: str
    qualified_symbols: tuple[str, ...]
    qualified_symbols_sha256: str
    ledger_id: str
    ledger_sha256: str
    recommendation_id: str
    recommendation_sha256: str
    decision_symbol: str
    decision_observed_at: str
    decision_signal: str
    decision_action: str
    selected_parameters_sha256: str
    lineage_key: ForwardEligibilityLineageKey
    progression_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema_version != SOURCE_SCHEMA_VERSION:
            raise BrokerSafetySourceModelError("unsupported handoff schema_version")
        if self.artifact_type != HANDOFF_ARTIFACT_TYPE:
            raise BrokerSafetySourceModelError("unsupported handoff artifact_type")
        for name in (
            "workspace_run_id",
            "publication_id",
            "activation_id",
            "qualification_evaluation_id",
            "eligibility_id",
            "ledger_id",
            "recommendation_id",
        ):
            _uuid(name, getattr(self, name))
        for name in (
            "publication_index_sha256",
            "qualified_symbols_sha256",
            "ledger_sha256",
            "recommendation_sha256",
            "selected_parameters_sha256",
            "progression_fingerprint",
        ):
            _sha(name, getattr(self, name))
        for name in (
            "strategy_id",
            "policy_id",
            "policy_version",
            "decision_symbol",
        ):
            _clean(name, getattr(self, name))
        if self.eligibility_state is not ForwardEligibilityState.ACTIVE:
            raise BrokerSafetySourceModelError(
                "broker-safety source handoff requires exact ACTIVE state"
            )
        if type(self.qualified_symbols) is not tuple or not self.qualified_symbols:
            raise BrokerSafetySourceModelError(
                "qualified_symbols must be a non-empty exact tuple"
            )
        if (
            any(type(item) is not str or not item or item.strip() != item for item in self.qualified_symbols)
            or self.qualified_symbols != tuple(sorted(self.qualified_symbols))
            or len(set(self.qualified_symbols)) != len(self.qualified_symbols)
        ):
            raise BrokerSafetySourceModelError(
                "qualified_symbols must be unique, clean, and canonically ordered"
            )
        if self.decision_symbol not in self.qualified_symbols:
            raise BrokerSafetySourceModelError(
                "decision_symbol must belong to qualified_symbols"
            )
        expected_symbols_sha = _canonical_sha256({
            "schema_version": SOURCE_SCHEMA_VERSION,
            "artifact_type": "qualified_symbol_universe",
            "qualified_symbols": list(self.qualified_symbols),
        })
        if self.qualified_symbols_sha256 != expected_symbols_sha:
            raise BrokerSafetySourceModelError(
                "qualified_symbols_sha256 does not match qualified_symbols"
            )
        _timestamp("decision_observed_at", self.decision_observed_at)
        if self.decision_signal not in ("BUY", "HOLD", "SELL"):
            raise BrokerSafetySourceModelError(
                "decision_signal must be BUY, HOLD, or SELL"
            )
        if self.decision_action not in (
            "ENTER",
            "WATCH",
            "HOLD",
            "EXIT",
            "NO_TRADE",
        ):
            raise BrokerSafetySourceModelError("decision_action is not supported")
        if type(self.lineage_key) is not ForwardEligibilityLineageKey:
            raise BrokerSafetySourceModelError(
                "lineage_key must be an exact ForwardEligibilityLineageKey"
            )
        if (
            self.lineage_key.activation_id != self.activation_id
            or self.lineage_key.strategy_id != self.strategy_id
            or self.lineage_key.policy_id != self.policy_id
            or self.lineage_key.policy_version != self.policy_version
        ):
            raise BrokerSafetySourceModelError(
                "handoff identities must match lineage_key"
            )


@dataclass(frozen=True, slots=True)
class ForwardEligibilityHighWaterMark:
    schema_version: str
    artifact_type: str
    lineage_key: ForwardEligibilityLineageKey
    accepted_progression_fingerprint: str
    accepted_run_id: str
    accepted_publication_id: str
    accepted_publication_index_sha256: str
    accepted_qualification_evaluation_id: str
    accepted_eligibility_id: str
    accepted_state: ForwardEligibilityState
    accepted_eligibility_sha256: str
    accepted_metrics_id: str
    accepted_metrics_sha256: str
    accepted_ledger_id: str
    accepted_ledger_sha256: str
    accepted_decision_count: int
    accepted_last_observed_at: str | None
    accepted_recommendation_anchors: tuple[ForwardEligibilityDecisionAnchor, ...]

    def __post_init__(self) -> None:
        if self.schema_version != SOURCE_SCHEMA_VERSION:
            raise BrokerSafetySourceModelError(
                "unsupported high-water-mark schema_version"
            )
        if self.artifact_type != HIGH_WATER_MARK_ARTIFACT_TYPE:
            raise BrokerSafetySourceModelError(
                "unsupported high-water-mark artifact_type"
            )
        if type(self.lineage_key) is not ForwardEligibilityLineageKey:
            raise BrokerSafetySourceModelError(
                "lineage_key must be an exact ForwardEligibilityLineageKey"
            )
        accepted = self.to_progression()
        if accepted.progression_fingerprint != self.accepted_progression_fingerprint:
            raise BrokerSafetySourceModelError(
                "accepted high-water-mark facts do not match fingerprint"
            )

    @classmethod
    def from_progression(
        cls, progression: ForwardEligibilityProgression
    ) -> ForwardEligibilityHighWaterMark:
        if type(progression) is not ForwardEligibilityProgression:
            raise BrokerSafetySourceModelError(
                "progression must be an exact ForwardEligibilityProgression"
            )
        return cls(
            schema_version=SOURCE_SCHEMA_VERSION,
            artifact_type=HIGH_WATER_MARK_ARTIFACT_TYPE,
            lineage_key=progression.lineage_key,
            accepted_progression_fingerprint=progression.progression_fingerprint,
            accepted_run_id=progression.run_id,
            accepted_publication_id=progression.publication_id,
            accepted_publication_index_sha256=(
                progression.publication_index_sha256
            ),
            accepted_qualification_evaluation_id=(
                progression.qualification_evaluation_id
            ),
            accepted_eligibility_id=progression.eligibility_id,
            accepted_state=progression.eligibility_state,
            accepted_eligibility_sha256=progression.eligibility_sha256,
            accepted_metrics_id=progression.metrics_id,
            accepted_metrics_sha256=progression.metrics_sha256,
            accepted_ledger_id=progression.ledger_id,
            accepted_ledger_sha256=progression.ledger_sha256,
            accepted_decision_count=progression.decision_count,
            accepted_last_observed_at=progression.last_observed_at,
            accepted_recommendation_anchors=progression.recommendation_anchors,
        )

    def to_progression(self) -> ForwardEligibilityProgression:
        facts = {
            "lineage_key": self.lineage_key,
            "run_id": self.accepted_run_id,
            "publication_id": self.accepted_publication_id,
            "publication_index_sha256": self.accepted_publication_index_sha256,
            "qualification_evaluation_id": (
                self.accepted_qualification_evaluation_id
            ),
            "eligibility_id": self.accepted_eligibility_id,
            "eligibility_state": self.accepted_state,
            "eligibility_sha256": self.accepted_eligibility_sha256,
            "metrics_id": self.accepted_metrics_id,
            "metrics_sha256": self.accepted_metrics_sha256,
            "ledger_id": self.accepted_ledger_id,
            "ledger_sha256": self.accepted_ledger_sha256,
            "decision_count": self.accepted_decision_count,
            "last_observed_at": self.accepted_last_observed_at,
            "recommendation_anchors": self.accepted_recommendation_anchors,
        }
        return ForwardEligibilityProgression(
            schema_version=SOURCE_SCHEMA_VERSION,
            artifact_type=PROGRESSION_ARTIFACT_TYPE,
            progression_fingerprint=self.accepted_progression_fingerprint,
            **facts,
        )


class ForwardEligibilityProgressionRelation(StrEnum):
    SAME = "SAME"
    STRICT_EXTENSION = "STRICT_EXTENSION"
    ROLLBACK = "ROLLBACK"
    INCOMPARABLE = "INCOMPARABLE"
    CONFLICT = "CONFLICT"
    DIFFERENT_LINEAGE = "DIFFERENT_LINEAGE"


__all__ = [
    "HANDOFF_ARTIFACT_TYPE",
    "HIGH_WATER_MARK_ARTIFACT_TYPE",
    "PROGRESSION_ARTIFACT_TYPE",
    "SOURCE_SCHEMA_VERSION",
    "BrokerSafetySourceHandoff",
    "BrokerSafetySourceModelError",
    "ForwardEligibilityDecisionAnchor",
    "ForwardEligibilityHighWaterMark",
    "ForwardEligibilityLineageKey",
    "ForwardEligibilityProgression",
    "ForwardEligibilityProgressionRelation",
    "progression_fingerprint",
]
