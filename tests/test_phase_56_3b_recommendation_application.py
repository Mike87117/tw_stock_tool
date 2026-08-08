from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from tw_stock_tool.analysis.analysis import StockAnalysis
from tw_stock_tool.application.recommendation_evidence import (
    RecommendationApplicationError,
    build_recommendation_from_stock_analysis,
)
from tw_stock_tool.application.universe_qualification import (
    UniverseOOSArtifact,
    UniverseQualificationRequest,
    build_universe_oos_evidence,
    evaluate_universe_qualification,
)
from tw_stock_tool.recommendation import (
    RecommendationEvidence,
    export_recommendation_evidence_json,
    load_recommendation_evidence_json,
)


EVALUATION_ID = "123e4567-e89b-42d3-a456-426614174000"
RECOMMENDATION_ID = "223e4567-e89b-42d3-a456-426614174000"
QUALIFICATION_CREATED_AT = "2025-04-01T00:00:00Z"
SIGNAL_OBSERVED_AT = "2025-04-02T00:00:00Z"
GENERATED_AT = "2025-04-03T00:00:00Z"
DEFAULT_SYMBOLS = ("2303", "2317", "2330", "2454", "2881")


def _frame(size: int = 70) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=size, freq="D")
    values = np.arange(100.0, 100.0 + size)
    return pd.DataFrame({"Open": values, "Close": values}, index=index)


def _flat_benchmark(size: int = 70) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=size, freq="D")
    values = np.full(size, 100.0)
    return pd.DataFrame({"Open": values, "Close": values}, index=index)


def _fake_backtest(frame, strategy, params, *args):
    selected = params["short_window"] == 2
    value = 10.0 if selected else 8.0
    return {
        "Total Return %": value,
        "Sharpe Ratio": value,
        "Trade Count": 1,
        "Max Drawdown %": 5.0,
    }


def _artifact(
    *,
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS,
    bad_symbol: str | None = None,
) -> UniverseOOSArtifact:
    symbol_data = {
        symbol: pd.DataFrame() if symbol == bad_symbol else _frame()
        for symbol in symbols
    }
    request = UniverseQualificationRequest(
        evaluation_id=EVALUATION_ID,
        created_at=QUALIFICATION_CREATED_AT,
        strategy="ma_cross",
        symbol_data=symbol_data,
        benchmark_data=_flat_benchmark(),
        train_days=10,
        test_days=10,
        step_days=10,
        parameter_options={"short_window": (2, 3), "long_window": (4,)},
    )
    with patch(
        "tw_stock_tool.application.universe_qualification.run_strategy_backtest",
        side_effect=_fake_backtest,
    ):
        result = evaluate_universe_qualification(request)
    return build_universe_oos_evidence(result)


def _analysis(
    *,
    stock_id: str = "2330",
    symbol: str = "2330.TW",
    signal: str = "BUY",
    score: float = 5.0,
    close: float = 1200.0,
    index: pd.Index | None = None,
    signal_df: pd.DataFrame | None = None,
) -> StockAnalysis:
    if signal_df is None:
        signal_index = (
            pd.DatetimeIndex([pd.Timestamp(SIGNAL_OBSERVED_AT)])
            if index is None
            else index
        )
        signal_df = pd.DataFrame(
            {"Signal": [signal], "Score": [score], "Close": [close]},
            index=signal_index,
        )
    # Deliberately conflicting convenience fields prove that signal_df is authoritative.
    latest = pd.Series({"Signal": "SELL", "Score": -99.0, "Close": 1.0})
    summary = {"Latest Signal": "SELL", "Tech Score": -99.0, "Latest Close": 1.0}
    return StockAnalysis(
        stock_id=stock_id,
        symbol=symbol,
        raw_df=pd.DataFrame(),
        indicator_df=pd.DataFrame(),
        signal_df=signal_df,
        latest=latest,
        summary=summary,
    )


def _build(
    artifact: UniverseOOSArtifact | None = None,
    analysis: StockAnalysis | None = None,
    *,
    generated_at: str = GENERATED_AT,
) -> RecommendationEvidence:
    return build_recommendation_from_stock_analysis(
        recommendation_id=RECOMMENDATION_ID,
        generated_at=generated_at,
        universe_evidence=_artifact() if artifact is None else artifact,
        analysis=_analysis() if analysis is None else analysis,
    )


class RecommendationApplicationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paper_ready_artifact = _artifact()
        if cls.paper_ready_artifact.qualification.decision.state != "PAPER_READY":
            raise AssertionError("test fixture must produce PAPER_READY qualification")

    def test_real_universe_artifact_and_stock_analysis_build_evidence(self):
        evidence = _build(self.paper_ready_artifact, _analysis())
        self.assertIsInstance(evidence, RecommendationEvidence)
        self.assertEqual(evidence.source_qualification_evaluation_id, EVALUATION_ID)
        self.assertEqual(evidence.signal_snapshot.symbol, "2330")
        self.assertEqual(evidence.signal_snapshot.observed_at, SIGNAL_OBSERVED_AT)

    def test_paper_ready_buy_uses_existing_action_gate_and_enters(self):
        evidence = _build(self.paper_ready_artifact, _analysis(signal="BUY"))
        self.assertEqual(evidence.promotion_state, "PAPER_READY")
        self.assertEqual(evidence.action, "ENTER")

    def test_canonical_universe_symbol_wins_over_resolved_provider_symbol(self):
        evidence = _build(self.paper_ready_artifact, _analysis(symbol="2330.TW"))
        self.assertEqual(evidence.signal_snapshot.symbol, "2330")

    def test_unrelated_analysis_symbol_fails_closed(self):
        with self.assertRaisesRegex(RecommendationApplicationError, "does not match"):
            _build(self.paper_ready_artifact, _analysis(stock_id="9999", symbol="9999.TW"))

    def test_ambiguous_requested_and_resolved_symbol_membership_fails_closed(self):
        artifact = _artifact(symbols=("2303", "2330", "2330.TW", "2454", "2881"))
        with self.assertRaisesRegex(RecommendationApplicationError, "multiple"):
            _build(artifact, _analysis(stock_id="2330", symbol="2330.TW"))

    def test_target_without_successful_oos_evaluation_fails_closed(self):
        artifact = _artifact(bad_symbol="2330")
        target = next(item for item in artifact.symbols if item.symbol == "2330")
        self.assertFalse(target.evaluated)
        with self.assertRaisesRegex(RecommendationApplicationError, "no successful OOS"):
            _build(artifact, _analysis())

    def test_empty_signal_frame_fails_closed(self):
        analysis = _analysis(signal_df=pd.DataFrame())
        with self.assertRaisesRegex(RecommendationApplicationError, "non-empty"):
            _build(self.paper_ready_artifact, analysis)

    def test_missing_required_signal_columns_fail_closed(self):
        for missing in ("Signal", "Score", "Close"):
            with self.subTest(missing=missing):
                frame = pd.DataFrame(
                    {"Signal": ["BUY"], "Score": [5.0], "Close": [1200.0]},
                    index=pd.DatetimeIndex([pd.Timestamp(SIGNAL_OBSERVED_AT)]),
                ).drop(columns=[missing])
                with self.assertRaisesRegex(RecommendationApplicationError, "missing required"):
                    _build(self.paper_ready_artifact, _analysis(signal_df=frame))

    def test_non_datetime_and_nat_final_indexes_fail_closed(self):
        cases = (
            pd.Index(["2025-04-02"]),
            pd.DatetimeIndex([pd.NaT]),
        )
        for index in cases:
            with self.subTest(index=index):
                with self.assertRaises(RecommendationApplicationError):
                    _build(self.paper_ready_artifact, _analysis(index=index))

    def test_latest_and_summary_cannot_override_signal_df(self):
        analysis = _analysis(signal="BUY", score=5.0, close=1200.0)
        evidence = _build(self.paper_ready_artifact, analysis)
        self.assertEqual(evidence.signal_snapshot.signal, "BUY")
        self.assertEqual(evidence.signal_snapshot.score, 5.0)
        self.assertEqual(evidence.signal_snapshot.latest_close, 1200.0)
        self.assertEqual(evidence.action, "ENTER")

    def test_generated_at_cannot_predate_qualification_creation(self):
        with self.assertRaisesRegex(RecommendationApplicationError, "qualification created_at"):
            _build(
                self.paper_ready_artifact,
                _analysis(),
                generated_at="2025-03-31T23:59:59Z",
            )

    def test_generated_at_cannot_predate_signal_observation(self):
        with self.assertRaisesRegex(RecommendationApplicationError, "signal observed_at"):
            _build(
                self.paper_ready_artifact,
                _analysis(),
                generated_at="2025-04-01T12:00:00Z",
            )

    def test_service_does_not_call_analysis_or_data_downloaders(self):
        with patch(
            "tw_stock_tool.analysis.analysis.analyze_stock",
            side_effect=AssertionError("analyze_stock must not be called"),
        ), patch(
            "tw_stock_tool.data.data_loader.download_tw_stock",
            side_effect=AssertionError("download_tw_stock must not be called"),
        ):
            evidence = _build(self.paper_ready_artifact, _analysis())
        self.assertEqual(evidence.action, "ENTER")

    def test_recommendation_round_trip_remains_deterministic(self):
        evidence = _build(self.paper_ready_artifact, _analysis())
        first = export_recommendation_evidence_json(evidence)
        loaded = load_recommendation_evidence_json(first)
        second = export_recommendation_evidence_json(loaded)
        self.assertEqual(first, second)
        self.assertEqual(loaded, evidence)

    def test_timezone_aware_signal_index_is_canonicalized_to_utc(self):
        local = pd.DatetimeIndex([pd.Timestamp("2025-04-02T08:00:00+08:00")])
        evidence = _build(self.paper_ready_artifact, _analysis(index=local))
        self.assertEqual(evidence.signal_snapshot.observed_at, SIGNAL_OBSERVED_AT)

    def test_convenience_field_replacement_does_not_change_evidence(self):
        analysis = _analysis()
        forged = replace(
            analysis,
            latest=pd.Series({"Signal": "SELL", "Score": -1000.0, "Close": 0.01}),
            summary={"Latest Signal": "SELL"},
        )
        original = _build(self.paper_ready_artifact, analysis)
        rebuilt = _build(self.paper_ready_artifact, forged)
        self.assertEqual(original, rebuilt)


if __name__ == "__main__":
    unittest.main()
