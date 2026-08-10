"""Immutable health and summary models for offline forward-paper inspection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
from pathlib import Path
from typing import Any

from tw_stock_tool.artifacts.workspace import validate_artifact_path, validate_run_id
from tw_stock_tool.forward_paper.eligibility_models import ForwardEligibilityState
from tw_stock_tool.forward_paper.publication import ForwardPaperPublicationIndex
from tw_stock_tool.research_run.models import RunManifest


class ForwardPaperPackageHealth(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"


class ForwardPaperPackageFindingCode(StrEnum):
    WORKSPACE_RUN_INVALID = "workspace_run_invalid"
    MANIFEST_CONTRACT_MISMATCH = "manifest_contract_mismatch"
    PUBLICATION_INDEX_INVALID = "publication_index_invalid"
    ARTIFACT_REFERENCE_MISMATCH = "artifact_reference_mismatch"
    ARTIFACT_READ_FAILURE = "artifact_read_failure"
    ARTIFACT_NONCANONICAL = "artifact_noncanonical"
    ARTIFACT_SHA256_MISMATCH = "artifact_sha256_mismatch"
    RECOMMENDATION_CONTRACT_MISMATCH = "recommendation_contract_mismatch"
    INDEX_IDENTITY_MISMATCH = "index_identity_mismatch"
    TRUST_CHAIN_INVALID = "trust_chain_invalid"


FINDING_CODE_ORDER = tuple(ForwardPaperPackageFindingCode)


def _clean(name: str, value: Any) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{name} must be an exact clean non-empty string")
    return value


def _count(name: str, value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be an exact non-negative int")
    return value


def _finite(name: str, value: Any, *, optional: bool = False) -> float | None:
    if optional and value is None:
        return None
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be an exact finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


@dataclass(frozen=True, slots=True)
class ForwardPaperPackageFinding:
    code: ForwardPaperPackageFindingCode
    path: str | None
    role: str | None
    message: str

    def __post_init__(self) -> None:
        if type(self.code) is not ForwardPaperPackageFindingCode:
            raise ValueError("code must be ForwardPaperPackageFindingCode")
        if self.path is not None:
            _clean("path", self.path)
            validate_artifact_path(self.path)
        if self.role is not None:
            _clean("role", self.role)
        _clean("message", self.message)


@dataclass(frozen=True, slots=True)
class ForwardPaperPackageSummary:
    publication_id: str
    activation_id: str
    qualification_evaluation_id: str
    strategy_id: str
    policy_id: str
    policy_version: str
    eligibility_state: ForwardEligibilityState
    eligibility_finding_codes: tuple[str, ...]
    qualification_cutoff: str
    qualified_symbols: tuple[str, ...]
    decision_count: int
    recommendation_count: int
    portfolio_observation_count: int
    filled_count: int
    skipped_invalid_open_count: int
    failed_portfolio_validation_count: int
    applied_total_cost: float
    total_return_pct: float | None
    max_drawdown_pct: float

    def __post_init__(self) -> None:
        for name in (
            "publication_id",
            "activation_id",
            "qualification_evaluation_id",
            "strategy_id",
            "policy_id",
            "policy_version",
            "qualification_cutoff",
        ):
            _clean(name, getattr(self, name))
        if type(self.eligibility_state) is not ForwardEligibilityState:
            raise ValueError("eligibility_state must be ForwardEligibilityState")
        for name in ("eligibility_finding_codes", "qualified_symbols"):
            values = getattr(self, name)
            if type(values) is not tuple or any(type(item) is not str or not item for item in values):
                raise ValueError(f"{name} must be an exact clean string tuple")
        for name in (
            "decision_count",
            "recommendation_count",
            "portfolio_observation_count",
            "filled_count",
            "skipped_invalid_open_count",
            "failed_portfolio_validation_count",
        ):
            _count(name, getattr(self, name))
        object.__setattr__(self, "applied_total_cost", _finite("applied_total_cost", self.applied_total_cost))
        object.__setattr__(self, "total_return_pct", _finite("total_return_pct", self.total_return_pct, optional=True))
        object.__setattr__(self, "max_drawdown_pct", _finite("max_drawdown_pct", self.max_drawdown_pct))


@dataclass(frozen=True, slots=True)
class ForwardPaperPackageInspection:
    health: ForwardPaperPackageHealth
    run_id: str
    run_directory: Path
    manifest: RunManifest
    publication_index: ForwardPaperPublicationIndex | None
    findings: tuple[ForwardPaperPackageFinding, ...]
    summary: ForwardPaperPackageSummary | None

    def __post_init__(self) -> None:
        if type(self.health) is not ForwardPaperPackageHealth:
            raise ValueError("health must be ForwardPaperPackageHealth")
        validate_run_id(self.run_id)
        if not isinstance(self.run_directory, Path):
            raise ValueError("run_directory must be Path")
        if type(self.manifest) is not RunManifest:
            raise ValueError("manifest must be RunManifest")
        if self.manifest.run_id != self.run_id:
            raise ValueError("manifest run_id must match inspection run_id")
        if self.publication_index is not None and type(self.publication_index) is not ForwardPaperPublicationIndex:
            raise ValueError("publication_index must be ForwardPaperPublicationIndex or None")
        if type(self.findings) is not tuple or any(
            type(item) is not ForwardPaperPackageFinding for item in self.findings
        ):
            raise ValueError("findings must be an exact ForwardPaperPackageFinding tuple")
        finding_keys = tuple(
            (item.code, item.path, item.role, item.message)
            for item in self.findings
        )
        expected_keys = tuple(sorted(
            set(finding_keys),
            key=lambda item: (
                FINDING_CODE_ORDER.index(item[0]),
                item[1] or "",
                item[2] or "",
                item[3],
            ),
        ))
        if finding_keys != expected_keys:
            raise ValueError("findings must be unique and canonically ordered")
        if self.health is ForwardPaperPackageHealth.VALID:
            if self.findings or self.publication_index is None or type(self.summary) is not ForwardPaperPackageSummary:
                raise ValueError("VALID inspection requires trusted index, summary, and no findings")
        elif not self.findings or self.summary is not None:
            raise ValueError("INVALID inspection requires findings and no summary")


__all__ = [
    "FINDING_CODE_ORDER",
    "ForwardPaperPackageFinding",
    "ForwardPaperPackageFindingCode",
    "ForwardPaperPackageHealth",
    "ForwardPaperPackageInspection",
    "ForwardPaperPackageSummary",
]

