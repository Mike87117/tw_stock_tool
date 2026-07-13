# Track C2.5 Unified CLI Nonzero Exit Behavior

## Repository

- Branch: `track-c2-research-correctness-fixes`
- Baseline commit: `7c8183a51908ce547cdefc40fa19cf0104b32cee`
- Final commit is recorded in the execution report.

## Problem statement

AI Walk Forward and Analyze printed handled runtime errors but returned `None`, so their module entrypoints could exit successfully after failure. The unified `twstock` dispatcher also discarded child return values.

## Approved contract

- Successful AI Walk Forward and Analyze execution returns `0`.
- Handled runtime failure or cancellation returns `1`.
- Argparse continues to own parse failures through `SystemExit`.
- Module execution uses `raise SystemExit(main())`.
- The unified dispatcher propagates integer child statuses.
- Legacy child `None` returns are normalized to `0`.
- Child `SystemExit` is not swallowed, and temporary `sys.argv` replacement is always restored.

## Implementation summary

`ai_walk_forward.main()` and Analyze `main()` now return integer statuses while preserving their existing messages and exception categories. Their module guards raise `SystemExit` with that status. The unified dispatcher returns child integers, treats legacy `None` as success, and returns the selected handler status from `twstock_cli.main()`.

## Before and after

| Path | Before | After |
| -- | -- | -- |
| AI Walk Forward success | `None` | `0` |
| AI Walk Forward handled failure | printed error, returned `None` | same error, returns `1` |
| Analyze success | `None` | `0` |
| Analyze handled failure/cancel | printed message, returned `None` | same message, returns `1` |
| Unified dispatcher | discarded child return | propagates integers; `None` becomes `0` |

## Changed files

- `src/tw_stock_tool/ml/ai_walk_forward.py`
- `src/tw_stock_tool/cli/main.py`
- `src/tw_stock_tool/cli/twstock_cli.py`
- `tests/test_ai_walk_forward.py`
- `tests/test_main.py`
- `tests/test_twstock_cli.py`
- `tests/test_track_c1_research_correctness.py`
- `docs/TRACK_C1_RESEARCH_CORRECTNESS_CHARACTERIZATION.md`
- `docs/TRACK_C2_5_UNIFIED_CLI_EXIT_BEHAVIOR.md`

## Validation

Tests cover leaf success and handled failure, preserved output, argparse behavior, legacy `None` normalization, integer status propagation, Analyze failure propagation, child `SystemExit`, and `sys.argv` restoration. Verification commands include each of the four targeted modules, their combined suite, process-level success/failure checks, and the full unittest discovery suite.

- Expected failures before: 2
- Expected failures after: 0

## Preserved behavior

Existing argparse parsing, output wording, child argument forwarding, and legacy child CLIs remain unchanged. No public CLI arguments were added or removed.

## Non-goals

This phase does not migrate every child CLI to integer returns, change application logic, alter analysis or ML algorithms, modify Backtest or metrics, change root compatibility wrappers, create a pull request, merge to main, or perform the aggregate closeout audit.

## Remaining Track C2 work

No additional approved implementation item is started here. The next step is an aggregate closeout audit and merge decision.