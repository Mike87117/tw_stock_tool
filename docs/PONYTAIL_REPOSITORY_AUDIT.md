# Ponytail Repository Audit — Over-Engineering and Safe Reduction Opportunities

## 1. Executive summary

The required baseline was verified exactly at `dde23346d60bf67f38ecc01f6ec138643cfdbc52`, and this audit was performed from the dedicated branch `audit-ponytail-repository-overengineering`. The repository has three plausible reduction candidates, but none is low-risk enough to approve without characterization. The strongest candidate is a narrow private helper for repeated report-CLI argument registration. No cleanup was implemented.

The raw Ponytail estimate is `net: -350 lines, -0 deps possible.` That is not an approved reduction. The validated low-risk estimate is zero. The characterization-dependent estimate is 38 production lines and 52 test lines, kept separate and not approved for this audit.

## 2. Formal audit result

**Ponytail Repository Audit: PASS -- REPORT READY FOR REVIEW**

## 3. Repository baseline

Required baseline:

`dde23346d60bf67f38ecc01f6ec138643cfdbc52`

Before the audit, `HEAD`, `main`, and `origin/main` all resolved to that commit. The working tree was clean. The audit branch was created directly from that commit:

`audit-ponytail-repository-overengineering`

The ignored user-owned file `custom_md.md` was not inspected, modified, restored, staged, or cleaned. `git clean` was not run. No rebase, merge, or force-push was performed.

## 4. Ponytail availability and exact invocation

The Ponytail audit skill was available at `C:\Users\Mike\.codex\skills\ponytail-audit\SKILL.md` and was read before the audit. The requested invocation was:

`@ponytail-audit`

It was applied to the complete tracked repository represented by `git ls-files`, in audit-only mode. No implementation-oriented Ponytail command was used. Ponytail was not installed, upgraded, replaced, or reconfigured.

Raw finding count: 12.

## 5. LLM Wiki availability result

No LLM Wiki service or connector was available in the current session. This was non-blocking. No Wiki repair or reconfiguration was attempted. Repository source, tests, package metadata, README usage, and existing architecture records were treated as authoritative.

## 6. Audit boundaries

The audit covered tracked production code, root entry points, CLI routing, providers and fallbacks, cache boundaries, backtesting, strategies, reports, paper trading, risk controls, kill switches, GUI code, tests, documentation, and packaging.

The audit did not run live market services, network-dependent behavior, the complete test suite, formatting, code changes, patches, dependency changes, file deletion, or broad cleanup. Generated, cached, ignored, virtual-environment, output, and user-owned files were excluded from reduction estimates.

## 7. Protected compatibility and safety boundaries

The following were treated as protected unless complete current evidence proved otherwise:

- root-level compatibility wrappers and historical script/import paths;
- yfinance, TWSE, TPEx, TW/TWO symbol fallback, normalization, provider validation, and cache boundaries;
- `paper_trading`, risk controls, kill switches, guard adapters, validation, schemas, error handling, and nonzero process-status propagation;
- tests covering wrappers, smoke paths, CLI exit status, fallback behavior, schemas, safety, and historical regressions;
- explicit package exports and documented CLI registrations.

Thin code at these boundaries was not treated as unnecessary merely because it is repetitive.

## 8. Tracked-file and LOC inventory

Counting method: `git ls-files` supplied the file set. For each tracked file, text was decoded as UTF-8 with an optional BOM and counted with Python `splitlines()`; binary files were excluded from line totals. No counting script was added to the repository.

| Tracked group | Files | Lines |
|---|---:|---:|
| `src/tw_stock_tool` | 106 | 14,699 |
| Root-level Python entry points | 41 | 363 |
| `tests` | 104 | 25,789 |
| `docs` | 47 | 8,208 |
| Other tracked Python files | 1 | 15 |
| Configuration and packaging (`.github/workflows/python-tests.yml`, `pyproject.toml`, `requirements.txt`) | 3 | 68 |
| Other tracked text files (`.gitignore`, `AGENTS.md`, `CHANGELOG.md`, `README.md`, `stocks.txt`) | 5 | 2,426 |
| **Total tracked files/text lines** | **307** | **51,568** |

