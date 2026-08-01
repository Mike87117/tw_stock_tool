# Phase 55.3：Artifact Hub 與 Research Workspace Planning

## 1. 文件目的

本文件定義 Phase 55.3 的產品目標、範圍、核心契約、相容性策略、子階段、驗收條件與明確非目標。

本文件是 Phase 55.3A 的 planning baseline。它不直接授權 production implementation；每一個 production 子階段仍需建立獨立範圍、測試計畫、Reviewer Gate、CI Gate 與 Merge Gate。

## 2. Baseline

- Repository：`Mike87117/tw_stock_tool`
- Baseline branch：`main`
- Baseline commit：`09156976def5a31f32e3b719214bc70b4639752e`
- Baseline date：2026-07-31
- Package version：`0.4.0`
- Previous phase：Phase 55.2 Research Run 與 Run Manifest
- Current product boundary：歷史資料研究、策略驗證、離線模擬交易與研究 artifacts
- Explicit non-goals：券商串接、真實下單、自動交易、投資建議與獲利保證

## 3. Product problem

Phase 55.2 已讓 Scan、Daily Report 與 Backtest 產生包含 Run ID、resolved configuration、data-source provenance、status 與 artifact references 的 Run Manifest。

但目前使用者仍面臨以下問題：

1. 不同 workflow 的輸出散落在使用者指定目錄。
2. 預設 manifest 與 report 檔名可能在重複執行時被覆寫。
3. 有 Run ID，但沒有可瀏覽的 Run History。
4. 無法從一個統一入口列出、尋找或檢查歷史 runs。
5. Artifact path 尚未定義可搬移的 Workspace-relative contract。
6. 缺失或損壞的 manifest／artifact 尚無統一 health reporting。
7. GUI 與後續 experiment comparison 沒有穩定的 storage foundation。

產品問題可簡化為：

> 已有可重現的單次 Research Run metadata，但尚未有持久、可搬移、可檢查的 Research Workspace。

## 4. Phase goal

Phase 55.3 的目標是建立一個本機、離線、檔案系統為基礎的 Research Workspace，使每一次受支援的 Research Run：

- 擁有唯一且不覆寫既有內容的 run directory。
- 將 manifest 與 Workspace-managed artifacts 放在同一個可搬移邊界。
- 可被 deterministic catalog 列出。
- 可依 Run ID inspect。
- 可報告 manifest／artifact health findings。
- 不改寫既有 domain artifact schema。
- 不使用 network 或重新執行研究即可進行 list／inspect／validate。

## 5. Product principles

### 5.1 Filesystem is the first source of truth

Phase 55.3 第一版不建立 SQLite、server、daemon 或 background index。

Workspace catalog 由 canonical filesystem layout 與 manifest strict read-back 建立。任何衍生 cache 都不得成為 authoritative source。

### 5.2 Append-only run history

Workspace-managed run directory 建立後：

- 不得因後續相同 command 而被默默覆寫。
- Collision 必須 fail closed。
- 使用者明確要求刪除或清理前，不自動移除舊 run。
- Phase 55.3 不提供自動 retention policy。

### 5.3 Existing artifact schemas remain authoritative

Run Manifest 是 run-level metadata。Daily、Backtest、Paper Trading、Portfolio 或其他 artifact 的既有 schema 仍由各自 owner module 管理。

Artifact Hub 不得在 Phase 55.3 中把所有 artifact 重寫成新統一 schema。

### 5.4 Offline inspection

以下操作必須是純離線操作：

- List runs
- Inspect run
- Validate manifest
- Check artifact existence
- Identify artifact type／media type／schema version

這些操作不得：

- 下載市場資料。
- 執行 strategy。
- 執行 backtest。
- 執行 simulated trading。
- 修改研究結果。

### 5.5 Backward compatibility first

Workspace mode 第一版採 opt-in。

未選擇 Workspace mode 時，既有 `--output-dir`、`--manifest-path`、artifact output options 與 process exit behavior 必須保持不變。

## 6. Workspace layout contract

### 6.1 Proposed layout

