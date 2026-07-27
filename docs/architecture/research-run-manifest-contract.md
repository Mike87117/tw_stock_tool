# Research Run 與 Run Manifest Contract

## 1. 文件目的

本文件為 `tw_stock_tool` 專案 Phase 55.2 的權威 Run Manifest 契約文件。

其目的在於：
1. 根據 repository 目前真實的 workflow、artifact、schema、CLI 與 GUI boundaries，鎖定可重現研究（Reproducible Research）與 Run Manifest 的邊界與資料結構。
2. 規範未來 Phase 55.2 sub-phases（55.2B ~ 55.2J）在建立 Python Data Models、JSON Serializers、Application Services 與各 Workflow 整合時的責任歸屬、欄位契約與向下相容性要求。
3. 確保所有 Phase 55.2 的變更在不破壞既有 Domain Result Models、Artifact Exporters、CLI/GUI 行為與測試的前提下，完成可重現執行紀錄的機械式導入。

---

## 2. Authoritative Source Hierarchy

在處理規格與相容性優先權時，必須嚴格遵守以下權威層級（Authoritative Source Hierarchy）：

1. **Current production source** (`src/tw_stock_tool/**`)
2. **Current artifact model and serializer tests** (`tests/**`)
3. **Current CLI and GUI behavior tests** (`tests/**`)
4. **This Run Manifest contract** (`docs/architecture/research-run-manifest-contract.md`)
5. **Product architecture roadmap** (`docs/architecture/product-architecture-and-roadmap.md`)
6. **Historical phase documents** (`docs/**`)

### 層級約束與相容性原則

* 本文件不得覆寫既有交易、回測、artifact 或 CLI 之行為與測試契約。
* 當本文件與既有 production code 或 existing unit tests 出現衝突時，必須以 current production code 與 existing tests 為準。
* 後續實作 phase（如 Phase 55.2B、55.2C 等）不得僅依據架構藍圖（Roadmap）摘要自行推測或更動 domain 行為。

---

## 3. Current Workflow Inventory

Installed console entrypoint:
`twstock = tw_stock_tool.cli.twstock_cli:main`

### 欄位語意界定

* **Primary Runtime Result**：該 public execution entrypoint 或其直接呼叫的 workflow function 實際在記憶體中建立的主要 result 物件。
* **Execution Entrypoint Output**：該 exact command 本身執行時實際寫出的檔案或 stdout。
* **Adjacent Artifact Boundary**：由其他獨立 command／serializer／exporter 所提供的 artifact 能力（非該 exact execution command 所直接產出）。

下表盤點目前 repository 中真實存在的各主要 workflow 資訊：

