# Phase 56：Strategy Qualification and Recommendation Evidence Planning

## 1. 文件目的

本文件定義 Phase 56 的產品問題、核心契約、promotion states、驗證原則、Workspace integration、子階段、驗收條件與明確非目標。

本文件是 planning baseline，不直接授權 production implementation。每一個 production 子階段仍需建立獨立範圍、測試計畫、Independent Reviewer Gate、CI Gate 與 Merge Gate。

## 2. Baseline

- Repository：`Mike87117/tw_stock_tool`
- Baseline branch：`main`
- Baseline commit：`7aca94093e98ada95cbb591af651070f5d2632cf`
- Package version：`0.4.0`
- Previous phase：Phase 55.3 Artifact Hub 與 Research Workspace
- Current product boundary：歷史資料研究、策略驗證、離線模擬交易與研究 artifacts
- Explicit non-goals：券商串接、真實下單、自動交易、個人化投資建議與獲利保證

## 3. Product problem

目前系統已具備：

- 技術訊號與多股票掃描。
- Backtest、Strategy Compare、Parameter Sweep 與 Walk Forward。
- Baseline ML walk-forward validation。
- 單股與多股歷史模擬交易。
- Portfolio Risk、Kill Switch 與 Guard boundaries。
- Research Run、Run Manifest 與 Workspace。

但這些能力尚未共同回答：

> 一個策略是否有足夠、可重現且樣本外的證據，值得從研究候選升級到 forward paper trading？

目前主要缺口：

1. Scanner ranking 主要反映當下技術條件，不代表未來超額報酬已被驗證。
2. Backtest、Parameter Sweep、Walk Forward 與 ML results 是分散工具，沒有一致 promotion decision。
3. 沒有跨股票、跨 window、跨市場狀態的策略穩定度判定。
4. 沒有版本化 qualification policy。
5. 沒有 fail-closed 規則阻止未驗證策略產生可執行 order intent。
6. 沒有 persistent evidence artifact 將 promotion decision 與 Run Manifest 關聯。

## 4. Phase goal

Phase 56 的目標是建立 Strategy Qualification product boundary，使每個候選策略可以產生：

- 可重現的 evaluation configuration。
- 嚴格分離的 in-sample 與 out-of-sample evidence。
- Universe-level、window-level 與 symbol-level metrics。
- Benchmark、交易成本與風險調整後結果。
- Deterministic findings。
- 明確 promotion decision。
- Workspace-managed qualification artifact。

Phase 56 不以「保證獲利」為驗收條件。產品目標是降低過度擬合、資料洩漏與未驗證策略進入交易流程的風險。

## 5. Product principles

### 5.1 Evidence before recommendation

原始 BUY／SELL 技術訊號不是 promotion evidence。

未達 `PAPER_READY` 的策略：

- 可以輸出 research result。
- 可以輸出 `WATCH`／`NO_TRADE` 類型的研究提示。
- 不得產生可送往 broker boundary 的 order intent。

### 5.2 Out-of-sample evidence is authoritative

Promotion decision 只能依據 out-of-sample evidence。

In-sample metrics 可用於：

- 選參數。
- 排序候選。
- 產生診斷。

但不得單獨導致 `PAPER_READY`。

### 5.3 Fail closed

下列任一狀況必須阻止升級：

- Evaluation data 不完整。
- Benchmark 無法建立。
- 成本假設缺失或無效。
- Out-of-sample sample size 不足。
- Metrics 含 non-finite values。
- Data leakage contract 無法證明。
- Workspace artifact 或 schema validation 失敗。
- Qualification policy 無法辨識。

### 5.4 Policy is versioned

Qualification thresholds 不得散落在 CLI、report renderer 或 strategy code。

第一版必須使用明確 policy identifier，例如：

```text
qualification_policy: taiwan_equity_daily_v1
```

Policy changes 必須可追蹤、可測試，並且不得回溯改寫既有 evaluation artifact。

### 5.5 No automatic live promotion

即使策略取得 `PAPER_READY`，也只代表可以進入固定版本的 forward paper trading。

它不代表：

- 可以自動連接 broker。
- 可以跳過人工 review。
- 可以放大資金。
- 可以保證未來績效。

## 6. Promotion states

第一版只使用三個 terminal states：

```text
REJECTED
RESEARCH_CANDIDATE
PAPER_READY
```

### `REJECTED`

策略存在 blocking findings，例如資料洩漏、樣本不足、成本後績效失效、重大不穩定或風險超標。

