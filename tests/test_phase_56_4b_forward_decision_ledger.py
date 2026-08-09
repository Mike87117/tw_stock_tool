from __future__ import annotations

import ast
from dataclasses import fields, replace
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from tw_stock_tool.application.forward_decision_ledger import (
    ForwardDecisionLedgerError,
    append_forward_decision,
    create_forward_decision_ledger,
)
from tw_stock_tool.application.forward_paper_activation import (
    build_forward_paper_activation,
)
from tw_stock_tool.application.universe_qualification import (
    UniverseOOSArtifact,
    UniverseQualificationRequest,
    build_universe_oos_evidence,
    evaluate_universe_qualification,
)
from tw_stock_tool.forward_paper import (
    ForwardDecisionRecord,
    ForwardPaperSerializationError,
    deserialize_forward_decision_ledger,
    export_forward_decision_ledger_json,
    export_forward_paper_activation_json,
    load_forward_decision_ledger_json,
    serialize_forward_decision_ledger,
)
from tw_stock_tool.qualification import TAIWAN_EQUITY_DAILY_V1
from tw_stock_tool.recommendation import (
    CurrentSignalSnapshot,
    StrategyBoundSignalSnapshot,
    StrategySignalProvenance,
    build_recommendation_evidence,
    build_strategy_bound_recommendation_evidence,
    export_strategy_bound_recommendation_evidence_json,
)


EVALUATION_ID = "523e4567-e89b-42d3-a456-426614174000"
OTHER_EVALUATION_ID = "523e4567-e89b-42d3-a456-426614174001"
ACTIVATION_ID = "623e4567-e89b-42d3-a456-426614174000"
LEDGER_ID = "723e4567-e89b-42d3-a456-426614174000"
RECOMMENDATION_IDS = tuple(
    f"823e4567-e89b-42d3-a456-4266141740{index:02d}" for index in range(30)
)
GOOD_SYMBOLS = ("2303", "2317", "2330", "2454", "2881")


