# DEVELOPMENT ROADMAP

本文件描述 `tw_stock_tool` 的長期發展方向。它用來界定研究工具、驗證工具、Paper Trading、Broker Interface、半自動下單與自動下單之間的階段差異。

目前專案仍是台股資料分析、技術指標、策略研究與回測工具；自動下單是長期目標，不是目前功能。本專案不提供投資建議，不保證獲利，也不應被視為任何買賣建議。

## 1. 目前定位

`tw_stock_tool` 目前主要用途：

- 取得台股資料。
- 計算技術指標。
- 掃描多檔股票。
- 產生 Daily Report。
- 進行策略比較、Parameter Sweep 與 Walk Forward 驗證。
- 建立研究用 AI / ML dataset 與 baseline validation。
- 提供本機 GUI 原型與 CLI 工具，降低使用門檻。

目前不包含：

- 真實下單。
- 券商 API 串接。
- 自動交易。
- 投資建議。
- 獲利保證。

## 2. 長期階段總覽

建議發展順序如下：

```text
台股資料取得
↓
技術指標分析
↓
多股票掃描 / Daily Report
↓
Backtest 標準化
↓
Parameter Sweep
↓
Walk Forward 驗證
↓
Paper Trading
↓
Risk Manager + Kill Switch
↓
Broker Interface
↓
半自動下單
↓
自動下單
```

任何下單相關功能都必須在前置階段完成後才可考慮。尤其在真實下單前，必須完成：

- Backtest 標準化。
- Parameter Sweep。
- Walk Forward。
- Paper Trading。
- Risk Manager。
- Kill Switch。
- Trade Log。

## 2.5 目前開發進度

- Phase 1：完成 (Backtest metrics / result standardization)
- Phase 1.5：完成 (Signal standard adapter)
- Phase 2：完成 (Daily Watchlist)
- Phase 2 cleanup：完成 (Daily Watchlist CLI / export cleanup)
- Phase 3：完成 (Backtest Report exporter)
- Phase 3.1：完成 (Backtest Report CLI)
- Phase 3.2：完成 (Backtest Report CLI 測試補強)
- Repo audit cleanup P1：完成 (避免 --auto-stock-list 污染 tracked stocks.txt)
- Repo audit cleanup P2：完成 (Backtest trade schema 顯示 PnL_pct / PnL % 相容)
- Phase 4.1：完成 (Parameter Sweep Report exporter)
- Phase 4.2：完成 (Parameter Sweep Report CLI)
- Phase 4.3：完成 (Parameter Sweep Report CLI documentation update)
- Phase 4.4B：完成 (Walk Forward Report exporter)
- Phase 4.5：完成 (Walk Forward Report CLI)
- Phase 4.6：完成 (Walk Forward Report CLI documentation update)
- Phase 4.7：完成 (Report CLI consistency audit / test hardening)
- Phase 4.8A：完成 (Parameter Sweep custom range engine support)
- Phase 4.8B：完成 (Expose custom parameter ranges in Parameter Sweep Report CLI)
- Phase 4.8C：完成 (Parameter Sweep custom range CLI documentation update)
- Phase 4.9：完成 (Report CLI consistency polish batch)
- Phase 4.10：完成 (Walk Forward custom range support)
- Phase 4.11：完成 (Report documentation polish / smoke audit)
- Phase 4.12：完成 (Release readiness audit / cleanup backlog)
- Phase 5.1：完成 (Daily Report MVP design / scope lock)
- Phase 5.2：完成 (Daily Report data model / builder)
- Phase 5.3：完成 (Daily Report Markdown exporter)
- Phase 5.4：完成 (Daily Report CLI)
- Phase 5.5：完成 (Daily Report docs and smoke tests)
- Phase 5.6：完成 (Daily Report MVP final audit / cleanup)
- Phase 6.1：完成 (Data reliability audit / failure-mode map)
- Phase 6.2：完成 (Price data fallback and cache behavior cleanup)
- Phase 6.3：完成 (Stock list reliability and invalid-symbol handling)
- Phase 6.4：完成 (Daily Report partial-failure behavior and user-facing warnings)
- Phase 6.5：完成 (Data reliability tests and documentation)
- Phase 6.6：完成 (Final data reliability cleanup / final audit)
- Phase 7.1：完成 (README / command documentation release-readiness polish)
- Phase 7.2：完成 (Unified CLI help / usage test hardening)
- Phase 7.3：完成 (Unified CLI entrypoint / wrapper smoke tests)
- Phase 7.4：完成 (Unified CLI cache subcommand)
- Phase 8：完成 (Release baseline / v0.1.0 / GitHub Release readiness)
- Phase 9：完成 (Report workflow cleanup / generated output ignore rules / report workflow error handling tests)
- Phase 10：完成 (Daily Report CLI polish / twstock daily --output-excel)
- Phase 11.1：完成 (Documentation consolidation audit)
- Phase 11.2：完成 (Docs-only consolidation patch)
- Phase 12.1：完成 (CLI Consistency Audit)
  - Read-only audit of CLI and report flag consistency.
  - Confirmed existing runtime and docs were generally aligned.
  - Identified Strategy Compare as the narrow inconsistency (used legacy `--output` for Excel output, unlike newer `--output-excel` CLIs).
  - Recommended narrow compatibility patch: add `--output-excel`, keep `--output` as backward-compatible alias, do not change strategy logic or Excel export behavior.
