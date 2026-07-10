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
the following test slice. A second `backtest/engine.py` plus
`strategies/base.py` exposes a protocol/class-based backtest path used by its
own tests but not by current CLI workflows.

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
-> single-symbol engine
-> function-local portfolio
-> function-local pending order
-> next-bar-open fill
-> optional guard provider
-> single-symbol result
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
| Parallel class backtest | `backtest/engine.py`, `strategies/base.py`, `tests/test_backtest_engine.py`, `tests/test_strategy_base.py` | Alternate protocol/class-based engine | Parallel implementation is a removal or consolidation candidate | REMOVE_CANDIDATE | Current application workflows call `backtesting/backtest.py`; alternate engine is referenced by dedicated tests | High until semantics and users are migrated | Separate backtest consolidation phase | No |
| Parameter sweep | `backtesting/parameter_sweep.py`: parameter-set loop and ranking | Evaluate and rank in-sample parameter combinations | Errors remain distinguishable; equal-metric ordering lacks an explicit secondary key | REFACTOR_LATER | Stable sort preserves grid order but the tie-break contract is implicit | Medium | Parameter-sweep determinism phase | No |
| Walk forward | `backtesting/walk_forward.py`: `split_windows`, `_evaluate_window_strategy`, `run_walk_forward` | Train selection then test evaluation | Train/test boundaries avoid selecting on test results | KEEP | Non-overlapping slices within each window; best parameters chosen from train metric before test call | High if changed | Existing behavior | No |
| CLI orchestration | `cli/main.py`, `cli/backtest_report.py`, `cli/parameter_sweep_report.py`, `cli/walk_forward_report.py`, `cli/daily_report_cli.py` | Parse, orchestrate, print, and export | Argument and parameter dictionary assembly is duplicated | REFACTOR_LATER | Similar strategy/backtest parameter plumbing appears in multiple CLI modules | High because CLI compatibility is tested | Future CLI maintenance phase | No |
| Paper models | `paper_trading/models.py`, `tests/test_paper_trading_models.py` | Orders, fills, positions, portfolio, log | Multi-position portfolio is suitable for shared runtime state | KEEP | `positions` is keyed by symbol and fill application is centralized | High | Existing behavior | No |
| Runtime state boundary | `paper_trading/engine.py`: local `portfolio` and `pending_order`; planned `paper_trading/runtime.py` | Hold mutable execution state | State is hidden inside one full-history function and cannot represent per-symbol reservations | REFACTOR_NOW | Concrete testability and runtime-semantics blocker for later chronological coordination | Low when added without integration | Phase 48.10 | Yes, new model only |
| Paper engine loop | `paper_trading/engine.py`: `_evaluate_order_intent`, `run_simulated_paper_trading` | Validation, order decisions, pending state, fills, guard calls | Loop handles too many execution responsibilities for a future coordinator | REFACTOR_LATER | Portfolio and pending state are local; fill errors are swallowed and invalid opens are skipped | High | Phase 48.11 | No |
| Fill outcomes | `paper_trading/engine.py`, `models.py`, engine/model tests | Apply fills and retain accepted/rejected intents | Invalid-price skips and failed fills are not separately represented in results | REFACTOR_LATER | `pass` clears pending order without a fill or failure record | High because artifacts have stable schemas | Phase 48.11 or later explicit outcome phase | No |
| Chronological coordination | Paper engine and CLI call graph | None | No global multi-symbol timeline or same-time ordering exists | DEFER | Each engine invocation consumes one DataFrame end-to-end | High | Phase 48.12 | No |
| Paper result | `paper_trading/results.py`, `tests/test_paper_trading_results.py` symbol/index review | Immutable single-symbol summary and row builders | Correct for current engine; cannot represent aggregate portfolio outcome | DEFER | Result stores one `symbol`, one position quantity, and one last price | High due schema compatibility | Phase 48.13 | No |
| Serialization/export | `paper_trading/serialization.py`, `exporters.py`, file helpers and corresponding tests | Stable JSON and Markdown/CSV artifacts | Correctly isolated but coupled to single-symbol result schema | DEFER | Serializer schema and exporters accept `SimulatedPaperTradingResult` | High | Phase 48.14 | No |
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
2. `yagni:` consolidate the alternate class-based backtest engine and base
   strategy if it has no external consumers; keep the active
   `backtesting/backtest.py` path. [`src/tw_stock_tool/backtest/engine.py`,
   `src/tw_stock_tool/strategies/base.py`]
3. `shrink:` centralize duplicated CLI strategy/backtest argument-to-dictionary
   plumbing only when a CLI phase already touches those modules. [`src/tw_stock_tool/cli/`]
4. `shrink:` separate provider/cache orchestration in the data loader only when
   changing fallback policy. [`src/tw_stock_tool/data/data_loader.py`]

Estimated removable surface after explicit deprecation and migration work:
`net: -180 lines, -0 deps possible.` No deletion is approved in Phase 48.10.

## 8. Approved Phase Sequence

```text
Phase 48.10 - Runtime state and pending BUY reservation model boundary
Phase 48.11 - Single-symbol bar stepper refactor
Phase 48.12 - Chronological multi-symbol coordinator
Phase 48.13 - Aggregate portfolio result boundary
Phase 48.14 - Aggregate serialization and export
Phase 48.15 - Historical multi-symbol CLI planning
Phase 48.16 - CLI total-exposure integration
```

Only **Phase 48.10** is approved for implementation now. Later phases are a
sequence, not implicit authorization.

### Proposed Phase 48.11 scope and acceptance criteria

Phase 48.11 should change the smallest set needed to step one symbol by one bar
using an injected `SimulatedPaperTradingRuntimeState`. It should preserve the
current public full-history functions as compatibility wrappers, next-bar-open
timing, guard behavior, costs, and existing result behavior. It should add no
coordinator, aggregate result, CLI flag, or public package export. Exact changed
files require separate approval.

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
- Commit SHA: to be recorded after the audit-only commit

### Phase 48.10 implementation

This subsection must be updated after implementation with:

- exact changed files
- implemented model contracts and validation
- targeted, model-regression, runtime-regression, and full-suite counts
- known limitations and deferred issues
- append-only commit SHAs

Current known limitations are intentional: no engine integration, bar stepper,
chronological coordinator, aggregate result, aggregate serialization/export,
multi-symbol CLI, `--max-total-exposure`, portfolio-wide user-facing
enforcement, broker interface, live data, or live order capability exists.
