# Track C3.3 Parameter Sweep Correctness Characterization

## Executive outcome

Track C3.3 directly exercised Parameter Sweep from a mocked external download boundary through real Analysis, indicators, signals, parameter-specific strategies, canonical Backtest, ranking, and in-memory report-data construction. All established contracts were correctly handled. No production defect was confirmed. Equal-metric rows preserved input grid order, but that tie order is `CONTRACT_UNDECIDED` because no explicit repository contract guarantees it.

Formal result: `Track C3.3 Characterization: PASS — NO DEFECT CONFIRMED`

## Repository and stacked-branch baseline

- Repository: `Mike87117/tw_stock_tool`
- `main` and `origin/main`: `e41181bbdcb79c6d8dffc5353b00755dfc2893bb`
- C3.1: `bfbcf135fc64ea66b6bd79625957445ac5b84923`
- Parent branch: `track-c3-2-ml-dataset-correctness-characterization`
- Parent HEAD: `653c78f59d2b031b87595169b180800b88996c3b`
- Parent relationship to main: 2 commits ahead, 0 behind
- Parent suite: 1,473 tests, 0 failures, 0 errors, 0 expected failures, `OK`
- C3.3 branch: `track-c3-3-parameter-sweep-correctness-characterization`
- C3.1 and C3.2 commits and historical files remained unchanged.

## LLM Wiki result

- Health: available and running
- Version: `0.5.4`
- Active project: `tw_stock_tool Wiki`
- Search: `parameter sweep analyze strategy canonical backtest ranking error row Sharpe report best row interval`
- Summary: results identified Parameter Sweep, Backtest, report, and test context, but did not establish the detailed end-to-end contracts characterized here. Repository source and tests remained authoritative.

## Existing coverage inventory

Existing Parameter Sweep unit tests cover grid construction, mocked orchestration, sorting, ranking, `top`, per-parameter errors, and unsupported inputs. Report tests cover result selection and rendering, while CLI tests cover parsing, forwarding, and exit behavior. Backtest, metrics, indicators, signals, C1, C3.1, and C3.2 provide their own focused contracts.

The missing boundary was direct evidence across real `analyze_stock()`, indicator and signal generation, parameter-specific strategy generation, canonical `run_backtest()`, sweep aggregation, and report best-row selection. Existing tests that mock both Analysis and Backtest were not treated as proof of that complete path.

## Direct integration path tested

`tests/test_track_c3_3_parameter_sweep_correctness.py` patches only `tw_stock_tool.analysis.analysis.download_tw_stock` in its complete-path scenarios. It supplies deterministic in-memory OHLCV data and exercises:

```text
mocked external download boundary
→ analyze_stock
→ add_indicators
→ generate_signals
→ score / MA-cross / RSI strategy generation
→ canonical run_backtest
→ sweep sorting and ranking
→ parameter sweep report-data builder
```

No live market data, future data, output files, caches, or model files were used.

## Finding matrix

