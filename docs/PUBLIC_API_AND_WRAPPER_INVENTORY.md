# Public API and Compatibility Wrapper Inventory

## A. Executive summary

The repository root preserves historical script and import paths while packaged implementation lives under `src/tw_stock_tool/`. Root wrappers cannot be treated as dead merely because internal callers are absent: README examples, tests, and external scripts may rely on them. `pyproject.toml` declares the canonical `twstock` console script. The active/canonical DataFrame-oriented `backtesting/` path is the sole packaged backtest path. Root wrappers target canonical package and CLI modules and remain compatibility surfaces.

## B. Source-of-truth hierarchy

1. Current runtime code and `pyproject.toml`.
2. Tests, particularly CLI, import, artifact, and wrapper tests.
3. Package exports and `__all__` declarations.
4. README and current documentation.
5. Historical phase records.
6. LLM Wiki only as supporting context.

Packaging evidence: `pyproject.toml` uses `src` discovery, supports Python `>=3.11`, and defines `twstock = tw_stock_tool.cli.twstock_cli:main`.

## C. Supported user entry points

The router in `src/tw_stock_tool/cli/twstock_cli.py` defines 19 command forms: doctor, scan, daily, stock-list update, stock-list smoke-check, stock-list clean, price-smoke-check, ai-scan, cache, benchmark, analyze, strategy-compare, parameter-sweep, backtest-report, walk-forward, simulated-paper-trading, simulated-paper-trading-export, backtest-artifact, and backtest-result-export. Every form is `SUPPORTED_CLI`; compatibility root wrappers are catalogued in section D.

## D. Root-wrapper inventory

Each row is one root-level Python file. `None found` means this audit found no repository evidence; it is not evidence of no external users.

