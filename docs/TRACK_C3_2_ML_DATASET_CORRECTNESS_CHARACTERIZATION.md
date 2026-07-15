# Track C3.2 ML Dataset Correctness Characterization

## Executive outcome

`PASS - NO DEFECT CONFIRMED`

Deterministic offline tests now exercise the real download-boundary-to-Analysis
and ML Dataset path. Continuous-rise data produces a finite, aligned dataset.
Zero-range flat data produces an empty default `dropna=True` dataset solely
because stochastic `K` and `D` are `NaN`; `dropna=False` preserves the expected
horizon-trimmed zero-return and false-target rows.

The repository defines feature selection, target construction, horizon
trimming, and optional missing-value removal, but it does not require valid
flat input to yield a non-empty dataset or an explicit error. The silent empty
default result is therefore `CONTRACT_UNDECIDED`, not a confirmed defect. No K/D
policy was invented and no production fix was started. Recommended branch
disposition: `HOLD`.

## Repository and stacked-branch baseline

- Repository: `Mike87117/tw_stock_tool`
- `main`: `e41181bbdcb79c6d8dffc5353b00755dfc2893bb`
- `origin/main`: `e41181bbdcb79c6d8dffc5353b00755dfc2893bb`
- Parent branch: `track-c3-1-scanner-daily-correctness-characterization`
- Parent branch HEAD: `bfbcf135fc64ea66b6bd79625957445ac5b84923`
- Parent branch relation to main: one commit ahead, zero commits behind
- Track C3.2 branch: `track-c3-2-ml-dataset-correctness-characterization`
- Initial Track C3.2 HEAD: `bfbcf135fc64ea66b6bd79625957445ac5b84923`
- Parent full suite: 1,461 tests, 0 failures, 0 errors, 0 expected failures, `OK`
- Initial working tree: clean
- `custom_md.md`: ignored only by `.git/info/exclude`; contents not accessed

Track C3.1 remains historical and unmodified. Neither characterization branch
has been merged.

## LLM Wiki result

- Health: available; `ok: true`, `status: running`
- Version: `0.5.4`
- Active project: `tw_stock_tool Wiki`
- Search: `ML dataset feature dropna stochastic K D NaN future return target horizon AI walk forward baseline model`
- Summary: results covered broad architecture, tests/CI, walk-forward research,
  and non-goals but did not establish a flat-data K/D or empty-dataset contract.
  Repository source, tests, and approved Track documents remained authoritative.

## Existing coverage inventory

| Area | Existing evidence | Boundary before Track C3.2 |
| --- | --- | --- |
| ML Dataset unit behavior | Synthetic signal-frame tests cover future return, target, tail trimming, feature exclusion, positive horizon, and CSV export | Direct unit evidence only |
| ML Dataset integration | Existing test mocks `analyze_stock()` | No real Analysis-to-dataset evidence |
| Analysis | Track C1 patches only the download boundary and proves rising/flat RSI | Direct through Analysis only |
| Scanner/Daily Report | Track C3.1 proves real Analysis integration and zero-range K/D NaN | Direct, but stops before ML Dataset |
| AI Walk Forward | Existing tests mock `build_ml_dataset()` and directly test chronological/purge helpers | Dataset integration mocked |
| Baseline ML | Existing tests mock `build_ml_dataset()` and execute model windows | Dataset integration mocked |

`FEATURE_COLUMNS` contains 17 same-day/historical features, including `K` and
`D`, and excludes all future-return and target columns. Dataset construction
creates `Future_Return_<horizon>D`, creates boolean `Target_Up_<horizon>D`,
removes the final horizon rows, and then optionally calls `dropna()`. AI Walk
Forward and Baseline ML pass a horizon-sized purge to `split_time_windows()`.

## Direct integration path tested

The new module patches only
`tw_stock_tool.analysis.analysis.download_tw_stock` for integration cases and
executes:

```text
download boundary
-> analyze_stock
-> add_indicators
-> generate_signals
-> build_ml_dataset
-> build_ml_dataset_from_signal_df
```

Bounded unit calls to `build_ml_dataset_from_signal_df()`,
`ml_feature_columns()`, and `split_time_windows()` separate missing-feature,
horizon-tail, unsupported-column, and immediate-consumer behavior after the
complete integration behavior is established.

Characterization tests used no network services or live market data. The
required localhost LLM Wiki check was supporting context only and was not part
of the test data path.

## Finding matrix