| ID | Area | Scenario | Expected contract | Observed behavior | Evidence type | Classification | Downstream impact | Future action |
|---|---|---|---|---|---|---|---|---|
| A | Score sweep | Four valid custom combinations | Complete real path, one finite rankable row per combination | Four successful rows, matching parameters, empty errors, descending selected metric, consecutive ranks | Direct integration | `CORRECTLY_HANDLED` | Score sweeps are directly supported by canonical results | None |
| B | MA-cross sweep | Two valid combinations and `top=1` | Evaluate every combination before limiting sorted successes | Both combinations matched explicit strategy/Backtest results; `top=1` retained the best success | Direct integration | `CORRECTLY_HANDLED` | No silent omission or pre-evaluation truncation | None |
| C | RSI sweep | Valid combinations plus gain-only, loss-only, and flat inputs | Preserve finite RSI edge behavior through the sweep | Warm RSI values reached 100, 0, and 50 as applicable; valid rows remained usable | Direct integration | `CORRECTLY_HANDLED` | Track C2 RSI behavior survives Parameter Sweep | None |
| D | Error isolation | One invalid and one valid RSI combination with `top=1` | Complete the valid row, retain the invalid unranked error row | Ranked success preceded one unranked row containing strategy validation text | Direct integration | `CORRECTLY_HANDLED` | One invalid parameter pair does not terminate the sweep | None |
| E | All failed | Two invalid RSI combinations | Return structured errors without fabricated ranks or metrics | Two unranked error rows returned; metric fields were empty | Direct integration | `CORRECTLY_HANDLED` | Callers receive complete failure evidence without a crash | None |
| F | Finite validation | Retained non-finite `Open` with two Score combinations | Canonical Backtest rejects before invalid arithmetic; sweep isolates each attempt | Analysis retained the row; both combinations reached Backtest and became finite-value error rows | Direct integration | `CORRECTLY_HANDLED` | Track C2 finite validation reaches Parameter Sweep | None |
| G1 | Sorting/ranking/top | Real successful Score results with positive, zero, and negative `top` | Descending sort, consecutive ranks, positive limit only | All results returned for `top <= 0`; `top=2` returned the two highest successes | Direct integration | `CORRECTLY_HANDLED` | Public result limiting matches established behavior | None |
| G2 | Tie order | Equal selected metric values | Do not invent an undocumented tie guarantee | Stable merge sorting preserved requested grid order | Direct observation | `CONTRACT_UNDECIDED` | Consumers should not rely on tie order as a public promise | Define only if a consumer requires it |
| H | Daily metrics | Sweep row versus explicit Backtest `interval="1d"` | Same Sharpe/Sortino; no public interval argument | Metrics matched and signature inspection found no interval parameter | Direct integration and signature inspection | `NOT_APPLICABLE` | Daily default is confirmed; weekly/monthly support is not claimed | None |
| I | Report best row | Reordered real results including an error row | Preserve Results and choose highest numeric Sharpe | Results were unchanged; Best Row was the highest numeric Sharpe, not the first/error row | Direct integration | `CORRECTLY_HANDLED` | Report summary identifies the correct successful row | None |
| J | Public propagation | All public execution/risk arguments and custom ranges | Forward existing arguments without adding interval | Downloader, strategy grid, and Backtest calls received the requested values; no interval was forwarded | Direct boundary observation | `CORRECTLY_HANDLED` | Existing public controls reach their intended boundaries | None |

## Score sweep result

Four bounded parameter combinations executed through real Analysis, Score strategy generation, and canonical Backtest. Each requested pair appeared exactly once. Every successful row had an empty error, numeric contract metrics were finite, the selected metric was descending, and ranks were consecutive.

Classification: `CORRECTLY_HANDLED`.

## MA-cross sweep result

Two bounded MA combinations produced crossover signals and completed canonical Backtest. Each sweep row matched a separately generated strategy frame and explicit Backtest result. `top=1` was applied after both combinations were evaluated and sorted.

Classification: `CORRECTLY_HANDLED`.

## RSI sweep result

Real rising-and-falling input produced finite post-warmup RSI values and usable rows for both requested threshold pairs. Additional gain-only, loss-only, and flat inputs preserved RSI values of 100, 0, and 50 respectively without causing sweep errors.

Classification: `CORRECTLY_HANDLED`.

## Mixed valid/invalid parameter result

The valid RSI pair completed and received rank 1. The out-of-range pair was independently attempted, retained its real strategy-validation message, remained unranked, and followed the success row. With `top=1`, the successful set was limited while the error evidence remained present.

Classification: `CORRECTLY_HANDLED`.

## All-failed result

Both requested invalid RSI pairs produced structured error rows. No rank or successful metric was fabricated, every pair was represented, and the sweep returned normally.

Classification: `CORRECTLY_HANDLED`.

## Finite-value boundary result

