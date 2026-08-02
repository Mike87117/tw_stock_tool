# Phase 55.3 Closeout：Artifact Hub 與 Research Workspace

## 1. Closeout summary

Phase 55.3 已完成本機、離線、檔案系統式 Research Workspace 的第一版產品邊界。

完成後，受支援的 Scan、Daily Report 與 Backtest Report 可以選擇使用 append-only Workspace execution：每一次執行配置獨立 run directory、canonical `manifest.json` 與 Workspace-managed artifacts。既有 legacy output mode 保持相容。

Workspace catalog 可以在不下載市場資料、不執行策略、不重跑研究的情況下列出與檢查既有 runs，並對損壞或不完整 run 回報 deterministic health findings。

本 Phase 不連接券商、不執行真實交易、不提供自動投資建議，也不保證獲利。

## 2. Baseline and final state

- Repository：`Mike87117/tw_stock_tool`
- Package version：`0.4.0`
- Final merged Phase 55.3D commit：`7aca94093e98ada95cbb591af651070f5d2632cf`
- Final Phase 55.3D pull request：`#71`
- Product boundary：歷史資料研究、策略驗證、離線模擬交易與研究 artifacts

## 3. Completed sub-phases

### Phase 55.3A：Contract Planning

- 定義 Workspace layout、path ownership、append-only run history 與 catalog source of truth。
- 鎖定 opt-in compatibility、full UUID lookup、duplicate detection 與 offline inspection boundary。

### Phase 55.3B：Workspace Storage Foundation

- 建立 Workspace models、controlled errors 與 canonical run allocation。
- 建立安全 relative path resolution、atomic no-clobber manifest persistence 與 strict read-back。
- 建立 filesystem catalog、run health findings 與 duplicate Run ID detection。

### Phase 55.3C：Workflow Integration

- 將 Scan、Daily Report 與 Backtest Report 接入 Workspace lifecycle。
- Workspace mode 將 managed outputs 限制於 allocated run directory。
- Legacy mode 的 output paths、manifest behavior 與 exit behavior 保持相容。
- Controlled workflow failure 在可行時發布 failure／partial manifest。

### Phase 55.3D：Read-only CLI

- 新增 `twstock run list --workspace PATH`。
- 新增 `twstock run inspect FULL-UUID --workspace PATH`。
- Query 只開啟既有 Workspace，不建立目錄、不讀取 artifact content、不抓取市場資料。
- Damaged runs 仍可被 catalog 看見；duplicate Run IDs fail closed。

### Phase 55.3E：Documentation and Migration Audit

- 核對 README、CLI guide、Artifact guide、Workspace runtime 與 Phase closeout evidence。
- 修正文件首頁停留在 Phase 55.3C／55.3D 的過期狀態。
- 將 Phase 55.3 標記為完成，並指定 Phase 56 Strategy Qualification 為下一個 approved planning topic。
- 保留既有 historical phase 文件，不以新文件改寫當時決策脈絡。

## 4. Final validation evidence

Phase 55.3D merge evidence：

- Focused tests：42 passed，2 skipped（本機 Windows 無 symlink privilege）。
- Unified CLI characterization：11 passed。
- Existing `twstock` CLI tests：56 passed。
- Full suite：2,326 passed，7 skipped。
- Python 3.11／3.12 GitHub Actions test 與 package-smoke 通過。
- Installed `twstock --help`、`twstock run --help`、`twstock run list --help` 與 `twstock run inspect --help` smoke 通過。

Phase 55.3E 僅修改文件與產品規劃，不修改 runtime behavior、schemas、CLI parser 或 package exports。

## 5. Acceptance criteria result

Phase 55.3 的主要 acceptance criteria 已達成：

1. 相同設定重跑會建立不同 run directory，不覆寫既有 run。
2. 每個完成的 managed run 具有 canonical `manifest.json`。
3. Canonical-looking incomplete directories 產生 controlled findings。
4. Managed artifact references 安全解析於 run directory 之下。
5. Workspace 搬移後仍可 list／inspect。
6. Catalog ordering 與 finding ordering deterministic。
7. 單一 damaged run 不會阻止其他 runs 被列出。
8. Missing artifact、unsupported schema 與 duplicate Run ID 皆有 controlled behavior。
9. List／inspect 不使用 network 或 domain execution。
10. Legacy CLI mode 維持相容。

## 6. Known limitations retained intentionally

以下能力不屬於 Phase 55.3：

- Parameter Sweep、Walk Forward、Strategy Compare、AI／ML、Paper Trading 與 Portfolio Simulation 的 Workspace migration。
- Run reproduce、delete、cleanup、retention 或 artifact preview。
- Experiment comparison 與策略資格審查。
- GUI Workspace browser。
- Database catalog、cloud sync 或 background daemon。
- Broker API、真實下單或自動交易。

本機 Windows 若沒有 symlink privilege，real-symlink tests 仍可能 skip；mocked reparse-point tests 與 CI coverage 保留。

## 7. Product decision after closeout

下一個產品問題不再是「如何保存研究結果」，而是：

> 如何根據可重現、樣本外、跨股票與成本調整後的證據，判定一個策略是否有資格從研究候選升級到 forward paper trading。

因此下一個 approved planning topic 是：

> **Phase 56 — Strategy Qualification and Recommendation Evidence**

Phase 56 必須先建立客觀 promotion gate，再考慮 Broker Interface。新增技術指標、複雜 ML 模型、GUI 或真實下單均不應早於 qualification contract。
