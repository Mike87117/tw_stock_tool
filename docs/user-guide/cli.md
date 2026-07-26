# CLI 使用指南

twstock 是正式命令列入口，適用於台股歷史研究；不連接券商、不執行真實交易，也不構成投資建議。

## 安裝與檢查

~~~bash
pip install -e .
twstock doctor
~~~

## 常用命令

~~~bash
twstock analyze --stock 2330 --period 2y
twstock scan --auto-stock-list --stock-limit 50
twstock daily --auto-stock-list --stock-limit 50 --output-md
twstock strategy-compare --stock 2330 --period 2y
twstock backtest-report --stock 2330 --strategy ma_cross --output-excel
twstock parameter-sweep --stock 2330 --strategy all --period 2y --output-excel
twstock walk-forward --stock 2330 --strategy ma_cross --period 10y --output-excel
twstock ai-report --stock 2330 --period 5y --horizon 5 --output-excel
twstock ml-dataset --stock 2330 --period 5y --horizon 5 --output-csv
twstock simulated-paper-trading --stock 2330 --strategy ma_cross --initial-cash 100000 --quantity-per-trade 1000
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
twstock simulated-portfolio-artifact inspect output/portfolio.json
twstock gui
~~~

## Simulated Portfolio Trading 風險限制

`simulated-portfolio-trading` 支援 4 個可選的 portfolio 風險限制參數：

- `--max-order-notional`: 單筆委託名目金額上限（有限且 strict > 0 數值）。
- `--max-position-quantity`: 單一標的持倉股數上限（嚴格正整數）。
- `--max-position-notional`: 單一標的持倉名目金額上限（有限且 strict > 0 數值）。
- `--max-total-exposure`: 整體組合總曝險上限（有限且 strict > 0 數值）。

規則與注意事項：

- 四個限制全部為可選（optional）。省略該參數即代表停用該項限制。
- 數值 `0` 或負值不是「停用」，而是無效設定，會導致 CLI 驗證失敗（fail closed）。
- `--max-position-quantity` 必須為正整數；其餘三個限制必須為有限且嚴格大於零（> 0）的數值。
- Portfolio risk caps 用於限制增加曝險的 BUY 委託。
- SELL 委託會 bypass 這四個 portfolio risk caps，避免風險限制阻擋減倉或平倉。
- Caller 提供的 fixed guard 或 custom guard 不一定 bypass SELL。
- 觸發風控限制（Risk limit exceeded）屬於正常的 simulated rejection，模擬交易會繼續進行並記錄於 rejection / audit log。
- Provider 異常、資料缺失或執行錯誤仍會觸發 fail closed 機制並中斷執行。
- 所有功能僅供台股歷史研究，不保證獲利或避免風險/虧損；不連接 broker，亦不構成投資建議。

## AI、ML 與 GUI

~~~bash
twstock ai-report --stock 2330 --period 5y --horizon 5 --output-excel
twstock ml-dataset --stock 2330 --period 5y --horizon 5 --output-csv
twstock gui
~~~

AI Report 與 ML Dataset 僅供歷史研究；GUI 是本機 prototype，不提供投資建議，也不連接 broker。AI walk-forward split 與 baseline model 僅透過 `tw_stock_tool.ml.*` package API 使用。

## 專題文件

- [資料來源與快取](data-and-cache.md)
- [股票清單與掃描](stock-list-and-scanning.md)
- [Daily Report](daily-report.md)
- [Artifact 操作](artifacts.md)
- [Root entry removal record](../archive/root-wrapper-removal.md)

以 twstock --help 或 twstock <command> --help 確認目前可用參數。
