# Track C8.2 Stock List Updater CLI Nonzero Runtime Exit Fix

## Executive outcome

Track C8.2 applies the smallest approved production fix for the six
false-success boundaries confirmed by C8.1. Handled validation/runtime failures
now return `1`; package and root executable guards propagate that status through
`SystemExit`; the unchanged unified dispatcher propagates integer `1`.
Successful direct execution remains legacy `None`, and parser failures remain
status `2`.

## Formal result

`Track C8.2 Implementation: PASS -- READY FOR REVIEW`

## Repository and stacked-branch baseline

- Repository: `Mike87117/tw_stock_tool`
- `main` and `origin/main`: `c6a666de6a756fa32efa3716eebfe75e5fa0eedf`
- Parent branch: `track-c8-1-stock-list-updater-cli-runtime-exit-characterization`
- Parent SHA: `790c5d39a8ffb096fca6297daefa12338e0c7b86`
- Production branch: `track-c8-2-stock-list-updater-cli-nonzero-runtime-exit-fix`
- Branch was created directly from the corrected C8.1 parent; initial relation
  was 0 behind and 0 ahead of the parent.

## Parent test results

Before branching, both parent suites passed:

```text
py -m unittest discover -s tests
1575 run; 1569 passed; 6 expected failures; 0 ordinary failures; 0 errors; OK

python -m unittest discover -s tests
1575 run; 1569 passed; 6 expected failures; 0 ordinary failures; 0 errors; OK
```

## custom_md.md protection result

`custom_md.md` remained present and unread. It remains ignored through the exact
root entry `/custom_md.md` in `.git/info/exclude`. No `git clean` command was
executed, and `.gitignore` was not modified.

## LLM Wiki result

No LLM Wiki connector was available in this environment. Wiki context was
therefore unavailable and non-blocking; repository source, tests, and Git
history remain authoritative.

## Six confirmed defects from C8.1

C8.1 directly confirmed false success for direct validation failure, direct
controlled runtime failure, package validation failure, root validation
failure, unified function validation failure, and unified module validation
failure. The six C8.1 expected failures required status/exit `1`.

## Approved behavior contract

- Successful direct `main()` execution remains implicit `None`.
- Handled validation/runtime failures return integer `1`.
- Package execution uses `raise SystemExit(main())`.
- Root execution uses `raise SystemExit(_impl.main())`.
- Argparse-owned failures remain `SystemExit(2)`.
- Unified integer child statuses propagate unchanged; only child `None` maps to
  `0`.
- Root import alias compatibility remains intact.

## Exact C8.2 scope

Only these four files changed relative to the corrected C8.1 parent:

- `src/tw_stock_tool/data/stock_list_updater.py`
- `stock_list_updater.py`
- `tests/test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior.py`
- `docs/TRACK_C8_2_STOCK_LIST_UPDATER_CLI_NONZERO_RUNTIME_EXIT_FIX.md`

The C8.1 historical document, unified dispatcher, existing Stock List Updater
tests, configuration, dependencies, and all other production files were not
modified.

## Direct success result

The synthetic success control still returns `None`, prints the existing
`Stock list updated:` and `Stocks: 1` output, calls the updater once with the
parsed values, makes no request, and creates no artifact.

## Direct validation result

The deterministic one-row TWSE validation path preserves
`Error: Abnormally few common stocks parsed: 1 < 100.`, leaves the temporary
filesystem unchanged, makes no HTTP request, and now returns `1`.

## Direct controlled runtime result

The controlled `RuntimeError("controlled stock list updater failure")` path
preserves its error wording, no traceback, no artifact, and one invocation; it
now returns `1`.

## Package-module result

`python -m tw_stock_tool.data.stock_list_updater --market twse --output
<temporary path>` preserves the deterministic validation error and no-output
assertions, and now exits `1` through `raise SystemExit(main())`.

## Root-wrapper result

`python stock_list_updater.py --market twse --output <temporary path>` preserves
the validation error, no traceback, and no artifact, and now exits `1` through
`raise SystemExit(_impl.main())`.

## Root `runpy` result

With package `main()` patched to return `1`, the root `runpy` control now catches
`SystemExit`, asserts code `1`, and confirms package `main()` is called exactly
once. The package module remains the resolved implementation.

