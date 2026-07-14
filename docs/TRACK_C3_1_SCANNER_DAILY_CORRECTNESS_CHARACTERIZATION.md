# Track C3.1 Scanner and Daily Report Correctness Characterization

## Executive outcome

`PASS - NO DEFECT CONFIRMED`

Deterministic offline tests now exercise the real internal path from the mocked
download boundary through Analysis, indicators, signals, Scanner, and Daily
Report. Continuous-rise, mixed-universe, interval-propagation, empty-input, and
all-failed behavior are `CORRECTLY_HANDLED`. Zero-range flat prices keep RSI and
ranking-critical fields usable but export `NaN` for stochastic `K` and `D`;
because no existing contract requires those non-ranking fields to be finite,
that observation is `CONTRACT_UNDECIDED`, not a confirmed defect.

No production fix was started. Recommended branch disposition: `HOLD`.

## Repository baseline

- Required base branch: `main`
- Local `main`: `e41181bbdcb79c6d8dffc5353b00755dfc2893bb`
- `origin/main`: `e41181bbdcb79c6d8dffc5353b00755dfc2893bb`
- Characterization branch: `track-c3-1-scanner-daily-correctness-characterization`
- Initial branch HEAD: `e41181bbdcb79c6d8dffc5353b00755dfc2893bb`
- Baseline suite: 1,452 tests, 0 failures, 0 errors, 0 expected failures, `OK`
- Initial working tree: clean
- `custom_md.md`: ignored only by `.git/info/exclude`; its contents were not accessed

## LLM Wiki result

- Health: available; `ok: true`, `status: running`, version `0.5.4`
- Active project: `tw_stock_tool Wiki`
- Search: `scanner daily report analyze_stock RSI code-path inference integration testing`
- Summary: results covered Scanner/Analysis flow, report generation, tests/CI,
  data-pipeline partial-failure isolation, and research-only boundaries. The
  Wiki was supporting context only; repository source, tests, and Track C1/C2
  documents remained authoritative.

## Existing coverage inventory

| Area | Existing evidence | Boundary before Track C3.1 |
| --- | --- | --- |
| RSI indicators | Direct rising, falling, flat, and mixed `_rsi` tests | Direct indicator evidence |
| Analysis | Track C1 patches only `download_tw_stock` and exercises real Analysis | Direct through Analysis |
| Scanner | Existing tests patch `scanner.analyze_stock` or `scan_one_stock` | Mocked below Analysis |
| Daily Report | Existing tests use synthetic ranking frames | No real Analysis/Scanner path |
| Daily Report CLI | Existing tests patch `run_daily_report` | Mocked integration |
| Analysis test module | No `tests/test_analysis.py` exists | Equivalent direct coverage is in Track C1 |

The proposed Scanner and Daily Report integration cases were not already
covered directly. Mocked `analyze_stock()` tests were not treated as proof of
indicator-to-Scanner integration.

## Direct integration path tested

The new module patches only `tw_stock_tool.analysis.analysis.download_tw_stock`
and exercises the real chain:

```text
download boundary
-> analyze_stock
-> add_indicators
-> generate_signals
-> scan_one_stock
-> scan_stocks
-> run_daily_report
```

All generated OHLCV data is deterministic and offline. No TWSE, TPEx, Yahoo
Finance, or other network market data was accessed.

## Finding matrix

| ID | Area | Scenario | Expected contract | Observed behavior | Evidence type | Classification | Downstream impact | Future action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C3.1-A | Scanner/RSI | Continuous rise | Ready row survives with RSI 100 and usable rank fields | `OK`, empty error, RSI 100, latest row ranked, critical fields finite | Direct deterministic integration | `CORRECTLY_HANDLED` | Track C2.2 survives through Scanner | None |
| C3.1-B | Scanner/flat indicators | Zero-range flat OHLCV | RSI 50 and ranking-critical values remain usable | `OK`; RSI 50; Score, Volume Ratio, Close, RSI, ATR finite; exported K/D are `NaN` | Direct deterministic integration | `CONTRACT_UNDECIDED` | Daily candidate fields remain usable; K/D consumers may see `NaN` | Decide K/D export contract before any fix |
| C3.1-C | Scanner failures | Two valid stocks and one controlled failure | Failure is isolated and valid rows remain deterministically ranked | Valid rows rank 1/2; failed row is last, unranked, with retained message | Direct deterministic integration | `CORRECTLY_HANDLED` | Partial failure does not terminate scan | None |
| C3.1-D | Daily Report | Mixed universe | Summary/candidates exclude failed values but retain failure evidence | 3 scanned, 2 candidates; counts and averages match candidates; limitation contains failure | Direct deterministic integration | `CORRECTLY_HANDLED` | Honest report data remains constructible | None |
| C3.1-E | Interval | `interval="1wk"` | Existing interval reaches download boundary | Scanner and Daily Report each pass `1wk` to download | Direct deterministic integration | `CORRECTLY_HANDLED` | Existing weekly path is preserved | None |
| C3.1-F1 | Scanner input | Empty lower-level input | Empty input is explicitly rejected | `ValueError` raised before any download | Direct deterministic integration | `CORRECTLY_HANDLED` | No fabricated result | None |
| C3.1-F2 | Scanner/Daily Report | Every stock fails | Structured errors and honest zero-candidate report | Sorted ERROR rows, no ranks/scores, zero candidates/averages, messages retained | Direct deterministic integration | `CORRECTLY_HANDLED` | Report construction survives total data failure | None |