- Phase 12.2：完成 (Strategy Compare `--output-excel` Compatibility Patch)
  - Runtime patch completed and merged.
  - Added `--output-excel` to Strategy Compare.
  - Preserved legacy `--output` as a backward-compatible alias.
  - Added clear conflict handling when both flags are supplied.
  - Preserved default and custom output path behavior.
  - Did not change: strategy comparison logic, backtest logic, Excel exporter behavior, or Excel sheet name `Strategy_Compare`.
  - Tests passed: `tests.test_strategy_compare`, `tests.test_twstock_cli`, and full test suite (491 tests).
- Phase 12.3：完成 (Strategy Compare CLI Consistency Closeout Audit)
  - Closeout audit passed.
  - Confirmed main HEAD: `3cf607701a9fcc6949a7914343cd60d55b3a975a`.
  - Confirmed scope was limited to: `src/tw_stock_tool/backtesting/strategy_compare.py`, `tests/test_strategy_compare.py`, `README.md`.
  - Confirmed: working tree clean, `git diff --check` clean, `--output-excel` exists, `--output` remains, both flags together fail clearly, `export_strategy_compare()` unchanged, Excel sheet name remains `Strategy_Compare`, strategy/backtest logic unchanged, README matches runtime, `twstock_cli.py` and root wrappers untouched.
  - Targeted tests passed (8 Strategy Compare tests, 33 unified CLI tests).
- Phase 13.1：完成 (Backtest Fill Model Consistency Audit)
- Phase 13.2：完成 (Backtest Fill Model Consistency Patch)
  - Aligned backtest fill model with `next_bar_open` for standard signals.
- Phase 13.2.1：完成 (Backtest Next-Bar-Open Full Suite Compatibility Fix)
  - Updated mock test fixtures and preserved `Open` column across strategies.
- Phase 13.3：完成 (Backtest Report CLI Parameter Exposure Audit)
- Phase 13.4：完成 (Backtest Report CLI Parameter Exposure Patch)
  - Exposed RSI, Score, and engine parameters in `backtest_report.py`.
- Phase 13.5：完成 (Backtest Report Unified CLI Exposure Audit)
- Phase 13.6：完成 (Backtest Report Unified CLI Exposure Patch)
  - Added `twstock backtest-report` through unified CLI.
- Phase 14.1：完成 (Parameter Sweep & Walk Forward Parameter Consistency Audit)
- Phase 14.2：完成 (Parameter Sweep CLI & Metadata Patch)
- Phase 14.3：完成 (Walk Forward Parameter Consistency Audit)
- Phase 14.4：完成 (Walk Forward Engine Params & Metadata Patch)
- Phase 14.5：完成 (Walk Forward Unified CLI Exposure Audit)
- Phase 14.6：完成 (Walk Forward Unified CLI Exposure Patch)
- Phase 14.7：完成 (Parameter Sweep Unified CLI Dispatch Alignment Audit)
- Phase 14.8：完成 (Parameter Sweep Unified CLI Dispatch Alignment Patch)
  - Aligned `twstock parameter-sweep` dispatch with the report-facing `cli.parameter_sweep_report.main`.
- Phase 14.9：完成 (Report CLI Alignment Closeout Audit)
- Phase 15.1：完成 (Release Readiness / Next Scope Audit)
- Phase 15.2：完成 (Root Wrapper Alignment Patch)
  - Updated legacy root wrappers `parameter_sweep.py` and `walk_forward.py` to point to the modern CLI layer.
- Phase 15.3：完成 (Root Wrapper Alignment Closeout Audit)
- Phase 15.4：完成 (Root Entrypoint Redundancy / Deprecation Audit)
- Phase 15.5：完成 (Root Entrypoint Policy Documentation Patch)
  - Documented Root Entrypoint Policy: preserving both legacy and modern Report root wrappers as stable entrypoints for backwards compatibility, while retaining pure report CLI dispatch for the unified CLI.
