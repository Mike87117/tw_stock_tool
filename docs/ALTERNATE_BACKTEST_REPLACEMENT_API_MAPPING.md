# Alternate Backtest Replacement API Mapping

## A. Mapping outcome
**PARTIAL_CONCEPTUAL_MAPPING_NO_DROP_IN_REPLACEMENT**. Canonical APIs cover related concepts, but strategy interfaces, constructors, execution semantics, result schemas, and artifact boundaries differ. Direct redirect is unsafe. A6 authorizes no adapter or migration. Retention remains **RETAIN_WITHOUT_DEPRECATION**.

## B. Scope and mapping classifications

`EXACT_MAPPING`, `RENAMED_EQUIVALENT`, `PARTIAL_MAPPING`, `CONCEPTUAL_MAPPING_ONLY`, `NO_CANONICAL_EQUIVALENT`, `UNSUPPORTED_INTEGRATION`, `SEMANTICALLY_INCOMPATIBLE`, and `REQUIRES_EXPLICIT_ADAPTER` describe shape, fields, units, behavior, lifecycle, artifacts, and feasibility separately. Similar names do not prove equivalence; a theoretical adapter is not authorization.

## C. Top-level API replacement matrix

| Alternate symbol | Closest canonical API | Classification | Drop-in | Incompatibility |
|---|---|---|---|---|
| BacktestEngine | backtesting.backtest.run_backtest_result | REQUIRES_EXPLICIT_ADAPTER | No | class/state versus function/signals |
| alternate BacktestResult | backtesting.results.BacktestResult | SEMANTICALLY_INCOMPATIBLE | No | fields, units, lifecycle |
| SignalStrategy | strategy functions and signal DataFrame | CONCEPTUAL_MAPPING_ONLY | No | object protocol |
| BaseStrategy | backtesting.strategies functions | NO_CANONICAL_EQUIVALENT | No | no canonical base class |

## D. Construction and invocation mapping

| Alternate operation | Canonical target | Classification | Conversion | Semantic risk |
|---|---|---|---|---|
| price_df | df | PARTIAL_MAPPING | signal preparation | high |
| strategy | standardized signal DataFrame | REQUIRES_EXPLICIT_ADAPTER | strategy bridge | high |
| params | strategy/config inputs | PARTIAL_MAPPING | preprocessing | medium |
| initial_cash | initial_capital | RENAMED_EQUIVALENT | rename | medium |
| commission | fee_rate | PARTIAL_MAPPING | formula verification | high |
| tax | tax_rate | PARTIAL_MAPPING | exit-cost verification | high |
| slippage | none | NO_CANONICAL_EQUIVALENT | policy | high |
| .run() | run_backtest_result() | REQUIRES_EXPLICIT_ADAPTER | call/state/result bridge | high |
| validation | canonical validation | PARTIAL_MAPPING | explicit rules | high |

## E. Strategy-interface mapping

| Alternate concern | Canonical relation | Classification | Bridge required |
|---|---|---|---|
| SignalStrategy.name | registry key/metadata | CONCEPTUAL_MAPPING_ONLY | naming policy |
| generate_signals | strategy function | PARTIAL_MAPPING | invocation bridge |
| validate_signals | signal helpers | NO_CANONICAL_EQUIVALENT | validation design |
| BaseStrategy inheritance | no canonical base class | NO_CANONICAL_EQUIVALENT | API design |

Canonical strategies are function-based; no canonical inheritance contract exists.

## F. Input-data and signal mapping

| Concern | Alternate requirement/behavior | Canonical requirement/behavior | Mapping classification | Transformation required | Validation/failure risk |
|---|---|---|---|---|---|
| Open | price input | required price input | EXACT_MAPPING | none | low |
| Close | price input | required price input | EXACT_MAPPING | none | low |
| legacy Signal | not strategy output | accepted legacy route | PARTIAL_MAPPING | normalize | medium |
| entry_signal | generated bool column | standardized bool column | PARTIAL_MAPPING | validate | medium |
| exit_signal | generated bool column | standardized bool column | PARTIAL_MAPPING | validate | medium |
| DataFrame index equality | strategy frame check | canonical frame check | PARTIAL_MAPPING | enforce | high |
| DataFrame length equality | strategy frame check | canonical frame check | PARTIAL_MAPPING | enforce | high |
| Copying/mutation | engine copies input | canonical execution normalizes | PARTIAL_MAPPING | ownership policy | medium |
| Legacy normalization | no direct route | ensure_standard_signals | CONCEPTUAL_MAPPING_ONLY | signal conversion | high |
| Standard normalization | strategy output | canonical helper | PARTIAL_MAPPING | helper call | high |
| Strategy-added columns | strategy-owned | preserved in signal frame | CONCEPTUAL_MAPPING_ONLY | bridge | medium |
| Params ownership | object call parameter | canonical call/config | PARTIAL_MAPPING | preprocessing | medium |

Alternate generates signals through a strategy object; canonical accepts precomputed standardized or legacy signals. Alternate validates bool/length/index through its strategy; canonical validates its own normalized frame.

## G. Execution-semantics mapping

