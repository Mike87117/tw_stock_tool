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
python parameter_sweep.py --stock 2330 --period 2y --strategy ma_cross --output
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
- `--sort-by`: ??????? `Total Return %`?????????
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
- `--force-refresh`: 忽略快取重新下載
- `--output`: 輸出 CSV，省略路徑時使用 `output/{stock}_parameter_sweep.csv`
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

注意：參數掃描只是歷史回測比較，不代表未來績效，也不提供投資建議。單一參數組合失敗時，工具會記錄在 `Error` 欄位並繼續掃描其他組合。

## 資料來源與快取

主要資料來源為 yfinance。若 yfinance 無資料且 `auto_adjust=False`，會嘗試官方 fallback：

- `.TW`: TWSE 官方日成交資訊
- `.TWO`: TPEX 官方個股月成交資訊；若月資料端點回空，會退到 TPEX openapi 最近一日收盤行情

注意：官方 fallback 目前提供未除權息調整的日資料，只支援 `1d` interval。TPEX openapi 備援只保證最近一日資料可用，長週期指標仍可能因資料筆數不足而失敗。若你需要除權息調整價，請使用 yfinance 的 `--auto-adjust`，此時不會混用官方 fallback。

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

## 測試

```bash
python -m unittest discover -s tests
```

目前測試涵蓋：

- 技術指標欄位與資料不足錯誤
- 訊號分數與 BUY / WATCH / HOLD / SELL 門檻
- 回測交易、停損、停利、最大持有天數
- 多股票掃描篩選與排序
- 快取工具
- data loader 快取、TWSE/TPEX fallback 路由
- `main.py` CLI / 互動式入口
- `benchmark.py` Summary / Detail / Errors
- `score_strategy` 分數門檻
- `strategy_compare.py` 分數門檻 CLI 傳遞
- `parameter_sweep.py` 參數組合、排序、錯誤處理

## 專案結構

```text
tw_stock_tool/
  .github/workflows/python-tests.yml
  main.py
  scan_stocks.py
  strategy_compare.py
  parameter_sweep.py
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

