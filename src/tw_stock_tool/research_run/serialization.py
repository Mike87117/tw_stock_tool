"""JSON serialization boundary for Research Run Manifest artifacts."""

from __future__ import annotations

from collections.abc import Mapping
import json
import math
from typing import Any, NoReturn

from tw_stock_tool.research_run.models import (
    RUN_MANIFEST_SCHEMA_VERSION,
    ArtifactReference,
    DataSourceRecord,
    ResearchRunModelError,
    RunConfig,
    RunManifest,
)

_RUN_MANIFEST_KEYS = (
    "schema_version",
    "run_id",
    "created_at",
    "tool_version",
    "status",
    "config",
    "data_sources",
    "success_count",
    "failure_count",
    "partial_count",
    "artifacts",
    "errors",
    "limitations",
)

_RUN_CONFIG_KEYS = (
    "workflow",
    "universe",
    "canonical_symbols",
    "period",
    "interval",
    "auto_adjust",
    "force_refresh",
    "strategy",
    "backtest",
    "parameter_sweep",
    "walk_forward",
    "ml",
    "workflow_options",
)

_DATA_SOURCE_RECORD_KEYS = (
    "canonical_symbol",
    "requested_symbol",
    "provider",
    "period",
    "interval",
    "auto_adjust",
    "source_kind",
    "cache_state",
    "success",
    "error",
)

_ARTIFACT_REFERENCE_KEYS = (
    "artifact_type",
    "path",
    "media_type",
    "schema_version",
)


class ResearchRunSerializationError(ValueError):
    """Raised when a run manifest cannot be serialized or read back."""


def _fail(path: str, message: str) -> NoReturn:
    raise ResearchRunSerializationError(f"{path}: {message}")


