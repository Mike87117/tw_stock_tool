
# Track C10.1 - Simulated Paper Trading Export CLI Runtime Exit Characterization

## 1. Executive outcome

C10.1 characterized the direct exporter, package-module, unified-function, unified-module, package-guard, root-wrapper, and console-metadata boundaries for the simulated paper trading export command.

The exporter is locally deterministic and research-only. The new tests use the real JSON serialization boundary, temporary directories, and the shared repository subprocess helper. No market-data provider, broker, live-trading path, strategy execution path, or production module was modified.

The complete characterization records five current defects against the future integer-return contract. The approved next decision is recorded as PROCEED_TO_C10_2. C10.2 was not started.

## 2. Formal result

Track C10.1 Characterization: PASS -- DECISION RECORDED

Final outcome: PROCEED_TO_C10_2

The result is a characterization decision, not a production fix.

## 3. Repository baseline

- Repository: Mike87117/tw_stock_tool
- Required main baseline: 43402917cdf05822dfcd5622d96c8bdd46eae5cc
- Parent branch: track-p3-2-shared-subprocess-test-helper-v2
- Parent commit: 373bb4fff3d389d96a9728f14d2b1cba634004d0
- Implementation branch: track-c10-1-simulated-paper-trading-export-cli-runtime-exit-characterization
- The branch was created directly from the approved parent.
- No rebase, merge, squash, amend, or force-push was performed.

The parent and main SHAs were verified against origin before changes.

## 4. Complete stacked-parent relationship

    43402917cdf05822dfcd5622d96c8bdd46eae5cc
      main baseline

    ae5eb66903c4fb107428596325f90fae788e7dbf
      P3.1 subprocess-helper characterization

    7a46af2acf75bca6f4eac592afd4ea2c0734b8ef
      P3.1 CI portability fix

    373bb4fff3d389d96a9728f14d2b1cba634004d0
      P3.2 shared subprocess test helper

    new C10.1 commit
      simulated paper trading export CLI runtime characterization

## 5. Working-tree protection

The ignored user-owned file custom_md.md was not inspected, modified, staged, restored, deleted, or cleaned. git clean was not run.

Only the two approved new files were added. No existing file was modified.

## 6. LLM Wiki availability result

The local LLM Wiki service and its health, project, and search endpoints were not available as callable tools in this session. This was non-blocking.

Repository source, existing tests, and the new deterministic characterization tests were treated as authoritative. No attempt was made to repair or reconfigure LLM Wiki.

## 7. Existing implementation inventory

The characterized production module is:

    src/tw_stock_tool/cli/simulated_paper_trading_export_cli.py

It currently:

- builds an argparse parser for an input JSON artifact;
- requires at least one of output Markdown or output CSV directory;
- loads the artifact through load_simulated_paper_trading_result_json_file;
- exports through the existing Markdown and CSV file boundaries;
- uses parser.error for missing output targets;
- uses parser.exit(1, ...) for missing files, model errors, and existing output files;
- returns None after successful direct export;
- calls main() directly in its package executable guard.

The unified route is simulated-paper-trading-export in:

    src/tw_stock_tool/cli/twstock_cli.py

The unified dispatcher maps a child None result to integer 0 and propagates a child SystemExit.

## 8. Existing test inventory

The parent already contains:

- tests/test_simulated_paper_trading_export_cli.py
  - direct help and safety wording;
  - missing output target;
  - Markdown, CSV, and combined export;
  - overwrite behavior;
  - invalid JSON, unsupported schema, and missing input;
  - no-live-data import restrictions.
- tests/test_twstock_cli.py
  - unified route dispatch;
  - route arguments;
  - help registration;
  - status propagation and argv behavior;
  - console metadata and root unified wrapper behavior.
- tests/test_track_p2_1_unified_cli_passthrough_registration_characterization.py
  - route inventory and exact unified boundary characterization.
- tests/subprocess_test_support.py
  - shared offline repository-Python subprocess execution.
- tests/test_track_p3_1_subprocess_test_helper_characterization.py
  - shared-helper environment and invocation snapshots.

