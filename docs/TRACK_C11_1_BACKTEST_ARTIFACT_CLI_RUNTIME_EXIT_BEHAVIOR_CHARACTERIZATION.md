# Track C11.1 — Backtest Artifact CLI Runtime Exit Behavior Characterization

## 1. Executive outcome
Current callable, package-module, unified-function, and unified-module behavior was characterized offline without changing production code.

## 2. Formal result
Track C11.1 Characterization: PASS -- DECISION RECORDED

## 3. Repository baseline
`HEAD`, `main`, and `origin/main` were verified as `4411b15d3d28a8a5072f4eae082c75e84d13cbce`.

## 4. Branch and parent relationship
Branch `track-c11-1-backtest-artifact-cli-runtime-exit-characterization` was created directly from the verified main baseline.

## 5. Working-tree and ignored-file protection
The tracked working tree was clean before work. `custom_md.md` was not inspected, modified, staged, deleted, restored, or cleaned; `git clean` was not run.

## 6. LLM Wiki availability result
The optional local Wiki health endpoint at `127.0.0.1:8000/api/v1/health` was unavailable with a connection failure; this was non-blocking. No other Wiki endpoint was queried.

## 7. Production implementation inventory
`backtest_artifact_cli.main` currently returns `None` on success, uses `parser.exit(1, ...)` for handled runtime/file failures, and calls `main()` directly from its package guard.

## 8. Existing test inventory
Existing inventories inspected included 16 Backtest Artifact CLI tests, 48 unified CLI tests, 5 root-wrapper tests, 3 root-wrapper-exit tests, and related serialization/converter tests.

## 9. Test-gap inventory
Before C11.1 there was no complete deterministic boundary matrix covering direct callable return behavior, unified runtime propagation, package-module execution, guard structure, and conversion output preservation together.

## 10. Fixture design
Each test creates a deterministic real `BacktestResult`, exports it through `export_backtest_result_json_file`, and reads conversion output through `load_simulated_paper_trading_result_json_file`. All artifact files are under `TemporaryDirectory`.

## 11. Complete characterization matrix

| ID | Boundary | Scenario | Current result | Future contract | Classification |
|---|---|---|---|---|---|
| D1 | Direct | Valid validate | `None`, validation text | `None` | CORRECTLY_HANDLED |
| D2 | Direct | Valid inspect | `None`, summary text | `None` | CORRECTLY_HANDLED |
| D3 | Direct | Valid conversion | `None`, valid output | `None` | CORRECTLY_HANDLED |
| D4 | Direct | Help | `SystemExit(0)` | Status `0` | CORRECTLY_HANDLED |
| D5 | Direct | Missing command | `SystemExit(2)` | Status `2` | CORRECTLY_HANDLED |
| D6 | Direct | Unknown command | `SystemExit(2)` | Status `2` | CORRECTLY_HANDLED |
| D7 | Direct | Missing input | `SystemExit(1)` | Return `1` | DEFECT_CONFIRMED |
| D8 | Direct | Invalid JSON | `SystemExit(1)` | Return `1` | DEFECT_CONFIRMED |
| D9 | Direct | Invalid schema | `SystemExit(1)` | Return `1` | DEFECT_CONFIRMED |
| D10 | Direct | Existing output without overwrite | `SystemExit(1)`; sentinel preserved | Return `1`; preserve sentinel | DEFECT_CONFIRMED |
| D11 | Direct | Existing output with overwrite | `None`; valid replacement | `None`; valid replacement | CORRECTLY_HANDLED |
| D12 | Direct | Output path is directory | `SystemExit(1)` | Return `1` | DEFECT_CONFIRMED |
| D13 | Direct | Converter validation failure | `SystemExit(1)` | Return `1` | DEFECT_CONFIRMED |
| P1 | Package module | Help | Process `0` | Process `0` | CORRECTLY_HANDLED |
| P2 | Package module | Missing command | Process `2` | Process `2` | CORRECTLY_HANDLED |
| P3 | Package module | Runtime failure | Process `1`, clean stderr | Process `1`, clean stderr | CORRECTLY_HANDLED |
| P4 | Package module | Validate/conversion success | Process `0` | Process `0` | CORRECTLY_HANDLED |
| U1 | Unified function | Validate/inspect/convert success | Integer `0` | Integer `0` | CORRECTLY_HANDLED |
| U2 | Unified function | Missing or invalid artifact | `SystemExit(1)` | Return `1` | DEFECT_CONFIRMED |
| U3 | Unified function | Parser failure | `SystemExit(2)` | `SystemExit(2)` | CORRECTLY_HANDLED |
| U4 | Unified function | Argument forwarding and argv restoration | Original order preserved; argv restored | Preserve both | CORRECTLY_HANDLED |
| M1 | Unified module | Help | Process `0` | Process `0` | CORRECTLY_HANDLED |
| M2 | Unified module | Parser failure | Process `2` | Process `2` | CORRECTLY_HANDLED |
| M3 | Unified module | Runtime failure | Process `1`, clean output | Process `1`, clean output | CORRECTLY_HANDLED |
| M4 | Unified module | Validate/conversion success | Process `0` | Process `0` | CORRECTLY_HANDLED |
| G1 | Package guard | Guard calls `main()` directly | Missing `raise SystemExit(main())` | Required guard | DEFECT_CONFIRMED |
| R1 | Root wrapper | `backtest_artifact_cli.py` absent | Absent | No wrapper required | NOT_APPLICABLE |
| S1 | Console metadata | `twstock` entry point | Unified mapping preserved | Preserve mapping | CORRECTLY_HANDLED |

