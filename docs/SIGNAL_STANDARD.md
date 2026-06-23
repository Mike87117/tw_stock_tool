# SIGNAL STANDARD

本文件定義 `tw_stock_tool` 的策略訊號標準，目標是讓研究、回測、GUI 顯示、Paper Trading 與未來可能的實盤下單使用同一套語意，避免「研究結果看起來有效，但實際執行時語意不同」造成偏差或風險。

## 1. 基本定位

目前 `tw_stock_tool` 以台股現貨研究為主，因此策略設計預設採用 long-only 邏輯：

- 只考慮買進持有與賣出離場。
- 不預設放空。
- 不預設期貨、選擇權或槓桿商品。
- 所有訊號都應能被回測與未來 Paper Trading 以相同方式解讀。

這個標準不代表任何投資建議，也不保證任何策略能獲利。

## 2. 統一訊號欄位

策略應統一輸出下列兩個布林欄位：

- `entry_signal`
- `exit_signal`

### entry_signal

`entry_signal=True` 代表策略在該 bar 產生進場訊號。

在目前 long-only 台股現貨語境中，這代表：

- 空手時可以考慮建立多單部位。
- 已持有部位時，不應重複加碼，除非未來策略明確支援部位管理。

### exit_signal

`exit_signal=True` 代表策略在該 bar 產生出場訊號。

在目前 long-only 台股現貨語境中，這代表：

- 已持有部位時可以考慮賣出離場。
- 空手時不應產生實際交易。

## 3. 回測成交時點

回測預設必須使用 `next_bar_open` 成交。

也就是：

```text
第 t 根 bar 收盤後產生訊號
↓
第 t+1 根 bar 開盤價成交
```

這個規則是為了避免 look-ahead bias。策略可以使用第 `t` 日已知資料產生訊號，但不能假設自己能在同一天已經知道收盤資料後，又用同一天價格成交。

若未來提供不同成交模型，例如 `next_bar_close`、VWAP 或 intraday fill，必須在回測設定中明確標示，且不能改變 `entry_signal` / `exit_signal` 本身的語意。

## 4. 禁止使用未來資料

策略訊號不得使用任何未來資料。

禁止範例：

```python
df["future_return"] = df["Close"].shift(-1) / df["Close"] - 1
df["entry_signal"] = df["future_return"] > 0
```

任何用來產生 `entry_signal` 或 `exit_signal` 的特徵，都只能使用當下或過去已知資料。

允許範例：

```python
work_df = df.copy()
work_df["entry_signal"] = work_df["MA5"] > work_df["MA20"]
work_df["exit_signal"] = work_df["MA5"] < work_df["MA20"]
```

## 5. Signal 欄位型別

`entry_signal` 與 `exit_signal` 必須是 bool 欄位。

要求：

- 欄位值只能表示 `True` 或 `False`。
- 不應混用字串，例如 `"BUY"`、`"SELL"`。
- 不應使用 `1`、`0` 作為最終標準輸出。
- 若中間計算產生 `NaN`，最終輸出前應轉為 `False` 或明確處理。

建議：

```python
work_df["entry_signal"] = work_df["entry_signal"].fillna(False).astype(bool)
work_df["exit_signal"] = work_df["exit_signal"].fillna(False).astype(bool)
```

## 6. Signal 長度

`entry_signal` 與 `exit_signal` 的長度必須與 price dataframe 一致。

要求：

- 不可少一列。
- 不可多一列。
- index 應與原始價格資料對齊。
- 技術指標前期資料不足時，可以讓訊號為 `False`，但不應刪除 rows 造成對齊錯誤。

這可以確保回測、報表與未來 GUI 顯示都能正確對應日期。

## 7. 策略不得修改原始 DataFrame

策略不得直接修改傳入的原始 dataframe。

策略應使用：

```python
work_df = df.copy()
```

原因：

- 避免不同策略互相污染資料。
- 避免測試結果受前一次策略執行影響。
- 避免回測、Parameter Sweep、Walk Forward 在重複執行時產生隱性狀態。

## 8. entry / exit 同時為 True 的處理

在 long-only 現貨策略中，同一列同時出現：

```text
entry_signal=True
exit_signal=True
```

通常代表策略規則互相衝突。

建議處理方式：

- 策略層應盡量避免同一天同時產生 entry 與 exit。
- 若無法避免，回測層必須有明確優先順序。
- 建議 long-only 預設以風險控制優先，也就是已持倉時優先處理 exit，空手時才處理 entry。

實際優先順序必須在回測文件與測試中保持一致。

## 9. 回測與未來實盤下單的語意一致性

回測、Paper Trading、半自動下單與未來可能的自動下單，必須使用同一套訊號語意：

- `entry_signal=True`：產生進場意圖。
- `exit_signal=True`：產生出場意圖。
- 實際成交時點由 execution model 決定，例如 `next_bar_open`。
- 風控層可以拒絕交易，但不應改寫策略訊號的原始含義。

這點非常重要。若研究階段與實際執行階段使用不同語意，就會造成：

- 回測結果與實際交易結果不可比較。
- Paper Trading 驗證失去意義。
- Risk Manager 難以判斷策略真正意圖。
- 未來 Broker Interface 可能錯誤下單。

因此，策略訊號標準必須在所有階段保持一致。

## 10. 未來擴充方向

若未來支援放空、期貨或其他多方向商品，可以擴充為更明確的四種訊號：

- `open_long`
- `close_long`
- `open_short`
- `close_short`

可能語意：

- `open_long=True`：建立多單。
- `close_long=True`：平掉多單。
- `open_short=True`：建立空單。
- `close_short=True`：平掉空單。

但在台股現貨 long-only 階段，先維持 `entry_signal` / `exit_signal`，避免過早增加複雜度。

## 11. 最低測試要求

任何新增策略至少應測試：

- `entry_signal` 欄位存在。
- `exit_signal` 欄位存在。
- 兩個欄位型別為 bool。
- 兩個欄位長度與 price dataframe 一致。
- 策略不修改原始 dataframe。
- 策略沒有使用 `shift(-1)` 或其他未來資料產生訊號。
- 回測成交發生在訊號後的下一根 bar，而不是同一根 bar。

## 12. 結論

`entry_signal` / `exit_signal` 是 `tw_stock_tool` 從研究到未來執行層的核心語意。短期內，本專案仍是研究與技術分析工具；長期若要走向 Paper Trading、半自動下單或自動下單，必須先確保訊號語意、回測成交模型與風險控管規則完全一致。

本專案不提供投資建議，不保證獲利。任何交易決策都應由使用者自行判斷並承擔風險。