| File | Surface type | Canonical target | Import behavior | Executable behavior | README or documentation reference | Test evidence | Classification | External-usage uncertainty | Compatibility risk | Proposed canonical replacement | Earliest safe action |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ai_prediction_report.py | import re-export and executable wrapper | tw_stock_tool.reports.ai_prediction_report | re-exports target module | calls target main() | None found | test_ai_prediction_report.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.reports.ai_prediction_report | Retain through compatibility window |
| ai_stock_scanner.py | import re-export and executable wrapper | tw_stock_tool.ml.ai_stock_scanner | re-exports target module | calls target main() | None found | test_ai_stock_scanner.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.ml.ai_stock_scanner | Retain through compatibility window |
| ai_walk_forward.py | import re-export and executable wrapper | tw_stock_tool.ml.ai_walk_forward | re-exports target module | calls target main() | None found | test_ai_walk_forward.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.ml.ai_walk_forward | Retain through compatibility window |
| analysis.py | import re-export wrapper | tw_stock_tool.analysis.analysis | re-exports target module | Not applicable | None found | None found | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.analysis.analysis | Retain through compatibility window |
| app_services.py | import re-export wrapper | tw_stock_tool.gui.app_services | re-exports target module | Not applicable | None found | test_app_services.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.gui.app_services | Retain through compatibility window |
| backtest.py | import re-export wrapper | tw_stock_tool.backtesting.backtest | re-exports target module | Not applicable | None found | test_backtest.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.backtesting.backtest | Retain through compatibility window |
| backtest_report.py | executable CLI wrapper | tw_stock_tool.cli.backtest_report | Not applicable | calls target main() | None found | test_backtest_report.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.cli.backtest_report | Retain through compatibility window |
| baseline_ml_model.py | import re-export wrapper | tw_stock_tool.ml.baseline_ml_model | re-exports target module | Not applicable | None found | test_baseline_ml_model.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.ml.baseline_ml_model | Retain through compatibility window |
| benchmark.py | import re-export and executable wrapper | tw_stock_tool.cli.benchmark | re-exports target module | calls target main() | None found | test_benchmark.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.cli.benchmark | Retain through compatibility window |
| cache_manager.py | import re-export wrapper | tw_stock_tool.data.cache_manager | re-exports target module | Not applicable | None found | None found | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.data.cache_manager | Retain through compatibility window |
| cache_utils.py | import re-export wrapper | tw_stock_tool.data.cache_utils | re-exports target module | Not applicable | None found | test_cache_utils.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.data.cache_utils | Retain through compatibility window |
| clean_stocks.py | import re-export and executable wrapper | tw_stock_tool.cli.clean_stocks | re-exports target module | calls target main() | None found | test_clean_stocks.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.cli.clean_stocks | Retain through compatibility window |
| config.py | import re-export wrapper | tw_stock_tool.utils.config | re-exports target module | Not applicable | None found | None found | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.utils.config | Retain through compatibility window |
| console_lock.py | import re-export wrapper | tw_stock_tool.utils.console_lock | re-exports target module | Not applicable | None found | None found | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.utils.console_lock | Retain through compatibility window |
| daily_report.py | import re-export and executable wrapper | tw_stock_tool.reports.daily_report | re-exports target module | calls target main() | None found | test_daily_report.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.reports.daily_report | Retain through compatibility window |
| daily_watchlist.py | import re-export and executable wrapper | tw_stock_tool.cli.daily_watchlist | re-exports target module | calls target main() | None found | test_daily_watchlist.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.cli.daily_watchlist | Retain through compatibility window |
| data_loader.py | import re-export wrapper | tw_stock_tool.data.data_loader | re-exports target module | Not applicable | None found | test_data_loader.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.data.data_loader | Retain through compatibility window |
| doctor.py | import re-export and executable wrapper | tw_stock_tool.utils.doctor | re-exports target module | calls target main() | None found | test_doctor.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.utils.doctor | Retain through compatibility window |
| gui_app.py | import re-export and executable wrapper | tw_stock_tool.gui.gui_app | re-exports target module | calls target main() | None found | test_gui_app.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.gui.gui_app | Retain through compatibility window |
| gui_result_formatter.py | import re-export wrapper | tw_stock_tool.gui.gui_result_formatter | re-exports target module | Not applicable | None found | test_gui_result_formatter.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.gui.gui_result_formatter | Retain through compatibility window |
| gui_tasks.py | import re-export wrapper | tw_stock_tool.gui.gui_tasks | re-exports target module | Not applicable | None found | test_gui_tasks.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.gui.gui_tasks | Retain through compatibility window |
| indicators.py | import re-export wrapper | tw_stock_tool.analysis.indicators | re-exports target module | Not applicable | None found | test_indicators.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.analysis.indicators | Retain through compatibility window |
| main.py | import re-export and executable wrapper | tw_stock_tool.cli.main | re-exports target module | calls target main() | None found | test_main.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.cli.main | Retain through compatibility window |
| ml_dataset.py | import re-export and executable wrapper | tw_stock_tool.ml.ml_dataset | re-exports target module | calls target main() | None found | test_ml_dataset.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.ml.ml_dataset | Retain through compatibility window |
| parameter_sweep.py | import re-export and executable wrapper | tw_stock_tool.backtesting.parameter_sweep (import); tw_stock_tool.cli.parameter_sweep_report (execute) | re-exports target module | calls target main() | None found | test_parameter_sweep.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.backtesting.parameter_sweep (import); tw_stock_tool.cli.parameter_sweep_report (execute) | Retain through compatibility window |
| parameter_sweep_report.py | executable CLI wrapper | tw_stock_tool.cli.parameter_sweep_report | Not applicable | calls target main() | None found | test_parameter_sweep_report.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.cli.parameter_sweep_report | Retain through compatibility window |
| plotter.py | import re-export wrapper | tw_stock_tool.reports.plotter | re-exports target module | Not applicable | None found | None found | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.reports.plotter | Retain through compatibility window |
| price_data_smoke_check.py | import re-export and executable wrapper | tw_stock_tool.cli.price_data_smoke_check | re-exports target module | calls target main() | None found | test_price_data_smoke_check.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.cli.price_data_smoke_check | Retain through compatibility window |
| report.py | import re-export wrapper | tw_stock_tool.reports.report | re-exports target module | Not applicable | None found | test_report.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.reports.report | Retain through compatibility window |
| scan_stocks.py | import re-export and executable wrapper | tw_stock_tool.cli.scan_stocks | re-exports target module | calls target main() | None found | None found | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.cli.scan_stocks | Retain through compatibility window |
| scanner.py | import re-export wrapper | tw_stock_tool.analysis.scanner | re-exports target module | Not applicable | None found | test_scanner.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.analysis.scanner | Retain through compatibility window |
| signals.py | import re-export wrapper | tw_stock_tool.analysis.signals | re-exports target module | Not applicable | None found | test_signals.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.analysis.signals | Retain through compatibility window |
| stock_list_smoke_check.py | import re-export and executable wrapper | tw_stock_tool.cli.stock_list_smoke_check | re-exports target module | calls target main() | None found | test_stock_list_smoke_check.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.cli.stock_list_smoke_check | Retain through compatibility window |
| stock_list_updater.py | import re-export and executable wrapper | tw_stock_tool.data.stock_list_updater | re-exports target module | calls target main() | None found | test_stock_list_updater.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.data.stock_list_updater | Retain through compatibility window |
| stock_selection.py | import re-export wrapper | tw_stock_tool.analysis.stock_selection | re-exports target module | Not applicable | None found | test_stock_selection.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.analysis.stock_selection | Retain through compatibility window |
| strategies.py | import re-export wrapper | tw_stock_tool.backtesting.strategies | re-exports target module | Not applicable | None found | test_strategies.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.backtesting.strategies | Retain through compatibility window |
| strategy_compare.py | import re-export and executable wrapper | tw_stock_tool.backtesting.strategy_compare | re-exports target module | calls target main() | None found | test_strategy_compare.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.backtesting.strategy_compare | Retain through compatibility window |
| twstock_cli.py | import re-export and executable wrapper | tw_stock_tool.cli.twstock_cli | re-exports target module | calls target main() | None found | test_twstock_cli.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.cli.twstock_cli | Retain through compatibility window |
| verify_batch.py | import re-export and executable wrapper | tw_stock_tool.utils.verify_batch | re-exports target module | calls target main() | None found | test_verify_batch.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.utils.verify_batch | Retain through compatibility window |
| walk_forward.py | import re-export and executable wrapper | tw_stock_tool.backtesting.walk_forward (import); tw_stock_tool.cli.walk_forward_report (execute) | re-exports target module | calls target main() | None found | test_walk_forward.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.backtesting.walk_forward (import); tw_stock_tool.cli.walk_forward_report (execute) | Retain through compatibility window |
| walk_forward_report.py | executable CLI wrapper | tw_stock_tool.cli.walk_forward_report | Not applicable | calls target main() | None found | test_walk_forward_report.py | COMPATIBILITY_ONLY | Unknown external use | High | tw_stock_tool.cli.walk_forward_report | Retain through compatibility window |

