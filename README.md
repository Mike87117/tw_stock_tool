# tw_stock_tool

台股技術分析與研究工具，提供單股分析、掃描、歷史回測、報告，以及模擬紙上交易的離線研究流程。

這不是券商下單系統：不連接券商、不執行真實交易、不提供投資建議，也不保證獲利。

![Python Tests](https://github.com/Mike87117/tw_stock_tool/actions/workflows/python-tests.yml/badge.svg)

## 快速開始

請從專案根目錄安裝，並先確認本機環境：

```bash
pip install -e .
twstock doctor
```

`twstock` 是正式的命令列入口。完整指令說明、輸出、快取與排錯方式請見[使用指南](docs/user-guide/cli.md)。

## 常用研究流程

```bash
twstock analyze --stock 2330 --period 2y
twstock scan --auto-stock-list --stock-limit 50
twstock daily --auto-stock-list --stock-limit 50 --output-md
twstock strategy-compare --stock 2330 --period 2y
twstock backtest-report --stock 2330 --strategy ma_cross --output-excel
twstock parameter-sweep --stock 2330 --strategy all --period 2y --output-excel
twstock walk-forward --stock 2330 --strategy ma_cross --period 10y --output-excel
twstock simulated-paper-trading-export result.json --output-markdown report.md
```

以上命令用於研究與歷史資料分析；結果不構成投資建議。

## 文件導覽

[文件首頁](docs/index.md)是唯一的文件入口，包含：

- [使用指南](docs/user-guide/cli.md)：安裝、CLI、輸出、快取與排錯。
- [開發指南](docs/developer-guide/contributing.md)：套件結構、測試與相容性注意事項。
- [架構概覽](docs/architecture/overview.md)：目前的正式實作位置與模組分工。
- [Root compatibility wrappers](docs/compatibility/root-wrappers.md)：歷史 root Python 入口與對應的正式目標。
- [歷史與決策紀錄](docs/archive/index.md)：phase、audit 與 roadmap 文件的閱讀方式。

## Repository map

```text
一般使用者
└── twstock CLI

正式實作
└── src/tw_stock_tool/
    ├── analysis/                       指標、訊號與分析
    ├── backtesting/                    回測、參數搜尋與 Walk Forward
    ├── cli/                            指令入口
    ├── data/                           資料來源與快取
    ├── gui/                            本機 GUI 原型
    ├── kill_switch/                    停止條件模型
    ├── ml/                             ML 研究工具
    ├── paper_trading/                  模擬紙上交易研究
    ├── reports/                        報告建構與輸出
    ├── risk/                           風險判斷模型
    ├── scanners/                       專用掃描流程
    ├── simulated_paper_trading_guard/  模擬交易防護邊界
    ├── ui/                             唯讀 UI 邊界
    └── utils/                          共用工具

Repository root 的 Python 檔案
└── 歷史相容入口，不是主要實作位置
```

## 歷史相容入口

Repository root 的 Python scripts 仍保留為歷史相容入口。新使用者應優先使用 `twstock`；完整對照表、直接模組目標與入口型態請見 [root wrapper compatibility](docs/compatibility/root-wrappers.md)。