```text
workspace/
└── runs/
    └── 2026/
        └── 07/
            └── 20260731T151900Z_backtest_8f31a40c/
                ├── manifest.json
                ├── artifacts/
                │   ├── backtest-report.md
                │   └── backtest-report.xlsx
                └── logs/
                    └── errors.log
```

### 6.2 Run directory name

Proposed format：

```text
<UTC basic timestamp>_<workflow-slug>_<run-id-prefix>
```

Rules：

- Timestamp uses UTC `YYYYMMDDTHHMMSSZ`.
- Run ID prefix uses the first eight hexadecimal characters of the canonical UUID.
- The full UUID remains authoritative in `manifest.json`.
- Symbols and strategy parameters are not embedded in the directory name.
- Directory names must remain safe for Windows、macOS and Linux filesystems.
- The filesystem component is a separately validated `workflow-slug`; it must not directly embed an arbitrary `RunConfig.workflow` value.
- Phase 55.3B must provide an exact slug validator or registered mapping. Initial integration values are expected to include `scan`、`daily` and `backtest`.

`RunConfig.workflow` currently guarantees a clean nonblank string, but does not itself guarantee lowercase or filesystem-safe characters. Workspace safety therefore belongs to the Workspace boundary, not the Run Manifest schema.

### 6.3 Canonical run files

Each completed managed run directory must contain：

```text
manifest.json
```

Optional managed directories：

```text
artifacts/
logs/
tables/
```

`manifest.json` is the only mandatory completed-run file. A canonical-looking directory without it is an incomplete or damaged run and must be reported through catalog health findings rather than silently treated as valid.

### 6.4 Directory creation

Run-directory creation must：

1. Validate Workspace root.
2. Validate the workflow slug and Run ID.
3. Derive the target path from run metadata.
4. Create parent year／month directories if needed.
5. Create the run directory using collision-rejecting semantics.
6. Never reuse an existing run directory, including an empty one.
7. Return a typed run-directory handle.

If a collision occurs, the operation must fail with a controlled Workspace error. It must not add random retries that obscure the original Run ID.

## 7. Path contract

### 7.1 Workspace-managed artifacts

Manifest artifact paths for Workspace-managed output must be stored relative to the run directory and use POSIX `/` separators.

Example：

```json
{
  "artifact_type": "backtest_report_markdown",
  "path": "artifacts/backtest-report.md",
  "media_type": "text/markdown",
  "schema_version": null
}
```

Benefits：

- Workspace can be moved or copied.
- Paths are independent of the original machine root.
- Windows absolute-path details are not persisted into portable metadata.

The existing `ArtifactReference` model remains broader for legacy mode and currently only enforces a clean POSIX-style string. Phase 55.3B must add a stricter Workspace path profile without changing Run Manifest schema version `1.0`.

### 7.2 External artifacts

First-version decision：

> Workspace mode owns all managed output and rejects artifact destinations outside the allocated run directory.

Therefore：

- Conflicting explicit output paths are rejected in Workspace mode.
- Legacy mode continues to support its existing explicit path behavior.
- A future external-reference model requires a separate schema and compatibility decision.
- A plain `ArtifactReference.path` must not ambiguously represent both portable relative paths and external absolute paths within Workspace mode.

### 7.3 Path safety

Workspace path resolution must reject：

- Absolute paths where a relative artifact path is required.
- `..` traversal outside the run directory.
- NUL characters.
- Empty or ambiguous path segments.
- Paths resolving outside the run directory.
- Symlink or reparse-point components in managed run and artifact paths in the first version.

The first implementation should reject symlink-based managed paths rather than attempt partial support. Any later relaxation requires separate cross-platform characterization.

## 8. Manifest ownership and write ordering

### 8.1 Manifest is the run index record

`manifest.json` is the authoritative metadata entry for one run.

The Workspace catalog must not infer successful completion only from directory naming or artifact presence.

### 8.2 Proposed write sequence

For successful runs：

1. Complete request validation and assign Run ID.
2. Create the unique run directory.
3. Execute workflow and write artifacts inside managed paths.
4. Validate generated artifact references through the Workspace path profile.
5. Write final `manifest.json` atomically.
6. Read back and strictly validate the manifest.
7. Return the Research Run result.

For failed runs：

