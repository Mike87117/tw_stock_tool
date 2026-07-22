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

所有 artifact、Markdown、Excel 與 CSV 都是歷史研究輸出，不是交易指令或投資建議。
