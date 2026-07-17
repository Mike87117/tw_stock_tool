# Track P2.2 - Unified CLI Passthrough Registration Helper

## 1. Executive outcome

Implemented the single approved private helper in src/tw_stock_tool/cli/twstock_cli.py. Exactly 17 direct-dispatch routes now use it. The stock-list container, stock-list update, and stock-list smoke-check remain explicit.

The characterized behavior is preserved. Production source size changed from 194 lines to 176 lines: 84 gross lines removed, 66 added, for an actual net reduction of 18 production lines. This is lower than the P2.1 hypothetical 69-line reduction because readable multiline helper calls were retained, but it remains above the required 10-line gate.

## 2. Formal result

Track P2.2 Implementation: PASS -- READY FOR REVIEW

## 3. Repository baseline

Required parent commit:

93050beff9565cbe8a19d0bca4bf96a9a14d272c

Required parent branch:

track-p2-1-unified-cli-passthrough-registration-characterization

The parent branch and origin ref were verified at the exact commit. The stacked main baseline remained:

main == origin/main == dde23346d60bf67f38ecc01f6ec138643cfdbc52

The implementation branch was created directly from the exact P2.1 parent:

track-p2-2-unified-cli-passthrough-registration-helper

## 4. Stacked parent relationship

The stack is:

1. Reviewed Ponytail repository audit.
2. P1.1 characterization, closed as CLOSE_PT_AUDIT_001.
3. P2.1 characterization, decision PROCEED_TO_P2_2.
4. This P2.2 helper implementation.

## 5. P1.1 closure preservation

P1.1 remains closed as CLOSE_PT_AUDIT_001. Its report and tests were not modified.

## 6. P2.1 characterization decision

P2.1 recorded PROCEED_TO_P2_2 after proving that one private helper could cover the 17 direct routes, preserve lazy-import timing, retain custom runners, and exceed the 10-line reduction gate.

## 7. Working-tree and ignored-file protection

custom_md.md was not inspected, modified, staged, restored, deleted, or cleaned. git clean was not run.

Only the three approved files changed:

* src/tw_stock_tool/cli/twstock_cli.py
* tests/test_track_p2_1_unified_cli_passthrough_registration_characterization.py
* docs/TRACK_P2_2_UNIFIED_CLI_PASSTHROUGH_REGISTRATION_HELPER.md

## 8. LLM Wiki availability result

No local LLM Wiki service or callable LLM Wiki tool was available. This was non-blocking. Repository source and tests were authoritative.

The Ponytail audit skill was available and read for this task. Ponytail was not invoked again because P2.2 explicitly prohibits another audit invocation.

## 9. Exact production scope

Only PT-AUDIT-002 was addressed. No child CLI parser, wrapper, package entry point, dispatcher, argv context manager, custom runner, dependency, public API, or unrelated Ponytail finding was changed.

## 10. Helper signature

The implemented private helper is:

~~~python
def _add_passthrough_parser(subparsers, name, module_main, program_name, help_text, description=None) -> None:
~~~

It is local to tw_stock_tool.py and introduces no public type or export.

## 11. Helper behavior

The helper:

* builds one child parser with subparsers.add_parser;
* always passes the exact help_text as help;
* adds description only when description is not None;
* binds one handler calling _dispatch_existing_main(module_main, program_name, args.args);
* returns None;
* leaves _dispatch_existing_main unchanged.

No route table, dataclass, parser factory, loop, conditional, callback lookup, dynamic import, or new module was added.

## 12. Converted route inventory

Exactly 17 direct-dispatch executable routes now call the helper:

* doctor
* scan
* daily
* price-smoke-check
* ai-scan
* cache
* benchmark
* analyze
* strategy-compare
* parameter-sweep
* backtest-report
* walk-forward
* simulated-paper-trading-export
* backtest-artifact
* stock-list clean
* simulated-paper-trading
* backtest-result-export

## 13. Explicit retained route inventory

These structures remain explicit and unchanged:

* stock-list top-level parser;
* required nested stock_list_command subparser;
* stock-list update registration;
* stock-list smoke-check registration;
* _run_stock_list_update;
* _run_stock_list_smoke_check.

The remaining explicit registrations are six nonblank parser/handler statements: the top-level container, nested subparser action, and two parser-plus-handler pairs for the custom routes.

## 14. Route-order preservation

Top-level order remains:

doctor, scan, daily, stock-list, price-smoke-check, ai-scan, cache, benchmark, analyze, strategy-compare, parameter-sweep, backtest-report, walk-forward, simulated-paper-trading, simulated-paper-trading-export, backtest-artifact, backtest-result-export.

Nested order remains:

update, smoke-check, clean.

The P2.1 parser-tree and help snapshots passed unchanged.

## 15. Help-string preservation

All command names and help strings remain literal-equivalent. The targeted characterization suite passed exact top-level and nested help snapshots, including order and argparse wrapping.

## 16. Description preservation

The four descriptions remain exact, including safety wording, punctuation, capitalization, and embedded newline behavior:

* simulated-paper-trading;
* simulated-paper-trading-export;
* backtest-artifact;
* backtest-result-export.

The helper omits description when it is None and passes each existing literal unchanged when present.

## 17. Callable mapping preservation

Each converted call passes the same module main callable previously bound by the explicit registration. No callable was replaced by a string, import path, wrapper, lookup, or partial.

## 18. Child program-name preservation

All existing synthetic child program names remain unchanged, including doctor.py, scan_stocks.py, daily_report_cli.py, clean_stocks.py, price_data_smoke_check.py, ai_stock_scanner.py, cache_manager.py, benchmark.py, main.py, strategy_compare.py, parameter_sweep_report.py, backtest_report.py, walk_forward_report.py, simulated_paper_trading_cli.py, simulated_paper_trading_export_cli.py, backtest_artifact_cli.py, and backtest_result_export_cli.py.

