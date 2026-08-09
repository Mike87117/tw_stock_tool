from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, replace
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from tw_stock_tool.application.forward_paper_activation import (
    ForwardPaperActivationError,
    build_forward_paper_activation,
)
from tw_stock_tool.application.universe_qualification import (
    UniverseOOSArtifact,
    UniverseQualificationRequest,
    build_universe_oos_evidence,
    evaluate_universe_qualification,
    export_universe_oos_evidence_json,
    load_universe_oos_evidence_json,
)
from tw_stock_tool.forward_paper import (
    ForwardPaperActivation,
    ForwardPaperModelError,
    ForwardPaperSerializationError,
    deserialize_forward_paper_activation,
    export_forward_paper_activation_json,
    load_forward_paper_activation_json,
    serialize_forward_paper_activation,
)
from tw_stock_tool.qualification import TAIWAN_EQUITY_DAILY_V1
from tw_stock_tool.qualification.models import PromotionDecision, StrategyQualificationResult


ACTIVATION_ID = "623e4567-e89b-42d3-a456-426614174000"
GOOD_SYMBOLS = ("2303", "2317", "2330", "2454", "2881")


def _fake_backtest(data, strategy, params, *args):
    preferred = {"short_window": 2, "long_window": 4}
    value = 10.0 if dict(params) == preferred else 8.0
    return {
        "Total Return %": value,
        "Sharpe Ratio": value,
        "Trade Count": 1,
        "Max Drawdown %": 5.0,
    }


def _artifact(
    evaluation_id: str,
    *,
    qualification_created_at: str = "2025-04-01T00:00:00Z",
    benchmark_periods: int = 70,
    policy=TAIWAN_EQUITY_DAILY_V1,
    benchmark_final: float = 100.0,
) -> UniverseOOSArtifact:
    index = pd.date_range("2025-01-01", periods=70, freq="D")
    close = np.linspace(100.0, 110.0, len(index))
    frame = pd.DataFrame({"Open": close, "Close": close}, index=index)
    benchmark_index = pd.date_range("2025-01-01", periods=benchmark_periods, freq="D")
    benchmark_close = np.linspace(100.0, benchmark_final, len(benchmark_index))
    benchmark = pd.DataFrame(
        {
            "Open": benchmark_close,
            "Close": benchmark_close,
        },
        index=benchmark_index,
    )
    symbol_data = {symbol: frame for symbol in GOOD_SYMBOLS}
    request = UniverseQualificationRequest(
        evaluation_id=evaluation_id,
        created_at=qualification_created_at,
        strategy="ma_cross",
        symbol_data=symbol_data,
        benchmark_data=benchmark,
        train_days=10,
        test_days=10,
        step_days=10,
        parameter_options={"short_window": (2, 3), "long_window": (4, 5)},
        policy=policy,
    )
    with patch(
        "tw_stock_tool.application.universe_qualification.run_strategy_backtest",
        side_effect=_fake_backtest,
    ):
        return build_universe_oos_evidence(evaluate_universe_qualification(request))


def _forged_copy(value, **changes):
    forged = object.__new__(type(value))
    for item in fields(value):
        object.__setattr__(forged, item.name, changes.get(item.name, getattr(value, item.name)))
    return forged


def _forge_paper_ready(source: UniverseOOSArtifact) -> UniverseOOSArtifact:
    decision = object.__new__(PromotionDecision)
    object.__setattr__(decision, "state", "PAPER_READY")
    object.__setattr__(decision, "reason_codes", source.qualification.decision.reason_codes)
    qualification = object.__new__(StrategyQualificationResult)
    for item in fields(StrategyQualificationResult):
        value = decision if item.name == "decision" else getattr(source.qualification, item.name)
        object.__setattr__(qualification, item.name, value)
    forged = object.__new__(UniverseOOSArtifact)
    for item in fields(UniverseOOSArtifact):
        value = qualification if item.name == "qualification" else getattr(source, item.name)
        object.__setattr__(forged, item.name, value)
    return forged


def _forge_numeric_representation(source: UniverseOOSArtifact) -> UniverseOOSArtifact:
    metrics = _forged_copy(source.qualification.request.metrics, total_return_pct=10)
    request = _forged_copy(source.qualification.request, metrics=metrics)
    qualification = _forged_copy(source.qualification, request=request)
    return _forged_copy(source, qualification=qualification)


class ForwardPaperActivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ready = _artifact("523e4567-e89b-42d3-a456-426614174000")
        cls.changed = _artifact("523e4567-e89b-42d3-a456-426614174001")
        cls.early_qualification = _artifact(
            "523e4567-e89b-42d3-a456-426614174002",
            qualification_created_at="2025-01-01T00:00:00Z",
        )
        cls.late_benchmark = _artifact(
            "523e4567-e89b-42d3-a456-426614174003", benchmark_periods=80
        )
        cls.rejected = _artifact(
            "523e4567-e89b-42d3-a456-426614174004",
            policy=replace(TAIWAN_EQUITY_DAILY_V1, minimum_completed_trades=10_000),
        )
        cls.research_candidate = _artifact(
            "523e4567-e89b-42d3-a456-426614174005", benchmark_final=1_000.0
        )
        cls.activation = build_forward_paper_activation(
            cls.ready, activation_id=ACTIVATION_ID, created_at="2025-04-02T00:00:00Z"
        )

    def test_valid_real_paper_ready_artifact_builds_immutable_activation(self):
        self.assertIsInstance(self.activation, ForwardPaperActivation)
        with self.assertRaises(FrozenInstanceError):
            self.activation.strategy_id = "rsi"

    def test_builder_requires_actual_universe_artifact(self):
        with self.assertRaisesRegex(ForwardPaperActivationError, "actual UniverseOOSArtifact"):
            build_forward_paper_activation(
                object(), activation_id=ACTIVATION_ID, created_at="2025-04-02T00:00:00Z"
            )

    def test_rejected_and_research_candidate_cannot_activate(self):
        self.assertEqual(self.rejected.qualification.decision.state, "REJECTED")
        self.assertEqual(
            self.research_candidate.qualification.decision.state,
            "RESEARCH_CANDIDATE",
        )
        for source in (self.rejected, self.research_candidate):
            with self.subTest(state=source.qualification.decision.state):
                with self.assertRaisesRegex(ForwardPaperActivationError, "PAPER_READY"):
                    build_forward_paper_activation(
                        source,
                        activation_id=ACTIVATION_ID,
                        created_at="2025-04-02T00:00:00Z",
                    )

    def test_forged_paper_ready_state_fails_canonical_revalidation(self):
        forged = _forge_paper_ready(self.rejected)
        with self.assertRaisesRegex(ForwardPaperActivationError, "canonical validation"):
            build_forward_paper_activation(
                forged,
                activation_id=ACTIVATION_ID,
                created_at="2025-04-02T00:00:00Z",
            )

    def test_noncanonical_numeric_representation_drift_rejects(self):
        forged = _forge_numeric_representation(self.ready)
        input_json = export_universe_oos_evidence_json(forged)
        trusted = load_universe_oos_evidence_json(input_json)
        self.assertNotEqual(
            input_json,
            export_universe_oos_evidence_json(trusted),
        )
        with self.assertRaisesRegex(ForwardPaperActivationError, "canonical serialized form"):
            build_forward_paper_activation(
                forged, activation_id=ACTIVATION_ID, created_at="2025-04-02T00:00:00Z"
            )

    def test_cutoff_is_maximum_of_all_window_and_benchmark_ends(self):
        candidates = [
            window.test_end
            for symbol in self.ready.symbols
            for window in symbol.windows
        ]
        candidates.extend(
            descriptor.index_end
            for descriptor in self.ready.resolved_configuration.benchmark_descriptors
            if descriptor.index_end is not None
        )
        self.assertEqual(self.activation.qualification_cutoff, max(candidates))

    def test_later_benchmark_end_advances_cutoff(self):
        activation = build_forward_paper_activation(
            self.late_benchmark,
            activation_id=ACTIVATION_ID,
            created_at="2025-04-02T00:00:00Z",
        )
        benchmark_end = max(
            descriptor.index_end
            for descriptor in self.late_benchmark.resolved_configuration.benchmark_descriptors
            if descriptor.index_end is not None
        )
        window_end = max(
            window.test_end
            for symbol in self.late_benchmark.symbols
            for window in symbol.windows
        )
        self.assertGreater(benchmark_end, window_end)
        self.assertEqual(activation.qualification_cutoff, benchmark_end)

    def test_creation_timestamp_is_not_substituted_for_cutoff(self):
        self.assertNotEqual(self.activation.created_at, self.activation.qualification_cutoff)
        self.assertNotEqual(
            self.ready.qualification.request.created_at,
            self.activation.qualification_cutoff,
        )

    def test_activation_cannot_predate_qualification_creation(self):
        with self.assertRaisesRegex(ForwardPaperActivationError, "qualification creation"):
            build_forward_paper_activation(
                self.ready,
                activation_id=ACTIVATION_ID,
                created_at="2025-03-20T00:00:00Z",
            )

    def test_activation_cannot_predate_market_data_cutoff(self):
        with self.assertRaisesRegex(ForwardPaperActivationError, "qualification_cutoff"):
            build_forward_paper_activation(
                self.early_qualification,
                activation_id=ACTIVATION_ID,
                created_at="2025-03-01T00:00:00Z",
            )

    def test_exact_source_identities_are_copied(self):
        qualification = self.ready.qualification
        self.assertEqual(
            self.activation.qualification_evaluation_id, self.ready.evaluation_id
        )
        self.assertEqual(
            self.activation.strategy_id, qualification.request.strategy.strategy_id
        )
        self.assertEqual(self.activation.policy_id, qualification.request.policy.policy_id)
        self.assertEqual(
            self.activation.policy_version, qualification.request.policy.policy_version
        )
        self.assertEqual(self.activation.qualification_artifact_type, self.ready.artifact_type)
        self.assertEqual(self.activation.qualification_schema_version, self.ready.schema_version)

    def test_qualified_symbols_are_exact_sorted_successful_source_subset(self):
        expected = tuple(
            symbol.symbol
            for symbol in self.ready.symbols
            if symbol.evaluated and symbol.valid_windows > 0 and symbol.oos_observations > 0
        )
        self.assertEqual(self.activation.qualified_symbols, expected)
        self.assertEqual(expected, GOOD_SYMBOLS)

    def test_same_canonical_source_has_same_sha256(self):
        other = build_forward_paper_activation(
            self.ready,
            activation_id="623e4567-e89b-42d3-a456-426614174001",
            created_at="2025-04-03T00:00:00Z",
        )
        expected = hashlib.sha256(
            export_universe_oos_evidence_json(self.ready).encode("utf-8")
        ).hexdigest()
        self.assertEqual(self.activation.qualification_sha256, expected)
        self.assertEqual(other.qualification_sha256, expected)

    def test_changed_canonical_source_changes_sha256(self):
        changed = build_forward_paper_activation(
            self.changed,
            activation_id=ACTIVATION_ID,
            created_at="2025-04-02T00:00:00Z",
        )
        self.assertNotEqual(
            self.activation.qualification_sha256, changed.qualification_sha256
        )

    def test_invalid_uppercase_and_wrong_length_digest_reject(self):
        for digest in ("A" * 64, "a" * 63, "a" * 65):
            with self.subTest(digest=digest):
                with self.assertRaisesRegex(ForwardPaperModelError, "SHA-256"):
                    replace(self.activation, qualification_sha256=digest)

    def test_missing_and_unknown_fields_reject(self):
        payload = serialize_forward_paper_activation(self.activation)
        missing = dict(payload)
        missing.pop("policy_id")
        unknown = dict(payload, extra=True)
        for value in (missing, unknown):
            with self.subTest(keys=tuple(value)):
                with self.assertRaises(ForwardPaperSerializationError):
                    deserialize_forward_paper_activation(value)

    def test_duplicate_and_nonfinite_json_reject(self):
        text = export_forward_paper_activation_json(self.activation)
        duplicate = text.replace(
            '"schema_version": "1.0",',
            '"schema_version": "1.0",\n  "schema_version": "1.0",',
        )
        nonfinite = text.replace(
            f'"qualification_sha256": "{self.activation.qualification_sha256}"',
            '"qualification_sha256": NaN',
        )
        for value in (duplicate, nonfinite):
            with self.subTest(value=value[:30]):
                with self.assertRaises(ForwardPaperSerializationError):
                    load_forward_paper_activation_json(value)

    def test_exact_container_types_and_unknown_identities_reject(self):
        payload = serialize_forward_paper_activation(self.activation)
        variants = []
        wrong_symbols = dict(payload)
        wrong_symbols["qualified_symbols"] = tuple(wrong_symbols["qualified_symbols"])
        variants.append(wrong_symbols)
        wrong_schema = dict(payload)
        wrong_schema["schema_version"] = "1.1"
        variants.append(wrong_schema)
        wrong_type = dict(payload)
        wrong_type["artifact_type"] = "other"
        variants.append(wrong_type)
        for value in variants:
            with self.subTest(value=value):
                with self.assertRaises(ForwardPaperSerializationError):
                    deserialize_forward_paper_activation(value)

    def test_serialization_is_deterministic_and_round_trips(self):
        first = export_forward_paper_activation_json(self.activation)
        loaded = load_forward_paper_activation_json(first)
        self.assertEqual(loaded, self.activation)
        self.assertEqual(export_forward_paper_activation_json(loaded), first)
        self.assertEqual(json.loads(first), serialize_forward_paper_activation(loaded))

    def test_pure_domain_has_no_forbidden_imports(self):
        root = Path(__file__).parents[1] / "src" / "tw_stock_tool" / "forward_paper"
        forbidden = (
            "pandas",
            "requests",
            "tw_stock_tool.application",
            "tw_stock_tool.backtesting",
            "tw_stock_tool.data",
            "tw_stock_tool.paper_trading",
            "tw_stock_tool.broker",
        )
        for source in root.glob("*.py"):
            tree = ast.parse(source.read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            for module in imports:
                self.assertFalse(
                    module.startswith(forbidden), f"forbidden import {module} in {source}"
                )

    def test_phase_contains_no_order_or_fill_conversion(self):
        root = Path(__file__).parents[1] / "src" / "tw_stock_tool"
        sources = (
            root / "forward_paper" / "models.py",
            root / "forward_paper" / "serialization.py",
            root / "application" / "forward_paper_activation.py",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)
        self.assertNotIn("SimulatedOrder", combined)
        self.assertNotIn("SimulatedFill", combined)


if __name__ == "__main__":
    unittest.main()