No existing test was modified or reinterpreted.

## 9. Test-gap inventory

Before C10.1 there was no dedicated process-level characterization for this export command covering the full matrix of:

- direct callable result versus SystemExit behavior;
- package-module status;
- unified function status and argv restoration on success and failure;
- unified-module status;
- package executable-guard propagation;
- root-wrapper absence;
- console-script metadata as a source-tree assertion.

C10.1 supplements existing export and unified-route coverage without replacing it.

## 10. Artifact-fixture design

Each new test creates a TemporaryDirectory and keeps all generated files inside it.

The fixture uses the real SimulatedOrder, SimulatedFill, and SimulatedPaperTradingResult models with deterministic symbol, dates, cash, quantity, fee, and price values. It writes the input JSON through export_simulated_paper_trading_result_json_file rather than copying a production JSON schema.

Markdown and CSV assertions use the existing exporter output contracts. Tests assert expected filenames, stable headings or CSV headers, content preservation, and absence of unrelated files.

No output is written outside the per-test temporary directory.

## 11. Complete characterization matrix

| ID | Boundary | Scenario | Current result | Future contract | Classification |
| --- | --- | --- | --- | --- | --- |
| C10.1-SPTE-01 | Direct callable | Markdown success | returns None and writes the Markdown artifact | preserve legacy None | CORRECTLY_HANDLED |
| C10.1-SPTE-02 | Direct callable | CSV success | returns None and writes the five-file CSV bundle | preserve legacy None | CORRECTLY_HANDLED |
| C10.1-SPTE-03 | Direct callable | Missing output target | parser raises SystemExit(2) | parser-owned status 2 | CORRECTLY_HANDLED |
| C10.1-SPTE-04 | Direct callable | Missing input JSON | parser raises SystemExit(1) | return integer 1 | DEFECT_CONFIRMED |
| C10.1-SPTE-05 | Direct callable | Invalid JSON/schema | parser raises SystemExit(1) with clean error | return integer 1 | DEFECT_CONFIRMED |
| C10.1-SPTE-06 | Direct callable | Existing output without overwrite | parser raises SystemExit(1), existing file unchanged | return integer 1 | DEFECT_CONFIRMED |
| C10.1-SPTE-07 | Package module | Help | exits 0 | exit 0 | CORRECTLY_HANDLED |
| C10.1-SPTE-08 | Package module | Missing output target | exits 2 with argparse error | exit 2 | CORRECTLY_HANDLED |
| C10.1-SPTE-09 | Package module | Missing input JSON | exits 1 with clean error | exit 1 | CORRECTLY_HANDLED |
| C10.1-SPTE-10 | Unified function | Successful export | returns integer 0 | return integer 0 | CORRECTLY_HANDLED |
| C10.1-SPTE-11 | Unified function | Missing input JSON | raises SystemExit(1), restores sys.argv | return integer 1 and restore sys.argv | DEFECT_CONFIRMED |
| C10.1-SPTE-12 | Unified module | Help | exits 0 | exit 0 | CORRECTLY_HANDLED |
| C10.1-SPTE-13 | Unified module | Missing output target | exits 2 | exit 2 | CORRECTLY_HANDLED |
| C10.1-SPTE-14 | Unified module | Missing input JSON | exits 1 with clean error | exit 1 | CORRECTLY_HANDLED |
| C10.1-SPTE-15 | Package guard | Integer status propagation | source calls main() directly without raise SystemExit | raise SystemExit(main()) | DEFECT_CONFIRMED |
| C10.1-SPTE-16 | Root wrapper | File presence | simulated_paper_trading_export_cli.py is absent at repository root | do not create one | NOT_APPLICABLE |
| C10.1-SPTE-17 | Console metadata | twstock mapping | pyproject.toml maps twstock to the unified main | preserve mapping only | CORRECTLY_HANDLED |

Counts:

- characterization rows: 17;
- CORRECTLY_HANDLED: 11;
- DEFECT_CONFIRMED: 5;
- NOT_APPLICABLE: 1.

