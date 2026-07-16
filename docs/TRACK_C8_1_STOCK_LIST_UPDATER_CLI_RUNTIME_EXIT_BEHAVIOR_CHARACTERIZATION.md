# Track C8.1 Stock List Updater CLI Runtime Exit Behavior Characterization

## Executive outcome

Track C8.1 characterized the Stock List Updater at every approved invocation
boundary using deterministic offline controls. Six handled validation/runtime
failures currently report success: direct calls return `None`, package/root
processes exit `0`, and unified calls return/exit `0`. Legacy direct success,
argparse status `2`, root import aliasing, and integer sibling propagation are
correctly handled. No production behavior was changed.

## Formal result

`Track C8.1 Characterization: PASS -- DEFECTS CONFIRMED`

## Repository baseline

- Repository: `Mike87117/tw_stock_tool`
- Required `main` and `origin/main`: `c6a666de6a756fa32efa3716eebfe75e5fa0eedf`
- Baseline suites: both `py -m unittest discover -s tests` and
  `python -m unittest discover -s tests` ran 1,556 tests with 1,556 passes,
  0 expected failures, 0 failures, and 0 errors.

## Branch relationship

- Branch: `track-c8-1-stock-list-updater-cli-runtime-exit-characterization`
- Created directly from the required `main` baseline.
- Immediately after creation: 0 behind, 0 ahead.

## custom_md.md protection result

`custom_md.md` remained present and unread. It remains ignored only through the
exact root entry `/custom_md.md` in `.git/info/exclude`. No `git clean` command
was executed, and the tracked `.gitignore` was not modified.

## LLM Wiki result

No LLM Wiki connector was available in this execution environment. The Wiki
check was therefore unavailable and non-blocking; repository source, tests, and
Git history are authoritative.

## Existing Stock List Updater contract inventory

The package module `src/tw_stock_tool/data/stock_list_updater.py` keeps
`main() -> None`, calls `update_stock_list(...)`, catches `Exception`, prints
`Error: {exc}`, and has no explicit handled-error return. Its executable guard
calls `main()` directly. The root `stock_list_updater.py` executable branch
calls `_impl.main()` directly, while its import branch aliases the package
module through `_sys.modules[__name__] = _impl`. The unified route
`stock-list update` calls `stock_list_updater.main`; the shared dispatcher
restores `sys.argv`, propagates integer child statuses, and maps only child
`None` to `0`.

## Existing test-gap inventory

Before C8.1 there was no boundary characterization proving the six handled
false-success cases for the direct callable, package module, root wrapper,
unified function, and unified module. The future contract requires failures to
return/exit `1` while preserving successful direct `None` and parser `2`.

## Offline test-isolation design

Direct tests patch only the relevant fetch/update callables and assert that
`requests.get` is not called. Package, root, and unified subprocess tests use a
temporary `sitecustomize.py` placed first in `PYTHONPATH`; it patches
`requests.get` before target execution and returns exactly one deterministic
TWSE common-stock record (`2330`). The real validation then raises
`Abnormally few common stocks parsed: 1 < 100.` before writing output.

Each subprocess uses `sys.executable`, repository-root working directory,
`check=False`, captured stdout/stderr, preserved existing `PYTHONPATH`, and
`PYTHONDONTWRITEBYTECODE=1`. The helper directory is temporary and disappears
after each test.

## Invocation-boundary matrix

| Boundary | Current observation | Future contract | Classification |
| --- | --- | --- | --- |
| Direct success | Returns `None` | Preserve `None` | `CORRECTLY_HANDLED` |
| Direct validation | Returns `None` | Return `1` | `DEFECT_CONFIRMED` |
| Direct runtime | Returns `None` | Return `1` | `DEFECT_CONFIRMED` |
| Package validation | Exits `0` | Exit `1` | `DEFECT_CONFIRMED` |
| Root validation | Exits `0` | Exit `1` | `DEFECT_CONFIRMED` |
| Root `runpy` invocation | Calls package `main()` once and ignores integer status | Raise `SystemExit(1)` | `CORRECTLY_HANDLED` invocation, propagation defect isolated by process test |
| Unified function | Returns `0` | Return `1` | `DEFECT_CONFIRMED` |
| Unified module | Exits `0` | Exit `1` | `DEFECT_CONFIRMED` |
| Package argparse | Exits `2` | Preserve `2` | `CORRECTLY_HANDLED` |
| Root argparse | Exits `2` | Preserve `2` | `CORRECTLY_HANDLED` |
| Unified argparse | Exits `2` | Preserve `2` | `CORRECTLY_HANDLED` |
| Root import | Same module and callable; no execution | Preserve compatibility | `CORRECTLY_HANDLED` |
| Clean Stocks sibling | Returns/propagates integer `1` | Preserve propagation | `CORRECTLY_HANDLED` |

## Direct success result

The real package `main()` was invoked with `--market twse --output <temporary
path>` while only `update_stock_list(...)` was patched. It returned legacy
`None`, called the updater exactly once with parsed values, printed `Stock list
updated:` and `Stocks: 1`, made no `requests.get` call, and created no file or
directory.

## Direct validation result

The real update path used a deterministic one-row TWSE DataFrame while TPEx was
patched and verified unused. It printed the existing
`Error: Abnormally few common stocks parsed: 1 < 100.` wording, returned
`None`, made no HTTP request, left the temporary filesystem unchanged, and did
not create the requested output.

## Direct controlled runtime result

