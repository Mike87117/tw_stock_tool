"""Immutable domain model for forward-paper activation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any
from uuid import UUID


FORWARD_PAPER_ACTIVATION_SCHEMA_VERSION = "1.0"
FORWARD_PAPER_ACTIVATION_ARTIFACT_TYPE = "forward_paper_activation"
QUALIFICATION_ARTIFACT_TYPE = "universe_oos_evidence"
QUALIFICATION_SCHEMA_VERSION = "1.0"

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class ForwardPaperModelError(ValueError):
    """Raised when forward-paper activation data violates schema 1.0."""


def _clean_string(name: str, value: Any) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ForwardPaperModelError(f"{name} must be an exact clean non-empty string")
    return value


def _canonical_uuid_v4(name: str, value: Any) -> str:
    clean = _clean_string(name, value)
    try:
        parsed = UUID(clean)
    except ValueError as exc:
        raise ForwardPaperModelError(f"{name} must be a canonical lowercase UUID v4") from exc
    if parsed.version != 4 or str(parsed) != clean:
        raise ForwardPaperModelError(f"{name} must be a canonical lowercase UUID v4")
    return clean


def _canonical_timestamp(name: str, value: Any) -> str:
    clean = _clean_string(name, value)
    try:
        parsed = datetime.strptime(clean, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ForwardPaperModelError(
            f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != clean:
        raise ForwardPaperModelError(
            f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
        )
    return clean


@dataclass(frozen=True, slots=True)
class ForwardPaperActivation:
    schema_version: str
    artifact_type: str
    activation_id: str
    created_at: str
    qualification_evaluation_id: str
    qualification_artifact_type: str
    qualification_schema_version: str
    qualification_sha256: str
    strategy_id: str
    policy_id: str
    policy_version: str
    qualification_cutoff: str
    qualified_symbols: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != FORWARD_PAPER_ACTIVATION_SCHEMA_VERSION:
            raise ForwardPaperModelError(
                f"schema_version must equal {FORWARD_PAPER_ACTIVATION_SCHEMA_VERSION!r}"
            )
        if self.artifact_type != FORWARD_PAPER_ACTIVATION_ARTIFACT_TYPE:
            raise ForwardPaperModelError(
                f"artifact_type must equal {FORWARD_PAPER_ACTIVATION_ARTIFACT_TYPE!r}"
            )
        _canonical_uuid_v4("activation_id", self.activation_id)
        _canonical_timestamp("created_at", self.created_at)
        _canonical_uuid_v4(
            "qualification_evaluation_id", self.qualification_evaluation_id
        )
        if self.qualification_artifact_type != QUALIFICATION_ARTIFACT_TYPE:
            raise ForwardPaperModelError(
                f"qualification_artifact_type must equal {QUALIFICATION_ARTIFACT_TYPE!r}"
            )
        if self.qualification_schema_version != QUALIFICATION_SCHEMA_VERSION:
            raise ForwardPaperModelError(
                f"qualification_schema_version must equal {QUALIFICATION_SCHEMA_VERSION!r}"
            )
        if type(self.qualification_sha256) is not str or _SHA256_PATTERN.fullmatch(
            self.qualification_sha256
        ) is None:
            raise ForwardPaperModelError(
                "qualification_sha256 must be a lowercase 64-character SHA-256 hex digest"
            )
        _clean_string("strategy_id", self.strategy_id)
        _clean_string("policy_id", self.policy_id)
        _clean_string("policy_version", self.policy_version)
        _canonical_timestamp("qualification_cutoff", self.qualification_cutoff)
        if self.created_at < self.qualification_cutoff:
            raise ForwardPaperModelError(
                "created_at must not predate qualification_cutoff"
            )
        if type(self.qualified_symbols) is not tuple or not self.qualified_symbols:
            raise ForwardPaperModelError(
                "qualified_symbols must be a non-empty exact tuple"
            )
        for index, symbol in enumerate(self.qualified_symbols):
            _clean_string(f"qualified_symbols[{index}]", symbol)
        if self.qualified_symbols != tuple(sorted(self.qualified_symbols)):
            raise ForwardPaperModelError("qualified_symbols must be sorted")
        if len(set(self.qualified_symbols)) != len(self.qualified_symbols):
            raise ForwardPaperModelError("qualified_symbols must be unique")


__all__ = [
    "FORWARD_PAPER_ACTIVATION_ARTIFACT_TYPE",
    "FORWARD_PAPER_ACTIVATION_SCHEMA_VERSION",
    "QUALIFICATION_ARTIFACT_TYPE",
    "QUALIFICATION_SCHEMA_VERSION",
    "ForwardPaperActivation",
    "ForwardPaperModelError",
]
