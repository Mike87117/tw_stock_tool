"""Core runner for the daily research pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Callable, Iterable
import math
from numbers import Real
from typing import Any

import pandas as pd

from tw_stock_tool.analysis.analysis import StockAnalysis
from tw_stock_tool.analysis.analysis_session import AnalysisSession
from tw_stock_tool.backtesting.parameter_sweep import SORTABLE_COLUMNS as PARAMETER_SWEEP_SORTABLE_COLUMNS
from tw_stock_tool.backtesting.walk_forward import SORTABLE_COLUMNS as WALK_FORWARD_SORTABLE_COLUMNS
from tw_stock_tool.reports.daily_report import (
    BACKTEST_HIGHLIGHT_COLUMNS,
    DEFAULT_MIN_SCORE,
    DEFAULT_SIGNALS,
    DEFAULT_TOP,
    PARAMETER_SWEEP_HIGHLIGHT_COLUMNS,
    WALK_FORWARD_HIGHLIGHT_COLUMNS,
    build_daily_report_data,
    build_data_limitations_from_ranking,
    render_daily_report_markdown,
    run_candidate_backtest_validation,
    run_candidate_parameter_sweep_validation,
    run_candidate_walk_forward_validation,
    run_daily_report,
)
from tw_stock_tool.utils.config import (
    DEFAULT_AUTO_ADJUST,
    DEFAULT_INTERVAL,
    DEFAULT_PERIOD,
    FEE_RATE,
    INITIAL_CAPITAL,
    TAX_RATE,
)


@dataclass(frozen=True)
class DailyPipelineConfig:
    period: str = DEFAULT_PERIOD
    interval: str = DEFAULT_INTERVAL
    signals: tuple[str, ...] = DEFAULT_SIGNALS
    min_score: float = DEFAULT_MIN_SCORE
    top: int | None = DEFAULT_TOP
    force_refresh: bool = False
    auto_adjust: bool = DEFAULT_AUTO_ADJUST

    validate_top: int = 0
    validation_strategy: str = "ma_cross"
    validation_initial_capital: float = INITIAL_CAPITAL
    validation_fee_rate: float = FEE_RATE
    validation_tax_rate: float = TAX_RATE
    validation_position_size: float = 1.0

    parameter_sweep_top: int = 0
    parameter_sweep_sort_by: str = "Sharpe Ratio"

    walk_forward_top: int = 0
    walk_forward_train_days: int = 126
    walk_forward_test_days: int = 63
    walk_forward_step_days: int | None = None
    walk_forward_sort_by: str = "Train Sharpe Ratio"

    output_excel: str | None = None
    progress: bool = True
    report_date: str | None = None

    def __post_init__(self) -> None:
        if self.signals is None or isinstance(self.signals, (str, bytes)):
            raise ValueError("signals must be an iterable of non-empty strings.")
        try:
            normalized = tuple(self.signals)
        except TypeError as exc:
            raise ValueError("signals must be an iterable of non-empty strings.") from exc
        if any(not isinstance(signal, str) or not signal.strip() for signal in normalized):
            raise ValueError("signals must be an iterable of non-empty strings.")
        object.__setattr__(self, "signals", normalized)


@dataclass
class DailyPipelineResult:
    summary_df: pd.DataFrame
    candidates_df: pd.DataFrame
    ranking_df: pd.DataFrame
    backtest_highlights: pd.DataFrame
    parameter_sweep_highlights: pd.DataFrame
    walk_forward_highlights: pd.DataFrame
    risk_notes: list[str]
    data_limitations: list[str]
    run_configuration: dict[str, Any]
    report_data: dict[str, Any]
    markdown: str


def _finite_real(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite numeric value.")


def validate_daily_pipeline_config(config: DailyPipelineConfig) -> None:
    """Validate pipeline configuration without touching data or analysis services."""
    if not isinstance(config, DailyPipelineConfig):
        raise ValueError("config must be a DailyPipelineConfig.")
    _finite_real(config.min_score, "min_score")
    if config.top is not None and (isinstance(config.top, bool) or not isinstance(config.top, int)):
        raise ValueError("top must be an integer or None.")
    for name in ("validate_top", "parameter_sweep_top", "walk_forward_top"):
        value = getattr(config, name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer.")
    if config.validation_strategy not in ("ma_cross", "macd", "rsi", "score"):
        raise ValueError(f"Unsupported validation strategy: {config.validation_strategy}")
    for name in ("validation_initial_capital", "validation_fee_rate", "validation_tax_rate", "validation_position_size"):
        _finite_real(getattr(config, name), name)
    if config.validation_initial_capital <= 0:
        raise ValueError("validation_initial_capital must be greater than 0.")
    if config.validation_fee_rate < 0:
        raise ValueError("validation_fee_rate must be non-negative.")
    if config.validation_tax_rate < 0:
        raise ValueError("validation_tax_rate must be non-negative.")
    if not 0 < config.validation_position_size <= 1:
        raise ValueError("validation_position_size must be greater than 0 and at most 1.")
    for name in ("walk_forward_train_days", "walk_forward_test_days"):
        value = getattr(config, name)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be greater than 0.")
    if config.walk_forward_step_days is not None and (
        isinstance(config.walk_forward_step_days, bool)
        or not isinstance(config.walk_forward_step_days, int)
        or config.walk_forward_step_days <= 0
    ):
        raise ValueError("walk_forward_step_days must be greater than 0.")
    if config.parameter_sweep_top > 0:
        if config.validate_top <= 0:
            raise ValueError("--parameter-sweep-top requires --validate-top greater than 0.")
        if config.parameter_sweep_top > config.validate_top:
            raise ValueError("--parameter-sweep-top cannot exceed --validate-top.")
        if config.validation_strategy == "macd":
            raise ValueError("MACD is supported for backtest-only validation, not parameter sweep validation.")
        if config.parameter_sweep_sort_by not in PARAMETER_SWEEP_SORTABLE_COLUMNS:
            raise ValueError(f"Unsupported parameter sweep sort metric: {config.parameter_sweep_sort_by}")
    if config.walk_forward_top > 0:
        if config.validate_top <= 0:
            raise ValueError("--walk-forward-top requires --validate-top greater than 0.")
        if config.walk_forward_top > config.validate_top:
            raise ValueError("--walk-forward-top cannot exceed --validate-top.")
        if config.validation_strategy == "macd":
            raise ValueError("MACD is supported for backtest-only validation, not walk-forward validation.")
        if config.walk_forward_sort_by not in WALK_FORWARD_SORTABLE_COLUMNS:
            raise ValueError(f"Unsupported walk-forward sort metric: {config.walk_forward_sort_by}")


def build_daily_pipeline_run_configuration(
    config: DailyPipelineConfig,
) -> dict[str, Any]:
    """Build the deterministic scalar configuration snapshot for the report."""
    validate_daily_pipeline_config(config)
    return {
        "Period": config.period,
        "Interval": config.interval,
        "Signals": ", ".join(config.signals),
        "Minimum Score": config.min_score,
        "Candidate Top": config.top if config.top is not None else "All",
        "Auto Adjust": "Yes" if config.auto_adjust else "No",
        "Force Refresh": "Yes" if config.force_refresh else "No",
        "Backtest Enabled": "Yes" if config.validate_top > 0 else "No",
        "Backtest Top": config.validate_top,
        "Validation Strategy": config.validation_strategy,
        "Initial Capital": config.validation_initial_capital,
        "Fee Rate": config.validation_fee_rate,
        "Tax Rate": config.validation_tax_rate,
        "Position Size": config.validation_position_size,
        "Parameter Sweep Enabled": "Yes" if config.parameter_sweep_top > 0 else "No",
        "Parameter Sweep Top": config.parameter_sweep_top,
        "Parameter Sweep Sort By": config.parameter_sweep_sort_by,
        "Walk Forward Enabled": "Yes" if config.walk_forward_top > 0 else "No",
        "Walk Forward Top": config.walk_forward_top,
        "Train Days": config.walk_forward_train_days,
        "Test Days": config.walk_forward_test_days,
        "Effective Step Days": (
            config.walk_forward_step_days
            if config.walk_forward_step_days is not None
            else config.walk_forward_test_days
        ),
        "Walk Forward Sort By": config.walk_forward_sort_by,
    }


def _empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def run_daily_research_pipeline(
    stock_ids: Iterable[str],
    config: DailyPipelineConfig,
    *,
    analysis_provider: Callable[[str], StockAnalysis] | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> DailyPipelineResult:
    """Run scan and optional research stages with one shared analysis provider."""
    validate_daily_pipeline_config(config)
    normalized_stock_ids = list(stock_ids)
    if not normalized_stock_ids:
        raise ValueError("No stocks provided.")

    def emit(message: str) -> None:
        if status_callback is not None:
            status_callback(message)

    if analysis_provider is None:
        session = AnalysisSession(
            period=config.period,
            interval=config.interval,
            auto_adjust=config.auto_adjust,
            force_refresh=config.force_refresh,
        )
        analysis_provider = session.get

    emit(f"Scanning {len(normalized_stock_ids)} stocks...")
    summary_df, candidates_df, ranking_df, _ = run_daily_report(
        stock_ids=normalized_stock_ids,
        period=config.period,
        interval=config.interval,
        signals=config.signals,
        min_score=config.min_score,
        top=config.top,
        force_refresh=config.force_refresh,
        auto_adjust=config.auto_adjust,
        output=config.output_excel,
        progress=config.progress,
        analysis_provider=analysis_provider,
    )
    data_limitations = build_data_limitations_from_ranking(ranking_df)
    risk_notes: list[str] = []

    backtest_highlights = _empty(BACKTEST_HIGHLIGHT_COLUMNS)
    if config.validate_top > 0:
        emit(f"Validating top {config.validate_top} candidates with {config.validation_strategy}...")
        backtest_highlights, limitations = run_candidate_backtest_validation(
            candidates_df,
            validate_top=config.validate_top,
            strategy=config.validation_strategy,
            period=config.period,
            interval=config.interval,
            auto_adjust=config.auto_adjust,
            force_refresh=config.force_refresh,
            initial_capital=config.validation_initial_capital,
            fee_rate=config.validation_fee_rate,
            tax_rate=config.validation_tax_rate,
            position_size=config.validation_position_size,
            analysis_provider=analysis_provider,
        )
        data_limitations.extend(limitations)
        successes = int((backtest_highlights["Status"] == "OK").sum())
        emit(f"Validation completed: selected {len(backtest_highlights)}, success {successes}, failed {len(backtest_highlights) - successes}.")
        risk_notes.append(
            "Candidate backtests use historical data and next-bar Open execution assumptions; "
            "historical results do not predict future performance."
        )

    parameter_sweep_highlights = _empty(PARAMETER_SWEEP_HIGHLIGHT_COLUMNS)
    if config.parameter_sweep_top > 0:
        emit(f"Sweeping parameters for up to {config.parameter_sweep_top} successful backtest candidate(s)...")
        parameter_sweep_highlights, limitations = run_candidate_parameter_sweep_validation(
            backtest_highlights,
            parameter_sweep_top=config.parameter_sweep_top,
            strategy=config.validation_strategy,
            period=config.period,
            interval=config.interval,
            auto_adjust=config.auto_adjust,
            force_refresh=config.force_refresh,
            sort_by=config.parameter_sweep_sort_by,
            initial_capital=config.validation_initial_capital,
            fee_rate=config.validation_fee_rate,
            tax_rate=config.validation_tax_rate,
            position_size=config.validation_position_size,
            analysis_provider=analysis_provider,
        )
        data_limitations.extend(limitations)
        counts = parameter_sweep_highlights["Status"].value_counts() if not parameter_sweep_highlights.empty else {}
        emit(f"Parameter sweep completed: selected {len(parameter_sweep_highlights)}, OK {counts.get('OK', 0)}, PARTIAL {counts.get('PARTIAL', 0)}, ERROR {counts.get('ERROR', 0)}.")
        risk_notes.append(
            "Parameter sweep results are historical in-sample search summaries across multiple parameter combinations. "
            "The displayed best result may reflect overfitting, does not change candidate ranking, is not passed into "
            "walk-forward validation, and does not predict future performance."
        )

    walk_forward_highlights = _empty(WALK_FORWARD_HIGHLIGHT_COLUMNS)
    if config.walk_forward_top > 0:
        emit(f"Validating walk-forward for up to {config.walk_forward_top} successful backtest candidate(s)...")
        walk_forward_highlights, limitations = run_candidate_walk_forward_validation(
            backtest_highlights,
            walk_forward_top=config.walk_forward_top,
            strategy=config.validation_strategy,
            period=config.period,
            interval=config.interval,
            auto_adjust=config.auto_adjust,
            force_refresh=config.force_refresh,
            train_days=config.walk_forward_train_days,
            test_days=config.walk_forward_test_days,
            step_days=config.walk_forward_step_days,
            sort_by=config.walk_forward_sort_by,
            initial_capital=config.validation_initial_capital,
            fee_rate=config.validation_fee_rate,
            tax_rate=config.validation_tax_rate,
            position_size=config.validation_position_size,
            analysis_provider=analysis_provider,
        )
        data_limitations.extend(limitations)
        counts = walk_forward_highlights["Status"].value_counts() if not walk_forward_highlights.empty else {}
        emit(f"Walk-forward validation completed: selected {len(walk_forward_highlights)}, OK {counts.get('OK', 0)}, PARTIAL {counts.get('PARTIAL', 0)}, ERROR {counts.get('ERROR', 0)}.")
        risk_notes.append(
            "Walk-forward results are historical out-of-sample research estimates. Parameters are selected on training windows and evaluated on later test windows; results do not predict future performance. Window fields represent observations (rows) in the current engine."
        )

    run_configuration = build_daily_pipeline_run_configuration(config)

    report_date = (
        config.report_date
        if config.report_date is not None
        else datetime.now().strftime("%Y-%m-%d")
    )
    report_data = build_daily_report_data(
        report_date=report_date,
        stock_universe=normalized_stock_ids,
        run_configuration=run_configuration,
        screening_results=summary_df,
        watchlist_candidates=candidates_df,
        backtest_highlights=backtest_highlights,
        parameter_sweep_highlights=parameter_sweep_highlights,
        walk_forward_highlights=walk_forward_highlights,
        risk_notes=risk_notes,
        data_limitations=data_limitations,
    )
    markdown = render_daily_report_markdown(report_data)
    return DailyPipelineResult(
        summary_df=summary_df,
        candidates_df=candidates_df,
        ranking_df=ranking_df,
        backtest_highlights=backtest_highlights,
        parameter_sweep_highlights=parameter_sweep_highlights,
        walk_forward_highlights=walk_forward_highlights,
        risk_notes=risk_notes,
        data_limitations=data_limitations,
        run_configuration=run_configuration,
        report_data=report_data,
        markdown=markdown,
    )