### `RESEARCH_CANDIDATE`

策略具有部分正向 evidence，但尚未滿足全部 paper-trading gate。可繼續研究，不得產生 broker-facing order intent。

### `PAPER_READY`

策略通過已指定版本 qualification policy，可進入固定版本的 forward paper trading。

Promotion state 必須由 deterministic evaluator 產生，不能由 report renderer 或 LLM 自由判斷。

## 7. Proposed models

```text
QualificationPolicy
StrategyQualificationRequest
StrategyDescriptor
EvaluationDatasetDescriptor
BenchmarkDescriptor
CostAssumptions
QualificationMetricSet
SymbolEvaluation
WindowEvaluation
StabilityEvaluation
QualificationFinding
PromotionDecision
StrategyQualificationResult
```

建議全部採用 frozen／slotted dataclasses 或同等 immutable typed models。

### `QualificationPolicy`

至少包含：

- `policy_id`
- `policy_version`
- minimum out-of-sample observations
- minimum completed trades
- minimum evaluated symbols
- minimum valid windows
- benchmark requirement
- transaction cost stress scenarios
- drawdown／loss constraints
- stability requirements
- finding severity mapping

本 planning phase 不鎖定具投資意義的數值門檻；數值必須在獨立 policy phase 以 evidence 與測試鎖定。

### `StrategyQualificationRequest`

至少包含：

- strategy identifier
- exact strategy parameters or parameter search definition
- universe or canonical symbols
- data period and interval
- train／test／step configuration
- benchmark
- fee、tax、slippage assumptions
- qualification policy ID
- deterministic random seed where applicable

### `StrategyQualificationResult`

至少包含：

- evaluation ID
- strategy descriptor
- resolved request
- policy identity
- aggregate out-of-sample metrics
- symbol evaluations
- window evaluations
- sensitivity／stability summary
- findings
- promotion decision
- generated timestamp
- source Run IDs where applicable

## 8. Qualification evidence dimensions

第一版 evaluator 至少必須處理：

### 8.1 Data separation

- Train end 必須早於 test start。
- Parameter selection 只能讀取 training window。
- ML target horizon 必須使用 purge／embargo equivalent boundary。
- Same-bar signal／price execution 不得引入 look-ahead。
- Existing next-bar-open execution contract 必須保留。

### 8.2 Sample sufficiency

- Out-of-sample observations。
- Completed trades。
- Valid windows。
- Evaluated symbols。
- Error／missing window count。

少量交易造成的高 Sharpe 或高勝率不得直接通過。

### 8.3 Benchmark comparison

至少支援：

- Buy and hold of the evaluated symbol。
- Cash／zero-return reference where appropriate。
- Future market-index benchmark only after a separate data contract is approved。

Promotion evidence 必須清楚分開 absolute return 與 benchmark-relative result。

### 8.4 Cost realism

至少包含：

- Brokerage fee。
- Taiwan securities transaction tax。
- Configurable slippage。
- Higher-cost stress scenario。

策略只有在成本後仍符合 policy 時才可能升級。

### 8.5 Risk and stability

至少檢查：

- Maximum drawdown。
- Worst window。
- Positive／negative window ratio。
- Symbol concentration。
- Trade concentration。
- Turnover or exposure proxy。
- Parameter neighborhood sensitivity。
- Performance dispersion across symbols and windows。

### 8.6 Data quality findings

Evaluation 必須傳播：

- stale cache usage
- provider fallback
- partial symbol failure
- missing price fields
- invalid or non-finite metrics
- unsupported interval or schema

資料限制不得只出現在 Markdown prose；必須存在 typed findings。

## 9. Findings contract

建議 finding 結構：

```text
QualificationFinding
- code
- severity
- scope
- message
- metric_name
- observed_value
- threshold_value
- symbol
- window
```

Severity：

```text
info
warning
blocking
```

第一版 finding codes 至少包含：

```text
data_leakage_risk
insufficient_oos_observations
insufficient_trades
insufficient_symbols
insufficient_valid_windows
benchmark_missing
underperforms_benchmark
cost_stress_failure
max_drawdown_exceeded
window_instability
symbol_concentration
parameter_instability
non_finite_metric
partial_data_failure
unsupported_policy
```

Finding ordering、deduplication 與 promotion mapping 必須 deterministic。

## 10. Workspace and artifact contract

Phase 56 qualification result 必須支援 Workspace-managed artifact。

