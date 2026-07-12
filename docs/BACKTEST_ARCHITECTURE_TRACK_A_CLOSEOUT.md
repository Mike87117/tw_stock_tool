# Backtest Architecture Track A Closeout

## A. Closeout outcome

**TRACK_A_DECISION_CLOSED_CONTINUE_RETENTION_NO_ADAPTER**

**MERGE_DEFERRED_UNTIL_APPROVED_PRODUCTION_CHANGE**

Track A architecture investigation and decision work is complete. Canonical development remains `tw_stock_tool.backtesting`; alternate imports remain retained; no adapter is justified; no migration target or deprecation clock exists; and no warning or removal is authorized. A1-A8 remains HOLD because this closeout is documentation-only. **No Track A production implementation is pending or authorized.** Track A is neither merged nor released.

## B. Scope and closeout terminology

| Term | Meaning |
|---|---|
| Track A | Expanded A1-A8 backtest architecture decision work. |
| Decision closeout | Completion of documented decisions. |
| Integration closeout | Later merge-gate work; not performed here. |
| Canonical path | `tw_stock_tool.backtesting`. |
| Alternate path | `backtest.engine` and `strategies.base`. |
| Retention | Keeping imports and package availability without parity. |
| Compatibility surface | An import, package, wrapper, test, or artifact boundary. |
| HOLD | Intentionally unmerged pending an approved production change. |
| Stacked PR | A PR based on the preceding phase branch. |
| Production merge gate | Future full-stack readiness audit. |
| Reopening trigger | Evidence requiring Track A review. |
| Next architecture track | Separately named bounded cleanup work. |
| Carry-forward base | Latest A8 branch used as Track B base. |
| Superseded roadmap numbering | Original architecture review used coarse A1-A8; expanded work uses Track A/A1-A8. |

Decision closeout does not mean Git merge completion. HOLD does not mean failure. Retention does not mean semantic parity. No-adapter does not mean unsupported imports. Future work uses Track B naming to avoid a numbering collision.

## C. A1-A7 phase ledger

| Phase | Primary question | Changed artifact or tests | Formal outcome | Production code changed | Current PR status | Closeout implication |
|---|---|---|---|---|---|---|
| A1 - Public API and wrapper inventory | What surfaces exist? | inventory document | inventory completed | No | #2 Draft HOLD | establishes surfaces |
| A2 - Duplicate backtest characterization and decision | Are paths equivalent? | characterization tests and decision | INSUFFICIENT_EVIDENCE_RETAIN_TEMPORARILY | No | #3 Draft HOLD | divergence retained |
| A3 - Compatibility contract | What contracts must not break? | contract tests/document | compatibility retained | No | #4 Draft HOLD | artifacts stay canonical |
| A4 - Deprecation evidence | Is deprecation justified? | evidence document | INSUFFICIENT_EVIDENCE_CONTINUE_RETENTION | No | #5 Draft HOLD | no deprecation |
| A5 - Retention policy | How are paths retained? | policy document | RETAIN_WITHOUT_DEPRECATION | No | #6 Draft HOLD | imports remain retained |
| A6 - Replacement API mapping | Is replacement drop-in? | mapping document | PARTIAL_CONCEPTUAL_MAPPING_NO_DROP_IN_REPLACEMENT | No | #7 Draft HOLD | explicit design needed |
| A7 - Adapter design decision | Should an adapter be built? | decision document | NO_ADAPTER_IMPLEMENTATION_CONTINUE_RETENTION | No | #8 Draft HOLD | no adapter authorized |

A2 and A3 tests characterize and protect contracts; they are not adapter implementation tests.

## D. Final Track A architecture state

| Surface | Final status | Supported or retained behavior | Explicit non-guarantee | Authority required for change |
|---|---|---|---|---|
| Canonical backtest execution | canonical | DataFrame execution | alternate parity | production phase |
| Canonical BacktestResult | canonical | reports/artifacts result | alternate interchange | production phase |
| Alternate BacktestEngine | retained | direct import/behavior | canonical replacement | adapter phase |
| Alternate BacktestResult | retained distinct | direct result identity | canonical interchange | adapter phase |
| SignalStrategy | retained | alternate protocol | canonical interface | adapter phase |
| BaseStrategy | retained | alternate inheritance | canonical base class | adapter phase |
| Direct alternate imports | retained | import availability | permanent support | compatibility phase |
| Wheel/package inclusion | retained | distribution inclusion | active use proven | packaging phase |
| Package-root exports | canonical-oriented | root wrappers target canonical | alternate export | API phase |
| Canonical serialization | canonical-only | canonical result schema | alternate serialization | adapter phase |
| Paper-trading conversion | canonical-only | canonical trades/metadata | alternate conversion | adapter phase |
| New production development | canonical-only | backtesting use | new alternate callers | production approval |
| Runtime warnings | inactive | no warning | deprecation started | deprecation phase |
| Deprecation | inactive | no clock | future retention permanent | deprecation phase |
| Adapter | inactive | no new layer | never reconsidered | adapter decision |
| Removal | prohibited | retained paths | removal approved | breaking-change phase |

