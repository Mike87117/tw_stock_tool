# Track C2.3.2 Paper Trading Finite-Number Validation

## Repository

- Branch: `track-c2-research-correctness-fixes`
- Baseline commit: `a7966b4b4c66cbdfa8ef6ec6f5e426fbb5e3d1b6`
- Final commit is recorded in the execution report.

## Problem statement

`SimulatedFill` monetary fields and `SimulatedPortfolio` initial cash used sign-only validation, allowing NaN and Infinity. Because fills are mutable, a valid fill could also be corrupted after construction and contaminate portfolio or position arithmetic before any error was raised.

## Approved monetary contracts

- Fill price: real numeric, non-boolean, finite, and strictly positive.
- Fill fee, tax, and slippage: real numeric, non-boolean, finite, and non-negative; zero remains valid.
- Portfolio initial cash: real numeric, non-boolean, finite, and non-negative; integer and floating-point zero remain valid.
- Existing order, quantity, symbol, side, timestamp, valuation, trade-log record, last-price, and engine Open-price contracts remain unchanged.

## Constructor validation

One private module-level helper uses the existing standard-library `Real` and `math.isfinite` imports. `SimulatedFill.__post_init__` applies it to price, fee, tax, and slippage. `SimulatedPortfolio.__post_init__` applies it to initial cash. Type and boolean checks occur before conversion or finiteness checks, and valid caller values are not normalized or overwritten.

## Mutable-fill defense

A second private helper revalidates that an object is a `SimulatedFill` and that its four monetary fields still satisfy their contracts. Both `SimulatedPosition.apply_fill` and `SimulatedPortfolio.apply_fill` call it before reading monetary properties, checking resources, mutating cash or positions, or recording a fill.

## Fail-fast state-integrity guarantees

A mutable fill corrupted to NaN is rejected before portfolio cash changes, before a position is created, and before the trade log records the fill. A position-level fill corrupted to positive Infinity is rejected without changing quantity, average cost, or realized PnL.

Successful BUY/SELL cash reconciliation, weighted average cost, realized PnL, oversell handling, and zero-quantity average-cost reset retain their existing formulas. Public class signatures and APIs are unchanged. No dependency was added.

## Validation matrix

| Boundary | NaN | +Infinity | -Infinity | Boolean | Wrong type | Valid boundary |
| -- | -- | -- | -- | -- | -- | -- |
| Fill price | Reject | Reject | Reject | Reject | Reject | Positive integer and float accepted |
| Fill fee/tax/slippage | Reject | Reject | Reject | Reject | Reject | Zero and positive finite values accepted |
| Portfolio initial cash | Reject | Reject | Reject | Reject | Reject | `0`, `0.0`, positive integer and float accepted |
| Mutable fill at Portfolio | Reject before mutation | Reject before mutation | Reject before mutation | Reject before mutation | Reject before mutation | Valid fills preserve reconciliation |
| Mutable fill at Position | Reject before mutation | Reject before mutation | Reject before mutation | Reject before mutation | Reject before mutation | Valid fills preserve position arithmetic |

## Changed files

- `src/tw_stock_tool/paper_trading/models.py`
- `tests/test_paper_trading_models.py`
- `tests/test_track_c1_research_correctness.py`
- `docs/TRACK_C1_RESEARCH_CORRECTNESS_CHARACTERIZATION.md`
- `docs/TRACK_C2_3_2_PAPER_TRADING_FINITE_VALIDATION.md`

## Expected-failure transition

- Before Track C2.3.2: 5
- Resolved in Track C2.3.2: 2
- After Track C2.3.2: 3

## Tests executed

- `py -m unittest tests.test_paper_trading_models`
- `py -m unittest tests.test_paper_trading_engine`
- `py -m unittest tests.test_simulated_paper_trading_guard_adapter`
- `py -m unittest tests.test_track_c1_research_correctness`
- Combined targeted suite for all four modules
- `py -m unittest discover -s tests`
- Direct fail-fast checks for non-finite fill values, initial cash, and mutated fills

## Non-goals

This phase does not modify the Paper Trading engine or results, Backtest validation, Risk, Guard, Analysis, ML, compatibility wrappers, project configuration, CI, trade-log record contracts, valuation APIs, or successful trading formulas.

## Remaining Track C2 work

1. Backtest finite-number validation.
2. Interval-aware metrics.
3. Unified CLI nonzero exit behavior.