def _format(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _shift(value: str, days: int) -> str:
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return _format(parsed + timedelta(days=days))


def _cutoff(source: UniverseOOSArtifact) -> str:
    values = [
        window.test_end for symbol in source.symbols for window in symbol.windows
    ]
    values.extend(
        item.index_end
        for item in source.resolved_configuration.benchmark_descriptors
        if item.index_end is not None
    )
    return max(values)


def _source(
    evaluation_id: str = EVALUATION_ID,
    *,
    strategy: str = "ma_cross",
    selected_return: float = 10.0,
) -> UniverseOOSArtifact:
    index = pd.date_range("2025-01-01", periods=70, freq="D")
    close = np.linspace(100.0, 110.0, len(index))
    frame = pd.DataFrame({"Open": close, "Close": close}, index=index)
    benchmark = pd.DataFrame(
        {"Open": np.full(len(index), 100.0), "Close": np.full(len(index), 100.0)},
        index=index,
    )
    if strategy == "ma_cross":
        options = {"short_window": (2, 3), "long_window": (4, 5)}
        preferred = {"short_window": 2, "long_window": 4}
    else:
        options = {"buy_below": (30, 35), "sell_above": (65, 70)}
        preferred = {"buy_below": 30, "sell_above": 65}

    def fake_backtest(data, strategy_name, params, *args):
        value = selected_return if dict(params) == preferred else selected_return * 0.8
        return {
            "Total Return %": value,
            "Sharpe Ratio": value,
            "Trade Count": 1,
            "Max Drawdown %": 5.0,
        }

    request = UniverseQualificationRequest(
        evaluation_id=evaluation_id,
        created_at="2025-04-01T00:00:00Z",
        strategy=strategy,
        symbol_data={symbol: frame for symbol in GOOD_SYMBOLS},
        benchmark_data=benchmark,
        train_days=10,
        test_days=10,
        step_days=10,
        parameter_options=options,
        policy=TAIWAN_EQUITY_DAILY_V1,
    )
    with patch(
        "tw_stock_tool.application.universe_qualification.run_strategy_backtest",
        side_effect=fake_backtest,
    ):
        return build_universe_oos_evidence(evaluate_universe_qualification(request))


def _evidence(
    source: UniverseOOSArtifact,
    *,
    recommendation_id: str = RECOMMENDATION_IDS[0],
    symbol: str = "2303",
    observed_at: str | None = None,
    signal: str = "BUY",
    selected_parameters=None,
):
    observed_at = observed_at or _shift(_cutoff(source), 1)
    train_end = _shift(observed_at, -1)
    provenance = StrategySignalProvenance(
        qualification_evaluation_id=source.evaluation_id,
        strategy_id=source.qualification.request.strategy.strategy_id,
        selected_parameters=(
            source.resolved_configuration.parameter_grid[0]
            if selected_parameters is None
            else selected_parameters
        ),
        selection_rule="train_only_parameter_search_v1",
        selection_metric=source.resolved_configuration.sort_by,
        selection_train_start=_shift(train_end, -9),
        selection_train_end=train_end,
        selection_train_rows=source.resolved_configuration.train_days,
    )
    snapshot = StrategyBoundSignalSnapshot(
        symbol=symbol,
        observed_at=observed_at,
        signal=signal,
        latest_close=1200.0,
        provenance=provenance,
    )
    return build_strategy_bound_recommendation_evidence(
        recommendation_id=recommendation_id,
        generated_at=_shift(observed_at, 1),
        qualification=source.qualification,
        signal_snapshot=snapshot,
    )


def _forged_copy(value, **changes):
    forged = object.__new__(type(value))
    for item in fields(value):
        object.__setattr__(
            forged, item.name, changes.get(item.name, getattr(value, item.name))
        )
    return forged


class ForwardDecisionLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = _source()
        cls.other_source = _source(OTHER_EVALUATION_ID)
        cls.same_id_different_source = _source(selected_return=12.0)
        cls.rsi_source = _source(strategy="rsi")
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

    def test_create_empty_ledger_from_real_activation_and_source(self):
        self.assertEqual(self.empty.decisions, ())
        self.assertEqual(self.empty.activation_id, self.activation.activation_id)
        self.assertEqual(
            self.empty.qualification_sha256, self.activation.qualification_sha256
        )

    def test_activation_sha_is_exact_canonical_export_sha(self):
        expected = hashlib.sha256(
            export_forward_paper_activation_json(self.activation).encode("utf-8")
        ).hexdigest()
        self.assertEqual(self.empty.activation_sha256, expected)

    def test_append_real_schema_11_decision_after_cutoff(self):
        evidence = _evidence(self.source)
        ledger = append_forward_decision(
            self.empty, self.activation, self.source, evidence
        )
        self.assertEqual(len(ledger.decisions), 1)
        self.assertEqual(ledger.decisions[0].recommendation_id, evidence.recommendation_id)

    def test_schema_10_recommendation_evidence_rejects(self):
        observed_at = _shift(self.activation.qualification_cutoff, 1)
        legacy = build_recommendation_evidence(
            recommendation_id=RECOMMENDATION_IDS[1],
            generated_at=_shift(observed_at, 1),
            qualification=self.source.qualification,
            signal_snapshot=CurrentSignalSnapshot(
                symbol="2303",
                observed_at=observed_at,
                signal="BUY",
                score=5.0,
                latest_close=1200.0,
            ),
        )
        with self.assertRaisesRegex(ForwardDecisionLedgerError, "schema 1.1"):
            append_forward_decision(
                self.empty, self.activation, self.source, legacy
            )

    def test_observation_equal_to_cutoff_rejects(self):
        evidence = _evidence(
            self.source, observed_at=self.activation.qualification_cutoff
        )
        with self.assertRaisesRegex(ForwardDecisionLedgerError, "strictly after"):
            append_forward_decision(
                self.empty, self.activation, self.source, evidence
            )

    def test_observation_before_cutoff_rejects(self):
        evidence = _evidence(
            self.source, observed_at=_shift(self.activation.qualification_cutoff, -1)
        )
        with self.assertRaisesRegex(ForwardDecisionLedgerError, "strictly after"):
            append_forward_decision(
                self.empty, self.activation, self.source, evidence
            )

    def test_symbol_outside_frozen_universe_rejects(self):
        evidence = _evidence(self.source, symbol="9999")
        with self.assertRaisesRegex(ForwardDecisionLedgerError, "qualified universe"):
            append_forward_decision(
                self.empty, self.activation, self.source, evidence
            )

    def test_strategy_mismatch_rejects(self):
        evidence = _evidence(self.rsi_source)
        with self.assertRaisesRegex(ForwardDecisionLedgerError, "strategy mismatch"):
            append_forward_decision(
                self.empty, self.activation, self.source, evidence
            )

    def test_qualification_evaluation_id_mismatch_rejects(self):
        evidence = _evidence(self.other_source)
        with self.assertRaisesRegex(ForwardDecisionLedgerError, "evaluation ID mismatch"):
            append_forward_decision(
                self.empty, self.activation, self.source, evidence
            )

    def test_same_id_different_embedded_qualification_content_rejects(self):
        evidence = _evidence(self.same_id_different_source)
        with self.assertRaisesRegex(
            ForwardDecisionLedgerError, "qualification content"
        ):
            append_forward_decision(
                self.empty, self.activation, self.source, evidence
            )

    def test_source_universe_digest_mismatch_rejects(self):
        with self.assertRaisesRegex(ForwardDecisionLedgerError, "does not match"):
            create_forward_decision_ledger(
                self.activation,
                self.same_id_different_source,
                ledger_id=LEDGER_ID,
                created_at="2025-04-02T00:00:00Z",
            )

    def test_source_numeric_representation_drift_rejects(self):
        metrics = _forged_copy(
            self.source.qualification.request.metrics, total_return_pct=10
        )
        request = _forged_copy(self.source.qualification.request, metrics=metrics)
        qualification = _forged_copy(self.source.qualification, request=request)
        forged = _forged_copy(self.source, qualification=qualification)
        with self.assertRaisesRegex(ForwardDecisionLedgerError, "canonical serialized"):
            create_forward_decision_ledger(
                self.activation,
                forged,
                ledger_id=LEDGER_ID,
                created_at="2025-04-02T00:00:00Z",
            )

    def test_altered_activation_content_rejects_existing_ledger_lock(self):
        altered = replace(self.activation, created_at="2025-04-03T00:00:00Z")
        with self.assertRaisesRegex(ForwardDecisionLedgerError, "identity lock"):
            append_forward_decision(
                self.empty, altered, self.source, _evidence(self.source)
            )

    def test_same_timestamp_different_symbols_accept_in_symbol_order(self):
        observed_at = _shift(self.activation.qualification_cutoff, 1)
        first = _evidence(
            self.source,
            recommendation_id=RECOMMENDATION_IDS[2],
            observed_at=observed_at,
            symbol="2303",
        )
        second = _evidence(
            self.source,
            recommendation_id=RECOMMENDATION_IDS[3],
            observed_at=observed_at,
            symbol="2317",
        )
        one = append_forward_decision(
            self.empty, self.activation, self.source, first
        )
        two = append_forward_decision(one, self.activation, self.source, second)
        self.assertEqual(
            tuple((item.observed_at, item.symbol) for item in two.decisions),
            ((observed_at, "2303"), (observed_at, "2317")),
        )

    def test_same_timestamp_reverse_symbol_order_rejects(self):
        observed_at = _shift(self.activation.qualification_cutoff, 1)
        first = _evidence(
            self.source,
            recommendation_id=RECOMMENDATION_IDS[4],
            observed_at=observed_at,
            symbol="2317",
        )
        second = _evidence(
            self.source,
            recommendation_id=RECOMMENDATION_IDS[5],
            observed_at=observed_at,
            symbol="2303",
        )
        ledger = append_forward_decision(
            self.empty, self.activation, self.source, first
        )
        with self.assertRaisesRegex(ForwardDecisionLedgerError, "backward"):
            append_forward_decision(
                ledger, self.activation, self.source, second
            )

    def test_duplicate_observation_symbol_key_rejects(self):
        first = _evidence(self.source, recommendation_id=RECOMMENDATION_IDS[6])
        second = _evidence(self.source, recommendation_id=RECOMMENDATION_IDS[7])
        ledger = append_forward_decision(
            self.empty, self.activation, self.source, first
        )
        with self.assertRaisesRegex(ForwardDecisionLedgerError, "duplicate.*key"):
            append_forward_decision(
                ledger, self.activation, self.source, second
            )

    def test_backward_chronology_append_rejects(self):
        later = _evidence(
            self.source,
            recommendation_id=RECOMMENDATION_IDS[8],
            observed_at=_shift(self.activation.qualification_cutoff, 2),
        )
        earlier = _evidence(
            self.source,
            recommendation_id=RECOMMENDATION_IDS[9],
            observed_at=_shift(self.activation.qualification_cutoff, 1),
        )
        ledger = append_forward_decision(
            self.empty, self.activation, self.source, later
        )
        with self.assertRaisesRegex(ForwardDecisionLedgerError, "backward"):
            append_forward_decision(
                ledger, self.activation, self.source, earlier
            )

    def test_duplicate_recommendation_id_rejects(self):
        first = _evidence(self.source, recommendation_id=RECOMMENDATION_IDS[10])
        second = _evidence(
            self.source,
            recommendation_id=RECOMMENDATION_IDS[10],
            observed_at=_shift(self.activation.qualification_cutoff, 2),
        )
        ledger = append_forward_decision(
            self.empty, self.activation, self.source, first
        )
        with self.assertRaisesRegex(ForwardDecisionLedgerError, "duplicate recommendation ID"):
            append_forward_decision(
                ledger, self.activation, self.source, second
            )

    def test_duplicate_recommendation_sha_rejects(self):
        evidence = _evidence(
            self.source,
            recommendation_id=RECOMMENDATION_IDS[11],
            observed_at=_shift(self.activation.qualification_cutoff, 2),
            symbol="2317",
        )
        digest = hashlib.sha256(
            export_strategy_bound_recommendation_evidence_json(evidence).encode(
                "utf-8"
            )
        ).hexdigest()
        dummy = ForwardDecisionRecord(
            recommendation_id=RECOMMENDATION_IDS[12],
            recommendation_sha256=digest,
            observed_at=_shift(self.activation.qualification_cutoff, 1),
            generated_at=_shift(self.activation.qualification_cutoff, 2),
            symbol="2303",
            signal="BUY",
            action="ENTER",
            qualification_evaluation_id=self.activation.qualification_evaluation_id,
            strategy_id=self.activation.strategy_id,
            selected_parameters=self.source.resolved_configuration.parameter_grid[0],
        )
        ledger = replace(self.empty, decisions=(dummy,))
        with self.assertRaisesRegex(ForwardDecisionLedgerError, "duplicate recommendation SHA"):
            append_forward_decision(
                ledger, self.activation, self.source, evidence
            )

    def test_per_decision_sha_equals_canonical_schema_11_export(self):
        evidence = _evidence(self.source, recommendation_id=RECOMMENDATION_IDS[13])
        ledger = append_forward_decision(
            self.empty, self.activation, self.source, evidence
        )
        expected = hashlib.sha256(
            export_strategy_bound_recommendation_evidence_json(evidence).encode(
                "utf-8"
            )
        ).hexdigest()
        self.assertEqual(ledger.decisions[0].recommendation_sha256, expected)

    def test_selected_parameters_may_change_between_valid_decisions(self):
        first = _evidence(
            self.source,
            recommendation_id=RECOMMENDATION_IDS[14],
            selected_parameters=self.source.resolved_configuration.parameter_grid[0],
        )
        second = _evidence(
            self.source,
            recommendation_id=RECOMMENDATION_IDS[15],
            observed_at=_shift(self.activation.qualification_cutoff, 2),
            selected_parameters=self.source.resolved_configuration.parameter_grid[1],
        )
        one = append_forward_decision(
            self.empty, self.activation, self.source, first
        )
        two = append_forward_decision(one, self.activation, self.source, second)
        self.assertNotEqual(
            two.decisions[0].selected_parameters,
            two.decisions[1].selected_parameters,
        )

    def test_action_is_copied_without_local_derivation(self):
        evidence = _evidence(
            self.source,
            recommendation_id=RECOMMENDATION_IDS[16],
            signal="SELL",
        )
        ledger = append_forward_decision(
            self.empty, self.activation, self.source, evidence
        )
        self.assertEqual(evidence.action, "EXIT")
        self.assertEqual(ledger.decisions[0].action, evidence.action)
        source = (
            Path(__file__).parents[1]
            / "src"
            / "tw_stock_tool"
            / "application"
            / "forward_decision_ledger.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("derive_recommendation_action", source)

    def test_previous_ledger_remains_unchanged_after_append(self):
        ledger = append_forward_decision(
            self.empty, self.activation, self.source, _evidence(self.source)
        )
        self.assertEqual(self.empty.decisions, ())
        self.assertEqual(len(ledger.decisions), 1)
        self.assertIsNot(ledger, self.empty)

    def test_recommendation_numeric_representation_drift_rejects(self):
        evidence = _evidence(self.source)
        snapshot = _forged_copy(evidence.signal_snapshot, latest_close=1200)
        forged = _forged_copy(evidence, signal_snapshot=snapshot)
        with self.assertRaisesRegex(ForwardDecisionLedgerError, "canonical serialized"):
            append_forward_decision(
                self.empty, self.activation, self.source, forged
            )

    def test_strict_missing_and_unknown_ledger_fields_reject(self):
        payload = serialize_forward_decision_ledger(self.empty)
        missing = dict(payload)
        missing.pop("activation_id")
        unknown = dict(payload, extra=True)
        for value in (missing, unknown):
            with self.subTest(keys=tuple(value)):
                with self.assertRaises(ForwardPaperSerializationError):
                    deserialize_forward_decision_ledger(value)

    def test_strict_duplicate_nonfinite_and_container_types_reject(self):
        text = export_forward_decision_ledger_json(self.empty)
        duplicate = text.replace(
            '"schema_version": "1.0",',
            '"schema_version": "1.0",\n  "schema_version": "1.0",',
        )
        nonfinite = text.replace(
            f'"activation_sha256": "{self.empty.activation_sha256}"',
            '"activation_sha256": NaN',
        )
        for value in (duplicate, nonfinite):
            with self.subTest(value=value[:40]):
                with self.assertRaises(ForwardPaperSerializationError):
                    load_forward_decision_ledger_json(value)
        payload = serialize_forward_decision_ledger(self.empty)
        payload["decisions"] = ()
        with self.assertRaises(ForwardPaperSerializationError):
            deserialize_forward_decision_ledger(payload)

    def test_ledger_serialization_round_trip_is_byte_stable(self):
        ledger = append_forward_decision(
            self.empty, self.activation, self.source, _evidence(self.source)
        )
        first = export_forward_decision_ledger_json(ledger)
        loaded = load_forward_decision_ledger_json(first)
        self.assertEqual(loaded, ledger)
        self.assertEqual(export_forward_decision_ledger_json(loaded), first)
        self.assertEqual(json.loads(first), serialize_forward_decision_ledger(loaded))

    def test_pure_forward_paper_domain_has_no_forbidden_imports(self):
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
            imports = []
            for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    imports.extend(item.name for item in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            for module in imports:
                self.assertFalse(
                    module.startswith(forbidden), f"forbidden import {module} in {source}"
                )

    def test_production_diff_has_no_order_fill_or_runtime_coupling(self):
        root = Path(__file__).parents[1] / "src" / "tw_stock_tool"
        paths = (
            root / "forward_paper" / "decision_models.py",
            root / "forward_paper" / "decision_serialization.py",
            root / "application" / "forward_decision_ledger.py",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for forbidden in ("SimulatedOrder", "SimulatedFill", "paper_trading"):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