| Workflow | Public Entrypoint | Installed Console Command | Legacy / Module Invocation | Primary Runtime Result | Execution Entrypoint Output | Adjacent Artifact Boundary | Existing Schema/Version | Current Run-Level Metadata |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Scan** | `tw_stock_tool.cli.scan_stocks.main` | `twstock scan` | N/A | `pandas.DataFrame` (`ranking_df`) | stdout summary / Excel / CSV / HTML / optional `scan_errors.log` | None required for this inventory row | N/A | None at run level |
| **Daily Report** | `tw_stock_tool.cli.daily_report_cli.main` (Workflow function: `tw_stock_tool.reports.daily_pipeline.run_daily_research_pipeline`) | `twstock daily` | N/A | `DailyPipelineResult` | Markdown / optional JSON Daily Report artifact v1 / optional Excel through `DailyPipelineConfig.output_excel` | N/A | Daily Report JSON `schema_version = 1` | `report_date`, `stock_universe`, `run_configuration`, `pipeline_run_summary`, `data_limitations` |
| **Backtest Report** | `tw_stock_tool.cli.backtest_report.main` | `twstock backtest-report` | N/A | `dict[str, Any]` (normalized report payload) | stdout summary when no file output requested / optional Markdown / optional Excel | `BacktestResult` JSON v1 exists through separately authorized backtest artifact/export commands | N/A for exact execution command | `Stock`, `Strategy`, `Start Date`, `End Date`, `Parameters` |
| **Parameter Sweep** | `tw_stock_tool.cli.parameter_sweep_report.main` | `twstock parameter-sweep` | `python -m tw_stock_tool.cli.parameter_sweep_report` | `pandas.DataFrame` (`sweep_df`) wrapped in `dict[str, Any]` for report exporters | stdout summary / optional Markdown / optional Excel | N/A | N/A | `Stock`, `Strategy`, `Parameters` |
| **Walk Forward** | `tw_stock_tool.cli.walk_forward_report.main` | `twstock walk-forward` | `python -m tw_stock_tool.cli.walk_forward_report` | `pandas.DataFrame` (`wf_df`) wrapped in `dict[str, Any]` for report exporters | stdout summary / optional Markdown / optional Excel | N/A | N/A | `Stock`, `Strategy`, `Parameters` |
| **AI Scan** | `tw_stock_tool.ml.ai_stock_scanner.main` | `twstock ai-scan` | N/A | `pandas.DataFrame` (`ranking`) | stdout table / optional Excel | N/A | N/A | None at run level |
| **AI Report** | `tw_stock_tool.reports.ai_prediction_report.main` | `twstock ai-report` | N/A | `dict[str, pandas.DataFrame]` with Summary, Detail, Errors | stdout Summary and Detail / optional Excel | N/A | N/A | None at run level |
| **ML Dataset** | `tw_stock_tool.ml.ml_dataset.main` | `twstock ml-dataset` | N/A | `pandas.DataFrame` (`dataset`) | stdout table / optional CSV encoded with `utf-8-sig` | N/A | N/A | None at run level |
| **Single-Symbol Paper Trading** | `tw_stock_tool.cli.simulated_paper_trading_cli.main` | `twstock simulated-paper-trading` | `python -m tw_stock_tool.cli.simulated_paper_trading_cli` | `SimulatedPaperTradingResult` | stdout summary only | Simulated Paper Trading JSON schema v3 and CSV/Markdown export capabilities exist through separate serialization/export commands | N/A for exact execution command | No centralized run-level metadata |
| **Multi-Symbol Portfolio Trading** | `tw_stock_tool.cli.simulated_portfolio_trading_cli.main` | `twstock simulated-portfolio-trading` | `python -m tw_stock_tool.cli.simulated_portfolio_trading_cli` | `SimulatedPortfolioTradingResult` | required JSON artifact / stdout summary | offline artifact command may inspect/export the existing JSON without rerunning simulation | Simulated Portfolio Trading JSON `schema_version = 1` | No centralized run-level metadata |

### 市場資料存取點與 GUI 邊界附註

* **Market-Data Access Point 附註**：部分 Workflow（如 Backtest Report, Parameter Sweep, Walk Forward, Paper Trading, AI Workflows）係透過 `analyze_stock`, `AnalysisSession` 或 Scanner 間接取得市場資料，其存取路徑為 `Indirect through analysis/session boundary to data_loader.download_tw_stock`。
* **GUI Entrypoint 附註**：GUI entrypoints 目前由 Tkinter UI（`src/tw_stock_tool/gui/`）內部控制層依工作流程獨立調用，標示為 `Not yet centralized`。

---

## 4. Run Boundary

### 定義

> **一次 Research Run 是由一份不可變的 resolved configuration 啟動，產生零個或多個既有 artifacts，並以一份 run-level manifest 記錄執行設定、資料來源、結果狀態、限制及 artifact references。**

### 邊界原則與限制

1. **Manifest 的定位**：Manifest 是 run-level 的中介詮釋資料（metadata），記錄該次運行的上下文與成果摘要。
2. **不替代既有 Artifact**：RunManifest 絕不取代既有的 Daily Report, BacktestResult, PaperTradingResult 等 domain artifacts。
3. **無內嵌與無迴圈依賴**：既有 domain artifacts 不得內嵌完整的 RunManifest；RunManifest 僅透過 `ArtifactReference` 參照 artifacts 的產出路徑與基本資訊。
4. **多 Artifact 支援**：單一 Research Run 可以根據 workflow 設定同時產出多種格式的 artifacts（例如同時輸出 Markdown、Excel 與 JSON）。
5. **檢視不構成 Run**：對既有 artifact 進行離線讀取、檢視或驗證（Inspect / Read-back），不得視為開啟一次新的 Research Run。
6. **離線讀取無 Side-effect**：單純讀取既有 artifact 絕不得重新下載或向市場資料源發起連線。
7. **嚴格禁止擴張至實體交易**：Research Run 邊界僅限於資料分析、策略回測與模擬交易，絕不得延伸至真實券商 API 下單或實體資金交易。

