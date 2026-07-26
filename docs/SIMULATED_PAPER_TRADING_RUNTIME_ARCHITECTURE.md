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

**Phase 53.3 status:** Merged via PR #35 (main merge commit `907a38d907d760a66d05bbeeaeb0ec0d63bb11de`). PHASE_53_3_REVIEWER_GATE: PASS.

## 14. Phase 53.4A Aggregate Portfolio Artifact and Exporter Planning

### 14.1 Baseline and LLM Wiki Check

Phase 53.4A planning was conducted from repository `Mike87117/tw_stock_tool` on branch `phase-53-4a-portfolio-artifact-planning` at `main` merge commit `907a38d907d760a66d05bbeeaeb0ec0d63bb11de`.

- **LLM Wiki Check**:
  - `health` endpoint: unavailable (`<urlopen error timed out>`)
  - `projects` endpoint: unavailable
  - `current project search` endpoint: unavailable
  - **Decision**: Repository source code, tests, and documentation are authoritative. LLM Wiki is unavailable and does not expand or replace repository evidence.

### 14.2 Report-Data Contract

Phase 53.4B will introduce a pure report-data module:
`src/tw_stock_tool/paper_trading/portfolio_report_data.py` (planned, not created in 53.4A).

Functions to be defined:
- `build_simulated_portfolio_trading_summary(result)`
- `build_simulated_portfolio_position_rows(result)`
- `build_simulated_portfolio_pending_order_rows(result)`
- `build_simulated_portfolio_order_rows(result)`
- `build_simulated_portfolio_fill_rows(result)`
- `build_simulated_portfolio_rejection_rows(result)`
- `build_simulated_portfolio_trade_log_rows(result)`
- `build_simulated_portfolio_trading_report_data(result)`

`build_simulated_portfolio_trading_report_data(result)` exact top-level keys:
```python
{
    "summary": ...,
    "position_rows": ...,
    "pending_order_rows": ...,
    "order_rows": ...,
    "fill_rows": ...,
    "rejection_rows": ...,
    "trade_log_rows": ...,
}
```

#### Summary Keys
- `initial_cash`
- `final_cash`
- `total_market_value`
- `total_equity`
- `realized_pnl`
- `unrealized_pnl`
- `total_return`
- `total_return_pct`
- `open_position_count`
- `pending_order_count` (`len(result.pending_orders)` as a presentation derived value)
- `order_count`
- `fill_count`
- `rejection_count`
- `audit_record_count`

All metrics except `pending_order_count` directly reflect `SimulatedPortfolioTradingResult` fields without recomputing portfolio valuation.

#### Position Row Keys
- `symbol`
- `quantity`
- `average_cost`
- `last_price`
- `market_value`
- `realized_pnl`
- `unrealized_pnl`

Preserves canonical symbol order from `result.positions`. Closed positions (`quantity == 0`) are retained.

#### Pending Order Row Keys
- `order_id`
- `symbol`
- `side`
- `quantity`
- `signal_time`
- `created_at`
- `strategy`
- `reference_price`
- `reserved_buy_notional`

Preserves canonical `(symbol, order_id)` order from `result.pending_orders`. Pending BUY displays reservation; pending SELL exposes `0.0`.

#### Orders, Fills, Rejections, and Trade Log Rows
- **Order rows**: `order_id`, `symbol`, `side`, `quantity`, `signal_time`, `created_at`, `strategy`
- **Fill rows**: `order_id`, `symbol`, `side`, `quantity`, `price`, `filled_at`, `fee`, `tax`, `slippage`, `gross_amount`, `net_cash_effect`
- **Rejection rows**: `order_id`, `symbol`, `side`, `quantity`, `signal_time`, `created_at`, `strategy`, `reasons` (`" | ".join(rejection.reasons)`)
- **Trade-log rows**: `sequence`, `record_id`, `event_type`, `status`, `order_id`, `symbol`, `side`, `quantity`, `signal_time`, `order_created_at`, `expected_execution_model`, `fill_time`, `fill_price`, `fee`, `tax`, `slippage`, `strategy_name`, `strategy_metadata`, `risk_allowed`, `risk_rejection_reasons`, `guard_metadata`, `error_code`, `error_message`. Output row order exactly matches `result.audit_log` order to preserve the global chronological audit order (`sequence` is an output field and verifiable data item, not an exporter sorting instruction; the builder must not sort by `sequence`, symbol, order ID, or event type).

### 14.3 Mutation and Responsibility Policy

- Builders perform pure read-only transformations.
- No mutation of `SimulatedPortfolioTradingResult`, tuple collections, or inner mutable event objects.
- No recomputation of domain valuations or PnL.
- No network access, coordinator calls, strategy/backtest execution, or simulated trading runs.
- No pending order creation, filling, cancellation, or clearing.
- Schema v1 contract remains unchanged.
- Presentation formatting is never written back into domain models.

### 14.4 Markdown Contract

Phase 53.4B will introduce:
`src/tw_stock_tool/paper_trading/portfolio_exporters.py` (planned, not created in 53.4A).

Function: `export_simulated_portfolio_trading_markdown(result)`

Title and section headers in exact order:
```markdown
# Simulated Portfolio Trading Report

## Summary
## Positions
## Pending Orders
## Orders
## Fills
## Rejected Simulated Order Intents
## Trade Log
```

