# Phase 56.5：Broker Safety Architecture Planning

## 1. 文件狀態與授權邊界

本文件是 Phase 56.5 的權威 planning baseline。它只凍結 broker-neutral 安全契約與 dependency-ordered backlog，不授權 production broker implementation。

本階段明確禁止：

- 選擇、安裝或串接 broker SDK。
- 取得 credentials、登入 broker 或讀取真實帳戶。
- 送出、取消、修改或排程任何真實訂單。
- 新增 live-trading CLI／GUI 或 unattended automation。
- 改變 Phase 56 qualification、recommendation 或 forward-paper policy。
- 由 backtest／forward-paper 報酬自動放大 capital。

任何 Phase 56.5A–F production 工作都必須另開 issue、另行授權、獨立 review，且不得把本文件視為 live-order 授權。

## 2. Baseline

- Repository：`Mike87117/tw_stock_tool`
- Baseline branch：`main`
- Baseline commit：`dcb863d4a246d19b1e862afe918d673e37b58f00`
- Baseline date：2026-08-10
- Previous phase：Phase 56.4 Forward Paper Trading Gate
- E2 reviewed implementation：`bcd33f69925778c8e811ae4afbcb1cdfff1e6c0f`
- Existing full-suite evidence：2741 passed、7 skipped
- Parent roadmap：[Phase 56 Strategy Qualification Plan](phase-56-strategy-qualification-plan.md)

## 3. Safety objective

Phase 56.5 的目標是定義 deterministic、fail-closed 的 execution-control boundary，使未來系統可以從嚴格驗證的 forward-paper package 建立受限制的 order intent，同時保證 research artifact、LLM、renderer、CLI flag 或模糊 broker response 都不能直接造成 uncontrolled live order。

本文件處理的是安全與可恢復性，不保證策略獲利，也不降低市場、流動性或 broker operational risk。

### 3.1 Fundamental authorization rule

以下條件是必要但不充分：

```text
ForwardPaperPackageInspection.health == VALID
AND
ForwardPaperPackageSummary.eligibility_state == ACTIVE
```

`ACTIVE` 只代表 forward-paper eligibility。它永遠不是 live authorization。

禁止路徑：

```text
RecommendationEvidence -> broker order
ForwardEligibilityEvidence -> broker order
ACTIVE -> broker order
LLM / renderer / report -> broker order
```

唯一允許的概念路徑：

```text
fresh E2 inspection
    -> frozen source identity
    -> broker capability and session checks
    -> read-only account snapshot
    -> deterministic reconciliation
    -> versioned capital/risk policy
    -> explicit human authorization persisted
    -> bounded order intent persisted
    -> kill-switch recheck
    -> submission record persisted as SUBMITTING
    -> broker adapter side effect
    -> broker query/reconciliation
    -> externally anchored audit
```

任何必要狀態無法讀取、驗證、持久化或對帳時，一律停止新訂單。

## 4. Required repository audit

本計畫以現有實作為基礎，不假設尚不存在的能力。

