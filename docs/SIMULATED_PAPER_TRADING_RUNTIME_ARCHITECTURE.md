# Simulated Paper Trading Runtime Architecture

This document is the persistent architecture and implementation record for the
simulated paper trading runtime stream. It is intentionally narrower than a
repository-wide refactor plan: repository findings are recorded here, but only
the phase explicitly marked approved may change production code.

## 1. Baseline

| Item | Value |
| --- | --- |
| Repository | `Mike87117/tw_stock_tool` |
| Starting commit | `63daf0205f73395c60e70bb8834f7106a137499d` |
| Branch | `phase-48-10-runtime-state-model` |
| Date | 2026-07-10 |
| Working tree at start | Only intentionally untracked `custom_md.md` |
| Test baseline | `py -m unittest discover -s tests`: 1207 tests, OK |
| LLM Wiki | Available through local API v1, app version 0.5.4 |

The approved remote `main`, local `main`, and actual starting `HEAD` all matched
the required starting commit. `custom_md.md` was not read, modified, staged,
deleted, renamed, moved, or committed.

### LLM Wiki check

The local API health endpoint returned `ok: true`, `status: running`, and
version `0.5.4`. The projects endpoint identified `tw_stock_tool Wiki` as the
current project. Searches were run against the current-project search endpoint
for:

- `paper trading runtime state`
- `pending order reservation`
- `multi-symbol chronological engine`
- `portfolio exposure`
- `look-ahead`
- `engine refactor`

The Wiki was available, but the results reflected an older project summary.
They described the general research-only boundary, current architecture,
backtesting, reports, and non-goals. They did not document a runtime-state
model, pending BUY reservation, a chronological multi-symbol engine, or a
look-ahead decision for this phase. The `look-ahead` search returned no results.
Accordingly, Wiki results did not expand or replace the repository evidence
used below.

## 2. Repository Architecture Map

### Packaging and entry points

`pyproject.toml` defines the `src/` package layout and the `twstock` console
script. Root-level Python files are mostly compatibility wrappers that import
package implementations. `src/tw_stock_tool/cli/twstock_cli.py` is the unified
command router, while individual CLI modules also remain directly callable.

### Analysis and data loading

`analysis/analysis.py` composes data download, indicators, signals, and the
latest summary into `StockAnalysis`. `analysis/indicators.py` and
`analysis/signals.py` contain DataFrame transformations. `data/data_loader.py`
owns symbol fallback, TWSE/TPEX and yfinance access, normalization, cache
freshness, cache reads/writes, and error aggregation. `analysis/scanner.py`
adds concurrent multi-stock orchestration and deterministic result ranking.

### Strategies, backtesting, parameter sweep, and walk forward

`backtesting/strategies.py` emits standard entry/exit signals.
`backtesting/backtest.py` consumes them and executes signals at the following
bar open. `backtesting/parameter_sweep.py` evaluates parameter grids and ranks
results. `backtesting/walk_forward.py` separates training and test slices,
selects parameters on training data, and evaluates the chosen parameters on
the following test slice.

### Scan and report workflows

`analysis/scanner.py`, `scanners/`, and `reports/` separate core analysis rows,
watchlist selection, risk-warning presentation, and Markdown/Excel rendering,
although some workflow and export functions still coexist in large modules.
CLI modules collect arguments, call those workflows, and write or print
results. Scanner success and failure rows remain distinguishable.

### Simulated paper trading

`paper_trading/models.py` contains order, fill, rejection, position, trade-log,
and portfolio models. `paper_trading/engine.py` validates a historical
DataFrame, creates a fresh portfolio, stores one pending order in a local
variable, fills it at the next valid bar open, optionally invokes a guard, and
returns a portfolio or single-symbol result. `paper_trading/results.py`,
`serialization.py`, `exporters.py`, and their file helpers provide separate
result, JSON, Markdown/CSV, and filesystem boundaries. The historical CLI
accepts one stock and calls the result engine directly.

### Risk, kill switch, and simulated guard

`risk/` provides pure snapshots, decisions, rules, configuration, and a builder.
`kill_switch/` provides a pure state and decision boundary.
`simulated_paper_trading_guard/` adapts simulated orders and portfolios into
risk snapshots. Its portfolio exposure provider can value multiple open
positions. The workflow layer passes an optional exposure provider through to
the adapter without changing the engine.

### GUI, ML, utilities, and tests

The Tkinter GUI and app-service layer orchestrate existing research workflows.
The ML package contains offline dataset and baseline-model workflows. Utilities
own shared configuration, console locking, output writing, diagnostics, and
batch verification. The repository uses `unittest`; focused tests cover model,
engine, risk, guard, serialization/export, CLI, package exports, compatibility
wrappers, ordering, error rows, and CI imports.

## 3. Current Simulated Paper Trading Runtime

The current execution path is:

```text
historical DataFrame
-> full-history compatibility engine
-> shared runtime state
-> single-symbol bar stepper
-> per-symbol pending state
-> next-bar-open fill
-> existing single-symbol result
```

`run_simulated_paper_trading(...)` validates the complete DataFrame and standard
signals, creates `SimulatedPortfolio(cash=float(initial_cash))`, and sets
`pending_order` to `None`. On each row it first attempts the previous bar's
pending fill at the current open, clears that pending state, then creates at
most one new BUY or SELL intent for the configured symbol. Invalid open prices
and portfolio fill errors currently cause the fill to be skipped. The
result-building wrapper summarizes only the requested symbol.

The next-bar-open rule prevents same-bar signal/price look-ahead in this path.
It does not by itself coordinate bars across symbols.

## 4. Confirmed Architectural Facts

- `SimulatedPortfolio` can contain positions for multiple symbols.
- The current engine creates a fresh portfolio for every invocation.
- Pending order state is local to one engine invocation.
- The current result boundary is single-symbol.
- The historical simulated paper trading CLI accepts one stock.
- The CLI calls `run_simulated_paper_trading_result(...)` directly.
- `DataFramePortfolioExposureProvider` can value multiple open positions.
- That provider requires an exact candidate signal-time price for every open
  position with positive quantity.
