# Track C9.1 Smoke Check CLI Runtime Exit Behavior Characterization

## Executive outcome

Track C9.1 characterized both smoke-check CLIs at every approved invocation
boundary using deterministic offline controls. Package, root-process, and
unified-module handled failures currently exit with status `1`. Direct package
callables and unified function calls currently raise `SystemExit(1)` instead of
returning integer `1`. Both root wrappers also ignore a patched integer child
status when executed through `runpy`. Legacy direct success, existing output,
argparse status `2`, `sys.argv` restoration, and root import compatibility are
preserved. No production behavior was changed.

## Formal result

`Track C9.1 Characterization: PASS -- DEFECTS CONFIRMED`

## Repository baseline

- Repository: `Mike87117/tw_stock_tool`
- Starting branch: `main`
- Fetch: `git fetch origin` completed successfully before branch creation.
- Required baseline SHA: `8cf63bcbf0b8db1386bc12323d8e6e28a2fb1940`
- `main`, `origin/main`, and `HEAD` were all aligned at that SHA.
- Starting working tree: clean.
- No `git clean` command was executed.
- `custom_md.md` was not inspected, modified, deleted, staged, or cleaned.

## Branch relationship

- Branch: `track-c9-1-smoke-check-cli-runtime-exit-characterization`
- Created directly from the required `main` baseline SHA.
- At branch creation: `main...HEAD` was `0` ahead and `0` behind.
- The branch remains unmerged and is held for characterization review.

## Working-tree and ignored-file protection result

Only the two explicitly allowed files were created. The user-owned ignored
file `custom_md.md` was left untouched and unread. No ignored-file listing,
delete, clean, or broad workspace cleanup was performed. The tracked
`.gitignore` and `.git/info/exclude` were not changed.

## LLM Wiki availability result

No LLM Wiki connector was available in this execution environment. The Wiki
check was therefore unavailable and non-blocking; repository source, tests,
and Git history were used as the authoritative evidence.

## Existing implementation inventory

### Stock List Smoke Check

`src/tw_stock_tool/cli/stock_list_smoke_check.py` parses its arguments, calls
the real TWSE and TPEx fetch/normalize/validate path, prints a result on
success, and keeps legacy direct success as `None`. On any handled exception,
it prints the existing failure report and raises `SystemExit(1)`. Its package
guard calls `main()` directly.

`stock_list_smoke_check.py` imports the package implementation. Its executable
branch calls `_impl.main()` directly and therefore ignores an integer return;
its import branch aliases the package module through `sys.modules`.

The unified route `stock-list smoke-check` dispatches to the package `main()`
through `_dispatch_existing_main`. The shared dispatcher restores `sys.argv`
and maps child `None` to `0`, but does not convert a child `SystemExit(1)` into
a function return.

### Price Data Smoke Check

`src/tw_stock_tool/cli/price_data_smoke_check.py` runs the real yfinance and
official-fallback result collection and validation path. Its direct success
remains `None`. A handled failure is printed and raised as `SystemExit(1)`.
Its package guard calls `main()` directly.

`price_data_smoke_check.py` has the same compatibility-wrapper structure as
the stock-list wrapper: executable calls ignore an integer child return, and
imports alias the package module.

The unified route `price-smoke-check` uses the same shared dispatcher and the
same current `SystemExit(1)` behavior for a handled child failure.

## Existing test-gap inventory

The existing `tests/test_stock_list_smoke_check.py` and
`tests/test_price_data_smoke_check.py` cover provider stubs, validation
helpers, and result collection, but do not characterize direct `main()` exit
behavior. Existing unified CLI and wrapper tests cover other commands, not the
two smoke-check routes across all requested boundaries. Before this phase,
there was no focused test proving the current direct `SystemExit(1)` behavior,
root `runpy` integer-status behavior, or the complete package/root/unified
smoke-check matrix.

## Offline isolation design

