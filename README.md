# 台股技術分析工具

![Python Tests](https://github.com/Mike87117/tw_stock_tool/actions/workflows/python-tests.yml/badge.svg)

本工具用於台股技術分析、回測、多股票掃描、策略比較與 benchmark 研究。
本專案目前是台股研究 / 回測 / 報告工具，不是自動下單系統，不串接券商 API，不提供保證獲利，不提供買賣建議。

## 目前可用功能摘要

- 單股分析
- 多股票掃描
- Daily Report
- Backtest Report
- Parameter Sweep Report
- Walk Forward Report
- BacktestResult artifact export
- Stock list updater / smoke check
- Cache manager
- Benchmark
- ML dataset / baseline research tools
- 統一 CLI：twstock
- 本機 GUI 原型

## CI

本專案已加入 GitHub Actions：

- workflow: `.github/workflows/python-tests.yml`
- trigger: `push`、`pull_request`
- Python: `3.11`、`3.12`
- command: `python -m unittest discover -s tests`


## 安裝

推薦的安裝方式是安裝套件與統一指令介面 (`twstock`)，以便後續能使用簡潔的指令：

```bash
cd tw_stock_tool
pip install -e .
twstock doctor
```

### 可選：僅安裝相依套件 (Fallback / Development)

如果你只是為了開發、測試或是環境限制，可以只安裝相依套件：

```bash
pip install -r requirements.txt
```

**注意：** 若使用此方式安裝，將無法使用 `twstock` 簡短指令，且所有的操作都必須改為直接執行 Python 腳本（例如 `python twstock_cli.py ...` 或 `python main.py ...`）。

### 輸出與快取路徑設定

工具預設會在當前執行目錄下建立輸出與快取資料夾：
- 預設輸出目錄：`./output`
- 預設快取目錄：`./cache`

你可以透過設定環境變數來覆寫預設路徑：
- `TW_STOCK_TOOL_OUTPUT_DIR`：自訂輸出目錄（例如 `~/.twstock/output`）
- `TW_STOCK_TOOL_CACHE_DIR`：自訂快取目錄（例如 `~/.twstock/cache`）

### 資料來源與快取備援 (Data Source & Cache Resilience)

本工具在抓取資料時採用多層備援機制，以降低因暫時性網路問題或 API 限制而導致的執行中斷。資料抓取的順序為：
1. **Fresh Cache** (當日有效的快取)
2. **Yahoo Finance** (首選即時/歷史資料)
3. **Official TWSE / TPEx** (若不需要還原權值，則回退至官方資料)
4. **Stale Cache Fallback** (過期快取備援，受限於最長天數)
5. 若所有來源均失敗，則拋出 `DataLoaderError`。

**重要提示**：官方 TWSE / TPEx 備援並非完整的還原歷史資料庫，無法完全替代 Yahoo Finance 提供的 `auto_adjust=True` 歷史價格。

#### 過期快取備援 (Stale Cache Fallback)
如果所有的即時資料來源抓取失敗，工具可能會讀取已存在的過期快取作為最後的備援手段。這有助於在資料源中斷時避免分析與報表完全停擺。當使用過期快取時，系統會輸出警告 (Warning)。
> **注意**：過期快取備援是為了提高系統可用性 (availability)，並不保證提供最新的市場資料。請將過期快取的警告視為提示，並在使用分析結果前自行確認資料的新鮮度。

#### 最長過期快取天數限制
為避免分析過於陳舊的資料，預設的過期快取最長保留使用天數為 **14 天**。若快取檔案的修改時間超過此限制，系統將拒絕使用並拋出 `DataLoaderError`。

你可以透過設定環境變數來覆寫預設的 14 天限制：
- `TW_STOCK_TOOL_MAX_STALE_CACHE_DAYS`：正整數，控制過期快取的最長有效天數。若設定為無效值、0 或負數，則自動回退至預設的 14 天。
例如 (Windows CMD)：
```cmd
set TW_STOCK_TOOL_MAX_STALE_CACHE_DAYS=7
```
(Windows PowerShell)：
```powershell
$env:TW_STOCK_TOOL_MAX_STALE_CACHE_DAYS = "7"
```

#### 強制更新 (--force-refresh)
如果在執行指令時加入了強制更新參數 (`--force-refresh` 或 `force_refresh=True`)，系統將完全繞過過期快取備援機制。在此情況下，如果即時抓取失敗，程式將直接報錯，不會嘗試使用舊資料。

### 環境檢查

安裝套件後，建議先執行本機檢查：

```bash
twstock doctor
```

如果想同時檢查外部資料來源，可以執行：

```bash
twstock doctor --live
```

說明：

- `doctor.py` 預設只檢查本機環境，不連外部資料源。
- `doctor.py --live` 會額外執行官方股票清單與價格資料 smoke check。
- live check 失敗可能是外部服務暫時不穩，不一定代表程式邏輯錯誤。

如果 Windows 環境中 `python` 不在 PATH，請改用你的 Python 絕對路徑執行，例如：

```powershell
& "C:\Users\Mike\AppData\Local\Programs\Python\Python312\python.exe" -m unittest discover -s tests
```

## 常用指令速查表

以下列出最常使用的指令，推薦優先使用 `twstock` 統一介面。

### 推薦使用的統一 CLI (twstock)

| 目的 | 指令 |
| --- | --- |
| 環境檢查 | `twstock doctor` |
| 單股分析 | `twstock analyze --stock 2330 --period 2y` |
| 策略比較 | `twstock strategy-compare --stock 2330 --period 2y` |
| 多股票掃描 | `twstock scan --auto-stock-list --stock-limit 50` |
| 每日候選報告 | `twstock daily --auto-stock-list --stock-limit 50 --output-md` |
| Daily Report artifact operations | `twstock daily-report-artifact validate output/daily_report.json` |
| 產生歷史回測報告 | `twstock backtest-report --stock 2330 --strategy ma_cross --output-excel` |
| Parameter Sweep | `twstock parameter-sweep --stock 2330 --strategy all --period 2y --output-excel` |
| Walk Forward | `twstock walk-forward --stock 2330 --strategy ma_cross --period 10y --output-excel` |
| 匯出 BacktestResult JSON artifact | `twstock backtest-result-export --stock 2330 --strategy ma_cross --output-json output/backtest_result.json` |
| 匯出模擬紙上交易報告 | `twstock simulated-paper-trading-export result.json --output-markdown report.md` |
| 檢查股票清單 | `twstock stock-list clean --file stocks.txt --output --write-clean-file` |
| 查看快取摘要 | `twstock cache --summary` |
| 列出快取檔案 | `twstock cache --list` |
| 清除快取 | `twstock cache --clear` |
| Benchmark | `twstock benchmark --file stocks.txt --workers 8 --repeat 3` |
| 執行全部測試 | `python -m unittest discover -s tests` |

### 相容性直接腳本執行 (Legacy / Compatibility Scripts)

如果你沒有使用 `pip install -e .` 安裝套件，可直接執行根目錄下的腳本：

| 目的 | 指令 |
| --- | --- |
| 單股分析 | `python main.py --stock 2330 --period 2y` |
| 更新股票清單 | `python stock_list_updater.py --market all --output stocks.txt` |
| 官方資料來源檢查 | `python stock_list_smoke_check.py` |
| 價格資料來源檢查 | `python price_data_smoke_check.py` |
| 多股票掃描 | `python scan_stocks.py --file stocks.txt` |
| 策略比較 | `python strategy_compare.py --stock 2330 --period 2y` |
| Parameter Sweep | `python parameter_sweep.py --stock 2330 --strategy all --period 2y --output-excel` |
| Walk Forward Test | `python walk_forward.py --stock 2330 --strategy ma_cross --period 10y --output-excel` |
| 建立 ML Dataset | `python ml_dataset.py --stock 2330 --period 5y --horizon 5 --output` |
| AI Walk Forward | `python ai_walk_forward.py --stock 2330 --period 5y --horizon 5 --train-size 252 --test-size 63` |
| Baseline ML model | `python baseline_ml_model.py --stock 2330 --period 5y --horizon 5 --train-size 252 --test-size 63` |
| AI Prediction Report | `python ai_prediction_report.py --stock 2330 --period 5y --horizon 5 --output` |
| 多股票 AI 掃描 | `python ai_stock_scanner.py --file stocks.txt --period 5y --horizon 5 --output` |
| 本機 GUI 原型 | `python gui_app.py` |

### 更新股票清單

```bash
python stock_list_updater.py --market all --output stocks.txt --add-suffix
```

- Default behavior remains unchanged: `stock_list_updater.py` writes plain stock IDs such as `2330`.
- With `--add-suffix`, it writes market-qualified symbols such as `2330.TW` or `8069.TWO`.
- This can reduce later TW/TWO fallback guessing during price download.

### 本機 GUI 原型

```bash
python gui_app.py
```

說明：

- 這是初版 Tkinter GUI 原型。
- 目前主要用於環境檢查、官方股票清單來源檢查、價格資料來源檢查、股票清單更新、多股票掃描、Daily Report、單股分析、快取管理與 Task Log。
- GUI 會透過 `gui_tasks.TaskRunner` 背景執行 `app_services`，避免主畫面卡住。
- 研究工具與 AI/ML 頁面會在後續視需求加入 GUI。
- 原本 CLI 與 `twstock ...` 指令仍可正常使用。

### 統一 CLI 入口

原本的 `main.py`、`scan_stocks.py` 等既有 CLI 檔案仍可直接使用。Daily Report 請使用統一入口 `twstock daily` 或 `python twstock_cli.py daily`。

```bash
twstock doctor
twstock analyze --stock 2330 --period 2y
twstock strategy-compare --stock 2330 --period 2y
twstock backtest-report --stock 2330 --strategy ma_cross --output-excel
twstock parameter-sweep --stock 2330 --strategy all --period 2y --output-excel
twstock walk-forward --stock 2330 --strategy ma_cross --period 10y --output-excel
twstock backtest-result-export --stock 2330 --strategy ma_cross --output-json output/backtest_result.json
twstock simulated-paper-trading-export result.json --output-markdown report.md
twstock scan --auto-stock-list --stock-limit 50
twstock daily --auto-stock-list --stock-limit 50 --output-md
twstock stock-list update --market all --output stocks.txt
twstock stock-list smoke-check
twstock stock-list clean --file stocks.txt --output --write-clean-file
twstock price-smoke-check
twstock ai-scan --auto-stock-list --stock-limit 20 --output
twstock cache --summary
twstock cache --list
twstock cache --clear
twstock benchmark --file stocks.txt --workers 8 --repeat 3

python twstock_cli.py doctor
python twstock_cli.py scan --auto-stock-list --stock-limit 50
python twstock_cli.py daily --auto-stock-list --stock-limit 50 --output-md
```

### Auto Stock List 安全使用建議

`--auto-stock-list` 會先從 TWSE / TPEx 官方公開資料更新股票清單，再進行掃描。
第一次使用時，建議先用 `--stock-limit` 限制掃描數量，避免一次掃描全市場導致執行時間過長，或遇到 yfinance rate limit。

```bash
twstock scan --auto-stock-list --stock-limit 50
twstock daily --auto-stock-list --stock-limit 50 --output-md
twstock ai-scan --auto-stock-list --stock-limit 20 --output
```

如果想隨機抽樣，可以使用：

```bash
twstock scan --auto-stock-list --stock-sample 50 --random-state 42
```

補充說明：

- `--stock-limit N`：只取股票清單前 N 檔。
- `--stock-sample N`：從股票清單隨機抽 N 檔。
- `--random-state`：固定抽樣結果，方便重複測試。
- `--stock-limit` 與 `--stock-sample` 不可同時使用。

### 官方資料來源檢查

如果懷疑 TWSE / TPEx 官方資料來源格式改變、網路連線異常，或 `--auto-stock-list` 抓不到合理股票數量，可以手動執行：

```bash
python stock_list_smoke_check.py
```

這個工具會直接連線到 TWSE / TPEx 官方公開資料來源，檢查：

- TWSE 股票數量
- TPEx 股票數量
- 合併後股票數量
- 常見股票代號，例如 `2330`、`2317`、`8069`

注意：

- 這是 live API smoke check。
- 不會放進一般 unittest / CI 預設流程。
- 如果官方服務暫時不穩，可能會失敗，失敗不一定代表程式邏輯錯誤。


### 價格資料來源檢查

如果掃描時大量股票顯示 no data、疑似 yfinance rate limit，或官方 fallback 無法使用，可以手動執行：

```bash
python price_data_smoke_check.py
```

這個工具會透過 `data_loader.download_tw_stock()` 檢查 yfinance 主資料源與官方 fallback 價格資料路徑是否可用。

注意：

- 這是 live API smoke check。
- 不會放進一般 unittest / CI 預設流程。
- 如果外部資料源暫時不穩，失敗不一定代表程式邏輯錯誤。


### 建議研究流程

```text
更新股票清單
↓
掃描股票
↓
Daily Report
↓
單股分析
↓
策略比較
↓
Parameter Sweep
↓
Walk Forward
↓
持續追蹤
```

AI / ML 延伸流程：

```text
Walk Forward
↓
ML Dataset
↓
AI Walk Forward
↓
Baseline ML Model
↓
AI Prediction Report
↓
AI Stock Scanner
↓
持續追蹤
```

補充說明：

- Parameter Sweep 用來找歷史最佳參數。
- Walk Forward 用來驗證參數穩定性。
- Walk Forward 結果比單純 Parameter Sweep 更具參考價值。
- `ml_dataset.py` 只建立 feature / target，不訓練模型。
- `ai_walk_forward.py` 只做時間切分，不訓練模型。
- `baseline_ml_model.py` 使用 `RandomForestClassifier` 作為 baseline。
- `ai_prediction_report.py` 整理 baseline model 結果成 `Summary` / `Detail` / `Errors`。
- `ai_stock_scanner.py` 會批次執行多檔股票的 baseline AI validation，並輸出 ranking。
- 這仍然只是研究工具，不是投資建議。
- 所有 AI / ML 功能僅供研究，不保證預測績效，也不是投資建議。

## 新手第一次使用範例

本流程適合第一次使用本專案的使用者。建議先檢查資料來源，再用小範圍掃描熟悉輸出，最後再進入策略比較、Walk Forward 與 AI / ML 研究。

如果不想記 CLI 指令，也可以先試用本機 GUI 原型：

```bash
python gui_app.py
```

但目前 GUI 還是初版，完整功能仍以 CLI / `twstock ...` 為主。

### Step 1：安裝套件與指令介面

推薦使用 `pip install -e .` 將套件與 `twstock` 指令一起安裝，這樣後續的操作會更簡單。

```bash
pip install -e .
twstock --help
```

### Step 2：檢查資料來源

第一次使用時，建議先確認官方股票清單來源與價格資料來源可用。

```bash
twstock stock-list smoke-check
twstock price-smoke-check
```

說明：

- 如果這兩個檢查失敗，可能是外部資料源暫時不穩，不一定是程式錯。
- 第一次使用時建議先確認資料來源正常。
- 這兩個 smoke check 是手動 live API 檢查，不會放進一般 unittest / CI 預設流程。

### Step 3：先小範圍掃描

```bash
twstock scan --auto-stock-list --stock-limit 50
```

說明：

- 第一次不要直接掃全市場。
- 先用 `--stock-limit` 限制股票數量，確認速度與輸出都正常。
- 如果想隨機抽樣，可以改用 `--stock-sample` 搭配 `--random-state`。

### Step 4：產生每日候選報告

```bash
twstock daily --auto-stock-list --stock-limit 50 --output-md
```

這會產生 Markdown 格式的每日候選股票報告，可以先觀察：

- `Signal`
- `Score`
- `Volume_Ratio`
- `Analysis`

### Step 5：單股深入分析

假設對 `2330` 有興趣，可以輸出單股分析 Excel 與圖表。

```bash
twstock analyze --stock 2330 --period 2y --export-excel --save-chart
```

### Step 6：策略比較與 Walk Forward

```bash
twstock strategy-compare --stock 2330 --period 2y
twstock walk-forward --stock 2330 --strategy ma_cross --period 10y --output-excel
```

說明：

- `strategy-compare` 用來比較不同策略在同一檔股票上的歷史回測結果。
- `walk-forward` 用 train / test 視窗驗證參數是否可能過度擬合。
- Walk Forward 比單純 Parameter Sweep 更適合用來觀察策略穩定性。

### Step 7：AI / ML 研究流程（進階選項）

如果想研究 baseline AI / ML 結果，可以再執行：

```bash
twstock ai-scan --auto-stock-list --stock-limit 20 --output
```

*(註：單股的 AI 預測報告 `ai_prediction_report.py` 仍可透過相容性直接腳本執行使用。)*

提醒：

- 本工具僅供研究，不是投資建議。
- AI / ML 結果不保證預測績效。
- 第一次使用 `--auto-stock-list` 建議搭配 `--stock-limit`。
- 歷史績效不代表未來績效。

## 常見使用流程

### 流程 1：快速尋找值得研究的股票

目的：

從大量股票中快速找出值得進一步分析的標的。

Step 1：使用多股票掃描器。

掃描前可以先用 `clean_stocks.py` 檢查並清理 `stocks.txt`，避免下市或錯誤代號拖慢後續流程。

```bash
python clean_stocks.py --file stocks.txt --output --write-clean-file
python scan_stocks.py --file stocks.txt
python scan_stocks.py --stocks 2330 2317 2454
```

如果想直接產生每日候選清單：

```bash
twstock daily --file stocks.txt --output-md
```

說明：

- 掃描多檔股票
- 查看 `Signal`
- 查看 `Score`
- 查看 `Volume_Ratio`
- 查看 `Analysis`

重點：

優先關注：

- `BUY`
- `WATCH`
- 高 `Score`
- 成交量放大

Step 2：挑選感興趣股票後，進行單股分析。

```bash
python main.py --stock 2330 --period 2y
```

查看：

- 技術指標
- 訊號
- 回測結果
- 圖表

### 流程 2：比較策略

目的：

比較不同策略在同一檔股票上的表現。

使用：

```bash
python strategy_compare.py --stock 2330 --period 2y
```

觀察：

- `Total Return %`
- `CAGR %`
- `Sharpe Ratio`
- `Sortino Ratio`
- `Max Drawdown %`

比較：

- Score Strategy
- MA Cross Strategy
- RSI Strategy
- MACD Strategy

### 流程 3：尋找最佳參數

目的：

找出歷史回測表現較佳的參數組合。

使用：

```bash
python parameter_sweep.py --stock 2330 --strategy all --period 2y
python parameter_sweep.py --stock 2330 --period 2y --strategy ma_cross
```

流程：

- 自動測試多組參數
- 排序回測結果
- 找出較佳參數

注意：

這一步只是在歷史資料上尋找最佳參數。

### 流程 4：驗證是否過度擬合

目的：

避免直接相信 `parameter_sweep.py` 找出的最佳參數。

使用：

```bash
python walk_forward.py --stock 2330 --strategy ma_cross --period 10y
```

流程：

- train 區間選參數
- test 區間驗證

觀察：

- `Avg Test Total Return %`
- `Avg Test Sharpe Ratio`
- `Positive Test Windows %`

重點：

如果 train 很好但 test 很差，代表可能過度擬合。

### 流程 5：大量股票效能測試

目的：

評估大量掃描時的速度。

使用：

```bash
python benchmark.py --file stocks.txt --workers 8 --repeat 3
```

觀察：

- `Avg Elapsed Seconds`
- `Avg Stocks Per Second`
- `Success Rate %`

用途：

- 評估 cache 效果
- 評估 worker 數量
- 評估 force-refresh 成本

### 研究流程總結

```text
掃描股票
↓
單股分析
↓
策略比較
↓
參數掃描
↓
Walk Forward 驗證
↓
持續追蹤
```

`parameter_sweep.py` 的結果不應直接視為最佳策略。

`walk_forward.py` 才是檢查策略是否具備穩定性的關鍵步驟。

## 單股票分析

### 互動式模式

不帶任何參數時，會保留原本互動式輸入流程：

```bash
python main.py
```

### CLI 模式

帶參數時會進入 CLI 模式：

```bash
python main.py --stock 2330 --period 1y
python main.py --stock 2330 --period 2y --stop-loss 8 --take-profit 20 --max-hold-days 30
python main.py --stock 2330 --period 1y --export-excel --save-chart
python main.py --stock 2330 --period 1y --force-refresh
```

常用參數：

- `--stock`: 股票代號，例如 `2330`
- `--period`: 分析期間，例如 `1y`、`2y`、`5y`、`max`
- `--interval`: K 線週期，支援 `1d`、`1wk`、`1mo`
- `--force-refresh`: 忽略今日快取並重新下載
- `--auto-adjust` / `--no-auto-adjust`: 是否使用 yfinance 除權息調整價
- `--stop-loss`: 停損百分比，例如 `8`
- `--take-profit`: 停利百分比，例如 `20`
- `--max-hold-days`: 最大持有天數
- `--position-size`: 每次投入資金比例，預設 `1.0`
- `--export-excel`: 匯出 Excel 報表
- `--save-chart`: 儲存技術分析圖表

## 多股票掃描

```bash
python scan_stocks.py --stocks 2330 2317 2454 2308 0050
python scan_stocks.py --file stocks.txt
python scan_stocks.py --stocks 2330 2317 2454 --period 1y --signals BUY WATCH --top 10
python scan_stocks.py --file stocks.txt --min-score 3 --sort-by Volume_Ratio --force-refresh
python scan_stocks.py --file stocks.txt --errors-only --log-errors
```

輸出檔案：

- `output/stock_ranking.xlsx`
- `output/stock_ranking.csv`
- `output/stock_ranking.html`
- `output/scan_errors.log`，需使用 `--log-errors`

## 股票清單檢查

`clean_stocks.py` 用於檢查 `stocks.txt` 內股票代號是否有效，適合在 `twstock daily` 或 `scan_stocks.py` 前先執行。它會重用 `data_loader.download_tw_stock()`，保留 `.TW` / `.TWO` fallback、快取與 yfinance quiet download 行為。

CLI 範例：

```bash
python clean_stocks.py --file stocks.txt
python clean_stocks.py --file stocks.txt --output
python clean_stocks.py --file stocks.txt --write-clean-file
python clean_stocks.py --file stocks.txt --output output/clean_stocks_report.xlsx --write-clean-file output/stocks_clean.txt
python clean_stocks.py --file stocks.txt --period 1y
python clean_stocks.py --file stocks.txt --force-refresh
python clean_stocks.py --file stocks.txt --no-auto-adjust
```

常用參數：

- `--file`: 股票清單檔案，必填
- `--period`: 分析期間，預設 `DEFAULT_PERIOD`
- `--interval`: K 線週期，預設 `DEFAULT_INTERVAL`
- `--auto-adjust` / `--no-auto-adjust`: 是否使用 yfinance 除權息調整價
- `--force-refresh`: 忽略快取重新下載
- `--output`: 輸出 Excel，省略路徑時使用 `output/clean_stocks_report.xlsx`
- `--write-clean-file`: 輸出有效股票清單，省略路徑時使用 `output/stocks_clean.txt`

Excel sheets：

- `Summary`: 檔案、輸入行數、唯一股票數、有效/無效股票數、重複列數與 clean file 路徑
- `Valid`: 可正常取得資料的股票
- `Invalid`: 無法取得資料的股票與錯誤訊息
- `Duplicates`: 重複股票代號與第一次出現的行號
- `All`: 全部唯一股票檢查結果

Clean file 只輸出有效股票的 `Normalized Stock`，例如純數字輸入會保留為 `2330`、`8069`；若原始輸入已明確帶 `.TW` / `.TWO`，則會保留完整市場別。

## Daily Report
### Optional Daily Report JSON artifact

Daily Report JSON export is opt-in and produces an offline research artifact.
It is generated from the same `DailyPipelineResult` as the Markdown report.

```powershell
py twstock_cli.py daily `
  --stocks 2330 2317 `
  --output-json
```

Without a path, JSON is written to <output-dir>/daily_report.json, defaulting
to output/daily_report.json. The `--output-json` option is not required; when
it is omitted, no JSON artifact is produced.

Use a custom JSON path when needed:

```powershell
py twstock_cli.py daily `
  --stocks 2330 2317 `
  --output-json output/daily_report.json
```

Use `--overwrite` to replace an existing JSON artifact:

```powershell
py twstock_cli.py daily `
  --stocks 2330 2317 `
  --output-json output/daily_report.json `
  --overwrite
```

The JSON is for offline research only. It does not include broker integration,
live trading, order placement, investment recommendations, or investment advice.

### Daily Report Artifact Operations

Operate on an existing schema v1 Daily Research Report JSON artifact without
fetching market data or running the Daily Pipeline.

Validate an artifact:

```powershell
twstock daily-report-artifact validate output/daily_report.json
```

Inspect deterministic metadata and section counts (not report rows):

```powershell
twstock daily-report-artifact inspect output/daily_report.json
```

Restore Markdown from canonical artifact data:

```powershell
twstock daily-report-artifact export-markdown `
  output/daily_report.json `
  --output-markdown output/restored_daily_report.md
```

Use `--overwrite` to replace an existing Markdown file:

```powershell
twstock daily-report-artifact export-markdown `
  output/daily_report.json `
  --output-markdown output/restored_daily_report.md `
  --overwrite
```

- These commands operate only on an existing offline schema v1 JSON artifact.
- They do not fetch market data or run the Daily Pipeline.
- `inspect` prints metadata and counts only.
- `export-markdown` renders canonical artifact data; it does not reconstruct Excel.
- They do not connect to brokers, place orders, produce live signals, recommend stocks, or provide investment advice.

### Optional top-candidate backtest validation

Daily Report keeps its existing scan-only behavior by default. Add `--validate-top N` to backtest the first N candidates in the displayed deterministic candidate order and include scalar results in the Markdown `Backtest Highlights` section:

```bash
twstock daily --stocks 2330 2317 --validate-top 3 --validation-strategy ma_cross
```

Supported strategies are `ma_cross`, `macd`, `rsi`, and `score`. The validation controls also include `--validation-initial-capital`, `--validation-fee-rate`, `--validation-tax-rate`, and `--validation-position-size`. This is historical, research-only validation using next-bar `Open` execution assumptions; it does not provide advice, live signals, broker access, or orders. A per-candidate failure remains visible in `Backtest Highlights` and `Data Limitations` while later candidates continue. Excel output remains unchanged and does not add a validation sheet.

### Optional top-candidate walk-forward validation

Phase 50.2 adds opt-in historical out-of-sample validation after successful Phase 50.1 backtests. It validates only the first `--walk-forward-top` successful backtest rows, preserves their displayed order, and supports `ma_cross`, `rsi`, and `score`; `macd` remains backtest-only. The default window settings are `--walk-forward-train-days 126`, `--walk-forward-test-days 63`, an omitted `--walk-forward-step-days` (effective step `63`), and `--walk-forward-sort-by "Train Sharpe Ratio"`. These window flags represent observations/rows in the current row-based engine.

Use the existing validation financial assumptions; no separate walk-forward capital, fee, tax, or position-size flags are added:

```powershell
py twstock_cli.py daily `
  --stocks 2330 2317 2454 `
  --period 2y `
  --top 3 `
  --validate-top 3 `
  --validation-strategy ma_cross `
  --walk-forward-top 2 `
  --walk-forward-train-days 126 `
  --walk-forward-test-days 63 `
  --output-md output/daily_report.md
```

Walk Forward Highlights are scalar summaries in the Markdown Daily Research Report only. Partial and full candidate/window failures appear in that section and Data Limitations; no raw window tables, trades, equity curves, recommendations, or new Excel sheets are added. Results are historical research estimates and do not predict future performance.
### Optional daily parameter sweep highlights

Phase 50.4 adds an opt-in in-sample parameter sweep after successful candidate backtests and before walk-forward validation:

```powershell
py twstock_cli.py daily `
  --stocks 2330 2317 2454 `
  --period 2y `
  --validate-top 3 `
  --validation-strategy ma_cross `
  --parameter-sweep-top 2 `
  --parameter-sweep-sort-by "Sharpe Ratio" `
  --walk-forward-top 2 `
  --output-md output/daily_report.md
```

`--parameter-sweep-top` defaults to `0` (disabled). It uses the existing validation capital, fee, tax, and position-size assumptions; no separate sweep grid or trading-control flags are added. Only successful `Backtest Highlights` rows are eligible, and the displayed scalar best combination is not passed into walk-forward validation or used to reorder candidates. Sweep results are historical in-sample research summaries and may reflect overfitting; Excel output remains unchanged.
`twstock daily` CLI 用於每天快速產生 Markdown 格式的綜合研究報告。該報告包含掃描結果摘要、篩選出的觀察候選清單（Watchlist Candidates）、風險提示與資料限制等資訊。

這是一個純研究分析工具。產生的報告僅供研究用途，絕不構成任何投資建議、也不提供任何買賣建議。

CLI 範例（基本使用）：

```bash
twstock daily --stocks 2330 2317
```

CLI 範例（自動讀取檔案並同時匯出 Markdown 與 Excel）：

```bash
twstock daily --file stocks.txt --stock-limit 20 --output-md --output-excel
```

CLI 範例（自動更新台股全市場清單）：

```bash
twstock daily --auto-stock-list --stock-market twse --stock-limit 50 --output-md
```

Markdown 與 Excel 輸出行為：

- 若指定 `--output-excel`，會匯出 Excel 格式的報告檔案，供進一步研究分析使用。

- 若未指定 `--output-md`，預設會輸出到 `output/daily_report.md`。
- 若指定 `--output-md` 但未提供路徑：
  ```bash
  twstock daily --stocks 2330 2317 --output-md
  ```
  也會輸出到 `output/daily_report.md`。
- 若指定自訂路徑：
  ```bash
  twstock daily --stocks 2330 2317 --output-md custom/report.md
  ```
  會輸出到 `custom/report.md`。
- 若只指定 `--output-dir`：
  ```bash
  twstock daily --stocks 2330 2317 --output-dir reports
  ```
  會將預設檔名放入該資料夾：`reports/daily_report.md`。

常用參數：

- `--stocks`: 手動輸入股票清單。
- `--file`: 從 txt 載入股票清單。
- `--auto-stock-list`: 自動從官方來源獲取最新股票清單。
- `--stock-limit`: 限制處理的股票數量（第一次測試建議使用）。
- `--period`: 分析期間，預設 `DEFAULT_PERIOD`。
- `--interval`: K 線週期，預設 `DEFAULT_INTERVAL`。
- `--signals`: 篩選候選清單的技術訊號，預設包含 `BUY`、`WATCH`。
- `--min-score`: 篩選候選清單的最低分數，預設 `4.0`。
- `--top`: 顯示候選股前 N 名，預設 `20`。
- `--force-refresh`: 忽略快取，重新下載報價資料。
- `--auto-adjust` / `--no-auto-adjust`: 是否使用 yfinance 除權息調整價。
- `--output-md`: 指定 Markdown 報告匯出路徑。
- `--output-dir`: 指定輸出資料夾。

候選股（Watchlist Candidates）排序規則：

1. `Score` 由高到低
2. `Volume_Ratio` 由高到低

資料限制與風險提示（Disclaimer）：

- **這份報告僅供研究參考，絕不構成投資建議。**
- `twstock daily` 只依賴歷史資料快照與預先定義的技術指標條件，不包含任何未來表現的預測，也不是買賣推薦。
- 自動掃描全市場可能會受限於 yfinance 的 API 請求限制（rate limit），建議適當使用 `--stock-limit` 控制數量或使用快取機制。

## Daily Watchlist / 股票雷達

`daily_watchlist.py` 用於掃描台股並找出符合特定條件（如技術面突破）的候選股。

CLI 範例：

```bash
python daily_watchlist.py --stock 2330 --output-md --output-excel
```

多股票：

```bash
python daily_watchlist.py --stocks 2330 2317 2454 --output-md
```

使用檔案：

```bash
python daily_watchlist.py --file stocks.txt --output-excel
```

自動取得官方股票清單：

```bash
python daily_watchlist.py --auto-stock-list --stock-limit 50 --output-md
```

說明：
`--auto-stock-list` 預設會把下載的清單寫到 `output/auto_stock_list.txt`，不會直接覆蓋 tracked `stocks.txt`。

若使用者真的想更新 `stocks.txt`，請明確指定：

```bash
python daily_watchlist.py --auto-stock-list --auto-stock-list-output stocks.txt
```

這會修改 tracked `stocks.txt`，建議確認 git diff 後再 commit。

## 匯出模擬紙上交易報告 (Simulated Paper Trading Artifact Export)

`twstock simulated-paper-trading-export` 是一個 artifact-only format conversion CLI。
它只轉換已存在、已經計算完成的 simulated paper trading result JSON artifact。
它不會下載市場資料、不會執行策略、不會產生交易訊號、不會連接券商、不會下單，也不提供投資建議或買賣建議。

報表中的 `BUY` / `SELL` 僅代表已存在 JSON artifact 內的歷史模擬方向記錄，不是即時訊號、下單指令、買賣建議或投資建議。

功能：
- 將已存在的 simulated paper trading result JSON 檔案轉換為 Markdown 或 CSV 報表。
- 目前輸出 schema v3；讀取仍支援 v1/v2。Markdown 包含 `Trade Log`，CSV 另含 `<basename>_trade_log.csv`，既有 Orders、Fills、Rejections 輸出保留。
- 至少需要指定 `--output-markdown` 或 `--output-csv-dir` 其中一個輸出選項。
- 兩個輸出選項可以同時使用。
- `--basename` 參數僅會影響匯出的 CSV 檔案名稱字首（預設為 `simulated_paper_trading`）。
- `--overwrite` 參數允許覆蓋已存在的輸出檔案。

CLI 範例：

```bash
twstock simulated-paper-trading-export result.json --output-markdown report.md
twstock simulated-paper-trading-export result.json --output-csv-dir output_csv
twstock simulated-paper-trading-export result.json --output-markdown report.md --output-csv-dir output_csv --overwrite
```

## Benchmark

benchmark 工具檔名維持 `benchmark.py`，輸出分為三段：

- `Summary`: 多次 benchmark 的平均、最快、最慢與成功率
- `Detail`: 每一次 run 的耗時、成功數、失敗數
- `Errors`: 每一次 run 的失敗股票與錯誤訊息

```bash
python benchmark.py --stocks 2330 2317 2454 --period 1y --workers 8
python benchmark.py --file stocks.txt --period 1y --workers 8 --repeat 3 --warmup 1
python benchmark.py --stocks 2330 2317 2454 --period 1y --workers 8 --output
python benchmark.py --stocks 2330 2317 2454 --period 1y --interval 1d --no-auto-adjust
```

常用參數：

- `--repeat`: 正式 benchmark 次數，預設 `1`
- `--warmup`: 暖身次數，不納入輸出，預設 `0`
- `--workers`: 掃描執行緒數，必須大於 `0`
- `--interval`: K 線週期，預設 `1d`
- `--auto-adjust` / `--no-auto-adjust`: 是否使用調整價
- `--output`: 輸出 `benchmark_summary.csv`、`benchmark_detail.csv`、`benchmark_errors.csv`

## 策略比較

```bash
python strategy_compare.py --stock 2330 --period 2y
python strategy_compare.py --stock 2330 --period 2y --ma-short 10 --ma-long 30
python strategy_compare.py --stock 2330 --period 2y --rsi-buy-below 35 --rsi-sell-above 75
python strategy_compare.py --stock 2330 --period 2y --score-buy 5 --score-sell -3
python strategy_compare.py --stock 2330 --period 2y --output-excel
```

- `--output-excel`: 匯出 Excel 報告（推薦使用）。
- `--output`: 保留作為向下相容的別名。

目前策略：

- `score_strategy`: 預設使用 `signals.py` 產生的 `Signal`
- `score_strategy`: 若指定 `--score-buy` 與 `--score-sell`，會用 `Score` 重新產生 BUY / SELL / HOLD
- `ma_cross_strategy`: MA 短長線交叉
- `macd_strategy`: MACD 與 MACD Signal 交叉
- `rsi_strategy`: RSI 門檻策略

`score_strategy` 門檻規則：

- `Score >= score_buy`: `BUY`
- `Score <= score_sell`: `SELL`
- 其他：`HOLD`
- `score_buy` 必須大於 `score_sell`
- 若指定其中一個門檻，另一個也必須指定

## 策略參數掃描

`parameter_sweep.py` 會自動測試多組策略參數，並用歷史回測結果比較不同參數組合的表現。

```bash
python parameter_sweep.py --stock 2330 --strategy all --period 2y
python parameter_sweep.py --stock 2330 --period 2y --strategy ma_cross
python parameter_sweep.py --stock 2330 --period 2y --strategy rsi
python parameter_sweep.py --stock 2330 --period 2y --strategy score
python parameter_sweep.py --stock 2330 --strategy all --period 2y --output-excel
python parameter_sweep.py --stock 2330 --period 2y --strategy ma_cross --output-excel output/2330_ma_sweep.xlsx
```

支援策略：

- `all`: 預設，掃描全部策略
- `ma_cross`: 掃描 MA 交叉策略
- `rsi`: 掃描 RSI 策略
- `score`: 掃描技術分數策略

參數組合：

- `ma_cross`: `short_window` 使用 `5, 10, 20`，`long_window` 使用 `20, 30, 60`，且 `short_window < long_window`
- `rsi`: `buy_below` 使用 `25, 30, 35`，`sell_above` 使用 `65, 70, 75`，且 `buy_below < sell_above`
- `score`: `buy_score` 使用 `4, 5, 6`，`sell_score` 使用 `-2, -3, -4`，且 `buy_score > sell_score`

常用參數：

- `--stock`: 股票代號，必填
- `--period`: 分析期間，預設 `DEFAULT_PERIOD`
- `--strategy`: `all`、`ma_cross`、`rsi`、`score`，必填
- `--force-refresh`: 忽略快取重新下載
- `--output-md`: 輸出 Markdown 報告
- `--output-excel`: 輸出 Excel 報告
- `--stop-loss-pct`: 停損百分比
- `--take-profit-pct`: 停利百分比
- `--max-hold-days`: 最大持有天數
- `--position-size`: 每次投入資金比例，需符合 `0 < value <= 1`

輸出欄位：

- `Rank`
- `Strategy`
- `Parameters`
- `Total Return %`
- `Buy and Hold Return %`
- `CAGR %`
- `Trade Count`
- `Win Rate %`
- `Max Drawdown %`
- `Profit Factor`
- `Sharpe Ratio`
- `Sortino Ratio`
- `Error`

## Parameter Sweep Report CLI

我們提供了專用的 CLI 來輸出 Parameter Sweep Report，包含詳細的 Markdown 與 Excel 報表格式。
此 CLI 的執行入口為 `parameter_sweep_report.py` 或 `tw_stock_tool/cli/parameter_sweep_report.py`。

### Important Behavior Notes

1. `--stock` is required.
2. `--strategy` is required.
3. `--output-md` is optional.
4. `--output-excel` is optional.
5. If neither output flag is provided, the CLI prints a summary only.
6. `--output-md` without a custom path uses `output/parameter_sweep_report.md`.
7. `--output-excel` without a custom path uses `output/parameter_sweep_report.xlsx`.
8. Custom paths are supported.
9. The report is for research only and is not investment advice.
10. The CLI does not place orders and does not connect to broker APIs.

### Basic run without file export

這會執行 Parameter Sweep 並將簡明摘要印在 stdout，不會產出任何報表檔案。

```bash
python parameter_sweep_report.py --stock 2330 --strategy ma_cross
```

### Export Markdown report

```bash
python parameter_sweep_report.py --stock 2330 --strategy ma_cross --output-md
```

Default output: `output/parameter_sweep_report.md`

### Export Excel report

```bash
python parameter_sweep_report.py --stock 2330 --strategy ma_cross --output-excel
```

Default output: `output/parameter_sweep_report.xlsx`

### Export both Markdown and Excel

```bash
python parameter_sweep_report.py --stock 2330 --strategy ma_cross --output-md --output-excel
```

### Custom output paths

```bash
python parameter_sweep_report.py --stock 2330 --strategy ma_cross --output-md reports/sweep.md --output-excel reports/sweep.xlsx
```

### Optional period

```bash
python parameter_sweep_report.py --stock 2330 --strategy ma_cross --period 2y --output-md
```

### Force refresh

```bash
python parameter_sweep_report.py --stock 2330 --strategy ma_cross --force-refresh --output-md
```

> **Note**: Research report only, not investment advice. Historical performance does not guarantee future results.

### Custom parameter ranges

You can provide custom parameter ranges to override the built-in defaults. Values are comma-separated integers, and whitespace is tolerated. Negative integers are supported for score ranges (e.g. `--score-sell=-2,-3,-4`).

MA custom ranges:
```bash
python parameter_sweep_report.py --stock 2330 --strategy ma_cross --ma-short-windows 5,10,20 --ma-long-windows 30,60,120
```

RSI custom ranges:
```bash
python parameter_sweep_report.py --stock 2330 --strategy rsi --rsi-buy-below "25, 30, 35" --rsi-sell-above 65,70,75
```

Score custom ranges:
```bash
python parameter_sweep_report.py --stock 2330 --strategy score --score-buy 4,5,6 --score-sell=-2,-3,-4
```

Combined custom ranges with Markdown or Excel output:
```bash
python parameter_sweep_report.py --stock 2330 --strategy all --ma-short-windows 5,10 --rsi-buy-below 20,30 --score-sell=-2,-4 --output-md --output-excel
```

> **Safety Boundary**: This project is a research / backtesting / reporting tool. It is not an auto-trading system. It does not connect to broker APIs. It does not provide investment advice. It does not guarantee profit.

## Walk Forward 驗證
- 若某個 sheet 沒有資料，仍會保留欄位標題。

注意：參數掃描只是歷史回測比較，不代表未來績效，也不提供投資建議。單一參數組合失敗時，工具會記錄在 `Error` 欄位並繼續掃描其他組合。

## Walk Forward Test

`walk_forward.py` 用於驗證 `parameter_sweep.py` 找到的最佳參數是否可能過度擬合。

流程：

1. 將歷史資料切成 train / test 視窗
2. 在 train 區間尋找最佳參數
3. 將最佳參數套用到 test 區間
4. 比較 train 與 test 表現
5. 輸出 Summary / Detail / Errors Excel

CLI 範例：

```bash
python walk_forward.py --stock 2330 --strategy all --period 5y
python walk_forward.py --stock 2330 --period 10y --strategy ma_cross
python walk_forward.py --stock 2330 --period 10y --strategy rsi
python walk_forward.py --stock 2330 --period 10y --strategy score
python walk_forward.py --stock 2330 --strategy all --period 10y --train-days 504 --test-days 126
python walk_forward.py --stock 2330 --strategy all --period 10y --output-excel
python walk_forward.py --stock 2330 --strategy all --period 10y --output-excel output/2330_walk_forward.xlsx
```

參數說明：

- `--stock`：股票代號，必填
- `--period`：分析期間，預設 `DEFAULT_PERIOD`
- `--strategy`：`all`、`ma_cross`、`rsi`、`score`，必填
- `--train-days`：訓練區間交易日數，預設 `504`
- `--test-days`：驗證區間交易日數，預設 `126`
- `--step-days`：每次視窗往後移動的交易日數，預設等於 `test-days`
- `--sort-by`：train 區間選最佳參數用的欄位，預設 `Train Sharpe Ratio`
- `--force-refresh`：忽略快取重新下載
- `--output-md`：輸出 Markdown 報告
- `--output-excel`：輸出 Excel 報告
- `--stop-loss-pct`：停損百分比
- `--take-profit-pct`：停利百分比
- `--max-hold-days`：最大持有天數
- `--position-size`：每次投入資金比例，需符合 `0 < value <= 1`

支援 `sort-by`：

- `Train Total Return %`
- `Train CAGR %`
- `Train Sharpe Ratio`
- `Train Sortino Ratio`
- `Train Profit Factor`
- `Train Max Drawdown %`

Excel sheet：

- `Summary`
- `Detail`
- `Errors`

限制與提醒：

- Walk Forward 只是歷史驗證，不代表未來績效
- 仍是收盤價回測
- 不模擬盤中觸價、滑價、流動性
- 不提供投資建議
- 不提供自動下單

## Walk Forward Report CLI

我們提供了專用的 CLI 來輸出 Walk Forward Report，包含詳細的 Markdown 與 Excel 報表格式。
此 CLI 的執行入口為 `walk_forward_report.py` 或 `tw_stock_tool/cli/walk_forward_report.py`。

### Important Behavior Notes

1. `--stock` is required.
2. `--strategy` is required.
3. `--output-md` is optional.
4. `--output-excel` is optional.
5. If neither output flag is provided, the CLI prints a summary only and does not create report files.
6. `--output-md` without a custom path uses `output/walk_forward_report.md`.
7. `--output-excel` without a custom path uses `output/walk_forward_report.xlsx`.
8. Custom paths are supported.
9. The CLI supports `--output-dir` to change the default output directory.
10. The report uses the existing Walk Forward Report exporter logic.
11. Best-window selection follows the report exporter logic (e.g. Test Sharpe Ratio > Test Total Return %), not raw row order.
12. Research report only, not investment advice. Historical performance does not guarantee future results.
13. The CLI does not place orders and does not connect to broker APIs.

### Basic run without file export

這會執行 Walk Forward 並將簡明摘要印在 stdout，不會產出任何報表檔案。

```bash
python walk_forward_report.py --stock 2330 --strategy ma_cross
```

### Export Markdown report

```bash
python walk_forward_report.py --stock 2330 --strategy ma_cross --output-md
```

Default output: `output/walk_forward_report.md`

### Export Excel report

```bash
python walk_forward_report.py --stock 2330 --strategy ma_cross --output-excel
```

Default output: `output/walk_forward_report.xlsx`

### Export both Markdown and Excel

```bash
python walk_forward_report.py --stock 2330 --strategy ma_cross --output-md --output-excel
```

### Custom output paths

```bash
python walk_forward_report.py --stock 2330 --strategy ma_cross --output-md reports/wf.md --output-excel reports/wf.xlsx
```

### Optional period

```bash
python walk_forward_report.py --stock 2330 --strategy ma_cross --period 2y --output-md
```

### Force refresh

```bash
python walk_forward_report.py --stock 2330 --strategy ma_cross --force-refresh --output-md
```

### Custom parameter ranges

You can provide custom parameter ranges to override the built-in defaults. Values are comma-separated integers, and whitespace is tolerated. Negative integers are supported for score ranges (e.g. `--score-sell=-2,-3,-4`).

MA custom ranges:
```bash
python walk_forward_report.py --stock 2330 --strategy ma_cross --ma-short-windows 5,10,20 --ma-long-windows 30,60,120
```

RSI custom ranges:
```bash
python walk_forward_report.py --stock 2330 --strategy rsi --rsi-buy-below "25, 30, 35" --rsi-sell-above 65,70,75
```

Score custom ranges:
```bash
python walk_forward_report.py --stock 2330 --strategy score --score-buy 4,5,6 --score-sell=-2,-3,-4
```

Combined custom ranges with Markdown or Excel output:
```bash
python walk_forward_report.py --stock 2330 --strategy all --ma-short-windows 5,10 --rsi-buy-below 20,30 --score-sell=-2,-4 --output-md --output-excel
```

## Backtest Report CLI

`backtest_report.py` 提供單次歷史回測並輸出研究報告（Markdown / Excel）。
此 CLI 的執行入口為 `backtest_report.py` 或 `tw_stock_tool/cli/backtest_report.py`。

### Important Behavior Notes

1. `--stock` is required.
2. `--strategy` is required.
3. `--output-md` is optional.
4. `--output-excel` is optional.
5. If neither output flag is provided, the CLI prints a summary only and does not create report files.
6. `--output-md` without a custom path uses `output/backtest_report.md`.
7. `--output-excel` without a custom path uses `output/backtest_report.xlsx`.
8. Custom paths are supported.
9. The CLI supports `--output-dir` to change the default output directory.
10. The report uses the existing Backtest Report exporter logic.
11. Backtest trades 目前支援 `PnL_pct` 欄位；report exporter 也保留 legacy `PnL %` 顯示相容。
12. The report is for research only and is not investment advice.
13. The CLI does not place orders and does not connect to broker APIs.

### Basic run without file export

這會執行 Backtest 並將簡明摘要印在 stdout，不會產出任何報表檔案。

```bash
python backtest_report.py --stock 2330 --strategy ma_cross
```

### Export Markdown report

```bash
python backtest_report.py --stock 2330 --strategy ma_cross --output-md
```

Default output: `output/backtest_report.md`

### Export Excel report

```bash
python backtest_report.py --stock 2330 --strategy ma_cross --output-excel
```

Default output: `output/backtest_report.xlsx`

### Export both Markdown and Excel

```bash
python backtest_report.py --stock 2330 --strategy ma_cross --output-md --output-excel
```

### Custom output paths

```bash
python backtest_report.py --stock 2330 --strategy ma_cross --output-md reports/backtest.md --output-excel reports/backtest.xlsx
```

### Optional period

```bash
python backtest_report.py --stock 2330 --strategy ma_cross --period 2y --output-md
```

### Force refresh

```bash
python backtest_report.py --stock 2330 --strategy ma_cross --force-refresh --output-md
```

## Backtest to Simulated Paper Trading Converter API

This library-level API acts as an offline data transformer. It converts an already-computed internal `BacktestResult` object into a `SimulatedPaperTradingResult` artifact.

> **Safety Boundary**: The converted BUY / SELL values are retrospective historical backtest-side records. They are not live trading signals, order instructions, buy/sell recommendations, or investment advice.

**What it does:**
- Converts a structured `BacktestResult` object into a `SimulatedPaperTradingResult` artifact.
- It integrates seamlessly with Phase 29 APIs: the converted object can be serialized to JSON and subsequently exported to Markdown or CSV using existing export APIs.

**What it does NOT do:**
- Does not run a backtest.
- Does not execute a strategy.
- Does not fetch market data.
- Does not generate new signals.
- Does not connect to a broker.
- Does not place orders.
- Does not provide investment advice.

**Current Limitations:**
- The converter accepts only the internal structured `BacktestResult` object.
- It does not currently accept the legacy dict returned by the public `run_backtest()`.
- There is no CLI command for this converter yet. JSON input for backtests and CLI commands remain future work.

**Minimal Example:**

```python
from tw_stock_tool.paper_trading import (
    convert_backtest_result_to_simulated_paper_trading_result,
)
from tw_stock_tool.paper_trading.serialization import (
    export_simulated_paper_trading_result_json,
)

# `backtest_result` must be a pre-computed BacktestResult object.
result = convert_backtest_result_to_simulated_paper_trading_result(backtest_result)
json_content = export_simulated_paper_trading_result_json(result)
```

## Simulated Paper Trading Export APIs

This library-level helper API exports an already constructed simulated paper trading result to markdown or CSV formats.

> **Safety Boundary**: This is a research-only simulated reporting feature. It is not live trading, broker integration, investment advice, or a buy/sell/hold recommendation system, and it does not guarantee profit.

> **CLI 工具**: 若需要從命令列直接轉換已存在的 JSON artifact，請參考 [匯出模擬紙上交易報告 (Simulated Paper Trading Artifact Export)](#匯出模擬紙上交易報告-simulated-paper-trading-artifact-export) 區塊，使用 `twstock simulated-paper-trading-export` 指令。

### 1. Markdown string export

Use this to render a result into a Markdown string. It returns a Markdown string and does not write files.

```python
from tw_stock_tool.paper_trading import export_simulated_paper_trading_markdown

markdown_text = export_simulated_paper_trading_markdown(result)
```

### 2. CSV bundle string export

Use this to render a result into a bundle of CSV strings. It does not write files.

```python
from tw_stock_tool.paper_trading import export_simulated_paper_trading_csv_bundle

csv_bundle = export_simulated_paper_trading_csv_bundle(result)

summary_csv = csv_bundle["summary"]
orders_csv = csv_bundle["orders"]
fills_csv = csv_bundle["fills"]
rejections_csv = csv_bundle["rejections"]
trade_log_csv = csv_bundle["trade_log"]
```

### 3. Markdown file export

Use this to render a simulated paper trading result and write the Markdown report to the requested path. It returns a `Path`.

```python
from tw_stock_tool.paper_trading import export_simulated_paper_trading_markdown_file

path = export_simulated_paper_trading_markdown_file(
    result,
    "output/simulated_paper_trading_report.md",
    overwrite=False,
)
```

*(Note: This function only writes an output file. It does not fetch market data or run a strategy.)*

### 4. CSV files export

Use this to render a simulated paper trading result and write the CSV bundle to a directory.

```python
from tw_stock_tool.paper_trading import export_simulated_paper_trading_csv_files

paths = export_simulated_paper_trading_csv_files(
    result,
    "output/simulated_paper_trading",
    basename="simulated_paper_trading",
    overwrite=False,
)
```

This writes:
- `simulated_paper_trading_summary.csv`
- `simulated_paper_trading_orders.csv`
- `simulated_paper_trading_fills.csv`
- `simulated_paper_trading_rejections.csv`
- `simulated_paper_trading_trade_log.csv`

And returns:

```python
{
    "summary": Path(...),
    "orders": Path(...),
    "fills": Path(...),
    "rejections": Path(...),
    "trade_log": Path(...),
}
```

## BacktestResult Artifact Workflow

The intended offline research artifact workflow is:

```text
twstock backtest-result-export
→ BacktestResult JSON artifact
→ twstock backtest-artifact validate
→ twstock backtest-artifact inspect
→ optional convert-to-simulated-paper-trading
```

- `backtest-result-export` is the historical execution export path.
- `backtest-artifact` is artifact-input-only.
- `backtest-artifact validate` validates an existing artifact.
- `backtest-artifact inspect` prints only a safe summary.
- `convert-to-simulated-paper-trading` converts an existing BacktestResult artifact to a simulated paper trading artifact.
- This is an offline research artifact workflow.
- This is not live trading, not broker integration, not auto trading, not order placement, not investment advice, and not a buy/sell/hold signal generator.

### Future Boundary Planning

- Do not add `backtest-report --output-backtest-json` yet.
- If that is considered later, it must first have explicit boundary planning.
- Future planning must decide whether it uses `run_backtest_result()`, how it interacts with existing Excel/Markdown report output, and how it avoids legacy dict normalization issues.

## 輸出檔案位置總覽

| 工具 | 功能 | 預設輸出位置 | 備註 |
| --- | --- | --- | --- |
| `main.py` | 單股分析 Excel | `output/{stock}_report.xlsx` | 需搭配 `--export-excel`。 |
| `main.py` | 單股分析圖表 | `output/{stock}_chart.png` | 需搭配 `--save-chart`。 |
| `scan_stocks.py` | 股票排行報表 | `output/stock_ranking.xlsx`<br>`output/stock_ranking.csv`<br>`output/stock_ranking.html` | 執行掃描後輸出；可用 `--output-dir` 指定資料夾。 |
| `scan_stocks.py` | 錯誤紀錄 | `output/scan_errors.log` | 需使用 `--log-errors`。 |
| `clean_stocks.py` | 股票清單檢查 Excel | `output/clean_stocks_report.xlsx` | 使用 `--output`；也可指定自訂路徑。 |
| `clean_stocks.py` | 有效股票清單 | `output/stocks_clean.txt` | 使用 `--write-clean-file`；只包含可正常取得資料的股票。 |
| `twstock daily` | 每日候選清單報告 | `output/daily_report.md`, `output/daily_report.xlsx` | 使用 `--output-md`、`--output-excel` 或 `--output-dir`；也可指定自訂路徑。 |
| `strategy_compare.py` | 策略比較 Excel | `output/{stock}_strategy_compare.xlsx` | 優先使用 `--output-excel`（舊版 `--output` 仍可作為相容別名）；也可指定自訂路徑。 |
| `parameter_sweep.py` | Parameter Sweep Markdown | `output/{stock}_parameter_sweep.md` | 使用 `--output-md`；也可指定自訂路徑。 |
| `parameter_sweep.py` | Parameter Sweep Excel | `output/{stock}_parameter_sweep.xlsx` | 使用 `--output-excel`；也可指定自訂路徑。 |
| `walk_forward.py` | Walk Forward Markdown | `output/{stock}_walk_forward.md` | 使用 `--output-md`；也可指定自訂路徑。 |
| `walk_forward.py` | Walk Forward Excel | `output/{stock}_walk_forward.xlsx` | 使用 `--output-excel`；也可指定自訂路徑。 |
| `benchmark.py` | Benchmark 統計結果 | `output/benchmark/benchmark_summary.csv`<br>`output/benchmark/benchmark_detail.csv`<br>`output/benchmark/benchmark_errors.csv` | 使用 `--output` 時建立；可指定自訂資料夾或檔名前綴。 |
| `cache/` | 快取資料 | `cache/{symbol}_{period}_{interval}_adjusted-{auto_adjust}.csv` | 由系統自動建立。 |
| `cache_manager.py` | 快取管理 | 無固定輸出檔 | 主要顯示資訊與清除快取。 |

### output/ 目錄

大部分分析結果都會放在：

```text
output/
```

建議：

- 定期整理
- 不要直接刪除仍在使用的分析結果

### cache/ 目錄

`cache/` 是資料快取目錄。

用途：

- 減少重複下載
- 加速分析流程

可使用下列指令清除快取：

```bash
python cache_manager.py --clear
```

## 資料來源與快取

主要資料來源為 yfinance。輸入純數字股票代號時，程式會先嘗試 `{stock}.TW`，若 yfinance 無資料，再嘗試 `{stock}.TWO`。若已知市場別，也可以直接輸入完整代號，例如 `2330.TW` 或 `8069.TWO`。

台股 Yahoo Finance 常見代號規則：

- `.TW`: 通常代表上市股票
- `.TWO`: 通常代表上櫃股票

若 yfinance 的 `.TW` 與 `.TWO` 都無資料且 `auto_adjust=False`，會嘗試官方 fallback：

- `.TW`: TWSE 官方日成交資訊
- `.TWO`: TPEX 官方個股月成交資訊；若月資料端點回空，會退到 TPEX openapi 最近一日收盤行情

注意：官方 fallback 目前提供未除權息調整的日資料，只支援 `1d` interval。TPEX openapi 備援只保證最近一日資料可用，長週期指標仍可能因資料筆數不足而失敗。若你需要除權息調整價，請使用 yfinance 的 `--auto-adjust`，此時不會混用官方 fallback。

若 `.TW` 與 `.TWO` 都查無資料，可能是股票已下市、代號錯誤、Yahoo Finance 暫時無資料，或資料源暫時限流。例如 `2888` 這類歷史代號或下市合併類型，工具可能無法取得正常價格資料，建議從 `stocks.txt` 移除，或保留在輸出錯誤清單中追蹤。

快取規則：

- 快取目錄：`cache/`
- 快取檔名：`cache/{symbol}_{period}_{interval}_adjusted-{auto_adjust}.csv`
- 今日產生的快取會直接讀取
- 使用 `--force-refresh` 可強制重新下載
- 快取讀取或寫入失敗不會中斷整體流程，程式會嘗試重新下載

快取管理：

```bash
python cache_manager.py --list
python cache_manager.py --summary
python cache_manager.py --clear
```

## 回測參數

`main.py`、`strategy_compare.py` 皆支援下列回測參數：

- `stop_loss_pct`: 停損百分比
- `take_profit_pct`: 停利百分比
- `max_hold_days`: 最大持有天數
- `position_size`: 每次投入資金比例

回測保留手續費與證交稅估算，並輸出交易紀錄與 Equity Curve。

## 輸出欄位說明


### Daily Report 欄位說明

適用：`daily_report.py`

#### Summary

| 欄位 | 說明 |
| --- | --- |
| `Report Date` | 報告產生日期。 |
| `Stocks Scanned` | 掃描股票總數。 |
| `Candidates` | 符合條件的候選股票數。 |
| `BUY Count` | 候選清單中的 BUY 數量。 |
| `WATCH Count` | 候選清單中的 WATCH 數量。 |
| `Average Score` | 候選股票平均技術分數。 |
| `Average Volume Ratio` | 候選股票平均成交量比例。 |

#### Candidates

| 欄位 | 說明 |
| --- | --- |
| `Rank` | 候選股票排名。 |
| `Stock` | 股票代號。 |
| `Signal` | 技術訊號，通常為 `BUY` 或 `WATCH`。 |
| `Score` | 技術分數。 |
| `Close` | 最新收盤價。 |
| `Volume_Ratio` | 成交量與 20 日均量的比例。 |
| `RSI` | 相對強弱指標。 |
| `Analysis` | 文字化技術分析摘要。 |

#### All / Errors

- `All`: 保留完整 `scan_stocks.py` 掃描結果。
- `Errors`: 保留 `Status != OK` 的失敗股票與錯誤訊息。

### Stock Ranking 欄位說明

適用：`scan_stocks.py`

| 欄位 | 說明 |
| --- | --- |
| `Rank` | 排名，只針對成功分析的股票排序。 |
| `Stock` | 使用者輸入的股票代號。 |
| `Symbol` | 實際資料代號，例如 `2330.TW` 或 `6488.TWO`。 |
| `Date` | 最新資料日期。 |
| `Signal` | 技術訊號，可能為 `BUY` / `WATCH` / `HOLD` / `SELL`。 |
| `Score` | 技術分數，越高代表多方條件越集中。 |
| `Close` | 最新收盤價。 |
| `MA5` / `MA20` / `MA60` | 移動平均線。 |
| `RSI` | 相對強弱指標。 |
| `MACD` / `MACD_Signal` | MACD 與訊號線。 |
| `K` / `D` | KD 指標。 |
| `BB_Upper` / `BB_Middle` / `BB_Lower` | 布林通道上軌、中線、下軌。 |
| `ATR` | 平均真實波幅，用於觀察波動程度。 |
| `OBV` | 能量潮指標。 |
| `Volume_Ratio` | 成交量與 20 日均量的比例。 |
| `Analysis` | 文字化技術分析摘要。 |
| `Status` | `OK` 或 `ERROR`。 |
| `Error` | 錯誤訊息，成功時為空白。 |

提醒：

- `ERROR` 股票會保留在輸出中，方便追蹤失敗原因。
- `Rank` 只套用在 `Status=OK` 的股票。

### Benchmark 欄位說明

適用：`benchmark.py`

#### Summary

| 欄位 | 說明 |
| --- | --- |
| `Runs` | 正式 benchmark 次數。 |
| `Warmup Runs` | 暖身次數，不納入統計。 |
| `Stocks` | 股票數量。 |
| `Workers` | 執行緒數。 |
| `Period` | 分析期間。 |
| `Interval` | K 線週期。 |
| `Auto Adjust` | 是否使用 yfinance 調整價。 |
| `Force Refresh` | 是否忽略快取重新下載。 |
| `Avg OK` | 平均成功數。 |
| `Avg ERROR` | 平均失敗數。 |
| `Avg Success Rate %` | 平均成功率。 |
| `Avg Elapsed Seconds` | 平均總耗時。 |
| `Min Elapsed Seconds` | 最快總耗時。 |
| `Max Elapsed Seconds` | 最慢總耗時。 |
| `Avg Seconds Per Stock` | 平均每檔耗時。 |
| `Avg Stocks Per Second` | 平均每秒處理檔數。 |

#### Detail

| 欄位 | 說明 |
| --- | --- |
| `Run` | 第幾次正式 benchmark。 |
| `Stocks` | 股票數量。 |
| `OK` | 成功數。 |
| `ERROR` | 失敗數。 |
| `Workers` | 執行緒數。 |
| `Period` | 分析期間。 |
| `Interval` | K 線週期。 |
| `Auto Adjust` | 是否使用調整價。 |
| `Force Refresh` | 是否忽略快取。 |
| `Elapsed Seconds` | 該次總耗時。 |
| `Seconds Per Stock` | 該次平均每檔耗時。 |
| `Stocks Per Second` | 該次每秒處理檔數。 |
| `Success Rate %` | 該次成功率。 |

#### Errors

| 欄位 | 說明 |
| --- | --- |
| `Run` | 第幾次 benchmark。 |
| `Stock` | 失敗股票代號。 |
| `Symbol` | 資料代號，若尚未取得可能為空。 |
| `Error` | 錯誤訊息。 |

### Parameter Sweep 欄位說明

適用：`parameter_sweep.py`

| 欄位 | 說明 |
| --- | --- |
| `Rank` | 依指定 `sort-by` 排序後的排名。 |
| `Strategy` | 策略名稱，`ma_cross` / `rsi` / `score`。 |
| `Parameters` | 該次測試的策略參數。 |
| `Total Return %` | 策略總報酬率。 |
| `Buy and Hold Return %` | 買進持有報酬率。 |
| `CAGR %` | 年化報酬率。 |
| `Trade Count` | 交易次數。 |
| `Win Rate %` | 勝率。 |
| `Max Drawdown %` | 最大回撤。 |
| `Profit Factor` | 獲利因子，總獲利 / 總虧損。 |
| `Sharpe Ratio` | 夏普比率。 |
| `Sortino Ratio` | 索提諾比率。 |
| `Error` | 該參數組合錯誤訊息，成功時為空白。 |

提醒：

- `Rank` 只套用在成功測試的參數組合。
- `Error` 不為空代表該組參數失敗，但不影響其他參數組合。
- `--sort-by` 只能使用支援的數值欄位。
- `--top <= 0` 會顯示全部結果。

### Walk Forward 欄位說明

適用：`walk_forward.py`

#### Detail

| 欄位 | 說明 |
| --- | --- |
| `Window` | 第幾個 walk-forward 視窗。 |
| `Train Start` | 訓練區間開始日期。 |
| `Train End` | 訓練區間結束日期。 |
| `Test Start` | 驗證區間開始日期。 |
| `Test End` | 驗證區間結束日期。 |
| `Strategy` | 策略名稱。 |
| `Parameters` | 在 train 區間選出的最佳參數。 |
| `Train Total Return %` | 訓練區間總報酬率。 |
| `Test Total Return %` | 驗證區間總報酬率。 |
| `Train CAGR %` | 訓練區間年化報酬率。 |
| `Test CAGR %` | 驗證區間年化報酬率。 |
| `Train Trade Count` | 訓練區間交易次數。 |
| `Test Trade Count` | 驗證區間交易次數。 |
| `Train Win Rate %` | 訓練區間勝率。 |
| `Test Win Rate %` | 驗證區間勝率。 |
| `Train Max Drawdown %` | 訓練區間最大回撤。 |
| `Test Max Drawdown %` | 驗證區間最大回撤。 |
| `Train Profit Factor` | 訓練區間獲利因子。 |
| `Test Profit Factor` | 驗證區間獲利因子。 |
| `Train Sharpe Ratio` | 訓練區間夏普比率。 |
| `Test Sharpe Ratio` | 驗證區間夏普比率。 |
| `Train Sortino Ratio` | 訓練區間索提諾比率。 |
| `Test Sortino Ratio` | 驗證區間索提諾比率。 |
| `Error` | 該視窗錯誤訊息，成功時為空白。 |

#### Summary

| 欄位 | 說明 |
| --- | --- |
| `Stock` | 股票代號。 |
| `Period` | 分析期間。 |
| `Strategy` | 策略範圍。 |
| `Train Days` | 訓練區間交易日數。 |
| `Test Days` | 驗證區間交易日數。 |
| `Step Days` | 每次視窗往後移動的交易日數。 |
| `Windows` | 視窗數量。 |
| `Avg Test Total Return %` | 驗證區間平均總報酬率。 |
| `Avg Test CAGR %` | 驗證區間平均年化報酬率。 |
| `Avg Test Sharpe Ratio` | 驗證區間平均夏普比率。 |
| `Avg Test Max Drawdown %` | 驗證區間平均最大回撤。 |
| `Positive Test Windows` | 驗證區間報酬率為正的視窗數。 |
| `Positive Test Windows %` | 驗證區間報酬率為正的比例。 |
| `Error Windows` | 失敗視窗數。 |

提醒：

- Walk Forward 用 train 選參數、用 test 驗證，目的是降低過度擬合風險。
- Test 結果才是更重要的驗證參考。
- 仍然只是歷史收盤價回測，不代表未來績效。

## 常見問題 FAQ

### Q: 執行 python 指令時出現 `'python' is not recognized...` 怎麼辦？

### A:

這通常代表 Python 尚未加入 PATH，或目前終端機找不到 Python 執行檔。

建議先確認 Python 是否已安裝：

```bash
python --version
```

如果仍然找不到 `python`，可以在 Windows PowerShell 使用完整路徑執行，例如：

```powershell
& "C:\Users\YourName\AppData\Local\Programs\Python\Python312\python.exe" main.py
```

你也可以把 Python 安裝路徑加入系統 PATH，之後就能直接使用 `python` 指令。

### Q: `pip install -r requirements.txt` 失敗怎麼辦？

### A:

可以先升級 pip，再重新安裝 requirements。

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果你的環境中 `python` 指令無法使用，請改用 Python 完整路徑搭配 `-m pip` 執行。

### Q: yfinance 下載不到資料怎麼辦？

### A:

可能原因包含：

- 網路問題
- Yahoo Finance 暫時限流
- 股票代號錯誤

建議：

- 稍後重試
- 使用 `--force-refresh` 忽略快取並重新下載
- 確認股票代號是否正確

部分情況下，若未使用除權息調整價，程式會自動嘗試 TWSE / TPEX 官方 fallback。

### Q: `2330.TW` 和 `6488.TWO` 是什麼意思？

### A:

這是台股資料來源使用的代號格式：

- `.TW` = 通常代表上市股票
- `.TWO` = 通常代表上櫃股票

範例：

```text
2330 -> 2330.TW
6488 -> 6488.TWO
```

使用本工具時通常只需要輸入數字股票代號。程式會先嘗試 `.TW`，如果 yfinance 查無資料，再嘗試 `.TWO`。若 `.TW` 失敗但 `.TWO` 成功，中間的 yfinance 原生錯誤訊息不會直接顯示。若你已知市場別，可以直接輸入完整代號，例如 `2330.TW` 或 `8069.TWO`。多股票掃描時，工具會盡量抑制 yfinance 內部錯誤輸出，並保護進度輸出，避免錯誤訊息或進度行互相干擾，最後改由工具統一記錄 ERROR。

如果 `.TW` 與 `.TWO` 都失敗，可能原因包含股票已下市、股票代號錯誤、Yahoo Finance 暫時無資料，或資料源暫時限流。例如 `2888` 這類歷史代號或下市合併類型，工具可能無法取得正常價格資料，建議從 `stocks.txt` 移除，或保留在輸出錯誤清單中追蹤。

### Q: 什麼是 `auto_adjust`？

### A:

`auto_adjust` 是 yfinance 的除權息調整價設定，適合用於較長期的價格觀察與回測。

提醒：

使用 `auto_adjust` 時，程式不會混用 TWSE / TPEX 官方 fallback，因為官方 fallback 目前提供的是未除權息調整資料。

### Q: 為什麼我明明重新執行，速度卻變很快？

### A:

這通常是因為使用了 cache。

補充：

- cache 位於 `cache/`
- 當天快取會直接使用
- 使用 `--force-refresh` 可忽略快取並重新下載

cache 可以減少重複下載資料的時間，也能讓大量掃描更快完成。

### Q: 輸出 Excel 失敗怎麼辦？

### A:

最常見原因是 Excel 檔案仍被開啟，Windows 特別容易遇到這種情況。

建議：

- 關閉正在開啟的 Excel 檔案
- 重新執行指令
- 換一個輸出檔名

### Q: 出現資料不足（Data too short）怎麼辦？

### A:

技術指標需要足夠的歷史資料才能計算，例如 MA60、RSI、MACD、KD 等都需要累積資料。

建議：

- 增加 `period`
- 使用 `1y` 或 `2y`

範例：

```bash
python main.py --stock 2330 --period 2y
```

### Q: Walk Forward 顯示資料不足怎麼辦？

### A:

Walk Forward 需要資料量大於 `train_days + test_days`，否則無法建立任何 train / test 視窗。

建議：

- 增加 `period`
- 降低 `--train-days`
- 降低 `--test-days`

範例：

```bash
python walk_forward.py --stock 2330 --strategy all --period 10y
```

### Q: Parameter Sweep 很好，為什麼 Walk Forward 很差？

### A:

這可能代表發生過度擬合（Overfitting）。

`parameter_sweep.py` 只是在歷史資料中找出表現較佳的參數；`walk_forward.py` 則會用不同區間驗證參數是否穩定。

提醒：

Walk Forward 結果通常比單純 Parameter Sweep 更有參考價值。

### Q: 本工具能預測未來股價嗎？

### A:

不能。

說明：

- 本工具是技術分析與回測工具
- 不使用 AI 預測
- 不保證未來績效
- 不提供投資建議

### Q: 本工具能自動下單嗎？

### A:

不能。

目前：

- 不串接券商 API
- 不提供自動交易
- 僅供研究用途

## 測試

```bash
python -m unittest discover -s tests
```

目前測試涵蓋：

- 技術指標欄位與資料不足錯誤
- 訊號分數與 BUY / WATCH / HOLD / SELL 門檻
- 回測交易、停損、停利、最大持有天數
- 多股票掃描篩選與排序
- `clean_stocks.py` 股票清單讀取、重複偵測、Excel 與 clean txt 輸出
- 快取工具
- data loader 快取、TWSE/TPEX fallback 路由
- `main.py` CLI / 互動式入口
- `benchmark.py` Summary / Detail / Errors
- `score_strategy` 分數門檻
- `strategy_compare.py` 分數門檻 CLI 傳遞
- `parameter_sweep.py` 參數組合、排序、錯誤處理
- `walk_forward.py` 視窗切分、策略驗證、錯誤處理與 Excel 輸出
- `twstock daily` Summary、候選股篩選、排序、錯誤處理與 Markdown 輸出

## 根目錄進入點政策 (Root Entrypoint Policy)

為確保向下相容並簡化執行流程，專案保留了多個根目錄（root）的腳本作為進入點（entrypoints）。這些腳本主要做為現代 CLI 模組的橋樑：

1. **保留的 Report Wrappers：**
   - `backtest_report.py`
   - `parameter_sweep_report.py`
   - `walk_forward_report.py`
   這些檔案仍作為支援的相容性進入點。

2. **對齊的 Legacy Root Wrappers：**
   - `parameter_sweep.py`
   - `walk_forward.py`
   這些檔案直接將執行（Direct execution）導向現代的 Report CLI。

3. **直接執行行為（Direct Execution Behavior）：**
   - 執行 `python parameter_sweep.py ...` 會使用現代的 Parameter Sweep Report CLI。
   - 執行 `python walk_forward.py ...` 會使用現代的 Walk Forward Report CLI。
   - `python parameter_sweep_report.py ...` 與 `python walk_forward_report.py ...` 仍為支援的相容進入點。
   - `python backtest_report.py ...` 仍為支援的 Report CLI 進入點。

4. **Import 相容性：**
   - `import parameter_sweep` 仍相容並對應於 `tw_stock_tool.backtesting.parameter_sweep`。
   - `import walk_forward` 仍相容並對應於 `tw_stock_tool.backtesting.walk_forward`。

5. **統一 CLI 政策（Unified CLI Policy）：**
   - `twstock parameter-sweep` 會直接導向 `tw_stock_tool.cli.parameter_sweep_report.main`。
   - `twstock walk-forward` 會直接導向 `tw_stock_tool.cli.walk_forward_report.main`。
   - 統一的 CLI **不會**透過根目錄 wrapper 檔案進行路由，而是直接呼叫內部套件。

## 專案結構

```text
tw_stock_tool/
  .github/
    workflows/
      python-tests.yml          # GitHub Actions：執行 unittest

  src/
    tw_stock_tool/
      __init__.py

      analysis/                 # 單股分析、多股票掃描、股票篩選共用邏輯
      backtesting/              # 回測、策略、績效指標、Signal adapter
      cli/                      # package 內的 CLI 入口
      data/                     # 資料下載、股票清單更新、資料快取
      gui/                      # Tkinter GUI 原型相關模組
      ml/                       # AI / ML 研究用 baseline 與資料集流程
      reports/                  # 報表輸出與摘要整理
      scanners/                 # Daily Watchlist / 股票雷達
      strategies/               # 策略或策略相關擴充
      utils/                    # 設定、路徑與共用工具

  tw_stock_tool/
    __init__.py                 # 相容 src layout 的 package shim

  tests/                        # unittest 測試

  output/                       # 報表輸出資料夾，執行後自動產生
  cache/                        # 價格資料快取資料夾，執行後自動產生

  main.py                       # 單股分析 wrapper
  scan_stocks.py                # 多股票掃描 wrapper
  daily_report.py               # 每日候選報告 wrapper
  daily_watchlist.py            # Daily Watchlist / 股票雷達 wrapper
  strategy_compare.py           # 策略比較 wrapper
  parameter_sweep.py            # 參數掃描 wrapper
  walk_forward.py               # Walk Forward 驗證 wrapper
  benchmark.py                  # 大量股票掃描效能測試 wrapper
  clean_stocks.py               # 股票清單檢查 wrapper
  doctor.py                     # 環境檢查 wrapper
  twstock_cli.py                # 統一 CLI 入口

  pyproject.toml
  requirements.txt
  README.md
```

### 架構說明

本專案採用 `src/` layout，主要程式邏輯放在 `src/tw_stock_tool/`。

根目錄的 `main.py`、`scan_stocks.py`、`daily_report.py`、`daily_watchlist.py`、`strategy_compare.py`、`parameter_sweep.py`、`walk_forward.py` 等檔案主要是相容舊用法的 thin wrapper，方便使用者直接執行：

```bash
python main.py --stock 2330
python scan_stocks.py --file stocks.txt
python daily_watchlist.py --stock 2330 --output-excel --output-md
```

若使用：

```bash
pip install -e .
```

則可以讓 package import 與 CLI 使用更穩定。後續開發也應優先把主要邏輯放在 `src/tw_stock_tool/` 內，再視需要保留根目錄 wrapper。

### 主要模組職責

| 模組 | 職責 |
| --- | --- |
| `analysis/` | 單股分析、多股票掃描、股票篩選與分析流程整合 |
| `backtesting/` | 回測引擎、策略、績效指標、BacktestResult、Signal 標準化 |
| `data/` | yfinance / TWSE / TPEx 資料下載、股票清單、cache |
| `scanners/` | Daily Watchlist / 股票雷達候選股偵測 |
| `reports/` | Excel / Markdown / 報告輸出輔助 |
| `ml/` | AI / ML 研究流程與 baseline model |
| `cli/` | package 內 CLI 解析與入口 |
| `gui/` | 本機 Tkinter GUI 原型 |
| `utils/` | 共用設定、路徑、常數與工具函式 |

### 開發原則

- 新功能的主要邏輯應放在 `src/tw_stock_tool/`。
- 根目錄 `.py` 檔案優先維持 thin wrapper，避免把新邏輯塞回根目錄。
- 測試放在 `tests/`，並使用 `unittest`。
- `output/` 與 `cache/` 是執行後產生的資料夾，不應放入核心邏輯。
- 本專案目前仍是研究工具，不提供自動下單、不串接券商 API，也不保證投資績效。

## 注意事項

- 本工具僅供研究、教學與技術分析參考。
- 本工具不保證投資績效，也不宣稱能準確預測股價。
- 本工具不提供自動下單。
- 本工具不串接券商 API。
- 官方 fallback 與 yfinance 的資料口徑可能不同，尤其是除權息調整與成交量單位，正式使用前請自行比對。

## 開發與安全文件

本專案目前仍是台股研究工具，不提供投資建議，也不保證獲利。若要理解長期功能方向、策略訊號標準與未來自動下單前置安全條件，請先閱讀：

- [Development Roadmap](docs/DEVELOPMENT_ROADMAP.md)
- [Signal Standard](docs/SIGNAL_STANDARD.md)
- [Auto Trading Safety](docs/AUTO_TRADING_SAFETY.md)

自動下單是長期目標，不是目前功能；在任何真實下單前，必須完成 Backtest 標準化、Parameter Sweep、Walk Forward、Paper Trading、Risk Manager、Kill Switch 與 Trade Log。
目前專案已完成研究用的 simulated paper trading artifact/export 邊界；尚未開始 live paper trading、Broker integration、半自動下單、自動下單或 AI 自動決策。