A controlled `NaN` in `Open` survived Analysis and strategy generation. Canonical Backtest rejected it before invalid arithmetic, and Parameter Sweep captured the rejection independently for both attempted Score combinations. No successful metric row was produced.

Classification: `CORRECTLY_HANDLED`.

## Sorting, ranking, and top result

Real successful results sorted descending by the selected metric and received consecutive ranks. Positive `top` limited sorted successes; zero and negative values returned all successes. Error rows stayed after successes and remained unranked. Equal values preserved input grid order through the current stable sort, but no explicit contract guarantees that order.

Sorting/ranking classification: `CORRECTLY_HANDLED`. Tie-order classification: `CONTRACT_UNDECIDED`.

## Daily interval default result

The sweep row's Sharpe and Sortino matched an independently executed canonical Backtest using `interval="1d"`. Signature inspection confirmed that `run_parameter_sweep()` has no interval parameter. Daily metric behavior is directly confirmed; no weekly or monthly Parameter Sweep support or propagation is claimed.

Public interval propagation classification: `NOT_APPLICABLE`.

## Report best-row result

The in-memory report builder preserved the full Results frame unchanged. Its Best Row was the row with the highest numeric Sharpe Ratio even when input order was reversed and an error row was present. It did not assume the first sweep row was best.

Classification: `CORRECTLY_HANDLED`.

## Public parameter propagation result

Direct boundary observation confirmed propagation of `stock_id`, `period`, `force_refresh`, `initial_capital`, `fee_rate`, `tax_rate`, `position_size`, `stop_loss_pct`, `take_profit_pct`, `max_hold_days`, and custom strategy ranges. A separate narrow Backtest spy was used only for arguments not reliably observable in final metrics. No interval argument exists or was invented.

Classification: `CORRECTLY_HANDLED`.

## Expected-failure inventory

- Before C3.3: 0
- Added by C3.3: 0
- After C3.3: 0
- Confirmed defects: 0
- Contract-undecided findings: 1
- Inference-only findings: 0

## Direct evidence versus inference

All finding-matrix behavior except the normative meaning of tie ordering was directly exercised with deterministic data. Tie ordering itself was directly observed, but whether it is promised remains contract-undecided. No finding is inference-only.

## Production files changed

None.

## Test files changed

- Added `tests/test_track_c3_3_parameter_sweep_correctness.py` with 11 tests.

## Documentation files changed

- Added `docs/TRACK_C3_3_PARAMETER_SWEEP_CORRECTNESS_CHARACTERIZATION.md`.

## Validation commands

```powershell
py -m unittest tests.test_track_c3_3_parameter_sweep_correctness
# Ran 11 tests; 11 passed; 0 expected failures; 0 failures; 0 errors; OK

py -m unittest tests.test_track_c3_3_parameter_sweep_correctness tests.test_track_c3_2_ml_dataset_correctness tests.test_track_c3_1_scanner_daily_correctness tests.test_parameter_sweep tests.test_parameter_sweep_report tests.test_parameter_sweep_report_cli tests.test_backtest tests.test_backtest_metrics tests.test_indicators tests.test_signals tests.test_track_c1_research_correctness
# Ran 162 tests; 162 passed; 0 expected failures; 0 failures; 0 errors; OK

py -m unittest discover -s tests
# Ran 1,484 tests; 1,484 passed; 0 expected failures; 0 failures; 0 errors; OK
```

The full count increased from 1,473 to 1,484, exactly matching the 11 new tests.

## Non-goals

This track did not change production code, strategy formulas, Backtest execution, metrics, grids, ranking, errors, reports, exporters, CLI behavior, dependencies, or interval support. It did not use live data, start a production fix, merge a characterization branch, or continue to another phase. `custom_md.md` was not accessed or changed.

## Recommended next action

Hold this characterization branch. No production phase is justified because no correctness defect was confirmed. Define tie ordering only if a real consumer requires a guaranteed tie-break contract.

Branch disposition: `HOLD`.
