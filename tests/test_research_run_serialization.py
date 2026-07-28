"""Tests for Research Run Manifest serialization boundary."""

from __future__ import annotations

import json
from types import MappingProxyType
import unittest

from tw_stock_tool.research_run import (
    RUN_MANIFEST_SCHEMA_VERSION,
    ArtifactReference,
    DataSourceRecord,
    ResearchRunModelError,
    ResearchRunSerializationError,
    RunConfig,
    RunManifest,
    deserialize_run_manifest,
    export_run_manifest_json,
    load_run_manifest_json,
    serialize_run_manifest,
)
import tw_stock_tool.research_run as research_run_pkg


def _make_valid_manifest(
    status: str = "success",
    success_count: int = 0,
    failure_count: int = 0,
    partial_count: int = 0,
    errors: tuple[str, ...] = (),
    limitations: tuple[str, ...] = ("僅供研究使用",),
    workflow_options: dict | None = None,
) -> RunManifest:
    if workflow_options is None:
        workflow_options = {"title": "台股研究", "levels": [1, 2]}
    return RunManifest(
        schema_version=RUN_MANIFEST_SCHEMA_VERSION,
        run_id="550e8400-e29b-41d4-a716-446655440000",
        created_at="2026-07-27T20:00:00Z",
        tool_version="0.4.0",
        status=status,
        config=RunConfig(
            workflow="scan",
            universe="custom",
            canonical_symbols=("2330.TW",),
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
            strategy=None,
            backtest=None,
            parameter_sweep=None,
            walk_forward=None,
            ml=None,
            workflow_options=workflow_options,
        ),
        data_sources=(),
        success_count=success_count,
        failure_count=failure_count,
        partial_count=partial_count,
        artifacts=(),
        errors=errors,
        limitations=limitations,
    )


