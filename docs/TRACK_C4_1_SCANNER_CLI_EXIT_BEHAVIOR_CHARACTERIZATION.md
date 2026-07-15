# Track C4.1 Scanner CLI Runtime Exit Behavior Characterization

## Executive outcome

Scanner success remains compatible: its direct `main()` returns legacy `None` after successful work. In contrast, every directly tested Scanner runtime-failure category visibly reports failure, stops normal work, returns `None`, and produces success status at package, root-wrapper, and unified process boundaries.

Track C2.5 establishes the repository runtime-exit contract: successful execution returns `0`, handled runtime failures and cancellation return `1`, parser failures remain `SystemExit`, package module guards use `raise SystemExit(main())`, and the unified dispatcher propagates integer child statuses. It intentionally normalizes legacy child `None` only as a compatibility fallback, not as an intended failed-command status. Scanner violates that contract on its runtime-failure paths.

Formal result: `Track C4.1 Characterization: PASS — DEFECTS CONFIRMED`

## Repository and stacked-branch baseline

- Repository: `Mike87117/tw_stock_tool`
- `main` and `origin/main`: `e41181bbdcb79c6d8dffc5353b00755dfc2893bb`
- C3.1: `bfbcf135fc64ea66b6bd79625957445ac5b84923`
- C3.2: `653c78f59d2b031b87595169b180800b88996c3b`
- Parent branch: `track-c3-3-parameter-sweep-correctness-characterization`
- Parent HEAD: `8329de9ead09278edcadaba2b95fd70469be08ad`
- Parent relationship to main: 3 commits ahead, 0 behind
- Parent suite: 1,484 tests, 0 expected failures, 0 failures, 0 errors, `OK`
- C4.1 branch: `track-c4-1-scanner-cli-exit-characterization`
- C3.1 through C3.3 commits and historical files remained unchanged.

## LLM Wiki result

- Health: available; `ok: true`, `status: running`
- Version: `0.5.4`
- Active project: `tw_stock_tool Wiki`
- Search: `Scanner CLI runtime failure exit status unified dispatcher root wrapper SystemExit handled error cancellation`
- Summary: results covered CLI entrypoints, Scanner flow, architecture, and test context. They did not establish a more specific Scanner runtime-status exception. Repository source, C2.5 documentation, and deterministic tests remained authoritative.

## Existing CLI exit-contract inventory

`docs/TRACK_C2_5_UNIFIED_CLI_EXIT_BEHAVIOR.md` establishes that successful Analyze and AI Walk Forward commands return `0`, handled runtime failures and cancellation return `1`, parser failures remain owned by `argparse`, package module guards use `raise SystemExit(main())`, and the unified dispatcher propagates integer child statuses. Legacy child `None` is normalized to `0` only for compatibility.

`src/tw_stock_tool/cli/main.py` implements the approved `0`/`1` behavior for Analyze; direct and unified `analyze --stock ""` controls return `1`. `src/tw_stock_tool/ml/ai_walk_forward.py` likewise returns `0` or `1`. Existing `tests/test_twstock_cli.py` proves integer propagation, `SystemExit` propagation, `sys.argv` restoration, and parser failures. C2.5.1 updated only the `main.py`, `ai_walk_forward.py`, and `twstock_cli.py` root wrappers; it did not make Scanner an exception to the runtime-failure contract.

Scanner differs: `scan_stocks.main()` catches `ValueError`, `ReportError`, `KeyboardInterrupt`, and unexpected `Exception`, prints its existing message, then falls through with `None`. Its package module guard calls `main()` directly, its root wrapper calls `_impl.main()` directly, and the unified dispatcher normalizes its `None` to `0`.

## Invocation-boundary matrix

