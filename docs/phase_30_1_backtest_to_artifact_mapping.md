# Phase 30.1 Goal
This phase defines the mapping design from an already-computed historical backtest result to a simulated paper trading artifact.
No production converter is implemented in this phase.

# Current Model Summary

**BacktestResult** (`src/tw_stock_tool/backtesting/results.py`):
- `stock`: string symbol or `None`
- `initial_capital`: float
- `final_capital`: float
- `trades`: pandas DataFrame containing backtest trade history (Columns: `Entry Date`, `Exit Date`, `Entry Price`, `Exit Price`, `Shares`, `PnL`, `PnL_pct`, `Hold Days`, `Exit Reason`, `Type`)
- `strategy`: string or `None`
- `parameters`: dict (defaults to empty)
- `start_date`: Any or `None`
- `end_date`: Any or `None`
- Various metrics (total_return_pct, max_drawdown_pct, etc.)

**Note on run_backtest() output**: The internal structured model is `BacktestResult`. However, the current public `run_backtest()` returns a legacy dict (`return result.to_legacy_dict()`). Therefore, Phase 30.3 must explicitly decide whether the converter accepts:
1. `BacktestResult` object
2. legacy backtest dict
3. both
This also reinforces why the future CLI should remain deferred until a concrete serialized backtest artifact format exists.

**SimulatedPaperTradingResult** (`src/tw_stock_tool/paper_trading/results.py`):
- `symbol`: str
- `initial_cash`: float
- `final_cash`: float
- `final_position_quantity`: int
- `average_cost`: float
- `realized_pnl`: float
- `unrealized_pnl`: float
- `total_equity`: float
- `order_count`: int
- `fill_count`: int
- `open_position_count`: int
- `orders`: tuple[SimulatedOrder, ...]
- `fills`: tuple[SimulatedFill, ...]

**SimulatedOrder**: `order_id`, `symbol`, `side`, `quantity`, `signal_time`, `created_at`, `strategy`, `metadata`
**SimulatedFill**: `order_id`, `symbol`, `side`, `quantity`, `price`, `filled_at`, `fee`, `tax`, `slippage`

# Proposed Mapping Table

| Source (`BacktestResult`) | Target (`SimulatedPaperTradingResult`) | Mapping Rule / Conversion | Default / Validation | Open Question |
|---|---|---|---|---|
| `stock` | `symbol` | Direct mapping | Future validation must decide if missing `stock` (None) should be rejected, defaulted, or supplied externally | |
| `initial_capital` | `initial_cash` | Direct mapping | Must be >= 0, finite float | |
| `final_capital` | `final_cash` | Direct mapping | Must be >= 0, finite float | |
| `trades` DataFrame | `final_position_quantity` | Net open quantity | `0` | Are open trades represented clearly in the DF? |
| `trades` DataFrame | `average_cost` | Weighted avg of open entries | `0.0` | |
| `PnL` | `realized_pnl` | Sum of closed trades PnL | `0.0` | |
| Open positions PnL | `unrealized_pnl` | Floating PnL | `0.0` | How is current price retrieved for open trades? |
| `final_capital` | `total_equity` | `final_cash + unrealized_pnl` | Must be finite float | |
| Count of entries/exits | `order_count` | Number of mapped orders | `>= 0` | |
| Count of entries/exits | `fill_count` | Number of mapped fills | `>= 0` | |
| Open position check | `open_position_count` | 1 if open else 0 | `0` | |
| `trades` rows | `orders` & `fills` | Each trade maps to BUY and SELL pairs explicitly using DF columns | | |

**Trades Mapping Rule (BUY / SELL generation)**:
- **BUY order/fill side**: mapped from `Entry Date`, `Entry Price`, `Shares`
- **SELL order/fill side**: mapped from `Exit Date`, `Exit Price`, `Shares`
- **Realized PnL**: mapped from `PnL`
- **Metadata**: mapped from `Exit Reason` / `Type`

# Retrospective Semantics

