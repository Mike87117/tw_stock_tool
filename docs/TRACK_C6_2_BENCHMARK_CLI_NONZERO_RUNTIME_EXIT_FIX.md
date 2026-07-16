# Track C6.2 Benchmark CLI Nonzero Runtime Exit Fix

## Executive outcome

Track C6.2 resolves the six Benchmark false-success boundaries confirmed by C6.1. Benchmark callable handled failures now return `1` while successful direct execution remains legacy `None`. The package module and root wrapper propagate callable status through `SystemExit`. The unchanged unified dispatcher consequently returns and exits `1` for Benchmark failures.

Existing error wording, stdout ownership, argparse behavior, root import aliasing, benchmark computation, output paths, CSV contents, and CSV encoding are unchanged. No live scan or CSV generation occurred.

Formal result: `Track C6.2 Implementation: PASS -- READY FOR REVIEW`

## Repository and stacked-branch baseline

- Repository: `Mike87117/tw_stock_tool`
- `main`: `71146c4b1fa155affc707b29dc2bb29d7cf6caf3`
- `origin/main`: `71146c4b1fa155affc707b29dc2bb29d7cf6caf3`
- Parent branch: `track-c6-1-benchmark-cli-runtime-exit-characterization`
- Parent SHA: `3fabf23cd07134137da2c6d7620824a214d34686`
- Parent relationship to main: ahead 1, behind 0
- C6.2 branch initial relationship: ahead 1, behind 0
- Parent suite: 1,537 run; 1,531 passed; 6 expected failures; 0 failures; 0 errors
- `custom_md.md`: present, unread, unmodified, untracked, and ignored only by `.git/info/exclude`

## LLM Wiki result

- Health: available; `ok: true`, `status: running`
- Version: `0.5.4`
- Active project: `tw_stock_tool Wiki`
- Search: `Track C6.1 Benchmark CLI nonzero runtime exit package root SystemExit unified propagation`
- Summary: 10 keyword-result documents and 12 token hits. The Wiki provided supporting CLI and project context only; repository source, tests, and C6.1 evidence remained authoritative.

## Confirmed defects

C6.1 directly confirmed that Benchmark validation and unexpected runtime failures returned `None`; the package module, root wrapper, unified function, and unified module therefore reported success status `0`. The six expected-failure contracts were the direct callable statuses and the five affected process/dispatcher boundaries.

## Approved behavior contract

- Successful direct Benchmark execution remains `None`.
- Handled validation and runtime failures return `1` after printing the existing `Error: {exc}` text.
- Package and root executable guards use `raise SystemExit(main())` or its wrapper equivalent.
- Package, root, and unified invalid options remain argparse exit `2`.
- Root `benchmark` import remains the package-module alias.
- Unified dispatch propagates Benchmark integer `1` without modification.
- No callable raises `SystemExit` for handled runtime errors.

## Implementation scope

Only the approved files were changed:

- `src/tw_stock_tool/cli/benchmark.py`: return annotation, handled-error `return 1`, and package `SystemExit` guard.
- `benchmark.py`: root executable `SystemExit` propagation with import alias preserved.
- `tests/test_track_c6_1_benchmark_cli_runtime_exit_behavior.py`: activate six contracts, update six observations, and catch root `SystemExit(None)`.
- `docs/TRACK_C6_2_BENCHMARK_CLI_NONZERO_RUNTIME_EXIT_FIX.md`: this record.

The unified dispatcher, Benchmark computation, input validation, output-path construction, CSV behavior, argument names, Scanner, Cache Manager, and all unrelated files were left unchanged.

## Direct success result

The synthetic offline Benchmark success test still returns `None`, calls `run_benchmark()` once with the expected arguments, prints Summary, Detail, and Errors, and creates no artifact. No explicit success `return 0` was added.

## Direct validation-failure result

Calling real `benchmark.main()` without stocks still prints `Error: benchmark stock list cannot be empty.` without a traceback, performs no scan, does not call `_output_paths()`, preserves the temporary filesystem, and now returns `1`.

