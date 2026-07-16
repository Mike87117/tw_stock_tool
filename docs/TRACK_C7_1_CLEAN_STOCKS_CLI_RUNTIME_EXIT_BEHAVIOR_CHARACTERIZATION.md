# Track C7.1 Clean Stocks CLI Runtime Exit Behavior Characterization

## Executive outcome

Track C7.1 independently characterized Clean Stocks at every approved invocation
boundary using deterministic offline tests. Legacy successful direct execution
returns `None`, while six handled validation/runtime failure boundaries currently
report success instead of the approved status `1`. Parser-owned failures remain
status `2`, root import compatibility is preserved, and the unified dispatcher
propagates integer child statuses unchanged.

## Formal result

`Track C7.1 Characterization: PASS -- DEFECTS CONFIRMED`

## Repository baseline

- Repository: `Mike87117/tw_stock_tool`
- Required baseline: `c87c2ef8bb0eab020d5377c276a7950e8249c9b4`
- Local `main`, `origin/main`, and `HEAD` before branching all matched the baseline.
- Initial `main...origin/main` relationship: `0` ahead, `0` behind.
- Parent canonical suite: 1,537 run, 1,537 passed, 0 expected failures, 0 failures, 0 errors.
- Parent repository-Python suite: 1,537 run, 1,537 passed, 0 expected failures, 0 failures, 0 errors.

## Branch relationship

- Branch: `track-c7-1-clean-stocks-cli-runtime-exit-characterization`
- Initial branch relationship to `main`: `0` ahead, `0` behind.
- Branch disposition: `HOLD`.

## Parent test results

The required parent `py -m unittest discover -s tests` and
`python -m unittest discover -s tests` runs both completed with 1,537 tests,
1,537 passes, 0 expected failures, 0 failures, and 0 errors before the branch
was created.

## custom_md.md protection result

`custom_md.md` was confirmed present without reading its contents. It remains
untracked and ignored only by `.git/info/exclude`; it was not modified, staged,
or committed. No `git clean` command was executed.

## LLM Wiki result

- Health: available; `ok: true`, `status: running`.
- Version: `0.5.4`.
- Active project: `tw_stock_tool Wiki`.
- Search: `Clean Stocks CLI runtime exit status package root wrapper unified dispatcher SystemExit Track C4 C5 C6`.
- Summary: keyword search returned 13 token hits and 10 result documents, led by
  CLI reference, phase history, current architecture, and project overview.
  Wiki content was supporting context only; repository source and tests were
  authoritative.

## Existing Clean Stocks contract inventory

`src/tw_stock_tool/cli/clean_stocks.py` parses `--file` and optional output
controls, calls `run_clean_stocks`, prints the existing summary, catches
`Exception`, and prints `Error: ...` without returning a status. Its package
guard calls `main()` directly. The root `clean_stocks.py` wrapper invokes the
package `main()` directly when executed and aliases the package module through
`sys.modules` when imported. The unchanged unified dispatcher routes
`stock-list clean`, restores `sys.argv`, and converts only a child `None` to
status `0`.

## Existing test-gap inventory

Existing Clean Stocks tests cover file parsing, normalization, validation,
summary construction, output helpers, and data-loader behavior. They did not
provide the complete direct/package/root/unified return and process-exit matrix,
root executable invocation control, or the separate future status contracts.

## Invocation-boundary matrix

