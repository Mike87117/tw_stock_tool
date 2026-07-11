# Public API and Compatibility Wrapper Inventory

## A. Executive summary

The repository root is intentionally cluttered: it preserves historical script and import paths while the packaged implementation lives under `src/tw_stock_tool/`. Root scripts must not be treated as dead merely because package code has no internal caller. `pyproject.toml` exposes `twstock` as the supported console command, while README examples and wrapper tests retain many compatibility paths. The genuinely duplicated area is the alternate class-based `backtest/engine.py` path versus the active/canonical DataFrame-oriented `backtesting/` path; their models and execution semantics differ. Deletion is unsafe until a replacement, documented migration window, and smoke coverage exist. **Phase A2 decision:** choose and document distinct purposes first; do not delete or move paths.

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

All 19 unified command forms are dispatched by `src/tw_stock_tool/cli/twstock_cli.py`: doctor, scan, daily, stock-list update, stock-list smoke-check, stock-list clean, price-smoke-check, ai-scan, cache, benchmark, analyze, strategy-compare, parameter-sweep, backtest-report, walk-forward, simulated-paper-trading, simulated-paper-trading-export, backtest-artifact, and backtest-result-export (the stock-list group contains three forms).

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
| `backtest` | alternate class-based engine; package `__init__.py` exports nothing | dedicated class-path tests only | INVESTIGATE; high |
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
| `backtesting/` | README report workflows and report tests call active/canonical DataFrame-oriented runtime and artifact path | established report outputs, timing, costs, and legacy dict normalization; external usage unknown |
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

**Initial grouped counts were superseded by the row-level count table below. Highest risks are root import wrappers, report/artifact filenames, v1/v2/v3 simulation JSON compatibility, and divergent backtest semantics.

## D.1 Per-file root-wrapper evidence (supersedes grouped table)

Each row is one root-level file (41 rows). None found and Unknown mean this inventory did not find repository evidence, not that a surface is unused.

