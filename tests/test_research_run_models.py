"""Unit tests for research run core models and pure validation boundary."""

import unittest
from datetime import datetime
from pathlib import Path
from types import MappingProxyType

import pandas as pd

from tw_stock_tool import research_run
from tw_stock_tool.research_run import (
    RUN_MANIFEST_SCHEMA_VERSION,
    ArtifactReference,
    DataSourceRecord,
    ResearchRunModelError,
    ResearchRunResult,
    RunConfig,
    RunManifest,
)


def _build_valid_config() -> RunConfig:
    return RunConfig(
        workflow="scan",
        universe="custom",
        canonical_symbols=("2330.TW", "2317.TW"),
        period="1y",
        interval="1d",
        auto_adjust=True,
        force_refresh=False,
        strategy="ma_cross",
        backtest={"initial_capital": 100000.0},
        parameter_sweep=None,
        walk_forward=None,
        ml=None,
        workflow_options={"top": 5},
    )


def _build_valid_artifact() -> ArtifactReference:
    return ArtifactReference(
        artifact_type="daily_report_json",
        path="output/daily_report.json",
        media_type="application/json",
        schema_version=1,
    )


def _build_valid_manifest(
    status: str = "success",
    success_count: int = 1,
    failure_count: int = 0,
    partial_count: int = 0,
    errors: tuple[str, ...] = (),
) -> RunManifest:
    return RunManifest(
        schema_version=RUN_MANIFEST_SCHEMA_VERSION,
        run_id="550e8400-e29b-41d4-a716-446655440000",
        created_at="2026-07-27T20:00:00Z",
        tool_version="0.4.0",
        status=status,
        config=_build_valid_config(),
        data_sources=(
            DataSourceRecord(
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
            ),
        ),
        success_count=success_count,
        failure_count=failure_count,
        partial_count=partial_count,
        artifacts=(_build_valid_artifact(),),
        errors=errors,
        limitations=("Data delayed by 15 mins",),
    )


