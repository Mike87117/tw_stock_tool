# Alternate Backtest Adapter Decision

## A. Decision outcome

**NO_ADAPTER_IMPLEMENTATION_CONTINUE_RETENTION**. No internal production caller requiring migration was identified, and no confirmed external migration target exists. Alternate imports are already retained by policy; a direct redirect is unsafe; a result-only adapter cannot be lossless; and full recomputation would apply canonical semantics rather than preserve alternate behavior. A lossless result-only adapter is not possible. Artifact and converter boundaries require canonical result construction and explicit mapping. Adapter-specific fixtures and round-trip tests are incomplete. The expected benefit does not currently justify a new compatibility layer and maintenance surface.

**No adapter implementation phase is currently authorized.** This is reversible when explicit consumer and design evidence appears; it does not permanently rule out a future adapter design.

## B. Decision scope and terminology

| Term | Meaning |
|---|---|
| Adapter | Code translating alternate inputs, execution, or results to canonical contracts. |
| Compatibility layer | A retained runtime surface intended to shield callers from an implementation difference. |
| Migration target | A confirmed caller or user workflow that must move between paths. |
| Known consumer | A repository caller identified by source, test, or packaging evidence. |
| External consumer | A user outside this repository; its absence from searches is not proof of no use. |
| Semantic preservation | Keeping execution timing, quantities, costs, lifecycle, and result meaning. |
| Lossless conversion | Producing the required target data without fabricated or discarded information. |
| Full recomputation | Re-running inputs through canonical execution rather than preserving alternate output. |
| Retention | Keeping alternate import and package availability without adding an adapter. |
| Canonical path | `tw_stock_tool.backtesting`. |
| Alternate path | `tw_stock_tool.backtest.engine` and `tw_stock_tool.strategies.base`. |
| Maintenance surface | Public behavior, tests, documentation, and ownership created by a change. |
| Decision trigger | New evidence that permits reconsideration. |
| Production implementation phase | Explicitly approved phase allowed to change runtime behavior. |
| Reversible decision | A decision that may be reopened when supporting evidence changes. |

Retention is not an adapter. A migration guide is not an adapter. A theoretical design is not implementation authorization. Absence of identified consumers is not proof that no external consumers exist. The A7 decision is reversible when new evidence appears.

## C. Evidence baseline

| Evidence area | A1-A6 finding | Evidence strength | Adapter-decision implication | Remaining uncertainty |
|---|---|---|---|---|
| Public API and wrapper inventory | Root wrappers target canonical modules; alternate paths have no root export. | DIRECT_EVIDENCE | No redirect target is established. | Direct external imports may exist. |
| Internal production callers | No application, CLI, GUI, report, or artifact caller was identified. | STRONG_INTERNAL_EVIDENCE | No repository migration need. | Future callers may appear. |
| Alternate dedicated tests | Engine and BaseStrategy tests retain alternate behavior. | DIRECT_EVIDENCE | Retention has behavior protection. | Tests do not establish external support. |
| Behavioral characterization | A2 records divergent fills, quantities, EOD behavior, and NaN behavior. | STRONG_INTERNAL_EVIDENCE | Silent bridging is unsafe. | No adapter-specific fixture set. |
| Compatibility contract | Canonical and alternate result identities remain distinct. | DIRECT_EVIDENCE | Interchange requires explicit design. | No approved bridge policy. |
| Wheel inclusion | Alternate packages are included in built distribution. | DIRECT_EVIDENCE | Removing or redirecting imports is risky. | Install population unknown. |
| Tagged distribution exposure | All three known tags include alternate modules. | DIRECT_EVIDENCE | Historical exposure supports retention. | Tags do not prove active users. |
| Public package-index search | No matching public distribution was found. | WEAK_NEGATIVE_EVIDENCE | Does not justify an adapter or removal. | Private/direct/fork use unknown. |
| External source-code search | No confirmed external consumer was found. | UNKNOWN_EXTERNAL_EVIDENCE | No migration target exists. | Search coverage is incomplete. |
| Retention policy | Retain alternate imports without deprecation. | POLICY_DECISION | Retention is adequate current compatibility. | Policy may be revised later. |
| Replacement API mapping | Only partial conceptual mapping; no drop-in replacement. | STRONG_INTERNAL_EVIDENCE | Adapter needs a selected design. | Consumer priorities unknown. |
| Result-only conversion | Required fields, metadata, inputs, and equity data are absent. | DIRECT_EVIDENCE | Result-only adapter is not eligible. | None without original sources. |
| Full recomputation | Canonical execution changes alternate semantics. | STRONG_INTERNAL_EVIDENCE | Not a compatibility adapter. | A future migration may choose canonical semantics. |
| Serializer boundaries | Serializer accepts canonical BacktestResult only. | DIRECT_EVIDENCE | Requires canonical construction/schema conversion. | No adapter artifact design. |
| Paper-trading converter | Converter accepts canonical result and integer shares only. | DIRECT_EVIDENCE | Alternate conversion requires explicit policy. | No converter bridge tests. |
| Adapter-specific fixtures | A2 tests are not adapter-specific golden fixtures. | PARTIAL_EXISTING_EVIDENCE | Implementation gate remains blocked. | Required fixture scope absent. |
| Adapter artifact round trips | A3 tests protect canonical contracts, not alternate adapters. | PARTIAL_EXISTING_EVIDENCE | Implementation gate remains blocked. | No round-trip design. |
| Versioning and migration policy | No release target, migration target, or compatibility window exists. | POLICY_DECISION | No migration/adaptor rollout is eligible. | Future release policy needed. |

