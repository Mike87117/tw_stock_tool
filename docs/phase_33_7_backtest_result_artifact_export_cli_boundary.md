# Phase 33.7 — BacktestResult Artifact Export CLI Boundary Planning

## 1. Current state

The project already has:

* `run_backtest_result(...) -> BacktestResult`
* `run_backtest(...)` as a backward-compatible legacy dict wrapper
* `BacktestResult` JSON serialization helpers
* `BacktestResult` JSON file helper: `export_backtest_result_json_file(..., overwrite=False)`
* existing artifact-input-only CLI:
  * `twstock backtest-artifact validate`
  * `twstock backtest-artifact inspect`
  * `twstock backtest-artifact convert-to-simulated-paper-trading`

## 2. Boundary problem

The current `backtest-artifact` CLI is intentionally artifact-input-only.

It currently says it does not:

* fetch market data
* run strategies
* execute backtests
* connect to brokers
* place orders
* produce live signals
* provide investment advice

Therefore, adding a run-export command directly under the same CLI requires a deliberate boundary decision, because a run-export command would fetch historical data, apply a strategy, and execute a historical backtest.

## 3. CLI options considered

### Option A
`twstock backtest-artifact run-export ... --output-json result.json`

**Pros:**
* discoverable under artifact commands
* name clearly says artifact
* can use `run_backtest_result` directly

**Cons:**
* changes `backtest-artifact` from artifact-input-only to mixed artifact/execution CLI
* existing help wording and tests would need careful updates
* must avoid direct top-level imports that pull data/broker dependencies into validate/inspect/convert paths

### Option B
`twstock backtest-result-export ... --output-json result.json`

**Pros:**
* keeps existing `backtest-artifact` CLI artifact-input-only
* creates a clearer execution/export boundary
* avoids weakening existing validate/inspect/convert semantics
* safer for preserving existing forbidden dependency tests

**Cons:**
* adds another top-level command
* less grouped with artifact validation commands

### Option C
`twstock backtest-report ... --output-backtest-json result.json`

**Pros:**
* reuses existing backtest-report execution flow
* familiar arguments already exist

**Cons:**
* couples report generation and artifact export
* risks mixing legacy dict report normalization with structured `BacktestResult` artifact output
* should remain deferred until structured export path is proven stable

## 4. Recommendation

We recommend **Option B** as the safest next production implementation target:

`twstock backtest-result-export ... --output-json result.json`

This keeps:

* `backtest-artifact` CLI artifact-input-only
* validate / inspect / convert behavior unchanged
* report CLI unchanged
* `run_backtest_result` as the structured execution source
* file-writing boundary delegated to `export_backtest_result_json_file`

## 5. Proposed future production phase

The next production phase after this planning doc is:

**Suggested name:** Phase 33.9 — BacktestResult Artifact Execution Export CLI
**Suggested branch:** `phase-33-9-backtest-result-artifact-execution-export-cli`

### Expected scope for Phase 33.9:

* Add a new CLI module, for example: `src/tw_stock_tool/cli/backtest_result_export_cli.py`
* Add unified CLI route: `twstock backtest-result-export`
* The new CLI should use a minimal argument set aligned with existing `backtest_report` CLI:
  `--stock`, `--strategy`, `--period`, `--initial-capital`, `--output-json`, `--overwrite`, `--force-refresh`, `--short-window`, `--long-window`, `--rsi-buy-below`, `--rsi-sell-above`, `--score-buy`, `--score-sell`, `--fee-rate`, `--tax-rate`, `--position-size`, `--stop-loss-pct`, `--take-profit-pct`, `--max-hold-days`
* It must call: `run_backtest_result(...)`
* It must set `BacktestResult` metadata: `stock`, `strategy`, `start_date`, `end_date`, `parameters`
* It must write using: `export_backtest_result_json_file(result, args.output_json, overwrite=args.overwrite)`
* It must not use:
  * `run_backtest()`
  * legacy dict -> BacktestResult converter
  * manual `open()`
  * manual `mkdir()`
  * manual `Path.resolve()`
  * manual `os.path.exists()`
  * manual overwrite checks
* It must produce clean errors without traceback.
* Existing file-writing boundary must remain delegated to shared writer through: `export_backtest_result_json_file(...)`

## 6. Safety wording

**Allowed wording:**
* historical backtest artifact
* research-only JSON artifact
* structured BacktestResult artifact
* offline research artifact
* historical execution export
* not investment advice

**Forbidden wording:**
* live signal
* order signal
* buy/sell/hold advice
* investment recommendation
* recommended stocks
* best stocks to buy
* guaranteed profit
* guaranteed return
* broker order
* order placement
* live trading
* auto trading

## 7. Explicit non-goals

This phase must explicitly defer:

* actual CLI implementation
* modifying `backtest_artifact_cli.py`
* modifying `backtest_report.py`
* adding `--output-backtest-json` to `backtest-report`
* broker API
* Shioaji integration
* live trading
* live signal
* order execution
* investment advice
* legacy dict -> BacktestResult converter
* README changes
* tests