## Direct runtime-failure result

With only `run_benchmark()` raising `RuntimeError("controlled benchmark failure")`, the existing `Error: controlled benchmark failure` text remains on stdout, no traceback appears, no output path or CSV work occurs, and direct `main()` now returns `1`.

## Package-module result

`python -m tw_stock_tool.cli.benchmark` with no stocks reports the existing validation error without a traceback and exits `1` through `raise SystemExit(main())`.

## Root-wrapper result

`python benchmark.py` with no stocks invokes Benchmark, preserves the existing error text and no-traceback behavior, and exits `1` through `raise SystemExit(_impl.main())`. Root import compatibility remains unchanged.

## Unified function result

`twstock_cli.main(["benchmark"])` invokes the real Benchmark child, restores `sys.argv`, preserves output and artifact behavior, and now returns `1`. `tw_stock_tool.cli.twstock_cli` was not modified.

## Unified module result

`python -m tw_stock_tool.cli.twstock_cli benchmark` reports the existing validation error without a traceback and exits `1` because the unchanged dispatcher propagates the corrected child integer.

## Argparse preservation

Package, root, and unified invalid Benchmark options remain parser-owned exit `2` with usage/error output and no traceback. No parser argument or behavior changed.

## Root import compatibility

`import benchmark` remains the same module object as `tw_stock_tool.cli.benchmark`, with the same `main` callable. The root executable change is isolated to the `__main__` branch.

## Regression-test adaptation

The six C6.1 expected-failure decorators were removed without weakening assertions. Six old observation tests now assert the corrected direct/process status while retaining visibility, no-traceback, no-scan, no-output-path, artifact, invocation, and `sys.argv` checks. The root `runpy` control now catches `SystemExit` and asserts `SystemExit(None)` for a patched successful `main()`.

The C6 module remains exactly 19 tests.

## Expected-failure resolution

Expected failures changed from 6 to 0. All six confirmed C6.1 defect contracts are now ordinary passing regression tests. No success, argparse, import, sibling, or inference case was changed into an expected failure.

## Production files changed

- `src/tw_stock_tool/cli/benchmark.py`
- `benchmark.py`

## Test files changed

- `tests/test_track_c6_1_benchmark_cli_runtime_exit_behavior.py`

All 19 C6 tests pass with zero expected failures.

## Documentation files changed

- `docs/TRACK_C6_2_BENCHMARK_CLI_NONZERO_RUNTIME_EXIT_FIX.md`

## Validation commands

```powershell
py -m unittest tests.test_track_c6_1_benchmark_cli_runtime_exit_behavior
# 19 run; 19 passed; 0 expected failures; 0 failures; 0 errors; OK

py -m unittest tests.test_track_c6_1_benchmark_cli_runtime_exit_behavior tests.test_benchmark tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior tests.test_track_c4_1_scanner_cli_exit_behavior
# 113 run; 113 passed; 0 expected failures; 0 failures; 0 errors; OK

py -m unittest discover -s tests
# 1,537 run; 1,537 passed; 0 expected failures; 0 failures; 0 errors; OK

python -m unittest discover -s tests
# 1,537 run; 1,537 passed; 0 expected failures; 0 failures; 0 errors; OK
```

`git diff --check` passed. The four authorized changed files are UTF-8 without BOM. No live scan, Benchmark CSV, or output directory was created. No ignored artifact entered the commit.

## Deferred related candidates

- Clean Stocks CLI runtime exit behavior.
- Stock List Updater CLI runtime exit behavior.

Both remain outside C6.2.

## Non-goals

No unified dispatcher modification, Scanner or Cache Manager change, Benchmark computation change, CSV behavior change, parser change, dependency addition, ignore-rule change, C6.1 document change, live market-data access, real CSV generation, merge, or main push was performed. Retained ignored artifacts remained non-blocking and `custom_md.md` was not read or changed.

## Recommended next action

Submit this bounded branch for production review. If approved, include it in a separate aggregate merge audit; do not merge during this task.

Branch disposition: `READY FOR REVIEW`.