## 12. Direct callable results
Valid validate, inspect, and conversion calls return `None`. Handled missing-input, invalid-artifact, output, and converter failures raise `SystemExit(1)`.

## 13. Parser-owned results
Help raises `SystemExit(0)`. Missing and unknown commands raise `SystemExit(2)`.

## 14. Runtime-failure results
The direct callable defect is confirmed for `FileNotFoundError`, serialization errors, converter errors, and output-path failures. Error text is clean and has no traceback.

## 15. Package-module results
`python -m tw_stock_tool.cli.backtest_artifact_cli` returns process status `0` for help/success, `2` for parser failures, and `1` for handled runtime failures.

## 16. Unified-function results
The existing dispatcher maps child `None` to `0`, but child handled failures currently propagate `SystemExit(1)` instead of returning integer `1`.

## 17. Unified-module results
`python -m tw_stock_tool.cli.twstock_cli backtest-artifact ...` returns process status `0`, `2`, or `1` for success, parser, and runtime cases respectively.

## 18. Package-guard result
The current source contains `if __name__ == "__main__":` followed by `main()`, confirming the future-contract guard defect.

## 19. Root-wrapper result
The repository-root `backtest_artifact_cli.py` file is absent and classified `NOT_APPLICABLE`; no wrapper was added.

## 20. Console-script metadata result
`pyproject.toml` preserves `twstock = "tw_stock_tool.cli.twstock_cli:main"`.

## 21. `sys.argv` restoration result
Unified success and handled runtime failure restore the original `sys.argv` exactly; child arguments retain their original order.

## 22. Error-output and traceback result
Handled runtime failures print clean `error:` text to stderr with no traceback. Parser-owned errors retain argparse output and status `2`.

## 23. Filesystem-artifact result
All new artifact activity is inside temporary directories. Successful conversion creates exactly the requested JSON; failures create no output artifact and preserve existing output bytes.

## 24. Offline/no-live-request result
The new characterization is artifact-only and uses no yfinance, TWSE, TPEx, requests, strategy execution, backtests, brokers, orders, installed console scripts, or real user files.

## 25. Existing coverage preservation
No existing test or production file was modified. The required existing artifact, unified CLI, root-wrapper, serialization, and converter tests remain in the relevant regression set.

## 26. Expected-failure inventory
Exactly three expected failures express only future behavior: direct runtime failure should return `1`; unified-function runtime failure should return `1`; the package guard should use `raise SystemExit(main())`.

## 27. Confirmed defect inventory
Confirmed: `C11.1-DEFECT-01` direct `SystemExit(1)`; `C11.1-DEFECT-02` unified-function `SystemExit(1)` propagation; `C11.1-DEFECT-03` direct executable guard.

## 28. Candidate C11.2 scope
Future work may change only handled runtime paths to clean stderr plus `return 1`, preserve direct success `None`, preserve argparse `0/2`, pass unified `1`, and change the guard to `raise SystemExit(main())`, while preserving wording, formats, conversion, overwrite, routes, safety, APIs, dependencies, and wrappers.

## 29. Explicit production-fix restriction
C11.1 did not implement C11.2. No production source, serializer, converter, CLI route, configuration, dependency, or wrapper was changed.

## 30. Exact files changed
Only these two new files are approved: `tests/test_track_c11_1_backtest_artifact_cli_runtime_exit_behavior.py` and this report.

## 31. Targeted test results
`py -m unittest tests.test_track_c11_1_backtest_artifact_cli_runtime_exit_behavior`: 37 total, 34 ordinary passes, 3 expected failures, 0 skips, 0 failures, 0 errors.

## 32. Combined test results
The required combined suite ran 109 tests: 106 ordinary passes, 3 expected failures, 0 skips, 0 failures, 0 errors.

## 33. Full-suite results
Both `py -m unittest discover -s tests` and `python -m unittest discover -s tests` ran 1,683 tests: 1,680 ordinary passes, 3 expected failures, 0 skips, 0 failures, 0 errors.

## 34. `git diff --check` result
PASS — `git diff --check` completed after the report was finalized and found no whitespace errors.

## 35. UTF-8 BOM result
PASS — both added C11.1 files are UTF-8 without BOM.

## 36. Working-tree result
PASS — after the C11.1 commit, the working tree was clean. Only the two approved C11.1 files were included in the characterization commit.

## 37. Branch disposition
The C11.1 characterization commit was created and pushed successfully. The local and remote branches were aligned after the push.

Branch disposition: HOLD FOR REVIEW

The tests-and-documentation-only C11.1 branch must not be merged by itself. It may be stacked beneath the separately approved C11.2 production fix.

C11.2 was not started during C11.1.

## 38. Exact commands used
Baseline: `git fetch origin`; `git checkout main`; `git rev-parse HEAD`; `git rev-parse main`; `git rev-parse origin/main`; `git status --short`; `git checkout -b track-c11-1-backtest-artifact-cli-runtime-exit-characterization`.

Validation: `py -m unittest tests.test_track_c11_1_backtest_artifact_cli_runtime_exit_behavior`; `py -m unittest tests.test_track_c11_1_backtest_artifact_cli_runtime_exit_behavior tests.test_backtest_artifact_cli tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes`; `py -m unittest discover -s tests`; `python -m unittest discover -s tests`; `git diff --check`; `git status --short`; `git diff --name-only`; `git ls-files --others --exclude-standard`.

No merge, rebase, squash, amend, force-push, pull request, C11.2, C12, or later track was started.

Track C11.1 Characterization: PASS -- DECISION RECORDED
Branch disposition: HOLD FOR REVIEW
C11.2 was not started.