| Boundary | Current observation | Approved future contract | Classification |
|---|---|---|---|
| Direct success | Returns `None`; summary is visible; no artifact | Preserve legacy `None` | `CORRECTLY_HANDLED` |
| Direct validation failure | Prints `Error: Stock file not found: ...`; returns `None` | Return `1` | `DEFECT_CONFIRMED` |
| Direct controlled runtime failure | Prints `Error: controlled clean stocks failure`; returns `None` | Return `1` | `DEFECT_CONFIRMED` |
| Package validation failure | Prints the existing error; exits `0` | Exit `1` | `DEFECT_CONFIRMED` |
| Root validation failure | Invokes package behavior; exits `0` | Exit `1` | `DEFECT_CONFIRMED` |
| Root `runpy` execution | Calls package `main()` once; ignores returned status | Propagate status through `SystemExit` | `CORRECTLY_HANDLED` invocation, `DEFECT_CONFIRMED` propagation |
| Unified function validation failure | Prints the existing error; returns `0`; restores `sys.argv` | Return `1` | `DEFECT_CONFIRMED` |
| Unified module validation failure | Prints the existing error; exits `0` | Exit `1` | `DEFECT_CONFIRMED` |
| Package argparse | Invalid option exits `2` with usage/error | Preserve `2` | `CORRECTLY_HANDLED` |
| Root argparse | Invalid option exits `2` with usage/error | Preserve `2` | `CORRECTLY_HANDLED` |
| Unified argparse | Invalid clean option exits `2` with usage/error | Preserve `2` | `CORRECTLY_HANDLED` |
| Root import | Root and package resolve to the same module and callable | Preserve alias | `CORRECTLY_HANDLED` |
| Sibling contract | Scanner handled failure returns `1`; unified dispatcher propagates child `1` | Preserve unchanged dispatcher contract | `CORRECTLY_HANDLED` |

## Direct success result

The real `clean_stocks.main()` was invoked with `run_clean_stocks` patched to a
synthetic one-row result. It returned legacy `None`, called `run_clean_stocks`
once with parsed defaults, printed the existing `Clean Stocks` summary, emitted
no traceback, and created no report, clean file, directory, or other artifact.
The downstream `download_tw_stock` path was not called.

## Direct validation-failure result

With an absolute nonexistent temporary `--file`, the real path produced the
existing `Error: Stock file not found: ...` message, no traceback, no artifact,
and current return `None`. The downstream market-data loader was not called.
The separate future-contract test requiring return `1` is expected-failing.

## Direct controlled runtime-failure result

With only `run_clean_stocks` patched to raise
`RuntimeError("controlled clean stocks failure")`, the real `main()` printed
`Error: controlled clean stocks failure`, emitted no traceback or artifact, and
returned `None`. The separate future-contract test requiring return `1` is
expected-failing.

## Package-module result

`python -m tw_stock_tool.cli.clean_stocks --file <missing>` printed the existing
validation error without a traceback or artifact and exited `0`. The separate
future-contract test requiring process exit `1` is expected-failing.

## Root-wrapper result

`python clean_stocks.py --file <missing>` printed the existing validation error
without a traceback or artifact and exited `0`. A separate `runpy` control
proved the root script invokes package `main()` exactly once and that the
current defect is failure to propagate its returned status. The separate future
process-exit contract requiring `1` is expected-failing.

## Unified-function result

`twstock_cli.main(["stock-list", "clean", "--file", <missing>])` printed the
existing validation error, created no artifact, restored `sys.argv` exactly, and
returned `0`. The unchanged dispatcher maps the Clean Stocks child `None` to
`0`; the separate future status-`1` contract is expected-failing.

## Unified-module result

`python -m tw_stock_tool.cli.twstock_cli stock-list clean --file <missing>`
printed the existing validation error without a traceback or artifact and exited
`0`. The separate future process-exit contract requiring `1` is expected-failing.

## Argparse controls

Package, root, and unified invalid-option controls each produced usage/error
output, no traceback, no artifact, and parser-owned exit status `2`. None is an
expected failure.

## Root import compatibility

Importing `clean_stocks` and `tw_stock_tool.cli.clean_stocks` resolved to the
same module object and exposed the same `main` callable. Import did not execute
the CLI.

## Sibling contract evidence

The bounded sibling control forced a Scanner runtime failure and observed its
handled status `1`. It then patched the existing Scanner child to return
integer `1` and confirmed the unchanged unified dispatcher propagated `1` while
restoring `sys.argv`. No sibling audit or implementation was started.

## Finding matrix

