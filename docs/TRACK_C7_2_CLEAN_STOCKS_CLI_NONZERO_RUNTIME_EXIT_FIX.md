# Track C7.2 Clean Stocks CLI Nonzero Runtime Exit Fix

## Executive outcome

Track C7.2 applies the smallest approved fix for the six Clean Stocks
false-success boundaries confirmed by C7.1. The existing handled-error path now
returns `1`; package and root executable guards propagate that result through
`SystemExit`; the unchanged unified dispatcher then propagates status `1`.
Successful direct execution remains legacy `None`, parser errors remain `2`,
and all required tests pass with zero expected failures.

## Formal result

`Track C7.2 Implementation: PASS -- READY FOR REVIEW`

## Repository and stacked-branch baseline

- Repository: `Mike87117/tw_stock_tool`
- `main` and `origin/main`: `c87c2ef8bb0eab020d5377c276a7950e8249c9b4`
- Parent branch: `track-c7-1-clean-stocks-cli-runtime-exit-characterization`
- Parent SHA: `d80240bb28bdcf605560d6a41495279e03549e0b`
- Production branch: `track-c7-2-clean-stocks-cli-nonzero-runtime-exit-fix`
- Initial parent relationship to `main`: 2 ahead, 0 behind.

## Parent test results

Before branching, both required parent suites completed with 1,556 run, 1,550
passed, 6 expected failures, 0 failures, and 0 errors:

```text
py -m unittest discover -s tests
python -m unittest discover -s tests
```

## custom_md.md protection result

`custom_md.md` remained present, unread, unmodified, untracked, and ignored only
through `.git/info/exclude`. No `git clean` command was executed and retained
ignored artifacts were preserved.

## LLM Wiki result

- Health: available; `ok: true`, `status: running`.
- Version: `0.5.4`.
- Active project: `tw_stock_tool Wiki`.
- Search: `Track C7.1 Clean Stocks CLI nonzero runtime exit package root SystemExit unified propagation`.
- Summary: keyword search returned 12 token hits and 10 supporting documents,
  led by CLI reference, architecture, phase history, and tests/CI. Repository
  source, tests, and Git history remained authoritative.

## Six confirmed defects from C7.1

C7.1 directly confirmed false success for direct validation failure, direct
handled runtime failure, package-module failure, root-wrapper failure, unified
function failure, and unified-module failure. Each boundary previously reported
`None` or process/function status `0` instead of the approved status `1`.

## Approved behavior contract

- Successful direct Clean Stocks calls continue to return `None`.
- Handled validation/runtime failures return integer `1`.
- Package and root executable guards propagate the callable result via
  `raise SystemExit(...)`.
- The unchanged unified dispatcher propagates child integer `1` and maps only
  legacy child `None` to `0`.
- Existing `Error: ...` wording, stdout/stderr ownership, parsing, validation,
  downloads, report logic, clean-file logic, argparse status `2`, and root import
  aliasing are preserved.

## Exact implementation scope

Only these four files changed relative to the C7.1 parent:

- `src/tw_stock_tool/cli/clean_stocks.py`
- `clean_stocks.py`
- `tests/test_track_c7_1_clean_stocks_cli_runtime_exit_behavior.py`
- `docs/TRACK_C7_2_CLEAN_STOCKS_CLI_NONZERO_RUNTIME_EXIT_FIX.md`

The unified dispatcher, C7.1 document, existing Clean Stocks tests, and all
other production/configuration files were unchanged.

## Direct success result

The synthetic success control still returns `None`, preserves the summary
output, calls the downstream workflow once with parsed arguments, and creates no
artifact or market-data access.

## Direct validation result

The real missing-file path preserves `Error: Stock file not found: ...`, emits
no traceback or artifact, and now returns `1`.

## Direct controlled runtime result

The real handled `RuntimeError("controlled clean stocks failure")` path preserves
the existing error output, emits no traceback or artifact, and now returns `1`.

## Package-module result

`python -m tw_stock_tool.cli.clean_stocks --file <missing>` preserves the
validation message and exits `1` through `raise SystemExit(main())`.

## Root-wrapper result

`python clean_stocks.py --file <missing>` preserves the validation message and
exits `1` through `raise SystemExit(_impl.main())`. The root runpy control now
catches `SystemExit` code `1` and still confirms package `main()` is called once.

## Unified-function result

`twstock_cli.main(["stock-list", "clean", "--file", <missing>])` now returns
`1`, preserves output and filesystem assertions, and restores `sys.argv` exactly.
The dispatcher itself was not modified.

## Unified-module result

`python -m tw_stock_tool.cli.twstock_cli stock-list clean --file <missing>` now
exits `1` with the existing error output and no traceback or artifact.

## Argparse preservation

Package, root, and unified invalid-option controls continue to produce usage and
error output with exit status `2`; parser behavior and arguments were unchanged.

## Root import compatibility

Root `clean_stocks` and package `tw_stock_tool.cli.clean_stocks` continue to
resolve to the same module object and expose the same `main` callable. Importing
the wrapper does not execute the CLI.

## Regression-test adaptation

The existing 19-test C7.1 module was adapted in place. Exactly six
`@unittest.expectedFailure` decorators were removed. The six observation tests
now assert status/exit `1`, and the root runpy test asserts `SystemExit.code == 1`
while retaining the single invocation assertion. The success control still
asserts direct `None`; all artifact, traceback, invocation, parser, import,
filesystem, and `sys.argv` checks remain.

## Expected-failure resolution

Expected failures before C7.2: `6`.

Expected failures after C7.2: `0`. All 19 C7.1 tests are ordinary passing tests.

## Production files changed

- `src/tw_stock_tool/cli/clean_stocks.py`: return annotation, handled-error
  return `1`, and package `SystemExit` guard.
- `clean_stocks.py`: root executable `SystemExit` propagation; import alias
  branch unchanged.

## Test file changed

- `tests/test_track_c7_1_clean_stocks_cli_runtime_exit_behavior.py`

## Documentation file created

- `docs/TRACK_C7_2_CLEAN_STOCKS_CLI_NONZERO_RUNTIME_EXIT_FIX.md`

## Targeted test result

```text
py -m unittest tests.test_track_c7_1_clean_stocks_cli_runtime_exit_behavior
19 run; 19 passed; 0 expected failures; 0 failures; 0 errors; OK
```

## Combined test result

```text
py -m unittest tests.test_track_c7_1_clean_stocks_cli_runtime_exit_behavior tests.test_clean_stocks tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_track_c6_1_benchmark_cli_runtime_exit_behavior tests.test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior tests.test_track_c4_1_scanner_cli_exit_behavior
137 run; 137 passed; 0 expected failures; 0 failures; 0 errors; OK
```

## Canonical full-suite result

```text
py -m unittest discover -s tests
1556 run; 1556 passed; 0 expected failures; 0 failures; 0 errors; OK
```

## Secondary Python full-suite result

```text
python -m unittest discover -s tests
1556 run; 1556 passed; 0 expected failures; 0 failures; 0 errors; OK
```

## Whitespace and BOM results

`git diff --check` passed. All four changed files are UTF-8 without BOM.

## Explicit non-goals

No unified-dispatcher change, parser redesign, Clean Stocks functional rewrite,
live market access, real Excel/clean-stock/cache/report artifact, unrelated
production change, C7.1 document edit, C7.3 work, merge, rebase, squash, or
force-push was performed.

## Merge status

No merge occurred. `main` remains unchanged at the approved baseline.

## Branch disposition

`READY FOR REVIEW`