| Existing boundary | Current behavior | Reuse decision | Live-safety gap |
|---|---|---|---|
| [`application.forward_paper_inspection`](../../src/tw_stock_tool/application/forward_paper_inspection.py) | 透過 `Workspace.open_existing`、catalog、resolver 與 D3 rebuild 做完全離線 E2 驗證 | 必須作為 source trust gate；不得另寫較寬鬆 scanner | summary 未形成 live handoff，且 package 只有 self-consistency、沒有簽章真實性 |
| [`forward_paper.inspection`](../../src/tw_stock_tool/forward_paper/inspection.py) | 型別化 `VALID`／`INVALID`、canonical findings、valid-only summary | 重用 health、run／publication／policy／symbol identity | `ACTIVE` 不含帳戶、時效、限額、人工核准或 broker state |
| [`forward_paper.publication`](../../src/tw_stock_tool/forward_paper/publication.py) | Publication Index 錨定 qualification、activation、ledger、recommendations、portfolio、metrics、eligibility 的 canonical SHA-256 | publication ID、artifact hashes 與 recommendation anchors 是 source identity | Publication Index 本身未外部簽章；coherent rewrite 仍可能 self-consistent |
| [`forward_paper.eligibility_models`](../../src/tw_stock_tool/forward_paper/eligibility_models.py) | `ACTIVE`／`PAUSED`／`REVOKED` 由 forward metrics 與 versioned policy 決定 | fail-closed state vocabulary 與 policy identity | policy 是 research-to-forward gate，不是 research-to-live limits |
| [`risk.rules`](../../src/tw_stock_tool/risk/rules.py) | 純函式檢查 order notional、position quantity/notional、total exposure、open positions | 計算模式可在新 immutable broker models 上重寫／驗證 | 現有 snapshot 是模擬帳戶、模型可變，缺 daily loss/notional、broker open orders 與 authorization identity |
| [`simulated_paper_trading_guard`](../../src/tw_stock_tool/simulated_paper_trading_guard/adapter.py) | 聚合 simulated risk 與一個 in-memory kill-switch decision | 可重用「所有 gate 必須 allow」的概念 | adapter 綁定 `SimulatedOrder`／`SimulatedPortfolio`，沒有 reconciliation、approval、persistence 或 broker ambiguity |
| [`kill_switch`](../../src/tw_stock_tool/kill_switch/models.py) | 單一 process 內的 active boolean、reason、timestamp | 可重用 fail-closed decision 概念 | 無 durable/external state，且沒有 stop-new、cancel-open、liquidate 三種語意 |
| [`paper_trading.models`](../../src/tw_stock_tool/paper_trading/models.py) | 模擬 order、單一 fill、rejection、position 與 sequential audit records | side、quantity、fill accounting 與事件追蹤概念可參考 | `SimulatedOrder` 可變；假設一 order 對一 fill；audit 是 mutable application-owned list |
| [`paper_trading.runtime`](../../src/tw_stock_tool/paper_trading/runtime.py) | pending order 依 symbol 保存在記憶體，計算 reserved BUY notional | reserved exposure 概念可重用 | restart 即遺失；無 account scope、client ID、submission attempt 或 unknown state |
| [`paper_trading.stepper`](../../src/tw_stock_tool/paper_trading/stepper.py) | order ID 為 `<symbol>-<side>-<bar-position>`；next-bar-open 直接 pop pending 並產生一個 fill／failure | deterministic ordering 與先處理 pending 的概念可參考 | 此 ID 不是跨 process/broker idempotency key；不能處理 partial fill、timeout、cancel/replace |
| [`paper_trading.coordinator`](../../src/tw_stock_tool/paper_trading/coordinator.py) | 以全域 chronological timeline、stable symbol order 處理模擬事件 | deterministic event order 可用於測試 oracle | 歷史 DataFrame timeline 不是 exchange session/calendar boundary |
| [`artifacts.workspace`](../../src/tw_stock_tool/artifacts/workspace.py) 與 [`artifacts.catalog`](../../src/tw_stock_tool/artifacts/catalog.py) | canonical path、no-clobber write、strict manifest read、offline catalog、unsafe path rejection | E2 package lookup與本機 evidence storage 可重用 | Workspace self-consistency 不是 external immutable audit，也不適合作為 live submission transaction store |
| [`research_run.RunManifest`](../../src/tw_stock_tool/research_run/models.py) | versioned run metadata 與 artifact references | run ID 與 manifest identity進入 source correlation | manifest 不得存 credentials，也不能代表 broker authorization |

Audit 結論：repository 目前沒有 broker adapter、account reconciliation、session calendar、persistent client-order idempotency、submission state machine、restart recovery、human approval store 或 externally anchored audit。這些都是新 boundary，不得把 simulated components 直接重新命名後投入 live path。

## 5. Exact Phase 56.4 precondition contract

### 5.1 Mandatory E2 input

未來 authorization application service 必須接收 Workspace root 與 exact run ID，並在同一 authorization operation 內呼叫：

```text
inspect_forward_paper_workspace_package(workspace_root, run_id)
```

禁止接收 report、cached prose summary、手動複製的 `ACTIVE` 字串或先前 process 留下的 boolean 取代 fresh inspection。

只有同時符合以下條件才可進入 broker read-only preflight：

1. inspection 是 exact `ForwardPaperPackageInspection`。
2. `health == VALID`、`findings == ()`、`summary` 與 `publication_index` 皆存在。
3. `summary.eligibility_state == ACTIVE`。
4. exact run ID、manifest run ID、Publication Index 與 rebuilt trust chain 已由 E2 對齊。
5. policy ID/version 是 package 中已驗證的 identity。
6. intent symbol 位於 `summary.qualified_symbols`。
7. intent 的 recommendation ID/SHA-256 與 ledger decision identity 必須對應 Publication Index 的 ordered recommendation anchor。

