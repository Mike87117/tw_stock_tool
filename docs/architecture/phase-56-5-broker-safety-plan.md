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
    -> resolve unique current eligibility head / anti-rollback
    -> frozen source identity
    -> broker capability and session checks
    -> read-only account snapshot
    -> deterministic reconciliation
    -> versioned capital/risk policy
    -> explicit human authorization persisted
    -> bounded order intent persisted
    -> current-head + kill-switch recheck
    -> authorization-use claim + submission record persisted as SUBMITTING
    -> broker adapter side effect
    -> broker query/reconciliation
    -> externally anchored audit
```

任何必要狀態無法讀取、驗證、持久化或對帳時，一律停止新訂單。

## 4. Required repository audit

本計畫以現有實作為基礎，不假設尚不存在的能力。

| Existing boundary | Current behavior | Reuse decision | Live-safety gap |
|---|---|---|---|
| [`application.forward_paper_inspection`](../../src/tw_stock_tool/application/forward_paper_inspection.py) | 透過 `Workspace.open_existing`、catalog、resolver 與 D3 rebuild 做完全離線 E2 驗證 | 必須作為 source trust gate；不得另寫較寬鬆 scanner | summary 未形成 live handoff；per-run E2 validation 也沒有 current-head／supersession 語意，且 package 只有 self-consistency、沒有簽章真實性 |
| [`forward_paper.inspection`](../../src/tw_stock_tool/forward_paper/inspection.py) | 型別化 `VALID`／`INVALID`、canonical findings、valid-only summary | 重用 health、run／publication／policy／symbol identity | `ACTIVE` 不含 lineage head、帳戶、時效、限額、人工核准或 broker state |
| [`forward_paper.publication`](../../src/tw_stock_tool/forward_paper/publication.py) | Publication Index 錨定 qualification、activation、ledger、recommendations、portfolio、metrics、eligibility 的 canonical SHA-256 | publication ID、artifact hashes 與 recommendation anchors 是 source identity | Publication Index 本身未外部簽章；coherent rewrite 仍可能 self-consistent；多個 publication package 之間沒有 authoritative latest pointer |
| [`forward_paper.eligibility_models`](../../src/tw_stock_tool/forward_paper/eligibility_models.py) | `ACTIVE`／`PAUSED`／`REVOKED` 由 forward metrics 與 versioned policy 決定 | fail-closed state vocabulary 與 policy identity | 單一 artifact 沒有 predecessor／head／sequence，因此舊 `ACTIVE` 仍可被 E2 重新驗證；policy 也是 research-to-forward gate，不是 research-to-live limits |
| [`risk.rules`](../../src/tw_stock_tool/risk/rules.py) | 純函式檢查 order notional、position quantity/notional、total exposure、open positions | 計算模式可在新 immutable broker models 上重寫／驗證 | 現有 snapshot 是模擬帳戶、模型可變，缺 daily loss/notional、broker open orders 與 authorization identity |
| [`simulated_paper_trading_guard`](../../src/tw_stock_tool/simulated_paper_trading_guard/adapter.py) | 聚合 simulated risk 與一個 in-memory kill-switch decision | 可重用「所有 gate 必須 allow」的概念 | adapter 綁定 `SimulatedOrder`／`SimulatedPortfolio`，沒有 reconciliation、approval、persistence 或 broker ambiguity |
| [`kill_switch`](../../src/tw_stock_tool/kill_switch/models.py) | 單一 process 內的 active boolean、reason、timestamp | 可重用 fail-closed decision 概念 | 無 durable/external state，且沒有 stop-new、cancel-open、liquidate 三種語意 |
| [`paper_trading.models`](../../src/tw_stock_tool/paper_trading/models.py) | 模擬 order、單一 fill、rejection、position 與 sequential audit records | side、quantity、fill accounting 與事件追蹤概念可參考 | `SimulatedOrder` 可變；假設一 order 對一 fill；audit 是 mutable application-owned list |
| [`paper_trading.runtime`](../../src/tw_stock_tool/paper_trading/runtime.py) | pending order 依 symbol 保存在記憶體，計算 reserved BUY notional | reserved exposure 概念可重用 | restart 即遺失；無 account scope、client ID、submission attempt 或 unknown state |
| [`paper_trading.stepper`](../../src/tw_stock_tool/paper_trading/stepper.py) | order ID 為 `<symbol>-<side>-<bar-position>`；next-bar-open 直接 pop pending 並產生一個 fill／failure | deterministic ordering 與先處理 pending 的概念可參考 | 此 ID 不是跨 process/broker idempotency key；不能處理 partial fill、timeout、cancel/replace |
| [`paper_trading.coordinator`](../../src/tw_stock_tool/paper_trading/coordinator.py) | 以全域 chronological timeline、stable symbol order 處理模擬事件 | deterministic event order 可用於測試 oracle | 歷史 DataFrame timeline 不是 exchange session/calendar boundary |
| [`artifacts.workspace`](../../src/tw_stock_tool/artifacts/workspace.py) 與 [`artifacts.catalog`](../../src/tw_stock_tool/artifacts/catalog.py) | canonical path、no-clobber write、strict manifest read、offline catalog、unsafe path rejection | E2 package lookup與本機 evidence storage 可重用 | Workspace self-consistency 不是 external immutable audit，也不適合作為 live submission transaction store |
| [`research_run.RunManifest`](../../src/tw_stock_tool/research_run/models.py) | versioned run metadata 與 artifact references | run ID 與 manifest identity進入 source correlation | manifest 不得存 credentials，也不能代表 broker authorization |

Audit 結論：repository 目前沒有 broker adapter、account reconciliation、session calendar、persistent client-order idempotency、submission state machine、restart recovery、human approval store、forward eligibility current-head／anti-rollback registry 或 externally anchored audit。這些都是新 boundary，不得把 simulated components 直接重新命名後投入 live path。

## 5. Exact Phase 56.4 precondition contract

### 5.1 Mandatory E2 input

未來 authorization application service 不能只信 caller 指定的 Workspace run。它必須先對 candidate run 做：

```text
inspect_forward_paper_workspace_package(workspace_root, run_id)
```

再依本節 5.4 的 lineage contract 解析同一 evidence scope 中唯一 authoritative current eligibility head。Caller 提供的 exact run ID 只是一個 candidate identity，不是 current-state authority。

禁止接收 report、cached prose summary、手動複製的 `ACTIVE` 字串或先前 process 留下的 boolean 取代 fresh inspection／current-head resolution。

只有同時符合以下條件才可進入 broker read-only preflight：

1. candidate inspection 是 exact `ForwardPaperPackageInspection`。
2. `health == VALID`、`findings == ()`、`summary` 與 `publication_index` 皆存在。
3. `summary.eligibility_state == ACTIVE`。
4. exact run ID、manifest run ID、Publication Index 與 rebuilt trust chain 已由 E2 對齊。
5. policy ID/version 是 package 中已驗證的 identity。
6. intent symbol 位於 `summary.qualified_symbols`。
7. intent 的 recommendation ID/SHA-256 與 ledger decision identity 必須對應 Publication Index 的 ordered recommendation anchor。
8. candidate package 是 5.4 所定義的唯一 current lineage head，且沒有 newer／incomparable `PAUSED`、`REVOKED` 或 conflicting branch。
9. candidate head 不得低於 broker durable high-water mark。

`INVALID`、`PAUSED`、`REVOKED`、stale/superseded `ACTIVE`、lineage fork、缺 artifact、未知 schema、path 不安全、identity mismatch 或 E2 exception 一律 fail closed。

### 5.2 Frozen source identity

每個 future `BrokerOrderIntent` 與 authorization 必須綁定：

- Workspace exact `run_id`。
- `publication_id`。
- E2 驗證後 Publication Index canonical bytes 的 SHA-256。
- `activation_id`。
- `qualification_evaluation_id`。
- `strategy_id`。
- `eligibility_id`、policy ID/version 與 exact `ACTIVE` state。
- current-lineage-head fingerprint 與 progression identity。
- qualified symbol universe digest與 intent symbol membership。
- source ledger ID。
- source recommendation ID 與 recommendation SHA-256。
- source decision 的 observed time、signal、action與 selected-parameters digest。

現有 E2 summary 未攜帶全部 decision-level identity或 lineage progression；56.5A 必須建立一個由 fresh E2 trusted objects 產生的 immutable handoff／lineage observation model，不得讓 caller 自行拼接這些欄位。

### 5.3 Freshness and time-of-check rules

- Fresh E2 inspection 與 current-head resolution 必須在 authorization transaction 內執行，不能只依賴 cache。
- Authorization 必須綁定 inspection completion timestamp、canonical Publication Index digest與 current-lineage-head fingerprint。
- Package digest 或 current lineage head 在 authorization 前後改變時 authorization 無效。
- `AUTHORIZED -> SUBMITTING` 前必須再次 resolve current head；若 head identity/state/progression 改變、出現 newer `PAUSED`/`REVOKED` 或 resolver 無法證明唯一 head，禁止 side effect並使原 authorization失效。
- Broker snapshot、reconciliation 與 approval 各自具有短 TTL；任何一者過期都必須重新讀取／重新核准。
- E2 package 即使 valid 仍是 unsigned local evidence；live pilot 前必須另有 reviewed provenance/anchor policy，不能宣稱 E2 提供作者真實性。

### 5.4 Current eligibility lineage and anti-rollback

Fresh validation of one package does **not** prove that package is the current eligibility state。Broker safety boundary 必須額外建立 deterministic anti-rollback contract。

#### Lineage key

同一 lineage 至少以以下 immutable identities 綁定：

```text
activation_id
strategy_id
forward_eligibility_policy_id
forward_eligibility_policy_version
```

`activation_id` 已綁定 exact qualification source；不同 activation 不得被默認成彼此 supersede。若未來需要跨 activation promotion，必須另有 explicit reviewed migration/supersession contract。

#### Progression relation

對同 lineage 的兩個 E2-VALID publication packages，只有在較新 candidate 的 forward decision ledger 是較舊 ledger 的 **exact append-only prefix extension** 時，才可視為可比較的 progression：

- 舊 ledger decisions 必須逐筆 canonical-equal 成為新 ledger 的 prefix；
- recommendation IDs／SHA anchors 對應該 prefix 必須完全相同；
- 新 package 可增加後續 decisions，但不得重寫、刪除或重新排序舊 decisions；
- qualification、activation、strategy與policy identities 必須相同；
- progression 的 last observed decision time／decision count 不得倒退；
- equal progression 但 state、metrics、ledger SHA 或 publication identity 衝突時視為 fork，不得以 `created_at` 猜 winner。

`created_at`、random UUID 或 filesystem mtime 只能作 correlation，不能單獨決定哪個 package 比較新。

#### Unique current head

對 configured evidence scope 中同 lineage 的所有 E2-VALID packages，resolver 必須找到唯一 maximal package：它必須是所有其他可比較 package 的相同或 strict append-only extension。

Fail closed cases：

- 存在兩個 incomparable forks；
- equal progression 對應不同 state／content；
- 無法完整列舉 configured evidence scope；
- 任一可能更新 package 無法 E2 validate；
- current unique head 為 `PAUSED` 或 `REVOKED`；
- candidate 是舊 `ACTIVE`，但 unique head 已前進到另一 package。

因此「舊 `ACTIVE` package 在 newer `PAUSED`/`REVOKED` 之後仍能 E2 VALID」是預期現象，但它 **不得再取得 broker authorization**。

#### Durable broker high-water mark

Live-capable broker safety store 必須按 lineage 保存 durable `ForwardEligibilityHighWaterMark` 或等價記錄，至少包含：

- lineage key；
- last accepted current-head run/publication/eligibility/ledger identities；
- Publication Index digest；
- decision count與 last observed decision time；
- state；
- persisted-at與 audit correlation。

Rules：

- 新 candidate 必須證明為 stored high-water mark 的相同或 strict extension，不得倒退；
- broker process restart 後必須先恢復 high-water mark，再接受 authorization；
- high-water mark 指向的 package 消失、無法驗證或出現 fork時 fail closed；
- newer `PAUSED`／`REVOKED` 一旦成為 current head，舊 `ACTIVE` 不得因 restart、caller 選舊 run、Workspace relocation 或 cache 而重新生效；
- high-water mark 不能由 caller 手動降低；任何 reset/migration 必須是獨立 human-reviewed audited operation。

56.5A 凍結 lineage models／pure comparison rules；56.5C 提供 durable high-water mark／concurrency storage；56.5E 將 authorization 與 pre-submit current-head recheck 接入 live safety gate。

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

- invalid E2 source、stale/superseded source或 non-`ACTIVE` current eligibility。
- eligibility lineage fork／rollback／high-water-mark mismatch。
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

第一個 live-capable contract 必須是 short-lived **immutable approval facts**，至少包含：

- authorization ID。
- account/environment/broker identity。
- source run/publication/current-head/decision/recommendation identity。
- reconciliation ID與 snapshot ID。
- allowed exact symbol set、side、order type/time-in-force。
- maximum quantity與 maximum notional。
- not-before與 expiration timestamp。
- broker safety policy ID/version。
- approval timestamp與 opaque approver identity reference。
- kill-switch state version observed at approval。

不得使用 wildcard account/symbol/side、無期限 approval、`--yes`、config file、LLM output 或 `ACTIVE` 作為 approval。Authorization object 本身永遠不 mutation；過期、source/current-head digest 改變、reconciliation 改變或 kill-switch version 改變會使它不再可用，但不改寫舊 approval record。

#### 6.8.1 `BrokerAuthorizationUseRecord`

One-time consumption 必須與 immutable approval facts 分離。Durable store 以 `authorization_id` 建立 account-scoped unique use claim／record，至少包含：

- authorization ID；
- authorization-use ID；
- account/environment；
- bound economic intent ID與 idempotency key；
- claimed-at；
- use state，例如 `RESERVED`、`CONSUMED`、`ABANDONED`；
- submission attempt ID（若已建立）；
- persistence version與 audit correlation。

Rules：

- `authorization_id` 必須有 durable uniqueness constraint；兩個 process 不得同時 claim 同一 approval；
- claim 成功後，不允許另一 economic intent 使用同一 authorization；
- `RESERVED -> CONSUMED` 只能與同一 intent 的 `SUBMITTING` durable transaction 對齊；
- crash 後不得靠修改 `BrokerExecutionAuthorization` 回復「未使用」；restart recovery 必須讀 use record 判定狀態；
- 若 side effect 尚未發生且 operator 決定放棄，記錄 `ABANDONED`／新 audit event；若需要再嘗試，預設建立新的 human authorization，而不是偷偷重置舊 approval；
- approval facts、use claim與歷史 audit 都採 append/new-version semantics，不覆寫歷史證據。

### 6.9 `BrokerOrderIntent`

至少包含：economic intent ID、stable idempotency key、source/authorization identity、account/environment、session date、canonical/broker symbol、side、quantity或 reviewed notional policy、order type、time-in-force、limit price（若適用）、created-at與 revision。

Intent 是 immutable economic request，不是 broker SDK request。Adapter 只能從已 authorized intent 建立 provider payload。

### 6.10 `BrokerSubmissionRecord` and `BrokerExecutionRecord`

`BrokerSubmissionRecord` 保存每次 side-effect attempt：intent ID、attempt ID、state、stable client order ID、broker order ID（可空）、pre-submit persistence version、request timestamp、ack timestamp、sanitized outcome與 last reconciliation ID。

`BrokerExecutionRecord` 保存 broker execution facts：broker order ID、stable fill/execution ID、fill quantity/price/time、incremental fee/tax、cumulative quantity與received-at。Broker 重複 event 必須由 stable execution identity 去重，不得重複套用 position/cash。

### 6.11 `BrokerAuditRecord`

每筆 record 至少包含：monotonic sequence、record ID、event type、occurred/recorded timestamp、actor reference、source/reconciliation/authorization/authorization-use/intent/submission/broker IDs、kill-switch version、sanitized payload digest、previous-record digest與external-anchor reference（若已錨定）。

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

然後與 local durable state 對帳：positions、known open orders、nonterminal submission records、daily submitted notional、fills/fees/taxes、eligibility high-water mark與 last reconciled cursor。

### 7.2 Blocking discrepancies

下列任何一項阻擋 authorization：

- account、broker或 sandbox/live environment 不符 policy。
- local position quantity 與 broker quantity 不符。
- broker 有 local 不知道的 open order，或 local nonterminal order 在 broker 無法解析。
- 相同 client order ID 對應不同 economic facts。
- cash/buying power/currency 缺失、過期、非有限值或互相矛盾。
- capability/trading permission 未知或不足。
- previous `UNKNOWN_SUBMISSION_STATE`／`RECONCILIATION_REQUIRED` 尚未解除。
- current eligibility head 無法解析、倒退、fork、non-`ACTIVE` 或低於 durable high-water mark。
- daily notional/loss、exposure或open-order counters 無法可靠計算。

Human resolution 必須產生獨立 audit record與新的 local-state version；不能直接 mutate 舊 record 或靜默「以 broker 為準」。Eligibility high-water mark 的降低／reset 也不能被一般 reconciliation 自動修正。

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
current_lineage_head_fingerprint
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

在第一次 broker side effect 前必須以 durable account-scoped transaction：

1. re-resolve current eligibility head，要求仍與 authorization 綁定的 head 完全一致且 `ACTIVE`，並證明不低於 durable high-water mark；
2. enforce unique economic-intent key；
3. persist intent與source/current-head/authorization/reconciliation identities；
4. atomically create unique `BrokerAuthorizationUseRecord` claim for `authorization_id`；
5. persist submission attempt為 `SUBMITTING` 並將同一 use record transition／append至 `CONSUMED`；
6. advance eligibility high-water mark if and only if candidate is a proven strict extension；
7. append pre-submit audit record；
8. only after the durable transaction commits may broker adapter side effect occur。

同帳戶必須有跨 process 的 durable concurrency control。In-memory dict、lock、「先送單再寫檔」或 mutate approval object 都不接受。

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

- `PREPARED -> AUTHORIZED`：fresh E2、unique current eligibility head、session、reconciliation、limits、human approval與kill-switch皆通過且已持久化。
- `AUTHORIZED -> SUBMITTING`：authorization 未過期；current head 再次 resolve 後仍為相同 `ACTIVE` head且不低於 high-water mark；immediate kill-switch recheck 通過；unique authorization-use claim、submission與audit 已 durable commit。
- `SUBMITTING -> ACKNOWLEDGED|REJECTED`：只有明確 broker response或query evidence。
- `SUBMITTING -> UNKNOWN_SUBMISSION_STATE`：timeout、connection loss、process crash window或無法證明 broker 未收到。
- `ACKNOWLEDGED -> PARTIALLY_FILLED|FILLED|CANCEL_PENDING|REJECTED`：依 broker facts，不以 local timer猜測。
- `PARTIALLY_FILLED -> PARTIALLY_FILLED|FILLED|CANCEL_PENDING`：每個 unique fill 增量更新。
- `CANCEL_PENDING -> CANCELLED|PARTIALLY_FILLED|FILLED|UNKNOWN_SUBMISSION_STATE`。
- 任一 contradictory/unsupported event -> `RECONCILIATION_REQUIRED`。
- Terminal record immutable；resolution 以新 event追加，不重寫歷史。

`UNKNOWN_SUBMISSION_STATE`、`RECONCILIATION_REQUIRED`、eligibility lineage fork／rollback 或 current head non-`ACTIVE` 必須阻擋同帳戶新 authorization與 blind resubmission。

## 11. Retry and timeout policy

### 11.1 Safe bounded retries

Read-only capability/account/position/open-order/get-order calls可在 total deadline 內使用 bounded exponential backoff與 jitter；每次 retry 都 audit。Read failure 最終結果是 unavailable，不得沿用 stale success 當作 current reconciliation。

Local transaction 在確認未發生 broker side effect時可安全 retry，但仍受 unique key、authorization-use uniqueness與state transition約束。

### 11.2 Unsafe automatic retries

以下不能因 timeout 自動重送：

- `submit_order`。
- cancel/replace 中可能已建立 replacement order 的 mutating call。
- broker 已收到但 acknowledgement 遺失的任何 operation。

Network timeout 不是 submission failure 證明。正確流程：

1. persist `UNKNOWN_SUBMISSION_STATE`。
2. 先以 stable client order ID 查詢。
3. 再以 broker order ID、account open orders、fills與positions reconciliation。
4. 只有可證明未提交且 policy 明確允許時，才可由 human-reviewed recovery action建立新 attempt；若需要新 approval，建立新的 immutable authorization，而不是重置既有 use record。
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
- Replacement quantity不得超過原 intent remaining approved quantity；authorization過期、current eligibility head改變或risk/session state改變時需重新核准。
- Cancel/replace ambiguity 進入 unknown/reconciliation state，不得同時保留兩個未計入risk的live orders。

## 13. Session and calendar boundary

Phase 56.5A 定義 broker-neutral `TradingSessionSnapshot`／calendar protocol，至少回答：

- timezone identity與session date。
- current state：regular、auction/pre-open（若支援）、closed、unknown。
- 現在是否允許該 order type submission/cancel。
- holiday、special closure與early close。
- data source/version與as-of time。

Weekday/hour hard-code、local machine timezone或historical DataFrame index都不合格。實際 exchange calendar provider待 broker/market選定後在獨立 issue決定。

Queued intent不得靜默跨 session。Session 改變時 intent `EXPIRED`；若 policy允許下一 session，必須 fresh E2/current-head resolution/reconciliation、重新計算limits並取得新 authorization。

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

- E2 run/package/publication/current-lineage-head/decision/recommendation identity。
- eligibility high-water-mark progression。
- account snapshot與reconciliation identity。
- authorization、authorization-use、approver與policy identity。
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
- `submit_order`只接受persisted、authorized intent、valid authorization-use claim與stable client ID。
- Adapter不決定strategy、quantity、approval、retry、current eligibility head或kill-switch policy。

## 18. Restart recovery

任何 live-capable process在接受新intent前必須：

1. 取得account-scoped durable lease。
2. load eligibility high-water marks、所有nonterminal submission、unknown state、authorization-use claims與last audit anchor；immutable approval facts只讀取，不靠 mutation 推斷是否已使用。
3. 重新解析 configured evidence scope 的 unique current eligibility heads，要求不得低於 durable high-water marks，且任何 active live lineage 仍為 `ACTIVE`。
4. 由stable client/broker IDs查詢broker。
5. 取得fresh account/positions/open orders/fills snapshot。
6. deterministic reconcile每個record與aggregate account state。
7. append recovery audit並persist新state version。
8. 只有所有blocking discrepancies解除後才開放新authorization。

Crash windows必須以failure-injection tests覆蓋：intent persist前、authorization-use claim前後、`SUBMITTING` persist後/SDK call前、SDK call後/ack persist前、partial fill persist中與cancel/replace中。

特別的 anti-rollback regression：先接受 lineage `ACTIVE@N`，再出現其 strict extension `PAUSED@N+1` 或 `REVOKED@N+1`；process restart後即使 caller 指定舊 `ACTIVE@N` run，也必須因 current-head/high-water-mark contract 被拒絕。

In-memory-only idempotency、pending order、eligibility head、authorization use或audit不接受。

## 19. Architecture decisions settled by this plan

1. **Mandatory Phase 56.4 identity**：fresh exact E2 inspection，加上run ID、canonical Publication Index SHA-256、publication/activation/qualification/strategy/eligibility/policy/ledger/recommendation identities、qualified-symbol membership，且 candidate 必須是 configured scope 中唯一 current lineage head。
2. **Eligibility anti-rollback**：同 activation/strategy/policy lineage 只接受 ledger exact append-only prefix progression；fork/equal-progression conflict fail closed；broker durable high-water mark禁止 restart/caller 選舊 run 造成 rollback；pre-submit 必須重解 current head。
3. **Broker data before authorization**：capabilities、account/environment、cash/buying power/equity/currency、positions、open orders、unresolved submissions、permissions與freshness。
4. **Blocking discrepancies**：任何identity、eligibility rollback/fork、position/order/submission、cash/currency、capability、session、limit、kill-switch、persistence/audit或unknown-state mismatch。
5. **Stable client order identity**：`broker_order_intent_key_v1` canonical JSON SHA-256；provider encoding必須persistent、collision-checked、queryable。
6. **Retry safety**：bounded read-only retry可接受；mutating timeout先unknown再reconcile，禁止blind resubmit。
7. **Partial fills**：unique executions增量記帳，remaining quantity嚴格推導，risk/audit立即更新，cancel/replace保留economic lineage。
8. **Restart-persistent state**：source/current-head/high-water-mark identity、policy/snapshot/reconciliation、authorization-use claim、intent/idempotency mapping、submission lifecycle、fills、daily limits、kill switch與audit anchor。
9. **Human approval**：reconciliation後建立short-lived immutable、account/source/head/symbol/side/quantity/notional-bounded authorization；approval facts不含mutable consumption state；one-time use由durable unique `BrokerAuthorizationUseRecord` 表達。
10. **Mandatory first-live limits**：order、account exposure、per-symbol、open orders、daily notional、reliable daily loss與very-small allocation；default zero。
11. **Secret exclusion**：external secret provider、domain完全無secret、adapter allowlist redaction、fake-only tests與secret scan。
12. **Kill-switch meaning**：stop-new、cancel-open、liquidate三個獨立scope；unknown fail closed；第一版不自動liquidate。
13. **Audit trust**：application append-only/hash chain不是tamper-proof；live claim需要external signed/WORM anchor。
14. **Broker-independent vs specific**：models、eligibility lineage/high-water mark、policy、state machine、idempotency、reconciliation、audit與approval/use-record為broker-independent；SDK mapping、capabilities、calendar provider與secret acquisition留在adapter。
15. **Evidence before live pilot**：完成56.5A–E review/CI/sandbox/failure injection/recovery/security/audit/operations evidence後，仍需單獨明確授權56.5F。

## 20. Dependency-ordered implementation backlog

本planning PR不建立follow-up implementation issues。只有本文件通過independent review後，才依下列順序建立各自scope與gate。

### 56.5A — Broker safety contracts and pure architecture

Scope：immutable broker-neutral models、strict serializers、forward-eligibility lineage/high-water-mark models與pure append-only-prefix comparator、immutable authorization + separate authorization-use model、state transition table、stable intent-key builder、pure reconciliation/limit evaluators、calendar/adapter protocols。不得加入broker SDK或I/O side effect。

Exit evidence：model/adversarial tests、canonical serialization、transition property tests、source identity tests、lineage fork/equal-progression conflict tests、old `ACTIVE` vs newer `PAUSED/REVOKED` anti-rollback tests、authorization/use-record immutability tests、no-secret/no-SDK audit、independent review。

### 56.5B — Read-only broker account adapter and reconciliation

Depends on：56.5A。

Scope：選定sandbox/test environment後的read-only adapter、capability discovery、account/position/open-order snapshots與deterministic reconciliation。不得submit/cancel order。

Exit evidence：contract tests、stale/missing/duplicate data fail-closed tests、account/environment mismatch tests、recorded fake responses、no real credentials inrepository。

### 56.5C — Persistent idempotency and external audit foundation

Depends on：56.5A；可與56.5B在不衝突scope下開發，但56.5D同時依賴B與C。

Scope：durable account-scoped transaction store、eligibility high-water marks、unique intent keys、atomic authorization-use claims、submission lifecycle persistence、restart recovery skeleton、append-only audit與external anchor selection。仍不得broker mutation。

Exit evidence：concurrency tests、two-process authorization-use race tests、eligibility rollback/fork persistence tests、crash-window failure injection、migration/backup/restore、audit verification、secret redaction與operator recovery runbook。

### 56.5D — Broker sandbox/test-environment submission boundary

Depends on：56.5B、56.5C。

Scope：只在broker官方sandbox/test environment實作submit/cancel adapter、partial fill、timeout/unknown/reconciliation與cancel/replace。Production/live endpoint hard-disabled。

Exit evidence：duplicate-event、lost-ack、timeout、partial-fill、restart、session rollover、kill-switch、current-head rollback與adapter capability tests；sandbox account reconciliation drill。

### 56.5E — Human approval and live safety gate integration

Depends on：56.5D。

Scope：short-lived immutable approval workflow、durable one-time use claim、versioned live safety policy、operator identity/audit、kill-switch scopes、authorization-time + pre-submit current-head recheck與live endpoint deny-by-default integration。完成此階段仍不授權真實下單。

Exit evidence：approval expiry/replay tests、old `ACTIVE` superseded by `PAUSED/REVOKED` tests、head-change-between-approval-and-submit tests、zero-default limits、two-process race tests、secret/audit review、operator cancel/recovery tabletop、independent security/safety review。

### 56.5F — Extremely bounded live pilot

Depends on：56.5E，且必須另有explicit human/business/security authorization。

Scope不得由本文件預先授權。提案至少要指定broker/account、極小capital ceiling、symbols、side/order type、session、supervision、rollback、incident ownership與time-bounded authorization。

Go/no-go evidence：

- 56.5A–E exact-head independent reviews與CI全綠。
- Sandbox duplicate-prevention、eligibility anti-rollback、partial-fill、timeout、restart與reconciliation drills通過。
- External audit anchor可驗證，secret scanning/redaction通過。
- Production account read-only reconciliation連續成功且無unresolved discrepancy。
- Calendar/capability/kill-switch/operator runbook演練完成。
- Named human approver與incident responder在線監督。
- Separate issue明確授權一次、限時、極小額pilot；未授權即no-go。

## 21. Review and validation checklist

Planning review必須拒絕任何：

- 把`ACTIVE`視為充分live authorization的路徑。
- 只 fresh-validate caller 指定舊 `ACTIVE` run，而不解析 current lineage head／high-water mark 的路徑。
- newer `PAUSED`/`REVOKED` 出現後仍允許舊 `ACTIVE` authorization，或以 `created_at`／mtime 猜 fork winner。
- reconciliation/approval/persistence之前的submission。
- 把 immutable `BrokerExecutionAuthorization` 當成可 mutation 的 consumption state；one-time use 必須由獨立 durable unique claim 表達。
- timeout後blind duplicate submission。
- in-memory-only idempotency、authorization-use、eligibility high-water mark或restart recovery。
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
2. Phase 56.4 E2 trust boundary、per-run validation limitation、current eligibility anti-rollback/high-water-mark contract與unsigned limitation明確。
3. Reconciliation、idempotency、partial fills、retry、session、secrets、external audit、immutable human approval + separate one-time use、limits、kill switch與restart contracts全數凍結。
4. 56.5A–F dependency graph與各階段gate完成review。
5. Independent Review通過planning exact HEAD。
6. CI、full suite、lint與package smoke綠燈。
7. Repository仍無broker SDK、credentials或live execution path。
8. 後續production work保持separately gated並需要explicit authorization。