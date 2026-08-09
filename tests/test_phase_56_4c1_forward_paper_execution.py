from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path
import json
import unittest
from unittest.mock import patch

import pandas as pd

from test_phase_56_4b_forward_decision_ledger import (
    ACTIVATION_ID,
    LEDGER_ID,
    RECOMMENDATION_IDS,
    _cutoff,
    _evidence,
    _shift,
    _source,
)
from tw_stock_tool.application.forward_decision_ledger import (
    append_forward_decision,
    create_forward_decision_ledger,
)
from tw_stock_tool.application.forward_paper_activation import (
    build_forward_paper_activation,
)
from tw_stock_tool.application.forward_paper_execution import (
    ForwardPaperExecutionError,
    run_forward_paper_execution_replay,
)
from tw_stock_tool.forward_paper import ForwardDecisionRecord
from tw_stock_tool.paper_trading import portfolio_engine
from tw_stock_tool.paper_trading.portfolio_serialization import (
    export_simulated_portfolio_trading_result_json,
)
from tw_stock_tool.recommendation import (
    CurrentSignalSnapshot,
    build_recommendation_evidence,
)


class ForwardPaperExecutionReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = _source()
        cls.activation = build_forward_paper_activation(
            cls.source,
            activation_id=ACTIVATION_ID,
            created_at="2025-04-02T00:00:00Z",
        )
        cls.empty = create_forward_decision_ledger(
            cls.activation,
            cls.source,
            ledger_id=LEDGER_ID,
            created_at="2025-04-02T00:00:00Z",
        )

    def _evidence_at(self, index: int, *, symbol: str = "2303", offset: int = 1, signal: str = "BUY"):
        return _evidence(
            self.source,
            recommendation_id=RECOMMENDATION_IDS[index],
            symbol=symbol,
            observed_at=_shift(_cutoff(self.source), offset),
            signal=signal,
        )

    def _ledger(self, *evidence):
        ledger = self.empty
        for item in evidence:
            ledger = append_forward_decision(
                ledger, self.activation, self.source, item
            )
        return ledger

    def _frame(
        self,
        *,
        offsets=(1, 2),
        opens=None,
        closes=None,
        index=None,
        signal_columns=None,
    ):
        if index is None:
            index = pd.to_datetime(
                [_shift(_cutoff(self.source), offset) for offset in offsets]
            )
        opens = [100.0 + index for index in range(len(index))] if opens is None else opens
        closes = [100.0 + index for index in range(len(index))] if closes is None else closes
        data = {"Open": opens, "Close": closes}
        if signal_columns is not None:
            data.update(signal_columns)
        return pd.DataFrame(data, index=index)

    def _run(self, ledger, evidence, frames=None, **kwargs):
        if frames is None:
            frames = {"2303": self._frame()}
        return run_forward_paper_execution_replay(
            self.activation,
            self.source,
            ledger,
            {item.recommendation_id: item for item in evidence},
            frames,
            initial_cash=100_000.0,
            quantity_per_trade=1,
            **kwargs,
        )

    def test_valid_bundle_executes_through_existing_facade(self):
        evidence = self._evidence_at(0)
        result = self._run(self._ledger(evidence), (evidence,))
        self.assertEqual(result.order_count, 1)
        self.assertEqual(result.fill_count, 1)

    def test_schema_10_evidence_rejects_before_runtime(self):
        evidence = self._evidence_at(1)
        ledger = self._ledger(evidence)
        legacy = build_recommendation_evidence(
            recommendation_id=evidence.recommendation_id,
            generated_at=evidence.generated_at,
            qualification=self.source.qualification,
            signal_snapshot=CurrentSignalSnapshot(
                symbol=evidence.signal_snapshot.symbol,
                observed_at=evidence.signal_snapshot.observed_at,
                signal="BUY",
                score=1.0,
                latest_close=100.0,
            ),
        )
        with patch.object(portfolio_engine, "run_simulated_portfolio_trading_result") as runtime:
            with self.assertRaises(ForwardPaperExecutionError):
                self._run(ledger, (legacy,))
        runtime.assert_not_called()

    def test_missing_evidence_rejects(self):
        evidence = self._evidence_at(2)
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(self._ledger(evidence), ())

    def test_extra_orphan_evidence_rejects(self):
        evidence = self._evidence_at(3)
        orphan = self._evidence_at(4, offset=2)
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(self._ledger(evidence), (evidence, orphan))

    def test_recommendation_sha_mismatch_rejects(self):
        evidence = self._evidence_at(5)
        ledger = self._ledger(evidence)
        forged_record = replace(ledger.decisions[0], recommendation_sha256="a" * 64)
        forged_ledger = replace(ledger, decisions=(forged_record,))
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(forged_ledger, (evidence,))

    def test_same_id_changed_evidence_content_rejects(self):
        evidence = self._evidence_at(6)
        changed = self._evidence_at(6, signal="SELL")
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(self._ledger(evidence), (changed,))

    def test_forged_ledger_copied_fields_cannot_execute(self):
        evidence = self._evidence_at(7)
        ledger = self._ledger(evidence)
        forged_record = replace(ledger.decisions[0], action="EXIT")
        forged_ledger = replace(ledger, decisions=(forged_record,))
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(forged_ledger, (evidence,))

    def test_poisoned_history_attack_set_rejects(self):
        dummy = ForwardDecisionRecord(
            recommendation_id=RECOMMENDATION_IDS[8],
            recommendation_sha256="b" * 64,
            observed_at=_shift(self.activation.qualification_cutoff, 1),
            generated_at=_shift(self.activation.qualification_cutoff, 2),
            symbol="9999",
            signal="BUY",
            action="ENTER",
            qualification_evaluation_id=self.activation.qualification_evaluation_id,
            strategy_id=self.activation.strategy_id,
            selected_parameters=self.source.resolved_configuration.parameter_grid[0],
        )
        poisoned = replace(self.empty, decisions=(dummy,))
        evidence = self._evidence_at(9, offset=2)
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(poisoned, (evidence,))

    def test_foreign_market_frame_rejects(self):
        evidence = self._evidence_at(10)
        frames = {"2303": self._frame(), "9999": self._frame()}
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(self._ledger(evidence), (evidence,), frames)

    def test_missing_decision_symbol_frame_rejects(self):
        evidence = self._evidence_at(11, symbol="2317")
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(self._ledger(evidence), (evidence,))

    def test_non_datetime_index_rejects(self):
        evidence = self._evidence_at(12)
        frame = self._frame(index=["2025-04-03", "2025-04-04"])
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(self._ledger(evidence), (evidence,), {"2303": frame})

    def test_duplicate_index_rejects(self):
        evidence = self._evidence_at(13)
        ts = pd.Timestamp(_shift(_cutoff(self.source), 1))
        frame = self._frame(index=pd.DatetimeIndex([ts, ts]))
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(self._ledger(evidence), (evidence,), {"2303": frame})

    def test_non_monotonic_index_rejects(self):
        evidence = self._evidence_at(14)
        frame = self._frame(index=pd.to_datetime([_shift(_cutoff(self.source), 2), _shift(_cutoff(self.source), 1)]))
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(self._ledger(evidence), (evidence,), {"2303": frame})

    def test_nat_index_rejects(self):
        evidence = self._evidence_at(15)
        frame = self._frame(index=pd.DatetimeIndex([pd.NaT, pd.Timestamp(_shift(_cutoff(self.source), 1))]))
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(self._ledger(evidence), (evidence,), {"2303": frame})

    def test_subsecond_index_rejects(self):
        evidence = self._evidence_at(16)
        frame = self._frame(index=pd.to_datetime([_shift(_cutoff(self.source), 1)]) + pd.Timedelta(milliseconds=1))
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(self._ledger(evidence), (evidence,), {"2303": frame})

    def test_timezone_normalization_collision_rejects(self):
        evidence = self._evidence_at(17)
        frame = self._frame(index=pd.to_datetime([_shift(_cutoff(self.source), 1), _shift(_cutoff(self.source), 1)]))
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(self._ledger(evidence), (evidence,), {"2303": frame})

    def test_market_row_at_cutoff_rejects(self):
        evidence = self._evidence_at(18)
        frame = self._frame(index=pd.to_datetime([self.activation.qualification_cutoff, _shift(self.activation.qualification_cutoff, 1)]))
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(self._ledger(evidence), (evidence,), {"2303": frame})

    def test_decision_timestamp_missing_from_frame_rejects(self):
        evidence = self._evidence_at(19, offset=2)
        frame = self._frame(offsets=(1, 3))
        with self.assertRaises(ForwardPaperExecutionError):
            self._run(self._ledger(evidence), (evidence,), {"2303": frame})

    def test_caller_frames_are_not_mutated(self):
        evidence = self._evidence_at(20)
        frame = self._frame(signal_columns={"entry_signal": [False, False], "exit_signal": [True, False]})
        before = frame.copy(deep=True)
        self._run(self._ledger(evidence), (evidence,), {"2303": frame})
        pd.testing.assert_frame_equal(frame, before)

    def test_existing_signal_columns_are_erased_before_overlay(self):
        evidence = self._evidence_at(21)
        frame = self._frame(signal_columns={"entry_signal": [False, False], "exit_signal": [True, True]})
        with patch.object(portfolio_engine, "run_simulated_portfolio_trading_result", wraps=portfolio_engine.run_simulated_portfolio_trading_result) as runtime:
            self._run(self._ledger(evidence), (evidence,), {"2303": frame})
        prepared = runtime.call_args.args[0]
        self.assertEqual(prepared["2303"]["exit_signal"].tolist(), [False, False])
        self.assertEqual(prepared["2303"]["entry_signal"].tolist(), [True, False])

    def test_enter_maps_only_to_entry_signal(self):
        evidence = self._evidence_at(22, signal="BUY")
        with patch.object(portfolio_engine, "run_simulated_portfolio_trading_result", wraps=portfolio_engine.run_simulated_portfolio_trading_result) as runtime:
            self._run(self._ledger(evidence), (evidence,))
        prepared = runtime.call_args.args[0]["2303"]
        self.assertEqual(prepared["entry_signal"].tolist(), [True, False])
        self.assertEqual(prepared["exit_signal"].tolist(), [False, False])

    def test_exit_maps_only_to_exit_signal(self):
        evidence = self._evidence_at(23, signal="SELL")
        with patch.object(portfolio_engine, "run_simulated_portfolio_trading_result", wraps=portfolio_engine.run_simulated_portfolio_trading_result) as runtime:
            self._run(self._ledger(evidence), (evidence,))
        prepared = runtime.call_args.args[0]["2303"]
        self.assertEqual(prepared["entry_signal"].tolist(), [False, False])
        self.assertEqual(prepared["exit_signal"].tolist(), [True, False])

    def test_hold_maps_to_no_signal(self):
        evidence = self._evidence_at(24, signal="HOLD")
        with patch.object(portfolio_engine, "run_simulated_portfolio_trading_result", wraps=portfolio_engine.run_simulated_portfolio_trading_result) as runtime:
            self._run(self._ledger(evidence), (evidence,))
        prepared = runtime.call_args.args[0]["2303"]
        self.assertEqual(prepared["entry_signal"].tolist(), [False, False])
        self.assertEqual(prepared["exit_signal"].tolist(), [False, False])

    def test_same_timestamp_symbols_use_one_global_replay(self):
        first = self._evidence_at(0, symbol="2303")
        second = self._evidence_at(1, symbol="2317")
        ledger = self._ledger(first, second)
        frames = {"2303": self._frame(), "2317": self._frame()}
        with patch.object(portfolio_engine, "run_simulated_portfolio_trading_result", wraps=portfolio_engine.run_simulated_portfolio_trading_result) as runtime:
            self._run(ledger, (first, second), frames)
        runtime.assert_called_once()

    def test_enter_uses_existing_pending_next_bar_fill_lifecycle(self):
        evidence = self._evidence_at(2)
        result = self._run(self._ledger(evidence), (evidence,))
        self.assertEqual(result.order_count, 1)
        self.assertEqual(result.fill_count, 1)

    def test_exit_after_enter_uses_existing_portfolio_state(self):
        enter = self._evidence_at(3, offset=1, signal="BUY")
        exit_evidence = self._evidence_at(4, offset=3, signal="SELL")
        result = self._run(
            self._ledger(enter, exit_evidence),
            (enter, exit_evidence),
            {"2303": self._frame(offsets=(1, 2, 3, 4))},
        )
        self.assertEqual(result.order_count, 2)
        self.assertEqual(result.fill_count, 2)

    def test_last_row_enter_remains_pending(self):
        evidence = self._evidence_at(5)
        result = self._run(
            self._ledger(evidence),
            (evidence,),
            {"2303": self._frame(offsets=(1,))},
        )
        self.assertEqual(result.order_count, 1)
        self.assertEqual(result.fill_count, 0)
        self.assertEqual(len(result.pending_orders), 1)

    def test_invalid_next_open_keeps_existing_skipped_fill_audit(self):
        evidence = self._evidence_at(6)
        result = self._run(
            self._ledger(evidence),
            (evidence,),
            {"2303": self._frame(offsets=(1, 2), opens=[100.0, float("nan")])},
        )
        self.assertEqual(result.audit_log[-1].status.value, "skipped_invalid_open")

    def test_boolean_open_rejects_before_runtime(self):
        evidence = self._evidence_at(6)
        with patch.object(portfolio_engine, "run_simulated_portfolio_trading_result") as runtime:
            with self.assertRaises(ForwardPaperExecutionError):
                self._run(
                    self._ledger(evidence),
                    (evidence,),
                    {"2303": self._frame(offsets=(1, 2), opens=[100.0, True])},
                )
        runtime.assert_not_called()

    def test_numeric_string_open_rejects_before_runtime(self):
        evidence = self._evidence_at(7)
        with patch.object(portfolio_engine, "run_simulated_portfolio_trading_result") as runtime:
            with self.assertRaises(ForwardPaperExecutionError):
                self._run(
                    self._ledger(evidence),
                    (evidence,),
                    {"2303": self._frame(offsets=(1, 2), opens=[100.0, "101.5"])},
                )
        runtime.assert_not_called()

    def test_existing_risk_limit_rejection_remains_visible(self):
        evidence = self._evidence_at(7)
        result = self._run(
            self._ledger(evidence),
            (evidence,),
            max_order_notional=0.01,
        )
        self.assertGreaterEqual(result.rejection_count, 1)

    def test_trusted_qualification_fee_tax_are_passed_to_runtime(self):
        evidence = self._evidence_at(8)
        with patch.object(portfolio_engine, "run_simulated_portfolio_trading_result", wraps=portfolio_engine.run_simulated_portfolio_trading_result) as runtime:
            self._run(self._ledger(evidence), (evidence,))
        kwargs = runtime.call_args.kwargs
        self.assertEqual(kwargs["fee_rate"], self.source.resolved_configuration.fee_rate)
        self.assertEqual(kwargs["tax_rate"], self.source.resolved_configuration.tax_rate)

    def test_final_close_is_used_for_last_prices(self):
        evidence = self._evidence_at(9)
        frame = self._frame(closes=[100.0, 123.45])
        with patch.object(portfolio_engine, "run_simulated_portfolio_trading_result", wraps=portfolio_engine.run_simulated_portfolio_trading_result) as runtime:
            self._run(self._ledger(evidence), (evidence,), {"2303": frame})
        self.assertEqual(runtime.call_args.kwargs["last_prices"], {"2303": 123.45})

    def test_invalid_final_close_rejects_before_runtime(self):
        evidence = self._evidence_at(10)
        frame = self._frame(closes=[100.0, float("nan")])
        with patch.object(portfolio_engine, "run_simulated_portfolio_trading_result") as runtime:
            with self.assertRaises(ForwardPaperExecutionError):
                self._run(self._ledger(evidence), (evidence,), {"2303": frame})
        runtime.assert_not_called()

    def test_strategy_metadata_is_deterministic_json_identity(self):
        evidence = self._evidence_at(11)
        with patch.object(portfolio_engine, "run_simulated_portfolio_trading_result", wraps=portfolio_engine.run_simulated_portfolio_trading_result) as runtime:
            self._run(self._ledger(evidence), (evidence,))
        metadata = runtime.call_args.kwargs["strategy_metadata"]
        json.dumps(metadata, sort_keys=True, allow_nan=False)
        self.assertEqual(metadata["activation_id"], self.activation.activation_id)
        self.assertEqual(metadata["ledger_id"], self.empty.ledger_id)
        self.assertEqual(metadata["qualification_evaluation_id"], self.source.evaluation_id)

    def test_same_inputs_have_equivalent_result_serialization(self):
        evidence = self._evidence_at(12)
        ledger = self._ledger(evidence)
        frames = {"2303": self._frame()}
        first = self._run(ledger, (evidence,), frames)
        second = self._run(ledger, (evidence,), frames)
        self.assertEqual(
            export_simulated_portfolio_trading_result_json(first),
            export_simulated_portfolio_trading_result_json(second),
        )

    def test_production_adapter_has_no_second_order_fill_engine(self):
        path = Path("src/tw_stock_tool/application/forward_paper_execution.py")
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertNotIn("SimulatedOrder", source)
        self.assertNotIn("SimulatedFill", source)
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
