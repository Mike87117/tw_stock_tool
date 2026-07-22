# 資料來源與快取

價格資料由 tw_stock_tool.data.data_loader 取得。正常流程依序嘗試：

~~~text
Fresh Cache → Yahoo Finance → Official TWSE / TPEx fallback → Stale Cache fallback → DataLoaderError
~~~

未指定 .TW 或 .TWO 時，會依序嘗試 .TW、.TWO。官方 fallback 僅在 auto_adjust 關閉時使用，且只支援日線（1d）。

## 官方 fallback 的限制

TWSE／TPEx 是 Yahoo Finance 失敗時的官方來源 fallback。其資料用於維持研究流程可用，但不提供 Yahoo Finance auto_adjust=True 的完整調整價格語意；非日線或需要調整價格時，fallback 不適用。

## Stale cache

預設可接受最長 14 天的 stale cache。可用 TW_STOCK_TOOL_MAX_STALE_CACHE_DAYS 調整；無效、零或負值會回復為 14。當所有即時來源失敗且 stale cache 尚在期限內，程式會在 stderr 顯示 warning。Stale cache 不代表最新市場資料。

--force-refresh 會略過 fresh cache，也不會使用 stale-cache fallback；若即時來源全數失敗，命令會回報資料錯誤。

## 路徑

預設輸出與快取分別是目前工作目錄下的 output/、cache/。可設定 TW_STOCK_TOOL_OUTPUT_DIR 與 TW_STOCK_TOOL_CACHE_DIR。

## 排錯

~~~bash
twstock doctor
twstock doctor --live
twstock stock-list smoke-check
twstock price-smoke-check
~~~

--live 與 smoke checks 會接觸外部服務；其失敗可能是服務暫時不可用或 rate limit，而不一定是程式 regression。