---

## 5. Core Models

Phase 55.2 鎖定以下五個核心 Data Models 及其責任邊界：

1. `RunConfig`
2. `DataSourceRecord`
3. `ArtifactReference`
4. `RunManifest`
5. `ResearchRunResult`

### 5.1 RunConfig

* **責任**：保存已解析（resolved）、完全不可變且可精確重現的執行設定。
* **限制**：不得包含執行結果、DataFrame 物件、無效的 CLI 原始字串或不可序列化的 callback 函式。

```python
class RunConfig:
    workflow: str  # e.g., "scan", "daily", "backtest", "parameter_sweep", "walk_forward", "ml", "paper_trading"
    universe: str | None  # e.g., "all", "twse", "tpex", "custom"
    canonical_symbols: tuple[str, ...]  # e.g., ("2330.TW", "2317.TW")
    period: str  # e.g., "1y"
    interval: str  # e.g., "1d"
    auto_adjust: bool  # resolved boolean value (DEFAULT_AUTO_ADJUST resolved)
    force_refresh: bool  # resolved boolean value
    strategy: str | None  # e.g., "ma_cross", "rsi", "macd", "score"
    backtest: dict[str, Any] | None  # defensive snapshot dict
    parameter_sweep: dict[str, Any] | None
    walk_forward: dict[str, Any] | None
    ml: dict[str, Any] | None
    workflow_options: dict[str, Any]  # defensive snapshot dict
```

*註：不適用的 workflow 欄位設為 `None` 或空字典 `{}`。所有 workflow 共用同一套 `RunConfig` schema，不得為不同 workflow 建立獨立的 config schema。*

### 5.2 DataSourceRecord

* **責任**：記錄單一市場標的（Symbol）在本次 Run 中請求與載入市場資料的歷程與狀態。

```python
class DataSourceRecord:
    canonical_symbol: str  # e.g., "2330.TW"
    requested_symbol: str  # e.g., "2330"
    provider: str  # e.g., "yfinance", "twse", "tpex", "cache"
    period: str  # e.g., "1y"
    interval: str  # e.g., "1d"
    auto_adjust: bool  # boolean
    source_kind: str  # Enum: "live" | "cache"
    cache_state: str  # Enum: "not_applicable" | "fresh" | "stale"
    success: bool  # boolean
    error: str | None  # error message if failed
```

*限制：不得將 `pandas.DataFrame` 或 provider 的原始 HTTP response 寫入紀錄中。*

### 5.3 ArtifactReference

* **責任**：記錄 Research Run 所產生的既有 Domain Artifact 參照資訊。

```python
class ArtifactReference:
    artifact_type: str  # e.g., "daily_report_json", "backtest_result_json", "markdown_report", "excel_report"
    path: str  # A normalized path string using forward slashes
    media_type: str  # e.g., "application/json", "text/markdown", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    schema_version: int | str | None  # existing artifact schema_version (e.g., 1 or 3)
```

*註：Phase 55.2 不強制修改既有 artifact exporters。Checksum、size 與 parent reference 屬於 Phase 55.3 未來擴充，不得列為 Phase 55.2B 的必選功能。*

### 5.4 RunManifest

* **責任**：彙整整次 Research Run 的不可變詮釋資料。

```python
class RunManifest:
    schema_version: str  # Frozen to "1.0"
    run_id: str  # Canonical UUID v4 string
    created_at: str  # UTC RFC 3339 timestamp (ending with 'Z')
    tool_version: str  # Package version (authoritative runtime source: installed package metadata for "tw-stock-tool"; baseline example: "0.4.0")
    status: str  # Enum: "success" | "partial" | "failure"
    config: RunConfig
    data_sources: tuple[DataSourceRecord, ...]
    success_count: int
    failure_count: int
    partial_count: int
    artifacts: tuple[ArtifactReference, ...]
    errors: tuple[str, ...]
    limitations: tuple[str, ...]
```

