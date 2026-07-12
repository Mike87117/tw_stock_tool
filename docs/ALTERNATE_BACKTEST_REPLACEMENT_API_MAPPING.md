# Alternate Backtest Replacement API Mapping

## A. Mapping outcome

**PARTIAL_CONCEPTUAL_MAPPING_NO_DROP_IN_REPLACEMENT**. Canonical APIs cover related concepts, but strategy interfaces, constructors, execution semantics, result schemas, and artifact boundaries differ. Direct redirect is unsafe. A6 authorizes no adapter or migration. A5 policy remains **RETAIN_WITHOUT_DEPRECATION**.

## B. Scope and mapping classifications

`EXACT_MAPPING` preserves shape; `RENAMED_EQUIVALENT` changes names; `PARTIAL_MAPPING` maps some fields; `CONCEPTUAL_MAPPING_ONLY` relates concepts; `NO_CANONICAL_EQUIVALENT` has no class/function; `UNSUPPORTED_INTEGRATION` rejects cross-use; `SEMANTICALLY_INCOMPATIBLE` changes behavior; `REQUIRES_EXPLICIT_ADAPTER` needs designed bridging. API shape, call shape, fields, units, behavior, lifecycle, artifact compatibility, drop-in replacement, adapter, and silent redirect are separate. Similar names do not prove equivalence.

## C. Top-level API replacement matrix

| Alternate symbol | Alternate import | Closest canonical API | Classification | Drop-in | Primary incompatibility | Artifact compatibility | Required future work |
|---|---|---|---|---|---|---|---|
| BacktestEngine | tw_stock_tool.backtest.engine | backtesting.backtest.run_backtest_result | REQUIRES_EXPLICIT_ADAPTER | No | class/state versus function/signals | no | adapter design |
| alternate BacktestResult | tw_stock_tool.backtest.engine | backtesting.results.BacktestResult | SEMANTICALLY_INCOMPATIBLE | No | fields, units, lifecycle | rejected | field policy |
| SignalStrategy | tw_stock_tool.backtest.engine | strategy functions and signal DataFrame | CONCEPTUAL_MAPPING_ONLY | No | object protocol | no | strategy bridge |
| BaseStrategy | tw_stock_tool.strategies.base | backtesting.strategies functions | NO_CANONICAL_EQUIVALENT | No | no canonical base class | no | API decision |

## D. Construction and invocation mapping

| Alternate operation | Canonical target | Classification | Conversion | Semantic risk | Notes |
|---|---|---|---|---|---|
| price_df | df | EXACT_MAPPING | none | low | both DataFrame inputs |
| strategy | standardized signal DataFrame | REQUIRES_EXPLICIT_ADAPTER | strategy bridge | high | canonical engine does not accept object |
| params | strategy/config inputs | PARTIAL_MAPPING | preprocessing | medium | ownership differs |
| initial_cash | initial_capital | RENAMED_EQUIVALENT | rename | medium | formulas differ |
| commission | fee_rate | PARTIAL_MAPPING | formula verification | high | not automatically exact |
| tax | tax_rate | PARTIAL_MAPPING | exit-cost verification | high | semantics differ |
| slippage | none | NO_CANONICAL_EQUIVALENT | policy required | high | no direct canonical argument |
| .run() | run_backtest_result() | RENAMED_EQUIVALENT | call-site change | medium | no alias |
| constructor validation | function validation | PARTIAL_MAPPING | explicit rules | high | errors differ |
| signal validation | standardized signals | PARTIAL_MAPPING | bridge validation | high | object method absent |
| result return | canonical BacktestResult | SEMANTICALLY_INCOMPATIBLE | result conversion | high | schemas differ |

## E. Strategy-interface mapping

| Alternate concept | Canonical relation | Classification | Required bridge |
|---|---|---|---|
| SignalStrategy.name | registry key/metadata | CONCEPTUAL_MAPPING_ONLY | naming policy |
| generate_signals(df, params) | strategy function returning DataFrame | PARTIAL_MAPPING | invocation bridge |
| validate_signals | signal normalization/validation helpers | NO_CANONICAL_EQUIVALENT | validation design |
| BaseStrategy inheritance | no canonical inheritance contract | NO_CANONICAL_EQUIVALENT | API design |

Canonical strategies are function-based; no canonical base class exists. Any bridge is adapter territory and not authorized.

## F. Input-data and signal mapping

| Concern | Alternate | Canonical | Status | Transformation | Risk |
|---|---|---|---|---|---|
| Open/Close | required | required | EXACT_MAPPING | none | low |
| Signal | absent/strategy output | accepted legacy route | PARTIAL_MAPPING | normalize | medium |
| entry_signal/exit_signal | strategy output, bool | standardized DataFrame | PARTIAL_MAPPING | validate | medium |
| index/length | strategy frame checks | canonical frame checks | PARTIAL_MAPPING | enforce | high |
| params | strategy-owned | call/config-owned | CONCEPTUAL_MAPPING_ONLY | bridge | medium |

## G. Execution-semantics mapping