- Both workflow helpers pass through an optional portfolio exposure provider.
- No chronological multi-symbol coordinator exists.
- No user-facing `--max-total-exposure` option exists.
- The existing risk rule adds a BUY candidate notional to filled exposure and
  subtracts a SELL candidate notional, but no runtime object yet represents
  accepted pending BUY reservations shared across symbols.
- Package export contracts are explicitly tested for paper trading, risk, guard,
  and kill-switch surfaces; Phase 48.10 does not change an export surface.

## 5. Invalid Architecture Options

### Sequential full-history execution

Running all history for symbol A and then all history for symbol B against one
shared portfolio is invalid. Symbol A's future fills and position state could
affect earlier calendar dates processed later for symbol B. This introduces
cross-symbol look-ahead. A future coordinator must merge or step symbol bars in
deterministic chronological order.

### Initial portfolio injection by itself

Adding only `initial_portfolio` to the existing engine is insufficient. It
would share filled state but would not expose or coordinate each symbol's
pending order, define global chronological ordering, or reserve same-time BUY
exposure. Full-history calls would still have invalid temporal semantics.

### Single-symbol CLI total exposure

Adding `--max-total-exposure` to the current one-stock CLI would suggest a
portfolio-wide guarantee while the CLI constructs only one stock's DataFrame,
one fresh portfolio, and one engine run. It cannot price other holdings,
coordinate same-time candidates, or account for accepted pending BUYs. The flag
must wait until the multi-symbol runtime and portfolio result boundaries exist.

## 6. Pending BUY Exposure Reservation

The failure case is:

```text
current filled exposure = 0
BUY A candidate notional = 1000
BUY B candidate notional = 1000
limit = 1500
```

If both candidates are checked before either fills and accepted pending BUYs
are not reserved, each sees zero filled exposure and both can pass. The future
effective exposure rule is:

```text
effective exposure
= filled portfolio exposure
+ accepted pending BUY reserved exposure
```

The reserved amount for a pending BUY is `quantity * reference_price`. A
pending SELL contributes zero reservation and must not reduce exposure before
its fill actually occurs. Phase 48.10 represents this state and arithmetic but
does not call a guard, process candidates, order same-time events, or fill an
order.

## 7. Refactor Review Matrix

