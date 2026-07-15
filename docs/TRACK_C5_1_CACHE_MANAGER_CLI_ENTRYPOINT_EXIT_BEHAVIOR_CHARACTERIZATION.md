# Track C5.1 Cache Manager CLI Entrypoint and Runtime Exit Behavior Characterization

## Executive outcome

Direct Cache Manager success preserves the legacy `None` return for `--list`,
`--clear`, and `--summary`. Each direct handled runtime failure also returns
`None` after printing the existing error, confirming three direct runtime-status
defects under the C2.5/C4 contract.

The package module catches a controlled runtime failure and exits `0`. The root
wrapper imports the package module but does not invoke Cache Manager when run as
a script; it exits `0` for both a controlled runtime scenario and an invalid
argument. The unified function and module also report `0` after the failed
Cache Manager child because unified dispatch normalizes legacy `None` to `0`.

Package and unified argparse controls correctly exit `2`, and root import
compatibility remains intact. No production fix is authorized in C5.1.

Formal result: `Track C5.1 Characterization: PASS -- DEFECTS CONFIRMED`

## Repository baseline

- Repository: `Mike87117/tw_stock_tool`
- `main`: `e0c1a4eae6c3a1079a17d22c538407d0aed84eda`
- `origin/main`: `e0c1a4eae6c3a1079a17d22c538407d0aed84eda`
- Parent full suite: 1,504 tests; 1,504 passed; 0 expected failures; 0 failures; 0 errors
- Characterization branch: `track-c5-1-cache-manager-cli-entrypoint-exit-characterization`
- Initial branch relation to `main`: 0 ahead, 0 behind
- `custom_md.md`: present, unread, unmodified, and ignored only through `.git/info/exclude`

## LLM Wiki result

- Health: available; `ok: true`, `status: running`
- Version: `0.5.4`
- Active project: `tw_stock_tool Wiki`
- Search: `Cache Manager CLI root wrapper entrypoint runtime exit status unified dispatcher SystemExit Track C2.5 C4`
- Summary: 13 keyword hits across phase history, CLI reference, cache/data pipeline,
  architecture, project overview, Scanner flow, tests/CI, and related project notes.
  The Wiki remained supporting context only; repository source, tests, and C2.5/C4
  evidence were authoritative.

## Existing Cache Manager contract inventory

`src/tw_stock_tool/data/cache_manager.py` exposes a mutually exclusive argparse
interface for `--list`, `--clear`, and `--summary`. It calls the selected
`cache_utils` operation, prints the existing result, catches `Exception`, prints
the existing error wording, and implicitly returns `None` on both success and
handled failure. Its module guard calls `main()` directly.

`cache_manager.py` is an import compatibility wrapper. It aliases
`tw_stock_tool.data.cache_manager` through `sys.modules`, but has no executable
guard and therefore performs no command work when run as a script.

`tw_stock_tool.cli.twstock_cli` dispatches the `cache` subcommand through
`_dispatch_existing_main`; it restores `sys.argv` and converts child `None` to
`0`. Its module guard correctly propagates the unified callable through
`SystemExit`.

Existing tests cover Cache Manager dispatch, argument forwarding, cache utility
behavior, and integer child-status propagation. They did not cover Cache
Manager runtime status, package execution, root execution, or root parser
ownership.

## Invocation-boundary matrix

