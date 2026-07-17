
# Track P3.2 - Shared Subprocess Test Helper

## 1. Executive outcome

P3.2 is complete as a test-only implementation. One shared subprocess helper now owns repeated repository-Python process setup used by six characterized CLI test modules. Invocation-specific behavior remains local to each test module.

Formal result: P3.2 Shared Subprocess Test Helper: PASS -- READY FOR REVIEW

The implementation-boundary reduction is 56 nonblank lines across the six target modules plus the helper. The complete test suite passed under both py and python. No production code, public API, CLI implementation, compatibility wrapper, provider behavior, cache behavior, safety boundary, or test coverage was removed.

## 2. Scope and authorization

This phase implements only the approved P3.2 test-helper reduction following P3.1 characterization. It does not implement a production cleanup, remove a test scenario, begin P3.3, run Ponytail, or alter repository architecture.

The exact permitted file scope was:

1. tests/subprocess_test_support.py
2. tests/test_track_c4_1_scanner_cli_exit_behavior.py
3. tests/test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior.py
4. tests/test_track_c6_1_benchmark_cli_runtime_exit_behavior.py
5. tests/test_track_c7_1_clean_stocks_cli_runtime_exit_behavior.py
6. tests/test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior.py
7. tests/test_track_c9_1_smoke_check_cli_runtime_exit_behavior.py
8. tests/test_track_p3_1_subprocess_test_helper_characterization.py
9. docs/TRACK_P3_2_SHARED_SUBPROCESS_TEST_HELPER.md

## 3. Repository baseline

- Repository: Mike87117/tw_stock_tool
- Required main commit: 43402917cdf05822dfcd5622d96c8bdd46eae5cc
- P3.1 branch: track-p3-1-subprocess-test-helper-characterization
- Exact approved P3.1 parent: ae5eb66903c4fb107428596325f90fae788e7dbf
- Current branch: track-p3-2-shared-subprocess-test-helper
- Current implementation commit before commit creation: ae5eb66903c4fb107428596325f90fae788e7dbf
- Branch was created directly from the exact P3.1 parent.
- No rebase, merge, squash, amend, force-push, or PR was performed.

The baseline was verified against origin/main before implementation. The working tree was clean before the P3.2 edits.

## 4. P3.1 decision

P3.1 established the characterization gate for the six local subprocess helpers and approved proceeding to P3.2. The five existing P3.1 characterization test methods remain present. The P3.1 report was not modified.

P3.2 preserves the P3.1 decisions rather than reopening them:

- C4 keeps inherited bytecode behavior by passing suppress_bytecode=False.
- C5 keeps inherited subprocess decoding behavior by passing errors=None.
- C8 keeps TemporaryDirectory and sitecustomize lifecycle ownership local.
- C9 keeps its distinct before/after helper-directory artifact checks local.

## 5. Corrections carried into P3.2

Two earlier characterization details were corrected in this implementation:

- The C7 unified route is stock-list clean. It is not scan.
- C8 does not compare helper-directory contents before and after. C8 owns TemporaryDirectory, returns the helper path after cleanup, and existing tests verify that the returned path no longer exists.
- C9 retains separate helper_path.iterdir() checks before and after execution. Those checks were not moved or removed.

## 6. Working-tree protection

The user-owned ignored file custom_md.md was not inspected, modified, deleted, staged, or cleaned. git clean was not run.

No generated report, cache, virtual-environment file, market data, network response, or persistent test artifact was created as part of this phase.

## 7. Shared helper implementation

tests/subprocess_test_support.py contains exactly one public helper:

    run_repo_python(*args, extra_pythonpath=(), include_repository_root=True,
                    suppress_bytecode=True, errors="replace")

The helper:

- copies os.environ;
- builds PYTHONPATH from optional extra paths, the repository root when enabled, the repository src directory, and inherited PYTHONPATH;
- uses os.pathsep for platform-safe path joining;
- sets PYTHONDONTWRITEBYTECODE only when suppress_bytecode is true;
- runs the current interpreter with the supplied arguments;
- uses the repository root as cwd;
- captures stdout and stderr as text;
- sets check=False;
- forwards errors only when a caller requests a non-None value.

There is one subprocess.run call in the helper and no provider-specific import or cleanup logic.

## 8. Helper parameter characterization

| Parameter | Default | Used by | Preserved behavior |
| --- | --- | --- | --- |
| extra_pythonpath | empty tuple | C8 and C9 | Adds the caller-owned offline helper directory to PYTHONPATH |
| include_repository_root | true | C4 overrides false | C4 keeps its prior source-only path behavior |
| suppress_bytecode | true | C4 overrides false | Other callers suppress bytecode as before; C4 leaves inherited state untouched |
| errors | replace | C5 overrides None | Other callers retain replacement decoding; C5 retains inherited decoding behavior |

All six target call sites use shared setup while retaining only local differences characterized in P3.1.

## 9. C4 scanner CLI boundary

C4 delegates its process launch to run_repo_python with include_repository_root=False, suppress_bytecode=False, and the shared default errors=replace.

The test still exercises package-module, root-wrapper, unified-function, unified-module, console-script mapping, argparse, and sibling-propagation behavior. The helper does not absorb scanner-specific assertions or command construction.

## 10. C5 cache-manager CLI boundary

C5 delegates to run_repo_python with errors=None. Its local _run_python wrapper still performs textwrap.dedent before invocation.

The tests still cover list, clear, summary, package module, root wrapper, unified command, invalid-argument exit status, import alias compatibility, and failure propagation. Cache-manager command and output assertions are unchanged.

## 11. C6 benchmark CLI boundary

C6 delegates its generic process launch to run_repo_python with default behavior. Benchmark-specific command arguments, mocked execution, package entry point, root wrapper, unified routing, argparse status, and sibling propagation remain in the test module.

No benchmark implementation or performance behavior was changed.

## 12. C7 clean-stocks CLI boundary

C7 delegates its generic process launch to run_repo_python with default behavior. The unified command characterized by this module is stock-list clean.

Package module, root wrapper, unified function, unified module, invalid-argument behavior, root import alias, and nonzero-status propagation tests remain intact. No stock-cleaning behavior or dispatcher route was changed.

## 13. C8 stock-list updater boundary

C8 delegates process launching to run_repo_python and passes its TemporaryDirectory path through extra_pythonpath.

C8 still owns the exact offline sitecustomize source, TemporaryDirectory lifetime, UTF-8 file writing, returned helper path, assertion that the temporary path is gone after the process returns, updater-specific command, and output assertions.

No generic helper-directory before/after comparison was added. This is intentional because C8's characterized contract is cleanup after TemporaryDirectory exit, while C9 has a separate artifact contract.

## 14. C9 smoke-check boundary

C9 delegates process launching to run_repo_python and passes helper_path through extra_pythonpath when present.

C9 still owns stock and price modes, distinct sitecustomize sources, TemporaryDirectory creation and UTF-8 writing, helper_path.iterdir() checks before and after execution, artifact absence assertions, output, traceback, argparse, import-alias, and status propagation assertions.

The helper does not absorb smoke-check mode or artifact semantics.

## 15. Invocation-boundary matrix

| Characterized module | Package boundary | Root boundary | Unified boundary |
| --- | --- | --- | --- |
| C4 | tw_stock_tool.cli.scan_stocks | scan_stocks.py | scan |
| C5 | tw_stock_tool.data.cache_manager | cache_manager.py | cache |
| C6 | tw_stock_tool.cli.benchmark | benchmark.py | benchmark |
| C7 | tw_stock_tool.cli.clean_stocks | clean_stocks.py | stock-list clean |
| C8 | tw_stock_tool.data.stock_list_updater | stock_list_updater.py | stock-list |
| C9 | tw_stock_tool.cli.smoke_check and price_check | smoke_check.py and price_check.py | stock and price |

