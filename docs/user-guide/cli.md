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
~~~

## 專題文件

- [資料來源與快取](data-and-cache.md)
- [股票清單與掃描](stock-list-and-scanning.md)
- [Daily Report](daily-report.md)
- [Artifact 操作](artifacts.md)
- [Root compatibility wrappers](../compatibility/root-wrappers.md)

以 twstock --help 或 twstock <command> --help 確認目前可用參數。
