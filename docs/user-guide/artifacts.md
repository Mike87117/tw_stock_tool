# Artifact 操作

Artifact 是研究結果的可攜 JSON，與產生它的分析命令不同：artifact 操作命令讀取既有檔案，不重新執行研究。

## Daily Research Report

Daily CLI 的 --output-json 產生 schema v1 artifact；未指定路徑時為 output/daily_report.json。支援 validate、inspect 與 export-markdown，詳見 [Daily Report](daily-report.md)。輸出檔存在時需使用 --overwrite。

## BacktestResult

~~~bash
twstock backtest-result-export --stock 2330 --strategy ma_cross --output-json output/backtest.json
twstock backtest-artifact validate output/backtest.json
twstock backtest-artifact inspect output/backtest.json
~~~

backtest-artifact 也支援 convert-to-simulated-paper-trading，要求 --output-json；既有輸出須以 --overwrite 明確取代。這是 retrospective offline mapping，不抓取資料或重新執行 backtest。

## Simulated paper trading

~~~bash
twstock simulated-paper-trading --stock 2330 --strategy ma_cross --initial-cash 100000 --quantity-per-trade 1000
twstock simulated-paper-trading-export result.json --output-markdown report.md
twstock simulated-paper-trading-export result.json --output-csv-dir csv
~~~

export 命令可輸出 Markdown、CSV bundle 或兩者；既有輸出須使用 --overwrite。CSV basename 預設為 simulated_paper_trading。讀取支援 schema versions 1、2、3；目前輸出為 version 3。

## Simulated Portfolio Trading

使用 `twstock simulated-portfolio-trading` 執行多股票歷史模擬並直接產生 schema v1 JSON artifact，並支援可選的 portfolio 風險限制（`--max-order-notional`, `--max-position-quantity`, `--max-position-notional`, `--max-total-exposure`）：

~~~bash
twstock simulated-portfolio-trading \
  --stocks 2330 2317 2454 \
  --strategy ma_cross \
  --initial-cash 1000000 \
  --quantity-per-trade 1000 \
  --max-order-notional 200000 \
  --max-position-quantity 3000 \
  --max-position-notional 500000 \
  --max-total-exposure 800000 \
  --period 2y \
  --output-json output/portfolio.json
~~~

說明：
- 觸發風控限制之拒絕紀錄會使用既有的 rejection、audit log 與 schema v1 結構記錄，不因 Phase 53.6 新增 schema version。
- 任一股票在取得資料、分析、策略執行或格式驗證失敗時，整個 portfolio 執行會立即失敗（fail closed），且不會在寫檔前建立 JSON artifact。寫檔與讀回驗證不具備 transactional rollback 保證。

產生 JSON artifact 後，使用離線工具操作：

~~~bash
twstock simulated-portfolio-artifact validate output/portfolio.json

twstock simulated-portfolio-artifact inspect output/portfolio.json

twstock simulated-portfolio-artifact export-markdown \
  output/portfolio.json \
  --output-markdown output/portfolio.md

twstock simulated-portfolio-artifact export-csv \
  output/portfolio.json \
  --output-csv-dir output/portfolio_csv
~~~

說明：
- 此命令只操作既有 JSON artifact。
- 不抓取市場資料。
- 不執行分析、策略、回測或 simulated trading。
- 不呼叫 multi-symbol coordinator。
- 不連接 broker。
- 不放置真實訂單。
- CSV 為七檔 bundle（包含 summary, positions, pending_orders, orders, fills, rejections, trade_log）。
- 預設不覆寫既有輸出；覆寫必須明確使用 `--overwrite`。
- 此功能是歷史研究輸出，不是投資建議。

所有 artifact、Markdown、Excel 與 CSV 都是歷史研究輸出，不是交易指令或投資建議。

## Workspace-managed Runs

Workspace mode stores each supported Scan、Daily Report 或 Backtest run below:

~~~text
workspace/
└── runs/YYYY/MM/<timestamp>_<workflow>_<run-id-prefix>/
    ├── manifest.json
    └── artifacts/
~~~

manifest.json is the run-level record and remains Run Manifest schema 1.0. Its managed artifact references are relative POSIX paths such as artifacts/stock_ranking.csv; they do not contain the original machine absolute Workspace path. The existing scan_catalog／scan_workspace API can scan the runs offline and reports missing or unsafe artifacts without fetching data or rerunning research. Re-running the same command creates another run directory and does not overwrite the earlier run.
Workspace run listing and inspection are offline and read-only. Damaged runs remain visible in 	wstock run list; inspect shows manifest metadata and catalog findings only, never artifact contents.