The helper is below these boundaries. It does not consolidate package modules, root compatibility wrappers, or unified CLI registration.

## 16. Exit-status preservation

The helper keeps check=False, so completed-process status remains observable to each existing test. The six modules continue to assert distinctions among direct legacy None returns, handled runtime or validation failures returning one, argparse-owned invalid arguments exiting two, package and root module process status, and unified function and module propagation.

The implementation does not convert subprocess status into a new exception or alter process-status wording.

## 17. Output and assertion preservation

Existing command arguments, stdout and stderr capture, text mode, decoding choices, and assertions remain at their original invocation boundaries. The implementation changes only repeated environment and subprocess construction.

The P3.1 characterization assertions still pin the C4-C9 subprocess snapshots. The existing six test modules retain their invocation-boundary coverage and output assertions.

## 18. Offline artifact preservation

No live market service was used. Offline sitecustomize test setup remains in C8 and C9. The shared helper only transports the extra PYTHONPATH entry and does not generate, inspect, or remove the offline modules.

This preserves provider and dependency isolation boundaries.

## 19. Characterization-test adaptation

The existing tests/test_track_p3_1_subprocess_test_helper_characterization.py was adapted in place; it was not replaced or expanded with a new test method.

The five existing methods remain:

- test_each_local_process_helper_preserves_its_exact_invocation_snapshot
- test_c5_inline_source_is_dedented_and_delegated_unchanged
- test_c8_offline_sitecustomize_and_cleanup_are_local_and_exact
- test_c9_stock_and_price_offline_sources_remain_distinct
- test_offline_sources_encode_their_intended_dependency_boundaries

The test now patches the shared helper's environment and subprocess.run for invocation snapshots, and adds structural assertions for one shared subprocess call, six delegating imports, no direct target-module subprocess.run calls, no provider imports, C8 cleanup ownership, and C9 before/after directory checks.

## 20. Coverage preservation

No test method was deleted. No invocation boundary was merged away. No smoke, wrapper, status, schema, fallback, cleanup, or historical regression coverage was removed.

The six target modules and the P3.1 characterization module all continued to pass. The full discovered test count remained 1,622.

## 21. Mechanical LOC method

Counts use tracked or explicitly approved working-tree files and count nonblank physical lines with:

    Path(path).read_text(encoding="utf-8").splitlines()
    sum(bool(line.strip()) for line in lines)

The before snapshot was read from the exact P3.1 parent ae5eb66903c4fb107428596325f90fae788e7dbf. The helper was counted as zero before and 33 nonblank lines after. No permanent counting script was added.

## 22. Target-module LOC inventory

| File | Before | After | Net |
| --- | ---: | ---: | ---: |
| tests/test_track_c4_1_scanner_cli_exit_behavior.py | 229 | 221 | -8 |
| tests/test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior.py | 245 | 233 | -12 |
| tests/test_track_c6_1_benchmark_cli_runtime_exit_behavior.py | 246 | 233 | -13 |
| tests/test_track_c7_1_clean_stocks_cli_runtime_exit_behavior.py | 304 | 291 | -13 |
| tests/test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior.py | 410 | 382 | -28 |
| tests/test_track_c9_1_smoke_check_cli_runtime_exit_behavior.py | 446 | 431 | -15 |
| Six target modules | 1880 | 1791 | -89 |
| tests/subprocess_test_support.py | 0 | 33 | +33 |
| Implementation boundary total | 1880 | 1824 | -56 |

## 23. Gross diff accounting

The six target modules remove 108 nonblank diff lines and add 19 nonblank diff lines. The new helper adds 33 nonblank lines.

Therefore:

- gross removed from target modules: 108;
- gross added in target modules plus helper: 52;
- implementation-boundary net reduction: 56.

The net figure is the only reduction estimate used for this phase.

## 24. Characterization-test LOC impact

