# Issue #84 - BacktestResult artifact and terminal accounting (B3, B10a)

Maintenance/correctness work. It does **not** change the Phase 56 product
roadmap; Phase 56.3 Recommendation Evidence remains the next product phase.

Baseline: `3f21a32cce75d31b01a92015588e4de7da68791b` (PR #85).

Both defects let a legitimate backtest produce a result that could not be
exported, or that was exported with fabricated numbers.

## Consumer map

`profit_factor` is produced once and consumed on two independent paths:

| Consumer | Reads | Affected by this change |
| --- | --- | --- |
| `metrics.calculate_profit_factor()` | trade records | no - unchanged |
| `BacktestResult.profit_factor` | metric | no - still `float`, still `math.inf` |
| `results.to_legacy_dict()` -> `"Profit Factor"` | `BacktestResult` | no - already had an explicit non-finite branch returning `float("inf")` |
| parameter sweep / walk-forward / strategy compare / all reports | **legacy dict** | no - they never read the artifact |
| `serialization.serialize/deserialize` | `BacktestResult` <-> JSON | **yes** - this was the only breakage |
| `paper_trading.backtest_converter` | `BacktestResult` | no - does not read `profit_factor` |
| Phase 56.1 / 56.2 qualification | `QualificationMetricSet` | no - **no qualification path reads `profit_factor` at all** |

The qualification result is important: `grep profit_factor src/tw_stock_tool/qualification`
returns nothing, and `universe_qualification` reads only `Total Return %`,
`Trade Count` and `Max Drawdown %`. Strategy promotion therefore cannot be
influenced by the artifact representation chosen here.

## B3 - unbounded profit factor vs artifact serialization

**Root cause.** `calculate_profit_factor()` returns `math.inf` when gross
profit is positive and gross loss is exactly zero - the mathematically correct
answer for an all-winning backtest. `serialize_backtest_result()` passed that
value through `_normalize_float()`, which rejects every non-finite value, so a
valid short-window or single-trade backtest failed artifact export.

### Decision record

| Question | Decision |
| --- | --- |
| Chosen artifact representation | `summary.profit_factor: null` |
| Meaning of `null` | mathematically unbounded: gross loss `== 0` and gross profit `> 0` |
| Schema version impact | **bump `1` -> `2`** |
| Backward-reading policy | reader accepts `{1, 2}`; version 1 still requires a finite number, version 2 additionally allows `null` |
| Internal `BacktestResult` behavior | unchanged - `profit_factor: float`, `math.inf` for unbounded |
| Legacy dict behavior | unchanged - `to_legacy_dict()["Profit Factor"]` is still `float("inf")` |
| Qualification behavior | unchanged - no qualification consumer reads `profit_factor` |

### Why the states stay distinguishable

| Case | Internal | Artifact |
| --- | --- | --- |
| no trades | `0.0` | `0.0` |
| gross profit `0`, losses only | `0.0` | `0.0` |
| wins and losses | finite `> 0` | same finite number |
| all wins, no losing trade | `math.inf` | `null` |
| `NaN` / `-inf` | not reachable from the metric | rejected |

`null` and `0.0` are different JSON values, so "no trades" is never confused
with "no losing trades".

### Why the schema was bumped

The reader is strict: it rejects unknown fields and gates on an exact
`schema_version`. Emitting a value that a version 1 reader rejects, while still
labelling the artifact version 1, would break the promise that a version 1
artifact is readable by a version 1 reader. Bumping keeps `schema_version` a
real contract rather than decoration.

Nothing becomes unreadable. Version 1 artifacts keep their exact meaning and
still load, because an all-winning backtest could never have been serialized as
version 1 in the first place - that was the bug. There is consequently no
corpus of version 1 artifacts containing `null`, and version 1 continues to
reject `null` rather than silently reinterpreting it.

This supersedes "Numeric values must be finite" in
[Phase 31.1 §5](phase_31_1_backtest_result_artifact_serialization_boundary.md)
for this one field. `null` is not a numeric value, so the finite-number rule
itself is untouched: `initial_capital`, `final_capital`, `sharpe_ratio` and
every other numeric field still reject `NaN` and both infinities, and
`profit_factor` still rejects `NaN` and `-inf` because neither is reachable
from `calculate_profit_factor()`.

The encoding lives in two named helpers, `_profit_factor_to_json()` and
`_profit_factor_from_json()`, kept separate from the general `_normalize_float()`
so that the unbounded-metric semantics cannot leak into ordinary numeric
validation.

## B10a - terminal position accounting

**Root cause.** The end-of-data block closed the position only when the final
close was usable, but ran `equity_curve[-1] = cash` unconditionally:

```python
if shares > 0:
    last_price = float(df.iloc[-1]["Close"])
    if not (pd.isna(last_price) or last_price <= 0):
        close_position(len(df) - 1, "SELL_EOD", last_price)
    equity_curve[-1] = cash
```

With a final close of `0` or negative, the position stayed logically open, no
trade was recorded, and final equity was forced to cash. Observed on the
production path with a held position and `Close = 0.0`:

```
trade_count      = 0          <- the trade vanished
final_capital    = 7.71       <- leftover cash only
total_return_pct = -99.99     <- fabricated near-total loss
```

`NaN` and `+/-inf` were never reachable here: `_validate_price_columns()`
already rejects them before the run starts. The reachable cases are exactly
`Close == 0` and `Close < 0`.

### Decision record

**Terminal invariant: a returned `BacktestResult` never carries an open
position.** If the final bar cannot supply a usable exit price, the run fails
closed with `BacktestError`.

This is not a new invariant, it is enforcement of an existing documented one.
[Phase 30.1 §Edge Cases](phase_30_1_backtest_to_artifact_mapping.md) records:

> Current legacy `run_backtest()` output appears to be closed-trade-only
> because remaining shares are force-closed as `SELL_EOD` at the end of data.
> [...] If future backtest variants preserve open positions, the converter will
> need a defined last price / mark price policy for `unrealized_pnl`.

No such mark-price policy exists, and `BacktestResult` has no open-position
field, no unrealized-PnL field and a scalar `final_capital`. Inventing a mark
price (last valid close, entry price, or zero) would change the financial
meaning of the result silently. Failing closed is also consistent with the
portfolio path, where `DEVELOPMENT_ROADMAP.md` §53.5B already specifies that an
`invalid/non-numeric/NaN/infinity/<=0 final close` fails the whole execution.

Scope is the terminal position only. A non-positive close elsewhere in the
frame is unchanged: if the position is already closed by a signal, the run
still succeeds.

### Invariants now asserted

For every successfully returned result:

* `equity_curve.iloc[-1] == final_capital`
* `len(trades) == trade_count`
* `total_return_pct` is derived from the same `final_capital`
* the `SELL_EOD` trade's fee, tax and PnL are unchanged

## Out of scope

Issue #84 items B5, B6, B7, B8, B10b, B10c and the A-series remain open and
were not touched. No strategy logic, execution timing, position sizing, cost
formula, Sharpe/Sortino definition or qualification threshold was changed.