| Semantic area | Alternate behavior | Canonical behavior | Compatibility classification | Adapter possibility | Silent redirect risk |
|---|---|---|---|---|---|
| Signal timing | prior signal | prior signal | PARTIAL_MAPPING | possible | medium |
| Next-open execution | next open | next open | PARTIAL_MAPPING | possible | medium |
| Invalid next-open | NaN may propagate | skip invalid | KNOWN_DEFECT_NOT_GUARANTEED | design | high |
| Entry sizing | fractional all-in | integer affordable | SEMANTICALLY_INCOMPATIBLE | policy | high |
| Fractional shares | yes | no | CHARACTERIZED_DIFFERENCE | policy | high |
| Position-size control | absent | supported | NO_FEATURE_EQUIVALENT | no direct | high |
| Commission/fee | commission | fee_rate | PARTIAL_MAPPING | formulas | high |
| Tax | exit tax | exit tax | PARTIAL_MAPPING | formulas | medium |
| Slippage | explicit | no equivalent argument | NO_FEATURE_EQUIVALENT | policy | high |
| Stop loss | absent | supported | NO_FEATURE_EQUIVALENT | no direct | medium |
| Take profit | absent | supported | NO_FEATURE_EQUIVALENT | no direct | medium |
| Maximum hold days | absent | supported | NO_FEATURE_EQUIVALENT | no direct | medium |
| Exit signals | strategy signal | standardized signal | PARTIAL_MAPPING | bridge | medium |
| End-of-data | mark-to-market | forced SELL_EOD | SEMANTICALLY_INCOMPATIBLE | policy | high |
| Open-position valuation | final mark | final close/close trade | SEMANTICALLY_INCOMPATIBLE | policy | high |
| Empty-trade behavior | compact empty log | canonical metrics/empty trades | PARTIAL_MAPPING | result policy | medium |
| Initial-capital validation | positive cash | canonical validation | PARTIAL_MAPPING | explicit rules | medium |

Direct redirect can alter trade count, quantities, exit dates, PnL, final equity/capital, and reported metrics.

## H. Result-model field mapping

| Alternate field | Canonical field | Mapping classification | Unit conversion | Information loss | Derivable | Required assumptions |
|---|---|---|---|---|---|---|
| total_return | total_return_pct | RENAMED_EQUIVALENT | ratio to percent | no | yes | scale |
| max_drawdown | max_drawdown_pct | PARTIAL_MAPPING | verify units | possible | assumptions | curve |
| win_rate | win_rate_pct | PARTIAL_MAPPING | ratio to percent | possible | yes | lifecycle |
| trade_count | trade_count | PARTIAL_MAPPING | none | possible | yes | EOD policy |
| final_equity | final_capital | PARTIAL_MAPPING | none | possible | assumptions | lifecycle |
| trade_log | trades | SEMANTICALLY_INCOMPATIBLE | schema | columns | partial | original inputs |

Canonical-only inventory: `initial_capital` DERIVABLE_WITH_ASSUMPTIONS; `buy_hold_return_pct` DERIVABLE_ONLY_WITH_ORIGINAL_INPUT; `cagr_pct` NO_SAFE_DERIVATION; `exposure_pct` NO_SAFE_DERIVATION; `profit_factor` NOT_AVAILABLE_FROM_ALTERNATE_RESULT; `best_trade_pct` DERIVABLE_WITH_ASSUMPTIONS; `worst_trade_pct` DERIVABLE_WITH_ASSUMPTIONS; `avg_hold_days` NO_SAFE_DERIVATION; `sharpe_ratio` NO_SAFE_DERIVATION; `sortino_ratio` NO_SAFE_DERIVATION; `avg_profit` DERIVABLE_WITH_ASSUMPTIONS; `avg_loss` DERIVABLE_WITH_ASSUMPTIONS; `equity_curve` NO_SAFE_DERIVATION; `stock` NOT_AVAILABLE_FROM_ALTERNATE_RESULT; `strategy` NOT_AVAILABLE_FROM_ALTERNATE_RESULT; `parameters` NOT_AVAILABLE_FROM_ALTERNATE_RESULT; `start_date` DERIVABLE_WITH_ASSUMPTIONS; `end_date` DERIVABLE_WITH_ASSUMPTIONS.

## I. Trade-log and equity mapping

| Trade column | Canonical mapping | Classification |
|---|---|---|
| Entry Date | Entry Date | PARTIAL_MAPPING |
| Exit Date | Exit Date | PARTIAL_MAPPING |
| Entry Price | Entry Price | PARTIAL_MAPPING |
| Exit Price | Exit Price | PARTIAL_MAPPING |
| Shares | Shares | SEMANTICALLY_INCOMPATIBLE |
| PnL | PnL | PARTIAL_MAPPING |
| PnL % | PnL_pct | PARTIAL_MAPPING |
| Hold Days | absent alternate | NO_CANONICAL_EQUIVALENT |
| Exit Reason | absent alternate | NO_CANONICAL_EQUIVALENT |
| Type | absent alternate | NO_CANONICAL_EQUIVALENT |

