# Track C1 Research Correctness Characterization

## Executive outcome

`RESEARCH_CORRECTNESS_DEFECTS_CONFIRMED`

## Repository baseline

- Branch: `track-c1-research-correctness-characterization`
- Base SHA and latest main integration commit: `5eee34738d9d46c9c0c4ac9a9732d3843f882885`
- Working tree at characterization start: clean except user-owned untracked `custom_md.md`; it was not read, changed, or staged.

## Finding matrix

| ID | Area | Target behavior | Current behavior and exact test | Reproduced / expected failure | Downstream impact and evidence | Track C2 action |
| -- | -- | -- | -- | -- | -- | -- |
| C1-RSI-1 | RSI increasing | Warm RSI is finite and 100. | `IndicatorTest.test_rsi_continuous_gains_reaches_100_after_warmup`: remains NaN. | Yes / expected failure | Direct: `TrackC1ResearchCorrectnessTest.test_analyze_stock_drops_all_rising_rows_when_rsi_is_nan` proves `analyze_stock(...).dropna(subset=[..., RSI])` removes every rising row and raises before a latest row exists. `test_generate_signals_keeps_rows_with_nonfinite_rsi` proves signals alone retain rows. | Define and implement finite gain behavior. |
| C1-RSI-2 | RSI falling | Warm RSI is 0. | `IndicatorTest.test_rsi_continuous_losses_reaches_0_after_warmup` passes. | NOT_REPRODUCED / no | No adverse direct finding. | No correction required. |
| C1-RSI-3 | RSI flat | Contract must be explicit. | `IndicatorTest.test_rsi_flat_series_currently_remains_nan_after_warmup` confirms NaN. `CURRENT_BEHAVIOR_CONFIRMED. Final contract remains undecided for Track C2.` | No defect label / no | Direct ready-column removal applies if this data reaches analysis. Scanner, Daily Report, and ML Dataset effects are code-path inference only and were not integration-tested. | Select 50, 0, or retained NaN contract. |
| C1-ML-1 | Walk-forward labels | A train label must not use a price in its test window. | `TrackC1ResearchCorrectnessTest.test_walk_forward_purges_train_labels_that_reach_test_window` computes `feature_row_date`, `label_source_date`, and `first_test_date` with horizon=5, train=8, test=4. The indices do not overlap but tail labels reach the test window. | Yes / expected failure | Direct split/data-index evidence. Baseline ML uses the same future-label dataset; no model training was run. | Purge gap, remove tail horizon rows, or add explicit label-end times. |
| C1-FIN-1 | Backtest | Parameters and Open/Close must be finite. | `test_backtest_rejects_nonfinite_parameters_and_prices` shows parameter validation does not universally reject NaN; existing `BacktestTest.test_nan_open_price_skips_execution_safely` documents NaN Open is skipped, not rejected. | Yes / expected failure | Direct unit evidence; no production change. | Add finite validation for all inputs and bar prices. |
| C1-FIN-2 | Risk snapshot/rules | Monetary and exposure values must be finite. | `test_risk_snapshot_rejects_nonfinite_numeric_fields` accepts at least NaN for price/cash/notional/exposure. Existing rule tests show zero, negative, bool, and wrong-type limits are rejected. | Yes / expected failure | Direct snapshot evidence; rules consume validated snapshot values (code-path inference for propagated NaN). | Validate finite snapshot values and monetary/exposure limits. |
| C1-FIN-3 | Simulated models | Fill money, portfolio cash, and average cost must remain finite. | `test_simulated_fill_and_portfolio_reject_nonfinite_money` confirms non-finite fill/cash acceptance. | Yes / expected failure | Direct constructor evidence; average-cost contamination follows from accepted fill (code-path inference, not a separate integration assertion). | Enforce finite values before fill/portfolio arithmetic. |
| C1-FIN-4 | Guard adapter | Reference/exposure providers reject bool, non-finite, and negative values. | Exposure rejection is directly confirmed by `test_guard_adapter_rejects_nonfinite_and_boolean_exposure`; `test_guard_adapter_rejects_nonfinite_reference_prices` confirms NaN/+Infinity reference-price defect. | Mixed: exposure CORRECTLY_REJECTED; reference price defect / expected failure | Direct adapter tests. | Use finite reference-price check. |
| C1-MET-1 | Sharpe/Sortino | 1d/1wk/1mo annualization is representable as 252/52/12. | `test_metrics_have_daily_factor_and_no_interval_context` proves allowed intervals contain all three and both functions match `sqrt(252)` for the same returns. | Yes / normal characterization test | Direct API evidence. The metrics API cannot represent interval-aware annualization and always applies the daily factor. | Add interval-aware API or restrict metrics to daily bars. |
| C1-CLI-1 | CLI exit status | Runtime errors return nonzero. | `test_ai_walk_forward_runtime_exception_returns_nonzero_exit_status` and `test_analyze_cli_runtime_validation_returns_nonzero_exit_status` show caught runtime errors print and return `None`. `test_argparse_invalid_option_exits_nonzero` passes. | Runtime defects / expected failures; argparse CORRECTLY_REJECTED | Direct invocation evidence: it establishes Python `main()` return behavior; console-entry returncode needs a subprocess follow-up in C2. | Make runtime mains raise `SystemExit(1)` or return and propagate 1. |

