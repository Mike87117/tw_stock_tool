"""Immutable research-only recommendation evidence models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import math
from types import MappingProxyType
from typing import Any, Literal, TypeAlias
from uuid import UUID

from tw_stock_tool.qualification import StrategyQualificationResult

RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE = "recommendation_evidence"
RECOMMENDATION_EVIDENCE_SCHEMA_VERSION = "1.0"

RecommendationAction: TypeAlias = Literal[
    "ENTER", "WATCH", "HOLD", "EXIT", "NO_TRADE"
]
CurrentSignal: TypeAlias = Literal["BUY", "WATCH", "HOLD", "SELL"]
JsonScalar: TypeAlias = str | int | float | bool | None
FrozenJsonValue: TypeAlias = (
    JsonScalar | tuple["FrozenJsonValue", ...] | Mapping[str, "FrozenJsonValue"]
)


class RecommendationModelError(ValueError):
    """Raised when recommendation evidence violates its domain contract."""


def _clean_string(name: str, value: Any) -> str:
    if type(value) is not str:
        raise RecommendationModelError(
            f"{name} must be exact str, got {type(value).__name__}"
        )
    if not value or value.strip() != value:
        raise RecommendationModelError(f"{name} must be a clean non-blank string")
    return value


def _finite_float(name: str, value: Any) -> float:
    if type(value) not in (int, float):
        raise RecommendationModelError(
            f"{name} must be an exact finite number, got {type(value).__name__}"
        )
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise RecommendationModelError(
            f"{name} must be a finite number; conversion failed"
        ) from exc
    if not math.isfinite(result):
        raise RecommendationModelError(f"{name} must be finite, got {value!r}")
    return result


def _optional_finite_float(name: str, value: Any) -> float | None:
    if value is None:
        return None
    return _finite_float(name, value)


def _validate_uuid_v4(name: str, value: Any) -> str:
    clean = _clean_string(name, value)
    try:
        parsed = UUID(clean)
    except ValueError as exc:
        raise RecommendationModelError(f"{name} must be a canonical UUID v4") from exc
    if parsed.version != 4 or str(parsed) != clean:
        raise RecommendationModelError(
            f"{name} must be a canonical lowercase UUID v4"
        )
    return clean


def _validate_utc_timestamp(name: str, value: Any) -> str:
    clean = _clean_string(name, value)
    try:
        parsed = datetime.strptime(clean, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise RecommendationModelError(
            f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != clean:
        raise RecommendationModelError(
            f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
        )
    return clean


def _freeze_json(name: str, value: Any) -> FrozenJsonValue:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise RecommendationModelError(f"{name} contains a non-finite float")
        return value
    if type(value) in (list, tuple):
        return tuple(
            _freeze_json(f"{name}[{index}]", item)
            for index, item in enumerate(value)
        )
    if isinstance(value, Mapping):
        clean_items: dict[str, Any] = {}
        for key, item in value.items():
            clean_key = _clean_string(f"{name} key", key)
            clean_items[clean_key] = item
        frozen: dict[str, FrozenJsonValue] = {}
        for clean_key in sorted(clean_items):
            frozen[clean_key] = _freeze_json(
                f"{name}.{clean_key}",
                clean_items[clean_key],
            )
        return MappingProxyType(frozen)
    raise RecommendationModelError(
        f"{name} contains unsupported type {type(value).__name__}"
    )


def _freeze_mapping(name: str, value: Any) -> Mapping[str, FrozenJsonValue]:
    if not isinstance(value, Mapping):
        raise RecommendationModelError(
            f"{name} must be a Mapping, got {type(value).__name__}"
        )
    frozen = _freeze_json(name, value)
    assert isinstance(frozen, Mapping)
    return frozen


def _same_frozen_json(left: Any, right: Any) -> bool:
    """Compare frozen JSON trees without Python numeric type coercion."""
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        if set(left) != set(right):
            return False
        return all(_same_frozen_json(left[key], right[key]) for key in left)
    if type(left) is tuple:
        if len(left) != len(right):
            return False
        return all(
            _same_frozen_json(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return left == right


@dataclass(frozen=True, slots=True)
class CurrentSignalSnapshot:
    symbol: str
    observed_at: str
    signal: CurrentSignal
    score: float
    latest_close: float | None = None

    def __post_init__(self) -> None:
        _clean_string("symbol", self.symbol)
        _validate_utc_timestamp("observed_at", self.observed_at)
        signal = _clean_string("signal", self.signal)
        if signal not in ("BUY", "WATCH", "HOLD", "SELL"):
            raise RecommendationModelError(
                "signal must be BUY, WATCH, HOLD, or SELL"
            )
        object.__setattr__(self, "score", _finite_float("score", self.score))
        object.__setattr__(
            self,
            "latest_close",
            _optional_finite_float("latest_close", self.latest_close),
        )


@dataclass(frozen=True, slots=True)
class RecommendationEvidence:
    schema_version: str
    artifact_type: str
    recommendation_id: str
    generated_at: str
    source_qualification_evaluation_id: str
    promotion_state: str
    strategy_id: str
    strategy_parameters: Mapping[str, FrozenJsonValue]
    qualification_finding_codes: tuple[str, ...]
    signal_snapshot: CurrentSignalSnapshot
    action: RecommendationAction
    qualification: StrategyQualificationResult

    def __post_init__(self) -> None:
        if self.schema_version != RECOMMENDATION_EVIDENCE_SCHEMA_VERSION:
            raise RecommendationModelError(
                "schema_version must equal "
                f"{RECOMMENDATION_EVIDENCE_SCHEMA_VERSION!r}"
            )
        if self.artifact_type != RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE:
            raise RecommendationModelError(
                f"artifact_type must equal {RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE!r}"
            )
        _validate_uuid_v4("recommendation_id", self.recommendation_id)
        _validate_utc_timestamp("generated_at", self.generated_at)
        _validate_uuid_v4(
            "source_qualification_evaluation_id",
            self.source_qualification_evaluation_id,
        )
        if not isinstance(self.qualification, StrategyQualificationResult):
            raise RecommendationModelError(
                "qualification must be a StrategyQualificationResult"
            )
        if not isinstance(self.signal_snapshot, CurrentSignalSnapshot):
            raise RecommendationModelError(
                "signal_snapshot must be a CurrentSignalSnapshot"
            )

        qualification_request = self.qualification.request
        canonical_evaluation_id = qualification_request.evaluation_id
        if self.source_qualification_evaluation_id != canonical_evaluation_id:
            raise RecommendationModelError(
                "source qualification evaluation_id does not match qualification"
            )

        canonical_promotion = self.qualification.decision.state
        promotion = _clean_string("promotion_state", self.promotion_state)
        if promotion != canonical_promotion:
            raise RecommendationModelError(
                "promotion_state must equal qualification decision state"
            )

        canonical_strategy_id = qualification_request.strategy.strategy_id
        strategy_id = _clean_string("strategy_id", self.strategy_id)
        if strategy_id != canonical_strategy_id:
            raise RecommendationModelError(
                "strategy_id must equal qualification strategy_id"
            )

        frozen_parameters = _freeze_mapping(
            "strategy_parameters", self.strategy_parameters
        )
        canonical_parameters = _freeze_mapping(
            "qualification strategy parameters",
            qualification_request.strategy.parameters,
        )
        if not _same_frozen_json(frozen_parameters, canonical_parameters):
            raise RecommendationModelError(
                "strategy_parameters must exactly equal qualification strategy parameters"
            )
        object.__setattr__(self, "strategy_parameters", frozen_parameters)

        if type(self.qualification_finding_codes) is not tuple:
            raise RecommendationModelError(
                "qualification_finding_codes must be an exact tuple"
            )
        canonical_codes = self.qualification.decision.reason_codes
        for index, code in enumerate(self.qualification_finding_codes):
            _clean_string(f"qualification_finding_codes[{index}]", code)
        if self.qualification_finding_codes != canonical_codes:
            raise RecommendationModelError(
                "qualification_finding_codes must equal qualification reason codes"
            )

        action = _clean_string("action", self.action)
        if action not in ("ENTER", "WATCH", "HOLD", "EXIT", "NO_TRADE"):
            raise RecommendationModelError(
                "action must be ENTER, WATCH, HOLD, EXIT, or NO_TRADE"
            )
        from tw_stock_tool.recommendation.derivation import (
            derive_recommendation_action,
        )

        canonical_action = derive_recommendation_action(
            self.qualification,
            self.signal_snapshot,
        )
        if action != canonical_action:
            raise RecommendationModelError(
                f"action must equal canonical derived action {canonical_action!r}"
            )


__all__ = [
    "RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE",
    "RECOMMENDATION_EVIDENCE_SCHEMA_VERSION",
    "CurrentSignal",
    "CurrentSignalSnapshot",
    "RecommendationAction",
    "RecommendationEvidence",
    "RecommendationModelError",
]