## E. Public API and compatibility state

| Surface | Evidence | Current guarantee | Unknowns | Prohibited interpretation | Future change authority |
|---|---|---|---|---|---|
| Root compatibility wrappers | A1 inventory | canonical wrapper targets retained | external scripts | alternate redirect | compatibility phase |
| Canonical package imports | source/tests | canonical APIs active | external usage | drop-in alternate mapping | API phase |
| Alternate direct imports | A4/A5 | retained | external users | permanent support | compatibility phase |
| Alternate package initializers | A1 | no symbol export | direct callers | imports absent | API phase |
| Wheel inclusion | A4 | alternate paths included | install count | active use proven | packaging phase |
| Historical tag exposure | A4 | exposure recorded | actual users | tags prove use | release phase |
| Dedicated alternate tests | tests | behavior protected | external contract | adapter complete | test phase |
| Characterization tests | A2 | differences recorded | adapter behavior | parity promised | adapter phase |
| Compatibility-contract tests | A3 | canonical boundaries protected | bridge contract | alternate accepted | adapter phase |
| README/examples | A1/A5 | no migration claim | reader use | migration guide exists | documentation phase |
| External consumers | searches | none confirmed | private/direct/fork use | no users exist | evidence phase |
| Private/direct installations | A4 | risk remains | population | absent distribution | evidence phase |
| Versioning policy | A4/A5 | no transition window | future policy | release plan exists | release phase |
| Migration guide | A7 | none active | future target | migration approved | migration phase |

## F. Consumer, artifact, and test evidence

| Evidence area | Current finding | Evidence strength | Contract protected | Gap remaining | Closeout effect |
|---|---|---|---|---|---|
| Internal production consumers | none identified | STRONG_INTERNAL_EVIDENCE | no forced migration | future callers | retention |
| CLI consumers | canonical path | DIRECT_EVIDENCE | CLI behavior | external scripts | canonical-only |
| GUI consumers | canonical path | DIRECT_EVIDENCE | GUI behavior | future links | canonical-only |
| Report consumers | canonical result | DIRECT_EVIDENCE | result fields | external reports | canonical-only |
| Parameter-sweep consumers | canonical path | DIRECT_EVIDENCE | execution | future callers | canonical-only |
| Walk-forward consumers | canonical path | DIRECT_EVIDENCE | execution | future callers | canonical-only |
| Paper-trading consumers | canonical converter | DIRECT_EVIDENCE | integer/schema contract | alternate bridge | canonical-only |
| Canonical serialization | rejects alternate result | DIRECT_EVIDENCE | schema | adapter design | boundary retained |
| Serialization file boundaries | canonical construction | DIRECT_EVIDENCE | file schema | alternate schema | boundary retained |
| Paper-trading converter | rejects alternate result | DIRECT_EVIDENCE | model contract | bridge tests | boundary retained |
| Alternate dedicated tests | existing engine/base tests | DIRECT_EVIDENCE | retained behavior | external support | retention |
| A2 characterization tests | semantic differences recorded | PARTIAL_EXISTING_EVIDENCE | divergence | adapter fixtures | no adapter |
| A3 compatibility tests | canonical contract protected | PARTIAL_EXISTING_EVIDENCE | type boundaries | adapter rounds | no adapter |
| Adapter-specific fixtures | incomplete | PARTIAL_EXISTING_EVIDENCE | none | golden cases | gate closed |
| Alternate-to-canonical round trips | incomplete | PARTIAL_EXISTING_EVIDENCE | none | round trips | gate closed |

## G. Decision consistency audit

| Decision label | Originating phase | Meaning | Still active | Superseded or preserved | Closeout consistency |
|---|---|---|---|---|---|
| INSUFFICIENT_EVIDENCE_RETAIN_TEMPORARILY | A2 | retain distinct paths | yes | preserved historical evidence | consistent |
| INSUFFICIENT_EVIDENCE_CONTINUE_RETENTION | A4 | no deprecation evidence | yes | preserved | consistent |
| RETAIN_WITHOUT_DEPRECATION | A5 | retain imports without clock | yes | active policy | consistent |
| PARTIAL_CONCEPTUAL_MAPPING_NO_DROP_IN_REPLACEMENT | A6 | no drop-in replacement | yes | active mapping | consistent |
| EXPLICIT_ADAPTER_DESIGN_REQUIRED_BEFORE_ANY_MIGRATION | A6 | design gate required | yes | active | consistent |
| NO_ADAPTER_IMPLEMENTATION_CONTINUE_RETENTION | A7 | no speculative adapter | yes | active | consistent |
| TRACK_A_DECISION_CLOSED_CONTINUE_RETENTION_NO_ADAPTER | A8 | close decision work | yes | preserves underlying evidence | consistent |