建議 artifact：

```text
artifacts/strategy-qualification.json
```

建議 artifact type：

```text
strategy_qualification
```

建議 schema：

```text
strategy_qualification schema 1.0
```

要求：

- JSON serializer／deserializer strict validation。
- UTF-8、deterministic key／collection ordering where contract requires。
- Existing artifact 不得默默 overwrite。
- Artifact reference 必須寫入 Run Manifest。
- Offline validate／inspect 不得抓取資料或重跑 evaluation。
- Workspace relocation 後 reference 仍可解析。

Run Manifest 不取代 qualification schema；它只保存 run-level provenance 與 artifact relationship。

## 11. Application boundary

建議新增：

```text
src/tw_stock_tool/application/strategy_qualification.py
```

Responsibilities：

- Validate typed request。
- Resolve qualification policy。
- Orchestrate existing backtest／walk-forward capabilities。
- Build deterministic evaluation result。
- Publish Workspace artifact through existing boundaries。

CLI、GUI 與 future API 不得自行實作 promotion logic。

Domain-level pure evaluator 建議位於：

```text
src/tw_stock_tool/qualification/
├── models.py
├── policies.py
├── evaluator.py
├── findings.py
└── serialization.py
```

Exact package names 必須在 Phase 56.1 implementation planning 中鎖定。

## 12. CLI direction

Possible future command：

```bash
twstock qualify-strategy \
  --strategy ma_cross \
  --stocks 2330 2317 2454 \
  --period 10y \
  --train-days 504 \
  --test-days 126 \
  --policy taiwan_equity_daily_v1 \
  --workspace research-workspace
```

CLI naming、arguments 與 output format 尚未授權；需在獨立 CLI phase characterization 後決定。

第一版不應讓 CLI 接受 `--force-paper-ready` 或任何繞過 blocking findings 的參數。

## 13. Recommendation evidence boundary

Phase 56 後續可建立 recommendation model，但必須與 raw signal 分離：

```text
RecommendationEvidence
- action: ENTER / WATCH / HOLD / EXIT / NO_TRADE
- promotion_state
- strategy_id and version
- evidence_run_id
- expected holding horizon
- risk budget reference
- invalidation conditions
- findings
- data limitations
```

Rules：

- `ENTER` 必須引用 `PAPER_READY` strategy evaluation。
- `RESEARCH_CANDIDATE` 最多產生 `WATCH`／`NO_TRADE`。
- `REJECTED` 不得產生 `ENTER`。
- LLM 可摘要 evidence，但不得改寫 promotion state。
- Recommendation evidence 仍是研究輸出，不是個人化投資建議。

## 14. Phase breakdown

## Phase 56.0：Contract Planning and Backlog

### Scope

- Freeze product problem、promotion states 與 non-goals。
- 定義 typed models、findings、policy identity 與 artifact boundary。
- 定義 data leakage、sample sufficiency、benchmark、cost 與 stability contracts。
- 建立 implementation issues 與 dependency graph。

### Production code

None。

### Exit criteria

- Planning document merged。
- Independent document review passes。
- Runtime source、tests 與 docs consistency audit passes。
- Phase 56.1 scope locked。

## Phase 56.1：Qualification Models and Pure Policy Evaluator

### Scope

- Add immutable typed models。
- Add versioned policy registry with one research-only default policy fixture。
- Add deterministic findings and promotion mapping。
- Evaluate supplied metric inputs only；不抓資料、不跑 backtest。
- Add strict JSON serialization and read-back。

### Required tests

- Invalid／non-finite value rejection。
- Finding ordering and deduplication。
- Blocking finding always prevents `PAPER_READY`。
- Policy identity round-trip。
- Unknown policy fail closed。
- Schema strict read-back。
- Deterministic serialization。

## Phase 56.2：Universe-level Out-of-sample Evaluation

### Scope

- Orchestrate existing Walk Forward and Backtest capabilities across symbols。
- Preserve next-bar-open execution semantics。
- Add cost stress scenarios and benchmark comparison。
- Build symbol、window and aggregate metrics。
- Publish Strategy Qualification artifact into Workspace。

### Required tests

- No test-window parameter leakage。
- Partial symbol failure is represented, not hidden。
- Insufficient sample cannot promote。
- Same inputs produce deterministic result ordering。
- Cost stress can downgrade promotion state。
- Workspace relocation and strict read-back。
- Legacy research commands remain unchanged。

