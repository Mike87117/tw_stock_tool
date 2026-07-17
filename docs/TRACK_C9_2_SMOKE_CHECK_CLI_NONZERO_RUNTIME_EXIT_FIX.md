# Track C9.2 Smoke Check CLI Nonzero Runtime Exit Fix

## Executive outcome

Track C9.2 applied the smallest production fix for the six runtime-status
defects directly confirmed by Track C9.1. Both smoke-check package `main()`
functions now return integer `1` for handled failures while preserving legacy
successful direct `None`. Their package guards and root wrappers propagate the
result through `SystemExit`, and the existing unified dispatcher now returns
integer `1` without any dispatcher change. Existing output, validation,
provider behavior, import compatibility, `sys.argv` restoration, and argparse
status `2` are preserved.

## Formal result

`Track C9.2 Implementation: PASS -- READY FOR REVIEW`

## Repository and stacked-branch baseline

- Repository: `Mike87117/tw_stock_tool`
- C9.2 branch: `track-c9-2-smoke-check-cli-nonzero-runtime-exit-fix`
- Parent branch: `track-c9-1-smoke-check-cli-runtime-exit-characterization`
- C9.2 was created directly from the verified C9.1 parent.
- Starting C9.2 working tree: clean.
- Starting C9.2 branch relationship to `main`: `0` behind, `1` ahead.
- The user-owned ignored `custom_md.md` was not inspected, modified, deleted,
  staged, or cleaned.
- No `git clean` command was run.

## Parent commit and branch confirmation

The required parent was confirmed exactly before changes:

```text
02a276a2e31df8cc1a20039095ddde91802fe976
```

The checked-out parent branch was:

```text
track-c9-1-smoke-check-cli-runtime-exit-characterization
```

`git fetch origin` completed before verification. The C9.2 branch was then
created directly from that parent commit.

## Parent test results

The C9.1 parent report recorded these actual results:

- Targeted: 24 run; 18 passed; 6 expected failures; 0 ordinary failures; 0
  errors.
- Combined: 92 run; 86 passed; 6 expected failures; 0 ordinary failures; 0
  errors.
- Canonical full suite: 1,599 run; 1,593 passed; 6 expected failures; 0
  ordinary failures; 0 errors.
- Secondary full suite: 1,599 run; 1,593 passed; 6 expected failures; 0
  ordinary failures; 0 errors.

## Working-tree and ignored-file protection result

Only the six approved C9.2 paths were changed relative to the parent: four
production entry points, the existing characterization test module, and the
new C9.2 report. The historical C9.1 report was not modified. No ignored-file
inspection, deletion, staging, or cleanup was performed for `custom_md.md`.

## LLM Wiki availability result

No LLM Wiki connector was available in this execution environment. The Wiki
check was unavailable and non-blocking; repository source, tests, and Git
history were used as authoritative evidence.

## Six confirmed C9.1 defects resolved

### Stock List Smoke Check

- `C9.1-SLSC-02`: handled direct failure raised `SystemExit(1)` instead of
  returning integer `1`.
- `C9.1-SLSC-05`: the root executable wrapper ignored a patched child return
  value of `1`.
- `C9.1-SLSC-06`: unified function invocation raised `SystemExit(1)` instead
  of returning integer `1`.

### Price Data Smoke Check

- `C9.1-PDSC-02`: handled direct failure raised `SystemExit(1)` instead of
  returning integer `1`.
- `C9.1-PDSC-05`: the root executable wrapper ignored a patched child return
  value of `1`.
- `C9.1-PDSC-06`: unified function invocation raised `SystemExit(1)` instead
  of returning integer `1`.

No additional defect classification was introduced.

## Approved behavior contract

- Successful direct `main()` calls continue returning implicit `None`.
- Handled validation or runtime failures return integer `1`.
- Package-module execution exits with status `1` for handled failures.
- Root-wrapper execution exits with status `1` for handled failures.
- Unified CLI function calls return integer `1` for handled failures.
- Unified CLI module execution exits with status `1`.
- Argparse-owned failures remain status `2`.
- Existing output, validation, provider behavior, import compatibility, and
  `sys.argv` restoration remain unchanged.

## Exact C9.2 scope

The production change is limited to:

1. Returning `1` from the existing handled-exception blocks in the two smoke-
   check package `main()` functions.
2. Updating both package executable guards to `raise SystemExit(main())`.
3. Updating both root executable branches to `raise SystemExit(_impl.main())`.
4. Adapting the existing 24-test characterization module so the six former
   expected failures are ordinary passing contract tests.
5. Creating this report.

`src/tw_stock_tool/cli/twstock_cli.py` was not modified because its existing
dispatcher already maps `None` to `0`, propagates integer child statuses, and
restores `sys.argv`.

## Stock-list direct success result

The real package `main()` was run with deterministic mocked success data: 250
TWSE rows and 250 TPEx rows, including expected stocks `2317`, `2330`, and
`8069`. It continued returning `None`, printed the existing PASS report with
counts `250`, `250`, and `500`, made no provider request, produced no
traceback, and created no artifact.

## Stock-list direct handled-failure result

The real validation path was run with deterministic small TWSE/TPEx frames.
The existing failure output was preserved, the function now returned integer
`1`, no traceback was produced, `requests.get` was not called, and no artifact
was created.

## Price-data direct success result

The real package `main()` was run with deterministic valid OHLCV data and
valid `.TW`/`.TWO` symbols. It continued returning `None`, printed four
existing PASS rows, called the patched loader four times, made no network or
yfinance request, produced no traceback, and created no artifact.