## D. Candidate options

| Option | Intended benefit | Required inputs | Semantic preservation | Artifact compatibility | New public surface | Implementation complexity | Maintenance burden | Reversibility | Current eligibility |
|---|---|---|---|---|---|---|---|---|---|
| Continue retention with no adapter | Preserve imports safely | existing packages | retained alternate behavior | unchanged | none | low | low | high | selected |
| Strategy-object and input-DataFrame bridge | Accept alternate strategy calls | strategy, params, data | uncertain | partial | yes | high | high | medium | deferred |
| Full explicit execution adapter | Translate lifecycle and results | all inputs and policy | uncertain | partial | yes | high | high | medium | deferred |
| Result-only adapter | Convert completed results | unavailable fields/inputs | no | no | yes | medium | high | low | not eligible |
| Full canonical recomputation adapter | Recreate canonical output | all original inputs | no | partial | yes | high | high | medium | not eligible |
| Migration guide without adapter | Explain a future move | selected target/policy | not applicable | no | documentation | medium | medium | high | deferred |
| Direct module alias | Keep import spelling | none | no | no | hidden | low | high | low | not eligible |
| Direct class alias | Keep class spelling | none | no | no | hidden | low | high | low | not eligible |
| Direct engine redirect | Route calls to canonical function | call translation | no | no | hidden | medium | high | low | not eligible |
| Serializer-only adapter | Export alternate results | complete canonical fields | no | no | yes | medium | high | low | not eligible |
| Paper-trading-converter-specific adapter | Feed paper trading | canonical trade and metadata | no | no | yes | high | high | low | not eligible |
| Additional evidence collection before reconsideration | Establish a future decision basis | consumer and fixture evidence | not applicable | not applicable | none | low | low | high | deferred |

## E. Decision criteria

| Criterion | Favorable result | Current evidence | Status | Blocking |
|---|---|---|---|---|
| Confirmed consumer value | Confirmed user benefits | No confirmed target | NOT_SATISFIED | yes |
| Migration necessity | Caller must move paths | No internal caller | NOT_SATISFIED | yes |
| Semantic fidelity | Alternate behavior can be preserved | Material differences documented | NOT_SATISFIED | yes |
| Data completeness | Inputs are available | Result omits original inputs | NOT_SATISFIED | yes |
| Result-model completeness | All canonical fields can be supplied | Canonical-only fields absent | NOT_SATISFIED | yes |
| Artifact compatibility | Canonical artifacts can accept output | Strict canonical boundaries reject alternate | NOT_SATISFIED | yes |
| Serializer compatibility | Schema can be safely preserved | Canonical construction required | NOT_SATISFIED | yes |
| Paper-trading compatibility | Converter contract can be met | Integer/share metadata gaps | NOT_SATISFIED | yes |
| Testability | Adapter fixtures and round trips exist | Existing tests are partial | PARTIALLY_SATISFIED | yes |
| Rollback feasibility | New surface can be safely removed | No design selected | NOT_SATISFIED | yes |
| Implementation complexity | Work is proportionate | Bridge is high complexity | NOT_SATISFIED | yes |
| Long-term maintenance cost | Owner accepts support burden | No owner or value case | NOT_SATISFIED | yes |
| Public-API expansion risk | Surface is governed | New adapter surface undefined | NOT_SATISFIED | yes |
| Documentation burden | Migration/docs are ready | No migration target | NOT_SATISFIED | yes |
| Versioning readiness | Release compatibility policy exists | No rollout boundary | NOT_SATISFIED | yes |
| External uncertainty | Consumer evidence is sufficient | External use remains unknown | NOT_SATISFIED | yes |
| Alignment with retention policy | Change respects retention | Retention supports no adapter | SATISFIED | no |
| Alignment with canonical-development policy | New work uses canonical APIs | Policy directs canonical development | SATISFIED | no |

