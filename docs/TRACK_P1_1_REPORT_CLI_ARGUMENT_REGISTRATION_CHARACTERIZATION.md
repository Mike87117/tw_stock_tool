# Track P1.1 — Shared Report CLI Argument Registration Characterization

## 1. Executive outcome

The three real report parsers were characterized without changing production code. Parser metadata, complete default and explicit Namespace mappings, output tri-state behavior, help output, package-module help, root-wrapper help, and argparse failure behavior are frozen by the new test module.

There are 64 project-defined add_argument registration lines across the three parsers and 58 registration lines belonging to options repeated across parser modules. The largest exact-order-preserving one-helper design can safely cover only the four output/refresh options. Its gross eligible block is 12 lines, its conservative replacement is 9 lines, and its net reduction is 3 lines. The permitted abstraction is below the 10-line decision threshold.

## 2. Formal result

**Track P1.1 Characterization: PASS -- DECISION RECORDED**

## 3. Repository baseline

Approved parent commit:

69929deab29d66ec8ce2cd15826329c21e18a9f3

Approved parent branch:

audit-ponytail-repository-overengineering

The parent contains the reviewed Ponytail audit and is one documentation-only commit above the required main baseline.

## 4. Stacked parent relationship

Before branch creation:

- HEAD on the approved parent was 69929deab29d66ec8ce2cd15826329c21e18a9f3.
- main was dde23346d60bf67f38ecc01f6ec138643cfdbc52.
- origin/main was dde23346d60bf67f38ecc01f6ec138643cfdbc52.
- The approved parent branch tracked its pushed remote branch.
- The working tree was clean.

The characterization branch was created directly from the approved parent:

track-p1-1-report-cli-argument-registration-characterization

## 5. Ponytail audit finding

This phase addressed only PT-AUDIT-001 from the parent audit:

- src/tw_stock_tool/cli/backtest_report.py
- src/tw_stock_tool/cli/parameter_sweep_report.py
- src/tw_stock_tool/cli/walk_forward_report.py

No other Ponytail finding was investigated. Ponytail was not run again. No production helper was implemented.

## 6. Working-tree and ignored-file protection

The user-owned ignored file custom_md.md was not inspected, modified, deleted, staged, restored, or cleaned. git clean was not run. Only the two newly authorized files were added.

## 7. LLM Wiki availability result

No LLM Wiki service or connector was available in the session. This was non-blocking. Repository source, existing tests, README examples, and the parent audit were treated as authoritative.

## 8. Production files inspected

Read-only inspection covered:

- src/tw_stock_tool/cli/backtest_report.py
- src/tw_stock_tool/cli/parameter_sweep_report.py
- src/tw_stock_tool/cli/walk_forward_report.py
- src/tw_stock_tool/cli/parsers.py
- src/tw_stock_tool/cli/twstock_cli.py
- backtest_report.py
- parameter_sweep_report.py
- walk_forward_report.py
- relevant README command examples and package metadata.

No production file was modified.

## 9. Existing test coverage inventory

Existing tests already protect the surrounding behavior:

- tests/test_backtest_report_cli.py covers Backtest parser basics, output paths, report execution, and runtime status 1.
- tests/test_parameter_sweep_report_cli.py covers Parameter Sweep parser defaults, ranges, output paths, preflight behavior, and runtime status 1.
- tests/test_walk_forward_report_cli.py covers Walk Forward parser defaults, ranges, window values, output paths, and runtime status 1.
- tests/test_twstock_cli.py covers unified route registration, passthrough arguments, help, child status propagation, and argv restoration.
- tests/test_root_wrappers.py covers report root-wrapper help and wrapper resolution.
- tests/test_root_cli_wrapper_exit_codes.py covers root-wrapper help status 0, handled failure status 1, and import identity.

The new module adds parser-focused characterization rather than duplicating report execution tests.

## 10. Existing characterization gaps

Before this phase, the repository did not freeze:

