# Root entry status

正式 console entry point 是 `twstock`，正式 Python implementation 位於 `src/tw_stock_tool/`。

Cleanup 4A 已刻意移除舊的 repository-root compatibility wrappers。`python root_script.py` 與 `import root_module` 不再是目前支援的 public contract；新程式與文件應使用 `twstock` 或 `tw_stock_tool.*`。

目前暫時保留、待 Cleanup 4B 重新決定 canonical entry 的六個 legacy entries：

| Legacy root entry | Canonical package target | Status |
| --- | --- | --- |
| `ai_prediction_report.py` | `tw_stock_tool.reports.ai_prediction_report` | retained until Cleanup 4B |
| `ai_walk_forward.py` | `tw_stock_tool.ml.ai_walk_forward` | retained until Cleanup 4B |
| `daily_watchlist.py` | `tw_stock_tool.cli.daily_watchlist` | retained until Cleanup 4B |
| `gui_app.py` | `tw_stock_tool.gui.gui_app` | retained until Cleanup 4B |
| `ml_dataset.py` | `tw_stock_tool.ml.ml_dataset` | retained until Cleanup 4B |
| `verify_batch.py` | `tw_stock_tool.utils.verify_batch` | retained until Cleanup 4B |

已移除 36 個 wrappers 的逐檔 replacement 與 gate 紀錄見 [Root wrapper removal record](../archive/root-wrapper-removal.md)。
