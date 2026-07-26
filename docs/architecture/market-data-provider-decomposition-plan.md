# Phase 55.1A: Market Data Provider Decomposition Audit & Contract Planning

> **PHASE:** 55.1A  
> **PHASE_TYPE:** PLANNING_AND_DOCUMENTATION_ONLY  
> **PRODUCTION_CODE_CHANGED:** NO  
> **TEST_CODE_CHANGED:** NO  
> **RUNTIME_BEHAVIOR_CHANGED:** NO  
> **CLI_BEHAVIOR_CHANGED:** NO  
> **DATA_PROVIDER_ORDER_CHANGED:** NO  
> **CACHE_POLICY_CHANGED:** NO  
> **ERROR_CONTRACT_CHANGED:** NO  
> **EXTRACTION_STARTED:** NO  
> **PHASE_55_1B_STARTED:** NO  
> **MERGE_GATE:** HOLD  

---

## 一、Purpose and Baseline

本文件為 Phase 55.1A 的現況稽核與拆分契約規劃報告。

### 1.1 Baseline 資訊

* **Repository:** `Mike87117/tw_stock_tool`
* **Base branch:** `agent/docs-product-architecture-roadmap`
* **Expected stacked base HEAD:** `e32d184094e6524a265e6768af7de09cb4393b6a`
* **Phase branch:** `phase-55-1a-market-data-provider-planning`
* **Existing Draft PR:** `#44` (stacked on PR `#43`)
* **Scope Limit:** 本 Phase 為 pure architecture audit & contract documentation。不得修改任何 production code 或 test code，不得提前執行 Provider 拆分或新增 Provider 模組。

---

## 二、Authoritative Source-of-Truth Hierarchy

判斷現況時遵循以下嚴格優先順序：

1. **目前 branch 的 production runtime source** ([`data_loader.py`](../../src/tw_stock_tool/data/data_loader.py), [`cache_runtime.py`](../../src/tw_stock_tool/data/cache_runtime.py) 等)
2. **目前 test suite** ([`test_data_loader.py`](../../tests/test_data_loader.py) 及相關測試)
3. **`pyproject.toml` 與 package/CLI entrypoints**
4. **現行 user/developer documentation** ([`DATA_PROVIDER_CACHE_BOUNDARY_CONTRACT.md`](../DATA_PROVIDER_CACHE_BOUNDARY_CONTRACT.md), [`data-and-cache.md`](../user-guide/data-and-cache.md) 等)
5. **Git history 與最近 merged PRs** (`dddb0c1`, `23aa63e`, `5eee347` 等)
6. **歷史 Phase / Track 文件**
7. **LLM Wiki** (僅作輔助，不得覆蓋 repository evidence)

---

## 三、LLM Wiki Check

* **Health Check & Status:** LLM Wiki / CLI 工具 (`wiki` / `agy`) 在本機執行環境中未安裝或未設定。
* **Active Project:** N/A (CLI unavailable)
* **搜尋結果:** 不適用 (CLI unavailable)
* **處理原則:** 依照規範，Wiki 無法使用時不停止整個 Phase，而是明確記錄限制，並 100% 以 repository 原始碼、測試與 git commit 歷史為權威依據。

---

## 四、Current Data-Loading Architecture

現行資料載入入口為 [`download_tw_stock`](../../src/tw_stock_tool/data/data_loader.py)，作為 fallback orchestration facade。

### 4.1 Orchestration 流程

```text
download_tw_stock(stock_id, period="1y", interval="1d", auto_adjust=None, force_refresh=False, verbose=False)
│
├── 1. _validate_inputs (驗證 stock_id, period, interval)
├── 2. _symbol_candidates (解析候選符號：如 "2330" -> [("2330.TW", "2330", ".TW"), ("2330.TWO", "2330", ".TWO")])
│
├── 3. Fresh Cache 階段 (若 !force_refresh)
│    └── 依序對 candidates 檢查 _is_cache_fresh(cache_path)
│         └── 若 fresh 則 _read_cache -> _prepare_ohlcv 並回傳
│         └── 若讀取失敗則紀錄 error，繼續嘗試下一個
│
├── 4. Yahoo Finance (yfinance) 階段
│    └── 依序對 candidates 呼叫 _download_yfinance_quiet(symbol, period, interval, auto_adjust)
│         └── 若 returned DataFrame 非空 -> _prepare_ohlcv -> 嘗試 _write_cache (非致命) -> 回傳
│         └── 若 returned DataFrame 為空或拋出 Exception -> 紀錄 error，嘗試下個 candidate
│
├── 5. Official Fallback 階段 (僅當 !auto_adjust 時啟用)
│    └── 依序對 candidates 呼叫 _download_official_stock(base_stock_id, suffix, period, interval)
│         ├── suffix == ".TW" -> _download_twse_stock (僅限 interval=="1d")
│         └── suffix == ".TWO" -> _download_tpex_stock (僅限 interval=="1d")
│              └── 若月報表無資料 -> _download_tpex_latest_quote (OpenAPI fallback)
│         └── 成功取得 -> _write_cache (非致命) -> 回傳
│         └── 失敗拋出 Exception -> 紀錄 error
│
├── 6. Stale Cache 階段 (若 !force_refresh 且 live 來源全數失敗)
│    └── 依序對 candidates 檢查 cache_path.exists()
│         ├── _get_cache_age_days(cache_path) <= MAX_STALE_CACHE_DAYS (14天)
│         └── 成功 _read_cache -> 輸出 sys.stderr [WARNING] 警告 -> 回傳
│         └── 若超過 14 天或讀取失敗 -> 紀錄 error
│
└── 7. 失敗彙整階段
     └── 拋出 _format_no_data_error 統一封裝的 DataLoaderError
```