## 9. Raw Ponytail summary

Ponytail identified repeated CLI registration and test-environment setup as the most concrete reductions. It also flagged repeated serialization wrappers, concentrated data-loading/report/GUI responsibilities, duplicate dependency declarations, root wrappers, the alternate backtest path, historical documentation volume, and thin safety/status boundaries. Validation rejected or deferred the latter group where compatibility, schema, safety, or architecture evidence exists.

## 10. Finding-validation methodology

Each candidate was checked against imports, callers, package exports, CLI registrations, root wrappers, tests, README command examples, architecture records, compatibility inventories, schemas, provider fallbacks, cache behavior, safety boundaries, and exit-status tests. Evidence came from `git grep`, `rg`, `git ls-files`, source inspection, and existing tests. No candidate was accepted solely because it appeared repetitive or thin.

## 11. Full validated finding table

Line counts are current tracked lines for the named files or groups. An estimate of zero approved lines means no safe reduction is authorized from the evidence available in this audit; it does not claim the underlying architecture can never change.

| ID | Ponytail tag | Disposition | Candidate | Paths | Current structure | Usage evidence | Compatibility impact | Safety impact | Current tracked lines | Estimated removable lines | Dependency impact | Confidence | Required proof | Recommendation |
|---|---|---|---|---|---|---|---|---|---:|---:|---|---|---|---|
| PT-AUDIT-001 | `shrink` | `ACCEPT_NEEDS_CHARACTERIZATION` | Repeated backtest/strategy CLI argument registration | `src/tw_stock_tool/cli/backtest_report.py`; `src/tw_stock_tool/cli/parameter_sweep_report.py`; `src/tw_stock_tool/cli/walk_forward_report.py` | Each report CLI registers overlapping stock, strategy, period, output, refresh, and risk arguments locally; defaults and types are not identical. | README documents these commands; tests exercise parser behavior and report routes; unified CLI routes into these modules. | A shared helper could change help text, defaults, requiredness, flag aliases, tuple parsing, or Namespace shape. | Must preserve validation, output paths, report schemas, and nonzero status. | 476 | 24 | None | High | Characterize `--help`, defaults, required arguments, types, aliases, Namespace mapping, output flags, and failure statuses for all three entry points before and after a private helper. | Accept only as a small future characterization phase; do not change now. |
| PT-AUDIT-002 | `shrink` | `ACCEPT_NEEDS_CHARACTERIZATION` | Repeated unified CLI passthrough registration | `src/tw_stock_tool/cli/twstock_cli.py` | The dispatcher repeats `add_parser`, aliases/help metadata, and handler wiring for approximately 19 command routes. | `tests/test_twstock_cli.py` and wrapper exit-code tests cover routing; README and the public command inventory document supported forms. | A helper could alter aliases, help ordering/text, defaults, passthrough arguments, or handler return propagation. | Must preserve command dispatch and nonzero process statuses. | 194 | 14 | None | Medium | Snapshot route names, aliases, help output, handler arguments, and exit statuses for every registered route. | Keep characterization-dependent; no CLI framework rewrite. |
| PT-AUDIT-003 | `shrink` | `ACCEPT_NEEDS_CHARACTERIZATION` | Duplicated offline subprocess and test-environment setup | `tests/test_track_c4_1_scanner_cli_exit_behavior.py`; `tests/test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior.py`; `tests/test_track_c6_1_benchmark_cli_runtime_exit_behavior.py`; `tests/test_track_c7_1_clean_stocks_cli_runtime_exit_behavior.py`; `tests/test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior.py`; `tests/test_track_c9_1_smoke_check_cli_runtime_exit_behavior.py` | Several test modules repeat subprocess environment setup, `PYTHONPATH`, bytecode suppression, and offline `sitecustomize.py` preparation. | The modules test separate invocation boundaries, runtime behavior, and exit propagation; C8/C9 specifically protect offline subprocess behavior. | A shared test helper must not merge or delete invocation-boundary coverage. | Must preserve offline isolation and exact status assertions. | 2,213 | 52 | None | Medium | Characterize every subprocess command, environment variable, generated offline hook, cleanup path, and failure assertion before extracting one test-only helper. | Accept only as test-helper characterization; never reduce coverage. |
| PT-AUDIT-004 | `shrink` | `DEFER_ARCHITECTURAL` | Repeated serialization file-boundary wrappers | `src/tw_stock_tool/backtesting/serialization_files.py`; `src/tw_stock_tool/paper_trading/serialization_files.py` | Each module has small JSON file export/load wrappers, but each binds a different result type and schema. | Active imports occur in backtest artifact/export paths, paper-trading exports, package initializers, conversion code, tests, and docs. | Public names, result models, and JSON schemas differ; generic consolidation would be an API and schema decision. | Do not blur paper-trading and backtest safety or artifact boundaries. | 48 | 0 approved | None | High | Characterize schema identity, exports, error behavior, and every caller; require an explicit architecture decision. | Defer until a schema-preserving internal abstraction is approved. |
| PT-AUDIT-005 | `shrink` | `DEFER_ARCHITECTURAL` | Concentrated provider/cache/orchestration responsibility | `src/tw_stock_tool/data/data_loader.py` | One 427-line loader coordinates providers, fallback, normalization, cache, validation, and orchestration. | Broad production and test usage crosses CLI, GUI, analysis, and data-loading boundaries. | Splitting or replacing seams risks provider behavior, fallback order, normalization, and cache contracts. | High risk to yfinance/TWSE/TPEx/TW/TWO fallback and cache behavior. | 427 | 0 approved | None | High | Characterize each provider/fallback/cache contract with offline tests before any seam extraction. | Defer; no immediate reduction. |
| PT-AUDIT-006 | `shrink` | `DEFER_ARCHITECTURAL` | Report builder/render/export/file-writing responsibility concentration | `src/tw_stock_tool/reports/daily_report.py`; `src/tw_stock_tool/reports/backtest_report.py`; `src/tw_stock_tool/reports/parameter_sweep_report.py`; `src/tw_stock_tool/reports/walk_forward_report.py` | Report modules mix data construction, formatting, exporting, and filesystem concerns to varying degrees. | CLI, GUI, report tests, artifact exporters, and documented output schemas depend on these boundaries. | Moving or merging layers can change wording, ordering, file names, formats, or schemas. | Preserve report validation and output compatibility. | 1,254 | 0 approved | None | Medium | Characterize one report’s pure-data, rendering, and I/O contracts at a time. | Defer; a broad report refactor is outside a safe small phase. |
| PT-AUDIT-007 | `shrink` | `DEFER_ARCHITECTURAL` | Large GUI controller/service modules | `src/tw_stock_tool/gui/gui_app.py`; `src/tw_stock_tool/gui/app_services.py` | GUI application and service modules contain repeated widget/state-management and feature orchestration code. | GUI imports, callbacks, user workflows, and tests/docs rely on the current feature boundaries. | Source inspection cannot prove unchanged UI state, event ordering, or user-visible behavior. | Must preserve paper-trading and risk-control presentation/guarding in GUI flows. | 1,124 | 0 approved | None | Medium | Characterize UI workflows and state transitions before extracting any feature helper. | Defer until GUI work resumes. |
| PT-AUDIT-008 | `yagni` | `DEFER_ARCHITECTURAL` | Duplicate dependency declarations | `requirements.txt`; `pyproject.toml` | The same runtime dependencies are declared in both files. | CI installs `requirements.txt`; README directs users to it; `utils/doctor.py` checks it; tests protect both metadata paths. | Removing one source changes supported installation and diagnostic workflows. | Dependency resolution must remain equivalent for all supported workflows. | 38 | 0 approved | No dependency can be removed; source-of-truth change required | High | Characterize CI, README, doctor, metadata tests, and package installation before choosing a source of truth. | Defer as packaging policy, not a Ponytail cleanup now. |
| PT-AUDIT-009 | `delete` | `REJECT_COMPATIBILITY_BOUNDARY` | Root compatibility wrappers | Root-level Python entry points, including `main.py`, smoke checks, scanners, report CLIs, and compatibility imports | Thin wrappers forward historical script execution and import paths into `src/tw_stock_tool`. | README gives direct `python <wrapper>.py` examples; the wrapper inventory lists 41 compatibility-only rows; tests protect wrapper imports, routing, and exit codes. | Deletion would break documented historical invocation or imports; no complete deprecation path exists. | Wrapper exit propagation and safety guards are tested boundaries. | 363 | 0 | None | High | No deletion proof exists; a future versioned deprecation plan would be required. | Reject immediate deletion. |
| PT-AUDIT-011 | `shrink` | `DEFER_ARCHITECTURAL` | Historical README and phase-documentation volume | `README.md`; selected historical files under `docs/` | README is 2,054 lines and the repository retains historical phase/audit records. | README contains current command examples and compatibility notes; historical documents record prior architecture decisions. | Removing or restructuring history can obscure supported workflows or erase decision context. | No production safety impact, but documentation correctness must be preserved. | 10,262 | 0 approved | None | Medium | Perform a documentation-only navigation review with link and command validation. | Defer as documentation maintenance; do not count it as production reduction. |
| PT-AUDIT-012 | `yagni` | `REJECT_TEST_SAFETY` | Thin safety, validation, schema, and status-propagation boundaries | `src/tw_stock_tool/paper_trading/`; `src/tw_stock_tool/risk/`; `src/tw_stock_tool/kill_switch/`; guard/validation modules; related tests | Some boundaries are small wrappers or adapters around risk, kill-switch, validation, schemas, and process statuses. | Imports, package exports, tests, CLI routes, and historical regression coverage actively exercise them. | Public imports, schemas, output wording, and nonzero statuses are compatibility contracts. | Removing or merging them could bypass paper-trading guards, risk controls, kill switches, validation, or failure propagation. | Not aggregated | 0 | None | High | No reduction proof is acceptable without safety-specific characterization and approval. | Reject deletion or consolidation. |

