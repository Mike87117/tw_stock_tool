# Track C1 Research Correctness Characterization

## Executive outcome

`RESEARCH_CORRECTNESS_DEFECTS_CONFIRMED`

Track C1 established the original evidence. Track C2.1 resolved the ML horizon-leakage finding, and Track C2.2 resolved the rising and flat RSI edge cases.

## Repository baseline

- Original characterization branch: `track-c1-research-correctness-characterization`
- Original base SHA: `5eee34738d9d46c9c0c4ac9a9732d3843f882885`
- Track C1 characterization commit: `ea08fca8e226a56eddb07928219e619dd9b49670`

## Finding matrix

| ID | Area | Current status | Exact test evidence | Track C2 action |
| -- | -- | -- | -- | -- |
| C1-RSI-1 | Rising RSI | RESOLVED in Track C2.2 | `IndicatorTest.test_rsi_continuous_gains_reaches_100_after_warmup`; `TrackC1ResearchCorrectnessTest.test_analyze_stock_keeps_rising_rows_when_rsi_is_finite` | Warm gain-only RSI is finite 100. |
| C1-RSI-2 | Falling RSI | NOT_REPRODUCED | `IndicatorTest.test_rsi_continuous_losses_reaches_0_after_warmup` | None. |
| C1-RSI-3 | Flat RSI | RESOLVED in Track C2.2 | `IndicatorTest.test_rsi_flat_series_is_neutral_50_after_warmup`; `TrackC1ResearchCorrectnessTest.test_analyze_stock_keeps_flat_rows_with_neutral_rsi` | Flat RSI is 50 after warmup. |
| C1-ML-1 | Horizon leakage | RESOLVED in Track C2.1 | `TrackC1ResearchCorrectnessTest.test_walk_forward_purges_train_labels_that_reach_test_window` | Horizon-sized purge gap between train and test. |
| C1-FIN-1 | Backtest finite values | DEFECT_CONFIRMED | `test_backtest_rejects_all_nonfinite_parameters_and_prices` | Validate all parameters and Open/Close. |
| C1-FIN-2 | Risk snapshot and limits | DEFECT_CONFIRMED | `test_risk_snapshot_rejects_all_nonfinite_numeric_fields`; `test_risk_monetary_limits_reject_all_nonfinite_values` | Validate snapshot values and monetary/exposure limits. |
| C1-FIN-3 | Simulated fill/portfolio | DEFECT_CONFIRMED | `test_simulated_fill_and_portfolio_reject_all_nonfinite_money`; `test_portfolio_arithmetic_rejects_nonfinite_fill_before_contamination` | Reject non-finite values before arithmetic. |
| C1-FIN-4 | Guard reference price | DEFECT_CONFIRMED | `test_guard_adapter_rejects_all_nonfinite_positive_reference_prices` | Require finite positive reference price. |
| C1-MET-1 | Sharpe/Sortino annualization | DEFECT_CONFIRMED | `test_metrics_have_daily_factor_and_no_interval_context` | Represent 1d/1wk/1mo annualization. |
| C1-CLI-1 | Runtime exit behavior | DEFECT_CONFIRMED | `test_ai_walk_forward_runtime_exception_returns_nonzero_exit_status`; `test_analyze_cli_runtime_validation_returns_nonzero_exit_status` | Return or propagate nonzero exit. |

## Validation classification

RESOLVED:

- ML horizon leakage — resolved in Track C2.1 by a horizon-sized purge gap.
- RSI rising and flat edge cases — Track C2.2.

REMAINING DEFECT_CONFIRMED:

- finite-number validation defects at Backtest, Risk, Paper Trading, and Guard reference price boundaries;
- fixed daily annualization;
- caught CLI runtime exceptions returning `None`.

CORRECTLY_REJECTED includes argparse invalid options, guard exposure bool/non-finite/negative values, and non-finite quantity limits. Risk-rule cash/affordability limit is `NOT_APPLICABLE`: no such rule API exists.

## Expected failure inventory

The current inventory contains exactly eight tests:

1. `tests.test_track_c1_research_correctness.TrackC1ResearchCorrectnessTest.test_risk_snapshot_rejects_all_nonfinite_numeric_fields`
2. `tests.test_track_c1_research_correctness.TrackC1ResearchCorrectnessTest.test_risk_monetary_limits_reject_all_nonfinite_values`
3. `tests.test_track_c1_research_correctness.TrackC1ResearchCorrectnessTest.test_simulated_fill_and_portfolio_reject_all_nonfinite_money`
4. `tests.test_track_c1_research_correctness.TrackC1ResearchCorrectnessTest.test_portfolio_arithmetic_rejects_nonfinite_fill_before_contamination`
5. `tests.test_track_c1_research_correctness.TrackC1ResearchCorrectnessTest.test_backtest_rejects_all_nonfinite_parameters_and_prices`
6. `tests.test_track_c1_research_correctness.TrackC1ResearchCorrectnessTest.test_guard_adapter_rejects_all_nonfinite_positive_reference_prices`
7. `tests.test_track_c1_research_correctness.TrackC1ResearchCorrectnessTest.test_ai_walk_forward_runtime_exception_returns_nonzero_exit_status`
8. `tests.test_track_c1_research_correctness.TrackC1ResearchCorrectnessTest.test_analyze_cli_runtime_validation_returns_nonzero_exit_status`

The ML leakage test is intentionally absent because it passes after Track C2.1.

## Direct and inferred impact

Direct tests show Track C2.2 keeps rising and flat RSI rows available to Analyze, while non-finite values still cross the stated boundaries. The original ML split leakage was resolved in Track C2.1. Scanner, Daily Report, ML Dataset, and Parameter Sweep effects remain code-path inference unless separately integration-tested.

## Remaining bounded recommendation

1. Finite-number validation.
2. Interval-aware metrics.
3. Unified CLI nonzero exit behavior.

## Non-goals

Track C1 did not change production behavior. Track C2.1 changed only ML split leakage. Track C2.2 changed only RSI rising and flat edge-case behavior and did not alter finite validation, metrics, CLI behavior, targets, models, reports, artifacts, strategies, data sources, or broker integration.
