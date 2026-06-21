# 台股技術分析工具

![Python Tests](https://github.com/Mike87117/tw_stock_tool/actions/workflows/python-tests.yml/badge.svg)

本工具用於台股技術分析、回測、多股票掃描、策略比較與 benchmark 研究。它不提供自動下單，不串接券商 API，也不保證投資績效。

## CI

本專案已加入 GitHub Actions：

- workflow: `.github/workflows/python-tests.yml`
- trigger: `push`、`pull_request`
- Python: `3.11`、`3.12`
- command: `python -m unittest discover -s tests`


## 安裝

```bash
cd tw_stock_tool
pip install -r requirements.txt
```

如果 Windows 環境中 `python` 不在 PATH，請改用你的 Python 絕對路徑執行，例如：

```powershell
& "C:\Users\Mike\AppData\Local\Programs\Python\Python312\python.exe" -m unittest discover -s tests
```

## 常用指令速查表

以下列出最常使用的指令，方便快速查找。

| 目的 | 指令 |
| --- | --- |
| 單股分析 | `python main.py --stock 2330 --period 2y` |
| 匯出單股分析 Excel | `python main.py --stock 2330 --period 2y --export-excel` |
| 輸出單股分析圖表 | `python main.py --stock 2330 --period 2y --save-chart` |
| 更新股票清單 | `python stock_list_updater.py --market all --output stocks.txt` |
| 多股票掃描 | `python scan_stocks.py --file stocks.txt` |
| 自動更新後多股票掃描 | `python scan_stocks.py --auto-stock-list` |
| 檢查股票清單 | `python clean_stocks.py --file stocks.txt --output --write-clean-file` |
| 每日候選股票報告 | `python daily_report.py --file stocks.txt --output` |
| 自動更新後每日候選股票報告 | `python daily_report.py --auto-stock-list --output` |
| 策略比較 | `python strategy_compare.py --stock 2330 --period 2y` |
| Parameter Sweep | `python parameter_sweep.py --stock 2330 --period 2y --output-excel` |
| Walk Forward Test | `python walk_forward.py --stock 2330 --period 10y --output` |
| 建立 ML Dataset | `python ml_dataset.py --stock 2330 --period 5y --horizon 5 --output` |
| AI Walk Forward skeleton | `python ai_walk_forward.py --stock 2330 --period 5y --horizon 5 --train-size 252 --test-size 63` |
| Baseline ML model | `python baseline_ml_model.py --stock 2330 --period 5y --horizon 5 --train-size 252 --test-size 63` |
| AI Prediction Report | `python ai_prediction_report.py --stock 2330 --period 5y --horizon 5 --output` |
| 多股票 AI 掃描 | `python ai_stock_scanner.py --file stocks.txt --period 5y --horizon 5 --output` |
| 自動更新後多股票 AI 掃描 | `python ai_stock_scanner.py --auto-stock-list --period 5y --horizon 5 --output` |
| Benchmark | `python benchmark.py --file stocks.txt --workers 8 --repeat 3` |
| 查看快取摘要 | `python cache_manager.py --summary` |
| 清除快取 | `python cache_manager.py --clear` |
| 執行全部測試 | `python -m unittest discover -s tests` |

### Auto Stock List ????

????? `--auto-stock-list` ???????????????????????????????? yfinance rate limit?

```bash
python scan_stocks.py --auto-stock-list --stock-limit 50
python daily_report.py --auto-stock-list --stock-limit 50 --output
python ai_stock_scanner.py --auto-stock-list --stock-limit 20 --output
```

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

這個範例適合第一次接觸本專案、還不熟悉技術分析、也不知道該先用哪個功能的使用者。以下使用 `2330` 作為主要範例股票，帶你從安裝到 Walk Forward 驗證完整跑一次。

### Step 1：安裝套件

先安裝需求套件。

```bash
pip install -r requirements.txt
```

確認 CLI 能正常顯示說明：

```bash
python main.py --help
```

### Step 2：準備股票清單

建立 `stocks.txt`，每行一個股票代號：

```text
2330
2317
2454
2308
2882
```

### Step 3：掃描股票

```bash
python scan_stocks.py --file stocks.txt
```

如果想直接產生每日候選清單 Excel：

```bash
python daily_report.py --file stocks.txt --output
```

這一步會從多檔股票中找出值得進一步研究的標的。

觀察：

- `Signal`
- `Score`
- `Volume_Ratio`
- `Analysis`

優先關注：

- `BUY`
- `WATCH`
- 高 `Score`
- 成交量放大

### Step 4：單股分析

假設對 `2330` 有興趣，可以執行：

```bash
python main.py --stock 2330 --period 2y
```

觀察：

- 技術指標
- 訊號
- 回測結果

如果要輸出 Excel：

```bash
python main.py --stock 2330 --period 2y --export-excel
```

如果要輸出圖表：

```bash
python main.py --stock 2330 --period 2y --save-chart
```

### Step 5：比較策略

```bash
python strategy_compare.py --stock 2330 --period 2y
```

比較：

- Score Strategy
- MA Cross Strategy
- RSI Strategy
- MACD Strategy

觀察：

- `Total Return %`
- `CAGR %`
- `Sharpe Ratio`
- `Max Drawdown %`

### Step 6：參數掃描

```bash
python parameter_sweep.py --stock 2330 --period 2y
python parameter_sweep.py --stock 2330 --period 2y --strategy ma_cross
```

如果要輸出 Excel：

```bash
python parameter_sweep.py --stock 2330 --period 2y --output-excel
```

觀察：

- 哪組參數回測較佳
- `Sharpe Ratio`
- `Total Return %`
- `Max Drawdown %`

提醒：

不要直接相信最佳參數。這一步只是在歷史資料上尋找表現較佳的參數組合。

### Step 7：Walk Forward 驗證

```bash
python walk_forward.py --stock 2330 --period 10y
```

如果要輸出 Excel：

```bash
python walk_forward.py --stock 2330 --period 10y --output
```

觀察：

- `Avg Test Total Return %`
- `Avg Test Sharpe Ratio`
- `Positive Test Windows %`

重點：

如果 train 很好但 test 很差，代表可能過度擬合。

### Step 8：效能測試（選擇性）

```bash
python benchmark.py --file stocks.txt --workers 8 --repeat 3
```

用途：

- 評估 cache 效果
- 評估 worker 數量
- 評估 force-refresh 成本

### 最後成果

執行完成後，使用者通常會得到：

- 股票排行 Excel
- 單股分析 Excel
- 單股分析圖表
- Parameter Sweep Excel
- Walk Forward Excel
- Benchmark 統計結果

### 最後提醒

注意事項：

- 本工具僅供研究與技術分析用途
- 不保證投資績效
- 不提供投資建議
- Walk Forward 比單純 Parameter Sweep 更有參考價值
- 歷史績效不代表未來績效

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
python daily_report.py --file stocks.txt --output
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
python parameter_sweep.py --stock 2330 --period 2y
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
python walk_forward.py --stock 2330 --period 10y
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

`clean_stocks.py` 用於檢查 `stocks.txt` 內股票代號是否有效，適合在 `daily_report.py` 或 `scan_stocks.py` 前先執行。它會重用 `data_loader.download_tw_stock()`，保留 `.TW` / `.TWO` fallback、快取與 yfinance quiet download 行為。

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

`daily_report.py` 用於每天快速產生值得研究的股票候選清單。它會重用既有多股票掃描器，先掃描股票，再依訊號與分數篩選候選股，最後可輸出 Excel 報表。

CLI 範例：

```bash
python daily_report.py --file stocks.txt
python daily_report.py --stocks 2330 2317 2454
python daily_report.py --file stocks.txt --signals BUY WATCH
python daily_report.py --file stocks.txt --min-score 4
python daily_report.py --file stocks.txt --top 20
python daily_report.py --file stocks.txt --output
python daily_report.py --file stocks.txt --output output/daily_report.xlsx
python daily_report.py --file stocks.txt --force-refresh
python daily_report.py --file stocks.txt --no-auto-adjust
```

常用參數：

- `--stocks`: 股票清單
- `--file`: 從 txt 載入股票清單
- `--period`: 分析期間，預設 `DEFAULT_PERIOD`
- `--interval`: K 線週期，預設 `DEFAULT_INTERVAL`
- `--signals`: 候選訊號，預設 `BUY WATCH`
- `--min-score`: 候選最低分數，預設 `4`
- `--top`: 候選股前 N 名，預設 `20`
- `--force-refresh`: 忽略快取重新下載
- `--auto-adjust` / `--no-auto-adjust`: 是否使用 yfinance 除權息調整價
- `--output`: 輸出 Excel，省略路徑時使用 `output/daily_report.xlsx`

Excel sheets：

- `Summary`: 報告日期、掃描股票數、候選股票數、BUY / WATCH 數量、平均分數與平均量比
- `Candidates`: 符合條件的候選股票
- `All`: 全部掃描結果
- `Errors`: 掃描失敗股票

候選股排序規則：

1. `Score` 由高到低
2. `Volume_Ratio` 由高到低

Daily Report 只是研究候選清單，不代表買賣建議，也不提供自動下單。

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
python strategy_compare.py --stock 2330 --period 2y --output
```

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
python parameter_sweep.py --stock 2330 --period 2y
python parameter_sweep.py --stock 2330 --period 2y --strategy ma_cross
python parameter_sweep.py --stock 2330 --period 2y --strategy rsi
python parameter_sweep.py --stock 2330 --period 2y --strategy score
python parameter_sweep.py --stock 2330 --period 2y --top 10
python parameter_sweep.py --stock 2330 --period 2y --output
python parameter_sweep.py --stock 2330 --period 2y --output-excel
python parameter_sweep.py --stock 2330 --period 2y --strategy ma_cross --output
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
- `--strategy`: `all`、`ma_cross`、`rsi`、`score`，預設 `all`
- `--sort-by`: 排序欄位，預設 `Total Return %`，僅支援下列數值欄位：
  - `Total Return %`
  - `Buy and Hold Return %`
  - `CAGR %`
  - `Trade Count`
  - `Win Rate %`
  - `Max Drawdown %`
  - `Profit Factor`
  - `Sharpe Ratio`
  - `Sortino Ratio`
- `--top`: 顯示前 N 筆，預設 `20`
  - `--top <= 0` 時會顯示全部結果
- `--force-refresh`: 忽略快取重新下載
- `--output`: 輸出 CSV，省略路徑時使用 `output/{stock}_parameter_sweep.csv`
- `--output-excel`: 輸出 Excel，省略路徑時使用 `output/{stock}_parameter_sweep.xlsx`
- `--stop-loss`: 停損百分比
- `--take-profit`: 停利百分比
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

CSV / Excel 輸出：

- `--output`: 輸出 CSV，預設路徑為 `output/{stock}_parameter_sweep.csv`。
- `--output-excel`: 輸出 Excel，預設路徑為 `output/{stock}_parameter_sweep.xlsx`。
- `--output-excel output/custom.xlsx`: 輸出 Excel 到指定路徑。
- Excel 會固定建立 `All`、`MA_Cross`、`RSI`、`Score`、`Errors` sheets。
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
python walk_forward.py --stock 2330 --period 5y
python walk_forward.py --stock 2330 --period 10y --strategy ma_cross
python walk_forward.py --stock 2330 --period 10y --strategy rsi
python walk_forward.py --stock 2330 --period 10y --strategy score
python walk_forward.py --stock 2330 --period 10y --train-days 504 --test-days 126
python walk_forward.py --stock 2330 --period 10y --output
python walk_forward.py --stock 2330 --period 10y --output output/2330_walk_forward.xlsx
```

參數說明：

- `--stock`：股票代號，必填
- `--period`：分析期間，預設 `DEFAULT_PERIOD`
- `--strategy`：`all`、`ma_cross`、`rsi`、`score`，預設 `all`
- `--train-days`：訓練區間交易日數，預設 `504`
- `--test-days`：驗證區間交易日數，預設 `126`
- `--step-days`：每次視窗往後移動的交易日數，預設等於 `test-days`
- `--sort-by`：train 區間選最佳參數用的欄位，預設 `Train Sharpe Ratio`
- `--force-refresh`：忽略快取重新下載
- `--output`：輸出 Excel，省略路徑時使用 `output/{stock}_walk_forward.xlsx`
- `--stop-loss`：停損百分比
- `--take-profit`：停利百分比
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

## 輸出檔案位置總覽

| 工具 | 功能 | 預設輸出位置 | 備註 |
| --- | --- | --- | --- |
| `main.py` | 單股分析 Excel | `output/{stock}_report.xlsx` | 需搭配 `--export-excel`。 |
| `main.py` | 單股分析圖表 | `output/{stock}_chart.png` | 需搭配 `--save-chart`。 |
| `scan_stocks.py` | 股票排行報表 | `output/stock_ranking.xlsx`<br>`output/stock_ranking.csv`<br>`output/stock_ranking.html` | 執行掃描後輸出；可用 `--output-dir` 指定資料夾。 |
| `scan_stocks.py` | 錯誤紀錄 | `output/scan_errors.log` | 需使用 `--log-errors`。 |
| `clean_stocks.py` | 股票清單檢查 Excel | `output/clean_stocks_report.xlsx` | 使用 `--output`；也可指定自訂路徑。 |
| `clean_stocks.py` | 有效股票清單 | `output/stocks_clean.txt` | 使用 `--write-clean-file`；只包含可正常取得資料的股票。 |
| `daily_report.py` | 每日候選清單 Excel | `output/daily_report.xlsx` | 使用 `--output`；也可指定自訂路徑。 |
| `strategy_compare.py` | 策略比較 Excel | `output/{stock}_strategy_compare.xlsx` | 需搭配 `--output`；也可指定自訂路徑。 |
| `parameter_sweep.py` | Parameter Sweep CSV | `output/{stock}_parameter_sweep.csv` | 使用 `--output`；也可指定自訂路徑。 |
| `parameter_sweep.py` | Parameter Sweep Excel | `output/{stock}_parameter_sweep.xlsx` | 使用 `--output-excel`；也可指定自訂路徑。 |
| `walk_forward.py` | Walk Forward Excel | `output/{stock}_walk_forward.xlsx` | 使用 `--output`；也可指定自訂路徑。 |
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
python walk_forward.py --stock 2330 --period 10y
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
- `daily_report.py` Summary、候選股篩選、排序、Errors sheet 與 Excel 輸出

## 專案結構

```text
tw_stock_tool/
  .github/workflows/python-tests.yml
  main.py
  scan_stocks.py
  clean_stocks.py
  daily_report.py
  strategy_compare.py
  parameter_sweep.py
  walk_forward.py
  benchmark.py
  cache_manager.py
  analysis.py
  scanner.py
  strategies.py
  cache_utils.py
  data_loader.py
  indicators.py
  signals.py
  backtest.py
  report.py
  plotter.py
  config.py
  requirements.txt
  README.md
  tests/
```

## 注意事項

- 本工具僅供研究、教學與技術分析參考。
- 本工具不保證投資績效，也不宣稱能準確預測股價。
- 本工具不提供自動下單。
- 本工具不串接券商 API。
- 官方 fallback 與 yfinance 的資料口徑可能不同，尤其是除權息調整與成交量單位，正式使用前請自行比對。