Empty-section messages:
- `*No positions to display.*`
- `*No pending orders to display.*`
- `*No orders to display.*`
- `*No fills to display.*`
- `*No rejected simulated order intents.*`
- `*No audit events to display.*`

Formatting policy:
- `None` renders as empty string `""`.
- Floating point values render formatted with thousands separators and 2 decimal places (`:,.2f`).
- `total_return_pct` renders as percentage (`{value * 100:,.2f}%`).
- Table cell pipe characters `|` are escaped to `\|`.
- Line breaks (CRLF, CR, LF) in cell text are converted to `<br>`.
- Timestamps render using stable string representation without re-parsing.
- Dictionary metadata uses deterministic JSON: `json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)`.

### 14.5 CSV Bundle Contract

Function: `export_simulated_portfolio_trading_csv_bundle(result)`

Exact 7 bundle keys:
- `"summary"`
- `"positions"`
- `"pending_orders"`
- `"orders"`
- `"fills"`
- `"rejections"`
- `"trade_log"`

Empty datasets still emit headers.

CSV filenames:
- `<basename>_summary.csv`
- `<basename>_positions.csv`
- `<basename>_pending_orders.csv`
- `<basename>_orders.csv`
- `<basename>_fills.csv`
- `<basename>_rejections.csv`
- `<basename>_trade_log.csv`

Default basename: `simulated_portfolio_trading`

CSV formatting policy:
- Standard Python `csv.writer` with `lineterminator="\n"`.
- `None` outputs as empty cell `""`.
- Numeric values output raw unformatted string values (no thousand separator commas).
- Dictionary metadata outputs deterministic JSON string.
- Row order matches report-data collection order (`trade_log` row order exactly matches `result.audit_log`).

### 14.6 Filesystem Boundary & CSV Preflight Policy

Phase 53.4C will introduce:
- `src/tw_stock_tool/paper_trading/portfolio_serialization_files.py` (planned)
- `src/tw_stock_tool/paper_trading/portfolio_export_files.py` (planned)

Functions:
- `export_simulated_portfolio_trading_result_json_file(result, path, *, overwrite=False)`
- `load_simulated_portfolio_trading_result_json_file(path)`
- `export_simulated_portfolio_trading_markdown_file(result, path, *, overwrite=False)`
- `export_simulated_portfolio_trading_csv_files(result, output_dir, *, basename="simulated_portfolio_trading", overwrite=False)`

#### Encoding and Schema Reuse
- JSON, Markdown, and CSV text files strictly use UTF-8 encoding.
- `export_simulated_portfolio_trading_result_json_file(...)` must call the existing `export_simulated_portfolio_trading_result_json(...)`.
- `load_simulated_portfolio_trading_result_json_file(...)` must call the existing `load_simulated_portfolio_trading_result_json(...)`.
- File helpers must NOT duplicate, fork, or re-implement schema v1 validation.
- File helpers are solely responsible for path resolution, encoding, read/write execution, and overwrite boundary enforcement.

#### CSV Preflight Limitations
- All 7 target paths (`<basename>_summary.csv`, `<basename>_positions.csv`, `<basename>_pending_orders.csv`, `<basename>_orders.csv`, `<basename>_fills.csv`, `<basename>_rejections.csv`, `<basename>_trade_log.csv`) must be resolved prior to any write operation.
- When `overwrite=False`, if any single target file already exists, the function must fail with `FileExistsError` immediately before creating or writing any output files (preflight check prevents partial bundle creation).
- This guarantee covers preflight existence checking only.
- The 7-file output does NOT provide full transactional atomicity; mid-write disk space exhaustion, permission changes, filesystem failures, or OS I/O errors may still result in partial writes.
- This phase does NOT introduce temporary-file transaction staging, rollback mechanisms, or database transactions.

