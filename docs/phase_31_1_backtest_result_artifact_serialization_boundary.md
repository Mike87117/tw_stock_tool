# Phase 31.1 - BacktestResult Artifact Serialization Boundary Planning

## Goal
Define how internal `BacktestResult` should eventually be serialized into a stable JSON artifact and loaded back safely, without executing backtests, strategies, market data downloads, broker integrations, live trading, order execution, or investment advice logic.

## 1. Proposed Module Location
`src/tw_stock_tool/backtesting/serialization.py`

## 2. Proposed Public Library-Level APIs
Future implementation will expose these APIs:
- `serialize_backtest_result(result: BacktestResult) -> dict[str, Any]`
- `deserialize_backtest_result(data: dict[str, Any]) -> BacktestResult`
- `export_backtest_result_json(result: BacktestResult) -> str`
- `load_backtest_result_json(content: str) -> BacktestResult`
- Optional future file helpers (not implemented in Phase 31.1).

## 3. Proposed JSON Top-Level Schema
The serialized JSON artifact will follow this top-level schema:
- `schema_version`
- `result_type`
- `summary`
- `trades`
- `equity_curve`
- `metadata`

## 4. Proposed Summary Fields
Include all scalar `BacktestResult` metrics:
- `initial_capital`
- `final_capital`
- `total_return_pct`
- `buy_hold_return_pct`
- `cagr_pct`
- `exposure_pct`
- `trade_count`
- `win_rate_pct`
- `max_drawdown_pct`
- `profit_factor`
- `best_trade_pct`
- `worst_trade_pct`
- `avg_hold_days`
- `sharpe_ratio`
- `sortino_ratio`
- `avg_profit`
- `avg_loss`
- `stock`
- `strategy`
- `parameters`
- `start_date`
- `end_date`

## 5. DataFrame / Series Serialization Plan
- `trades` DataFrame should become a list of JSON-safe records.
- `equity_curve` Series should become a list of date/equity records.
- Datetime-like values should be serialized using `.isoformat()` when available, otherwise `str()`.
- Numeric values must be finite.
- `bool` must not be accepted as numeric.

## 6. Validation Plan
The implementation must:
- reject non-dict top-level data
- reject unsupported `schema_version`
- reject unsupported `result_type`
- reject missing required top-level fields
- reject unknown top-level fields
- reject non-list `trades`
- reject non-list `equity_curve`
- reject non-dict `parameters`
- reject non-JSON-serializable `parameters`
- reject NaN/inf numeric values
- preserve empty `trades` and empty `equity_curve` safely

## 7. Safety Boundary
This is an **offline research artifact serialization boundary**.
It must not:
- run backtests
- run strategies
- download market data
- connect to broker APIs
- create orders
- produce live signals
- provide investment advice

## 8. Future Phases
- **Phase 31.3**: implement library serialization APIs
- **Phase 31.5**: add tests
- **Phase 31.7**: optional file helpers
- **Later only**: consider CLI or `run_backtest` integration after serialization boundary is stable