## F. Comparative decision matrix

| Option | Consumer value | Semantic fidelity | Lossless result support | Artifact compatibility | Complexity | Maintenance burden | Rollback safety | Evidence completeness | Policy alignment | Decision |
|---|---|---|---|---|---|---|---|---|---|---|
| Continue retention with no adapter | established | retained | not needed | unchanged | low | low | high | sufficient | high | SELECTED |
| Strategy/input bridge | unproven | uncertain | partial | partial | high | high | medium | incomplete | conditional | DEFERRED |
| Full explicit execution adapter | unproven | uncertain | partial | partial | high | high | medium | incomplete | conditional | DEFERRED |
| Result-only adapter | unproven | no | no | no | medium | high | low | direct contrary evidence | low | NOT_ELIGIBLE |
| Full canonical recomputation adapter | unproven | no | no | partial | high | high | medium | direct contrary evidence | low | REJECTED |
| Migration guide without adapter | unproven | not applicable | not applicable | no | medium | medium | high | incomplete | conditional | DEFERRED |
| Direct module alias | unproven | no | no | no | low | high | low | direct contrary evidence | low | REJECTED |
| Direct class alias | unproven | no | no | no | low | high | low | direct contrary evidence | low | REJECTED |
| Direct engine redirect | unproven | no | no | no | medium | high | low | direct contrary evidence | low | REJECTED |
| Serializer-only adapter | unproven | no | no | no | medium | high | low | incomplete | low | NOT_ELIGIBLE |
| Converter-specific adapter | unproven | no | no | no | high | high | low | incomplete | low | NOT_ELIGIBLE |
| Additional evidence collection | future value | not applicable | not applicable | not applicable | low | low | high | incomplete | high | DEFERRED |

This matrix is an architecture decision, not an implementation backlog.

## G. Selected decision and rationale

**NO_ADAPTER_IMPLEMENTATION_CONTINUE_RETENTION** is selected.

| Rationale | Supporting evidence | Risk avoided | Tradeoff accepted | Review trigger |
|---|---|---|---|---|
| No established migration target | no internal caller; no confirmed external target | speculative surface | no migration convenience | confirmed consumer |
| No internal production dependency | repository inventory | runtime disruption | alternate remains distinct | new production caller |
| Uncertain external usage | wheel/tags; negative search is weak | unsafe assumptions | retention cost | external report |
| Existing retention preserves imports | A5 policy | breaking imports | no convergence | packaging failure |
| No lossless result-only conversion | A6 field matrix | fabricated fields | no result bridge | complete source capture |
| Full recomputation changes semantics | A2/A6 execution evidence | false compatibility | canonical-only recomputation deferred | approved semantic policy |
| Canonical artifacts reject alternate results | serializer/converter checks | corrupt artifacts | no artifact bridge | approved artifact design |
| Adapter adds a public compatibility surface | option review | indefinite support debt | no new API | owner and policy |
| Tests and artifact round trips incomplete | A2/A3 partial evidence | untested compatibility | retained tests only | completed fixtures |
| Maintenance cost is speculative | no demonstrated value | unsupported burden | no feature layer | material demand |

New production work continues to use canonical APIs. Alternate modules continue to be retained. Existing alternate tests continue to protect retained behavior. No semantic convergence is promised. No adapter code is planned under A7.

## H. Rejected and deferred options

| Option | Status | Primary rejection/defer reason | What would need to change | Can it be reconsidered | Required future phase |
|---|---|---|---|---|---|
| Strategy-object and input-DataFrame bridge | DEFERRED | consumer and semantic policy absent | target, contract, fixtures | yes | adapter design |
| Full explicit execution adapter | DEFERRED | design gates incomplete | selected semantics and owner | yes | adapter design |
| Result-only adapter | NOT_ELIGIBLE | required fields and inputs absent | complete source data/policy | yes | adapter design |
| Full canonical recomputation adapter | REJECTED | substitutes canonical semantics | approved migration, not compatibility | yes | migration design |
| Migration guide without adapter | DEFERRED | no selected target or semantic policy | target and policy | yes | migration design |
| Direct module alias | REJECTED | silently changes behavior | none; structural mismatch persists | no | none |
| Direct class alias | REJECTED | silently changes identity and fields | none; structural mismatch persists | no | none |
| Direct engine redirect | REJECTED | silently changes execution behavior | none; semantic mismatch persists | no | none |
| Serializer-only adapter | NOT_ELIGIBLE | cannot solve execution and field gaps | complete design and fields | yes | adapter design |
| Paper-trading-converter-specific adapter | NOT_ELIGIBLE | cannot solve execution and field gaps | complete design and trade policy | yes | adapter design |
| Additional evidence collection | DEFERRED | evidence activity, not primary action | confirmed evidence | yes | evidence review |