#### Exact Basename Policy
- `basename` must be an exact `str` instance (`type(basename) is str`); it must reject `Path`, `bytes`, integers, or `str` subclasses with `ValueError` (no implicit type coercion or subclass tolerance).
- `basename` must not be an empty string `""` or contain whitespace only `"   "`.
- `basename` must not be `.` or `..`.
- `basename` must not contain forward slash `/` or backslash `\`.
- `basename` must not alter or escape the caller-specified output directory.
- If any basename rule is violated, the helper fails closed immediately with `ValueError` without creating or writing any files.

### 14.7 Offline Artifact CLI Boundary

Phase 53.4C will introduce:
`src/tw_stock_tool/cli/simulated_portfolio_artifact_cli.py` (planned)

Unified CLI command:
`twstock simulated-portfolio-artifact`

Subcommands:
- `validate INPUT_JSON`
- `inspect INPUT_JSON`
- `export-markdown INPUT_JSON --output-markdown PATH [--overwrite]`
- `export-csv INPUT_JSON --output-csv-dir DIRECTORY [--basename NAME] [--overwrite]`

#### Prohibited Behaviors & Offline Non-Goals
The `simulated-portfolio-artifact` CLI:
- Operates strictly on existing schema v1 JSON artifacts.
- Does NOT download market data.
- Does NOT run analysis.
- Does NOT execute strategies.
- Does NOT run backtests.
- Does NOT execute simulated trading.
- Does NOT run the multi-symbol coordinator.
- Does NOT create, accept, fill, reject, cancel, or clear orders.
- Does NOT call the Risk Manager.
- Does NOT call the Kill Switch.
- Does NOT connect to brokers.
- Does NOT perform real order placement.
- Does NOT generate live signals.
- Does NOT provide investment advice.
- Does NOT recommend stocks.
- Does NOT guarantee returns.

### 14.8 Error Policy

- Domain, schema, artifact content, and contract violation errors raise `PaperTradingModelError` (e.g. unsupported schema version, wrong result type, missing/extra schema fields, invalid domain values, malformed valid-UTF-8 JSON artifact content, serializer/deserializer contract violations).
- Malformed UTF-8 file reads raise `UnicodeDecodeError` (filesystem decoding errors are NOT wrapped in `PaperTradingModelError`).
- Basename validation failures raise `ValueError` (NOT wrapped in `PaperTradingModelError`).
- Filesystem I/O preserves `FileNotFoundError`, `FileExistsError`, `IsADirectoryError`, `PermissionError`, and `UnicodeDecodeError`.
- CLI outputs error messages to `sys.stderr` and returns a non-zero exit code. `FileExistsError` suggests using `--overwrite`.

### 14.9 Implementation Phase Split

- **Phase 53.4A**: Planning & docs lock (current phase).
- **Phase 53.4B**: Pure report-data and string exporters (`portfolio_report_data.py`, `portfolio_exporters.py`, unit tests). No filesystem, CLI, or package exports.
- **Phase 53.4C**: Filesystem operations and offline artifact CLI (`portfolio_serialization_files.py`, `portfolio_export_files.py`, `simulated_portfolio_artifact_cli.py`, unified CLI routing, unit tests). No multi-symbol historical trading execution.
- **Phase 53.5**: Multi-symbol historical execution CLI orchestration.
- **Phase 53.6**: Portfolio-wide user-facing risk enforcement (`--max-total-exposure`).

### 14.10 Package Export Policy

- `tw_stock_tool.paper_trading.__init__` is NOT modified in Phase 53.4A or 53.4B.
- Package-root exports remain unchanged; callers import directly from specific modules until an independent public package API review.

### 14.11 Compatibility Guarantees

Preserves single-symbol models, builders, schemas v1/v2/v3, single-symbol Markdown/CSV exporters, file helpers, CLIs, coordinator, stepper, risk manager, kill switch, guard adapter, GUI, backtest/daily report artifacts, package version, `twstock` commands, and broker interface state.

### 14.12 Planned Test Matrix

#### Phase 53.4B Report-Data Tests (`test_paper_trading_portfolio_report_data.py`)
- cash-only empty portfolio
- one open position
- multiple positions
- mixed open and closed positions
- pending BUY
- pending SELL
- multiple pending orders
- orders
- fills
- rejections
- audit events
- exact report-data top-level keys
- exact summary keys
- exact row keys
- canonical position order preservation (sorted by `symbol`)
- canonical pending-order order preservation (sorted by `(symbol, order_id)`)
- global audit chronology preservation: output row order exactly matches `result.audit_log` order; the report-data builder must not sort by `sequence`, symbol, order ID, event type, or any other field
- derived `pending_order_count`
- invalid result input type fails closed (`PaperTradingModelError`)
- no source tuple mutation
- no inner event-object mutation
- no source reordering

#### Phase 53.4B Markdown Exporter Tests (`test_paper_trading_portfolio_exporters.py`)
- exact title (`# Simulated Portfolio Trading Report`)
- exact section order (Summary, Positions, Pending Orders, Orders, Fills, Rejected Simulated Order Intents, Trade Log)
- exact summary labels
- exact empty-section messages (`*No positions to display.*`, `*No pending orders to display.*`, `*No orders to display.*`, `*No fills to display.*`, `*No rejected simulated order intents.*`, `*No audit events to display.*`)
- `None` renders as empty string `""`
- general float `:,.2f` formatting
- `total_return_pct` percentage formatting (`{value * 100:,.2f}%`)
- pipe escaping (`|` -> `\|`)
- CRLF conversion (`\r\n` -> `<br>`)
- CR conversion (`\r` -> `<br>`)
- LF conversion (`\n` -> `<br>`)
- deterministic metadata JSON (`json.dumps(..., ensure_ascii=False, sort_keys=True, allow_nan=False)`)
- timestamp stable string rendering
- trailing newline
- Unicode content
- no source mutation

#### Phase 53.4B CSV Bundle Exporter Tests (`test_paper_trading_portfolio_exporters.py`)
- exact seven bundle keys (`summary`, `positions`, `pending_orders`, `orders`, `fills`, `rejections`, `trade_log`)
- exact summary header
- exact positions header
- exact pending-orders header
- exact orders header
- exact fills header
- exact rejections header
- exact trade-log header
- empty datasets still emit headers
- deterministic collection row order
- deterministic metadata JSON
- `None` outputs as empty cell `""`
- raw unformatted numeric strings
- `lineterminator="\n"`
- Unicode content
- no source mutation