| ID | Finding | Evidence | Classification |
|---|---|---|---|
| C7.1-01 | Legacy direct success returns `None` | Direct synthetic success test | `CORRECTLY_HANDLED` |
| C7.1-02 | Direct validation failure returns `None` | Direct missing-file observation | `DEFECT_CONFIRMED` |
| C7.1-03 | Direct runtime failure returns `None` | Direct controlled exception observation | `DEFECT_CONFIRMED` |
| C7.1-04 | Package validation failure exits `0` | Package subprocess observation | `DEFECT_CONFIRMED` |
| C7.1-05 | Root wrapper validation failure exits `0` | Root subprocess and `runpy` controls | `DEFECT_CONFIRMED` |
| C7.1-06 | Unified function validation failure returns `0` | Direct unified invocation | `DEFECT_CONFIRMED` |
| C7.1-07 | Unified module validation failure exits `0` | Unified subprocess observation | `DEFECT_CONFIRMED` |
| C7.1-08 | Package argparse remains exit `2` | Package invalid-option control | `CORRECTLY_HANDLED` |
| C7.1-09 | Root argparse remains exit `2` | Root invalid-option control | `CORRECTLY_HANDLED` |
| C7.1-10 | Unified argparse remains exit `2` | Unified invalid-option control | `CORRECTLY_HANDLED` |
| C7.1-11 | Root import alias remains compatible | Direct import control | `CORRECTLY_HANDLED` |
| C7.1-12 | Sibling integer status and dispatch remain correct | Bounded Scanner/dispatcher control | `CORRECTLY_HANDLED` |

## Classification totals

- `DEFECT_CONFIRMED`: 6
- `CORRECTLY_HANDLED`: 7
- `CONTRACT_UNDECIDED`: 0
- `NOT_APPLICABLE`: 0
- `INFERENCE_ONLY`: 0

The seven correctly handled controls are legacy direct success, root `runpy`
package-main invocation, package argparse, root argparse, unified argparse,
root import alias, and bounded sibling integer-status propagation.

## Expected-failure inventory

Exactly six future-contract tests are expected failures, one for each directly
confirmed false-success boundary: direct validation return, direct runtime
return, package process exit, root process exit, unified function status, and
unified module exit. Observation tests for current behavior remain ordinary
passing tests. Success, argparse, import, sibling, and root invocation controls
are not expected failures.

## Direct evidence versus inference

Direct calls, subprocesses, `runpy`, redirected output, patched dependencies,
temporary paths, and synthetic DataFrames provide the current behavior,
messages, returns, exits, invocation, `sys.argv`, and artifact evidence. The
future status `1` requirements are approved contract expectations represented by
separate expected-failure tests. The unchanged dispatcher explanation is based
on source and sibling integer-propagation evidence; no production defect was
inferred without a Clean Stocks observation.

## Production files changed

`None`.

## Test files changed

- `tests/test_track_c7_1_clean_stocks_cli_runtime_exit_behavior.py`

## Documentation files changed

- `docs/TRACK_C7_1_CLEAN_STOCKS_CLI_RUNTIME_EXIT_BEHAVIOR_CHARACTERIZATION.md`

## Validation commands and actual results

```text
py -m unittest tests.test_track_c7_1_clean_stocks_cli_runtime_exit_behavior
19 run; 13 passed; 6 expected failures; 0 failures; 0 errors; OK

py -m unittest tests.test_track_c7_1_clean_stocks_cli_runtime_exit_behavior tests.test_clean_stocks tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_track_c6_1_benchmark_cli_runtime_exit_behavior tests.test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior tests.test_track_c4_1_scanner_cli_exit_behavior
137 run; 131 passed; 6 expected failures; 0 failures; 0 errors; OK

py -m unittest discover -s tests
1556 run; 1550 passed; 6 expected failures; 0 failures; 0 errors; OK

python -m unittest discover -s tests
1556 run; 1550 passed; 6 expected failures; 0 failures; 0 errors; OK
```

`git diff --check` passed. Both new files are UTF-8 without BOM. No production
file, existing test, existing document, dependency, configuration, real stock
file, report, clean-stock output, cache, or market-data path was modified.

## Deferred C7.2 candidate scope

C7.2 may implement only the bounded Clean Stocks runtime-status fix: preserve
successful direct `None`, return `1` for handled validation/runtime failures,
propagate package/root statuses through `SystemExit`, and preserve argparse
`2`, root import aliasing, output wording, and the unchanged unified dispatcher.
No C7.2 implementation was authorized or started in this track.

## Production-fix restriction

This was a tests-and-documentation-only characterization. No production fix was
authorized or started. No merge, rebase, squash, force-push, or next track was
performed.

## Branch disposition

`HOLD`
