# 文件導覽

本頁是 tw_stock_tool 的主要文件入口。現行 runtime source、pyproject.toml 與測試優先於歷史 phase 或 MVP 文件。

## 使用者

- [CLI 使用指南](user-guide/cli.md)：安裝與常用命令總覽。
- [資料來源與快取](user-guide/data-and-cache.md)
- [股票清單與掃描](user-guide/stock-list-and-scanning.md)
- [Daily Report](user-guide/daily-report.md)
- [Artifact 操作](user-guide/artifacts.md)
- [訊號標準](SIGNAL_STANDARD.md)
- [模擬紙上交易 runtime 架構](SIMULATED_PAPER_TRADING_RUNTIME_ARCHITECTURE.md)

## 開發者

- [開發指南](developer-guide/contributing.md)
- [架構概覽](architecture/overview.md)
- [Root compatibility wrappers](compatibility/root-wrappers.md)
- [資料提供者與快取契約](DATA_PROVIDER_CACHE_BOUNDARY_CONTRACT.md)

## 現行設計參考

- [Repository architecture review](REPOSITORY_ARCHITECTURE_REVIEW.md)
- [Public API and wrapper inventory](PUBLIC_API_AND_WRAPPER_INVENTORY.md)

## 歷史與決策紀錄

[歷史與決策紀錄](archive/index.md)導覽完成的 phase、characterization、audit 與 roadmap 文件。 [Daily Report MVP](DAILY_REPORT_MVP.md) 是 Historical MVP design；後續 phases 已擴充 Daily Pipeline，現行使用方式請見 [Daily Report](user-guide/daily-report.md)。
