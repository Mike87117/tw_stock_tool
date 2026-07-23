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

## 相容性注意事項

- Production code 與 tests 必須從 `tw_stock_tool.*` 匯入，不得依賴 repository-root compatibility modules。
- 修改 CLI、schema、輸出或 package exports 前，先檢查現有 source、tests 與 canonical CLI routes。
- Cleanup 4A 的 root-wrapper removal record 是歷史決策紀錄，不是目前可用的 root invocation 指南。
- 相對於 phase 文件，現行 runtime source、`pyproject.toml` 與測試具有較高的判斷優先順序。
- 資料與快取相關修改須遵守[資料提供者與快取契約](../DATA_PROVIDER_CACHE_BOUNDARY_CONTRACT.md)。