1. Create the run directory after request validation and Run ID assignment.
2. Record controlled failure details.
3. Write a failure manifest atomically when possible.
4. Preserve available managed logs without claiming successful artifacts.

Request validation failures that occur before Run ID creation do not require a Workspace directory.

### 8.3 Atomicity

Phase 55.3B should provide a shared filesystem writer using：

- UTF-8.
- `\n` newlines for text artifacts where the existing contract allows it.
- A temporary sibling file.
- Flush／close before replace.
- Atomic replace where supported.
- Cleanup of temporary files after controlled failure where safely possible.

Atomic replacement applies to a file inside a newly created run directory. It must not enable replacing an existing run directory.

## 9. Workspace catalog contract

### 9.1 Catalog source

The catalog scans canonical run directories at：

```text
workspace/runs/<year>/<month>/<run-directory>/
```

For each canonical-looking run directory, it checks：

```text
manifest.json
```

This distinction is required so the catalog can report `missing_manifest`. The first version must not recursively scan arbitrary files or directories outside the canonical year／month／run shape.

Canonical-looking run directories are identified by an exact parser for the approved directory-name format. Directories that do not match the format are ignored rather than interpreted as runs.

### 9.2 Catalog entry

Proposed typed summary：

```text
WorkspaceRunEntry
- run_id
- created_at
- workflow
- status
- canonical_symbols
- universe
- tool_version
- artifact_count
- run_directory
- manifest_path
- health
- findings
```

This is a run-level entry. It must not be named `ArtifactCatalogEntry`, because one entry represents one Research Run and may contain multiple artifacts.

### 9.3 Health summary and findings

A run may have more than one problem. The first version should separate：

```text
RunHealth
- valid
- warning
- invalid
```

from deterministic finding codes：

```text
invalid_manifest
missing_manifest
missing_artifact
unsafe_path
unsupported_schema
unregistered_artifact_type
```

Rules：

- `valid` has no findings.
- `warning` may include non-fatal findings such as an unregistered artifact type.
- `invalid` includes findings that prevent trusted inspection, such as invalid or missing manifest and unsafe path.
- Findings are deduplicated and sorted by an exact priority defined in Phase 55.3B.

### 9.4 Invalid entries

One malformed run must not prevent listing other runs.

Catalog scanning must：

- Return valid entries normally.
- Return controlled invalid entries where enough path metadata can be recovered safely.
- Never execute code or import arbitrary artifact content.
- Never trust directory timestamp or workflow text without parsing.
- Sort deterministically.

### 9.5 Ordering

Default ordering：

1. Valid and warning entries with a readable manifest, ordered by `created_at` descending.
2. `run_id` ascending as tie-breaker.
3. Invalid entries after readable entries, ordered by normalized run-directory path.

Filesystem modification time must not be used as the primary run timestamp.

## 10. Run lookup contract

First-version `run inspect` lookup requires the full canonical UUID.

Rules：

- Prefix lookup is deferred.
- Duplicate Run IDs across different directories are treated as an invalid Workspace condition.
- A duplicate must not be resolved by newest timestamp or path order.
- Lookup remains offline and read-only.

## 11. CLI compatibility direction

The exact parser design belongs to Phase 55.3C and Phase 55.3D, but the product direction is：

```bash
twstock scan ... --workspace workspace
twstock daily ... --workspace workspace
twstock backtest-report ... --workspace workspace

twstock run list --workspace workspace
twstock run inspect <full-run-id> --workspace workspace
```

### 11.1 Workspace execution mode

When `--workspace` is provided：

- The Application Service or a dedicated run-lifecycle service owns the run directory.
- Workflow outputs are written below that directory.
- Manifest path is canonical `manifest.json`.
- Conflicting explicit artifact paths are rejected.
- Workspace-relative artifact references are returned.

The CLI must not silently split one run across unrelated directories.

### 11.2 Legacy execution mode

When `--workspace` is omitted：

- Current output behavior remains unchanged.
- Current default artifact filenames remain unchanged.
- Current exit behavior remains unchanged.
- Current `--manifest-path` behavior remains unchanged.

### 11.3 Read-only commands