*限制：Status Enum 僅包含 `"success"`, `"partial"`, `"failure"`。不包含 `"running"` 狀態；執行中的進度管理由 Application Service 負責處理。*

### 5.5 ResearchRunResult

* **責任**：作為 Application Service 在記憶體內（in-memory）回傳的整體結果邊界物件。

```python
class ResearchRunResult:
    manifest: RunManifest
    domain_result: Any | None  # opaque reference to existing domain model (e.g. BacktestResult, DailyReport, DataFrame)
    generated_artifacts: tuple[ArtifactReference, ...]
```

### 5.6 Immutable Model Boundary 規則

1. **Sequence Fields as Tuples**：
   * `RunConfig.canonical_symbols: tuple[str, ...]`
   * `RunManifest.data_sources: tuple[DataSourceRecord, ...]`
   * `RunManifest.artifacts: tuple[ArtifactReference, ...]`
   * `RunManifest.errors: tuple[str, ...]`
   * `RunManifest.limitations: tuple[str, ...]`
   * `ResearchRunResult.generated_artifacts: tuple[ArtifactReference, ...]`
   *(JSON Serializer 將在 Phase 55.2C 將 tuple 序列化為 JSON array)*
2. **Defensive Configuration Snapshot**：
   * 對於 `backtest`, `parameter_sweep`, `walk_forward`, `ml`, `workflow_options` 等 dict 欄位，Model 在建構時必須建立 defensive snapshot。
   * 內部包含的 nested lists 轉為 tuples 或等價不可變序列。
   * 內部包含的 nested dicts 轉為 read-only mappings 或等價不可變字典。
   * Keys 必須為 exact strings；Values 只允許 JSON-safe scalar, sequence 或 mapping。
   * 所有 float 必須為 finite（禁止 `NaN`, `Infinity`）。
   * 嚴格禁止 `DataFrame`, `Path`, `datetime`, `set`, `callback`, open file handle 或任意自訂 runtime 物件。
   * Model 建構完成後，修改 caller 原始傳入的 list 或 dict 絕不得改變 Model 內部內容。
3. **Opaque Domain Result**：
   * `ResearchRunResult.domain_result` 為既有 domain result 物件（如 `DailyPipelineResult`, `SimulatedPaperTradingResult`, `DataFrame` 等）的 opaque reference。
   * 不屬於 RunManifest 序列化範疇，不納入 `RunManifest` 深度不可變保證。
   * 核心模型驗證不得對 `domain_result` 進行遞迴序列化或形態強迫。
   * 不取代任何既有 domain models。

---

## 6. Field Contracts

### 6.1 Run ID 契約

* **格式**：UUID Version 4 Canonical Lowercase String（例如：`"550e8400-e29b-41d4-a716-446655440000"`）。
* **原則**：不得單獨使用股票代號、策略名稱或時間戳作為唯一 Run ID。
* **驗證規則**：
  * Parsed UUID version must equal 4.
  * Canonical lowercase rendering must equal the original value.

### 6.2 Timestamp 契約

* **格式**：UTC RFC 3339 Timestamp，精確至秒，且必須以字母 `Z` 結尾（例如：`"2026-07-27T20:00:00Z"`）。
* **原則**：不得包含本機時區（Local Timezone）偏移渲染（如 `+08:00`）。

### 6.3 Schema Version 與 Tool Version 契約

* **`RunManifest.schema_version`**：固定為字串 `"1.0"`。
* **`RunManifest.tool_version`**：
  * `tool_version` records the package version used for the run.
  * Its authoritative runtime source is installed package metadata for the `"tw-stock-tool"` distribution.
  * The repository baseline source is `pyproject.toml` `[project].version` (e.g., `"0.4.0"`).
* **層級區隔**：
  * `schema_version` (`"1.0"`)：專指 Run Manifest 結構的版本。
  * `tool_version` (`"0.4.0"`)：專指 `tw_stock_tool` 套件目前 baseline 版本。
  * `ArtifactReference.schema_version` (如整數 `1` 或 `3`)：專指各個產出的 domain artifact 本身之 schema 版本。

### 6.4 Pure Model Validation Contract

