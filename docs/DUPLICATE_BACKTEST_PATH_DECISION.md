# Duplicate Backtest Path Decision

## A. Executive decision

**INSUFFICIENT_EVIDENCE_RETAIN_TEMPORARILY.** The active/canonical DataFrame-oriented `backtesting/` path has application, report, artifact, and root-wrapper consumers. The alternate class-based `backtest/engine.py` path has dedicated tests but no identified application caller or package export. Their semantics are materially different, and external imports remain unknown. Retention is safer than merging, adapting, or deprecating without an adapter contract and migration window.

## B. Scope and terminology

The canonical path is `backtesting/backtest.py`, `results.py`, `signals.py`, and `strategies.py`; it accepts DataFrames and standardized or legacy signals. The alternate path is `backtest/engine.py` with `strategies/base.py`; it consumes a strategy object. Root compatibility wrappers are `backtest.py` and `strategies.py`; both target canonical `tw_stock_tool.backtesting` modules. External-usage uncertainty means repository search cannot prove external absence. A characterization test records current behavior without requiring parity.

## C. Caller, export, and test matrix

| Path or symbol | Runtime consumers | Wrappers/exports | Tests | Docs | External certainty | Risk |
|---|---|---|---|---|---|---|
| `backtesting.run_backtest_result` / canonical `BacktestResult` | reports, parameter sweep, walk-forward, serialization, paper-trading converter | root backtest.py targets canonical path; no package initializer export | backtest/result/artifact/converter tests | README report and artifact workflows | unknown external imports | High |
| `backtest.BacktestEngine` / alternate `BacktestResult` | no production, CLI, GUI, report, or artifact caller found | no package export; no root wrapper target | test_backtest_engine.py and characterization tests | inventory/architecture docs | unknown external imports | High |
| `strategies.BaseStrategy` | no application caller found | no package export; root strategies.py targets canonical backtesting.strategies | test_strategy_base.py and characterization tests | inventory docs | unknown external imports | High |
| canonical artifact result | backtesting serialization and paper-trading conversion | artifact CLI imports `tw_stock_tool.backtesting.results.BacktestResult` | artifact and conversion tests | phase artifact docs | established internal contract | High |

Tests preserve behavior; they do not alone establish a supported external API.

## D. Semantic comparison

| Concern | Canonical DataFrame path | Alternate class-based path | Status |
|---|---|---|---|
| Input and strategy interface | DataFrame signal columns, including legacy `Signal` | strategy object with `generate_signals` and `validate_signals` | Materially different |
| Timing | next-bar open pending order | previous-bar signal at next open | Equivalent |
| Final-bar signal | cannot execute | cannot execute | Equivalent |
| Position sizing | integer affordable shares; `position_size` | all-in fractional shares | Materially different |
| Fees/tax | fee_rate on entry and fee/tax on exit | commission on both sides, tax on exit | Similar but not identical |
| Slippage | no direct parameter | explicit entry/exit slippage | Present only in alternate |
| Stops/take profit/max hold | supported | absent | Present only in canonical |
| Invalid open | skips pending execution | no equivalent invalid-open guard | Materially different |
| End of data | forced `SELL_EOD` at final close | position remains open and is marked to market | Materially different |
| Trade log | `PnL_pct`, hold days, exit reason, type | `PnL %` compact columns | Materially different |
| Equity/metrics | equity curve and broad metrics | final equity, total return, drawdown, win rate | Materially different |
| Adapter | `to_legacy_dict` | compact `to_dict` | Materially different |
| Validation/errors | BacktestError for canonical inputs | ValueError for engine/strategy inputs | Materially different |
| Mutation | mutable/slotted result | frozen compact result | Materially different |
| Artifact consumers | serialization, artifact CLI, paper-trading conversion | none found | Present only in canonical |

## E. Compatibility constraints

Unknown external imports prevent deletion. Dedicated alternate tests protect behavior. Root wrappers target the canonical path, and artifact consumers use canonical `backtesting.results.BacktestResult`, not the alternate result. Existing reports and CLIs depend on canonical fields. Silent changes to fractional shares, EOD liquidation, fees/tax/slippage, trade-log columns, or exception behavior would be breaking.

## F. Alternatives considered

| Decision | Benefits | Risks and required work | Outcome |
|---|---|---|---|
| RETAIN_DISTINCT | lowest immediate risk | requires distinct public purpose documentation | not selected: external contract still unclear |
| FREEZE_AND_PLAN_DEPRECATION | reduces future ambiguity | adapter, warnings, release window, migration tests | rejected: insufficient external evidence |
| ADAPT_TO_CANONICAL | one runtime direction | must preserve or intentionally migrate all material semantics | rejected: no approved migration contract |
| MERGE_IMPLEMENTATIONS | less duplicated code | high semantic and artifact break risk | rejected |
| INSUFFICIENT_EVIDENCE_RETAIN_TEMPORARILY | preserves contracts while evidence is gathered | maintains two paths temporarily | selected |

## G. Recommended future migration sequence

1. Compatibility-contract phase: enumerate imports, result and artifact consumers.
2. Adapter or deprecation-boundary phase only after approval.
3. Documentation and warning phase with a release window.
4. Application-caller migration phase.
5. Release-window phase with migration tests and rollback plan.
6. Retained-boundary or eventual breaking-release removal phase.

## H. Production-phase entry criteria

Before code changes: approve this decision; keep characterization tests passing; document a canonical replacement; acknowledge external uncertainty; protect artifact and CLI contracts; prepare migration tests; define rollback; and prohibit silent semantic changes.

## I. Explicit non-goals

A2 does not delete, move, modify, adapt, or warn on either engine; change imports, CLI behavior, reports, schemas, result names, trading semantics, or add broker/real-trading functionality.

## J. Final recommendation

Selected label: **INSUFFICIENT_EVIDENCE_RETAIN_TEMPORARILY**. Recommended next production phase: **Backtest Compatibility Contract and Consumer Evidence**. Its only allowed scope is consumer mapping and approved adapter/deprecation-boundary design; it must not consolidate implementations, change semantics, or remove modules.