| Area | Files / symbols inspected | Current responsibility | Finding | Classification | Evidence | Compatibility risk | Recommended phase | Approved to change now? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Package layout | `pyproject.toml`, root wrappers, `cli/twstock_cli.py`, `tests/test_root_wrappers.py`, `tests/test_ci_imports.py` | Install package and preserve old entry points | Console script and compatibility entry points are intentional | KEEP | Current tests import and execute both package and wrapper surfaces | High if removed | Existing behavior | No |
| Legacy wrappers | Root `analysis.py`, `backtest.py`, `data_loader.py`, `indicators.py`, `strategies.py`, report/CLI wrappers | Delegate imports or execution to package modules | Many one-purpose wrapper files are deletion candidates after a published migration | REMOVE_CANDIDATE | Wrappers mostly re-export one package implementation; README and tests promise compatibility | High | Separate compatibility deprecation phase | No |
| Analysis composition | `analysis/analysis.py`: `StockAnalysis`, `analyze_stock`, `build_latest_summary` | Compose loading, indicators, signals, latest result | Small, explicit composition boundary | KEEP | Dependencies are direct and returned data is structured | Low | Existing behavior | No |
| Indicators and signals | `analysis/indicators.py`, `analysis/signals.py`, `backtesting/strategies.py` | Pure DataFrame transforms and signal generation | Current calculations use current and prior rows without future shifts | KEEP | Rolling/EMA and `.shift(1)` logic; no negative shift observed | Medium if semantics change | Existing behavior | No |
| Data loading | `data/data_loader.py`: `download_tw_stock` and helpers | Network fallback, validation, normalization, cache I/O | Module combines several responsibilities and broad fallback errors | REFACTOR_LATER | One large module owns providers, cache policy, parsing, and orchestration | High because data fallback behavior is user-visible | Future data-provider phase | No |
| Scanner | `analysis/scanner.py`: `scan_one_stock`, `scan_stocks` | Concurrent scan, filtering, errors, ranking | Deterministic output and explicit error rows are appropriate | KEEP | Stable mergesort plus stock tie-break; failed rows retained separately | Medium | Existing behavior | No |
| Report workflows | `reports/daily_report.py`, `reports/backtest_report.py`, `reports/parameter_sweep_report.py`, `reports/walk_forward_report.py` symbol/index review | Build and render research artifacts | Some large modules mix shaping and rendering, but the split is not needed here | REFACTOR_LATER | Builder, renderer, and file-export functions coexist | Medium | Report-specific phase | No |
| Backtest function engine | `backtesting/backtest.py`: `run_backtest_result`, `run_backtest` | Historical execution and metrics | Next-bar-open pending execution is explicit; result adapter preserves compatibility | KEEP | Comment and control flow execute yesterday's signal at today's open | High | Existing behavior | No |
| Parameter sweep | `backtesting/parameter_sweep.py`: parameter-set loop and ranking | Evaluate and rank in-sample parameter combinations | Errors remain distinguishable; equal-metric ordering lacks an explicit secondary key | REFACTOR_LATER | Stable sort preserves grid order but the tie-break contract is implicit | Medium | Parameter-sweep determinism phase | No |
| Walk forward | `backtesting/walk_forward.py`: `split_windows`, `_evaluate_window_strategy`, `run_walk_forward` | Train selection then test evaluation | Train/test boundaries avoid selecting on test results | KEEP | Non-overlapping slices within each window; best parameters chosen from train metric before test call | High if changed | Existing behavior | No |
| CLI orchestration | `cli/main.py`, `cli/backtest_report.py`, `cli/parameter_sweep_report.py`, `cli/walk_forward_report.py`, `cli/daily_report_cli.py` | Parse, orchestrate, print, and export | Argument and parameter dictionary assembly is duplicated | REFACTOR_LATER | Similar strategy/backtest parameter plumbing appears in multiple CLI modules | High because CLI compatibility is tested | Future CLI maintenance phase | No |
| Paper models | `paper_trading/models.py`, `tests/test_paper_trading_models.py` | Orders, fills, positions, portfolio, log | Multi-position portfolio is suitable for shared runtime state | KEEP | `positions` is keyed by symbol and fill application is centralized | High | Existing behavior | No |
| Runtime state boundary | `paper_trading/runtime.py`, `engine.py` | Hold shared portfolio and per-symbol pending state | Integrated and preserves pending BUY reservation | KEEP | Single-symbol engine and coordinator share the same state model | High | Phase 48.10-48.12 complete | No |
| Paper engine and stepper | `paper_trading/engine.py`, `stepper.py` | Full-history compatibility wrapper and shared per-bar lifecycle | Responsibilities are separated; all accepted pending outcomes are audited | KEEP | Stepper records fills, invalid-open skips, and portfolio failures | High | Phase 49 complete | No |
| Fill outcomes | `paper_trading/stepper.py`, `models.py`, Trade Log tests | Apply fills and retain every terminal simulated outcome | Typed filled, skipped-invalid-open, and failed-portfolio-validation events are persisted | KEEP | Error code and message survive result/export boundaries | High because artifacts are versioned | Phase 49 complete | No |
| Chronological coordination | `paper_trading/coordinator.py` | Shared multi-symbol timeline | Fill-first same-time handling and ascending-symbol candidate order are implemented | KEEP | Coordinator tests cover chronology, reservation, and look-ahead boundaries | High | Phase 48.12 complete | No |
| Paper result | `paper_trading/results.py`, `tests/test_paper_trading_results.py` symbol/index review | Immutable single-symbol summary and row builders | Correct for current engine; cannot represent aggregate portfolio outcome | DEFER | Result stores one `symbol`, one position quantity, and one last price | High due schema compatibility | Phase 48.13 | No |
| Serialization/export | `paper_trading/serialization.py`, `exporters.py`, file helpers | Versioned single-symbol result artifacts | Schema v3 persists audit events; v1/v2 remain readable; Trade Log Markdown/CSV is additive | KEEP | Strict round-trip and unknown-field tests protect the boundary | High | Phase 49 complete | No |
| Historical paper CLI | `cli/simulated_paper_trading_cli.py`, CLI tests | Load one stock, run strategy, construct guard, call engine, print summary | Must not expose portfolio-wide total exposure yet | DEFER | Required `--stock`; no portfolio exposure provider or total-exposure flag | High | Phases 48.15-48.16 | No |
| Risk rules | `risk/models.py`, `risk/rules.py`, `risk/config.py`, `risk/builder.py`, tests | Pure risk snapshots and decisions | Keep pure rule boundary; pending reservations belong to runtime input assembly | KEEP | Rules consume snapshots and have no DataFrame/CLI dependency | High | Existing behavior | No |
| Guard adapter/builders | `simulated_paper_trading_guard/adapter.py`, `builder.py`, `workflow.py`, provider/workflow tests | Bridge portfolio/order state to risk and kill-switch decisions | Injection and passthrough boundaries are appropriate | KEEP | Optional portfolio exposure provider is passed through without engine coupling | Medium | Existing behavior | No |
| Exposure provider | `simulated_paper_trading_guard/providers.py`: `DataFramePortfolioExposureProvider` | Value all filled positions | Exact signal-time lookup for every open symbol needs a coordinator-aligned pricing policy | REFACTOR_LATER | Missing a timestamp for any open position raises an error | High | Phase 48.12 provider policy review | No |
| Kill switch | `kill_switch/models.py`, `decisions.py`, package-boundary tests | Pure activation state and decision | Independent, fail-closed boundary is appropriate | KEEP | No engine, DataFrame, broker, or CLI dependency | High | Existing behavior | No |
| Public exports | `paper_trading/__init__.py`, `risk/__init__.py`, guard/kill-switch `__init__.py`, package-boundary tests | Stable package API | Do not export new runtime models during this phase | KEEP | Existing exports are asserted by tests; approved files exclude `__init__.py` | High | Consider after runtime integration | No |
| GUI and ML | `gui/` and `ml/` definition/import inventory; associated tests | Offline research UI and ML workflows | Unrelated to runtime state | DEFER | No dependency in current paper runtime path | High | Separate roadmap work | No |
| Broker/live trading | `README.md`, `docs/AUTO_TRADING_SAFETY.md`, Roadmap | Long-term safety constraints only | No implementation belongs in this stream | DEFER | Repository explicitly remains research-only, simulated-only, offline-only | Critical | Unapproved future roadmap | No |

### Refactor audit conclusion

The only `REFACTOR_NOW` finding is the explicit runtime model boundary added by
Phase 48.10. No existing engine, CLI, risk, guard, provider, result, exporter,
serialization, or package-export code must change to create and test that pure
model. All other cleanup preferences were downgraded to `REFACTOR_LATER`,
`DEFER`, or `REMOVE_CANDIDATE` because they do not block this phase.

### Ponytail complexity audit

Ranked over-engineering findings, recorded but not applied:

1. `delete:` retire legacy root wrappers after a compatibility window; use the
   `twstock` console script and package modules. [`/` root wrappers]
2. `shrink:` centralize duplicated CLI strategy/backtest argument-to-dictionary
   plumbing only when a CLI phase already touches those modules. [`src/tw_stock_tool/cli/`]
3. `shrink:` separate provider/cache orchestration in the data loader only when
   changing fallback policy. [`src/tw_stock_tool/data/data_loader.py`]

Estimated removable surface after explicit deprecation and migration work:
`net: -180 lines, -0 deps possible.` No deletion is approved in Phase 48.10.

## 8. Approved Phase Sequence

```text
Phase 48.10 — COMPLETE
Phase 48.11 — COMPLETE
Phase 48.12 — COMPLETE
Phase 48.13 — PLANNED / NOT AUTHORIZED
Phase 48.14 — PLANNED / NOT AUTHORIZED
Phase 48.15 — PLANNED / NOT AUTHORIZED
Phase 48.16 — PLANNED / NOT AUTHORIZED
```

Phases 48.10, 48.11, and 48.12 are complete.
Phase 48.13 and all later phases remain planning entries and are not authorized.

### Completed Phase 48.11 boundary

