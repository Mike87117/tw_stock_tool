# Track P3.1 — Subprocess Test-Environment Helper Characterization

## 1. Executive outcome

The six PT-AUDIT-003 characterization modules contain a common subprocess runner shape with bounded, observable variants. A single test-only helper can preserve the exact executable, working directory, `PYTHONPATH` ordering, inherited environment placement, output capture, decoding behavior, bytecode suppression, and `check=False` behavior.

C8 and C9 must retain their local `sitecustomize.py` source, temporary-directory ownership, cleanup assertions, and artifact checks. C9 must retain separate `stock` and `price` offline modes. Those boundaries do not require helper modes.

The complexity gate passes. The characterization outcome is:

```text
PROCEED_TO_P3_2
```

No shared helper was created in this phase.

## 2. Formal result

```text
Track P3.1 Characterization: PASS -- DECISION RECORDED
```

Final outcome: `PROCEED_TO_P3_2`

## 3. Repository baseline

- Parent commit: `43402917cdf05822dfcd5622d96c8bdd46eae5cc`
- Required `main`: `43402917cdf05822dfcd5622d96c8bdd46eae5cc`
- Required `origin/main`: `43402917cdf05822dfcd5622d96c8bdd46eae5cc`
- Branch: `track-p3-1-subprocess-test-helper-characterization`
- Branch was created directly from the verified `main` commit.

The baseline gate used `git fetch origin`, `git checkout main`, `git pull --ff-only origin main`, both SHA checks, and `git status --short`. Both SHAs matched and the starting working tree was clean.

## 4. Working-tree protection

Only the two approved new files were changed. No existing test module, production file, wrapper, configuration file, dependency file, or documentation file was modified.

`custom_md.md` was not inspected, modified, staged, restored, deleted, or cleaned. `git clean` was not run.

## 5. Ponytail finding

This phase characterizes `PT-AUDIT-003`, concerning duplicated subprocess invocation and offline test-environment preparation in:

```text
tests/test_track_c4_1_scanner_cli_exit_behavior.py
tests/test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior.py
tests/test_track_c6_1_benchmark_cli_runtime_exit_behavior.py
tests/test_track_c7_1_clean_stocks_cli_runtime_exit_behavior.py
tests/test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior.py
tests/test_track_c9_1_smoke_check_cli_runtime_exit_behavior.py
```

Ponytail was not run again. PT-AUDIT-003 was characterized from repository source and tests only.

## 6. Modules inspected

Primary scope:

- `tests/test_track_c4_1_scanner_cli_exit_behavior.py`
- `tests/test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior.py`
- `tests/test_track_c6_1_benchmark_cli_runtime_exit_behavior.py`
- `tests/test_track_c7_1_clean_stocks_cli_runtime_exit_behavior.py`
- `tests/test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior.py`
- `tests/test_track_c9_1_smoke_check_cli_runtime_exit_behavior.py`

Adjacent evidence only:

- `tests/test_track_p1_1_report_cli_argument_registration_characterization.py`
- `tests/test_track_p2_1_unified_cli_passthrough_registration_characterization.py`

The adjacent P1.1 and P2.1 subprocess code was not added to the implementation candidate.

## 7. Existing helper inventory

| Module | Existing subprocess/environment helper or pattern | Direct `subprocess.run()` |
| --- | --- | --- |
| C4 scanner | `_run_process()` | Yes, once |
| C5 cache manager | `_run_process()`; `_run_python()` delegates dedented source with `-c` | Yes, once |
| C6 benchmark | `_run_process()` | Yes, once |
| C7 clean stocks | `_run_process()` | Yes, once |
| C8 stock-list updater | `_run_process()`; `_run_offline_process()` duplicates environment and invocation setup | Yes, twice |
| C9 smoke checks | `_run_process()`; `_run_offline_process()` owns temporary source and delegates to `_run_process()` | Yes, once |