This converter is an offline data transformer. It only maps an already-computed historical BacktestResult into a SimulatedPaperTradingResult artifact. It does not run a strategy, fetch live or historical market data, generate new trading signals, connect to a broker, place orders, or provide investment advice.

Any BUY / SELL values in the converted artifact are retrospective historical backtest-side records. They are not live signals, order instructions, buy/sell recommendations, or investment advice.

# Edge Cases

- **Empty backtest result / No trades**: Must correctly generate an artifact with initial cash == final cash, 0 orders/fills, and 0 PnL.
- **Open positions**: Current legacy `run_backtest()` output appears to be closed-trade-only because remaining shares are force-closed as `SELL_EOD` at the end of data. Open-position conversion should remain a future compatibility edge case. If future backtest variants preserve open positions, the converter will need a defined last price / mark price policy for `unrealized_pnl`.
- **Missing optional metadata**: `strategy` or `parameters` might be `None`.
- **Non-finite numeric values**: NaNs from pandas DataFrames must be sanitized or rejected.
- **Decimal / float precision**: Float differences must not break serialization boundaries.
- **Datetime serialization**: Pandas Timestamps in `trades` must be safely converted to standard format strings.
- **Unknown symbol**: Must be rejected or handled gracefully.
- **Fees / slippage / tax fields**: If not present in `BacktestResult` trades, they should default to `0.0`.
- **Strict type checking**: Fractional numeric values are invalid for integer fields (e.g., `quantity`). Boolean values must be rejected for numeric fields.

# Validation Rules

- **JSON Serializable**: Mapped metadata and timestamps must be strictly JSON serializable.
- **Finite floats only**: All monetary and pricing fields must be finite floats (no NaN / Infinity).
- **Strict integer fields**: `quantity` and counts must be strict `int`. No silent truncation of fractional floats into integers.
- **No bool as numbers**: Booleans are rejected for numeric fields.
- **Required fields**: Essential structural fields (`symbol`, `initial_cash`, `orders`, `fills`) must be strictly present.
- **Exception boundary**: Re-use `PaperTradingModelError` or raise `ValueError` for mapping failures, consistent with Phase 29 strictness.

# Proposed Future API

```python
def convert_backtest_result_to_simulated_paper_trading_result(
    backtest_result: "BacktestResult",
    *,
    metadata: dict | None = None,
) -> "SimulatedPaperTradingResult":
    ...
```
Expected location: `src/tw_stock_tool/paper_trading/backtest_converter.py`

# Proposed Future CLI

```bash
twstock convert-backtest-to-artifact <input_backtest_json> --output-json result.json
```
*(Open Question: Currently there is no serialized `BacktestResult` JSON format documented. Therefore, CLI input format and implementation details remain an open question).*

The future CLI must only convert existing local artifacts. It must not run a backtest. It must not download data. It must not execute a strategy. It must not connect to a broker. It must not place orders.

# Proposed Future Tests

Tests to add in Phase 30.3:
- Successful conversion with multiple trades.
- Successful conversion with no trades.
- Metadata handling and propagation.
- Rejection of invalid numeric values (NaN/Infinity) from backtest trades.
- Rejection of invalid metadata.
- Validation of BUY / SELL retrospective wording.
- Type strictness (no truncation of fractional quantities, no bools as numbers).
- Schema compatibility with existing JSON exporter.
- Verification of no live-data imports, no broker imports, and no strategy execution.

# Out of Scope

The following are strictly out of scope:
- Implementing the converter code.
- Implementing the CLI.
- Running backtests.
- Running strategies.
- Downloading market data.
- Producing new signals.
- Broker integration.
- Order execution.
- Auto trading.
- Investment advice.
- Modifying unrelated modules.

# Recommended Next Step

Phase 30.3 should focus strictly on implementing the core converter logic (`backtest_converter.py`) and its unit tests. CLI implementation should be delayed until a concrete JSON representation for `BacktestResult` is formalized, or deferred entirely if only Python library usage is needed for now.
