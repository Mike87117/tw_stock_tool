# Track C12.2 — Backtest Result Export CLI Runtime Exit Contract Fix

## 1. Executive outcome

Track C12.2 is complete. The backtest-result-export CLI now returns integer status `1` from runtime-error paths, preserves the existing stderr wording, and exits through the package guard with `raise SystemExit(main())`.

## 2. Formal implementation result

The implementation closes the three C12.1 runtime-exit defects with the smallest production change: exception handlers return `1`, successful execution still returns `None`, and the module guard owns process termination.

## 3. Verified parent branch and commit

The verified parent branch is `track-c12-1-backtest-result-export-cli-runtime-exit-characterization` at commit `05779f136d260035cb435d93b668d73fca663c19`.

## 4. Main baseline and ancestry

`main` and `origin/main` both resolve to `af53c68dfb0c141ecae6159866a559206a34cb93`. The parent commit has that baseline as its merge base and is two commits ahead with zero commits behind.

## 5. New branch

The implementation branch is `track-c12-2-backtest-result-export-cli-runtime-exit-fix`, created directly from the verified C12.1 parent.

## 6. Exact changed paths

Only these four paths are in scope:

1. `src/tw_stock_tool/cli/backtest_result_export_cli.py`
2. `tests/test_backtest_result_export_cli.py`
3. `tests/test_track_c12_1_backtest_result_export_cli_runtime_exit_behavior.py`
4. `docs/TRACK_C12_2_BACKTEST_RESULT_EXPORT_CLI_RUNTIME_EXIT_FIX.md`

## 7. Pre-fix contract

Direct calls to `main(argv)` raised `SystemExit(1)` for known and unexpected runtime failures. The unified dispatcher propagated that exception, and the package module guard called `main()` directly.

## 8. Production changes

`main` is annotated as `int | None`. `FileExistsError`, the known runtime-error group, and the unexpected-error fallback now return integer `1`. The `__main__` guard uses `raise SystemExit(main())`.

## 9. Existing test changes

The existing 10-test CLI module now checks returned integer status `1` for FileExistsError, unknown strategy, known runtime errors, and serialization read-back failures. Parser failures remain `SystemExit` assertions.

## 10. Characterization test changes

The C12.1 characterization module now asserts the corrected direct and unified contracts, removes the three temporary `expectedFailure` markers, and checks the new package guard text.

## 11. Direct success matrix

Direct success continues to return `None`, write a real JSON artifact, preserve alias metadata, preserve empty-result dates, and avoid stderr output.

## 12. Direct parser matrix

Help continues to raise `SystemExit(0)`. Missing required arguments and invalid typed arguments continue to raise `SystemExit(2)` with argparse wording.

## 13. Direct known-runtime matrix

Unknown strategy, FileExistsError, FileNotFoundError, IsADirectoryError, PermissionError, ValueError, BacktestError, and BacktestResultSerializationError return `1`, preserve the expected stderr text, write no traceback, and avoid success output.

## 14. Direct unexpected-runtime matrix

Unexpected exceptions return `1`, preserve the `error: Unexpected error:` prefix, write no traceback, and avoid success output.

## 15. Package module matrix

The package module exits with process codes `0`, `1`, and `2` for success, runtime failure, and parser failure respectively. Controlled subprocess tests verify no traceback and no unintended artifact on failure.

## 16. Unified function matrix

The unified `twstock_cli.main([...])` route returns `0` for child success and `1` for child runtime status, while child parser failure remains `SystemExit(2)`.

## 17. Unified module matrix

The unified module route preserves success, unknown-strategy failure, unexpected failure, help, and child-parser process behavior through the unchanged dispatcher route.

## 18. argv restoration

Unified-function tests confirm the original `sys.argv` is restored after child success, child runtime status, and child parser failure.

## 19. Error wording

Existing error wording is unchanged: FileExistsError retains `Use --overwrite`, known failures retain `error: <message>`, and unexpected failures retain `error: Unexpected error: <message>`.

## 20. Strategy resolution

The tested alias path continues to resolve `ma_cross` to `ma_cross_strategy` and records both requested and resolved strategy names in the artifact metadata.

## 21. Backtest and metadata behavior

The patch does not alter analysis, strategy execution, backtest calculation, or metadata construction. Existing controlled tests continue to verify initial capital, position size, parameters, and result fields.

## 22. Artifact and overwrite behavior

Successful exports and read-back remain unchanged. Existing artifacts still fail without `--overwrite`, and the overwrite wording and load suppression remain covered.

## 23. Package guard

The package guard is now exactly `if __name__ == "__main__":` followed by `raise SystemExit(main())`, giving process ownership to the module boundary.

## 24. Root wrapper

The repository remains package-only for this command. No root-level `backtest_result_export_cli.py` wrapper was added or modified.