There are seven direct `subprocess.run()` expressions across the six modules. There are six local `_run_process()` methods, one C5 inline-source wrapper, one C8 duplicated offline invocation pattern, and one C9 offline lifecycle wrapper.

## 8. Complete behavior matrix

The matrix preserves differences rather than normalizing them away.

| Module | Local helper | Command prefix | Working directory | Base `PYTHONPATH` order | Extra helper path | Inherited `PYTHONPATH` | Bytecode suppression | Capture output | Text mode | Error decoding | Check behavior | Inline source | Sitecustomize | Cleanup ownership | Artifact check | Return shape |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C4 scanner | `_run_process` | `[sys.executable, *command]` | `REPOSITORY_ROOT` | `src` | Not supported | Appended after `src` | Absent | `True` | `True` | `errors="replace"` | `check=False` | No | No | None in runner; test fixture owns temp dir | Fixture checks empty temp directory where applicable | `CompletedProcess[str]` |
| C5 cache manager | `_run_process` | `[sys.executable, *args]` | `REPOSITORY_ROOT` | repository root, then `src` | Not supported | Appended after `src` | `"1"` | `True` | `True` | Absent | `check=False` | `_run_python` supports dedented `-c` source | No | None in runner; test fixture owns temp dir | Fixture compares directory before/after | `CompletedProcess[str]` |
| C5 cache manager | `_run_python` | Delegates as `("-c", textwrap.dedent(source))` | Delegated to `_run_process` | Delegated to `_run_process` | Not supported | Delegated | Delegated | Delegated | Delegated | Delegated | Delegated | Yes | No | Delegated | Delegated | `CompletedProcess[str]` |
| C6 benchmark | `_run_process` | `[sys.executable, *args]` | `REPOSITORY_ROOT` | repository root, then `src` | Not supported | Appended after `src` | `"1"` | `True` | `True` | `errors="replace"` | `check=False` | No | No | None in runner; test fixture owns temp dir | Success tests compare temp directory before/after | `CompletedProcess[str]` |
| C7 clean stocks | `_run_process` | `[sys.executable, *args]` | `REPOSITORY_ROOT` | repository root, then `src` | Not supported | Appended after `src` | `"1"` | `True` | `True` | `errors="replace"` | `check=False` | No | No | None in runner; test fixture owns temp dir | Success and failure tests compare temp directory before/after | `CompletedProcess[str]` |
| C8 stock-list updater | `_run_process` | `[sys.executable, *args]` | `REPOSITORY_ROOT` | repository root, then `src` | Not supported by this method | Appended after `src` | `"1"` | `True` | `True` | `errors="replace"` | `check=False` | No | No | None in runner; `_run_offline_process` owns its temporary context | Existing tests assert helper-directory contents unchanged | `CompletedProcess[str]` |
| C8 stock-list updater | `_run_offline_process` | `[sys.executable, *args]` | `REPOSITORY_ROOT` | temporary helper path, repository root, then `src` | Supported locally by inline setup | Appended after `src` | `"1"` | `True` | `True` | `errors="replace"` | `check=False` | No | Writes local stock-list patch | Owns `TemporaryDirectory()` and returns its path after cleanup | Checks directory contents before/after child execution | `(CompletedProcess[str], Path)`; returned path is cleaned up |
| C9 smoke checks | `_run_process` | `[sys.executable, *args]` | `REPOSITORY_ROOT` | repository root, then `src` | Supported through `helper_path` | Appended after `src` | `"1"` | `True` | `True` | `errors="replace"` | `check=False` | No | No | None in runner; offline wrapper owns context | Offline wrapper checks directory contents before/after | `CompletedProcess[str]` |
| C9 smoke checks | `_run_offline_process` | Delegates `[sys.executable, *args]` | `REPOSITORY_ROOT` | helper path is passed to `_run_process`, then repository root, `src`, inherited path | Supported through `helper_path` | Appended after `src` | `"1"` | `True` | `True` | `errors="replace"` | `check=False` | No | Local source selected by `mode` | Owns `TemporaryDirectory()` and cleanup assertion | Compares helper-directory names before/after | `CompletedProcess[str]` |

