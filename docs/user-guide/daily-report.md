# Daily Report

Daily Report 是歷史資料研究流程，輸出候選清單與可選的驗證摘要；不連接券商、不送出真實委託、不產生 live signals，也不構成投資建議。

## 基本使用

~~~bash
twstock daily --auto-stock-list --stock-limit 50 --output-md
~~~

股票 universe 可由 --stocks、--file 或 --auto-stock-list 提供。每次執行都會寫出 Markdown；預設為 output/daily_report.md。--output-md 可指定 Markdown 路徑，--output-excel 可接受輸出路徑參數；使用 --output-dir 調整預設資料夾。

## JSON artifact

加上 --output-json 會寫出 Daily Research Report JSON artifact。未指定路徑時，預設為 output/daily_report.json；可傳入自訂路徑。既有 JSON 不會被覆寫，除非同時給 --overwrite。

~~~bash
twstock daily --auto-stock-list --stock-limit 50 --output-md --output-json
twstock daily --auto-stock-list --stock-limit 50 --output-json reports/today.json --overwrite
~~~

## 操作既有 artifact

以下命令只讀取既有 JSON artifact：不重新抓取市場資料、不重跑 Daily Pipeline 或 backtest，也不重建 Excel。

~~~bash
twstock daily-report-artifact validate output/daily_report.json
twstock daily-report-artifact inspect output/daily_report.json
twstock daily-report-artifact export-markdown output/daily_report.json --output-markdown report.md
~~~

export-markdown 對既有檔案採保護模式；要取代檔案時加入 --overwrite。

## 可選驗證

--validate-top 預設為 0，代表不執行驗證。大於零時，會以指定 strategy 對排名前段候選進行歷史 backtest；可用 --validation-strategy（ma_cross、macd、rsi、score）及 --validation-initial-capital、--validation-fee-rate、--validation-tax-rate、--validation-position-size 調整假設。個別候選失敗會記錄在 highlights/limitations，不會把它描述為即時訊號；Excel schema 不因這些選項改變。

--parameter-sweep-top 與 --walk-forward-top 皆預設為 0。兩者都要求 --validate-top 大於零，且不得超過它；parameter sweep 只處理 successful backtest candidates，使用 --parameter-sweep-sort-by 排序。

walk-forward 同樣只處理 successful backtest candidates；--walk-forward-train-days、--walk-forward-test-days 的單位是 observation days，預設 126 與 63。未指定 --walk-forward-step-days 時使用 test days 作為有效 step。--walk-forward-sort-by 決定排序；validation financial assumptions 會沿用。MACD 可用於 backtest validation，但不支援 parameter sweep 或 walk-forward validation。
