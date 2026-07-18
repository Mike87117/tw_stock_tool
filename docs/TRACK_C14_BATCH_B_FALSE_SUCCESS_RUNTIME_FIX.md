# Track C14 — Batch B False-Success Runtime Contract Fixes

## Executive outcome

PASS. Seven approved Batch B callables now return integer status 1 after handled runtime failures while preserving existing error text, stdout behavior, and successful implicit None. Four approved executable root wrappers now propagate delegated return values. No live request or unrelated runtime behavior changed.

## Formal implementation result

- Parent branch: track-c13-repository-wide-cli-runtime-contract-audit
- Parent HEAD: 629fc5dacffc9fa18920d00b7237b0f7b878254e (Fix C13 wrapper propagation inventory)
- Parent commits above main: 3c833004938ebe3a6be9ceaa34d976853bbef4e2, then 629fc5dacffc9fa18920d00b7237b0f7b878254e
- Main and origin/main: da32b3ef92eba08987307aa99ebac3f3afcb916d
- Merge base: da32b3ef92eba08987307aa99ebac3f3afcb916d
- Parent relationship: 2 commits ahead, 0 behind
- New branch: track-c14-batch-b-false-success-runtime-fixes

## Exact files changed

Package targets:

- src/tw_stock_tool/backtesting/parameter_sweep.py
- src/tw_stock_tool/backtesting/strategy_compare.py
- src/tw_stock_tool/backtesting/walk_forward.py
- src/tw_stock_tool/ml/ai_stock_scanner.py
- src/tw_stock_tool/ml/baseline_ml_model.py
- src/tw_stock_tool/ml/ml_dataset.py
- src/tw_stock_tool/reports/ai_prediction_report.py

Executable wrappers:

- ai_prediction_report.py
- ai_stock_scanner.py
- ml_dataset.py
- strategy_compare.py

Tests and report:

- tests/test_track_c14_batch_b_false_success_runtime_contract.py
- docs/TRACK_C14_BATCH_B_FALSE_SUCCESS_RUNTIME_FIX.md

No existing test file was modified. C13 inventory/report files, twstock_cli.py, Batch A targets, Batch C targets, import-only baseline_ml_model.py, packaging, and dependencies were not changed.

## C13 Batch B source inventory

| CLI ID | Package target | Result |
|---|---|---|
| CLI-001 | src/tw_stock_tool/backtesting/parameter_sweep.py | Return 1 and propagate through package guard |
| CLI-002 | src/tw_stock_tool/backtesting/strategy_compare.py | Return 1 in both existing handlers and propagate |
| CLI-003 | src/tw_stock_tool/backtesting/walk_forward.py | Return 1 and propagate through package guard |
| CLI-023 | src/tw_stock_tool/ml/ai_stock_scanner.py | Return 1 and propagate through package guard |
| CLI-025 | src/tw_stock_tool/ml/baseline_ml_model.py | Return 1 and propagate through package guard |
| CLI-026 | src/tw_stock_tool/ml/ml_dataset.py | Return 1 and propagate through package guard |
| CLI-027 | src/tw_stock_tool/reports/ai_prediction_report.py | Return 1 and propagate through package guard |

Wrapper alignment:

| Wrapper | Target | Result |
|---|---|---|
| ai_prediction_report.py | CLI-027 | raise SystemExit(_impl.main()) |
| ai_stock_scanner.py | CLI-023 | raise SystemExit(_impl.main()) |
| ml_dataset.py | CLI-026 | raise SystemExit(_impl.main()) |
| strategy_compare.py | CLI-002 | raise SystemExit(_impl.main()) |

## Runtime contract

Pre-fix: handled exceptions were printed, main fell through to None, and package/unified/root process boundaries reported status 0.

Post-fix:

- Successful execution remains implicit None.
- Every approved top-level handled runtime exception returns 1.
- No callable raises SystemExit(1) or calls sys.exit(1).
- All seven package guards use raise SystemExit(main()).
- Argparse-owned help 0 and usage/type failure 2 remain unchanged.
- Existing Error: and Unexpected error: wording remains unchanged.
- Error output remains stdout; no logging, traceback, or stream move was added.
- Success output, research-only messages, CSV/Excel/report boundaries, and model/backtest behavior remain unchanged.
- Baseline model per-window error rows remain unchanged.

## Unified behavior

Only strategy-compare and ai-scan are Batch B unified routes. The dispatcher was not modified. Tests verify child None to unified 0, child integer 1 to unified 1, parser SystemExit(2) propagation, original sys.argv restoration, child program names, and argument order. At least one failure test per route executes the corrected real target handler rather than replacing the child main.

## Shared acceptance-test architecture

tests/test_track_c14_batch_b_false_success_runtime_contract.py covers:

- direct success and handled failure for all seven targets;
- exact error prefixes, no traceback, no post-failure export call, and preserved success messages;
- help and parser-failure exits for every target;
- AST package-guard structure and int | None annotations;
- deterministic package-process success/failure/help/parser statuses;
- real target failure handlers through strategy-compare and ai-scan;
- unified function/process status and sys.argv restoration;
- all four root-wrapper statuses for delegated None and 1;
- import alias compatibility for all four wrappers;
- exclusion of Batch A, Batch C, dispatcher, C13 documents, and the import-only baseline wrapper.

