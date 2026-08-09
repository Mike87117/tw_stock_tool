from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest

from test_phase_56_4b_forward_decision_ledger import (
    ACTIVATION_ID,
    LEDGER_ID,
    RECOMMENDATION_IDS,
    _cutoff,
    _evidence,
    _shift,
    _source,
)
from tw_stock_tool.application.forward_decision_ledger import create_forward_decision_ledger, append_forward_decision
from tw_stock_tool.application.forward_execution_evidence import (
    ForwardExecutionEvidenceError,
    build_forward_execution_evidence,
)
from tw_stock_tool.application.forward_paper_activation import build_forward_paper_activation
from tw_stock_tool.application.forward_paper_execution import run_forward_paper_execution_replay
from tw_stock_tool.forward_paper.execution_models import ForwardExecutionOutcome
from tw_stock_tool.forward_paper.execution_serialization import (
    ForwardExecutionEvidenceSerializationError,
    export_forward_execution_evidence_json,
    load_forward_execution_evidence_json,
)


class ForwardExecutionEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = _source()
        cls.activation = build_forward_paper_activation(
            cls.source, activation_id=ACTIVATION_ID, created_at="2025-04-02T00:00:00Z"
        )
        cls.empty = create_forward_decision_ledger(
            cls.activation, cls.source, ledger_id=LEDGER_ID, created_at="2025-04-02T00:00:00Z"
        )

    def _evidence_at(self, index: int, *, signal: str = "BUY"):
        return _evidence(
            self.source,
            recommendation_id=RECOMMENDATION_IDS[index],
            symbol="2303",
            observed_at=_shift(_cutoff(self.source), 1),
            signal=signal,
        )

    def _ledger(self, *evidence):
        ledger = self.empty
        for item in evidence:
            ledger = append_forward_decision(ledger, self.activation, self.source, item)
        return ledger

    def _result(self, evidence, ledger=None, **kwargs):
        from test_phase_56_4c1_forward_paper_execution import ForwardPaperExecutionReplayTests

        fixture = ForwardPaperExecutionReplayTests("test_valid_bundle_executes_through_existing_facade")
        fixture.setUpClass()
        return fixture._run(ledger or self._ledger(evidence), (evidence,), **kwargs)

    def _build(self, evidence, result, ledger=None):
        ledger = ledger or self._ledger(evidence)
        return build_forward_execution_evidence(
            self.activation,
            self.source,
            ledger,
            {evidence.recommendation_id: evidence},
            result,
            evidence_id="823e4567-e89b-42d3-a456-426614174000",
            created_at="2025-04-02T00:00:00Z",
        )

    def test_filled_result_builds_exact_cost_and_audit_evidence(self):
        evidence = self._evidence_at(0)
        artifact = self._build(evidence, self._result(evidence))
        decision = artifact.decisions[0]
        self.assertEqual(decision.outcome, ForwardExecutionOutcome.FILLED)
        self.assertEqual(decision.order_id, "2303-BUY-0")
        self.assertEqual(decision.fill_price, 101.0)
        self.assertEqual(decision.audit_record_ids, ("audit-000001", "audit-000002", "audit-000003"))

    def test_pending_result_maps_reference_price(self):
        evidence = self._evidence_at(1)
        from test_phase_56_4c1_forward_paper_execution import ForwardPaperExecutionReplayTests
        fixture = ForwardPaperExecutionReplayTests("test_valid_bundle_executes_through_existing_facade")
        fixture.setUpClass()
        ledger = self._ledger(evidence)
        result = fixture._run(ledger, (evidence,), {"2303": fixture._frame(offsets=(1,))})
        decision = self._build(evidence, result, ledger).decisions[0]
        self.assertEqual(decision.outcome, ForwardExecutionOutcome.PENDING_NEXT_BAR_OPEN)
        self.assertEqual(decision.pending_reference_price, 100.0)

    def test_rejected_result_copies_exact_reasons(self):
        evidence = self._evidence_at(2)
        artifact = self._build(evidence, self._result(evidence, max_order_notional=0.01))
        self.assertEqual(artifact.decisions[0].outcome, ForwardExecutionOutcome.REJECTED)
        self.assertEqual(artifact.decisions[0].risk_rejection_reasons, ("order_notional exceeds max_order_notional",))

    def test_rejection_without_risk_evaluation_rejects(self):
        evidence = self._evidence_at(21)
        result = self._result(evidence, max_order_notional=0.01)
        terminal = replace(result.audit_log[-1], sequence=2, record_id="audit-000002")
        forged = replace(
            result,
            audit_log=(result.audit_log[0], terminal),
            audit_record_count=2,
        )
        with self.assertRaises(ForwardExecutionEvidenceError):
            self._build(evidence, forged)

    def test_invalid_open_result_maps_skip(self):
        evidence = self._evidence_at(3)
        from test_phase_56_4c1_forward_paper_execution import ForwardPaperExecutionReplayTests
        fixture = ForwardPaperExecutionReplayTests("test_valid_bundle_executes_through_existing_facade")
        fixture.setUpClass()
        ledger = self._ledger(evidence)
        result = fixture._run(ledger, (evidence,), {"2303": fixture._frame(offsets=(1, 2), opens=[100.0, float("nan")])})
        decision = self._build(evidence, result, ledger).decisions[0]
        self.assertEqual(decision.outcome, ForwardExecutionOutcome.FILL_SKIPPED_INVALID_OPEN)
        self.assertIsNone(decision.fill_price)

    def test_genuine_portfolio_validation_failure_maps_failed_fill(self):
        evidence = self._evidence_at(20)
        from test_phase_56_4c1_forward_paper_execution import ForwardPaperExecutionReplayTests
        fixture = ForwardPaperExecutionReplayTests("test_valid_bundle_executes_through_existing_facade")
        fixture.setUpClass()
        ledger = self._ledger(evidence)
        result = run_forward_paper_execution_replay(
            self.activation,
            self.source,
            ledger,
            {evidence.recommendation_id: evidence},
            {"2303": fixture._frame(offsets=(1, 2))},
            initial_cash=1.0,
            quantity_per_trade=1,
        )
        decision = self._build(evidence, result, ledger).decisions[0]
        self.assertEqual(
            decision.outcome,
            ForwardExecutionOutcome.FILL_FAILED_PORTFOLIO_VALIDATION,
        )
        self.assertIsNone(decision.fill_price)
        self.assertEqual(decision.fee, result.audit_log[-1].fee)

    def test_actionable_without_candidate_is_explicit(self):
        evidence = self._evidence_at(4, signal="SELL")
        result = self._result(evidence)
        decision = self._build(evidence, result).decisions[0]
        self.assertEqual(decision.outcome, ForwardExecutionOutcome.NO_CANDIDATE)

    def test_non_action_is_empty_lifecycle(self):
        evidence = self._evidence_at(5, signal="HOLD")
        result = self._result(evidence)
        decision = self._build(evidence, result).decisions[0]
        self.assertEqual(decision.outcome, ForwardExecutionOutcome.NON_ACTION)
        self.assertEqual(decision.audit_record_ids, ())

    def test_portfolio_result_sha_uses_exact_canonical_json(self):
        evidence = self._evidence_at(6)
        result = self._result(evidence)
        artifact = self._build(evidence, result)
        from tw_stock_tool.paper_trading.portfolio_serialization import export_simulated_portfolio_trading_result_json
        expected = hashlib.sha256(export_simulated_portfolio_trading_result_json(result).encode()).hexdigest()
        self.assertEqual(artifact.portfolio_result_sha256, expected)

    def test_same_input_serialization_is_deterministic(self):
        evidence = self._evidence_at(7)
        result = self._result(evidence)
        first = export_forward_execution_evidence_json(self._build(evidence, result))
        second = export_forward_execution_evidence_json(self._build(evidence, result))
        self.assertEqual(first, second)
        self.assertEqual(load_forward_execution_evidence_json(first), load_forward_execution_evidence_json(second))

    def test_result_list_instead_of_tuple_rejects_before_correlation(self):
        evidence = self._evidence_at(8)
        result = self._result(evidence)
        with self.assertRaises(ForwardExecutionEvidenceError):
            self._build(evidence, replace(result, orders=list(result.orders)))

    def test_wrong_order_metadata_rejects(self):
        evidence = self._evidence_at(9)
        result = self._result(evidence)
        order = replace(result.orders[0], metadata={**result.orders[0].metadata, "ledger_id": "bad"})
        with self.assertRaises(ForwardExecutionEvidenceError):
            self._build(evidence, replace(result, orders=(order,)))

    def test_wrong_strategy_rejects(self):
        evidence = self._evidence_at(10)
        result = self._result(evidence)
        order = replace(result.orders[0], strategy="foreign")
        with self.assertRaises(ForwardExecutionEvidenceError):
            self._build(evidence, replace(result, orders=(order,)))

    def test_order_signal_time_not_in_ledger_rejects(self):
        evidence = self._evidence_at(11)
        result = self._result(evidence)
        order = replace(result.orders[0], signal_time="2025-03-13T00:00:00")
        with self.assertRaises(ForwardExecutionEvidenceError):
            self._build(evidence, replace(result, orders=(order,)))

    def test_wrong_side_rejects(self):
        evidence = self._evidence_at(12)
        result = self._result(evidence)
        order = replace(result.orders[0], side="SELL")
        with self.assertRaises(ForwardExecutionEvidenceError):
            self._build(evidence, replace(result, orders=(order,)))

    def test_orphan_fill_rejects(self):
        evidence = self._evidence_at(13)
        result = self._result(evidence)
        fill = replace(result.fills[0], order_id="orphan")
        with self.assertRaises(ForwardExecutionEvidenceError):
            self._build(evidence, replace(result, fills=(fill,)))

    def test_orphan_pending_rejects(self):
        evidence = self._evidence_at(14)
        from test_phase_56_4c1_forward_paper_execution import ForwardPaperExecutionReplayTests
        fixture = ForwardPaperExecutionReplayTests("test_valid_bundle_executes_through_existing_facade")
        fixture.setUpClass()
        ledger = self._ledger(evidence)
        result = fixture._run(ledger, (evidence,), {"2303": fixture._frame(offsets=(1,))})
        with self.assertRaises(ForwardExecutionEvidenceError):
            self._build(evidence, replace(result, pending_orders=(replace(result.pending_orders[0], order_id="orphan"),)), ledger)

    def test_audit_sequence_gap_rejects(self):
        evidence = self._evidence_at(15)
        result = self._result(evidence)
        with self.assertRaises(ForwardExecutionEvidenceError):
            self._build(evidence, replace(result, audit_log=(replace(result.audit_log[1], sequence=3), result.audit_log[2])))

    def test_fill_and_audit_cost_disagreement_rejects(self):
        evidence = self._evidence_at(16)
        result = self._result(evidence)
        altered = replace(result.audit_log[-1], fee=result.audit_log[-1].fee + 1.0)
        with self.assertRaises(ForwardExecutionEvidenceError):
            self._build(evidence, replace(result, audit_log=(*result.audit_log[:-1], altered)))

    def test_duplicate_json_key_rejects(self):
        evidence = self._evidence_at(17)
        result = self._result(evidence)
        payload = export_forward_execution_evidence_json(self._build(evidence, result)).replace('"schema_version": "1.0",', '"schema_version": "1.0",\n  "schema_version": "1.0",', 1)
        with self.assertRaises(ForwardExecutionEvidenceSerializationError):
            load_forward_execution_evidence_json(payload)

    def test_unknown_json_field_rejects(self):
        evidence = self._evidence_at(18)
        result = self._result(evidence)
        payload = json.loads(export_forward_execution_evidence_json(self._build(evidence, result)))
        payload["unknown"] = True
        with self.assertRaises(ForwardExecutionEvidenceSerializationError):
            load_forward_execution_evidence_json(json.dumps(payload))

    def test_nonfinite_json_rejects(self):
        evidence = self._evidence_at(19)
        result = self._result(evidence)
        payload = export_forward_execution_evidence_json(self._build(evidence, result)).replace('"fee": 0.143925', '"fee": NaN')
        with self.assertRaises(ForwardExecutionEvidenceSerializationError):
            load_forward_execution_evidence_json(payload)

    def test_production_builder_does_not_execute_runtime(self):
        path = Path("src/tw_stock_tool/application/forward_execution_evidence.py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        source = path.read_text(encoding="utf-8")
        self.assertNotIn("run_forward_paper_execution_replay", source)
        self.assertNotIn("run_simulated_portfolio_trading_result", source)
        self.assertFalse(any(isinstance(node, ast.Call) and getattr(node.func, "id", "") == "run_forward_paper_execution_replay" for node in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
