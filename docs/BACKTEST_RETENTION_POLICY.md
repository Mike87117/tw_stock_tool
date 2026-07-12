# Backtest Retention Policy

## A. Policy decision

**RETAIN_WITHOUT_DEPRECATION**. A4 found distribution exposure while external usage remains uncertain and no prior compatibility policy or migration window existed. Alternate paths remain available without warnings; they are not canonical or recommended. No deprecation countdown has started.

## B. Scope and terminology

Canonical path: `tw_stock_tool.backtesting`. Alternate path: `tw_stock_tool.backtest.engine` and `tw_stock_tool.strategies.base`. Retention means import availability, not semantic equivalence or permanent support. Compatibility means preserving current boundaries. A behavioral guarantee is an explicitly supported contract. Deprecation, warning, removal, migration, compatibility window, and dedicated production phase require separate approval. Removal is not authorized.

## C. Current status matrix

| Symbol | Import path | Status | Wheel | Root export | Internal production caller | Canonical relation | Guarantee | Artifact support |
|---|---|---|---|---|---|---|---|---|
| BacktestEngine | tw_stock_tool.backtest.engine | TEMPORARY_COMPATIBILITY_RETAINED | yes | no | none identified | canonical backtesting engine | import only | NOT_SUPPORTED |
| alternate BacktestResult | tw_stock_tool.backtest.engine | CHARACTERIZED_NOT_GUARANTEED | yes | no | none identified | distinct canonical result | not interchangeable | NOT_SUPPORTED |
| SignalStrategy | tw_stock_tool.backtest.engine | TEMPORARY_COMPATIBILITY_RETAINED | yes | no | none identified | no drop-in guarantee | import only | NOT_SUPPORTED |
| BaseStrategy | tw_stock_tool.strategies.base | TEMPORARY_COMPATIBILITY_RETAINED | yes | no | none identified | canonical strategies differ | import only | NOT_SUPPORTED |

## D. Canonical development policy

New production development must use `tw_stock_tool.backtesting`. New dependencies on `tw_stock_tool.backtest.engine` or `tw_stock_tool.strategies.base` are prohibited by documented policy only. Exceptions are dedicated tests, characterization/contract tests, architecture documents, or separately approved migration/adapter phases.

## E. Retention commitment

Retained: existing module files, direct imports, symbol names, wheel inclusion, dedicated tests, and distinct result identities. Retention continues until a future dedicated phase changes policy. **No deprecation clock is currently running.** No removal date is promised.

## F. Supported and non-guaranteed boundaries

| Boundary | Commitment | Guarantee | Reason | Change authority |
|---|---|---|---|---|
| Direct import availability | retained | import-only | external usage unknown | dedicated phase |
| Wheel inclusion | retained | distribution surface | wheel evidence | dedicated phase |
| Symbol names | retained | compatibility | tests/imports | dedicated phase |
| Dedicated tests | retained | maintained behavior | existing tests | normal test changes |
| Semantic equivalence | none | not guaranteed | A2 divergence | production phase |
| Result interchangeability | none | NOT_SUPPORTED | distinct classes | adapter phase |
| Canonical serialization/converter | canonical only | supported canonical | type boundary | production phase |
| Feature parity | none | not guaranteed | materially different engines | production phase |
| New alternate features | prohibited | not supported | canonical development rule | dedicated phase |
| NaN-open behavior | observed only | CHARACTERIZED_NOT_GUARANTEED | A2 evidence | production fix phase |
| Artifact schema | canonical only | supported canonical | consumers | production phase |
| Package-root exports | none | not promised | initializers empty | dedicated phase |

## G. Known behavioral divergence

A2 characterizes distinct result identity, strategy interfaces, integer versus fractional quantities, trade schemas, EOD lifecycle, invalid-open behavior, and serializer/converter rejection. These are characterized differences or unsupported integrations, not convergence promises or fixes.

## H. Distribution and import policy

Alternate modules are in the local wheel and all three known tags (`v0.1.0`, `v0.2.0`, `v0.3.0`); first tagged exposure is `v0.1.0`. Public package-index lookup found no matching distribution, which does not eliminate Git, editable, private-index, archived, or fork usage. Alternate initializers export nothing; root wrappers target canonical modules. Wheel removal is breaking and requires a dedicated phase.

## I. Consumer and documentation policy

| Surface | Policy |
|---|---|
| Existing/new production consumer | use canonical paths |
| Alternate tests | may import retained paths |
| README/examples | must not recommend alternate paths |
| Architecture/policy docs | may describe retained compatibility |
| Migration guide | requires separate approved phase |
| Third-party consumer discovered | record evidence before escalation |

## J. Change-control matrix

| Proposed action | Allowed A5 | Evidence | Phase | Impact |
|---|---|---|---|---|
| Documentation clarification | Yes | review | A5 | low |
| Characterization tests | separate approval | behavior | test phase | low |
| Import/package break fix | No | failure evidence | production | high |
| Alternate semantic fix | No | defect evidence | production | high |
| New alternate feature | No | requirements | production | high |
| Documentation deprecation | No | policy/window | deprecation phase | medium |
| Runtime warnings | No | warning design | deprecation phase | medium |
| Adapter | No | mapping | adapter phase | high |
| Redirect imports | No | migration | production | high |
| Remove wheel/imports | No | external evidence | breaking phase | high |
| Package-root exports | No | API design | production | medium |

## K. Policy review triggers

| Trigger | Evidence | Immediate runtime action | Review |
|---|---|---|---|
| third-party import | repository/package evidence | none | evidence phase |
| public package publication/release | index/release record | none | policy review |
| new internal caller | source/import | none | consumer review |
| security or packaging failure | issue/repro | containment only | production phase |
| replacement mapping/migration guide complete | approved docs | none | deprecation review |
| artifact contract change or user feedback | tests/issues | none | contract review |
| major-version boundary | release policy | none | dedicated phase |

No trigger automatically authorizes removal.

## L. Future deprecation entry criteria

Require replacement API mapping, drop-in assessment, migration guide, external-use risk, distribution history, warning design/tests, release target/window, artifact and converter assessment, rollback plan, user communication, and dedicated production approval. **Retention continues if these criteria are incomplete.**

## M. Recommended next phase and non-goals

Recommend **Alternate Backtest Replacement API Mapping**. A5 does not add warnings, start a countdown, mark code deprecated, add adapters, redirect imports, change exports, remove wheel/import paths, fix alternate behavior, migrate consumers, change schemas/versions, publish, merge stacked PRs, or start Phase A6.