Repository root inclusion is absent only in C4. `src` is included by all six modules. A temporary helper directory is used only by C8 and C9 offline wrappers. Inherited `PYTHONPATH` is appended in every subprocess runner.

## 9. Command-prefix differences

All direct runners use `sys.executable` as the executable prefix. The command-specific suffix remains visible at each call site:

- C4 invokes package module, root wrapper, and unified module forms for scanner failures.
- C5 invokes package, root, and unified cache-manager forms; `_run_python` adds `-c` after the executable.
- C6 invokes package, root, and unified benchmark forms.
- C7 invokes package, root, and unified clean-stocks forms.
- C8 invokes package, root, and unified stock-list updater forms.
- C9 separately invokes package, root, and unified stock-list smoke-check forms and price smoke-check forms.

The proposed helper receives `*args` and does not contain command-name conditionals or a route table.

## 10. Working-directory results

Every subprocess runner uses the exact same `cwd=REPOSITORY_ROOT`. The proposed helper can preserve this as one fixed boundary. No module-specific working-directory behavior was found.

## 11. `PYTHONPATH` results

The exact variants are:

1. C4: `src`, then inherited `PYTHONPATH`; repository root is not included.
2. C5, C6, C7, C8 direct, C9 direct: repository root, `src`, then inherited `PYTHONPATH`.
3. C8 offline: temporary helper path, repository root, `src`, then inherited `PYTHONPATH`.
4. C9 offline: temporary helper path is passed through the local runner and is placed before repository root, `src`, and inherited `PYTHONPATH`.

The ordering is behaviorally important because `sitecustomize.py` must be discovered before package imports and inherited paths must remain last.

## 12. Bytecode-suppression results

C4 does not set `PYTHONDONTWRITEBYTECODE`. C5, C6, C7, C8, and C9 set it to the exact string value `"1"`, including their offline paths.

This is one boolean helper parameter, `suppress_bytecode`, with `False` required only for C4.

## 13. Output-capture results

Every subprocess call captures output with `capture_output=True`, uses `text=True`, and supplies `check=False`. These options must remain exact because the tests inspect stdout/stderr and assert exit-status propagation rather than allowing `subprocess.run()` to raise.

## 14. Decoding differences

C4, C6, C7, C8, and C9 supply `errors="replace"`. C5 intentionally omits `errors`. The helper therefore needs an optional decoding parameter whose `None` value means omit the keyword, not pass `errors=None`.

## 15. Inline-source behavior

C5 `_run_python(source)` performs exactly two operations: it applies `textwrap.dedent(source)` and delegates to `_run_process("-c", dedented_source)`. The characterization test freezes both the dedenting result and the delegation arguments. The proposed shared helper does not need to own inline source; C5 can retain this two-line behavior locally.

## 16. C8 offline helper lifecycle

C8 `_run_offline_process()`:

1. Enters `tempfile.TemporaryDirectory()`.
2. Converts the directory name to `Path`.
3. Writes `sitecustomize.py` using `encoding="utf-8"`.
4. Builds `PYTHONPATH` with the helper path first, followed by repository root, `src`, and inherited `PYTHONPATH`.
5. Sets `PYTHONDONTWRITEBYTECODE="1"`.
6. Executes the child with the same captured-output, text, decoding, and `check=False` options.
7. Lets the temporary-directory context own cleanup.
8. Returns `(completed, helper_path)` after the context exits; the returned path no longer exists.

The characterization test patches `subprocess.run` and `Path.write_text`, freezes the exact source and encoding, verifies temporary-directory construction, verifies helper-path ordering, and verifies cleanup without launching a child.

## 17. C9 offline mode lifecycle