## 19. Lazy-import preservation

These imports remain inside _parse_args() and immediately precede their helper registrations:

* from tw_stock_tool.cli import simulated_paper_trading_cli
* from tw_stock_tool.cli import backtest_result_export_cli

The clean-subprocess probes continue to show that both modules become imported during unrelated parser construction and top-level help. No import moved to module scope.

## 20. Passthrough preservation

parse_known_args() and args.args remain unchanged. The characterization suite passed ordinary flags, values, output flags, positional paths, nested commands, unknown child flags, and --option=-2 in the original order.

## 21. Status-propagation preservation

The combined and full suites passed. The characterized dispatcher contract remains:

* child None becomes unified status 0;
* child integer results propagate exactly;
* child SystemExit codes propagate exactly.

## 22. sys.argv restoration preservation

_patched_argv and the dispatcher were not modified. The P2.1 tests passed restoration checks after both normal returns and SystemExit exceptions.

## 23. Public invocation-boundary preservation

The helper did not modify:

* the root twstock_cli.py wrapper;
* pyproject.toml console entry-point mapping;
* python -m tw_stock_tool behavior;
* python -m tw_stock_tool.cli.twstock_cli;
* python twstock_cli.py;
* twstock.

The package-level __main__.py remains absent as an existing baseline fact outside this phase.

## 24. Characterization-test adaptation

Only the source-structure inventory assertions in tests/test_track_p2_1_unified_cli_passthrough_registration_characterization.py were adapted:

* one helper definition;
* 18 occurrences of the helper name, accounting for one definition plus 17 calls;
* four remaining .add_parser occurrences;
* three remaining .set_defaults occurrences;
* explicit stock-list container and custom runner assertions;
* no route removed;
* no test method removed;
* all nine tests remain ordinary passing tests.

All behavioral snapshots and route mappings remain intact.

## 25. Production lines before

The exact P2.1 parent production file had 194 UTF-8 source lines.

## 26. Production lines after

The implemented production file has 176 UTF-8 source lines.

## 27. Actual gross removed lines

Git diff for src/tw_stock_tool/cli/twstock_cli.py reports 84 removed lines.

## 28. Actual added lines

Git diff for src/tw_stock_tool/cli/twstock_cli.py reports 66 added lines.

The helper definition occupies 6 physical lines. The 17 helper call sites occupy 62 physical lines because the described routes retain readable multiline calls.

## 29. Actual net reduction

194 before - 176 after = 18 net production lines removed.

## 30. Predicted-versus-actual comparison

| Measure | P2.1 prediction | P2.2 actual |
|---|---:|---:|
| Production lines before | 194 | 194 |
| Production lines after | 125 hypothetical | 176 |
| Replacement lines | 23 | 66 added diff lines |
| Gross removed lines | 92 eligible | 84 |
| Net reduction | 69 | 18 |

The actual result is smaller than the one-line-call-site estimate because the implementation retained readable multiline calls for descriptions and complex registrations. It still exceeds the required 10-line gate and requires only one helper.

## 31. Exact files changed

Only:

* src/tw_stock_tool/cli/twstock_cli.py
* tests/test_track_p2_1_unified_cli_passthrough_registration_characterization.py
* docs/TRACK_P2_2_UNIFIED_CLI_PASSTHROUGH_REGISTRATION_HELPER.md

## 32. Targeted test result

Command:

~~~text
py -m unittest tests.test_track_p2_1_unified_cli_passthrough_registration_characterization
~~~

Result: PASS, 9 tests.

## 33. Combined test result

Result: PASS, 98 tests.

Command:

~~~text
py -m unittest tests.test_track_p2_1_unified_cli_passthrough_registration_characterization tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_track_c9_1_smoke_check_cli_runtime_exit_behavior tests.test_track_p1_1_report_cli_argument_registration_characterization
~~~

## 34. Full-suite results

Both required full suites passed:

* py -m unittest discover -s tests: PASS, 1,617 tests.
* python -m unittest discover -s tests: PASS, 1,617 tests.

The observed workflow output came from existing mocked/offline fixtures. No live market service was accessed.

## 35. git diff --check

Result: PASS. No whitespace errors.

## 36. UTF-8 BOM result

All three changed files are UTF-8 without BOM.

## 37. No-unrelated-change confirmation

PASS. No unrelated production file, test, report, README, wrapper, package boundary, configuration, dependency, lock file, generated artifact, or user-owned ignored file changed. No later Ponytail finding was started.

## 38. Branch disposition

The implementation branch is ready for review:

track-p2-2-unified-cli-passthrough-registration-helper

No merge, rebase, squash, force-push, pull request, or later phase was started.

## Exact commands used

~~~text
git fetch origin
git checkout track-p1-1-report-cli-argument-registration-characterization
git status --short
git rev-parse HEAD
git rev-parse origin/track-p2-1-unified-cli-passthrough-registration-characterization
git rev-parse main
git rev-parse origin/main
git checkout -b track-p2-2-unified-cli-passthrough-registration-helper 93050beff9565cbe8a19d0bca4bf96a9a14d272c
py -m unittest tests.test_track_p2_1_unified_cli_passthrough_registration_characterization
py -m unittest tests.test_track_p2_1_unified_cli_passthrough_registration_characterization tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_track_c9_1_smoke_check_cli_runtime_exit_behavior tests.test_track_p1_1_report_cli_argument_registration_characterization
py -m unittest discover -s tests
python -m unittest discover -s tests
git diff --check
git status --short
~~~

Track P2.2 Implementation: PASS -- READY FOR REVIEW
Branch disposition: READY FOR REVIEW
No later Ponytail finding was started.