## Unified-function result

The real `twstock_cli.main(["stock-list", "update", ...])` path preserves error
wording, no-output and no-request assertions, TPEx non-use, and exact
`sys.argv` restoration; it now returns `1`.

## Unified-module result

`python -m tw_stock_tool.cli.twstock_cli stock-list update --market twse
--output <temporary path>` preserves offline validation behavior and no
artifact, and now exits `1`.

## Argparse preservation

Package, root, and unified invalid-option controls continue to produce usage
and error output with exit status `2`. No parser code or `SystemExit` handling
was changed.

## Root import compatibility

Root `stock_list_updater` and package
`tw_stock_tool.data.stock_list_updater` remain the same module object with the
same `main` callable. Importing the root wrapper does not execute the CLI.

## Offline network isolation result

Direct tests patch fetch/update callables and `requests.get`. Package, root,
and unified subprocess tests preserve the temporary `sitecustomize.py` helper,
which patches `requests.get` before execution and returns exactly one valid
TWSE record. The helper directory is temporary, `PYTHONDONTWRITEBYTECODE=1` is
preserved, `sys.executable` and repository-root working directory are used,
and existing `PYTHONPATH` is preserved.

## Stock-list artifact result

No external request occurred and no real or persistent `stocks.txt` or other
stock-list output was created. Temporary output paths remained absent; helper
directories disappeared after each subprocess test.

## Regression-test adaptation

The existing 19-test C8.1 module was adapted in place. Exactly six
`@unittest.expectedFailure` decorators were removed. Six observation tests now
assert status/exit `1`; the six future-contract tests remain separate ordinary
passing tests. The root `runpy` control asserts `SystemExit.code == 1` and one
package-main invocation. Success, parser, alias, sibling, filesystem,
traceback, error-wording, request, TPEx, artifact, and `sys.argv` assertions
remain.

## Expected-failure resolution

- Before C8.2: 6 expected failures.
- After C8.2: 0 expected failures; all 19 tests pass ordinarily.

## Production files changed

- `src/tw_stock_tool/data/stock_list_updater.py`: changed `main()` annotation
  to `int | None`, added handled-error `return 1`, and changed the package
  guard to `raise SystemExit(main())`.
- `stock_list_updater.py`: changed only the executable branch to
  `raise SystemExit(_impl.main())`; import alias branch is unchanged.

No fetching, filtering, normalization, partial-update, validation threshold,
writing, output, warning, timeout, or error-message logic changed.

## Test file changed

- `tests/test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior.py`

## Documentation file created

- `docs/TRACK_C8_2_STOCK_LIST_UPDATER_CLI_NONZERO_RUNTIME_EXIT_FIX.md`

## Targeted test result

```text
py -m unittest tests.test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior
19 run; 19 passed; 0 expected failures; 0 failures; 0 errors; OK
```

## Combined test result

```text
py -m unittest tests.test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior tests.test_stock_list_updater tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_track_c7_1_clean_stocks_cli_runtime_exit_behavior tests.test_track_c6_1_benchmark_cli_runtime_exit_behavior tests.test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior tests.test_track_c4_1_scanner_cli_exit_behavior
163 run; 163 passed; 0 expected failures; 0 failures; 0 errors; OK
```

## Canonical full-suite result

```text
py -m unittest discover -s tests
1575 run; 1575 passed; 0 expected failures; 0 failures; 0 errors; OK
```

## Secondary Python full-suite result

```text
python -m unittest discover -s tests
1575 run; 1575 passed; 0 expected failures; 0 failures; 0 errors; OK
```

## `git diff --check` result

`git diff --check` passed with no output.

## UTF-8 BOM result

All four changed files are UTF-8 without BOM.

## Explicit non-goals

No unified-dispatcher change, parser redesign, data-path rewrite, dependency
change, configuration change, unrelated production change, live market access,
stock-list artifact, C8.1 document edit, C8.3 work, merge, rebase, squash, or
force-push was performed.

## No-merge statement

No merge occurred. `main` remains unchanged at the approved baseline.

## Branch disposition

`READY FOR REVIEW`
