# Track C13 ??Repository-wide CLI Runtime Contract Audit

## Executive outcome

PASS -- complete tracked-tree inventory and classification recorded. Only the two approved files are added; no production/test/configuration code was changed and no runtime fix was started.

## Formal audit result and baseline

Verified HEAD, local main, and origin/main: da32b3ef92eba08987307aa99ebac3f3afcb916d. Branch: track-c13-repository-wide-cli-runtime-contract-audit, created directly from that baseline. Pre-audit status was clean. Ignored bytecode was allowed and not deleted.

## Exact files added

- docs/TRACK_C13_REPOSITORY_WIDE_CLI_RUNTIME_CONTRACT_AUDIT.md
- docs/CLI_RUNTIME_CONTRACT_INVENTORY.json

## Methodology, AST, Git/text, and Ponytail

Every tracked Python file came from git ls-files '*.py'. A temporary inline ast visitor collected main definitions/signatures/annotations, parser construction, sys.exit, raise SystemExit, guards, guard calls, and main references. Independent git grep searches covered sys.exit, raise SystemExit, main guards, def main, ArgumentParser, and .main(. pyproject.toml, the unified dispatcher, all 41 root Python files, package modules, and CLI/wrapper/subprocess tests were inspected.

Ponytail mode was @ponytail-audit read-only. Get-Command ponytail* found no standalone executable, so no auto-fix was possible or used. Read-only findings: repeated report parser registration, repeated unified route registration, duplicated subprocess setup, and compatibility wrappers. Safe immediate reduction is -0 lines and -0 dependencies.

## Discovery counts

| Measure | Result |
|---|---:|
| Tracked Python files | 259 |
| main function definitions | 29 |
| argparse CLI files | 28 |
| executable guards | 155 (29 src, 24 root, 102 unittest) |
| sys.exit occurrences | 8 text; 2 AST |
| raise SystemExit occurrences | 34 text; 29 AST |
| console scripts | 1 |
| unified route forms | 19 |
| root-wrapper files | 41 |
| package __main__.py files | 0 |
| total executable surfaces | 53 (29 callable + 24 executable wrappers) |

## Runtime contract and dispatcher

The model is success None or documented status, handled failure 1, argparse help SystemExit(0), argparse usage SystemExit(2), package guard raise SystemExit(main()), and dispatcher None -> 0 with integers unchanged. twstock_cli.py restores sys.argv in finally and imports most children eagerly; simulated paper trading and backtest-result-export are lazy. Child SystemExit is not normalized by the dispatcher.

## Console-script inventory

| Script | Target | Contract |
|---|---|---|
| twstock | tw_stock_tool.cli.twstock_cli:main | returns int; package guard raises SystemExit(main()) |

## Unified route inventory

| Route | Child module | Synthetic program | Import | Nested |
|---|---|---|---|---|
| doctor | tw_stock_tool.utils.doctor:main | doctor.py | eager | - |
| scan | tw_stock_tool.cli.scan_stocks:main | scan_stocks.py | eager | - |
| daily | tw_stock_tool.cli.daily_report_cli:main | daily_report_cli.py | eager | - |
| stock-list update | tw_stock_tool.data.stock_list_updater:main | stock_list_updater.py | eager | - |
| stock-list smoke-check | tw_stock_tool.cli.stock_list_smoke_check:main | stock_list_smoke_check.py | eager | - |
| stock-list clean | tw_stock_tool.cli.clean_stocks:main | clean_stocks.py | eager | - |
| price-smoke-check | tw_stock_tool.cli.price_data_smoke_check:main | price_data_smoke_check.py | eager | - |
| ai-scan | tw_stock_tool.ml.ai_stock_scanner:main | ai_stock_scanner.py | eager | - |
| cache | tw_stock_tool.data.cache_manager:main | cache_manager.py | eager | - |
| benchmark | tw_stock_tool.cli.benchmark:main | benchmark.py | eager | - |
| analyze | tw_stock_tool.cli.main:main | main.py | eager | - |
| strategy-compare | tw_stock_tool.backtesting.strategy_compare:main | strategy_compare.py | eager | - |
| parameter-sweep | tw_stock_tool.cli.parameter_sweep_report:main | parameter_sweep_report.py | eager | - |
| backtest-report | tw_stock_tool.cli.backtest_report:main | backtest_report.py | eager | - |
| walk-forward | tw_stock_tool.cli.walk_forward_report:main | walk_forward_report.py | eager | - |
| simulated-paper-trading | tw_stock_tool.cli.simulated_paper_trading_cli:main | simulated_paper_trading_cli.py | lazy | - |
| simulated-paper-trading-export | tw_stock_tool.cli.simulated_paper_trading_export_cli:main | simulated_paper_trading_export_cli.py | eager | - |
| backtest-artifact | tw_stock_tool.cli.backtest_artifact_cli:main | backtest_artifact_cli.py | eager | validate, inspect, convert-to-simulated-paper-trading |
| backtest-result-export | tw_stock_tool.cli.backtest_result_export_cli:main | backtest_result_export_cli.py | lazy | - |

All 19 registrations use _dispatch_existing_main and patched sys.argv. backtest-artifact has three child parser commands.

## Root-wrapper inventory

| Root wrapper | Target(s) | Guard | Translation |
|---|---|---|---|
| ai_prediction_report.py | tw_stock_tool.reports.ai_prediction_report | _impl.main() | direct call/import only |
| ai_stock_scanner.py | tw_stock_tool.ml.ai_stock_scanner | _impl.main() | direct call/import only |
| ai_walk_forward.py | tw_stock_tool.ml.ai_walk_forward | raise SystemExit(_impl.main()) | raise SystemExit status |
| analysis.py | tw_stock_tool.analysis.analysis | none | direct call/import only |
| app_services.py | tw_stock_tool.gui.app_services | none | direct call/import only |
| backtest.py | tw_stock_tool.backtesting.backtest | none | direct call/import only |
| backtest_report.py | tw_stock_tool.cli.backtest_report | main() | direct call/import only |
| baseline_ml_model.py | tw_stock_tool.ml.baseline_ml_model | none | direct call/import only |
| benchmark.py | tw_stock_tool.cli.benchmark | raise SystemExit(_impl.main()) | raise SystemExit status |
| cache_manager.py | tw_stock_tool.data.cache_manager | raise SystemExit(_impl.main()) | raise SystemExit status |
| cache_utils.py | tw_stock_tool.data.cache_utils | none | direct call/import only |
| clean_stocks.py | tw_stock_tool.cli.clean_stocks | raise SystemExit(_impl.main()) | raise SystemExit status |
| config.py | tw_stock_tool.utils.config | none | direct call/import only |
| console_lock.py | tw_stock_tool.utils.console_lock | none | direct call/import only |
| daily_report.py | tw_stock_tool.reports.daily_report | _impl.main() | direct call/import only |
| daily_watchlist.py | tw_stock_tool.cli.daily_watchlist | _impl.main() | direct call/import only |
| data_loader.py | tw_stock_tool.data.data_loader | none | direct call/import only |
| doctor.py | tw_stock_tool.utils.doctor | _impl.main() | direct call/import only |
| gui_app.py | tw_stock_tool.gui.gui_app | _impl.main() | direct call/import only |
| gui_result_formatter.py | tw_stock_tool.gui.gui_result_formatter | none | direct call/import only |
| gui_tasks.py | tw_stock_tool.gui.gui_tasks | none | direct call/import only |
| indicators.py | tw_stock_tool.analysis.indicators | none | direct call/import only |
| main.py | tw_stock_tool.cli.main | raise SystemExit(_impl.main()) | raise SystemExit status |
| ml_dataset.py | tw_stock_tool.ml.ml_dataset | _impl.main() | direct call/import only |
| parameter_sweep.py | tw_stock_tool.cli.parameter_sweep_report | _impl.main() | direct call/import only |
| parameter_sweep_report.py | tw_stock_tool.cli.parameter_sweep_report | main() | direct call/import only |
| plotter.py | tw_stock_tool.reports.plotter | none | direct call/import only |
| price_data_smoke_check.py | tw_stock_tool.cli.price_data_smoke_check | raise SystemExit(_impl.main()) | raise SystemExit status |
| report.py | tw_stock_tool.reports.report | none | direct call/import only |
| scan_stocks.py | tw_stock_tool.cli.scan_stocks | raise SystemExit(_impl.main()) | raise SystemExit status |
| scanner.py | tw_stock_tool.analysis.scanner | none | direct call/import only |
| signals.py | tw_stock_tool.analysis.signals | none | direct call/import only |
| stock_list_smoke_check.py | tw_stock_tool.cli.stock_list_smoke_check | raise SystemExit(_impl.main()) | raise SystemExit status |
| stock_list_updater.py | tw_stock_tool.data.stock_list_updater | raise SystemExit(_impl.main()) | raise SystemExit status |
| stock_selection.py | tw_stock_tool.analysis.stock_selection | none | direct call/import only |
| strategies.py | tw_stock_tool.backtesting.strategies | none | direct call/import only |
| strategy_compare.py | tw_stock_tool.backtesting.strategy_compare | _impl.main() | direct call/import only |
| twstock_cli.py | tw_stock_tool.cli.twstock_cli | raise SystemExit(_impl.main()) | raise SystemExit status |
| verify_batch.py | tw_stock_tool.utils.verify_batch | _impl.main() | direct call/import only |
| walk_forward.py | tw_stock_tool.cli.walk_forward_report | _impl.main() | direct call/import only |
| walk_forward_report.py | tw_stock_tool.cli.walk_forward_report | main() | direct call/import only |

All 41 root files remain documented compatibility boundaries; no deletion is proposed in this phase.

## Entrypoint matrix

| ID | Path | Surface | Route/Script | Callable Success | Runtime Failure | Parser 0/2 | Guard | Classification | Severity | Compatibility Risk | Future Batch |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CLI-001 | src/tw_stock_tool/backtesting/parameter_sweep.py | callable_main | - | Returns None on successful completion. | Returns None on success and after caught failures, allowing false process success. | 0/2 | if __name__ == "__main__": main() | FALSE_SUCCESS_RUNTIME | CRITICAL | MEDIUM_COMPATIBILITY_RISK | BATCH_B_FALSE_SUCCESS_FIXES |
| CLI-002 | src/tw_stock_tool/backtesting/strategy_compare.py | callable_main | strategy-compare | Returns None on successful completion. | Returns None on success and after caught failures, allowing false process success. | 0/2 | if __name__ == "__main__": main() | FALSE_SUCCESS_RUNTIME | CRITICAL | HIGH_COMPATIBILITY_RISK | BATCH_B_FALSE_SUCCESS_FIXES |
| CLI-003 | src/tw_stock_tool/backtesting/walk_forward.py | callable_main | - | Returns None on successful completion. | Returns None on success and after caught failures, allowing false process success. | 0/2 | if __name__ == "__main__": main() | FALSE_SUCCESS_RUNTIME | CRITICAL | MEDIUM_COMPATIBILITY_RISK | BATCH_B_FALSE_SUCCESS_FIXES |
| CLI-004 | src/tw_stock_tool/cli/backtest_artifact_cli.py | callable_main | backtest-artifact | Returns 0 or None on successful completion. | Returns None or an explicit nonzero integer on handled failure. | 0/2 | if __name__ == "__main__": raise SystemExit(main()) | COMPLIANT_RETURN_CONTRACT | NONE | LOW_COMPATIBILITY_RISK | NO_FIX_REQUIRED |
| CLI-005 | src/tw_stock_tool/cli/backtest_report.py | callable_main | backtest-report | Returns None on successful completion. | Returns None on success; raises SystemExit(1) on handled runtime failure. | 0/2 | if __name__ == "__main__": main() | RAISE_SYSTEM_EXIT_RUNTIME | HIGH | HIGH_COMPATIBILITY_RISK | BATCH_A_RETURN_CODE_NORMALIZATION |
| CLI-006 | src/tw_stock_tool/cli/backtest_result_export_cli.py | callable_main | backtest-result-export | Returns 0 or None on successful completion. | Returns None or an explicit nonzero integer on handled failure. | 0/2 | if __name__ == "__main__": raise SystemExit(main()) | COMPLIANT_RETURN_CONTRACT | NONE | LOW_COMPATIBILITY_RISK | NO_FIX_REQUIRED |
| CLI-007 | src/tw_stock_tool/cli/benchmark.py | callable_main | benchmark | Returns 0 or None on successful completion. | Returns None or an explicit nonzero integer on handled failure. | 0/2 | if __name__ == "__main__": raise SystemExit(main()) | COMPLIANT_RETURN_CONTRACT | NONE | LOW_COMPATIBILITY_RISK | NO_FIX_REQUIRED |
| CLI-008 | src/tw_stock_tool/cli/clean_stocks.py | callable_main | stock-list clean | Returns 0 or None on successful completion. | Returns None or an explicit nonzero integer on handled failure. | 0/2 | if __name__ == "__main__": raise SystemExit(main()) | COMPLIANT_RETURN_CONTRACT | NONE | LOW_COMPATIBILITY_RISK | NO_FIX_REQUIRED |
| CLI-009 | src/tw_stock_tool/cli/daily_report_cli.py | callable_main | daily | Returns None on successful completion. | Returns None on success; calls sys.exit(1) on handled runtime failure. | 0/2 | if __name__ == "__main__": main() | DIRECT_SYS_EXIT_RUNTIME | HIGH | HIGH_COMPATIBILITY_RISK | BATCH_A_RETURN_CODE_NORMALIZATION |
| CLI-010 | src/tw_stock_tool/cli/daily_watchlist.py | callable_main | - | Returns None on successful completion. | Process-only or interactive command; status boundary requires isolated design. | 0/2 | if __name__ == "__main__": main() | PROCESS_ONLY_REVIEW_REQUIRED | MEDIUM | MEDIUM_COMPATIBILITY_RISK | BATCH_C_SPECIAL_PROCESS_LIVE_INTERACTIVE |
| CLI-011 | src/tw_stock_tool/cli/main.py | callable_main | analyze | Returns 0 or None on successful completion. | Returns None or an explicit nonzero integer on handled failure. | 0/2 | if __name__ == "__main__": raise SystemExit(main()) | COMPLIANT_RETURN_CONTRACT | NONE | LOW_COMPATIBILITY_RISK | NO_FIX_REQUIRED |
| CLI-012 | src/tw_stock_tool/cli/parameter_sweep_report.py | callable_main | parameter-sweep | Returns None on successful completion. | Returns None on success; raises SystemExit(1) on handled runtime failure. | 0/2 | if __name__ == "__main__": main() | RAISE_SYSTEM_EXIT_RUNTIME | HIGH | HIGH_COMPATIBILITY_RISK | BATCH_A_RETURN_CODE_NORMALIZATION |
| CLI-013 | src/tw_stock_tool/cli/price_data_smoke_check.py | callable_main | price-smoke-check | Returns 0 or None on successful completion. | Returns None or an explicit nonzero integer on handled failure. | 0/2 | if __name__ == "__main__": raise SystemExit(main()) | COMPLIANT_RETURN_CONTRACT | NONE | LOW_COMPATIBILITY_RISK | NO_FIX_REQUIRED |
| CLI-014 | src/tw_stock_tool/cli/scan_stocks.py | callable_main | scan | Returns 0 or None on successful completion. | Returns None or an explicit nonzero integer on handled failure. | 0/2 | if __name__ == "__main__": raise SystemExit(main()) | COMPLIANT_RETURN_CONTRACT | NONE | LOW_COMPATIBILITY_RISK | NO_FIX_REQUIRED |
| CLI-015 | src/tw_stock_tool/cli/simulated_paper_trading_cli.py | callable_main | simulated-paper-trading | Returns None on successful completion. | Returns None on success; raises SystemExit(1) on handled runtime failure. | 0/2 | if __name__ == "__main__": main() | RAISE_SYSTEM_EXIT_RUNTIME | HIGH | HIGH_COMPATIBILITY_RISK | BATCH_A_RETURN_CODE_NORMALIZATION |
| CLI-016 | src/tw_stock_tool/cli/simulated_paper_trading_export_cli.py | callable_main | simulated-paper-trading-export | Returns 0 or None on successful completion. | Returns None or an explicit nonzero integer on handled failure. | 0/2 | if __name__ == "__main__": raise SystemExit(main()) | COMPLIANT_RETURN_CONTRACT | NONE | LOW_COMPATIBILITY_RISK | NO_FIX_REQUIRED |
| CLI-017 | src/tw_stock_tool/cli/stock_list_smoke_check.py | callable_main | stock-list smoke-check | Returns 0 or None on successful completion. | Returns None or an explicit nonzero integer on handled failure. | 0/2 | if __name__ == "__main__": raise SystemExit(main()) | COMPLIANT_RETURN_CONTRACT | NONE | LOW_COMPATIBILITY_RISK | NO_FIX_REQUIRED |
| CLI-018 | src/tw_stock_tool/cli/twstock_cli.py | callable_main | - | Returns 0 or None on successful completion. | Returns None or an explicit nonzero integer on handled failure. | 0/2 | if __name__ == "__main__": raise SystemExit(main()) | COMPLIANT_RETURN_CONTRACT | NONE | LOW_COMPATIBILITY_RISK | NO_FIX_REQUIRED |
| CLI-019 | src/tw_stock_tool/cli/walk_forward_report.py | callable_main | walk-forward | Returns None on successful completion. | Returns None on success; raises SystemExit(1) on handled runtime failure. | 0/2 | if __name__ == "__main__": main() | RAISE_SYSTEM_EXIT_RUNTIME | HIGH | HIGH_COMPATIBILITY_RISK | BATCH_A_RETURN_CODE_NORMALIZATION |
| CLI-020 | src/tw_stock_tool/data/cache_manager.py | callable_main | cache | Returns 0 or None on successful completion. | Returns None or an explicit nonzero integer on handled failure. | 0/2 | if __name__ == "__main__": raise SystemExit(main()) | COMPLIANT_RETURN_CONTRACT | NONE | LOW_COMPATIBILITY_RISK | NO_FIX_REQUIRED |
| CLI-021 | src/tw_stock_tool/data/stock_list_updater.py | callable_main | stock-list update | Returns 0 or None on successful completion. | Returns None or an explicit nonzero integer on handled failure. | 0/2 | if __name__ == "__main__": raise SystemExit(main()) | COMPLIANT_RETURN_CONTRACT | NONE | LOW_COMPATIBILITY_RISK | NO_FIX_REQUIRED |
| CLI-022 | src/tw_stock_tool/gui/gui_app.py | callable_main | - | Returns None on successful completion. | Process-only or interactive command; status boundary requires isolated design. | - | if __name__ == "__main__": main() | PROCESS_ONLY_REVIEW_REQUIRED | MEDIUM | HIGH_COMPATIBILITY_RISK | BATCH_C_SPECIAL_PROCESS_LIVE_INTERACTIVE |
| CLI-023 | src/tw_stock_tool/ml/ai_stock_scanner.py | callable_main | ai-scan | Returns None on successful completion. | Returns None on success and after caught failures, allowing false process success. | 0/2 | if __name__ == "__main__": main() | FALSE_SUCCESS_RUNTIME | CRITICAL | HIGH_COMPATIBILITY_RISK | BATCH_B_FALSE_SUCCESS_FIXES |
| CLI-024 | src/tw_stock_tool/ml/ai_walk_forward.py | callable_main | - | Returns 0 or None on successful completion. | Returns None or an explicit nonzero integer on handled failure. | 0/2 | if __name__ == "__main__": raise SystemExit(main()) | COMPLIANT_RETURN_CONTRACT | NONE | LOW_COMPATIBILITY_RISK | NO_FIX_REQUIRED |
| CLI-025 | src/tw_stock_tool/ml/baseline_ml_model.py | callable_main | - | Returns None on successful completion. | Returns None on success and after caught failures, allowing false process success. | 0/2 | if __name__ == "__main__": main() | FALSE_SUCCESS_RUNTIME | CRITICAL | MEDIUM_COMPATIBILITY_RISK | BATCH_B_FALSE_SUCCESS_FIXES |
| CLI-026 | src/tw_stock_tool/ml/ml_dataset.py | callable_main | - | Returns None on successful completion. | Returns None on success and after caught failures, allowing false process success. | 0/2 | if __name__ == "__main__": main() | FALSE_SUCCESS_RUNTIME | CRITICAL | MEDIUM_COMPATIBILITY_RISK | BATCH_B_FALSE_SUCCESS_FIXES |
| CLI-027 | src/tw_stock_tool/reports/ai_prediction_report.py | callable_main | - | Returns None on successful completion. | Returns None on success and after caught failures, allowing false process success. | 0/2 | if __name__ == "__main__": main() | FALSE_SUCCESS_RUNTIME | CRITICAL | MEDIUM_COMPATIBILITY_RISK | BATCH_B_FALSE_SUCCESS_FIXES |
| CLI-028 | src/tw_stock_tool/utils/doctor.py | callable_main | doctor | Returns None on successful completion. | Returns None on success; raises SystemExit(1) on handled runtime failure. | 0/2 | if __name__ == "__main__": main() | RAISE_SYSTEM_EXIT_RUNTIME | HIGH | HIGH_COMPATIBILITY_RISK | BATCH_A_RETURN_CODE_NORMALIZATION |
| CLI-029 | src/tw_stock_tool/utils/verify_batch.py | callable_main | - | Returns None on successful completion. | No callable runtime return-code boundary; exceptions propagate or process behavior is inherited. | 0/2 | if __name__ == "__main__": main() | NO_RUNTIME_ERROR_BOUNDARY | MEDIUM | MEDIUM_COMPATIBILITY_RISK | DEFER_PENDING_DESIGN |

The JSON contains all 29 canonical callable records and all 41 wrapper records; 17 wrappers are import-only and therefore excluded from the 53 executable-surface count.

## Classification, severity, and compatibility totals

| Primary classification | Count |
|---|---:|
| COMPLIANT_RETURN_CONTRACT | 13 |
| DIRECT_SYS_EXIT_RUNTIME | 1 |
| RAISE_SYSTEM_EXIT_RUNTIME | 5 |
| FALSE_SUCCESS_RUNTIME | 7 |
| GUARD_ONLY_MISMATCH | 0 |
| PROCESS_ONLY_REVIEW_REQUIRED | 2 |
| NO_RUNTIME_ERROR_BOUNDARY | 1 |
| ARGPARSE_ONLY | 0 |
| DELEGATING_WRAPPER | 0 |
| NOT_APPLICABLE | 0 |

Canonical severity: CRITICAL=7, HIGH=6, MEDIUM=3, LOW=0, NONE=13.
Canonical compatibility risk: HIGH_COMPATIBILITY_RISK=9, MEDIUM_COMPATIBILITY_RISK=7, LOW_COMPATIBILITY_RISK=13.

## Direct caller matrix

The scan found 54 direct production caller sites (24 root guards, 29 package guards, one dispatcher helper) and 221 test main call sites across 27 test modules.

| CLI ID | Caller Path | Caller Type | Expected Behavior | Compatibility Concern |
|---|---|---|---|---|
| CLI-001 | src/tw_stock_tool/backtesting/parameter_sweep.py: guard line 369 | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-002 | src/tw_stock_tool/backtesting/strategy_compare.py: guard line 158, strategy_compare.py: root wrapper guard, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-003 | src/tw_stock_tool/backtesting/walk_forward.py: guard line 602 | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-004 | src/tw_stock_tool/cli/backtest_artifact_cli.py: guard line 127, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-005 | src/tw_stock_tool/cli/backtest_report.py: guard line 172, backtest_report.py: root wrapper guard, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-006 | src/tw_stock_tool/cli/backtest_result_export_cli.py: guard line 137, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-007 | src/tw_stock_tool/cli/benchmark.py: guard line 215, benchmark.py: root wrapper guard, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-008 | src/tw_stock_tool/cli/clean_stocks.py: guard line 338, clean_stocks.py: root wrapper guard, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-009 | src/tw_stock_tool/cli/daily_report_cli.py: guard line 117, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-010 | src/tw_stock_tool/cli/daily_watchlist.py: guard line 125, daily_watchlist.py: root wrapper guard | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-011 | src/tw_stock_tool/cli/main.py: guard line 276, main.py: root wrapper guard, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-012 | src/tw_stock_tool/cli/parameter_sweep_report.py: guard line 157, parameter_sweep.py: root wrapper guard, parameter_sweep_report.py: root wrapper guard, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-013 | src/tw_stock_tool/cli/price_data_smoke_check.py: guard line 156, price_data_smoke_check.py: root wrapper guard, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-014 | src/tw_stock_tool/cli/scan_stocks.py: guard line 163, scan_stocks.py: root wrapper guard, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-015 | src/tw_stock_tool/cli/simulated_paper_trading_cli.py: guard line 219, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-016 | src/tw_stock_tool/cli/simulated_paper_trading_export_cli.py: guard line 87, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-017 | src/tw_stock_tool/cli/stock_list_smoke_check.py: guard line 111, stock_list_smoke_check.py: root wrapper guard, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-018 | src/tw_stock_tool/cli/twstock_cli.py: guard line 175, twstock_cli.py: root wrapper guard | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-019 | src/tw_stock_tool/cli/walk_forward_report.py: guard line 144, walk_forward.py: root wrapper guard, walk_forward_report.py: root wrapper guard, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-020 | src/tw_stock_tool/data/cache_manager.py: guard line 39, cache_manager.py: root wrapper guard, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-021 | src/tw_stock_tool/data/stock_list_updater.py: guard line 255, stock_list_updater.py: root wrapper guard, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-022 | src/tw_stock_tool/gui/gui_app.py: guard line 695, gui_app.py: root wrapper guard | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-023 | src/tw_stock_tool/ml/ai_stock_scanner.py: guard line 296, ai_stock_scanner.py: root wrapper guard, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-024 | src/tw_stock_tool/ml/ai_walk_forward.py: guard line 203, ai_walk_forward.py: root wrapper guard | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-025 | src/tw_stock_tool/ml/baseline_ml_model.py: guard line 237 | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-026 | src/tw_stock_tool/ml/ml_dataset.py: guard line 157, ml_dataset.py: root wrapper guard | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-027 | src/tw_stock_tool/reports/ai_prediction_report.py: guard line 226, ai_prediction_report.py: root wrapper guard | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-028 | src/tw_stock_tool/utils/doctor.py: guard line 192, doctor.py: root wrapper guard, src/tw_stock_tool/cli/twstock_cli.py:_dispatch_existing_main | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |
| CLI-029 | src/tw_stock_tool/utils/verify_batch.py: guard line 162, verify_batch.py: root wrapper guard | guard/wrapper/dispatcher | None/0 success; classified nonzero failure | guard propagation and child SystemExit/None mapping |

### Test coverage inventory

| Test caller path | Direct main calls |
|---|---:|
| tests/test_ai_stock_scanner.py | 1 |
| tests/test_ai_walk_forward.py | 2 |
| tests/test_backtest_artifact_cli.py | 16 |
| tests/test_backtest_report_cli.py | 10 |
| tests/test_backtest_result_export_cli.py | 11 |
| tests/test_daily_report_cli.py | 8 |
| tests/test_daily_watchlist.py | 2 |
| tests/test_main.py | 5 |
| tests/test_parameter_sweep_report_cli.py | 13 |
| tests/test_scanner.py | 2 |
| tests/test_simulated_paper_trading_cli.py | 26 |
| tests/test_simulated_paper_trading_export_cli.py | 10 |
| tests/test_stock_list_updater.py | 1 |
| tests/test_strategy_compare.py | 1 |
| tests/test_track_c10_1_simulated_paper_trading_export_cli_runtime_exit_behavior.py | 4 |
| tests/test_track_c11_1_backtest_artifact_cli_runtime_exit_behavior.py | 9 |
| tests/test_track_c12_1_backtest_result_export_cli_runtime_exit_behavior.py | 6 |
| tests/test_track_c1_research_correctness.py | 2 |
| tests/test_track_c4_1_scanner_cli_exit_behavior.py | 10 |
| tests/test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior.py | 2 |
| tests/test_track_c6_1_benchmark_cli_runtime_exit_behavior.py | 5 |
| tests/test_track_c7_1_clean_stocks_cli_runtime_exit_behavior.py | 5 |
| tests/test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior.py | 5 |
| tests/test_track_c9_1_smoke_check_cli_runtime_exit_behavior.py | 3 |
| tests/test_track_p2_1_unified_cli_passthrough_registration_characterization.py | 6 |
| tests/test_twstock_cli.py | 45 |
| tests/test_walk_forward_report_cli.py | 11 |

Raw supporting searches: assertRaises(SystemExit)=78, returncode=78, subprocess=77, runpy.run_module=2, sys.argv=127, live/exclusion=47. Search counts are not unique tests. Root wrapper execution is covered by test_root_wrappers and test_root_cli_wrapper_exit_codes; routing/argv by test_twstock_cli and Track P2 tests; C4-C12 cover named runtime boundaries.

## Live, interactive, file-writing, and destructive inventory

Live/network-capable canonical surfaces: 25; interactive: 2; file-writing: 22; destructive-capable: 12.

### Live/network

Source-derived live/network capabilities:

- CLI-001 src/tw_stock_tool/backtesting/parameter_sweep.py -- Standalone parameter sweep catches exceptions, prints, and falls through to None.
- CLI-002 src/tw_stock_tool/backtesting/strategy_compare.py -- Supported unified route maps caught failures returning None to status 0.
- CLI-003 src/tw_stock_tool/backtesting/walk_forward.py -- Standalone walk-forward catches exceptions, prints, and falls through to None.
- CLI-005 src/tw_stock_tool/cli/backtest_report.py -- Unified route child catches a runtime error and raises SystemExit(1).
- CLI-006 src/tw_stock_tool/cli/backtest_result_export_cli.py -- Historical data export returns 1 for handled errors; --overwrite is explicit.
- CLI-007 src/tw_stock_tool/cli/benchmark.py -- Network-backed benchmark with optional CSV output.
- CLI-008 src/tw_stock_tool/cli/clean_stocks.py -- Downloads prices and can replace selected clean-list/report files.
- CLI-009 src/tw_stock_tool/cli/daily_report_cli.py -- Calls sys.exit(1) for empty input and caught runtime failures; always writes Markdown.
- CLI-010 src/tw_stock_tool/cli/daily_watchlist.py -- Standalone live/file-writing command with isolated SystemExit process behavior.
- CLI-011 src/tw_stock_tool/cli/main.py -- Returns 0/1; no --stock enters input()-based interactive mode.
- CLI-012 src/tw_stock_tool/cli/parameter_sweep_report.py -- Catches runtime errors and raises SystemExit(1) from a routed callable.
- CLI-013 src/tw_stock_tool/cli/price_data_smoke_check.py -- Live/manual smoke check returns nonzero through its callable path.
- CLI-014 src/tw_stock_tool/cli/scan_stocks.py -- Known compliant scanner; auto stock-list and optional ranking/error files are side effects.
- CLI-015 src/tw_stock_tool/cli/simulated_paper_trading_cli.py -- Historical simulation raises SystemExit(1) on runtime failure; no broker/order operation.
- CLI-017 src/tw_stock_tool/cli/stock_list_smoke_check.py -- Live/manual TWSE/TPEx smoke check returns nonzero on failure.
- CLI-019 src/tw_stock_tool/cli/walk_forward_report.py -- Catches runtime errors and raises SystemExit(1) from a routed callable.
- CLI-021 src/tw_stock_tool/data/stock_list_updater.py -- Known compliant updater; fetches official sources and replaces selected output.
- CLI-022 src/tw_stock_tool/gui/gui_app.py -- Legacy Tk GUI is interactive and exposes live, file, cache-clear, and update callbacks.
- CLI-023 src/tw_stock_tool/ml/ai_stock_scanner.py -- Starting lead confirmed: caught error prints and unified None-to-0 reports success.
- CLI-024 src/tw_stock_tool/ml/ai_walk_forward.py -- Standalone validation skeleton returns 0/1.
- CLI-025 src/tw_stock_tool/ml/baseline_ml_model.py -- Standalone caught failures print and fall through to process status 0.
- CLI-026 src/tw_stock_tool/ml/ml_dataset.py -- Standalone dataset command catches failures and optionally writes CSV.
- CLI-027 src/tw_stock_tool/reports/ai_prediction_report.py -- Standalone report catches failures and optionally writes Excel.
- CLI-028 src/tw_stock_tool/utils/doctor.py -- Starting lead confirmed: failed checks raise SystemExit(1); --live is network-dependent.
- CLI-029 src/tw_stock_tool/utils/verify_batch.py -- Network/file-writing verifier has no callable exception-to-status boundary.


### Interactive

Source-derived interactive capabilities:

- CLI-011 src/tw_stock_tool/cli/main.py -- Returns 0/1; no --stock enters input()-based interactive mode.
- CLI-022 src/tw_stock_tool/gui/gui_app.py -- Legacy Tk GUI is interactive and exposes live, file, cache-clear, and update callbacks.


### File-writing

Source-derived file-writing capabilities:

- CLI-001 src/tw_stock_tool/backtesting/parameter_sweep.py -- Standalone parameter sweep catches exceptions, prints, and falls through to None.
- CLI-002 src/tw_stock_tool/backtesting/strategy_compare.py -- Supported unified route maps caught failures returning None to status 0.
- CLI-003 src/tw_stock_tool/backtesting/walk_forward.py -- Standalone walk-forward catches exceptions, prints, and falls through to None.
- CLI-004 src/tw_stock_tool/cli/backtest_artifact_cli.py -- Offline artifact validation and conversion; --overwrite is explicit.
- CLI-005 src/tw_stock_tool/cli/backtest_report.py -- Unified route child catches a runtime error and raises SystemExit(1).
- CLI-006 src/tw_stock_tool/cli/backtest_result_export_cli.py -- Historical data export returns 1 for handled errors; --overwrite is explicit.
- CLI-007 src/tw_stock_tool/cli/benchmark.py -- Network-backed benchmark with optional CSV output.
- CLI-008 src/tw_stock_tool/cli/clean_stocks.py -- Downloads prices and can replace selected clean-list/report files.
- CLI-009 src/tw_stock_tool/cli/daily_report_cli.py -- Calls sys.exit(1) for empty input and caught runtime failures; always writes Markdown.
- CLI-010 src/tw_stock_tool/cli/daily_watchlist.py -- Standalone live/file-writing command with isolated SystemExit process behavior.
- CLI-011 src/tw_stock_tool/cli/main.py -- Returns 0/1; no --stock enters input()-based interactive mode.
- CLI-012 src/tw_stock_tool/cli/parameter_sweep_report.py -- Catches runtime errors and raises SystemExit(1) from a routed callable.
- CLI-014 src/tw_stock_tool/cli/scan_stocks.py -- Known compliant scanner; auto stock-list and optional ranking/error files are side effects.
- CLI-016 src/tw_stock_tool/cli/simulated_paper_trading_export_cli.py -- Offline artifact export with parser-owned missing-option failure and --overwrite.
- CLI-019 src/tw_stock_tool/cli/walk_forward_report.py -- Catches runtime errors and raises SystemExit(1) from a routed callable.
- CLI-021 src/tw_stock_tool/data/stock_list_updater.py -- Known compliant updater; fetches official sources and replaces selected output.
- CLI-022 src/tw_stock_tool/gui/gui_app.py -- Legacy Tk GUI is interactive and exposes live, file, cache-clear, and update callbacks.
- CLI-023 src/tw_stock_tool/ml/ai_stock_scanner.py -- Starting lead confirmed: caught error prints and unified None-to-0 reports success.
- CLI-026 src/tw_stock_tool/ml/ml_dataset.py -- Standalone dataset command catches failures and optionally writes CSV.
- CLI-027 src/tw_stock_tool/reports/ai_prediction_report.py -- Standalone report catches failures and optionally writes Excel.
- CLI-028 src/tw_stock_tool/utils/doctor.py -- Starting lead confirmed: failed checks raise SystemExit(1); --live is network-dependent.
- CLI-029 src/tw_stock_tool/utils/verify_batch.py -- Network/file-writing verifier has no callable exception-to-status boundary.


### Destructive

Source-derived destructive capabilities:

- CLI-004 src/tw_stock_tool/cli/backtest_artifact_cli.py -- Offline artifact validation and conversion; --overwrite is explicit.
- CLI-006 src/tw_stock_tool/cli/backtest_result_export_cli.py -- Historical data export returns 1 for handled errors; --overwrite is explicit.
- CLI-008 src/tw_stock_tool/cli/clean_stocks.py -- Downloads prices and can replace selected clean-list/report files.
- CLI-009 src/tw_stock_tool/cli/daily_report_cli.py -- Calls sys.exit(1) for empty input and caught runtime failures; always writes Markdown.
- CLI-010 src/tw_stock_tool/cli/daily_watchlist.py -- Standalone live/file-writing command with isolated SystemExit process behavior.
- CLI-016 src/tw_stock_tool/cli/simulated_paper_trading_export_cli.py -- Offline artifact export with parser-owned missing-option failure and --overwrite.
- CLI-020 src/tw_stock_tool/data/cache_manager.py -- Returns 1 on errors; --clear deletes cache files.
- CLI-021 src/tw_stock_tool/data/stock_list_updater.py -- Known compliant updater; fetches official sources and replaces selected output.
- CLI-022 src/tw_stock_tool/gui/gui_app.py -- Legacy Tk GUI is interactive and exposes live, file, cache-clear, and update callbacks.
- CLI-023 src/tw_stock_tool/ml/ai_stock_scanner.py -- Starting lead confirmed: caught error prints and unified None-to-0 reports success.
- CLI-026 src/tw_stock_tool/ml/ml_dataset.py -- Standalone dataset command catches failures and optionally writes CSV.
- CLI-027 src/tw_stock_tool/reports/ai_prediction_report.py -- Standalone report catches failures and optionally writes Excel.


No live/manual/interactive command was invoked; the lists are source-derived capability classifications.

## Defect inventories

### Compliant contract inventory

- CLI-004 src/tw_stock_tool/cli/backtest_artifact_cli.py -- Offline artifact validation and conversion; --overwrite is explicit.
- CLI-006 src/tw_stock_tool/cli/backtest_result_export_cli.py -- Historical data export returns 1 for handled errors; --overwrite is explicit.
- CLI-007 src/tw_stock_tool/cli/benchmark.py -- Network-backed benchmark with optional CSV output.
- CLI-008 src/tw_stock_tool/cli/clean_stocks.py -- Downloads prices and can replace selected clean-list/report files.
- CLI-011 src/tw_stock_tool/cli/main.py -- Returns 0/1; no --stock enters input()-based interactive mode.
- CLI-013 src/tw_stock_tool/cli/price_data_smoke_check.py -- Live/manual smoke check returns nonzero through its callable path.
- CLI-014 src/tw_stock_tool/cli/scan_stocks.py -- Known compliant scanner; auto stock-list and optional ranking/error files are side effects.
- CLI-016 src/tw_stock_tool/cli/simulated_paper_trading_export_cli.py -- Offline artifact export with parser-owned missing-option failure and --overwrite.
- CLI-017 src/tw_stock_tool/cli/stock_list_smoke_check.py -- Live/manual TWSE/TPEx smoke check returns nonzero on failure.
- CLI-018 src/tw_stock_tool/cli/twstock_cli.py -- Unified dispatcher maps child None to 0, preserves integers, and restores sys.argv.
- CLI-020 src/tw_stock_tool/data/cache_manager.py -- Returns 1 on errors; --clear deletes cache files.
- CLI-021 src/tw_stock_tool/data/stock_list_updater.py -- Known compliant updater; fetches official sources and replaces selected output.
- CLI-024 src/tw_stock_tool/ml/ai_walk_forward.py -- Standalone validation skeleton returns 0/1.

### Direct sys.exit defect inventory

- CLI-009 src/tw_stock_tool/cli/daily_report_cli.py -- Calls sys.exit(1) for empty input and caught runtime failures; always writes Markdown.

### Raised SystemExit defect inventory

- CLI-005 src/tw_stock_tool/cli/backtest_report.py -- Unified route child catches a runtime error and raises SystemExit(1).
- CLI-012 src/tw_stock_tool/cli/parameter_sweep_report.py -- Catches runtime errors and raises SystemExit(1) from a routed callable.
- CLI-015 src/tw_stock_tool/cli/simulated_paper_trading_cli.py -- Historical simulation raises SystemExit(1) on runtime failure; no broker/order operation.
- CLI-019 src/tw_stock_tool/cli/walk_forward_report.py -- Catches runtime errors and raises SystemExit(1) from a routed callable.
- CLI-028 src/tw_stock_tool/utils/doctor.py -- Starting lead confirmed: failed checks raise SystemExit(1); --live is network-dependent.

### False-success defect inventory

- CLI-001 src/tw_stock_tool/backtesting/parameter_sweep.py -- Standalone parameter sweep catches exceptions, prints, and falls through to None.
- CLI-002 src/tw_stock_tool/backtesting/strategy_compare.py -- Supported unified route maps caught failures returning None to status 0.
- CLI-003 src/tw_stock_tool/backtesting/walk_forward.py -- Standalone walk-forward catches exceptions, prints, and falls through to None.
- CLI-023 src/tw_stock_tool/ml/ai_stock_scanner.py -- Starting lead confirmed: caught error prints and unified None-to-0 reports success.
- CLI-025 src/tw_stock_tool/ml/baseline_ml_model.py -- Standalone caught failures print and fall through to process status 0.
- CLI-026 src/tw_stock_tool/ml/ml_dataset.py -- Standalone dataset command catches failures and optionally writes CSV.
- CLI-027 src/tw_stock_tool/reports/ai_prediction_report.py -- Standalone report catches failures and optionally writes Excel.

### Process-only review inventory

- CLI-010 src/tw_stock_tool/cli/daily_watchlist.py -- Standalone live/file-writing command with isolated SystemExit process behavior.
- CLI-022 src/tw_stock_tool/gui/gui_app.py -- Legacy Tk GUI is interactive and exposes live, file, cache-clear, and update callbacks.

### No-runtime-boundary inventory

- CLI-029 src/tw_stock_tool/utils/verify_batch.py -- Network/file-writing verifier has no callable exception-to-status boundary.

### Guard-only mismatch inventory

None as a canonical primary classification. Root guards were individually inspected; integer-return targets use raise SystemExit and direct-call wrappers target None-returning/process-only callables.

## Future batches

| Batch | Included CLI IDs | Shared defect pattern | Expected production files | Required tests | Risk | Order |
|---|---|---|---|---|---|---|
| BATCH_A_RETURN_CODE_NORMALIZATION | CLI-005, CLI-009, CLI-012, CLI-015, CLI-019, CLI-028 | return/raise normalization | the listed CLI modules | direct, unified, package guard and subprocess status tests | high | 2 |
| BATCH_B_FALSE_SUCCESS_FIXES | CLI-001, CLI-002, CLI-003, CLI-023, CLI-025, CLI-026, CLI-027 | caught errors fall through to None | the listed backtesting/ML/report modules | direct, unified, and process status tests | critical | 1 |
| BATCH_C_SPECIAL_PROCESS_LIVE_INTERACTIVE | CLI-010, CLI-022 | live/interactive/destructive process-only behavior | daily_watchlist and gui_app | offline fakes plus explicit manual exclusions | high | 4 |
| BATCH_D_WRAPPER_AND_GUARD_ALIGNMENT | none | wrapper/guard propagation if characterized | none currently | structural wrapper and subprocess tests | medium | 3 |
| DEFER_PENDING_DESIGN | CLI-029 | no callable runtime boundary | utils/verify_batch | design-specific characterization | high | deferred |

Recommended order: BATCH_B_FALSE_SUCCESS_FIXES, BATCH_A_RETURN_CODE_NORMALIZATION, BATCH_D_WRAPPER_AND_GUARD_ALIGNMENT, BATCH_C_SPECIAL_PROCESS_LIVE_INTERACTIVE. False success is first because it misleads scripts and CI.

## Shared contract-test architecture proposal

Future tests should centralize unified route metadata; parameterize None -> 0 and child 1 -> 1; assert sys.argv restoration even after exceptions; structurally check package guards; use subprocess process-code checks; explicitly exclude live and interactive commands; use deterministic offline bootstraps for data/file boundaries; and reject handled exceptions that silently produce status 0. Do not force materially different CLI/safety/artifact fixtures together. This proposal is not implemented.

## Validation and scope result

- JSON validation: PASS via py -m json.tool.
- Inventory consistency: PASS for all 19 routes, 1 console script, 41 root wrappers, 29 production guards, required fields, unique IDs, deterministic sort, and allowed enums.
- Safe CLI boundary tests: PASS, 56 tests.
- py -m unittest discover -s tests: PASS, 1,713 tests, 0 failures, 0 errors, 0 skips.
- python -m unittest discover -s tests: PASS, 1,713 tests, 0 failures, 0 errors, 0 skips.
- git diff --check: PASS.
- UTF-8 BOM: PASS for both files.
- Changed-file scope: exactly the two approved files.
- Ignored bytecode was not deleted; git clean was not run.
- No production code, existing test, README, config, dependency, wrapper, or existing documentation changed. No defect or batch fix was implemented.
- Commit/push result is completed after validation; exact SHA and remote status are recorded in the final handoff. Branch disposition: HOLD FOR REVIEW.

## Exact commands used

- git fetch origin
- git rev-parse HEAD
- git rev-parse refs/heads/main
- git rev-parse refs/remotes/origin/main
- git status --short --branch
- git switch -c track-c13-repository-wide-cli-runtime-contract-audit
- git ls-files '*.py'
- git grep -n 'sys.exit' -- '*.py'
- git grep -n 'raise SystemExit' -- '*.py'
- git grep -n 'def main' -- '*.py'
- git grep -n 'ArgumentParser' -- '*.py'
- git grep -n '__name__.*__main__' -- '*.py'
- git grep -n '\.main(' -- '*.py'
- Get-Command ponytail*
- py -m unittest tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes
- py -m unittest discover -s tests
- python -m unittest discover -s tests
- py -m json.tool docs/CLI_RUNTIME_CONTRACT_INVENTORY.json
- git diff --check
- git diff --stat
- git diff --name-only
- git status --short
- git ls-files --others --exclude-standard
- git ls-files '*.pyc' '*.pyo'

## Exact JSON result

docs/CLI_RUNTIME_CONTRACT_INVENTORY.json is the deterministic UTF-8 machine-readable inventory; required fields are present on every entrypoint record, with explicit non-CLI test guards.

Track C13 Repository-wide CLI Audit: PASS -- INVENTORY RECORDED
Branch disposition: HOLD FOR REVIEW
No production code was changed.
Batch fixes were not started.
