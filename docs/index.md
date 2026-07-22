# 文件導覽

本頁是 `tw_stock_tool` 文件的主要入口。以目前 runtime source、`pyproject.toml` 與測試為準；歷史 phase 與 audit 文件保留作為決策脈絡，並不取代現行行為。

## 使用者

- [CLI 使用指南](user-guide/cli.md)：安裝、常用研究流程、輸出、快取、artifact、doctor 與 smoke check。
- [訊號標準](SIGNAL_STANDARD.md)：策略輸出與歷史研究訊號語意。
- [模擬紙上交易 runtime 架構](SIMULATED_PAPER_TRADING_RUNTIME_ARCHITECTURE.md)：離線、研究用途的模擬交易邊界。

## 開發者

- [開發指南](developer-guide/contributing.md)：套件結構、安裝、測試與相容性注意事項。
- [架構概覽](architecture/overview.md)：正式實作模組與 repository root 的定位。
- [Root compatibility wrappers](compatibility/root-wrappers.md)：所有 root Python 相容入口與正式目標。
- [資料提供者與快取契約](DATA_PROVIDER_CACHE_BOUNDARY_CONTRACT.md)：資料與快取邊界的現有契約。

## 現行設計參考

- [Repository architecture review](REPOSITORY_ARCHITECTURE_REVIEW.md)
- [Public API and wrapper inventory](PUBLIC_API_AND_WRAPPER_INVENTORY.md)
- [Daily Report MVP](DAILY_REPORT_MVP.md)

## 歷史與決策紀錄

完成的 phase、characterization、audit 與 roadmap 文件沒有在本次整理中搬移，以保留既有連結與 Git history。請由[歷史與決策紀錄](archive/index.md)開始閱讀；其中的敘述若與 runtime source 或測試不同，應以目前實作為準。