---

## 五、Current Function Responsibility Inventory

對目前 [`data_loader.py`](../../src/tw_stock_tool/data/data_loader.py) 中所有 23 個函式進行權責與拆分建議分類：

| Function Name | Current Responsibility | Direct Dependencies | Primary Caller | Patch / Monkeypatch Surface | User-Visible Behavior | Extraction Risk | Recommended Category |
|---|---|---|---|---|---|---|---|
| `_normalize_columns` | 展平 MultiIndex 欄位 | `pandas` | `_prepare_ohlcv` | 無直接測試 patch | 影響列名與 index 結構 | Low | `SHARED_NORMALIZATION` |
| `_validate_inputs` | 股票代碼、period、interval 輸入合法性檢查 | `VALID_PERIODS`, `VALID_INTERVALS` | `download_tw_stock` | 測試有單元測試呼叫 | 非法輸入丟出 `DataLoaderError` | Low | `KEEP_IN_FACADE` |
| `_cache_path` | 產生快取檔案路徑 | `_cache_runtime._cache_path`, `CACHE_DIR` | `download_tw_stock`, 測試 | `tests/test_data_loader.py` direct call | 快取檔名格式 | High (patch surface) | `COMPATIBILITY_DELEGATE` |
| `_is_cache_fresh` | 判斷快取是否為當日新鮮 | `_cache_runtime._is_cache_fresh` | `download_tw_stock`, 測試 | `tests/test_data_loader.py` patch/call | 判斷 14:30 市場關閉收盤快取 | High (patch surface) | `COMPATIBILITY_DELEGATE` |
| `_get_cache_age_days` | 計算快取檔案天數 | `_cache_runtime._get_cache_age_days` | `download_tw_stock`, 測試 | `tests/test_data_loader.py` patch/call | stale cache 警示天數 | High (patch surface) | `COMPATIBILITY_DELEGATE` |
| `_read_cache` | 讀取快取 CSV 為 DataFrame | `_cache_runtime._read_cache` | `download_tw_stock`, 測試 | `tests/test_data_loader.py` patch/call | DatetimeIndex named `Date` | High (patch surface) | `COMPATIBILITY_DELEGATE` |
| `_write_cache` | 寫入 DataFrame 至快取 CSV | `_cache_runtime._write_cache` | `download_tw_stock`, 測試 | `tests/test_data_loader.py` patch/call | CSV 寫入 | High (patch surface) | `COMPATIBILITY_DELEGATE` |
| `_prepare_ohlcv` | 檢查與標準化 OHLCV 欄位與 DatetimeIndex | `_normalize_columns`, `pandas` | `download_tw_stock`, official helpers | `tests/test_data_loader.py` direct call | 無效 OHLC/Index 拋出 `DataLoaderError` | Medium | `SHARED_NORMALIZATION` |
| `_period_start` | 依據 period 計算歷史起始 Timestamp | `pandas` | `_download_twse_stock`, `_download_tpex_stock` | `tests/test_data_loader.py` patch.object | 官方下載日期起始點 | Medium | `SHARED_PARSING` |
| `_month_starts` | 產生起迄月份一號清單 | `pandas` | `_download_twse_stock`, `_download_tpex_stock` | `tests/test_data_loader.py` patch.object | 月份迴圈起迄點 | Low | `SHARED_PARSING` |
| `_parse_roc_date` | 民國年日期字串 (YYY/MM/DD) 轉 Timestamp | `pandas` | `_download_twse_stock`, `_parse_tpex_date` | 無直接 patch | 轉成 Gregorian Datetime | Low | `SHARED_PARSING` |
| `_parse_tpex_date` | TPEx 多格式日期解析 (ROC/7碼/8碼) | `_parse_roc_date`, `pandas` | `_download_tpex_stock`, `_download_tpex_latest_quote` | 無直接 patch | 轉成 Gregorian Datetime | Low | `SHARED_PARSING` |
| `_to_float` | 清除逗號/連字號並轉 float | None | official downloads | 無直接 patch | 轉 float 或 NaN | Low | `SHARED_PARSING` |
| `_to_int` | 數值轉整數成交量 | `_to_float` | official downloads | 無直接 patch | 轉 int | Low | `SHARED_PARSING` |
| `_finalize_official_rows` | 官方原始 row 清單去重、排序、過濾、截取與 OHLCV 化 | `_prepare_ohlcv`, `pandas` | `_download_twse_stock`, `_download_tpex_stock`, `_download_tpex_latest_quote` | `tests/test_data_loader.py` direct call | 1d/5d/full 官方資料處理 | Medium | `SHARED_NORMALIZATION` |
| `_download_twse_stock` | 證交所 (TWSE) 網路下載與解析 | `_period_start`, `_month_starts`, `requests.get`, `_parse_roc_date`, `_to_float`, `_to_int`, `_finalize_official_rows` | `_download_official_stock`, 測試 | `tests/test_data_loader.py` patch.object | TWSE HTTP 下載 | High (Provider) | `EXTRACT_CANDIDATE` (TWSE Provider) |
| `_download_tpex_stock` | 櫃買中心 (TPEx) 月報表下載與解析 | `_period_start`, `_month_starts`, `requests.get`, `_parse_tpex_date`, `_to_float`, `_to_int`, `_finalize_official_rows`, `_download_tpex_latest_quote` | `_download_official_stock`, 測試 | `tests/test_data_loader.py` patch.object | TPEx HTTP 月報表下載 | High (Provider) | `EXTRACT_CANDIDATE` (TPEx Provider) |
| `_download_tpex_latest_quote` | TPEx OpenAPI 當日最新行情單頁 fallback | `requests.get`, `_parse_tpex_date`, `_to_float`, `_to_int`, `_finalize_official_rows` | `_download_tpex_stock` | `tests/test_data_loader.py` patch.object | TPEx OpenAPI 下載 | High (Provider) | `EXTRACT_CANDIDATE` (TPEx Provider) |
| `_download_official_stock` | 官方資料下載分發點 | `_download_twse_stock`, `_download_tpex_stock` | `download_tw_stock`, 測試 | `tests/test_data_loader.py` patch.object | 依 `.TW`/`.TWO` 分發 | Medium | `ORCHESTRATION_ONLY` |
| `_symbol_candidates` | 依據輸入產生候選市場符號元組 | None | `download_tw_stock` | 無直接 patch | 元組清單 | Low | `KEEP_IN_FACADE` |
| `_download_yfinance_quiet` | yfinance 下載與標準輸出/錯誤/Logger 靜音與 Thread 鎖 | `console_io_lock`, `redirect_stdout`, `redirect_stderr`, `yf.download`, `logging.getLogger` | `download_tw_stock`, 測試 | `tests/test_data_loader.py`, `test_scanner.py` patch.object | 靜音下載與 process-wide lock | High (Provider) | `EXTRACT_CANDIDATE` (Yahoo Provider) |
| `_format_no_data_error` | 格式化 `DataLoaderError` 錯誤訊息 | `DataLoaderError` | `download_tw_stock` | 測試檢查錯誤訊息文字 | 統一 exception 訊息 | Medium | `KEEP_IN_FACADE` |
| `download_tw_stock` | 主進入點 Orchestration Facade | All helpers | CLI, `analysis.py`, `clean_stocks.py`, `price_data_smoke_check.py`, tests | 外部主呼叫進入點 | 回傳 `(pd.DataFrame, str)` | High (Facade) | `KEEP_IN_FACADE` |

