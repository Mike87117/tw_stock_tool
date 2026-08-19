# Phase 56.5D0 — Fubon Neo TEST pre-mutation readiness

Reviewed: 2026-08-19

Reviewed baseline: `da9f29b77869ee8c8ebef65cbf8712ff09dbaa30`

Reviewed result: **BLOCKED**

This decision authorizes no broker mutation. It freezes the minimum candidate
profile and the complete prerequisites that a later review would have to prove
before Phase 56.5D may add any TEST mutation adapter.

## Existing path audit

The versioned machine-readable matrix is
`FUBON_NEO_D0_SAFETY_PATH_MATRIX`. The audit follows each fact through
`BrokerAccountSnapshot`, `evaluate_broker_preflight()`,
`evaluate_broker_limits()`, A4 authorization, the repeated authoritative
submission gate, and `SQLiteBrokerSafetyStore.commit_pre_submit()`.

| Fact | Existing v1 classification | Actual safety use |
| --- | --- | --- |
| `cash` | `UNUSED_IN_CURRENT_GATE` | Validated by the snapshot model but never used as BUY capital authority. |
| `buying_power` | `UNUSED_IN_CURRENT_GATE` | Structurally mandatory in v1, but no order-to-buying-power comparison exists. |
| `equity` | `UNUSED_IN_CURRENT_GATE` | Structurally mandatory in v1, but no percentage sizing or limit consumes it. |
| `positions.quantity` | `REQUIRED_FOR_SAFETY_DECISION` | Reconciliation and projected per-symbol quantity. |
| `positions.available_quantity` | `REQUIRED_FOR_SAFETY_DECISION` | Prevents an ordinary SELL from exceeding owned available quantity. |
| `positions.market_value` | `REQUIRED_FOR_SAFETY_DECISION` | Current account and symbol notional exposure. |
| open orders | `REQUIRED_FOR_SAFETY_DECISION` | Reconciliation, reserved notional/quantity, and simultaneous-order count. |
| capabilities | `REQUIRED_FOR_SAFETY_DECISION` | Market/currency/order support, fee support, and trading permission. |
| session | `REQUIRED_FOR_SAFETY_DECISION` | Exact market/date/permission/freshness at authorization and pre-submit. |
| reconciliation | `REQUIRED_FOR_SAFETY_DECISION` | Fresh matching no-finding result at authorization and pre-submit. |
| local reserved exposure | `REQUIRED_FOR_SAFETY_DECISION` | Includes unmatched orders and uncertain submissions; durable one-shot consumption. |
| daily submitted notional | `REQUIRED_FOR_SAFETY_DECISION` | Absolute daily cap including all reservations and the candidate. |
| daily loss | `REQUIRED_FOR_SAFETY_DECISION` | Mandatory and reliable whenever the absolute daily-loss cap is enabled. |
| fees/taxes | `REQUIRED_FOR_SAFETY_DECISION` | Added to order, account, symbol, daily, allocation, and authorization notionals. |

This exposes an under-constrained v1 capital path: the snapshot requires three
capital-looking values, while the safety gate consumes none of them as a BUY
availability bound. D0 does not relabel undocumented values or weaken the v1
artifact. A broker-neutral v2 is deferred because no complete conservative
capital authority can yet be proven. Existing v1 schemas and serialization
retain their exact meaning.

## Minimum candidate TEST profile

The frozen `FUBON_NEO_MINIMUM_TEST_PROFILE` is:

- exact official Fubon TEST endpoint and `SANDBOX` only;
- Taiwan securities, cash-stock only;
- long BUY or ordinary SELL within owned available quantity;
- common lot only;
- LIMIT + DAY only;
- margin, short, SBL, uncovered short, day trade, odd lot, unattended retry,
  and every live endpoint forbidden.

This profile is a description of the narrowest future candidate. It is not an
authorization and cannot bypass the D0 readiness result.

## Capital and equity decision

