# Track C2.4.1 Core Interval-Aware Metrics

## Repository

- Branch: `track-c2-research-correctness-fixes`
- Baseline commit: `d7f18781b4264fba17494f951b6ab04cd88c451b`
- Final commit is recorded in the execution report.

## Problem statement

Sharpe and Sortino always used `sqrt(252)`, which is valid for daily bars but overstates annualization for weekly and monthly observations. The canonical metric and Backtest APIs needed explicit interval context while preserving all daily callers.

## Approved mapping

- `1d`: 252 periods per year.
- `1wk`: 52 periods per year.
- `1mo`: 12 periods per year.
- Default: `1d`.

No timestamp inference, calendar-gap inference, or automatic frequency guessing is used.

## Standalone metric APIs

`calculate_sharpe()` and `calculate_sortino()` accept a final optional `interval` argument defaulting to `DEFAULT_INTERVAL`. A private resolver validates against `VALID_INTERVALS` and returns the approved periods-per-year value. Invalid intervals raise `ValueError`, including for empty input. Existing periodic returns, population standard deviation, downside-return selection, safe-ratio behavior, and edge-case results remain unchanged.

## Canonical Backtest APIs

`run_backtest_result()` and `run_backtest()` append the same optional interval argument. `_validate_inputs()` rejects invalid values with `BacktestError` before trading or metric calculation. The interval is passed only to Sharpe and Sortino; the legacy wrapper continues delegating to the structured API.

Default calls remain daily-compatible. No interval field was added to `BacktestResult`, and no interval key was added to the legacy dictionary.

## Trading-result invariance

For identical inputs, changing only interval leaves capital, trades, PnL, total return, CAGR, exposure, drawdown, profit factor, win rate, holding periods, trade records, and equity curve unchanged. Only Sharpe and Sortino annualization may differ.

## Changed files

- `src/tw_stock_tool/backtesting/metrics.py`
- `src/tw_stock_tool/backtesting/backtest.py`
- `tests/test_backtest_metrics.py`
- `tests/test_backtest.py`
- `tests/test_track_c1_research_correctness.py`
- `docs/TRACK_C1_RESEARCH_CORRECTNESS_CHARACTERIZATION.md`
- `docs/TRACK_C2_4_1_CORE_INTERVAL_AWARE_METRICS.md`

## Tests executed

- `py -m unittest tests.test_backtest_metrics`
- `py -m unittest tests.test_backtest`
- `py -m unittest tests.test_track_c1_research_correctness`
- Combined targeted suite
- `py -m unittest discover -s tests`
- Temporary direct metric and Backtest interval checks

## Expected-failure transition

- Before Track C2.4.1: 2 expected failures.
- After Track C2.4.1: 2 expected failures.
- Remaining: AI walk-forward CLI runtime exit and Analyze CLI runtime exit.

## Non-goals

This phase does not expose interval selection through Parameter Sweep, Walk Forward, Strategy Compare, Backtest Report, or other high-level CLIs. It does not change BacktestResult, legacy result schemas, trading logic, other metrics, reports, CLI exit behavior, Analysis, ML, Paper Trading, or Risk.

## Remaining Track C2 work

1. Unified CLI nonzero exit behavior.

## Analyze propagation follow-up

Track C2.4.2 propagates the already existing Analyze interval selection into the canonical Backtest. Other workflows that do not currently expose interval selection remain outside this follow-up.
