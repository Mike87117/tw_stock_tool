# Backtest Deprecation Evidence

## A. Executive evidence outcome

**INSUFFICIENT_EVIDENCE_CONTINUE_RETENTION.** The alternate modules are in the built wheel, while external direct-install and private usage remain unknown and no compatibility/deprecation policy or window exists.

## B. Scope and investigated symbols

Investigated: `BacktestEngine`, alternate `BacktestResult`, `SignalStrategy`, and `BaseStrategy`. Internal callers, distribution exposure, documented exposure, and external-use evidence are distinct. No internal caller is not proof of no external caller.

## C. Current package exposure

`pyproject.toml` distributes `tw-stock-tool` version `0.3.0` through `src` discovery of `tw_stock_tool*`. A temporary wheel contained `backtest/__init__.py`, `backtest/engine.py`, `strategies/__init__.py`, `strategies/base.py`, and canonical backtesting files. Alternate package initializers do not export these symbols; root wrappers target canonical backtesting. Direct imports remain available. Canonical serialization and conversion reject alternate results.

## D. Historical timeline

| Event | Evidence | Implication |
|---|---|---|
| Introduction | `06e7167c75c02a69108e06d9f447fe8c9006dcfc` — feat: add backtest engine | alternate engine/base path introduced |
| A1–A3 | inventory, characterization, and contract phases | retained without migration |
| A4 wheel build | temporary external build | distributed import surface, not public endorsement |

## E. Current internal-reference inventory

| Category | Finding | Implication |
|---|---|---|
| Production | no identified alternate runtime caller | weak negative evidence only |
| Tests | dedicated engine/base and A2/A3 tests | maintained behavior |
| Documentation | architecture evidence documents | not external use |
| Package | alternate paths included in wheel | distribution exposure |

## F. Tag, release, and distribution evidence

The current temporary wheel contains alternate and canonical modules. Public package-index lookup on 2026-07-12 returned `No matching distribution found for tw-stock-tool`. This does not exclude private indexes, direct Git installs, editable installs, archived releases, or forks. Git tags, GitHub Releases, and public-index publication are separate evidence categories.

## G. Public external-use evidence

| Search source | Result | Limitation |
|---|---|---|
| Current repository | tests/docs/package references; no production caller identified | not third-party use |
| Public package index | no matching distribution | not private/direct use |
| Wiki/public code/issues/PRs/forks | unavailable or not established in this recovery | negative/unavailable searches are weak evidence |

## H. Documentation and policy evidence

No README alternate-import example, deprecation policy, compatibility window, semantic-versioning policy, or release-note process was established by this evidence. Version `0.3.0` is not a policy.

## I. Evidence-quality assessment

Wheel contents and source history are `DIRECT`; package-index absence is `NEGATIVE_SEARCH_RESULT`; unavailable public searches are `UNAVAILABLE`; private/direct usage is `UNKNOWN`. Negative searches cannot prove no users.

## J. Risk matrix

| Action | User risk | Semantic risk | Reversibility | Evidence required |
|---|---|---|---|---|
| Keep imports | low | low | high | current evidence |
| Documentation deprecation | medium | low | medium | policy/replacement |
| Runtime warnings | medium | low | medium | warning design/window |
| Remove wheel/imports | high | high | low | distribution/external evidence |
| Redirect/adapter | high | high | medium | migration contract |

## K. Formal outcome and rationale

**INSUFFICIENT_EVIDENCE_CONTINUE_RETENTION.** Wheel inclusion creates distribution exposure; external use, release policy, migration documentation, and a compatibility window remain unknown. Stronger action is rejected because absence of internal callers is insufficient.

## L. Entry criteria for a future deprecation phase

Require confirmed distribution history, compatibility policy, replacement documentation, migration guide, warning design/tests, release target/window, rollback plan, external-risk statement, and artifact/consumer preservation.

## M. Recommended next phase and non-goals

Recommend **Backtest Retention Policy Documentation**. A4 adds no warnings, deprecation marking, exports, wheel removal, adapters, NaN fix, engine change, consumer migration, version change, or publication.