C9 `_run_offline_process(mode, *args)` owns the temporary directory, writes `self._sitecustomize_text(mode)` as UTF-8, snapshots helper-directory names, delegates to `_run_process(*args, helper_path=helper_path)`, and asserts the directory names are unchanged before returning the completed process.

The two modes remain separate:

- `stock` patches `requests.get` to return a synthetic response containing the expected stock row.
- `price` patches `yfinance.download` to return an empty `DataFrame` and patches `requests.get` to raise `RuntimeError("controlled offline HTTP request")`.

The shared helper must receive only the extra path. It must not receive a stock/price mode and must not import or patch any provider library.

## 18. Sitecustomize source comparison

C8 source hash, SHA-256 of the exact UTF-8 source string:

```text
29bd50ff71b8fca42dc09ccd72ed2e84d485e0d88ce45a70432dac6e6295c283
```

C9 `stock` source hash:

```text
d78209dc93a4ba8e9deb44f1aa1111759137451532aaf5fbce8ca2d2b3d3a4bd
```

C9 `price` source hash:

```text
323cbb507547117f8ef996ea949b6f58ca896c72e1f869526701a1b23ca82b1b
```

C8 and C9 source differ in function names and provider behavior, and C9 has two distinct source bodies. The source remains local to those modules in the candidate design.

## 19. Cleanup-ownership comparison

C4 uses a per-test temporary directory owned by `setUp()`/`tearDown()`. C5, C6, and C7 use local temporary-directory contexts in individual tests for artifact checks. C8 and C9 own temporary helper directories inside `_run_offline_process()`.

The proposed helper owns no temporary directory and performs no cleanup. C8 and C9 retain their local context managers and assertions.

## 20. Artifact-check comparison

Artifact checks remain outside the helper:

- C4 checks that its fixture directory remains empty where the subprocess boundary is exercised.
- C5 compares a temporary directory before and after direct operations.
- C6 checks that successful direct execution creates no artifacts.
- C7 checks temporary-directory stability for direct and validation paths.
- C8 checks helper-directory contents before and after offline child execution.
- C9 checks helper-directory contents before and after each offline mode and checks output directories for the existing smoke-check boundaries.

No artifact assertion is a candidate for deletion or consolidation.

## 21. Invocation-boundary inventory

The existing modules protect these boundaries and all remain required:

| Module | Package boundary | Root-wrapper boundary | Unified boundary |
| --- | --- | --- | --- |
| C4 | `python -m tw_stock_tool.cli.scan_stocks` | `scan_stocks.py` | `python -m tw_stock_tool.cli.twstock_cli scan` |
| C5 | `python -m tw_stock_tool.data.cache_manager` | `cache_manager.py` | `python -m tw_stock_tool.cli.twstock_cli cache` |
| C6 | `python -m tw_stock_tool.cli.benchmark` | `benchmark.py` | `python -m tw_stock_tool.cli.twstock_cli benchmark` |
| C7 | `python -m tw_stock_tool.cli.clean_stocks` | `clean_stocks.py` | `python -m tw_stock_tool.cli.twstock_cli scan` |
| C8 | `python -m tw_stock_tool.data.stock_list_updater` | `stock_list_updater.py` | `python -m tw_stock_tool.cli.twstock_cli stock-list` |
| C9 stock | `python -m tw_stock_tool.cli.stock_list_smoke_check` | `stock_list_smoke_check.py` | `python -m tw_stock_tool.cli.twstock_cli stock-list smoke-check` |
| C9 price | `python -m tw_stock_tool.cli.price_data_smoke_check` | `price_data_smoke_check.py` | `python -m tw_stock_tool.cli.twstock_cli price-smoke-check` |

Direct function calls, `runpy` wrapper execution, import aliases, parser-owned status 2 failures, runtime status 1 failures, and unified dispatch propagation are also protected by the existing tests. The characterization phase does not combine or remove any of those cases.

