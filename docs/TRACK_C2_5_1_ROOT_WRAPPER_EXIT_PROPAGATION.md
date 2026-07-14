# Track C2.5.1 Root Compatibility Wrapper Exit Propagation

## Repository

- Branch: `track-c2-research-correctness-fixes`
- Baseline commit: `a54ee7ef996d87ededd6ef07a390c5af16914354`
- Final commit is recorded in the execution report.

## Aggregate-audit blocker

Track C2.5 made the package CLI modules return integer statuses, but their root compatibility wrappers called `_impl.main()` without propagating the result. Direct root-wrapper commands could therefore report operating-system success after handled failures.

## Previous scope conflict and resolution

The first attempt correctly stopped because `tests/test_twstock_cli.py` asserted that root script execution completed without `SystemExit`, while that file was outside the original allowed scope. The revised scope permits updating only `test_root_twstock_cli_wrapper_executes_package_main_when_run_as_script`; it now verifies `SystemExit(0)` from a mocked package `main()` returning `0`.

## Affected wrappers

- `main.py`
- `ai_walk_forward.py`
- `twstock_cli.py`

## Before and after process behavior

Before this follow-up, each wrapper discarded the package implementation's return value. Each wrapper now executes `raise SystemExit(_impl.main())`, so handled failures exit with `1`, help exits with `0`, and existing argparse or child `SystemExit` behavior passes through unchanged.

## Subprocess verification

Dedicated tests run all three root wrappers as real child processes using an empty stock argument and verify exit code `1` plus representative existing output. Separate help cases verify exit code `0` and `usage:` output. Platform-locale text decoding preserves CP950 output on Traditional Chinese Windows. These paths do not access market data.

## Preserved import compatibility

The imported-wrapper branch still assigns `_sys.modules[__name__] = _impl`. Tests confirm importing each root wrapper resolves to the corresponding package implementation and `main` function.

## Updated existing wrapper test

`test_root_twstock_cli_wrapper_executes_package_main_when_run_as_script` continues to execute the real root wrapper through `runpy.run_path`, proves package `main()` is called once, and now proves its returned `0` becomes `SystemExit.code`.

## Changed files

- `ai_walk_forward.py`
- `main.py`
- `twstock_cli.py`
- `tests/test_root_cli_wrapper_exit_codes.py`
- `tests/test_twstock_cli.py`
- `docs/TRACK_C2_5_UNIFIED_CLI_EXIT_BEHAVIOR.md`
- `docs/TRACK_C2_5_1_ROOT_WRAPPER_EXIT_PROPAGATION.md`

## Tests executed

- Root-wrapper subprocess tests
- Unified CLI tests
- AI Walk Forward tests
- Analyze tests
- Track C1 research-correctness tests
- Combined targeted suite
- Full unittest discovery suite
- Direct root-wrapper process checks

## Non-goals

This follow-up does not modify package CLI implementations, other root wrappers, application behavior, Backtest or metrics, arguments, output text, dependencies, `pyproject.toml`, or README. It does not merge to main, create a pull request, start high-level interval propagation, or start another Track.

## Next step

Rerun the aggregate Track C2 closeout audit.