All subprocesses patch execution boundaries and use offline deterministic values. No persistent CSV, Excel, cache, model, bootstrap, or report artifact remains.

## Existing-test updates

No existing test file was modified. Existing assertions remained valid; the new shared suite owns the seven corrected callable contracts, four wrapper propagations, and the two unified runtime routes.

## Direct callable test matrix

| Surface | Success | Handled failure | Output assertion |
|---|---:|---:|---|
| CLI-001, CLI-003, CLI-023, CLI-025, CLI-026, CLI-027 | None | 1 | Existing Error: text; no traceback or post-failure export |
| CLI-002 known ValueError/ReportError | None | 1 | Existing Error: text |
| CLI-002 unexpected exception | None | 1 | Existing Unexpected error: text |

## Package process test matrix

| Scope | Success | Handled failure | Help | Parser failure |
|---|---:|---:|---:|---:|
| All seven package targets | 0 | 1 | 0 | 2 |

## Unified function test matrix

| Route | Success | Handled failure | Parser failure | sys.argv |
|---|---:|---:|---:|---|
| strategy-compare | 0 | 1 | SystemExit(2) | Restored exactly |
| ai-scan | 0 | 1 | SystemExit(2) | Restored exactly |

## Unified process test matrix

| Route | Success | Handled failure | Parser failure |
|---|---:|---:|---:|
| strategy-compare | 0 | 1 | 2 |
| ai-scan | 0 | 1 | 2 |

## Root-wrapper process matrix

| Wrapper | Delegated None | Delegated 1 | Import alias |
|---|---:|---:|---|
| ai_prediction_report.py | 0 | 1 | PASS |
| ai_stock_scanner.py | 0 | 1 | PASS |
| ml_dataset.py | 0 | 1 | PASS |
| strategy_compare.py | 0 | 1 | PASS |

## Defect closure

| Defect | Canonical fix | Wrapper alignment | Closure |
|---|---|---|---|
| CLI-001 | Return 1 and guard propagation | None | PASS |
| CLI-002 | Both handlers return 1 | strategy_compare.py | PASS |
| CLI-003 | Return 1 and guard propagation | None | PASS |
| CLI-023 | Return 1 and guard propagation | ai_stock_scanner.py | PASS |
| CLI-025 | Return 1 and guard propagation | Import-only wrapper unchanged | PASS |
| CLI-026 | Return 1 and guard propagation | ml_dataset.py | PASS |
| CLI-027 | Return 1 and guard propagation | ai_prediction_report.py | PASS |

## Test results

- New shared suite: 11 tests, PASS.
- Related existing suites: 82 tests, PASS.
- Root-wrapper suites: 8 tests, PASS.
- Unified CLI suite: 48 tests, PASS.
- Combined Batch B suite: 149 tests, PASS.
- py -m unittest discover -s tests: 1,724 tests, PASS.
- python -m unittest discover -s tests: 1,724 tests, PASS.
- Expected failures: 0.
- Unexpected successes: 0.
- Skips: 0.
- Failures: 0.
- Errors: 0.

No live/manual smoke-check CLI, network request, model download, broker call, order operation, interactive prompt, force refresh, official stock-list update, or cache clear was executed.

## Git and artifact validation

- git diff --check: PASS.
- UTF-8 without BOM: PASS for every changed/added text file.
- Changed-file gate: PASS; only the seven package targets, four wrappers, one new test, and this report are in scope.
- C13 inventory/report: unchanged.
- twstock_cli.py: unchanged.
- No tracked .pyc or .pyo files.
- Ignored bytecode was allowed and not deleted.
- No persistent generated artifact remains.
- Working tree: clean after commit.

## Commit and disposition

One intentional implementation commit was created with message Fix Batch B false-success CLI runtime exits and pushed to track-c14-batch-b-false-success-runtime-fixes. The branch remains unmerged for review. No merge or pull request was created. Batch A, Batch C, and deferred design work were not started.

## Exact validation commands

- git fetch origin
- git checkout track-c13-repository-wide-cli-runtime-contract-audit
- git checkout -b track-c14-batch-b-false-success-runtime-fixes
- py -m unittest tests.test_track_c14_batch_b_false_success_runtime_contract
- py -m unittest tests.test_parameter_sweep tests.test_strategy_compare tests.test_walk_forward tests.test_ai_stock_scanner tests.test_baseline_ml_model tests.test_ml_dataset tests.test_ai_prediction_report
- py -m unittest tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes
- py -m unittest tests.test_twstock_cli
- py -m unittest tests.test_track_c14_batch_b_false_success_runtime_contract tests.test_parameter_sweep tests.test_strategy_compare tests.test_walk_forward tests.test_ai_stock_scanner tests.test_baseline_ml_model tests.test_ml_dataset tests.test_ai_prediction_report tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_twstock_cli
- py -m unittest discover -s tests
- python -m unittest discover -s tests
- git diff --check
- git diff --stat
- git diff --name-only
- git status --short
- git ls-files --others --exclude-standard
- git ls-files "*.pyc" "*.pyo"

Batch A was not started.
