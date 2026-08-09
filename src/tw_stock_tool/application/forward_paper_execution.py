"""No-I/O replay of trusted forward decisions through the paper runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from numbers import Real
from typing import Any

import pandas as pd

from tw_stock_tool.application.forward_decision_ledger import (
    ForwardDecisionLedgerError,
    _validated_activation_source,
    _validated_evidence,
    _validated_ledger,
    _validate_ledger_records,
)
from tw_stock_tool.application.recommendation_evidence import (
    RecommendationApplicationError,
    _canonical_timestamp,
)
from tw_stock_tool.application.universe_qualification import UniverseOOSArtifact
from tw_stock_tool.forward_paper.decision_models import ForwardDecisionLedger
from tw_stock_tool.forward_paper.decision_serialization import (
    export_forward_decision_ledger_json,
)
from tw_stock_tool.forward_paper.models import ForwardPaperActivation
from tw_stock_tool.forward_paper.portfolio_trace_models import (
    ForwardPortfolioObservation,
    ForwardPortfolioPositionMark,
    ForwardPortfolioTrace,
    ForwardPortfolioTraceModelError,
)
from tw_stock_tool.forward_paper.portfolio_trace_serialization import (
    export_forward_portfolio_trace_json,
    load_forward_portfolio_trace_json,
)
from tw_stock_tool.qualification import export_strategy_qualification_json
from tw_stock_tool.recommendation import StrategyBoundRecommendationEvidence
from tw_stock_tool.paper_trading import portfolio_engine
from tw_stock_tool.paper_trading.portfolio_results import (
    SimulatedPortfolioTradingResult,
)
from tw_stock_tool.paper_trading.portfolio_serialization import (
    export_simulated_portfolio_trading_result_json,
    load_simulated_portfolio_trading_result_json,
)
from tw_stock_tool.paper_trading.runtime import SimulatedPaperTradingRuntimeState


class ForwardPaperExecutionError(ValueError):
    """Raised when a forward replay input cannot pass its trust boundary."""


_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _trusted_portfolio_result(
    result: SimulatedPortfolioTradingResult,
) -> tuple[SimulatedPortfolioTradingResult, str]:
    if type(result) is not SimulatedPortfolioTradingResult:
        raise ForwardPaperExecutionError(
            "portfolio_result must be an exact SimulatedPortfolioTradingResult"
        )
    try:
        canonical = export_simulated_portfolio_trading_result_json(result)
        loaded = load_simulated_portfolio_trading_result_json(canonical)
        if export_simulated_portfolio_trading_result_json(loaded) != canonical:
            raise ForwardPaperExecutionError(
                "portfolio result canonical round-trip drift"
            )
    except ForwardPaperExecutionError:
        raise
    except Exception as exc:
        raise ForwardPaperExecutionError(
            f"portfolio result canonical validation failed: {exc}"
        ) from exc
    return loaded, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_trace_result_pair(
    result: SimulatedPortfolioTradingResult,
    trace: ForwardPortfolioTrace,
) -> None:
    if type(trace) is not ForwardPortfolioTrace:
        raise ForwardPaperExecutionError(
            "portfolio_trace must be an exact ForwardPortfolioTrace"
        )
    trusted_result, result_sha256 = _trusted_portfolio_result(result)
    if trace.portfolio_result_sha256 != result_sha256:
        raise ForwardPaperExecutionError("portfolio-result SHA mismatch")
    if trace.initial_equity != trusted_result.initial_cash:
        raise ForwardPaperExecutionError("trace initial equity mismatch")
    final = trace.observations[-1]
    expected_positions = tuple(
        (item.symbol, item.quantity, item.last_price, item.market_value)
        for item in trusted_result.positions
        if item.quantity > 0
    )
    actual_positions = tuple(
        (item.symbol, item.quantity, item.mark_price, item.market_value)
        for item in final.positions
    )
    expected_terminal = (
        trusted_result.final_cash,
        trusted_result.total_market_value,
        trusted_result.total_equity,
        trusted_result.open_position_count,
        len(trusted_result.pending_orders),
        sum(item.reserved_buy_notional for item in trusted_result.pending_orders),
        expected_positions,
    )
    actual_terminal = (
        final.cash,
        final.total_market_value,
        final.total_equity,
        final.open_position_count,
        final.pending_order_count,
        final.reserved_buy_notional,
        actual_positions,
    )
    if actual_terminal != expected_terminal:
        raise ForwardPaperExecutionError(
            "final trace observation does not match terminal portfolio result"
        )


@dataclass(frozen=True, slots=True)
class ForwardPaperExecutionReplayBundle:
    portfolio_result: SimulatedPortfolioTradingResult
    portfolio_trace: ForwardPortfolioTrace

    def __post_init__(self) -> None:
        _validate_trace_result_pair(self.portfolio_result, self.portfolio_trace)


class _ForwardPortfolioTraceCollector:
    def __init__(self) -> None:
        self._marks: dict[str, float] = {}
        self.observations: list[ForwardPortfolioObservation] = []

    def __call__(
        self,
        timestamp: Any,
        runtime_state: SimulatedPaperTradingRuntimeState,
        closes_at_timestamp: Mapping[str, Any],
    ) -> None:
        if type(runtime_state) is not SimulatedPaperTradingRuntimeState:
            raise ForwardPaperExecutionError(
                "observation runtime must be an exact runtime state"
            )
        for symbol in sorted(closes_at_timestamp):
            close = closes_at_timestamp[symbol]
            if not _finite_positive(close):
                raise ForwardPaperExecutionError(
                    "observation Close must be finite and strictly positive"
                )
            self._marks[symbol] = float(close)
        try:
            observed_at = _canonical_timestamp(timestamp, "observation timestamp")
        except RecommendationApplicationError as exc:
            raise ForwardPaperExecutionError(str(exc)) from exc
        positions: list[ForwardPortfolioPositionMark] = []
        for symbol in sorted(runtime_state.portfolio.positions):
            position = runtime_state.portfolio.positions[symbol]
            if position.quantity <= 0:
                continue
            if symbol not in self._marks:
                raise ForwardPaperExecutionError(
                    f"open position {symbol!r} has no observed Close mark"
                )
            mark = self._marks[symbol]
            positions.append(
                ForwardPortfolioPositionMark(
                    symbol=symbol,
                    quantity=position.quantity,
                    mark_price=mark,
                    market_value=position.quantity * mark,
                )
            )
        total_market_value = sum(item.market_value for item in positions)
        cash = float(runtime_state.portfolio.cash)
        try:
            self.observations.append(
                ForwardPortfolioObservation(
                    observed_at=observed_at,
                    cash=cash,
                    total_market_value=total_market_value,
                    total_equity=cash + total_market_value,
                    open_position_count=len(positions),
                    pending_order_count=len(runtime_state.pending_orders),
                    reserved_buy_notional=runtime_state.total_reserved_buy_notional,
                    positions=tuple(positions),
                )
            )
        except ForwardPortfolioTraceModelError as exc:
            raise ForwardPaperExecutionError(
                f"portfolio observation validation failed: {exc}"
            ) from exc


def _finite_positive(value: Any) -> bool:
    if isinstance(value, bool) or type(value).__name__ in ("bool", "bool_"):
        return False
    if not isinstance(value, Real):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(number) and number > 0.0


def _canonical_index_timestamp(value: str) -> pd.Timestamp:
    return pd.Timestamp(datetime.strptime(value, _TIMESTAMP_FORMAT))


def _canonicalize_market_frame(
    symbol: str,
    frame: pd.DataFrame,
    qualification_cutoff: str,
) -> tuple[pd.DataFrame, dict[str, pd.Timestamp]]:
    if not isinstance(frame, pd.DataFrame):
        raise ForwardPaperExecutionError(
            f"forward market frame for {symbol!r} must be a pandas DataFrame"
        )
    if frame.empty:
        raise ForwardPaperExecutionError(
            f"forward market frame for {symbol!r} must not be empty"
        )
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ForwardPaperExecutionError(
            f"forward market frame for {symbol!r} must use a pandas.DatetimeIndex"
        )
    if frame.index.hasnans:
        raise ForwardPaperExecutionError(
            f"forward market frame for {symbol!r} must not contain NaT"
        )
    if not frame.index.is_unique:
        raise ForwardPaperExecutionError(
            f"forward market frame for {symbol!r} must have a unique index"
        )
    if not frame.index.is_monotonic_increasing:
        raise ForwardPaperExecutionError(
            f"forward market frame for {symbol!r} must have a monotonic index"
        )
    for column in ("Open", "Close"):
        if column not in frame.columns:
            raise ForwardPaperExecutionError(
                f"forward market frame for {symbol!r} must contain {column!r}"
            )
    try:
        canonical = tuple(
            _canonical_timestamp(value, f"{symbol}.index[{index}]")
            for index, value in enumerate(frame.index)
        )
    except RecommendationApplicationError as exc:
        raise ForwardPaperExecutionError(str(exc)) from exc
    if len(set(canonical)) != len(canonical):
        raise ForwardPaperExecutionError(
            f"forward market frame for {symbol!r} has a canonical timestamp collision"
        )
    if canonical != tuple(sorted(canonical)):
        raise ForwardPaperExecutionError(
            f"forward market frame for {symbol!r} is not canonically ordered"
        )
    if any(value <= qualification_cutoff for value in canonical):
        raise ForwardPaperExecutionError(
            f"forward market frame for {symbol!r} contains a row at or before qualification_cutoff"
        )
    for index, value in enumerate(frame["Open"]):
        if isinstance(value, bool) or type(value).__name__ in ("bool", "bool_"):
            raise ForwardPaperExecutionError(
                f"forward market frame for {symbol!r} Open[{index}] must be a numeric Real"
            )
        if not isinstance(value, Real):
            raise ForwardPaperExecutionError(
                f"forward market frame for {symbol!r} Open[{index}] must be a numeric Real"
            )
    if not any(_finite_positive(value) for value in frame["Open"]):
        raise ForwardPaperExecutionError(
            f"forward market frame for {symbol!r} has no finite positive Open"
        )
    if not all(_finite_positive(value) for value in frame["Close"]):
        raise ForwardPaperExecutionError(
            f"forward market frame for {symbol!r} must have finite positive Close values"
        )

    normalized_index = pd.DatetimeIndex(
        [_canonical_index_timestamp(value) for value in canonical]
    )
    prepared = frame.copy(deep=True)
    prepared.index = normalized_index
    prepared["entry_signal"] = pd.Series(False, index=prepared.index, dtype=bool)
    prepared["exit_signal"] = pd.Series(False, index=prepared.index, dtype=bool)
    return prepared, dict(zip(canonical, normalized_index, strict=True))


def _validate_replay_evidence(
    ledger: ForwardDecisionLedger,
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
    evidence_by_id: Mapping[str, Any],
) -> dict[str, StrategyBoundRecommendationEvidence]:
    if not isinstance(evidence_by_id, Mapping):
        raise ForwardPaperExecutionError(
            "recommendation_evidence_by_id must be a Mapping"
        )
    expected_ids = {item.recommendation_id for item in ledger.decisions}
    if set(evidence_by_id) != expected_ids:
        raise ForwardPaperExecutionError(
            "recommendation evidence IDs must exactly match ledger recommendation IDs"
        )

    resolved: dict[str, StrategyBoundRecommendationEvidence] = {}
    source_qualification_json = export_strategy_qualification_json(
        qualification_artifact.qualification
    )
    for record in ledger.decisions:
        try:
            evidence, recommendation_json = _validated_evidence(
                evidence_by_id[record.recommendation_id]
            )
        except (ForwardDecisionLedgerError, KeyError) as exc:
            raise ForwardPaperExecutionError(
                f"recommendation evidence failed validation: {exc}"
            ) from exc
        snapshot = evidence.signal_snapshot
        provenance = snapshot.provenance
        recommendation_sha256 = hashlib.sha256(
            recommendation_json.encode("utf-8")
        ).hexdigest()
        if evidence.recommendation_id != record.recommendation_id:
            raise ForwardPaperExecutionError(
                "recommendation evidence ID does not match ledger record"
            )
        if recommendation_sha256 != record.recommendation_sha256:
            raise ForwardPaperExecutionError(
                "recommendation evidence SHA-256 does not match ledger record"
            )
        copied_fields = (
            (snapshot.observed_at, record.observed_at, "observed_at"),
            (evidence.generated_at, record.generated_at, "generated_at"),
            (snapshot.symbol, record.symbol, "symbol"),
            (snapshot.signal, record.signal, "signal"),
            (evidence.action, record.action, "action"),
            (
                evidence.source_qualification_evaluation_id,
                record.qualification_evaluation_id,
                "qualification_evaluation_id",
            ),
            (evidence.strategy_id, record.strategy_id, "strategy_id"),
        )
        for evidence_value, record_value, field_name in copied_fields:
            if evidence_value != record_value:
                raise ForwardPaperExecutionError(
                    f"ledger field {field_name!r} does not match resolved evidence"
                )
        if tuple(provenance.selected_parameters.items()) != tuple(
            record.selected_parameters.items()
        ):
            raise ForwardPaperExecutionError(
                "ledger selected_parameters do not match resolved evidence"
            )
        if export_strategy_qualification_json(evidence.qualification) != source_qualification_json:
            raise ForwardPaperExecutionError(
                "resolved evidence qualification does not match source qualification"
            )
        resolved[record.recommendation_id] = evidence
    return resolved


def _validated_trust_chain(
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
    ledger: ForwardDecisionLedger,
) -> tuple[ForwardPaperActivation, UniverseOOSArtifact, ForwardDecisionLedger, str]:
    if type(activation) is not ForwardPaperActivation:
        raise ForwardPaperExecutionError(
            "activation must be an exact ForwardPaperActivation"
        )
    if type(qualification_artifact) is not UniverseOOSArtifact:
        raise ForwardPaperExecutionError(
            "qualification_artifact must be an exact UniverseOOSArtifact"
        )
    try:
        trusted_activation, activation_sha256 = _validated_activation_source(
            activation, qualification_artifact
        )
        trusted_ledger = _validated_ledger(ledger)
        _validate_ledger_records(
            trusted_ledger, trusted_activation, qualification_artifact
        )
    except (ForwardDecisionLedgerError, TypeError, ValueError) as exc:
        raise ForwardPaperExecutionError(
            f"forward trust chain validation failed: {exc}"
        ) from exc
    ledger_lock = (
        trusted_ledger.activation_id,
        trusted_ledger.activation_sha256,
        trusted_ledger.qualification_evaluation_id,
        trusted_ledger.qualification_sha256,
        trusted_ledger.strategy_id,
    )
    activation_lock = (
        trusted_activation.activation_id,
        activation_sha256,
        trusted_activation.qualification_evaluation_id,
        trusted_activation.qualification_sha256,
        trusted_activation.strategy_id,
    )
    if ledger_lock != activation_lock:
        raise ForwardPaperExecutionError(
            "ledger activation and qualification identity lock mismatch"
        )
    ledger_sha256 = hashlib.sha256(
        export_forward_decision_ledger_json(trusted_ledger).encode("utf-8")
    ).hexdigest()
    return trusted_activation, qualification_artifact, trusted_ledger, ledger_sha256


def _validated_replay_configuration(
    *,
    initial_cash: Any,
    quantity_per_trade: Any,
    slippage_per_share: Any,
    max_order_notional: Any,
    max_position_quantity: Any,
    max_position_notional: Any,
    max_total_exposure: Any,
) -> tuple[float, int, float, float | None, int | None, float | None, float | None]:
    try:
        initial_cash_float = portfolio_engine._require_finite_number(
            "initial_cash", initial_cash, non_negative=True
        )
        slippage_float = portfolio_engine._require_finite_number(
            "slippage_per_share", slippage_per_share, non_negative=True
        )
        max_order_notional_float = portfolio_engine._normalize_optional_risk_notional(
            "max_order_notional", max_order_notional
        )
        max_position_quantity_int = portfolio_engine._normalize_optional_risk_quantity(
            "max_position_quantity", max_position_quantity
        )
        max_position_notional_float = portfolio_engine._normalize_optional_risk_notional(
            "max_position_notional", max_position_notional
        )
        max_total_exposure_float = portfolio_engine._normalize_optional_risk_notional(
            "max_total_exposure", max_total_exposure
        )
    except (portfolio_engine.PaperTradingModelError, TypeError, ValueError) as exc:
        raise ForwardPaperExecutionError(
            f"invalid forward replay configuration: {exc}"
        ) from exc
    if type(quantity_per_trade) is not int or isinstance(quantity_per_trade, bool):
        raise ForwardPaperExecutionError(
            "quantity_per_trade must be a positive exact int"
        )
    if quantity_per_trade <= 0:
        raise ForwardPaperExecutionError(
            "quantity_per_trade must be a positive exact int"
        )
    return (
        initial_cash_float,
        quantity_per_trade,
        slippage_float,
        max_order_notional_float,
        max_position_quantity_int,
        max_position_notional_float,
        max_total_exposure_float,
    )


def _run_forward_paper_execution_replay(
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
    ledger: ForwardDecisionLedger,
    recommendation_evidence_by_id: Mapping[str, Any],
    forward_market_frames: Mapping[str, pd.DataFrame],
    *,
    initial_cash: float,
    quantity_per_trade: int,
    slippage_per_share: float = 0.0,
    max_order_notional: float | None = None,
    max_position_quantity: int | None = None,
    max_position_notional: float | None = None,
    max_total_exposure: float | None = None,
    _capture_trace: bool,
) -> SimulatedPortfolioTradingResult | ForwardPaperExecutionReplayBundle:
    """Replay trusted decisions through one fresh multi-symbol paper runtime."""
    trusted_activation, trusted_source, trusted_ledger, ledger_sha256 = (
        _validated_trust_chain(activation, qualification_artifact, ledger)
    )
    resolved_evidence = _validate_replay_evidence(
        trusted_ledger,
        trusted_activation,
        trusted_source,
        recommendation_evidence_by_id,
    )
    (
        initial_cash_float,
        quantity_per_trade_int,
        slippage_float,
        max_order_notional_float,
        max_position_quantity_int,
        max_position_notional_float,
        max_total_exposure_float,
    ) = _validated_replay_configuration(
        initial_cash=initial_cash,
        quantity_per_trade=quantity_per_trade,
        slippage_per_share=slippage_per_share,
        max_order_notional=max_order_notional,
        max_position_quantity=max_position_quantity,
        max_position_notional=max_position_notional,
        max_total_exposure=max_total_exposure,
    )
    frame_keys = set(forward_market_frames) if isinstance(forward_market_frames, Mapping) else set()
    if not isinstance(forward_market_frames, Mapping) or not frame_keys:
        raise ForwardPaperExecutionError(
            "forward_market_frames must be a non-empty Mapping"
        )
    if any(type(symbol) is not str or not symbol or symbol.strip() != symbol for symbol in frame_keys):
        raise ForwardPaperExecutionError(
            "forward market frame symbols must be exact clean strings"
        )
    qualified_symbols = set(trusted_activation.qualified_symbols)
    if not frame_keys <= qualified_symbols:
        raise ForwardPaperExecutionError(
            "forward market frames contain a foreign symbol"
        )
    ledger_symbols = {item.symbol for item in trusted_ledger.decisions}
    if not ledger_symbols <= frame_keys:
        raise ForwardPaperExecutionError(
            "a ledger decision symbol is missing from forward_market_frames"
        )

    prepared_frames: dict[str, pd.DataFrame] = {}
    canonical_indexes: dict[str, dict[str, pd.Timestamp]] = {}
    for symbol in sorted(frame_keys):
        prepared, canonical_index = _canonicalize_market_frame(
            symbol,
            forward_market_frames[symbol],
            trusted_activation.qualification_cutoff,
        )
        prepared_frames[symbol] = prepared
        canonical_indexes[symbol] = canonical_index

    for record in trusted_ledger.decisions:
        timestamp = canonical_indexes[record.symbol].get(record.observed_at)
        if timestamp is None:
            raise ForwardPaperExecutionError(
                "ledger decision timestamp is missing from its symbol frame"
            )
        action = resolved_evidence[record.recommendation_id].action
        if action == "ENTER":
            prepared_frames[record.symbol].at[timestamp, "entry_signal"] = True
        elif action == "EXIT":
            prepared_frames[record.symbol].at[timestamp, "exit_signal"] = True
        elif action not in {"WATCH", "HOLD", "NO_TRADE"}:
            raise ForwardPaperExecutionError(
                f"unsupported schema-1.1 action {action!r}"
            )

    last_prices = {
        symbol: float(frame["Close"].iloc[-1])
        for symbol, frame in prepared_frames.items()
    }
    fee_rate = portfolio_engine._require_finite_number(
        "qualification fee_rate",
        trusted_source.resolved_configuration.fee_rate,
        non_negative=True,
    )
    tax_rate = portfolio_engine._require_finite_number(
        "qualification tax_rate",
        trusted_source.resolved_configuration.tax_rate,
        non_negative=True,
    )
    strategy_metadata = {
        "activation_id": trusted_activation.activation_id,
        "ledger_id": trusted_ledger.ledger_id,
        "qualification_evaluation_id": trusted_activation.qualification_evaluation_id,
        "qualification_sha256": trusted_activation.qualification_sha256,
        "ledger_sha256": ledger_sha256,
    }
    json.dumps(strategy_metadata, ensure_ascii=False, sort_keys=True, allow_nan=False)
    collector = _ForwardPortfolioTraceCollector() if _capture_trace else None
    result = portfolio_engine.run_simulated_portfolio_trading_result(
        prepared_frames,
        initial_cash=initial_cash_float,
        last_prices=last_prices,
        quantity_per_trade=quantity_per_trade_int,
        fee_rate=fee_rate,
        tax_rate=tax_rate,
        slippage_per_share=slippage_float,
        max_order_notional=max_order_notional_float,
        max_position_quantity=max_position_quantity_int,
        max_position_notional=max_position_notional_float,
        max_total_exposure=max_total_exposure_float,
        strategy=trusted_activation.strategy_id,
        strategy_metadata=strategy_metadata,
        _after_timestamp=collector,
    )
    if collector is None:
        return result
    _trusted_result, result_sha256 = _trusted_portfolio_result(result)
    trace = ForwardPortfolioTrace(
        schema_version="1.0",
        artifact_type="forward_portfolio_trace",
        activation_id=trusted_activation.activation_id,
        qualification_evaluation_id=trusted_activation.qualification_evaluation_id,
        qualification_sha256=trusted_activation.qualification_sha256,
        ledger_id=trusted_ledger.ledger_id,
        ledger_sha256=ledger_sha256,
        strategy_id=trusted_activation.strategy_id,
        initial_equity=initial_cash_float,
        portfolio_result_sha256=result_sha256,
        observations=tuple(collector.observations),
    )
    trusted_trace = validate_forward_portfolio_trace(
        trusted_activation,
        trusted_source,
        trusted_ledger,
        result,
        trace,
    )
    return ForwardPaperExecutionReplayBundle(result, trusted_trace)


def validate_forward_portfolio_trace(
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
    ledger: ForwardDecisionLedger,
    portfolio_result: SimulatedPortfolioTradingResult,
    portfolio_trace: ForwardPortfolioTrace,
) -> ForwardPortfolioTrace:
    trusted_activation, _trusted_source, trusted_ledger, ledger_sha256 = (
        _validated_trust_chain(activation, qualification_artifact, ledger)
    )
    if type(portfolio_trace) is not ForwardPortfolioTrace:
        raise ForwardPaperExecutionError(
            "portfolio_trace must be an exact ForwardPortfolioTrace"
        )
    try:
        canonical = export_forward_portfolio_trace_json(portfolio_trace)
        trusted_trace = load_forward_portfolio_trace_json(canonical)
        if export_forward_portfolio_trace_json(trusted_trace) != canonical:
            raise ForwardPaperExecutionError("portfolio trace canonical round-trip drift")
    except ForwardPaperExecutionError:
        raise
    except Exception as exc:
        raise ForwardPaperExecutionError(
            f"portfolio trace canonical validation failed: {exc}"
        ) from exc
    expected_identity = (
        trusted_activation.activation_id,
        trusted_activation.qualification_evaluation_id,
        trusted_activation.qualification_sha256,
        trusted_ledger.ledger_id,
        ledger_sha256,
        trusted_activation.strategy_id,
    )
    actual_identity = (
        trusted_trace.activation_id,
        trusted_trace.qualification_evaluation_id,
        trusted_trace.qualification_sha256,
        trusted_trace.ledger_id,
        trusted_trace.ledger_sha256,
        trusted_trace.strategy_id,
    )
    if actual_identity != expected_identity:
        raise ForwardPaperExecutionError(
            "portfolio trace activation/qualification/ledger identity mismatch"
        )
    _validate_trace_result_pair(portfolio_result, trusted_trace)
    return trusted_trace


def run_forward_paper_execution_replay(
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
    ledger: ForwardDecisionLedger,
    recommendation_evidence_by_id: Mapping[str, Any],
    forward_market_frames: Mapping[str, pd.DataFrame],
    *,
    initial_cash: float,
    quantity_per_trade: int,
    slippage_per_share: float = 0.0,
    max_order_notional: float | None = None,
    max_position_quantity: int | None = None,
    max_position_notional: float | None = None,
    max_total_exposure: float | None = None,
) -> SimulatedPortfolioTradingResult:
    result = _run_forward_paper_execution_replay(
        activation,
        qualification_artifact,
        ledger,
        recommendation_evidence_by_id,
        forward_market_frames,
        initial_cash=initial_cash,
        quantity_per_trade=quantity_per_trade,
        slippage_per_share=slippage_per_share,
        max_order_notional=max_order_notional,
        max_position_quantity=max_position_quantity,
        max_position_notional=max_position_notional,
        max_total_exposure=max_total_exposure,
        _capture_trace=False,
    )
    if type(result) is not SimulatedPortfolioTradingResult:
        raise ForwardPaperExecutionError("legacy replay returned an invalid result type")
    return result


def run_forward_paper_execution_replay_with_trace(
    activation: ForwardPaperActivation,
    qualification_artifact: UniverseOOSArtifact,
    ledger: ForwardDecisionLedger,
    recommendation_evidence_by_id: Mapping[str, Any],
    forward_market_frames: Mapping[str, pd.DataFrame],
    *,
    initial_cash: float,
    quantity_per_trade: int,
    slippage_per_share: float = 0.0,
    max_order_notional: float | None = None,
    max_position_quantity: int | None = None,
    max_position_notional: float | None = None,
    max_total_exposure: float | None = None,
) -> ForwardPaperExecutionReplayBundle:
    result = _run_forward_paper_execution_replay(
        activation,
        qualification_artifact,
        ledger,
        recommendation_evidence_by_id,
        forward_market_frames,
        initial_cash=initial_cash,
        quantity_per_trade=quantity_per_trade,
        slippage_per_share=slippage_per_share,
        max_order_notional=max_order_notional,
        max_position_quantity=max_position_quantity,
        max_position_notional=max_position_notional,
        max_total_exposure=max_total_exposure,
        _capture_trace=True,
    )
    if type(result) is not ForwardPaperExecutionReplayBundle:
        raise ForwardPaperExecutionError("traced replay returned an invalid bundle type")
    return result


__all__ = [
    "ForwardPaperExecutionError",
    "ForwardPaperExecutionReplayBundle",
    "run_forward_paper_execution_replay",
    "run_forward_paper_execution_replay_with_trace",
    "validate_forward_portfolio_trace",
]
