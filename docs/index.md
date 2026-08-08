# 文件導覽

本頁是 tw_stock_tool 的主要文件入口。現行 runtime source、`pyproject.toml` 與測試優先於歷史 phase 或 MVP 文件。

## 目前開發狀態

- Current package version：`0.4.0`。
- Latest completed product phase：Phase 55.3 — Artifact Hub 與 Research Workspace。
- Latest merged runtime phase：Phase 55.3D，已完成 offline read-only `twstock run list`／`twstock run inspect`。
- Phase 55.3E documentation and migration audit：本次文件更新完成後 closeout。
- Current approved planning topic：Phase 56 — Strategy Qualification and Recommendation Evidence。
- Next production-code phase after planning：Phase 56.1 Qualification Models and Pure Policy Evaluator。

目前規劃與 closeout：

- [Phase 55.3 Closeout：Artifact Hub 與 Research Workspace](archive/phase-55-3-closeout.md)
- [Phase 56 Strategy Qualification Planning](architecture/phase-56-strategy-qualification-plan.md)
- [Phase 55.3 Artifact Hub 與 Research Workspace Planning](architecture/phase-55-3-artifact-hub-workspace-plan.md)
- [Phase 55.2 Closeout：Research Run 與 Run Manifest](archive/phase-55-2-closeout.md)
- [產品架構與後續開發計畫](architecture/product-architecture-and-roadmap.md)

Phase 55.3 planning 與較早 roadmap 中的歷史「下一步」敘述若與最新 closeout 或 Phase 56 planning 不一致，以現行 runtime、tests、Phase 55.3 closeout 與 Phase 56 planning 為準。

## 使用者

- [CLI 使用指南](user-guide/cli.md)：安裝與常用命令總覽。
- [資料來源與快取](user-guide/data-and-cache.md)
- [股票清單與掃描](user-guide/stock-list-and-scanning.md)
- [Daily Report](user-guide/daily-report.md)
- [Artifact 操作](user-guide/artifacts.md)
- [訊號標準](SIGNAL_STANDARD.md)
- [模擬紙上交易 runtime 架構](SIMULATED_PAPER_TRADING_RUNTIME_ARCHITECTURE.md)

## 開發者

- [開發指南](developer-guide/contributing.md)
- [架構概覽](architecture/overview.md)
- [產品架構與後續開發計畫](architecture/product-architecture-and-roadmap.md)
- [Phase 56 Strategy Qualification Planning](architecture/phase-56-strategy-qualification-plan.md)
- [Phase 55.3 Artifact Hub 與 Research Workspace Planning](architecture/phase-55-3-artifact-hub-workspace-plan.md)
- [Market Data Provider 拆分規劃](architecture/market-data-provider-decomposition-plan.md)
- [Root entry removal record](archive/root-wrapper-removal.md)
- [資料提供者與快取契約](DATA_PROVIDER_CACHE_BOUNDARY_CONTRACT.md)
- [Issue #84 Validation baseline：doctor／CLI help／subprocess／installed-package 契約](ISSUE_84_VALIDATION_BASELINE.md)

## Authoritative source hierarchy

發生文件或歷史紀錄衝突時，依下列順序判定：

1. 現行 production runtime source 與 `pyproject.toml`。
2. 現行 tests 與 CI／package smoke evidence。
3. 最新 merged Phase closeout 與 approved active Phase planning 文件。
4. 架構 roadmap 與 user／developer guides。
5. 歷史 Phase、characterization、audit 與 MVP 文件。

## 歷史與決策紀錄

[歷史與決策紀錄](archive/index.md) 導覽完成的 phase、characterization、audit 與 roadmap 文件。以下盤點只供歷史參考，不是目前 root invocation 或 import 指南：

- [Phase 55.3 Closeout](archive/phase-55-3-closeout.md)
- [Phase 55.2 Closeout](archive/phase-55-2-closeout.md)
- [Development Roadmap](DEVELOPMENT_ROADMAP.md)
- [Public API and wrapper inventory](PUBLIC_API_AND_WRAPPER_INVENTORY.md)
- [CLI runtime contract inventory](CLI_RUNTIME_CONTRACT_INVENTORY.json)
- [Cleanup 4A root-wrapper removal record](archive/root-wrapper-removal.md)

[Daily Report MVP](DAILY_REPORT_MVP.md) 是 Historical MVP design；後續 phases 已擴充 Daily Pipeline，現行使用方式請見 [Daily Report](user-guide/daily-report.md)。
