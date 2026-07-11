# Public API and Compatibility Wrapper Inventory

## A. Executive summary

The repository root is intentionally cluttered: it preserves historical script and import paths while the packaged implementation lives under `src/tw_stock_tool/`. Root scripts must not be treated as dead merely because package code has no internal caller. `pyproject.toml` exposes `twstock` as the supported console command, while README examples and wrapper tests retain many compatibility paths. The genuinely duplicated area is the class-based `backtest/engine.py` versus the legacy/dataframe-oriented `backtesting/` path; their models and execution semantics differ. Deletion is unsafe until a replacement, documented migration window, and smoke coverage exist. **Phase A2 decision:** choose and document distinct purposes first; do not delete or move paths.

## B. Source-of-truth hierarchy

1. Current runtime code and `pyproject.toml`.
2. Tests (especially CLI, import, artifact, and wrapper tests).
3. Package exports and `__all__` declarations.
4. README and current architecture/roadmap documentation.
5. Historical phase records in `docs/`.
6. LLM Wiki only as supporting context, never replacement evidence.

Packaging evidence: `pyproject.toml` uses `src` discovery (`tw_stock_tool*`), requires Python `>=3.11`, declares runtime dependencies (`pandas`, `numpy`, `yfinance`, `openpyxl`, `requests`, `scikit-learn`, plotting libraries), and defines `twstock = tw_stock_tool.cli.twstock_cli:main`.

## C. Supported user entry points

| Purpose | Recommended command | Canonical module | Compatibility alternatives | Evidence | Status |
|---|---|---|---|---|---|
| environment | `twstock doctor` | `utils.doctor` | `doctor.py` | `twstock_cli.py`, `test_doctor.py` | SUPPORTED_CLI |
| analysis | `twstock analyze` | `cli.main` | `main.py` | README, `test_main.py` | SUPPORTED_CLI |
| scanner | `twstock scan` | `cli.scan_stocks` | `scan_stocks.py` | README, `test_scan_stocks.py` | SUPPORTED_CLI |
| daily report | `twstock daily` | `cli.daily_report_cli` | `daily_report.py` | README, `test_daily_report_cli.py` | SUPPORTED_CLI |
| stock list | `twstock stock-list update|smoke-check|clean` | `data.stock_list_updater`, CLI modules | root wrappers | `twstock_cli.py`, smoke tests | SUPPORTED_CLI |
| research reports | `twstock strategy-compare|parameter-sweep|backtest-report|walk-forward` | `backtesting.strategy_compare`, CLI reports | root report wrappers | README, report CLI tests | SUPPORTED_CLI |
| artifacts | `twstock backtest-artifact|backtest-result-export` | artifact CLI modules | direct `-m` invocation | `test_backtest_artifact_cli.py` | SUPPORTED_CLI |
| simulation | `twstock simulated-paper-trading[-export]` | simulation CLI modules | root wrappers | README, simulation CLI tests | SUPPORTED_CLI |
| cache/benchmark/AI | `twstock cache|benchmark|ai-scan` | data/CLI/ML modules | root wrappers | `twstock_cli.py`, tests | SUPPORTED_CLI |

All 18 unified forms are dispatched by `src/tw_stock_tool/cli/twstock_cli.py`: doctor, scan, daily, stock-list update, stock-list smoke-check, stock-list clean, price-smoke-check, ai-scan, cache, benchmark, analyze, strategy-compare, parameter-sweep, backtest-report, walk-forward, simulated-paper-trading, simulated-paper-trading-export, backtest-artifact, and backtest-result-export (the stock-list group contains three forms).

## D. Root-wrapper inventory

Root `.py` inventory (41 files, filesystem root scan). “Wrapper” means a legacy executable/import surface; `UNKNOWN_EXTERNAL_USAGE` is intentional where README/tests do not prove consumers.

