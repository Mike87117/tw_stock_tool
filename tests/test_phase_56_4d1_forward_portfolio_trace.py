from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.application.forward_paper_execution import (
    ForwardPaperExecutionError,
    ForwardPaperExecutionReplayBundle,
    run_forward_paper_execution_replay,
    run_forward_paper_execution_replay_with_trace,
    validate_forward_portfolio_trace,
)
from tw_stock_tool.forward_paper import (
    ForwardPortfolioObservation,
    ForwardPortfolioPositionMark,
    ForwardPortfolioTraceModelError,
    ForwardPortfolioTraceSerializationError,
    export_forward_portfolio_trace_json,
    load_forward_portfolio_trace_json,
)
from tw_stock_tool.paper_trading import portfolio_engine
from tw_stock_tool.paper_trading.coordinator import (
    run_chronological_multi_symbol_simulated_paper_trading,
)
from tw_stock_tool.paper_trading.portfolio_results import (
    SimulatedPortfolioTradingResult,
)
from tw_stock_tool.paper_trading.portfolio_serialization import (
    export_simulated_portfolio_trading_result_json,
)
from tw_stock_tool.paper_trading.stepper import process_simulated_pending_fill


class ForwardPortfolioTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from test_phase_56_4c1_forward_paper_execution import (
            ForwardPaperExecutionReplayTests,
        )

        ForwardPaperExecutionReplayTests.setUpClass()
        cls.fixture = ForwardPaperExecutionReplayTests(
            "test_valid_bundle_executes_through_existing_facade"
        )

    def _evidence_at(
        self,
        index: int,
        *,
        symbol: str = "2303",
        offset: int = 1,
        signal: str = "BUY",
    ):
        return self.fixture._evidence_at(
            index, symbol=symbol, offset=offset, signal=signal
        )

    def _ledger(self, *evidence):
        return self.fixture._ledger(*evidence)

    def _frame(self, **kwargs):
        return self.fixture._frame(**kwargs)

    def _bundle(
        self,
        *evidence,
        frames=None,
        ledger=None,
        initial_cash=100_000.0,
        **kwargs,
    ) -> ForwardPaperExecutionReplayBundle:
        if frames is None:
            frames = {"2303": self._frame()}
        if ledger is None:
            ledger = self._ledger(*evidence)
        return run_forward_paper_execution_replay_with_trace(
            self.fixture.activation,
            self.fixture.source,
            ledger,
            {item.recommendation_id: item for item in evidence},
            frames,
            initial_cash=initial_cash,
            quantity_per_trade=1,
            **kwargs,
        )

    def test_legacy_result_type_and_traced_result_are_equivalent(self):
        evidence = self._evidence_at(0)
        ledger = self._ledger(evidence)
        frames = {"2303": self._frame()}
        legacy = run_forward_paper_execution_replay(
            self.fixture.activation,
            self.fixture.source,
            ledger,
            {evidence.recommendation_id: evidence},
            frames,
            initial_cash=100_000.0,
            quantity_per_trade=1,
        )
        bundle = self._bundle(evidence, frames=frames, ledger=ledger)
        self.assertIs(type(legacy), SimulatedPortfolioTradingResult)
        self.assertEqual(
            export_simulated_portfolio_trading_result_json(legacy),
            export_simulated_portfolio_trading_result_json(
                bundle.portfolio_result
            ),
        )

    def test_traced_replay_calls_facade_and_coordinator_once(self):
        evidence = self._evidence_at(1)
        with (
            patch.object(
                portfolio_engine,
                "run_simulated_portfolio_trading_result",
                wraps=portfolio_engine.run_simulated_portfolio_trading_result,
            ) as facade,
            patch.object(
                portfolio_engine,
                "run_chronological_multi_symbol_simulated_paper_trading",
                wraps=run_chronological_multi_symbol_simulated_paper_trading,
            ) as coordinator,
        ):
            self._bundle(evidence)
        facade.assert_called_once()
        coordinator.assert_called_once()

    def test_trace_does_not_replay_stepper_lifecycle(self):
        evidence = self._evidence_at(2)
        with patch(
            "tw_stock_tool.paper_trading.coordinator.process_simulated_pending_fill",
            wraps=process_simulated_pending_fill,
        ) as pending_fill:
            self._bundle(evidence)
        self.assertEqual(pending_fill.call_count, 2)

    def test_one_observation_per_unique_global_timestamp(self):
        first = self._evidence_at(3, symbol="2303")
        second = self._evidence_at(4, symbol="2317")
        bundle = self._bundle(
            first,
            second,
            frames={"2317": self._frame(), "2303": self._frame()},
        )
        self.assertEqual(len(bundle.portfolio_trace.observations), 2)
        self.assertEqual(
            len({item.observed_at for item in bundle.portfolio_trace.observations}),
            2,
        )

    def test_observations_are_strictly_chronological(self):
        evidence = self._evidence_at(5, signal="HOLD")
        observations = self._bundle(
            evidence,
            frames={"2303": self._frame(offsets=(1, 2, 3))},
        ).portfolio_trace.observations
        timestamps = tuple(item.observed_at for item in observations)
        self.assertEqual(timestamps, tuple(sorted(timestamps)))

    def test_same_timestamp_snapshot_is_after_all_candidates(self):
        first = self._evidence_at(6, symbol="2303")
        second = self._evidence_at(7, symbol="2317")
        first_observation = self._bundle(
            first,
            second,
            frames={"2317": self._frame(), "2303": self._frame()},
        ).portfolio_trace.observations[0]
        self.assertEqual(first_observation.pending_order_count, 2)
        self.assertEqual(first_observation.reserved_buy_notional, 200.0)

    def test_pending_fill_is_reflected_before_observation(self):
        evidence = self._evidence_at(8)
        observations = self._bundle(evidence).portfolio_trace.observations
        self.assertEqual(observations[0].pending_order_count, 1)
        self.assertEqual(observations[1].pending_order_count, 0)
        self.assertEqual(observations[1].open_position_count, 1)
        self.assertLess(observations[1].cash, observations[0].cash)

    def test_candidate_acceptance_reserves_at_same_observation(self):
        evidence = self._evidence_at(9)
        observation = self._bundle(
            evidence,
            frames={"2303": self._frame(offsets=(1,))},
        ).portfolio_trace.observations[0]
        self.assertEqual(observation.pending_order_count, 1)
        self.assertEqual(observation.reserved_buy_notional, 100.0)
        self.assertEqual(observation.open_position_count, 0)

    def test_rejection_creates_no_pending_order_or_position(self):
        evidence = self._evidence_at(10)
        bundle = self._bundle(evidence, max_order_notional=0.01)
        observation = bundle.portfolio_trace.observations[0]
        self.assertEqual(bundle.portfolio_result.rejection_count, 1)
        self.assertEqual(observation.pending_order_count, 0)
        self.assertEqual(observation.open_position_count, 0)

    def test_final_row_enter_remains_pending(self):
        evidence = self._evidence_at(11)
        bundle = self._bundle(
            evidence,
            frames={"2303": self._frame(offsets=(1,))},
        )
        self.assertEqual(bundle.portfolio_result.fill_count, 0)
        self.assertEqual(
            bundle.portfolio_trace.observations[-1].pending_order_count, 1
        )

    def test_invalid_next_open_clears_pending_before_observation(self):
        evidence = self._evidence_at(12)
        bundle = self._bundle(
            evidence,
            frames={
                "2303": self._frame(
                    offsets=(1, 2), opens=[100.0, float("nan")]
                )
            },
        )
        self.assertEqual(bundle.portfolio_result.audit_log[-1].status.value, "skipped_invalid_open")
        self.assertEqual(
            bundle.portfolio_trace.observations[-1].pending_order_count, 0
        )
        self.assertEqual(
            bundle.portfolio_trace.observations[-1].open_position_count, 0
        )

    def test_portfolio_validation_failure_clears_pending(self):
        evidence = self._evidence_at(13)
        bundle = self._bundle(evidence, initial_cash=1.0)
        self.assertEqual(
            bundle.portfolio_result.audit_log[-1].status.value,
            "failed_portfolio_validation",
        )
        final = bundle.portfolio_trace.observations[-1]
        self.assertEqual(final.pending_order_count, 0)
        self.assertEqual(final.open_position_count, 0)

    def test_successful_buy_changes_cash_and_position(self):
        evidence = self._evidence_at(14)
        observations = self._bundle(evidence).portfolio_trace.observations
        self.assertEqual(observations[-1].positions[0].quantity, 1)
        self.assertLess(observations[-1].cash, observations[0].cash)

    def test_successful_sell_changes_cash_and_closes_position(self):
        enter = self._evidence_at(15, offset=1, signal="BUY")
        exit_evidence = self._evidence_at(16, offset=3, signal="SELL")
        bundle = self._bundle(
            enter,
            exit_evidence,
            frames={
                "2303": self._frame(
                    offsets=(1, 2, 3, 4),
                    opens=[100.0, 101.0, 120.0, 121.0],
                    closes=[100.0, 110.0, 120.0, 121.0],
                )
            },
        )
        self.assertEqual(bundle.portfolio_result.fill_count, 2)
        self.assertEqual(
            bundle.portfolio_trace.observations[-1].open_position_count, 0
        )
        self.assertGreater(
            bundle.portfolio_trace.observations[-1].cash,
            bundle.portfolio_trace.observations[1].cash,
        )

    def test_current_close_marks_position(self):
        evidence = self._evidence_at(17)
        bundle = self._bundle(
            evidence,
            frames={
                "2303": self._frame(
                    offsets=(1, 2), closes=[100.0, 150.0]
                )
            },
        )
        position = bundle.portfolio_trace.observations[-1].positions[0]
        self.assertEqual(position.mark_price, 150.0)
        self.assertEqual(position.market_value, 150.0)

    def test_sparse_symbol_retains_only_latest_observed_close(self):
        evidence = self._evidence_at(18, symbol="2317")
        bundle = self._bundle(
            evidence,
            frames={
                "2303": self._frame(
                    offsets=(3,), opens=[200.0], closes=[200.0]
                ),
                "2317": self._frame(
                    offsets=(1, 2),
                    opens=[90.0, 91.0],
                    closes=[90.0, 91.0],
                ),
            },
        )
        final_position = bundle.portfolio_trace.observations[-1].positions[0]
        self.assertEqual(final_position.symbol, "2317")
        self.assertEqual(final_position.mark_price, 91.0)

    def test_future_close_cannot_leak_into_earlier_observation(self):
        evidence = self._evidence_at(19)
        observations = self._bundle(
            evidence,
            frames={
                "2303": self._frame(
                    offsets=(1, 2, 3),
                    closes=[100.0, 110.0, 999.0],
                )
            },
        ).portfolio_trace.observations
        self.assertEqual(observations[1].positions[0].mark_price, 110.0)
        self.assertEqual(observations[2].positions[0].mark_price, 999.0)

    def test_position_marks_are_canonically_sorted(self):
        first = self._evidence_at(20, symbol="2303")
        second = self._evidence_at(21, symbol="2317")
        final = self._bundle(
            first,
            second,
            frames={"2317": self._frame(), "2303": self._frame()},
        ).portfolio_trace.observations[-1]
        self.assertEqual(
            tuple(item.symbol for item in final.positions), ("2303", "2317")
        )

    def test_observation_arithmetic_is_exact(self):
        evidence = self._evidence_at(22)
        for observation in self._bundle(evidence).portfolio_trace.observations:
            self.assertEqual(
                observation.total_market_value,
                sum(item.market_value for item in observation.positions),
            )
            self.assertEqual(
                observation.total_equity,
                observation.cash + observation.total_market_value,
            )
            self.assertEqual(
                observation.open_position_count, len(observation.positions)
            )

    def test_initial_equity_is_validated_initial_cash(self):
        evidence = self._evidence_at(23, signal="HOLD")
        bundle = self._bundle(evidence, initial_cash=123_456.0)
        self.assertEqual(bundle.portfolio_trace.initial_equity, 123_456.0)
        self.assertEqual(bundle.portfolio_result.initial_cash, 123_456.0)

    def test_final_observation_matches_terminal_result(self):
        evidence = self._evidence_at(24)
        bundle = self._bundle(evidence)
        final = bundle.portfolio_trace.observations[-1]
        result = bundle.portfolio_result
        self.assertEqual(final.cash, result.final_cash)
        self.assertEqual(final.total_market_value, result.total_market_value)
        self.assertEqual(final.total_equity, result.total_equity)
        self.assertEqual(final.open_position_count, result.open_position_count)
        self.assertEqual(final.pending_order_count, len(result.pending_orders))

    def test_trace_sha_matches_exact_canonical_portfolio_result(self):
        evidence = self._evidence_at(25)
        bundle = self._bundle(evidence)
        expected = hashlib.sha256(
            export_simulated_portfolio_trading_result_json(
                bundle.portfolio_result
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(bundle.portfolio_trace.portfolio_result_sha256, expected)

    def test_altered_result_sha_rejects(self):
        evidence = self._evidence_at(26)
        bundle = self._bundle(evidence)
        forged = replace(bundle.portfolio_trace, portfolio_result_sha256="a" * 64)
        with self.assertRaises(ForwardPaperExecutionError):
            validate_forward_portfolio_trace(
                self.fixture.activation,
                self.fixture.source,
                self._ledger(evidence),
                bundle.portfolio_result,
                forged,
            )

    def test_trace_identity_substitution_rejects(self):
        evidence = self._evidence_at(27)
        bundle = self._bundle(evidence)
        forged = replace(
            bundle.portfolio_trace,
            activation_id="623e4567-e89b-42d3-a456-426614174001",
        )
        with self.assertRaises(ForwardPaperExecutionError):
            validate_forward_portfolio_trace(
                self.fixture.activation,
                self.fixture.source,
                self._ledger(evidence),
                bundle.portfolio_result,
                forged,
            )

    def test_forged_terminal_observation_rejects_bundle(self):
        evidence = self._evidence_at(28)
        bundle = self._bundle(evidence)
        final = bundle.portfolio_trace.observations[-1]
        forged_final = replace(
            final,
            cash=final.cash + 1.0,
            total_equity=final.total_equity + 1.0,
        )
        forged_trace = replace(
            bundle.portfolio_trace,
            observations=(*bundle.portfolio_trace.observations[:-1], forged_final),
        )
        with self.assertRaises(ForwardPaperExecutionError):
            ForwardPaperExecutionReplayBundle(
                bundle.portfolio_result, forged_trace
            )

    def test_nonfinite_boolean_and_negative_trace_numbers_reject(self):
        evidence = self._evidence_at(29)
        observation = self._bundle(evidence).portfolio_trace.observations[0]
        for field, value in (
            ("cash", float("nan")),
            ("cash", True),
            ("reserved_buy_notional", -1.0),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(ForwardPortfolioTraceModelError):
                    replace(observation, **{field: value})

    def test_invalid_position_mark_contract_rejects(self):
        for kwargs in (
            {"symbol": "2303", "quantity": 0, "mark_price": 1.0, "market_value": 0.0},
            {"symbol": "2303", "quantity": 1, "mark_price": 0.0, "market_value": 0.0},
            {"symbol": "2303", "quantity": 2, "mark_price": 3.0, "market_value": 7.0},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ForwardPortfolioTraceModelError):
                    ForwardPortfolioPositionMark(**kwargs)

    def test_impossible_pending_reservation_rejects(self):
        with self.assertRaises(ForwardPortfolioTraceModelError):
            ForwardPortfolioObservation(
                observed_at="2025-04-03T00:00:00Z",
                cash=1.0,
                total_market_value=0.0,
                total_equity=1.0,
                open_position_count=0,
                pending_order_count=0,
                reserved_buy_notional=1.0,
                positions=(),
            )

    def test_duplicate_and_nonmonotonic_observation_times_reject(self):
        evidence = self._evidence_at(0)
        trace = self._bundle(evidence).portfolio_trace
        duplicate = replace(
            trace.observations[1],
            observed_at=trace.observations[0].observed_at,
        )
        with self.assertRaises(ForwardPortfolioTraceModelError):
            replace(trace, observations=(trace.observations[0], duplicate))
        with self.assertRaises(ForwardPortfolioTraceModelError):
            replace(trace, observations=tuple(reversed(trace.observations)))

    def test_trace_serialization_is_deterministic_and_stable(self):
        evidence = self._evidence_at(1)
        trace = self._bundle(evidence).portfolio_trace
        first = export_forward_portfolio_trace_json(trace)
        second = export_forward_portfolio_trace_json(trace)
        self.assertEqual(first, second)
        self.assertEqual(
            export_forward_portfolio_trace_json(
                load_forward_portfolio_trace_json(first)
            ),
            first,
        )

    def test_missing_and_unknown_json_fields_reject(self):
        evidence = self._evidence_at(2)
        payload = json.loads(
            export_forward_portfolio_trace_json(
                self._bundle(evidence).portfolio_trace
            )
        )
        missing = dict(payload)
        missing.pop("ledger_id")
        unknown = {**payload, "unknown": True}
        for forged in (missing, unknown):
            with self.assertRaises(ForwardPortfolioTraceSerializationError):
                load_forward_portfolio_trace_json(json.dumps(forged))

    def test_duplicate_key_and_nonfinite_json_reject(self):
        evidence = self._evidence_at(3)
        payload = export_forward_portfolio_trace_json(
            self._bundle(evidence).portfolio_trace
        )
        duplicate = payload.replace(
            '"schema_version": "1.0",',
            '"schema_version": "1.0",\n  "schema_version": "1.0",',
            1,
        )
        nonfinite = payload.replace('"cash": 100000.0', '"cash": NaN', 1)
        for forged in (duplicate, nonfinite):
            with self.assertRaises(ForwardPortfolioTraceSerializationError):
                load_forward_portfolio_trace_json(forged)

    def test_unknown_schema_artifact_and_container_types_reject(self):
        evidence = self._evidence_at(4)
        payload = json.loads(
            export_forward_portfolio_trace_json(
                self._bundle(evidence).portfolio_trace
            )
        )
        for field, value in (
            ("schema_version", "2.0"),
            ("artifact_type", "foreign"),
            ("observations", {}),
        ):
            forged = {**payload, field: value}
            with self.subTest(field=field):
                with self.assertRaises(ForwardPortfolioTraceSerializationError):
                    load_forward_portfolio_trace_json(json.dumps(forged))

    def test_caller_market_frames_remain_unmodified(self):
        evidence = self._evidence_at(5)
        frame = self._frame(
            signal_columns={
                "entry_signal": [False, False],
                "exit_signal": [True, True],
            }
        )
        before = frame.copy(deep=True)
        self._bundle(evidence, frames={"2303": frame})
        pd.testing.assert_frame_equal(frame, before)

    def test_production_trace_has_no_metrics_policy_broker_or_second_engine(self):
        path = Path("src/tw_stock_tool/application/forward_paper_execution.py")
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for forbidden in (
            "broker",
            "max_drawdown",
            "sharpe",
            "sortino",
            "ForwardExecutionEvidence",
        ):
            self.assertNotIn(forbidden, source)
        self.assertEqual(
            sum(
                isinstance(node, ast.Attribute)
                and node.attr == "run_simulated_portfolio_trading_result"
                for node in ast.walk(tree)
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