Phase 55.2B 的純模型建立時，必須強制執行以下驗證規則：

1. **通用字串欄位驗證**：
   * `workflow`, `period`, `interval`, `canonical_symbol`, `requested_symbol`, `provider`, `artifact_type`, `path`, `media_type`, `tool_version` 必須為 exact `str`（`type(x) is str`），且去除首尾空白後非空。
   * 不進行自動隱式 trim；若傳入夾帶空白或非法字元直接拋出例外。
   * Optional string 欄位若非 `None`，亦必須為非空 exact string。
2. **Exact Boolean 驗證**：
   * `auto_adjust`, `force_refresh`, `success` 必須為 exact `bool`（`type(x) is bool`）。整數 `0` 或 `1` 均屬非法並直接拒絕。
3. **Canonical Symbols 驗證**：
   * `RunConfig.canonical_symbols` 必須為 tuple。
   * 每個元素必須為非空 exact string，且不允許重複。
   * 保留 caller 傳入的確定性順序，且至少必須包含一個 symbol。
   * Caller 必須傳入已解析完成的 canonical symbol（例如 `["2330.TW"]`）；Phase 55.2B 不重新解析 `.TW/.TWO`。
4. **Enum 精確值斷言**：
   * `RunManifest.status`: 只允許 exact `"success"`, `"partial"`, `"failure"`。
   * `DataSourceRecord.source_kind`: 只允許 exact `"live"`, `"cache"`。
   * `DataSourceRecord.cache_state`: 只允許 exact `"not_applicable"`, `"fresh"`, `"stale"`。
   * 絕不安裝自動大小寫轉換或模糊匹配。
5. **DataSourceRecord 內部一致性**：
   * `source_kind = live` ──> `cache_state` 必須為 `not_applicable`。
   * `source_kind = cache` ──> `cache_state` 必須為 `fresh` 或 `stale`。
   * `success = true` ──> `error` 必須為 `None`。
   * `success = false` ──> `error` 必須為非空 exact string。
   * `provider` 對於快取的紀錄（如 `source_kind = cache`）仍必須為非空字串（如 `"cache"`）。
6. **ArtifactReference 驗證**：
   * `path` 必須使用以 `/` 分隔的 normalized representation，非空。
   * `schema_version` 只允許 `None`、正整數（`type(x) is int and x > 0`，`bool` 屬非法）或非空 exact string。
   * Phase 55.2B 只驗證 reference metadata 結構，不檢查實體檔案是否存在，亦不讀取 artifact payload。
7. **Count 欄位語意與一致性**：
   * `success_count`, `failure_count`, `partial_count` 必須為 exact 非負整數（`type(x) is int and x >= 0`），`bool` 屬非法。
   * **Status Consistency Rules**：
     * `status = success` ──> `failure_count == 0` 且 `partial_count == 0`。
     * `status = failure` ──> `success_count == 0` 且 `partial_count == 0` 且 `failure_count >= 1`。
     * `status = partial` ──> `partial_count >= 1` OR (`success_count >= 1` AND `failure_count >= 1`)。
8. **Errors 與 Limitations 驗證**：
   * 必須為 tuple，內部每個元素必須為非空 exact string。
   * 當 `status = failure` 時，`errors` 至少必須包含一筆錯誤字串。
   * `limitations` 可為空 tuple。
9. **ResearchRunResult Artifact Consistency**：
   * 斷言 `ResearchRunResult.generated_artifacts` 必須等於（`==`，Value Equality）`ResearchRunResult.manifest.artifacts`。

---

## 7. Run Lifecycle

Research Run 的完整生命週期必須遵循以下單向順序：

```text
Resolve configuration
  │
  ▼
Generate run_id & create RunConfig
  │
  ▼
Establish shared per-run context
  │
  ▼
Execute workflow logic
  │
  ▼
Collect DataSourceRecords
  │
  ▼
Persist existing artifacts
  │
  ▼
Build ArtifactReferences
  │
  ▼
Finalize status, counts, errors & limitations
  │
  ▼
Serialize RunManifest to disk
  │
  ▼
Return ResearchRunResult
```

### 生命週期規則