- every parser action’s complete metadata;
- complete default Namespace mappings for all three parsers;
- complete explicit Namespace mappings;
- exact help text under deterministic width;
- package-module and root-wrapper help equivalence;
- a uniform matrix of argparse status-2 failures across all three modules;
- the distinction between scalar Backtest RSI/score options and tuple-based Sweep/Walk Forward options.

## 11. Parser metadata extraction method

The test module temporarily replaces the argparse.ArgumentParser constructor with a local factory that calls the real constructor and records the resulting parser. The production _parse_args functions are called unchanged.

The normalized action representation records option strings, destination, requiredness, action class, nargs, const, default and default type, type callable, choices, metavar, and help text.

The built-in -h/--help action is included and separately identified as _HelpAction. COLUMNS=120 and deterministic sys.argv[0] values are used for help snapshots.

## 12. Backtest Report parser inventory

Registration order is:

--stock, --strategy, --period, --initial-capital, --output-md, --output-excel, --output-dir, --force-refresh, --short-window, --long-window, --rsi-buy-below, --rsi-sell-above, --score-buy, --score-sell, --fee-rate, --tax-rate, --position-size, --stop-loss-pct, --take-profit-pct, --max-hold-days.

The parser has description Backtest Report Generator and epilog Backtest fills use next-bar Open as a research assumption. Backtest RSI, score, and short/long options are scalar values. Backtest engine defaults are literal values, and its engine options have explicit help text.

## 13. Parameter Sweep parser inventory

Registration order is:

--stock, --strategy, --period, --output-md, --output-excel, --output-dir, --force-refresh, --ma-short-windows, --ma-long-windows, --rsi-buy-below, --rsi-sell-above, --score-buy, --score-sell, --initial-capital, --fee-rate, --tax-rate, --position-size, --stop-loss-pct, --take-profit-pct, --max-hold-days.

The parser has description Parameter Sweep Report CLI and no epilog. Range arguments use tw_stock_tool.cli.parsers.parse_int_tuple. Engine defaults are configuration-backed for initial capital, fee rate, and tax rate, with explicit help text.

## 14. Walk Forward parser inventory

Registration order is:

--stock, --strategy, --period, --output-md, --output-excel, --output-dir, --force-refresh, --ma-short-windows, --ma-long-windows, --rsi-buy-below, --rsi-sell-above, --score-buy, --score-sell, --train-days, --test-days, --step-days, --sort-by, --initial-capital, --fee-rate, --tax-rate, --position-size, --stop-loss-pct, --take-profit-pct, --max-hold-days.

The parser has description Walk Forward Report CLI and no epilog. Its range arguments use parse_int_tuple. Its window arguments default to 504 training days, 126 test days, None step days, and Train Sharpe Ratio sort order. Its engine arguments have no help text.

## 15. Full option-difference matrix

Classification is based on option metadata and registration order. The project-defined count excludes the built-in help action.

