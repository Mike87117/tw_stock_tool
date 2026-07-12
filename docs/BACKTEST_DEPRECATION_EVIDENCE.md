# Backtest Deprecation Evidence

## A. Executive evidence outcome

**INSUFFICIENT_EVIDENCE_CONTINUE_RETENTION**. Alternate modules are distributed in the wheel, but external usage, private/direct installation, release policy, and a deprecation window remain unknown.

## B. Scope and investigated symbols

Investigated symbols are `BacktestEngine`, alternate `BacktestResult`, `SignalStrategy`, and `BaseStrategy`. Internal use, distribution exposure, documented public exposure, and external-use evidence are separate. No internal caller is not proof of no external caller.

## C. Current package exposure

`pyproject.toml` defines distribution `tw-stock-tool`, version `0.3.0`, with `src` discovery `tw_stock_tool*`. The locally built wheel contained `tw_stock_tool/backtest/__init__.py`, `backtest/engine.py`, `strategies/__init__.py`, `strategies/base.py`, and canonical backtesting files. Alternate package initializers do not export alternate symbols; root wrappers target canonical modules. Direct alternate imports work; canonical serializer/converter reject alternate results.

## D. Historical timeline

| Commit SHA | Date | Event | Files/symbols | Test/import evidence | Exposure implication |
|---|---|---|---|---|---|
| `d09d30d9005a236311354c8a45686c5029ed75a9` | 2026-06-23T20:56:33+08:00 | `feat: add base strategy contract` | `src/tw_stock_tool/__init__.py`, `strategies/__init__.py`, `strategies/base.py`, `tests/test_strategy_base.py` | initial test import `from src.tw_stock_tool.strategies.base import BaseStrategy` | alternate strategy path introduced |
| `06e7167c75c02a69108e06d9f447fe8c9006dcfc` | 2026-06-23T21:00:49+08:00 | `feat: add backtest engine` | `backtest/__init__.py`, `backtest/engine.py`, dedicated engine test | initial tests used `src.tw_stock_tool.backtest.engine` imports | alternate engine path introduced |
| `f323dcc59d87142b4d11b7b6df52adfb210625ed` | A1 branch head | public API inventory | wrapper/export evidence | inventory document | isolated path classified unknown |
| `1047367f2fdc63411715d8829c3717262929db88` | A2 branch head | semantic decision | characterization tests | A2 tests | retained temporarily |
| `4a3d752a2025fb5e3799348667b25dbf6166755b` | A3 branch head | compatibility contract | identity/consumer tests | A3 tests | import boundaries protected |
| `ba474504d7928172a4e7f36984fa22010377d8bb` | A4 start | initial evidence | evidence document | baseline 1,363 tests | no runtime change |
| `28cde2e714f386b859765c767716bb6b0230a892` | A4 evidence commit | wheel/index evidence | evidence document | wheel inspection | distributed exposure recorded |

`git log --follow` shows no later production modification after the introduction commits for either alternate module; no identified production consumer was migrated onto the alternate engine.

## E. Current internal-reference inventory

| File | Referenced symbol/import | Category | Runtime relevance | Deprecation implication |
|---|---|---|---|---|
| `src/tw_stock_tool/backtest/engine.py` | `BacktestEngine`, alternate `BacktestResult`, `SignalStrategy` | ALTERNATE_PRODUCTION_IMPLEMENTATION | isolated implementation | retain; not canonical |
| `src/tw_stock_tool/strategies/base.py` | `BaseStrategy` | ALTERNATE_PRODUCTION_IMPLEMENTATION | isolated strategy contract | retain; not canonical |
| `tests/test_backtest_engine.py` | alternate engine imports | DEDICATED_ALTERNATE_TEST | behavior maintenance | not proof of public API |
| `tests/test_strategy_base.py` | alternate strategy imports | DEDICATED_ALTERNATE_TEST | behavior maintenance | not proof of public API |
| `tests/test_backtest_path_characterization.py` | alternate path semantics | A2_CHARACTERIZATION_TEST | comparison evidence | not a deprecation signal |
| `tests/test_backtest_compatibility_contract.py` | identity/import boundaries | A3_COMPATIBILITY_TEST | contract evidence | protects retention |
| `docs/PUBLIC_API_AND_WRAPPER_INVENTORY.md` | alternate path references | ARCHITECTURE_DOCUMENTATION | audit only | no external-use claim |
| `docs/DUPLICATE_BACKTEST_PATH_DECISION.md` | alternate path decision | ARCHITECTURE_DOCUMENTATION | decision only | retain temporarily |
| `docs/BACKTEST_COMPATIBILITY_CONTRACT.md` | compatibility labels | ARCHITECTURE_DOCUMENTATION | contract only | no deprecation authorization |
| `docs/BACKTEST_DEPRECATION_EVIDENCE.md` | this evidence | ARCHITECTURE_DOCUMENTATION | evidence only | no runtime action |

Totals: ALTERNATE_PRODUCTION_IMPLEMENTATION 2; INTERNAL_PRODUCTION_CALLER 0 identified; DEDICATED_ALTERNATE_TEST 2; A2_CHARACTERIZATION_TEST 1; A3_COMPATIBILITY_TEST 1; ARCHITECTURE_DOCUMENTATION 4; PACKAGE_INITIALIZER 0; IRRELEVANT_OR_GENERATED 0. The zero is reproducible because the tracked search found only implementation, tests, and documents for these alternate symbols.

## F. Tag, release, and distribution evidence