## 22. Existing coverage that must remain

The six modules retain coverage for direct legacy return behavior, package execution, root-wrapper execution, unified routing, parser failures, runtime failures, status propagation, output wording, no-traceback behavior, import aliases, and artifact checks. C8 and C9 retain offline provider isolation. No existing test method or assertion is removed by P3.1.

## 23. Candidate shared boundary

The only evaluated candidate is the test-only module:

```text
tests/subprocess_test_support.py
```

It is not created in this phase. Its boundary would be limited to deterministic repository-Python subprocess setup and execution.

## 24. Module-specific behavior that must remain local

- C4’s omission of repository root and bytecode suppression.
- C5’s omission of `errors` and its `_run_python()` dedenting wrapper.
- C8’s stock-list `sitecustomize.py` source, temporary context, before/after check, and tuple return shape.
- C9’s `stock` and `price` source bodies, provider patching, mode selection, temporary context, and directory-content assertion.
- All command construction and package/root/unified invocation cases.
- All status, output, validation, and artifact assertions.

## 25. Hypothetical helper signature

The smallest evaluated interface is:

```python
run_repo_python(
    *args,
    extra_pythonpath=(),
    include_repository_root=True,
    suppress_bytecode=True,
    errors="replace",
)
```

The helper would preserve `sys.executable`, `REPOSITORY_ROOT`, deterministic `PYTHONPATH`, inherited `PYTHONPATH`, `capture_output=True`, `text=True`, optional `errors`, and `check=False`.

## 26. Helper parameter assessment

The four configuration parameters are sufficient and bounded:

1. `extra_pythonpath`: prepends C8/C9 temporary helper paths.
2. `include_repository_root`: preserves C4’s root omission.
3. `suppress_bytecode`: preserves C4’s absent setting.
4. `errors`: `None` omits the keyword for C5; `"replace"` preserves the other runners.

No behavior-specific subclass, mode flag, command-name conditional, provider parameter, cleanup callback, or route table is required.

## 27. Helper complexity assessment

The candidate passes the complexity gate:

- One shared function is sufficient.
- No stock/price mode belongs in the helper.
- Offline source creation remains local to C8/C9.
- Existing command construction remains visible in each module.
- All invocation tests remain.
- Four simple configuration parameters are sufficient.
- The conservative net estimate is 54 nonblank test lines, above the 25-line threshold.
- The helper is smaller than the duplicated environment and invocation setup it replaces.

## 28. Current candidate LOC

Counts below were produced from the tracked source using Python `ast` function spans and a nonblank executable-line count. The physical span includes signatures and blank lines; reduction estimates use nonblank lines and do not count blank-line deletion, comments, assertion deletion, test deletion, output assertion deletion, or boundary consolidation.

| Module | Helper spans | Physical lines | Nonblank lines |
| --- | --- | ---: | ---: |
| C4 | `_run_process` | 15 | 15 |
| C5 | `_run_process`, `_run_python` | 17 | 17 |
| C6 | `_run_process` | 16 | 16 |
| C7 | `_run_process` | 16 | 16 |
| C8 | `_run_process`, `_run_offline_process` | 61 | 54 |
| C9 common | `_run_process`, `_run_offline_process` | 39 | 39 |
| C9 local source, excluded from candidate | `_sitecustomize_text` | 35 | 22 |
| Total selected spans | Including C9 source | 199 | 179 |
| Candidate total | Excluding C9 source | 164 | 157 |

## 29. Helper-eligible LOC

The conservative replacement inventory identifies 120 existing nonblank lines as common subprocess/environment setup eligible for replacement:

- Six `_run_process()` bodies: 101 lines total.
- C8’s duplicated offline environment and invocation block: 19 lines.
- C5 `_run_python()`, C8 source/cleanup, C9 source/cleanup, and all assertions are retained and excluded from eligible deletion.

## 30. Retained local LOC

