from __future__ import annotations

import ast
from dataclasses import fields, replace
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tw_stock_tool.application.forward_execution_evidence import (
    build_forward_execution_evidence,
)
from tw_stock_tool.application.forward_metrics_evidence import (
    ForwardMetricsEvidenceError,
    _build_applied_cost_metrics,
    _build_execution_health_metrics,
    _build_portfolio_metrics,
    _validate_chronology,
    build_forward_metrics_evidence,
)
from tw_stock_tool.application.forward_paper_execution import (
    run_forward_paper_execution_replay_with_trace,
)
from tw_stock_tool.forward_paper import (
    ForwardExecutionDecisionEvidence,
    ForwardExecutionOutcome,
    ForwardMetricsEvidenceModelError,
    ForwardMetricsEvidenceSerializationError,
    ForwardPortfolioObservation,
    ForwardPortfolioPositionMark,
    ForwardPortfolioTrace,
    export_forward_execution_evidence_json,
    export_forward_metrics_evidence_json,
    export_forward_portfolio_trace_json,
    load_forward_metrics_evidence_json,
)


METRICS_ID = "923e4567-e89b-42d3-a456-426614174000"
EXECUTION_EVIDENCE_ID = "823e4567-e89b-42d3-a456-426614174099"
CREATED_AT = "2025-04-02T00:00:00Z"


class ForwardMetricsEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from test_phase_56_4c1_forward_paper_execution import (
            ForwardPaperExecutionReplayTests,
        )

        ForwardPaperExecutionReplayTests.setUpClass()
        cls.fixture = ForwardPaperExecutionReplayTests(
            "test_valid_bundle_executes_through_existing_facade"
        )

    def _evidence_at(self, index: int = 0, *, signal: str = "BUY"):
        return self.fixture._evidence_at(index, signal=signal)

    def _case(self, *, offsets=(1, 2), signal="BUY", **replay_kwargs):
        recommendation = self._evidence_at(0, signal=signal)
        ledger = self.fixture._ledger(recommendation)
        bundle = run_forward_paper_execution_replay_with_trace(
            self.fixture.activation,
            self.fixture.source,
            ledger,
            {recommendation.recommendation_id: recommendation},
            {"2303": self.fixture._frame(offsets=offsets)},
            initial_cash=100_000.0,
            quantity_per_trade=1,
            **replay_kwargs,
        )
        execution = build_forward_execution_evidence(
            self.fixture.activation,
            self.fixture.source,
            ledger,
            {recommendation.recommendation_id: recommendation},
            bundle.portfolio_result,
            evidence_id=EXECUTION_EVIDENCE_ID,
            created_at=CREATED_AT,
        )
        return recommendation, ledger, bundle, execution

    def _build(self, case=None, **overrides):
        recommendation, ledger, bundle, execution = case or self._case(
            slippage_per_share=0.25
        )
        values = {
            "activation": self.fixture.activation,
            "qualification_artifact": self.fixture.source,
            "ledger": ledger,
            "recommendation_evidence_by_id": {
                recommendation.recommendation_id: recommendation
            },
            "portfolio_result": bundle.portfolio_result,
            "execution_evidence": execution,
            "portfolio_trace": bundle.portfolio_trace,
            "expected_portfolio_trace_sha256": bundle.portfolio_trace_sha256,
            "metrics_id": METRICS_ID,
            "created_at": CREATED_AT,
        }
        values.update(overrides)
        return build_forward_metrics_evidence(**values)

    @staticmethod
    def _decision(
        index: int,
        outcome: ForwardExecutionOutcome,
        *,
        action: str = "ENTER",
        side: str | None = "BUY",
        quantity: int = 1,
        price: float = 100.0,
        fee: float = 0.0,
        tax: float = 0.0,
        slippage: float = 0.0,
    ) -> ForwardExecutionDecisionEvidence:
        order_id = f"order-{index}"
        common = {
            "recommendation_id": f"00000000-0000-4000-8000-{index:012d}",
            "recommendation_sha256": f"{index % 10}" * 64,
            "observed_at": f"2025-04-02T00:00:{index:02d}Z",
            "symbol": "2303",
            "action": action,
            "expected_side": side,
            "outcome": outcome,
            "order_id": order_id,
            "order_quantity": quantity,
            "pending_reference_price": None,
            "fill_time": None,
            "fill_price": None,
            "fee": fee,
            "tax": tax,
            "slippage": slippage,
            "risk_rejection_reasons": (),
            "audit_record_ids": (f"audit-{index}",),
        }
        if outcome in {
            ForwardExecutionOutcome.NON_ACTION,
            ForwardExecutionOutcome.NO_CANDIDATE,
        }:
            common.update(
                order_id=None,
                order_quantity=None,
                audit_record_ids=(),
                fee=0.0,
                tax=0.0,
                slippage=0.0,
            )
        if outcome is ForwardExecutionOutcome.PENDING_NEXT_BAR_OPEN:
            common["pending_reference_price"] = price
        if outcome is ForwardExecutionOutcome.FILLED:
            common["fill_time"] = f"2025-04-02T00:01:{index:02d}Z"
            common["fill_price"] = price
        if outcome in {
            ForwardExecutionOutcome.FILL_SKIPPED_INVALID_OPEN,
            ForwardExecutionOutcome.FILL_FAILED_PORTFOLIO_VALIDATION,
        }:
            common["fill_time"] = f"2025-04-02T00:01:{index:02d}Z"
        return ForwardExecutionDecisionEvidence(**common)

    @staticmethod
    def _trace(
        equities: tuple[float, ...],
        *,
        initial: float,
        market_values: tuple[float, ...] | None = None,
    ) -> ForwardPortfolioTrace:
        market_values = market_values or tuple(0.0 for _ in equities)
        observations = []
        for index, (equity, market_value) in enumerate(
            zip(equities, market_values, strict=True), start=1
        ):
            positions = (
                ()
                if market_value == 0.0
                else (
                    ForwardPortfolioPositionMark(
                        symbol="2303",
                        quantity=1,
                        mark_price=market_value,
                        market_value=market_value,
                    ),
                )
            )
            observations.append(
                ForwardPortfolioObservation(
                    observed_at=f"2025-04-02T00:00:{index:02d}Z",
                    cash=equity - market_value,
                    total_market_value=market_value,
                    total_equity=equity,
                    open_position_count=len(positions),
                    pending_order_count=0,
                    reserved_buy_notional=0.0,
                    positions=positions,
                )
            )
        return ForwardPortfolioTrace(
            schema_version="1.0",
            artifact_type="forward_portfolio_trace",
            activation_id="123e4567-e89b-42d3-a456-426614174000",
            qualification_evaluation_id="223e4567-e89b-42d3-a456-426614174000",
            qualification_sha256="a" * 64,
            ledger_id="323e4567-e89b-42d3-a456-426614174000",
            ledger_sha256="b" * 64,
            strategy_id="ma_cross",
            initial_equity=initial,
            portfolio_result_sha256="c" * 64,
            observations=tuple(observations),
        )

    def test_real_c1_c2_d1_inputs_build_trusted_d2(self):
        case = self._case(slippage_per_share=0.25)
        artifact = self._build(case)
        _, _, bundle, execution = case
        expected_c2_sha = hashlib.sha256(
            export_forward_execution_evidence_json(execution).encode("utf-8")
        ).hexdigest()
        self.assertEqual(artifact.execution_evidence_sha256, expected_c2_sha)
        self.assertEqual(
            artifact.portfolio_trace_sha256, bundle.portfolio_trace_sha256
        )
        self.assertEqual(artifact.execution_health.filled_count, 1)
        self.assertEqual(artifact.applied_costs.filled_quantity, 1)

    def test_builder_performs_no_replay_runtime_stepper_or_backtest_calls(self):
        case = self._case()
        targets = (
            "tw_stock_tool.application.forward_paper_execution.run_forward_paper_execution_replay",
            "tw_stock_tool.application.forward_paper_execution.run_forward_paper_execution_replay_with_trace",
            "tw_stock_tool.paper_trading.portfolio_engine.run_simulated_portfolio_trading_result",
            "tw_stock_tool.paper_trading.coordinator.run_chronological_multi_symbol_simulated_paper_trading",
            "tw_stock_tool.backtesting.walk_forward.run_strategy_backtest",
        )
        patches = [patch(target, side_effect=AssertionError(target)) for target in targets]
        mocks = [item.start() for item in patches]
        try:
            self._build(case)
        finally:
            for item in reversed(patches):
                item.stop()
        self.assertTrue(all(mock.call_count == 0 for mock in mocks))

    def test_forged_activation_and_missing_recommendation_chain_reject(self):
        case = self._case()
        forged_activation = replace(
            self.fixture.activation,
            activation_id="123e4567-e89b-42d3-a456-426614174999",
        )
        with self.assertRaises(ForwardMetricsEvidenceError):
            self._build(case, activation=forged_activation)
        with self.assertRaises(ForwardMetricsEvidenceError):
            self._build(case, recommendation_evidence_by_id={})

    def test_altered_c2_root_or_decision_rejects_against_exact_rebuild(self):
        case = self._case()
        execution = case[3]
        with self.assertRaises(ForwardMetricsEvidenceError):
            self._build(
                case,
                execution_evidence=replace(execution, activation_sha256="f" * 64),
            )
        forged_decision = replace(execution.decisions[0], slippage=99.0)
        with self.assertRaises(ForwardMetricsEvidenceError):
            self._build(
                case,
                execution_evidence=replace(execution, decisions=(forged_decision,)),
            )

    def test_c2_canonical_sha_and_metrics_bytes_are_deterministic(self):
        case = self._case(slippage_per_share=0.25)
        first = self._build(case)
        second = self._build(case)
        self.assertEqual(
            first.execution_evidence_sha256, second.execution_evidence_sha256
        )
        self.assertEqual(
            export_forward_metrics_evidence_json(first),
            export_forward_metrics_evidence_json(second),
        )

    def test_external_trace_sha_is_mandatory_and_wrong_anchor_rejects(self):
        recommendation, ledger, bundle, execution = self._case()
        with self.assertRaises(TypeError):
            build_forward_metrics_evidence(
                self.fixture.activation,
                self.fixture.source,
                ledger,
                {recommendation.recommendation_id: recommendation},
                bundle.portfolio_result,
                execution,
                bundle.portfolio_trace,
                metrics_id=METRICS_ID,
                created_at=CREATED_AT,
            )
        with self.assertRaises(ForwardMetricsEvidenceError):
            self._build(
                (recommendation, ledger, bundle, execution),
                expected_portfolio_trace_sha256="0" * 64,
            )

    def test_non_final_trace_mutation_with_original_anchor_rejects(self):
        case = self._case()
        trace = case[2].portfolio_trace
        first = trace.observations[0]
        forged_first = replace(
            first,
            cash=first.cash + 1.0,
            total_equity=first.total_equity + 1.0,
        )
        forged = replace(
            trace, observations=(forged_first, *trace.observations[1:])
        )
        with self.assertRaises(ForwardMetricsEvidenceError):
            self._build(case, portfolio_trace=forged)

    def test_result_and_cross_artifact_identity_mismatches_reject(self):
        case = self._case()
        trace = case[2].portfolio_trace
        for forged in (
            replace(trace, portfolio_result_sha256="f" * 64),
            replace(trace, strategy_id="foreign_strategy"),
            replace(
                trace,
                ledger_id="423e4567-e89b-42d3-a456-426614174000",
            ),
        ):
            forged_sha = hashlib.sha256(
                export_forward_portfolio_trace_json(forged).encode("utf-8")
            ).hexdigest()
            with self.assertRaises(ForwardMetricsEvidenceError):
                self._build(
                    case,
                    portfolio_trace=forged,
                    expected_portfolio_trace_sha256=forged_sha,
                )

    def test_decision_and_terminal_chronology_fail_closed(self):
        case = self._case()
        execution = case[3]
        trace = case[2].portfolio_trace
        with self.assertRaisesRegex(ForwardMetricsEvidenceError, "decision timestamp"):
            _validate_chronology(
                self.fixture.activation,
                execution,
                replace(trace, observations=trace.observations[1:]),
            )
        terminal = execution.decisions[0]
        absent = replace(terminal, fill_time="2025-04-02T00:00:59Z")
        with self.assertRaisesRegex(ForwardMetricsEvidenceError, "terminal fill timestamp"):
            _validate_chronology(
                self.fixture.activation,
                replace(execution, decisions=(absent,)),
                trace,
            )
        non_increasing = replace(terminal, fill_time=terminal.observed_at)
        trace_with_time = replace(
            trace,
            observations=(
                replace(trace.observations[0], observed_at=terminal.observed_at),
                *trace.observations[1:],
            ),
        )
        with self.assertRaisesRegex(ForwardMetricsEvidenceError, "must follow"):
            _validate_chronology(
                self.fixture.activation,
                replace(execution, decisions=(non_increasing,)),
                trace_with_time,
            )

    def test_trace_at_qualification_cutoff_rejects(self):
        case = self._case(signal="HOLD")
        trace = case[2].portfolio_trace
        cutoff_observation = replace(
            trace.observations[0],
            observed_at=self.fixture.activation.qualification_cutoff,
        )
        with self.assertRaisesRegex(ForwardMetricsEvidenceError, "qualification cutoff"):
            _validate_chronology(
                self.fixture.activation,
                case[3],
                replace(trace, observations=(cutoff_observation, *trace.observations[1:])),
            )

    def test_all_seven_outcomes_have_exact_counts_and_frozen_rates(self):
        decisions = (
            self._decision(
                1,
                ForwardExecutionOutcome.NON_ACTION,
                action="HOLD",
                side=None,
            ),
            self._decision(2, ForwardExecutionOutcome.NO_CANDIDATE),
            self._decision(3, ForwardExecutionOutcome.REJECTED),
            self._decision(4, ForwardExecutionOutcome.PENDING_NEXT_BAR_OPEN),
            self._decision(5, ForwardExecutionOutcome.FILLED),
            self._decision(6, ForwardExecutionOutcome.FILL_SKIPPED_INVALID_OPEN),
            self._decision(
                7,
                ForwardExecutionOutcome.FILL_FAILED_PORTFOLIO_VALIDATION,
            ),
        )
        metrics = _build_execution_health_metrics(decisions)
        self.assertEqual(
            (
                metrics.total_decisions,
                metrics.actionable_decisions,
                metrics.non_action_decisions,
                metrics.no_candidate_count,
                metrics.candidate_count,
                metrics.rejected_count,
                metrics.accepted_count,
                metrics.pending_count,
                metrics.filled_count,
                metrics.skipped_invalid_open_count,
                metrics.failed_portfolio_validation_count,
                metrics.terminal_attempt_count,
            ),
            (7, 6, 1, 1, 5, 1, 4, 1, 1, 1, 1, 3),
        )
        self.assertEqual(metrics.candidate_rate, 5 / 6)
        self.assertEqual(metrics.rejection_rate, 1 / 5)
        self.assertEqual(metrics.terminal_fill_success_rate, 1 / 3)
        self.assertEqual(metrics.invalid_open_rate, 1 / 3)
        self.assertEqual(metrics.portfolio_validation_failure_rate, 1 / 3)
        self.assertEqual(metrics.pending_rate, 1 / 4)

    def test_zero_denominator_rates_are_none_and_invariants_reject(self):
        decision = self._decision(
            8,
            ForwardExecutionOutcome.NON_ACTION,
            action="NO_TRADE",
            side=None,
        )
        metrics = _build_execution_health_metrics((decision,))
        self.assertIsNone(metrics.candidate_rate)
        self.assertIsNone(metrics.rejection_rate)
        self.assertIsNone(metrics.terminal_fill_success_rate)
        self.assertIsNone(metrics.pending_rate)
        with self.assertRaises(ForwardMetricsEvidenceModelError):
            replace(metrics, candidate_count=1)

    def test_buy_and_sell_costs_use_frozen_rates(self):
        buy = self._decision(
            9,
            ForwardExecutionOutcome.FILLED,
            price=100.0,
            fee=0.1,
            slippage=0.25,
        )
        sell = self._decision(
            10,
            ForwardExecutionOutcome.FILLED,
            action="EXIT",
            side="SELL",
            price=200.0,
            fee=0.2,
            tax=0.6,
            slippage=0.25,
        )
        metrics = _build_applied_cost_metrics(
            (buy, sell), fee_rate=0.001, tax_rate=0.003
        )
        self.assertEqual(metrics.filled_quantity, 2)
        self.assertEqual(metrics.filled_gross_notional, 300.0)
        self.assertAlmostEqual(metrics.applied_fee, 0.3)
        self.assertEqual(metrics.applied_tax, 0.6)
        self.assertEqual(metrics.applied_slippage, 0.5)
        self.assertAlmostEqual(metrics.applied_total_cost, 1.4)
        self.assertAlmostEqual(
            metrics.applied_cost_bps, 1.4 / 300.0 * 10_000.0
        )
        self.assertEqual(metrics.effective_slippage_per_share, 0.25)

    def test_forged_filled_fee_or_tax_rejects(self):
        buy = self._decision(
            11,
            ForwardExecutionOutcome.FILLED,
            price=100.0,
            fee=0.2,
        )
        sell = self._decision(
            12,
            ForwardExecutionOutcome.FILLED,
            action="EXIT",
            side="SELL",
            price=100.0,
            fee=0.1,
            tax=0.0,
        )
        for decision in (buy, sell):
            with self.assertRaisesRegex(ForwardMetricsEvidenceError, "frozen"):
                _build_applied_cost_metrics(
                    (decision,), fee_rate=0.001, tax_rate=0.003
                )

    def test_failed_fill_attempted_costs_are_not_applied(self):
        failed = self._decision(
            13,
            ForwardExecutionOutcome.FILL_FAILED_PORTFOLIO_VALIDATION,
            fee=10.0,
            tax=20.0,
            slippage=30.0,
        )
        metrics = _build_applied_cost_metrics(
            (failed,), fee_rate=0.001, tax_rate=0.003
        )
        self.assertEqual(metrics.filled_quantity, 0)
        self.assertEqual(metrics.applied_total_cost, 0.0)
        self.assertIsNone(metrics.applied_cost_bps)
        self.assertIsNone(metrics.effective_slippage_per_share)

    def test_portfolio_return_drawdown_and_initial_baseline(self):
        metrics = _build_portfolio_metrics(
            self._trace((90.0, 120.0, 60.0, 110.0), initial=100.0)
        )
        self.assertEqual(metrics.total_return_pct, 10.000000000000009)
        self.assertEqual(metrics.max_drawdown_pct, 50.0)
        baseline = _build_portfolio_metrics(
            self._trace((80.0, 90.0), initial=100.0)
        )
        self.assertEqual(baseline.max_drawdown_pct, 20.0)
        zero = _build_portfolio_metrics(self._trace((0.0,), initial=0.0))
        self.assertIsNone(zero.total_return_pct)
        self.assertEqual(zero.max_drawdown_pct, 0.0)

    def test_exposure_and_single_symbol_share_formulas(self):
        metrics = _build_portfolio_metrics(
            self._trace((100.0, 200.0), initial=100.0, market_values=(40.0, 100.0))
        )
        self.assertEqual(metrics.max_market_exposure_pct, 50.0)
        self.assertEqual(metrics.max_single_symbol_market_value_share_pct, 100.0)
        never_invested = _build_portfolio_metrics(
            self._trace((100.0, 100.0), initial=100.0)
        )
        self.assertEqual(never_invested.max_market_exposure_pct, 0.0)
        self.assertEqual(
            never_invested.max_single_symbol_market_value_share_pct, 0.0
        )

    def test_qualification_reference_has_frozen_basis_without_drift(self):
        artifact = self._build()
        reference = artifact.qualification_reference
        self.assertEqual(
            reference.qualification_return_basis,
            "mean_valid_window_test_return_pct",
        )
        self.assertEqual(
            reference.qualification_drawdown_basis,
            "worst_valid_window_symbol_backtest_max_drawdown_pct",
        )
        self.assertEqual(
            reference.forward_return_basis,
            "combined_forward_portfolio_total_equity_return_pct",
        )
        self.assertEqual(
            reference.forward_drawdown_basis,
            "combined_forward_portfolio_equity_trace_max_drawdown_pct",
        )
        field_names = {item.name for item in fields(type(artifact))}
        field_names.update(item.name for item in fields(type(reference)))
        self.assertFalse(any("drift" in name for name in field_names))

    def test_strict_json_missing_unknown_duplicate_and_nonfinite_reject(self):
        text = export_forward_metrics_evidence_json(self._build())
        payload = json.loads(text)
        missing = dict(payload)
        missing.pop("ledger_sha256")
        unknown = dict(payload, surprise=True)
        for invalid in (json.dumps(missing), json.dumps(unknown)):
            with self.assertRaises(ForwardMetricsEvidenceSerializationError):
                load_forward_metrics_evidence_json(invalid)
        duplicate = text.replace(
            '"schema_version": "1.0",',
            '"schema_version": "1.0", "schema_version": "1.0",',
        )
        with self.assertRaises(ForwardMetricsEvidenceSerializationError):
            load_forward_metrics_evidence_json(duplicate)
        nonfinite = text.replace(
            '"filled_gross_notional": 101.0',
            '"filled_gross_notional": NaN',
        )
        with self.assertRaises(ForwardMetricsEvidenceSerializationError):
            load_forward_metrics_evidence_json(nonfinite)

    def test_unknown_schema_artifact_and_nested_arithmetic_reject(self):
        payload = json.loads(export_forward_metrics_evidence_json(self._build()))
        for name, value in (
            ("schema_version", "2.0"),
            ("artifact_type", "foreign"),
        ):
            forged = dict(payload)
            forged[name] = value
            with self.assertRaises(ForwardMetricsEvidenceSerializationError):
                load_forward_metrics_evidence_json(json.dumps(forged))
        forged = json.loads(json.dumps(payload))
        forged["applied_costs"]["applied_total_cost"] += 1.0
        with self.assertRaises(ForwardMetricsEvidenceSerializationError):
            load_forward_metrics_evidence_json(json.dumps(forged))

    def test_metrics_serialization_round_trip_is_byte_deterministic(self):
        first = export_forward_metrics_evidence_json(self._build())
        second = export_forward_metrics_evidence_json(
            load_forward_metrics_evidence_json(first)
        )
        self.assertEqual(first, second)

    def test_production_module_has_no_self_auth_trace_or_scope_creep(self):
        path = Path(
            "src/tw_stock_tool/application/forward_metrics_evidence.py"
        )
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = (
            "run_forward_paper_execution_replay",
            "run_forward_paper_execution_replay_with_trace",
            "run_simulated_portfolio_trading_result",
            "run_chronological_multi_symbol_simulated_paper_trading",
            "run_strategy_backtest",
            "fetch",
            "broker",
            "workspace",
            "active",
            "paused",
            "revoked",
            "return_drift",
            "drawdown_drift",
        )
        names = {node.id.lower() for node in ast.walk(tree) if isinstance(node, ast.Name)}
        imports = {
            alias.name.lower()
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse(any(item in names or item in imports for item in forbidden))
        self.assertEqual(source.count("hashlib.sha256"), 1)
        self.assertIn(
            "expected_portfolio_trace_sha256=expected_portfolio_trace_sha256",
            source,
        )


if __name__ == "__main__":
    unittest.main()