Phase 48.11 changed the smallest set needed to step one symbol by one bar
using an injected `SimulatedPaperTradingRuntimeState`. It preserved the
current public full-history functions as compatibility wrappers, next-bar-open
timing, guard behavior, costs, and existing result behavior. It added no
coordinator, aggregate result, CLI flag, or public package export.

## 9. Decision Log

| Decision | Reason | Evidence | Alternatives rejected | Compatibility impact | Follow-up phase |
| --- | --- | --- | --- | --- | --- |
| Add pure runtime models in a new module | State needs an explicit testable boundary before engine extraction | Portfolio and pending order are local variables in the current engine | Modify the engine now; inject only an initial portfolio | None until integrated | 48.11 |
| Store pending orders by symbol | A coordinator must retain independent next-bar intent for each symbol | Current one-order local variable cannot represent multiple symbols | One global pending order; list without symbol invariant | New module only | 48.11-48.12 |
| Reserve BUY at accepted reference price | Same-time accepted BUYs must consume exposure before fills | Two 1000 candidates can each pass a 1500 limit against zero filled exposure | Reserve at future fill price; do not reserve | New module only | 48.12 |
| Pending SELL reservation is zero | Filled holdings remain exposed until SELL fill | A pending SELL has not changed the portfolio | Subtract SELL notional early | New module only | 48.12 |
| Preserve exact portfolio identity | Runtime state must coordinate one shared mutable portfolio | Rebuilding would split fills/logs/state | Clone or normalize portfolio | New module only | 48.11-48.12 |
| Validate the provided dictionary in place | Preserve exact state values and avoid hidden copying | Contract requires key/value/symbol invariants and exact state identity | Silently repair mismatches; coerce arbitrary mappings | Caller receives same mapping object; invalid input fails | 48.11 |
| Add no optional state methods in 48.10 | Properties and direct mapping are sufficient for the approved contract | No stepper exists yet to prove method semantics | Speculative `set/pop/get` API | Smaller API surface | Reconsider in 48.11 |
| Do not export runtime models from package root | Approved scope excludes `paper_trading/__init__.py`; direct module import is adequate | Package exports are intentionally tested | Expand public API early | No existing public API change | Reconsider after integration |
| Keep engine and CLI unchanged | This phase is model/state only | Prohibited scope and independent model tests | Partial coordinator or misleading CLI exposure | Zero runtime behavior change | 48.11-48.16 |
| Use repository evidence over stale Wiki summaries | Wiki had no current runtime/reservation decisions | Search results were generic or empty | Infer missing design from generic Wiki pages | None | Keep document current |

## 10. Implementation Record

### Architecture audit commit

- Changed file: `docs/SIMULATED_PAPER_TRADING_RUNTIME_ARCHITECTURE.md`
- Contract: persistent repository architecture map, invalid options, reservation
  rule, refactor matrix, approved sequence, and decision log
- Baseline tests: 1207 tests, OK
- Commit SHA: `bb48c9476fc9ae8f84f287fe99296ac18e76fbf0`

### Phase 48.10 implementation

- Changed files: this document, `docs/DEVELOPMENT_ROADMAP.md`,
  `src/tw_stock_tool/paper_trading/runtime.py`, and
  `tests/test_paper_trading_runtime.py`
- Implemented `SimulatedPendingOrderState` with strict order and finite positive
  numeric reference-price validation, float normalization, BUY reservation, and
  zero SELL reservation
- Implemented `SimulatedPaperTradingRuntimeState` with exact portfolio identity,
  per-symbol dictionary validation, key/order-symbol equality, independent
  default mappings, and total BUY reservation
- Added no optional state methods, package exports, engine integration, or
  runtime behavior changes
- Tests:
  - targeted runtime: 30 tests, OK
  - paper model regression: 40 tests, OK
  - runtime-related engine/guard regression: 121 tests, OK
  - full suite: 1237 tests, OK
- Baseline-to-final delta: 30 tests
- Architecture audit commit: `bb48c9476fc9ae8f84f287fe99296ac18e76fbf0`
- Phase 48.10 implementation commit: `4f557573e93f1458fabe734bde38c2af0696e46f`

### Phase 48.11 implementation

- Changed files: this document, `docs/DEVELOPMENT_ROADMAP.md`,
  `src/tw_stock_tool/paper_trading/engine.py`, `src/tw_stock_tool/paper_trading/stepper.py`,
  `tests/test_paper_trading_engine.py`, `tests/test_paper_trading_stepper.py`,
  and `tests/test_simulated_paper_trading_cli.py`
- Extracted simulated bar processing into a new `step_simulated_symbol_bar` function in `stepper.py`
- Updated the existing engine loop in `engine.py` to maintain backwards compatibility while delegating to the stepper
- Updated the engine to use `SimulatedPaperTradingRuntimeState`
- Enforced a fail-closed policy where signals on invalid (NaN, Infinity, zero, negative) Open prices do not record accepted orders or trigger fills
- Did not add a multi-symbol chronological coordinator, aggregate portfolio result, or CLI flag
- Did not export new modules from `tw_stock_tool.paper_trading`

## Record
- implementation commit: `15ec8611510aaf6141f964385dabff9bd449addc`
- initial architecture-record commit: `cb6026a06f23dd4542293e0f2b6ea8151822073c`
- test-coverage correction commit: `c27ae1df2d564728edda93a5fb1ae31d1df96cee`
- intermediate HOLD record commit: `ceb466c84bebb6dba5ee494aa4d538f3fa1e160d` (captured the one failing legacy CLI regression and was superseded by this final correction)
- CLI regression correction commit: `910771450acbf95860a3838ecb8be0da96d29ea1`
- whitespace cleanup commit: `1704a3bd0bc2057e7b7cc8cbbb96ed69594775f9`
- trailing-whitespace occurrences removed: 28
- AST equivalence check: PASS
- `git diff main...HEAD --check`: PASS
- Git trailing-whitespace scan: PASS
- independent pathlib trailing-whitespace scan: PASS
- whitespace cleanup changed no Python semantics
- final targeted and full-suite tests remained PASS

- Stepper and engine: 62 tests, OK
- Runtime/model regression: 102 tests, OK
- Guard regression: 92 tests, OK
- CLI regression: 42 tests, OK
- Broader paper-trading regression: 429 tests, OK
- Full suite: 1270 tests, OK

