# 股票清單與掃描

掃描與 Daily Report 可從 --stocks、--file 或 --auto-stock-list 建立股票 universe。--auto-stock-list 會更新並使用官方股票清單；可用 --stock-market all|twse|tpex、--stock-list-output 與 --allow-partial-stock-list 控制來源與部分結果行為。

## 建議先限制範圍

第一次使用 auto stock list 時，請搭配 --stock-limit，避免全市場執行時間過長或觸發資料來源 rate limit。

~~~bash
twstock scan --auto-stock-list --stock-limit 50
twstock scan --auto-stock-list --stock-sample 50 --random-state 42
~~~

--stock-limit 取收集清單的前 N 檔；--stock-sample 隨機取 N 檔，並可用 --random-state 重現抽樣。兩者互斥，且數值必須大於零。

## 股票清單操作

~~~bash
twstock stock-list update --market all --output stocks.txt
twstock stock-list clean --file stocks.txt --output --write-clean-file
twstock stock-list smoke-check
twstock price-smoke-check
~~~

兩種 smoke check 都是 live API 檢查，不是一般 unittest 或 CI 的替代品；外部服務短暫故障可能造成失敗。