class TestResearchRunSerialization(unittest.TestCase):
    # A. Serialization: 8 tests

    def test_serialize_run_manifest_returns_exact_ordered_payload(self) -> None:
        manifest = _make_valid_manifest()
        payload = serialize_run_manifest(manifest)

        expected_manifest_keys = [
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
        ]
        self.assertEqual(list(payload.keys()), expected_manifest_keys)

        expected_config_keys = [
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
        ]
        self.assertEqual(list(payload["config"].keys()), expected_config_keys)

    def test_serialize_run_manifest_serializes_nested_config_values(self) -> None:
        manifest = _make_valid_manifest(
            workflow_options={"levels": (1, 2), "meta": MappingProxyType({"a": 1})}
        )
        payload = serialize_run_manifest(manifest)
        self.assertEqual(payload["config"]["workflow_options"]["levels"], [1, 2])
        self.assertEqual(payload["config"]["workflow_options"]["meta"], {"a": 1})

    def test_serialize_run_manifest_serializes_data_sources_and_artifacts(self) -> None:
        ds = DataSourceRecord(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            provider="yfinance",
            period="1y",
            interval="1d",
            auto_adjust=True,
            source_kind="live",
            cache_state="not_applicable",
            success=True,
            error=None,
        )
        art = ArtifactReference(
            artifact_type="report",
            path="output/daily.json",
            media_type="application/json",
            schema_version="1.0",
        )
        manifest = RunManifest(
            schema_version=RUN_MANIFEST_SCHEMA_VERSION,
            run_id="550e8400-e29b-41d4-a716-446655440000",
            created_at="2026-07-27T20:00:00Z",
            tool_version="0.4.0",
            status="success",
            config=RunConfig(
                workflow="scan",
                universe="custom",
                canonical_symbols=("2330.TW",),
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
                strategy=None,
                backtest=None,
                parameter_sweep=None,
                walk_forward=None,
                ml=None,
                workflow_options={},
            ),
            data_sources=(ds,),
            success_count=1,
            failure_count=0,
            partial_count=0,
            artifacts=(art,),
            errors=(),
            limitations=(),
        )
        payload = serialize_run_manifest(manifest)

        expected_ds_keys = [
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
        ]
        self.assertEqual(list(payload["data_sources"][0].keys()), expected_ds_keys)

        expected_art_keys = [
            "artifact_type",
            "path",
            "media_type",
            "schema_version",
        ]
        self.assertEqual(list(payload["artifacts"][0].keys()), expected_art_keys)

    def test_serialize_run_manifest_converts_tuples_to_lists(self) -> None:
        manifest = _make_valid_manifest(limitations=("a", "b"))
        payload = serialize_run_manifest(manifest)

        self.assertIsInstance(payload["config"]["canonical_symbols"], list)
        self.assertIsInstance(payload["data_sources"], list)
        self.assertIsInstance(payload["artifacts"], list)
        self.assertIsInstance(payload["errors"], list)
        self.assertIsInstance(payload["limitations"], list)

    def test_serialize_run_manifest_returns_detached_mutable_payload(self) -> None:
        manifest = _make_valid_manifest()
        payload = serialize_run_manifest(manifest)
        payload["config"]["workflow_options"]["levels"].append(3)

        self.assertEqual(manifest.config.workflow_options["levels"], (1, 2))

    def test_serialize_run_manifest_is_deterministic(self) -> None:
        manifest = _make_valid_manifest()
        p1 = serialize_run_manifest(manifest)
        p2 = serialize_run_manifest(manifest)

        self.assertEqual(p1, p2)
        self.assertEqual(list(p1.keys()), list(p2.keys()))

    def test_serialize_run_manifest_requires_run_manifest(self) -> None:
        with self.assertRaises(ResearchRunSerializationError):
            serialize_run_manifest({"schema_version": "1.0"})  # type: ignore[arg-type]

    def test_serialize_run_manifest_preserves_artifact_schema_version_types(self) -> None:
        art_none = ArtifactReference("r1", "p1.json", "app/json", None)
        art_int = ArtifactReference("r2", "p2.json", "app/json", 1)
        art_str = ArtifactReference("r3", "p3.json", "app/json", "1.0")

        manifest = RunManifest(
            schema_version=RUN_MANIFEST_SCHEMA_VERSION,
            run_id="550e8400-e29b-41d4-a716-446655440000",
            created_at="2026-07-27T20:00:00Z",
            tool_version="0.4.0",
            status="success",
            config=RunConfig(
                workflow="scan",
                universe="custom",
                canonical_symbols=("2330.TW",),
                period="1y",
                interval="1d",
                auto_adjust=True,
                force_refresh=False,
                strategy=None,
                backtest=None,
                parameter_sweep=None,
                walk_forward=None,
                ml=None,
                workflow_options={},
            ),
            data_sources=(),
            success_count=0,
            failure_count=0,
            partial_count=0,
            artifacts=(art_none, art_int, art_str),
            errors=(),
            limitations=(),
        )
        payload = serialize_run_manifest(manifest)
        self.assertIsNone(payload["artifacts"][0]["schema_version"])
        self.assertIs(type(payload["artifacts"][1]["schema_version"]), int)
        self.assertIs(type(payload["artifacts"][2]["schema_version"]), str)

    # B. Deserialization: 20 tests

    def test_deserialize_run_manifest_round_trips_success_manifest(self) -> None:
        manifest = _make_valid_manifest()
        payload = serialize_run_manifest(manifest)
        restored = deserialize_run_manifest(payload)

        self.assertEqual(restored, manifest)

    def test_deserialize_run_manifest_round_trips_partial_and_failure_manifests(self) -> None:
        partial_manifest = _make_valid_manifest(
            status="partial", success_count=1, failure_count=1
        )
        p_payload = serialize_run_manifest(partial_manifest)
        p_restored = deserialize_run_manifest(p_payload)
        self.assertEqual(p_restored, partial_manifest)

        failure_manifest = _make_valid_manifest(
            status="failure", failure_count=1, errors=("Failed to fetch data",)
        )
        f_payload = serialize_run_manifest(failure_manifest)
        f_restored = deserialize_run_manifest(f_payload)
        self.assertEqual(f_restored, failure_manifest)

    def test_deserialize_run_manifest_restores_deep_immutable_config(self) -> None:
        manifest = _make_valid_manifest()
        payload = serialize_run_manifest(manifest)
        restored = deserialize_run_manifest(payload)

        self.assertIsInstance(restored.config.canonical_symbols, tuple)
        self.assertIsInstance(restored.config.workflow_options, MappingProxyType)
        with self.assertRaises(TypeError):
            restored.config.workflow_options["levels"] = [3]  # type: ignore[index]

    def test_deserialize_run_manifest_requires_exact_top_level_dict(self) -> None:
        manifest = _make_valid_manifest()
        payload = serialize_run_manifest(manifest)
        proxy_payload = MappingProxyType(payload)

        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(proxy_payload)  # type: ignore[arg-type]

    def test_deserialize_run_manifest_rejects_missing_top_level_fields(self) -> None:
        manifest = _make_valid_manifest()
        payload = serialize_run_manifest(manifest)
        del payload["status"]

        with self.assertRaises(ResearchRunSerializationError) as ctx:
            deserialize_run_manifest(payload)
        self.assertIn("missing field(s): status", str(ctx.exception))

    def test_deserialize_run_manifest_rejects_unknown_top_level_fields(self) -> None:
        manifest = _make_valid_manifest()
        payload = serialize_run_manifest(manifest)
        payload["extra_field"] = 123

        with self.assertRaises(ResearchRunSerializationError) as ctx:
            deserialize_run_manifest(payload)
        self.assertIn("unknown field(s): extra_field", str(ctx.exception))

    def test_deserialize_run_manifest_rejects_unknown_schema_version(self) -> None:
        manifest = _make_valid_manifest()

        for bad_version in [1, 1.0, "1", "2.0", None]:
            payload = serialize_run_manifest(manifest)
            payload["schema_version"] = bad_version
            with self.assertRaises(ResearchRunSerializationError):
                deserialize_run_manifest(payload)

    def test_deserialize_run_manifest_requires_exact_schema_field_types(self) -> None:
        manifest = _make_valid_manifest()
        payload = serialize_run_manifest(manifest)
        payload["run_id"] = 12345

        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload)

    def test_deserialize_run_manifest_validates_exact_config_keys(self) -> None:
        manifest = _make_valid_manifest()
        payload = serialize_run_manifest(manifest)
        del payload["config"]["workflow"]

        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload)

        payload2 = serialize_run_manifest(manifest)
        payload2["config"]["unknown_opt"] = True
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload2)

    def test_deserialize_run_manifest_validates_config_field_types(self) -> None:
        manifest = _make_valid_manifest()
        payload = serialize_run_manifest(manifest)
        payload["config"]["canonical_symbols"] = ("2330.TW",)

        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload)

    def test_deserialize_run_manifest_validates_config_json_values(self) -> None:
        manifest = _make_valid_manifest()

        payload_tuple = serialize_run_manifest(manifest)
        payload_tuple["config"]["workflow_options"] = {"bad_tuple": (1, 2)}
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload_tuple)

        payload_nan = serialize_run_manifest(manifest)
        payload_nan["config"]["workflow_options"] = {"bad_nan": float("nan")}
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload_nan)

    def test_deserialize_run_manifest_validates_data_source_list_and_member_types(self) -> None:
        manifest = _make_valid_manifest()

        payload_tuple = serialize_run_manifest(manifest)
        payload_tuple["data_sources"] = ()
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload_tuple)

        payload_invalid_member = serialize_run_manifest(manifest)
        payload_invalid_member["data_sources"] = ["not_a_dict"]
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload_invalid_member)

    def test_deserialize_run_manifest_validates_exact_data_source_keys(self) -> None:
        manifest = _make_valid_manifest()
        payload = serialize_run_manifest(manifest)
        payload["data_sources"] = [
            {
                "canonical_symbol": "2330.TW",
                "requested_symbol": "2330",
                "provider": "yfinance",
                "period": "1y",
                "interval": "1d",
                "auto_adjust": True,
                "source_kind": "live",
                "cache_state": "not_applicable",
                "success": True,
                "error": None,
                "extra": 1,
            }
        ]
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload)

    def test_deserialize_run_manifest_wraps_data_source_model_errors(self) -> None:
        manifest = _make_valid_manifest()
        payload = serialize_run_manifest(manifest)
        payload["data_sources"] = [
            {
                "canonical_symbol": "2330.TW",
                "requested_symbol": "2330",
                "provider": "yfinance",
                "period": "1y",
                "interval": "1d",
                "auto_adjust": True,
                "source_kind": "invalid_kind",
                "cache_state": "not_applicable",
                "success": True,
                "error": None,
            }
        ]
        with self.assertRaises(ResearchRunSerializationError) as ctx:
            deserialize_run_manifest(payload)
        self.assertIsInstance(ctx.exception.__cause__, ResearchRunModelError)

    def test_deserialize_run_manifest_validates_artifact_list_and_member_types(self) -> None:
        manifest = _make_valid_manifest()

        payload_tuple = serialize_run_manifest(manifest)
        payload_tuple["artifacts"] = ()
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload_tuple)

        payload_invalid_member = serialize_run_manifest(manifest)
        payload_invalid_member["artifacts"] = [123]
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload_invalid_member)

    def test_deserialize_run_manifest_validates_exact_artifact_keys(self) -> None:
        manifest = _make_valid_manifest()
        payload = serialize_run_manifest(manifest)
        payload["artifacts"] = [
            {
                "artifact_type": "report",
                "path": "output/daily.json",
                "media_type": "application/json",
                # missing schema_version
            }
        ]
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload)

    def test_deserialize_run_manifest_wraps_artifact_model_errors(self) -> None:
        manifest = _make_valid_manifest()
        payload = serialize_run_manifest(manifest)
        payload["artifacts"] = [
            {
                "artifact_type": "report",
                "path": "",  # invalid blank path
                "media_type": "application/json",
                "schema_version": "1.0",
            }
        ]
        with self.assertRaises(ResearchRunSerializationError) as ctx:
            deserialize_run_manifest(payload)
        self.assertIsInstance(ctx.exception.__cause__, ResearchRunModelError)

    def test_deserialize_run_manifest_validates_errors_and_limitations_lists(self) -> None:
        manifest = _make_valid_manifest()

        payload_tuple_err = serialize_run_manifest(manifest)
        payload_tuple_err["errors"] = ("err",)
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload_tuple_err)

        payload_non_str_lim = serialize_run_manifest(manifest)
        payload_non_str_lim["limitations"] = [123]
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload_non_str_lim)

    def test_deserialize_run_manifest_validates_exact_counts(self) -> None:
        manifest = _make_valid_manifest()

        for bad_count in [True, 1.0, "0"]:
            payload = serialize_run_manifest(manifest)
            payload["success_count"] = bad_count
            with self.assertRaises(ResearchRunSerializationError):
                deserialize_run_manifest(payload)

    def test_deserialize_run_manifest_wraps_manifest_model_errors(self) -> None:
        manifest = _make_valid_manifest()
        payload = serialize_run_manifest(manifest)
        payload["status"] = "success"
        payload["failure_count"] = 1  # inconsistent with success status

        with self.assertRaises(ResearchRunSerializationError) as ctx:
            deserialize_run_manifest(payload)
        self.assertIsInstance(ctx.exception.__cause__, ResearchRunModelError)

    # C. JSON text: 7 tests

    def test_export_run_manifest_json_uses_contract_format(self) -> None:
        manifest = _make_valid_manifest()
        text = export_run_manifest_json(manifest)
        data = json.loads(text)

        self.assertEqual(data["schema_version"], "1.0")
        self.assertEqual(data["config"]["workflow"], "scan")

    def test_export_run_manifest_json_preserves_traditional_chinese(self) -> None:
        manifest = _make_valid_manifest()
        text = export_run_manifest_json(manifest)

        self.assertIn("台股研究", text)
        self.assertIn("僅供研究使用", text)
        self.assertNotIn("\\u53f0", text)

    def test_export_run_manifest_json_has_exactly_one_trailing_newline_and_is_deterministic(self) -> None:
        manifest = _make_valid_manifest()
        text1 = export_run_manifest_json(manifest)
        text2 = export_run_manifest_json(manifest)

        self.assertEqual(text1, text2)
        self.assertTrue(text1.endswith("\n"))
        self.assertFalse(text1.endswith("\n\n"))

    def test_load_run_manifest_json_round_trips_manifest(self) -> None:
        manifest = _make_valid_manifest()
        text = export_run_manifest_json(manifest)
        loaded = load_run_manifest_json(text)

        self.assertEqual(loaded, manifest)

    def test_load_run_manifest_json_requires_exact_string(self) -> None:
        with self.assertRaises(ResearchRunSerializationError):
            load_run_manifest_json(b'{"schema_version":"1.0"}')  # type: ignore[arg-type]

    def test_load_run_manifest_json_rejects_malformed_or_non_object_content(self) -> None:
        for bad_content in ["{", "[]", '"hello"', "null", "123"]:
            with self.assertRaises(ResearchRunSerializationError):
                load_run_manifest_json(bad_content)

    def test_load_run_manifest_json_rejects_nonstandard_constants_and_duplicate_keys(self) -> None:
        manifest = _make_valid_manifest()
        valid_text = export_run_manifest_json(manifest)

        nan_text = valid_text.replace('"force_refresh": false', '"force_refresh": NaN')
        with self.assertRaises(ResearchRunSerializationError):
            load_run_manifest_json(nan_text)

        top_dup = '{"schema_version":"1.0","schema_version":"2.0"}'
        with self.assertRaises(ResearchRunSerializationError) as ctx:
            load_run_manifest_json(top_dup)
        self.assertIn("duplicate dictionary key 'schema_version'", str(ctx.exception))

        nested_dup = '{"config":{"workflow":"scan","workflow":"daily"}}'
        with self.assertRaises(ResearchRunSerializationError) as ctx:
            load_run_manifest_json(nested_dup)
        self.assertIn("duplicate dictionary key 'workflow'", str(ctx.exception))

    # D. Public exports: 1 test

    def test_research_run_package_exports_serialization_boundary(self) -> None:
        expected_all = [
            "RUN_MANIFEST_SCHEMA_VERSION",
            "ArtifactReference",
            "CacheState",
            "DataSourceRecord",
            "ResearchRunModelError",
            "ResearchRunResult",
            "RunConfig",
            "RunManifest",
            "RunStatus",
            "SourceKind",
            "ResearchRunSerializationError",
            "deserialize_run_manifest",
            "export_run_manifest_json",
            "load_run_manifest_json",
            "serialize_run_manifest",
        ]
        self.assertEqual(research_run_pkg.__all__, expected_all)
        for name in expected_all:
            self.assertTrue(hasattr(research_run_pkg, name))