#### Phase 53.4C Filesystem Tests (`test_paper_trading_portfolio_serialization_files.py` & `test_paper_trading_portfolio_export_files.py`)
- UTF-8 JSON file round trip
- missing JSON file (`FileNotFoundError`)
- directory passed as JSON file (`IsADirectoryError`)
- malformed UTF-8 (`UnicodeDecodeError`)
- invalid schema (`PaperTradingModelError`)
- parent directory creation
- Markdown overwrite default refusal (`FileExistsError`)
- Markdown overwrite opt-in
- Markdown UTF-8 output
- all seven CSV paths
- default basename (`simulated_portfolio_trading`)
- custom basename
- non-string basename (`ValueError`)
- blank basename (`ValueError`)
- `.` basename (`ValueError`)
- `..` basename (`ValueError`)
- forward-slash basename (`ValueError`)
- backslash basename (`ValueError`)
- basename cannot escape output directory (`ValueError`)
- one existing target causes preflight failure (`FileExistsError`)
- preflight failure creates no new files (zero partial files written)
- permission errors (`PermissionError`)
- no claim of transactional atomicity

#### Phase 53.4C CLI Tests (`test_simulated_portfolio_artifact_cli.py`)
- `validate` success
- `validate` invalid schema failure
- `validate` missing-file failure
- `inspect` output and counts
- `export-markdown` success
- `export-markdown` overwrite refusal
- `export-csv` success
- `export-csv` overwrite/preflight refusal
- invalid basename error (`ValueError`)
- filesystem errors write to stderr
- non-zero failure exit code
- unified CLI passthrough (`twstock simulated-portfolio-artifact`)
- clean-subprocess import boundaries
- existing unified commands remain unchanged

- existing unified commands remain unchanged

### 14.13 Explicit Non-Goals

- No production code in 53.4A
- No test code in 53.4A
- No schema v1 changes
- No single-symbol schema changes
- No report-data implementation in 53.4A
- No Markdown exporter implementation in 53.4A
- No CSV exporter implementation in 53.4A
- No filesystem implementation in 53.4A
- No CLI implementation in 53.4A
- No unified CLI routing in 53.4A
- No package exports in 53.4A
- No coordinator changes
- No runtime state changes
- No stepper changes
- No strategy execution
- No market data fetching
- No Risk Manager changes
- No Kill Switch changes
- No `--max-total-exposure` flag
- No GUI
- No database
- No scheduler
- No Broker Interface implementation
- No Shioaji
- No live trading
- No real order placement
- No semi-automatic trading
- No automatic trading
- No investment advice
- No stock recommendations
- No guaranteed returns
- No Phase 53.4B implementation in Phase 53.4A
Phase 53.4A–53.4B merged via PR #36.
Main merge commit: 3be8b67dbd0570c10a8b92c25247353afee5d1bf.
Phase 53.4C merged via PR #37.
Main merge commit: 03181acc7f85a229a687eb538dd6801ad3f7410c.
PHASE_53_4C_REVIEWER_GATE: PASS.
Phase 53.5A–53.5B merged via PR #38.
Main merge commit: 899e6c2b7ff4caf2fe8b347c87e7c8bf97e17d96.
PHASE_53_5A_REVIEWER_GATE: PASS.
PHASE_53_5B_REVIEWER_GATE: PASS.
PR_38_MERGED: YES.
MERGE_GATE: COMPLETE.
Phase 53.6A architecture planning in progress.
PHASE_53_6A_REVIEWER_GATE: PENDING_REVIEW.
PHASE_53_6B_STARTED: NO.
MERGE_GATE: HOLD.


## Phase 53.5A Architecture & Planning Specification

### 1. Overview and Goal
Phase 53.5A establishes the technical orchestration contract for multi-symbol historical simulated paper trading CLI (`twstock simulated-portfolio-trading`) to be implemented in Phase 53.5B. It bridges market data retrieval, analysis, strategy signal generation, multi-symbol chronological coordination, aggregate result building, and schema v1 JSON artifact generation into a unified workflow.

### 2. Command Interface Contract (`twstock simulated-portfolio-trading`)
- New CLI entrypoint: `twstock simulated-portfolio-trading`.
- Preserves 100% backwards compatibility with single-symbol `twstock simulated-paper-trading`.
- Input parameters:
  - `--stocks` (space-separated list of symbols)
  - `--file` (path to stock list text file)
  - Rules:
    - At least one of `--stocks` or `--file` required.
    - `--stocks` CLI input: explicitly provided empty string (`""`) or whitespace-only items (`"   "`) MUST fail closed (exit code 1) and are not silently dropped before validation.
    - `--file` input: uses `load_stock_ids_from_file(...)` semantics; blank lines and `#` comment lines are ignored.
    - Combined inputs: `--stocks` and `--file` can be combined, deduplicated deterministically based on first-occurrence order.
    - Final list: if final normalized stock symbol list is empty after processing, execution fails closed.
  - Non-goals: `--auto-stock-list`, `--stock-limit`, and `--stock-sample` are explicitly deferred in Phase 53.5B.
- Execution options:
  - `--strategy` (choices: `ma_cross`, `macd`, `rsi`)
  - `--initial-cash` (required finite non-negative float; allows `0`, rejects `bool`, `NaN`, `infinity`, negative values, and non-numeric values; when `initial_cash == 0`, `total_return_pct` remains `None`)
  - `--quantity-per-trade` (positive int, default 1000)
  - `--period` (historical data period, e.g. `1y`, `2y`)
  - `--fee-rate` (non-negative float)
  - `--tax-rate` (non-negative float)
  - `--slippage-per-share` (non-negative float)
  - `--force-refresh` (flag)
  - `--output-json` (required output path string)
  - `--overwrite` (flag, default False)
- Uniform parameters: All stocks in the portfolio share identical strategy, period, trade quantity, fee/tax/slippage rates. No per-symbol overrides in Phase 53.5B.