---

## 六、Existing Cache-Runtime Extraction Status

經檢視 Git history (`dddb0c1b0b30733722292fab1eb7debdd2e1e2d3`, `23aa63e6e756dda7695a8ab7e66d1aa184afa059`, `5eee34738d9d46c9c0c4ac9a9732d3843f882885`) 與現行程式碼：

1. **已完成事項：**
   * 快取底層邏輯已經抽取至 [`cache_runtime.py`](../../src/tw_stock_tool/data/cache_runtime.py)。
   * `cache_runtime.py` 實作了 `_cache_path`, `_is_cache_fresh`, `_get_cache_age_days`, `_read_cache`, `_write_cache`。
2. **`data_loader.py` 現狀：**
   * 保留同名的相容性代理函式 (compatibility delegates)，例如：
     ```python
     def _cache_path(symbol: str, period: str, interval: str, auto_adjust: bool) -> Path:
         return _cache_runtime._cache_path(symbol, period, interval, auto_adjust, cache_dir=CACHE_DIR)
     ```
   * 如此設計係為了維持 [`test_data_loader.py`](../../tests/test_data_loader.py) 中直接 patch `data_loader._cache_path` 或 `data_loader._is_cache_fresh` 的測試能力與向下相容性。
3. **本 Phase 原則：**
   * 不得撤銷或重做此已完成之抽取。
   * 未來 Provider 拆分時亦需參考此 Compatibility Delegate 模式，保護既存測試 patch surface。

---

## 七、Caller and Patch-Surface Inventory

### 7.1 Runtime Callers Inventory