`INVALID`、`PAUSED`、`REVOKED`、缺 artifact、未知 schema、path 不安全、identity mismatch 或 E2 exception 一律 fail closed。

### 5.2 Frozen source identity

每個 future `BrokerOrderIntent` 與 authorization 必須綁定：

- Workspace exact `run_id`。
- `publication_id`。
- E2 驗證後 Publication Index canonical bytes 的 SHA-256。
- `activation_id`。
- `qualification_evaluation_id`。
- `strategy_id`。
- `eligibility_id`、policy ID/version 與 exact `ACTIVE` state。
- qualified symbol universe digest與 intent symbol membership。
- source ledger ID。
- source recommendation ID 與 recommendation SHA-256。
- source decision 的 observed time、signal、action與 selected-parameters digest。

現有 E2 summary 未攜帶全部 decision-level identity；56.5A 必須建立一個由 fresh E2 trusted objects 產生的 immutable handoff model，不得讓 caller 自行拼接這些欄位。

### 5.3 Freshness and time-of-check rules

- Fresh E2 inspection 必須在 authorization transaction 內執行，不能只依賴 cache。
- Authorization 必須綁定 inspection completion timestamp與 canonical Publication Index digest。
- Package 在 authorization 前後 digest 改變時 authorization 無效。
- Broker snapshot、reconciliation 與 approval 各自具有短 TTL；任何一者過期都必須重新讀取／重新核准。
- E2 package 即使 valid 仍是 unsigned local evidence；live pilot 前必須另有 reviewed provenance/anchor policy，不能宣稱 E2 提供作者真實性。

## 6. Broker-neutral domain contracts

Phase 56.5A 若獲獨立授權，應建立 immutable、strictly validated、versioned models。Domain model 不得 import broker SDK type，也不得包含 credentials。

### 6.1 `BrokerCapabilities`

至少包含：broker/environment identity、market/currency、client-order-ID support與最大長度、query-by-client-ID support、fractional quantity support、supported order types/time-in-force、partial-fill reporting、cancel/replace semantics、account data freshness、trading permission、capability timestamp。

未知或不支援的必要能力不得降級猜測；它產生 blocking finding。

### 6.2 `BrokerAccountSnapshot`

至少包含：snapshot ID、account reference、environment identity（sandbox/live）、broker identity、retrieved-at、currency、cash、buying power、equity、capabilities、positions、open orders與 broker data version/cursor（若有）。

Account reference 必須是可稽核的 opaque identifier，不是 secret。所有 monetary values 必須有限、currency 明確、timestamp timezone 明確。

### 6.3 `BrokerPositionSnapshot`

至少包含：canonical symbol、broker symbol、quantity、available quantity、average cost（若可靠）、market value（若可靠）、realized/unrealized PnL（若可靠）、as-of time與 reliability flags。

缺少 policy 必要欄位時不得以 0 代替未知值。

### 6.4 `BrokerOpenOrderSnapshot`

至少包含：broker order ID、client order ID、economic intent ID、symbol、side、original quantity、cumulative filled quantity、remaining quantity、status、submitted-at、last broker update與 fees/taxes（若有）。

### 6.5 `BrokerSafetyPolicy`

至少包含：policy ID/version、allowed broker/environment/account refs、allowed markets/order types、maximum order notional、maximum post-fill account exposure、maximum per-symbol exposure、maximum simultaneous open orders、maximum daily submitted notional、maximum daily loss、snapshot/reconciliation/authorization TTL、initial allocation ceiling與 required capabilities。

Policy 預設限額為零；沒有 explicit reviewed non-zero policy 就不能送單。Strategy sizing 不能覆寫 safety limit，實際允許值取兩者中更小者。

### 6.6 `BrokerSafetyFinding`

Finding 至少具有 stable code、severity、subject identity、observed/expected（經 redaction）、message與 blocking boolean。第一版 blocking categories 至少包含：

- invalid E2 source或 non-`ACTIVE` eligibility。
- account/environment mismatch。
- stale/incomplete broker snapshot。
- position/open-order/unresolved-submission mismatch。
- missing capability或 trading permission。
- session closed/unknown或 authorization expired。
- capital/position/daily-loss limit exceeded。
- kill-switch active/unknown。
- persistence/audit unavailable。
- ambiguous prior broker state。

### 6.7 `BrokerReconciliationResult`

至少包含：reconciliation ID、snapshot ID、local-state version、expected vs observed positions/open orders/submissions、ordered findings、completed-at與 `is_reconciled`。