| Option | Presence | Classification | Exact observation |
|---|---|---|---|
| -h, --help | All three | EXACTLY_SHARED_ALL_THREE | Built-in _HelpAction; excluded from project-defined count. |
| --stock | All three | EXACTLY_SHARED_ALL_THREE | Same position, destination, requiredness, type, default, and help. |
| --strategy | All three | SHARED_ALL_THREE_WITH_METADATA_DIFFERENCE | Backtest help omits ", all"; Sweep/Walk include it. |
| --period | All three | EXACTLY_SHARED_ALL_THREE | Same position, default source, type, and help. |
| --output-md | All three | SHARED_ALL_THREE_WITH_METADATA_DIFFERENCE | Action metadata matches, but Backtest registration order is shifted by --initial-capital. |
| --output-excel | All three | SHARED_ALL_THREE_WITH_METADATA_DIFFERENCE | Same order difference as --output-md. |
| --output-dir | All three | SHARED_ALL_THREE_WITH_METADATA_DIFFERENCE | Same order difference as --output-md. |
| --force-refresh | All three | SHARED_ALL_THREE_WITH_METADATA_DIFFERENCE | Same action metadata, but registration position differs. |
| --initial-capital | All three | SHARED_ALL_THREE_WITH_METADATA_DIFFERENCE | Backtest literal 100000.0 and help differ from config-backed integer 100000; Walk has no help. |
| --fee-rate | All three | SHARED_ALL_THREE_WITH_METADATA_DIFFERENCE | Backtest help says backtest assumption; Sweep config help; Walk no help. |
| --tax-rate | All three | SHARED_ALL_THREE_WITH_METADATA_DIFFERENCE | Backtest help says backtest assumption; Sweep config help; Walk no help. |
| --position-size | All three | SHARED_ALL_THREE_WITH_METADATA_DIFFERENCE | Backtest, Sweep, and Walk help text differ. |
| --stop-loss-pct | All three | SHARED_ALL_THREE_WITH_METADATA_DIFFERENCE | Backtest, Sweep, and Walk help text differ. |
| --take-profit-pct | All three | SHARED_ALL_THREE_WITH_METADATA_DIFFERENCE | Backtest, Sweep, and Walk help text differ. |
| --max-hold-days | All three | SHARED_ALL_THREE_WITH_METADATA_DIFFERENCE | Backtest, Sweep, and Walk help text differ. |
| --rsi-buy-below | All three | SAME_NAME_DIFFERENT_SEMANTICS | Backtest scalar float default 30.0; Sweep/Walk tuple parser default None. |
| --rsi-sell-above | All three | SAME_NAME_DIFFERENT_SEMANTICS | Backtest scalar float default 70.0; Sweep/Walk tuple parser default None. |
| --score-buy | All three | SAME_NAME_DIFFERENT_SEMANTICS | Backtest scalar float default None; Sweep/Walk tuple parser default None. |
| --score-sell | All three | SAME_NAME_DIFFERENT_SEMANTICS | Backtest scalar float; Sweep/Walk tuple parser with negative values. |
| --ma-short-windows | Sweep and Walk | EXACTLY_SHARED_SWEEP_AND_WALK_FORWARD | Same parser, type, default, help, and relative order. |
| --ma-long-windows | Sweep and Walk | EXACTLY_SHARED_SWEEP_AND_WALK_FORWARD | Same parser, type, default, help, and relative order. |
| --short-window | Backtest only | BACKTEST_ONLY | Scalar integer with default 5. |
| --long-window | Backtest only | BACKTEST_ONLY | Scalar integer with default 20. |
| --train-days | Walk only | WALK_FORWARD_ONLY | Integer default 504. |
| --test-days | Walk only | WALK_FORWARD_ONLY | Integer default 126. |
| --step-days | Walk only | WALK_FORWARD_ONLY | Integer default None. |
| --sort-by | Walk only | WALK_FORWARD_ONLY | String default Train Sharpe Ratio. |

Counts:

- Exactly shared across all three project-defined options: 2; plus 1 built-in help action.
- Shared across all three with metadata/order differences: 12.
- Same name with different semantics: 4.
- Exactly shared only by Sweep and Walk Forward: 2.
- Backtest-only: 2.
- Parameter-Sweep-only: 0.
- Walk-Forward-only: 4.

## 16. Complete default Namespace snapshots

Minimal invocation for every parser:

--stock 2330 --strategy ma_cross

Backtest Report:

~~~json
{
  "stock": "2330",
  "strategy": "ma_cross",
  "period": "1y",
  "initial_capital": 100000.0,
  "output_md": null,
  "output_excel": null,
  "output_dir": "output",
  "force_refresh": false,
  "short_window": 5,
  "long_window": 20,
  "rsi_buy_below": 30.0,
  "rsi_sell_above": 70.0,
  "score_buy": null,
  "score_sell": null,
  "fee_rate": 0.001425,
  "tax_rate": 0.003,
  "position_size": 1.0,
  "stop_loss_pct": null,
  "take_profit_pct": null,
  "max_hold_days": null
}
~~~

Parameter Sweep:

~~~json
{
  "stock": "2330",
  "strategy": "ma_cross",
  "period": "1y",
  "output_md": null,
  "output_excel": null,
  "output_dir": "output",
  "force_refresh": false,
  "ma_short_windows": null,
  "ma_long_windows": null,
  "rsi_buy_below": null,
  "rsi_sell_above": null,
  "score_buy": null,
  "score_sell": null,
  "initial_capital": 100000,
  "fee_rate": 0.001425,
  "tax_rate": 0.003,
  "position_size": 1.0,
  "stop_loss_pct": null,
  "take_profit_pct": null,
  "max_hold_days": null
}
~~~

Walk Forward:

~~~json
{
  "stock": "2330",
  "strategy": "ma_cross",
  "period": "1y",
  "output_md": null,
  "output_excel": null,
  "output_dir": "output",
  "force_refresh": false,
  "ma_short_windows": null,
  "ma_long_windows": null,
  "rsi_buy_below": null,
  "rsi_sell_above": null,
  "score_buy": null,
  "score_sell": null,
  "train_days": 504,
  "test_days": 126,
  "step_days": null,
  "sort_by": "Train Sharpe Ratio",
  "initial_capital": 100000,
  "fee_rate": 0.001425,
  "tax_rate": 0.003,
  "position_size": 1.0,
  "stop_loss_pct": null,
  "take_profit_pct": null,
  "max_hold_days": null
}
~~~

These are complete vars(namespace) snapshots, not selected-field assertions.

## 17. Complete explicit Namespace snapshots

The explicit invocation supplies every parser-specific field, output paths, refresh, tuple ranges, and engine/window values. The test freezes the complete mappings. The resulting differences are:

- Backtest retains scalar RSI/score values and scalar MA windows.
- Sweep and Walk retain tuples from parse_int_tuple, including whitespace-trimmed values and negative score values.
- Walk additionally retains train_days=252, test_days=63, step_days=21, and sort_by="Train Total Return %".
- All three retain exact output strings and force_refresh=True.

The complete explicit dictionaries are frozen in EXPLICIT_NAMESPACES in the new test module, including every key and value; no selected-field-only assertion is used.

## 18. Output tri-state results

For each parser and each output option:

| State | --output-md / --output-excel result |
|---|---|
| Absent | None |
| Bare flag | "" |
| Explicit path | Exact supplied string, such as custom/report.md or custom/report.xlsx |

--output-dir custom/output remains the exact string custom/output. --force-refresh is False when omitted and True when supplied.

## 19. Help-output results

Each real parser was invoked with deterministic program names and COLUMNS=120.

- All three help calls exit with SystemExit(0).
- Help is written to stdout.
- stderr is empty.
- Option order, descriptions, epilog, defaults, and omitted/default-display behavior are frozen exactly in HELP_SNAPSHOTS.
- Backtest includes its research-assumption epilog.
- Sweep and Walk have no epilog.
- Walk engine options display no help text, which is intentionally preserved.

## 20. Package-module help results

These commands returned status 0 with no stderr and matched the in-process snapshots after normalizing only the usage program-name token:

~~~text
python -m tw_stock_tool.cli.backtest_report --help
python -m tw_stock_tool.cli.parameter_sweep_report --help
python -m tw_stock_tool.cli.walk_forward_report --help
~~~

No report execution, filesystem output, or market request occurs on these help paths.

## 21. Root-wrapper help results

These commands returned status 0 with no stderr and matched the corresponding package snapshots after normalizing only the usage program-name token:

~~~text
python backtest_report.py --help
python parameter_sweep_report.py --help
python walk_forward_report.py --help
~~~

The wrappers remain thin compatibility entry points and were not modified.

## 22. Argparse failure results

For all three parsers, the new tests cover missing --stock, missing --strategy, invalid integer, invalid float, and unknown option. Sweep and Walk additionally cover invalid integer tuple input.

Every case:

- exits with status 2;
- contains usage output;
- contains an argparse error;
- contains no traceback;
- calls only the parser path, not a production runtime function;
- creates no file in the isolated temporary directory used by the test.

Tuple behavior also covers one-value tuples, multiple-value tuples, whitespace trimming, negative scores, and exact parse_int_tuple metadata.

## 23. Existing public route confirmation

The following remain present and callable:

- root wrappers backtest_report.py, parameter_sweep_report.py, and walk_forward_report.py;
- package parser modules under tw_stock_tool.cli;
- unified routes twstock backtest-report, twstock parameter-sweep, and twstock walk-forward.

The new route test inspects unified passthrough parsing without invoking report execution. Existing tests continue to protect actual routing, output paths, and runtime status 1.

## 24. Exactly shared arguments

By complete metadata and position, the exactly shared project-defined options across all three are:

- --stock
- --period

The built-in help action is also identical but is excluded from the project-defined count. Output and refresh options have identical local action metadata but are shifted in Backtest registration order by --initial-capital, so they are not classified as exact all-three matches.

## 25. Metadata-different arguments

The 12 all-three options with differences are:

- --strategy — help wording;
- --output-md, --output-excel, --output-dir, --force-refresh — registration order;
- --initial-capital, --fee-rate, --tax-rate, --position-size, --stop-loss-pct, --take-profit-pct, --max-hold-days — help text, default source/type, or both.

The configuration-backed defaults must not be treated as equivalent to Backtest literal defaults merely because resulting numbers are close or equal.

## 26. Same-name/different-semantics arguments

The four RSI/score options are not safe common registrations:

- Backtest --rsi-buy-below and --rsi-sell-above are scalar floats with defaults 30.0 and 70.0.
- Sweep/Walk versions are tuple ranges using parse_int_tuple with default None.
- Backtest score options are scalar floats.
- Sweep/Walk score options are integer tuples and explicitly support negative values.

## 27. CLI-specific arguments

Backtest-only options are --short-window and --long-window.

Walk-Forward-only options are --train-days, --test-days, --step-days, and --sort-by.

No Parameter-Sweep-only option exists in the current parser definitions.

## 28. Hypothetical helper shape

The only behavior-preserving one-helper design that keeps exact registration order without a metadata table or mode switch is a small output/refresh helper in the existing src/tw_stock_tool/cli/parsers.py:

~~~python
def add_report_output_arguments(parser):
    parser.add_argument("--output-md", nargs="?", const="", default=None, help="Export Markdown report")
    parser.add_argument("--output-excel", nargs="?", const="", default=None, help="Export Excel report")
    parser.add_argument("--output-dir", default="output", help="Default output directory")
    parser.add_argument("--force-refresh", action="store_true", help="Redownload data ignoring cache")
~~~

It would be called at the corresponding order point in each parser. Sweep and Walk already import from parsers.py; Backtest would add one import. This design uses one helper, no metadata argument, no factory, no table, and no public export.

A helper containing all seven base options would not preserve Backtest order because Backtest inserts --initial-capital between --period and the output block. Preserving that order with one helper would require multiple calls, a mode switch, or multiple helpers, which the approved design explicitly excludes.

## 29. Helper-complexity assessment

The narrow output/refresh helper is simpler than a metadata framework and does not require a new production module. It still provides only a small reduction because the largest shared group is interrupted by Backtest-specific registration.

Including strategy help, configuration-backed defaults, engine help, or tuple ranges would require additional metadata or branching and would be comparable in complexity to the duplication. That design is rejected by the phase constraints.

## 30. Gross duplicated-line count

Mechanical count using rg -c "parser\\.add_argument":

- Backtest Report: 20 registration lines.
- Parameter Sweep: 20 registration lines.
- Walk Forward: 24 registration lines.
- Total project-defined registration lines: **64**.
- Repeated-option registration lines across modules: **58**.

The 58-line gross figure includes all repeated options, including metadata-different engine options and same-name/different-semantics RSI/score options. It is not an approved removal estimate.

## 31. Replacement-line count

