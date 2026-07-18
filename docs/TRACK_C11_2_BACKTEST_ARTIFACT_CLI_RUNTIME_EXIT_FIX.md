# Track C11.2 - Backtest Artifact CLI Runtime Exit Contract Fix

1. Executive outcome

C11.2 is implemented and validated on the required branch. Handled runtime failures now return integer status code 1 to callers while the module guard converts that result into the process exit code.

2. Formal implementation result

PASS. The production CLI, its direct tests, and the C11.1 characterization assertions now express the intended runtime exit contract. Successful direct calls retain their existing implicit None result.

3. Verified parent

Parent branch: track-c11-1-backtest-artifact-cli-runtime-exit-characterization
Parent commit: 857f4aa7224b74ddb619d3d58ba55f319b014452 (Fix C11.1 closeout report)

4. Main baseline and ancestry

main and origin/main were both 4411b15d3d28a8a5072f4eae082c75e84d13cbce. The new branch was created from the required C11.1 parent, whose merge base with main is that baseline and which is exactly two commits ahead.

5. New branch

track-c11-2-backtest-artifact-cli-runtime-exit-fix

6. Exact changed files

Only these four paths are in scope:

- src/tw_stock_tool/cli/backtest_artifact_cli.py
- tests/test_backtest_artifact_cli.py
- tests/test_track_c11_1_backtest_artifact_cli_runtime_exit_behavior.py
- docs/TRACK_C11_2_BACKTEST_ARTIFACT_CLI_RUNTIME_EXIT_FIX.md

7. Pre-fix contract

The six caught runtime exception handlers called parser.exit(1, ...), so direct callers and unified in-process callers observed SystemExit(1). The package process and unified subprocess already exposed exit code 1. This left direct and process contracts inconsistent.

8. Production changes

Added sys, changed main to return int | None, replaced each caught parser.exit call with an exact stderr print plus return 1, and changed the module guard to raise SystemExit(main()). No success return was added.

9. Test changes

Updated only runtime-failure expectations in the existing direct CLI tests and C11.1 characterization tests. Help and parser-error assertions remain SystemExit-based, success behavior remains unchanged, and argv, forwarding, filesystem, safety, metadata, wrapper, and offline assertions remain covered.

10. Direct function matrix

Direct backtest_artifact_cli.main runtime failures for missing input, invalid JSON, invalid schema, readback validation, existing output without --overwrite, output directory, and invalid trade structure return 1 and print clean stderr. Direct success paths return None.

11. Package module matrix

Running python -m tw_stock_tool.cli.backtest_artifact_cli preserves process exit 0 for help and success, 2 for argparse failures, and 1 for handled runtime failures.

12. Unified function matrix

twstock_cli.main returns 0 for successful backtest-artifact operations, returns 1 for handled runtime failures, and preserves SystemExit(2) for child argparse failures. sys.argv is restored after dispatch.

13. Unified module matrix

Running the unified twstock entry point preserves process exit 0 for success/help, 2 for parser failures, and 1 for handled backtest-artifact runtime failures.

14. Argparse preservation

Argparse exits were not caught or rewritten. Help remains SystemExit(0), missing or invalid parser arguments remain SystemExit(2), and only the pre-existing caught runtime exception classes changed contract.

15. Error wording

FileExistsError retains: error: <original exception>. Use --overwrite to replace existing files. All other handled runtime exceptions retain: error: <original exception>. Output remains on stderr without traceback text.

16. Filesystem and overwrite

Existing output remains unchanged without --overwrite, overwrite still replaces it, output-directory failures return 1, and no partial success message is emitted after readback validation failure.

17. argv restoration

The unified function tests continue to verify that sys.argv is restored after runtime failure and that child arguments are forwarded in order.

18. Module guard

The package CLI guard is now exactly raise SystemExit(main()), allowing the integer return from direct execution to become the process exit code without changing caller behavior.

