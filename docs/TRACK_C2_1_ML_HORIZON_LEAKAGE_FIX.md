# Track C2.1 ML Horizon Leakage Fix

## Baseline

- Baseline Track C1 commit: `ea08fca8e226a56eddb07928219e619dd9b49670`
- Branch: `track-c2-research-correctness-fixes`

## Problem and approved design

The chronological split previously placed the test window immediately after training. A training row's horizon label could therefore consume a price in the test window. The fix retains the complete requested training set and inserts a horizon-sized purge gap before the test set.

`split_time_windows` now accepts keyword-only `purge_size=0` for compatibility. Production workflows pass `purge_size=horizon`.

## Before and after

For horizon=5, train_size=8, test_size=4:

- Before: train 0-7; test 8-11; train labels could reach the test set.
- After: train 0-7; purge 8-12; test 13-16. The last train label source is 12, before first test position 13.

## Compatibility

- Default `purge_size=0` retains direct adjacent splits.
- Tuple return format, window numbering, result schema, ordering, and step-size behavior are unchanged.
- `train_size` and `test_size` remain actual model-training and evaluation row counts.
- Required rows are `train_size + purge_size + test_size`.

## Changed files

- `src/tw_stock_tool/ml/ai_walk_forward.py`
- `src/tw_stock_tool/ml/baseline_ml_model.py`
- `tests/test_ai_walk_forward.py`
- `tests/test_baseline_ml_model.py`
- `tests/test_track_c1_research_correctness.py`
- `docs/TRACK_C1_RESEARCH_CORRECTNESS_CHARACTERIZATION.md`
- this report

## Verification

Targeted tests cover zero-purge compatibility, explicit gap slicing, required rows, negative purge rejection, real AI walk-forward slicing, baseline model slicing and metrics, and the converted C1 leakage proof.

Expected failures changed from 10 to 9 because only the ML leakage characterization defect is now resolved.

## Non-goals and remaining findings

This change does not alter ML target calculation, model settings, reporting schema, RSI, finite-number validation, metrics, or CLI exit behavior. Remaining Track C1 work: RSI edge cases, finite-number validation, interval-aware metrics, and CLI nonzero exit behavior.

## Closeout follow-up

- Duplicate leakage assertion removed.
- Track C1 stale test references corrected.
- Track C1 expected-failure inventory normalized to 9 current tests.
- ML horizon leakage classification changed from confirmed to resolved.
- Final amended commit is recorded in the final execution report.