| Additional input | Why required | Available from alternate result | Lossless mapping | Recomputable | Risk if absent |
|---|---|---|---|---|---|
| Original price DataFrame | fills/equity | no | required | yes | high |
| Original signal DataFrame | lifecycle | no | required | yes | high |
| Initial cash | capital | partial | required | no | high |
| Commission | costs | partial | required | yes | high |
| Tax | costs | partial | required | yes | high |
| Slippage | fills | partial | required | yes | high |
| Strategy name | metadata | no | required | no | medium |
| Parameters | metadata | no | required | no | medium |
| Stock symbol | metadata | no | required | no | medium |
| Start date | metadata | partial | required | yes | medium |
| End date | metadata | partial | required | yes | medium |
| Equity curve or recomputation rules | metrics | no | required | yes | high |

**A lossless result-only adapter is not possible.**

## J. Serialization, artifact, and converter mapping

| Boundary | Accepted type/schema | Alternate compatibility | Failure mode | Mapping needed | Artifact risk | Authorized in A6 |
|---|---|---|---|---|---|---|
| serialize_backtest_result | canonical | rejected | type error | none | high | no |
| deserialize_backtest_result | canonical construction | no alternate | canonical object | none | high | no |
| JSON export | canonical | rejected | serializer error | none | high | no |
| JSON load | canonical schema | no alternate | canonical result | none | high | no |
| file writer | canonical | rejected | type boundary | none | high | no |
| file reader | canonical | no alternate | schema boundary | none | high | no |
| report builders | canonical reports | no alternate | field mismatch | mapping | high | no |
| paper-trading converter | canonical | rejected | model error | mapping | high | no |
| downstream contracts | canonical consumers | alternate unsupported | contract break | migration | high | no |

Strict canonical checks reject alternate results; aliasing cannot provide missing fields; fabrication is prohibited.

## K. Adapter and redirect feasibility

| Option | Technically possible | Lossless | Semantic preservation | Required inputs | Artifact compatibility | Complexity | Main risk | A6 authorization |
|---|---|---|---|---|---|---|---|---|
| Direct module alias | yes | no | no | none | no | low | silent change | no |
| Direct class alias | yes | no | no | none | no | low | identity break | no |
| Engine redirect to function | yes | no | no | call changes | no | medium | lifecycle drift | no |
| Strategy-object bridge | possible | partial | uncertain | strategy/signals | partial | high | interface drift | no |
| Input DataFrame bridge | possible | partial | uncertain | inputs/signals | partial | medium | signal drift | no |
| Result-only adapter | limited | no | no | original inputs absent | no | medium | fabricated fields | no |
| Full recomputation adapter | possible | no | canonical only | all inputs | partial | high | semantics change | no |
| Dual-result facade | possible | no | complex | both models | partial | high | maintenance | no |
| Serializer-only adapter | possible | no | no | missing fields | no | medium | corrupt artifact | no |
| Converter adapter | possible | no | no | quantities/metadata | no | high | paper semantics | no |

Feasibility outcome: **EXPLICIT_ADAPTER_DESIGN_REQUIRED_BEFORE_ANY_MIGRATION**. No option is authorized.

## L. Migration evidence and implementation entry criteria

| Criterion | Current status | Evidence required | Blocking | Required phase |
|---|---|---|---|---|
| Confirmed migration target | incomplete | approved decision | yes | design |
| Alternate-versus-canonical semantic priority | incomplete | policy | yes | design |
| Parameter mapping specification | incomplete | formulas | yes | design |
| Strategy bridge specification | incomplete | API mapping | yes | design |
| Signal normalization specification | incomplete | fixtures | yes | design |
| Cost formula mapping | incomplete | golden cases | yes | design |
| Slippage policy | incomplete | policy | yes | design |
| Fractional-share policy | incomplete | policy | yes | design |
| EOD lifecycle policy | incomplete | policy | yes | design |
| Invalid-open policy | incomplete | policy | yes | design |
| Complete result-field policy | incomplete | field matrix | yes | design |
| Unit-conversion policy | incomplete | numeric cases | yes | design |
| Trade-schema policy | incomplete | schema tests | yes | design |
| Equity-curve policy | incomplete | curve fixtures | yes | design |
| Metadata policy | incomplete | consumer evidence | yes | design |
| Serialization impact assessment | incomplete | artifact tests | yes | design |
| Paper-trading converter impact assessment | incomplete | converter tests | yes | design |
| Golden characterization fixtures | present | maintenance | yes | test phase |
| Round-trip artifact tests | present | maintenance | yes | test phase |
| External-consumer risk assessment | incomplete | external evidence | yes | evidence phase |
| Rollback plan | incomplete | approved plan | yes | design |
| Version plan | incomplete | release policy | yes | design |
| User communication plan | incomplete | reviewed docs | yes | design |
| Dedicated production-phase approval | absent | explicit approval | yes | production phase |

**No adapter or migration implementation may begin while these criteria are incomplete.**

## M. Recommended next phase and non-goals

Recommend **Alternate Backtest Adapter Design Decision**. A6 does not add adapters, redirects, aliases, migrations, warnings, fixes, serializer/converter changes, schemas, consumer migration, removals, version changes, merged PRs, or Phase A7.