| Tracked File | imported Surface | Usage | Arguments | Return Values | Error Handling | Compatibility Dependency |
|---|---|---|---|---|---|---|
| `src/tw_stock_tool/analysis/analysis.py` | `download_tw_stock` | Direct | `stock_id, period, interval` | `(df, symbol)` | 向上拋出 `DataLoaderError` | 依賴元組結構與 `DataLoaderError` |
| `src/tw_stock_tool/cli/clean_stocks.py` | `download_tw_stock` | Direct | `stock_id, period` | `(df, symbol)` | 捕捉 `DataLoaderError` 記錄無效股票 | 依賴元組結構與異常型別 |
| `src/tw_stock_tool/cli/price_data_smoke_check.py` | `data_loader.download_tw_stock` | Direct live check | `stock_id, period, interval` | `(df, symbol)` | 捕捉例外並記錄 smoke check 失敗 | 依賴 facade 進入點 |
| `src/tw_stock_tool/analysis/scanner.py` | via `analyze_stock` | Indirect | Via analysis | `analysis_dict` | 內部捕捉並排版錯誤 | 依賴 `analysis.py` 介面 |
| `src/tw_stock_tool/gui/app_services.py` | via `analyze_stock` | Indirect | Via analysis | `analysis_dict` | UI 錯誤提示 | 依賴 `analysis.py` 介面 |
| `tests/test_data_loader.py` | `data_loader` module & private helpers | Direct & Monkeypatch | Various | Various | Assertions | 依賴 `data_loader` 的模組級物件與私有函式 |

### 7.2 Major Patch-Surface Inventory

| Patch Target | Current Test Usage Path | Reason Used in Tests | Risk of Breaking upon Extraction | Compatibility Strategy Required | Characterization Gap Status | Allowed / Forbidden Observable Behavior Changes |
|---|---|---|---|---|---|---|
| `data_loader.yf.download` | `patch.object(data_loader.yf, "download", ...)` | 模擬 yfinance 網路回應 | High | `data_loader.py` 需保有 `yf` 或代理，否則 `patch.object` 失敗 | COVERED (Current inline implementation) | **Forbidden:** 不得改變靜音、鎖控、及傳入 `yf.download` 的參數與順序 |
| `data_loader.requests.get` | `patch.object(data_loader.requests, "get", ...)` | 模擬 TWSE/TPEx 網路回應 | High | `data_loader.py` 需保有 `requests` 或代理，或將官方 provider 作為內部可 patch 屬性 | COVERED | **Forbidden:** 不得改變 URL, query params, headers, timeout |
| `data_loader._download_yfinance_quiet` | `patch.object(data_loader, "_download_yfinance_quiet")` | 隔離 yfinance 測試 fallback 邏輯 | High | `data_loader.py` 必須保留 `_download_yfinance_quiet` 代理函式 | COVERED (Current inline implementation) | **Forbidden:** 不得改變 quiet 輸出 suppression 與鎖控 |
| `data_loader._download_twse_stock` | `patch.object(data_loader, "_download_twse_stock")` | 測試 TPEx fallback 的單元切換 | High | `data_loader.py` 必須保留 `_download_twse_stock` 代理函式 | COVERED | **Forbidden:** 不得改變 TWSE 下載邏輯與月報表過濾 |
| `data_loader._download_tpex_stock` | `patch.object(data_loader, "_download_tpex_stock")` | 測試 6488 上櫃股票 fallback | High | `data_loader.py` 必須保留 `_download_tpex_stock` 代理函式 | COVERED | **Forbidden:** 不得改變 TPEx 月報表與 OpenAPI quote 轉接 |
| `data_loader._download_official_stock` | `patch.object(data_loader, "_download_official_stock")` | 測試 auto_adjust=False 進入官方 fallback | High | `data_loader.py` 必須保留 `_download_official_stock` 代理函式 | COVERED | **Forbidden:** 不得改變 `.TW`/`.TWO` 官方轉接通道 |
| `data_loader.CACHE_DIR` | `patch.object(data_loader, "CACHE_DIR", Path(tmp_dir))` | 將測試快取隔離在臨時目錄 | High | `data_loader.py` 必須繼續引用並允許 patch `CACHE_DIR` | COVERED | **Forbidden:** 快取檔名與目錄結構不得改變 |
| `pd.Timestamp.now` | `patch.object(data_loader.pd.Timestamp, "now", ...)` | 測試 14:30 收盤前後快取新鮮度 | High | 內部需繼續透過 `pd.Timestamp.now` 或可測試時間來源 | COVERED | **Forbidden:** 快取 14:30 判定時間基準不得改變 |
| `console_io_lock` | `with console_io_lock():` | 防止多執行緒控制台輸出交錯 | Medium | Provider 必須續用 `tw_stock_tool.utils.console_lock` | COVERED | **Forbidden:** 多執行緒下不可交錯 stdout/stderr 輸出 |

---

## 八、Provider Seam Comparison Matrix

本 Phase 針對 5 種可能的拆分方案進行完整評估：

```text
Option A: 先抽出 Yahoo Finance Provider
Option B: 先抽出 TWSE Provider
Option C: 先抽出 TPEx Provider
Option D: 先抽出 Shared Official Parsing / Normalization
Option E: 一次抽出全部 Providers (Big Bang Extraction)
```

### 8.1 方案詳細評估

