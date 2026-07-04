# Phase 33.1 — BacktestResult Artifact Export Boundary Planning

## 1. Goal

Phase 33.1 is a docs-only planning phase for the future `BacktestResult` artifact export from backtest execution paths. 
This phase involves:
* no production code
* no tests
* no CLI implementation
* no README update
* no merge

## 2. Current State

* The `BacktestResult` model exists.
* Serialization and file helpers exist.
* Artifact-input-only CLI exists under `twstock backtest-artifact`.
* `run_backtest()` still returns a legacy dict.
* Existing `backtest-report` and other execution-oriented CLIs should not be assumed to have direct access to a stable `BacktestResult` artifact boundary yet.

## 3. Core Problem

The core boundary problem: `BacktestResult` artifact export should not be bolted directly onto legacy dict output without a clear transition path.

The risks of forcing direct export:
* breaking existing callers of `run_backtest()`
* confusing legacy report output with stable JSON artifact output
* creating duplicate conversion logic
* accidentally mixing execution, report generation, and artifact serialization
* weakening offline research-only semantics

## 4. Candidate Design Options

### A. Add a new structured execution API
**Example future shape:**
```python
run_backtest_result(...) -> BacktestResult
```
This should be the preferred direction if feasible.
* keep `run_backtest()` backward-compatible
* `run_backtest()` may internally call `run_backtest_result()` and then return `to_legacy_dict()`
* artifact export can use `run_backtest_result()` directly
* avoids legacy dict → BacktestResult conversion

### B. Add artifact export option to an existing CLI after structured API exists
**Example future shape:**
```bash
twstock backtest-report ... --output-backtest-json result.json
```
* only safe after a stable structured `BacktestResult` path exists
* must use `export_backtest_result_json_file(...)`
* must respect `--overwrite`
* must not alter existing report output behavior

### C. Create a separate execution-to-artifact CLI
**Example future shape:**
```bash
twstock backtest-artifact run-export ... --output-json result.json
```
**Pros and cons:**
* clearer artifact semantics
* but may duplicate `backtest-report` argument parsing
* must avoid implying live trading or investment advice

### D. Add legacy dict → BacktestResult converter
*(Not recommended for the near term)*
* legacy dict may lose metadata
* DataFrame / Series fields may not be stable
* easier to create silent inconsistencies
* better to preserve typed `BacktestResult` before converting to legacy dict

## 5. Recommended Direction

A conservative sequence is recommended:
* **Phase 33.1**: docs-only boundary planning
* **Phase 33.3**: introduce `run_backtest_result(...) -> BacktestResult` while keeping `run_backtest()` backward-compatible
* **Phase 33.5**: add focused tests proving `run_backtest()` legacy output remains unchanged and `run_backtest_result()` returns structured `BacktestResult`
* **Phase 33.7 or later**: consider CLI export using `export_backtest_result_json_file(...)`
* **Later only**: consider backtest-report `--output-backtest-json`

Direct CLI export should wait until the structured API boundary is implemented and tested.

## 6. Backward Compatibility Plan

* Do not break `run_backtest()` callers.
* `run_backtest()` should continue returning the current legacy dict unless a major version boundary is intentionally planned.
* Future structured API should be additive.
* Existing reports and CLIs should continue working.

## 7. File / Overwrite Plan

For any future artifact-writing CLI:
* use `export_backtest_result_json_file(...)`
* do not reimplement writer logic
* rely on shared `write_text_report(..., overwrite=overwrite)`
* default overwrite should be false
* existing output file should fail safely unless `--overwrite` is provided
* UTF-8 should be preserved

## 8. Error Handling Plan

Future CLI export should handle:
* `BacktestError`
* `FileNotFoundError`
* `IsADirectoryError`
* `PermissionError`
* `FileExistsError`
* `BacktestResultSerializationError`
* data loading errors if the CLI path loads market data

*Note: Phase 33.1 does not implement these handlers; it only plans them.*

## 9. Safety / Semantics Boundary

**This is an offline research artifact workflow.**

Future implementation must not:
* connect to broker APIs
* create orders
* place trades
* produce live buy/sell/hold signals
* claim to provide investment advice
* claim or imply guaranteed profit
* imply real-time trading capability

**Allowed wording:**
* offline research artifact
* historical backtest artifact
* existing artifact export
* structured backtest result
* research-only JSON artifact

**Avoid wording:**
* live_signal
* order_signal
* recommendation
* auto_trade
* broker_order
* buy/sell/hold advice
* guaranteed profit

## 10. Explicit Non-Goals

Phase 33.1 must not implement:
* `run_backtest_result()`
* CLI code
* tests
* README changes
* `run_backtest()` behavior changes
* legacy dict converter
* direct backtest execution export
* broker API
* auto trading
* live trading
* live signals
* investment advice wording
* merge

## 11. Proposed Future Phase Breakdown

Suggest a conservative future sequence:
* **Phase 33.1**: docs-only export boundary planning
* **Phase 33.3**: structured `run_backtest_result()` API
* **Phase 33.5**: compatibility and roundtrip tests
* **Phase 33.7**: optional backtest artifact export CLI planning or implementation
* **Later only**: evaluate adding `--output-backtest-json` to `backtest-report`