### 3. Canonical Resolved Symbol Policy
- `analyze_stock(stock_id=...)` returns `StockAnalysis` containing `stock_id` (input ID) and `symbol` (canonical resolved symbol, e.g. `2330.TW`, `8069.TWO`).
- Rules:
  1. User input list is used ONLY for data retrieval and error messages.
  2. After calling `analyze_stock(stock_id=...)`, `analysis.symbol` MUST be used as the canonical portfolio symbol.
  3. All downstream mappings MUST use `analysis.symbol` as key: `dataframes`, `last_prices`, `coordinator` symbols, runtime `positions`, pending `orders`, aggregate artifact `symbols`.
  4. Raw input `stock_id` MUST NOT be used as coordinator key.
  5. Resolved symbol MUST be a non-blank string and MUST be unique across all portfolio symbols.
  6. If two different input stock IDs resolve to the same canonical symbol (e.g. `2330` and `2330.TW` both resolving to `2330.TW`), the entire execution MUST fail closed immediately (no silent dictionary overwrite). Error message includes conflicting input stock IDs and resolved canonical symbol.

### 4. Orchestration Layering
- Facade (`src/tw_stock_tool/paper_trading/portfolio_engine.py`):
  Pure, reusable module facade function:
  `run_simulated_portfolio_trading_result(dataframes, *, initial_cash, last_prices, quantity_per_trade=1000, fee_rate=0.0, tax_rate=0.0, slippage_per_share=0.0, guard_decision=None, guard_decision_provider=None, strategy=None, strategy_metadata=None) -> SimulatedPortfolioTradingResult`
  - Responsibilities: Input validation, shared `SimulatedPortfolio` & `SimulatedPaperTradingRuntimeState` instantiation, `run_chronological_multi_symbol_simulated_paper_trading` delegation, `build_simulated_portfolio_trading_result` construction.
  - Prohibitions: No I/O, no network fetching, no CLI parsing, no file exports, no recommendations, no coordinator/schema modifications.
- CLI Adapter (`src/tw_stock_tool/cli/simulated_portfolio_trading_cli.py`):
  Handles symbol collection, `analyze_stock(...)` data fetching, strategy signal generation using canonical resolved symbols, `Mapping[str, pandas.DataFrame]` construction using canonical symbols, final close `last_prices` extraction using canonical symbols, facade invocation, `export_simulated_portfolio_trading_result_json_file(...)` artifact output, `load_simulated_portfolio_trading_result_json_file(...)` read-back validation, and terminal summary output via `build_simulated_portfolio_trading_summary(read_back_result)`.

### 5. Fail-Closed Error Policy & Artifact Atomicity Boundary
- Entire portfolio fails immediately (exit code 1) if any single stock encounters:
  - Market data fetch error or network error
  - `analyze_stock` failure
  - Strategy signal generation error
  - Empty strategy DataFrame
  - Missing `Open` or `Close` column
  - Missing `entry_signal` or `exit_signal` column
  - Non-unique or non-monotonic index
  - Non-numeric, boolean, NaN, infinite, or <=0 final close price
- Pre-write failure contract: All data fetching, analysis, strategy signal generation, DataFrame validation, canonical resolved symbol checks, facade execution, and result building MUST succeed before artifact file writing is initiated. On pre-write failure, no artifact file is created or written.
- Filesystem atomicity contract: JSON filesystem helpers do NOT provide transactional atomicity. Mid-write filesystem failures or post-write read-back failures may leave partial/empty files on disk. Phase 53.5B does NOT claim transactional rollback, atomic replace, or ACID guarantees.

### 6. Artifact Output & Separation of Concerns
- `simulated-portfolio-trading`: Executes multi-symbol historical simulation -> outputs JSON artifact (`--output-json`).
- `simulated-portfolio-artifact`: Reads existing JSON artifact -> `validate`, `inspect`, `export-markdown`, `export-csv`.

### 7. Deterministic Execution and Terminal Summary Boundary
- Preserves chronological timeline, deterministic symbol ordering, pending fill prioritization before new order evaluation, shared cash/portfolio/trade_log.
- `build_simulated_portfolio_trading_summary(read_back_result)` is the SINGLE presentation boundary for terminal summary output.
- Execution CLI reads back written artifact and passes `read_back_result` to `build_simulated_portfolio_trading_summary(...)`. Execution CLI does NOT recompute domain metrics.
- Terminal summary displays 14 domain summary metrics (Initial Cash, Final Cash, Total Market Value, Total Equity, Realized PnL, Unrealized PnL, Total Return, Total Return Pct raw float, Open Position Count, Pending Order Count, Order Count, Fill Count, Rejection Count, Audit Record Count) plus Output JSON Path (printed separately).

### 8. Phase 53.5B File Scope & Test Strategy
- Planned files: `portfolio_engine.py`, `simulated_portfolio_trading_cli.py`, `twstock_cli.py` (routing), and corresponding test files.
- Test categories: Portfolio Engine Facade (16 tests planned), CLI Input & Symbol Collection (25 tests planned), CLI Execution & Fail-Closed Semantics (19 tests planned), Integration & CLI Compatibility (9 tests planned).

### 9. Non-Goals and Phase 53.6 Deferred Scope
- Non-goals: No Broker Interface, Shioaji, live trading, real orders, automatic trading, investment advice, recommendations, scheduler, database, GUI, Excel exporter, schema v1 changes, per-symb## Phase 53.6A Portfolio Risk Flags Architecture Specification

