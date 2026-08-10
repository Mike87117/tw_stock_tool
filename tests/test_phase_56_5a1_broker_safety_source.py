from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta
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
    ForwardPaperPackageFinding,
    ForwardPaperPackageFindingCode,
    ForwardPaperPackageHealth,
)
from tw_stock_tool.recommendation.models import (
    CurrentSignalSnapshot,
    RecommendationEvidence,
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
            self.inspection, self.ledger
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

    def _state_inspection(self, state: ForwardEligibilityState):
        return replace(
            self.inspection,
            publication_index=replace(
                self.inspection.publication_index,
                eligibility_state=state,
            ),
            summary=replace(self.inspection.summary, eligibility_state=state),
        )

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
                self.inspection, self.ledger, self.recommendation
            )
            repeated = build_broker_safety_source_handoff(
                self.inspection, self.ledger, self.recommendation
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
            ("inspection", "ledger", "recommendation"),
        )

    def test_handoff_rejects_invalid_nonactive_legacy_missing_and_changed_sources(self):
        finding = ForwardPaperPackageFinding(
            ForwardPaperPackageFindingCode.TRUST_CHAIN_INVALID,
            None,
            None,
            "invalid trusted chain",
        )
        invalid = replace(
            self.inspection,
            health=ForwardPaperPackageHealth.INVALID,
            findings=(finding,),
            summary=None,
        )
        for value in (
            invalid,
            self._state_inspection(ForwardEligibilityState.PAUSED),
            self._state_inspection(ForwardEligibilityState.REVOKED),
        ):
            with self.subTest(inspection=value):
                with self.assertRaises(BrokerSafetySourceError):
                    build_broker_safety_source_handoff(
                        value, self.ledger, self.recommendation
                    )

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
        changed_time = (
            datetime.strptime(
                self.recommendation.generated_at, "%Y-%m-%dT%H:%M:%SZ"
            )
            + timedelta(seconds=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        cases = (
            legacy,
            replace(self.recommendation, recommendation_id=str(uuid4())),
            replace(self.recommendation, generated_at=changed_time),
        )
        for recommendation in cases:
            with self.subTest(recommendation=recommendation):
                with self.assertRaises(BrokerSafetySourceError):
                    build_broker_safety_source_handoff(
                        self.inspection, self.ledger, recommendation
                    )
        substituted = replace(self.ledger, ledger_id=str(uuid4()))
        with self.assertRaises(BrokerSafetySourceError):
            build_broker_safety_source_handoff(
                self.inspection, substituted, self.recommendation
            )

    def test_source_digests_are_deterministic_and_exact_type_sensitive(self):
        first = build_broker_safety_source_handoff(
            self.inspection, self.ledger, self.recommendation
        )
        second = build_broker_safety_source_handoff(
            self.inspection, self.ledger, self.recommendation
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
            self.inspection, self.ledger, self.recommendation
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
            "Workspace",
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
