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


class _StringSubclass(str):
    pass


def _make_valid_manifest(
    status: str = "success",
    success_count: int = 0,
    failure_count: int = 0,
    partial_count: int = 0,
    errors: tuple[str, ...] = (),
    limitations: tuple[str, ...] = ("僅供研究使用",),
    strategy: str | None = None,
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
            strategy=strategy,
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
        manifest = _make_valid_manifest(strategy="ma_cross")
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
        self.assertEqual(payload["config"]["strategy"], "ma_cross")
        self.assertIs(type(payload["config"]["strategy"]), str)

    def test_serialize_run_manifest_serializes_nested_config_values(self) -> None:
        manifest = _make_valid_manifest(
            strategy="ma_cross",
            workflow_options={"levels": (1, 2), "meta": MappingProxyType({"a": 1})},
        )
        payload = serialize_run_manifest(manifest)
        self.assertEqual(payload["config"]["strategy"], "ma_cross")
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
        manifest = _make_valid_manifest(strategy="ma_cross")
        payload = serialize_run_manifest(manifest)
        restored = deserialize_run_manifest(payload)

        self.assertEqual(restored, manifest)
        self.assertEqual(restored.config.strategy, "ma_cross")

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

        for bad_version in [1, 1.0, "1", "2.0", None, _StringSubclass("1.0")]:
            payload = serialize_run_manifest(manifest)
            payload["schema_version"] = bad_version
            with self.assertRaises(ResearchRunSerializationError):
                deserialize_run_manifest(payload)

    def test_deserialize_run_manifest_requires_exact_schema_field_types(self) -> None:
        manifest = _make_valid_manifest()

        for bad_field, bad_val in [
            ("run_id", 12345),
            ("created_at", 123),
            ("tool_version", 123),
            ("status", 123),
            ("status", _StringSubclass("success")),
        ]:
            payload = serialize_run_manifest(manifest)
            payload[bad_field] = bad_val
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

        # Tuple canonical_symbols rejected (must be list in payload)
        payload1 = serialize_run_manifest(manifest)
        payload1["config"]["canonical_symbols"] = ("2330.TW",)
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload1)

        # Valid strategy forms
        payload_none = serialize_run_manifest(manifest)
        payload_none["config"]["strategy"] = None
        m_none = deserialize_run_manifest(payload_none)
        self.assertIsNone(m_none.config.strategy)

        payload_str = serialize_run_manifest(manifest)
        payload_str["config"]["strategy"] = "ma_cross"
        m_str = deserialize_run_manifest(payload_str)
        self.assertEqual(m_str.config.strategy, "ma_cross")

        # Invalid strategy forms
        for bad_strat in [{}, [], 1, True, _StringSubclass("ma_cross")]:
            payload_bad = serialize_run_manifest(manifest)
            payload_bad["config"]["strategy"] = bad_strat
            with self.assertRaises(ResearchRunSerializationError):
                deserialize_run_manifest(payload_bad)

        # Blank/unclean strategy wrapped
        for invalid_strat in ["", " ma_cross "]:
            payload_invalid = serialize_run_manifest(manifest)
            payload_invalid["config"]["strategy"] = invalid_strat
            with self.assertRaises(ResearchRunSerializationError) as ctx:
                deserialize_run_manifest(payload_invalid)
            self.assertIsInstance(ctx.exception.__cause__, ResearchRunModelError)

    def test_deserialize_run_manifest_validates_config_json_values(self) -> None:
        manifest = _make_valid_manifest()

        bad_payloads = [
            {"bad_tuple": (1, 2)},
            {"bad_nan": float("nan")},
            {"bad_inf": float("inf")},
            {"bad_neginf": float("-inf")},
            {1: "bad"},
            {"": "bad"},
            {" bad ": "bad"},
            {"bad_set": {1, 2}},
        ]
        for bad_opt in bad_payloads:
            payload = serialize_run_manifest(manifest)
            payload["config"]["workflow_options"] = bad_opt
            with self.assertRaises(ResearchRunSerializationError):
                deserialize_run_manifest(payload)

        # workflow_options itself must be exact dict
        for bad_wf in [MappingProxyType({"a": 1}), [1, 2]]:
            payload_wf = serialize_run_manifest(manifest)
            payload_wf["config"]["workflow_options"] = bad_wf
            with self.assertRaises(ResearchRunSerializationError):
                deserialize_run_manifest(payload_wf)

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

        valid_ds = {
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
        }

        # Missing field
        ds_missing = dict(valid_ds)
        del ds_missing["provider"]
        p_missing = serialize_run_manifest(manifest)
        p_missing["data_sources"] = [ds_missing]
        with self.assertRaises(ResearchRunSerializationError) as ctx_m:
            deserialize_run_manifest(p_missing)
        self.assertIn("missing field(s): provider", str(ctx_m.exception))

        # Unknown field
        ds_unknown = dict(valid_ds)
        ds_unknown["extra"] = 1
        p_unknown = serialize_run_manifest(manifest)
        p_unknown["data_sources"] = [ds_unknown]
        with self.assertRaises(ResearchRunSerializationError) as ctx_u:
            deserialize_run_manifest(p_unknown)
        self.assertIn("unknown field(s): extra", str(ctx_u.exception))

        # Non-string key
        ds_nonstr = dict(valid_ds)
        ds_nonstr[123] = "bad"  # type: ignore[dict-item]
        p_nonstr = serialize_run_manifest(manifest)
        p_nonstr["data_sources"] = [ds_nonstr]
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(p_nonstr)

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

        valid_art = {
            "artifact_type": "report",
            "path": "output/daily.json",
            "media_type": "application/json",
            "schema_version": "1.0",
        }

        # Missing field
        art_missing = dict(valid_art)
        del art_missing["media_type"]
        p_missing = serialize_run_manifest(manifest)
        p_missing["artifacts"] = [art_missing]
        with self.assertRaises(ResearchRunSerializationError) as ctx_m:
            deserialize_run_manifest(p_missing)
        self.assertIn("missing field(s): media_type", str(ctx_m.exception))

        # Unknown field
        art_unknown = dict(valid_art)
        art_unknown["extra"] = 1
        p_unknown = serialize_run_manifest(manifest)
        p_unknown["artifacts"] = [art_unknown]
        with self.assertRaises(ResearchRunSerializationError) as ctx_u:
            deserialize_run_manifest(p_unknown)
        self.assertIn("unknown field(s): extra", str(ctx_u.exception))

        # Non-string key
        art_nonstr = dict(valid_art)
        art_nonstr[123] = "bad"  # type: ignore[dict-item]
        p_nonstr = serialize_run_manifest(manifest)
        p_nonstr["artifacts"] = [art_nonstr]
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(p_nonstr)

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

        # Errors tuple rejected
        payload_tuple_err = serialize_run_manifest(manifest)
        payload_tuple_err["errors"] = ("err",)
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload_tuple_err)

        # Limitations tuple rejected
        payload_tuple_lim = serialize_run_manifest(manifest)
        payload_tuple_lim["limitations"] = ("lim",)
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload_tuple_lim)

        # Non-string error member
        payload_non_str_err = serialize_run_manifest(manifest)
        payload_non_str_err["errors"] = [123]
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload_non_str_err)

        # Non-string limitation member
        payload_non_str_lim = serialize_run_manifest(manifest)
        payload_non_str_lim["limitations"] = [123]
        with self.assertRaises(ResearchRunSerializationError):
            deserialize_run_manifest(payload_non_str_lim)

        # Blank/unclean error wrapped
        payload_blank_err = serialize_run_manifest(manifest)
        payload_blank_err["errors"] = [" "]
        with self.assertRaises(ResearchRunSerializationError) as ctx_err:
            deserialize_run_manifest(payload_blank_err)
        self.assertIsInstance(ctx_err.exception.__cause__, ResearchRunModelError)

        # Blank/unclean limitation wrapped
        payload_blank_lim = serialize_run_manifest(manifest)
        payload_blank_lim["limitations"] = [" "]
        with self.assertRaises(ResearchRunSerializationError) as ctx_lim:
            deserialize_run_manifest(payload_blank_lim)
        self.assertIsInstance(ctx_lim.exception.__cause__, ResearchRunModelError)

    def test_deserialize_run_manifest_validates_exact_counts(self) -> None:
        manifest = _make_valid_manifest()

        for count_field in ["success_count", "failure_count", "partial_count"]:
            for bad_count in [True, 1.0, "0"]:
                payload = serialize_run_manifest(manifest)
                payload[count_field] = bad_count
                with self.assertRaises(ResearchRunSerializationError):
                    deserialize_run_manifest(payload)

            # Negative int rejected by model and wrapped
            payload_neg = serialize_run_manifest(manifest)
            payload_neg[count_field] = -1
            with self.assertRaises(ResearchRunSerializationError) as ctx_neg:
                deserialize_run_manifest(payload_neg)
            self.assertIsInstance(ctx_neg.exception.__cause__, ResearchRunModelError)

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

    def test_export_run_manifest_json_has_strictly_one_trailing_newline(self) -> None:
        manifest = _make_valid_manifest()
        text1 = export_run_manifest_json(manifest)
        text2 = export_run_manifest_json(manifest)

        self.assertEqual(text1, text2)
        self.assertTrue(text1.endswith("\n"))
        self.assertFalse(text1.endswith("\n\n"))

    def test_load_run_manifest_json_round_trips_manifest(self) -> None:
        manifest = _make_valid_manifest(strategy="ma_cross")
        text = export_run_manifest_json(manifest)
        loaded = load_run_manifest_json(text)

        self.assertEqual(loaded, manifest)
        self.assertEqual(loaded.config.strategy, "ma_cross")

    def test_load_run_manifest_json_requires_exact_string(self) -> None:
        manifest = _make_valid_manifest()
        valid_text = export_run_manifest_json(manifest)

        with self.assertRaises(ResearchRunSerializationError):
            load_run_manifest_json(b'{"schema_version":"1.0"}')  # type: ignore[arg-type]

        with self.assertRaises(ResearchRunSerializationError):
            load_run_manifest_json(_StringSubclass(valid_text))

    def test_load_run_manifest_json_rejects_malformed_or_non_object_content(self) -> None:
        for bad_content in ["{", "[]", '"hello"', "null", "123"]:
            with self.assertRaises(ResearchRunSerializationError):
                load_run_manifest_json(bad_content)

    def test_load_run_manifest_json_rejects_nonstandard_constants_and_duplicate_keys(self) -> None:
        manifest = _make_valid_manifest()
        valid_text = export_run_manifest_json(manifest)

        for const_name in ["NaN", "Infinity", "-Infinity"]:
            const_text = valid_text.replace('"force_refresh": false', f'"force_refresh": {const_name}')
            with self.assertRaises(ResearchRunSerializationError):
                load_run_manifest_json(const_text)

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
        expected_serialization_exports = {
            "ResearchRunSerializationError",
            "deserialize_run_manifest",
            "export_run_manifest_json",
            "load_run_manifest_json",
            "serialize_run_manifest",
        }
        actual_exports = set(research_run_pkg.__all__)
        self.assertTrue(expected_serialization_exports.issubset(actual_exports))
        for name in expected_serialization_exports:
            self.assertTrue(hasattr(research_run_pkg, name))
        self.assertNotIn("_validate_exact_keys", actual_exports)
        self.assertNotIn("_object_pairs_hook", actual_exports)