## Price-data direct handled-failure result

The real four-check validation path was run with deterministic empty
DataFrames. It preserved the existing FAIL rows and aggregate error output,
returned integer `1`, called the patched loader four times, made no network or
yfinance request, produced no traceback, and created no artifact.

## Package-module results

The package stock-list module and price-data module each propagated their
handled return value through `raise SystemExit(main())` and exited with status
`1`. Existing failure output remained visible and no traceback or persistent
artifact was produced.

## Root-wrapper process results

Both root wrappers now propagate the package return value through
`raise SystemExit(_impl.main())`. Stock-list and price-data handled-failure
subprocesses each exited with status `1`, preserved existing output, produced
no traceback, and created no persistent artifact.

## Root `runpy` propagation results

For each root wrapper, the package `main()` was patched to return integer `1`
and executed once through `runpy.run_path(..., run_name="__main__")`. Each
wrapper raised `SystemExit(1)` and verified exactly one package-main call.
Import-alias behavior was not changed.

## Unified-function results

The existing dispatcher required no change. With package `main()` now
returning `1`, both `twstock_cli.main(["stock-list", "smoke-check"])` and
`twstock_cli.main(["price-smoke-check"])` returned integer `1`. Existing
failure output and provider call assertions remained unchanged, and `sys.argv`
was restored exactly after each call.

## Unified-module results

Both unified module routes exited with status `1` for handled failures. Their
visible failure output and no-traceback/no-artifact assertions passed.

## Argparse preservation

Package, root-wrapper, and unified invalid-option controls for both commands
continued to produce usage/error output with status `2`, no traceback, and no
provider request. No parser code or argument behavior changed.

## Root import compatibility

Both root wrappers continued resolving to the same package module objects and
the same `main` callables. Importing either root wrapper did not execute the
CLI, and the import-alias branches were not changed.

## Offline network-isolation result

The targeted characterization tests retained deterministic offline controls.
Direct and unified-function tests patched the relevant stock-list fetch or
price-data loader callables and patched network/yfinance tripwires. Subprocess
tests used temporary `sitecustomize.py` controls first in `PYTHONPATH`,
`sys.executable`, repository-root working directory, captured stdout/stderr,
`check=False`, preserved `PYTHONPATH`, and
`PYTHONDONTWRITEBYTECODE=1`. No live market service was accessed.

## Filesystem-artifact result

The targeted tests left their temporary directories unchanged and removed all
temporary helper directories after each test. No stock-list, cache, report, or
output artifact was created by the characterization tests. The full validation
completed without a persistent C9.2 artifact.

## Regression-test adaptation

The existing characterization module was adapted in place. Exactly six
`@unittest.expectedFailure` decorators were removed. The direct handled-failure
tests now assert `("return", 1)`, the root `runpy` tests now assert
`("system_exit", 1)` and one package-main call, and the unified-function tests
now assert `("return", 1)` with exact `sys.argv` restoration. The existing
success, output, provider, artifact, process, parser, and import assertions
were preserved. The 24-test matrix was retained.

## Expected-failure resolution

The six former expected failures now pass as ordinary tests. The targeted
module has zero expected failures, zero ordinary failures, and zero errors.

## Production files changed

- `src/tw_stock_tool/cli/stock_list_smoke_check.py`
- `src/tw_stock_tool/cli/price_data_smoke_check.py`
- `stock_list_smoke_check.py`
- `price_data_smoke_check.py`

## Test file changed

- `tests/test_track_c9_1_smoke_check_cli_runtime_exit_behavior.py`

## Documentation file created

- `docs/TRACK_C9_2_SMOKE_CHECK_CLI_NONZERO_RUNTIME_EXIT_FIX.md`

The historical C9.1 characterization report was not modified.

## Exact targeted test result

```text
py -m unittest tests.test_track_c9_1_smoke_check_cli_runtime_exit_behavior
24 run; 24 passed; 0 expected failures; 0 failures; 0 errors; OK
```

## Exact combined test result

```text
py -m unittest tests.test_track_c9_1_smoke_check_cli_runtime_exit_behavior tests.test_stock_list_smoke_check tests.test_price_data_smoke_check tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes
92 run; 92 passed; 0 expected failures; 0 failures; 0 errors; OK
```

## Exact canonical full-suite result

```text
py -m unittest discover -s tests
1599 run; 1599 passed; 0 expected failures; 0 failures; 0 errors; OK
```

## Secondary Python full-suite result

```text
python -m unittest discover -s tests
1599 run; 1599 passed; 0 expected failures; 0 failures; 0 errors; OK
```

## `git diff --check` result

`git diff --check` passed with no output; the staged equivalent also passed.

## UTF-8 BOM result

All six changed/new text files decoded as UTF-8 and reported `BOM=False`.

## Explicit non-goals

No validation thresholds, expected stock IDs, provider or fallback behavior,
HTTP/yfinance handling, result collection, output wording, output channels,
argument parsing, exception coverage, dispatcher logic, wrapper architecture,
aliases, command names, flags, successful return behavior, argparse behavior,
dependencies, configuration, or shared abstractions were changed. No live
market service, persistent artifact, Ponytail audit, merge, rebase, squash,
force-push, C9.3 work, or later track was started.

## No-merge statement

C9.2 is limited to one intentional commit pushed to the production branch.
The branch will not be merged.

## Branch disposition

`READY FOR REVIEW`