| Tag | Tag date | Contains `backtest/engine.py` | Contains `strategies/base.py` | Exposure interpretation |
|---|---|---|---|---|
| `v0.1.0` | repository tag | yes | yes | first known tagged alternate-module exposure |
| `v0.2.0` | repository tag | yes | yes | continued tagged exposure |
| `v0.3.0` | repository tag | yes | yes | current tagged exposure |

First known tagged alternate-module exposure: `v0.1.0`. Git tag count is 3. Current project metadata is version `0.3.0`. Public package-index lookup returned `No matching distribution found for tw-stock-tool`. The locally built wheel contained all six alternate/canonical paths recorded in Section C. GitHub Release query was unavailable in the completed evidence run; private-index, direct Git/editable-install, archived-artifact, and private-fork exposure remain unknown. Tags are not proof of GitHub Releases or public package publication.

## G. Public external-use evidence

| Search source | Exact query or query set | Result count | Relevant results | Exclusions | Interpretation | Limitation |
|---|---|---:|---|---|---|---|
| Repository issues | `BacktestEngine`, `BaseStrategy`, `SignalStrategy`, `tw_stock_tool.backtest.engine`, `tw_stock_tool.strategies.base` | 0 | No public issue evidence was found by the checked queries. | source implementation | no evidence | not proof of no users |
| Repository PRs | same five symbol/path queries plus `backtest engine`, `class-based backtest` | 0 | No public PR evidence was found by the checked queries. | source implementation | no evidence | not proof |
| Commit messages | `BacktestEngine`, `BaseStrategy`, `SignalStrategy` | introduction hits | two introduction commits | test/doc commits | implementation history | not external usage |
| Global public GitHub code | `"tw_stock_tool.backtest.engine"`, `"from tw_stock_tool.backtest.engine import"`, `"tw_stock_tool.strategies.base"` | unavailable | Public GitHub code-search evidence unavailable. | private code | unknown | global search unavailable |
| Public forks | alternate paths/imports | unavailable | unavailable | private forks | unknown | API evidence unavailable |
| GitHub Releases | repository releases | unavailable | unavailable | tags | unknown | release query unavailable |
| Public package index | `tw-stock-tool` | 0 | no matching distribution | private indexes | weak negative evidence | direct/private installs unknown |
| LLM Wiki | health/projects/current/search | unavailable | service unavailable | none | unknown | supporting source only |

## H. Documentation and policy evidence

| Surface/file pattern | Checked files or command | Result | Interpretation |
|---|---|---|---|
| `README.md` | tracked README search | no alternate import example | alternate paths not user-documented |
| tracked `docs/**` | `git ls-files` and symbol search | A1-A4 evidence references | architecture evidence, not support commitment |
| CLI help strings | CLI source/help tests | no alternate path help | no CLI exposure |
| `CHANGELOG*` | tracked file listing | file absent | no changelog process demonstrated |
| `RELEASE*` | tracked file listing | file absent | no release-note process demonstrated |
| `VERSIONING*` | tracked file listing | file absent | no versioning policy demonstrated |
| `DEPRECATION*` | tracked file listing | file absent | no deprecation policy demonstrated |
| `CONTRIBUTING*` | tracked file listing | file absent | no contribution policy found |
| `SECURITY*` | tracked file listing | file absent | no security policy found |
| migration guides | tracked docs search | file absent | no migration guide |
| compatibility policy | tracked docs search | no formal policy found | no window established |
| replacement API docs | A1-A3 documents | canonical path documented | insufficient as migration guide |

## I. Evidence-quality assessment

Direct wheel, history, source, and tag findings are `DIRECT`. Empty package-index and issue/PR results are `NEGATIVE_SEARCH_RESULT`. Global code, releases, forks, and Wiki are `UNAVAILABLE`. Private/direct use is `UNKNOWN`. Negative searches are weak evidence.

## J. Risk matrix

| Action | User risk | Artifact risk | Semantic risk | External-usage uncertainty | Reversibility | Evidence required |
|---|---|---|---|---|---|---|
| Keep alternate imports indefinitely | Low | Low | Low | Unknown | High | current evidence |
| Add retention-policy documentation | Low | Low | Low | Unknown | High | policy review |
| Add documentation-only deprecation | Medium | Low | Low | Unknown | Medium | replacement/window |
| Add runtime warnings | Medium | Low | Medium | Unknown | Medium | warning design |
| Remove alternate files from wheel | High | High | High | Unknown | Low | distribution/users |
| Remove alternate import paths | High | Medium | High | Unknown | Low | external evidence |
| Redirect alternate paths to canonical | High | Medium | High | Unknown | Medium | migration contract |
| Build an explicit adapter | Medium | High | High | Unknown | Medium | semantic adapter spec |

## K. Formal outcome and rationale

**INSUFFICIENT_EVIDENCE_CONTINUE_RETENTION**. Wheel inclusion is direct distribution evidence. No public index result and zero identified internal production callers are weak negative evidence. Global code, releases, forks, Wiki, private indexes, direct installs, and archived artifacts are unavailable or unknown. Warning planning is premature; removal is prohibited. Public-index absence does not eliminate distribution risk.

## L. Entry criteria for a future deprecation phase

Require confirmed distribution history, compatibility policy, replacement documentation, migration guide, warning design/tests, release target/window, rollback plan, external-risk statement, and preserved artifact/consumer contracts.

## M. Recommended next phase and non-goals

Recommend **Backtest Retention Policy Documentation**. A4 adds no warnings, deprecation markers, exports, wheel removal, adapters, NaN fixes, engine changes, migrations, version changes, publication, or Phase A5 work.