### 1. Architectural Overview & Planned Dataflow
Phase 53.6A defines the architecture for four CLI portfolio risk management flags to be implemented in Phase 53.6B for multi-symbol historical simulated trading (`twstock simulated-portfolio-trading`).

```text
Multi-symbol CLI flags
    ↓
Facade strictly-positive validation
    ↓
Existing SimulatedPaperTradingRiskConfig
    ↓
MultiSymbolDataFrameReferencePriceProvider (NEW)
    ↓
Existing ChronologicalRuntimePortfolioExposureProvider
    ↓
Existing build_guard_decision_provider_from_config
    ↓
Facade-local composite provider (evaluates all sources)
    ↓
Existing coordinator and stepper unchanged
    ↓
Existing rejection and audit pipeline
```

- **Existing Architectural Components**:
  - Coordinator lexical symbol ordering
  - Pending fills processing before candidate order evaluation
  - `SimulatedPaperTradingRuntimeState.pending_orders` & `total_reserved_buy_notional`
  - `SimulatedPendingOrderState.reference_price` & `reserved_buy_notional`
  - Existing `SimulatedPaperTradingRiskConfig` & `SimulatedPaperTradingGuardConfig`
  - Existing `build_guard_decision_provider_from_config(...)`
  - Existing `ChronologicalRuntimePortfolioExposureProvider`
  - Rejection models & `portfolio.trade_log` audit trail
  - Schema v1 JSON artifact structures
- **Planned Phase 53.6B Components**:
  - `MultiSymbolDataFrameReferencePriceProvider` in `src/tw_stock_tool/simulated_paper_trading_guard/providers.py`
  - Multi-symbol CLI risk flags parsing, facade parameter wiring, and strictly-positive domain validation
  - Facade-local composite provider orchestration (evaluating fixed decision, risk limits, and custom provider)

### 2. Command & Feature Boundary Contract
- Target Command: `twstock simulated-portfolio-trading` (and pure Python facade `run_simulated_portfolio_trading_result`).
- Single-symbol CLI (`twstock simulated-paper-trading`) remains 100% UNTOUCHED.
- Four optional risk flags:
  - `--max-order-notional`: Maximum notional value permitted for a single candidate order.
  - `--max-position-quantity`: Maximum share quantity permitted for a single stock position.
  - `--max-position-notional`: Maximum notional value permitted for a single stock position.
  - `--max-total-exposure`: Maximum aggregate notional exposure permitted across all portfolio stock positions and active pending BUY reservations.
- All flags are research-only simulated safeguards. They do not connect to brokers, do not place real orders, do not provide investment advice, and do not guarantee risk mitigation or returns.
- When omitted (`None`), Phase 53.5B multi-symbol trading behavior is 100% preserved.

### 3. Per-Flag Numeric Types & Validation Contract
- `--max-order-notional`:
  - CLI: `type=float` (strictly positive finite float).
  - Domain: `None` or strictly positive finite `Real` (`int`, `float`). `None` disables cap. Rejects `0`, negative values (`< 0`), `bool`, `numpy.bool_`, numeric strings at domain boundary (e.g. `"100000"`), `NaN`, `+inf`, and `-inf`.
- `--max-position-quantity`:
  - CLI: `type=int` (strictly positive integer).
  - Domain: `None` or exact strictly positive `int` (`type(value) is int`). `None` disables cap. Rejects `0`, negative integers, `bool`, `numpy.bool_`, floats (including exact float `1000.0` or fractional floats), and numeric strings at domain boundary (e.g. `"100"`).
- `--max-position-notional`:
  - CLI: `type=float` (strictly positive finite float).
  - Domain: `None` or strictly positive finite `Real` (`int`, `float`). Same rejection rules as `--max-order-notional`.
- `--max-total-exposure`:
  - CLI: `type=float` (strictly positive finite float).
  - Domain: `None` or strictly positive finite `Real` (`int`, `float`). Same rejection rules as `--max-order-notional`.
- Strictly-Positive Contract: Setting any limit to `0` or `0.0` is an invalid configuration (fails closed). `None` means disabled.

### 4. Exposure-Increasing Order Policy & SELL Bypass
- The paper trading runtime is long-only (`SimulatedPortfolio`).
- `BUY` orders increase portfolio exposure and position sizes: MUST undergo risk limit evaluation.
- `SELL` / exit orders decrease portfolio exposure and position sizes: Portfolio risk caps (`max_order_notional`, `max_position_quantity`, `max_position_notional`, `max_total_exposure`) BYPASS `SELL` orders (returning an allow decision for the portfolio-risk source) so users can always exit existing long positions without being blocked by risk caps.
- Caller-supplied `fixed_guard` decision or custom `guard_decision_provider` do NOT automatically bypass `SELL` orders; they evaluate `SELL` orders according to their own semantics.

### 5. Reference Price & As-Of DataFrame Pricing Architecture
- **Candidate Reference Price Provider**: Phase 53.6B is planned to introduce `MultiSymbolDataFrameReferencePriceProvider` in `src/tw_stock_tool/simulated_paper_trading_guard/providers.py`.
  - Accepts `dataframes: Mapping[str, pandas.DataFrame]` and `price_column: str = "Open"`.
  - Uses `order.symbol` and `order.signal_time` for exact DataFrame index lookup.
  - Does not read order metadata price, future rows, next-bar Open fill price, or simulation end `last_prices`.
  - Fails closed if symbol is missing, signal-time row is missing, or Open price is missing, non-finite, or non-positive.
  - Preserves existing single-symbol `DataFrameReferencePriceProvider`.
