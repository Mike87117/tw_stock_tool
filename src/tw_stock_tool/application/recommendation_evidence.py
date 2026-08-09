"""Application integration for research-only Recommendation Evidence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import math
from typing import TYPE_CHECKING, Any

import pandas as pd

from tw_stock_tool.backtesting.strategies import build_strategy_signal_frame
from tw_stock_tool.recommendation import (
    STRATEGY_SIGNAL_SELECTION_RULE,
    CurrentSignalSnapshot,
    RecommendationEvidence,
    RecommendationModelError,
    StrategyBoundRecommendationError,
    StrategyBoundRecommendationEvidence,
    StrategyBoundSignalSnapshot,
    StrategySignalProvenance,
    build_recommendation_evidence,
    build_strategy_bound_recommendation_evidence,
)

if TYPE_CHECKING:
    from tw_stock_tool.analysis.analysis import StockAnalysis
    from tw_stock_tool.application.universe_qualification import UniverseOOSArtifact


class RecommendationApplicationError(ValueError):
    """Raised when supplied application evidence cannot be joined safely."""


_REQUIRED_SIGNAL_COLUMNS = ("Signal", "Score", "Close")
_STRATEGY_PARAMETER_KEYS = {
    "ma_cross": ("short_window", "long_window"),
    "rsi": ("buy_below", "sell_above"),
    "score": ("buy_score", "sell_score"),
}
_STRATEGY_FEATURE_COLUMNS = {
    "ma_cross": ("Open", "Close"),
    "rsi": ("Open", "Close", "RSI"),
    "score": ("Open", "Close", "Score"),
}
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _clean_identity(name: str, value: Any) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise RecommendationApplicationError(f"{name} must be a clean non-blank string")
    return value


def _canonical_timestamp(value: Any, name: str) -> str:
    if type(value) is str:
        try:
            parsed = datetime.strptime(value, _TIMESTAMP_FORMAT)
        except ValueError as exc:
            raise RecommendationApplicationError(
                f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
            ) from exc
        if parsed.strftime(_TIMESTAMP_FORMAT) != value:
            raise RecommendationApplicationError(
                f"{name} must match exact UTC format YYYY-MM-DDTHH:MM:SSZ"
            )
        return value

    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise RecommendationApplicationError(
            f"{name} must be a valid pandas timestamp"
        ) from exc
    if pd.isna(timestamp):
        raise RecommendationApplicationError(f"{name} must not be NaT")
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    if timestamp != timestamp.floor("s"):
        raise RecommendationApplicationError(
            f"{name} must not lose sub-second precision"
        )
    return timestamp.strftime(_TIMESTAMP_FORMAT)


def _finite_number(value: Any, name: str) -> float:
    if pd.api.types.is_bool(value):
        raise RecommendationApplicationError(f"{name} must be numeric, not bool")
    if isinstance(value, str):
        raise RecommendationApplicationError(f"{name} must be numeric, not str")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RecommendationApplicationError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise RecommendationApplicationError(f"{name} must be finite")
    return result


def _finite_strategy_feature(value: Any, name: str) -> float:
    if pd.api.types.is_bool(value):
        raise RecommendationApplicationError(f"{name} must be numeric, not bool")
    if isinstance(value, (str, bytes, bytearray)):
        raise RecommendationApplicationError(
            f"{name} must be numeric, not {type(value).__name__}"
        )
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RecommendationApplicationError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise RecommendationApplicationError(f"{name} must be finite")
    return result


def _validated_inputs(
    universe_evidence: UniverseOOSArtifact,
    analysis: StockAnalysis,
) -> tuple[UniverseOOSArtifact, StockAnalysis]:
    # Lazy imports keep this module itself from owning market-data/provider imports.
    from tw_stock_tool.analysis.analysis import StockAnalysis as RuntimeStockAnalysis
    from tw_stock_tool.application.universe_qualification import (
        UniverseOOSArtifact as RuntimeUniverseOOSArtifact,
    )

    if not isinstance(universe_evidence, RuntimeUniverseOOSArtifact):
        raise RecommendationApplicationError(
            "universe_evidence must be a UniverseOOSArtifact"
        )
    if not isinstance(analysis, RuntimeStockAnalysis):
        raise RecommendationApplicationError("analysis must be a StockAnalysis")
    return universe_evidence, analysis


def _matched_universe_symbol(
    universe_evidence: UniverseOOSArtifact,
    analysis: StockAnalysis,
) -> str:
    stock_id = _clean_identity("analysis.stock_id", analysis.stock_id)
    resolved_symbol = _clean_identity("analysis.symbol", analysis.symbol)
    identities = tuple(dict.fromkeys((stock_id, resolved_symbol)))
    matches = tuple(
        item for item in universe_evidence.symbols if item.symbol in identities
    )
    if not matches:
        raise RecommendationApplicationError(
            "analysis does not match any symbol in the qualification universe"
        )
    if len(matches) != 1:
        raise RecommendationApplicationError(
            "analysis identities match multiple qualification-universe symbols"
        )
    target = matches[0]
    if not target.evaluated or target.valid_windows <= 0:
        raise RecommendationApplicationError(
            "matched qualification-universe symbol has no successful OOS evaluation"
        )
    if not any(window.valid for window in target.windows):
        raise RecommendationApplicationError(
            "matched qualification-universe symbol has no valid OOS window"
        )
    return target.symbol


def _signal_snapshot(
    analysis: StockAnalysis,
    *,
    canonical_symbol: str,
) -> CurrentSignalSnapshot:
    signal_df = analysis.signal_df
    if not isinstance(signal_df, pd.DataFrame) or signal_df.empty:
        raise RecommendationApplicationError(
            "analysis.signal_df must be a non-empty pandas DataFrame"
        )
    missing = [column for column in _REQUIRED_SIGNAL_COLUMNS if column not in signal_df]
    if missing:
        raise RecommendationApplicationError(
            f"analysis.signal_df is missing required columns: {missing}"
        )
    if not isinstance(signal_df.index, pd.DatetimeIndex):
        raise RecommendationApplicationError(
            "analysis.signal_df must use a DatetimeIndex"
        )
    if not signal_df.index.is_monotonic_increasing:
        raise RecommendationApplicationError(
            "analysis.signal_df DatetimeIndex must be monotonic increasing"
        )

    observed_at = _canonical_timestamp(signal_df.index[-1], "signal observed_at")
    row = signal_df.iloc[-1]
    signal = str(row["Signal"])
    score = _finite_number(row["Score"], "signal score")
    latest_close = _finite_number(row["Close"], "signal latest_close")
    try:
        return CurrentSignalSnapshot(
            symbol=canonical_symbol,
            observed_at=observed_at,
            signal=signal,
            score=score,
            latest_close=latest_close,
        )
    except RecommendationModelError as exc:
        raise RecommendationApplicationError(
            f"current signal snapshot violates Recommendation contract: {exc}"
        ) from exc


def _strategy_feature_frame(
    analysis: StockAnalysis,
    *,
    strategy: str,
) -> pd.DataFrame:
    signal_df = analysis.signal_df
    if not isinstance(signal_df, pd.DataFrame) or signal_df.empty:
        raise RecommendationApplicationError(
            "analysis.signal_df must be a non-empty pandas DataFrame"
        )
    if strategy not in _STRATEGY_FEATURE_COLUMNS:
        raise RecommendationApplicationError(
            f"qualified strategy is unsupported for current signal: {strategy!r}"
        )
    if not isinstance(signal_df.index, pd.DatetimeIndex):
        raise RecommendationApplicationError(
            "analysis.signal_df must use a DatetimeIndex"
        )
    if not signal_df.index.is_unique:
        raise RecommendationApplicationError(
            "analysis.signal_df DatetimeIndex must be unique for strategy selection"
        )
    if not signal_df.index.is_monotonic_increasing:
        raise RecommendationApplicationError(
            "analysis.signal_df DatetimeIndex must be monotonic increasing"
        )
    if bool(signal_df.index.hasnans):
        raise RecommendationApplicationError(
            "analysis.signal_df DatetimeIndex must not contain NaT"
        )
    required = _STRATEGY_FEATURE_COLUMNS[strategy]
    missing = [column for column in required if column not in signal_df]
    if missing:
        raise RecommendationApplicationError(
            f"analysis.signal_df is missing qualified-strategy features: {missing}"
        )

    clean = signal_df.copy(deep=True)
    for column in required:
        normalized = [
            _finite_strategy_feature(value, f"strategy feature {column}")
            for value in clean[column].tolist()
        ]
        clean[column] = normalized
    return clean


def _parameter_key(value: Mapping[str, int]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(value.items()))


def _ordered_qualified_parameter_grid(resolved_configuration: Any) -> tuple[dict[str, int], ...]:
    strategy = resolved_configuration.strategy
    if strategy not in _STRATEGY_PARAMETER_KEYS:
        raise RecommendationApplicationError(
            f"qualified strategy is unsupported for parameter selection: {strategy!r}"
        )
    expected_keys = set(_STRATEGY_PARAMETER_KEYS[strategy])
    artifact_grid = resolved_configuration.parameter_grid
    if type(artifact_grid) is not tuple or not artifact_grid:
        raise RecommendationApplicationError(
            "qualification resolved parameter grid must be a non-empty tuple"
        )

    options: dict[str, set[int]] = {key: set() for key in expected_keys}
    artifact_keys: set[tuple[tuple[str, int], ...]] = set()
    for index, item in enumerate(artifact_grid):
        if not isinstance(item, Mapping) or set(item) != expected_keys:
            raise RecommendationApplicationError(
                f"qualification parameter_grid[{index}] does not match strategy keys"
            )
        clean: dict[str, int] = {}
        for key in sorted(item):
            value = item[key]
            if type(key) is not str or type(value) is not int:
                raise RecommendationApplicationError(
                    "qualification parameter grid must use exact str/int values"
                )
            clean[key] = value
            options[key].add(value)
        artifact_keys.add(_parameter_key(clean))

    from tw_stock_tool.backtesting.walk_forward import parameter_grid

    kwargs: dict[str, tuple[int, ...] | None] = {
        "ma_short_windows": None,
        "ma_long_windows": None,
        "rsi_buy_below": None,
        "rsi_sell_above": None,
        "score_buy": None,
        "score_sell": None,
    }
    if strategy == "ma_cross":
        kwargs["ma_short_windows"] = tuple(sorted(options["short_window"]))
        kwargs["ma_long_windows"] = tuple(sorted(options["long_window"]))
    elif strategy == "rsi":
        kwargs["rsi_buy_below"] = tuple(sorted(options["buy_below"]))
        kwargs["rsi_sell_above"] = tuple(sorted(options["sell_above"]))
    else:
        kwargs["score_buy"] = tuple(sorted(options["buy_score"]))
        kwargs["score_sell"] = tuple(sorted(options["sell_score"]))

    rebuilt = tuple(parameter_grid(strategy, **kwargs))
    rebuilt_keys = {_parameter_key(item) for item in rebuilt}
    if len(rebuilt) != len(artifact_grid) or rebuilt_keys != artifact_keys:
        raise RecommendationApplicationError(
            "qualification parameter grid cannot be reconstructed exactly"
        )
    return rebuilt


def _select_qualified_parameters(
    train: pd.DataFrame,
    *,
    resolved_configuration: Any,
) -> dict[str, int]:
    from tw_stock_tool.backtesting.walk_forward import (
        run_strategy_backtest,
        sort_train_metric,
    )

    best: tuple[float, dict[str, int]] | None = None
    errors: list[str] = []
    for params in _ordered_qualified_parameter_grid(resolved_configuration):
        try:
            result = run_strategy_backtest(
                train,
                resolved_configuration.strategy,
                params,
                resolved_configuration.stop_loss_pct,
                resolved_configuration.take_profit_pct,
                resolved_configuration.max_hold_days,
                resolved_configuration.position_size,
                resolved_configuration.initial_capital,
                resolved_configuration.fee_rate,
                resolved_configuration.tax_rate,
                resolved_configuration.interval,
            )
            metric = sort_train_metric(result, resolved_configuration.sort_by)
            if not math.isfinite(metric):
                raise ValueError("train selection metric is non-finite")
            if best is None or metric > best[0]:
                best = (metric, dict(params))
        except Exception as exc:
            errors.append(f"{dict(params)}: {exc}")
    if best is None:
        detail = "; ".join(errors) if errors else "no candidates"
        raise RecommendationApplicationError(
            f"no qualified train parameter set succeeded: {detail}"
        )
    return best[1]


def _strategy_bound_signal_snapshot(
    universe_evidence: UniverseOOSArtifact,
    analysis: StockAnalysis,
    *,
    canonical_symbol: str,
) -> StrategyBoundSignalSnapshot:
    resolved = universe_evidence.resolved_configuration
    frame = _strategy_feature_frame(analysis, strategy=resolved.strategy)
    train_days = resolved.train_days
    if len(frame) < train_days + 1:
        raise RecommendationApplicationError(
            "analysis.signal_df lacks enough pre-observation rows for qualified selection"
        )

    observed_index = frame.index[-1]
    train = frame.iloc[-(train_days + 1):-1].copy(deep=True)
    if len(train) != train_days:
        raise RecommendationApplicationError(
            "qualified selection frame must contain exactly train_days rows"
        )
    try:
        if not bool(train.index[-1] < observed_index):
            raise RecommendationApplicationError(
                "selection train end must strictly predate current observation"
            )
    except TypeError as exc:
        raise RecommendationApplicationError(
            "selection/current chronology cannot be proved"
        ) from exc

    selected = _select_qualified_parameters(
        train,
        resolved_configuration=resolved,
    )
    try:
        strategy_df = build_strategy_signal_frame(
            resolved.strategy,
            frame,
            selected,
        )
    except Exception as exc:
        raise RecommendationApplicationError(
            f"qualified current strategy signal failed: {exc}"
        ) from exc
    if (
        not isinstance(strategy_df, pd.DataFrame)
        or strategy_df.empty
        or "Signal" not in strategy_df
        or "Close" not in strategy_df
        or not strategy_df.index.equals(frame.index)
    ):
        raise RecommendationApplicationError(
            "qualified strategy signal output is incomplete or misaligned"
        )

    row = strategy_df.iloc[-1]
    signal = row["Signal"]
    if type(signal) is not str or signal not in ("BUY", "HOLD", "SELL"):
        raise RecommendationApplicationError(
            "qualified current strategy signal must be BUY, HOLD, or SELL"
        )
    latest_close = _finite_strategy_feature(
        row["Close"],
        "qualified signal latest_close",
    )
    observed_at = _canonical_timestamp(observed_index, "signal observed_at")
    train_start = _canonical_timestamp(
        train.index[0],
        "selection train start",
    )
    train_end = _canonical_timestamp(
        train.index[-1],
        "selection train end",
    )
    try:
        provenance = StrategySignalProvenance(
            qualification_evaluation_id=universe_evidence.evaluation_id,
            strategy_id=resolved.strategy,
            selected_parameters=selected,
            selection_rule=STRATEGY_SIGNAL_SELECTION_RULE,
            selection_metric=resolved.sort_by,
            selection_train_start=train_start,
            selection_train_end=train_end,
            selection_train_rows=len(train),
        )
        return StrategyBoundSignalSnapshot(
            symbol=canonical_symbol,
            observed_at=observed_at,
            signal=signal,
            latest_close=latest_close,
            provenance=provenance,
        )
    except StrategyBoundRecommendationError as exc:
        raise RecommendationApplicationError(
            f"strategy-bound signal provenance is invalid: {exc}"
        ) from exc


def _validate_chronology(
    *,
    generated_at: str,
    qualification_created_at: str,
    observed_at: str,
) -> str:
    generated = _canonical_timestamp(generated_at, "generated_at")
    qualification_created = _canonical_timestamp(
        qualification_created_at,
        "qualification created_at",
    )
    observed = _canonical_timestamp(observed_at, "signal observed_at")
    generated_dt = datetime.strptime(generated, _TIMESTAMP_FORMAT)
    if generated_dt < datetime.strptime(qualification_created, _TIMESTAMP_FORMAT):
        raise RecommendationApplicationError(
            "generated_at cannot predate qualification created_at"
        )
    if generated_dt < datetime.strptime(observed, _TIMESTAMP_FORMAT):
        raise RecommendationApplicationError(
            "generated_at cannot predate signal observed_at"
        )
    return generated


def build_recommendation_from_stock_analysis(
    *,
    recommendation_id: str,
    generated_at: str,
    universe_evidence: UniverseOOSArtifact,
    analysis: StockAnalysis,
) -> RecommendationEvidence:
    """Join Phase 56.2 evidence and an existing StockAnalysis without I/O."""
    universe_evidence, analysis = _validated_inputs(universe_evidence, analysis)
    canonical_symbol = _matched_universe_symbol(universe_evidence, analysis)
    snapshot = _signal_snapshot(analysis, canonical_symbol=canonical_symbol)
    generated = _validate_chronology(
        generated_at=generated_at,
        qualification_created_at=universe_evidence.qualification.request.created_at,
        observed_at=snapshot.observed_at,
    )
    try:
        return build_recommendation_evidence(
            recommendation_id=recommendation_id,
            generated_at=generated,
            qualification=universe_evidence.qualification,
            signal_snapshot=snapshot,
        )
    except RecommendationModelError as exc:
        raise RecommendationApplicationError(
            f"Recommendation Evidence construction failed: {exc}"
        ) from exc


def build_strategy_bound_recommendation_from_stock_analysis(
    *,
    recommendation_id: str,
    generated_at: str,
    universe_evidence: UniverseOOSArtifact,
    analysis: StockAnalysis,
) -> StrategyBoundRecommendationEvidence:
    """Derive schema-1.1 evidence from the qualified strategy without I/O."""
    universe_evidence, analysis = _validated_inputs(universe_evidence, analysis)
    canonical_symbol = _matched_universe_symbol(universe_evidence, analysis)
    snapshot = _strategy_bound_signal_snapshot(
        universe_evidence,
        analysis,
        canonical_symbol=canonical_symbol,
    )
    generated = _validate_chronology(
        generated_at=generated_at,
        qualification_created_at=universe_evidence.qualification.request.created_at,
        observed_at=snapshot.observed_at,
    )
    try:
        return build_strategy_bound_recommendation_evidence(
            recommendation_id=recommendation_id,
            generated_at=generated,
            qualification=universe_evidence.qualification,
            signal_snapshot=snapshot,
        )
    except StrategyBoundRecommendationError as exc:
        raise RecommendationApplicationError(
            f"Strategy-bound Recommendation Evidence construction failed: {exc}"
        ) from exc


def require_strategy_bound_recommendation_evidence(
    value: Any,
) -> StrategyBoundRecommendationEvidence:
    """Fail closed when a strategy-bound consumer is handed legacy schema 1.0."""
    if not isinstance(value, StrategyBoundRecommendationEvidence):
        raise RecommendationApplicationError(
            "strategy-bound consumer requires Recommendation Evidence schema 1.1"
        )
    return value


__all__ = [
    "RecommendationApplicationError",
    "build_recommendation_from_stock_analysis",
    "build_strategy_bound_recommendation_from_stock_analysis",
    "require_strategy_bound_recommendation_evidence",
]