For the only order-preserving one-helper design:

- helper signature: 1 line;
- helper body: 4 add_argument lines;
- three call sites: 3 lines;
- new Backtest import: 1 line;
- Sweep and Walk extend their existing parser import line rather than adding a new line;
- no new dependency.

Conservative replacement cost: **9 production lines**.

The eligible current block is the four output/refresh options registered three times: **12 gross lines**. The Backtest DEFAULT_PERIOD import is retained for --period, and Sweep/Walk configuration and parse_int_tuple imports remain needed by other local definitions.

## 32. Conservative net reduction

Eligible gross block: **12 lines**.

Hypothetical replacement: **9 lines**.

Conservative net removable production lines: **3 lines**.

This is below the required 10-line threshold. The full 58-line repeated-option inventory cannot be counted because preserving its behavior would require multiple helpers, metadata switches, or semantic changes.

## 33. Behavior-preservation risks

The relevant risks are now characterized rather than assumed:

- exact Backtest registration order differs because --initial-capital interrupts the common output block;
- strategy help differs;
- engine default source and default type differ;
- Walk engine help is omitted;
- Backtest RSI/score arguments are scalar while Sweep/Walk versions are tuples;
- tuple whitespace and negative-value parsing are observable;
- bare output flags produce empty strings rather than None;
- argparse failures must remain status 2 with usage and error output;
- package and root help must remain equivalent apart from program-name usage text;
- unified routes and root-wrapper compatibility remain outside the proposed change.

## 34. Decision-gate evaluation

The one-helper proposal:

- uses the existing parsers.py;
- requires no dependency;
- can preserve help and order for the four-option output/refresh block;
- does not change public APIs or _parse_args behavior;
- is simpler than a table or parser factory;
- produces only 3 conservative net lines.

The required 10-line minimum is not met. A broader helper would require multiple mode switches, multiple helper calls/functions, or metadata collections and would violate the approved design.

## 35. Final outcome

CLOSE_PT_AUDIT_001

The characterization is complete, the behavior is frozen, and the finding should not proceed to a production helper phase. No production cleanup was implemented.

## 36. Exact files changed

Only these two files were added:

- tests/test_track_p1_1_report_cli_argument_registration_characterization.py
- docs/TRACK_P1_1_REPORT_CLI_ARGUMENT_REGISTRATION_CHARACTERIZATION.md

No existing file was modified.

## 37. Targeted test result

Command:

~~~text
py -m unittest tests.test_track_p1_1_report_cli_argument_registration_characterization
~~~

Result: **9 tests passed**.

## 38. Combined test result

Command:

~~~text
py -m unittest tests.test_track_p1_1_report_cli_argument_registration_characterization tests.test_backtest_report_cli tests.test_parameter_sweep_report_cli tests.test_walk_forward_report_cli tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes
~~~

Result: **127 tests passed**.

## 39. Full-suite results

Canonical command:

~~~text
py -m unittest discover -s tests
~~~

Result: **1,608 tests passed**.

Secondary command:

~~~text
python -m unittest discover -s tests
~~~

Result: **1,608 tests passed**.

No expected failures were added. The suites completed with existing warning output only. No live market request was made by the characterization tests.

## 40. git diff --check result

PASS — no whitespace errors.

## 41. UTF-8 BOM result

PASS — both added files are UTF-8 without a BOM.

## 42. No-production-change confirmation

PASS — no production file, existing test, README, existing report, configuration, dependency, lock file, CI file, package metadata, root wrapper, unified route, or ignored/user-owned file was modified. No production helper was implemented. No persistent output or cache artifact was retained by the branch.

## 43. Branch disposition

One tests-and-documentation-only commit is to be created on track-p1-1-report-cli-argument-registration-characterization and pushed without merging. The branch remains held for review. Do not continue to a production helper phase.

Track P1.1 Characterization: PASS -- DECISION RECORDED
Branch disposition: HOLD
Final outcome: CLOSE_PT_AUDIT_001
No production cleanup was implemented.
