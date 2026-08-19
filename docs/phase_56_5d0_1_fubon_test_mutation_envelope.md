# Phase 56.5D0.1 — Fubon TEST mutation envelope

Reviewed result: `BLOCKED`.

Independent review found that the repository has neither a sealed official provider-read implementation capable of issuing non-forgeable order observations nor a Phase 56.5C mapping path for a non-promotable TEST canonical identity. The gate therefore blocks rather than accepting caller facts, creating a live-capable intent, or weakening Phase C recovery. It does not authorize, implement, or expose a Fubon SDK mutation, an order side effect, a live endpoint, credentials, a live CLI/GUI, or an unattended retry.

## Non-promotable contract

The `broker-test-mutation-v1` artifacts are a separate type and JSON namespace from `BrokerAccountSnapshot` and `BrokerExecutionAuthorization` v1. The live serializer rejects every TEST artifact, the TEST serializer rejects every live artifact, and there is no conversion or promotion helper. The existing live-capable types and `SQLiteBrokerSafetyStore.commit_pre_submit()` are unchanged.

The TEST lifecycle is a separately versioned SQLite sidecar and does not migrate the live-capable schema. It has no lease table and no provider-ID table. Its account scope is pinned to the exact Phase C store identity, every write checks the current unexpired Phase C lease/fencing token, and a short-tag reference is accepted only when the exact canonical mapping already exists in Phase C durable state.

- immutable economic intent, idempotency key, and full `twst1-<64hex>` identity;
- a store-issued, account/envelope/policy/date-bound, expiring, one-shot operator opt-in;
- durable Phase C short-tag mapping under the current fence before pre-submit;
- one-shot opt-in and authorization use;
- atomic high-water, authorization use, `SUBMITTING`, audit, and pre-submit commit;
- at most one active TEST order and one unresolved TEST submission;
- restart recovery that cross-links opt-in, authorization, use, provider binding, pre-submit commit, first history, current state, contiguous later history, audit, and high-water state;
- no retry transition.

The fixed envelope is exact Fubon SANDBOX at `wss://neoapitest.fbs.com.tw/TASP/XCPXWS`, Taiwan securities, cash stock, BUY-only, one 1,000-share common lot, LIMIT, DAY/ROD. Margin, short, SBL, day trade, odd lot, SELL, live endpoint selection, and unattended retry are forbidden.

The numeric caps are `SYNTHETIC_SANDBOX_HARNESS_ONLY`. They contain a TEST command; they are not cash, buying power, equity, a fee/tax estimate, trading permission, portfolio exposure, or live capital authority.

## D0 blocker classification

| D0 blocker | D0.1 classification | TEST-only rule |
|---|---|---|
| Account capital authority | `REPLACED_BY_TEST_ONLY_FAIL_CLOSED_RULE` | Synthetic command-notional cap with no capital claim |
| Position valuation/exposure authority | `REQUIRED_ONLY_FOR_LIVE_CAPABLE_AUTHORIZATION` | BUY-only, one common lot, no portfolio-exposure claim |
| Trading-permission proof | `REPLACED_BY_TEST_ONLY_FAIL_CLOSED_RULE` | Exact official TEST provenance plus explicit expiring one-shot operator opt-in |
| Fee/tax authority | `REQUIRED_ONLY_FOR_LIVE_CAPABLE_AUTHORIZATION` | Synthetic command cap is not a fee or capital calculation |
| Client correlation/lost-ACK safety | `REQUIRED_BEFORE_ANY_TEST_MUTATION` | Blocked until a sealed provider-read issuer and non-promotable Phase C mapping path exist |
| Exact session proof | `REPLACED_BY_TEST_ONLY_FAIL_CLOSED_RULE` | Same-date expiring operator opt-in; provider rejection fails closed and proves no market-session fact |

All six blockers remain blocking for the live-capable D0 contract.

## Correlation and lost ACK

Fubon `user_def` is only the deterministic ten-character correlation tag. Durable state always retains the full canonical identity. Both provider observations and validated matches require private reviewed-boundary authority. The current repository has no sealed official provider-read implementation, so it exposes no observation issuer and cannot produce `MATCHED`. A future reviewed boundary must check the durable tag binding and exact account, date, symbol, side, quantity, order type, time-in-force, price, endpoint, and environment facts before it can issue evidence; arbitrary caller-created records cannot do so.

- `MATCHED` records the provider ID on the existing durable attempt for reconciliation.
- `NO_MATCH` becomes `RECONCILIATION_REQUIRED`.
- `AMBIGUOUS` becomes `UNKNOWN_SUBMISSION_STATE`.
- none creates a retry path.

## Official review sources

- [Fubon Neo API welcome / TEST environment](https://www.fbs.com.tw/TradeAPI/docs/welcome/)
- [Fubon Neo TEST WebSocket endpoint](https://www.fbs.com.tw/TradeAPI/docs/trading/guide/advance/ping_pong/)
- [Fubon securities order-result fields](https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/trade/GetOrderResults/)
- [Fubon SDK v2.2.8 and user_def constraints](https://www.fbs.com.tw/TradeAPI/docs/download/download-sdk/)
- [Fubon TEST order-command and report testing announcement](https://www.fbs.com.tw/wcm/new_web/trade/trade_20250320_458309.html)

Normal tests use only sanitized, deterministic values and perform no network or broker I/O.