- **Portfolio Exposure Provider**: Directly reuses existing `ChronologicalRuntimePortfolioExposureProvider(dataframes, runtime_state, price_column="Open")`.
  - Valuates each open long position (`quantity > 0`) using the latest row at or before `order.signal_time` (as-of lookup).
  - If current global timestamp has no bar for a symbol, uses the nearest earlier observable Open.
  - Never reads future rows or ending `last_prices`.
  - Fails closed if missing positive position DataFrame, no row at or before signal time, or invalid price.
- **No Look-Ahead Bias & Zero Mutation**: No coordinator or stepper price-state observer/mutation required. Public callback signature remains `(order, portfolio) -> SimulatedPaperTradingGuardDecision`.

### 6. Quantity and Notional Formulas
- `candidate_reference_price = MultiSymbolDataFrameReferencePriceProvider(order, portfolio)`.
- `candidate_order_notional = order.quantity * candidate_reference_price` (BUY only).
- `current_position_quantity(symbol) = portfolio.position_for(symbol).quantity`.
- `projected_position_quantity = current_position_quantity(symbol) + candidate_order.quantity`.
- `filled_positions_exposure = sum(pos.quantity * latest DataFrame Open at or before order.signal_time for pos in portfolio.positions.values() if pos.quantity > 0)`.
- `pending_buy_reservation = runtime_state.total_reserved_buy_notional` (summing `SimulatedPendingOrderState.reserved_buy_notional`).
- `current_total_exposure = filled_positions_exposure + pending_buy_reservation`.
- `projected_total_exposure = current_total_exposure + candidate_order_notional` (for BUY).
- Policy: Cash is not exposure; SELL pending reservations are not exposure; rejected orders are not exposure; candidate BUY order is not double-counted by exposure provider; pending BUY reservation is released when filled, skipped, or failed; fees/taxes/slippage are excluded from notional caps; long-only non-negative values.

### 7. Pending Order Exposure Reservation Semantics
- In chronological multi-symbol evaluation, candidate BUY orders created on Bar $N$ become `pending_orders` awaiting Bar $N+1$ Open fills.
- Pending BUY orders ARE included in `runtime_state.total_reserved_buy_notional` when evaluating subsequent candidate orders on the same or subsequent bars until filled, rejected, or skipped.
- Evaluation order within the same timestamp is strictly lexicographical by canonical symbol key (`"2317.TW" < "2330.TW"`).
- Once a pending order fills or is rejected/skipped, its reservation is cleanly resolved via portfolio position state or removed from pending state.

### 8. Enforcement Layer & Guard Reuse Architecture
- Phase 53.6B is planned to reuse existing risk & guard infrastructure:
  - `SimulatedPaperTradingRiskConfig`
  - `SimulatedPaperTradingGuardConfig`
  - `build_guard_decision_provider_from_config`
  - `SimulatedPaperTradingGuardAdapter`
  - `MultiSymbolDataFrameReferencePriceProvider` (NEW)
  - `ChronologicalRuntimePortfolioExposureProvider`
- Flow: Four CLI flags -> `SimulatedPaperTradingRiskConfig` -> `SimulatedPaperTradingGuardConfig` -> `MultiSymbolDataFrameReferencePriceProvider` & `ChronologicalRuntimePortfolioExposureProvider` -> `build_guard_decision_provider_from_config(...)` -> risk `guard_decision_provider`.

### 9. Guard Composition & Evaluation Policy
- Facade Composition Contract:
  - **No risk limits enabled**: 100% Phase 53.5B behavior and caller mutual exclusion preserved. No composite provider created.
  - **Risk limits enabled**: Facade validates caller mutual exclusion, then builds a facade-local composite provider (`composite_provider`), passing `guard_decision=None` and `guard_decision_provider=composite_provider` to coordinator. Valid combinations:
    - Risk only: evaluates `[portfolio_risk_source]`
    - Fixed decision + Risk: evaluates `[fixed_guard_decision, portfolio_risk_source]`
    - Risk + Custom provider: evaluates `[portfolio_risk_source, caller_custom_provider]`
    (Fixed decision + Risk + Custom provider remains invalid).
- **Evaluation Policy: Evaluate All**: All configured sources in the composite provider are evaluated without short-circuiting.
- **Reason Composition**: Combine denial reasons in source evaluation order, apply global stable deduplication (keep first occurrence), set `is_allowed = False` if any source blocks.
- **Metadata Composition**: Namespaced under `fixed_guard`, `portfolio_risk_guard`, `custom_guard`.
- **Exception Policy**: Internal risk provider errors and custom provider exceptions fail execution closed (record execution error, abort simulation, fail entire execution). If an earlier source blocked but a later source raises an exception, the exception takes precedence and the entire execution fails closed.

### 10. Canonical Existing Rejection Reasons
- Reuses existing canonical reason strings from core risk rules:
  - `order_notional exceeds max_order_notional`
  - `projected_position_quantity exceeds max_position_quantity`
  - `projected_position_notional exceeds max_position_notional`
  - `projected_total_exposure exceeds max_total_exposure`
