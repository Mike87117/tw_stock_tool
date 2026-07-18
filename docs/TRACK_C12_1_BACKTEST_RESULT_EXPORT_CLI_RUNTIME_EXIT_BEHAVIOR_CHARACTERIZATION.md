# Track C12.1 — Backtest Result Export CLI Runtime Exit Behavior Characterization

1. Executive outcome

C12.1 characterization is complete on the branch created directly from the approved merged C11 baseline. The current callable, package, and unified runtime exit behavior is frozen without changing production code.

2. Formal characterization result

PASS — current behavior is characterized. Exactly three future-contract assertions are expected failures; all ordinary characterization and regression tests pass. C12.1-DEFECT-01, C12.1-DEFECT-02, and C12.1-DEFECT-03 are confirmed.

3. Repository baseline

HEAD, local main, and origin/main were verified at `af53c68dfb0c141ecae6159866a559206a34cb93`, with commit message `Merge Track C11 backtest artifact CLI runtime exit fixes`.

4. Branch and parent relationship

Branch: `track-c12-1-backtest-result-export-cli-runtime-exit-characterization`.

The branch was created directly from the verified main baseline. It was not stacked on an older C11 branch.

5. Working-tree and ignored-file protection

The starting working tree was clean. `custom_md.md` was not inspected, modified, staged, deleted, restored, or cleaned. No `git clean` operation was used.

6. Optional LLM Wiki availability result

No local LLM Wiki health or search endpoint was available through the configured environment. This optional check was non-blocking and was not used for characterization.

7. Production implementation inventory

The target CLI parses historical backtest arguments, resolves aliases through `STRATEGIES`, calls `analyze_stock`, executes the selected strategy, calls `run_backtest_result`, populates BacktestResult metadata, exports and reloads the JSON artifact, prints success text, and catches known and unexpected runtime exceptions with `sys.exit(1)`. Its package guard currently calls `main()` directly.

8. Existing test inventory

`tests/test_backtest_result_export_cli.py` contains 10 existing tests covering safety wording, parser defaults and errors, successful mocked export, overwrite forwarding, selected runtime failures, and artifact round-trip validation.

9. Test-gap inventory

The new characterization adds complete direct callable coverage, deterministic package and unified subprocess coverage, unified-function argv restoration and forwarding checks, the package-guard structural assertion, route and metadata checks, all required known exception groups, the unexpected fallback, and exactly three future-contract expected failures.

10. Data and network-risk inventory

Direct tests patch analysis, strategy, backtest, export, and load boundaries as needed. Process tests use temporary `sitecustomize.py` bootstraps that patch imported analysis, strategy, and backtest modules before the CLI loads. No live request, cache refresh, download, broker, order, or signal path is used.

11. Fixture and mock design

Fixtures use fixed `DatetimeIndex` values, deterministic Open/Close/Signal DataFrames, a deterministic strategy double, and real BacktestResult objects. Successful direct and subprocess tests use the real JSON writer and loader where practical. Every output is inside a cleaned TemporaryDirectory.

12. Subprocess bootstrap design

The existing `tests/subprocess_test_support.py` `run_repo_python` helper is reused. Temporary bootstraps patch `analyze_stock`, `run_backtest_result`, and `STRATEGIES`, then run the real package or unified module. The bootstrap is never added to the repository.

13. Complete characterization matrix

