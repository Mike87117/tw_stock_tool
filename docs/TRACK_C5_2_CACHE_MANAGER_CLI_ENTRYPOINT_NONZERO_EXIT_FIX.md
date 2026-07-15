# Track C5.2 Cache Manager CLI Entrypoint and Nonzero Runtime Exit Fix

## Executive outcome

Track C5.2 is implemented on the approved C5.1 parent. Cache Manager failures now return status `1` through direct calls, the package module, and the root wrapper while preserving successful return values and existing output wording. `Track C5.2 Implementation: PASS — READY FOR REVIEW`.

## Repository and stacked-branch baseline

- Main baseline: `e0c1a4eae6c3a1079a17d22c538407d0aed84eda` (`main` and `origin/main`).
- Parent: `track-c5-1-cache-manager-cli-entrypoint-exit-characterization` at `689e1dd19065ef60d4f3a27ba3e9ab454f3ca474`.
- Implementation branch: `track-c5-2-cache-manager-cli-entrypoint-nonzero-exit-fix`.
- Parent relation to main before implementation: ahead `2`, behind `0`.

## LLM Wiki result

The approved local Wiki search was healthy and returned keyword hits for Cache Manager entrypoints, CLI exit propagation, unified dispatch, and the C5.1 phase history. No repository behavior was inferred from the Wiki in place of runtime validation.

## Confirmed defects

- Cache Manager `main()` was annotated as returning `None` and swallowed exceptions without a nonzero status.
- The package and root `__main__` paths did not propagate a returned status through `SystemExit`.
- The C5.1 regression tests therefore retained exactly eight expected failures for nonzero runtime behavior.

## Approved behavior contract

- Direct successful list, clear, and summary calls return `None`.
- Direct list, clear, and summary failures return `1` and preserve the exact existing `錯誤：...` output wording.
- Package execution raises `SystemExit` with status `1` on failure.
- Root-wrapper execution invokes Cache Manager and raises `SystemExit` with status `1` on failure; invalid root-wrapper arguments remain status `2`.
- Unified function dispatch returns status `1` for Cache Manager failure; unified module execution exits `1`.
- Package and unified invalid-argument behavior remains status `2`.
- Root import compatibility remains an alias to the package implementation.

## Implementation scope

Only the approved production and regression-test files were changed:

- `src/tw_stock_tool/data/cache_manager.py`
- `cache_manager.py`
- `tests/test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior.py`
- `docs/TRACK_C5_2_CACHE_MANAGER_CLI_ENTRYPOINT_NONZERO_EXIT_FIX.md`

The unified dispatcher, `cache_utils.py`, and all unrelated tests/docs were left unchanged. No real cache read, clear, delete, or write operation was performed.

## Direct Cache Manager results

The C5.1 direct-call cases now pass with the approved contract: successful list/clear/summary calls return `None`; all corresponding failure cases return `1`; and the existing error text is unchanged.

## Package module result

`python -m tw_stock_tool.data.cache_manager` preserves successful behavior and exits `1` for the forced failure path via `raise SystemExit(main())`.

## Root wrapper runtime result

`python cache_manager.py` invokes the package implementation and exits `1` for the forced failure path. The wrapper keeps import alias compatibility while adding executable status propagation.

## Root wrapper argparse result

Invalid root-wrapper arguments continue to exit with status `2`.

## Unified function result

Unified function dispatch continues to route Cache Manager unchanged and returns status `1` for the forced Cache Manager failure.

## Unified module result

Unified module execution continues to propagate the Cache Manager failure as process exit status `1`.

## Package and unified argparse preservation

Package and unified invalid-argument paths remain status `2`; no parser or dispatcher behavior was changed.

## Root import compatibility preservation

Importing the root wrapper continues to expose the package module object through `sys.modules`, preserving the existing alias behavior.

## Expected-failure resolution

Exactly eight C5.1 `@unittest.expectedFailure` decorators were removed. The C5 module now runs `14` tests with `14` passes, `0` expected failures, `0` failures, and `0` errors.

## Production files changed

- `src/tw_stock_tool/data/cache_manager.py`: return annotation, failure return `1`, and package `SystemExit` guard.
- `cache_manager.py`: executable wrapper status propagation with preserved import aliasing.

## Test files changed

- `tests/test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior.py`: only the eight obsolete expected-failure decorators were removed.

## Documentation files changed

- `docs/TRACK_C5_2_CACHE_MANAGER_CLI_ENTRYPOINT_NONZERO_EXIT_FIX.md`: this implementation and validation record.

## Validation commands

- C5 module: `py -m unittest tests.test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior` — `14` run, `14` pass, `0` expected failures/failures/errors.
- Combined exact regression set — `91` run, `91` pass, `0` expected failures/failures/errors.
- Full canonical suite: `py -m unittest discover -s tests` — `1518` run, `1518` pass, `0` expected failures/failures/errors.
- Required full suite: `python -m unittest discover -s tests` — `1518` run, `1518` pass, `0` expected failures/failures/errors.
- `git diff --check` — pass.
- All four changed files are UTF-8 without BOM.

## Deferred related candidates

- Benchmark CLI runtime exit behavior.
- Clean Stocks CLI runtime exit behavior.
- Stock List Updater CLI runtime exit behavior.

## Non-goals

No C5.3 work, no changes to unrelated CLI entrypoints, no cache operations, no ignored-artifact changes, no `custom_md.md` access or modification, and no merge to `main`.

## Recommended next action

Review and merge this branch into the approved integration target only after the final pushed-branch checks confirm the branch is ahead `3`, behind `0`, with `main` unchanged.