Direct tests patch only the relevant package provider callables. Stock-list
tests patch the TWSE and TPEx fetch functions and patch `requests.get` as a
network tripwire. Price-data tests patch `download_tw_stock` and patch both
`requests.get` and `yfinance.download` as tripwires. No patched provider was
called unexpectedly.

Subprocess tests use a temporary `sitecustomize.py` placed first in
`PYTHONPATH`. The stock mode returns one deterministic record through a local
stub, exercising the real count and expected-stock validation path. The price
mode returns an empty DataFrame from yfinance and raises a controlled local
exception from `requests.get`, exercising the real handled-failure path while
blocking all external providers.

Every subprocess uses `sys.executable`, the repository root as its working
directory, `check=False`, captured stdout/stderr, preserved existing
`PYTHONPATH`, and `PYTHONDONTWRITEBYTECODE=1`. Temporary helper directories
were checked for unexpected files and removed after each test.

## Full invocation-boundary matrix

### Stock List Smoke Check

| ID | Boundary | Current observation | Future contract | Classification |
| --- | --- | --- | --- | --- |
| C9.1-SLSC-01 | Direct callable success | Returns `None`; prints PASS with counts 250/250/500 | Preserve `None`, output, and no artifact | `CORRECTLY_HANDLED` |
| C9.1-SLSC-02 | Direct callable handled validation | Raises `SystemExit(1)` after printing failure | Return integer `1` | `DEFECT_CONFIRMED` |
| C9.1-SLSC-03 | Package-module handled validation | Process exits `1`; failure output has no traceback | Exit `1` | `CORRECTLY_HANDLED` |
| C9.1-SLSC-04 | Root-wrapper handled validation | Process exits `1`; failure output has no traceback | Exit `1` | `CORRECTLY_HANDLED` |
| C9.1-SLSC-05 | Root-wrapper `runpy` with child return `1` | Calls package main once and returns normally, ignoring `1` | Propagate with `SystemExit(1)` | `DEFECT_CONFIRMED` |
| C9.1-SLSC-06 | Unified function handled validation | Raises `SystemExit(1)`; restores `sys.argv` | Return integer `1` and restore `sys.argv` | `DEFECT_CONFIRMED` |
| C9.1-SLSC-07 | Unified-module handled validation | Process exits `1`; failure output has no traceback | Exit `1` | `CORRECTLY_HANDLED` |
| C9.1-SLSC-08 | Package invalid option | Exit status `2`, usage/error output, no traceback | Preserve status `2` | `CORRECTLY_HANDLED` |
| C9.1-SLSC-09 | Root invalid option | Exit status `2`, usage/error output, no traceback | Preserve status `2` | `CORRECTLY_HANDLED` |
| C9.1-SLSC-10 | Unified invalid option | Exit status `2`, usage/error output, no traceback | Preserve status `2` | `CORRECTLY_HANDLED` |
| C9.1-SLSC-11 | Root import compatibility | Root and package resolve to the same module and `main`; import does not execute CLI | Preserve compatibility | `CORRECTLY_HANDLED` |

### Price Data Smoke Check