Earlier evidence labels remain authoritative for their phases; A8 closes Track A without replacing them.

## H. Remaining risks and reopening triggers

| Trigger | Evidence required | Immediate maintenance allowed | Track A reopening required | Possible future decision | Required phase/reviewer |
|---|---|---|---|---|---|
| Confirmed third-party consumer | reproducible workflow | record | yes | target review | evidence |
| New internal production caller | source import | record | yes | migration decision | architecture |
| Approved migration target | approved target | document | yes | adapter design | architecture |
| Public package publication | release evidence | record | yes | retention review | release |
| New release containing alternate modules | tag/release | record | yes | retention review | release |
| Repeated import/package failures | reproducible issue | repair integrity | yes | packaging fix | production |
| Security vulnerability | security evidence | security repair | yes | fix/policy | security |
| Material maintenance burden | measured cost | record | yes | ownership decision | architecture |
| Artifact integration requirement | consumer contract | record | yes | adapter design | architecture |
| Paper-trading integration requirement | workflow | record | yes | adapter design | architecture |
| Adapter-specific fixtures completed | passing tests | review | yes | gate review | test |
| Adapter round-trip tests completed | passing tests | review | yes | gate review | test |
| Versioning/compatibility policy adopted | approved policy | review | yes | migration plan | release |
| Planned major-version boundary | release plan | review | yes | deprecation decision | release |
| Reproducible user migration request | workflow | record | yes | target decision | evidence |
| Proposal to remove alternate modules | approved proposal | impact review | yes | breaking plan | architecture |

No trigger directly authorizes adapter implementation, migration, deprecation, or removal.

## I. Pending work and prohibited interpretations

Track A has no pending production implementation. Packaging/import integrity remains a maintenance responsibility; security repairs may be separately approved. Neither automatically reopens adapter or deprecation work.

| Item | Pending after A8 | Authorized | Why not | Reopening requirement |
|---|---|---|---|---|
| Adapter implementation | No | No | no design/value | Track A review |
| Strategy/input bridge | No | No | semantics unknown | adapter decision |
| Result conversion | No | No | fields absent | adapter decision |
| Serializer integration | No | No | canonical schema | adapter decision |
| Paper-trading integration | No | No | converter boundary | adapter decision |
| Consumer migration | No | No | no target | migration decision |
| Migration guide | No | No | no target/policy | migration decision |
| Runtime warning | No | No | no deprecation | deprecation phase |
| Deprecation window | No | No | evidence incomplete | deprecation phase |
| Alternate semantic fixes | No | No | behavior change | production approval |
| Alternate feature expansion | No | No | retention only | product approval |
| Import redirect | No | No | silent semantic change | adapter decision |
| Module removal | No | No | external risk | breaking phase |
| Wheel removal | No | No | distribution risk | packaging phase |
| Package-root export changes | No | No | API surface change | API phase |
| Version changes | No | No | no transition policy | release phase |

## J. Stacked PR and merge disposition

**MERGE_DEFERRED_UNTIL_APPROVED_PRODUCTION_CHANGE**

| Phase | Branch | PR number if currently known | Change type | Current gate | Merge status | Carry-forward role |
|---|---|---|---|---|---|---|
| A1 | phase-a1-public-api-wrapper-inventory | #2 | inventory docs | HOLD | Draft unmerged | evidence base |
| A2 | phase-a2-duplicate-backtest-decision | #3 | tests/docs | HOLD | Draft unmerged | characterization |
| A3 | phase-a3-backtest-compatibility-contract | #4 | tests/docs | HOLD | Draft unmerged | contract |
| A4 | phase-a4-backtest-deprecation-evidence | #5 | evidence docs | HOLD | Draft unmerged | retention evidence |
| A5 | phase-a5-backtest-retention-policy | #6 | policy docs | HOLD | Draft unmerged | policy |
| A6 | phase-a6-alternate-backtest-api-mapping | #7 | mapping docs | HOLD | Draft unmerged | mapping |
| A7 | phase-a7-alternate-backtest-adapter-decision | #8 | decision docs | HOLD | Draft unmerged | no-adapter decision |
| A8 | phase-a8-backtest-track-a-closeout | current closeout PR | closeout docs | HOLD | Draft unmerged | Track B base |

