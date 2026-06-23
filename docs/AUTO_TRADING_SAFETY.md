# AUTO TRADING SAFETY

本文件定義 `tw_stock_tool` 若未來走向 Paper Trading、半自動下單或自動下單時，必須遵守的安全原則。

目前專案仍是研究工具。現階段不支援真實下單、不串接券商 API、不提供自動交易，也不提供投資建議或獲利保證。

## 1. 安全總原則

- 自動下單預設關閉。
- 第一階段只允許 Paper Trading。
- 真實下單必須由使用者手動開啟。
- 任何真實下單前必須完成 Kill Switch。
- 任何真實下單前必須完成 Risk Manager。
- 任何真實下單前必須完成 Trade Log。
- 資料異常、帳戶同步失敗、持倉同步失敗、風控失敗時必須禁止下單。

交易自動化的優先順序必須是：

```text
安全停止 > 風險控管 > 資料正確性 > 策略訊號 > 下單效率
```

## 2. 階段限制

### 第一階段：Paper Trading only

第一階段只允許 Paper Trading。

允許：

- 使用標準訊號產生模擬交易。
- 記錄模擬委託與模擬成交。
- 追蹤模擬持倉、現金、損益。
- 測試 Risk Manager 與 Kill Switch 的行為。

禁止：

- 送出真實委託。
- 串接真實券商下單 API。
- 自動修改真實帳戶持倉。

### 第二階段：半自動下單

半自動下單必須由使用者逐筆確認。

必要條件：

- Paper Trading 已穩定運作。
- Risk Manager 已可阻擋高風險委託。
- Kill Switch 已完成。
- Broker Interface 已完成最小安全檢查。
- Trade Log 可完整記錄每筆委託。

禁止：

- 未經使用者確認直接送出委託。
- 在風控失敗時允許覆蓋下單。
- 在資料異常時繼續下單。

### 第三階段：自動下單

自動下單是長期目標，不是目前功能。

必要條件：

- Backtest 標準化完成。
- Parameter Sweep 與 Walk Forward 已完成策略驗證。
- Paper Trading 已長時間穩定。
- Risk Manager 已完成。
- Kill Switch 已完成。
- Trade Log 已完成。
- Broker Interface 已完成。
- 帳戶同步與持倉同步可靠。
- 異常處理與人工介入流程完成。

自動下單必須預設關閉，且必須由使用者明確手動開啟。

## 3. 真實下單啟用條件

真實下單功能若未來存在，必須同時滿足：

- 使用者明確開啟真實下單模式。
- 使用者已確認交易風險。
- Broker Interface 可正常連線。
- 帳戶同步成功。
- 持倉同步成功。
- 資料來源檢查通過。
- Risk Manager 檢查通過。
- Kill Switch 未啟動。
- Trade Log 可寫入。

任一條件不成立，必須禁止下單。

## 4. 必須禁止下單的情境

以下任何情境發生時，系統必須禁止下單：

- 價格資料缺失。
- 價格資料時間異常。
- 價格欄位出現不合理值，例如負價格或零成交價。
- 股票代號解析失敗。
- yfinance / 官方 fallback 全部失敗。
- 帳戶同步失敗。
- 持倉同步失敗。
- 委託狀態同步失敗。
- Risk Manager 檢查失敗。
- Kill Switch 已啟動。
- Trade Log 無法寫入。
- Broker API 回傳未知錯誤。
- 使用者尚未手動開啟真實下單。

安全預設必須是「不下單」。

## 5. Kill Switch

Kill Switch 是所有真實交易功能的必要前置條件。

Kill Switch 必須能：

- 立即停止新委託。
- 阻止半自動下單。
- 阻止自動下單。
- 在資料異常時自動啟動。
- 在帳戶同步失敗時自動啟動。
- 在持倉同步失敗時自動啟動。
- 在風控失敗時自動啟動。
- 記錄啟動原因。
- 允許使用者人工檢查後解除。

Kill Switch 的狀態必須容易查詢，且不能被策略層繞過。

## 6. Risk Manager

Risk Manager 必須在 Broker Interface 前執行。

至少應檢查：

- 單筆交易最大金額。
- 單筆交易最大風險。
- 單一股票最大持倉。
- 總持倉曝險。
- 單日最大虧損。
- 連續虧損次數。
- 最大委託次數。
- 是否允許買進。
- 是否允許賣出。

Risk Manager 應回傳明確結果：

- 通過。
- 拒絕。
- 拒絕原因。

若 Risk Manager 發生例外或無法完成檢查，必須視為拒絕下單。

## 7. Trade Log

Trade Log 是所有交易流程的稽核基礎。

Paper Trading、半自動下單與自動下單都必須記錄：

- 策略名稱。
- 策略參數。
- 訊號時間。
- 訊號欄位。
- 預期成交模型。
- 股票代號。
- 方向。
- 價格。
- 股數。
- 手續費、稅、滑價。
- Risk Manager 檢查結果。
- Kill Switch 狀態。
- 委託狀態。
- Broker 回應。
- 錯誤訊息。

若 Trade Log 無法寫入，真實下單必須停止。

## 8. Broker Interface 安全邊界

Broker Interface 只應負責和券商 API 溝通，不應負責策略判斷。

Broker Interface 不得：

- 直接讀取報告文字 Signal 後下單。
- 繞過 Risk Manager。
- 繞過 Kill Switch。
- 在 Trade Log 失敗時繼續下單。

Broker Interface 只能執行已通過所有安全檢查的交易意圖。

## 9. 文字 Signal 不得作為下單依據

舊版 `Signal=BUY/SELL/HOLD/WATCH` 只應用於報告顯示與人工閱讀。

未來下單流程必須使用標準化的 bool 訊號：

- `entry_signal`
- `exit_signal`

這能避免 `WATCH`、`HOLD` 等報告語意被錯誤解讀成交易指令。

## 10. 結論

`tw_stock_tool` 目前仍是研究工具。長期可以逐步走向 Paper Trading、Broker Interface、半自動下單與自動下單，但任何真實下單都必須預設關閉，且必須經過 Backtest、Parameter Sweep、Walk Forward、Paper Trading、Risk Manager、Kill Switch 與 Trade Log 的完整驗證。

本專案不提供投資建議，不保證獲利。任何交易決策與風險都由使用者自行承擔。
