"""Research-run core models and pure validation boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import math
import re
from types import MappingProxyType
from typing import Any, Literal, TypeAlias
from uuid import UUID

RUN_MANIFEST_SCHEMA_VERSION = "1.0"


class ResearchRunModelError(ValueError):
    """Raised when research-run model data violates its contract."""


RunStatus: TypeAlias = Literal[
    "success",
    "partial",
    "failure",
]

SourceKind: TypeAlias = Literal[
    "live",
    "cache",
]

CacheState: TypeAlias = Literal[
    "not_applicable",
    "fresh",
    "stale",
]

_JsonScalar: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
)

_FrozenJsonValue: TypeAlias = (
    _JsonScalar
    | tuple["_FrozenJsonValue", ...]
    | Mapping[str, "_FrozenJsonValue"]
)

_TIMESTAMP_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _require_clean_string(name: str, value: Any) -> str:
    if type(value) is not str:
        raise ResearchRunModelError(f"{name} must be exact str, got {type(value).__name__}")
    stripped = value.strip()
    if not stripped or value != stripped:
        raise ResearchRunModelError(f"{name} must be a clean non-blank string without leading/trailing whitespace")
    return value


def _require_optional_clean_string(name: str, value: Any) -> str | None:
    if value is None:
        return None
    return _require_clean_string(name, value)


def _require_exact_bool(name: str, value: Any) -> bool:
    if type(value) is not bool:
        raise ResearchRunModelError(f"{name} must be exact bool, got {type(value).__name__}")
    return value


def _require_exact_nonnegative_int(name: str, value: Any) -> int:
    if type(value) is not int:
        raise ResearchRunModelError(f"{name} must be exact int, got {type(value).__name__}")
    if value < 0:
        raise ResearchRunModelError(f"{name} must be non-negative, got {value}")
    return value


def _require_exact_tuple(name: str, value: Any) -> tuple[Any, ...]:
    if type(value) is not tuple:
        raise ResearchRunModelError(f"{name} must be exact tuple, got {type(value).__name__}")
    return value


def _freeze_json_value(name: str, value: Any) -> _FrozenJsonValue:
    if value is None:
        return None
    val_type = type(value)
    if val_type is str:
        return value
    if val_type is bool:
        return value
    if val_type is int:
        return value
    if val_type is float:
        if not math.isfinite(value):
            raise ResearchRunModelError(f"Non-finite float value in {name}: {value}")
        return value
    if val_type in (list, tuple):
        frozen_list = [_freeze_json_value(f"{name}[{i}]", item) for i, item in enumerate(value)]
        return tuple(frozen_list)
    if isinstance(value, Mapping):
        frozen_dict: dict[str, _FrozenJsonValue] = {}
        for k, v in value.items():
            if type(k) is not str:
                raise ResearchRunModelError(f"Mapping key in {name} must be exact str, got {type(k).__name__}")
            if not k.strip() or k != k.strip():
                raise ResearchRunModelError(f"Mapping key in {name} must be clean non-blank string, got {k!r}")
            frozen_dict[k] = _freeze_json_value(f"{name}.{k}", v)
        return MappingProxyType(frozen_dict)

    raise ResearchRunModelError(f"Unsupported runtime value in {name}: {value!r} of type {type(value).__name__}")


def _freeze_config_mapping(name: str, value: Any, allow_none: bool = True) -> Mapping[str, Any] | None:
    if value is None:
        if not allow_none:
            raise ResearchRunModelError(f"{name} cannot be None")
        return None
    if not isinstance(value, Mapping):
        raise ResearchRunModelError(f"{name} must be a Mapping, got {type(value).__name__}")
    frozen = _freeze_json_value(name, value)
    assert isinstance(frozen, Mapping)
    return frozen


def _validate_uuid_v4(name: str, value: Any) -> str:
    clean_str = _require_clean_string(name, value)
    try:
        parsed = UUID(clean_str)
    except ValueError as e:
        raise ResearchRunModelError(f"Invalid UUID string for {name}: {clean_str!r}") from e
    if parsed.version != 4:
        raise ResearchRunModelError(f"{name} must be UUID version 4, got version {parsed.version}")
    if str(parsed) != clean_str:
        raise ResearchRunModelError(f"{name} must be canonical lowercase rendering, got {clean_str!r}")
    return clean_str


def _validate_utc_timestamp(name: str, value: Any) -> str:
    clean_str = _require_clean_string(name, value)
    if not _TIMESTAMP_REGEX.match(clean_str):
        raise ResearchRunModelError(f"{name} must match exact UTC RFC 3339 timestamp format 'YYYY-MM-DDTHH:MM:SSZ', got {clean_str!r}")
    try:
        datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as e:
        raise ResearchRunModelError(f"{name} contains invalid date/time: {clean_str!r}") from e
    return clean_str


@dataclass(frozen=True, slots=True)
class RunConfig:
    workflow: str
    universe: str | None
    canonical_symbols: tuple[str, ...]
    period: str
    interval: str
    auto_adjust: bool
    force_refresh: bool
    strategy: str | None
    backtest: Mapping[str, Any] | None
    parameter_sweep: Mapping[str, Any] | None
    walk_forward: Mapping[str, Any] | None
    ml: Mapping[str, Any] | None
    workflow_options: Mapping[str, Any]

    def __post_init__(self) -> None:
        _require_clean_string("workflow", self.workflow)
        _require_optional_clean_string("universe", self.universe)
        _require_clean_string("period", self.period)
        _require_clean_string("interval", self.interval)
        _require_exact_bool("auto_adjust", self.auto_adjust)
        _require_exact_bool("force_refresh", self.force_refresh)
        _require_optional_clean_string("strategy", self.strategy)

        _require_exact_tuple("canonical_symbols", self.canonical_symbols)
        if len(self.canonical_symbols) == 0:
            raise ResearchRunModelError("canonical_symbols must contain at least one symbol")
        seen_symbols: set[str] = set()
        for i, sym in enumerate(self.canonical_symbols):
            clean_sym = _require_clean_string(f"canonical_symbols[{i}]", sym)
            if clean_sym in seen_symbols:
                raise ResearchRunModelError(f"Duplicate symbol in canonical_symbols: {clean_sym}")
            seen_symbols.add(clean_sym)

        object.__setattr__(self, "backtest", _freeze_config_mapping("backtest", self.backtest, allow_none=True))
        object.__setattr__(self, "parameter_sweep", _freeze_config_mapping("parameter_sweep", self.parameter_sweep, allow_none=True))
        object.__setattr__(self, "walk_forward", _freeze_config_mapping("walk_forward", self.walk_forward, allow_none=True))
        object.__setattr__(self, "ml", _freeze_config_mapping("ml", self.ml, allow_none=True))
        object.__setattr__(self, "workflow_options", _freeze_config_mapping("workflow_options", self.workflow_options, allow_none=False))


@dataclass(frozen=True, slots=True)
class DataSourceRecord:
    canonical_symbol: str
    requested_symbol: str
    provider: str
    period: str
    interval: str
    auto_adjust: bool
    source_kind: SourceKind
    cache_state: CacheState
    success: bool
    error: str | None

    def __post_init__(self) -> None:
        _require_clean_string("canonical_symbol", self.canonical_symbol)
        _require_clean_string("requested_symbol", self.requested_symbol)
        _require_clean_string("provider", self.provider)
        _require_clean_string("period", self.period)
        _require_clean_string("interval", self.interval)
        _require_exact_bool("auto_adjust", self.auto_adjust)
        _require_exact_bool("success", self.success)

        source_kind = _require_clean_string("source_kind", self.source_kind)
        cache_state = _require_clean_string("cache_state", self.cache_state)

        if source_kind not in ("live", "cache"):
            raise ResearchRunModelError(f"source_kind must be 'live' or 'cache', got {source_kind!r}")
        if cache_state not in ("not_applicable", "fresh", "stale"):
            raise ResearchRunModelError(f"cache_state must be 'not_applicable', 'fresh', or 'stale', got {cache_state!r}")

        if source_kind == "live" and cache_state != "not_applicable":
            raise ResearchRunModelError(
                "cache_state must be 'not_applicable' when source_kind is 'live'"
            )
        if source_kind == "cache" and cache_state not in ("fresh", "stale"):
            raise ResearchRunModelError("cache_state must be 'fresh' or 'stale' when source_kind is 'cache'")

        if self.success:
            if self.error is not None:
                raise ResearchRunModelError("error must be None when success is True")
        else:
            if self.error is None:
                raise ResearchRunModelError("error must be a clean non-blank string when success is False")
            _require_clean_string("error", self.error)


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    artifact_type: str
    path: str
    media_type: str
    schema_version: int | str | None

    def __post_init__(self) -> None:
        _require_clean_string("artifact_type", self.artifact_type)
        _require_clean_string("path", self.path)
        if "\\" in self.path:
            raise ResearchRunModelError(f"path must use POSIX forward slashes, got backslash in {self.path!r}")
        _require_clean_string("media_type", self.media_type)

        if self.schema_version is not None:
            sv_type = type(self.schema_version)
            if sv_type is int:
                if self.schema_version <= 0:
                    raise ResearchRunModelError(f"schema_version integer must be positive, got {self.schema_version}")
            elif sv_type is str:
                _require_clean_string("schema_version", self.schema_version)
            else:
                raise ResearchRunModelError(f"schema_version must be int, str, or None, got {sv_type.__name__}")


@dataclass(frozen=True, slots=True)
class RunManifest:
    schema_version: str
    run_id: str
    created_at: str
    tool_version: str
    status: RunStatus
    config: RunConfig
    data_sources: tuple[DataSourceRecord, ...]
    success_count: int
    failure_count: int
    partial_count: int
    artifacts: tuple[ArtifactReference, ...]
    errors: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_clean_string("schema_version", self.schema_version)
        if self.schema_version != RUN_MANIFEST_SCHEMA_VERSION:
            raise ResearchRunModelError(f"schema_version must equal {RUN_MANIFEST_SCHEMA_VERSION!r}, got {self.schema_version!r}")

        _validate_uuid_v4("run_id", self.run_id)
        _validate_utc_timestamp("created_at", self.created_at)
        _require_clean_string("tool_version", self.tool_version)

        status = _require_clean_string("status", self.status)
        if status not in ("success", "partial", "failure"):
            raise ResearchRunModelError(f"status must be 'success', 'partial', or 'failure', got {status!r}")

        if not isinstance(self.config, RunConfig):
            raise ResearchRunModelError(f"config must be RunConfig instance, got {type(self.config).__name__}")

        _require_exact_tuple("data_sources", self.data_sources)
        for i, ds in enumerate(self.data_sources):
            if not isinstance(ds, DataSourceRecord):
                raise ResearchRunModelError(f"data_sources[{i}] must be DataSourceRecord instance, got {type(ds).__name__}")

        _require_exact_nonnegative_int("success_count", self.success_count)
        _require_exact_nonnegative_int("failure_count", self.failure_count)
        _require_exact_nonnegative_int("partial_count", self.partial_count)

        _require_exact_tuple("artifacts", self.artifacts)
        for i, art in enumerate(self.artifacts):
            if not isinstance(art, ArtifactReference):
                raise ResearchRunModelError(f"artifacts[{i}] must be ArtifactReference instance, got {type(art).__name__}")

        _require_exact_tuple("errors", self.errors)
        for i, err in enumerate(self.errors):
            _require_clean_string(f"errors[{i}]", err)

        _require_exact_tuple("limitations", self.limitations)
        for i, lim in enumerate(self.limitations):
            _require_clean_string(f"limitations[{i}]", lim)

        # Status & count consistency rules
        if self.status == "success":
            if self.failure_count != 0 or self.partial_count != 0:
                raise ResearchRunModelError("When status is 'success', failure_count and partial_count must be 0")
        elif self.status == "failure":
            if self.success_count != 0 or self.partial_count != 0:
                raise ResearchRunModelError("When status is 'failure', success_count and partial_count must be 0")
            if self.failure_count < 1:
                raise ResearchRunModelError("When status is 'failure', failure_count must be at least 1")
            if len(self.errors) < 1:
                raise ResearchRunModelError("When status is 'failure', errors must contain at least 1 message")
        elif self.status == "partial":
            if not (self.partial_count >= 1 or (self.success_count >= 1 and self.failure_count >= 1)):
                raise ResearchRunModelError("When status is 'partial', partial_count must be >= 1 OR (success_count >= 1 AND failure_count >= 1)")


@dataclass(frozen=True, slots=True)
class ResearchRunResult:
    manifest: RunManifest
    domain_result: Any | None
    generated_artifacts: tuple[ArtifactReference, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, RunManifest):
            raise ResearchRunModelError(f"manifest must be RunManifest instance, got {type(self.manifest).__name__}")

        _require_exact_tuple("generated_artifacts", self.generated_artifacts)
        for i, art in enumerate(self.generated_artifacts):
            if not isinstance(art, ArtifactReference):
                raise ResearchRunModelError(f"generated_artifacts[{i}] must be ArtifactReference instance, got {type(art).__name__}")

        if self.generated_artifacts != self.manifest.artifacts:
            raise ResearchRunModelError("generated_artifacts must equal manifest.artifacts")
