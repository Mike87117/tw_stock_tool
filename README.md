# tw_stock_tool

台股技術分析與研究工具，提供單股分析、掃描、歷史回測、報告與模擬紙上交易的離線研究流程。

這不是券商下單系統：不連接券商、不執行真實交易、不提供投資建議，也不保證獲利。

![Python Tests](https://github.com/Mike87117/tw_stock_tool/actions/workflows/python-tests.yml/badge.svg)

## 快速開始

~~~bash
pip install -e .
twstock doctor
~~~

twstock 是正式命令列入口。

## 常用研究流程

~~~bash
twstock analyze --stock 2330 --period 2y
twstock scan --auto-stock-list --stock-limit 50
twstock daily --auto-stock-list --stock-limit 50 --output-md
twstock strategy-compare --stock 2330 --period 2y
twstock backtest-report --stock 2330 --strategy ma_cross --output-excel
twstock parameter-sweep --stock 2330 --strategy all --period 2y --output-excel
twstock walk-forward --stock 2330 --strategy ma_cross --period 10y --output-excel
~~~

結果僅供歷史研究，不構成投資建議。

## 文件導覽

[文件首頁](docs/index.md)是唯一主要入口。常用文件：

- [CLI 使用指南](docs/user-guide/cli.md)
- [資料來源與快取](docs/user-guide/data-and-cache.md)
- [股票清單與掃描](docs/user-guide/stock-list-and-scanning.md)
- [Daily Report](docs/user-guide/daily-report.md)
- [Artifact 操作](docs/user-guide/artifacts.md)
- [Root compatibility wrappers](docs/compatibility/root-wrappers.md)

## Repository map

~~~text
一般使用者
└── twstock CLI

正式實作
└── src/tw_stock_tool/
    ├── analysis/、backtesting/、cli/、data/、gui/
    ├── kill_switch/、ml/、paper_trading/、reports/、risk/
    └── scanners/、simulated_paper_trading_guard/、ui/、utils/

Repository root 的 Python 檔案
└── retained compatibility entries，不是主要實作位置
~~~

Root Python scripts 仍保留為歷史相容入口；新使用者應優先使用 twstock。完整對照表見 [root wrapper compatibility](docs/compatibility/root-wrappers.md)。
