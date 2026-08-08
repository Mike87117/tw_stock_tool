"""Pure strategy-bound Recommendation Evidence schema 1.1.

Schema 1.0 remains owned by recommendation.models/serialization and keeps the
legacy independent-research-signal contract. This module adds a separate,
backward-compatible strategy-bound artifact for the forward-paper path.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import json
import math
from types import MappingProxyType
from typing import Any, Literal, NoReturn, TypeAlias
from uuid import UUID

from tw_stock_tool.qualification import (
    QualificationSerializationError,
    StrategyQualificationResult,
)
from tw_stock_tool.qualification.serialization import (
    deserialize_strategy_qualification_result,
    serialize_strategy_qualification_result,
)
from tw_stock_tool.recommendation.derivation import derive_recommendation_action
from tw_stock_tool.recommendation.models import (
    RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE,
    CurrentSignalSnapshot,
    RecommendationAction,
    RecommendationEvidence,
    RecommendationModelError,
)

STRATEGY_BOUND_RECOMMENDATION_EVIDENCE_SCHEMA_VERSION = "1.1"
STRATEGY_SIGNAL_SELECTION_RULE = "train_only_parameter_search_v1"

StrategyBoundSignal: TypeAlias = Literal["BUY", "HOLD", "SELL"]


class StrategyBoundRecommendationError(ValueError):
    """Raised when strategy-bound recommendation provenance is invalid."""


class StrategyBoundSerializationError(ValueError):
    """Raised when schema-1.1 strategy-bound evidence cannot be serialized."""


def _clean_string(name: str, value: Any) -> str:
    if type(value) is not str:
        raise StrategyBoundRecommendationError(
            f"{name} must be exact str, got {type(value).__name__}"
        )
    if not value or value.strip() != value:
        raise StrategyBoundRecommendationError(
            f"{name} must be a clean non-blank string"
        )
    return value


def _canonical_uuid_v4(name: str, value: Any) -> str:
    clean = _clean_string(name, value)
    try:
        parsed = UUID(clean)
    except ValueError as exc:
        raise StrategyBoundRecommendationError(
            f"{name} must be a canonical UUID v4"
        ) from exc
    if parsed.version != 4 or str(parsed) != clean:
        raise StrategyBoundRecommendationError(
            f"{name} must be a canonical lowercase UUID v4"
        )
    return clean


def _canonical_timestamp(name: str, value: Any) -> str:
    clean = _clean_string(name, value)
    try:
        parsed = datetime.strptime(clean, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise StrategyBoundRecommendationError(
            f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != clean:
        raise StrategyBoundRecommendationError(
            f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
        )
    return clean


def _finite_float(name: str, value: Any) -> float:
    if type(value) not in (int, float):
        raise StrategyBoundRecommendationError(
            f"{name} must be an exact finite number"
        )
    result = float(value)
    if not math.isfinite(result):
        raise StrategyBoundRecommendationError(f"{name} must be finite")
    return result


def _positive_int(name: str, value: Any) -> int:
    if type(value) is not int or value <= 0:
        raise StrategyBoundRecommendationError(
            f"{name} must be a positive exact int"
        )
    return value


def _freeze_selected_parameters(value: Any) -> Mapping[str, int]:
    if not isinstance(value, Mapping) or isinstance(
        value, (str, bytes, bytearray, list, tuple)
    ):
        raise StrategyBoundRecommendationError(
            "selected_parameters must be a Mapping"
        )
    frozen: dict[str, int] = {}
    for key in sorted(value):
        clean_key = _clean_string("selected_parameters key", key)
        item = value[key]
        if type(item) is not int:
            raise StrategyBoundRecommendationError(
                f"selected_parameters.{clean_key} must be exact int"
            )
        frozen[clean_key] = item
    if not frozen:
        raise StrategyBoundRecommendationError(
            "selected_parameters must not be empty"
        )
    return MappingProxyType(frozen)


def _exact_parameter_mapping(value: Any) -> tuple[tuple[str, int], ...] | None:
    if not isinstance(value, Mapping):
        return None
    pairs: list[tuple[str, int]] = []
    for key in sorted(value):
        if type(key) is not str or type(value[key]) is not int:
            return None
        pairs.append((key, value[key]))
    return tuple(pairs)


def _qualification_selection_contract(
    qualification: StrategyQualificationResult,
) -> tuple[str, str, int, tuple[tuple[tuple[str, int], ...], ...]]:
    if not isinstance(qualification, StrategyQualificationResult):
        raise StrategyBoundRecommendationError(
            "qualification must be a StrategyQualificationResult"
        )
    parameters = qualification.request.strategy.parameters
    selection = parameters.get("selection")
    train_days = parameters.get("train_days")
    resolved = parameters.get("resolved_configuration")
    if (
        type(selection) is not str
        or not selection
        or type(train_days) is not int
        or train_days <= 0
        or not isinstance(resolved, Mapping)
    ):
        raise StrategyBoundRecommendationError(
            "qualification lacks canonical train-only selection provenance"
        )
    resolved_strategy = resolved.get("strategy")
    resolved_sort_by = resolved.get("sort_by")
    resolved_train_days = resolved.get("train_days")
    grid = resolved.get("parameter_grid")
    if (
        type(resolved_strategy) is not str
        or resolved_strategy != qualification.request.strategy.strategy_id
        or type(resolved_sort_by) is not str
        or resolved_sort_by != selection
        or type(resolved_train_days) is not int
        or resolved_train_days != train_days
        or type(grid) is not tuple
        or not grid
    ):
        raise StrategyBoundRecommendationError(
            "qualification resolved selection contract is inconsistent"
        )
    canonical_grid: list[tuple[tuple[str, int], ...]] = []
    for item in grid:
        canonical = _exact_parameter_mapping(item)
        if canonical is None or not canonical:
            raise StrategyBoundRecommendationError(
                "qualification parameter grid has invalid exact types"
            )
        canonical_grid.append(canonical)
    return (
        qualification.request.strategy.strategy_id,
        selection,
        train_days,
        tuple(canonical_grid),
    )


@dataclass(frozen=True, slots=True)
class StrategySignalProvenance:
    qualification_evaluation_id: str
    strategy_id: str
    selected_parameters: Mapping[str, int]
    selection_rule: str
    selection_metric: str
    selection_train_start: str
    selection_train_end: str
    selection_train_rows: int

    def __post_init__(self) -> None:
        _canonical_uuid_v4(
            "qualification_evaluation_id", self.qualification_evaluation_id
        )
        _clean_string("strategy_id", self.strategy_id)
        object.__setattr__(
            self,
            "selected_parameters",
            _freeze_selected_parameters(self.selected_parameters),
        )
        if self.selection_rule != STRATEGY_SIGNAL_SELECTION_RULE:
            raise StrategyBoundRecommendationError(
                f"selection_rule must equal {STRATEGY_SIGNAL_SELECTION_RULE!r}"
            )
        _clean_string("selection_metric", self.selection_metric)
        start = _canonical_timestamp(
            "selection_train_start", self.selection_train_start
        )
        end = _canonical_timestamp(
            "selection_train_end", self.selection_train_end
        )
        if datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ") > datetime.strptime(
            end, "%Y-%m-%dT%H:%M:%SZ"
        ):
            raise StrategyBoundRecommendationError(
                "selection train range must be ordered"
            )
        _positive_int("selection_train_rows", self.selection_train_rows)


@dataclass(frozen=True, slots=True)
class StrategyBoundSignalSnapshot:
    symbol: str
    observed_at: str
    signal: StrategyBoundSignal
    latest_close: float | None
    provenance: StrategySignalProvenance

    def __post_init__(self) -> None:
        _clean_string("symbol", self.symbol)
        observed = _canonical_timestamp("observed_at", self.observed_at)
        signal = _clean_string("signal", self.signal)
        if signal not in ("BUY", "HOLD", "SELL"):
            raise StrategyBoundRecommendationError(
                "signal must be BUY, HOLD, or SELL"
            )
        if self.latest_close is not None:
            object.__setattr__(
                self,
                "latest_close",
                _finite_float("latest_close", self.latest_close),
            )
        if not isinstance(self.provenance, StrategySignalProvenance):
            raise StrategyBoundRecommendationError(
                "provenance must be StrategySignalProvenance"
            )
        train_end = datetime.strptime(
            self.provenance.selection_train_end, "%Y-%m-%dT%H:%M:%SZ"
        )
        if train_end >= datetime.strptime(observed, "%Y-%m-%dT%H:%M:%SZ"):
            raise StrategyBoundRecommendationError(
                "selection_train_end must strictly predate observed_at"
            )


@dataclass(frozen=True, slots=True)
class StrategyBoundRecommendationEvidence:
    schema_version: str
    artifact_type: str
    recommendation_id: str
    generated_at: str
    source_qualification_evaluation_id: str
    promotion_state: str
    strategy_id: str
    strategy_parameters: Mapping[str, Any]
    qualification_finding_codes: tuple[str, ...]
    signal_snapshot: StrategyBoundSignalSnapshot
    action: RecommendationAction
    qualification: StrategyQualificationResult

    def __post_init__(self) -> None:
        if (
            self.schema_version
            != STRATEGY_BOUND_RECOMMENDATION_EVIDENCE_SCHEMA_VERSION
        ):
            raise StrategyBoundRecommendationError(
                "schema_version must equal "
                f"{STRATEGY_BOUND_RECOMMENDATION_EVIDENCE_SCHEMA_VERSION!r}"
            )
        if self.artifact_type != RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE:
            raise StrategyBoundRecommendationError(
                f"artifact_type must equal {RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE!r}"
            )
        if not isinstance(self.signal_snapshot, StrategyBoundSignalSnapshot):
            raise StrategyBoundRecommendationError(
                "signal_snapshot must be StrategyBoundSignalSnapshot"
            )
        if not isinstance(self.qualification, StrategyQualificationResult):
            raise StrategyBoundRecommendationError(
                "qualification must be a StrategyQualificationResult"
            )

        legacy_snapshot = CurrentSignalSnapshot(
            symbol=self.signal_snapshot.symbol,
            observed_at=self.signal_snapshot.observed_at,
            signal=self.signal_snapshot.signal,
            score=0.0,
            latest_close=self.signal_snapshot.latest_close,
        )
        try:
            RecommendationEvidence(
                schema_version="1.0",
                artifact_type=self.artifact_type,
                recommendation_id=self.recommendation_id,
                generated_at=self.generated_at,
                source_qualification_evaluation_id=(
                    self.source_qualification_evaluation_id
                ),
                promotion_state=self.promotion_state,
                strategy_id=self.strategy_id,
                strategy_parameters=self.strategy_parameters,
                qualification_finding_codes=self.qualification_finding_codes,
                signal_snapshot=legacy_snapshot,
                action=self.action,
                qualification=self.qualification,
            )
        except RecommendationModelError as exc:
            raise StrategyBoundRecommendationError(
                f"schema-1.0 recommendation invariants failed: {exc}"
            ) from exc
        object.__setattr__(
            self,
            "strategy_parameters",
            self.qualification.request.strategy.parameters,
        )

        provenance = self.signal_snapshot.provenance
        qualified_strategy, selection, train_days, grid = (
            _qualification_selection_contract(self.qualification)
        )
        if (
            provenance.qualification_evaluation_id
            != self.source_qualification_evaluation_id
        ):
            raise StrategyBoundRecommendationError(
                "signal provenance evaluation_id must equal recommendation qualification"
            )
        if provenance.strategy_id != qualified_strategy:
            raise StrategyBoundRecommendationError(
                "signal provenance strategy_id must equal qualification strategy"
            )
        selected = tuple(provenance.selected_parameters.items())
        if selected not in grid:
            raise StrategyBoundRecommendationError(
                "selected_parameters must belong to the qualified parameter grid"
            )
        if provenance.selection_metric != selection:
            raise StrategyBoundRecommendationError(
                "selection_metric must equal the qualification selection metric"
            )
        if provenance.selection_train_rows != train_days:
            raise StrategyBoundRecommendationError(
                "selection_train_rows must equal the qualified train_days"
            )


def build_strategy_bound_recommendation_evidence(
    *,
    recommendation_id: str,
    generated_at: str,
    qualification: StrategyQualificationResult,
    signal_snapshot: StrategyBoundSignalSnapshot,
) -> StrategyBoundRecommendationEvidence:
    """Build schema-1.1 evidence while reusing the Phase 56.3A action gate."""
    if not isinstance(qualification, StrategyQualificationResult):
        raise StrategyBoundRecommendationError(
            "qualification must be a StrategyQualificationResult"
        )
    if not isinstance(signal_snapshot, StrategyBoundSignalSnapshot):
        raise StrategyBoundRecommendationError(
            "signal_snapshot must be StrategyBoundSignalSnapshot"
        )
    legacy_snapshot = CurrentSignalSnapshot(
        symbol=signal_snapshot.symbol,
        observed_at=signal_snapshot.observed_at,
        signal=signal_snapshot.signal,
        score=0.0,
        latest_close=signal_snapshot.latest_close,
    )
    action = derive_recommendation_action(qualification, legacy_snapshot)
    return StrategyBoundRecommendationEvidence(
        schema_version=STRATEGY_BOUND_RECOMMENDATION_EVIDENCE_SCHEMA_VERSION,
        artifact_type=RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE,
        recommendation_id=recommendation_id,
        generated_at=generated_at,
        source_qualification_evaluation_id=qualification.request.evaluation_id,
        promotion_state=qualification.decision.state,
        strategy_id=qualification.request.strategy.strategy_id,
        strategy_parameters=qualification.request.strategy.parameters,
        qualification_finding_codes=qualification.decision.reason_codes,
        signal_snapshot=signal_snapshot,
        action=action,
        qualification=qualification,
    )


_ROOT_KEYS = (
    "schema_version",
    "artifact_type",
    "recommendation_id",
    "generated_at",
    "source_qualification_evaluation_id",
    "promotion_state",
    "strategy_id",
    "strategy_parameters",
    "qualification_finding_codes",
    "signal_snapshot",
    "action",
    "qualification",
)
_SIGNAL_KEYS = (
    "symbol",
    "observed_at",
    "signal",
    "latest_close",
    "provenance",
)
_PROVENANCE_KEYS = (
    "qualification_evaluation_id",
    "strategy_id",
    "selected_parameters",
    "selection_rule",
    "selection_metric",
    "selection_train_start",
    "selection_train_end",
    "selection_train_rows",
)


def _fail(path: str, message: str) -> NoReturn:
    raise StrategyBoundSerializationError(f"{path}: {message}")


def _json_value(value: Any, path: str) -> Any:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            _fail(path, "non-finite float values are not supported")
        return value
    if isinstance(value, (list, tuple)):
        return [
            _json_value(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key in sorted(value):
            if type(key) is not str or not key or key.strip() != key:
                _fail(path, "mapping keys must be clean exact strings")
            output[key] = _json_value(value[key], f"{path}.{key}")
        return output
    _fail(path, f"unsupported value type: {type(value).__name__}")


def serialize_strategy_bound_recommendation_evidence(
    evidence: StrategyBoundRecommendationEvidence,
) -> dict[str, Any]:
    if not isinstance(evidence, StrategyBoundRecommendationEvidence):
        _fail("$", "expected a StrategyBoundRecommendationEvidence instance")
    snapshot = evidence.signal_snapshot
    provenance = snapshot.provenance
    return {
        "schema_version": evidence.schema_version,
        "artifact_type": evidence.artifact_type,
        "recommendation_id": evidence.recommendation_id,
        "generated_at": evidence.generated_at,
        "source_qualification_evaluation_id": (
            evidence.source_qualification_evaluation_id
        ),
        "promotion_state": evidence.promotion_state,
        "strategy_id": evidence.strategy_id,
        "strategy_parameters": _json_value(
            evidence.strategy_parameters, "$.strategy_parameters"
        ),
        "qualification_finding_codes": list(
            evidence.qualification_finding_codes
        ),
        "signal_snapshot": {
            "symbol": snapshot.symbol,
            "observed_at": snapshot.observed_at,
            "signal": snapshot.signal,
            "latest_close": snapshot.latest_close,
            "provenance": {
                "qualification_evaluation_id": (
                    provenance.qualification_evaluation_id
                ),
                "strategy_id": provenance.strategy_id,
                "selected_parameters": dict(provenance.selected_parameters),
                "selection_rule": provenance.selection_rule,
                "selection_metric": provenance.selection_metric,
                "selection_train_start": provenance.selection_train_start,
                "selection_train_end": provenance.selection_train_end,
                "selection_train_rows": provenance.selection_train_rows,
            },
        },
        "action": evidence.action,
        "qualification": serialize_strategy_qualification_result(
            evidence.qualification
        ),
    }


def _exact_keys(
    value: dict[str, Any],
    expected: tuple[str, ...],
    path: str,
) -> None:
    missing = [key for key in expected if key not in value]
    unknown = [key for key in value if key not in expected]
    if missing:
        _fail(path, f"missing field(s): {', '.join(missing)}")
    if unknown:
        _fail(path, f"unknown field(s): {', '.join(unknown)}")


def _dict(
    value: Any,
    path: str,
    expected: tuple[str, ...],
) -> dict[str, Any]:
    if type(value) is not dict:
        _fail(path, "expected an exact dictionary")
    _exact_keys(value, expected, path)
    return value


def _list(value: Any, path: str) -> list[Any]:
    if type(value) is not list:
        _fail(path, "expected a list")
    return value


def _native_json(value: Any, path: str) -> Any:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            _fail(path, "non-finite float values are not supported")
        return value
    if type(value) is list:
        return [
            _native_json(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if type(value) is dict:
        output: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str or not key or key.strip() != key:
                _fail(path, "mapping keys must be clean exact strings")
            output[key] = _native_json(item, f"{path}.{key}")
        return output
    _fail(path, f"unsupported value type: {type(value).__name__}")


def _construct(path: str, constructor, **kwargs):
    try:
        return constructor(**kwargs)
    except StrategyBoundRecommendationError as exc:
        raise StrategyBoundSerializationError(
            f"{path}: model validation failed: {exc}"
        ) from exc


def deserialize_strategy_bound_recommendation_evidence(
    data: dict[str, Any],
) -> StrategyBoundRecommendationEvidence:
    root = _dict(data, "$", _ROOT_KEYS)
    if (
        root["schema_version"]
        != STRATEGY_BOUND_RECOMMENDATION_EVIDENCE_SCHEMA_VERSION
    ):
        _fail(
            "$.schema_version",
            f"unsupported schema version {root['schema_version']!r}",
        )
    if root["artifact_type"] != RECOMMENDATION_EVIDENCE_ARTIFACT_TYPE:
        _fail(
            "$.artifact_type",
            f"unsupported artifact type {root['artifact_type']!r}",
        )

    qualification_raw = root["qualification"]
    if type(qualification_raw) is not dict:
        _fail("$.qualification", "expected an exact dictionary")
    try:
        qualification = deserialize_strategy_qualification_result(
            qualification_raw
        )
    except QualificationSerializationError as exc:
        raise StrategyBoundSerializationError(
            f"$.qualification: {exc}"
        ) from exc

    snapshot_raw = _dict(
        root["signal_snapshot"], "$.signal_snapshot", _SIGNAL_KEYS
    )
    provenance_raw = _dict(
        snapshot_raw["provenance"],
        "$.signal_snapshot.provenance",
        _PROVENANCE_KEYS,
    )
    selected_raw = provenance_raw["selected_parameters"]
    if type(selected_raw) is not dict:
        _fail(
            "$.signal_snapshot.provenance.selected_parameters",
            "expected an exact dictionary",
        )
    provenance = _construct(
        "$.signal_snapshot.provenance",
        StrategySignalProvenance,
        qualification_evaluation_id=provenance_raw[
            "qualification_evaluation_id"
        ],
        strategy_id=provenance_raw["strategy_id"],
        selected_parameters=_native_json(
            selected_raw,
            "$.signal_snapshot.provenance.selected_parameters",
        ),
        selection_rule=provenance_raw["selection_rule"],
        selection_metric=provenance_raw["selection_metric"],
        selection_train_start=provenance_raw["selection_train_start"],
        selection_train_end=provenance_raw["selection_train_end"],
        selection_train_rows=provenance_raw["selection_train_rows"],
    )
    snapshot = _construct(
        "$.signal_snapshot",
        StrategyBoundSignalSnapshot,
        symbol=snapshot_raw["symbol"],
        observed_at=snapshot_raw["observed_at"],
        signal=snapshot_raw["signal"],
        latest_close=snapshot_raw["latest_close"],
        provenance=provenance,
    )

    parameters_raw = root["strategy_parameters"]
    if type(parameters_raw) is not dict:
        _fail("$.strategy_parameters", "expected an exact dictionary")
    codes = _list(
        root["qualification_finding_codes"],
        "$.qualification_finding_codes",
    )
    return _construct(
        "$",
        StrategyBoundRecommendationEvidence,
        schema_version=root["schema_version"],
        artifact_type=root["artifact_type"],
        recommendation_id=root["recommendation_id"],
        generated_at=root["generated_at"],
        source_qualification_evaluation_id=root[
            "source_qualification_evaluation_id"
        ],
        promotion_state=root["promotion_state"],
        strategy_id=root["strategy_id"],
        strategy_parameters=_native_json(
            parameters_raw, "$.strategy_parameters"
        ),
        qualification_finding_codes=tuple(codes),
        signal_snapshot=snapshot,
        action=root["action"],
        qualification=qualification,
    )


def export_strategy_bound_recommendation_evidence_json(
    evidence: StrategyBoundRecommendationEvidence,
) -> str:
    return (
        json.dumps(
            serialize_strategy_bound_recommendation_evidence(evidence),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
            sort_keys=True,
        )
        + "\n"
    )


def _reject_constant(value: str) -> NoReturn:
    raise StrategyBoundSerializationError(
        f"$: invalid JSON numeric constant {value}"
    )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrategyBoundSerializationError(
                f"$: duplicate JSON field {key!r}"
            )
        result[key] = value
    return result


def load_strategy_bound_recommendation_evidence_json(
    text: str,
) -> StrategyBoundRecommendationEvidence:
    if type(text) is not str:
        _fail("$", "JSON input must be an exact string")
    try:
        payload = json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_strict_object,
        )
    except StrategyBoundSerializationError:
        raise
    except json.JSONDecodeError as exc:
        raise StrategyBoundSerializationError(
            f"$: invalid JSON: {exc.msg}"
        ) from exc
    if type(payload) is not dict:
        _fail("$", "expected a JSON object")
    return deserialize_strategy_bound_recommendation_evidence(payload)


__all__ = [
    "STRATEGY_BOUND_RECOMMENDATION_EVIDENCE_SCHEMA_VERSION",
    "STRATEGY_SIGNAL_SELECTION_RULE",
    "StrategyBoundRecommendationError",
    "StrategyBoundRecommendationEvidence",
    "StrategyBoundSerializationError",
    "StrategyBoundSignal",
    "StrategyBoundSignalSnapshot",
    "StrategySignalProvenance",
    "build_strategy_bound_recommendation_evidence",
    "deserialize_strategy_bound_recommendation_evidence",
    "export_strategy_bound_recommendation_evidence_json",
    "load_strategy_bound_recommendation_evidence_json",
    "serialize_strategy_bound_recommendation_evidence",
]