## I. Retention and compatibility implications

| Surface | Status after A7 | Guarantee | Prohibited interpretation | Required authority for change |
|---|---|---|---|---|
| Existing alternate imports | retained | direct imports remain available | semantic parity | compatibility phase |
| Alternate wheel inclusion | retained | package inclusion continues | permanent distribution | packaging phase |
| Alternate tagged exposure | historical retained evidence | past tags remain evidence | active external use proven | release review |
| Dedicated alternate tests | retained | behavior remains tested | adapter tests complete | test phase |
| Characterization tests | retained | observed differences remain protected | convergence promised | adapter phase |
| Compatibility-contract tests | retained | canonical boundaries remain protected | alternate accepted | adapter phase |
| New production consumers | canonical only | new work uses backtesting | alternate is recommended | production approval |
| README/examples | unchanged | no migration claim added | migration guide exists | documentation phase |
| Serializer integration | unsupported | canonical result required | alternate artifact support | adapter phase |
| Paper-trading integration | unsupported | canonical result required | alternate converter support | adapter phase |
| New alternate-engine features | no commitment | retention only | feature expansion | production approval |
| Runtime warnings | none | no warning added | deprecation started | deprecation phase |
| Deprecation | none | no clock starts | retirement approved | deprecation phase |
| Removal | prohibited | paths remain retained | unmaintained or removable | breaking-change phase |

## J. Maintenance and ownership implications

| Maintenance concern | Current responsibility | Allowed maintenance | Not automatically authorized | Escalation trigger | Required phase type |
|---|---|---|---|---|---|
| Alternate module ownership | repository maintainers | import/package integrity | parity work | owner gap | policy review |
| Dedicated behavior tests | maintainers | preserve current behavior | adapter fixtures | behavior regression | test fix |
| Characterization tests | maintainers | preserve observations | migration semantics | changed evidence | evidence review |
| Canonical compatibility tests | maintainers | protect canonical contracts | alternate acceptance | adapter request | adapter design |
| Documentation consistency | maintainers | correct evidence | migration claims | contradiction | documentation |
| Consumer discovery | maintainers | record reports | infer external absence | confirmed user | evidence review |
| Packaging verification | maintainers | repair package breaks | remove paths | wheel failure | packaging fix |
| Security fixes | maintainers | approved security repair | feature work | vulnerability | production fix |
| Import/package break repairs | maintainers | restore retained imports | redirects | break report | production fix |
| Semantic bug fixes | maintainers | none without approval | behavior change | reproducible issue | production approval |
| Feature requests | maintainers | record request | new alternate feature | demonstrated demand | product decision |
| Artifact integration requests | maintainers | record requirement | serializer bridge | consumer need | adapter design |
| External-user reports | maintainers | record evidence | policy escalation without evidence | reproducible report | evidence review |

Retention requires import/package integrity, not semantic parity or new features. Security and packaging failures may justify a separate production fix. Runtime semantic fixes require explicit approval. External-user reports must be recorded before policy escalation. No-adapter does not mean unmaintained or removable.

## K. Reconsideration triggers

| Trigger | Evidence required | Immediate action allowed | Decision to reopen | Possible next outcome | Required reviewer/phase |
|---|---|---|---|---|---|
| Confirmed third-party consumer | reproducible import/workflow | record evidence | yes | policy review | evidence |
| New internal production caller | source/import evidence | record caller | yes | migration decision | architecture |
| Approved migration target | approved target | document target | yes | adapter design | architecture |
| Public package publication | package/release evidence | record exposure | yes | retention review | release |
| New release containing alternate modules | tag/release evidence | update evidence | yes | retention review | release |
| Repeated import/package failures | reproducible failures | repair integrity | yes | packaging fix | production |
| Security vulnerability | security evidence | security response | yes | fix or policy | security |
| Material maintenance burden | measured support cost | record burden | yes | ownership decision | architecture |
| Artifact integration requirement | consumer contract | record requirement | yes | adapter design | architecture |
| Paper-trading integration requirement | consumer workflow | record requirement | yes | adapter design | architecture |
| Completed adapter-specific golden fixtures | passing fixtures | review evidence | yes | design eligibility | test |
| Completed adapter artifact round-trip tests | passing round trips | review evidence | yes | design eligibility | test |
| Adopted versioning/compatibility policy | approved policy | apply policy review | yes | migration plan | release |
| Planned major-version boundary | approved release plan | plan review | yes | deprecation/migration decision | release |
| User request with reproducible migration need | reproducible request | record workflow | yes | target decision | evidence |
| Decision to remove alternate modules | approved proposal | impact review | yes | breaking-change plan | architecture |