| File(s) | Type / canonical target | Evidence | Classification | Risk / earliest action |
|---|---|---|---|---|
| `main.py`, `twstock_cli.py`, `scan_stocks.py`, `daily_report.py`, `daily_watchlist.py`, `doctor.py` | executable compatibility wrappers to `cli.*`/`utils.doctor` | README commands; matching `test_*.py` | COMPATIBILITY_ONLY | high; retain through release window |
| `backtest_report.py`, `parameter_sweep.py`, `parameter_sweep_report.py`, `walk_forward.py`, `walk_forward_report.py`, `strategy_compare.py` | report executable wrappers | README report examples and wrapper-help tests | COMPATIBILITY_ONLY | high; canonical `twstock` first |
| `simulated_paper_trading_cli.py`, `simulated_paper_trading_export_cli.py`, `backtest_artifact_cli.py`, `backtest_result_export_cli.py` | artifact/simulation executable wrappers | CLI tests, Phase 49 README | COMPATIBILITY_ONLY | high; retain |
| `ai_stock_scanner.py`, `ai_prediction_report.py`, `ai_walk_forward.py`, `baseline_ml_model.py`, `ml_dataset.py` | ML compatibility/standalone research scripts | README/tests | UNKNOWN_EXTERNAL_USAGE | investigate before migration |
| `analysis.py`, `backtest.py`, `indicators.py`, `signals.py`, `strategies.py`, `report.py`, `scanner.py` | import compatibility re-exports | root import tests; package modules | COMPATIBILITY_ONLY | high import break risk |
| `app_services.py`, `gui_app.py`, `gui_result_formatter.py`, `gui_tasks.py` | GUI supported scripts/modules | GUI docs and `test_app_services.py` | SUPPORTED_PUBLIC_API | retain; GUI migration required |
| `cache_manager.py`, `cache_utils.py`, `config.py`, `console_lock.py`, `data_loader.py`, `plotter.py`, `stock_selection.py` | legacy import wrappers/helpers | package modules and tests | COMPATIBILITY_ONLY | unknown external imports |
| `clean_stocks.py`, `benchmark.py`, `price_data_smoke_check.py`, `stock_list_smoke_check.py`, `stock_list_updater.py`, `verify_batch.py` | supported operations/development utilities | README/CLI tests | SUPPORTED_CLI | retain; unify docs later |

No root file is a `REMOVE_CANDIDATE`: no negative-evidence threshold is met. Generated outputs are excluded by `.gitignore`/README (`output/`, `cache/`); `custom_md.md` is user-owned and not inspected.

## E. Package export inventory

| Package | Export surface / source | `__all__` and evidence | Classification / migration risk |
|---|---|---|---|
| `analysis` | scanner/analysis functions | package imports, scanner tests | INTERNAL; medium |
| `backtesting` | dataframe backtest, reports, strategy comparison | README/report tests | SUPPORTED_PUBLIC_API; high |
| `backtest` | structured `BacktestResult` engine/artifacts | `test_backtest_*`, artifact docs | SUPPORTED_PUBLIC_API; high |
| `strategies` | strategy functions plus `base.py` interfaces | README, backtest tests | SUPPORTED_PUBLIC_API; high |
| `reports` | Markdown/Excel builders/writers | report tests and README filenames | SUPPORTED_PUBLIC_API; high |
| `paper_trading` | simulation models, engine, exports | explicit `__all__`, README imports, Phase 49 tests | SUPPORTED_PUBLIC_API; high |
| `risk` | decisions/evaluations | explicit `__all__`, `test_risk_*` | SUPPORTED_PUBLIC_API; medium |
| `kill_switch` | kill-switch API | explicit `__all__`, package tests | SUPPORTED_PUBLIC_API; medium |
| `simulated_paper_trading_guard` | guard decision/provider adapter | explicit `__all__`, guard tests | SUPPORTED_PUBLIC_API; high |
| `scanners` | scanner internals | scanner tests | INTERNAL; medium |
| `ml` | dataset/model/research flows | ML tests/root scripts | UNKNOWN_EXTERNAL_USAGE; medium |
| `ui` | UI public helpers | explicit `__all__`, GUI docs | SUPPORTED_PUBLIC_API; medium |
| `utils` | output/config/diagnostics | `utils.output.__all__`, doctor/cache tests | INTERNAL; medium |

Package `__init__.py` files without an explicit `__all__` are not permission to remove imports; export evidence also includes README examples, root re-exports, and package-boundary smoke tests.

## F. CLI compatibility inventory