1. **Manifest 產生時機**：最終的 `RunManifest` 必須在 Workflow 執行完成且結果狀態確定後才進行建立與寫入。
2. **中途失敗處理**：若執行途中發生異常（In-flight failure），只要 Run Boundary 已成功建立，仍應嘗試產出 `status="failure"` 的 manifest 檔記錄錯誤。
3. **前置驗證失敗**：若在 Run Boundary 建立前的 Configuration Validation 即宣告失敗（例如傳入非法 period/interval），可以不產生 manifest 檔。
4. **Manifest 寫入失敗**：Manifest 寫入磁碟失敗不得被吞掉或誤報為研究成功。
5. **Partial Status**：`status="partial"` 必須由 workflow 既有的部分失敗語意（如部分股票下載失敗但其餘成功）決定，不得重新定義 domain 行為。

---

## 8. Data Source Recording

### Shared Per-Run Market-Data Context

為了避免同一次 Research Run（如執行 Daily Report 或 Multi-symbol Backtest）中重複下載相同的市場資料，未來 Application Service 必須提供僅限單次 Run 生命週期的 shared market-data context。

#### Market-Data Deduplication Key

去重比對 Key 定義如下五元組：

```text
(canonical_symbol, period, interval, auto_adjust, force_refresh)
```

#### 行為規範

1. **單次解析**：在同一 Research Run 內，若遇到相同 key 的請求，僅執行一次市場資料下載/載入解析。
2. **重用 DataFrame**：後續相同的請求直接重用第一次解析出的 `pandas.DataFrame`。
3. **無全域單例**：去重機制限定在單次 Run context 內，不得透過全域變數或 Process-wide singleton 實作。
4. **不改變磁碟快取**：此機制不改動 `data_loader.download_tw_stock(...)` 的既有磁碟快取邏輯。
5. **記憶體防護**：DataFrame 是否複製（copy vs reference）由實作階段根據 mutation 風險決定。

---

## 9. Artifact Relationship

### 結構關聯

`RunManifest` 與產出的 Artifacts 保持一對多單向參照：

```text
RunManifest
└── artifacts: tuple[ArtifactReference, ...]
```

### 關聯與 Path 過渡政策原則

1. **不修改舊 Schema**：不得為了併入 Run 概念而修改既有 domain artifacts（如 Daily Report JSON, Backtest Result JSON）的結構去強制注入 `run_id`。
2. **不內嵌 Payload**：`RunManifest` 的 `artifacts` 串列僅記錄 `ArtifactReference`，絕不內嵌整個 artifact 的檔案內容。
3. **離線驗證解耦**：驗證 artifact 檔案存在或讀取內容時，不得觸發工作流程重新執行。
4. **Serializer 解耦**：`RunManifest` 的序列化器不得直接依賴特定的 Daily 或 Backtest domain result classes。
5. **Path 過渡政策**：
   * 未來有 run directory 或明確 workspace root 時，優先儲存相對於該 root 的 path。
   * Phase 55.3 Workspace 尚未建立前，允許保存 exporter 目前實際產生的 output path。
   * Phase 55.2B 不得假設所有 artifact paths 都已能轉成 run-relative path。
   * Path 只記錄參照，不得讀取或內嵌 artifact payload。
   * Windows path 序列化時統一使用 `/`，但不得因此改變實際 filesystem location。

---

## 10. Serialization Contract

`RunManifest` 的 JSON 序列化器必須嚴格遵守以下格式規範：

* **文件編碼**：UTF-8。
* **Format**：JSON，`indent=2`，`ensure_ascii=False`（直觀顯示中文不轉義）。
* **確定性輸出**：Dict 欄位保持確定性順序（Deterministic field order）。
* **結尾換行**：檔案結尾必須包含單一 newline (`\n`)。
* **Strict Read-Back Validation**：反序列化讀回時進行嚴格型別與結構驗證。
* **Fail-Closed 政策**：當遇到未知的 `schema_version`（非 `"1.0"`）時，必須立即拋出例外（Fail-closed）。
* **特殊數值禁止**：Serializer 絕不得寫入 `NaN`、`Infinity` 或 Python 特有型別（如 `set`, `datetime`）；`None` 統一序列化為 JSON `null`。
* **Enum 序列化**：Enum 統一轉為純字串。
* **Timestamp 序列化**：以 ISO 8601 / RFC 3339 UTC 字串（結尾 `Z`）儲存。
* **Path 序列化**：Path 物件統一轉為跨平台 normalized path 字串（使用正斜線 `/`）。
* **Tuple 序列化**：
  * Tuple serialization: Python tuples are serialized as JSON arrays.