| Evaluation Aspect | Option A: Yahoo Provider | Option B: TWSE Provider | Option C: TPEx Provider | Option D: Shared Normalization / Parsing | Option E: All-at-once Big Bang |
|---|---|---|---|---|---|
| **Cohesion (凝聚度)** | **High** (純粹 Yahoo 下載與靜音鎖控) | Medium (依賴月報表與日期解析) | Medium (依賴月報表 + OpenAPI 雙層 fallback) | High (純數據轉換與格式解析) | Low (同時跨多個獨立數據源) |
| **Direct Seam Cleanliness** | **Clean** (輸入 `symbol, period, interval, auto_adjust` -> `DataFrame`) | Requires shared helpers (`_period_start`, `_month_starts`, `_parse_roc_date`) | Requires shared helpers (`_period_start`, `_month_starts`, `_parse_tpex_date`, latest quote) | Pure utility functions | Very complex multi-module boundaries |
| **Existing Patch Surface Impact** | Moderate (需維護 `yf.download` 與 `_download_yfinance_quiet` delegates) | Moderate (需維護 `requests.get` 與 `_download_twse_stock` delegates) | Moderate (需維護 `requests.get` 與 `_download_tpex_stock` delegates) | Low | **Extremely High** (同時影響所有測試 patch) |
| **Circular Dependency Risk** | **None** | Moderate (若 Helper 留在 `data_loader.py` 則會反向引用) | Moderate (若 Helper 留在 `data_loader.py` 則會反向引用) | **None** | High |
| **Characterization Test Readiness** | **HIGH** (五個方案中測試準備度最高) | MEDIUM (月報表解析缺部份邊界測試) | LOW (OpenAPI quote 部分缺乏直連獨立測試) | MEDIUM | LOW (總體風阻極大) |
| **Blast Radius (衝擊範圍)** | **Low** (僅影響 yfinance 下載階段) | Medium (僅影響上市 fallback) | Medium (僅影響上櫃 fallback) | Low (但影響全體輸出格式) | **Maximum** (整個 data 模組被拆解) |
| **Recommendation** | **RECOMMENDED (1st Choice)** | Deferred to 3rd | Deferred to 4th | RECOMMENDED (2nd Choice or accompanying helper module) | **REJECTED** |

---

## 九、Characterization Gap Matrix

針對各數據源與流程的 characterization test 覆蓋狀況進行全盤盤點：

### 9.1 Yahoo Finance Characterization