## Phase 56.3：Recommendation Evidence

### Scope

- Convert qualified strategy evidence and current research signal into typed recommendation evidence。
- Enforce promotion-state action limits。
- Add offline inspect／validate artifact commands if separately approved。

### Required tests

- `REJECTED` cannot emit `ENTER`。
- `RESEARCH_CANDIDATE` cannot emit `ENTER`。
- `PAPER_READY` still may emit `NO_TRADE` when current signal or risk condition fails。
- LLM／renderer cannot modify promotion state。

## Phase 56.4：Forward Paper Trading Gate

### Scope

- Freeze exact qualified strategy version and policy evidence。
- Execute only on data arriving after qualification cutoff。
- Track expected versus observed fills、costs、drawdown and drift。
- Revoke or pause eligibility when predefined conditions fail。

### Out of scope

- Broker order placement。
- Real account state。
- Automatic capital scaling。

## Phase 56.5：Broker Safety Planning

Only after forward paper evidence is reviewed：

Authoritative safety contracts and dependency-ordered backlog are frozen in the [Phase 56.5 Broker Safety Architecture Plan](phase-56-5-broker-safety-plan.md).

- Account reconciliation。
- Order idempotency。
- Partial fills。
- Session calendar。
- Retry／timeout and broker error recovery。
- Secret management。
- Immutable external audit。
- Human approval。
- Emergency kill switch。

This phase is planning-only unless separately authorized。

## 15. Acceptance criteria

Phase 56 core qualification capability is complete only when：

1. Promotion decision is produced by typed deterministic code, not prose or LLM judgment。
2. In-sample metrics alone cannot produce `PAPER_READY`。
3. Parameter selection never reads test-window outcomes。
4. Evaluation includes minimum sample checks。
5. Evaluation includes benchmark-relative results。
6. Evaluation includes configured fees、tax and slippage stress。
7. Evaluation includes drawdown and stability findings。
8. Blocking findings always prevent promotion。
9. Unknown or invalid policy fails closed。
10. Result has strict versioned JSON schema and read-back validation。
11. Result can be stored in and relocated with Workspace。
12. Every recommendation action is constrained by promotion state。
13. Existing Scan、Daily、Backtest、Walk Forward、ML and simulated trading behavior remains compatible unless an explicit migration phase changes it。
14. Python 3.11／3.12 full suite and package smoke pass。
15. Documentation matches runtime behavior。

## 16. Explicit non-goals

Phase 56 must not include unless separately authorized：

- Guaranteed profit or guaranteed loss avoidance。
- Personalized financial advice。
- Broker API integration。
- Real order placement。
- Automatic live trading。
- Automatic capital scaling。
- New technical indicators solely to improve apparent backtest results。
- Large model／LLM selecting promotion state。
- Replacing deterministic policy with natural-language judgment。
- Optimizing thresholds on the same test set used for promotion。
- Silent exclusion of failed symbols or windows。
- Retrospective rewriting of historical qualification artifacts。

## 17. Dependency graph

```text
Phase 55.3 Closeout
        ↓
Phase 56.0 Contract Planning
        ↓
Phase 56.1 Models / Pure Policy Evaluator
        ↓
Phase 56.2 Universe-level OOS Evaluation
        ↓
Phase 56.3 Recommendation Evidence
        ↓
Phase 56.4 Forward Paper Trading Gate
        ↓
Phase 56.5 Broker Safety Planning
```

GUI improvements、new ML models and Broker Interface must not bypass this dependency graph。

## 18. Product metrics

後續除測試數量外，至少追蹤：

| Metric | Target direction |
| --- | --- |
| Qualification artifacts linked to Run Manifest | 100% |
| `PAPER_READY` decisions with complete OOS evidence | 100% |
| Promotion decisions produced by deterministic evaluator | 100% |
| Strategies promoted with blocking findings | 0 |
| Evaluations missing explicit cost assumptions | 0 |
| Evaluations silently dropping failed symbols／windows | 0 |
| Recommendation `ENTER` without `PAPER_READY` evidence | 0 |
| Same input／policy deterministic output ordering | 100% |

## 19. Product decision

The next production-code task after Phase 56.0 planning should be：

> **Phase 56.1 — Add Strategy Qualification immutable models, versioned policy identity, deterministic findings／promotion mapping, and strict JSON serialization without market-data or backtest orchestration.**

This ordering creates a testable decision contract before connecting existing research workflows or considering broker integration。
