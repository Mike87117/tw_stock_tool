# Track C2.2 RSI Edge Case Fix

## Repository

- Branch: `track-c2-research-correctness-fixes`
- Baseline commit: `2d57911bebd8989c6ba41b23400f08c7b96c79f7`
- Final commit is recorded in the execution report.

## Problem statement

The RSI calculation returned non-finite values after warmup for continuous gains and completely flat price series. Analyze consequently dropped otherwise ready rows because RSI is a required signal-ready column.

## Approved RSI contracts

- Warmup: RSI remains `NaN` before 14 observations complete the default period.
- Continuous gains: average gain above zero and average loss equal to zero produces `100.0`.
- Continuous losses: average gain equal to zero and average loss above zero produces `0.0`.
- Flat series: average gain and average loss both equal to zero produces neutral RSI `50.0`.
- Mixed movement: the existing RS and RSI formulas remain unchanged, with finite results between 0 and 100.

## Production implementation

`_rsi` still uses Wilder-style exponential smoothing with `period=14`, `adjust=False`, and `min_periods=period`. It first calculates the existing general formula, then applies explicit gain-only, loss-only, and flat masks only where both smoothed averages are valid. It does not fill warmup or other missing values, clip results, mutate the input, or add a dependency.

## Before and after

| Series | Before warmup | Before Track C2.2 after warmup | After Track C2.2 after warmup |
| -- | -- | -- | -- |
| Continuous gains | `NaN` | `NaN` | `100.0` |
| Continuous losses | `NaN` | `0.0` | `0.0` |
| Flat | `NaN` | `NaN` | `50.0` |
| Mixed | `NaN` | General formula | General formula |

## Downstream Analyze impact

Deterministic rising and flat OHLCV integration tests now prove that Analyze retains ready rows. Rising data reports RSI `100.0`; flat data reports RSI `50.0`, with both `RSI_Hot` and `RSI_Cold` false for the flat latest row. No Analyze ready-column or `dropna` behavior changed.

## Changed files

- `src/tw_stock_tool/analysis/indicators.py`
- `tests/test_indicators.py`
- `tests/test_track_c1_research_correctness.py`
- `docs/TRACK_C1_RESEARCH_CORRECTNESS_CHARACTERIZATION.md`
- `docs/TRACK_C2_2_RSI_EDGE_CASE_FIX.md`

## Tests executed

- `py -m unittest tests.test_indicators`
- `py -m unittest tests.test_track_c1_research_correctness`
- `py -m unittest tests.test_signals`, or `NOT_APPLICABLE` if the module does not exist
- `py -m unittest tests.test_indicators tests.test_track_c1_research_correctness`
- `py -m unittest discover -s tests`
- Direct continuous-gain, continuous-loss, and flat RSI checks

Expected failures before: 9. Expected failures after: 8.

## Non-goals

This track does not change finite-number validation, interval-aware metrics, CLI exit behavior, other indicators, smoothing, periods, signal rules, Analyze ready columns, ML, Backtesting, Risk, Paper Trading, or compatibility wrappers.

## Remaining Track C2 work

1. Finite-number validation.
2. Interval-aware metrics.
3. Unified CLI nonzero exit behavior.