`is_reconciled` 只能在沒有 blocking finding 時為 true。Reconciliation 絕不自動覆寫 local state 配合 broker；差異必須保留並由明確 human resolution action 處理。

### 6.8 `BrokerExecutionAuthorization`

第一個 live-capable contract 必須是 short-lived immutable approval，至少包含：

- authorization ID與 one-time consumption state。
- account/environment/broker identity。
- source run/publication/decision/recommendation identity。
- reconciliation ID與 snapshot ID。
- allowed exact symbol set、side、order type/time-in-force。
- maximum quantity與 maximum notional。
- not-before與 expiration timestamp。
- broker safety policy ID/version。
- approval timestamp與 opaque approver identity reference。
- kill-switch state version observed at approval。

不得使用 wildcard account/symbol/side、無期限 approval、`--yes`、config file、LLM output 或 `ACTIVE` 作為 approval。Authorization 使用後、過期、source digest 改變、reconciliation 改變或 kill-switch version 改變即失效。

### 6.9 `BrokerOrderIntent`

至少包含：economic intent ID、stable idempotency key、source/authorization identity、account/environment、session date、canonical/broker symbol、side、quantity或 reviewed notional policy、order type、time-in-force、limit price（若適用）、created-at與 revision。

Intent 是 immutable economic request，不是 broker SDK request。Adapter 只能從已 authorized intent 建立 provider payload。

### 6.10 `BrokerSubmissionRecord` and `BrokerExecutionRecord`

`BrokerSubmissionRecord` 保存每次 side-effect attempt：intent ID、attempt ID、state、stable client order ID、broker order ID（可空）、pre-submit persistence version、request timestamp、ack timestamp、sanitized outcome與 last reconciliation ID。

`BrokerExecutionRecord` 保存 broker execution facts：broker order ID、stable fill/execution ID、fill quantity/price/time、incremental fee/tax、cumulative quantity與received-at。Broker 重複 event 必須由 stable execution identity 去重，不得重複套用 position/cash。

### 6.11 `BrokerAuditRecord`

每筆 record 至少包含：monotonic sequence、record ID、event type、occurred/recorded timestamp、actor reference、source/reconciliation/authorization/intent/submission/broker IDs、kill-switch version、sanitized payload digest、previous-record digest與external-anchor reference（若已錨定）。

Audit model 不包含 secret或 raw broker request/response。

## 7. Reconciliation before authorization

### 7.1 Read-only preflight

每次 authorization 前，系統必須從 read-only adapter 取得並持久化：

1. account/environment identity與 capabilities。
2. cash、buying power與 currency。
3. canonical positions。
4. open orders與 broker-reported pending/cancel states。
5. 可由 stable client/broker IDs 查詢的 unresolved submissions。
6. trading permission與data freshness。

然後與 local durable state 對帳：positions、known open orders、nonterminal submission records、daily submitted notional、fills/fees/taxes與 last reconciled cursor。

### 7.2 Blocking discrepancies

下列任何一項阻擋 authorization：

- account、broker或 sandbox/live environment 不符 policy。
- local position quantity 與 broker quantity 不符。
- broker 有 local 不知道的 open order，或 local nonterminal order 在 broker 無法解析。
- 相同 client order ID 對應不同 economic facts。
- cash/buying power/currency 缺失、過期、非有限值或互相矛盾。
- capability/trading permission 未知或不足。
- previous `UNKNOWN_SUBMISSION_STATE`／`RECONCILIATION_REQUIRED` 尚未解除。
- daily notional/loss、exposure或open-order counters 無法可靠計算。

Human resolution 必須產生獨立 audit record與新的 local-state version；不能直接 mutate 舊 record 或靜默「以 broker 為準」。

## 8. Capital and position limits

Live safety limits 與 strategy sizing 分離且 versioned。第一個 live-capable policy 必須同時限制：

- per-order maximum notional。
- post-fill total account exposure。
- post-fill per-symbol exposure與quantity。
- simultaneous broker open orders plus unresolved submissions。
- daily submitted notional，包含 pending/unknown attempts而不只 filled orders。
- daily realized/unrealized loss；若 broker data 不可靠，first live pilot 必須 fail closed 而不是略過。
- zero/very-small initial allocation ceiling。

Limit 計算必須包含已成交部位、open order remaining quantity、unknown submissions的保守全額與本 intent projected exposure。Sell 不能假設一定降低 risk；shorting、borrow、currency與fees capability 不明時 fail closed。

Backtest、qualification或forward-paper return 不得自動決定這些限額。