| Boundary | Invocation form | Observed message | Observed function return | Observed process exit | Classification | Contract source | Future action |
|---|---|---|---|---:|---|---|---|
| Direct success | `scan_stocks.main()` with mocked scan/export | Existing Excel/CSV/HTML summary | `None` | N/A | `CORRECTLY_HANDLED` | Legacy success compatibility | Preserve |
| Direct ValueError | Missing `--file` | Existing `錯誤：...` | `None` | N/A | `DEFECT_CONFIRMED` | C2.5 runtime failure returns 1 | Bounded C4.2 candidate |
| Direct ReportError | Exporter raises `ReportError` | Existing `錯誤：...` | `None` | N/A | `DEFECT_CONFIRMED` | C2.5 runtime failure returns 1 | Bounded C4.2 candidate |
| Direct cancellation | Scanner raises `KeyboardInterrupt` | Existing `已取消` | `None` | N/A | `DEFECT_CONFIRMED` | C2.5 cancellation returns 1 | Bounded C4.2 candidate |
| Direct unexpected error | Scanner raises `RuntimeError` | Existing `未預期錯誤：...` | `None` | N/A | `DEFECT_CONFIRMED` | C2.5 runtime failure returns 1 | Bounded C4.2 candidate |
| Package module | `python -m tw_stock_tool.cli.scan_stocks --file <missing>` | Existing `錯誤：...`; no traceback | N/A | 0 | `DEFECT_CONFIRMED` | C2.5 module guard contract | Bounded C4.2 candidate |
| Root wrapper | `python scan_stocks.py --file <missing>` | Existing `錯誤：...`; no traceback | N/A | 0 | `DEFECT_CONFIRMED` | C2.5.1 root-wrapper propagation | Bounded C4.2 candidate |
| Unified function | `twstock_cli.main(["scan", "--file", <missing>])` | Existing `錯誤：...` | 0 | N/A | `DEFECT_CONFIRMED` | C2.5 integer-status propagation | Bounded C4.2 candidate |
| Unified module | `python -m tw_stock_tool.cli.twstock_cli scan --file <missing>` | Existing `錯誤：...`; no traceback | N/A | 0 | `DEFECT_CONFIRMED` | C2.5 dispatcher/module contract | Bounded C4.2 candidate |
| Console mapping | `pyproject.toml` `twstock` entrypoint | Mapping is direct to unified `main` | `main` callable | N/A | `CORRECTLY_HANDLED` | `pyproject.toml` | Preserve mapping |
| Installed console command | Local `twstock.exe` | `ModuleNotFoundError` before Scanner loads | N/A | 1 | `NOT_APPLICABLE` | Current environment limitation | Do not install during this track |
| Argparse control | Invalid `--workers` at Scanner/unified boundaries | argparse usage/error | raises `SystemExit(2)` | N/A | `CORRECTLY_HANDLED` | argparse and C2.5 | Preserve |

## Direct Scanner success result

With only Scanner and export boundaries mocked, direct Scanner `main()` printed its existing Excel, CSV, and HTML summaries, returned `None`, and raised no exception. The exporter mock returned paths but created no files. This is the existing legacy success contract and is not a defect.

Classification: `CORRECTLY_HANDLED`.

## Direct handled-failure result

A guaranteed nonexistent stock-list file raised `ValueError` before scanning. Scanner printed its existing handled-error message, did not begin scanning or exporting, raised no `SystemExit`, returned `None`, and created no files. C2.5 directly establishes that a handled runtime failure should return `1`; this is a confirmed defect.

Classification: `DEFECT_CONFIRMED`.

## ReportError result

A real `ReportError` raised by the mocked ranking exporter retained Scanner's existing handled-error message. It did not reach the later success summary or error-log work, returned `None`, and left no artifact. The handled report failure falls under the same C2.5 runtime-status contract.

Classification: `DEFECT_CONFIRMED`.

## Cancellation result

`KeyboardInterrupt` at the Scanner execution boundary printed the existing cancellation message, was swallowed, returned `None`, did not invoke exporting, and created no artifact. C2.5 explicitly includes cancellation in the `1`-status runtime contract.

Classification: `DEFECT_CONFIRMED`.

## Unexpected-error result

