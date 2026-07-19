# Track C15 - Consolidated Runtime Return-Code Normalization

## Executive result

PASS. The six approved package entrypoints now return status `1` for handled runtime failures, and their six root wrappers propagate that status through `SystemExit`. Successful execution remains status `0` at the process boundary.

## Formal result

- Scope: Track C15 Batch A only.
- Branch: `stability-c15-consolidated-runtime-batch`.
- Starting base commit: `bd5d56e56714d9872c75137c7bfe6088356ad5fb`
- Original implementation commit: `3118ca16b1b182d8bae17c3d9aed82b5bcc89270`.
- The branch remains unmerged; `main` is unchanged.
- This follow-up corrects the handoff documentation only. The documentation-fix commit hash is reported in the final handoff after commit creation.
- No dispatcher, workflow, dependency, Batch B, or Batch C changes were made.

## Approved files

Package targets:

- `src/tw_stock_tool/cli/backtest_report.py`
- `src/tw_stock_tool/cli/daily_report_cli.py`
- `src/tw_stock_tool/cli/parameter_sweep_report.py`
- `src/tw_stock_tool/cli/simulated_paper_trading_cli.py`
- `src/tw_stock_tool/cli/walk_forward_report.py`
- `src/tw_stock_tool/utils/doctor.py`

Root wrappers:

- `backtest_report.py`
- `doctor.py`
- `parameter_sweep.py`
- `parameter_sweep_report.py`
- `walk_forward.py`
- `walk_forward_report.py`

No other production path was changed. Existing test updates are limited to the five permitted CLI test modules. New contract coverage is `tests/test_track_c15_batch_a_return_code_normalization.py`.

## Behavior contract

All six package `main` functions annotate `int | None`. Success preserves existing output and returns `None` to direct callers. Handled runtime failures preserve `Error: ...` output and return `1`. Argparse help remains `0` and invalid usage remains `SystemExit(2)`.

All six package guards use `raise SystemExit(main())`. All six wrappers propagate the delegated result. Import compatibility for `parameter_sweep.py`, `walk_forward.py`, and `doctor.py` is unchanged.

Unified routes were tested without changing `twstock_cli.py`: success is `0`, handled runtime failure is `1`, help is `0`, invalid usage is `2`, and `sys.argv` is restored after callable dispatch.

Existing error text, streams, success output, report paths, and offline behavior are preserved. No live or manual command was used.

## Defects closed

| Defect | Result |
| --- | --- |
| CLI-005 | Package failure returns `1` and the guard propagates it. |
| CLI-009 | Daily no-stock and runtime failures return `1`. |
| CLI-012 | Parameter-sweep runtime and preflight failures return `1`. |
| CLI-015 | Simulated-paper ordinary failures return `1`; parser `SystemExit` is preserved. |
| CLI-019 | Walk-forward runtime failures return `1`. |
| CLI-028 | Doctor failure status returns `1` and the guard propagates it. |

## Verification

Observed results from the required `py` commands:

| Test group | Command result |
| --- | ---: |
| Focused C15 contract suite | 13 passed |
| Related CLI and doctor suites | 122 passed |
| Root wrapper and unified CLI suites | 56 passed |
| C14 and data-loader regressions | 59 passed |
| Required combined targeted matrix | 250 passed |
| Full test suite | 1,737 passed |

The four individual targeted groups are non-overlapping for these commands, so their sum is 250. In general, targeted-group counts should not be added when commands overlap.

Commands executed:

```powershell
py -m unittest tests.test_track_c15_batch_a_return_code_normalization
py -m unittest tests.test_backtest_report_cli tests.test_daily_report_cli tests.test_parameter_sweep_report_cli tests.test_simulated_paper_trading_cli tests.test_walk_forward_report_cli tests.test_doctor
py -m unittest tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_twstock_cli
py -m unittest tests.test_track_c14_batch_b_false_success_runtime_contract tests.test_data_loader
py -m unittest tests.test_track_c15_batch_a_return_code_normalization tests.test_backtest_report_cli tests.test_daily_report_cli tests.test_parameter_sweep_report_cli tests.test_simulated_paper_trading_cli tests.test_walk_forward_report_cli tests.test_doctor tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_twstock_cli tests.test_track_c14_batch_b_false_success_runtime_contract tests.test_data_loader
py -m unittest discover -s tests
```

`git diff --check` passed. No generated CSV, Excel, Markdown output, cache, model, bootstrap, or temporary helper is part of the change.

## Handoff

The implementation commit is `3118ca16b1b182d8bae17c3d9aed82b5bcc89270`. The documentation correction is committed separately on `stability-c15-consolidated-runtime-batch`; its final commit hash is included in the final handoff report after commit creation. The branch is pushed with upstream tracking.

Disposition: HOLD FOR REVIEW. Merge was not performed. Batch C was not started. No pull request, history rewrite, force push, or branch deletion was performed.

Final workflow commands:

```powershell
git status --short
py -m unittest discover -s tests
git diff --check
git add docs/TRACK_C15_BATCH_A_RETURN_CODE_NORMALIZATION.md
git commit -m "Correct C15 handoff documentation"
git push
```