The adapted P3.1 characterization module changed from 260 to 318 nonblank lines, a delta of +58. This is test characterization overhead, not a reduction estimate.

Including the six target modules, the helper, and the adapted characterization module, test code changed from 2140 to 2142 nonblank lines, a total delta of +2. This confirms that the reduction is a local deduplication offset by explicit characterization, not coverage removal.

## 25. P3.1 estimate versus actual result

The P3.1 characterization report predicted a 54-line implementation-boundary net reduction based on a provisional helper size. The actual implementation has a 56-line nonblank reduction after measuring the concrete helper and all six call sites.

The actual result passes the required gate:

- net reduction >= 25 lines: PASS;
- one helper: PASS;
- no production code: PASS;
- no coverage removal: PASS;
- no dependency change: PASS;
- six target modules delegate: PASS;
- helper contains one subprocess.run call: PASS.

## 26. Dependencies and architecture

Dependency impact: none.

No package metadata, lock file, dependency declaration, public import, root wrapper, production module, CLI registration, provider boundary, cache boundary, risk boundary, or architecture decision was changed.

The helper is a small test-only local utility. It does not introduce a framework or generalized subprocess abstraction outside the six characterized modules.

## 27. Targeted test result

Command:

    py -m unittest tests.test_track_p3_1_subprocess_test_helper_characterization

Result:

    Ran 5 tests
    OK

## 28. Combined characterization result

Command:

    py -m unittest tests.test_track_p3_1_subprocess_test_helper_characterization tests.test_track_c4_1_scanner_cli_exit_behavior tests.test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior tests.test_track_c6_1_benchmark_cli_runtime_exit_behavior tests.test_track_c7_1_clean_stocks_cli_runtime_exit_behavior tests.test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior tests.test_track_c9_1_smoke_check_cli_runtime_exit_behavior

Result:

    Ran 120 tests
    OK

## 29. Full test result with py

Command:

    py -m unittest discover -s tests

Result:

    Ran 1622 tests
    OK

## 30. Full test result with python

Command:

    python -m unittest discover -s tests

Result:

    Ran 1622 tests
    OK

Mocked and offline tests emitted their existing diagnostic output and warnings, but no test failed and no live market request was made.

## 31. Required validation

The remaining final checks are:

- git diff --check;
- git status --short;
- report encoding check for a UTF-8 BOM;
- changed-file scope check;
- production, test, and dependency change check;
- commit and push verification.

These checks are recorded in the final task handoff after the report is added.

## 32. Exact files changed

The completed change is limited to:

- tests/subprocess_test_support.py
- tests/test_track_c4_1_scanner_cli_exit_behavior.py
- tests/test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior.py
- tests/test_track_c6_1_benchmark_cli_runtime_exit_behavior.py
- tests/test_track_c7_1_clean_stocks_cli_runtime_exit_behavior.py
- tests/test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior.py
- tests/test_track_c9_1_smoke_check_cli_runtime_exit_behavior.py
- tests/test_track_p3_1_subprocess_test_helper_characterization.py
- docs/TRACK_P3_2_SHARED_SUBPROCESS_TEST_HELPER.md

## 33. No-production-change confirmation

No file under src/tw_stock_tool was modified. No root-level production entry point was modified. No test invocation boundary was removed. No dependency or configuration file was modified.

This phase is test infrastructure only.

## 34. Branch disposition

The branch remains separate from main and from the P3.1 branch. It is not merged. No later phase is started.

Exactly one next-phase recommendation:

Hold this branch for review and integration; do not begin another production or cleanup phase until this P3.2 implementation is accepted.

Deferred future work, if separately authorized, includes any production cleanup, test-helper expansion beyond the six characterized modules, and documentation restructuring. None is started here.

## 35. Final status

P3.2 Shared Subprocess Test Helper: PASS -- READY FOR REVIEW

No production code was changed.
No coverage was removed.
No dependency was added or removed.
No live market service was contacted.