## 9. Stable idempotency identity

### 9.1 Economic intent key v1

Domain stable key 固定為：

```text
broker_order_intent_key_v1:<sha256(canonical-json-bytes)>
```

Canonical JSON 必須使用 versioned strict serializer、UTF-8、sorted keys、no NaN，且只包含 immutable source facts：

```text
schema_version
account_reference
environment_identity
publication_id
publication_index_sha256
ledger_id
recommendation_id
recommendation_sha256
canonical_symbol
side
quantity_mode
quantity_or_notional
order_type
limit_price_if_any
time_in_force
execution_session_date
intent_revision
```

Timestamp、random UUID、process ID 或 broker request attempt 不得單獨成為 duplicate protection。相同 payload 必須產生相同 key；任一 economic fact 改變必須產生不同 key。

### 9.2 Broker client order ID

Canonical client ID 是 `twst1-` 加上完整 64-character digest。若 broker 不支援其長度，adapter 可以使用 capability-specific encoding，但必須在第一次 submission 前持久化 full-key-to-client-ID mapping、檢查 collision並可由 client ID 反查 full key。單純截斷 digest 不合格；無法提供穩定查詢能力的 broker capability fail closed。

### 9.3 Persistence ordering and concurrency

在第一次 broker side effect 前必須以 durable transaction：

1. enforce unique economic-intent key。
2. persist intent與source/authorization/reconciliation identities。
3. consume authorization或原子地保留其使用權。
4. persist submission attempt為 `SUBMITTING`。
5. append pre-submit audit record。

同帳戶必須有跨 process 的 durable concurrency control。In-memory dict、lock或「先送單再寫檔」都不接受。

## 10. Submission state machine

Frozen first-version states：

```text
PREPARED
AUTHORIZED
SUBMITTING
ACKNOWLEDGED
PARTIALLY_FILLED
FILLED
CANCEL_PENDING
CANCELLED
REJECTED
EXPIRED
UNKNOWN_SUBMISSION_STATE
RECONCILIATION_REQUIRED
```

核心 transition rules：

- `PREPARED -> AUTHORIZED`：fresh E2、session、reconciliation、limits、human approval與kill-switch皆通過且已持久化。
- `AUTHORIZED -> SUBMITTING`：authorization 未過期且未消耗；immediate kill-switch recheck 通過；submission/audit 已 durable commit。
- `SUBMITTING -> ACKNOWLEDGED|REJECTED`：只有明確 broker response或query evidence。
- `SUBMITTING -> UNKNOWN_SUBMISSION_STATE`：timeout、connection loss、process crash window或無法證明 broker 未收到。
- `ACKNOWLEDGED -> PARTIALLY_FILLED|FILLED|CANCEL_PENDING|REJECTED`：依 broker facts，不以 local timer猜測。
- `PARTIALLY_FILLED -> PARTIALLY_FILLED|FILLED|CANCEL_PENDING`：每個 unique fill 增量更新。
- `CANCEL_PENDING -> CANCELLED|PARTIALLY_FILLED|FILLED|UNKNOWN_SUBMISSION_STATE`。
- 任一 contradictory/unsupported event -> `RECONCILIATION_REQUIRED`。
- Terminal record immutable；resolution 以新 event追加，不重寫歷史。

`UNKNOWN_SUBMISSION_STATE` 與 `RECONCILIATION_REQUIRED` 必須阻擋同帳戶新 authorization與 blind resubmission。

## 11. Retry and timeout policy

### 11.1 Safe bounded retries

Read-only capability/account/position/open-order/get-order calls可在 total deadline 內使用 bounded exponential backoff與 jitter；每次 retry 都 audit。Read failure 最終結果是 unavailable，不得沿用 stale success 當作 current reconciliation。

Local transaction 在確認未發生 broker side effect時可安全 retry，但仍受 unique key與state transition約束。

### 11.2 Unsafe automatic retries

以下不能因 timeout 自動重送：

- `submit_order`。
- cancel/replace 中可能已建立 replacement order 的 mutating call。
- broker 已收到但 acknowledgement 遺失的任何 operation。

Network timeout 不是 submission failure 證明。正確流程：

1. persist `UNKNOWN_SUBMISSION_STATE`。
2. 先以 stable client order ID 查詢。
3. 再以 broker order ID、account open orders、fills與positions reconciliation。
4. 只有可證明未提交且 policy 明確允許時，才可由 human-reviewed recovery action建立新 attempt。
5. 仍模糊則維持 blocked，要求 human resolution。