Patching only `update_stock_list(...)` to raise
`RuntimeError("controlled stock list updater failure")` produced the existing
error text, no traceback, no output artifact, and current return `None`; the
patched updater was called once.

## Package-module result

`python -m tw_stock_tool.data.stock_list_updater --market twse --output
<temporary path>` with the temporary network stub printed the deterministic
validation error, produced no traceback or output file, removed its helper
directory, and exited `0`.

## Root-wrapper result

`python stock_list_updater.py --market twse --output <temporary path>` showed the
same deterministic validation error, no traceback or persistent artifact, and
exited `0`.

## Root `runpy` result

With package `main()` patched to return `1`, `runpy.run_path(...,
run_name="__main__")` proved the root `_impl` resolves to the package module,
the package callable is invoked exactly once, and the current wrapper ignores
the returned integer without raising `SystemExit`.

## Unified-function result

`twstock_cli.main(["stock-list", "update", "--market", "twse", "--output",
<temporary path>])` used the deterministic one-row TWSE frame, verified TPEx
was not called, returned `0`, preserved the error wording, restored `sys.argv`
exactly, made no HTTP request, and created no output.

## Unified-module result

`python -m tw_stock_tool.cli.twstock_cli stock-list update --market twse
--output <temporary path>` used the same offline stub, printed the validation
error, produced no traceback or output artifact, removed the helper directory,
and exited `0`.

## Argparse controls

Package, root, and unified invalid-option subprocess controls each produced
usage/error output with exit status `2`, no traceback, no output file, and no
network helper. None is marked as an expected failure.

## Root import compatibility

Importing `stock_list_updater` and
`tw_stock_tool.data.stock_list_updater` resolves to the same module object and
the same `main` callable. Importing the root wrapper does not execute the CLI.

## Sibling contract evidence

The already-correct Clean Stocks CLI was used only as a bounded sibling
control. Its controlled runtime failure returned `1` with the existing error
and no artifact; patching its `main` to return `1` produced unified dispatcher
status `1` and exact `sys.argv` restoration. No Clean Stocks code or tests were
modified or audited beyond this control.

## Finding matrix

The six directly observed false-success boundaries are direct validation,
direct runtime, package validation, root validation, unified function
validation, and unified module validation. Each has one ordinary observation
test and one separate `@unittest.expectedFailure` future-contract test.

## Classification totals

- `DEFECT_CONFIRMED`: 6
- `CORRECTLY_HANDLED`: 7
- `CONTRACT_UNDECIDED`: 0
- `NOT_APPLICABLE`: 0
- `INFERENCE_ONLY`: 0

## Seven correctly handled controls

1. Legacy direct success
2. Root `runpy` package-main invocation
3. Package argparse
4. Root argparse
5. Unified argparse
6. Root import alias
7. Bounded sibling integer-status propagation

## Expected-failure inventory

The new characterization module contains exactly 19 tests: 13 ordinary passing
tests and six expected failures, one for each directly confirmed false-success
boundary. No current-behavior observation test is marked expected-failure.

## Direct evidence versus inference

The six defect classifications are based on deterministic direct, subprocess,
and unified-function observations. The future return/exit `1` behavior is the
approved standard contract being characterized, not an implemented fix. The
unchanged dispatcher behavior is directly evidenced by the bounded sibling
control and source inventory.

## Production files changed

None. No production code, unified dispatcher, parser, data loader, network
logic, or output logic was modified.

## Test file changed

- `tests/test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior.py`

## Documentation file changed

- `docs/TRACK_C8_1_STOCK_LIST_UPDATER_CLI_RUNTIME_EXIT_BEHAVIOR_CHARACTERIZATION.md`

## Exact validation commands and actual results

Targeted:

```text
py -m unittest tests.test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior
19 run; 13 passed; 6 expected failures; 0 ordinary failures; 0 errors; OK
```

Combined:

```text
py -m unittest tests.test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior tests.test_stock_list_updater tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_track_c7_1_clean_stocks_cli_runtime_exit_behavior tests.test_track_c6_1_benchmark_cli_runtime_exit_behavior tests.test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior tests.test_track_c4_1_scanner_cli_exit_behavior
163 run; 157 passed; 6 expected failures; 0 ordinary failures; 0 errors; OK
```

Canonical full suite:

```text
py -m unittest discover -s tests
1575 run; 1569 passed; 6 expected failures; 0 ordinary failures; 0 errors; OK
```

Secondary repository-Python suite:

```text
python -m unittest discover -s tests
1575 run; 1569 passed; 6 expected failures; 0 ordinary failures; 0 errors; OK
```

## `git diff --check` result

`git diff --check` passed with no output.

## UTF-8 BOM result

Both new files were validated as UTF-8 without BOM. No existing file encoding
or line ending was altered.

## External request result

No test made an external request. Direct and unified-function tests patched
`requests.get` or the fetch callable; subprocess tests injected the temporary
deterministic `sitecustomize.py` before module execution.

## Stock-list artifact result

No real `stocks.txt` or other stock-list output was created. Temporary output
paths remained absent, temporary helper directories disappeared, and no
persistent test artifact was created.

## Deferred C8.2 candidate scope

C8.2 may evaluate the bounded production change required to return `1` from
handled failures and propagate it through package/root executable guards. C8.2
was not started, completed, or authorized by this characterization.

## Production-fix restriction

This branch contains tests and documentation only. No production fix,
refactor, dependency change, configuration change, merge, rebase, squash, or
force-push was performed.

## Branch disposition

`HOLD`
