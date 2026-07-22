# CLI 使用指南

`twstock` 是正式的命令列入口。所有功能皆用於台股研究與歷史資料分析，不連接券商、不執行真實交易，且不構成投資建議。

## 安裝與環境檢查

```bash
pip install -e .
twstock doctor
```

需要檢查可用的外部資料來源時，可執行：

```bash
twstock doctor --live
twstock stock-list smoke-check
twstock price-smoke-check
```

這些 smoke check 會接觸外部資料來源，並非單元測試的替代品。

## 常用命令

```bash
twstock analyze --stock 2330 --period 2y
twstock scan --auto-stock-list --stock-limit 50
twstock daily --auto-stock-list --stock-limit 50 --output-md
twstock strategy-compare --stock 2330 --period 2y
twstock backtest-report --stock 2330 --strategy ma_cross --output-excel
twstock parameter-sweep --stock 2330 --strategy all --period 2y --output-excel
twstock walk-forward --stock 2330 --strategy ma_cross --period 10y --output-excel
```

股票清單與快取管理：

```bash
twstock stock-list update --market all --output stocks.txt
twstock stock-list clean --file stocks.txt --output --write-clean-file
twstock cache --summary
```

以 `twstock --help` 或 `twstock <command> --help` 查看目前可用的參數。

## 報告與 artifact

```bash
twstock daily-report-artifact validate output/daily_report.json
twstock backtest-result-export --stock 2330 --strategy ma_cross --output-json output/backtest_result.json
twstock simulated-paper-trading-export result.json --output-markdown report.md
```

模擬紙上交易只用於離線、歷史研究；詳細邊界請見[模擬紙上交易 runtime 架構](../SIMULATED_PAPER_TRADING_RUNTIME_ARCHITECTURE.md)。

## 輸出、快取與排錯

預設輸出與快取位置可由 `TW_STOCK_TOOL_OUTPUT_DIR` 與 `TW_STOCK_TOOL_CACHE_DIR` 調整。資料來源或環境問題請先執行 `twstock doctor`，並由[文件首頁](../index.md)前往相應文件。
