# Track C1 Research Correctness Characterization

## Executive outcome

`RESEARCH_CORRECTNESS_DEFECTS_CONFIRMED`

Track C1 established the original evidence. Track C2.1 resolved ML horizon leakage, Track C2.2 resolved rising and flat RSI edge cases, Track C2.3.1 resolved Risk and Guard finiteness, Track C2.3.2 resolved Paper Trading monetary finiteness and mutable-fill contamination, Track C2.3.3 resolved Backtest parameter and price finiteness, Track C2.4.1 resolved core interval-aware Sharpe and Sortino annualization, Track C2.4.2 propagated the existing Analyze interval into Backtest, and Track C2.5 resolved scoped CLI runtime exit behavior.

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
| C1-FIN-1 | Backtest finite values | RESOLVED in Track C2.3.3 | `test_backtest_rejects_all_nonfinite_parameters_and_prices` | Require finite scoped parameters and Open/Close values. |
| C1-FIN-2 | Risk snapshot and limits | RESOLVED in Track C2.3.1 | `test_risk_snapshot_rejects_all_nonfinite_numeric_fields`; `test_risk_monetary_limits_reject_all_nonfinite_values` | Require finite Risk snapshot values and monetary/exposure limits. |
| C1-FIN-3 | Simulated fill/portfolio | RESOLVED in Track C2.3.2 | `test_simulated_fill_and_portfolio_reject_all_nonfinite_money`; `test_portfolio_arithmetic_rejects_nonfinite_fill_before_contamination` | Reject non-finite values before arithmetic or state mutation. |
| C1-FIN-4 | Guard reference price | RESOLVED in Track C2.3.1 | `test_guard_adapter_rejects_all_nonfinite_positive_reference_prices` | Require finite positive reference price. |
| C1-MET-1 | Sharpe/Sortino annualization | RESOLVED in Track C2.4.1 | `test_metrics_use_interval_specific_annualization`; `test_analyze_propagates_selected_interval_to_backtest` | Cover standalone metrics, canonical Backtest APIs, and the existing Analyze interval path. |
| C1-CLI-1 | Runtime exit behavior | RESOLVED in Track C2.5 | `test_ai_walk_forward_runtime_exception_returns_nonzero_exit_status`; `test_analyze_cli_runtime_validation_returns_nonzero_exit_status` | Leaf CLIs return 0/1 and the unified dispatcher propagates child status. |

## Validation classification

RESOLVED:

- ML horizon leakage - Track C2.1.
- RSI rising and flat edge cases - Track C2.2.
- Risk snapshot, Risk monetary limits, and Guard reference price - Track C2.3.1.
- SimulatedFill, SimulatedPortfolio, and fill-arithmetic contamination - Track C2.3.2.
- Backtest parameter and Open/Close finiteness - Track C2.3.3.
- Interval-aware Sharpe and Sortino annualization - Track C2.4.1, with Analyze propagation in Track C2.4.2.
- AI Walk Forward, Analyze, and unified dispatcher runtime exit behavior - Track C2.5.

REMAINING DEFECT_CONFIRMED:

- None.

CORRECTLY_REJECTED includes argparse invalid options, guard exposure bool/non-finite/negative values, and non-finite quantity limits. Risk-rule cash/affordability limit is `NOT_APPLICABLE`: no such rule API exists.

## Expected failure inventory

The current inventory contains exactly zero tests.

## Direct and inferred impact

Direct tests show Track C2.2 keeps rising and flat RSI rows available to Analyze. Track C2.3.1 rejects non-finite Risk snapshot fields, Risk monetary limits, and Guard reference prices. Track C2.3.2 rejects non-finite SimulatedFill and SimulatedPortfolio monetary values and blocks mutable invalid fills before state mutation. Track C2.3.3 rejects non-finite Backtest parameters and Open/Close values while preserving finite non-positive Open execution skips. Track C2.4.1 uses 252, 52, and 12 periods per year for 1d, 1wk, and 1mo Sharpe and Sortino calculations while preserving the daily default. Track C2.4.2 propagates the already existing Analyze interval selection into canonical Backtest annualization. Track C2.5 makes AI Walk Forward and Analyze return 0 on success and 1 for handled runtime failures, and makes the unified dispatcher propagate integer child statuses while normalizing legacy `None` returns to 0. Other high-level workflows that do not expose interval selection remain unchanged. The original ML split leakage was resolved in Track C2.1. Scanner, Daily Report, ML Dataset, and Parameter Sweep effects remain code-path inference unless separately integration-tested.

## Remaining bounded recommendation

1. Aggregate closeout audit and merge decision.

## Non-goals

Track C1 did not change production behavior. Track C2.1 changed only ML split leakage. Track C2.2 changed only RSI rising and flat edge-case behavior. Track C2.3.1 changed only Risk and Guard finite validation. Track C2.3.2 changed only Paper Trading monetary validation and mutable-fill defenses. Track C2.3.3 changed only Backtest parameter and Open/Close finite validation. Track C2.4.1 changed only core Sharpe/Sortino annualization and explicit canonical Backtest interval context. Track C2.4.2 propagated the existing Analyze interval into Backtest; it did not expose interval selection through Parameter Sweep, Walk Forward, Strategy Compare, Backtest Report, or other high-level CLIs, and did not alter signal timing, result schemas, targets, reports, artifacts, strategies, data sources, or broker integration. Track C2.5 changed only the AI Walk Forward, Analyze, and unified `twstock` exit-code path; it did not migrate other child CLIs, change argparse behavior, merge branches, or start an aggregate closeout audit.