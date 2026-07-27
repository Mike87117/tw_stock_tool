# Research Run 與 Run Manifest Contract

## 1. 文件目的

本文件為 `tw_stock_tool` 專案 Phase 55.2 的權威 Run Manifest 契約文件。

其目的在於：
1. 根據 repository 目前真實的 workflow、artifact、schema、CLI 與 GUI boundaries，鎖定可重現研究（Reproducible Research）與 Run Manifest 的邊界與資料結構。
2. 規範未來 Phase 55.2Sub-phases（55.2B ~ 55.2J）在建立 Python Data Models、JSON Serializers、Application Services 與各 Workflow 整合時的責任歸屬、欄位契約與向下相容性要求。
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

下表盤點目前 repository 中真實存在的各主要 workflow entrypoints、輸出模型、產出 artifact、市場資料存取點與版本狀態：

| Workflow | Public Entrypoint | CLI Command | GUI Entrypoint | Primary Result Model | Generated Artifacts | Market-Data Access Point | Existing Schema/Version | Current Run-Level Metadata |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Scan** | `tw_stock_tool.cli.run_scan` | `tw-stock-tool scan` | Not yet centralized | `pandas.DataFrame` | stdout / Markdown / CSV / JSON | `data_loader.download_tw_stock` | N/A | None |
| **Daily Report** | `tw_stock_tool.cli.run_daily` | `tw-stock-tool daily` | Not yet centralized | `DailyReport` | `daily_report.md` / `daily_report.json` | `data_loader.download_tw_stock` | `schema_version = 1` | `generated_at`, `stock_count` |
| **Backtest** | `tw_stock_tool.cli.run_backtest` | `tw-stock-tool backtest` | Not yet centralized | `BacktestResult` | stdout / Markdown / Excel / JSON | `data_loader.download_tw_stock` | `schema_version = 1` | `strategy_name`, `timestamp` |
| **Parameter Sweep** | `tw_stock_tool.cli.run_parameter_sweep` | `tw-stock-tool parameter-sweep` / `parameter_sweep_report.py` | Not yet centralized | `pandas.DataFrame` | Markdown / Excel | `data_loader.download_tw_stock` | N/A | `strategy`, `period` |
| **Walk Forward** | `tw_stock_tool.cli.run_walk_forward` | `tw-stock-tool walk-forward` / `walk_forward_report.py` | Not yet centralized | `pandas.DataFrame` | Markdown / Excel | `data_loader.download_tw_stock` | N/A | `strategy`, `period` |
| **ML Baseline** | `tw_stock_tool.cli.run_ml` | `tw-stock-tool ml` / `ml_predict.py` | Not yet centralized | `pandas.DataFrame` | CSV / Excel | `data_loader.download_tw_stock` | N/A | `horizon`, `train_size` |
| **Single-Symbol Paper Trading** | `tw_stock_tool.cli.run_simulated_paper_trading` | `tw-stock-tool simulated-paper-trading` / `simulated_paper_trading.py` | Not yet centralized | `PaperTradingResult` | JSON / CSV / Markdown | `data_loader.download_tw_stock` | `schema_version = 3` | `timestamp`, `strategy` |
| **Multi-Symbol Portfolio Trading** | `tw_stock_tool.cli.run_simulated_portfolio_trading` | `tw-stock-tool simulated-portfolio-trading` / `simulated_portfolio_trading.py` | Not yet centralized | `PortfolioResult` | JSON / CSV / Markdown | `data_loader.download_tw_stock` | `schema_version = 1` | `timestamp`, `initial_cash` |

*註：`GUI Entrypoint` 目前由 Tkinter UI 控制層依工作流程獨立調用，尚未收攏至統一的 Application Service。*

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
    canonical_symbols: list[str]  # e.g., ["2330.TW", "2317.TW"]
    period: str  # e.g., "1y"
    interval: str  # e.g., "1d"
    auto_adjust: bool  # resolved boolean value (DEFAULT_AUTO_ADJUST resolved)
    force_refresh: bool  # resolved boolean value
    strategy: str | None  # e.g., "ma_cross", "rsi", "macd", "score"
    backtest: dict[str, Any] | None  # e.g., {"initial_capital": 100000.0, "fee_rate": 0.001425}
    parameter_sweep: dict[str, Any] | None
    walk_forward: dict[str, Any] | None
    ml: dict[str, Any] | None
    workflow_options: dict[str, Any]  # additional resolved workflow flags
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
    path: str  # normalized relative path string
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
    tool_version: str  # Package version (e.g., "0.1.0")
    status: str  # Enum: "success" | "partial" | "failure"
    config: RunConfig
    data_sources: list[DataSourceRecord]
    success_count: int
    failure_count: int
    partial_count: int
    artifacts: list[ArtifactReference]
    errors: list[str]
    limitations: list[str]
```

*限制：Status Enum 僅包含 `"success"`, `"partial"`, `"failure"`。不包含 `"running"` 狀態；執行中的進度管理由 Application Service 負責處理。*

### 5.5 ResearchRunResult

* **責任**：作為 Application Service 在記憶體內（in-memory）回傳的整體結果邊界物件。

```python
class ResearchRunResult:
    manifest: RunManifest
    domain_result: Any | None  # existing domain model (e.g. BacktestResult, DailyReport, DataFrame)
    generated_artifacts: list[ArtifactReference]
```

*限制：`ResearchRunResult` 僅用於 Application Service 的記憶體交接，不取代既有 domain result models，也不作為新的 universal trading result model。*

---

## 6. Field Contracts

### 6.1 Run ID 契約

* **格式**：UUID Version 4 Canonical Lowercase String（例如：`"f81d4fae-7dec-11d0-a765-00a0c91e6bf6"`）。
* **原則**：不得單獨使用股票代號、策略名稱或時間戳作為唯一 Run ID。

### 6.2 Timestamp 契約

* **格式**：UTC RFC 3339 Timestamp，精確至秒，且必須以字母 `Z` 結尾（例如：`"2026-07-27T20:00:00Z"`）。
* **原則**：不得包含本機時區（Local Timezone）偏移渲染（如 `+08:00`）。

### 6.3 Schema Version 契約

* **`RunManifest.schema_version`**：固定為字串 `"1.0"`。
* **層級區隔**：
  * `schema_version` (`"1.0"`)：專指 Run Manifest 結構的版本。
  * `tool_version` (`"0.1.0"`)：專指 `tw_stock_tool` 套件版本。
  * `ArtifactReference.schema_version` (如整數 `1` 或 `3`)：專指各個產出的 domain artifact 本身的 schema 版本。

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
└── artifacts: list[ArtifactReference]
```

### 關聯原則

1. **不修改舊 Schema**：不得為了併入 Run 概念而修改既有 domain artifacts（如 Daily Report JSON, Backtest Result JSON）的結構去強制注入 `run_id`。
2. **不內嵌 Payload**：`RunManifest` 的 `artifacts` 串列僅記錄 `ArtifactReference`，絕不內嵌整個 artifact 的檔案內容。
3. **離線驗證解耦**：驗證 artifact 檔案存在或讀取內容時，不得觸發工作流程重新執行。
4. **Serializer 解耦**：`RunManifest` 的序列化器不得直接依賴特定的 Daily 或 Backtest domain result classes。

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