| File | Surface type | Canonical target | Import behavior | Executable behavior | README/documentation reference | Test evidence | Current classification | External-usage uncertainty | Compatibility risk | Proposed canonical replacement | Earliest safe action |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `ai_prediction_report.py` | import re-export + executable CLI wrapper | `tw_stock_tool.reports.ai_prediction_report` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.reports.ai_prediction_report` | Retain through documented compatibility window |
| `ai_stock_scanner.py` | import re-export + executable CLI wrapper | `tw_stock_tool.ml.ai_stock_scanner` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.ml.ai_stock_scanner` | Retain through documented compatibility window |
| `ai_walk_forward.py` | import re-export + executable CLI wrapper | `tw_stock_tool.ml.ai_walk_forward` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.ml.ai_walk_forward` | Retain through documented compatibility window |
| `analysis.py` | import re-export wrapper | `tw_stock_tool.analysis.analysis` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.analysis.analysis` | Retain through documented compatibility window |
| `app_services.py` | import re-export wrapper | `tw_stock_tool.gui.app_services` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.gui.app_services` | Retain through documented compatibility window |
| `backtest.py` | import re-export wrapper | `tw_stock_tool.backtesting.backtest` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.backtesting.backtest` | Retain through documented compatibility window |
| `backtest_report.py` | executable CLI wrapper | `tw_stock_tool.cli.backtest_report` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.cli.backtest_report` | Retain through documented compatibility window |
| `baseline_ml_model.py` | import re-export wrapper | `tw_stock_tool.ml.baseline_ml_model` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.ml.baseline_ml_model` | Retain through documented compatibility window |
| `benchmark.py` | import re-export + executable CLI wrapper | `tw_stock_tool.cli.benchmark` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.cli.benchmark` | Retain through documented compatibility window |
| `cache_manager.py` | import re-export wrapper | `tw_stock_tool.data.cache_manager` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.data.cache_manager` | Retain through documented compatibility window |
| `cache_utils.py` | import re-export wrapper | `tw_stock_tool.data.cache_utils` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.data.cache_utils` | Retain through documented compatibility window |
| `clean_stocks.py` | import re-export + executable CLI wrapper | `tw_stock_tool.cli.clean_stocks` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.cli.clean_stocks` | Retain through documented compatibility window |
| `config.py` | import re-export wrapper | `tw_stock_tool.utils.config` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.utils.config` | Retain through documented compatibility window |
| `console_lock.py` | import re-export wrapper | `tw_stock_tool.utils.console_lock` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.utils.console_lock` | Retain through documented compatibility window |
| `daily_report.py` | import re-export + executable CLI wrapper | `tw_stock_tool.reports.daily_report` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.reports.daily_report` | Retain through documented compatibility window |
| `daily_watchlist.py` | import re-export + executable CLI wrapper | `tw_stock_tool.cli.daily_watchlist` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.cli.daily_watchlist` | Retain through documented compatibility window |
| `data_loader.py` | import re-export wrapper | `tw_stock_tool.data.data_loader` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.data.data_loader` | Retain through documented compatibility window |
| `doctor.py` | import re-export + executable CLI wrapper | `tw_stock_tool.utils.doctor` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.utils.doctor` | Retain through documented compatibility window |
| `gui_app.py` | import re-export + executable CLI wrapper | `tw_stock_tool.gui.gui_app` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.gui.gui_app` | Retain through documented compatibility window |
| `gui_result_formatter.py` | import re-export wrapper | `tw_stock_tool.gui.gui_result_formatter` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.gui.gui_result_formatter` | Retain through documented compatibility window |
| `gui_tasks.py` | import re-export wrapper | `tw_stock_tool.gui.gui_tasks` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.gui.gui_tasks` | Retain through documented compatibility window |
| `indicators.py` | import re-export wrapper | `tw_stock_tool.analysis.indicators` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.analysis.indicators` | Retain through documented compatibility window |
| `main.py` | import re-export + executable CLI wrapper | `tw_stock_tool.cli.main` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.cli.main` | Retain through documented compatibility window |
| `ml_dataset.py` | import re-export + executable CLI wrapper | `tw_stock_tool.ml.ml_dataset` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.ml.ml_dataset` | Retain through documented compatibility window |
| `parameter_sweep.py` | import re-export + executable CLI wrapper | `tw_stock_tool.cli.parameter_sweep_report` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.cli.parameter_sweep_report` | Retain through documented compatibility window |
| `parameter_sweep_report.py` | executable CLI wrapper | `tw_stock_tool.cli.parameter_sweep_report` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.cli.parameter_sweep_report` | Retain through documented compatibility window |
| `plotter.py` | import re-export wrapper | `tw_stock_tool.reports.plotter` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.reports.plotter` | Retain through documented compatibility window |
| `price_data_smoke_check.py` | import re-export + executable CLI wrapper | `tw_stock_tool.cli.price_data_smoke_check` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.cli.price_data_smoke_check` | Retain through documented compatibility window |
| `report.py` | import re-export wrapper | `tw_stock_tool.reports.report` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.reports.report` | Retain through documented compatibility window |
| `scan_stocks.py` | import re-export + executable CLI wrapper | `tw_stock_tool.cli.scan_stocks` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.cli.scan_stocks` | Retain through documented compatibility window |
| `scanner.py` | import re-export wrapper | `tw_stock_tool.analysis.scanner` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.analysis.scanner` | Retain through documented compatibility window |
| `signals.py` | import re-export wrapper | `tw_stock_tool.analysis.signals` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.analysis.signals` | Retain through documented compatibility window |
| `stock_list_smoke_check.py` | import re-export + executable CLI wrapper | `tw_stock_tool.cli.stock_list_smoke_check` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.cli.stock_list_smoke_check` | Retain through documented compatibility window |
| `stock_list_updater.py` | import re-export + executable CLI wrapper | `tw_stock_tool.data.stock_list_updater` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.data.stock_list_updater` | Retain through documented compatibility window |
| `stock_selection.py` | import re-export wrapper | `tw_stock_tool.analysis.stock_selection` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.analysis.stock_selection` | Retain through documented compatibility window |
| `strategies.py` | import re-export wrapper | `tw_stock_tool.backtesting.strategies` | Replaces module in `sys.modules` where shown | Not applicable | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.backtesting.strategies` | Retain through documented compatibility window |
| `strategy_compare.py` | import re-export + executable CLI wrapper | `tw_stock_tool.backtesting.strategy_compare` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.backtesting.strategy_compare` | Retain through documented compatibility window |
| `twstock_cli.py` | import re-export + executable CLI wrapper | `tw_stock_tool.cli.twstock_cli` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.cli.twstock_cli` | Retain through documented compatibility window |
| `verify_batch.py` | import re-export + executable CLI wrapper | `tw_stock_tool.utils.verify_batch` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.utils.verify_batch` | Retain through documented compatibility window |
| `walk_forward.py` | import re-export + executable CLI wrapper | `tw_stock_tool.cli.walk_forward_report` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.cli.walk_forward_report` | Retain through documented compatibility window |
| `walk_forward_report.py` | executable CLI wrapper | `tw_stock_tool.cli.walk_forward_report` | Replaces module in `sys.modules` where shown | Calls target main() | None found | Wrapper source; targeted test unknown | COMPATIBILITY_ONLY | Unknown external imports/scripts | High | `tw_stock_tool.cli.walk_forward_report` | Retain through documented compatibility window |

