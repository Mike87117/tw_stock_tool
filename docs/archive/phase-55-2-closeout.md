# Phase 55.2 Closeout：Research Run 與 Run Manifest

## 1. Closeout purpose

本文件凍結 Phase 55.2 的完成狀態、已建立契約、驗收 evidence、已知限制與後續依賴。

本文件是 Phase 55.2 的 closeout record，不是新的 production implementation authorization。後續修改仍需依照獨立 Phase planning、Reviewer Gate、CI Gate 與 Merge Gate 進行。

## 2. Baseline

- Repository：`Mike87117/tw_stock_tool`
- Baseline branch：`main`
- Baseline commit：`09156976def5a31f32e3b719214bc70b4639752e`
- Baseline date：2026-07-31
- Package version：`0.4.0`
- Full-suite evidence：Python 3.11／3.12 各 2,244 tests PASS
- Package smoke：Python 3.11／3.12 PASS
- Product boundary：歷史資料研究、策略驗證、離線模擬交易與研究 artifacts
- Explicit non-goals：券商串接、真實下單、自動交易、投資建議與獲利保證

## 3. Phase status

**Phase 55.2 is complete for the planned Scan、Daily Report 與 Backtest Research Run foundation.**

已完成的主要子階段：

| 子階段 | 結果 |
| --- | --- |
| 55.2A Run Manifest contract planning | Complete |
| 55.2B Core models | Complete |
| 55.2C Serialization and strict read-back | Complete |
| 55.2D Per-run market-data context | Complete |
| 55.2E Scan manifest integration | Complete |
| 55.2F Backtest manifest integration | Complete |
| 55.2G Daily Report manifest integration | Complete |
| 55.2H1 Typed application boundary | Complete |
| 55.2H2 Catalog-backed canonical symbol resolution | Complete |
| 55.2H3 CLI application-service wiring | Complete |
| Test-suite and Data Loader compatibility cleanup | Complete for Cleanup A–D; private compatibility retirement remains partial |

## 4. Delivered contracts

### 4.1 Run-level models

Phase 55.2 established validated typed boundaries for：

- `RunConfig`
- `RunManifest`
- `DataSourceRecord`
- `ArtifactReference`
- `ResearchRunResult`
- `SymbolRequest`
- `ScanRunRequest`
- `DailyRunRequest`
- `BacktestRunRequest`

The manifest records at least：

- UUID v4 Run ID
- UTC creation timestamp
- Tool version
- Workflow and universe
- Canonical symbols
- Period／interval
- Auto-adjust／force-refresh
- Resolved workflow options
- Strategy and backtest configuration where applicable
- Data-source provenance
- Fresh／stale cache state
- Success／failure／partial counts
- Generated artifact references
- Errors and limitations

### 4.2 Serialization boundary

Run Manifest schema version `1.0` provides：

- Deterministic JSON serialization
- UTF-8 JSON output
- Strict field inventory
- Duplicate JSON-key rejection
- Unknown-field rejection
- Non-finite number rejection
- Model validation on read-back

The manifest remains run-level metadata and does not replace existing Daily、Backtest、Paper Trading or Portfolio artifact schemas.

### 4.3 Market-data reuse boundary

`ResearchRunContext` provides per-run market-data reuse keyed by：

```text
canonical symbol
+ period
+ interval
+ auto_adjust
+ force_refresh
```

The context：

- Reuses completed outcomes within the same run.
- Coalesces concurrent same-key requests.
- Preserves deterministic request order for data-source records.
- Re-raises the stored error for repeated failed requests.
- Rejects recursive same-thread same-key loading.

### 4.4 Application-service boundary

The typed Application Service supports：

- Scan
- Daily Report
- Backtest

The supported CLI adapters now parse input, resolve symbols, build typed requests, call the Application Service and render output／exit status. Direct domain execution was removed from the migrated success paths.

The Application Service is reusable by GUI code, but Phase 55.2 did **not** wire the existing GUI prototype to the new boundary.

### 4.5 Canonical symbol resolution

The migrated CLIs resolve requested stock IDs to canonical `.TW`／`.TWO` symbols through the stock catalog boundary, including reuse of an already fetched auto-stock-list catalog.

## 5. Acceptance result

| Phase 55.2 acceptance criterion | Result |
| --- | --- |
| Scan can produce a Run Manifest | PASS |
| Daily Report can produce a Run Manifest | PASS |
| Backtest can produce a Run Manifest | PASS |
| Same-run market data can be reused | PASS |
| Daily auto-stock-list catalog fetch is reused | PASS |
| Resolved configuration is recorded | PASS |
| Data-source provenance is recorded | PASS |
| Manifest strict JSON read-back exists | PASS |
| CLI uses shared typed Application Service | PASS for Scan／Daily／Backtest |
| GUI can share the Application Service | Boundary ready; GUI wiring deferred |
| Existing artifact schemas remain separate | PASS |
| Existing CLI process exit behavior preserved | PASS |

## 6. Known limitations and technical debt

### 6.1 No Workspace or Run History yet

Each workflow can generate a unique Run ID, but default manifest and report paths are still output-directory based and may use fixed filenames such as：

- `scan_run_manifest.json`
- `daily_report_run_manifest.json`
- `backtest_run_manifest.json`

Repeated runs in the same output directory can replace earlier files. Therefore the product currently has Run metadata but does not yet provide durable Run History.

### 6.2 Artifact paths are not Workspace-relative

`ArtifactReference.path` is normalized to POSIX separators, but Phase 55.2 does not define：

- A portable run-directory root.
- Workspace-relative artifact addressing.
- External artifact references.
- Relocation behavior.
- Missing-artifact health state.

These are Phase 55.3 concerns.

### 6.3 No Artifact Catalog

The runtime can record artifacts inside one manifest, but it cannot yet：

- List all runs.
- Find a run by Run ID.
- Inspect all artifacts in a Workspace.
- Report invalid or missing artifacts without opening each workflow manually.
- Compare runs.

### 6.4 Private Data Loader compatibility seams remain

The Research Run market-data adapter still obtains cache、provider and fallback observations through private `data_loader` facade functions.

This was intentionally not removed during test cleanup because changing it is an architecture and behavior-risk change. It must be handled in a separate technical-debt Phase and must not be hidden inside Artifact Hub implementation.

### 6.5 Workflow coverage is intentionally partial

Phase 55.2 does not yet provide the same Run Application boundary for：

- Parameter Sweep standalone command
- Walk Forward standalone command
- ML／AI workflows
- Single-symbol simulated paper trading
- Multi-symbol portfolio simulation
- GUI execution paths

Their integration should follow after Workspace storage contracts are stable, unless a later planning Phase explicitly reprioritizes them.

## 7. Protected invariants

The next Phase must preserve：

- Existing artifact schema versions and read-back behavior.
- Existing CLI behavior when Workspace mode is not selected.
- Fresh Cache → Yahoo Finance → Official TWSE／TPEx → Stale Cache → final error ordering.
- Cache filename and stale-cache warning contracts.
- Backtest next-bar-open execution semantics.
- Simulated trading and portfolio chronology semantics.
- Artifact-only operations remaining offline and side-effect limited.
- Research-only product positioning.

## 8. Closeout decision

Phase 55.2 should not be extended with additional unrelated workflow integrations before the Workspace boundary is planned.

The next product Phase is：

> **Phase 55.3A — Artifact Hub and Workspace Contract Planning**

Phase 55.3A is a documentation and contract-planning Phase. It must define layout、path ownership、collision behavior、catalog source of truth、offline inspection and compatibility strategy before production storage code is introduced.