即使 broker 宣稱 client-order-ID idempotent，第一版也不以 blind retry取代 reconciliation。

## 12. Partial fills, cancel and replace

每個 broker order 必須維持：

```text
0 <= cumulative_filled_quantity <= submitted_quantity
remaining_quantity = submitted_quantity - cumulative_filled_quantity
cumulative_filled_quantity = sum(unique execution quantities)
```

規則：

- 一個 order 可有零到多個 fill；每個 fill 按 stable broker execution ID 去重。
- Fees/taxes以 incremental execution facts 累加；unknown 不得當作 0。
- Partial fill 立即影響 position、cash、risk exposure與daily limits。
- Cancel after partial fill 只取消 remaining quantity，已成交部位不可回滾。
- Cancel acknowledgement 前仍把 remaining quantity視為 exposure。
- Broker rejection after partial execution不得把整筆標為無成交；保留 fills並進入 reconcileable terminal lineage。
- Replace 必須建立新的 broker order identity與submission record，保留同一 economic lineage並增加 `intent_revision`。
- Replacement quantity不得超過原 intent remaining approved quantity；authorization過期或risk/session state改變時需重新核准。
- Cancel/replace ambiguity 進入 unknown/reconciliation state，不得同時保留兩個未計入risk的live orders。

## 13. Session and calendar boundary

Phase 56.5A 定義 broker-neutral `TradingSessionSnapshot`／calendar protocol，至少回答：

- timezone identity與session date。
- current state：regular、auction/pre-open（若支援）、closed、unknown。
- 現在是否允許該 order type submission/cancel。
- holiday、special closure與early close。
- data source/version與as-of time。

Weekday/hour hard-code、local machine timezone或historical DataFrame index都不合格。實際 exchange calendar provider待 broker/market選定後在獨立 issue決定。

Queued intent不得靜默跨 session。Session 改變時 intent `EXPIRED`；若 policy允許下一 session，必須 fresh E2/reconciliation、重新計算limits並取得新 authorization。

## 14. Emergency kill switch

Broker-neutral kill-switch state必須由 durable/external source讀取，並具有 state version、scope、changed-at、reason與actor reference。讀不到狀態等同 active。

必查時點：

- authorization 前。
- authorization persist transaction 內。
- submission side effect 立即前。
- recovery retry、cancel/replace前。

三種 action scope 必須分離：

1. `STOP_NEW_ORDERS`：阻擋新 authorization/submission；不自動取消或賣出。
2. `CANCEL_OPEN_ORDERS`：需獨立 operator action、session/capability check與逐筆audit；不代表成功取消。
3. `LIQUIDATE_POSITIONS`：第一版不實作；必須另有reviewed policy、human approval、limits與order plan。

單一 boolean 不得同時觸發 liquidation。Submission途中 switch啟動時，先保存unknown/ack facts並reconcile；不能假設 broker order被取消。

## 15. Secret management

Frozen rules：

- credentials/API keys/tokens不得出現在 repository、Workspace、Run Manifest、Publication Index、domain dataclass、equality/hash、serialization、logs、exceptions、audit、screenshots或fixtures。
- Broker adapter透過 external runtime secret provider取得短期 secret或opaque handle；domain/application layer只看非敏感 account/broker reference。
- Secret provider、broker SDK與credential lifecycle只存在adapter composition boundary。
- Adapter在丟出error前必須轉為typed sanitized error；headers、URLs、request bodies、account raw identifiers與SDK repr依allowlist redaction。
- Audit/application logs只保存request digest、stable IDs與sanitized category，不保存raw payload。
- Tests只使用明顯fake values，並加入repository/diff/log secret scan。

Provider-specific secret storage待broker/environment選定後另行決策。

## 16. Immutable external audit and trust model

Live audit與mutable application log、Workspace research artifacts分離。Audit必須correlate：

- E2 run/package/publication/decision/recommendation identity。
- account snapshot與reconciliation identity。
- authorization、approver與policy identity。
- intent、client order、submission attempt與broker order IDs。
- acknowledgements、fills、fees/taxes、rejections、cancels、timeouts與unknown states。
- kill-switch state/version與human recovery actions。

每個 side effect 前後都必須先能append audit；audit unavailable時禁止新 side effect。Records append-only、hash-linked並定期由external signed/WORM/independently controlled anchor保存root digest。

Trust claim 必須精確：

