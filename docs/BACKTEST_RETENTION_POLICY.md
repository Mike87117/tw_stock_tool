# Backtest Retention Policy

## A. Policy decision

**RETAIN_WITHOUT_DEPRECATION**. Distribution exposure exists, external usage is uncertain, and no deprecation window has started. Alternate paths remain available without warnings, but are not canonical or recommended for new development.

## B. Scope and terminology

Canonical path: `tw_stock_tool.backtesting`. Alternate path: `tw_stock_tool.backtest.engine` and `tw_stock_tool.strategies.base`. Retention means import availability, not equivalence or permanent support. Deprecation, warning, removal, migration, compatibility window, and dedicated production phase require separate approval. Removal is not authorized.

## C. Current status matrix

| Symbol | Import path | Current status | Included in wheel | Package-root export | Internal production caller | Canonical equivalent | Behavior guarantee | Artifact support |
|---|---|---|---|---|---|---|---|---|
| BacktestEngine | tw_stock_tool.backtest.engine | TEMPORARY_COMPATIBILITY_RETAINED | yes | no | none identified | backtesting path | import only | NOT_SUPPORTED |
| alternate BacktestResult | tw_stock_tool.backtest.engine | CHARACTERIZED_NOT_GUARANTEED | yes | no | none identified | distinct canonical result | not interchangeable | NOT_SUPPORTED |
| SignalStrategy | tw_stock_tool.backtest.engine | TEMPORARY_COMPATIBILITY_RETAINED | yes | no | none identified | no drop-in guarantee | import only | NOT_SUPPORTED |
| BaseStrategy | tw_stock_tool.strategies.base | TEMPORARY_COMPATIBILITY_RETAINED | yes | no | none identified | canonical strategies differ | import only | NOT_SUPPORTED |

## D. Canonical development policy

New production development must use `tw_stock_tool.backtesting`. New dependencies on alternate paths are prohibited by documented policy only. Exceptions: dedicated alternate tests, characterization/contract tests, architecture/policy documents, or separately approved migration/adapter phases.

## E. Retention commitment

Retained: module files, direct imports, symbol names, wheel inclusion, dedicated tests, and distinct result identities. **No deprecation clock is currently running.** No removal date is promised; retention is not permanent support.

## F. Supported and non-guaranteed boundaries

| Boundary | Current commitment | Guarantee level | Reason | Change authority |
|---|---|---|---|---|
| Direct import availability | retained | compatibility | external usage unknown | dedicated phase |
| Wheel inclusion | retained | distribution surface | wheel evidence | packaging phase |
| Symbol names | retained | import compatibility | tests/imports | dedicated phase |
| Dedicated test coverage | retained | maintained behavior | existing tests | separately approved test phase |
| Semantic equivalence | none | not guaranteed | A2 divergence | production phase |
| Result interchangeability | none | UNSUPPORTED_INTEGRATION | distinct classes | adapter phase |
| Canonical serialization/converter | canonical only | supported canonical | type boundary | production phase |
| Feature parity | none | not guaranteed | engine differences | production phase |
| New alternate features | prohibited | not supported | canonical development rule | dedicated phase |
| NaN-open behavior | observed | KNOWN_DEFECT_NOT_GUARANTEED | A2 evidence | fix phase |
| Artifact schema | canonical only | supported canonical | consumers | production phase |
| Package-root exports | none | not promised | initializers empty | API phase |

## G. Known behavioral divergence

| Area | Alternate behavior/interface | Canonical behavior/interface | Policy classification | Current commitment | Permitted future action |
|---|---|---|---|---|---|
| Result type identity | distinct class | canonical BacktestResult | CHARACTERIZED_DIFFERENCE | retain distinction | mapping phase |
| Signal interface | strategy object | DataFrame signals | CHARACTERIZED_DIFFERENCE | imports only | replacement mapping |
| Quantity behavior | fractional all-in | integer affordable shares | CHARACTERIZED_DIFFERENCE | no parity promise | semantic review |
| Trade-log/schema | compact alternate columns | canonical extended columns | CHARACTERIZED_DIFFERENCE | no convergence promise | contract review |
| EOD lifecycle | mark-to-market | forced SELL_EOD | CHARACTERIZED_DIFFERENCE | behavior retained | production phase |
| Invalid/NaN next-open | may propagate NaN | skips invalid execution | KNOWN_DEFECT_NOT_GUARANTEED | do not endorse | dedicated fix phase |
| Canonical serialization | rejects alternate result | accepts canonical | UNSUPPORTED_INTEGRATION | canonical only | adapter phase |
| Paper-trading converter | rejects alternate result | accepts canonical | UNSUPPORTED_INTEGRATION | canonical only | adapter phase |