acktest.py re-exports 	w_stock_tool.backtesting.backtest; strategies.py re-exports 	w_stock_tool.backtesting.strategies. Neither is evidence for 	w_stock_tool.backtest.engine or strategies.base.

## E.1 Symbol-level package export evidence (supersedes grouped table)

One row represents an explicit symbol set exported by the package initializer, or an explicit empty initializer; it does not treat tests as a public-contract declaration.

| Package | Symbol or explicit export group | Definition module | Re-exported by package __init__ | In __all__ | Root compatibility re-export | README evidence | Test evidence | Application caller evidence | Classification | Migration risk |
|---|---|---|---|---|---|---|---|---|---|---|
| analysis | No package exports | Not applicable | No | No | nalysis.py, indicators.py, scanner.py, signals.py, stock_selection.py target submodules | README analysis commands | analysis/scanner tests | CLI scanner/main | INTERNAL | Medium |
| backtesting | No package exports; active DataFrame-oriented modules | acktest, esults, strategies, report modules | No | No | acktest.py, strategies.py, report wrappers | README backtest/report commands | 	est_backtesting*, report tests | CLI reports/strategy compare | SUPPORTED_PUBLIC_API | High |
| backtest | No package exports; alternate class-based path under investigation | acktest.engine, class result/model modules | No | No | None found | None found | dedicated class-path tests | None found | INVESTIGATE | High |
| strategies | No package exports; ase.py supports alternate class path | strategies.base | No | No | None; root strategies.py targets acktesting.strategies | None found | dedicated class strategy tests | None found | INVESTIGATE | High |
| reports | No package exports | report/plotter modules | No | No | eport.py, plotter.py, daily_report.py, i_prediction_report.py | README report filenames | report tests | CLI and GUI services | SUPPORTED_PUBLIC_API | High |
| paper_trading | 22 named simulation models, runners, builders, exporters, serializers, converter | models, engine, esults, exporters, serialization*, acktest_converter | Yes | Yes | None found | README import examples | 	est_paper_trading_* | simulation CLI/coordinator | SUPPORTED_PUBLIC_API | High |
| risk | 14 named decision/model/rule symbols | models, ules | Yes | Yes | None found | None found | 	est_risk_* | guard adapter | SUPPORTED_PUBLIC_API | Medium |
| kill_switch | 6 named state/decision/evaluator symbols | models, decisions | Yes | Yes | None found | None found | package tests | guard adapter | SUPPORTED_PUBLIC_API | Medium |
| simulated_paper_trading_guard | 9 named decisions, adapter types, evaluators, workflows | models, dapter, evaluator, workflow | Yes | Yes | None found | README simulation boundary | 	est_simulated_paper_trading_guard* | simulation workflow | SUPPORTED_PUBLIC_API | High |
| scanners | No package exports | scanner submodules | No | No | None found | README scanner commands | scanner tests | CLI scanner | INTERNAL | Medium |
| ml | No package exports | ML submodules | No | No | ML root wrappers | README ML commands | ML tests | AI CLI | UNKNOWN_EXTERNAL_USAGE | Medium |
| ui | 4 read-only UI boundary constants/function | ead_only_boundary | Yes | Yes | GUI root wrappers target gui, not ui | GUI scope docs | UI/package tests | GUI boundary | SUPPORTED_PUBLIC_API | Medium |
| utils | No package exports; nested utils.output exports output helpers | utils modules / utils.output | No at top level | No at top level | config/doctor/cache wrappers | README diagnostics | utility tests | CLI/GUI | INTERNAL | Medium |

