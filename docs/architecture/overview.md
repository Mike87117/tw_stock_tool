# 架構概覽

正式 implementation 位於 `src/tw_stock_tool/`；`pyproject.toml` 提供 `twstock` console script，統一 CLI router 位於 `tw_stock_tool.cli.twstock_cli`。

```text
src/tw_stock_tool/
├── analysis/                      指標、訊號與單股分析
├── backtesting/                   回測、策略比較、參數搜尋與 Walk Forward
├── cli/                           CLI adapters 與 artifact 操作
├── data/                          股票清單、資料下載與快取
├── gui/                           本機 GUI 原型與服務
├── kill_switch/                   停止條件模型
├── ml/                            ML 研究工具
├── paper_trading/                 模擬紙上交易模型、序列化與輸出
├── reports/                       報告與圖表輸出
├── risk/                          研究用風險模型
├── simulated_paper_trading_guard/ 模擬交易防護邊界
├── ui/                            唯讀 UI 邊界
└── utils/                         設定、診斷與共用工具
```

Repository root 沒有受支援的 Python entry points；正式 CLI 是 `twstock`，正式 Python implementation 位於 `src/tw_stock_tool/`。Cleanup 4A–4B 的 entry removal 紀錄請見[archive record](../archive/root-wrapper-removal.md)。

本頁只描述目前結構。phase、audit 與已完成工作則保留在[歷史與決策紀錄](../archive/index.md)。