## H. Distribution and import policy

Alternate modules are included in the locally built wheel and all three known tags. Public index lookup found no matching distribution, which does not eliminate Git, editable, private-index, archived, or fork usage. Alternate initializers export nothing; root wrappers target canonical modules. Wheel removal is breaking and requires a dedicated phase.

## I. Consumer and documentation policy

| Consumer/surface | Current allowed path | Alternate-path policy | Required evidence | Change authority |
|---|---|---|---|---|
| Existing canonical production consumer | canonical | remain canonical | consumer tests | production phase |
| New production consumer | canonical | must not use alternate | review/AST evidence | production phase |
| Dedicated alternate-path test | alternate allowed | retain approved scope | focused tests | separately approved test phase |
| A2 characterization test | alternate allowed | characterization only | semantic evidence | A2 scope |
| A3 compatibility test | alternate allowed | identity/import only | contract evidence | A3 scope |
| User-facing README/example | canonical | must not recommend alternate | doc review | documentation phase |
| Architecture/policy document | either described | alternate only as retained surface | evidence | documentation phase |
| Migration guide | canonical replacement | requires approved phase | migration evidence | migration phase |
| Third-party consumer discovered later | record actual path | no silent migration | external evidence | policy review |

## J. Change-control matrix

| Proposed action | Allowed under A5 policy | Required evidence | Required phase type | Compatibility impact | Rollback requirement |
|---|---|---|---|---|---|
| Documentation clarification | Yes | review | A5 | low | revert document |
| Adding characterization tests | No | behavior case | separately approved test phase | low | revert tests |
| Fixing import/package break | No | reproduction | production phase | high | restore import |
| Fixing alternate runtime semantics | No | defect evidence | production phase | high | restore behavior |
| Adding new alternate-engine features | No | requirements | production phase | high | revert feature |
| Adding documentation-only deprecation | No | policy/window | deprecation phase | medium | remove notice |
| Adding runtime warnings | No | warning design | deprecation phase | medium | disable warning |
| Adding an adapter | No | mapping/tests | adapter phase | high | remove adapter |
| Redirecting alternate imports to canonical | No | migration contract | production phase | high | restore target |
| Removing alternate files from wheel | No | distribution evidence | packaging phase | high | packaging rollback |
| Removing alternate import paths | No | external evidence | breaking phase | high | API compatibility rollback |
| Adding package-root alternate exports | No | API design | API phase | medium | remove exports |

## K. Policy review triggers

| Trigger | Evidence to collect | Immediate runtime action permitted | Required reviewer/phase | Possible policy outcomes |
|---|---|---|---|---|
| Confirmed third-party import | repository/package evidence | none | policy review | CONTINUE_RETENTION or EXPAND_EVIDENCE |
| Public package publication | index records | none | distribution review | EXPAND_EVIDENCE |
| New GitHub Release | release notes/assets | none | policy review | CONTINUE_RETENTION |
| New internal production caller | source/import evidence | none | consumer review | REPAIR_COMPATIBILITY |
| Security issue | issue/reproduction | containment only | security production phase | REPAIR_COMPATIBILITY |
| Packaging/import failure | reproducible failure | no removal | packaging phase | REPAIR_COMPATIBILITY |
| Maintenance burden | measured maintenance evidence | none | policy review | EXPAND_EVIDENCE |
| Canonical replacement mapping completed | approved mapping | none | mapping phase | AUTHORIZE_MAPPING_PHASE |
| Migration guide completed | reviewed guide | none | migration review | AUTHORIZE_MAPPING_PHASE |
| Compatibility/versioning policy adopted | policy record | none | governance review | AUTHORIZE_DEPRECATION_PLANNING |
| Artifact contract changed | artifact tests | none | contract phase | REPAIR_COMPATIBILITY |
| External-user feedback | verifiable report | none | policy review | CONTINUE_RETENTION |
| Planned major-version boundary | release plan | none | release phase | AUTHORIZE_DEPRECATION_PLANNING or REJECT_REMOVAL |

No trigger automatically authorizes removal.

## L. Future deprecation entry criteria

Require replacement API mapping, drop-in assessment, migration guide, external-use risk, distribution history, warning design/tests, release target/window, artifact/converter assessment, rollback, user communication, and dedicated production approval. **Retention continues if these criteria are incomplete.**

## M. Recommended next phase and non-goals

Recommend **Alternate Backtest Replacement API Mapping**. A5 does not add warnings, start a countdown, mark code deprecated, add adapters, redirect imports, change exports, remove wheel/import paths, fix behavior, migrate consumers, change schemas/versions, publish, merge stacked PRs, or start Phase A6.