| ID | Area | Scenario | Expected contract | Observed behavior | Evidence type | Classification | Downstream impact | Future action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C3.2-A | ML Dataset | Continuous rise, default dropna | Finite supported features and correctly trimmed labels | Non-empty; all 17 features finite; RSI 100; K/D finite; final five rows absent | Direct deterministic integration | `CORRECTLY_HANDLED` | Normal dataset remains usable | None |
| C3.2-B | ML Dataset | Zero-range flat, default dropna | Apply documented missing-value removal | Empty without exception or warning; K/D are the only missing supported features | Direct deterministic integration | `CONTRACT_UNDECIDED` | Immediate split cannot create a window | Decide whether empty-or-error policy is required |
| C3.2-C | ML Dataset | Zero-range flat, no dropna | Preserve feature-missing rows after label-tail removal | Rows preserved; K/D NaN; future returns zero; targets boolean false | Direct deterministic integration | `CORRECTLY_HANDLED` | Cause of default empty result is isolated | None |
| C3.2-D1 | Label alignment | Five-row future return | Label at date t uses Close at t+5 while features remain at t | Every retained value matches independently indexed Analysis data | Direct deterministic integration | `CORRECTLY_HANDLED` | No target/date shift observed | None |
| C3.2-D2 | Target alignment | Positive/non-positive future returns | Target is return greater than zero | Boolean target matches every independently calculated return | Direct deterministic integration | `CORRECTLY_HANDLED` | Both target classes align | None |
| C3.2-E | dropna isolation | One supported NaN plus unsupported NaNs | Drop only rows missing supported/output values | One supported-feature row removed; unsupported NaNs ignored; tail already trimmed | Direct bounded unit evidence | `CORRECTLY_HANDLED` | Missingness sources are distinguishable | None |
| C3.2-F1 | Horizon | Positive smaller horizon | Keep only rows with real future values | Non-empty result of length n-horizon; no future NaNs | Direct bounded unit evidence | `CORRECTLY_HANDLED` | Usable labels retained | None |
| C3.2-F2 | Horizon | Horizon equal to frame length | No row has a future label | Empty structured dataset returned | Direct bounded unit evidence | `CORRECTLY_HANDLED` | No fabricated label | None |
| C3.2-F3 | Horizon | Horizon greater than frame length | No row has a future label | Empty structured dataset returned | Direct bounded unit evidence | `CORRECTLY_HANDLED` | No fabricated label | None |
| C3.2-F4 | Horizon | Zero and negative | Reject invalid public value | Explicit `ValueError` for both | Direct bounded unit evidence | `CORRECTLY_HANDLED` | Malformed target names are prevented | None |
| C3.2-G | Immediate AI boundary | Normal and empty datasets | Select present features; create only real chronological windows with requested purge | Normal features exclude labels and preserve five-row purge; empty split raises clear insufficient-row error | Direct deterministic evidence | `CORRECTLY_HANDLED` | No fabricated window; Track C2 purge preserved | None |
| C3.2-H1 | Public parameters | stock, period, horizon, force_refresh, dropna | Existing values reach their current boundaries | Stock is trimmed; period/force reach download; horizon names/trims labels; no-drop preserves K/D NaN | Direct deterministic integration | `CORRECTLY_HANDLED` | Existing API contract preserved | None |
| C3.2-H2 | Public parameters | interval | No interval parameter exists | Signature has no `interval` argument | Direct signature evidence | `NOT_APPLICABLE` | No interval propagation path exists | Do not add one in this track |
| C3.2-I | Baseline ML | Training impact of empty default dataset | Not required for immediate-boundary characterization | Not executed; insufficient-row behavior is inferred from shared splitter use | Inference | `INFERENCE_ONLY` | Baseline cannot obtain a real window from zero rows | Test only if a future contract requires it |

## Continuous-rise dataset result

The real `build_ml_dataset()` path returns a non-empty dataset whose feature
columns exactly match `FEATURE_COLUMNS`. K, D, RSI, and every other retained
numeric feature are finite; RSI is exactly `100.0`. Future-return and target
columns are present but absent from the feature list. Dataset indexes equal the
chronological, unique Analysis signal indexes excluding exactly the final five
horizon rows.

## Flat default-dropna result

For 160 rows with `Open == High == Low == Close`, real Analysis succeeds with
RSI `50.0`. Default `build_ml_dataset(..., dropna=True)` returns an empty frame
without exception, warning, or explicit explanation. Before dropping, K and D
are NaN for every usable row; all other supported features are finite, future
returns are finite zero values, and targets are valid false values. Removing K
and D from a test-local copy allows every otherwise usable row to survive,
directly isolating the cause.

This empty-result behavior is `CONTRACT_UNDECIDED`. The repository documents
missing-row removal but does not require non-empty output or explicit rejection
for this input. No defect and no K/D policy are inferred from inconvenience.

## Flat no-dropna result

`dropna=False` retains exactly `len(signal_df) - horizon` rows. K and D remain
NaN, future returns are exactly zero, targets are boolean false, the first
feature row stays on its original date, and the last five unlabeled rows are
removed without an extra shift.

