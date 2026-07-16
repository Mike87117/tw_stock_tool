# Track C6.1 Benchmark CLI Runtime Exit Behavior Characterization

## Executive outcome

Benchmark direct success preserves its legacy `None` return and existing
Summary, Detail, and Errors output. Direct validation and controlled unexpected
runtime failures visibly print the existing `Error: ...` wording, stop before
CSV export, and return `None`. The package module and root wrapper invoke
Benchmark but exit `0` for validation failure. Unified function and module
execution also report `0` because the unchanged dispatcher normalizes the
failed child `None` result to `0`.

The merged C2.5, C4, and C5 contracts establish status `1` for handled runtime
failure, `SystemExit(main())` propagation at package and root executable guards,
integer propagation through unified dispatch, and parser-owned status `2`.
Accordingly, six Benchmark false-success boundaries are confirmed defects and
are represented by exactly six expected-failure regression contracts. No
production fix is authorized or started.

Formal result: `Track C6.1 Characterization: PASS -- DEFECTS CONFIRMED`

## Repository baseline

- Repository: `Mike87117/tw_stock_tool`
- Required and observed `HEAD`: `71146c4b1fa155affc707b29dc2bb29d7cf6caf3`
- Required and observed `main`: `71146c4b1fa155affc707b29dc2bb29d7cf6caf3`
- Required and observed `origin/main`: `71146c4b1fa155affc707b29dc2bb29d7cf6caf3`
- Parent canonical suite: 1,518 tests; 1,518 passed; 0 expected failures; 0 failures; 0 errors
- Parent repository-Python suite: 1,518 tests; 1,518 passed; 0 expected failures; 0 failures; 0 errors
- Branch: `track-c6-1-benchmark-cli-runtime-exit-characterization`
- Initial branch relationship to `main`: 0 ahead, 0 behind
- `custom_md.md`: present, unread, unmodified, untracked, and ignored only by `.git/info/exclude`
- Previously retained ignored artifacts were non-blocking and were not deleted or modified by this track.

## LLM Wiki result

- Health: available; `ok: true`, `status: running`
- Version: `0.5.4`
- Active project: `tw_stock_tool Wiki`
- Search: `Benchmark CLI runtime exit status package root wrapper unified dispatcher SystemExit Track C2.5 C4 C5`
- Summary: keyword search returned 10 results and 13 token hits across phase history,
  CLI reference, current architecture, project overview, Scanner flow, backtest,
  tests/CI, workflow, checklist, and data/cache context. It did not supersede the
  repository source, tests, or merged C2.5/C4/C5 contract evidence.

## Existing Benchmark contract inventory

`tw_stock_tool.cli.benchmark.main()` parses arguments, gathers stock IDs, calls
`run_benchmark()`, prints Summary, Detail, and Errors, optionally exports three
CSV files, and catches every `Exception` with `Error: {exc}`. It has no explicit
success or failure return, so both successful direct calls and handled failures
return `None`. Argparse `SystemExit` is not caught because it is not an
`Exception` subclass.

The package executable guard calls `main()` without `SystemExit`. The root
compatibility wrapper aliases the package module on import and calls package
`main()` when executed, also without `SystemExit`. The unified dispatcher
restores `sys.argv`, propagates integer results, and maps legacy child `None` to
`0`; its module guard correctly raises `SystemExit(main())`.

Existing `tests/test_benchmark.py` covers benchmark aggregation, invalid worker
and repeat validation in `run_benchmark()`, and output-path naming. Existing
unified and root tests cover routing, help, general integer propagation, and
selected root wrappers. Before C6.1 they did not cover Benchmark direct `main()`
results, handled-failure process exits, Benchmark argparse exits at all three
boundaries, or Benchmark root import/executable separation.

## Invocation-boundary matrix

| Boundary | Invocation | Observed output | Function return | Process exit | Classification | Contract source | Future action |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| Direct success | `benchmark.main()` with synthetic result and `--stocks 2330` | Existing Summary, Detail, Errors | `None` | N/A | `CORRECTLY_HANDLED` | Legacy success compatibility | Preserve |
| Direct validation failure | `benchmark.main()` without stocks | `Error: benchmark stock list cannot be empty.`; no traceback | `None` | N/A | `DEFECT_CONFIRMED` | C2.5/C4/C5 runtime status | Return `1` after existing message |
| Direct runtime failure | `run_benchmark()` raises controlled `RuntimeError` | `Error: controlled benchmark failure`; no traceback | `None` | N/A | `DEFECT_CONFIRMED` | C2.5/C4/C5 runtime status | Return `1` after existing message |
| Package module | `python -m tw_stock_tool.cli.benchmark` | Validation error; no traceback | N/A | 0 | `DEFECT_CONFIRMED` | C2.5/C4/C5 module guard | Propagate callable status |
| Root wrapper | `python benchmark.py` | Validation error; no traceback; package `main()` invoked | N/A | 0 | `DEFECT_CONFIRMED` | C4/C5 root guard | Propagate callable status |
| Unified function | `twstock_cli.main(["benchmark"])` | Validation error; no traceback | 0 | N/A | `DEFECT_CONFIRMED` | C2.5 integer propagation | Fix child; leave dispatcher unchanged |
| Unified module | `python -m tw_stock_tool.cli.twstock_cli benchmark` | Validation error; no traceback | N/A | 0 | `DEFECT_CONFIRMED` | C2.5/C4/C5 propagation | Fix child; leave dispatcher unchanged |
| Package argparse | Package module plus invalid option | Usage and argparse error | N/A | 2 | `CORRECTLY_HANDLED` | Argparse/C2.5 | Preserve |
| Root argparse | Root wrapper plus invalid option | Usage and argparse error | N/A | 2 | `CORRECTLY_HANDLED` | Argparse/C4/C5 | Preserve |
| Unified argparse | Unified module plus invalid Benchmark option | Usage and argparse error | N/A | 2 | `CORRECTLY_HANDLED` | Argparse/C2.5 | Preserve |
| Root import | `import benchmark` | No command output | Package callable | N/A | `CORRECTLY_HANDLED` | Compatibility wrapper contract | Preserve alias |
| Sibling evidence | Controlled Scanner/Cache Manager failures and integer dispatch | Existing handled messages | 1 | N/A | `CORRECTLY_HANDLED` | Merged C4/C5 | Apply same bounded contract |

