# 完整版台股分析工具

## 安裝方式

```bash
cd tw_stock_tool
pip install -r requirements.txt
```

## 執行方式

### 單股票分析

```bash
python main.py
```

依序輸入：
- 股票代號（例如 `2330`、`2317`、`2454`、`0050`）
- 分析期間（例如 `1y`、`2y`、`5y`、`max`）
- 是否強制重新下載資料（`y/n`）
- 停損百分比（空白代表不使用）
- 停利百分比（空白代表不使用）
- 最大持有天數（空白代表不使用）
- 每次投入資金比例（空白預設 `1.0`）
- 是否匯出 Excel（`y/n`）
- 是否儲存圖表（`y/n`）

### 多股票掃描器

直接輸入股票清單：

```bash
python scan_stocks.py --stocks 2330 2317 2454 2308 0050
```

從 txt 載入，每行一檔股票：

```bash
python scan_stocks.py --file stocks.txt
```

常用參數：

```bash
python scan_stocks.py --file stocks.txt --period 1y --workers 8
```

篩選 BUY / WATCH 訊號並只輸出前 10 名：

```bash
python scan_stocks.py --stocks 2330 2317 2454 --period 1y --signals BUY WATCH --top 10
```

依量能比排序、最低分數 3 分，並強制重新下載：

```bash
python scan_stocks.py --file stocks.txt --min-score 3 --sort-by Volume_Ratio --force-refresh
```

依量能比與價格篩選：

```bash
python scan_stocks.py --file stocks.txt --min-score 3 --min-volume-ratio 1.5 --sort-by Volume_Ratio
python scan_stocks.py --file stocks.txt --min-close 50 --max-close 500 --sheet-by-signal
```

只輸出失敗股票並寫入錯誤紀錄：

```bash
python scan_stocks.py --file stocks.txt --errors-only --log-errors
```

掃描時會顯示進度：

```text
[1/100] 2330 OK
[2/100] 2317 OK
```

若單一股票下載或分析失敗，程式會記錄錯誤並繼續掃描下一檔。

掃描器常用參數：

- `--min-score`: 只輸出分數大於等於指定值的股票
- `--signals`: 只輸出指定訊號，例如 `BUY WATCH`
- `--sort-by`: 支援 `Score`、`Volume_Ratio`、`RSI`、`Close`、`ATR`
- `--min-volume-ratio`: 只輸出量能比大於等於指定值的股票
- `--min-close`: 只輸出收盤價大於等於指定值的股票
- `--max-close`: 只輸出收盤價小於等於指定值的股票
- `--top`: 只輸出前 N 名 OK 股票
- `--errors-only`: 只輸出失敗股票
- `--log-errors`: 將錯誤輸出到 `output/scan_errors.log`
- `--force-refresh`: 忽略今日快取並重新下載
- `--sheet-by-signal`: Excel 依 `BUY / WATCH / HOLD / SELL` 分 sheet

### 策略比較器

比較內建策略：

```bash
python strategy_compare.py --stock 2330 --period 2y
```

套用回測參數：

```bash
python strategy_compare.py --stock 2330 --period 2y --stop-loss 8 --take-profit 20 --max-hold-days 30
```

調整策略參數：

```bash
python strategy_compare.py --stock 2330 --period 2y --ma-short 10 --ma-long 30 --rsi-buy-below 35 --rsi-sell-above 75
```

輸出 Excel：

```bash
python strategy_compare.py --stock 2330 --period 2y --output
```

內建策略：

- `score_strategy`: 使用現有 `signals.py` 的 `Signal`
- `ma_cross_strategy`: MA5 上穿/下穿 MA20
- `macd_strategy`: MACD 上穿/下穿 MACD Signal
- `rsi_strategy`: RSI < 30 買入，RSI > 70 賣出

### Benchmark 工具

量測多股票掃描耗時：

