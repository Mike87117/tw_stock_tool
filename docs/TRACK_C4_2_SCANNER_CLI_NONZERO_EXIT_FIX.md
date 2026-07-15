# Track C4.2 Scanner CLI Nonzero Runtime Exit Fix

## Executive outcome

Track C4.2 resolves the eight Scanner false-success boundaries confirmed by C4.1. Scanner direct success still returns legacy `None`; each handled runtime failure now returns `1`. The package-module and root-wrapper guards propagate that value through `SystemExit`, and the unchanged unified dispatcher consequently returns and exits `1` for Scanner runtime failures.

Formal result: `Track C4.2 Implementation: PASS — READY FOR REVIEW`

## Repository and stacked-branch baseline

- Repository: `Mike87117/tw_stock_tool`
- `main` and `origin/main`: `e41181bbdcb79c6d8dffc5353b00755dfc2893bb`
- Parent branch: `track-c4-1-scanner-cli-exit-characterization`
- Parent HEAD: `31757f4c064126a9084a36802c60033e735ba5f1`
- Parent relation to main: 4 commits ahead, 0 behind
- Parent suite: 1,504 tests; 1,496 passed; 8 expected failures; 0 failures; 0 errors; `OK`
- C3.1 through C4.1 commits and historical documents remained unchanged.

## LLM Wiki result

- Health: available; `ok: true`, `status: running`
- Version: `0.5.4`
- Active project: `tw_stock_tool Wiki`
- Search: `Scanner CLI nonzero runtime exit return 1 SystemExit wrapper unified propagation Track C4.1`
- Summary: supporting CLI, Scanner, and architecture context was found. C4.1, C2.5, source, and regression tests remained authoritative.

## Confirmed defect

C4.1 showed that Scanner printed its existing error or cancellation text while its callable returned `None`. That `None` was treated as success by the package module, root wrapper, and unified dispatcher, producing process/status `0` after failed Scanner work.

## Approved behavior contract

- Successful direct Scanner execution remains legacy `None`.
- `ValueError`, `ReportError`, cancellation, and unexpected runtime failures return `1`.
- Package-module and root-wrapper execution use `SystemExit(main())`.
- The unchanged unified dispatcher propagates Scanner's integer `1`.
- Argparse retains `SystemExit(2)`.
- Existing output wording and exception ownership remain unchanged.

## Implementation scope

The implementation is limited to three `return 1` statements, two executable-guard propagations, and activation of the eight C4.1 regression tests. No new dependencies, helpers, arguments, or abstractions were added.

## Direct Scanner result

Direct success still returns `None`. Direct `ValueError`, `ReportError`, cancellation, and unexpected runtime failure each return `1` after preserving their existing printed message.

## Package module result

`python -m tw_stock_tool.cli.scan_stocks --file <missing>` preserves the handled missing-file message and exits `1` without a traceback.

## Root wrapper result

`python scan_stocks.py --file <missing>` preserves the same handled message and exits `1`. Normal import compatibility remains `_sys.modules[__name__] = _impl`.

## Unified function result

`twstock_cli.main(["scan", "--file", <missing>])` returns `1` and restores `sys.argv`. The unified dispatcher was not modified.

## Unified module result

`python -m tw_stock_tool.cli.twstock_cli scan --file <missing>` exits `1` without a traceback.

## Argparse preservation

Invalid Scanner arguments remain parser-owned `SystemExit(2)` at direct and unified boundaries.

## Success compatibility preservation

The successful direct callable result remains `None`; no success `return 0` was added. Scanner scanning, ranking, exporting, error logging, argument parsing, and output text are unchanged.

## Expected-failure resolution

The eight C4.1 expected failures are now ordinary passing regression tests:

- Four direct Scanner runtime categories
- Package module process
- Root wrapper process
- Unified function
- Unified module process

Expected failures changed from 8 to 0.

## Production files changed

- `src/tw_stock_tool/cli/scan_stocks.py`
- `scan_stocks.py`

## Test files changed

- `tests/test_track_c4_1_scanner_cli_exit_behavior.py`

## Documentation files changed

- Added `docs/TRACK_C4_2_SCANNER_CLI_NONZERO_EXIT_FIX.md`.

## Validation commands

```powershell
py -m unittest tests.test_track_c4_1_scanner_cli_exit_behavior
# Ran 20 tests; 20 passed; 0 expected failures; 0 failures; 0 errors; OK

py -m unittest tests.test_track_c4_1_scanner_cli_exit_behavior tests.test_scanner tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_main tests.test_ai_walk_forward tests.test_track_c3_1_scanner_daily_correctness
# Ran 125 tests; 125 passed; 0 expected failures; 0 failures; 0 errors; OK

py -m unittest discover -s tests
# Ran 1,504 tests; 1,504 passed; 0 expected failures; 0 failures; 0 errors; OK
```

The full test count remains 1,504 because no new tests were added.

## Non-goals

This fix does not change Scanner output, parsing, scan/ranking/export/error-log behavior, unified dispatch, other CLIs, root-wrapper imports, dependencies, configuration, or historical C3/C4.1 work. No market-data network was accessed, no Scanner artifact remains, `custom_md.md` was not accessed or changed, and no branch was merged.

## Recommended next action

Submit this bounded production-fix branch for separate review. It is ready for review but not merged.
