from __future__ import annotations

from dataclasses import replace
import inspect
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from tw_stock_tool.analysis.analysis import StockAnalysis
from tw_stock_tool.application.recommendation_evidence import (
    RecommendationApplicationError,
    build_recommendation_from_stock_analysis,
    build_strategy_bound_recommendation_from_stock_analysis,
    require_strategy_bound_recommendation_evidence,
)
from tw_stock_tool.application.universe_qualification import (
    UniverseOOSArtifact,
    UniverseQualificationRequest,
    build_universe_oos_evidence,
    evaluate_universe_qualification,
)
from tw_stock_tool.recommendation import (
    RecommendationEvidence,
    StrategyBoundRecommendationEvidence,
)

EVALUATION_ID = "323e4567-e89b-42d3-a456-426614174000"
RECOMMENDATION_ID = "423e4567-e89b-42d3-a456-426614174000"
QUALIFICATION_CREATED_AT = "2025-04-01T00:00:00Z"
GENERATED_AT = "2025-04-03T00:00:00Z"
DEFAULT_SYMBOLS = ("2303", "2317", "2330", "2454", "2881")


def _qualification_frame(size: int = 70) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=size, freq="D")
    close = np.linspace(100.0, 110.0, size)
    return pd.DataFrame(
        {
            "Open": close,
            "Close": close,
            "RSI": np.full(size, 50.0),
            "Score": np.zeros(size),
            "Signal": np.full(size, "HOLD", dtype=object),
        },
        index=index,
    )


def _flat_benchmark(size: int = 70) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=size, freq="D")
    close = np.full(size, 100.0)
    return pd.DataFrame({"Open": close, "Close": close}, index=index)


def _qualification_backtest(frame, strategy, params, *args):
    return {
        "Total Return %": 10.0,
        "Sharpe Ratio": 10.0,
        "Trade Count": 1,
        "Max Drawdown %": 5.0,
    }


def _parameter_options(strategy: str) -> dict[str, tuple[int, ...]]:
    if strategy == "ma_cross":
        return {"short_window": (2, 3), "long_window": (4, 5)}
    if strategy == "rsi":
        return {"buy_below": (25, 30), "sell_above": (70, 75)}
    if strategy == "score":
        return {"buy_score": (4, 5), "sell_score": (-2, -3)}
    raise AssertionError(strategy)


def _artifact(strategy: str) -> UniverseOOSArtifact:
    request = UniverseQualificationRequest(
        evaluation_id=EVALUATION_ID,
        created_at=QUALIFICATION_CREATED_AT,
        strategy=strategy,
        symbol_data={symbol: _qualification_frame() for symbol in DEFAULT_SYMBOLS},
        benchmark_data=_flat_benchmark(),
        train_days=10,
        test_days=10,
        step_days=10,
        parameter_options=_parameter_options(strategy),
    )
    with patch(
        "tw_stock_tool.application.universe_qualification.run_strategy_backtest",
        side_effect=_qualification_backtest,
    ):
        result = evaluate_universe_qualification(request)
    artifact = build_universe_oos_evidence(result)
    if artifact.qualification.decision.state != "PAPER_READY":
        raise AssertionError("test fixture must produce PAPER_READY qualification")
    return artifact


def _current_frame(rows: int = 16, composite_signal: str = "SELL") -> pd.DataFrame:
    index = pd.date_range(end="2025-04-02", periods=rows, freq="D")
    close = np.full(rows, 10.0)
    rsi = np.full(rows, 50.0)
    score = np.zeros(rows)
    close[-1] = 20.0
    rsi[-1] = 20.0
    score[-1] = 5.0
    return pd.DataFrame(
        {
            "Open": close,
            "Close": close,
            "RSI": rsi,
            "Score": score,
            "Signal": np.full(rows, composite_signal, dtype=object),
        },
        index=index,
    )


def _analysis(frame: pd.DataFrame | None = None, composite_signal: str = "SELL") -> StockAnalysis:
    signal_df = _current_frame(composite_signal=composite_signal) if frame is None else frame
    return StockAnalysis(
        stock_id="2330",
        symbol="2330.TW",
        raw_df=pd.DataFrame(),
        indicator_df=pd.DataFrame(),
        signal_df=signal_df,
        latest=pd.Series({"Signal": "SELL", "Score": -999.0, "Close": 0.01}),
        summary={"Latest Signal": "SELL", "Tech Score": -999.0, "Latest Close": 0.01},
    )