## 12. Accepted low-risk findings

None. A zero low-risk estimate is intentional: the audit did not authorize production edits, and the concrete candidates still require behavioral characterization.

## 13. Findings requiring characterization

Three findings are accepted only as future characterization work: PT-AUDIT-001 and PT-AUDIT-002 in production CLI code, and PT-AUDIT-003 in test helpers. Their separate estimates are 24, 14, and 52 lines respectively. These are not approved changes and do not reduce current production/test totals.

## 14. Deferred architecture candidates

PT-AUDIT-004 through PT-AUDIT-008 and PT-AUDIT-011 are deferred. They involve schema boundaries, provider/cache behavior, report architecture, GUI behavior, packaging policy, alternate backtesting semantics, or documentation history. No removable-line estimate is approved for them.

## 15. Rejected Ponytail findings

PT-AUDIT-009 is rejected because root wrappers are active compatibility boundaries. PT-AUDIT-012 is rejected because thin safety, validation, schema, and status boundaries are active safety or compatibility contracts. Neither supports a safe deletion estimate.

## 16. Production-code reduction estimate

- Validated low-risk: **0 lines**.
- Characterization-dependent: **38 lines** (PT-AUDIT-001: 24; PT-AUDIT-002: 14).
- Deferred or rejected: **0 approved lines**.