## Future-return and target alignment result

A reproducible oscillating Close sequence produces both positive and
non-positive five-row future returns. For every retained date, the test locates
that date independently in the real Analysis signal frame, reads Close at t and
t+5, and verifies the stored return and boolean target. The feature Close stays
at t, the target column is boolean, and only the final five source dates are
absent. Future-return and target alignment are both `CORRECTLY_HANDLED`.

## Missing-feature and dropna result

A controlled NaN in one supported RSI row removes exactly that row under
`dropna=True` and remains under `dropna=False`. An unsupported all-NaN column is
never selected and removes no rows. Future-return and target values are already
complete after explicit horizon-tail trimming, distinguishing feature
missingness, target-tail handling, and unsupported-column missingness.

## Horizon boundary result

- Positive horizon smaller than the frame: non-empty `n - horizon` result.
- Horizon equal to frame length: empty structured result.
- Horizon greater than frame length: empty structured result.
- Horizon zero: explicit `ValueError`.
- Negative horizon: explicit `ValueError`.

No case fabricates a future value or malformed target column. Equal and
oversized positive horizons match the established rule that rows without future
data must not be used.

## Immediate AI consumer result

For a normal real dataset, `ml_feature_columns()` includes K and D only when
present and excludes future-return and target columns. `split_time_windows()`
keeps chronological train/test frames and the explicitly supplied five-row
purge, preserving the Track C2.1 horizon-leakage contract.

For the empty flat/default dataset, `ml_feature_columns()` still reports the
present schema, while `split_time_windows()` raises a clear error stating that
seven rows are required and zero were supplied. It does not fabricate a window.
These shared immediate AI helpers were tested directly. Baseline model training
on this empty integrated dataset was not needed and remains `INFERENCE_ONLY`.

## Existing parameter propagation result

Direct download-boundary evidence confirms trimmed `stock_id`, `period`, and
`force_refresh`; dataset shape/columns confirm `horizon` and `dropna`. The
public `build_ml_dataset()` signature has no `interval` parameter, so interval
propagation is `NOT_APPLICABLE`. No interval option was added.

## Expected-failure inventory

- Before: 0
- After: 0
- Confirmed defects: 0
- Contract-undecided findings: 1
- Inference-only findings: 1

No `@unittest.expectedFailure` was added because no repository-supported
correctness contract was directly violated.

## Direct evidence versus inference

Scenarios A-H have direct deterministic evidence at their stated boundaries.
The only normative uncertainty is whether flat/default construction should
silently return empty or explicitly reject/explain the input. Immediate feature
selection, insufficient-row handling, and purge behavior are direct. Baseline
model training impact remains inference because the shared splitter rejects the
empty dataset before any window exists and model training was unnecessary.

## Production files changed

None.

## Test files changed

- `tests/test_track_c3_2_ml_dataset_correctness.py` (new; 12 tests)

## Documentation files changed

- `docs/TRACK_C3_2_ML_DATASET_CORRECTNESS_CHARACTERIZATION.md` (new)

Track C3.1 and all Track C1/C2 historical files remain unchanged.

## Validation commands

- Parent baseline: `py -m unittest discover -s tests` - 1,461 tests, `OK`
- New module: `py -m unittest tests.test_track_c3_2_ml_dataset_correctness` - 12 tests, `OK`
- Combined targeted: `py -m unittest tests.test_track_c3_2_ml_dataset_correctness tests.test_track_c3_1_scanner_daily_correctness tests.test_ml_dataset tests.test_ai_walk_forward tests.test_baseline_ml_model tests.test_track_c1_research_correctness tests.test_indicators tests.test_signals` - 82 tests, `OK`
- Final full suite: `py -m unittest discover -s tests` - 1,473 tests, 0 failures, 0 errors, 0 expected failures, `OK`
- Repository-required suite: `python -m unittest discover -s tests` - 1,473 tests, 0 failures, 0 errors, 0 expected failures, `OK`
- `git diff --check` - passed
- UTF-8 BOM verification - passed for both new files; neither has a UTF-8 BOM

## Non-goals

This track did not modify production code, `FEATURE_COLUMNS`, K/D or RSI
behavior, Analysis filtering, Scanner, Daily Report, AI Walk Forward, Baseline
ML, CLI behavior, dependencies, configuration, or historical documents. It did
not add interval support, train a model, access live market data, invent a K/D
policy, start a production fix, merge or delete branches, push `main`, start
Parameter Sweep characterization, or continue to Track C3.3. `custom_md.md` was
not accessed or changed.

## Recommended next action

Hold the stacked characterization branch for review. If reviewers establish a
contract requiring flat valid input to produce rows or an explicit diagnostic,
plan a separate bounded production-fix phase. Otherwise no production action is
indicated. Branch disposition: `HOLD`.
