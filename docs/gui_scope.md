# GUI Scope 設計草案

## 1. 目標

GUI 第一版目標是把本專案最常用、最適合新手的主流程做成可視化操作介面，而不是一次把所有研究工具都塞進 GUI。

- 降低新手使用門檻。
- 讓使用者不用記 CLI 指令與參數組合。
- 提供股票清單更新、多股票掃描、Daily Report 與單股分析。
- 提供環境與資料來源檢查，讓使用者能先確認本機與外部資料狀態。
- 不把所有研究工具一次塞進 GUI，避免第一版過度複雜。

## 2. GUI 第一版納入功能

第一版 GUI 應優先支援以下工具，這些工具屬於使用者最常用的主流程，也最能降低入門門檻。

| 工具 | GUI 中的用途 |
| --- | --- |
| `doctor.py` | 檢查 Python 版本、必要套件、`cache/`、`output/` 與主要 CLI 檔案是否正常。可作為 GUI 首頁的環境健檢。 |
| `stock_list_updater.py` | 從 TWSE / TPEx 官方資料更新股票清單，讓使用者不用手動維護 `stocks.txt`。 |
| `stock_list_smoke_check.py` | 手動檢查 TWSE / TPEx 官方股票清單來源是否仍可用。 |
| `price_data_smoke_check.py` | 手動檢查 yfinance 與官方 fallback 價格資料是否可用。 |
| `scan_stocks.py` | 多股票技術掃描，支援 `--auto-stock-list`、`--stock-limit` 與常用篩選條件。 |
| `daily_report.py` | 產生每日候選股報告，適合做成一鍵生成 Excel 的 GUI 功能。 |
| `main.py` | 單股深入分析，包含技術指標、訊號、回測結果與圖表輸出。 |
| `cache_manager.py` | 查看快取摘要與清除快取，用於解決資料過期或空間管理問題。 |

## 3. GUI 第二階段考慮納入

以下工具偏研究用途，參數與輸出解讀成本較高。建議等第一版 GUI 主流程穩定後，再考慮納入研究頁面。

- `strategy_compare.py`: 適合比較不同策略的歷史表現，但需要使用者理解回測指標。
- `walk_forward.py`: 用於檢查參數是否過度擬合，適合作為進階研究功能。
- `parameter_sweep.py`: 會測試多組參數，執行時間可能較長，且容易被誤讀為最佳未來策略。
- `ai_prediction_report.py`: 用於單股 baseline AI validation，需要清楚標示不是投資預測。
- `ai_stock_scanner.py`: 會對多檔股票執行 baseline AI validation，計算成本與誤解風險較高。

## 4. 第一版 GUI 暫不納入

以下工具第一版不建議納入 GUI。

- `ml_dataset.py`
- `ai_walk_forward.py`
- `baseline_ml_model.py`
- `benchmark.py`

暫不納入原因：

- 偏實驗或效能測試用途。
- 使用者需要理解較多參數與輸出指標。
- 任務可能耗時，需要更完整的背景執行與取消機制。
- 不適合放在新手 GUI 第一版。

## 5. `twstock_cli.py` 的角色

- `twstock_cli.py` 是 CLI 統一入口，讓進階使用者不需記住多個 `.py` 檔名。
- GUI 不應該透過 subprocess 呼叫 `twstock_cli.py`，因為這會讓錯誤處理、進度回報與取消任務變複雜。
- GUI 應該直接呼叫 `app_services.py` 或未來新增的 service layer。
- `twstock_cli.py` 可以保留給進階使用者與自動化腳本使用。

## 6. GUI 架構建議

建議 GUI 第一版頁面如下：

1. 環境 / 資料來源檢查
2. 股票清單
3. 多股票掃描
4. Daily Report
5. 單股分析
6. 快取管理

## 7. 長時間任務處理

未來 GUI 需要考慮以下任務管理能力：

- 背景執行緒。
- 進度條。
- 取消任務。
- 錯誤列表。
- 輸出檔案開啟按鈕。

## 8. 結論

GUI 第一版不追求包進所有工具。應先完成主流程：環境與資料檢查、股票清單、多股票掃描、Daily Report、單股分析與快取管理。研究工具先保留 CLI，等第一版 GUI 穩定後，再考慮加入 research / AI 頁面。
