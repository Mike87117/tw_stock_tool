"""Application integration for research-only Recommendation Evidence."""

from __future__ import annotations

from datetime import datetime
import math
from typing import TYPE_CHECKING, Any

import pandas as pd

from tw_stock_tool.recommendation import (
    CurrentSignalSnapshot,
    RecommendationEvidence,
    RecommendationModelError,
    build_recommendation_evidence,
)

if TYPE_CHECKING:
    from tw_stock_tool.analysis.analysis import StockAnalysis
    from tw_stock_tool.application.universe_qualification import UniverseOOSArtifact


class RecommendationApplicationError(ValueError):
    """Raised when supplied application evidence cannot be joined safely."""


_REQUIRED_SIGNAL_COLUMNS = ("Signal", "Score", "Close")
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


__all__ = [
    "RecommendationApplicationError",
    "build_recommendation_from_stock_analysis",
]