`bank_remain.balance` remains authoritative settled cash.
`bank_remain.available_balance` remains semantically unclassified and is not
renamed buying power. `query_settlement` rows do not prove whether every debit
or credit is already reflected in the balance, so combining them could double
count. Fees and taxes also lack reviewed conservative authority.

Consequently neither `PROVIDER_BUYING_POWER` nor
`CONSERVATIVE_SPENDABLE_CASH_LOWER_BOUND` is proven. The typed capital proof
records the incomplete obligations and returns `BLOCKED`. No equity is
synthesized. Although equity is not consumed by the current absolute-limit
calculations, v1 still requires it structurally; D0 does not relax that contract
just because Fubon lacks an authoritative securities-equity surface.

## Other prerequisite decisions

- Position/open-order reconciliation is proven only for the existing strict
  same-account, same-date cash/common-lot projection and Phase 56.5C local
  reservations.
- Position valuation is blocked. The mapper correctly retains
  `market_value=None` / `UNAVAILABLE`; cost and unrealized P/L are not current
  market-value authority.
- Trading permission is blocked. Login, an account object, endpoint reachability,
  method existence, or a prior order do not prove current permission for this
  profile.
- Fee/tax authority is blocked. Provider support stays `UNKNOWN`; a caller
  estimate cannot promote it.
- Exact session proof is blocked. No reviewed read-only source binds the TEST
  account to calendar/date, market state, submission permission, timezone TTL,
  and TEST-versus-live behavior together.

## Client identity and lost ACK

The canonical durable identity remains `twst1-<64 lowercase hex>`. Fubon's
`user_def` is only a custom field: current official SDK notes restrict it to ten
alphanumeric characters and state that invalid/long values may be modified
without preventing order submission. It therefore cannot be canonical identity.

`derive_fubon_provider_correlation_tag()` defines a deterministic versioned
ten-character tag. Before use, Phase 56.5C's durable provider-ID mapping must
bind that tag to the full canonical ID under the account fence; collision is a
hard failure. This local mechanism is proven, but provider scan/query
completeness is not. `get_order_results()` returns `user_def`, yet the official
contract does not establish an exact query-by-canonical-ID operation or prove
that a no-match result is conclusive after a lost ACK.

Therefore no match becomes `RECONCILIATION_REQUIRED`, ambiguity becomes
`UNKNOWN_SUBMISSION_STATE`, and neither outcome permits blind resubmission.
This preserves the Phase 56.5C one-shot, fencing, high-water, audit, and
idempotency boundaries.

## Official documentation rechecked

- [SDK downloads and `user_def` version notes](https://www.fbs.com.tw/TradeAPI/docs/download/download-sdk/)
- [Bank balance](https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/Balance/)
- [Settlement query](https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/QuerySettlement/)
- [Inventories](https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/Inventories/)
- [Unrealized P/L](https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/UnrealizedPnLDetail/)
- [Order results](https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/trade/GetOrderResults/)
- [Order error/status reference](https://www.fbs.com.tw/TradeAPI/docs/trading/guide/error-codes/)

The order-status reference directs timeout cases back to order-result status
queries; it does not make absence a safe retry signal.

## Unified result

Proven prerequisites are official TEST provenance, the pinned read-only
SDK/provider contract, strict supported position/open-order reconciliation,
Phase 56.5C durable one-shot pre-submit, and the absence of a live endpoint.

Canonical blockers are:

1. `ACCOUNT_CAPITAL_AUTHORITY_UNPROVEN`
2. `CLIENT_CORRELATION_QUERY_UNPROVEN`
3. `FEE_TAX_AUTHORITY_UNPROVEN`
4. `POSITION_VALUATION_AUTHORITY_UNPROVEN`
5. `SESSION_PROOF_UNPROVEN`
6. `TRADING_PERMISSION_UNPROVEN`

The exact reviewed outcome is **BLOCKED**. `read_account_snapshot()` continues
to fail closed through the #144 account-fact gate, and no caller value, fixture,
or environment flag can manufacture `READY_FOR_56_5D`.