- CLI does not rewrite reasons; composite provider performs source-level deduplication without modifying canonical rule output strings.
- Rejections record standard `SimulatedOrderRejection` events into `portfolio.trade_log`, updating `rejection_count`, `rejections`, and `audit_log`.

### 11. Deterministic Same-Timestamp Execution
- Same-timestamp evaluation order is deterministic by canonical symbol key (`"2317.TW" < "2330.TW"`).
- Shared limit deductions are deterministic. Input dictionary order does not alter outcome. Repeat runs produce identical results.

### 12. Failure Boundary Classification
- **Configuration / Parser Failure**: Non-positive limit (0, negative), NaN, infinity, string at facade -> Pre-execution fail closed (`ret=1`, stderr `error: ...`, no output file).
- **Risk Limit Exceeded**: Normal simulated trading rejection (`risk_rejected`), trading continues for remaining bars/symbols, final artifact JSON generated cleanly.
- **Internal Provider Error**: Unhandled exception fails closed to prevent hidden corrupt state.

### 13. Schema and Artifact Compatibility
- `SERIALIZATION_SCHEMA_CHANGED: NO`
- The existing result, rejection, audit, and schema structures appear sufficient. Phase 53.6B is planned to preserve them without a schema version change, subject to implementation and offline artifact compatibility verification.

### 14. Backward Compatibility Guarantees
- When flags are omitted (`None`), Phase 53.5B behavior is 100% unchanged.
- Single-symbol CLI, existing facade callers, and existing custom guard decision providers remain fully compatible.

### 15. Planned File Scope & Test Matrix for Phase 53.6B
- **Required Production Files**:
  - `src/tw_stock_tool/cli/simulated_portfolio_trading_cli.py`
  - `src/tw_stock_tool/paper_trading/portfolio_engine.py`
  - `src/tw_stock_tool/simulated_paper_trading_guard/providers.py`
- **Required Test Files**:
  - `tests/test_simulated_portfolio_trading_cli.py`
  - `tests/test_paper_trading_portfolio_engine.py`
  - `tests/test_simulated_paper_trading_guard_providers.py`
- **Optional Documentation Files**:
  - `docs/DEVELOPMENT_ROADMAP.md`
  - `docs/SIMULATED_PAPER_TRADING_RUNTIME_ARCHITECTURE.md`
  - `docs/user-guide/cli.md`
- **Explicitly Forbidden Production Files**:
  - `src/tw_stock_tool/paper_trading/coordinator.py`
  - `src/tw_stock_tool/paper_trading/stepper.py`
  - `src/tw_stock_tool/paper_trading/runtime.py`
  - `src/tw_stock_tool/paper_trading/models.py`
  - `src/tw_stock_tool/paper_trading/portfolio_results.py`
  - `src/tw_stock_tool/risk/config.py`
  - `src/tw_stock_tool/risk/rules.py`
  - `src/tw_stock_tool/risk/models.py`
  - `src/tw_stock_tool/risk/builder.py`
  - `src/tw_stock_tool/simulated_paper_trading_guard/adapter.py`
  - `src/tw_stock_tool/simulated_paper_trading_guard/builder.py`
  - `src/tw_stock_tool/simulated_paper_trading_guard/config.py`
  - `portfolio_risk_guard.py` (NEW)
  - serialization schema files
  - generic output writers
  - single-symbol CLI files
- **Planned Test Matrix**:
  - Multi-Symbol Reference Provider: exact candidate symbol lookup, exact signal-time Open lookup, different DataFrames per symbol, missing symbol/row/Open fail-closed, invalid Open (bool/string/NaN/inf/zero/negative) fail-closed, does not read order metadata price, does not mutate inputs, preserves single-symbol `DataFrameReferencePriceProvider`.
  - As-Of Exposure Integration: position with bar at candidate timestamp, position without bar at candidate timestamp uses nearest earlier Open, no-signal intermediate bar available via DataFrame as-of lookup, later/future row never used, no row at or before signal time fails closed, final `last_prices` not used, multiple positions sum deterministically, pending BUY reservation included, pending SELL reservation excluded, candidate BUY not double-counted, mismatched symbol calendars, runtime portfolio identity mismatch fails closed.
  - Validation: notional/exposure flags (omitted accepted, positive int/float accepted, zero/negative/bool/string/NaN/inf rejected), position quantity (omitted accepted, positive exact int accepted, zero/negative/bool/numpy.bool_/1000.0/fractional float/string rejected).
  - Risk Behavior: below limit allowed, exactly equal allowed, above limit rejected, all 4 existing canonical reason strings preserved, BUY total exposure adds candidate notional once, pending reservation competes across same-timestamp candidates, lexicographical symbol ordering deterministic, SELL bypasses portfolio risk caps (large SELL not rejected by max-order-notional), SELL does not bypass fixed guard or custom provider.
  - Guard Composition & Exceptions: risk only, fixed allow/block + risk allow/block, risk allow/block + custom allow/block, fixed and custom together remain invalid, evaluate-all behavior, deterministic reason ordering, stable deduplication, metadata namespacing, risk/custom provider exception fails execution, later exception overrides earlier block.
  - Compatibility & Integration: CLI help smoke, all four flags routed, successful artifact JSON export, offline artifact CLI compatibility, no schema version change, single-symbol CLI unaffected, full suite regression.
