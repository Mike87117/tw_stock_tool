# Track C10.2 ? Simulated Paper Trading Export CLI Runtime Exit Fix

## 1. Executive outcome
Handled runtime and file failures now print the existing clean error text and return integer `1` from direct calls.

## 2. Formal result
Track C10.2 Implementation: PASS -- READY FOR REVIEW

## 3. Repository baseline
`main == origin/main == 43402917cdf05822dfcd5622d96c8bdd46eae5cc`; approved parent is `f9d2261a9dd17baf68e5bbc1f3a1587fdf2982c6`.

## 4. Complete stacked-parent relationship
`43402917cdf05822dfcd5622d96c8bdd46eae5cc` main baseline ? `ae5eb66903c4fb107428596325f90fae788e7dbf` P3.1 characterization ? `7a46af2acf75bca6f4eac592afd4ea2c0734b8ef` CI portability fix ? `373bb4fff3d389d96a9728f14d2b1cba634004d0` P3.2 subprocess test helper ? `f9d2261a9dd17baf68e5bbc1f3a1587fdf2982c6` C10.1 characterization ? this C10.2 implementation commit.

## 5. C10.1 decision
The three characterized expected failures were closed as ordinary passing tests.

## 6. Working-tree protection
Only approved files were touched; `custom_md.md` was not inspected, read, modified, staged, restored, deleted, or cleaned.

## 7. LLM Wiki availability result
The optional local Wiki at `127.0.0.1:8000` was unavailable (connection failure); this was non-blocking. No other Wiki endpoint was queried.

## 8. Exact production defect
Handled failures called `parser.exit(1, ...)`, raising `SystemExit(1)` during direct callable use.

## 9. Approved production scope
Only `src/tw_stock_tool/cli/simulated_paper_trading_export_cli.py` was changed in production code.

## 10. Return annotation change
`main` now declares `-> int | None` without changing its arguments.

## 11. Input-loading error handling
The existing `FileNotFoundError`, `IsADirectoryError`, `PermissionError`, and `PaperTradingModelError` handlers print to stderr and return `1`.

## 12. Export error handling
The existing `FileExistsError` and output-path exception handlers print to stderr and return `1`; exception boundaries were not broadened.

## 13. Error wording preservation
The lowercase `error:` prefix and overwrite suffix remain unchanged.

## 14. Direct success preservation
Successful direct calls still reach the end normally and return `None`.

## 15. Direct runtime-failure result
Missing input, invalid JSON, unsupported schema, and existing output without overwrite return `1` directly.

## 16. Parser-owned behavior preservation
Help remains `SystemExit(0)`; missing output targets and unknown options remain parser status `2`.

## 17. Package executable-guard change
The package guard now uses `raise SystemExit(main())`.

## 18. Package-module result
Package-module runtime failures continue to exit with process status `1`.

## 19. Unified-function result
Unified success remains `0` through child `None` mapping; unified runtime failure is `1` through integer passthrough.

## 20. Unified-module result
Unified-module runtime failures continue to exit with process status `1`.

## 21. `sys.argv` restoration
The existing unified context manager continues to restore `sys.argv` exactly.

## 22. Partial-output semantics preservation
Markdown remains written before CSV export; no preflight, transaction, rollback, replacement, or reordering was added.

## 23. Root-wrapper absence preservation
No root-level `simulated_paper_trading_export_cli.py` wrapper was added.

## 24. Console metadata preservation
`twstock = "tw_stock_tool.cli.twstock_cli:main"` remains unchanged.

## 25. Artifact-format preservation
Serialization, Markdown, CSV names and headers, encoding, directory creation, overwrite behavior, models, and calculations were untouched.

## 26. Existing-test updates
The four direct runtime-failure expectations now assert integer `1`; help, parser, success, overwrite, safety, and offline-import tests were preserved.

## 27. Expected-failure closure
The C10 characterization module has 24 ordinary passes, zero expected failures, zero skips, zero failures, and zero errors.

## 28. Exact files changed
`src/tw_stock_tool/cli/simulated_paper_trading_export_cli.py`; `tests/test_simulated_paper_trading_export_cli.py`; `tests/test_track_c10_1_simulated_paper_trading_export_cli_runtime_exit_behavior.py`; `docs/TRACK_C10_2_SIMULATED_PAPER_TRADING_EXPORT_CLI_RUNTIME_EXIT_FIX.md`.

## 29. Targeted test result
`py -m unittest tests.test_track_c10_1_simulated_paper_trading_export_cli_runtime_exit_behavior`: 24 tests, all ordinary passes.

## 30. Combined test result
The required combined regression set passed 97/97 tests with zero expected failures, skips, failures, or errors.

## 31. Both full-suite results
Both `py -m unittest discover -s tests` and `python -m unittest discover -s tests` passed 1,646/1,646 tests with zero expected failures, skips, failures, or errors.

## 32. `git diff --check`
Passed with no whitespace errors.

## 33. UTF-8 BOM result
All four changed files are UTF-8 without BOM.

## 34. No-live-request result
No live market-data request, broker connection, order placement, or installed `twstock` command was used.

## 35. No-artifact result
Test outputs remained in temporary test locations; no helper directory, cache, output, bytecode, or generated artifact is included in the final change.

## 36. No-unrelated-production-change confirmation
No unified CLI, exporter, serializer, model, dependency, CI, README, `pyproject.toml`, or unrelated production file was changed.

## 37. Branch disposition
Branch: `track-c10-2-simulated-paper-trading-export-cli-runtime-exit-fix`; ready for merge review after push.

## 38. Merge-carrier status
One C10.2 implementation commit will carry the complete held stack; no merge, rebase, squash, amend, force-push, or pull request was created.