The characterization-dependent figure is a conservative proposal for a bounded private-helper phase, not permission to implement it.

## 17. Root-wrapper reduction estimate

- Validated low-risk: **0 lines**.
- Characterization-dependent: **0 lines**.
- Deferred or rejected: **0 approved lines**.

The 363 current wrapper lines are excluded from reduction estimates because their compatibility role is documented and tested.

## 18. Test-code reduction estimate

- Validated low-risk: **0 lines**.
- Characterization-dependent: **52 lines** (PT-AUDIT-003).
- Deferred or rejected: **0 approved lines**.

This estimate concerns only shared setup. Invocation-boundary coverage, smoke coverage, exit-status assertions, and fallback/safety tests must remain.

## 19. Documentation reduction estimate

- Validated low-risk: **0 lines**.
- Characterization-dependent: **0 lines**.
- Deferred or rejected: **0 approved lines**.

Historical reports and README navigation are documentation concerns and are not production-code reduction.

## 20. Dependency reduction estimate

- Validated low-risk: **0 dependencies**.
- Characterization-dependent: **0 dependencies**.
- Deferred or rejected: **0 dependencies**.

The duplicate declaration finding does not identify a removable dependency. It identifies a future source-of-truth policy decision involving CI, README, doctor checks, and metadata tests.