- Phase 15.6：完成 (Final Root Entrypoint Closeout Audit)
- Phase 16.1：完成 (Release Candidate / User Workflow Audit)
- Phase 16.2：完成 (README CLI UX Standardization Patch)
  - Standardized README to consistently recommend the unified `twstock` CLI for user workflows, reserving root wrapper usage for backward compatibility.
- Phase 16.3：完成 (Runtime Output/Cache Path Policy Audit)
- Phase 16.4：完成 (Runtime Output/Cache Path Policy Patch)
  - Changed default `OUTPUT_DIR` and `CACHE_DIR` to use `Path.cwd()` to prevent writing to site-packages after installation.
  - Added support for `TW_STOCK_TOOL_OUTPUT_DIR` and `TW_STOCK_TOOL_CACHE_DIR` environment variables to globally override paths.
- Phase 16.5：完成 (Report Exporter PermissionError Consistency Audit)
- Phase 16.6：完成 (Report Exporter PermissionError Consistency Patch)
  - Added localized `try/except PermissionError` blocks to all missing exporters (`backtest_report`, `parameter_sweep_report`, `walk_forward_report`, `daily_watchlist`, `verify_batch`) to consistently raise `ValueError` with a user-friendly message when Excel files are locked.
- Phase 17–27：完成 (Architecture refactoring, test hardening, AI/ML extensions, codebase maintenance)
- Phase 28：完成 (Simulated Paper Trading export / file output)
- Phase 29.x：完成 (Simulated Paper Trading JSON serialization, file I/O, artifact export CLI, and README documentation)
- Phase 30.x：完成 (Backtest artifact converter, public converter API, and metadata propagation)
- Phase 31：完成 (BacktestResult artifact serialization boundary)
- Phase 32.x：完成 (BacktestResult artifact CLI planning, validate/inspect, and convert-to-simulated-paper-trading)
- Phase 33.x：完成 (Structured `run_backtest_result(...)`, artifact roundtrip / compatibility tests, and `backtest-result-export`)
- Phase 34.x：完成 (BacktestResult export CLI UX / roundtrip smoke tests / read-back validation)
- Phase 35.1：完成 (BacktestResult artifact workflow documentation)
- Phase 35.3：完成 (`backtest-artifact convert-to-simulated-paper-trading` read-back validation)

## 3. 台股資料取得

目標是穩定取得台股價格資料與股票清單，降低單一資料源失效造成的影響。

目前已具備或正在建立的方向：

- Yahoo Finance 台股資料。
- `.TW` / `.TWO` fallback。
- TWSE / TPEx 官方資料 fallback。
- cache 機制，降低重複下載與 rate limit 風險。
- stock list updater，自動產生股票清單。
- smoke check，手動確認股票清單來源與價格資料來源是否仍可用。

後續重點：

- 更清楚標記資料來源。
- 強化資料品質檢查。
- 將資料異常視為阻止交易的高風險事件。

## 4. 技術指標分析

目標是提供可重現、可測試、可解釋的技術分析基礎。

目前包含：

- MA。
- RSI。
- MACD。
- KD。
- Bollinger Band。
- ATR。
- OBV。
- 技術分數與報告用 Signal。

後續重點：

- 持續確認指標計算是否符合預期。
- 避免 look-ahead bias。
- 將策略訊號逐步標準化為 `entry_signal` / `exit_signal`。

## 5. 多股票掃描

目標是從股票清單中快速找出值得進一步研究的標的。

目前方向：

- 支援股票清單檔案。
- 支援手動輸入多檔股票。
- 支援 auto stock list。
- 支援 `--stock-limit` 與 `--stock-sample`，避免第一次使用就掃全市場。
- 支援錯誤保留與報表輸出。

多股票掃描只應作為研究入口，不應直接觸發下單。

## 6. Backtest 標準化

回測是進入任何交易自動化之前的基本門檻。

標準化方向：

- 統一策略訊號語意為 `entry_signal` / `exit_signal`。
- 預設成交模型為 `next_bar_open`（實作與測試已對齊，這是純研究用的回測假設，不代表實際交易執行的保證）。
- 不允許同一根 bar 產生訊號又在同一根 bar 成交。
- 記錄完整 Trade Log。
- 保留交易成本、稅、滑價等設定。
- 計算 total return、max drawdown、win rate、trade count、final equity 等核心指標。

Backtest 的目的不是證明未來會獲利，而是排除明顯錯誤、look-ahead bias 與不可執行策略。

## 7. Parameter Sweep