19. Root wrapper

No root-level backtest_artifact_cli.py wrapper was added or modified. The existing absence assertion passes.

20. Metadata

The console-script mapping remains twstock = tw_stock_tool.cli.twstock_cli:main.

21. Offline and research-only scope

No network, broker, market-data, strategy-execution, serializer, converter, unified-dispatcher, dependency, README, or custom_md.md changes were made. The source remains research-only and offline at the CLI boundary.

22. Defect closure

| Defect | Result |
| --- | --- |
| C11.1-DEFECT-01 | CLOSED - direct handled runtime failures return 1 |
| C11.1-DEFECT-02 | CLOSED - unified function handled runtime failures return 1 |
| C11.1-DEFECT-03 | CLOSED - package guard propagates integer results |

The C11.1 historical report was not modified.

23. Expected-failure conversion

All three C11.1 expectedFailure markers were removed. The former future-contract tests and package-guard structural test now pass ordinarily; the C11.2 characterization module has zero expected failures.

24. Targeted validation

py -m unittest tests.test_track_c11_1_backtest_artifact_cli_runtime_exit_behavior: 37 tests, OK.
py -m unittest tests.test_backtest_artifact_cli: 16 tests, OK.

25. Combined validation

The required five-module combined command ran 109 tests and completed OK.

26. Full validation

Both required full-suite interpreter commands completed OK. No failures, errors, skips, or expected failures were reported.

27. Exact validation counts

python -m unittest discover -s tests: 1683 tests in 104.072s, OK.
py -m unittest discover -s tests: 1683 tests in 99.420s, OK.

28. Diff checks

The final validation includes git diff --check, git diff --stat, and git diff --name-only. The changed-file list is exactly the four approved paths and the diff has no whitespace errors.

29. BOM checks

Each changed or added text file is checked bytewise for UTF-8 BOM bytes EF BB BF. The deterministic check reports no BOM in any of the four approved paths.

30. Scope proof

No unapproved path is staged or present as an untracked file. The historical C11.1 report remains byte-for-byte outside this change, and no main branch or C12 work is included.

31. Working tree

The working tree is expected to be clean after commit and push. The final status and untracked-file checks are part of the required handoff validation.

32. Commit and push

One intentional commit will be created with message: Fix backtest artifact CLI runtime exits. It will be pushed only to origin/track-c11-2-backtest-artifact-cli-runtime-exit-fix.

33. Merge disposition

The branch remains HOLD FOR REVIEW. No merge to main, pull request, release action, or C12 work is authorized by this track.

34. Exact validation commands

py -m unittest tests.test_track_c11_1_backtest_artifact_cli_runtime_exit_behavior
py -m unittest tests.test_backtest_artifact_cli
py -m unittest tests.test_track_c11_1_backtest_artifact_cli_runtime_exit_behavior tests.test_backtest_artifact_cli tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes
py -m unittest discover -s tests
python -m unittest discover -s tests
git diff --check
git diff --stat
git diff --name-only
git status --short
git ls-files --others --exclude-standard
@(
    'src/tw_stock_tool/cli/backtest_artifact_cli.py'
    'tests/test_backtest_artifact_cli.py'
    'tests/test_track_c11_1_backtest_artifact_cli_runtime_exit_behavior.py'
    'docs/TRACK_C11_2_BACKTEST_ARTIFACT_CLI_RUNTIME_EXIT_FIX.md'
) | ForEach-Object {
    $bytes = [IO.File]::ReadAllBytes($_)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 239 -and $bytes[1] -eq 187 -and $bytes[2] -eq 191) { throw "UTF-8 BOM: $_" }
}

Track C11.2 Implementation: PASS
Defects closed: C11.1-DEFECT-01, C11.1-DEFECT-02, C11.1-DEFECT-03
Branch disposition: HOLD FOR REVIEW
Merge was not performed.
C12 was not started.