No trigger directly authorizes adapter implementation, deprecation, or removal.

## L. Future adapter implementation gate

| Gate | Current A7 status | Evidence required | Blocking | Owner/phase | Completion authority |
|---|---|---|---|---|---|
| Confirmed migration target | incomplete | approved target | yes | design | architecture approval |
| Alternate-versus-canonical semantic priority | incomplete | policy | yes | design | architecture approval |
| Parameter mapping specification | incomplete | formulas | yes | design | architecture approval |
| Strategy bridge specification | incomplete | interface design | yes | design | architecture approval |
| Signal normalization specification | incomplete | fixtures | yes | test | architecture approval |
| Cost formula mapping | incomplete | golden cases | yes | design | architecture approval |
| Slippage policy | incomplete | policy | yes | design | architecture approval |
| Fractional-share policy | incomplete | policy | yes | design | architecture approval |
| EOD lifecycle policy | incomplete | policy | yes | design | architecture approval |
| Invalid-open policy | incomplete | policy | yes | design | architecture approval |
| Complete result-field policy | incomplete | field matrix | yes | design | architecture approval |
| Unit-conversion policy | incomplete | numeric cases | yes | test | architecture approval |
| Trade-schema policy | incomplete | schema tests | yes | test | architecture approval |
| Equity-curve policy | incomplete | curve fixtures | yes | test | architecture approval |
| Metadata policy | incomplete | consumer evidence | yes | evidence | architecture approval |
| Serialization impact assessment | incomplete | artifact design/tests | yes | design | architecture approval |
| Paper-trading converter impact assessment | incomplete | converter design/tests | yes | design | architecture approval |
| Adapter-specific golden characterization fixtures | PARTIAL_EXISTING_EVIDENCE | Existing A2 tests are not adapter-specific fixtures. | yes | test | architecture approval |
| Alternate-to-canonical artifact round-trip tests | PARTIAL_EXISTING_EVIDENCE | Existing A3 tests protect canonical contracts but do not validate an adapter. | yes | test | architecture approval |
| External-consumer risk assessment | incomplete | external evidence | yes | evidence | architecture approval |
| Rollback plan | incomplete | approved plan | yes | design | architecture approval |
| Version plan | incomplete | release policy | yes | release | architecture approval |
| User communication plan | incomplete | reviewed docs | yes | documentation | architecture approval |
| Dedicated production-phase approval | absent | explicit approval | yes | production | architecture approval |
| Demonstrated consumer value | incomplete | confirmed value | yes | evidence | architecture approval |
| Approved migration target | incomplete | approved target | yes | design | architecture approval |
| Approved adapter option | incomplete | selected option | yes | design | architecture approval |
| Approved public-surface policy | incomplete | support policy | yes | policy | architecture approval |
| Maintenance owner | incomplete | named owner | yes | policy | architecture approval |
| Sunset or long-term ownership policy | incomplete | approved policy | yes | policy | architecture approval |

**No adapter implementation phase may begin unless every blocking gate for the selected design is complete and explicitly approved.** Because no adapter design is selected in A7, the implementation gate remains closed.

## M. Recommended next phase and non-goals

Recommend exactly **Backtest Architecture Track A Closeout Review**. It should summarize A1-A7 decisions, confirm the final Track A architecture state and HOLD PRs, check that no production implementation is pending, record reopening triggers, determine how the stacked documentation/test work carries into the next production-code track, and select the next architecture-cleanup track. It must not merge PRs automatically.

A7 does not implement an adapter; select an adapter design for implementation; add redirects, aliases, or wrappers; add serializer or converter support; change alternate or canonical behavior; add features; fix NaN handling; migrate consumers; create a migration guide; add warnings; start deprecation; remove modules; change wheel contents, imports, or versions; merge stacked PRs; or start Phase A8.