A8 becomes the base for Track B. Do not merge A1-A8 independently or mark their PRs ready. The first approved Track B production-code phase must run a full-stack merge-readiness audit of full diff, tests, PR bases, CI, and obsolete decisions. Merge method or PR retargeting is chosen only at that later gate; A8 does not authorize retargeting, closing, or merging PR #2-#8.

## K. Next-track candidate comparison

| Candidate track | Architecture priority | Production value | Compatibility risk | Existing test coverage | Scope isolation | Dependency on user-facing feature work | Recommended order | Decision |
|---|---|---|---|---|---|---|---|---|
| Data provider/cache boundary | P1 | high | medium | strong | high | low | 1 | SELECTED_NEXT |
| CLI argument-builder consolidation | P2 | medium | medium | medium | medium | medium | later | DEFERRED |
| Report/walk-forward separation | P2 | medium | medium | strong | medium | medium | later | DEFERRED |
| GUI feature-controller extraction | P1 | medium | high | medium | low | high | later | DEFERRED |
| Scanner ownership investigation | P2 | medium | medium | medium | medium | medium | later | DEFERRED |
| Release-engineering/documentation hygiene | P3 | low | low | medium | high | low | opportunistic | OPPORTUNISTIC_ONLY |

**NEXT_TRACK_DATA_PROVIDER_CACHE_BOUNDARY** is selected. It is an existing P1 issue: `data_loader.py` concentrates provider, fallback, normalization, cache, diagnostics, and orchestration; it has a stable public facade; it is independently testable; it follows the original cleanup order; and it can eventually carry the HOLD stack through a production merge gate. No extraction is begun here.

## L. Track B entry contract

| Contract | Current evidence source | Must remain stable | Characterization required | Allowed Track B change | Prohibited Track B change |
|---|---|---|---|---|---|
| Preserve `download_tw_stock` public call contract | data_loader/tests | yes | yes | inventory | signature change |
| Preserve symbol normalization | source/tests | yes | yes | inventory | normalization change |
| Preserve market suffix fallback behavior | source/tests | yes | yes | characterize | fallback reordering |
| Preserve provider fallback order | source/tests | yes | yes | characterize | provider policy change |
| Preserve returned DataFrame schema | source/tests | yes | yes | characterize | schema change |
| Preserve index ordering and validation | source/tests | yes | yes | characterize | validation change |
| Preserve cache-hit behavior | tests | yes | yes | characterize | cache semantics change |
| Preserve force-refresh behavior | tests | yes | yes | characterize | refresh change |
| Preserve cache path and naming behavior | source/tests | yes | yes | inventory | path change |
| Preserve stale/invalid cache handling | tests | yes | yes | characterize | stale policy change |
| Preserve provider error translation | source/tests | yes | yes | characterize | error contract change |
| Preserve diagnostics and console-capture behavior | tests | yes | yes | characterize | output change |
| Preserve offline/test determinism | tests | yes | yes | characterize | network dependency change |
| Preserve root/package wrapper compatibility | A1/source | yes | yes | inventory | wrapper break |
| No new provider feature | scope | yes | no | none | feature addition |
| No network-policy change | scope | yes | no | none | network change |
| No GUI or CLI redesign | scope | yes | no | none | UI/CLI redesign |
| Characterization tests before extraction | Track B contract | yes | yes | add tests | extraction first |
| Extract one seam per production phase | Track B contract | yes | no | narrow seam | broad rewrite |
| Rollback plan required | Track B contract | yes | no | plan | unplanned change |
| Full-suite and provider-focused CI required | Track B contract | yes | no | validation | skipped tests |
| Full stacked merge-readiness audit before integration | A8 disposition | yes | no | audit | independent merge |

Actual code behavior is authoritative; this document does not invent unverified fallback details. Track B is incremental: inventory and contract, characterize missing behavior, then extract one narrow provider/cache seam while preserving `data_loader.py` as orchestration facade.

## M. Recommended next phase and non-goals

Recommend exactly **Track B1 ??Data Provider/Cache Boundary Contract Inventory**. It should start from final A8 HEAD; inventory `data_loader.py`, cache manager, provider helpers, wrappers, and callers; record exact public/internal contracts; identify provider/cache/orchestration seams and missing coverage; and produce a bounded first production extraction proposal. It must avoid production modification until that proposal is reviewed.

A8 does not modify backtest code, implement an adapter, start migration, add warnings, start deprecation, remove alternate modules, merge or retarget stacked PRs, modify data-loader code, extract providers, change cache policy/fallback/network/CLI/GUI behavior, change versions, start Track B1, or start Phase A9.
