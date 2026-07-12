# Alternate Backtest Replacement API Mapping

## A. Mapping outcome
**PARTIAL_CONCEPTUAL_MAPPING_NO_DROP_IN_REPLACEMENT**. Canonical APIs cover related concepts, but strategy interfaces, constructors, execution semantics, result schemas, and artifact boundaries differ. Direct redirect is unsafe. A6 authorizes no adapter or migration. Retention remains **RETAIN_WITHOUT_DEPRECATION**.

## B. Scope and mapping classifications

`EXACT_MAPPING`, `RENAMED_EQUIVALENT`, `PARTIAL_MAPPING`, `CONCEPTUAL_MAPPING_ONLY`, `NO_CANONICAL_EQUIVALENT`, `UNSUPPORTED_INTEGRATION`, `SEMANTICALLY_INCOMPATIBLE`, and `REQUIRES_EXPLICIT_ADAPTER` describe shape, fields, units, behavior, lifecycle, artifacts, and feasibility separately. Similar names do not prove equivalence; a theoretical adapter is not authorization.

## C. Top-level API replacement matrix

| Alternate symbol | Alternate import | Closest canonical API | Mapping classification | Drop-in replacement | Primary incompatibility | Artifact compatibility | Required future work |
|---|---|---|---|---|---|---|---|
| BacktestEngine | `tw_stock_tool.backtest.engine.BacktestEngine` | `tw_stock_tool.backtesting.backtest.run_backtest_result` | REQUIRES_EXPLICIT_ADAPTER | No | class/state versus function/signals | incompatible | adapter design |
| alternate BacktestResult | `tw_stock_tool.backtest.engine.BacktestResult` | `tw_stock_tool.backtesting.results.BacktestResult` | SEMANTICALLY_INCOMPATIBLE | No | fields, units, lifecycle | incompatible | canonical result construction |
| SignalStrategy | `tw_stock_tool.backtest.engine.SignalStrategy` | strategy functions and signal DataFrame | CONCEPTUAL_MAPPING_ONLY | No | object protocol | incompatible | strategy bridge |
| BaseStrategy | `tw_stock_tool.strategies.base.BaseStrategy` | `tw_stock_tool.backtesting.strategies` functions | NO_CANONICAL_EQUIVALENT | No | no canonical base class | not applicable | migration design |

## D. Construction and invocation mapping

| Alternate operation | Canonical target | Classification | Conversion | Semantic risk |
|---|---|---|---|---|
| price_df | df | PARTIAL_MAPPING | signal preparation | high |
| strategy | standardized signal DataFrame | REQUIRES_EXPLICIT_ADAPTER | strategy bridge | high |
| params | strategy/config inputs | PARTIAL_MAPPING | preprocessing | medium |
| initial_cash | initial_capital | RENAMED_EQUIVALENT | rename | medium |
| commission | fee_rate | PARTIAL_MAPPING | formula verification | high |
| tax | tax_rate | PARTIAL_MAPPING | exit-cost verification | high |
| slippage | no canonical argument | NO_CANONICAL_EQUIVALENT | policy | high |
| .run() | run_backtest_result() | REQUIRES_EXPLICIT_ADAPTER | call/state/result bridge | high |
| constructor validation | canonical input validation | PARTIAL_MAPPING | explicit rules | high |
| signal validation | canonical signal validation | PARTIAL_MAPPING | explicit rules | high |
| result return type | canonical BacktestResult | SEMANTICALLY_INCOMPATIBLE | canonical result construction | high |

## E. Strategy-interface mapping

| Alternate API | Canonical relation | Classification | Transformation or bridge required | Main semantic risk |
|---|---|---|---|---|
| SignalStrategy.name | registry key/metadata | CONCEPTUAL_MAPPING_ONLY | naming policy | identity is not preserved |
| SignalStrategy.generate_signals(df, params) | strategy function and signal DataFrame | PARTIAL_MAPPING | invocation bridge | object lifecycle differs |
| SignalStrategy.validate_signals(result_df) | canonical signal validation | NO_CANONICAL_EQUIVALENT | validation design | validation rules differ |
| BaseStrategy abstract inheritance contract | no canonical base-strategy class or inheritance contract | NO_CANONICAL_EQUIVALENT | migration design | subclass contract cannot redirect |
| BaseStrategy.name | registry key/metadata | CONCEPTUAL_MAPPING_ONLY | naming policy | identity is not preserved |
| BaseStrategy.generate_signals(df, params) | strategy function and signal DataFrame | PARTIAL_MAPPING | invocation bridge | object lifecycle differs |
| BaseStrategy.validate_signals(result_df) | canonical signal validation | NO_CANONICAL_EQUIVALENT | validation design | validation rules differ |

Canonical strategies are function-based; no canonical base-strategy class or inheritance contract exists.

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