- all final results PASS
- invalid signal-row Open now produces no candidate, no guard call, no accepted order, no rejection, and no fill
- CLI emits a normal zero-order summary
- no production code change was required
- no CLI implementation change was required


Known limitations are intentional: aggregate result, aggregate serialization/export,
multi-symbol CLI, `--max-total-exposure`, portfolio-wide user-facing
enforcement, broker interface, live data, or live order capability exists.

### Phase 48.12 implementation

- Changed files: `docs/SIMULATED_PAPER_TRADING_RUNTIME_ARCHITECTURE.md`, `docs/DEVELOPMENT_ROADMAP.md`, `src/tw_stock_tool/paper_trading/coordinator.py`, `src/tw_stock_tool/simulated_paper_trading_guard/providers.py`, `tests/test_paper_trading_coordinator.py`, `tests/test_simulated_paper_trading_guard_providers.py`
- Implemented `run_chronological_multi_symbol_simulated_paper_trading` in `coordinator.py` to perform deterministic same-time ordering (ascending symbol order) and chronological union interleaving.
- All bars at a timestamp are available for as-of valuation. Missing bars cause no signal but prices are retrieved via nearest-earlier logic.
- Delegated raw-Open invalid-price fail-closed behavior to the existing stepper.
- Added `ChronologicalRuntimePortfolioExposureProvider` that evaluates as-of valuation using only rows `<= signal_time`.
- `ChronologicalRuntimePortfolioExposureProvider` fails closed on invalid selected as-of prices (does not fall back to older valid rows).
- Includes pending BUY reservations; pending SELL reservations contribute zero.
- The engine and CLI remain single-symbol.
- Known limitations: aggregate result, aggregate serialization/export, multi-symbol CLI, and CLI `--max-total-exposure` still do not exist.


- implementation commit: `07973c595d98d4754443f719cb5133076720653d`
- test and documentation correction commit: `0167e0a21f7d3de0156a2eaa71c0ccab9a783071`
- closeout correction commit: 950bd3501a4f299ab2bc0bcaea0ebcd49831ee6f

Exact final test commands and counts:
```powershell
py -m unittest tests.test_paper_trading_coordinator (28 tests PASS)
py -m unittest tests.test_simulated_paper_trading_guard_providers (76 tests PASS)
py -m unittest discover -s tests -p "test_paper_trading_*.py" (216 tests PASS)
py -m unittest discover -s tests -p "test_simulated_paper_trading_guard*.py" (189 tests PASS)
py -m unittest discover -s tests -p "test_risk_*.py" (177 tests PASS)
py -m unittest discover -s tests (1324 tests PASS)
```

Whitespace checks and actual results:
- `git diff origin/main...HEAD --check`: PASS
- `git grep -nI -E '[[:blank:]]+$'`: PASS
- `independent py/pathlib trailing-whitespace scan`: PASS

Existing engine remains single-symbol.
Historical CLI remains single-symbol.
No aggregate portfolio result exists.
No aggregate serialization/export exists.
No multi-symbol CLI exists.
CLI `--max-total-exposure` does not exist.
No broker, live-trading, semi-auto, or auto-trading capability exists.

### Phase 48.12.1 implementation

- same-timestamp fill-before-signal correction
- all fills complete before any new candidate evaluation
- deterministic candidate ordering remains symbol ascending
- single-symbol stepper remains a compatibility wrapper
- aggregate result remains deferred

implementation commit:
46ce2470923cee2adfe55982b01ed15973c079db


### Phase 48.12.1 verification closeout

- production implementation commit: `46ce2470923cee2adfe55982b01ed15973c079db`
- test-correction commit: `55e6fdfb3726950724be9bdfdd42713b3e32ee51`
- documentation closeout commit: 1ff325243e7e80f373a07a14c9194f72a6c41499
- test-correction commit (pending SELL): 5d45ba41ab89420e29fe758c325b7b251c4583b5

Exact changed files:
- `docs/SIMULATED_PAPER_TRADING_RUNTIME_ARCHITECTURE.md`
- `src/tw_stock_tool/paper_trading/coordinator.py`
- `src/tw_stock_tool/paper_trading/stepper.py`
- `tests/test_paper_trading_coordinator.py`
- `tests/test_paper_trading_stepper.py`

Exact focused test commands and counts:
```powershell
py -m unittest tests.test_paper_trading_stepper (31 tests PASS)
py -m unittest tests.test_paper_trading_coordinator (36 tests PASS)
py -m unittest tests.test_paper_trading_engine (34 tests PASS)
py -m unittest tests.test_simulated_paper_trading_guard_providers (76 tests PASS)
```

Exact broader regression commands and counts:
```powershell
py -m unittest discover -s tests -p "test_paper_trading_*.py" (227 tests PASS)
py -m unittest discover -s tests -p "test_simulated_paper_trading_guard*.py" (189 tests PASS)
py -m unittest discover -s tests -p "test_risk_*.py" (177 tests PASS)
```

Exact full-suite count:
```powershell
py -m unittest discover -s tests (1335 tests PASS)
```

Whitespace checks and actual results:
- `git diff origin/main...HEAD --check`: PASS
- `independent py/pathlib trailing-whitespace scan`: PASS

Known limitations:
- The engine and CLI remain single-symbol.
- Aggregate portfolio result logic, aggregate JSON serialization, Markdown export, and CLI multi-symbol wrappers (such as `--max-total-exposure`) remain deferred.

## 11. Phase 49 Canonical Trade Log

The canonical audit boundary is `SimulatedTradeLog.records`. Each `SimulatedTradeLogRecord` is frozen, slotted, deterministically sequenced, and uses `SimulatedTradeEventType` plus `SimulatedTradeStatus` rather than scattered free-form lifecycle strings. The compatibility collections `orders`, `fills`, and `rejections` remain populated.

Lifecycle integration is centralized in `paper_trading/stepper.py`, so the full-history engine and chronological coordinator share candidate, guard, pending, rejection, fill, invalid-open, and portfolio-validation-failure recording. `risk_allowed=None` means no guard ran. `next_bar_open`, fill-before-signal ordering, symbol ordering, pending BUY reservation, and no-look-ahead behavior are unchanged.

