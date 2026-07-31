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
6. 缺失或損壞的 manifest／artifact 尚無統一 health state。
7. GUI 與後續 experiment comparison 沒有穩定的 storage foundation。

產品問題可簡化為：

> 已有可重現的單次 Research Run metadata，但尚未有持久、可搬移、可檢查的 Research Workspace。

## 4. Phase goal

Phase 55.3 的目標是建立一個本機、離線、檔案系統為基礎的 Research Workspace，使每一次受支援的 Research Run：

- 擁有唯一且不覆寫既有內容的 run directory。
- 將 manifest 與 Workspace-managed artifacts 放在同一個可搬移邊界。
- 可被 deterministic catalog 列出。
- 可依 Run ID inspect。
- 可報告 manifest／artifact health。
- 不改寫既有 domain artifact schema。
- 不使用 network 或重新執行研究即可進行 list／inspect／validate。

## 5. Product principles

### 5.1 Filesystem is the first source of truth

Phase 55.3 第一版不建立 SQLite、server、daemon 或 background index。

Workspace catalog 由 filesystem scan 與 manifest strict read-back 建立。任何衍生 cache 都不得成為 authoritative source。

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
- Identify result type／media type／schema version

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
<UTC basic timestamp>_<workflow>_<run-id-prefix>
```

Rules：

- Timestamp uses UTC `YYYYMMDDTHHMMSSZ`.
- Workflow is a clean lowercase identifier already accepted by `RunConfig.workflow`.
- Run ID prefix uses the first eight hexadecimal characters of the canonical UUID.
- The full UUID remains authoritative in `manifest.json`.
- Symbols and strategy parameters are not embedded in the directory name.
- Directory names must remain safe for Windows, macOS and Linux filesystems.

### 6.3 Canonical run files

Each managed run directory must contain：

```text
manifest.json
```

Optional managed directories：

```text
artifacts/
logs/
tables/
```

Only `manifest.json` is mandatory. The existence of optional directories depends on generated output.

### 6.4 Directory creation

Run-directory creation must：

1. Validate Workspace root.
2. Derive the target path from the run metadata.
3. Create parent year／month directories if needed.
4. Create the run directory using collision-rejecting semantics.
5. Never reuse a non-empty existing run directory.
6. Return a typed run-directory handle.

If a collision occurs, the operation must fail with a controlled Workspace error. It must not add random retries that obscure the original Run ID.

## 7. Path contract

### 7.1 Workspace-managed artifacts

Manifest artifact paths for Workspace-managed output should be stored relative to the run directory and use POSIX `/` separators.

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

### 7.2 External artifacts

Phase 55.3B must make an explicit implementation decision between these two contracts：

1. Reject external artifact destinations in Workspace mode; or
2. Represent external paths using an explicit external-reference model.

The first implementation should prefer **Workspace-owned output only** unless compatibility evidence proves that external output is necessary.

Do not overload a plain relative `ArtifactReference.path` with ambiguous absolute-path meaning.

### 7.3 Path safety

Workspace path resolution must reject：

- Absolute paths where a relative artifact path is required.
- `..` traversal outside the run directory.
- NUL characters.
- Empty path segments that change interpretation.
- Symlink traversal that escapes the Workspace boundary, if symlink handling is supported.

The exact symlink policy must be locked in Phase 55.3B before production code.

## 8. Manifest ownership and write ordering

### 8.1 Manifest is the run index record

`manifest.json` is the authoritative metadata entry for one run.

The Workspace catalog must not infer successful completion only from directory naming or artifact presence.

### 8.2 Proposed write sequence

For successful runs：

1. Create unique run directory.
2. Execute workflow and write artifacts inside temporary or final managed paths.
3. Validate generated artifact references.
4. Write final `manifest.json` atomically.
5. Read back and validate the manifest.
6. Return the Research Run result.

For failed runs：

1. Create unique run directory when the run has passed request validation and has an assigned Run ID.
2. Record controlled failure details.
3. Write a failure manifest atomically when possible.
4. Preserve available logs without claiming successful artifacts.

Request validation failures that occur before Run ID creation do not require a Workspace directory.

### 8.3 Atomicity

Phase 55.3B should provide a shared filesystem writer using：

- UTF-8.
- `\n` newlines for text artifacts where the existing contract allows it.
- Temporary sibling file.
- Flush／close before replace.
- Atomic replace where supported.

Atomic replacement applies to a file inside a newly created run directory. It must not enable replacing an existing run directory.

## 9. Artifact Catalog contract

### 9.1 Catalog source

The catalog scans：

```text
workspace/runs/<year>/<month>/<run-directory>/manifest.json
```

The first version should not recursively scan arbitrary files outside this shape.

### 9.2 Catalog entry

Proposed typed summary：

```text
ArtifactCatalogEntry
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
- health_messages
```

### 9.3 Health states

Proposed values：

```text
valid
invalid_manifest
missing_manifest
missing_artifact
unsafe_path
unsupported_schema
```

A later implementation may represent multiple findings separately, but the user-facing summary must remain deterministic.

### 9.4 Invalid entries

One malformed run must not prevent listing other runs.

Catalog scanning must：

- Return valid entries normally.
- Return controlled invalid entries where enough metadata can be recovered safely.
- Never execute code or import arbitrary artifact content.
- Sort deterministically.

### 9.5 Ordering

Default ordering：

1. `created_at` descending when valid.
2. `run_id` ascending as tie-breaker.
3. Invalid entries after valid entries, ordered by normalized path.

No filesystem modification time should be used as the primary run timestamp.

## 10. CLI compatibility direction

The exact parser design belongs to Phase 55.3C, but the product direction is：

```bash
twstock scan ... --workspace workspace
twstock daily ... --workspace workspace
twstock backtest-report ... --workspace workspace

