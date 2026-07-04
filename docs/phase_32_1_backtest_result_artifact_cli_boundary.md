# Phase 32.1 — BacktestResult Artifact CLI Boundary Planning

## 1. Goal
This phase only plans a future CLI boundary for `BacktestResult` JSON artifacts. It does not implement the CLI itself, nor does it connect any execution pathways. The objective is to define whether and how existing offline research artifacts should be exposed through command-line operations safely.

## 2. Current State
Phase 31 is already complete and merged. It successfully added:
* `BacktestResult` JSON serialization core API
* `BacktestResult` JSON roundtrip tests
* `BacktestResult` → `SimulatedPaperTradingResult` converter chain safety tests
* subprocess-isolated forbidden dependency sanity tests
* `BacktestResult` JSON file helpers

The relevant APIs currently available are:
* `serialize_backtest_result(result: BacktestResult) -> dict[str, Any]`
* `deserialize_backtest_result(data: dict[str, Any]) -> BacktestResult`
* `export_backtest_result_json(result: BacktestResult) -> str`
* `load_backtest_result_json(content: str) -> BacktestResult`
* `export_backtest_result_json_file(result, path, overwrite=False) -> Path`
* `load_backtest_result_json_file(path) -> BacktestResult`

The unified CLI currently routes subcommands through `twstock`. The `simulated-paper-trading-export` subcommand serves as the closest existing CLI pattern because it reads an existing research-only JSON artifact and exports reports, keeping artifact handling strictly separated from execution.

**Important existing boundary:** `run_backtest()` still returns a legacy dictionary via `result.to_legacy_dict()`. `run_backtest()` does NOT return a `BacktestResult` at this time. This phase does NOT integrate `run_backtest()` or add legacy dict → `BacktestResult` conversion.

## 3. Proposed CLI Boundary Options

### A. BacktestResult artifact inspection CLI
**Example future shape:**
`twstock backtest-artifact inspect input.json`

**Purpose:**
Read an existing `BacktestResult` JSON artifact and print a safe summary to the console.

### B. BacktestResult artifact validation CLI
**Example future shape:**
`twstock backtest-artifact validate input.json`

**Purpose:**
Load and validate an existing `BacktestResult` JSON artifact strictly to verify JSON well-formedness and schema adherence without running backtests or fetching data.

### C. BacktestResult artifact conversion CLI to simulated paper trading artifact
**Example future shape:**
`twstock backtest-artifact convert-to-simulated-paper-trading input.json --output-json output.json`

**Purpose:**
Load an existing `BacktestResult` artifact, convert it to a `SimulatedPaperTradingResult` using the existing converter, and write a simulated paper trading JSON artifact to disk.

### D. Direct backtest execution export CLI
**Example future shape:**
`twstock backtest-report ... --output-backtest-json ...`

**Assessment:**
This is deferred and **not recommended** for Phase 32. Implementing this currently risks mixing `run_backtest()` legacy dict behavior with modern `BacktestResult` artifact behavior. 

## 4. Recommended Phase 32 Direction

We recommend starting with artifact-input-only CLI commands first:
* `validate`
* `inspect`
* optionally `convert-to-simulated-paper-trading`

Artifact-input-only CLI operations are significantly safer because they:
* do not run strategies
* do not fetch market data
* do not depend on `run_backtest()`
* do not require legacy dict conversion
* preserve offline artifact semantics
* perfectly mirror the `simulated-paper-trading-export` boundary

## 5. Naming Plan

A conservative naming scheme will be applied to prevent misunderstandings about capabilities.

**Preferred future unified CLI command:**
`twstock backtest-artifact ...`

**Possible subcommands:**
* `validate`
* `inspect`
* `convert-to-simulated-paper-trading`

Names implying live signals, orders, recommendation, or auto trading must be strictly avoided.

## 6. File / Overwrite Behavior
Any future output-writing CLI should use existing file helpers and shared writer behavior:
* Future output JSON should respect `--overwrite`.
* Default should be `overwrite=False`.
* Existing files should fail safely unless `--overwrite` is provided.
* UTF-8 character encoding must be preserved.

## 7. Error Handling Plan
The future CLI must gracefully handle:
* `FileNotFoundError`
* `IsADirectoryError`
* `PermissionError`
* `BacktestResultSerializationError`
* `PaperTradingModelError` (if conversion to simulated paper trading is involved)
* `FileExistsError` for output overwrite protection

Error messages should be clear, localized where appropriate, and CLI-friendly.

## 8. Public API Export Plan
Should Phase 32 expose file helper APIs from package-level `__init__.py` files? 
We recommend deferring public re-export unless there is an explicit user-facing need. Direct module imports remain perfectly acceptable and limit namespace pollution.

## 9. Safety / Semantics Boundary

**This is an offline research artifact workflow.**

It must not:
* fetch live market data
* run strategies
* execute backtests
* connect to broker APIs
* create orders
* place trades
* produce live buy/sell/hold signals
* provide investment advice
* claim or imply guaranteed profit

All future implementations should rely on terminology such as:
* `offline_research_artifact`
* `retrospective_offline_mapping`
* `research-only JSON artifact`
* `existing artifact input`

Strictly avoid terminology such as:
* live_signal
* order_signal
* recommendation
* auto_trade
* broker_order
* buy/sell/hold advice
* guaranteed profit

## 10. Explicit Non-Goals

Phase 32.1 must not implement:
* CLI code
* tests
* README updates
* `run_backtest` integration
* legacy dict converter
* broker API
* auto trading
* live trading
* live signal generation
* investment advice wording
* merge

## 11. Proposed Future Phase Breakdown

A conservative, incremental future sequence is proposed:
* **Phase 32.1:** docs-only CLI boundary planning (Current Phase)
* **Phase 32.3:** artifact validate / inspect CLI implementation and tests
* **Phase 32.5:** optional artifact → simulated paper trading artifact CLI conversion
* **Later only:** evaluate direct backtest execution export, strictly after the `run_backtest` / `BacktestResult` boundary is fully clarified and the legacy dict is removed.