| ID | Boundary | Current observation | Future contract | Classification |
| --- | --- | --- | --- | --- |
| C9.1-PDSC-01 | Direct callable success | Returns `None`; prints four PASS rows | Preserve `None`, output, and no artifact | `CORRECTLY_HANDLED` |
| C9.1-PDSC-02 | Direct callable handled empty-data validation | Raises `SystemExit(1)` after printing failure | Return integer `1` | `DEFECT_CONFIRMED` |
| C9.1-PDSC-03 | Package-module handled failure | Process exits `1`; failure output has no traceback | Exit `1` | `CORRECTLY_HANDLED` |
| C9.1-PDSC-04 | Root-wrapper handled failure | Process exits `1`; failure output has no traceback | Exit `1` | `CORRECTLY_HANDLED` |
| C9.1-PDSC-05 | Root-wrapper `runpy` with child return `1` | Calls package main once and returns normally, ignoring `1` | Propagate with `SystemExit(1)` | `DEFECT_CONFIRMED` |
| C9.1-PDSC-06 | Unified function handled failure | Raises `SystemExit(1)` four-call validation path; restores `sys.argv` | Return integer `1` and restore `sys.argv` | `DEFECT_CONFIRMED` |
| C9.1-PDSC-07 | Unified-module handled failure | Process exits `1`; failure output has no traceback | Exit `1` | `CORRECTLY_HANDLED` |
| C9.1-PDSC-08 | Package invalid option | Exit status `2`, usage/error output, no traceback | Preserve status `2` | `CORRECTLY_HANDLED` |
| C9.1-PDSC-09 | Root invalid option | Exit status `2`, usage/error output, no traceback | Preserve status `2` | `CORRECTLY_HANDLED` |
| C9.1-PDSC-10 | Unified invalid option | Exit status `2`, usage/error output, no traceback | Preserve status `2` | `CORRECTLY_HANDLED` |
| C9.1-PDSC-11 | Root import compatibility | Root and package resolve to the same module and `main`; import does not execute CLI | Preserve compatibility | `CORRECTLY_HANDLED` |

## Direct callable results

### Stock list

The real package `main()` was called with 250 deterministic TWSE rows and 250
deterministic TPEx rows, including expected stocks `2317`, `2330`, and `8069`.
It returned `None`, printed the existing report with `Status: PASS`, made no
`requests.get` call, produced no traceback, and left the temporary directory
unchanged.

With one deterministic row per market, the real validation path produced the
existing count/missing-stock failure output and raised `SystemExit(1)`. It did
not make an HTTP request or create an artifact. The expected-failure contract
test records that the future callable result should instead be integer `1`.

### Price data

The real package `main()` was called with a deterministic OHLCV DataFrame and
valid `.TW`/`.TWO` symbols. It returned `None`, printed four existing PASS
rows, called the patched loader four times, made no `requests.get` or
`yfinance.download` call, produced no traceback, and left the temporary
directory unchanged.

With the real result-validation path fed empty DataFrames, all four checks
became FAIL rows and `main()` printed the existing aggregate error before
raising `SystemExit(1)`. No provider tripwire was called and no artifact was
created. The expected-failure contract test records that the future callable
result should instead be integer `1`.

## Package-module results

The package stock-list module, run with the one-record offline response,
exited `1` after real threshold and expected-stock validation. The package
price-data module, run with empty yfinance data and blocked fallback HTTP,
exited `1` after real result collection. Both preserved visible failure output,
produced no traceback, made no external request, and produced no persistent
artifact.

## Root-wrapper results

The stock-list and price-data root wrappers each exited `1` in subprocess tests
with the same visible handled-failure behavior as their package modules. This
is the current process result because the package `main()` raises
`SystemExit(1)`.

## Root `runpy` results

For each root wrapper, the package `main()` was patched to return integer `1`,
the wrapper was executed with `runpy.run_path(..., run_name="__main__")`, and
the package callable was invoked exactly once. Both wrappers returned normally
and ignored the integer status; neither raised `SystemExit(1)`. These are
direct controls for the future status-propagation defect and did not patch
`main()` in any other test.

## Unified-function results

`twstock_cli.main(["stock-list", "smoke-check"])` ran the real stock-list
validation path with patched fetch functions and raised `SystemExit(1)` rather
than returning integer `1`. `sys.argv` was restored exactly and no HTTP call or
artifact occurred.

`twstock_cli.main(["price-smoke-check"])` ran the real four-check empty-data
path and likewise raised `SystemExit(1)` rather than returning integer `1`.
`sys.argv` was restored exactly, the patched loader was called four times, and
no provider tripwire or artifact occurred.

## Unified-module results

The stock-list and price-data unified module routes each exited `1` under the
same deterministic offline controls. Each printed visible failure output,
produced no traceback, made no external request, and produced no persistent
artifact.

## Argparse controls

