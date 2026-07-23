# Root entry status

正式 console entry point 是 `twstock`，正式 Python implementation 位於 `src/tw_stock_tool/`。

Cleanup 4B.1 已將 AI Report、ML Dataset 與 GUI canonicalize 到正式 commands，並將 AI walk-forward 與 baseline model 收斂為 package-only research APIs。

目前暫時保留、待 Cleanup 4B.2 處理的兩個 legacy entries：

| Legacy root entry | Canonical package target | Status |
| --- | --- | --- |
| `daily_watchlist.py` | `tw_stock_tool.cli.daily_watchlist` | retained until Cleanup 4B.2 |
| `verify_batch.py` | `tw_stock_tool.utils.verify_batch` | retained until Cleanup 4B.2 |

已移除 wrappers 的逐檔 replacement 與 gate 紀錄見 [Root wrapper removal record](../archive/root-wrapper-removal.md)。