Root `backtest.py` re-exports `tw_stock_tool.backtesting.backtest`; root `strategies.py` re-exports `tw_stock_tool.backtesting.strategies`.

## E. Package export inventory

A row represents explicit symbols exported from a package initializer, or an explicit statement that the initializer exports nothing. Dedicated tests demonstrate maintained behavior, not necessarily a supported external API.

| Package | Symbol or export group | Definition module | Re-exported by package initializer | In `__all__` | Root compatibility re-export | README evidence | Test evidence | Application caller evidence | Classification | Migration risk |
|---|---|---|---|---|---|---|---|---|---|---|
| analysis | No package exports | analysis submodules | No | No | analysis.py, indicators.py, scanner.py, signals.py, stock_selection.py | analysis commands | analysis/scanner tests | CLI scanner and main | INTERNAL | Medium |
| backtesting | No package exports; active DataFrame-oriented modules | backtest, results, strategies, report modules | No | No | backtest.py, strategies.py, report wrappers | report commands | backtesting and report tests | CLI reports and strategy compare | SUPPORTED_PUBLIC_API | High |
| reports | No package exports | reports modules | No | No | report.py, plotter.py, daily_report.py, ai_prediction_report.py | report filenames | report tests | CLI and GUI services | SUPPORTED_PUBLIC_API | High |
| paper_trading | typed models, runners, builders, exporters, serializers, converter | models, engine, results, exporters, serialization modules | Yes | Yes | None found | README imports | paper trading tests | simulation CLI | SUPPORTED_PUBLIC_API | High |
| risk | RiskDecision, RiskModelError, snapshots, evaluations, rule functions | models and rules | Yes | Yes | None found | None found | risk tests | guard adapter | SUPPORTED_PUBLIC_API | Medium |
| kill_switch | KillSwitchState, KillSwitchDecision, state and evaluation functions | models and decisions | Yes | Yes | None found | None found | package tests | guard adapter | SUPPORTED_PUBLIC_API | Medium |
| simulated_paper_trading_guard | decisions, adapter types, evaluator, workflows | models, adapter, evaluator, workflow | Yes | Yes | None found | simulation boundary docs | guard tests | simulation workflow | SUPPORTED_PUBLIC_API | High |
| scanners | No package exports | scanner submodules | No | No | None found | scanner commands | scanner tests | CLI scanner | INTERNAL | Medium |
| ml | No package exports | ML submodules | No | No | ML root wrappers | ML commands | ML tests | AI CLI | UNKNOWN_EXTERNAL_USAGE | Medium |
| ui | read-only UI constants and is_read_only_surface | read_only_boundary | Yes | Yes | GUI wrappers target gui package | GUI scope docs | UI tests | GUI boundary | SUPPORTED_PUBLIC_API | Medium |
| utils | No top-level package exports; utils.output has explicit output helpers | utils modules and utils.output | No at top level | No at top level | config.py, doctor.py, cache wrappers | diagnostics | utility tests | CLI and GUI | INTERNAL | Medium |