def _serialize_json_value(value: Any, path: str) -> Any:
    if value is None:
        return None
    if type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            _fail(path, "non-finite float values are not supported")
        return value
    if type(value) is str:
        return value
    if isinstance(value, (list, tuple)):
        return [
            _serialize_json_value(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        serialized_dict: dict[str, Any] = {}
        for k, v in value.items():
            if type(k) is not str:
                _fail(path, f"dictionary key {k!r} must be an exact string")
            serialized_dict[k] = _serialize_json_value(v, f"{path}.{k}")
        return serialized_dict

    _fail(path, f"unsupported value type: {type(value).__name__}")


def serialize_run_manifest(manifest: RunManifest) -> dict[str, Any]:
    """Serialize a RunManifest instance into a deterministic dictionary."""
    if not isinstance(manifest, RunManifest):
        _fail("$", "expected a RunManifest instance")

    config = manifest.config
    serialized_config: dict[str, Any] = {
        "workflow": config.workflow,
        "universe": config.universe,
        "canonical_symbols": list(config.canonical_symbols),
        "period": config.period,
        "interval": config.interval,
        "auto_adjust": config.auto_adjust,
        "force_refresh": config.force_refresh,
        "strategy": _serialize_json_value(config.strategy, "$.config.strategy"),
        "backtest": _serialize_json_value(config.backtest, "$.config.backtest"),
        "parameter_sweep": _serialize_json_value(config.parameter_sweep, "$.config.parameter_sweep"),
        "walk_forward": _serialize_json_value(config.walk_forward, "$.config.walk_forward"),
        "ml": _serialize_json_value(config.ml, "$.config.ml"),
        "workflow_options": _serialize_json_value(config.workflow_options, "$.config.workflow_options"),
    }

    serialized_data_sources = [
        {
            "canonical_symbol": ds.canonical_symbol,
            "requested_symbol": ds.requested_symbol,
            "provider": ds.provider,
            "period": ds.period,
            "interval": ds.interval,
            "auto_adjust": ds.auto_adjust,
            "source_kind": ds.source_kind,
            "cache_state": ds.cache_state,
            "success": ds.success,
            "error": ds.error,
        }
        for ds in manifest.data_sources
    ]

    serialized_artifacts = [
        {
            "artifact_type": art.artifact_type,
            "path": art.path,
            "media_type": art.media_type,
            "schema_version": art.schema_version,
        }
        for art in manifest.artifacts
    ]

    return {
        "schema_version": manifest.schema_version,
        "run_id": manifest.run_id,
        "created_at": manifest.created_at,
        "tool_version": manifest.tool_version,
        "status": manifest.status,
        "config": serialized_config,
        "data_sources": serialized_data_sources,
        "success_count": manifest.success_count,
        "failure_count": manifest.failure_count,
        "partial_count": manifest.partial_count,
        "artifacts": serialized_artifacts,
        "errors": list(manifest.errors),
        "limitations": list(manifest.limitations),
    }


def _validate_exact_keys(
    value: dict[str, Any],
    expected: tuple[str, ...],
    path: str,
) -> None:
    keys = list(value.keys())
    for key in keys:
        if type(key) is not str:
            _fail(path, f"dictionary key {key!r} must be an exact string")

    expected_set = set(expected)
    actual_set = set(keys)

    missing = [key for key in expected if key not in actual_set]
    unknown = [key for key in keys if key not in expected_set]

    if missing:
        _fail(path, f"missing field(s): {', '.join(missing)}")
    if unknown:
        _fail(path, f"unknown field(s): {', '.join(unknown)}")


def _validate_json_native_value(value: Any, path: str) -> Any:
    if value is None:
        return None
    if type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            _fail(path, "non-finite float values are not supported")
        return value
    if type(value) is str:
        return value
    if type(value) is list:
        return [
            _validate_json_native_value(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if type(value) is dict:
        validated_dict: dict[str, Any] = {}
        for k, v in value.items():
            if type(k) is not str or k.strip() != k or len(k) == 0:
                _fail(path, f"dictionary key {k!r} must be a clean exact string")
            validated_dict[k] = _validate_json_native_value(v, f"{path}.{k}")
        return validated_dict

    _fail(path, f"unsupported value type: {type(value).__name__}")


def deserialize_run_manifest(data: dict[str, Any]) -> RunManifest:
    """Deserialize a dictionary payload into a validated RunManifest instance."""
    if type(data) is not dict:
        _fail("$", "expected an exact dictionary")

    _validate_exact_keys(data, _RUN_MANIFEST_KEYS, "$")

    schema_version = data["schema_version"]
    if type(schema_version) is not str:
        _fail("$.schema_version", "must be an exact string")
    if schema_version != RUN_MANIFEST_SCHEMA_VERSION:
        _fail("$.schema_version", f"unsupported schema version {schema_version!r}")

    run_id = data["run_id"]
    if type(run_id) is not str:
        _fail("$.run_id", "must be an exact string")

    created_at = data["created_at"]
    if type(created_at) is not str:
        _fail("$.created_at", "must be an exact string")

    tool_version = data["tool_version"]
    if type(tool_version) is not str:
        _fail("$.tool_version", "must be an exact string")

    status = data["status"]
    if type(status) is not str:
        _fail("$.status", "must be an exact string")

    # Validate Config
    config_dict = data["config"]
    if type(config_dict) is not dict:
        _fail("$.config", "expected an exact dictionary")
    _validate_exact_keys(config_dict, _RUN_CONFIG_KEYS, "$.config")

    canonical_symbols_raw = config_dict["canonical_symbols"]
    if type(canonical_symbols_raw) is not list:
        _fail("$.config.canonical_symbols", "expected a list")

    strategy_raw = config_dict["strategy"]
    if strategy_raw is not None:
        if type(strategy_raw) is not dict:
            _fail("$.config.strategy", "expected a dictionary or None")
        strategy_val = _validate_json_native_value(strategy_raw, "$.config.strategy")
    else:
        strategy_val = None

    backtest_raw = config_dict["backtest"]
    if backtest_raw is not None:
        if type(backtest_raw) is not dict:
            _fail("$.config.backtest", "expected a dictionary or None")
        backtest_val = _validate_json_native_value(backtest_raw, "$.config.backtest")
    else:
        backtest_val = None

    param_sweep_raw = config_dict["parameter_sweep"]
    if param_sweep_raw is not None:
        if type(param_sweep_raw) is not dict:
            _fail("$.config.parameter_sweep", "expected a dictionary or None")
        param_sweep_val = _validate_json_native_value(param_sweep_raw, "$.config.parameter_sweep")
    else:
        param_sweep_val = None

    walk_forward_raw = config_dict["walk_forward"]
    if walk_forward_raw is not None:
        if type(walk_forward_raw) is not dict:
            _fail("$.config.walk_forward", "expected a dictionary or None")
        walk_forward_val = _validate_json_native_value(walk_forward_raw, "$.config.walk_forward")
    else:
        walk_forward_val = None

    ml_raw = config_dict["ml"]
    if ml_raw is not None:
        if type(ml_raw) is not dict:
            _fail("$.config.ml", "expected a dictionary or None")
        ml_val = _validate_json_native_value(ml_raw, "$.config.ml")
    else:
        ml_val = None

    wf_opt_raw = config_dict["workflow_options"]
    if type(wf_opt_raw) is not dict:
        _fail("$.config.workflow_options", "expected a dictionary")
    wf_opt_val = _validate_json_native_value(wf_opt_raw, "$.config.workflow_options")

    try:
        config_obj = RunConfig(
            workflow=config_dict["workflow"],
            universe=config_dict["universe"],
            canonical_symbols=tuple(canonical_symbols_raw),
            period=config_dict["period"],
            interval=config_dict["interval"],
            auto_adjust=config_dict["auto_adjust"],
            force_refresh=config_dict["force_refresh"],
            strategy=strategy_val,
            backtest=backtest_val,
            parameter_sweep=param_sweep_val,
            walk_forward=walk_forward_val,
            ml=ml_val,
            workflow_options=wf_opt_val,
        )
    except ResearchRunModelError as exc:
        raise ResearchRunSerializationError(f"$.config: model validation failed: {exc}") from exc

    # Validate data_sources
    ds_raw = data["data_sources"]
    if type(ds_raw) is not list:
        _fail("$.data_sources", "expected a list")

    data_source_objs: list[DataSourceRecord] = []
    for idx, ds_item in enumerate(ds_raw):
        ds_path = f"$.data_sources[{idx}]"
        if type(ds_item) is not dict:
            _fail(ds_path, "expected an exact dictionary")
        _validate_exact_keys(ds_item, _DATA_SOURCE_RECORD_KEYS, ds_path)

        try:
            ds_obj = DataSourceRecord(
                canonical_symbol=ds_item["canonical_symbol"],
                requested_symbol=ds_item["requested_symbol"],
                provider=ds_item["provider"],
                period=ds_item["period"],
                interval=ds_item["interval"],
                auto_adjust=ds_item["auto_adjust"],
                source_kind=ds_item["source_kind"],
                cache_state=ds_item["cache_state"],
                success=ds_item["success"],
                error=ds_item["error"],
            )
        except ResearchRunModelError as exc:
            raise ResearchRunSerializationError(f"{ds_path}: model validation failed: {exc}") from exc
        data_source_objs.append(ds_obj)

    # Validate counts
    success_count = data["success_count"]
    if type(success_count) is not int or type(success_count) is bool:
        _fail("$.success_count", "must be an exact integer")

    failure_count = data["failure_count"]
    if type(failure_count) is not int or type(failure_count) is bool:
        _fail("$.failure_count", "must be an exact integer")

    partial_count = data["partial_count"]
    if type(partial_count) is not int or type(partial_count) is bool:
        _fail("$.partial_count", "must be an exact integer")

    # Validate artifacts
    art_raw = data["artifacts"]
    if type(art_raw) is not list:
        _fail("$.artifacts", "expected a list")

    artifact_objs: list[ArtifactReference] = []
    for idx, art_item in enumerate(art_raw):
        art_path = f"$.artifacts[{idx}]"
        if type(art_item) is not dict:
            _fail(art_path, "expected an exact dictionary")
        _validate_exact_keys(art_item, _ARTIFACT_REFERENCE_KEYS, art_path)

        try:
            art_obj = ArtifactReference(
                artifact_type=art_item["artifact_type"],
                path=art_item["path"],
                media_type=art_item["media_type"],
                schema_version=art_item["schema_version"],
            )
        except ResearchRunModelError as exc:
            raise ResearchRunSerializationError(f"{art_path}: model validation failed: {exc}") from exc
        artifact_objs.append(art_obj)

    # Validate errors and limitations lists
    errors_raw = data["errors"]
    if type(errors_raw) is not list:
        _fail("$.errors", "expected a list")
    for idx, err_item in enumerate(errors_raw):
        if type(err_item) is not str:
            _fail(f"$.errors[{idx}]", "must be an exact string")

    limitations_raw = data["limitations"]
    if type(limitations_raw) is not list:
        _fail("$.limitations", "expected a list")
    for idx, lim_item in enumerate(limitations_raw):
        if type(lim_item) is not str:
            _fail(f"$.limitations[{idx}]", "must be an exact string")

    try:
        manifest_obj = RunManifest(
            schema_version=schema_version,
            run_id=run_id,
            created_at=created_at,
            tool_version=tool_version,
            status=status,
            config=config_obj,
            data_sources=tuple(data_source_objs),
            success_count=success_count,
            failure_count=failure_count,
            partial_count=partial_count,
            artifacts=tuple(artifact_objs),
            errors=tuple(errors_raw),
            limitations=tuple(limitations_raw),
        )
    except ResearchRunModelError as exc:
        raise ResearchRunSerializationError(f"$: model validation failed: {exc}") from exc

    return manifest_obj


def export_run_manifest_json(manifest: RunManifest) -> str:
    """Export a RunManifest instance as a deterministic JSON string."""
    payload = serialize_run_manifest(manifest)
    text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )
    return text + "\n"


def _reject_json_constant(value: str) -> NoReturn:
    raise ResearchRunSerializationError(f"$: unsupported JSON constant {value}")


def _object_pairs_hook(pairs: list[tuple[Any, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    result: dict[str, Any] = {}
    for key, value in pairs:
        if type(key) is not str:
            raise ResearchRunSerializationError(f"$: dictionary key {key!r} must be an exact string")
        if key in seen:
            raise ResearchRunSerializationError(f"$: duplicate dictionary key {key!r}")
        seen.add(key)
        result[key] = value
    return result


def load_run_manifest_json(content: str) -> RunManifest:
    """Load a JSON string into a validated RunManifest instance."""
    if type(content) is not str:
        raise ResearchRunSerializationError("$.content: expected a JSON string")
    try:
        data = json.loads(
            content,
            object_pairs_hook=_object_pairs_hook,
            parse_constant=_reject_json_constant,
        )
    except ResearchRunSerializationError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ResearchRunSerializationError(f"$: invalid JSON: {exc}") from exc

    return deserialize_run_manifest(data)