## 25. Unified route

`twstock_cli` remains unchanged. The existing `backtest-result-export` dispatch continues to invoke `backtest_result_export_cli.main` and now receives its integer runtime status.

## 26. Console metadata

The existing `twstock` console-script target remains `tw_stock_tool.cli.twstock_cli:main`. No packaging metadata was changed.

## 27. Offline and dependency boundary

All validation uses existing mocks, temporary bootstrap modules, and subprocess helpers. No live-data dependency, package dependency, root wrapper, or build configuration was added.

## 28. Defect closure table

| Defect | Pre-fix behavior | Post-fix behavior | Result |
|---|---|---|---|
| `C12.1-DEFECT-01` | Direct known and unexpected runtime failures raised `SystemExit(1)`. | Direct known and unexpected runtime failures print the preserved stderr text and return integer `1`. | CLOSED |
| `C12.1-DEFECT-02` | Unified-function runtime failures propagated `SystemExit(1)`. | The unchanged unified dispatcher receives and returns integer `1`. | CLOSED |
| `C12.1-DEFECT-03` | The package guard called `main()` directly. | The package guard uses `raise SystemExit(main())`. | CLOSED |

## 29. Expected-failure conversion

The three C12.1 expected failures are now ordinary passing tests. The characterization module reports 30 tests, 30 ordinary passes, zero expected failures, zero unexpected successes, zero skips, and zero errors.

## 30. Targeted acceptance result

`py -m unittest tests.test_track_c12_1_backtest_result_export_cli_runtime_exit_behavior` completed with 30 tests and `OK`.

## 31. Existing CLI result

`py -m unittest tests.test_backtest_result_export_cli` completed with 10 tests and `OK`.

## 32. Combined regression result

The required C11/C12.1/CLI/root-wrapper combined command completed with 133 tests and `OK`.

## 33. Full discovery result

Both required full discovery commands completed with `OK`:

- `py -m unittest discover -s tests`: 1713 tests.
- `python -m unittest discover -s tests`: 1713 tests.

## 34. Exact validation counts

| Suite | Tests | Ordinary failures | Errors | Expected failures |
|---|---:|---:|---:|---:|
| C12.1 targeted | 30 | 0 | 0 | 0 |
| Existing CLI | 10 | 0 | 0 | 0 |
| Combined regression | 133 | 0 | 0 | 0 |
| Full `py` discovery | 1713 | 0 | 0 | 0 |
| Full `python` discovery | 1713 | 0 | 0 | 0 |

## 35. Diff validation

`git diff --check` completed without whitespace errors. The implementation diff contains only the intended return-status, guard, test-contract, and report changes.

## 36. BOM validation

The four changed or added text files were checked byte-for-byte for a UTF-8 BOM. No BOM is present.

## 37. Scope validation

The historical C12.1 report remains untouched. `twstock_cli`, backtesting, analysis, data, README, pyproject, requirements, GitHub workflow files, and root wrappers remain untouched.

## 38. Working-tree validation

No persistent bootstrap module, JSON output, bytecode, cache, temporary helper, or unrelated untracked file remains in the repository. The final working tree is clean after commit.

## 39. Commit and push

One intentional commit with message `Fix backtest result export CLI runtime exits` was created and pushed to `origin/track-c12-2-backtest-result-export-cli-runtime-exit-fix`. The final commit SHA is recorded in the implementation handoff.

## 40. Merge disposition

The branch is pushed and held for review. No merge was performed and no pull request was opened.

## 41. Exact validation commands

```text
py -m unittest tests.test_track_c12_1_backtest_result_export_cli_runtime_exit_behavior
py -m unittest tests.test_backtest_result_export_cli
py -m unittest tests.test_track_c12_1_backtest_result_export_cli_runtime_exit_behavior tests.test_backtest_result_export_cli tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_track_c11_1_backtest_artifact_cli_runtime_exit_behavior
py -m unittest discover -s tests
python -m unittest discover -s tests
git diff --check
git diff --stat
git diff --name-only
git status --short
git ls-files --others --exclude-standard
git add src/tw_stock_tool/cli/backtest_result_export_cli.py tests/test_backtest_result_export_cli.py tests/test_track_c12_1_backtest_result_export_cli_runtime_exit_behavior.py docs/TRACK_C12_2_BACKTEST_RESULT_EXPORT_CLI_RUNTIME_EXIT_FIX.md
git commit -m "Fix backtest result export CLI runtime exits"
git push -u origin track-c12-2-backtest-result-export-cli-runtime-exit-fix
```

Track C12.2 Implementation: PASS
Defects closed: C12.1-DEFECT-01, C12.1-DEFECT-02, C12.1-DEFECT-03
Branch disposition: HOLD FOR REVIEW
Merge was not performed.
C13 was not started.