## 12. Direct success results

Markdown export returned None, created the requested Markdown file, preserved the existing report heading and summary values, and created no unrelated file.

CSV export returned None and created the expected summary, orders, fills, rejections, and trade-log CSV files under the requested directory.

Combined Markdown and CSV export returned None and created both requested output forms without changing the input artifact.

## 13. Parser-owned error results

Direct help raised SystemExit(0) and retained the research-only safety wording.

Direct missing output targets raised SystemExit(2) through parser.error. An invalid option also raised SystemExit(2).

Package-module and unified-module parser controls produced process status 2, usage text, and no traceback or output artifact.

Status 2 was classified as correctly handled parser behavior, not as a runtime defect.

## 14. Direct runtime-failure results

Missing input, invalid JSON, unsupported schema, and existing output without overwrite all produced clean stderr and no traceback.

The current direct callable behavior is SystemExit(1), not integer return 1. Existing output remained unchanged when overwrite was not supplied.

These three direct runtime cases are DEFECT_CONFIRMED against the future callable contract.

## 15. Package-module results

The command:

    python -m tw_stock_tool.cli.simulated_paper_trading_export_cli

produced:

- help status 0;
- missing-output parser status 2;
- missing-input runtime status 1;
- visible clean error text;
- no traceback;
- no output artifact on failure.

The package-module process boundary already satisfies the future process-status contract.

## 16. Unified-function results

twstock_cli.main successfully dispatched the route and returned integer 0 for a successful export.

On missing input, the child currently raises SystemExit(1). The unified context manager restored sys.argv exactly after the failure. This is DEFECT_CONFIRMED only for the direct callable return contract; argv restoration is correctly handled.

## 17. Unified-module results

The command:

    python -m tw_stock_tool.cli.twstock_cli simulated-paper-trading-export ...

produced:

- help status 0;
- parser-owned missing-output status 2;
- missing-input runtime status 1;
- clean visible errors;
- no traceback;
- no output artifact on failure.

The unified process boundary already satisfies the future process-status contract.

## 18. Package-guard result

The source guard is currently:

    if __name__ == "__main__":
        main()

It does not explicitly use raise SystemExit(main()). The future-contract expected-failure test records this structural gap without modifying production code.

## 19. Root-wrapper presence result

The repository-root file:

    simulated_paper_trading_export_cli.py

is absent.

This is NOT_APPLICABLE, not a defect. The command is intentionally exercised through its package module and unified CLI route. No root wrapper was added.

## 20. Console-script metadata result

pyproject.toml preserves:

    twstock = tw_stock_tool.cli.twstock_cli:main

The characterization reads this mapping directly. It does not execute twstock, use shutil.which, install the project, create a fake launcher, or use shell=True.

## 21. sys.argv restoration result

The unified dispatcher restored sys.argv exactly on successful export and on handled runtime failure.

The exact child argv route was retained:

    simulated_paper_trading_export_cli.py
    input.json
    --output-markdown
    output.md

## 22. Error-output and traceback result

All tested runtime failures emitted clean error text on stderr and no traceback.

Parser-owned failures emitted argparse usage and status 2. Help emitted status 0 and the existing research-only safety wording.

No new wording or production output was introduced.

## 23. Filesystem-artifact result

Success tests asserted the exact expected Markdown and CSV files.

Failure tests asserted no unexpected output artifact. Existing output remained byte-for-byte unchanged for the no-overwrite case.

Temporary directories were owned by each test and cleaned by tearDown. The new subprocess tests use the shared bytecode-suppressing helper. No persistent helper directory, cache, output file, or bytecode artifact remained.

## 24. No-live-request result

The new tests use only local JSON files and the real local serializer/exporter boundaries. No yfinance, TWSE, TPEx, requests, broker, or market-data provider was invoked.

The exporter source imports only argparse, pathlib, paper-trading model/serialization, and export-file boundaries. The new tests do not execute the installed twstock command or any live market path.

## 25. Existing coverage preservation

The following existing files were not modified:

- tests/test_simulated_paper_trading_export_cli.py
- tests/test_twstock_cli.py
- tests/test_track_p2_1_unified_cli_passthrough_registration_characterization.py
- src/tw_stock_tool/cli/simulated_paper_trading_export_cli.py
- src/tw_stock_tool/cli/twstock_cli.py
- pyproject.toml
- tests/subprocess_test_support.py
- tests/test_track_p3_1_subprocess_test_helper_characterization.py

No existing test method was removed, renamed, skipped, or weakened.

## 26. Expected-failure inventory

Exactly three expected-failure tests were added:

1. Direct handled runtime failure should return integer 1.
2. Unified-function handled runtime failure should return integer 1.
3. Package guard should use raise SystemExit(main()).

No help, parser status 2, process status 1, filesystem, output, or safety-wording test was marked expected failure.

The targeted suite had 21 ordinary passes and 3 expected failures. The combined and full suites had no ordinary failures or errors.

## 27. C10.2 candidate scope

If C10.2 is separately approved, its narrow production scope is:

- change direct handled runtime and file-error paths from parser.exit(1, ...) to integer return 1 while preserving error wording;
- retain direct success as None;
- retain parser-owned help 0 and argparse errors 2;
- retain unified success mapping to 0;
- retain unified failure propagation as integer 1;
- change the package executable guard to raise SystemExit(main());
- preserve sys.argv restoration, output files, overwrite behavior, schema validation, and safety wording.

This is a candidate scope only. No C10.2 production edit was made.

## 28. Explicit production-fix restriction

C10.1 did not modify production code, CLI routing, parser behavior, output wording, artifact serialization, root wrappers, metadata, dependencies, or package guards.

The three expected failures record the future contract without implementing it.

## 29. Exact files changed

Only these two new files were added:

- tests/test_track_c10_1_simulated_paper_trading_export_cli_runtime_exit_behavior.py
- docs/TRACK_C10_1_SIMULATED_PAPER_TRADING_EXPORT_CLI_RUNTIME_EXIT_BEHAVIOR_CHARACTERIZATION.md

No existing file was modified.

## 30. Targeted test result

Command:

    py -m unittest tests.test_track_c10_1_simulated_paper_trading_export_cli_runtime_exit_behavior

Result:

    Ran 24 tests
    OK (expected failures=3)

Ordinary failures: 0.
Errors: 0.
Expected failures: 3.

## 31. Combined test result

Command:

    py -m unittest tests.test_track_c10_1_simulated_paper_trading_export_cli_runtime_exit_behavior tests.test_simulated_paper_trading_export_cli tests.test_twstock_cli tests.test_track_p2_1_unified_cli_passthrough_registration_characterization tests.test_track_p3_1_subprocess_test_helper_characterization

Result:

    Ran 97 tests
    OK (expected failures=3)

Ordinary failures: 0.
Errors: 0.
Expected failures: 3.

## 32. Both full-suite results

Command:

    py -m unittest discover -s tests

Result:

    Ran 1646 tests
    OK (expected failures=3)

Command:

    python -m unittest discover -s tests

Result:

    Ran 1646 tests
    OK (expected failures=3)

The increase from the 1,622-test stacked baseline is the 24-test C10.1 module. Existing full-suite diagnostic output and warnings remained ordinary test output.

## 33. git diff --check

Final git diff --check passed.

The final changed-file scope contains only the two approved additions. No existing test, production, CI, dependency, or metadata file changed.

## 34. UTF-8 BOM result

Both changed files decode as UTF-8 and have no UTF-8 BOM.

## 35. Final outcome

PROCEED_TO_C10_2

This outcome is based on five confirmed deviations from the future direct/unified callable integer-return and package-guard propagation contract. The package-module and unified-module process boundaries, parser statuses, help status, argv restoration, output behavior, and safety boundaries are already characterized as correct.

C10.2 was not started.

## 36. Branch disposition

The branch remains separate from the approved parent and is not merged. No pull request was created. No later phase was started.

The branch is held for review with the characterization decision recorded.

Track C10.1 Characterization: PASS -- DECISION RECORDED