class TestResearchRunModels(unittest.TestCase):
    # RunConfig Tests (11)

    def test_run_config_accepts_valid_resolved_configuration(self):
        config = _build_valid_config()
        self.assertEqual(config.workflow, "scan")
        self.assertEqual(config.universe, "custom")
        self.assertEqual(config.canonical_symbols, ("2330.TW", "2317.TW"))
        self.assertTrue(config.auto_adjust)
        self.assertFalse(config.force_refresh)
        self.assertEqual(config.backtest, MappingProxyType({"initial_capital": 100000.0}))

    def test_run_config_is_frozen(self):
        config = _build_valid_config()
        with self.assertRaises(Exception):
            config.workflow = "daily"  # type: ignore[misc]

    def test_run_config_requires_exact_canonical_symbol_tuple(self):
        with self.assertRaisesRegex(ResearchRunModelError, "canonical_symbols must be exact tuple"):
            RunConfig(
                workflow="scan",
                universe=None,
                canonical_symbols=["2330.TW"],  # type: ignore[arg-type]
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
            )

    def test_run_config_rejects_empty_duplicate_or_unclean_symbols(self):
        base_args = dict(
            workflow="scan",
            universe=None,
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
        )
        with self.assertRaisesRegex(ResearchRunModelError, "canonical_symbols must contain at least one symbol"):
            RunConfig(canonical_symbols=(), **base_args)

        with self.assertRaisesRegex(ResearchRunModelError, "Duplicate symbol in canonical_symbols"):
            RunConfig(canonical_symbols=("2330.TW", "2330.TW"), **base_args)

        with self.assertRaisesRegex(ResearchRunModelError, "canonical_symbols\\[0\\] must be a clean non-blank string"):
            RunConfig(canonical_symbols=(" 2330.TW ",), **base_args)

    def test_run_config_validates_required_clean_strings(self):
        base_args = dict(
            universe=None,
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
        )
        with self.assertRaisesRegex(ResearchRunModelError, "workflow must be exact str"):
            RunConfig(workflow=123, **base_args)  # type: ignore[arg-type]

        with self.assertRaisesRegex(ResearchRunModelError, "workflow must be a clean non-blank string"):
            RunConfig(workflow=" scan ", **base_args)

    def test_run_config_requires_exact_booleans(self):
        base_args = dict(
            workflow="scan",
            universe=None,
            canonical_symbols=("2330.TW",),
            period="1y",
            interval="1d",
            force_refresh=False,
            strategy=None,
            backtest=None,
            parameter_sweep=None,
            walk_forward=None,
            ml=None,
            workflow_options={},
        )
        with self.assertRaisesRegex(ResearchRunModelError, "auto_adjust must be exact bool"):
            RunConfig(auto_adjust=1, **base_args)  # type: ignore[arg-type]

        with self.assertRaisesRegex(ResearchRunModelError, "auto_adjust must be exact bool"):
            RunConfig(auto_adjust=0, **base_args)  # type: ignore[arg-type]

    def test_run_config_validates_optional_strings(self):
        base_args = dict(
            workflow="scan",
            canonical_symbols=("2330.TW",),
            period="1y",
            interval="1d",
            auto_adjust=True,
            force_refresh=False,
            backtest=None,
            parameter_sweep=None,
            walk_forward=None,
            ml=None,
            workflow_options={},
        )
        conf = RunConfig(universe=None, strategy=None, **base_args)
        self.assertIsNone(conf.universe)
        self.assertIsNone(conf.strategy)

        with self.assertRaisesRegex(ResearchRunModelError, "universe must be a clean non-blank string"):
            RunConfig(universe="  ", strategy=None, **base_args)

    def test_run_config_takes_defensive_mapping_snapshot(self):
        source_opts = {"nested": [1, 2]}
        config = RunConfig(
            workflow="scan",
            universe=None,
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
            workflow_options=source_opts,
        )
        source_opts["nested"].append(3)
        self.assertEqual(config.workflow_options["nested"], (1, 2))

    def test_run_config_deep_freezes_nested_sequences_and_mappings(self):
        source = {
            "a": [1, {"b": 2}],
        }
        config = RunConfig(
            workflow="scan",
            universe=None,
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
            workflow_options=source,
        )
        opts = config.workflow_options
        self.assertIsInstance(opts, MappingProxyType)
        self.assertIsInstance(opts["a"], tuple)
        self.assertIsInstance(opts["a"][1], MappingProxyType)
        with self.assertRaises(TypeError):
            opts["a"][1]["b"] = 99  # type: ignore[index]

    def test_run_config_rejects_invalid_mapping_keys_and_nonfinite_floats(self):
        base_args = dict(
            workflow="scan",
            universe=None,
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
        )
        with self.assertRaisesRegex(ResearchRunModelError, "Mapping key in workflow_options must be exact str"):
            RunConfig(workflow_options={123: "val"}, **base_args)  # type: ignore[dict-item]

        with self.assertRaisesRegex(ResearchRunModelError, "Mapping key in workflow_options must be clean non-blank string"):
            RunConfig(workflow_options={" key ": "val"}, **base_args)

        with self.assertRaisesRegex(ResearchRunModelError, "Non-finite float value"):
            RunConfig(workflow_options={"nan_val": float("nan")}, **base_args)

    def test_run_config_rejects_unsupported_runtime_values(self):
        base_args = dict(
            workflow="scan",
            universe=None,
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
        )
        with self.assertRaisesRegex(ResearchRunModelError, "Unsupported runtime value"):
            RunConfig(workflow_options={"path": Path("output/test.json")}, **base_args)

        with self.assertRaisesRegex(ResearchRunModelError, "Unsupported runtime value"):
            RunConfig(workflow_options={"dt": datetime.now()}, **base_args)

        with self.assertRaisesRegex(ResearchRunModelError, "Unsupported runtime value"):
            RunConfig(workflow_options={"set": {1, 2}}, **base_args)

        with self.assertRaisesRegex(ResearchRunModelError, "Unsupported runtime value"):
            RunConfig(workflow_options={"df": pd.DataFrame()}, **base_args)

    # DataSourceRecord Tests (5)

    def test_data_source_record_accepts_valid_live_source(self):
        record = DataSourceRecord(
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
        self.assertEqual(record.canonical_symbol, "2330.TW")
        self.assertEqual(record.source_kind, "live")
        self.assertEqual(record.cache_state, "not_applicable")

    def test_data_source_record_accepts_valid_fresh_and_stale_cache(self):
        rec_fresh = DataSourceRecord(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            provider="cache",
            period="1y",
            interval="1d",
            auto_adjust=True,
            source_kind="cache",
            cache_state="fresh",
            success=True,
            error=None,
        )
        self.assertEqual(rec_fresh.cache_state, "fresh")

        rec_stale = DataSourceRecord(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            provider="cache",
            period="1y",
            interval="1d",
            auto_adjust=True,
            source_kind="cache",
            cache_state="stale",
            success=True,
            error=None,
        )
        self.assertEqual(rec_stale.cache_state, "stale")

    def test_data_source_record_enforces_source_and_cache_state_consistency(self):
        base_args = dict(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            provider="yfinance",
            period="1y",
            interval="1d",
            auto_adjust=True,
            success=True,
            error=None,
        )
        with self.assertRaisesRegex(ResearchRunModelError, "cache_state must be 'not_applicable' when source_kind is 'live'"):
            DataSourceRecord(source_kind="live", cache_state="fresh", **base_args)

        with self.assertRaisesRegex(ResearchRunModelError, "cache_state must be 'fresh' or 'stale' when source_kind is 'cache'"):
            DataSourceRecord(source_kind="cache", cache_state="not_applicable", **base_args)

    def test_data_source_record_requires_exact_booleans_and_enum_values(self):
        base_args = dict(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            provider="yfinance",
            period="1y",
            interval="1d",
            source_kind="live",
            cache_state="not_applicable",
            success=True,
            error=None,
        )
        with self.assertRaisesRegex(ResearchRunModelError, "auto_adjust must be exact bool"):
            DataSourceRecord(auto_adjust=1, **base_args)  # type: ignore[arg-type]

        with self.assertRaisesRegex(ResearchRunModelError, "source_kind must be 'live' or 'cache'"):
            DataSourceRecord(auto_adjust=True, source_kind="network", cache_state="not_applicable", success=True, error=None, canonical_symbol="2330.TW", requested_symbol="2330", provider="yfinance", period="1y", interval="1d")  # type: ignore[arg-type]

    def test_data_source_record_enforces_success_error_consistency(self):
        base_args = dict(
            canonical_symbol="2330.TW",
            requested_symbol="2330",
            provider="yfinance",
            period="1y",
            interval="1d",
            auto_adjust=True,
            source_kind="live",
            cache_state="not_applicable",
        )
        with self.assertRaisesRegex(ResearchRunModelError, "error must be None when success is True"):
            DataSourceRecord(success=True, error="Network failed", **base_args)

        with self.assertRaisesRegex(ResearchRunModelError, "error must be a clean non-blank string"):
            DataSourceRecord(success=False, error=None, **base_args)

    # ArtifactReference Tests (4)

    def test_artifact_reference_accepts_supported_schema_versions(self):
        ref_int = ArtifactReference("daily_report_json", "output/daily.json", "application/json", 1)
        self.assertEqual(ref_int.schema_version, 1)

        ref_str = ArtifactReference("daily_report_json", "output/daily.json", "application/json", "v1")
        self.assertEqual(ref_str.schema_version, "v1")

        ref_none = ArtifactReference("markdown_report", "output/daily.md", "text/markdown", None)
        self.assertIsNone(ref_none.schema_version)

    def test_artifact_reference_validates_clean_strings_and_posix_path(self):
        with self.assertRaisesRegex(ResearchRunModelError, "path must use POSIX forward slashes"):
            ArtifactReference("daily_report_json", "output\\daily.json", "application/json", 1)

        with self.assertRaisesRegex(ResearchRunModelError, "artifact_type must be exact str"):
            ArtifactReference(123, "output/daily.json", "application/json", 1)  # type: ignore[arg-type]

    def test_artifact_reference_rejects_invalid_schema_versions(self):
        with self.assertRaisesRegex(ResearchRunModelError, "schema_version must be int, str, or None, got bool"):
            ArtifactReference("daily_report_json", "output/daily.json", "application/json", True)  # type: ignore[arg-type]

        with self.assertRaisesRegex(ResearchRunModelError, "schema_version integer must be positive"):
            ArtifactReference("daily_report_json", "output/daily.json", "application/json", 0)

    def test_artifact_reference_is_frozen(self):
        ref = _build_valid_artifact()
        with self.assertRaises(Exception):
            ref.path = "output/new.json"  # type: ignore[misc]

    # RunManifest Tests (12)

    def test_run_manifest_accepts_valid_success_manifest(self):
        manifest = _build_valid_manifest(status="success", success_count=1)
        self.assertEqual(manifest.schema_version, RUN_MANIFEST_SCHEMA_VERSION)
        self.assertEqual(manifest.status, "success")
        self.assertEqual(manifest.success_count, 1)

    def test_run_manifest_is_frozen(self):
        manifest = _build_valid_manifest()
        with self.assertRaises(Exception):
            manifest.status = "failure"  # type: ignore[misc]

    def test_run_manifest_validates_canonical_uuid_v4(self):
        base_manifest = _build_valid_manifest()

        # UUID v1 (rejected)
        with self.assertRaisesRegex(ResearchRunModelError, "must be UUID version 4"):
            RunManifest(
                schema_version=base_manifest.schema_version,
                run_id="f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
                created_at=base_manifest.created_at,
                tool_version=base_manifest.tool_version,
                status=base_manifest.status,
                config=base_manifest.config,
                data_sources=base_manifest.data_sources,
                success_count=base_manifest.success_count,
                failure_count=base_manifest.failure_count,
                partial_count=base_manifest.partial_count,
                artifacts=base_manifest.artifacts,
                errors=base_manifest.errors,
                limitations=base_manifest.limitations,
            )

        # Uppercase UUID (rejected)
        with self.assertRaisesRegex(ResearchRunModelError, "must be canonical lowercase rendering"):
            RunManifest(
                schema_version=base_manifest.schema_version,
                run_id="550E8400-E29B-41D4-A716-446655440000",
                created_at=base_manifest.created_at,
                tool_version=base_manifest.tool_version,
                status=base_manifest.status,
                config=base_manifest.config,
                data_sources=base_manifest.data_sources,
                success_count=base_manifest.success_count,
                failure_count=base_manifest.failure_count,
                partial_count=base_manifest.partial_count,
                artifacts=base_manifest.artifacts,
                errors=base_manifest.errors,
                limitations=base_manifest.limitations,
            )

    def test_run_manifest_validates_exact_utc_second_timestamp(self):
        base_manifest = _build_valid_manifest()

        # Invalid offset (rejected)
        with self.assertRaisesRegex(ResearchRunModelError, "must match exact UTC RFC 3339 timestamp format"):
            RunManifest(
                schema_version=base_manifest.schema_version,
                run_id=base_manifest.run_id,
                created_at="2026-07-27T20:00:00+08:00",
                tool_version=base_manifest.tool_version,
                status=base_manifest.status,
                config=base_manifest.config,
                data_sources=base_manifest.data_sources,
                success_count=base_manifest.success_count,
                failure_count=base_manifest.failure_count,
                partial_count=base_manifest.partial_count,
                artifacts=base_manifest.artifacts,
                errors=base_manifest.errors,
                limitations=base_manifest.limitations,
            )

        # Invalid calendar date (Feb 30) (rejected)
        with self.assertRaisesRegex(ResearchRunModelError, "contains invalid date/time"):
            RunManifest(
                schema_version=base_manifest.schema_version,
                run_id=base_manifest.run_id,
                created_at="2026-02-30T20:00:00Z",
                tool_version=base_manifest.tool_version,
                status=base_manifest.status,
                config=base_manifest.config,
                data_sources=base_manifest.data_sources,
                success_count=base_manifest.success_count,
                failure_count=base_manifest.failure_count,
                partial_count=base_manifest.partial_count,
                artifacts=base_manifest.artifacts,
                errors=base_manifest.errors,
                limitations=base_manifest.limitations,
            )

    def test_run_manifest_enforces_schema_version_and_status_values(self):
        base_manifest = _build_valid_manifest()

        with self.assertRaisesRegex(ResearchRunModelError, "schema_version must equal '1.0'"):
            RunManifest(
                schema_version="2.0",
                run_id=base_manifest.run_id,
                created_at=base_manifest.created_at,
                tool_version=base_manifest.tool_version,
                status=base_manifest.status,
                config=base_manifest.config,
                data_sources=base_manifest.data_sources,
                success_count=base_manifest.success_count,
                failure_count=base_manifest.failure_count,
                partial_count=base_manifest.partial_count,
                artifacts=base_manifest.artifacts,
                errors=base_manifest.errors,
                limitations=base_manifest.limitations,
            )

        with self.assertRaisesRegex(ResearchRunModelError, "status must be 'success', 'partial', or 'failure'"):
            RunManifest(
                schema_version=base_manifest.schema_version,
                run_id=base_manifest.run_id,
                created_at=base_manifest.created_at,
                tool_version=base_manifest.tool_version,
                status="running",  # type: ignore[arg-type]
                config=base_manifest.config,
                data_sources=base_manifest.data_sources,
                success_count=base_manifest.success_count,
                failure_count=base_manifest.failure_count,
                partial_count=base_manifest.partial_count,
                artifacts=base_manifest.artifacts,
                errors=base_manifest.errors,
                limitations=base_manifest.limitations,
            )

    def test_run_manifest_requires_run_config(self):
        base_manifest = _build_valid_manifest()
        with self.assertRaisesRegex(ResearchRunModelError, "config must be RunConfig instance"):
            RunManifest(
                schema_version=base_manifest.schema_version,
                run_id=base_manifest.run_id,
                created_at=base_manifest.created_at,
                tool_version=base_manifest.tool_version,
                status=base_manifest.status,
                config={"workflow": "scan"},  # type: ignore[arg-type]
                data_sources=base_manifest.data_sources,
                success_count=base_manifest.success_count,
                failure_count=base_manifest.failure_count,
                partial_count=base_manifest.partial_count,
                artifacts=base_manifest.artifacts,
                errors=base_manifest.errors,
                limitations=base_manifest.limitations,
            )

    def test_run_manifest_requires_exact_tuple_fields(self):
        base_manifest = _build_valid_manifest()
        with self.assertRaisesRegex(ResearchRunModelError, "data_sources must be exact tuple"):
            RunManifest(
                schema_version=base_manifest.schema_version,
                run_id=base_manifest.run_id,
                created_at=base_manifest.created_at,
                tool_version=base_manifest.tool_version,
                status=base_manifest.status,
                config=base_manifest.config,
                data_sources=list(base_manifest.data_sources),  # type: ignore[arg-type]
                success_count=base_manifest.success_count,
                failure_count=base_manifest.failure_count,
                partial_count=base_manifest.partial_count,
                artifacts=base_manifest.artifacts,
                errors=base_manifest.errors,
                limitations=base_manifest.limitations,
            )

    def test_run_manifest_validates_tuple_member_types(self):
        base_manifest = _build_valid_manifest()
        with self.assertRaisesRegex(ResearchRunModelError, "data_sources\\[0\\] must be DataSourceRecord instance"):
            RunManifest(
                schema_version=base_manifest.schema_version,
                run_id=base_manifest.run_id,
                created_at=base_manifest.created_at,
                tool_version=base_manifest.tool_version,
                status=base_manifest.status,
                config=base_manifest.config,
                data_sources=("invalid_record",),  # type: ignore[arg-type]
                success_count=base_manifest.success_count,
                failure_count=base_manifest.failure_count,
                partial_count=base_manifest.partial_count,
                artifacts=base_manifest.artifacts,
                errors=base_manifest.errors,
                limitations=base_manifest.limitations,
            )

    def test_run_manifest_requires_exact_nonnegative_counts(self):
        base_manifest = _build_valid_manifest()
        with self.assertRaisesRegex(ResearchRunModelError, "success_count must be exact int"):
            RunManifest(
                schema_version=base_manifest.schema_version,
                run_id=base_manifest.run_id,
                created_at=base_manifest.created_at,
                tool_version=base_manifest.tool_version,
                status=base_manifest.status,
                config=base_manifest.config,
                data_sources=base_manifest.data_sources,
                success_count=True,  # type: ignore[arg-type]
                failure_count=base_manifest.failure_count,
                partial_count=base_manifest.partial_count,
                artifacts=base_manifest.artifacts,
                errors=base_manifest.errors,
                limitations=base_manifest.limitations,
            )

        with self.assertRaisesRegex(ResearchRunModelError, "success_count must be non-negative"):
            RunManifest(
                schema_version=base_manifest.schema_version,
                run_id=base_manifest.run_id,
                created_at=base_manifest.created_at,
                tool_version=base_manifest.tool_version,
                status=base_manifest.status,
                config=base_manifest.config,
                data_sources=base_manifest.data_sources,
                success_count=-1,
                failure_count=base_manifest.failure_count,
                partial_count=base_manifest.partial_count,
                artifacts=base_manifest.artifacts,
                errors=base_manifest.errors,
                limitations=base_manifest.limitations,
            )

    def test_run_manifest_enforces_success_count_consistency(self):
        base_manifest = _build_valid_manifest(status="success")
        with self.assertRaisesRegex(ResearchRunModelError, "When status is 'success', failure_count and partial_count must be 0"):
            RunManifest(
                schema_version=base_manifest.schema_version,
                run_id=base_manifest.run_id,
                created_at=base_manifest.created_at,
                tool_version=base_manifest.tool_version,
                status="success",
                config=base_manifest.config,
                data_sources=base_manifest.data_sources,
                success_count=1,
                failure_count=1,
                partial_count=0,
                artifacts=base_manifest.artifacts,
                errors=base_manifest.errors,
                limitations=base_manifest.limitations,
            )

    def test_run_manifest_enforces_failure_count_and_error_consistency(self):
        base_manifest = _build_valid_manifest()

        # failure_count must be >= 1 and errors must contain at least 1 message
        with self.assertRaisesRegex(ResearchRunModelError, "When status is 'failure', failure_count must be at least 1"):
            RunManifest(
                schema_version=base_manifest.schema_version,
                run_id=base_manifest.run_id,
                created_at=base_manifest.created_at,
                tool_version=base_manifest.tool_version,
                status="failure",
                config=base_manifest.config,
                data_sources=base_manifest.data_sources,
                success_count=0,
                failure_count=0,
                partial_count=0,
                artifacts=base_manifest.artifacts,
                errors=("Download failed",),
                limitations=base_manifest.limitations,
            )

        with self.assertRaisesRegex(ResearchRunModelError, "When status is 'failure', errors must contain at least 1 message"):
            RunManifest(
                schema_version=base_manifest.schema_version,
                run_id=base_manifest.run_id,
                created_at=base_manifest.created_at,
                tool_version=base_manifest.tool_version,
                status="failure",
                config=base_manifest.config,
                data_sources=base_manifest.data_sources,
                success_count=0,
                failure_count=1,
                partial_count=0,
                artifacts=base_manifest.artifacts,
                errors=(),
                limitations=base_manifest.limitations,
            )

    def test_run_manifest_enforces_partial_count_consistency(self):
        base_manifest = _build_valid_manifest()

        # Valid partial manifest (partial_count >= 1)
        m1 = RunManifest(
            schema_version=base_manifest.schema_version,
            run_id=base_manifest.run_id,
            created_at=base_manifest.created_at,
            tool_version=base_manifest.tool_version,
            status="partial",
            config=base_manifest.config,
            data_sources=base_manifest.data_sources,
            success_count=0,
            failure_count=0,
            partial_count=1,
            artifacts=base_manifest.artifacts,
            errors=(),
            limitations=base_manifest.limitations,
        )
        self.assertEqual(m1.status, "partial")

        # Valid partial manifest (success_count >= 1 and failure_count >= 1)
        m2 = RunManifest(
            schema_version=base_manifest.schema_version,
            run_id=base_manifest.run_id,
            created_at=base_manifest.created_at,
            tool_version=base_manifest.tool_version,
            status="partial",
            config=base_manifest.config,
            data_sources=base_manifest.data_sources,
            success_count=1,
            failure_count=1,
            partial_count=0,
            artifacts=base_manifest.artifacts,
            errors=(),
            limitations=base_manifest.limitations,
        )
        self.assertEqual(m2.status, "partial")

        # Invalid partial manifest
        with self.assertRaisesRegex(ResearchRunModelError, "When status is 'partial', partial_count must be >= 1"):
            RunManifest(
                schema_version=base_manifest.schema_version,
                run_id=base_manifest.run_id,
                created_at=base_manifest.created_at,
                tool_version=base_manifest.tool_version,
                status="partial",
                config=base_manifest.config,
                data_sources=base_manifest.data_sources,
                success_count=1,
                failure_count=0,
                partial_count=0,
                artifacts=base_manifest.artifacts,
                errors=(),
                limitations=base_manifest.limitations,
            )

    # ResearchRunResult Tests (3)

    def test_research_run_result_accepts_matching_artifacts(self):
        manifest = _build_valid_manifest()
        result = ResearchRunResult(
            manifest=manifest,
            domain_result={"summary": "ok"},
            generated_artifacts=manifest.artifacts,
        )
        self.assertEqual(result.manifest, manifest)
        self.assertEqual(result.generated_artifacts, manifest.artifacts)

    def test_research_run_result_rejects_mismatched_or_invalid_artifacts(self):
        manifest = _build_valid_manifest()
        other_art = ArtifactReference("markdown_report", "output/report.md", "text/markdown", None)

        with self.assertRaisesRegex(ResearchRunModelError, "generated_artifacts must equal manifest.artifacts"):
            ResearchRunResult(
                manifest=manifest,
                domain_result=None,
                generated_artifacts=(other_art,),
            )

    def test_research_run_result_keeps_opaque_domain_result_reference(self):
        manifest = _build_valid_manifest()
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = ResearchRunResult(
            manifest=manifest,
            domain_result=df,
            generated_artifacts=manifest.artifacts,
        )
        self.assertIs(result.domain_result, df)

    # Public Exports Test (1)

    def test_research_run_package_exports_public_model_boundary(self):
        expected_exports = {
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
        }
        self.assertEqual(set(research_run.__all__), expected_exports)
        self.assertEqual(research_run.RUN_MANIFEST_SCHEMA_VERSION, "1.0")


if __name__ == "__main__":
    unittest.main()