`run list` and `run inspect` must operate without network and without domain execution.

Phase 55.3 does not add `run reproduce`.

## 12. Proposed package boundary

Suggested Phase 55.3B structure：

```text
src/tw_stock_tool/
└── artifacts/
    ├── __init__.py
    ├── errors.py
    ├── workspace.py
    └── catalog.py
```

Responsibilities：

### `artifacts.workspace`

- Validate Workspace root.
- Validate workflow slugs and run-directory names.
- Create unique run directories.
- Resolve safe managed paths.
- Write／read canonical manifest files.
- Provide typed run-directory handles.

### `artifacts.catalog`

- Scan canonical run directories.
- Strictly load manifests.
- Build `WorkspaceRunEntry` values.
- Detect missing manifests、missing artifacts and unsafe paths.
- Sort deterministically.
- Perform exact full-UUID lookup.

### `artifacts.errors`

- Define controlled Workspace／Catalog errors.
- Preserve useful path and operation context.
- Avoid leaking implementation tracebacks through normal CLI output.

An artifact-type registry is not required for Phase 55.3B storage foundation. It may be added in a later subphase when artifact-type validation and user-facing inspection behavior are separately characterized.

Existing `research_run.models` and `research_run.serialization` remain the owners of Run Manifest schema and strict JSON read-back.

## 13. Phase breakdown

## Phase 55.3A：Contract Planning

### Scope

- Freeze product problem and non-goals.
- Define Workspace layout.
- Define path ownership and collision rules.
- Define catalog source of truth and ordering.
- Define read-only operation boundary.
- Define opt-in compatibility strategy.
- Define implementation sub-phases and acceptance criteria.

### Production code

None.

### Exit criteria

- Planning document merged.
- Phase 55.2 closeout merged.
- Independent document review passes.
- CI and package smoke pass.
- Phase 55.3B scope is locked without CLI or workflow migration.

## Phase 55.3B：Workspace Storage Foundation

### Scope

- Add Workspace models and controlled errors.
- Create unique run directories.
- Add safe relative-path resolution.
- Add canonical manifest persistence and strict read-back.
- Add filesystem catalog scanning.
- Add run health and artifact existence findings.
- Add exact full-UUID lookup.

### Out of scope

- Existing research workflow migration.
- CLI parser changes.
- GUI changes.
- Database index.
- Artifact-type registry unless separately authorized.

### Required tests

- Cross-platform path normalization.
- Workflow-slug validation.
- Collision rejection.
- Traversal rejection.
- Absolute-path rejection.
- Symlink／reparse-point rejection where testable.
- Invalid manifest isolation.
- Missing manifest detection.
- Missing artifact detection.
- Duplicate Run ID detection.
- Deterministic findings and ordering.
- Workspace relocation.
- Atomic manifest write failure behavior.

## Phase 55.3C：Scan／Daily／Backtest Integration

### Scope

- Add opt-in Workspace execution to typed requests or an application-level Workspace policy.
- Integrate Scan、Daily and Backtest only.
- Generate Workspace-relative artifact references.
- Reject conflicting external artifact paths in Workspace mode.
- Preserve legacy mode.

### Required tests

- Two identical runs create two distinct directories.
- Existing run is never overwritten.
- Manifest references resolve after moving the entire Workspace.
- Legacy mode outputs remain unchanged.
- Failure runs preserve a valid failure manifest when possible.
- CLI exit behavior remains unchanged.

## Phase 55.3D：Read-only CLI

### Scope

- `run list`
- `run inspect`
- Human-readable status and findings output
- Optional machine-readable JSON only if separately locked by contract

### Required tests

- No network calls.
- No strategy or backtest execution.
- Invalid run isolation.
- Full Run ID exact lookup.
- Duplicate Run ID controlled failure.
- Deterministic output ordering.
- Controlled not-found errors.

## Phase 55.3E：Documentation and Migration Audit

### Scope

- User guide for Workspace mode.
- Artifact guide updates.
- Legacy mode compatibility notes.
- Runtime／documentation consistency audit.
- Final Phase closeout.

## 14. Acceptance criteria

Phase 55.3 is complete only when：

