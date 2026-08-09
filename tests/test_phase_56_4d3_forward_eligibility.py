from __future__ import annotations

import ast
from dataclasses import fields, replace
import hashlib
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from tw_stock_tool.application.forward_eligibility_evidence import (
    ForwardEligibilityEvidenceError,
    build_forward_eligibility_evidence,
)
from tw_stock_tool.forward_paper.eligibility_models import (
    ForwardEligibilityEvidence,
    ForwardEligibilityFinding,
    ForwardEligibilityModelError,
    ForwardEligibilityPolicy,
    ForwardEligibilitySeverity,
    ForwardEligibilityState,
)
from tw_stock_tool.forward_paper.eligibility_policies import (
    TAIWAN_EQUITY_DAILY_FORWARD_V1,
    ForwardEligibilityPolicyError,
    evaluate_forward_eligibility,
    is_supported_forward_eligibility_policy,
    resolve_forward_eligibility_policy,
)
from tw_stock_tool.forward_paper.eligibility_serialization import (
    ForwardEligibilitySerializationError,
    export_forward_eligibility_evidence_json,
    load_forward_eligibility_evidence_json,
)
from tw_stock_tool.forward_paper.metrics_models import (
    ForwardExecutionHealthMetrics,
)
from tw_stock_tool.forward_paper.metrics_serialization import (
    export_forward_metrics_evidence_json,
)


ELIGIBILITY_ID = "a23e4567-e89b-42d3-a456-426614174000"
ELIGIBILITY_CREATED_AT = "2025-04-02T00:00:01Z"


class ForwardEligibilityEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from test_phase_56_4d2_forward_metrics_evidence import (
            ForwardMetricsEvidenceTests,
        )

        ForwardMetricsEvidenceTests.setUpClass()
        cls.d2 = ForwardMetricsEvidenceTests(
            "test_real_c1_c2_d1_inputs_build_trusted_d2"
        )
        cls.case = cls.d2._case(slippage_per_share=0.25)
        cls.metrics = cls.d2._build(cls.case)

    @staticmethod
    def _health(
        *,
        filled: int = 0,
        skipped: int = 0,
        failed: int = 0,
        pending: int = 0,
        rejected: int = 0,
    ) -> ForwardExecutionHealthMetrics:
        terminal = filled + skipped + failed
        accepted = terminal + pending
        candidate = accepted + rejected
        return ForwardExecutionHealthMetrics(
            total_decisions=candidate,
            actionable_decisions=candidate,
            enter_decisions=candidate,
            exit_decisions=0,
            non_action_decisions=0,
            no_candidate_count=0,
            candidate_count=candidate,
            rejected_count=rejected,
            accepted_count=accepted,
            pending_count=pending,
            filled_count=filled,
            skipped_invalid_open_count=skipped,
            failed_portfolio_validation_count=failed,
            terminal_attempt_count=terminal,
            candidate_rate=None if candidate == 0 else 1.0,
            rejection_rate=None if candidate == 0 else rejected / candidate,
            terminal_fill_success_rate=(
                None if terminal == 0 else filled / terminal
            ),
            invalid_open_rate=None if terminal == 0 else skipped / terminal,
            portfolio_validation_failure_rate=(
                None if terminal == 0 else failed / terminal
            ),
            pending_rate=None if accepted == 0 else pending / accepted,
        )

    def _build(self, **overrides):
        recommendation, ledger, bundle, execution = self.case
        values = {
            "activation": self.d2.fixture.activation,
            "qualification_artifact": self.d2.fixture.source,
            "ledger": ledger,
            "recommendation_evidence_by_id": {
                recommendation.recommendation_id: recommendation
            },
            "portfolio_result": bundle.portfolio_result,
            "execution_evidence": execution,
            "portfolio_trace": bundle.portfolio_trace,
            "metrics_evidence": self.metrics,
            "expected_portfolio_trace_sha256": bundle.portfolio_trace_sha256,
            "policy_id": TAIWAN_EQUITY_DAILY_FORWARD_V1.policy_id,
            "policy_version": TAIWAN_EQUITY_DAILY_FORWARD_V1.policy_version,
            "eligibility_id": ELIGIBILITY_ID,
            "created_at": ELIGIBILITY_CREATED_AT,
        }
        values.update(overrides)
        return build_forward_eligibility_evidence(**values)

    @staticmethod
    def _artifact_for(metrics) -> ForwardEligibilityEvidence:
        state, findings = evaluate_forward_eligibility(
            metrics, TAIWAN_EQUITY_DAILY_FORWARD_V1
        )
        return ForwardEligibilityEvidence(
            schema_version="1.0",
            artifact_type="forward_eligibility_evidence",
            eligibility_id=ELIGIBILITY_ID,
            created_at=ELIGIBILITY_CREATED_AT,
            activation_id=metrics.activation_id,
            activation_sha256=metrics.activation_sha256,
            qualification_evaluation_id=metrics.qualification_evaluation_id,
            qualification_sha256=metrics.qualification_sha256,
            ledger_id=metrics.ledger_id,
            ledger_sha256=metrics.ledger_sha256,
            metrics_id=metrics.metrics_id,
            metrics_sha256="a" * 64,
            strategy_id=metrics.strategy_id,
            policy_id=TAIWAN_EQUITY_DAILY_FORWARD_V1.policy_id,
            policy_version=TAIWAN_EQUITY_DAILY_FORWARD_V1.policy_version,
            state=state,
            findings=findings,
        )

    def test_genuine_chain_builds_active_evidence_with_canonical_d2_sha(self):
        artifact = self._build()
        expected = hashlib.sha256(
            export_forward_metrics_evidence_json(self.metrics).encode("utf-8")
        ).hexdigest()
        self.assertIs(artifact.state, ForwardEligibilityState.ACTIVE)
        self.assertEqual(artifact.findings, ())
        self.assertEqual(artifact.metrics_sha256, expected)
        self.assertEqual(artifact.metrics_id, self.metrics.metrics_id)

    def test_builder_performs_no_replay_fetch_backtest_or_runtime_calls(self):
        targets = (
            "tw_stock_tool.application.forward_paper_execution.run_forward_paper_execution_replay",
            "tw_stock_tool.application.forward_paper_execution.run_forward_paper_execution_replay_with_trace",
            "tw_stock_tool.paper_trading.portfolio_engine.run_simulated_portfolio_trading_result",
            "tw_stock_tool.paper_trading.coordinator.run_chronological_multi_symbol_simulated_paper_trading",
            "tw_stock_tool.backtesting.walk_forward.run_strategy_backtest",
            "tw_stock_tool.data.data_loader.download_tw_stock",
        )
        patches = [patch(target, side_effect=AssertionError(target)) for target in targets]
        mocks = [item.start() for item in patches]
        try:
            self._build()
        finally:
            for item in reversed(patches):
                item.stop()
        self.assertTrue(all(mock.call_count == 0 for mock in mocks))

    def test_altered_d2_root_nested_portfolio_and_qualification_reject(self):
        forged = (
            replace(self.metrics, activation_sha256="f" * 64),
            replace(
                self.metrics,
                execution_health=self._health(skipped=1),
            ),
            replace(
                self.metrics,
                portfolio_metrics=replace(
                    self.metrics.portfolio_metrics,
                    max_drawdown_pct=15.0,
                ),
            ),
            replace(
                self.metrics,
                qualification_reference=replace(
                    self.metrics.qualification_reference,
                    qualification_completed_trades=(
                        self.metrics.qualification_reference.qualification_completed_trades
                        + 1
                    ),
                ),
            ),
        )
        for artifact in forged:
            with self.subTest(artifact=artifact):
                with self.assertRaises(ForwardEligibilityEvidenceError):
                    self._build(metrics_evidence=artifact)

    def test_external_trace_anchor_remains_required_and_wrong_anchor_rejects(self):
        recommendation, ledger, bundle, execution = self.case
        with self.assertRaises(TypeError):
            build_forward_eligibility_evidence(
                self.d2.fixture.activation,
                self.d2.fixture.source,
                ledger,
                {recommendation.recommendation_id: recommendation},
                bundle.portfolio_result,
                execution,
                bundle.portfolio_trace,
                self.metrics,
                policy_id=TAIWAN_EQUITY_DAILY_FORWARD_V1.policy_id,
                policy_version=TAIWAN_EQUITY_DAILY_FORWARD_V1.policy_version,
                eligibility_id=ELIGIBILITY_ID,
                created_at=ELIGIBILITY_CREATED_AT,
            )
        with self.assertRaises(ForwardEligibilityEvidenceError):
            self._build(expected_portfolio_trace_sha256="0" * 64)

    def test_unknown_policy_identity_and_earlier_created_at_reject(self):
        for overrides in (
            {"policy_id": "unknown"},
            {"policy_version": "2.0"},
            {"created_at": "2025-04-01T23:59:59Z"},
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(ForwardEligibilityEvidenceError):
                    self._build(**overrides)

    def test_registered_policy_is_exact_and_mutation_is_unsupported(self):
        policy = resolve_forward_eligibility_policy(
            "taiwan_equity_daily_forward_v1", "1.0"
        )
        self.assertEqual(
            (
                policy.pause_max_drawdown_pct,
                policy.revoke_max_drawdown_pct,
                policy.minimum_terminal_attempts_for_invalid_open_rate,
                policy.pause_invalid_open_rate,
                policy.revoke_invalid_open_rate,
                policy.pause_portfolio_validation_failure_count,
                policy.revoke_portfolio_validation_failure_count,
            ),
            (15.0, 25.0, 5, 0.20, 0.50, 1, 3),
        )
        mutated = replace(policy, pause_max_drawdown_pct=14.0)
        self.assertFalse(is_supported_forward_eligibility_policy(mutated))
        with self.assertRaises(ForwardEligibilityPolicyError):
            evaluate_forward_eligibility(self.metrics, mutated)

    def test_policy_model_rejects_invalid_ranges_types_and_nonfinite_values(self):
        values = {
            field.name: getattr(TAIWAN_EQUITY_DAILY_FORWARD_V1, field.name)
            for field in fields(ForwardEligibilityPolicy)
        }
        invalid = (
            ("pause_max_drawdown_pct", math.nan),
            ("revoke_max_drawdown_pct", math.inf),
            ("pause_max_drawdown_pct", 25.0),
            ("pause_invalid_open_rate", 0.50),
            ("minimum_terminal_attempts_for_invalid_open_rate", 0),
            ("pause_portfolio_validation_failure_count", 3),
            ("revoke_portfolio_validation_failure_count", True),
        )
        for name, value in invalid:
            with self.subTest(name=name, value=value):
                with self.assertRaises(ForwardEligibilityModelError):
                    ForwardEligibilityPolicy(**dict(values, **{name: value}))

    def test_drawdown_thresholds_are_inclusive_and_emit_highest_only(self):
        cases = (
            (14.999, ForwardEligibilityState.ACTIVE, ()),
            (15.0, ForwardEligibilityState.PAUSED, ("forward_drawdown_pause",)),
            (25.0, ForwardEligibilityState.REVOKED, ("forward_drawdown_revoke",)),
        )
        for value, expected_state, expected_codes in cases:
            metrics = replace(
                self.metrics,
                portfolio_metrics=replace(
                    self.metrics.portfolio_metrics,
                    max_drawdown_pct=value,
                ),
                execution_health=self._health(),
            )
            state, findings = evaluate_forward_eligibility(
                metrics, TAIWAN_EQUITY_DAILY_FORWARD_V1
            )
            self.assertIs(state, expected_state)
            self.assertEqual(tuple(item.code for item in findings), expected_codes)

    def test_portfolio_failure_thresholds_are_inclusive_and_emit_highest_only(self):
        cases = (
            (0, ForwardEligibilityState.ACTIVE, ()),
            (
                1,
                ForwardEligibilityState.PAUSED,
                ("portfolio_validation_failure_pause",),
            ),
            (
                3,
                ForwardEligibilityState.REVOKED,
                ("portfolio_validation_failure_revoke",),
            ),
        )
        for count, expected_state, expected_codes in cases:
            metrics = replace(
                self.metrics,
                execution_health=self._health(failed=count),
                portfolio_metrics=replace(
                    self.metrics.portfolio_metrics, max_drawdown_pct=0.0
                ),
            )
            state, findings = evaluate_forward_eligibility(
                metrics, TAIWAN_EQUITY_DAILY_FORWARD_V1
            )
            self.assertIs(state, expected_state)
            self.assertEqual(tuple(item.code for item in findings), expected_codes)

    def test_invalid_open_minimum_and_inclusive_thresholds(self):
        cases = (
            (self._health(skipped=4), ForwardEligibilityState.ACTIVE, ()),
            (
                self._health(filled=4, skipped=1),
                ForwardEligibilityState.PAUSED,
                ("invalid_open_rate_pause",),
            ),
            (
                self._health(filled=3, skipped=3),
                ForwardEligibilityState.REVOKED,
                ("invalid_open_rate_revoke",),
            ),
        )
        for health, expected_state, expected_codes in cases:
            metrics = replace(
                self.metrics,
                execution_health=health,
                portfolio_metrics=replace(
                    self.metrics.portfolio_metrics, max_drawdown_pct=0.0
                ),
            )
            state, findings = evaluate_forward_eligibility(
                metrics, TAIWAN_EQUITY_DAILY_FORWARD_V1
            )
            self.assertIs(state, expected_state)
            self.assertEqual(tuple(item.code for item in findings), expected_codes)

    def test_simultaneous_findings_are_canonical_and_revoke_dominates(self):
        paused_metrics = replace(
            self.metrics,
            execution_health=self._health(filled=3, skipped=1, failed=1),
            portfolio_metrics=replace(
                self.metrics.portfolio_metrics, max_drawdown_pct=15.0
            ),
        )
        state, findings = evaluate_forward_eligibility(
            paused_metrics, TAIWAN_EQUITY_DAILY_FORWARD_V1
        )
        self.assertIs(state, ForwardEligibilityState.PAUSED)
        self.assertEqual(
            tuple(item.code for item in findings),
            (
                "forward_drawdown_pause",
                "invalid_open_rate_pause",
                "portfolio_validation_failure_pause",
            ),
        )
        revoked_metrics = replace(
            paused_metrics,
            execution_health=self._health(filled=2, skipped=3, failed=1),
        )
        state, findings = evaluate_forward_eligibility(
            revoked_metrics, TAIWAN_EQUITY_DAILY_FORWARD_V1
        )
        self.assertIs(state, ForwardEligibilityState.REVOKED)
        self.assertEqual(findings[1].code, "invalid_open_rate_revoke")

    def test_rejection_pending_return_and_concentration_are_not_policy_failures(self):
        health_cases = (self._health(rejected=20), self._health(pending=20))
        for health in health_cases:
            metrics = replace(
                self.metrics,
                execution_health=health,
                portfolio_metrics=replace(
                    self.metrics.portfolio_metrics,
                    initial_equity=100.0,
                    final_equity=50.0,
                    total_return_pct=-50.0,
                    max_drawdown_pct=0.0,
                    max_single_symbol_market_value_share_pct=100.0,
                ),
            )
            state, findings = evaluate_forward_eligibility(
                metrics, TAIWAN_EQUITY_DAILY_FORWARD_V1
            )
            self.assertIs(state, ForwardEligibilityState.ACTIVE)
            self.assertEqual(findings, ())

    def test_evidence_rejects_state_mismatch_duplicate_or_noncanonical_findings(self):
        metrics = replace(
            self.metrics,
            execution_health=self._health(filled=3, skipped=1, failed=1),
            portfolio_metrics=replace(
                self.metrics.portfolio_metrics, max_drawdown_pct=15.0
            ),
        )
        artifact = self._artifact_for(metrics)
        with self.assertRaises(ForwardEligibilityModelError):
            replace(artifact, state=ForwardEligibilityState.ACTIVE)
        with self.assertRaises(ForwardEligibilityModelError):
            replace(artifact, findings=(artifact.findings[0],) * 2)
        with self.assertRaises(ForwardEligibilityModelError):
            replace(artifact, findings=tuple(reversed(artifact.findings)))

    def test_finding_rejects_wrong_severity_metric_threshold_and_revoke_overlap(self):
        finding = ForwardEligibilityFinding(
            code="forward_drawdown_pause",
            severity=ForwardEligibilitySeverity.PAUSE,
            metric_name="max_drawdown_pct",
            observed_value=15.0,
            threshold_value=15.0,
            message="drawdown pause",
        )
        invalid = (
            {"severity": ForwardEligibilitySeverity.REVOKE},
            {"metric_name": "total_return_pct"},
            {"threshold_value": 14.0},
            {"observed_value": 25.0},
        )
        for overrides in invalid:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ForwardEligibilityModelError):
                    replace(finding, **overrides)

    def test_strict_json_rejects_missing_unknown_duplicate_nonfinite_and_vocab(self):
        metrics = replace(
            self.metrics,
            portfolio_metrics=replace(
                self.metrics.portfolio_metrics, max_drawdown_pct=15.0
            ),
            execution_health=self._health(),
        )
        text = export_forward_eligibility_evidence_json(
            self._artifact_for(metrics)
        )
        payload = json.loads(text)
        missing = dict(payload)
        missing.pop("ledger_sha256")
        unknown = dict(payload, surprise=True)
        duplicate = text.replace(
            '"schema_version": "1.0",',
            '"schema_version": "1.0", "schema_version": "1.0",',
        )
        nonfinite = text.replace('"observed_value": 15.0', '"observed_value": NaN')
        bad_state = json.dumps(dict(payload, state="HEALTHY"))
        bad_code = json.loads(text)
        bad_code["findings"][0]["code"] = "return_drift"
        for invalid in (
            json.dumps(missing),
            json.dumps(unknown),
            duplicate,
            nonfinite,
            bad_state,
            json.dumps(bad_code),
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ForwardEligibilitySerializationError):
                    load_forward_eligibility_evidence_json(invalid)

    def test_serialization_round_trip_is_byte_deterministic(self):
        first = export_forward_eligibility_evidence_json(self._build())
        second = export_forward_eligibility_evidence_json(
            load_forward_eligibility_evidence_json(first)
        )
        self.assertEqual(first, second)

    def test_production_boundary_has_no_scope_creep_or_drift_policy(self):
        paths = (
            Path("src/tw_stock_tool/application/forward_eligibility_evidence.py"),
            Path("src/tw_stock_tool/forward_paper/eligibility_policies.py"),
        )
        source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        tree = ast.parse(source)
        forbidden_names = {
            "run_forward_paper_execution_replay",
            "run_forward_paper_execution_replay_with_trace",
            "run_simulated_portfolio_trading_result",
            "run_strategy_backtest",
            "return_drift",
            "drawdown_drift",
        }
        names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }
        self.assertTrue(forbidden_names.isdisjoint(names))
        policy_fields = {item.name for item in fields(ForwardEligibilityPolicy)}
        self.assertFalse(any("drift" in name for name in policy_fields))
        self.assertIn(
            "expected_portfolio_trace_sha256=expected_portfolio_trace_sha256",
            source,
        )


if __name__ == "__main__":
    unittest.main()