* **Unknown Extra Fields 政策**：
  * Unknown extra fields: The exact read-back policy is intentionally deferred to Phase 55.2C, where it must be selected based on existing repository serializer conventions and frozen by tests.
  * Unknown schema versions remain fail-closed regardless of the extra-field policy.

---

## 11. Application Service Boundary

未來的 Application Service 為連鎖 CLI、GUI 與 Core Domain 的中央協調層。

### 職責範圍

* 解析與驗證 `RunConfig`。
* 建立單次 Run 的 context 與 `run_id`。
* 協調 workflow 執行。
* 去重市場資料載入與記錄 `DataSourceRecord`。
* 呼叫既有 domain exporter 產出 artifacts。
* 建立並序列化寫入 `RunManifest`。
* 回傳 `ResearchRunResult` 給調用方。

### 禁止行為

* **不得重撰 Domain 邏輯**：不得重新實作指標、策略、回測或模擬交易計算邏輯。
* **不得替代 Domain 模型**：不得替換既有的 `BacktestResult`, `DailyReport` 等模型。
* **不得耦合 GUI 控制元件**：不得直接存取或解析 Tkinter widgets 變數。
* **不得直接以 CLI Namespace 為介面**：不得將 `argparse.Namespace` 直接作為 Application Service 的 domain API 參數。
* **不得包含實體下單**：不得包含任何券商串接、真實資金下單或自動投資建議功能。

---

## 12. Workflow Integration Sequence

Phase 55.2 的子階段執行順序鎖定如下：

1. **55.2B** — Core models and pure validation
2. **55.2C** — JSON serializer/read-back boundary
3. **55.2D** — Per-run context and market-data deduplication
4. **55.2E** — Scan manifest integration
5. **55.2F** — Backtest manifest integration
6. **55.2G** — Daily Report manifest integration
7. **55.2H** — Shared CLI/Application Service boundary
8. **55.2I** — GUI adapter integration
9. **55.2J** — Phase 55.2 acceptance audit

### 順序理由

* 必須先完成核心 Data Models 與 Serializer (55.2B, 55.2C)，確保基礎元件完全凍結。
* 接著建置單次 Run 的執行 context (55.2D)。
* 按照由簡入繁的順序整合 Workflow：Scan (55.2E) -> Backtest (55.2F) -> Daily Report (55.2G)。
* 待核心 Workflow 整合完成後，才建立共用的 CLI/Application Service (55.2H) 與 GUI Adapter (55.2I)。
* 本文件僅規劃順序，**未授權**自動啟動後續任何子階段。

---

## 13. Compatibility and Non-goals

### 相容性承諾

* 公開 CLI 指令名稱與參數預設值保持完全不變（除非另行授權）。
* 既有 Domain Artifact Schemas（Daily Report JSON v1, Backtest JSON v1, Paper Trading JSON v3/v1）保持完全不變。
* 既有 JSON read-back 行為保持完全相容。
* 既有 Excel 工作表名稱（Sheet names）與欄位保持完全不變。
* 既有 Markdown 報告區塊順序與格式保持完全不變。
* 既有交易與回測計算邏輯保持完全不變。
* 既有市場資料快取（`data_loader` 快取）行為保持完全不變。

### 非目標（Non-goals）

* 本 Phase 不進行任何券商串接（No broker integration）。
* 本 Phase 不進行任何真實資金交易（No real trading）。
* 本 Phase 不提供自動投資建議（No automatic investment recommendation）。
* 本 Phase 不進行 Workspace 目錄結構轉移（No workspace migration in Phase 55.2）。
* 本 Phase 不進行全套件層級的檔案目錄大搬移（No package-wide directory relocation）。

---

## 14. Testing Strategy

後續 Phase 55.2 的測試必須包含以下層級：

### Pure Model Tests (Phase 55.2B)