## Direct success result

A synthetic `BenchmarkResult` containing one summary row, one detail row, and an
empty errors frame was returned by a patched `run_benchmark()`. `_output_paths()`
returned `None`. The real `main()` called `run_benchmark()` once with stock
`2330` and the expected defaults, printed all three existing sections, returned
legacy `None`, and created no file or directory. No live scan occurred.

Classification: `CORRECTLY_HANDLED`.

## Direct validation-failure result

Calling real `main()` without stocks reached the existing validation in
`run_benchmark()` and printed `Error: benchmark stock list cannot be empty.`
without a traceback. It did not scan, call `_output_paths()`, or change the test
filesystem. Its observed result was `None`; the established handled-failure
contract requires `1`.

Classification: `DEFECT_CONFIRMED`.

## Direct unexpected-runtime-failure result

With only `run_benchmark()` patched to raise
`RuntimeError("controlled benchmark failure")`, real `main()` printed
`Error: controlled benchmark failure`, returned `None`, emitted no traceback,
did not call `_output_paths()`, and created no file. The established contract
requires `1`.

Classification: `DEFECT_CONFIRMED`.

## Package-module result

`sys.executable -m tw_stock_tool.cli.benchmark` without stocks printed the
existing validation error, emitted no traceback, and exited `0`. Failed work was
therefore reported as process success; the future contract requires exit `1`.

Classification: `DEFECT_CONFIRMED`.

## Root-wrapper result

`sys.executable benchmark.py` without stocks printed the Benchmark validation
error, emitted no traceback, and exited `0`. A separate `runpy` control directly
verified that root execution calls package `main()` once. The remaining defect
is status propagation, not failure to invoke Benchmark.

Classification: `DEFECT_CONFIRMED`.

## Unified function result

`twstock_cli.main(["benchmark"])` invoked the real Benchmark `main()`, printed
the validation error, restored `sys.argv`, generated no artifact, and returned
`0`. This is the unchanged dispatcher's documented legacy-`None` normalization;
the child failure result is the defect and the dispatcher must remain unchanged.

Classification: `DEFECT_CONFIRMED`.

## Unified module result

`sys.executable -m tw_stock_tool.cli.twstock_cli benchmark` printed the
validation error without a traceback and exited `0`. The unified module guard
correctly propagates its dispatcher result; the false success originates in the
Benchmark child returning `None`.

Classification: `DEFECT_CONFIRMED`.

## Argparse controls

Package, root, and unified invalid-option processes each printed argparse usage
and error output, emitted no traceback, and exited `2`. Parser ownership is
already correct at all three boundaries and is not represented as an expected
failure.

Classifications: three `CORRECTLY_HANDLED` controls.

## Root import compatibility

Importing root `benchmark` resolves to the same module object as
`tw_stock_tool.cli.benchmark`, and both expose the identical `main` callable.
Import compatibility is independent of root executable status propagation.

Classification: `CORRECTLY_HANDLED`.

## Sibling contract evidence

Merged Scanner and Cache Manager source, tests, and C4.2/C5.2 documents provide
bounded evidence that successful legacy direct calls may remain `None`, handled
runtime failures return `1`, package and root guards propagate through
`SystemExit`, unified dispatch propagates integer status without modification,
and argparse remains status `2`. The C6.1 control test confirmed controlled
Scanner and Cache Manager failures return `1` and the existing unified
dispatcher propagates an integer `1`.

Classification: `CORRECTLY_HANDLED` contract evidence.

## Finding matrix