## Continuous-rise result

The Scanner returns one `OK` row with an empty error field, latest date
`2024-05-09`, RSI exactly `100.0`, rank 1, and finite Score, Volume Ratio, RSI,
Close, and ATR. This directly proves the Track C2.2 gain-only RSI correction
survives Analysis and Scanner.

## Flat-price result

A 130-row zero-range flat OHLCV series remains available as an `OK` Scanner
row. RSI is exactly `50.0`; Score, Volume Ratio, RSI, Close, and ATR are finite.
The stochastic denominator is zero, so exported `K` and `D` are `NaN`.

The repository establishes the RSI and ranking contracts but does not state
whether non-ranking stochastic export fields must be finite for zero-range
bars. The overall scenario is therefore `CONTRACT_UNDECIDED`; no expected
failure or production correction is justified by current evidence.

## Mixed-universe result

Two stocks use real internal Analysis while one download raises a controlled
exception. The valid rows remain ranked in deterministic Score/Stock order.
The failed row is last, has `Status == "ERROR"`, retains `controlled download
failure`, and receives neither a valid rank nor a valid score. Successful row
count is two.

## Daily Report result

`run_daily_report()` uses the same three-stock mixed universe without mocking
`scan_stocks()`. `Stocks Scanned` is three; the two valid rows are candidates
under the explicit all-signal/minimum-score test selection; the failed stock is
excluded. Candidate, BUY, and WATCH counts match the candidate table, averages
match candidate values only, the full ranking retains the ERROR row, and
`build_data_limitations_from_ranking()` exposes its exact message. In-memory
`build_daily_report_data()` succeeds. No Excel or Markdown output was written.

## Interval propagation result

Separate direct tests show Scanner and Daily Report propagate the existing
`interval="1wk"` value to `download_tw_stock`. No Backtest metric or additional
workflow option was involved.

## Empty and all-failed result

The lower-level Scanner API explicitly rejects an empty input with `ValueError`.
For a non-empty all-failed universe, Scanner returns deterministic structured
ERROR rows with no ranks or scores. Daily Report reports two stocks scanned,
zero candidates, zero BUY/WATCH counts, and zero averages while retaining both
failure messages. No successful result is fabricated.

## Expected-failure inventory

- Before: 0
- After: 0
- Confirmed defects: 0
- Contract-undecided findings: 1

No `@unittest.expectedFailure` was added because no supported correctness
contract was directly violated.

## Direct evidence versus inference

All required A-F scenarios now have direct deterministic tests through their
stated internal boundaries. The only unresolved point is normative rather than
inferential: current behavior for zero-range stochastic K/D is directly proven,
but the desired export contract is not established. File-writing behavior was
not required to characterize the in-memory Daily Report integration and is
covered separately by existing exporter tests.

## Production files changed

None.

## Test files changed

- `tests/test_track_c3_1_scanner_daily_correctness.py` (new; 9 tests)

## Documentation files changed

- `docs/TRACK_C3_1_SCANNER_DAILY_CORRECTNESS_CHARACTERIZATION.md` (new)

Existing Track C1 and Track C2 historical documents were not modified.

## Validation commands

- Baseline: `py -m unittest discover -s tests` - 1,452 tests, `OK`
- New module: `py -m unittest tests.test_track_c3_1_scanner_daily_correctness` - 9 tests, `OK`
- Combined targeted: `py -m unittest tests.test_track_c3_1_scanner_daily_correctness tests.test_indicators tests.test_signals tests.test_scanner tests.test_daily_report tests.test_daily_report_builder tests.test_daily_report_cli tests.test_track_c1_research_correctness` - 80 tests, `OK`
- Final full suite: `py -m unittest discover -s tests` - 1,461 tests, 0 failures, 0 errors, 0 expected failures, `OK`
- Repository-required suite: `python -m unittest discover -s tests` - 1,461 tests, 0 failures, 0 errors, 0 expected failures, `OK`
- `git diff --check` - passed
- UTF-8 BOM verification - passed for both new files; neither has a UTF-8 BOM

## Non-goals

This track did not modify production code, behavior, CLI behavior, dependencies,
configuration, reports, exports, schemas, providers, Backtest, strategies, or
signals. It did not access live market data, add public arguments, expand
interval support, start a production fix, merge the branch, push `main`, delete
branches, or start Track C3.2. `custom_md.md` was not accessed or changed.

## Recommended next action

Hold this characterization branch for review. If reviewers establish a finite
K/D export contract for zero-range bars, plan a separate bounded production-fix
phase. Otherwise no production action is indicated. Branch disposition: `HOLD`.