| Canonical-only field | Availability from alternate result | Derivation classification | Required source data | Required assumptions | Safe for lossless adapter |
|---|---|---|---|---|---|
| initial_capital | not directly available | DERIVABLE_ONLY_WITH_ORIGINAL_INPUT | original cash | explicit math | No |
| buy_hold_return_pct | unavailable | DERIVABLE_ONLY_WITH_ORIGINAL_INPUT | prices | period definition | No |
| cagr_pct | unavailable | NO_SAFE_DERIVATION | dates/capital | none | No |
| exposure_pct | unavailable | NO_SAFE_DERIVATION | equity/positions | none | No |
| profit_factor | incomplete | DERIVABLE_WITH_ASSUMPTIONS | complete PnL rows | canonical formula | No |
| best_trade_pct | incomplete | DERIVABLE_WITH_ASSUMPTIONS | complete rows | units | No |
| worst_trade_pct | incomplete | DERIVABLE_WITH_ASSUMPTIONS | complete rows | units | No |
| avg_hold_days | unavailable | NO_SAFE_DERIVATION | dates | lifecycle | No |
| sharpe_ratio | unavailable | NO_SAFE_DERIVATION | equity curve | frequency | No |
| sortino_ratio | unavailable | NO_SAFE_DERIVATION | equity curve | frequency | No |
| avg_profit | incomplete | DERIVABLE_WITH_ASSUMPTIONS | complete rows | units | No |
| avg_loss | incomplete | DERIVABLE_WITH_ASSUMPTIONS | complete rows | units | No |
| equity_curve | unavailable | NO_SAFE_DERIVATION | prices/signals | recomputation | No |
| stock | not stored | NOT_AVAILABLE_FROM_ALTERNATE_RESULT | metadata | none | No |
| strategy | not stored | NOT_AVAILABLE_FROM_ALTERNATE_RESULT | metadata | none | No |
| parameters | not stored | NOT_AVAILABLE_FROM_ALTERNATE_RESULT | metadata | none | No |
| start_date | not safely available | NO_SAFE_DERIVATION | full data | boundaries | No |
| end_date | not safely available | NO_SAFE_DERIVATION | full data | boundaries | No |

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

| Additional input | Directly available from alternate result | Inferable with assumptions | Recomputable with additional sources | Required for lossless mapping | Risk if absent |
|---|---|---|---|---|---|
| Original price DataFrame | No | No | Yes, only if supplied | Yes | high |
| Original signal DataFrame | No | No | Conditionally, with strategy, params, price data, and original semantics | Yes | high |
| Initial cash | No | No | No | Yes | high |
| Commission | No | No | No | Yes | high |
| Tax | No | No | No | Yes | high |
| Slippage | No | No | No | Yes | high |
| Strategy name | No | No | No | Yes | medium |
| Parameters | No | No | No | Yes | medium |
| Stock symbol | No | No | No | Yes | medium |
| Full start/end dates | No | No | Yes, only if source data is supplied | Yes | medium |
| Equity curve | No | No | Yes, only by recomputation with original inputs and semantics | Yes | high |

**A lossless result-only adapter is not possible.**

## J. Serialization, artifact, and converter mapping

| Boundary | Accepted type/schema | Alternate compatibility | Failure mode | Mapping needed | Artifact risk | Authorized in A6 |
|---|---|---|---|---|---|---|
| serialize_backtest_result | canonical | rejected | type error | EXPLICIT_CANONICAL_RESULT_CONSTRUCTION | high | no |
| deserialize_backtest_result | canonical construction | no alternate | canonical object | CANONICAL_SCHEMA_CONVERSION | high | no |
| JSON export | canonical | rejected | serializer error | EXPLICIT_CANONICAL_RESULT_CONSTRUCTION | high | no |
| JSON load | canonical schema | no alternate | canonical result | CANONICAL_SCHEMA_CONVERSION | high | no |
| serialization file writer | canonical | rejected | type boundary | ADAPTER_DESIGN_REQUIRED | high | no |
| serialization file reader | canonical | no alternate | schema boundary | CANONICAL_SCHEMA_CONVERSION | high | no |
| report builders | canonical reports | no alternate | field mismatch | ADAPTER_DESIGN_REQUIRED | high | no |
| paper-trading converter | canonical | rejected | model error | NO_SAFE_DIRECT_MAPPING | high | no |
| downstream consumer contracts | canonical consumers | alternate unsupported | contract break | MIGRATION_DESIGN_REQUIRED | high | no |

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
| Golden characterization fixtures | PARTIAL_EXISTING_EVIDENCE | Existing A2 tests are not adapter-specific golden fixtures. | yes | test phase |
| Round-trip artifact tests | PARTIAL_EXISTING_EVIDENCE | Existing A3 artifact tests do not test alternate-to-canonical adapter round trips. | yes | test phase |
| External-consumer risk assessment | incomplete | external evidence | yes | evidence phase |
| Rollback plan | incomplete | approved plan | yes | design |
| Version plan | incomplete | release policy | yes | design |
| User communication plan | incomplete | reviewed docs | yes | design |
| Dedicated production-phase approval | absent | explicit approval | yes | production phase |

**No adapter or migration implementation may begin while these criteria are incomplete.**

## M. Recommended next phase and non-goals

Recommend **Alternate Backtest Adapter Design Decision**. A6 does not add adapters, redirects, aliases, migrations, warnings, fixes, serializer/converter changes, schemas, consumer migration, removals, version changes, merged PRs, or Phase A7.