`SimulatedPaperTradingResult.audit_log` exposes the records. JSON schema v3 adds `audit_log`; strict v1/v2 loading is retained. Markdown adds `Trade Log`; CSV adds `<basename>_trade_log.csv`; Orders, Fills, and Rejections remain.

Current limits remain deliberate: the stable result and CLI are single-symbol, the coordinator has no aggregate public result/CLI, and no broker, live account, real order, semi-automatic, or automatic trading interface exists.

## 12. Phase 53.1 Aggregate Portfolio Result Boundary Planning

### 12.1 Planning baseline and evidence

Phase 53.1 planning was performed from repository `Mike87117/tw_stock_tool` on
branch `main` at `302e1c4036d4a0262f68b811ca9a944014a2c340`; `origin/main` matched
the same commit. The working tree was clean before inspection and the existing
user stash was not touched. The required baseline targeted tests all passed:

```text
test_paper_trading_models       16 tests PASS
test_paper_trading_runtime      30 tests PASS
test_paper_trading_coordinator  36 tests PASS
test_paper_trading_results      21 tests PASS
test_paper_trading_serialization 46 tests PASS
test_simulated_paper_trading_cli 42 tests PASS
full suite                       1792 tests PASS
compileall                       PASS
```

The local LLM Wiki health, projects, and current-project search endpoints were
not reachable at the available local endpoints during this planning run. The
Wiki result is therefore `unavailable` and non-blocking; repository source,
tests, runtime behavior, and this architecture document are authoritative.

### 12.2 Current execution path and gap

The implemented multi-symbol path is:

```text
Mapping[str, DataFrame]
-> chronological union timeline
-> deterministic symbol-ascending processing
-> same-timestamp pending fills first
-> per-symbol candidate and guard evaluation
-> shared SimulatedPortfolio and SimulatedPaperTradingRuntimeState
-> runtime_state returned by run_chronological_multi_symbol_simulated_paper_trading(...)
```

`SimulatedPortfolio.positions` is already keyed by symbol, and
`SimulatedTradeLog.records` is the global append-only canonical audit sequence.
`SimulatedPaperTradingRuntimeState.pending_orders` preserves at most one
accepted next-bar order per symbol and exposes pending BUY reservation through
`total_reserved_buy_notional`. The coordinator intentionally returns mutable
runtime state, not a report result.

The remaining gap is a pure, offline aggregate result boundary. The current
`SimulatedPaperTradingResult` has one `symbol`, one final position quantity,
one average cost, one optional last price, and single-symbol equity semantics.
It cannot represent all positions, per-symbol valuation/PnL, aggregate equity,
global counts, or terminal pending orders without changing the existing
single-symbol API and schema v3 contract.

### 12.3 Approved aggregate result contract for Phase 53.2

Phase 53.2 should add a separate module-level model, without changing
`SimulatedPaperTradingResult`:

```python
@dataclass(frozen=True, slots=True)
class SimulatedPortfolioPositionResult:
    symbol: str
    quantity: int
    average_cost: float
    last_price: float | None
    market_value: float
    realized_pnl: float
    unrealized_pnl: float


@dataclass(frozen=True, slots=True)
class SimulatedPortfolioPendingOrderResult:
    order_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: int
    signal_time: Any
    created_at: Any | None
    strategy: str | None
    reference_price: float
    reserved_buy_notional: float


@dataclass(frozen=True, slots=True)
class SimulatedPortfolioTradingResult:
    initial_cash: float
    final_cash: float
    total_market_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    total_return: float
    total_return_pct: float | None
    open_position_count: int
    order_count: int
    fill_count: int
    rejection_count: int
    audit_record_count: int
    positions: tuple[SimulatedPortfolioPositionResult, ...]
    pending_orders: tuple[SimulatedPortfolioPendingOrderResult, ...]
    orders: tuple[SimulatedOrder, ...]
    fills: tuple[SimulatedFill, ...]
    rejections: tuple[SimulatedOrderRejection, ...]
    audit_log: tuple[SimulatedTradeLogRecord, ...]
```

The position and pending-order rows are immutable scalar snapshots. Pending
order metadata remains represented by the canonical order/audit records rather
than being duplicated in a speculative result field. The aggregate result is
frozen and slotted; collections are tuples. No rounding occurs at this domain
boundary; exporters may format values later.

The builder should accept exactly one
`SimulatedPaperTradingRuntimeState`, an explicit `Mapping[str, float]` of final
valuation prices, and `initial_cash`. It must validate the runtime state and
read the portfolio and pending state without replacing or mutating either.
This prevents an inconsistent portfolio/pending pair from being supplied.

#### Final valuation-price contract

- `last_prices` must be a `Mapping`; it is not a DataFrame, provider,
  callback, or network/data-fetching input.
- Every key must be a non-blank string. Every value, including extra entries,
  must be a numeric `Real` but not `bool`, normalized to `float`, finite,
  and strictly positive.
- Extra symbol prices are allowed and ignored after validation. This lets a
  caller pass a complete final-price map without changing the position policy.
- Every open position (`quantity > 0`) must have a supplied price; a missing
  price raises `PaperTradingModelError` (fail closed).
- Closed positions do not require a price and expose `last_price=None`, zero
  market value, and zero unrealized PnL.
- No fetching, fallback lookup, DataFrame re-read, or implicit last-price
  retention occurs in the pure builder. The caller owns the final-price source.

#### Position inclusion and ordering

The result includes every valid entry already present in
`portfolio.positions`, including quantity-zero positions with realized PnL.
Rejected-only symbols that never entered `portfolio.positions` are not invented
as positions. Position rows are sorted by symbol for deterministic output;
source dictionaries are never sorted in place. `symbol_count` and
`closed_position_count` are intentionally derived (`len(positions)` and a
quantity predicate) rather than stored duplicate fields.

#### Aggregate metric definitions

- `final_cash` is the runtime portfolio cash at build time.
- `total_market_value` is the sum of `quantity * last_price` for open rows.
- `total_equity = final_cash + total_market_value`.
- `realized_pnl` is the sum of every position's realized PnL, including closed
  positions.