| Boundary | Invocation | Observed output | Function return | Process exit | Classification | Contract source | Future action |
|---|---|---|---|---:|---|---|---|
| Direct list success | `main(--list)` with mocked list operation | Existing paths printed | `None` | N/A | `CORRECTLY_HANDLED` | Legacy success compatibility | Preserve |
| Direct clear success | `main(--clear)` with mocked clear operation | Existing count printed | `None` | N/A | `CORRECTLY_HANDLED` | Legacy success compatibility | Preserve |
| Direct summary success | `main(--summary)` with mocked summary | Existing table printed | `None` | N/A | `CORRECTLY_HANDLED` | Legacy success compatibility | Preserve |
| Direct list failure | Mocked `RuntimeError` | Existing error plus controlled message | `None` | N/A | `DEFECT_CONFIRMED` | C2.5/C4 runtime failure contract | Separate bounded fix |
| Direct clear failure | Mocked `RuntimeError` | Existing error plus controlled message | `None` | N/A | `DEFECT_CONFIRMED` | C2.5/C4 runtime failure contract | Separate bounded fix |
| Direct summary failure | Mocked `RuntimeError` | Existing error plus controlled message | `None` | N/A | `DEFECT_CONFIRMED` | C2.5/C4 runtime failure contract | Separate bounded fix |
| Package module | `python -m tw_stock_tool.data.cache_manager --summary` with patched dependency | Existing error; no traceback | N/A | `0` | `DEFECT_CONFIRMED` | Package guard contract | Separate bounded fix |
| Root wrapper runtime | `python cache_manager.py --summary` with patched dependency | No Cache Manager output | N/A | `0` | `DEFECT_CONFIRMED` | Root executable contract | Separate bounded fix |
| Root wrapper parser | `python cache_manager.py --definitely-invalid-option` | No argparse usage/error | N/A | `0` | `DEFECT_CONFIRMED` | Root parser ownership contract | Separate bounded fix |
| Unified function | `twstock_cli.main([cache, --summary])` with patched dependency | Existing error; argv restored | `0` | N/A | `DEFECT_CONFIRMED` | Unified integer propagation | Separate bounded fix |
| Unified module | `python -m tw_stock_tool.cli.twstock_cli cache --summary` with patched dependency | Existing error; no traceback | N/A | `0` | `DEFECT_CONFIRMED` | Unified module guard plus child status | Separate bounded fix |
| Package argparse | Invalid package option | argparse usage/error | N/A | `2` | `CORRECTLY_HANDLED` | argparse | Preserve |
| Unified argparse | Invalid cache option | argparse usage/error | N/A | `2` | `CORRECTLY_HANDLED` | argparse | Preserve |
| Root import | `import cache_manager` | Package alias retained | Same package `main` | N/A | `CORRECTLY_HANDLED` | Compatibility wrapper | Preserve |

## Direct success results

All three operation branches were independently mocked. The selected operation
was called exactly once, non-selected operations were not called, existing
success values were printed, direct `main()` returned legacy `None`, and no
temporary file was created or deleted. `--clear` never touched the real cache.

Classification: `CORRECTLY_HANDLED`.

## Direct list-failure result

`list_cache_files` raised `RuntimeError("controlled list failure")`. Cache
Manager printed its existing handled-error wording, swallowed the exception,
did not call clear or summary, returned `None`, and changed no temporary file.

Classification: `DEFECT_CONFIRMED`; expected future status: `1`.

## Direct clear-failure result

`clear_cache` raised `RuntimeError("controlled clear failure")`. The existing
error output was preserved, no real cache was cleared, no other operation ran,
and direct `main()` returned `None`.

Classification: `DEFECT_CONFIRMED`; expected future status: `1`.

## Direct summary-failure result

`cache_summary` raised `RuntimeError("controlled summary failure")`. The
existing error output was preserved, no other operation ran, no file changed,
and direct `main()` returned `None`.

Classification: `DEFECT_CONFIRMED`; expected future status: `1`.

## Package-module process result

With `cache_utils.cache_summary` patched before loading the module through
`runpy`, the package module printed the controlled failure without a traceback
and exited `0`. Its direct `main()` call is not propagated through
`SystemExit`.

Classification: `DEFECT_CONFIRMED`; observed exit: `0`; expected future exit: `1`.

## Root-wrapper runtime result

The root wrapper imported the package implementation but did not invoke
Cache Manager when run through `runpy.run_path`. The controlled summary failure
message never appeared and the process exited `0`.

Classification: `DEFECT_CONFIRMED`; observed exit: `0`; expected future exit: `1`.

## Root-wrapper argparse result

`cache_manager.py --definitely-invalid-option` produced no parser usage/error
because the wrapper never invoked the package `main()` or its parser. It exited
`0` instead of the required `2`.

Classification: `DEFECT_CONFIRMED`; observed exit: `0`; expected future exit: `2`.

## Unified function result

Patching only the Cache Manager summary dependency preserved the existing error
output and restored `sys.argv`, but `twstock_cli.main(["cache", "--summary"])`
returned `0` because the child returned legacy `None`.

Classification: `DEFECT_CONFIRMED`; observed status: `0`; expected future status: `1`.

## Unified module result

The unified module guard correctly used `SystemExit`, but it propagated the
unified function's normalized `0`. The controlled failure had no traceback and
the process exited `0`.

Classification: `DEFECT_CONFIRMED`; observed exit: `0`; expected future exit: `1`.

## Argparse controls