For each command, package-module, root-wrapper, and unified-module invalid
option controls produced status `2`, usage/error output, no traceback, and no
provider request. These parser-owned failures remain distinct from handled
runtime/validation failures and were not marked expected failures.

## Root import compatibility

Importing `stock_list_smoke_check` and
`tw_stock_tool.cli.stock_list_smoke_check` resolved to the same module object
and the same `main` callable. The equivalent price-data imports did the same.
Importing the root wrappers did not execute either CLI.

## Finding matrix

| ID | Finding | Direct evidence | Classification |
| --- | --- | --- | --- |
| C9.1-SLSC-01 | Stock-list direct success preserves legacy `None` and output | Deterministic 500-row direct success | `CORRECTLY_HANDLED` |
| C9.1-SLSC-02 | Stock-list direct handled validation raises `SystemExit(1)` | Real one-row validation path | `DEFECT_CONFIRMED` |
| C9.1-SLSC-03 | Stock-list package failure exits `1` | Offline package subprocess | `CORRECTLY_HANDLED` |
| C9.1-SLSC-04 | Stock-list root failure exits `1` | Offline root subprocess | `CORRECTLY_HANDLED` |
| C9.1-SLSC-05 | Stock-list root wrapper ignores integer `1` under `runpy` | Patched package main and `runpy.run_path` | `DEFECT_CONFIRMED` |
| C9.1-SLSC-06 | Stock-list unified function raises instead of returning `1` | Real unified validation path | `DEFECT_CONFIRMED` |
| C9.1-SLSC-07 | Stock-list unified module exits `1` | Offline unified subprocess | `CORRECTLY_HANDLED` |
| C9.1-SLSC-08 | Stock-list package argparse remains `2` | Invalid-option subprocess | `CORRECTLY_HANDLED` |
| C9.1-SLSC-09 | Stock-list root argparse remains `2` | Invalid-option subprocess | `CORRECTLY_HANDLED` |
| C9.1-SLSC-10 | Stock-list unified argparse remains `2` | Invalid-option subprocess | `CORRECTLY_HANDLED` |
| C9.1-SLSC-11 | Stock-list root import alias remains compatible | Direct import identity control | `CORRECTLY_HANDLED` |
| C9.1-PDSC-01 | Price-data direct success preserves legacy `None` and output | Deterministic OHLCV direct success | `CORRECTLY_HANDLED` |
| C9.1-PDSC-02 | Price-data direct handled validation raises `SystemExit(1)` | Real empty-data validation path | `DEFECT_CONFIRMED` |
| C9.1-PDSC-03 | Price-data package failure exits `1` | Offline package subprocess | `CORRECTLY_HANDLED` |
| C9.1-PDSC-04 | Price-data root failure exits `1` | Offline root subprocess | `CORRECTLY_HANDLED` |
| C9.1-PDSC-05 | Price-data root wrapper ignores integer `1` under `runpy` | Patched package main and `runpy.run_path` | `DEFECT_CONFIRMED` |
| C9.1-PDSC-06 | Price-data unified function raises instead of returning `1` | Real unified empty-data path | `DEFECT_CONFIRMED` |
| C9.1-PDSC-07 | Price-data unified module exits `1` | Offline unified subprocess | `CORRECTLY_HANDLED` |
| C9.1-PDSC-08 | Price-data package argparse remains `2` | Invalid-option subprocess | `CORRECTLY_HANDLED` |
| C9.1-PDSC-09 | Price-data root argparse remains `2` | Invalid-option subprocess | `CORRECTLY_HANDLED` |
| C9.1-PDSC-10 | Price-data unified argparse remains `2` | Invalid-option subprocess | `CORRECTLY_HANDLED` |
| C9.1-PDSC-11 | Price-data root import alias remains compatible | Direct import identity control | `CORRECTLY_HANDLED` |

## Classification totals

- `DEFECT_CONFIRMED`: 6
- `CORRECTLY_HANDLED`: 16
- `CONTRACT_UNDECIDED`: 0
- `NOT_APPLICABLE`: 0
- `INFERENCE_ONLY`: 0