- `unrealized_pnl` is the sum of open-position unrealized PnL only.
- `total_return = total_equity - initial_cash`.
- `total_return_pct` is `total_return / initial_cash`, or `None` when initial
  cash is zero.
- `open_position_count` counts rows with quantity greater than zero.
- `order_count`, `fill_count`, and `rejection_count` are lengths of the
  existing global trade-log collections, including accepted orders that remain
  pending.
- `audit_record_count` is the length of `SimulatedTradeLog.records`.

Initial cash and all derived numeric values must remain finite and non-negative
where the existing models require it. The builder retains full float precision;
there is no display-oriented rounding in the result model.

#### Trade Log and pending terminal state

`orders`, `fills`, `rejections`, and `audit_log` are copied to tuples in
their existing order. The audit tuple is the canonical global chronological
sequence; it must not be regenerated, grouped by symbol, or reordered. No risk
decision, skip, failure, or rejection may be fabricated or dropped.

The result includes a deterministic tuple of pending-order snapshots sorted by
`(symbol, order_id)`. A pending BUY exposes its existing reference price and
reserved BUY notional; a pending SELL exposes zero reservation. Pending BUY
reservation is not current holdings, so it is not included in
`total_market_value` or `total_equity`; it remains visible in the pending
snapshot. Pending orders are included in `order_count` because they are already
accepted in the canonical order collection.

The builder must not fill, cancel, clear, or append terminal events for pending
orders. Phase 53.2 only reports coordinator terminal state and does not change
runtime behavior or add a synthetic terminal audit event.

#### Mutation, identity, and error policy

The builder is read-only: it must not mutate runtime state, portfolio, position
objects, pending mappings, trade-log lists, or caller-provided price mappings;
it must not sort source collections in place. Portfolio identity remains the
same object before and after building a result.

Phase 53.2 should reuse `PaperTradingModelError`, matching current paper-trading
model conventions. It should fail closed for invalid initial cash, wrong runtime
state type, non-Mapping prices, non-string/blank symbol keys, missing open
prices, boolean/string/non-finite/non-positive prices, invalid position state,
pending key/order-symbol mismatches, and invalid pending-order state. No new
exception hierarchy is justified.

#### Single-symbol compatibility

`SimulatedPaperTradingResult`, `build_simulated_paper_trading_result`, the
single-symbol engine, schema v1/v2/v3 loading, schema v3 serialization, existing
Markdown/CSV exporters, existing single-stock CLI flags, and current package
exports remain unchanged. The aggregate model is independent rather than a
subclass or widening of the single-symbol result. Phase 53.2 should initially
be imported from its module; package-root exports can wait for a separately
reviewed stable public API decision.

### 12.4 Deferred serialization and CLI boundaries

The aggregate result must not be inserted into the existing single-symbol JSON
schema v3. A later serialization phase may define an independent
`simulated_portfolio_trading_result` schema v1. The planned sequence remains:

```text
Phase 53.2  aggregate pure-Python result model and builder
Phase 53.3  aggregate serialization/schema boundary
Phase 53.4  offline artifact operations and Markdown/CSV exporters
Phase 53.5  multi-symbol CLI orchestration
Phase 53.6  portfolio-wide user-facing risk enforcement
```

The current CLI still accepts one `--stock`, builds one DataFrame, and calls the
single-symbol engine. It does not build a DataFrame mapping or shared runtime
state. No multi-symbol CLI flag and no `--max-total-exposure` option is exposed
by this planning phase.

### 12.5 Rejected designs

| Design | Decision | Repository-based reason |
| --- | --- | --- |
| Widen `SimulatedPaperTradingResult` for many symbols | Reject | Its `symbol` and single-position fields are covered by existing tests and schema v1/v2/v3; widening would make compatibility and exporters ambiguous. |
| Return only mutable `SimulatedPortfolio` | Reject | It leaks runtime mutation, has no explicit valuation contract, and forces callers to recompute metrics and terminal pending state. |
| Build one single-symbol result per symbol | Reject | Cash, equity, counts, risk decisions, and the global chronology would be duplicated or split, making portfolio totals undefined. |
| Implement JSON first | Reject | The current serializer is deliberately a strict single-symbol schema v3 boundary; a file format must follow a tested domain model, not perform domain calculations. |
| Make the coordinator return the aggregate result directly | Reject | The coordinator currently owns chronological execution and returns reusable runtime state; reporting there would couple execution, valuation, and snapshot semantics and reduce state reuse. |

### 12.6 Phase 53.2 exact scope and test matrix

Proposed files:

```text
src/tw_stock_tool/paper_trading/portfolio_results.py
tests/test_paper_trading_portfolio_results.py
docs/SIMULATED_PAPER_TRADING_RUNTIME_ARCHITECTURE.md
docs/DEVELOPMENT_ROADMAP.md
```

The implementation scope is limited to the three immutable result snapshot
types, a pure builder, deterministic ordering, final-price validation,
aggregate metrics, pending-order snapshots, and read-only behavior tests.

The Phase 53.2 test matrix must cover:

- construction: empty/cash-only, one and many open positions, closed realized
  positions, mixed open/closed positions, event preservation, pending BUY,
  pending SELL, and pending orders on multiple symbols;
- valuation: exact prices, one missing open price, extra prices, bool/string,
  NaN/infinity/zero/negative prices, and closed positions without a price;
- metrics: market value, equity, realized/unrealized PnL, total return,
  zero-initial-cash percentage, open count, and deterministic ordering;
- compatibility and immutability: unchanged single-symbol result/builder,
  unchanged schema v1/v2/v3, unchanged exporters/CLI/coordinator behavior,
  unchanged Trade Log order, runtime/portfolio identity, and no in-place
  sorting or mutation of mappings/lists.

Explicit Phase 53.1 and Phase 53.2 non-goals are JSON, Markdown, CSV,
filesystem I/O, CLI/GUI changes, network fetching, coordinator behavior
changes, Risk Manager or Kill Switch rule changes, `--max-total-exposure`,
package-version changes, Broker Interface, Shioaji, live/real/auto trading,
and investment advice or guaranteed returns.

### 12.7 Decision log and phase status

