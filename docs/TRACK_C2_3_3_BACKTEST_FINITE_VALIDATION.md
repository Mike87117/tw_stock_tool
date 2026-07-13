# Track C2.3.3 Backtest Finite-Number Validation

## Repository

- Branch: `track-c2-research-correctness-fixes`
- Baseline commit: `7c90803a1f145f3a5ee2a7c930b2989dee7ccee3`
- Final commit is recorded in the execution report.

## Problem statement

Backtest accepted non-finite numeric parameters and non-finite `Open` or `Close` values, allowing invalid data to reach trading arithmetic and metrics. Both public Backtest APIs required one shared upfront validation boundary.

## Approved contracts

- `initial_capital`, `fee_rate`, and `tax_rate`: real, non-boolean, finite; existing finite sign behavior is unchanged.
- `position_size`: real, non-boolean, finite, and within the existing `0 < position_size <= 1` range.
- `stop_loss_pct` and `take_profit_pct`: `None` or real, non-boolean, finite; existing absolute-value semantics are unchanged.
- `Open` and `Close`: every value is real, non-boolean, and finite.
- `max_hold_days`: unchanged.
- Finite zero and negative `Open` values retain the existing pending-execution skip behavior.

## Implementation summary

A private scalar helper uses `Real` and `math.isfinite()` after rejecting booleans and wrong types. A private price-column boundary validates every `Open` and `Close` value without changing the input DataFrame. `_validate_inputs()` now owns all scoped validation, and `run_backtest_result()` invokes it before signal normalization, trading arithmetic, or metric calculation. `run_backtest()` continues to delegate to `run_backtest_result()`.

Validation runs in this order:

1. Empty-data, required-column, and signal-column checks.
2. Scoped parameter type and finite checks.
3. Existing `position_size` range check.
4. Full `Open` and `Close` value validation.

## Compatibility and preserved behavior

- Next-bar Open execution, pending-order clearing, entry and exit timing, and look-ahead prevention are unchanged.
- Finite `Open` values of `0` or below still skip pending execution without raising.
- Fee, tax, stop-loss, take-profit, position sizing, forced close, PnL, and metric formulas are unchanged.
- `BacktestResult`, legacy dictionary output, trade schema, equity index, and public function signatures are unchanged.
- No dependencies were added.

## Changed files

- `src/tw_stock_tool/backtesting/backtest.py`
- `tests/test_backtest.py`
- `tests/test_backtest_path_characterization.py`
- `tests/test_track_c1_research_correctness.py`
- `docs/TRACK_C1_RESEARCH_CORRECTNESS_CHARACTERIZATION.md`
- `docs/TRACK_C2_3_3_BACKTEST_FINITE_VALIDATION.md`

## Validation matrices

- Parameters: 6 fields x NaN, positive Infinity, and negative Infinity = 18 independent cases.
- Prices: `Open` and `Close` x NaN, positive Infinity, and negative Infinity = 6 independent cases.
- Representative boolean, wrong-type, missing-price, optional-`None`, valid finite, and finite negative threshold cases are covered.
- Structured and legacy APIs both exercise the shared validation boundary.

## Expected-failure transition

- Before Track C2.3.3: 3 expected failures.
- After Track C2.3.3: 2 expected failures.
- Remaining: AI walk-forward CLI runtime exit and Analyze CLI runtime exit.

## Tests executed

- `py -m unittest tests.test_backtest`
- `py -m unittest tests.test_track_c1_research_correctness`
- Directly Backtest-dependent verification modules discovered by `git grep`
- Combined targeted suite
- `py -m unittest discover -s tests`
- Temporary direct parameter, price, and non-positive Open checks

## Non-goals

This phase does not change metrics annualization, signal timing, Backtest formulas, the root compatibility wrapper, alternate Backtest implementations, CLI behavior, Paper Trading, Risk, Analysis, or ML.

## Remaining Track C2 work

1. Interval-aware metrics.
2. Unified CLI nonzero exit behavior.