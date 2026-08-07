# 開發指南

## 正式實作位置

套件採用 `src` layout；正式 runtime implementation 位於 `src/tw_stock_tool/`。`pyproject.toml` 定義的 console script 為 `twstock = tw_stock_tool.cli.twstock_cli:main`。

各模組的目前分工請見[架構概覽](../architecture/overview.md)。Repository root 沒有受支援的 Python entry points；已移除 entry 的紀錄請見[Root entry removal record](../archive/root-wrapper-removal.md)。

## 本機安裝與測試

~~~bash
pip install -e .
python -m unittest discover -s tests
~~~

專案要求 Python 3.11 以上。

### Windows 低資源本機測試

Windows 開發者可使用 `scripts/test_local_safe.ps1` 以 Python 3.12 執行測試。腳本只供手動本機使用，不會被 GitHub Actions 呼叫，也不會改變 CI 的測試命令。

執行單一測試 module、class 或 method：

~~~powershell
.\scripts\test_local_safe.ps1 tests.test_twstock_cli
.\scripts\test_local_safe.ps1 tests.test_twstock_cli.TwStockCliTest
.\scripts\test_local_safe.ps1 tests.test_twstock_cli.TwStockCliTest.test_help
~~~

不帶測試名稱時執行完整 unittest suite：

~~~powershell
.\scripts\test_local_safe.ps1
~~~

腳本會將 `OMP_NUM_THREADS`、`OPENBLAS_NUM_THREADS`、`MKL_NUM_THREADS` 與 `NUMEXPR_NUM_THREADS` 限制為 `1`，並使用 `MPLBACKEND=Agg`。NumPy、SciPy、scikit-learn、OpenBLAS 或 OpenMP 可能在每個測試 subprocess 中各自建立執行緒；本機限制可避免多個測試程序同時搶占 CPU，降低 Windows 開發機卡頓。腳本也會將測試 Python process 設為 Windows `BelowNormal` priority，並原樣傳回 unittest exit code。

這五個環境變數只在安全測試腳本執行期間暫時覆寫。腳本會保存呼叫者目前 PowerShell process 中每個變數原本是否存在及其值，並在成功、測試失敗或啟動錯誤等所有結束路徑恢復原狀；原本不存在的變數會被移除。因此執行安全測試後，同一個 PowerShell session 中後續 Python 工作不會被意外限制為單執行緒，也不會被持續強制使用 `MPLBACKEND=Agg`。

本機安全模式與 CI 的責任不同：本機腳本只降低開發者電腦的資源優先權與數值運算執行緒數，不跳過、分片或平行化測試。Pull Request 的 GitHub Actions 會執行 Python 3.12 完整 unittest 與 Python 3.12 package/CLI smoke；變更合併到 `main` 後，CI 會額外執行 Python 3.11 compatibility suite。完整跨版本驗證與 package smoke 主要由 CI 負責。

## 相容性注意事項

- Production code 與 tests 必須從 `tw_stock_tool.*` 匯入，不得依賴 repository-root compatibility modules。
- 修改 CLI、schema、輸出或 package exports 前，先檢查現有 source、tests 與 canonical CLI routes。
- Cleanup 4A 的 root-wrapper removal record 是歷史決策紀錄，不是目前可用的 root invocation 指南。
- 相對於 phase 文件，現行 runtime source、`pyproject.toml` 與測試具有較高的判斷優先順序。
- 資料與快取相關修改須遵守[資料提供者與快取契約](../DATA_PROVIDER_CACHE_BOUNDARY_CONTRACT.md)。
