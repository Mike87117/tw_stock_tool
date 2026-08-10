from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta
import hashlib
import inspect
import json
from itertools import permutations
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from tw_stock_tool.application.broker_safety_source import (
    BrokerSafetySourceError,
    build_broker_safety_source_handoff,
    build_forward_eligibility_progression,
)
from tw_stock_tool.application.forward_execution_evidence import (
    build_forward_execution_evidence,
)
from tw_stock_tool.application.forward_paper_execution import (
    run_forward_paper_execution_replay_with_trace,
)
from tw_stock_tool.application.forward_paper_inspection import (
    inspect_forward_paper_workspace_package,
)
from tw_stock_tool.broker_safety import (
    BrokerSafetySourceHandoff,
    BrokerSafetySourceModelError,
    BrokerSafetySourceSerializationError,
    ForwardEligibilityDecisionAnchor,
    ForwardEligibilityHeadResolutionError,
    ForwardEligibilityHighWaterMark,
    ForwardEligibilityHighWaterMarkError,
    ForwardEligibilityLineageKey,
    ForwardEligibilityProgression,
    ForwardEligibilityProgressionRelation as Relation,
    compare_forward_eligibility_progression,
    export_broker_safety_source_handoff_json,
    export_forward_eligibility_high_water_mark_json,
    export_forward_eligibility_progression_json,
    load_broker_safety_source_handoff_json,
    load_forward_eligibility_high_water_mark_json,
    load_forward_eligibility_progression_json,
    resolve_current_forward_eligibility_head,
    serialize_forward_eligibility_progression,
    validate_forward_eligibility_high_water_mark,
)
from tw_stock_tool.broker_safety.source_models import (
    PROGRESSION_ARTIFACT_TYPE,
    SOURCE_SCHEMA_VERSION,
    _canonical_sha256,
    progression_fingerprint,
)
from tw_stock_tool.forward_paper.eligibility_models import ForwardEligibilityState
from tw_stock_tool.forward_paper.inspection import (
    ForwardPaperPackageHealth,
)
from tw_stock_tool.forward_paper.publication import (
    PUBLICATION_INDEX_PATH,
    export_forward_paper_publication_index_json,
)
from tw_stock_tool.recommendation.models import (
    CurrentSignalSnapshot,
    RecommendationEvidence,
)
from tw_stock_tool.recommendation.serialization import (
    export_recommendation_evidence_json,
)


_PROGRESSION_FACTS = (
    "lineage_key",
    "run_id",
    "publication_id",
    "publication_index_sha256",
    "qualification_evaluation_id",
    "eligibility_id",
    "eligibility_state",
    "eligibility_sha256",
    "metrics_id",
    "metrics_sha256",
    "ledger_id",
    "ledger_sha256",
    "decision_count",
    "last_observed_at",
    "recommendation_anchors",
)


class BrokerSafetySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from test_phase_56_4e1_forward_paper_publication import (
            ForwardPaperPublicationTests,
        )

        ForwardPaperPublicationTests.setUpClass()
        cls.e1_type = ForwardPaperPublicationTests

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.e1 = self.e1_type(
            "test_genuine_package_writes_all_artifacts_index_last_and_manifest"
        )
        self.e1.setUp()
        self.published = self.e1._publish(self.root)
        self.inspection = inspect_forward_paper_workspace_package(
            self.root, self.published.run_id
        )
        self.ledger = self.e1.values["ledger"]
        self.recommendation = self.e1.recommendation
        self.progression = build_forward_eligibility_progression(
            self.root,
            self.published.run_id,
        )

    @staticmethod
    def _variant(
        source: ForwardEligibilityProgression,
        **changes,
    ) -> ForwardEligibilityProgression:
        facts = {name: getattr(source, name) for name in _PROGRESSION_FACTS}
        facts.update(changes)
        return ForwardEligibilityProgression(
            schema_version=SOURCE_SCHEMA_VERSION,
            artifact_type=PROGRESSION_ARTIFACT_TYPE,
            progression_fingerprint=progression_fingerprint(**facts),
            **facts,
        )

    def _extension(
        self,
        source: ForwardEligibilityProgression,
        *,
        count: int = 1,
        state: ForwardEligibilityState = ForwardEligibilityState.ACTIVE,
        salt: str = "a",
    ) -> ForwardEligibilityProgression:
        previous = (
            datetime(2025, 1, 1)
            if source.last_observed_at is None
            else datetime.strptime(source.last_observed_at, "%Y-%m-%dT%H:%M:%SZ")
        )
        appended = tuple(
            ForwardEligibilityDecisionAnchor(
                recommendation_id=str(uuid4()),
                recommendation_sha256=chr(ord(salt) + index) * 64,
                observed_at=(previous + timedelta(seconds=index + 1)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                symbol=f"ZZ{index}",
                decision_sha256=(salt if index == 0 else chr(ord(salt) + index)) * 64,
            )
            for index in range(count)
        )
        anchors = source.recommendation_anchors + appended
        return self._variant(
            source,
            run_id=str(uuid4()),
            publication_id=str(uuid4()),
            publication_index_sha256="1" * 64,
            eligibility_id=str(uuid4()),
            eligibility_state=state,
            eligibility_sha256="2" * 64,
            metrics_id=str(uuid4()),
            metrics_sha256="3" * 64,
            ledger_id=str(uuid4()),
            ledger_sha256="4" * 64,
            decision_count=len(anchors),
            last_observed_at=anchors[-1].observed_at,
            recommendation_anchors=anchors,
        )


    def _publish_nonactive(
        self,
        root: Path,
        state: ForwardEligibilityState,
    ):
        d2 = self.e1.d3.d2
        fixture = d2.fixture
        recommendation = d2._evidence_at(0, signal="BUY")
        ledger = fixture._ledger(recommendation)
        quantity = 2 if state is ForwardEligibilityState.PAUSED else 3
        bundle = run_forward_paper_execution_replay_with_trace(
            fixture.activation,
            fixture.source,
            ledger,
            {recommendation.recommendation_id: recommendation},
            {
                "2303": fixture._frame(
                    opens=[100.0, 100.0],
                    closes=[100.0, 1.0],
                )
            },
            initial_cash=1_000.0,
            quantity_per_trade=quantity,
        )
        reference = self.e1.values["execution_evidence"]
        execution = build_forward_execution_evidence(
            fixture.activation,
            fixture.source,
            ledger,
            {recommendation.recommendation_id: recommendation},
            bundle.portfolio_result,
            evidence_id=reference.evidence_id,
            created_at=reference.created_at,
        )
        metrics = d2._build((recommendation, ledger, bundle, execution))
        eligibility = self.e1.d3._build(
            activation=fixture.activation,
            qualification_artifact=fixture.source,
            ledger=ledger,
            recommendation_evidence_by_id={
                recommendation.recommendation_id: recommendation
            },
            portfolio_result=bundle.portfolio_result,
            execution_evidence=execution,
            portfolio_trace=bundle.portfolio_trace,
            metrics_evidence=metrics,
            expected_portfolio_trace_sha256=bundle.portfolio_trace_sha256,
        )
        self.assertIs(eligibility.state, state)
        published = self.e1._publish(
            root,
            activation=fixture.activation,
            qualification_artifact=fixture.source,
            ledger=ledger,
            recommendation_evidence_by_id={
                recommendation.recommendation_id: recommendation
            },
            portfolio_result=bundle.portfolio_result,
            execution_evidence=execution,
            portfolio_trace=bundle.portfolio_trace,
            metrics_evidence=metrics,
            eligibility_evidence=eligibility,
            expected_portfolio_trace_sha256=bundle.portfolio_trace_sha256,
        )
        return published, recommendation
    def test_genuine_active_package_builds_canonical_handoff_without_side_effects(self):
        targets = (
            "tw_stock_tool.artifacts.workspace.write_managed_text",
            "tw_stock_tool.artifacts.workspace.write_manifest",
            "tw_stock_tool.data.data_loader.download_tw_stock",
            "tw_stock_tool.paper_trading.coordinator.run_chronological_multi_symbol_simulated_paper_trading",
        )
        patches = [patch(target, side_effect=AssertionError(target)) for target in targets]
        mocks = [item.start() for item in patches]
        try:
            handoff = build_broker_safety_source_handoff(
                self.root,
                self.published.run_id,
                self.recommendation.recommendation_id,
            )
            repeated = build_broker_safety_source_handoff(
                self.root,
                self.published.run_id,
                self.recommendation.recommendation_id,
            )
        finally:
            for item in reversed(patches):
                item.stop()
        self.assertEqual(handoff, repeated)
        self.assertEqual(
            export_broker_safety_source_handoff_json(handoff),
            export_broker_safety_source_handoff_json(repeated),
        )
        self.assertEqual(handoff.workspace_run_id, self.published.run_id)
        self.assertEqual(handoff.progression_fingerprint, self.progression.progression_fingerprint)
        self.assertEqual(handoff.eligibility_state, ForwardEligibilityState.ACTIVE)
        self.assertIn(handoff.decision_symbol, handoff.qualified_symbols)
        self.assertTrue(all(mock.call_count == 0 for mock in mocks))
        self.assertEqual(
            tuple(inspect.signature(build_broker_safety_source_handoff).parameters),
            ("workspace_root", "run_id", "recommendation_id"),
        )

    def test_fresh_e2_path_rejects_nonactive_and_state_substitution(self):
        for state in (
            ForwardEligibilityState.PAUSED,
            ForwardEligibilityState.REVOKED,
        ):
            with self.subTest(state=state):
                root = self.root / state.value.lower()
                published, recommendation = self._publish_nonactive(root, state)
                inspection = inspect_forward_paper_workspace_package(
                    root,
                    published.run_id,
                )
                self.assertIs(inspection.health, ForwardPaperPackageHealth.VALID)
                self.assertIs(inspection.summary.eligibility_state, state)
                forged = replace(
                    inspection,
                    publication_index=replace(
                        inspection.publication_index,
                        eligibility_state=ForwardEligibilityState.ACTIVE,
                    ),
                    summary=replace(
                        inspection.summary,
                        eligibility_state=ForwardEligibilityState.ACTIVE,
                    ),
                )
                with self.assertRaises(BrokerSafetySourceError):
                    build_broker_safety_source_handoff(
                        root,
                        published.run_id,
                        recommendation.recommendation_id,
                    )
                with self.assertRaises(BrokerSafetySourceError):
                    build_broker_safety_source_handoff(
                        forged,
                        self.ledger,
                        self.recommendation,
                    )

                substituted_anchors = tuple(
                    replace(anchor, sha256="f" * 64)
                    if anchor.role == "eligibility_evidence"
                    else anchor
                    for anchor in published.publication_index.artifact_anchors
                )
                substituted_index = replace(
                    published.publication_index,
                    artifact_anchors=substituted_anchors,
                    eligibility_state=ForwardEligibilityState.ACTIVE,
                    eligibility_sha256="f" * 64,
                )
                index_path = (
                    published.run_directory.path / PUBLICATION_INDEX_PATH
                )
                index_path.write_bytes(
                    export_forward_paper_publication_index_json(
                        substituted_index
                    ).encode("utf-8")
                )
                with self.assertRaises(BrokerSafetySourceError):
                    build_broker_safety_source_handoff(
                        root,
                        published.run_id,
                        recommendation.recommendation_id,
                    )

    def test_authoritative_path_rejects_missing_legacy_and_changed_sources(self):
        for recommendation_id in (str(uuid4()), self.recommendation):
            with self.subTest(recommendation_id=recommendation_id):
                with self.assertRaises(BrokerSafetySourceError):
                    build_broker_safety_source_handoff(
                        self.root,
                        self.published.run_id,
                        recommendation_id,
                    )

        legacy_root = self.root / "legacy"
        legacy_published = self.e1._publish(legacy_root)
        snapshot = self.recommendation.signal_snapshot
        legacy = RecommendationEvidence(
            schema_version="1.0",
            artifact_type=self.recommendation.artifact_type,
            recommendation_id=self.recommendation.recommendation_id,
            generated_at=self.recommendation.generated_at,
            source_qualification_evaluation_id=(
                self.recommendation.source_qualification_evaluation_id
            ),
            promotion_state=self.recommendation.promotion_state,
            strategy_id=self.recommendation.strategy_id,
            strategy_parameters=self.recommendation.strategy_parameters,
            qualification_finding_codes=(
                self.recommendation.qualification_finding_codes
            ),
            signal_snapshot=CurrentSignalSnapshot(
                symbol=snapshot.symbol,
                observed_at=snapshot.observed_at,
                signal=snapshot.signal,
                score=0.0,
                latest_close=snapshot.latest_close,
            ),
            action=self.recommendation.action,
            qualification=self.recommendation.qualification,
        )
        legacy_text = export_recommendation_evidence_json(legacy)
        anchor = legacy_published.publication_index.recommendation_anchors[0]
        (legacy_published.run_directory.path / anchor.path).write_bytes(
            legacy_text.encode("utf-8")
        )
        legacy_anchor = replace(
            anchor,
            recommendation_sha256=hashlib.sha256(
                legacy_text.encode("utf-8")
            ).hexdigest(),
        )
        legacy_index = replace(
            legacy_published.publication_index,
            recommendation_anchors=(legacy_anchor,),
        )
        (
            legacy_published.run_directory.path / PUBLICATION_INDEX_PATH
        ).write_bytes(
            export_forward_paper_publication_index_json(legacy_index).encode(
                "utf-8"
            )
        )
        with self.assertRaises(BrokerSafetySourceError):
            build_broker_safety_source_handoff(
                legacy_root,
                legacy_published.run_id,
                legacy.recommendation_id,
            )

        ledger_anchor = next(
            item
            for item in self.published.publication_index.artifact_anchors
            if item.role == "decision_ledger"
        )
        ledger_path = self.published.run_directory.path / ledger_anchor.path
        ledger_path.write_bytes(ledger_path.read_bytes() + b" ")
        with self.assertRaises(BrokerSafetySourceError):
            build_broker_safety_source_handoff(
                self.root,
                self.published.run_id,
                self.recommendation.recommendation_id,
            )
    def test_source_digests_are_deterministic_and_exact_type_sensitive(self):
        first = build_broker_safety_source_handoff(
            self.root,
            self.published.run_id,
            self.recommendation.recommendation_id,
        )
        second = build_broker_safety_source_handoff(
            self.root,
            self.published.run_id,
            self.recommendation.recommendation_id,
        )
        self.assertEqual(
            first.qualified_symbols_sha256, second.qualified_symbols_sha256
        )
        self.assertEqual(
            first.selected_parameters_sha256,
            second.selected_parameters_sha256,
        )
        self.assertNotEqual(
            _canonical_sha256({"selected_parameters": {"window": 1}}),
            _canonical_sha256({"selected_parameters": {"window": True}}),
        )
        with self.assertRaises(BrokerSafetySourceModelError):
            replace(first, qualified_symbols=tuple(reversed(first.qualified_symbols)))

    def test_strict_serialization_round_trips_all_boundary_models(self):
        handoff = build_broker_safety_source_handoff(
            self.root,
            self.published.run_id,
            self.recommendation.recommendation_id,
        )
        mark = ForwardEligibilityHighWaterMark.from_progression(self.progression)
        pairs = (
            (
                self.progression,
                export_forward_eligibility_progression_json,
                load_forward_eligibility_progression_json,
            ),
            (
                handoff,
                export_broker_safety_source_handoff_json,
                load_broker_safety_source_handoff_json,
            ),
            (
                mark,
                export_forward_eligibility_high_water_mark_json,
                load_forward_eligibility_high_water_mark_json,
            ),
        )
        for value, exporter, loader in pairs:
            with self.subTest(value=type(value).__name__):
                text = exporter(value)
                loaded = loader(text)
                self.assertEqual(loaded, value)
                self.assertEqual(exporter(loaded), text)

    def test_progression_loader_rejects_noncanonical_structures_and_values(self):
        payload = serialize_forward_eligibility_progression(self.progression)
        cases = []
        for key in ("run_id", "progression_fingerprint"):
            missing = dict(payload)
            missing.pop(key)
            cases.append(missing)
        unknown = dict(payload)
        unknown["token"] = "secret"
        cases.append(unknown)
        wrong_schema = dict(payload)
        wrong_schema["schema_version"] = "2.0"
        cases.append(wrong_schema)
        bool_count = dict(payload)
        bool_count["decision_count"] = True
        cases.append(bool_count)
        unknown_state = dict(payload)
        unknown_state["eligibility_state"] = "UNKNOWN"
        cases.append(unknown_state)
        duplicate_anchor = dict(payload)
        duplicate_anchor["decision_count"] = len(payload["recommendation_anchors"]) + 1
        duplicate_anchor["recommendation_anchors"] = [
            *payload["recommendation_anchors"],
            payload["recommendation_anchors"][0],
        ]
        cases.append(duplicate_anchor)
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(BrokerSafetySourceSerializationError):
                    load_forward_eligibility_progression_json(json.dumps(case))
        text = export_forward_eligibility_progression_json(self.progression)
        duplicate = text.replace(
            '"schema_version":',
            '"schema_version": "1.0", "schema_version":',
            1,
        )
        with self.assertRaises(BrokerSafetySourceSerializationError):
            load_forward_eligibility_progression_json(duplicate)
        with self.assertRaises(BrokerSafetySourceSerializationError):
            load_forward_eligibility_progression_json(
                text.replace(f'"decision_count": {self.progression.decision_count}', '"decision_count": NaN')
            )

    def test_progression_relations_are_append_only_and_directional(self):
        one = self._extension(self.progression)
        many = self._extension(self.progression, count=2)
        self.assertIs(
            compare_forward_eligibility_progression(self.progression, self.progression),
            Relation.SAME,
        )
        self.assertIs(
            compare_forward_eligibility_progression(self.progression, one),
            Relation.STRICT_EXTENSION,
        )
        self.assertIs(
            compare_forward_eligibility_progression(self.progression, many),
            Relation.STRICT_EXTENSION,
        )
        self.assertIs(
            compare_forward_eligibility_progression(one, self.progression),
            Relation.ROLLBACK,
        )

    def test_rewritten_reordered_or_reused_decisions_fail_closed(self):
        anchors = self.progression.recommendation_anchors
        rewritten = replace(anchors[0], decision_sha256="f" * 64)
        changed_sha = replace(anchors[0], recommendation_sha256="e" * 64)
        for candidate in (
            self._variant(self.progression, recommendation_anchors=(rewritten,)),
            self._variant(self.progression, recommendation_anchors=(changed_sha,)),
        ):
            with self.subTest(candidate=candidate):
                self.assertIs(
                    compare_forward_eligibility_progression(
                        self.progression, candidate
                    ),
                    Relation.CONFLICT,
                )
        many = self._extension(self.progression, count=2)
        with self.assertRaises(BrokerSafetySourceModelError):
            self._variant(
                many,
                recommendation_anchors=tuple(reversed(many.recommendation_anchors)),
            )

    def test_equal_progression_conflicts_and_random_id_or_state_cannot_win(self):
        conflict = self._variant(
            self.progression,
            run_id=str(uuid4()),
            publication_id=str(uuid4()),
            eligibility_state=ForwardEligibilityState.PAUSED,
        )
        self.assertIs(
            compare_forward_eligibility_progression(self.progression, conflict),
            Relation.CONFLICT,
        )
        with self.assertRaises(ForwardEligibilityHeadResolutionError):
            resolve_current_forward_eligibility_head(
                (self.progression, conflict),
                lineage_key=self.progression.lineage_key,
            )

    def test_different_activation_is_a_different_lineage(self):
        other_key = replace(
            self.progression.lineage_key,
            activation_id=str(uuid4()),
        )
        other = self._variant(self.progression, lineage_key=other_key)
        self.assertIs(
            compare_forward_eligibility_progression(self.progression, other),
            Relation.DIFFERENT_LINEAGE,
        )
        with self.assertRaises(ForwardEligibilityHeadResolutionError):
            resolve_current_forward_eligibility_head(
                (self.progression, other),
                lineage_key=self.progression.lineage_key,
            )

    def test_unique_head_is_order_independent_and_returns_nonactive_head(self):
        active = self._extension(self.progression)
        paused = self._extension(
            active,
            state=ForwardEligibilityState.PAUSED,
            salt="b",
        )
        for ordering in permutations((self.progression, active, paused)):
            self.assertEqual(
                resolve_current_forward_eligibility_head(
                    ordering,
                    lineage_key=self.progression.lineage_key,
                ),
                paused,
            )
        self.assertIs(paused.eligibility_state, ForwardEligibilityState.PAUSED)

    def test_newer_paused_or_revoked_prevents_old_active_from_winning(self):
        for state in (
            ForwardEligibilityState.PAUSED,
            ForwardEligibilityState.REVOKED,
        ):
            newer = self._extension(self.progression, state=state)
            with self.subTest(state=state):
                head = resolve_current_forward_eligibility_head(
                    (self.progression, newer),
                    lineage_key=self.progression.lineage_key,
                )
                self.assertEqual(head, newer)
                self.assertIsNot(head, self.progression)

    def test_incomparable_forks_fail_current_head_resolution(self):
        left = self._extension(self.progression, salt="a")
        right = self._extension(self.progression, salt="b")
        self.assertIs(
            compare_forward_eligibility_progression(left, right),
            Relation.INCOMPARABLE,
        )
        for ordering in ((left, right), (right, left)):
            with self.assertRaises(ForwardEligibilityHeadResolutionError):
                resolve_current_forward_eligibility_head(
                    ordering,
                    lineage_key=self.progression.lineage_key,
                )

    def test_high_water_mark_validates_same_advances_and_rejects_rollback_or_fork(self):
        mark = ForwardEligibilityHighWaterMark.from_progression(self.progression)
        self.assertIs(
            validate_forward_eligibility_high_water_mark(self.progression, mark),
            mark,
        )
        advanced_head = self._extension(self.progression)
        advanced = validate_forward_eligibility_high_water_mark(
            advanced_head, mark
        )
        self.assertEqual(advanced.to_progression(), advanced_head)
        self.assertEqual(mark.to_progression(), self.progression)
        with self.assertRaises(ForwardEligibilityHighWaterMarkError):
            validate_forward_eligibility_high_water_mark(self.progression, advanced)
        fork = self._extension(self.progression, salt="b")
        with self.assertRaises(ForwardEligibilityHighWaterMarkError):
            validate_forward_eligibility_high_water_mark(fork, advanced)
        with self.assertRaises(FrozenInstanceError):
            mark.accepted_decision_count = 0

    def test_nonactive_high_water_advance_permanently_blocks_old_active(self):
        initial = ForwardEligibilityHighWaterMark.from_progression(self.progression)
        for state in (
            ForwardEligibilityState.PAUSED,
            ForwardEligibilityState.REVOKED,
        ):
            head = self._extension(self.progression, state=state)
            advanced = validate_forward_eligibility_high_water_mark(head, initial)
            self.assertIs(advanced.accepted_state, state)
            with self.assertRaises(ForwardEligibilityHighWaterMarkError):
                validate_forward_eligibility_high_water_mark(
                    self.progression, advanced
                )

    def test_domain_scope_has_no_broker_io_runtime_or_secret_fields(self):
        source_files = (
            "src/tw_stock_tool/broker_safety/source_models.py",
            "src/tw_stock_tool/broker_safety/source_serialization.py",
            "src/tw_stock_tool/broker_safety/lineage.py",
            "src/tw_stock_tool/application/broker_safety_source.py",
        )
        forbidden_imports = (
            "import pandas",
            "import requests",
            "import yfinance",
            "paper_trading",
            "write_managed_text",
            "write_manifest",
        )
        for path in source_files:
            text = Path(path).read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertFalse(any(value in text for value in forbidden_imports))
        forbidden_fields = {"credentials", "credential", "api_key", "token", "secret"}
        for model in (
            BrokerSafetySourceHandoff,
            ForwardEligibilityProgression,
            ForwardEligibilityHighWaterMark,
            ForwardEligibilityLineageKey,
        ):
            self.assertTrue(
                forbidden_fields.isdisjoint(item.name for item in fields(model))
            )


if __name__ == "__main__":
    unittest.main()