## F. CLI compatibility inventory

| Unified command | Router dispatch | Canonical implementation | Direct module invocation | Root wrapper | Legacy aliases | Important defaults | Output behavior | Help/parser test evidence | Classification | Risk |
|---|---|---|---|---|---|---|---|---|---|---|
| twstock doctor | doctor | utils.doctor | py -m tw_stock_tool.utils.doctor | doctor.py | None found | environment checks | console | test_doctor.py | SUPPORTED_CLI | Medium |
| twstock scan | scan | cli.scan_stocks | py -m tw_stock_tool.cli.scan_stocks | scan_stocks.py | None found | output directory | ranking files | test_scan_stocks.py | SUPPORTED_CLI | High |
| twstock daily | daily | cli.daily_report_cli | py -m tw_stock_tool.cli.daily_report_cli | daily_report.py | None found | output/ | daily_report.md and daily_report.xlsx | daily CLI tests | SUPPORTED_CLI | High |
| twstock stock-list update | stock-list/update | data.stock_list_updater | py -m tw_stock_tool.data.stock_list_updater | stock_list_updater.py | None found | stocks.txt | user path | smoke tests | SUPPORTED_CLI | Medium |
| twstock stock-list smoke-check | stock-list/smoke-check | cli.stock_list_smoke_check | py -m tw_stock_tool.cli.stock_list_smoke_check | stock_list_smoke_check.py | None found | console | console | smoke tests | SUPPORTED_CLI | Medium |
| twstock stock-list clean | stock-list/clean | cli.clean_stocks | py -m tw_stock_tool.cli.clean_stocks | clean_stocks.py | None found | output/ | clean report, xlsx, txt | clean CLI tests | SUPPORTED_CLI | Medium |
| twstock price-smoke-check | price-smoke-check | cli.price_data_smoke_check | py -m tw_stock_tool.cli.price_data_smoke_check | price_data_smoke_check.py | None found | console | console | smoke tests | SUPPORTED_CLI | Medium |
| twstock ai-scan | ai-scan | ml.ai_stock_scanner | py -m tw_stock_tool.ml.ai_stock_scanner | ai_stock_scanner.py | None found | user output | xlsx/user path | AI scanner tests | SUPPORTED_CLI | Medium |
| twstock cache | cache | data.cache_manager | py -m tw_stock_tool.data.cache_manager | cache_manager.py | None found | cache directory | cache files | cache tests | SUPPORTED_CLI | Medium |
| twstock benchmark | benchmark | cli.benchmark | py -m tw_stock_tool.cli.benchmark | benchmark.py | None found | output/benchmark | benchmark_summary.csv, benchmark_detail.csv, benchmark_errors.csv | benchmark tests | SUPPORTED_CLI | Medium |
| twstock analyze | analyze | cli.main | py -m tw_stock_tool.cli.main | main.py | None found | output/ | report and chart | test_main.py | SUPPORTED_CLI | High |
| twstock strategy-compare | strategy-compare | backtesting.strategy_compare | py -m tw_stock_tool.backtesting.strategy_compare | strategy_compare.py | --output | output Excel | stock strategy compare xlsx | strategy compare tests | SUPPORTED_CLI | High |
| twstock parameter-sweep | parameter-sweep | cli.parameter_sweep_report | py -m tw_stock_tool.cli.parameter_sweep_report | parameter_sweep_report.py | None found | output/ | parameter_sweep_report.md and xlsx | report CLI tests | SUPPORTED_CLI | High |
| twstock backtest-report | backtest-report | cli.backtest_report | py -m tw_stock_tool.cli.backtest_report | backtest_report.py | None found | output/ | backtest_report.md and xlsx | report CLI tests | SUPPORTED_CLI | High |
| twstock walk-forward | walk-forward | cli.walk_forward_report | py -m tw_stock_tool.cli.walk_forward_report | walk_forward_report.py | None found | output/ | walk_forward_report.md and xlsx | report CLI tests | SUPPORTED_CLI | High |
| twstock simulated-paper-trading | simulated-paper-trading | cli.simulated_paper_trading_cli | py -m tw_stock_tool.cli.simulated_paper_trading_cli | simulated_paper_trading_cli.py | None found | research-only | artifact/user path | simulation CLI tests | SUPPORTED_CLI | High |
| twstock simulated-paper-trading-export | simulated-paper-trading-export | cli.simulated_paper_trading_export_cli | py -m tw_stock_tool.cli.simulated_paper_trading_export_cli | simulated_paper_trading_export_cli.py | None found | user output | Markdown and CSV files | export CLI tests | SUPPORTED_CLI | High |
| twstock backtest-artifact | backtest-artifact | cli.backtest_artifact_cli | py -m tw_stock_tool.cli.backtest_artifact_cli | None found | None found | explicit input/output | JSON artifact | test_backtest_artifact_cli.py | SUPPORTED_CLI | High |
| twstock backtest-result-export | backtest-result-export | cli.backtest_result_export_cli | py -m tw_stock_tool.cli.backtest_result_export_cli | None found | None found | required --output-json | JSON artifact | export CLI tests | SUPPORTED_CLI | High |