| ID | Boundary | Scenario | Current result | Future contract | Classification |
|---|---|---|---|---|---|
| D-01 | Direct | Successful export and read-back | `None`, artifact and success text | `None` | CORRECTLY_HANDLED |
| D-02 | Direct | `ma_cross` alias resolution | Metadata records requested and resolved names | Preserve metadata | CORRECTLY_HANDLED |
| D-03 | Direct | Empty execution DataFrame | Dates are `N/A` | Preserve dates | CORRECTLY_HANDLED |
| D-04 | Direct | Help | `SystemExit(0)` | `SystemExit(0)` | CORRECTLY_HANDLED |
| D-05 | Direct | Missing or invalid typed arguments | `SystemExit(2)` | `SystemExit(2)` | CORRECTLY_HANDLED |
| D-06 | Direct | Unknown strategy | `SystemExit(1)` before analysis | Return integer `1` | DEFECT_CONFIRMED |
| D-07 | Direct | FileExistsError | `SystemExit(1)` with overwrite wording | Print same stderr and return `1` | DEFECT_CONFIRMED |
| D-08 | Direct | FileNotFoundError, IsADirectoryError, PermissionError, ValueError, BacktestError, serialization error | `SystemExit(1)` with clean stderr | Return integer `1` | DEFECT_CONFIRMED |
| D-09 | Direct | Unexpected ordinary Exception | `SystemExit(1)` with `Unexpected error` wording | Return integer `1` | DEFECT_CONFIRMED |
| P-01 | Package | Help | Process status `0` | `0` | CORRECTLY_HANDLED |
| P-02 | Package | Missing arguments | Process status `2` | `2` | CORRECTLY_HANDLED |
| P-03 | Package | Unknown strategy | Process status `1`, no live analysis | `1` | CORRECTLY_HANDLED |
| P-04 | Package | Controlled success | Process status `0`, real artifact | `0` | CORRECTLY_HANDLED |
| P-05 | Package | Controlled unexpected failure | Process status `1`, no traceback | `1` | CORRECTLY_HANDLED |
| U-01 | Unified function | Successful child | Integer `0`, argv restored and order preserved | `0` | CORRECTLY_HANDLED |
| U-02 | Unified function | Known runtime failure | Propagated `SystemExit(1)` | Integer `1` | DEFECT_CONFIRMED |
| U-03 | Unified function | Unexpected runtime failure | Propagated `SystemExit(1)` | Integer `1` | DEFECT_CONFIRMED |
| U-04 | Unified function | Child parser failure | `SystemExit(2)` | `SystemExit(2)` | CORRECTLY_HANDLED |
| M-01 | Unified module | Help | Process status `0` | `0` | CORRECTLY_HANDLED |
| M-02 | Unified module | Missing child arguments | Process status `2` | `2` | CORRECTLY_HANDLED |
| M-03 | Unified module | Unknown strategy | Process status `1` | `1` | CORRECTLY_HANDLED |
| M-04 | Unified module | Controlled success | Process status `0`, real artifact | `0` | CORRECTLY_HANDLED |
| M-05 | Unified module | Controlled unexpected failure | Process status `1`, no traceback | `1` | CORRECTLY_HANDLED |
| G-01 | Package guard | Structural guard | Calls `main()` directly | `raise SystemExit(main())` | DEFECT_CONFIRMED |
| R-01 | Root wrapper | `backtest_result_export_cli.py` | Absent | No wrapper required | NOT_APPLICABLE |

14. Direct success results

Successful direct export returns implicit `None`, creates a valid JSON artifact, reloads it through the real loader, records stock, strategy, dates, parameters, requested strategy, resolved strategy, and prints the success message with no stderr or traceback.

15. Direct parser results

Help remains `SystemExit(0)`. Missing required arguments and invalid typed arguments remain `SystemExit(2)`. These argparse-owned exits contain no traceback.

16. Direct known-runtime-failure results

Unknown strategy, FileExistsError, FileNotFoundError, IsADirectoryError, PermissionError, ValueError, BacktestError, and BacktestResultSerializationError all currently produce `SystemExit(1)`, clean stderr, no false success message, and no traceback. FileExistsError preserves `Use --overwrite` wording and does not call read-back.

17. Direct unexpected-failure results

An ordinary RuntimeError currently produces `SystemExit(1)`, with `error: Unexpected error:` wording, no success message, and no traceback.

18. Package-module results

The real `python -m tw_stock_tool.cli.backtest_result_export_cli` boundary exits `0` for help and controlled success, `2` for parser failure, `1` for unknown strategy, and `1` for controlled unexpected failure. Successful execution writes an artifact readable by the real loader.

19. Unified-function results

`tw_stock_tool.cli.twstock_cli.main` returns integer `0` for successful child execution. Current known and unexpected child runtime failures propagate `SystemExit(1)`. Child parser failure remains `SystemExit(2)`.

20. Unified-module results

The real unified module exits `0` for help and controlled success, `2` for missing child arguments, and `1` for unknown strategy and controlled unexpected failure. No traceback is emitted.

21. sys.argv restoration result

The unified function restores `sys.argv` exactly after success, known failure, unexpected failure, and child parser failure. Child arguments are forwarded in original order with program name `backtest_result_export_cli.py`.

22. Package-guard result

The current source contains `if __name__ == "__main__":` followed by `main()`, not `raise SystemExit(main())`. This is the third confirmed future-contract defect.

23. Root-wrapper result

Repository-root `backtest_result_export_cli.py` is absent. This is classified `NOT_APPLICABLE`, not a defect, and no wrapper was added.

24. Unified-route result

The unified route is `backtest-result-export` and dispatches to `tw_stock_tool.cli.backtest_result_export_cli.main`.

25. Console metadata result

`pyproject.toml` preserves `twstock = "tw_stock_tool.cli.twstock_cli:main"`. No installed console script was executed.

26. Error wording and traceback result

Known failures preserve `error: <exception>` wording; FileExistsError preserves the overwrite suffix; unexpected failures preserve `error: Unexpected error: <exception>`. All characterized failures are traceback-free.