A deterministic `RuntimeError` printed Scanner's existing unexpected-error message, was swallowed, returned `None`, did not export, and created no artifact. The C2.5 failure-status contract covers handled unexpected runtime failures without changing exception ownership or output wording.

Classification: `DEFECT_CONFIRMED`.

## Package module process result

`sys.executable -m tw_stock_tool.cli.scan_stocks --file <missing>` printed the existing handled file error without a traceback and exited `0`. The package guard calls `main()` rather than `raise SystemExit(main())`, so a visibly failed command reports operating-system success.

Classification: `DEFECT_CONFIRMED`; failure exit code: `0`.

## Root wrapper process result

`sys.executable scan_stocks.py --file <missing>` printed the same handled file error without a traceback and exited `0`. The root compatibility wrapper discards the package `main()` result instead of propagating it through `SystemExit`.

Classification: `DEFECT_CONFIRMED`; failure exit code: `0`.

## Unified function result

`twstock_cli.main(["scan", "--file", <missing>])` preserved Scanner's error output and restored `sys.argv`, but returned `0`. The unified dispatcher correctly propagates integers and intentionally normalizes legacy `None` to `0`; Scanner's failed `None` therefore becomes a false success.

Classification: `DEFECT_CONFIRMED`; failure status: `0`.

## Unified module process result

`sys.executable -m tw_stock_tool.cli.twstock_cli scan --file <missing>` printed Scanner's error without a traceback and exited `0`. Its module guard is correct; the incorrect child status is what it accurately propagates.

Classification: `DEFECT_CONFIRMED`; failure exit code: `0`.

## Console-script entrypoint result

`pyproject.toml` directly maps `twstock` to `tw_stock_tool.cli.twstock_cli:main`, and that callable was importable in the test interpreter. A `twstock.exe` command exists in a different local Python installation but fails with `ModuleNotFoundError` before Scanner loads. No package was installed or changed, so installed-command Scanner execution is `NOT_APPLICABLE` in the current environment.

## Argparse control result

Invalid Scanner arguments cause `SystemExit(2)` at both direct Scanner and unified Scanner boundaries. The Scanner runtime handlers do not swallow parser failures, and unified dispatch does not convert them to `0`.

Classification: `CORRECTLY_HANDLED`.

## Sibling CLI control evidence

The C2.5 Analyze path is a bounded direct control: `analyze_cli.main(["--stock", ""])` returns `1`, and `twstock_cli.main(["analyze", "--stock", ""])` propagates `1`. Existing C2.5 source and tests establish equivalent AI Walk Forward behavior. This supports applying the runtime-failure status contract to Scanner rather than treating Scanner's failed `None` as an intended success contract.

Classification: `CORRECTLY_HANDLED`.

## Finding matrix