## Expected-failure inventory

The focused characterization module contains 24 tests: 18 ordinary passing
observation tests and exactly 6 expected failures. Each expected failure maps
to one confirmed future-contract mismatch:

1. `test_stock_direct_handled_failure_should_return_integer_one`
2. `test_stock_root_runpy_should_propagate_integer_status`
3. `test_stock_unified_function_failure_should_return_integer_one`
4. `test_price_direct_handled_failure_should_return_integer_one`
5. `test_price_root_runpy_should_propagate_integer_status`
6. `test_price_unified_function_failure_should_return_integer_one`

No current-behavior observation test is marked as an expected failure.

## Direct evidence versus inference

The six defect classifications are based on deterministic direct callable,
unified-function, and root `runpy` observations, plus subprocess status/output
controls. Package/root/unified process statuses, output text, `sys.argv`
restoration, import identity, no-traceback behavior, and provider tripwires
were directly observed. The future integer-return/status contract is the
approved reference contract, not an implemented change. Source inspection is
used only for the implementation inventory and is not used alone to classify
a defect.

## Exact files changed

- `tests/test_track_c9_1_smoke_check_cli_runtime_exit_behavior.py`
- `docs/TRACK_C9_1_SMOKE_CHECK_CLI_RUNTIME_EXIT_BEHAVIOR_CHARACTERIZATION.md`

No production file was changed.

## Exact validation commands and actual results

Targeted:

```text
py -m unittest tests.test_track_c9_1_smoke_check_cli_runtime_exit_behavior
24 run; 18 passed; 6 expected failures; 0 ordinary failures; 0 errors; OK
```

Combined smoke-check and CLI regression set:

```text
py -m unittest tests.test_track_c9_1_smoke_check_cli_runtime_exit_behavior tests.test_stock_list_smoke_check tests.test_price_data_smoke_check tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes
92 run; 86 passed; 6 expected failures; 0 ordinary failures; 0 errors; OK
```

Canonical full suite:

```text
py -m unittest discover -s tests
1599 run; 1593 passed; 6 expected failures; 0 ordinary failures; 0 errors; OK
```

Secondary repository-Python full suite:

```text
python -m unittest discover -s tests
1599 run; 1593 passed; 6 expected failures; 0 ordinary failures; 0 errors; OK
```

## `git diff --check` result

`git diff --check` passed with no output. The staged equivalent,
`git diff --check --cached`, also passed with no output.

## UTF-8 BOM result

Both new files decoded as UTF-8 and reported `BOM=False`. No existing file
encoding or line ending was intentionally altered.

## External-request result

No characterization test made a live external request. Direct and unified
function tests patched the relevant provider callables and network tripwires.
Subprocess tests injected deterministic local provider controls before target
module execution. The full repository suite was run as required; this report's
no-live-request claim applies to the new characterization tests.

## Filesystem-artifact result

No real stock-list, cache, report, or output artifact was created by the new
characterization tests. Direct temporary directories remained unchanged;
subprocess helper directories contained no files beyond their initial
`sitecustomize.py` and were removed after each test. The failure paths used
`force_refresh=True` and did not write cache data.

## Deferred C9.2 candidate scope

C9.2 may make the narrowly bounded production change required to align the two
smoke-check callable failure paths with integer return `1`, preserve direct
success `None`, keep parser status `2`, propagate integer child statuses from
both root wrappers, and preserve unified `sys.argv` restoration. C9.2 may
adjust executable guards only as needed to retain process exit `1` after the
callable contract is corrected. No C9.2 work was started here.

## Explicit production-fix restriction

This phase changed tests and documentation only. No smoke-check `main()`,
package executable guard, root wrapper, unified dispatcher, parser, provider,
cache behavior, output wording, dependency, configuration, or production
abstraction was modified. No live market service was accessed. No merge,
rebase, squash, force-push, or later track was started.

## Branch disposition

`HOLD`

Recommendation: Proceed with a narrowly bounded Track C9.2 production fix.