## G. Artifact and schema compatibility

| Artifact family | Writer | Reader | Current write version | Supported read versions | Stable fields or strictness | Defaults, keys, or sheets | Compatibility tests | Risk |
|---|---|---|---|---|---|---|---|---|
| BacktestResult JSON | artifact export CLI | artifact reader | current structured schema | supported schema only | schema version, identity, trades, metrics; unsupported versions rejected | explicit --output-json | test_backtest_artifact_cli.py and serialization tests | High |
| Simulated paper-trading JSON | serialization modules | serialization modules | v3 | v1, v2, v3 | summary, orders, fills, rejections, audit_log; unknown fields rejected | user JSON path | paper trading serialization and trade log tests | High |
| Simulated paper-trading Markdown | Markdown exporter | Not applicable | Not applicable | Not applicable | additive sections | user path | exporter and file tests | High |
| Simulated paper-trading CSV bundle | CSV exporter | Not applicable | Not applicable | Not applicable | stable row groups | summary, orders, fills, rejections, trade_log | exporter and file tests | High |
| Backtest report Markdown and Excel | report exporters | Not applicable | Not applicable | Not applicable | report result compatibility | output/backtest_report.md and xlsx | report CLI tests | High |
| Parameter sweep Markdown and Excel | report exporters | Not applicable | Not applicable | Not applicable | report result compatibility | output/parameter_sweep_report.md and xlsx | sweep report tests | High |
| Walk-forward Markdown and Excel | report exporters | Not applicable | Not applicable | Not applicable | report result compatibility | output/walk_forward_report.md and xlsx | walk-forward tests | High |
| Daily report and watchlist | daily CLI and exporters | Not applicable | Not applicable | Not applicable | report rows and errors | output/daily_report and daily_watchlist files | daily tests | High |
| Benchmark CSV | cli.benchmark | Not applicable | Not applicable | Not applicable | summary, detail, error rows | benchmark_summary.csv, benchmark_detail.csv, benchmark_errors.csv | benchmark tests | Medium |

## H. Duplicate-path findings

`backtesting/` is the active/canonical DataFrame-oriented runtime and artifact path. Root `backtest.py` and `strategies.py` target the canonical modules.

## I. Deprecation prerequisites

Deprecation requires a canonical replacement, adapter where needed, import and CLI smoke tests, README migration instructions, warning policy, documented release window, versioning plan, release notes, and removal-test updates.

## J. Recommended actions and corrected counts

Safe now: maintain this inventory and documentation links. Later: add import and help smoke matrices. Compatibility window required: root wrappers, aliases, public imports. Production migration required: GUI/data/report refactors. Must not change yet: filenames, schemas, CLI flags, wrappers, dependencies.

Counting units are table rows: root file rows, CLI command rows, package/export rows, and artifact rows are not combined.

| Measure | Count |
|---|---:|
| Root-level files represented by individual rows | 41 |
| Unified command forms and SUPPORTED_CLI rows | 19 |
| Package/export rows | 11 |
| Artifact/schema rows | 9 |
| SUPPORTED_PUBLIC_API package/export rows | 6 |
| COMPATIBILITY_ONLY root-file rows | 41 |
| UNKNOWN_EXTERNAL_USAGE package/export rows | 1 |
| INVESTIGATE package/export rows | 0 |
| DEPRECATION_CANDIDATE rows | 0 |
| REMOVE_CANDIDATE rows | 0 |