twstock run list --workspace workspace
twstock run inspect <run-id> --workspace workspace
```

### 10.1 Workspace execution mode

When `--workspace` is provided：

- Application Service owns the run directory.
- Workflow outputs are written below that directory.
- Manifest path is canonical `manifest.json`.
- Existing explicit output-path options must either be rejected as conflicting or normalized into Workspace-managed artifact names according to a separately characterized rule.

The CLI must not silently split one run across unrelated directories.

### 10.2 Legacy execution mode

When `--workspace` is omitted：

- Current output behavior remains unchanged.
- Current default artifact filenames remain unchanged.
- Current exit behavior remains unchanged.
- Current `--manifest-path` behavior remains unchanged.

### 10.3 Read-only commands

`run list` and `run inspect` must operate without network and without domain execution.

Phase 55.3 does not add `run reproduce`.

## 11. Proposed package boundary

Suggested first-version structure：

```text
src/tw_stock_tool/
├── application/
│   └── research_run.py
├── artifacts/
│   ├── __init__.py
│   ├── errors.py
│   ├── workspace.py
│   ├── catalog.py
│   └── registry.py
└── research_run/
    ├── models.py
    └── serialization.py
```

Responsibilities：

### `artifacts.workspace`

- Validate Workspace root.
- Create unique run directories.
- Resolve safe managed paths.
- Write／read canonical manifest files.
- Provide typed run-directory handles.

### `artifacts.catalog`

- Scan canonical run locations.
- Strictly load manifests.
- Build catalog entries.
- Detect missing artifacts and unsafe paths.
- Sort deterministically.

### `artifacts.registry`

- Map known `artifact_type` values to expected media type and optional schema ownership.
- Avoid opening or executing artifact content unless an explicit validator exists.
- Unknown artifact types remain inspectable but are reported as unregistered, not deleted or rewritten.

### `artifacts.errors`

- Define controlled Workspace／Catalog errors.
- Preserve useful path and operation context.
- Avoid leaking implementation tracebacks through normal CLI output.

## 12. Phase breakdown

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
- Open questions either resolved or explicitly assigned to Phase 55.3B characterization.

## Phase 55.3B：Workspace Storage Foundation

### Scope

- Add Workspace models and controlled errors.
- Create unique run directories.
- Add safe path resolution.
- Add canonical manifest persistence and strict read-back.
- Add filesystem catalog scanning.
- Add artifact existence health checks.

### Out of scope

- Existing research workflow migration.
- CLI parser changes.
- GUI changes.
- Database index.

### Required tests

- Cross-platform path normalization.
- Collision rejection.
- Traversal rejection.
- Invalid manifest isolation.
- Missing artifact detection.
- Deterministic ordering.
- Workspace relocation.
- Atomic manifest write failure behavior.

## Phase 55.3C：Scan／Daily／Backtest Integration

### Scope

- Add opt-in Workspace execution to typed requests or an application-level Workspace policy.
- Integrate Scan、Daily and Backtest only.
- Generate Workspace-relative artifact references.
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
- Human-readable status and health output
- Optional machine-readable JSON only if separately locked by contract

### Required tests

- No network calls.
- No strategy or backtest execution.
- Invalid run isolation.
- Run ID exact and unique lookup.
- Deterministic output ordering.
- Controlled not-found errors.

## Phase 55.3E：Documentation and Migration Audit

### Scope

- User guide for Workspace mode.
- Artifact guide updates.
- Legacy mode compatibility notes.
- Runtime／documentation consistency audit.
- Final Phase closeout.

## 13. Acceptance criteria

Phase 55.3 is complete only when：

1. Two same-configuration Workspace runs never overwrite each other.
2. Every managed run has one canonical `manifest.json`.
3. Every managed artifact reference resolves safely below the run directory.
4. A Workspace can be moved and still be listed／inspected.
5. Catalog ordering is deterministic.
6. One damaged run does not break catalog listing.
7. Missing artifacts produce controlled health findings.
8. Unsupported manifest schema produces a controlled finding.
9. List／inspect operate without network or domain execution.
10. Existing artifact schemas remain unchanged unless a separate schema Phase authorizes change.
11. Legacy CLI mode remains behavior-compatible.
12. Python 3.11／3.12 full suite and package smoke pass.
13. Documentation matches exact runtime behavior.

## 14. Explicit non-goals

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

## 15. Open questions for Phase 55.3B characterization

The following questions must be resolved before production implementation merges：

1. Are symlinks entirely rejected, or allowed only when the resolved target remains inside the run directory?
2. Are conflicting explicit artifact paths rejected in Workspace mode, or converted to safe basenames?
3. Should invalid directories without `manifest.json` appear as `missing_manifest`, or be ignored unless they match the canonical run-name pattern?
4. Should `artifact_type` registry mismatches be health warnings or hard validation failures?
5. Should failed runs create the run directory before market-data access, or only after request validation and Run ID assignment?
6. Does `run inspect` accept only full UUID, or also an unambiguous prefix?

Default recommendation：

- Reject symlink escape.
- Reject conflicting external paths.
- Report canonical-looking missing-manifest directories.
- Treat unknown artifact types as warnings.
- Create run directory after request validation and Run ID assignment.
- Require full Run ID in the first version.

## 16. Dependency graph

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

## 17. Product decision

The next production-code task after this planning Phase should be：

> **Phase 55.3B — Implement the filesystem-based Workspace storage and catalog foundation without migrating existing research workflows.**

This ordering separates storage correctness from CLI and workflow integration risk.