## 21. Raw versus validated estimate comparison

| Estimate | Production | Root wrappers | Tests | Documentation | Dependencies |
|---|---:|---:|---:|---:|---:|
| Raw Ponytail ending | Not separated; `net: -350 lines` | Included in raw candidate scan | Included in raw candidate scan | Included in raw candidate scan | `-0` |
| Validated low-risk | 0 | 0 | 0 | 0 | 0 |
| Characterization-dependent | 38 | 0 | 52 | 0 | 0 |

The raw total is neither a safe estimate nor a commitment. It includes candidates rejected or deferred after repository validation and therefore must not be combined with the validated figures.

## 22. False-positive analysis

The largest false positives were root wrappers. Both look thin or duplicative in isolation, but README examples, import paths, dedicated tests, compatibility inventory, and architecture decisions establish active or retained contracts. Similar serialization functions have different result types and schemas. Provider/cache code is a boundary, not merely a large function. Safety adapters, validation, and status propagation are deliberately small. Duplicate requirements declarations are operationally active, so they are not a dependency-removal opportunity.

## 23. Highest-value safe opportunity

PT-AUDIT-001 has the best risk-adjusted value: it is local to three report CLI parsers, already identified as a future small refactor in the architecture review, has no dependency impact, and has a bounded projected reduction. Its risk is still material because help text, defaults, types, requiredness, Namespace construction, output behavior, and exit statuses are public or tested behavior.

## 24. Exactly one recommended next production phase

Recommend one future phase: characterize and, only if characterization proves equivalence, extract a single private argument-registration helper across `src/tw_stock_tool/cli/backtest_report.py`, `src/tw_stock_tool/cli/parameter_sweep_report.py`, and `src/tw_stock_tool/cli/walk_forward_report.py`.

The phase must first capture `--help`, defaults, required arguments, aliases, tuple/float parsing, Namespace mapping, output flags, report output, and nonzero failure behavior for all three entry points. It must preserve wrappers, public imports, schemas, providers, caches, safety boundaries, and tests. It must stop if the helper is not a net reduction. Conservative estimate: **20–30 production lines**, no dependency change. This phase is recommended for later implementation; it was not begun by this audit.

## 25. Deferred future phases

The following remain deferred and are not additional next-phase recommendations: characterization of the unified CLI registration helper; extraction of a test-only subprocess environment helper; schema-preserving serialization utility design; provider/cache seam work; one-report-at-a-time boundary work; GUI characterization; dependency source-of-truth policy; and documentation navigation maintenance.

## 26. Explicitly protected files and modules

Protected examples include:

- all root-level compatibility wrappers;
- `src/tw_stock_tool/data/data_loader.py`;
- `src/tw_stock_tool/paper_trading/`;
- `src/tw_stock_tool/risk/`;
- `src/tw_stock_tool/kill_switch/`;
- guard and validation modules;
- serialization and report schema boundaries;
- `src/tw_stock_tool/cli/twstock_cli.py` route registrations;
- tests for wrappers, CLI statuses, fallback behavior, schemas, smoke paths, and safety;
- `README.md` and historical architecture/audit records during this audit.

## 27. Exact commands used

Read-only baseline and inventory commands:

~~~
git fetch origin
git checkout main
git pull --ff-only origin main
git rev-parse HEAD
git rev-parse main
git rev-parse origin/main
git status --short
git switch -c audit-ponytail-repository-overengineering
git ls-files
git grep -n ...
rg -n ...
~~~

The line inventory used an inline Python UTF-8 `splitlines()` calculation over `git ls-files`; no script was saved. Candidate file counts were cross-checked with read-only PowerShell `Get-Content ... | Measure-Object -Line`. The audit invocation was:

~~~
@ponytail-audit
~~~

Final validation commands:

~~~
git diff --check
git status --short
git diff --name-only
git ls-files --others --exclude-standard
~~~

`git clean` was not run. No live external request was made.

## 28. Exact files changed

Only this new file is permitted and changed:

`docs/PONYTAIL_REPOSITORY_AUDIT.md`

No existing file was modified.

## 29. git diff --check result

PASS — no whitespace errors in the audit report.

## 30. UTF-8 BOM result

PASS — `docs/PONYTAIL_REPOSITORY_AUDIT.md` is UTF-8 without a BOM.

## 31. No-production-change confirmation

PASS — no production code, tests, README, existing documentation, configuration, dependency file, lock file, CI file, package metadata, ignored file, generated artifact, or user-owned file was modified. The complete test suite was not run because this was a documentation-only audit and the task explicitly restricted validation to diff/status checks.

## 32. Branch disposition

One documentation-only commit is to be created on `audit-ponytail-repository-overengineering` and pushed without merging. The branch is held for review. No cleanup finding was implemented.

## Appendix A — Raw Ponytail Audit Output

~~~text
shrink repeated backtest/strategy CLI argument registration. Share one internal argument-builder helper across report CLIs. [src/tw_stock_tool/cli/backtest_report.py, src/tw_stock_tool/cli/parameter_sweep_report.py, src/tw_stock_tool/cli/walk_forward_report.py]
shrink repeated unified CLI passthrough registration. Add one internal registration helper. [src/tw_stock_tool/cli/twstock_cli.py]
shrink duplicated offline subprocess/test-environment setup. Share one test helper without removing boundary coverage. [tests/test_track_c4_1_scanner_cli_exit_behavior.py, tests/test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior.py, tests/test_track_c6_1_benchmark_cli_runtime_exit_behavior.py, tests/test_track_c7_1_clean_stocks_cli_runtime_exit_behavior.py, tests/test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior.py, tests/test_track_c9_1_smoke_check_cli_runtime_exit_behavior.py]
shrink repeated serialization file-boundary wrappers. Introduce one schema-parameterized internal file helper. [src/tw_stock_tool/backtesting/serialization_files.py, src/tw_stock_tool/paper_trading/serialization_files.py]
shrink provider/cache/orchestration responsibility concentration. Extract provider and cache seams. [src/tw_stock_tool/data/data_loader.py]
shrink report builder/render/write responsibility concentration. Split one report at a time. [src/tw_stock_tool/reports/backtest_report.py, src/tw_stock_tool/reports/parameter_sweep_report.py, src/tw_stock_tool/reports/walk_forward_report.py, src/tw_stock_tool/reports/daily_report.py]
shrink large GUI controller/service modules. Split feature responsibilities. [src/tw_stock_tool/gui/gui_app.py, src/tw_stock_tool/gui/app_services.py]
yagni duplicate dependency declarations. Choose one dependency source of truth. [requirements.txt, pyproject.toml]
delete root compatibility wrappers. Remove redirect files. [root-level Python wrappers]
shrink historical README and phase-documentation volume. Reorganize navigation and archive history. [README.md, docs/]
yagni thin safety, validation, schema, and status-propagation boundaries. Merge boundary layers. [src/tw_stock_tool/paper_trading/, src/tw_stock_tool/risk/, src/tw_stock_tool/kill_switch/, tests/]
net: -350 lines, -0 deps possible.
~~~

Ponytail Repository Audit: PASS -- REPORT READY FOR REVIEW
Branch disposition: HOLD
No cleanup findings were implemented.