| ID | Area | Scenario | Expected contract | Observed behavior | Evidence type | Classification | Production impact | Future action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C6.1-01 | Direct success | Synthetic successful result | Legacy `None` allowed | `None`; existing sections | Direct test | `CORRECTLY_HANDLED` | None | Preserve |
| C6.1-02 | Direct validation | Empty stocks | Return `1` | Error plus `None` | Direct test | `DEFECT_CONFIRMED` | Callable false success | Bounded C6.2 candidate |
| C6.1-03 | Direct runtime | Controlled `RuntimeError` | Return `1` | Error plus `None` | Direct test | `DEFECT_CONFIRMED` | Callable false success | Bounded C6.2 candidate |
| C6.1-04 | Package module | Empty stocks | Exit `1` | Exit `0` | Subprocess | `DEFECT_CONFIRMED` | Process false success | Bounded C6.2 candidate |
| C6.1-05 | Root wrapper | Empty stocks | Exit `1` | Benchmark invoked; exit `0` | Subprocess and `runpy` | `DEFECT_CONFIRMED` | Process false success | Bounded C6.2 candidate |
| C6.1-06 | Unified function | Benchmark validation failure | Return child integer `1` | Returns normalized `0` from child `None` | Direct test | `DEFECT_CONFIRMED` | Dispatcher caller false success | Fix child only |
| C6.1-07 | Unified module | Benchmark validation failure | Exit `1` | Exit `0` | Subprocess | `DEFECT_CONFIRMED` | Process false success | Fix child only |
| C6.1-08 | Package parser | Invalid option | Exit `2` | Exit `2` | Subprocess | `CORRECTLY_HANDLED` | None | Preserve |
| C6.1-09 | Root parser | Invalid option | Exit `2` | Exit `2` | Subprocess | `CORRECTLY_HANDLED` | None | Preserve |
| C6.1-10 | Unified parser | Invalid option | Exit `2` | Exit `2` | Subprocess | `CORRECTLY_HANDLED` | None | Preserve |
| C6.1-11 | Root import | Compatibility alias | Same module and callable | Same module and callable | Direct import | `CORRECTLY_HANDLED` | None | Preserve |
| C6.1-12 | Sibling contract | Scanner/Cache Manager failures | Status `1`; integer propagation | Status `1`; propagated | Direct bounded control | `CORRECTLY_HANDLED` | Contract applies | Reuse in C6.2 review |

Confirmed defects: 6. Contract-undecided: 0. Not-applicable: 0.
Inference-only: 0.

## Expected-failure inventory

Expected failures before C6.1: 0. Expected failures after C6.1: 6.

1. Direct validation failure should return `1`.
2. Direct unexpected runtime failure should return `1`.
3. Package-module validation failure should exit `1`.
4. Root-wrapper validation failure should exit `1`.
5. Unified function validation failure should return `1`.
6. Unified module validation failure should exit `1`.

Each expected failure represents one directly confirmed defect contract. No
success, argparse, import, inference, or unavailable-command case is marked as
an expected failure.

## Direct evidence versus inference

All twelve matrix rows are supported by deterministic direct tests,
subprocesses, direct imports, `runpy`, or bounded merged sibling controls. The
applicability of status `1` is supported by the merged C2.5/C4/C5 repository
contracts. No finding is based solely on inference or Wiki content.

## Production files changed

None.

## Test files changed

- Added `tests/test_track_c6_1_benchmark_cli_runtime_exit_behavior.py`.
- Exact new test count: 19.

## Documentation files changed

- Added `docs/TRACK_C6_1_BENCHMARK_CLI_RUNTIME_EXIT_BEHAVIOR_CHARACTERIZATION.md`.

## Validation commands

```powershell
py -m unittest tests.test_track_c6_1_benchmark_cli_runtime_exit_behavior
# 19 run; 13 passed; 6 expected failures; 0 failures; 0 errors; OK

py -m unittest tests.test_track_c6_1_benchmark_cli_runtime_exit_behavior tests.test_benchmark tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior tests.test_track_c4_1_scanner_cli_exit_behavior
# 113 run; 107 passed; 6 expected failures; 0 failures; 0 errors; OK

py -m unittest discover -s tests
# 1,537 run; 1,531 passed; 6 expected failures; 0 failures; 0 errors; OK

python -m unittest discover -s tests
# 1,537 run; 1,531 passed; 6 expected failures; 0 failures; 0 errors; OK
```

The final count is the 1,518-test parent plus exactly 19 new C6.1 tests.

## Deferred related candidates

- Clean Stocks CLI runtime exit behavior.
- Stock List Updater CLI runtime exit behavior.

Both remain recorded without testing or modification and are outside C6.1.

## Non-goals

No production code, existing test, existing documentation, scanner behavior,
output-path behavior, CSV-export behavior, or unified dispatcher behavior was
modified. No live stock scan or market-data access occurred. No Benchmark CSV
or output directory was generated. Retained ignored artifacts were untouched;
`custom_md.md` was not read or changed. No production fix or C6.2 work was
started, no branch was merged, and `main` was not pushed.

## Recommended next action

Hold this characterization branch for review. After approval, plan a separate,
bounded C6.2 production fix that preserves successful legacy `None`, existing
messages, argparse status `2`, import aliasing, and the unchanged unified
dispatcher while returning `1` for handled Benchmark failures and propagating
that status through package and root executable guards.

Branch disposition: `HOLD`.