Package and unified invalid-argument controls both exited `2` with argparse
usage/error output. No expected failures were added for parser behavior.

Classification: `CORRECTLY_HANDLED`.

## Root import compatibility

Importing root `cache_manager` still aliases
`tw_stock_tool.data.cache_manager`, and the `main` object is shared.

Classification: `CORRECTLY_HANDLED`.

## Sibling CLI contract evidence

Bounded C2.5/C4 source and existing tests establish that handled runtime
failures return `1`, package/root guards propagate through `SystemExit`, unified
dispatch propagates integer statuses, and argparse retains code `2`. No other
CLI was characterized or modified.

Classification: `CORRECTLY_HANDLED`.

## Finding matrix

| ID | Area | Scenario | Expected contract | Observed behavior | Evidence type | Classification | Production impact | Future action |
|---|---|---|---|---|---|---|---|---|
| C5.1-1 | Direct list | Runtime exception | Return `1` | Returns `None` | Direct test | `DEFECT_CONFIRMED` | False success to caller | C5.2 candidate |
| C5.1-2 | Direct clear | Runtime exception | Return `1` | Returns `None` | Direct test | `DEFECT_CONFIRMED` | False success to caller | C5.2 candidate |
| C5.1-3 | Direct summary | Runtime exception | Return `1` | Returns `None` | Direct test | `DEFECT_CONFIRMED` | False success to caller | C5.2 candidate |
| C5.1-4 | Package module | Runtime exception | Exit `1` | Exits `0` | Subprocess test | `DEFECT_CONFIRMED` | False process success | C5.2 candidate |
| C5.1-5 | Root wrapper | Runtime execution | Invoke and exit `1` | Does not invoke; exits `0` | Subprocess test | `DEFECT_CONFIRMED` | Root command is inert | C5.2 candidate |
| C5.1-6 | Root wrapper | Invalid argument | Parser exit `2` | No parser; exits `0` | Subprocess test | `DEFECT_CONFIRMED` | Invalid input accepted | C5.2 candidate |
| C5.1-7 | Unified function | Runtime exception | Status `1` | Normalizes to `0` | Direct test | `DEFECT_CONFIRMED` | False unified success | C5.2 candidate |
| C5.1-8 | Unified module | Runtime exception | Exit `1` | Exits `0` | Subprocess test | `DEFECT_CONFIRMED` | False process success | C5.2 candidate |

## Expected-failure inventory

- Before C5.1: 0 expected failures.
- After C5.1: 8 expected failures.
- The eight contracts are the three direct runtime statuses, package runtime
  exit, root runtime/entrypoint behavior, root parser ownership, unified
  function status, and unified module exit.
- No expected failures cover legacy success `None`, parser controls that already
  return `2`, or root import compatibility.

## Direct evidence versus inference

Direct and subprocess tests provide the observed returns, exits, output, and
file-preservation evidence. The future status `1` and root executable
propagation are contract-based regression expectations grounded in C2.5/C4;
they are not production changes in this track.

## Production files changed

None.

## Test files changed

- `tests/test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior.py`

## Documentation files changed

- `docs/TRACK_C5_1_CACHE_MANAGER_CLI_ENTRYPOINT_EXIT_BEHAVIOR_CHARACTERIZATION.md`

## Validation commands

Parent baseline before branching:

```text
py -m unittest discover -s tests       # 1,504 passed, 0 expected failures
python -m unittest discover -s tests   # 1,504 passed, 0 expected failures
```

C5.1 targeted and combined validation will be recorded after the new tests are
executed. No live market-data service or real cache operation is used.

## Deferred related candidates

Benchmark CLI runtime exit behavior, Clean Stocks CLI runtime exit behavior, and
Stock List Updater CLI runtime exit behavior require separate future
prioritization and are outside C5.1.

## Non-goals

No production code, existing tests, documentation, Cache Manager behavior,
Cache Manager root wrapper, unified CLI implementation, cache utility, ignore
rule, dependency, or retained artifact was modified. No real cache file was
read, cleared, deleted, or written. No Scanner, Benchmark, Clean Stocks, Stock
List Updater, Doctor, or other CLI was characterized as a production target.
No branch was merged and no C5.2 fix was started.

## Recommended next action

Hold this characterization branch for separate review. If approved, plan a
bounded C5.2 production fix for the eight confirmed contracts without changing
successful operation semantics or output wording.

Branch disposition: `HOLD`.