The hypothetical implementation retains approximately 74 nonblank module-local lines in the candidate spans. This includes the six thin local wrappers, C5 `_run_python()`, C8 source and lifecycle, C9 source and lifecycle, and the replacement call sites. These lines preserve readability and module-specific behavior.

## 31. Hypothetical helper LOC

The minimized helper design is estimated at 23 nonblank lines, including imports, repository-root resolution, deterministic environment construction, optional decoding, and one `subprocess.run()` call. It contains no provider imports, source generation, cleanup, or route logic.

## 32. Import/call-site LOC

The implementation phase would add six one-line imports, one per target module. Replacement call sites are included in the 74 retained local lines. No existing invocation test or assertion is removed.

## 33. Conservative net reduction

```text
Current candidate:       157 nonblank lines
- retained local code:    74 nonblank lines
- hypothetical helper:   23 nonblank lines
- six import lines:        6 lines
                          ----------------
Conservative net:         54 nonblank test lines
```

This estimate is tied to a concrete four-parameter helper and concrete local wrappers. It is not a claim that 120 lines can simply be deleted without replacement.

## 34. Decision-gate evaluation

| Gate | Result | Evidence |
| --- | --- | --- |
| One shared function sufficient | Pass | Six runner variants are covered by four bounded parameters. |
| No behavior-specific subclasses | Pass | No subclass or mode is required. |
| Offline source remains local | Pass | C8/C9 source hashes and writes remain local. |
| Existing command construction remains visible | Pass | Helper accepts `*args`; route-specific calls remain in modules. |
| All invocation tests remain | Pass | Existing suites passed unchanged. |
| At most four simple configuration parameters | Pass | Extra path, root inclusion, bytecode, decoding. |
| Net reduction at least 25 lines | Pass | Conservative estimate: 54 lines. |
| Helper simpler than duplication | Pass | 23 helper lines replace 120 common setup lines while preserving local boundaries. |

## 35. Final outcome

```text
PROCEED_TO_P3_2
```

This is a characterization decision only. P3.2 implementation is not started by this branch.

## 36. Exact files changed

Only these approved files were added:

- `tests/test_track_p3_1_subprocess_test_helper_characterization.py`
- `docs/TRACK_P3_1_SUBPROCESS_TEST_HELPER_CHARACTERIZATION.md`

No existing file was modified.

## 37. Targeted test result

```text
py -m unittest tests.test_track_p3_1_subprocess_test_helper_characterization
Ran 5 tests
OK
```

All subprocess calls in the new characterization test were patched. No child command or live network service was invoked by the new test.

## 38. Combined test result

The required C4-C9 boundary suite plus the new characterization test passed:

```text
Ran 120 tests
OK
```

## 39. Full-suite results

Both required full suites passed ordinarily:

```text
py -m unittest discover -s tests
Ran 1622 tests
OK

python -m unittest discover -s tests
Ran 1622 tests
OK
```

The suites produced the repository’s existing mocked/offline diagnostic output and warnings, but no test failure or expected-failure result.

## 40. `git diff --check`

The final documentation-only/test-only diff passed `git diff --check` with no output.

## 41. UTF-8 BOM result

Both added files are UTF-8 without a BOM. The check used the first-three-byte test and found no `EF BB BF` prefix.

## 42. No-existing-test-change confirmation

`git diff --name-only` shows only the two approved new files. The six C4-C9 modules and adjacent P1.1/P2.1 tests were inspected but not modified. No production code, dependency, configuration, wrapper, or public API changed.

No helper directory, bytecode artifact, generated report, or persistent output was added to the Git worktree. No live network request occurred as part of the new characterization test.

## 43. Branch disposition

One tests-and-documentation-only commit was created on:

```text
track-p3-1-subprocess-test-helper-characterization
```

The branch was pushed and was not merged. P3.2 was not started.

```text
Track P3.1 Characterization: PASS -- DECISION RECORDED
```