## F.1 One-row-per-command CLI compatibility evidence

| Unified command | Router key / dispatch | Canonical module | Direct module form | Root wrapper | Legacy alias | Important defaults | Output behavior | Help/parser test evidence | Classification | Risk |
|---|---|---|---|---|---|---|---|---|---|---|
| 	wstock doctor | doctor | utils.doctor | py -m tw_stock_tool.utils.doctor | doctor.py | None found | environment checks | console | 	est_doctor.py | SUPPORTED_CLI | Medium |
| 	wstock scan | scan | cli.scan_stocks | py -m tw_stock_tool.cli.scan_stocks | scan_stocks.py | None found | output dir | ranking files | 	est_scan_stocks.py | SUPPORTED_CLI | High |
| 	wstock daily | daily | cli.daily_report_cli | py -m tw_stock_tool.cli.daily_report_cli | daily_report.py | None found | output/ | daily_report.md/.xlsx | daily CLI tests | SUPPORTED_CLI | High |
| 	wstock stock-list update | nested update | data.stock_list_updater | py -m tw_stock_tool.data.stock_list_updater | stock_list_updater.py | None found | stocks.txt | user path | smoke tests | SUPPORTED_CLI | Medium |
| 	wstock stock-list smoke-check | nested smoke-check | cli.stock_list_smoke_check | py -m tw_stock_tool.cli.stock_list_smoke_check | stock_list_smoke_check.py | None found | console | console | smoke tests | SUPPORTED_CLI | Medium |
| 	wstock stock-list clean | nested clean | cli.clean_stocks | py -m tw_stock_tool.cli.clean_stocks | clean_stocks.py | None found | output/ | clean report/xlsx/txt | clean CLI tests | SUPPORTED_CLI | Medium |
| 	wstock price-smoke-check | price-smoke-check | cli.price_data_smoke_check | py -m tw_stock_tool.cli.price_data_smoke_check | price_data_smoke_check.py | None found | console | console | smoke tests | SUPPORTED_CLI | Medium |
| 	wstock ai-scan | i-scan | ml.ai_stock_scanner | py -m tw_stock_tool.ml.ai_stock_scanner | i_stock_scanner.py | None found | user output | XLSX/user path | AI scanner tests | SUPPORTED_CLI | Medium |
| 	wstock cache | cache | data.cache_manager | py -m tw_stock_tool.data.cache_manager | cache_manager.py | None found | cache dir | cache files | cache tests | SUPPORTED_CLI | Medium |
| 	wstock benchmark | enchmark | cli.benchmark | py -m tw_stock_tool.cli.benchmark | enchmark.py | None found | output/benchmark | _summary/_detail/_errors.csv | benchmark tests | SUPPORTED_CLI | Medium |
| 	wstock analyze | nalyze | cli.main | py -m tw_stock_tool.cli.main | main.py | None found | output/ | report/chart | 	est_main.py | SUPPORTED_CLI | High |
| 	wstock strategy-compare | strategy-compare | acktesting.strategy_compare | py -m tw_stock_tool.backtesting.strategy_compare | strategy_compare.py | --output | output Excel | *_strategy_compare.xlsx | strategy compare tests | SUPPORTED_CLI | High |
| 	wstock parameter-sweep | parameter-sweep | cli.parameter_sweep_report | py -m tw_stock_tool.cli.parameter_sweep_report | parameter_sweep_report.py | None found | output/ | parameter_sweep_report.md/.xlsx | report CLI tests | SUPPORTED_CLI | High |
| 	wstock backtest-report | acktest-report | cli.backtest_report | py -m tw_stock_tool.cli.backtest_report | acktest_report.py | None found | output/ | acktest_report.md/.xlsx | report CLI tests | SUPPORTED_CLI | High |
| 	wstock walk-forward | walk-forward | cli.walk_forward_report | py -m tw_stock_tool.cli.walk_forward_report | walk_forward_report.py | None found | output/ | walk_forward_report.md/.xlsx | report CLI tests | SUPPORTED_CLI | High |
| 	wstock simulated-paper-trading | simulated-paper-trading | cli.simulated_paper_trading_cli | py -m tw_stock_tool.cli.simulated_paper_trading_cli | simulated_paper_trading_cli.py | None found | research-only | artifact/user path | simulation CLI tests | SUPPORTED_CLI | High |
| 	wstock simulated-paper-trading-export | simulated-paper-trading-export | cli.simulated_paper_trading_export_cli | py -m tw_stock_tool.cli.simulated_paper_trading_export_cli | simulated_paper_trading_export_cli.py | None found | user output | MD/CSV files | export CLI tests | SUPPORTED_CLI | High |
| 	wstock backtest-artifact | acktest-artifact | cli.backtest_artifact_cli | py -m tw_stock_tool.cli.backtest_artifact_cli | None found | None found | explicit input/output | JSON artifact | 	est_backtest_artifact_cli.py | SUPPORTED_CLI | High |
| 	wstock backtest-result-export | acktest-result-export | cli.backtest_result_export_cli | py -m tw_stock_tool.cli.backtest_result_export_cli | None found | None found | required --output-json | JSON artifact | export CLI tests | SUPPORTED_CLI | High |