## Validation classification

- `CORRECTLY_REJECTED`: argparse invalid option; guard exposure bool/NaN/+Infinity/-Infinity/negative; existing risk-rule negative/bool/wrong-type limits.
- `DEFECT_CONFIRMED`: rising RSI; horizon leakage; finite-number acceptance at Backtest/Risk/Paper boundaries; non-finite reference price; fixed daily annualization; caught CLI runtime exceptions returning `None`.
- `NOT_APPLICABLE`: no separate constructor exists for a Risk-rule quantity limit beyond its rule argument; no interval parameter exists in metrics.

## Expected failure inventory

- `tests.test_indicators.IndicatorTest.test_rsi_continuous_gains_reaches_100_after_warmup` — gain-only RSI stays NaN; Track C2 must make it finite 100.
- `tests.test_track_c1_research_correctness.TrackC1ResearchCorrectnessTest.test_walk_forward_purges_train_labels_that_reach_test_window` — train labels reach test dates; Track C2 must purge horizon overlap.
- `tests.test_track_c1_research_correctness.TrackC1ResearchCorrectnessTest.test_risk_snapshot_rejects_nonfinite_numeric_fields` — snapshot accepts non-finite numeric values; Track C2 must validate finiteness.
- `tests.test_track_c1_research_correctness.TrackC1ResearchCorrectnessTest.test_simulated_fill_and_portfolio_reject_nonfinite_money` — models accept non-finite money; Track C2 must validate finiteness.
- `tests.test_track_c1_research_correctness.TrackC1ResearchCorrectnessTest.test_backtest_rejects_nonfinite_parameters_and_prices` — Backtest lacks complete finite validation; Track C2 must add it.
- `tests.test_track_c1_research_correctness.TrackC1ResearchCorrectnessTest.test_guard_adapter_rejects_nonfinite_reference_prices` — reference provider accepts NaN/+Infinity; Track C2 must require finite positive data.
- `tests.test_track_c1_research_correctness.TrackC1ResearchCorrectnessTest.test_ai_walk_forward_runtime_exception_returns_nonzero_exit_status` — caught runtime error returns None; Track C2 must produce nonzero exit.
- `tests.test_track_c1_research_correctness.TrackC1ResearchCorrectnessTest.test_analyze_cli_runtime_validation_returns_nonzero_exit_status` — caught validation error returns None; Track C2 must produce nonzero exit.

## Downstream impact

Directly demonstrated: Analyze cannot produce a latest row for the deterministic continuous-rise input. `generate_signals` retains rows, so the loss occurs at Analyze ready-column filtering. Backtest, Risk Guard, Paper Trading, Walk Forward, and Baseline ML have the direct boundary findings above.