* 驗證 `RunConfig`, `DataSourceRecord`, `ArtifactReference`, `RunManifest`, `ResearchRunResult` 之合法建立。
* 驗證必要欄位缺失時引發精確例外。
* 驗證 Status Enum, SourceKind Enum, CacheState Enum 之合法值與非法值阻絕。
* 驗證 UTC RFC 3339 Timestamp 與 UUID v4 之格式斷言。
* 斷言 Data Models 內絕無 DataFrame, Path 或 Callback 洩漏。

### Serialization Tests (Phase 55.2C)

* 驗證 JSON Payload 格式與 `indent=2`, `ensure_ascii=False`。
* 驗證繁體中文內容 Round-trip 不失真。
* 驗證確定性欄位順序與檔案結尾 newline (`\n`)。
* 驗證未知 `schema_version` 觸發 Fail-closed 拋出例外。
* 驗證 Malformed JSON 阻絕。

### Run-Context Tests (Phase 55.2D)

* 驗證相同 key 於同一 Run 內僅下載/載入一次。
* 驗證不同 key（不同 period/interval/auto_adjust/force_refresh）分開載入。
* 驗證 Live 與 Cache（Fresh/Stale）載入歷程正確記錄至 `DataSourceRecord`。
* 驗證無網路環境下（Fake providers）的 Context 去重運作。

### Integration Tests (Phase 55.2E ~ 55.2I)

* 驗證 Scan, Backtest, Daily Report 等工作流程執行後正確產出 `RunManifest`。
* 驗證既有 Exporters 產出之 Artifact 內容與格式完全不變。
* 驗證 Partial Failure 與 Full Failure 狀態下 Manifest 紀錄正確。
* 驗證 CLI 與 GUI 呼叫共用 Application Service 之結果一致性。

---

## 15. Phase 55.2 Sub-phase Plan

* **Phase 55.2A**: Document Research Run & Run Manifest Contract (This Phase)
* **Phase 55.2B**: Core Models & Pure Validation Implementation
* **Phase 55.2C**: Run Manifest Serializer & Read-Back Implementation
* **Phase 55.2D**: Shared Per-Run Market-Data Context Implementation
* **Phase 55.2E**: Scan Workflow Manifest Integration
* **Phase 55.2F**: Backtest Workflow Manifest Integration
* **Phase 55.2G**: Daily Report Workflow Manifest Integration
* **Phase 55.2H**: Application Service & Shared CLI Boundary Implementation
* **Phase 55.2I**: GUI Adapter Integration
* **Phase 55.2J**: Phase 55.2 Full Acceptance & Audit

---

## 16. Acceptance Checklist

- [x] Core model responsibilities are unambiguous (`RunConfig`, `DataSourceRecord`, `ArtifactReference`, `RunManifest`, `ResearchRunResult`).
- [x] Run ID and timestamp contracts are frozen (UUID v4 canonical string, UTC RFC 3339 ending in 'Z').
- [x] Manifest schema version is frozen (`"1.0"`).
- [x] Existing artifact schemas remain authoritative.
- [x] Data source recording is defined (`source_kind`, `cache_state`).
- [x] Per-run market-data deduplication key is defined (`canonical_symbol`, `period`, `interval`, `auto_adjust`, `force_refresh`).
- [x] Application Service responsibility is defined.
- [x] CLI and GUI dependency direction is defined (both consume shared Application Service).
- [x] Serialization requirements are defined (UTF-8, indent=2, ensure_ascii=False, deterministic, trailing newline, fail-closed).
- [x] Compatibility surfaces are listed.
- [x] Phase 55.2 sub-phase order is defined (55.2A through 55.2J).
- [x] Broker integration and real trading remain excluded.
- [x] Workflow inventory matches production entrypoints, primary runtime results, and execution outputs.
- [x] UUID v4 example is valid and version validation rules are explicit.
- [x] Tool version authoritative source and baseline example ("0.4.0") are explicit.
- [x] Artifact path transitional policy is defined.
- [x] Tuple serialization is defined (JSON array).
- [x] Unknown extra-field policy is explicitly deferred to Phase 55.2C.
- [x] Pure model validation contract is frozen (sequence tuples, defensive snapshots, opaque domain result, string/bool/enum/count/consistency rules).