## G.1 Detailed artifact and schema evidence

| Artifact family | Writer / reader | Write / read versions | Stable fields or groups / strictness | Defaults / keys / sheets | Tests | Risk |
|---|---|---|---|---|---|---|
| BacktestResult JSON | artifact export / artifact reader | current structured schema; unsupported versions rejected | schema version, result identity, trades/metrics; strict validation | explicit --output-json | 	est_backtest_artifact_cli.py, serialization tests | High |
| Simulated paper JSON | serialization* / serialization* | write v3; read v1/v2/v3 | summary, orders, fills, rejections; v3 udit_log; unknown fields rejected | user JSON path | 	est_paper_trading_serialization.py, 	est_paper_trading_trade_log.py | High |
| Simulated Markdown | markdown exporter / Not applicable | Not applicable | additive report sections | user path | exporter/file tests | High |
| Simulated CSV bundle | CSV exporter / Not applicable | Not applicable | stable row groups | summary, orders, ills, ejections, 	rade_log; matching filenames | exporter/file tests | High |
| Backtest report MD/XLSX | report exporters / Not applicable | Not applicable | report result compatibility | output/backtest_report.md/.xlsx | report CLI tests | High |
| Parameter sweep MD/XLSX | report exporters / Not applicable | Not applicable | report result compatibility | output/parameter_sweep_report.md/.xlsx | sweep report tests | High |
| Walk-forward MD/XLSX | report exporters / Not applicable | Not applicable | report result compatibility | output/walk_forward_report.md/.xlsx | walk-forward tests | High |
| Daily report/watchlist | daily CLI/exporters / Not applicable | Not applicable | report rows and errors | output/daily_report.*, daily_watchlist.* | daily tests | High |
| Benchmark CSV | cli.benchmark / Not applicable | Not applicable | summary/detail/error rows | enchmark_summary.csv, enchmark_detail.csv, enchmark_errors.csv | benchmark tests | Medium |

## K.1 Corrected row-based counts

Counting unit: a root table row/file, CLI table row/command form, package table row/export group, or artifact table row. The units are not combined.

| Measure | Corrected count |
|---|---:|
| Root-level files represented by individual rows | 41 |
| Unified command forms / SUPPORTED_CLI rows | 19 |
| Package export rows | 13 |
| Artifact rows | 9 |
| SUPPORTED_PUBLIC_API package/export rows | 6 |
| COMPATIBILITY_ONLY root-file rows | 41 |
| UNKNOWN_EXTERNAL_USAGE package/export rows | 1 |
| INVESTIGATE package/export rows | 2 |
| DEPRECATION_CANDIDATE rows | 0 |
| REMOVE_CANDIDATE rows | 0 |

Tests prove maintained behavior; they do not alone establish a supported external contract. Accordingly, the alternate class-based acktest/engine.py path and strategies/base.py are INVESTIGATE, while active/canonical DataFrame-oriented acktesting/ remains the runtime/artifact path. Phase A2 is not started by this documentation correction.