Code-path inference only: Scanner and Daily Report call analysis-oriented flows and may inherit the empty-analysis failure. ML Dataset can inherit NaN feature removal; Parameter Sweep may inherit Backtest non-finite behavior. These were not executed as end-to-end integrations and are not claimed as direct findings.

## Track C2 bounded recommendation

1. Fix ML horizon leakage.
2. Fix RSI edge cases.
3. Add finite-number validation.
4. Correct or limit non-daily annualized metrics.
5. Standardize nonzero CLI runtime failure exits.

## Explicit non-goals

This phase does not modify production code; fix RSI; change ML split; change metrics; change CLI exits; modify Risk or Paper Trading models; add strategies or data sources; modify artifact schemas; merge/delete Backtest paths; connect brokers; or start Track C2.
## Follow-up matrix reliability evidence

All non-finite matrices now use `_collect_unrejected_cases`: every case invokes the real boundary, records accepted or wrong-exception outcomes, and makes one assertion after the complete loop. No expected-failure matrix uses an assertion inside `subTest`.

### Actual accepted non-finite cases (direct tests)

- RiskInputSnapshot: `price`, `cash`, `current_position_notional`, and `total_exposure` accept `NaN` and `+Infinity`; each rejects `-Infinity`.
- Risk monetary limits: `max_order_notional`, `max_position_notional`, and `max_total_exposure` accept `NaN` and `+Infinity`; each rejects `-Infinity`.
- Risk quantity limit: `NaN`, `+Infinity`, and `-Infinity` are correctly rejected because the API requires an integer. Cash/affordability limit: `NOT_APPLICABLE`; no such risk-rule parameter exists.
- SimulatedFill: `price`, `fee`, `tax`, and `slippage` accept `NaN` and `+Infinity`; each rejects `-Infinity`.
- SimulatedPortfolio initial cash: accepts `NaN` and `+Infinity`, rejects `-Infinity`.
- Portfolio arithmetic: a `NaN` fill price directly contaminates `portfolio.cash` and position `average_cost`; quantity becomes 1. This is direct evidence, not inference.
- Backtest: all parameter and Open/Close cases are invoked. Non-finite handling is not a uniform `BacktestError` contract: accepted/safely-skipped paths are retained as the complete expected-failure evidence. In particular NaN Open is safely skipped by existing execution behavior rather than rejected; price cases are independently invoked in the follow-up matrix.
- Guard reference price: bool, zero, negative finite, and `-Infinity` are correctly rejected; `NaN` and `+Infinity` are accepted (defect).

### Correctly rejected cases (direct tests)

- Guard exposure provider: bool, NaN, +Infinity, -Infinity, and negative finite number.
- Guard reference provider: bool, zero, negative finite number, and -Infinity.
- Risk quantity limit: NaN, +Infinity, and -Infinity.
- Risk monetary limits and RiskInputSnapshot: -Infinity only.
- SimulatedFill and SimulatedPortfolio: -Infinity only.
- argparse invalid option: nonzero `SystemExit`.

### Expected-failure inventory after reliability follow-up

The existing RSI gain, ML leakage, metrics/CLI contracts remain. The matrix expected failures are now complete-case contracts:

- `TrackC1ResearchCorrectnessTest.test_risk_snapshot_rejects_all_nonfinite_numeric_fields` — 12 cases.
- `TrackC1ResearchCorrectnessTest.test_risk_monetary_limits_reject_all_nonfinite_values` — 9 cases.
- `TrackC1ResearchCorrectnessTest.test_simulated_fill_and_portfolio_reject_all_nonfinite_money` — 15 cases.
- `TrackC1ResearchCorrectnessTest.test_portfolio_arithmetic_rejects_nonfinite_fill_before_contamination` — direct NaN fill arithmetic boundary.
- `TrackC1ResearchCorrectnessTest.test_backtest_rejects_all_nonfinite_parameters_and_prices` — 24 cases: six parameters and two price fields, each with NaN/+Infinity/-Infinity.
- `TrackC1ResearchCorrectnessTest.test_guard_adapter_rejects_all_nonfinite_positive_reference_prices` — NaN and +Infinity.

The document is saved UTF-8 without BOM.