1. Two same-configuration Workspace runs never overwrite each other.
2. Every completed managed run has one canonical `manifest.json`.
3. Canonical-looking incomplete directories produce controlled findings.
4. Every managed artifact reference resolves safely below the run directory.
5. A Workspace can be moved and still be listed／inspected.
6. Catalog ordering and finding ordering are deterministic.
7. One damaged run does not break catalog listing.
8. Missing artifacts produce controlled findings.
9. Unsupported manifest schema produces a controlled finding.
10. Duplicate Run IDs produce a controlled invalid condition.
11. List／inspect operate without network or domain execution.
12. Existing artifact schemas remain unchanged unless a separate schema Phase authorizes change.
13. Legacy CLI mode remains behavior-compatible.
14. Python 3.11／3.12 full suite and package smoke pass.
15. Documentation matches exact runtime behavior.

## 15. Explicit non-goals

Phase 55.3 must not include：

- GUI 0.2.
- Run reproduction.
- Experiment comparison.
- Parameter Sweep／Walk Forward migration unless separately authorized.
- ML／AI workflow migration.
- Paper Trading／Portfolio migration.
- Broker API or live trading.
- Cloud sync.
- Multi-user access control.
- SQLite／PostgreSQL catalog.
- Background daemon.
- Automatic retention or cleanup.
- Artifact schema unification.
- Full package reorganization.
- Removal of remaining private Data Loader compatibility seams.

## 16. Locked first-version decisions

The following decisions are locked for the first implementation：

- Filesystem scan is the source of truth.
- Catalog scans canonical run directories, not only manifest files.
- Canonical-looking directories without manifest are reported.
- Workspace mode rejects external artifact destinations.
- Managed paths reject symlink／reparse-point components.
- Workspace path validation is stricter than the legacy `ArtifactReference` model.
- Unknown artifact types do not block storage foundation; registry behavior is deferred.
- Run directories are created after request validation and Run ID assignment.
- `run inspect` requires the full canonical UUID.
- Duplicate Run IDs fail closed.

## 17. Dependency graph

```text
Phase 55.2 Closeout
        ↓
Phase 55.3A Contract Planning
        ↓
Phase 55.3B Workspace Storage Foundation
        ↓
Phase 55.3C Scan / Daily / Backtest Integration
        ↓
Phase 55.3D Read-only CLI
        ↓
Phase 55.3E Documentation and Migration Audit
        ↓
Phase 55.4 Daily Report Decomposition or Phase 55.5 GUI Workspace
```

Phase 55.4 and Phase 55.5 must not assume Workspace APIs before Phase 55.3B–D contracts are merged and stable.

## 18. Product decision

The next production-code task after this planning Phase is：

> **Phase 55.3D — Add offline read-only twstock run list and twstock run inspect on the stable Workspace catalog.**

This ordering separates storage correctness from CLI and workflow integration risk.

## 19. Phase 55.3C implementation record

Phase 55.3B storage and catalog APIs are now used by the application-owned Workspace lifecycle for Scan、Daily Report and Backtest.

Implemented contract details:

- --workspace PATH is opt-in; legacy mode keeps its existing output and exit behavior.
- Request preflight and output-option conflict checks happen before Workspace allocation.
- Every managed run allocates a fresh canonical run directory through Workspace.allocate_run_directory.
- Workflow artifacts are written below <run-directory>/artifacts/; the canonical manifest is <run-directory>/manifest.json.
- Provisional workflow manifests are converted through the existing strict manifest models and published through Workspace.write_manifest／read_manifest.
- Published artifact references are relative POSIX paths and are checked with the Phase 55.3B resolver before publication.
- Controlled workflow failures publish failure or partial manifests when the provisional manifest is available; a publication failure preserves the original workflow error as its cause.
- twstock scan --help, twstock daily --help and twstock backtest-report --help expose the same --workspace option.

Known limitations:

- Phase 55.3D read-only twstock run list／twstock run inspect commands are not included.
- The existing standalone Parameter Sweep、Walk Forward、Strategy Compare、AI／ML and simulated-trading workflows remain outside this integration.
- Local Windows symlink privilege limitations remain covered by the Phase 55.3B path-safety tests and CI evidence.