def _selector_result(metric: float = 1.0) -> dict[str, float]:
    return {"Sharpe Ratio": metric}


def _build(
    artifact: UniverseOOSArtifact,
    analysis: StockAnalysis | None = None,
    *,
    selector=None,
) -> StrategyBoundRecommendationEvidence:
    side_effect = selector if selector is not None else (lambda *args, **kwargs: _selector_result())
    with patch(
        "tw_stock_tool.backtesting.walk_forward.run_strategy_backtest",
        side_effect=side_effect,
    ):
        return build_strategy_bound_recommendation_from_stock_analysis(
            recommendation_id=RECOMMENDATION_ID,
            generated_at=GENERATED_AT,
            universe_evidence=artifact,
            analysis=_analysis() if analysis is None else analysis,
        )


class QualifiedCurrentSignalIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ma_artifact = _artifact("ma_cross")
        cls.rsi_artifact = _artifact("rsi")
        cls.score_artifact = _artifact("score")

    def test_ma_cross_uses_qualified_strategy_not_composite_signal(self):
        evidence = _build(self.ma_artifact, _analysis(composite_signal="SELL"))
        self.assertIsInstance(evidence, StrategyBoundRecommendationEvidence)
        self.assertEqual(evidence.signal_snapshot.signal, "BUY")
        self.assertEqual(
            dict(evidence.signal_snapshot.provenance.selected_parameters),
            {"long_window": 4, "short_window": 2},
        )
        self.assertEqual(evidence.action, "ENTER")

    def test_rsi_uses_qualified_strategy_not_composite_signal(self):
        evidence = _build(self.rsi_artifact, _analysis(composite_signal="SELL"))
        self.assertEqual(evidence.signal_snapshot.signal, "BUY")
        self.assertEqual(
            dict(evidence.signal_snapshot.provenance.selected_parameters),
            {"buy_below": 25, "sell_above": 70},
        )

    def test_score_uses_score_feature_and_ignores_composite_signal(self):
        evidence = _build(self.score_artifact, _analysis(composite_signal="SELL"))
        self.assertEqual(evidence.signal_snapshot.signal, "BUY")
        self.assertEqual(
            dict(evidence.signal_snapshot.provenance.selected_parameters),
            {"buy_score": 4, "sell_score": -3},
        )

    def test_selection_excludes_row_n_and_uses_exact_train_days(self):
        analysis = _analysis()
        seen: list[pd.DataFrame] = []

        def selector(frame, *args, **kwargs):
            seen.append(frame.copy(deep=True))
            return _selector_result()

        evidence = _build(self.ma_artifact, analysis, selector=selector)
        self.assertTrue(seen)
        for frame in seen:
            self.assertEqual(len(frame), 10)
            self.assertEqual(frame.index[-1], analysis.signal_df.index[-2])
            self.assertNotIn(analysis.signal_df.index[-1], frame.index)
        self.assertEqual(evidence.signal_snapshot.provenance.selection_train_rows, 10)
        self.assertEqual(
            evidence.signal_snapshot.provenance.selection_train_end,
            "2025-04-01T00:00:00Z",
        )

    def test_first_best_tie_reconstructs_original_qualification_grid_order(self):
        seen: list[dict[str, int]] = []

        def selector(frame, strategy, params, *args):
            values = dict(params)
            seen.append(values)
            if values == {"short_window": 2, "long_window": 4}:
                raise ValueError("first candidate unavailable")
            return _selector_result()

        evidence = _build(self.ma_artifact, selector=selector)
        self.assertEqual(
            seen[:3],
            [
                {"short_window": 2, "long_window": 4},
                {"short_window": 2, "long_window": 5},
                {"short_window": 3, "long_window": 4},
            ],
        )
        self.assertEqual(
            dict(evidence.signal_snapshot.provenance.selected_parameters),
            {"long_window": 5, "short_window": 2},
        )

    def test_nonfinite_selection_metrics_fail_closed(self):
        with self.assertRaisesRegex(
            RecommendationApplicationError,
            "no qualified train parameter set succeeded",
        ):
            _build(
                self.ma_artifact,
                selector=lambda *args, **kwargs: _selector_result(float("nan")),
            )

    def test_insufficient_history_and_missing_strategy_feature_fail_closed(self):
        with self.assertRaisesRegex(RecommendationApplicationError, "enough pre-observation"):
            _build(self.ma_artifact, _analysis(_current_frame(rows=10)))
        with self.assertRaisesRegex(RecommendationApplicationError, "qualified-strategy features"):
            _build(self.rsi_artifact, _analysis(_current_frame().drop(columns=["RSI"])))

    def test_latest_summary_and_composite_signal_are_non_authoritative(self):
        first = _build(self.score_artifact, _analysis(composite_signal="BUY"))
        analysis = _analysis(composite_signal="SELL")
        forged = replace(
            analysis,
            latest=pd.Series({"Signal": "SELL", "Score": -10000.0, "Close": 0.001}),
            summary={"Latest Signal": "SELL", "Tech Score": -10000.0},
        )
        second = _build(self.score_artifact, forged)
        self.assertEqual(first, second)
        self.assertEqual(second.signal_snapshot.signal, "BUY")

    def test_strategy_signal_output_must_use_buy_hold_sell_vocabulary(self):
        def invalid_builder(strategy, frame, params):
            signal = ["HOLD"] * len(frame)
            signal[-1] = "WATCH"
            return pd.DataFrame(
                {"Close": frame["Close"].to_numpy(), "Signal": signal},
                index=frame.index,
            )

        with patch(
            "tw_stock_tool.backtesting.walk_forward.run_strategy_backtest",
            return_value=_selector_result(),
        ), patch(
            "tw_stock_tool.application.recommendation_evidence.build_strategy_signal_frame",
            side_effect=invalid_builder,
        ):
            with self.assertRaisesRegex(RecommendationApplicationError, "BUY, HOLD, or SELL"):
                build_strategy_bound_recommendation_from_stock_analysis(
                    recommendation_id=RECOMMENDATION_ID,
                    generated_at=GENERATED_AT,
                    universe_evidence=self.ma_artifact,
                    analysis=_analysis(),
                )

    def test_strategy_bound_consumer_rejects_legacy_schema_1_0(self):
        legacy = build_recommendation_from_stock_analysis(
            recommendation_id=RECOMMENDATION_ID,
            generated_at=GENERATED_AT,
            universe_evidence=self.ma_artifact,
            analysis=_analysis(),
        )
        self.assertIsInstance(legacy, RecommendationEvidence)
        with self.assertRaisesRegex(RecommendationApplicationError, "schema 1.1"):
            require_strategy_bound_recommendation_evidence(legacy)

    def test_strategy_bound_consumer_accepts_schema_1_1(self):
        evidence = _build(self.ma_artifact)
        self.assertIs(require_strategy_bound_recommendation_evidence(evidence), evidence)

    def test_caller_has_no_strategy_or_parameter_override(self):
        parameters = inspect.signature(
            build_strategy_bound_recommendation_from_stock_analysis
        ).parameters
        self.assertNotIn("strategy", parameters)
        self.assertNotIn("params", parameters)
        self.assertNotIn("parameters", parameters)

    def test_service_does_not_download_market_data(self):
        with patch(
            "tw_stock_tool.analysis.analysis.analyze_stock",
            side_effect=AssertionError("analyze_stock must not be called"),
        ), patch(
            "tw_stock_tool.data.data_loader.download_tw_stock",
            side_effect=AssertionError("download_tw_stock must not be called"),
        ), patch(
            "tw_stock_tool.backtesting.walk_forward.run_strategy_backtest",
            return_value=_selector_result(),
        ):
            evidence = build_strategy_bound_recommendation_from_stock_analysis(
                recommendation_id=RECOMMENDATION_ID,
                generated_at=GENERATED_AT,
                universe_evidence=self.ma_artifact,
                analysis=_analysis(),
            )
        self.assertEqual(evidence.action, "ENTER")


if __name__ == "__main__":
    unittest.main()
