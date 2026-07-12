# Backtest Deprecation Evidence

## A. Executive evidence outcome
**INSUFFICIENT_EVIDENCE_CONTINUE_RETENTION**. Wheel exposure exists; external use, private/direct installation, release policy, and a deprecation window remain unknown.

## B. Scope and investigated symbols
Investigated `BacktestEngine`, alternate `BacktestResult`, `SignalStrategy`, and `BaseStrategy`. No internal caller is not proof of no external caller. Distribution, documented exposure, and external-use evidence are distinct.

## C. Current package exposure
`pyproject.toml` defines `tw-stock-tool` version `0.3.0` with `src` discovery `tw_stock_tool*`. The temporary wheel contained alternate `backtest` and `strategies` files plus canonical `backtesting` files. Alternate package initializers export no alternate symbols; root wrappers target canonical modules; direct imports work; canonical serializer/converter reject alternate results.

## D. Historical timeline

| Commit SHA | Date | Event | Files/symbols | Evidence | Exposure implication |
|---|---|---|---|---|---|
| d09d30d9005a236311354c8a45686c5029ed75a9 | 2026-06-23 | Base strategy contract | strategies/base.py | git log | alternate path introduced |
| 06e7167c75c02a69108e06d9f447fe8c9006dcfc | 2026-06-23 | Add backtest engine | backtest/engine.py | git log | alternate path introduced |
| A1 | current stack | inventory | wrapper/export evidence | branch history | isolated |
| A2 | current stack | semantic comparison | characterization tests | branch history | retained |
| A3 | current stack | compatibility contract | identity tests | branch history | boundaries protected |
| A4 | 2026-07-12 | wheel evidence | alternate modules | temporary build | distributed surface |

No identified production migration onto the alternate engine.

## E. Current internal-reference inventory
| Category | Count | Implication |
|---|---:|---|
| Alternate production implementation | 2 | retain evidence |
| Identified internal production caller | 0 | weak negative evidence only |
| Dedicated alternate tests | 2 | maintained behavior |
| A2/A3 evidence tests | 2 | characterization/contract evidence |
| Documentation references | 4 | not external usage |

## F. Tag, release, and distribution evidence
Three tags exist: v0.1.0, v0.2.0, v0.3.0. The temporary wheel contains alternate modules. Current version is 0.3.0. Public index lookup returned `No matching distribution found for tw-stock-tool`. GitHub Release query, private indexes, direct Git installs, archives, and forks remain unknown.

## G. Public external-use evidence
| Search source | Query | Result count | Relevant results | Interpretation | Limitations |
|---|---|---:|---|---|---|
| Repository issues | alternate symbols | 0 | No public issue evidence was found by the checked queries. | no evidence | not proof |
| Repository PRs | alternate symbols | 0 | No public PR evidence was found by the checked queries. | no evidence | not proof |
| Commit messages | engine/base | history | introduction commits | implementation history | not users |
| Global GitHub code | alternate imports | unavailable | Public GitHub code-search evidence unavailable. | unknown | tool scope |
| Public forks | alternate imports | unavailable | unavailable | unknown | API unavailable |
| GitHub Releases | releases | unavailable | unavailable | unknown | query unavailable |
| Public package index | tw-stock-tool | 0 | no matching distribution | weak negative | private/direct unknown |
| LLM Wiki | health/search | unavailable | service unavailable | unknown | supporting only |

## H. Documentation and policy evidence
No README alternate import examples, CLI-help exposure, changelog/release-note process, versioning policy, deprecation policy, compatibility guarantee, or migration guide was found. Canonical paths are documented by A1-A3 evidence.

## I. Evidence-quality assessment
Wheel/history/source findings are DIRECT; package-index absence is NEGATIVE_SEARCH_RESULT; unavailable searches are UNAVAILABLE; private/direct usage is UNKNOWN. Negative searches cannot prove no users.

## J. Risk matrix
| Action | User risk | Artifact risk | Semantic risk | External-usage uncertainty | Reversibility | Evidence required |
|---|---|---|---|---|---|---|
| Keep alternate imports indefinitely | Low | Low | Low | Unknown | High | current evidence |
| Add retention-policy documentation | Low | Low | Low | Unknown | High | policy review |
| Add documentation-only deprecation | Medium | Low | Low | Unknown | Medium | replacement/window |
| Add runtime warnings | Medium | Low | Medium | Unknown | Medium | warning design |
| Remove alternate files from wheel | High | High | High | Unknown | Low | distribution/users |
| Remove alternate import paths | High | Medium | High | Unknown | Low | external evidence |
| Redirect alternate paths | High | Medium | High | Unknown | Medium | migration contract |
| Build an explicit adapter | Medium | High | High | Unknown | Medium | semantic adapter spec |

## K. Formal outcome and rationale
**INSUFFICIENT_EVIDENCE_CONTINUE_RETENTION**. Wheel exposure is direct evidence; no public index result and no identified production caller are weak negative evidence; public code, releases, forks, and private use remain unavailable or unknown. Warning planning is premature and removal prohibited. Public-index absence does not eliminate direct/private distribution risk.

## L. Entry criteria for a future deprecation phase
Require distribution history, compatibility policy, replacement documentation, migration guide, warning design/tests, release target/window, rollback, external-risk statement, and preserved artifact/consumer contracts.

## M. Recommended next phase and non-goals
Recommend **Backtest Retention Policy Documentation**. A4 adds no warnings, deprecation markers, exports, wheel removal, adapters, NaN fixes, engine changes, migrations, version changes, publication, or A5 work.