| Area | Alternate | Canonical | Classification | Adapter possibility | Redirect risk |
|---|---|---|---|---|---|
| Signal timing | prior signal, next open | prior signal, next open | PARTIAL_MAPPING | possible | medium |
| Invalid next open | NaN may propagate | skips invalid execution | KNOWN_DEFECT_NOT_GUARANTEED | design required | high |
| Entry sizing | fractional all-in | integer affordable | SEMANTICALLY_INCOMPATIBLE | policy required | high |
| Position size | absent | supported | NO_FEATURE_EQUIVALENT | no direct | high |
| Costs/tax | commission/tax/slippage | fee/tax, no slippage arg | PARTIAL_MAPPING | formula design | high |
| Stops/take/max hold | absent | canonical-only | NO_FEATURE_EQUIVALENT | no direct | medium |
| EOD | mark-to-market | forced SELL_EOD | SEMANTICALLY_INCOMPATIBLE | policy required | high |
| Final valuation | open mark | close when possible | SEMANTICALLY_INCOMPATIBLE | policy required | high |
| Initial cash validation | positive | canonical rules | PARTIAL_MAPPING | explicit rules | medium |

## H. Result-model field mapping

| Alternate field | Canonical field | Classification | Unit conversion | Information loss |
|---|---|---|---|---|
| total_return | total_return_pct | RENAMED_EQUIVALENT | ratio to percent | possible |
| max_drawdown | max_drawdown_pct | PARTIAL_MAPPING | unit verification | possible |
| win_rate | win_rate_pct | PARTIAL_MAPPING | unit verification | possible |
| trade_count | trade_count | RENAMED_EQUIVALENT | none | EOD may differ |
| final_equity | final_capital | PARTIAL_MAPPING | lifecycle-dependent | possible |
| trade_log | trades | SEMANTICALLY_INCOMPATIBLE | schema mapping | columns lost |
| none | equity_curve, CAGR, Sharpe, Sortino, metadata | NO_CANONICAL_EQUIVALENT | unsafe derivation | unavailable |

Most canonical metrics cannot safely be recovered from the alternate result alone.

## I. Trade-log and equity mapping

| Alternate column | Canonical column | Mapping |
|---|---|---|
| Entry Date | Entry Date | EXACT_MAPPING |
| Exit Date | Exit Date | EXACT_MAPPING |
| Entry Price | Entry Price | EXACT_MAPPING |
| Exit Price | Exit Price | EXACT_MAPPING |
| Shares | Shares | SEMANTICALLY_INCOMPATIBLE when fractional |
| PnL | PnL | PARTIAL_MAPPING |
| PnL % | PnL_pct | unit/name verification required |
| none | Hold Days, Exit Reason, Type | NO_CANONICAL_EQUIVALENT |

A lossless adapter needs original prices/signals, costs, strategy, metadata, and equity rules; result-only conversion is unsafe.

## J. Serialization, artifact, and converter mapping

| Boundary | Accepted type | Alternate compatibility | Failure/mapping | Artifact risk | A6 authorization |
|---|---|---|---|---|---|
| serialize/deserialize | canonical BacktestResult | rejected | strict type boundary | high | none |
| JSON file reader/writer | canonical result | rejected | canonical schema | high | none |
| report builders | canonical/legacy canonical outputs | not alternate | consumer fields differ | high | none |
| paper-trading converter | canonical BacktestResult | rejected | missing fields/quantities | high | none |

Casting or aliasing cannot fill missing fields; fabricated metrics are prohibited.

## K. Adapter and redirect feasibility

| Option | Technically possible | Lossless | Semantic preservation | Required inputs | Main risk | A6 authorization |
|---|---|---|---|---|---|---|
| Direct module/class alias | yes | no | no | none | silent behavior change | no |
| Function redirect | yes | no | no | call rewrite | lifecycle change | no |
| Strategy bridge | yes | partial | uncertain | object/signals/params | interface drift | no |
| Input bridge | yes | partial | uncertain | original DataFrame | signal/cost drift | no |
| Result-only adapter | limited | no | no | original inputs missing | fabricated data | no |
| Full recomputation | possible | no | canonical semantics only | all original inputs | changes results | no |
| Dual-result facade | possible | no | complex | both models | maintenance | no |
| Serializer-only adapter | possible | no | no | missing fields | artifact corruption | no |
| Converter adapter | possible | no | no | integer/metadata policy | paper semantics | no |

Feasibility outcome: **EXPLICIT_ADAPTER_DESIGN_REQUIRED_BEFORE_ANY_MIGRATION**. No option is authorized.

## L. Migration evidence and implementation entry criteria

Require target behavior, parameter/strategy/signal/cost/slippage/EOD/invalid-open/result/trade/equity/metadata policies, artifact/converter tests, golden fixtures, external risk, rollback, version/communication plan, and dedicated production approval. **No adapter or migration implementation may begin while these criteria are incomplete.**

## M. Recommended next phase and non-goals

Recommend **Alternate Backtest Adapter Design Decision**. A6 does not add adapters, redirects, aliases, migrations, warnings, fixes, serializer/converter changes, schema changes, consumer migration, removals, version changes, merged PRs, or Phase A7.
