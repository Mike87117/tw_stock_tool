# Phase 56.5B2 — Fubon Neo securities account-fact readiness

Reviewed: 2026-08-19

Contract: `fubon-neo-securities-account-facts-v1`

Provider contract: `fubon-neo-2.2.8-test-readonly-v1`

SDK: `2.2.8`

Evidence digest: `f34931c057487b4571462826de1d569cefe65fb096a8066ac0a4a8bd595f754b`

## Reviewed result

`BLOCKED`

The current official Fubon Neo securities documentation does not establish an exact account-wide `buying_power` fact or a complete securities account `equity` fact. Phase 56.5D therefore remains blocked. This is a successful readiness-gate outcome and authorizes no broker mutation.

The existing boundary remains unchanged:

```text
bank_remain.balance           -> cash
bank_remain.available_balance -> unclassified_available_balance
```

`available_balance` is not relabeled as buying power, and equity is not synthesized.

## Official evidence matrix

| Provider observation | Product / scope | Candidate A2 fact | Classification | Reviewed reason |
|---|---|---|---|---|
| `accounting.bank_remain.balance` | securities / account | cash | `EXACT_AUTHORITATIVE` | The documented bank balance is the settled-cash observation already used by the strict adapter. |
| `accounting.bank_remain.available_balance` | securities / account | buying power | `UNCLASSIFIED` | The documentation does not establish equivalence to account-wide securities purchasing power or describe all open-order reservations. |
| `accounting.query_settlement.details[*]` | securities / account | buying power | `UNCLASSIFIED` | Dated receivable/payable rows do not define a complete purchasing-power identity and may overlap effects reflected in bank balance. |
| `accounting.inventories[*]` | securities / position | positions | `EXACT_AUTHORITATIVE` | The strict v1 projection accepts only same-account, same-date cash-stock common-lot records with exact quantity accounting. |
| `accounting.unrealized_gains_and_loses[*]` | securities / position | positions | `EXACT_AUTHORITATIVE` | The strict mapper reconciles these rows to inventory; cost and unrealized P/L are not promoted to account equity. |
| `accounting.realized_gains_and_loses[*]` | securities / position | equity | `UNCLASSIFIED` | Position-level realized P/L is not a complete account-equity field or identity. |
| `accounting.realized_gains_and_loses_summary[*]` | securities / position | equity | `UNCLASSIFIED` | A date-range P/L summary does not prove all account assets, liabilities, unsettled effects, and positions. |
| `accounting.maintenance` | securities / account and position | equity | `UNCLASSIFIED` | This additional official securities endpoint documents margin/short maintenance components, not a complete securities equity identity. |
| `stock.margin_quota(account, stock_no)` | securities / symbol | buying power | `UNCLASSIFIED` | Per-symbol financing and short quotas cannot establish account-wide buying power. |
| `stock.get_order_results(account)` | securities / order | open orders | `EXACT_AUTHORITATIVE` | The existing strict mapper retains supported nonterminal exposure and rejects ambiguous status histories. |
| `futopt_accounting.query_margin_equity` | futures/options / account | equity | `UNAVAILABLE` | The documented object belongs to futures/options accounting and is not authority for a securities account. |

Primary sources:

- <https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/Balance/>
- <https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/QuerySettlement/>
- <https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/Inventories/>
- <https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/UnrealizedPnLDetail/>
- <https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/RealizedPnLDetail/>
- <https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/RealizedPnLSum/>
- <https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/accountManagement/Maintenance/>
- <https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/trade/MarginQuota/>
- <https://www.fbs.com.tw/TradeAPI/docs/trading/library/python/trade/GetOrderResults/>
- <https://www.fbs.com.tw/TradeAPI/docs/trading-future/guide/account_example/>

## Mandatory fact result

| Mandatory fact | Result |
|---|---|
| cash | `EXACT_AUTHORITATIVE` |
| buying power | `UNCLASSIFIED` |
| equity | `UNAVAILABLE` |
| positions | `EXACT_AUTHORITATIVE` for the existing closed cash-stock/common-lot projection |
| open orders | `EXACT_AUTHORITATIVE` for the existing closed supported order projection |
| complete `BrokerAccountSnapshot` | `BLOCKED` |

Canonical blockers:

```text
BUYING_POWER_SEMANTICS_UNCLASSIFIED
EQUITY_UNAVAILABLE
ACCOUNT_FACTS_INCOMPLETE
COMPLETE_ACCOUNT_SNAPSHOT_UNPROVEN
```

No derived account fact is proposed in v1. Any future `DERIVED_AUTHORITATIVE` classification must include a typed proof that freezes every authoritative input, the complete accounting identity, same-account and same-currency scope, freshness and settlement handling, open-order exposure, instrument/lot modes, missing/duplicate/contradiction behavior, and non-overstatement of available capital.

## 56.5D gate

The pure `FubonNeo56_5DReadiness` gate currently records:

```text
official TEST provenance            PROVEN
reviewed SDK version                PROVEN
position/open-order reconciliation  PROVEN
complete BrokerAccountSnapshot      BLOCKED
provider account-fact readiness     BLOCKED
overall                             BLOCKED
```

`read_account_snapshot()` has no override and continues to fail closed. The new API is evidence/readiness only: it adds no order submission, cancellation, modification, batch operation, production endpoint, credentials, certificate handling, persistence, or network-dependent normal test.