Parameter Sweep 用於系統化測試不同策略參數。

定位：

- 找出歷史資料中表現較佳的參數組合。
- 協助理解策略對參數的敏感度。
- 不可直接視為未來最佳參數。

風險：

- 容易過度擬合。
- 若沒有 Walk Forward 驗證，不應作為下單依據。

## 8. Walk Forward 驗證

Walk Forward 用於降低過度擬合風險。

基本流程：

1. 將歷史資料切成 train / test 視窗。
2. 在 train 區間挑選參數。
3. 用同一組參數在 test 區間驗證。
4. 彙整各視窗表現。

進入 Paper Trading 前，策略至少應通過合理的 Walk Forward 檢查。

## 9. Daily Report

Daily Report 用於每天快速產生候選股票清單。

定位：

- 提供研究候選名單。
- 協助使用者追蹤 Signal、Score、Volume Ratio 與文字分析。
- 不應直接觸發下單。

Daily Report 的結果必須被視為研究提示，而不是交易指令。

## 10. Paper Trading

Paper Trading 是自動下單前的第一個交易流程階段，但它不使用真實資金。

必要能力：

- 根據標準訊號產生模擬委託。
- 模擬持倉、現金、損益與風險暴露。
- 記錄每一筆模擬交易。
- 比對回測結果與每日模擬執行結果。
- 在資料異常或風控失敗時拒絕模擬交易。

第一階段只允許 Paper Trading，不允許真實下單。

## 11. Risk Manager

Risk Manager 必須獨立於策略與 Broker Interface。

必要能力：

- 單筆交易最大風險限制。
- 單日最大虧損限制。
- 最大持倉數限制。
- 單一股票最大部位限制。
- 總曝險限制。
- 連續虧損降風險機制。
- 風控失敗時禁止下單。

策略只能提出交易意圖，Risk Manager 才能決定該意圖是否可執行。

## 12. Kill Switch

Kill Switch 是任何真實下單能力的必要前置條件。

必要能力：

- 可立即停止所有新委託。
- 可阻止半自動與自動下單。
- 可在資料異常、帳戶同步失敗、持倉同步失敗、風控失敗時自動啟動。
- 狀態必須可記錄、可查詢、可人工解除。

沒有 Kill Switch，不應進入真實下單階段。

## 13. Trade Log

Trade Log 是研究、Paper Trading、半自動下單與自動下單共用的稽核紀錄。

至少應記錄：

- 訊號時間。
- 預計成交模型。
- 實際或模擬成交時間。
- 股票代號。
- 方向。
- 價格。
- 股數。
- 手續費、稅、滑價。
- 策略名稱與參數。
- 風控檢查結果。
- 委託狀態。
- 錯誤訊息。

沒有完整 Trade Log，就無法追蹤研究結果與執行結果是否一致。

## 14. Broker Interface

Broker Interface 是未來可能串接券商 API 的抽象層。

長期可能支援：

- 查詢帳戶餘額。
- 查詢持倉。
- 建立委託。
- 取消委託。
- 查詢委託狀態。
- 記錄券商 API 回應。

限制：

- Broker Interface 不等於啟用真實下單。
- Broker Interface 必須受 Risk Manager 與 Kill Switch 控制。
- Broker Interface 不應繞過 Trade Log。

## 15. 半自動下單

半自動下單代表系統產生建議，但每一筆真實委託都必須由使用者手動確認。

必要條件：

- Backtest 標準化完成。
- Parameter Sweep 與 Walk Forward 已用於策略驗證。
- Paper Trading 長時間穩定。
- Risk Manager 完成。
- Kill Switch 完成。
- Trade Log 完成。
- Broker Interface 完成。

半自動下單仍不是投資建議，使用者必須自行承擔交易風險。

## 16. 自動下單

自動下單是長期目標，不是目前功能。

在自動下單前，必須完成並驗證：

- Backtest 標準化。
- Parameter Sweep。
- Walk Forward。
- Paper Trading。
- Risk Manager。
- Kill Switch。
- Trade Log。
- Broker Interface。
- 帳戶同步。
- 持倉同步。
- 資料異常處理。
- 人工介入流程。

自動下單必須預設關閉，且必須由使用者明確手動開啟。

## 17. 結論

`tw_stock_tool` 的短中期重點是成為穩定、可驗證、可解釋的台股研究工具。長期可以逐步走向 Paper Trading、Broker Interface、半自動下單與自動下單，但每一階段都必須先完成訊號標準、回測標準、風控、Kill Switch 與 Trade Log。

本專案不提供投資建議，不保證獲利。任何交易決策都應由使用者自行判斷並承擔風險。
