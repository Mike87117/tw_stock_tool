"""Immutable pure-domain models for the forward decision ledger."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from tw_stock_tool.forward_paper.models import (
    ForwardPaperModelError,
    _SHA256_PATTERN,
    _canonical_timestamp,
    _canonical_uuid_v4,
    _clean_string,
)


FORWARD_DECISION_LEDGER_SCHEMA_VERSION = "1.0"
FORWARD_DECISION_LEDGER_ARTIFACT_TYPE = "forward_paper_decision_ledger"


def _sha256(name: str, value: Any) -> str:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise ForwardPaperModelError(
            f"{name} must be a lowercase 64-character SHA-256 hex digest"
        )
    return value


def _selected_parameters(value: Any) -> Mapping[str, int]:
    if not isinstance(value, Mapping) or isinstance(
        value, (str, bytes, bytearray, list, tuple)
    ):
        raise ForwardPaperModelError("selected_parameters must be a Mapping")
    clean: dict[str, int] = {}
    for key in sorted(value):
        clean_key = _clean_string("selected_parameters key", key)
        item = value[key]
        if type(item) is not int:
            raise ForwardPaperModelError(
                f"selected_parameters.{clean_key} must be an exact int"
            )
        clean[clean_key] = item
    if not clean:
        raise ForwardPaperModelError("selected_parameters must not be empty")
    return MappingProxyType(clean)


@dataclass(frozen=True, slots=True)
class ForwardDecisionRecord:
    recommendation_id: str
    recommendation_sha256: str
    observed_at: str
    generated_at: str
    symbol: str
    signal: str
    action: str
    qualification_evaluation_id: str
    strategy_id: str
    selected_parameters: Mapping[str, int]

    def __post_init__(self) -> None:
        _canonical_uuid_v4("recommendation_id", self.recommendation_id)
        _sha256("recommendation_sha256", self.recommendation_sha256)
        _canonical_timestamp("observed_at", self.observed_at)
        _canonical_timestamp("generated_at", self.generated_at)
        _clean_string("symbol", self.symbol)
        if self.signal not in ("BUY", "HOLD", "SELL"):
            raise ForwardPaperModelError("signal must be BUY, HOLD, or SELL")
        if self.action not in ("ENTER", "WATCH", "HOLD", "EXIT", "NO_TRADE"):
            raise ForwardPaperModelError(
                "action must be ENTER, WATCH, HOLD, EXIT, or NO_TRADE"
            )
        _canonical_uuid_v4(
            "qualification_evaluation_id", self.qualification_evaluation_id
        )
        _clean_string("strategy_id", self.strategy_id)
        object.__setattr__(
            self, "selected_parameters", _selected_parameters(self.selected_parameters)
        )


@dataclass(frozen=True, slots=True)
class ForwardDecisionLedger:
    schema_version: str
    artifact_type: str
    ledger_id: str
    created_at: str
    activation_id: str
    activation_sha256: str
    qualification_evaluation_id: str
    qualification_sha256: str
    strategy_id: str
    decisions: tuple[ForwardDecisionRecord, ...]

    def __post_init__(self) -> None:
        if self.schema_version != FORWARD_DECISION_LEDGER_SCHEMA_VERSION:
            raise ForwardPaperModelError(
                f"schema_version must equal {FORWARD_DECISION_LEDGER_SCHEMA_VERSION!r}"
            )
        if self.artifact_type != FORWARD_DECISION_LEDGER_ARTIFACT_TYPE:
            raise ForwardPaperModelError(
                f"artifact_type must equal {FORWARD_DECISION_LEDGER_ARTIFACT_TYPE!r}"
            )
        _canonical_uuid_v4("ledger_id", self.ledger_id)
        _canonical_timestamp("created_at", self.created_at)
        _canonical_uuid_v4("activation_id", self.activation_id)
        _sha256("activation_sha256", self.activation_sha256)
        _canonical_uuid_v4(
            "qualification_evaluation_id", self.qualification_evaluation_id
        )
        _sha256("qualification_sha256", self.qualification_sha256)
        _clean_string("strategy_id", self.strategy_id)
        if type(self.decisions) is not tuple:
            raise ForwardPaperModelError("decisions must be an exact tuple")
        if any(type(item) is not ForwardDecisionRecord for item in self.decisions):
            raise ForwardPaperModelError(
                "decisions must contain exact ForwardDecisionRecord instances"
            )
        if any(
            item.qualification_evaluation_id != self.qualification_evaluation_id
            or item.strategy_id != self.strategy_id
            for item in self.decisions
        ):
            raise ForwardPaperModelError(
                "decision qualification and strategy identities must match ledger"
            )
        keys = tuple((item.observed_at, item.symbol) for item in self.decisions)
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise ForwardPaperModelError(
                "decisions must have unique canonical (observed_at, symbol) order"
            )
        recommendation_ids = tuple(item.recommendation_id for item in self.decisions)
        if len(set(recommendation_ids)) != len(recommendation_ids):
            raise ForwardPaperModelError("recommendation IDs must be unique")
        recommendation_hashes = tuple(
            item.recommendation_sha256 for item in self.decisions
        )
        if len(set(recommendation_hashes)) != len(recommendation_hashes):
            raise ForwardPaperModelError("recommendation SHA-256 identities must be unique")


__all__ = [
    "FORWARD_DECISION_LEDGER_ARTIFACT_TYPE",
    "FORWARD_DECISION_LEDGER_SCHEMA_VERSION",
    "ForwardDecisionLedger",
    "ForwardDecisionRecord",
]