27. Filesystem-artifact result

Successful artifacts are created and read back from temporary paths. Failure cases do not emit false success messages. Temporary output, bootstrap, and helper directories are cleaned by the tests.

28. Offline/no-live-request result

PASS — all success paths use deterministic doubles or temporary subprocess bootstraps. No yfinance, TWSE, TPEx, HTTP, cache refresh, stock download, broker, order, or live-signal request was performed.

29. Existing coverage preservation

No existing test file was modified. The existing 10-test Backtest Result Export CLI suite remains green, and the C11 characterization suite remains included in the combined and full runs.

30. Expected-failure inventory

Exactly three expected failures represent only the future contract: direct runtime failure returns integer `1`; unified-function runtime failure returns integer `1`; and the package guard uses `raise SystemExit(main())`. No process, parser, success, wording, artifact, or offline test is an expected failure.

31. Confirmed defect inventory

- `C12.1-DEFECT-01`: direct known and unexpected runtime failures raise `SystemExit(1)` instead of returning integer `1`.
- `C12.1-DEFECT-02`: unified-function known and unexpected runtime failures propagate `SystemExit(1)` instead of returning integer `1`.
- `C12.1-DEFECT-03`: the package executable guard calls `main()` directly instead of `raise SystemExit(main())`.

32. Candidate C12.2 scope

Candidate scope only: change the return annotation to `int | None`; preserve implicit `None` success; replace runtime `sys.exit(1)` with identical stderr and `return 1`; preserve exception groups and unexpected wording; change the package guard to `raise SystemExit(main())`; and preserve argparse statuses `0` and `2` plus unchanged unified dispatch.

33. Explicit production-fix restriction

C12.2 is documented only. No argument names, defaults, strategy resolution, strategy or backtest parameters, analysis, strategy execution, backtest execution, serialization, metadata, output paths, overwrite semantics, safety wording, unified routing, console metadata, dependencies, or wrappers were changed.

34. Exact files changed

Only these two new files were added:

- `tests/test_track_c12_1_backtest_result_export_cli_runtime_exit_behavior.py`
- `docs/TRACK_C12_1_BACKTEST_RESULT_EXPORT_CLI_RUNTIME_EXIT_BEHAVIOR_CHARACTERIZATION.md`

No production file or existing test was changed.

35. Targeted test results

`py -m unittest tests.test_track_c12_1_backtest_result_export_cli_runtime_exit_behavior` ran 30 tests: 27 ordinary passes and 3 expected failures.

`py -m unittest tests.test_backtest_result_export_cli` ran 10 tests: 10 ordinary passes.

36. Combined test results

The required combined suite ran 133 tests: 130 ordinary passes and 3 expected failures, with zero errors, skips, or unexpected successes.

37. Full-suite results

Both complete suites passed with exactly three expected failures and zero ordinary failures, errors, skips, or unexpected successes.

38. Exact test counts

`py -m unittest discover -s tests`: 1,713 tests in 112.892s, OK, expected failures=3.

`python -m unittest discover -s tests`: 1,713 tests in 121.791s, OK, expected failures=3.

39. git diff --check result

The final `git diff --check` completed without whitespace errors.

40. UTF-8 BOM result

Both new files were checked bytewise and are UTF-8 without BOM.

41. Changed-file scope result

PASS -- the C12.1 characterization commit contains exactly these two approved files:

- `tests/test_track_c12_1_backtest_result_export_cli_runtime_exit_behavior.py`
- `docs/TRACK_C12_1_BACKTEST_RESULT_EXPORT_CLI_RUNTIME_EXIT_BEHAVIOR_CHARACTERIZATION.md`

No production, existing-test, configuration, root-wrapper, cache, bootstrap, JSON artifact, or temporary helper file was included.

42. Working-tree result

PASS -- after the C12.1 characterization commit and push, the working tree was clean.

No persistent JSON artifact, bytecode file, cache directory, subprocess bootstrap, or temporary helper directory remained in the repository.

43. Commit and push result

The C12.1 characterization commit was created successfully:

`b79ae05862e4232e2b366822384191a9125301c1` -- `Characterize backtest result export CLI exits`

The commit was pushed successfully to:

`origin/track-c12-1-backtest-result-export-cli-runtime-exit-characterization`

The local and remote C12.1 branches were aligned after the push.

44. Branch disposition

`HOLD FOR REVIEW`. No merge, pull request, production fix, C12.2 work, or later track was started.

45. Exact commands used

```text
git fetch origin
git checkout main
git checkout -b track-c12-1-backtest-result-export-cli-runtime-exit-characterization
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
```

Track C12.1 Characterization: PASS -- DECISION RECORDED
Branch disposition: HOLD FOR REVIEW
C12.2 was not started.