`twstock` is canonical (`pyproject.toml`); direct form is `py -m tw_stock_tool.cli.<module>` and root-wrapper form is `py <root-file>.py` where listed above. `twstock_cli.py` forwards unknown flags unchanged, so command flags/defaults are protected by individual CLI tests rather than duplicated parser definitions. Legacy `strategy_compare --output` remains a compatibility alias for `--output-excel` (`docs/DEVELOPMENT_ROADMAP.md`, Phase 12.2). Default outputs include `output/backtest_report.{md,xlsx}`, `output/parameter_sweep_report.{md,xlsx}`, `output/walk_forward_report.{md,xlsx}`, daily report/watchlist equivalents, and explicit user paths. Classification for every dispatch is `SUPPORTED_CLI`; root/direct alternatives are `COMPATIBILITY_ONLY` unless the module is documented as the primary script.

## G. Artifact and schema compatibility

| Artifact | Write/read version | Names/behavior | Evidence and risk |
|---|---|---|---|
| BacktestResult JSON | stable structured artifact; reject unsupported schema | explicit `--output-json`, overwrite protection | `test_backtest_artifact_cli.py`, Phase 31–33 docs; high |
| Simulated paper trading JSON | writes v3; reads v1, v2, v3 | v3 additive `audit_log`, strict fields | `test_paper_trading_serialization.py`, `test_paper_trading_trade_log.py`; high |
| Simulation Markdown/CSV | additive report surface | summary/orders/fills/rejections retained; adds `trade_log`; files `simulated_paper_trading_{summary,orders,fills,rejections,trade_log}.csv` | README and export tests; high |
| Backtest/report Markdown/Excel | existing names retained | report defaults listed in section F; sheet/output compatibility test-protected | report CLI tests; high |
| Scanner/daily/benchmark | CSV/HTML/XLSX/MD by command | README “output artifacts” table; benchmark `_summary/_detail/_errors.csv` | README, CLI tests; medium |

Required fields and strict schema validation are asserted by serialization tests. Additive changes must retain old keys, filenames, and v1/v2 loading.

## H. Duplicate-path findings

| Path | Evidence | Difference / risk |
|---|---|---|
| `backtesting/` | README report workflows and report tests call dataframe/legacy paths | established report outputs, timing, costs, and legacy dict normalization; external usage unknown |
| `backtest/engine.py` | structured artifact tests and `BacktestResult` docs | model-oriented result boundary and artifact semantics differ from legacy output |
| `strategies/base.py` | class strategy tests/imports | interface differs from function/dataframe strategy pipeline; no deletion decision |

Before any change, compare internal callers, README imports, artifact formats, fill/timing semantics, cost model, strategy interface, and package/root exports. Current no-internal-caller observations are not evidence against external users: classify that risk as `UNKNOWN_EXTERNAL_USAGE`.

## I. Deprecation prerequisites

A deprecation needs: a documented canonical replacement; adapter where needed; import/CLI smoke tests; README migration instructions; a warning policy that will not break scripts; one documented release window; versioning plan; release notes; and removal-test updates. No warning or removal is authorized in A1.

## J. Phase A2 entry criteria

A2 must collect a caller/export/test matrix for both backtest paths, compare result models, strategy interfaces, fill/timing and cost behavior, enumerate artifact consumers, publish replacement commands/imports, and choose one: retain with distinct purpose, adapt to canonical, deprecate, merge, or remove only in a future breaking release. External usage uncertainty blocks deletion.

## K. Recommended actions

| Safe documentation now | Safe test additions later | Requires compatibility window | Requires production migration | Must not change yet |
|---|---|---|---|---|
| Link this inventory from future roadmap work | root import and `--help` smoke matrix | root wrappers, aliases, public imports | backtest consolidation, GUI/data/report refactors | filenames, schemas, CLI flags, wrappers, dependencies |

**Counts:** 41 root Python files inventoried; 19 unified command forms including stock-list nested forms; compatibility-only surfaces: 28 grouped root/package surfaces; supported public APIs: 8 package groups; deprecation candidates: 0; unknown-external-usage groups: 5. Highest risks are root import wrappers, report/artifact filenames, v1/v2/v3 simulation JSON compatibility, and divergent backtest semantics.