- Workspace與hash chain只能證明目前內容self-consistent。
- Application-owned append-only store仍可能被有權限的actor重寫。
- 沒有external anchor/signature時不得稱為tamper-proof或cryptographically authentic。
- External mechanism、retention與verification procedure必須在56.5C選型後獨立review。

## 17. Broker adapter contract

Read-only與mutating operations在interface與application service中分開：

```text
BrokerReadAdapter
    get_capabilities()
    get_account_snapshot()
    get_positions()
    get_open_orders()
    get_order_by_client_id(client_order_id)
    get_order_by_broker_id(broker_order_id)

BrokerOrderAdapter
    submit_order(intent, client_order_id)
    cancel_order(broker_order_id, client_order_id)
```

Rules：

- Adapter input/output只使用broker-neutral models或sanitized typed errors。
- SDK classes、status strings與payload conversions不得洩漏到domain/application branches。
- Application不能用broker名稱做conditional risk logic；差異透過typed capabilities/policy表達。
- Unknown status映射為unknown/reconciliation required，不得映射成rejected/cancelled。
- `submit_order`只接受persisted、authorized intent與stable client ID。
- Adapter不決定strategy、quantity、approval、retry或kill-switch policy。

## 18. Restart recovery

任何 live-capable process在接受新intent前必須：

1. 取得account-scoped durable lease。
2. load所有nonterminal submission、unknown state、unconsumed/possibly consumed authorization與last audit anchor。
3. 由stable client/broker IDs查詢broker。
4. 取得fresh account/positions/open orders/fills snapshot。
5. deterministic reconcile每個record與aggregate account state。
6. append recovery audit並persist新state version。
7. 只有所有blocking discrepancies解除後才開放新authorization。

Crash windows必須以failure-injection tests覆蓋：intent persist前、authorization consume前後、`SUBMITTING` persist後/SDK call前、SDK call後/ack persist前、partial fill persist中與cancel/replace中。

In-memory-only idempotency、pending order或audit不接受。

## 19. Architecture decisions settled by this plan

1. **Mandatory Phase 56.4 identity**：fresh exact E2 inspection，加上run ID、canonical Publication Index SHA-256、publication/activation/qualification/strategy/eligibility/policy/ledger/recommendation identities與qualified-symbol membership。
2. **Broker data before authorization**：capabilities、account/environment、cash/buying power/equity/currency、positions、open orders、unresolved submissions、permissions與freshness。
3. **Blocking discrepancies**：任何identity、position/order/submission、cash/currency、capability、session、limit、kill-switch、persistence/audit或unknown-state mismatch。
4. **Stable client order identity**：`broker_order_intent_key_v1` canonical JSON SHA-256；provider encoding必須persistent、collision-checked、queryable。
5. **Retry safety**：bounded read-only retry可接受；mutating timeout先unknown再reconcile，禁止blind resubmit。
6. **Partial fills**：unique executions增量記帳，remaining quantity嚴格推導，risk/audit立即更新，cancel/replace保留economic lineage。
7. **Restart-persistent state**：source identity、policy/snapshot/reconciliation、authorization consumption、intent/idempotency mapping、submission lifecycle、fills、daily limits、kill switch與audit anchor。
8. **Human approval**：reconciliation後建立short-lived immutable、account/source/symbol/side/quantity/notional-bounded authorization；過期/使用/identity change即失效。
9. **Mandatory first-live limits**：order、account exposure、per-symbol、open orders、daily notional、reliable daily loss與very-small allocation；default zero。
10. **Secret exclusion**：external secret provider、domain完全無secret、adapter allowlist redaction、fake-only tests與secret scan。
11. **Kill-switch meaning**：stop-new、cancel-open、liquidate三個獨立scope；unknown fail closed；第一版不自動liquidate。
12. **Audit trust**：application append-only/hash chain不是tamper-proof；live claim需要external signed/WORM anchor。
13. **Broker-independent vs specific**：models、policy、state machine、idempotency、reconciliation、audit與approval為broker-independent；SDK mapping、capabilities、calendar provider與secret acquisition留在adapter。
14. **Evidence before live pilot**：完成56.5A–E review/CI/sandbox/failure injection/recovery/security/audit/operations evidence後，仍需單獨明確授權56.5F。

## 20. Dependency-ordered implementation backlog

本planning PR不建立follow-up implementation issues。只有本文件通過independent review後，才依下列順序建立各自scope與gate。

### 56.5A — Broker safety contracts and pure architecture