```bash
python benchmark.py --stocks 2330 2317 2454 --period 1y --workers 8
python benchmark.py --file stocks.txt --period 1y --workers 8 --output
```

輸出欄位包含股票數、成功/失敗數、worker 數、總秒數、每檔平均秒數。

### Cache 管理

```bash
python cache_manager.py --list
python cache_manager.py --summary
python cache_manager.py --clear
```

## 資料快取

- 下載成功後會寫入 `cache/`
- 快取檔名格式：`cache/{symbol}_{period}_{interval}_adjusted-{auto_adjust}.csv`
- 若快取檔是今天產生的，預設會直接讀取快取，減少重複下載
- 若快取損壞或讀取失敗，程式會自動重新下載
- 若要忽略快取，請使用 `--force-refresh`，或在 `main.py` 互動流程選擇強制重新下載
- `data_loader.download_tw_stock(..., verbose=True)` 可顯示資料來源：`From cache` 或 `Downloaded`
- 若 Yahoo/yfinance 無法取得 `.TW` 日線資料，且未使用調整價，會嘗試 TWSE fallback 的最小可用日線資料

## 功能說明

- 自動判斷台股代號後綴：先嘗試 `.TW`，失敗再嘗試 `.TWO`
- 使用 `yfinance` 下載 OHLCV 歷史資料
- 自動處理 `MultiIndex` 欄位
- 技術指標：
  - MA5 / MA20 / MA60 / MA120
  - RSI
  - MACD / MACD Signal / MACD Histogram
  - KD（K、D）
  - Bollinger Band（Upper、Middle、Lower）
  - ATR
  - OBV
  - Volume MA20 / Volume Ratio
- 訊號系統：`BUY / SELL / HOLD / WATCH`
- 分數制判斷與文字分析摘要
- 簡易回測：
  - BUY 買入、SELL 賣出
  - 初始資金 100000
  - 支援部位比例 `position_size`
  - 支援停損 `stop_loss_pct`
  - 支援停利 `take_profit_pct`
  - 支援最大持有天數 `max_hold_days`
  - 支援手續費與證交稅
  - 輸出勝率、最大回撤、CAGR、Exposure、Profit Factor、Sharpe、Sortino 等統計
- 圖表：
  - `mplfinance` K 線
  - 成交量
  - MA 與布林通道
  - RSI / MACD
  - 買賣點標記
- 報表輸出：
  - `output/<stock_id>_report.xlsx`
  - `output/<stock_id>_chart.png`
- 多股票排行榜輸出：
  - `output/stock_ranking.xlsx`
  - `output/stock_ranking.csv`
  - `output/stock_ranking.html`

## 多股票排行榜欄位

- `Rank`
- `Stock`
- `Symbol`
- `Date`
- `Signal`
- `Score`
- `Close`
- `MA5 / MA20 / MA60`
- `RSI`
- `MACD / MACD_Signal`
- `K / D`
- `BB_Upper / BB_Middle / BB_Lower`
- `ATR`
- `OBV`
- `Volume_Ratio`
- `Analysis`
- `Status`
- `Error`

## 專案結構

```text
tw_stock_tool/
├── main.py
├── scan_stocks.py
├── strategy_compare.py
├── benchmark.py
├── cache_manager.py
├── analysis.py
├── scanner.py
├── strategies.py
├── cache_utils.py
├── cache/
├── data_loader.py
├── indicators.py
├── signals.py
├── backtest.py
├── report.py
├── plotter.py
├── config.py
├── requirements.txt
└── README.md
```

## 測試方式

```bash
python -m unittest discover -s tests
```

## 注意事項

- 本工具為技術分析與回測用途，不保證預測準確率。
- 本工具僅供研究與技術分析，不保證任何投資績效。
- 不包含自動下單、券商 API 串接功能。
- 不提供自動下單功能。
- 若 Excel 檔案被開啟中，匯出可能失敗，請先關閉檔案後重試。
- 網路不穩時可能下載失敗，可稍後重試。