| ID | Area | Scenario | Expected contract | Observed behavior | Evidence type | Classification | Production impact | Future action |
|---|---|---|---|---|---|---|---|---|
| A | Scanner success | Mocked normal execution | Legacy success may return `None` | Existing summaries, no exception, `None`, no file | Direct boundary test | `CORRECTLY_HANDLED` | Compatibility preserved | None |
| B | Scanner runtime status | Missing input file | Handled failure returns nonzero | Message, no scan/export, `None` | Direct deterministic test | `DEFECT_CONFIRMED` | Direct callers cannot distinguish failure from legacy success | C4.2 candidate |
| C | Scanner runtime status | Export `ReportError` | Handled failure returns nonzero | Message, no summary, `None` | Direct deterministic test | `DEFECT_CONFIRMED` | Automation can read success after failed export | C4.2 candidate |
| D | Scanner cancellation | `KeyboardInterrupt` | Cancellation returns nonzero | Message, no export, `None` | Direct deterministic test | `DEFECT_CONFIRMED` | Cancellation is reported as success | C4.2 candidate |
| E | Scanner runtime status | Unexpected exception | Handled failure returns nonzero | Message, no export, `None` | Direct deterministic test | `DEFECT_CONFIRMED` | Unexpected failure is reported as success | C4.2 candidate |
| F | Package process | Missing file | Module propagates `main()` status | Visible failure, exit `0` | Offline subprocess | `DEFECT_CONFIRMED` | Shell automation receives success | C4.2 candidate |
| G | Root process | Missing file | Wrapper propagates `main()` status | Visible failure, exit `0` | Offline subprocess | `DEFECT_CONFIRMED` | Compatibility command receives success | C4.2 candidate |
| H | Unified function | Real Scanner missing file | Dispatcher receives child nonzero | Visible failure, return `0` | Direct deterministic test | `DEFECT_CONFIRMED` | Programmatic unified callers receive success | C4.2 candidate |
| I | Unified process | Missing file | Module exits with child nonzero | Visible failure, exit `0` | Offline subprocess | `DEFECT_CONFIRMED` | `twstock scan` reports success after failure | C4.2 candidate |
| J | Console mapping | `twstock` entrypoint | Maps to unified `main` | Mapping and callable confirmed | Direct configuration evidence | `CORRECTLY_HANDLED` | Entrypoint declaration is correct | None |
| K | Parser | Invalid `--workers` | argparse owns nonzero parse failures | `SystemExit(2)` at Scanner and unified boundaries | Direct deterministic test | `CORRECTLY_HANDLED` | Parser contract remains intact | None |
| L | C2.5 sibling | Analyze empty stock | Runtime failure returns and propagates 1 | Direct and unified status `1` | Direct deterministic control | `CORRECTLY_HANDLED` | Confirms applicable sibling contract | None |

## Expected-failure inventory

- Before C4.1: 0
- Added by C4.1: 8
- After C4.1: 8
- Confirmed defects: 8
- Contract-undecided findings: 0
- Not-applicable findings: 1
- Inference-only findings: 0

Each expected failure isolates one established nonzero-status contract: the four direct Scanner runtime categories, package module, root wrapper, unified function, and unified module. No expected failure covers success behavior, the unavailable installed command, or argparse control behavior.

## Direct evidence versus inference

All Scanner classifications are based on deterministic direct invocation or subprocess evidence. The missing-file path fails before download, so no market-data network access occurs. The console script's declared mapping is direct evidence; actual installed-command Scanner execution is unavailable in this environment because its launcher cannot import the package. No classification is inference-only.

## Production files changed

None.

## Test files changed

- Added `tests/test_track_c4_1_scanner_cli_exit_behavior.py` with 20 tests.

## Documentation files changed

- Added `docs/TRACK_C4_1_SCANNER_CLI_EXIT_BEHAVIOR_CHARACTERIZATION.md`.

## Validation commands

```powershell
py -m unittest tests.test_track_c4_1_scanner_cli_exit_behavior
# Ran 20 tests; 12 passed; 8 expected failures; 0 failures; 0 errors; OK

py -m unittest tests.test_track_c4_1_scanner_cli_exit_behavior tests.test_scanner tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_main tests.test_ai_walk_forward tests.test_track_c3_1_scanner_daily_correctness
# Ran 125 tests; 117 passed; 8 expected failures; 0 failures; 0 errors; OK

py -m unittest discover -s tests
# Ran 1,504 tests; 1,496 passed; 8 expected failures; 0 failures; 0 errors; OK
```

The full count increased from 1,484 to 1,504, exactly matching the 20 new tests.

## Non-goals

This track did not modify Scanner, unified dispatch, root wrappers, arguments, output wording, reports, exporters, dependencies, `pyproject.toml`, `.gitignore`, or production behavior. It did not access market data, create Scanner artifacts, start C4.2, merge a branch, push `main`, or continue to another phase. `custom_md.md` was not accessed or changed.

## Recommended next action

Hold this characterization branch. A separate, bounded C4.2 production-fix phase may be planned to make Scanner runtime failures return `1` and propagate that existing status through the package module, root wrapper, and unified command without changing output wording or parser exception ownership.

Branch disposition: `HOLD`.
