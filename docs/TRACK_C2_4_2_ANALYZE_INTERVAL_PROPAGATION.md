# Track C2.4.2 Analyze Interval Propagation

## Repository

- Branch: `track-c2-research-correctness-fixes`
- Baseline commit: `39c8eb569020543ee7989171c4b537c417297f0f`
- Final commit is recorded in the execution report.

## Aggregate-audit blocker

Analyze already accepts and validates `1d`, `1wk`, and `1mo`, and downloads bars with the selected interval. Its Backtest call omitted that interval, so weekly and monthly data used the daily metric default.

## Existing Analyze interval option

`MainOptions.interval` and the existing `--interval` parser option are unchanged. The selected value continues to pass directly to `analyze_stock()`.

## Missing Backtest propagation and production fix

`run_analysis_result()` now passes `interval=options.interval` to the existing canonical `run_backtest()` call. No transformation, normalization, new argument, or helper was added.

## Daily compatibility

A deterministic mocked test proves `MainOptions(stock_id="2330")` sends `1d` to both Analysis and Backtest while preserving all existing Backtest parameters.

## Weekly propagation proof

A deterministic mocked test proves `MainOptions(stock_id="2330", interval="1wk")` sends `1wk` to both Analysis and Backtest. A bounded Track C1 regression records the research-correctness contract without network access.

## Changed files

- `src/tw_stock_tool/cli/main.py`
- `tests/test_main.py`
- `tests/test_track_c1_research_correctness.py`
- `docs/TRACK_C1_RESEARCH_CORRECTNESS_CHARACTERIZATION.md`
- `docs/TRACK_C2_4_1_CORE_INTERVAL_AWARE_METRICS.md`
- `docs/TRACK_C2_4_2_ANALYZE_INTERVAL_PROPAGATION.md`

## Tests executed

- Analyze CLI tests
- Track C1 research-correctness tests
- Backtest tests
- Backtest metric tests
- Combined targeted suite
- Full unittest discovery suite
- Temporary mocked direct propagation checks

## Expected failures

- Before: 0
- After: 0

## Non-goals

This phase does not change Backtest or metric formulas, data download, Analysis, indicators, signals, trading logic, schemas, output, exports, charts, exit codes, root wrappers, or other interval workflows. It does not expose interval selection through Parameter Sweep, Walk Forward, Strategy Compare, Backtest Report, or other workflows, and does not merge to main or create a pull request.

## Next step

Rerun the aggregate Track C2 closeout audit.