| Requirement / Scenario | Description | Coverage Status | Action for Phase 55.1B |
|---|---|---|---|
| Forwarded Arguments | 正確轉送 `symbol, period, interval, auto_adjust, progress=False, threads=False` | **COVERED** ([`test_download_yfinance_quiet_calls_yfinance_download`](../../tests/test_data_loader.py#L131)) | NOT_REQUIRED_FOR_FIRST_SEAM |
| Empty DataFrame Return | yfinance 回傳空 DataFrame 時正常處理為失敗 | **COVERED** ([`test_all_yfinance_failures_are_quiet_until_unified_error`](../../tests/test_data_loader.py#L227)) | NOT_REQUIRED_FOR_FIRST_SEAM |
| Exception Handling | yfinance 拋出 Exception 時靜音、釋放鎖、恢復 logger 狀態並傳播例外 | **COVERED** ([`test_tpex_wrapper_and_logger_contracts`](../../tests/test_data_loader.py#L612) line 621 `side_effect=RuntimeError("boom")`) | NOT_REQUIRED_FOR_FIRST_SEAM |
| Quiet Stdout/Stderr | 過程輸出被 `redirect_stdout` / `redirect_stderr` 攔截 | **COVERED** ([`test_download_yfinance_quiet_suppresses_output`](../../tests/test_data_loader.py#L154)) | NOT_REQUIRED_FOR_FIRST_SEAM |
| Logger Restoration on Success | 成功下載後恢復預設或自訂之 `yfinance` logger 狀態 (`disabled`, `level`, `propagate`) | **PARTIALLY_COVERED** | **BLOCKING_PHASE_55_1B** (新增成功路徑自訂 logger 恢復測試) |
| Logger Restoration on Exception | 拋出 Exception 時 `finally` 仍確保恢復 `yfinance` logger 狀態 | **COVERED** ([`test_tpex_wrapper_and_logger_contracts`](../../tests/test_data_loader.py#L612) line 621 `side_effect=RuntimeError("boom")`) | NOT_REQUIRED_FOR_FIRST_SEAM |
| Thread Safety | 多執行緒下 `console_io_lock` 確保靜音與輸出不交錯 | **COVERED** ([`test_download_yfinance_quiet_is_thread_safe`](../../tests/test_data_loader.py#L175)) | NOT_REQUIRED_FOR_FIRST_SEAM |
| `auto_adjust=True` Forwarding | 正確轉送 `auto_adjust=True` 參數至 `yf.download` | **COVERED** ([`test_download_yfinance_quiet_calls_yfinance_download`](../../tests/test_data_loader.py#L131)) | NOT_REQUIRED_FOR_FIRST_SEAM |
| `auto_adjust=False` Forwarding | 正確轉送 `auto_adjust=False` 參數至 `yf.download` | **PARTIALLY_COVERED** | **BLOCKING_PHASE_55_1B** (新增 `auto_adjust=False` 精確轉送斷言) |
| Existing Patch Compatibility (Current Inline) | 現行 `data_loader.yf.download` 與 `data_loader._download_yfinance_quiet` 可被 monkeypatch | **COVERED** (現行測試套件) | **BLOCKING_PHASE_55_1B** (凍結現行可測試介面合約) |
| Future Compatibility Delegate after Extraction | 抽取後之 Provider 相容性代理介面 | **NOT_YET_IMPLEMENTED** | N/A (留待 Phase 55.1C 實作) |

### 9.2 TWSE Characterization

| Requirement / Scenario | Description | Coverage Status | Action for Future Phases |
|---|---|---|---|
| Target Endpoint URL | HTTP 請求至 `https://www.twse.com.tw/exchangeReport/STOCK_DAY` | **COVERED** ([`test_twse_fallback_when_yfinance_has_no_data`](../../tests/test_data_loader.py#L59)) | NOT_REQUIRED_FOR_PHASE_55_1B |
| Query Parameters | 帶入 `response=json`, `date=YYYYMM01`, `stockNo=ID` | **COVERED** | NOT_REQUIRED_FOR_PHASE_55_1B |
| Timeout & HTTP error | `timeout=20`, 支援 `raise_for_status` | **PARTIALLY_COVERED** | **BLOCKING_FUTURE_TWSE_EXTRACTION** |
| `stat != OK` handling | 忽略非 OK 月份繼續迴圈 | **PARTIALLY_COVERED** | **BLOCKING_FUTURE_TWSE_EXTRACTION** |
| ROC Date Parsing | 民國 115/06/18 解析為 2026-06-18 | **COVERED** ([`test_twse_fallback_when_yfinance_has_no_data`](../../tests/test_data_loader.py#L59)) | NOT_REQUIRED_FOR_PHASE_55_1B |
| Numeric Commas | `"1,000"` 千分位點正確轉換為 `1000.0` | **COVERED** | NOT_REQUIRED_FOR_PHASE_55_1B |
| Non-1d Interval Rejection | `interval != "1d"` 時拋出 `DataLoaderError` | **COVERED** ([`test_official_fallback_interval_limitation_is_in_error_message`](../../tests/test_data_loader.py#L454)) | NOT_REQUIRED_FOR_PHASE_55_1B |

### 9.3 TPEx Characterization

| Requirement / Scenario | Description | Coverage Status | Action for Future Phases |
|---|---|---|---|
| Target Endpoint URL | HTTP 請求至 `https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock` | **COVERED** ([`test_tpex_wrapper_and_logger_contracts`](../../tests/test_data_loader.py#L612)) | NOT_REQUIRED_FOR_PHASE_55_1B |
| OpenAPI Latest Quote Endpoint | `https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes` | **COVERED** ([`test_tpex_latest_quote_success_and_no_match`](../../tests/test_data_loader.py#L748)) | NOT_REQUIRED_FOR_PHASE_55_1B |
| Latest Quote Called Exactly Once | 當月報表全空時，呼叫 latest quote fallback 恰好一次 | **COVERED** ([`test_tpex_monthly_empty_calls_latest_quote_once`](../../tests/test_data_loader.py#L737)) | NOT_REQUIRED_FOR_PHASE_55_1B |
| Two Date Formats | 支援 ROC "/" 分隔與 7碼/8碼 純數字字串 | **PARTIALLY_COVERED** | **BLOCKING_FUTURE_TPEX_EXTRACTION** |
| No Matching Quote Exception | OpenAPI 回傳資料無匹配股票時拋出 `DataLoaderError` | **COVERED** ([`test_tpex_latest_quote_success_and_no_match`](../../tests/test_data_loader.py#L748)) | NOT_REQUIRED_FOR_PHASE_55_1B |

### 9.4 Shared Orchestration Characterization

| Requirement / Scenario | Description | Coverage Status | Action for Phase 55.1B / Future |
|---|---|---|---|
| Unsuffixed Attempt Order | 無字尾股票依序嘗試 `.TW` 再 `.TWO` | **COVERED** ([`test_numeric_symbol_tries_two_after_tw_yfinance_empty`](../../tests/test_data_loader.py#L110)) | NOT_REQUIRED_FOR_PHASE_55_1B |
| Explicit Suffix Behavior | 指定 `.TW` 時不得切換至 `.TWO` (反之亦然) | **COVERED** ([`test_explicit_tw_does_not_try_two`](../../tests/test_data_loader.py#L268), [`test_explicit_two_does_not_try_tw`](../../tests/test_data_loader.py#L286)) | NOT_REQUIRED_FOR_PHASE_55_1B |
| Official Only When `auto_adjust=False` | `auto_adjust=True` 時跳過官方 fallback 直奔 stale cache / error | **COVERED** ([`test_auto_adjust_skips_official_fallback`](../../tests/test_data_loader.py#L344)) | NOT_REQUIRED_FOR_PHASE_55_1B |
| Non-fatal Cache Write Failure | 快取寫入拋出例外時不破壞已下載之資料回傳 | **COVERED** ([`test_yfinance_cache_write_failure_is_non_fatal`](../../tests/test_data_loader.py#L433)) | NOT_REQUIRED_FOR_PHASE_55_1B |
| Stale Cache Rejection Boundary | 超過 14 天之快取拋出例外拒絕使用 | **COVERED** ([`test_stale_cache_older_than_threshold_is_rejected_and_raises`](../../tests/test_data_loader.py#L522)) | NOT_REQUIRED_FOR_PHASE_55_1B |
| Stale Cache Stderr Warning Channel | 使用符合期限之 Stale Cache 時明確向 `sys.stderr` 輸出 `[WARNING]` | **COVERED** ([`test_download_falls_back_to_stale_cache_when_live_fetch_fails`](../../tests/test_data_loader.py#L466)) | NOT_REQUIRED_FOR_PHASE_55_1B |
| `force_refresh` Bypass | `force_refresh=True` 完整跳過 fresh 與 stale 快取讀取 | **COVERED** ([`test_force_refresh_bypasses_stale_cache_fallback`](../../tests/test_data_loader.py#L537)) | NOT_REQUIRED_FOR_PHASE_55_1B |
| Unified DataLoaderError Message | 失敗訊息包含嘗試之符號清單與失敗原因組合 | **COVERED** ([`test_no_data_error_lists_tried_symbols`](../../tests/test_data_loader.py#L304)) | NOT_REQUIRED_FOR_PHASE_55_1B |

---

## 十、Recommended First Extraction Seam

基於上述客觀檢視，本報告推薦 **Option A (Yahoo Finance Provider)** 作為第一個 Production Extraction Seam。

### 10.1 Why Option A First?

1. **職責單純且獨立：** Yahoo Finance 是目前主要的外部價格資料來源，無須依賴 TWSE/TPEx 特有的民國年解析、月報表拆解與 OpenAPI fallback 邏輯。 (註：本產品不提供極速即時、保證最新或投資等級之資料承諾。)
2. **具備高測試準備度：** 靜音 (suppression)、鎖控 (locking)、執行緒安全 (thread-safety) 與例外恢復 (logger restoration on exception) 已具備現存高度測試覆蓋。
3. **無循環依賴風險：** 其介面為純粹的 `(symbol, period, interval, auto_adjust) -> pd.DataFrame`。

### 10.2 Future Seams

* **TWSE / TPEx Providers:** 延後至未來獨立 Phase (`BLOCKING_FUTURE_TWSE_EXTRACTION` / `BLOCKING_FUTURE_TPEX_EXTRACTION`)。
* **Shared Normalization / Parsing:** 可於未來作為獨立內部工具抽取，或與官方 Provider 一併處理。
* **Orchestration Facade (`download_tw_stock`):** 永久保留在 `data_loader.py`，作為公開 API 進入點。

---

## 十一、Phase 55.1B Scope (Tests-Only Yahoo Provider Characterization)

本 Phase 定義下一個 Phase (Phase 55.1B) 的精確範圍。**本 Phase 不得執行 Phase 55.1B 的任何工作。**

```text
PHASE: 55.1B
PHASE_TYPE: TESTS_ONLY_YFINANCE_PROVIDER_CHARACTERIZATION
PRODUCTION_CODE_CHANGED: NO
PROVIDER_EXTRACTION_STARTED: NO
MERGE_GATE: HOLD
```

### 11.1 Allowed Scope & Tests to Add in Phase 55.1B

Phase 55.1B 的目的**僅限於保護下一個 Yahoo Provider extraction**。在不修改任何 production code 的前提下，僅允許於 [`tests/test_data_loader.py`](../../tests/test_data_loader.py) 中新增以下 6 項 characterization tests：

1. **Logger Restoration on Success Test:**
   * 預先設定非預設 logger 狀態 (`disabled=False`, `level=logging.WARNING`, `propagate=True`)。
   * 讓 `yf.download` 成功回傳 DataFrame。
   * 呼叫 `_download_yfinance_quiet`。
   * 斷言 `disabled`, `level`, `propagate` 完整恢復至呼叫前狀態。
2. **`auto_adjust=False` Exact Forwarding Test:**
   * 顯式斷言當 `auto_adjust=False` 傳入時，`yf.download` 收到的 kwargs 中確實包含 `auto_adjust=False`。
3. **`data_loader.yf.download` Monkeypatch Contract Test:**
   * 驗證對 `data_loader.yf.download` 進行 `patch.object` 時能正確攔截並回傳模擬 DataFrame。
4. **`data_loader._download_yfinance_quiet` Monkeypatch Contract Test:**
   * 驗證對 `data_loader._download_yfinance_quiet` 進行 `patch.object` 時能正確攔截並傳回模擬 DataFrame。
5. **Yahoo Exception Cleanup Test:**
   * 驗證當 `yf.download` 拋出例外時，`console_io_lock` 正確釋放、logger 狀態恢復、且 stdout/stderr 無任何殘留或流失。
6. **Subsequent Call Lock Release Verification Test:**
   * 在拋出 Exception 之後隨即進行第二次 `_download_yfinance_quiet` 呼叫，證明進程鎖 (process lock) 未遭死鎖 (deadlock) 且可再次正常完成。

### 11.2 Allowed File for Phase 55.1B

只允許修改：
```text
tests/test_data_loader.py
```

明確禁止修改：
```text
src/**
docs/**
pyproject.toml
README.md
CHANGELOG.md
.github/**
```

---

## 十二、Candidate Scope for Phase 55.1C (Production Yahoo Extraction)

本章節記錄未來 Phase 55.1C (Production Extraction) 的候選範圍與契約要求。**本 Phase 不得執行 Phase 55.1C。**

### 12.1 Phase 55.1C Candidate Allowed Scope

預計允許修改/新增之檔案：
```text
src/tw_stock_tool/data/providers/__init__.py
src/tw_stock_tool/data/providers/yfinance_provider.py
src/tw_stock_tool/data/data_loader.py
tests/test_data_loader.py
```

### 12.2 Phase 55.1C Explicit Forbidden Scope

明確禁止修改：
```text
src/tw_stock_tool/data/cache_runtime.py
src/tw_stock_tool/data/cache_utils.py
src/tw_stock_tool/data/cache_manager.py
TWSE provider code
TPEx provider code
official parsing helpers
download_tw_stock orchestration order
cache policy
error aggregation
CLI / GUI / reports / backtesting / paper trading / risk modules
```

### 12.3 Phase 55.1C Compatibility Requirements

1. **Compatibility Delegate:** `data_loader.py` 必須保留同名代理函式 `_download_yfinance_quiet`：
   ```python
   def _download_yfinance_quiet(symbol: str, period: str, interval: str, auto_adjust: bool) -> pd.DataFrame:
       return yfinance_provider.download_yfinance_quiet(symbol, period, interval, auto_adjust)
   ```
2. **Patch Surface Preservation:** `data_loader.py` 必須保留 `import yfinance as yf` 模組物件或明確轉接點，確保既存測試對 `data_loader.yf.download` 的 `patch.object` 依然有效。
3. **No Early-Bound Imports:** 新建立的 Provider 模組或 `data_loader.py` 不得使用早綁定匯入 (如 `from yfinance import download`)，否則會繞過既有 `yf.download` 的模組級 patch。
4. **Facade Delegation Path:** `download_tw_stock(...)` 不得直接繞過 `data_loader._download_yfinance_quiet` 代理函式，否則既存外部測試對 `data_loader._download_yfinance_quiet` 的 patch contract 將會失效。

---

## 十三、Rollback Strategy & Non-Goals

### 13.1 Rollback Strategy

若未來的 Provider 抽取 Phase 發生非預期的測試破壞或相容性問題：
1. 可直接恢復 `data_loader.py` 內的原始 inline 實作。
2. 由於 `data_loader.py` 保留了完整的 Compatibility Delegates，外部 Caller (`analysis.py`, CLI 等) 介面無須作任何改動。

### 13.2 Explicit Non-Goals for Phase 55.1

* 不修改任何交易、回測、風控、或 artifact 運算語意。
* 不改變預設快取目錄或快取檔名命名邏輯。
* 不改變 Stale Cache 警示機制與 14 天期限上限。
* 不改變 `.TW` / `.TWO` 嘗試順序與 Fallback 順序。
* 不改變 `download_tw_stock(...)` 的回傳元組 `(pd.DataFrame, str)` 結構。
* 不改變 `DataLoaderError` 拋出條件與統一錯誤文字彙整格式。

---

## 十四、Phase 55.1B Entry & Exit Gates

### 14.1 Entry Gate for Phase 55.1B

* Phase 55.1A Reviewer Gate 通過。

### 14.2 Exit Gate for Phase 55.1B (Entry Gate for Phase 55.1C)

進入 Phase 55.1C (Production Extraction) 的充要條件：
1. Phase 55.1B 新增的 6 項 Yahoo 專屬 characterization tests 全數通過。
2. 既有 [`tests/test_data_loader.py`](../../tests/test_data_loader.py) 測試全數通過。
3. 全套單元測試 (`python -m unittest discover -s tests`) 100% 通過。
4. Reviewer 確認 Yahoo相容性契約 (compatibility contract) 完整無虞。
5. PR `#44` 與 Phase 55.1B 均維持 `MERGE_GATE: HOLD`，等待未來 Production PR 統一處理 stacked merge。

*(註：不需要先完成 TWSE / TPEx characterization 即可啟動 Yahoo extraction。)*

---

## 十五、Decision Summary & Gate Status

```text
PHASE_55_1A_DECISION: AUDIT_REFINED_FOR_YFINANCE_ONLY_SCOPE
RECOMMENDED_FIRST_SEAM: OPTION_A_YFINANCE_PROVIDER
BLOCKING_CHARACTERIZATION_GAPS: IDENTIFIED_FOR_PHASE_55_1B_YFINANCE_ONLY
TWSE_TPEX_CHARACTERIZATION: DEFERRED_TO_FUTURE_PHASES
PRODUCTION_CODE_CHANGED: NO
TEST_CODE_CHANGED: NO
PROVIDER_EXTRACTION_STARTED: NO
PHASE_55_1B_STARTED: NO
MERGE_GATE: HOLD
```
