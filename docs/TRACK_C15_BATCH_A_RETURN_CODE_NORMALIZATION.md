# Track C15 ? Batch A Return-Code Normalization

## Executive result

PASS. Batch A normalizes false-success runtime status for the six approved package entrypoints and six approved root wrappers. Direct runtime failures return 1; package guards and wrappers propagate that status through SystemExit.

## Formal result

- Scope: Track C15 Batch A only.
- Branch: track-c15-batch-a-return-code-normalization.
- Base: main at bd5d56e56714d9872c75137c7bfe6088356ad5fb.
- Main remains unchanged; the C15 branch remains unmerged for review.
- C14 72b244b1e6918a1672b122aa2a893c45f8e7d4ab and C14.1 cfd0e3820c43bb53ef42d9e4780b8d54266d1a92 ancestry was preserved.
- No dispatcher, workflow, dependency, Batch B, or Batch C changes were made.

## Approved files

Package targets:

- src/tw_stock_tool/cli/backtest_report.py
- src/tw_stock_tool/cli/daily_report_cli.py
- src/tw_stock_tool/cli/parameter_sweep_report.py
- src/tw_stock_tool/cli/simulated_paper_trading_cli.py
- src/tw_stock_tool/cli/walk_forward_report.py
- src/tw_stock_tool/utils/doctor.py

Root wrappers:

- backtest_report.py
- doctor.py
- parameter_sweep.py
- parameter_sweep_report.py
- walk_forward.py
- walk_forward_report.py

No other production path was changed. Existing test updates are limited to the five permitted CLI test modules. New contract coverage is tests/test_track_c15_batch_a_return_code_normalization.py.

## Behavior contract

All six package main functions now annotate int | None. Success preserves existing output and returns None to direct callers. Handled runtime failures preserve Error: ... output and return 1. Argparse help remains 0 and invalid usage remains SystemExit(2).

All six package guards use raise SystemExit(main()). All six wrappers propagate the delegated result. Import compatibility for parameter_sweep.py, walk_forward.py, and doctor.py is unchanged.

daily_report_cli returns 1 for no stocks and ordinary runtime exceptions. It no longer uses sys.exit for those paths. simulated_paper_trading_cli re-raises parser SystemExit and returns 1 for ordinary runtime failures. doctor.main returns 1 when checks contain failures and preserves local and mocked-live behavior.

Unified routes were tested without changing twstock_cli.py: success process status is 0, handled runtime failure is 1, help is 0, invalid usage is 2, and sys.argv is restored after callable dispatch.

Existing error text, streams, success output, report paths, and offline behavior are preserved. No live or manual command was used.

## Defects closed

| Defect | Result |
| --- | --- |
| CLI-005 | package failure returns 1 and guard propagates it |
| CLI-009 | daily no-stock and runtime failures return 1 |
| CLI-012 | parameter sweep runtime and preflight failures return 1 |
| CLI-015 | simulated paper ordinary failures return 1; parser SystemExit preserved |
| CLI-019 | walk-forward runtime failures return 1 |
| CLI-028 | doctor failure status returns 1 and guard propagates it |

## Verification

The new suite is table-driven over six package targets and six wrappers. It covers direct callable success/failure, exact error markers, false-success absence, parser help/usage, subprocess status, package guards, wrapper propagation, unified dispatch, argv restoration, doctor status, and exact in-memory scope inventory.

Observed results:

| Matrix | Result |
| --- | --- |
| Focused C15 contract suite | 13 passed |
| Related CLI and doctor suites | 122 passed |
| Root wrapper and unified suites | 56 passed |
| C14 and data-loader regressions | 59 passed |
| Required combined C15 matrix | 250 passed |
| Full python -m unittest discover -s tests | 1737 passed |

Commands executed:

    py -m unittest tests.test_track_c15_batch_a_return_code_normalization
    py -m unittest tests.test_backtest_report_cli tests.test_daily_report_cli tests.test_parameter_sweep_report_cli tests.test_simulated_paper_trading_cli tests.test_walk_forward_report_cli tests.test_doctor
    py -m unittest tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_twstock_cli
    py -m unittest tests.test_track_c14_batch_b_false_success_runtime_contract tests.test_data_loader
    py -m unittest tests.test_track_c15_batch_a_return_code_normalization tests.test_backtest_report_cli tests.test_daily_report_cli tests.test_parameter_sweep_report_cli tests.test_simulated_paper_trading_cli tests.test_walk_forward_report_cli tests.test_doctor tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_twstock_cli tests.test_track_c14_batch_b_false_success_runtime_contract tests.test_data_loader
    python -m unittest discover -s tests

git diff --check passed. Text artifacts are UTF-8 without BOM. No generated CSV, Excel, Markdown output, cache, model, bootstrap, or temporary helper is part of the change. Ignored Python bytecode was left untouched. custom_md.md was not inspected, modified, staged, deleted, restored, or cleaned.

## Handoff

The final changed-file gate is restricted to the 12 approved production/wrapper files, five permitted existing tests, this report, and the new C15 suite. The implementation uses one commit with message Normalize Batch A CLI runtime return codes. The final hash is recorded in the handoff after commit creation, and the branch is pushed with upstream tracking.

Disposition: HOLD FOR REVIEW. Merge was not performed. Batch C was not started. No pull request, history rewrite, force push, or branch deletion was performed.

Final workflow commands:

    git status
    python -m unittest discover -s tests
    git add approved C15 paths
    git commit -m Normalize Batch A CLI runtime return codes
    git push -u origin track-c15-batch-a-return-code-normalization