| Decision | Rationale | Follow-up |
| --- | --- | --- |
| Add an independent frozen/slotted aggregate result | Preserve the tested single-symbol boundary while providing an immutable snapshot | Phase 53.2 |
| Require explicit finite positive final prices for open positions | Keep valuation pure, deterministic, and fail closed without data fetching | Phase 53.2 |
| Include closed portfolio positions | Preserve per-symbol realized PnL without inventing symbols from rejected orders | Phase 53.2 |
| Preserve global event ordering and terminal pending state | Maintain canonical audit chronology and avoid runtime mutation | Phase 53.2 |
| Defer schema, exporters, CLI, and public exports | Avoid coupling an unimplemented domain boundary to user-facing surfaces | Phases 53.3-53.5 |
| Use `PaperTradingModelError` | Match existing model validation and avoid a speculative exception hierarchy | Phase 53.2 |

**Phase 53.1 status:** Planning and documentation are complete. This phase is
`RESEARCH_ONLY`, `OFFLINE_ONLY`, and `PLANNING_AND_DOCS_ONLY`; no production code,
test code, serialization, exporter, CLI, GUI, broker, or live-trading behavior
was changed. Reviewer Gate is required and `MERGE_GATE: HOLD`.

### 12.8 Phase 53.2 Implementation Record

- **New Module**: `src/tw_stock_tool/paper_trading/portfolio_results.py`
- **Result Dataclasses**: Added `SimulatedPortfolioPositionResult`, `SimulatedPortfolioPendingOrderResult`, and `SimulatedPortfolioTradingResult`.
- **Builder Signature**: Implemented `build_simulated_portfolio_trading_result(runtime_state, *, initial_cash, last_prices)`.
- **Valuation Policy**: Exact matching `last_prices` required for open positions; missing prices fail closed. Extra prices ignored. No DataFrame or network lookup.
- **Position Inclusion**: All portfolio positions mapped, including zero-quantity positions with realized PnL. Rejected-only symbols not fabricated.
- **Pending Snapshot**: `(symbol, order_id)` deterministic order. Pending BUY exposes reserved notional, SELL is zero.
- **Trade Log Preservation**: Immutable snapshots of original global collections preserving source object references and chronology.
- **Read-Only Constraints**: Source properties, trade log lists, state variables, and `last_prices` mapping remain strictly unmodified.
- **Shallow Immutability**: Result dataclasses are `frozen=True` and slotted, but preserve underlying mutable event object references (e.g. `SimulatedOrder`, `SimulatedFill`) from the trade log.
- **Tests**: Implemented full `test_paper_trading_portfolio_results.py` covering model constraints, construction rules, validation policies, identity limits, metric counts, and preservation logic.
- **Deferred Scope**: explicitly deferred JSON/Markdown/CSV exporters, multi-symbol CLI flags, GUI, `--max-total-exposure`, and live trading.

### 12.9 Phase 53.2 Reviewer Correction Record

- **Mutable Runtime Re-Validation**: Added explicit `isinstance` checks for mutable `portfolio`, `portfolio.positions`, `portfolio.trade_log`, and its inner collections inside `build_simulated_portfolio_trading_result`.
- **Numeric Overflow Validation**: Implemented private `_require_finite_number` helper to guarantee `float` extraction and catch `math.nan`, `math.inf`, `-math.inf` on inputs.
- **Derived Value Protection**: Re-validated all intermediate derived values (`market_val`, `cost_basis`, `unrealized_pnl`, `total_equity`, `reserved_buy_notional`) to fail closed on float overflows instead of silently propagating `inf`/`nan`.
- **Extended Test Matrix**: Expanded `test_paper_trading_portfolio_results.py` using `subTest` loop coverage for boundary type errors. Added regression tests to artificially induce numeric overflows on all derived metrics.

**Phase 53.1–53.2 status:** Merged via PR #34 (main merge commit `b8d01b34527b50ea8b0248b0f86585a5f5681306`). Phase 53.3 has started.

## 13. Phase 53.3 Aggregate Portfolio Serialization

Phase 53.3 added the `simulated_portfolio_trading_result` schema v1 boundary via `src/tw_stock_tool/paper_trading/portfolio_serialization.py`.

- **Independent Schema**: Schema v1 does not inherit from or widen the single-symbol schema v3. It strictly represents the multi-symbol portfolio results.
- **Symmetric Validation**: Serializer and deserializer enforce symmetric exact-type validation policies.
- **Exact Identifier String Policy**: `symbol`, `order_id`, `side`, `record_id` must be exact non-blank strings (`str` with `strip() != ""`). No `str(...)` coercion.
- **Optional Strategy String Policy**: `strategy` fields accept `None`, `""`, `"   "`, or valid non-empty string.
- **Exact Integer Policy**: Integer fields require exact `int` (rejecting `bool`, `float`, and numeric strings).
- **Finite Float Policy**: Float fields enforce finite numbers, rejecting `NaN`, `Inf`, and numeric overflow (`10**1000`).
- **Tuple Collection Contract**: Dataclass collections must be tuples, serialized to JSON lists, and deserialized as lists.
- **Element Type Revalidation**: Revalidates element types and inner mutable event fields before passing to shared event helpers.
- **Canonical Ordering**: Strictly requires positions to be canonically ordered by `symbol` and pending orders to be canonically ordered by `(symbol, order_id)`.
- **Count Consistency**: Validates `open_position_count`, `order_count`, `fill_count`, `rejection_count`, and `audit_record_count` against collection lengths.
- **Audit Event Fail-Closed Validation**: Pre-validates `SimulatedTradeLogRecord` fields and normalizes native exception leaks to `PaperTradingModelError`.
- **In-Memory Boundary**: Provides pure in-memory dict and JSON string serialization (`export_simulated_portfolio_trading_result_json`, `load_simulated_portfolio_trading_result_json`).
- **Unchanged Single-Symbol Schema**: Single-symbol schemas v1/v2/v3 remain unchanged.
- **Deferred Scope**: Filesystem operations, package-root exports, exporters, CLI, GUI, and Phase 53.4 are not started.

**Phase 53.3 status:** implementation complete, awaiting Reviewer Gate. `MERGE_GATE: HOLD`. Phase 53.4 not started.
