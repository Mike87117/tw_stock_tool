# SIGNAL STANDARD

本文件定義 `tw_stock_tool` 的策略訊號標準。目標是讓研究、回測、Paper Trading、半自動下單與未來可能的自動下單使用同一套訊號語意，避免研究結果與實際執行不一致。

目前專案仍是研究工具，不提供投資建議，不保證獲利，也不包含真實下單功能。

## 1. 適用範圍

目前台股現貨策略先以 long-only 為主。

這代表：

- 只考慮進場買進與出場賣出。
- 不預設放空。
- 不預設期貨、選擇權或槓桿商品。
- 策略只負責產生訊號，不負責下單。

未來若支援放空或期貨，可再擴充更細的訊號語意。

## 2. 標準輸出欄位

所有新策略應統一輸出：

- `entry_signal`
- `exit_signal`

### entry_signal

`entry_signal=True` 代表策略在該 bar 產生進場訊號。

在 long-only 台股現貨語境中，這代表策略提出「可以考慮建立多單」的意圖。

### exit_signal

`exit_signal=True` 代表策略在該 bar 產生出場訊號。

在 long-only 台股現貨語境中，這代表策略提出「可以考慮賣出離場」的意圖。

## 3. 舊版文字 Signal 的定位

目前舊版報表中仍可能出現：

- `Signal=BUY`
- `Signal=SELL`
- `Signal=HOLD`
- `Signal=WATCH`

這些文字 Signal 可以保留作為報告顯示、人工閱讀與 Daily Report 篩選用途。

但未來下單引擎不得直接依賴文字 `Signal` 欄位。

原因：

- `BUY` / `SELL` / `HOLD` / `WATCH` 是報告語意，不是標準交易執行語意。
- `WATCH` 不代表任何下單行為。
- `HOLD` 在不同情境下可能代表空手不動或持倉續抱。
- 真正可被回測、Paper Trading 或下單流程使用的標準欄位應是 bool 型別的 `entry_signal` / `exit_signal`。

## 4. 回測成交標準

回測預設成交方式為 `next_bar_open`。

也就是：

```text
第 t 根 bar 產生 entry_signal / exit_signal
↓
第 t+1 根 bar 的 Open 成交
```

這代表：

- 策略可以使用第 `t` 根 bar 當下或以前已知資料產生訊號。
- 不允許同一根 bar 產生訊號後，又使用同一根 bar 的成交價成交。
- 若最後一根 bar 才產生訊號，因為沒有下一根 bar，該訊號不得成交。

## 5. 禁止使用未來資料

策略不得使用 `shift(-1)` 或任何未來資料產生訊號。

禁止範例：

```python
df["future_return"] = df["Close"].shift(-1) / df["Close"] - 1
df["entry_signal"] = df["future_return"] > 0
```

任何用於產生 `entry_signal` / `exit_signal` 的資料，都必須在該 bar 或更早以前已知。

允許範例：

```python
work_df = df.copy()
work_df["entry_signal"] = work_df["MA5"] > work_df["MA20"]
work_df["exit_signal"] = work_df["MA5"] < work_df["MA20"]
```

## 6. Signal 型別

`entry_signal` 與 `exit_signal` 必須是 bool 欄位。

要求：

- 欄位 dtype 應為 bool。
- 不應使用字串作為標準訊號。
- 不應使用 `1` / `0` 作為最終標準輸出。
- 若中間計算產生缺值，最終輸出前應明確轉成 `False` 或做錯誤處理。

建議：

```python
work_df["entry_signal"] = work_df["entry_signal"].fillna(False).astype(bool)
work_df["exit_signal"] = work_df["exit_signal"].fillna(False).astype(bool)
```

## 7. Signal 長度與 index

`entry_signal` 與 `exit_signal` 的長度必須與 price dataframe 一致。

要求：

- 不可少一列。
- 不可多一列。
- index 應與原始價格 dataframe 對齊。
- 指標前期資料不足時，應讓訊號為 `False`，不要刪除 row 造成錯位。

這能避免回測、Paper Trading 與未來下單時日期錯位。

## 8. 策略不得修改原始 dataframe

策略應使用：

```python
work_df = df.copy()
```

不得直接修改傳入的原始 dataframe。

原因：

- 避免不同策略互相污染資料。
- 避免 Parameter Sweep 重複執行時累積隱性欄位。
- 避免 Walk Forward train / test 資料被前一次執行污染。

## 9. entry 與 exit 同時為 True

同一列同時出現：

```text
entry_signal=True
exit_signal=True
```

通常代表策略規則衝突。

建議：

- 策略層應盡量避免同時產生 entry 與 exit。
- 若無法避免，回測層必須明確定義優先順序。
- long-only 情境下，已持倉時應優先處理 exit；空手時才處理 entry。

## 10. 回測與未來實盤語意一致

回測與未來實盤下單必須使用同一套訊號語意。

也就是：

- `entry_signal=True` 永遠代表進場意圖。
- `exit_signal=True` 永遠代表出場意圖。
- 成交時間由 execution model 決定，預設為 `next_bar_open`。
- Risk Manager 可以拒絕交易，但不應改寫策略訊號本身。
- Broker Interface 只能執行經過風控與 Kill Switch 檢查後的交易意圖。

如果研究階段與實際執行階段使用不同語意，回測、Paper Trading 與真實執行結果將無法比較。

## 11. 未來擴充方向

若未來支援放空、期貨或其他多方向商品，可擴充為：

- `open_long`
- `close_long`
- `open_short`
- `close_short`

但在台股現貨 long-only 階段，先維持 `entry_signal` / `exit_signal`，避免過早增加複雜度。

## 12. 最低測試要求

任何新增策略至少應測試：

- `entry_signal` 欄位存在。
- `exit_signal` 欄位存在。
- 兩個欄位皆為 bool。
- 兩個欄位長度與 price dataframe 一致。
- index 與 price dataframe 一致。
- 策略不修改原始 dataframe。
- 策略沒有使用 `shift(-1)` 或其他未來資料產生訊號。
- 回測成交發生在訊號後的下一根 bar，而不是同一根 bar。

## 13. 結論

`entry_signal` / `exit_signal` 是 `tw_stock_tool` 從研究到未來 Paper Trading 與交易執行層的核心語意。舊版文字 `Signal` 可以作為報告顯示，但不應作為未來下單引擎的直接依據。

本專案目前仍是研究工具，不提供投資建議，不保證獲利。