Scope：immutable broker-neutral models、strict serializers、state transition table、stable intent-key builder、pure reconciliation/limit evaluators、calendar/adapter protocols。不得加入broker SDK或I/O side effect。

Exit evidence：model/adversarial tests、canonical serialization、transition property tests、source identity tests、no-secret/no-SDK audit、independent review。

### 56.5B — Read-only broker account adapter and reconciliation

Depends on：56.5A。

Scope：選定sandbox/test environment後的read-only adapter、capability discovery、account/position/open-order snapshots與deterministic reconciliation。不得submit/cancel order。

Exit evidence：contract tests、stale/missing/duplicate data fail-closed tests、account/environment mismatch tests、recorded fake responses、no real credentials inrepository。

### 56.5C — Persistent idempotency and external audit foundation

Depends on：56.5A；可與56.5B在不衝突scope下開發，但56.5D同時依賴B與C。

Scope：durable account-scoped transaction store、unique intent keys、authorization consumption、submission lifecycle persistence、restart recovery skeleton、append-only audit與external anchor selection。仍不得broker mutation。

Exit evidence：concurrency tests、crash-window failure injection、migration/backup/restore、audit verification、secret redaction與operator recovery runbook。

### 56.5D — Broker sandbox/test-environment submission boundary

Depends on：56.5B、56.5C。

Scope：只在broker官方sandbox/test environment實作submit/cancel adapter、partial fill、timeout/unknown/reconciliation與cancel/replace。Production/live endpoint hard-disabled。

Exit evidence：duplicate-event、lost-ack、timeout、partial-fill、restart、session rollover、kill-switch與adapter capability tests；sandbox account reconciliation drill。

### 56.5E — Human approval and live safety gate integration

Depends on：56.5D。

Scope：short-lived approval workflow、versioned live safety policy、operator identity/audit、kill-switch scopes、pre-submit recheck與live endpoint deny-by-default integration。完成此階段仍不授權真實下單。

Exit evidence：approval expiry/replay tests、zero-default limits、two-process race tests、secret/audit review、operator cancel/recovery tabletop、independent security/safety review。

### 56.5F — Extremely bounded live pilot

Depends on：56.5E，且必須另有explicit human/business/security authorization。

Scope不得由本文件預先授權。提案至少要指定broker/account、極小capital ceiling、symbols、side/order type、session、supervision、rollback、incident ownership與time-bounded authorization。

Go/no-go evidence：

- 56.5A–E exact-head independent reviews與CI全綠。
- Sandbox duplicate-prevention、partial-fill、timeout、restart與reconciliation drills通過。
- External audit anchor可驗證，secret scanning/redaction通過。
- Production account read-only reconciliation連續成功且無unresolved discrepancy。
- Calendar/capability/kill-switch/operator runbook演練完成。
- Named human approver與incident responder在線監督。
- Separate issue明確授權一次、限時、極小額pilot；未授權即no-go。

## 21. Review and validation checklist

Planning review必須拒絕任何：

- 把`ACTIVE`視為充分live authorization的路徑。
- reconciliation/approval/persistence之前的submission。
- timeout後blind duplicate submission。
- in-memory-only idempotency或restart recovery。
- one-order/one-fill假設。
- queued intent silent session rollover。
- secrets進入Workspace、logs、exceptions、audit或fixtures。
- ambiguous kill-switch或單一boolean自動liquidation。
- 把mutable/self-authenticating audit稱為tamper-proof。
- broker SDK type進入domain/application。
- 從planning直接跳到unrestricted live trading。
- profitability或guaranteed safety claim。

Repository validation：

- 本文件所有source/link paths存在且描述符合baseline行為。
- Diff不得包含broker dependency、credential、broker login、live order code或execution semantic change。
- 若文件索引變更，full unittest、Ruff與package smoke維持綠燈。
- Follow-up issue只能在本planning exact HEAD通過independent review後建立。

## 22. Exit criteria

Phase 56.5 planning只有在以下條件全部成立才完成：

1. Broker-neutral safety architecture與immutable model責任已凍結。
2. Phase 56.4 E2 trust boundary與unsigned limitation明確。
3. Reconciliation、idempotency、partial fills、retry、session、secrets、external audit、human approval、limits、kill switch與restart contracts全數凍結。
4. 56.5A–F dependency graph與各階段gate完成review。
5. Independent Review通過planning exact HEAD。
6. CI、full suite、lint與package smoke綠燈。
7. Repository仍無broker SDK、credentials或live execution path。
8. 後續production work保持separately gated並需要explicit authorization。
