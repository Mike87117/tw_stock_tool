# 開發指南

## 正式實作位置

套件採用 `src` layout；正式 runtime implementation 位於 `src/tw_stock_tool/`。`pyproject.toml` 定義的 console script 為 `twstock = tw_stock_tool.cli.twstock_cli:main`。

各模組的目前分工請見[架構概覽](../architecture/overview.md)。Repository root 的 Python 檔案是相容入口，完整盤點見[root wrapper compatibility](../compatibility/root-wrappers.md)。

## 本機安裝與測試

```bash
pip install -e .
python -m unittest discover -s tests
```

專案要求 Python 3.11 以上。

## 相容性注意事項

- 修改 CLI、schema、輸出、package exports 或 root wrapper 前，先檢查現有 source、tests 與 wrapper inventory。
- root wrapper 的 import 與直接執行行為均是保留的相容表面。
- 相對於 phase 文件，現行 runtime source、`pyproject.toml` 與測試具有較高的判斷優先順序。
- 資料與快取相關修改須遵守[資料提供者與快取契約](../DATA_PROVIDER_CACHE_BOUNDARY_CONTRACT.md)。
