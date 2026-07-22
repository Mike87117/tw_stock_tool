# Track P2.1 - Unified CLI Passthrough Registration Characterization

## 1. Executive outcome

The complete current unified CLI parser and dispatcher was characterized from the approved P1.1 parent. The parser exposes 17 top-level entries, including the non-executable stock-list container, and 19 executable command forms. The registration order, help text, descriptions, nested parser structure, callable targets, child program names, passthrough storage, lazy-import timing, status propagation, SystemExit behavior, sys.argv restoration, and public wrapper boundaries are covered by the new characterization tests.

One private helper is sufficient for the 17 direct passthrough routes, including the two routes whose imports remain inside _parse_args(). The two custom stock-list runner registrations and the nested parser container remain explicit. The mechanically counted eligible cost is 92 production lines. A concrete six-line helper plus 17 one-line call sites is 23 replacement lines, yielding a conservative net reduction of 69 production lines. This clears the 10-line decision gate without a route table, metadata framework, command-name branching, dependency change, or public API change.

The characterization decision is:

PROCEED_TO_P2_2

No production cleanup was implemented in this phase.

## 2. Formal result

Track P2.1 Characterization: PASS -- DECISION RECORDED

## 3. Repository baseline

Approved stacked parent branch:

track-p1-1-report-cli-argument-registration-characterization

Approved parent commit:

5934de37640d3ac141dc4ca8068dac10ee40a250

The parent branch and its origin-tracking branch were verified at the exact parent commit. The main baseline remained:

main == origin/main == dde23346d60bf67f38ecc01f6ec138643cfdbc52

The current branch was created directly from the approved parent:

track-p2-1-unified-cli-passthrough-registration-characterization

The working tree was clean before the two approved files were added.

## 4. Stacked parent relationship

The stack used for this phase is:

1. Reviewed Ponytail repository audit.
2. Reviewed P1.1 report-CLI argument-registration characterization.
3. P1.1 final outcome: CLOSE_PT_AUDIT_001.
4. P2.1 unified CLI passthrough-registration characterization.

No P2.2 implementation was started.

## 5. P1.1 closure confirmation

The P1.1 characterization remains closed as CLOSE_PT_AUDIT_001. Its report and test were treated as read-only parent evidence. Neither was modified.

## 6. Ponytail finding

This phase addresses only PT-AUDIT-002.

Original Ponytail tag: shrink.

Original audit disposition: ACCEPT_NEEDS_CHARACTERIZATION.

Ponytail-audit skill availability: available in the current Codex session. The prior repository audit used the exact invocation @ponytail-audit in audit mode. P2.1 did not invoke Ponytail again, as explicitly required.

The candidate is repeated unified CLI passthrough registration in src/tw_stock_tool/cli/twstock_cli.py. No other Ponytail finding was investigated.

## 7. Working-tree and ignored-file protection

The ignored, user-owned file custom_md.md was not inspected, modified, staged, restored, deleted, or cleaned. git clean was not run. No existing repository file was modified.

Only these two files are in scope for this phase:

* tests/test_track_p2_1_unified_cli_passthrough_registration_characterization.py
* docs/TRACK_P2_1_UNIFIED_CLI_PASSTHROUGH_REGISTRATION_CHARACTERIZATION.md

## 8. LLM Wiki availability result

No local LLM Wiki service or callable LLM Wiki tool was available in the current session. This was non-blocking. Repository source, existing tests, and deterministic subprocess probes were authoritative.

## 9. Production files inspected

The following production and packaging boundaries were inspected read-only:

* src/tw_stock_tool/cli/twstock_cli.py
* twstock_cli.py
* src/tw_stock_tool/__main__.py (confirmed absent)
* src/tw_stock_tool/cli/__init__.py
* pyproject.toml
* README.md
* Child modules referenced by the unified dispatcher, only for callable identity, program name, import timing, and return behavior.

The root wrapper imports tw_stock_tool.cli.twstock_cli, re-exports it for imports, and calls package main() when executed as a script. pyproject.toml maps twstock to tw_stock_tool.cli.twstock_cli:main.

## 10. Existing tests inspected

Relevant existing tests inspected:

* tests/test_twstock_cli.py
* tests/test_root_wrappers.py
* tests/test_root_cli_wrapper_exit_codes.py
* tests/test_track_c9_1_smoke_check_cli_runtime_exit_behavior.py
* tests/test_track_p1_1_report_cli_argument_registration_characterization.py
* tests/test_cli_wrapper_inventory.py (not present in this baseline)

Existing tests already covered representative unified routes, root wrapper identity, help/status behavior, and subprocess boundaries. The new test adds a complete deterministic parser-tree and route-target characterization without executing child workflows.

## 11. Current parser architecture

tw_stock_tool.cli.twstock_cli currently:

1. Builds an argparse.ArgumentParser with description Unified tw_stock_tool CLI.
2. Adds a required top-level subparser action with destination command.
3. Adds the stock-list container with a required nested subparser action with destination stock_list_command.
4. Uses parse_known_args(argv) and stores the untouched remaining list in args.args.
5. Binds direct routes to _dispatch_existing_main(module_main, program_name, args.args).
6. Binds stock-list update and stock-list smoke-check through _run_stock_list_update and _run_stock_list_smoke_check.
7. Uses _patched_argv() to set the child program name and restore the original sys.argv in a finally block.
8. Imports simulated_paper_trading_cli and backtest_result_export_cli inside _parse_args().

The proposed helper can call the existing dispatcher directly. It does not need to alter _patched_argv, _dispatch_existing_main, custom runners, imports, or package exports.

## 12. Top-level route inventory

The parser has 17 top-level entries. stock-list is a required command container and is not itself executable.

| Order | Entry | Executable | Help |
|---:|---|---|---|
| 1 | doctor | yes | Check local environment |
| 2 | scan | yes | Run multi-stock technical scanner |
| 3 | daily | yes | Run daily candidate report |
| 4 | stock-list | no, nested container | Stock-list utilities |
| 5 | price-smoke-check | yes | Smoke check price data sources |
| 6 | ai-scan | yes | Run multi-stock AI baseline scanner |
| 7 | cache | yes | Manage price data cache |
| 8 | benchmark | yes | Run multi-stock scanner benchmark |
| 9 | analyze | yes | Run single-stock analysis |
| 10 | strategy-compare | yes | Run strategy comparison |
| 11 | parameter-sweep | yes | Run parameter sweep |
| 12 | backtest-report | yes | Run backtest report |
| 13 | walk-forward | yes | Run walk forward report |
| 14 | simulated-paper-trading | yes | Run historical simulated paper trading |
| 15 | simulated-paper-trading-export | yes | Export reports from a simulated paper trading JSON artifact |
| 16 | backtest-artifact | yes | Validate or inspect BacktestResult JSON artifacts |
| 17 | backtest-result-export | yes | Export historical BacktestResult JSON artifact |

## 13. Nested route inventory

stock-list has a required nested subparser action with destination stock_list_command.

| Nested order | Route | Help |
|---:|---|---|
| 1 | stock-list update | Update stocks.txt from official sources |
| 2 | stock-list smoke-check | Smoke check official stock-list sources |
| 3 | stock-list clean | Clean stock list |

## 14. Executable command-form count

There are 16 executable top-level commands plus 3 executable nested commands: 19 executable command forms total.

## 15. Registration-order snapshot

The deterministic parser snapshot records:

* Root description: Unified tw_stock_tool CLI.
* Root subparser destination: command.
* Root subparser requiredness: True.
* Exact root order: doctor, scan, daily, stock-list, price-smoke-check, ai-scan, cache, benchmark, analyze, strategy-compare, parameter-sweep, backtest-report, walk-forward, simulated-paper-trading, simulated-paper-trading-export, backtest-artifact, backtest-result-export.
* Nested destination: stock_list_command.
* Nested requiredness: True.
* Exact nested order: update, smoke-check, clean.
* Every executable child has a handler default.
* The stock-list container has nested subparsers but no executable handler.
* No aliases are registered.

Registration order is observable in both top-level and nested help output and is therefore a compatibility boundary.

## 16. Complete route matrix

In this table, the symbol P means the exact direct-route probe list ["--flag", "value", "--output-md", "report.md", "--option=-2", "artifact.json"]. U means ["--flag", "value", "stocks.txt", "--option=-2"] for update. S means ["--flag", "value", "source.json"] for smoke-check.

All rows use the same status contract: child None becomes unified status 0; child integer 0, 1, or 7 is returned unchanged; child SystemExit(2) or another code is propagated unchanged; and the original sys.argv is restored.

| Route | Level/order | Help | Description | Child callable | Child program name | Registration form | Import timing | Passthrough behavior |
|---|---|---|---|---|---|---|---|---|
| doctor | top/1 | Check local environment | None | tw_stock_tool.utils.doctor.main | doctor.py | direct _dispatch_existing_main | module-level | P |
| scan | top/2 | Run multi-stock technical scanner | None | tw_stock_tool.cli.scan_stocks.main | scan_stocks.py | direct _dispatch_existing_main | module-level | P |
| daily | top/3 | Run daily candidate report | None | tw_stock_tool.cli.daily_report_cli.main | daily_report_cli.py | direct _dispatch_existing_main | module-level | P |
| stock-list update | nested/1 | Update stocks.txt from official sources | None | tw_stock_tool.data.stock_list_updater.main | stock_list_updater.py | custom _run_stock_list_update | module-level | U |
| stock-list smoke-check | nested/2 | Smoke check official stock-list sources | None | tw_stock_tool.cli.stock_list_smoke_check.main | stock_list_smoke_check.py | custom _run_stock_list_smoke_check | module-level | S |
| stock-list clean | nested/3 | Clean stock list | None | tw_stock_tool.cli.clean_stocks.main | clean_stocks.py | direct _dispatch_existing_main | module-level | P |
| price-smoke-check | top/5 | Smoke check price data sources | None | tw_stock_tool.cli.price_data_smoke_check.main | price_data_smoke_check.py | direct _dispatch_existing_main | module-level | P |
| ai-scan | top/6 | Run multi-stock AI baseline scanner | None | tw_stock_tool.ml.ai_stock_scanner.main | ai_stock_scanner.py | direct _dispatch_existing_main | module-level | P |
| cache | top/7 | Manage price data cache | None | tw_stock_tool.data.cache_manager.main | cache_manager.py | direct _dispatch_existing_main | module-level | P |
| benchmark | top/8 | Run multi-stock scanner benchmark | None | tw_stock_tool.cli.benchmark.main | benchmark.py | direct _dispatch_existing_main | module-level | P |
| analyze | top/9 | Run single-stock analysis | None | tw_stock_tool.cli.main.main | main.py | direct _dispatch_existing_main | module-level | P |
| strategy-compare | top/10 | Run strategy comparison | None | tw_stock_tool.backtesting.strategy_compare.main | strategy_compare.py | direct _dispatch_existing_main | module-level | P |
| parameter-sweep | top/11 | Run parameter sweep | None | tw_stock_tool.cli.parameter_sweep_report.main | parameter_sweep_report.py | direct _dispatch_existing_main | module-level | P |
| backtest-report | top/12 | Run backtest report | None | tw_stock_tool.cli.backtest_report.main | backtest_report.py | direct _dispatch_existing_main | module-level | P |
| walk-forward | top/13 | Run walk forward report | None | tw_stock_tool.cli.walk_forward_report.main | walk_forward_report.py | direct _dispatch_existing_main | module-level | P |
| simulated-paper-trading | top/14 | Run historical simulated paper trading | Run research-only simulated paper trading over historical data.<br>Does not connect to brokers, place real orders, or provide investment advice. | tw_stock_tool.cli.simulated_paper_trading_cli.main | simulated_paper_trading_cli.py | direct _dispatch_existing_main | inside _parse_args() | P |
| simulated-paper-trading-export | top/15 | Export reports from a simulated paper trading JSON artifact | Export reports from an existing research-only simulated paper trading JSON artifact.<br>Does not fetch market data, run strategies, connect to brokers, or place orders. | tw_stock_tool.cli.simulated_paper_trading_export_cli.main | simulated_paper_trading_export_cli.py | direct _dispatch_existing_main | module-level | P |
| backtest-artifact | top/16 | Validate or inspect BacktestResult JSON artifacts | Validate or inspect existing research-only BacktestResult JSON artifacts.<br>Does not fetch market data, run strategies, execute backtests, connect to brokers, place orders, produce live signals, or provide investment advice. | tw_stock_tool.cli.backtest_artifact_cli.main | backtest_artifact_cli.py | direct _dispatch_existing_main | module-level | P |
| backtest-result-export | top/17 | Export historical BacktestResult JSON artifact | Export a structured BacktestResult JSON artifact from a historical backtest execution.<br>This is a historical backtest artifact for offline research only. Not investment advice. | tw_stock_tool.cli.backtest_result_export_cli.main | backtest_result_export_cli.py | direct _dispatch_existing_main | inside _parse_args() | P |

## 17. Route classification

| Classification | Count | Routes |
|---|---:|---|
| STANDARD_TOP_LEVEL_PASSTHROUGH | 12 | doctor, scan, daily, price-smoke-check, ai-scan, cache, benchmark, analyze, strategy-compare, parameter-sweep, backtest-report, walk-forward |
| STANDARD_TOP_LEVEL_WITH_DESCRIPTION | 2 | simulated-paper-trading-export, backtest-artifact |
| NESTED_STANDARD_PASSTHROUGH | 1 | stock-list clean |
| NESTED_CUSTOM_RUNNER | 2 | stock-list update, stock-list smoke-check |
| LAZY_IMPORTED_STANDARD | 0 | none |
| LAZY_IMPORTED_WITH_DESCRIPTION | 2 | simulated-paper-trading, backtest-result-export |

Fifteen executable routes have only help metadata and no description: the 12 ordinary top-level routes and the 3 nested routes. Four executable routes also have descriptions. The non-executable stock-list container has its own help metadata.

## 18. Handler target results

The new test calls real twstock_cli.main(argv) for every direct route and intercepts _dispatch_existing_main. Each direct route bound the exact expected module main callable, exact synthetic child program name, and exact remaining argument list exactly once.

The two custom routes were called through real unified main(argv) and intercepted at their distinct _run_* intermediary. They were not rewritten to fit the direct helper shape.

## 19. Child program-name results

The exact values passed into _patched_argv() are:

* doctor.py
* scan_stocks.py
* daily_report_cli.py
* stock_list_updater.py
* stock_list_smoke_check.py
* clean_stocks.py
* price_data_smoke_check.py
* ai_stock_scanner.py
* cache_manager.py
* benchmark.py
* main.py
* strategy_compare.py
* parameter_sweep_report.py
* backtest_report.py
* walk_forward_report.py
* simulated_paper_trading_cli.py
* simulated_paper_trading_export_cli.py
* backtest_artifact_cli.py
* backtest_result_export_cli.py

## 20. Passthrough results

parse_known_args() preserves remaining arguments in order and assigns them to args.args. Characterization inputs included ordinary flags, values, optional output flags, positional paths, nested route tokens, unknown child flags, and a negative numeric form using --option=-2. The direct and custom route assertions verified exact lists without executing child workflows.

## 21. Status-propagation results

Representative routes from every registration category were tested with child returns None, 0, 1, and 7. The unified result was respectively 0, 0, 1, and 7. The same representatives raised SystemExit(2) and SystemExit(23); both codes propagated unchanged.

## 22. sys.argv restoration results

For every status and exception case, the original process sys.argv was equal to its pre-dispatch value after twstock_cli.main(argv) returned or raised. The child-facing values were exactly [child_program_name, *passthrough_args].

## 23. Top-level help snapshot

With sys.argv[0] = twstock and COLUMNS=120, the exact top-level help is:

~~~text
usage: twstock [-h]
               {doctor,scan,daily,stock-list,price-smoke-check,ai-scan,cache,benchmark,analyze,strategy-compare,parameter-sweep,backtest-report,walk-forward,simulated-paper-trading,simulated-paper-trading-export,backtest-artifact,backtest-result-export}
               ...

Unified tw_stock_tool CLI

positional arguments:
  {doctor,scan,daily,stock-list,price-smoke-check,ai-scan,cache,benchmark,analyze,strategy-compare,parameter-sweep,backtest-report,walk-forward,simulated-paper-trading,simulated-paper-trading-export,backtest-artifact,backtest-result-export}
    doctor              Check local environment
    scan                Run multi-stock technical scanner
    daily               Run daily candidate report
    stock-list          Stock-list utilities
    price-smoke-check   Smoke check price data sources
    ai-scan             Run multi-stock AI baseline scanner
    cache               Manage price data cache
    benchmark            Run multi-stock scanner benchmark
    analyze             Run single-stock analysis
    strategy-compare    Run strategy comparison
    parameter-sweep     Run parameter sweep
    backtest-report     Run backtest report
    walk-forward        Run walk forward report
    simulated-paper-trading
                        Run historical simulated paper trading
    simulated-paper-trading-export
                        Export reports from a simulated paper trading JSON artifact
    backtest-artifact   Validate or inspect BacktestResult JSON artifacts
    backtest-result-export
                        Export historical BacktestResult JSON artifact

options:
  -h, --help            show this help message and exit
~~~

## 24. Stock-list help snapshot

The exact nested container help is:

~~~text
usage: twstock stock-list [-h] {update,smoke-check,clean} ...

positional arguments:
  {update,smoke-check,clean}
    update              Update stocks.txt from official sources
    smoke-check         Smoke check official stock-list sources
    clean               Clean stock list

options:
  -h, --help            show this help message and exit
~~~

## 25. Safety-description help results

The exact top-level safety-description help is:

~~~text
usage: twstock simulated-paper-trading [-h]

Run research-only simulated paper trading over historical data. Does not connect to brokers, place real orders, or
provide investment advice.

options:
  -h, --help  show this help message and exit
~~~

The artifact/export category was also frozen by the exact backtest-artifact snapshot in the new test:

~~~text
usage: twstock backtest-artifact [-h]

Validate or inspect existing research-only BacktestResult JSON artifacts. Does not fetch market data, run strategies,
execute backtests, connect to brokers, place orders, produce live signals, or provide investment advice.

options:
  -h, --help  show this help message and exit
~~~

## 26. Parser failure results

The following inputs were characterized through twstock_cli.main(argv):

* no command
* unknown top-level command
* stock-list without a nested command
* unknown nested stock-list command

Every case raised SystemExit(2), emitted usage/error output, emitted no traceback, and did not call the child dispatcher. No child workflow, external request, or persistent artifact was created.

## 27. Lazy-import inventory

The only imports performed inside _parse_args() are:

* from tw_stock_tool.cli import simulated_paper_trading_cli
* from tw_stock_tool.cli import backtest_result_export_cli

In clean subprocess probes, both modules were absent from sys.modules before parsing. Both became present after unrelated doctor parsing and after top-level --help parsing. The helper can preserve this behavior by leaving both existing import statements in their current location and calling the helper only after each import. No import move is required.

## 28. Public invocation-boundary inventory

| Boundary | Result |
|---|---|
| python -m tw_stock_tool | Not present in this baseline: src/tw_stock_tool/__main__.py does not exist. This phase did not add or alter it. |
| python -m tw_stock_tool.cli.twstock_cli | Present; --help exited 0. |
| python twstock_cli.py | Present root compatibility wrapper; --help exited 0. |
| twstock | Present installed console entry point; --help exited 0. pyproject.toml maps it to tw_stock_tool.cli.twstock_cli:main. |

The missing package-level __main__.py is an existing repository fact outside PT-AUDIT-002 and was not changed.

## 29. Existing coverage versus new coverage

Existing tests cover representative dispatch, root wrapper identity, wrapper exit status, help behavior, and smoke-check subprocess boundaries. The new test adds:

* normalized parser-tree capture from real argparse objects;
* complete 19-route inventory and exact order;
* exact callable and child-program mapping for every route;
* distinction between direct dispatch and custom runners;
* representative passthrough values including --option=-2;
* full shared status and sys.argv restoration matrix;
* deterministic top-level, nested, safety, and artifact help snapshots;
* exact parser failure status 2 and no-child-dispatch controls;
* clean-subprocess lazy-import probes for unrelated parsing and help;
* root, module, and console invocation-boundary checks.

No invocation-boundary coverage was removed or weakened.

## 30. Hypothetical helper shape

The only evaluated helper is a private local helper inside src/tw_stock_tool/cli/twstock_cli.py:

~~~python
def _add_passthrough_parser(subparsers, name, module_main, program_name, help_text, description=None):
    parser_kwargs = {"help": help_text}
    if description is not None:
        parser_kwargs["description"] = description
    parser = subparsers.add_parser(name, **parser_kwargs)
    parser.set_defaults(handler=lambda args: _dispatch_existing_main(module_main, program_name, args.args))
~~~

This is a shape evaluation only. It was not added to production. It creates one parser, binds one handler, accepts the permitted optional description, and reuses the existing dispatcher.

## 31. Helper eligibility by route

Eligible routes: all 17 direct dispatcher routes, including both lazy-imported routes. Their existing imports remain explicit and in place:

* 12 STANDARD_TOP_LEVEL_PASSTHROUGH routes;
* 2 STANDARD_TOP_LEVEL_WITH_DESCRIPTION routes;
* 1 NESTED_STANDARD_PASSTHROUGH route;
* 2 LAZY_IMPORTED_WITH_DESCRIPTION routes.

Retained explicit routes:

* stock-list container and nested parser setup;
* stock-list update custom runner;
* stock-list smoke-check custom runner.

No route table, dataclass, metadata dictionary, parser factory, helper variant, command-name conditional, plugin mechanism, or import relocation is required.

## 32. Helper complexity assessment

The helper is simpler than the repeated direct registration blocks because one six-line local body handles both top-level and nested subparser actions, optional descriptions, and the existing dispatcher. The call sites retain the exact route order and literal help/description text. The two custom runners remain readable and explicit. Lazy imports remain visibly adjacent to their calls. This is a local helper, not a generalized CLI framework.

## 33. Total repeated registration LOC

Source file: src/tw_stock_tool/cli/twstock_cli.py.

* Total source lines: 194.
* Parser registrations: 20 .add_parser(...) calls.
* Handler registrations: 19 .set_defaults(...) calls.
* Total registration-block physical lines, including multiline formatting and ineligible setup: 101.

The 101-line count covers the exact registration block ranges from lines 65-181, excluding unrelated imports, blank lines, _patched_argv, _dispatch_existing_main, custom runner definitions, and parser finalization.

## 34. Helper-eligible LOC

The helper-eligible cost is 92 physical production lines:

* 17 direct route registration blocks;
* all their related multiline add_parser(...) and set_defaults(...) formatting;
* no imports;
* no parser container setup;
* no custom _run_* intermediary blocks.

The excluded 9 physical lines are the stock-list container/nested-subparser setup and the two custom runner registration blocks.

## 35. Replacement LOC

The concrete replacement cost is:

* 6 lines for the private helper signature/body, including optional description handling;
* 17 one-line helper call sites;
* 0 new imports;
* 0 route-table or metadata-framework lines.

Replacement total: 23 production lines.

## 36. Conservative net reduction

92 eligible lines - 23 replacement lines = 69 net removable production lines.

This is a hypothetical estimate only. It is not an implemented reduction and does not count the nine retained explicit lines as removable.

## 37. Behavior-preservation risks

The characterization identified and covered the relevant risks:

* top-level and nested registration order is observable;
* exact help strings and safety/artifact descriptions are observable;
* parse_known_args() passthrough storage is an interface to child CLIs;
* synthetic child program names affect child parser behavior and diagnostics;
* exact callable identity matters for route dispatch;
* custom stock-list runners are semantically distinct;
* lazy imports occur while the complete parser is built, including for unrelated commands and help;
* None, integer, and SystemExit results cross the dispatcher boundary;
* _patched_argv must restore process state after both returns and exceptions;
* root wrapper and console-entry-point mappings are public compatibility boundaries.

The proposed helper avoids these risks by leaving the dispatcher, argv context manager, import statements, custom runners, route literals, and call order unchanged.

## 38. Decision-gate evaluation

| Gate | Result |
|---|---|
| One helper sufficient | Pass for 17 direct routes; custom runners remain explicit |
| Exact command order | Pass; helper calls follow current order |
| Exact help and descriptions | Pass; literals pass directly to add_parser |
| Nested structure | Pass; helper accepts either subparser action |
| Callable and program-name mapping | Pass; both are direct helper arguments |
| Lazy-import timing | Pass; existing imports remain before helper calls |
| Status and SystemExit propagation | Pass; existing _dispatch_existing_main remains unchanged |
| No route table or metadata framework | Pass |
| Helper simpler than explicit registration | Pass |
| Conservative net reduction at least 10 lines | Pass; 69 lines |
| Dependency or public API change required | No |

## 39. Final outcome

PROCEED_TO_P2_2

This records authorization for a later, separately scoped production phase only. P2.2 was not started here.

## 40. Exact files changed

Only these files were added:

* tests/test_track_p2_1_unified_cli_passthrough_registration_characterization.py
* docs/TRACK_P2_1_UNIFIED_CLI_PASSTHROUGH_REGISTRATION_CHARACTERIZATION.md

No existing file was modified.

## 41. Targeted test result

Command:

py -m unittest tests.test_track_p2_1_unified_cli_passthrough_registration_characterization

Result: PASS, 9 tests.

The equivalent discovery form also passed 9 tests.

## 42. Combined test result

Command:

~~~text
py -m unittest tests.test_track_p2_1_unified_cli_passthrough_registration_characterization tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_track_c9_1_smoke_check_cli_runtime_exit_behavior tests.test_track_p1_1_report_cli_argument_registration_characterization
~~~

Result: PASS, 98 tests.

## 43. Full-suite results

Both required full-suite commands were executed:

* py -m unittest discover -s tests: PASS, 1,617 tests.
* python -m unittest discover -s tests: PASS, 1,617 tests.

The observed output came from existing mocked/offline test fixtures; no live market service was requested by this characterization.

## 44. git diff --check

Result: PASS. No whitespace errors.

## 45. UTF-8 BOM result

Both added files are UTF-8 without a BOM.

## 46. No-production-change confirmation

PASS. No production code, existing test, README, existing documentation, configuration, dependency file, lock file, CI file, package metadata, wrapper, import, public API, generated artifact, or user-owned ignored file was modified. No cleanup recommendation was implemented.

## 47. Branch disposition

One tests-and-documentation-only commit is to be created on:

track-p2-1-unified-cli-passthrough-registration-characterization

The branch is held for review. Do not merge, rebase, squash, force-push, or begin P2.2 from this phase.

## Exact commands used

~~~text
git fetch origin
git checkout track-p1-1-report-cli-argument-registration-characterization
git rev-parse HEAD
git rev-parse HEAD^
git rev-parse origin/track-p1-1-report-cli-argument-registration-characterization
git rev-parse main
git rev-parse origin/main
git checkout -b track-p2-1-unified-cli-passthrough-registration-characterization
git status --short
git ls-files
rg -n "add_parser|set_defaults" src/tw_stock_tool/cli/twstock_cli.py
py -m unittest tests.test_track_p2_1_unified_cli_passthrough_registration_characterization
py -m unittest tests.test_track_p2_1_unified_cli_passthrough_registration_characterization tests.test_twstock_cli tests.test_root_wrappers tests.test_root_cli_wrapper_exit_codes tests.test_track_c9_1_smoke_check_cli_runtime_exit_behavior tests.test_track_p1_1_report_cli_argument_registration_characterization
py -m unittest discover -s tests
python -m unittest discover -s tests
git diff --check
git status --short
~~~

The tracked-file and LOC inventory used one inline Python command over git ls-files -z; it decoded UTF-8 tracked text files, skipped binary files, counted splitlines(), and created no permanent script.

## Appendix A - Raw Ponytail Audit Output

The original Ponytail output is preserved below exactly as inherited from the reviewed repository audit. Ponytail was not invoked again in P2.1.

~~~text
shrink repeated backtest/strategy CLI argument registration. Share one internal argument-builder helper across report CLIs. [src/tw_stock_tool/cli/backtest_report.py, src/tw_stock_tool/cli/parameter_sweep_report.py, src/tw_stock_tool/cli/walk_forward_report.py]
shrink repeated unified CLI passthrough registration. Add one internal registration helper. [src/tw_stock_tool/cli/twstock_cli.py]
shrink duplicated offline subprocess/test-environment setup. Share one test helper without removing boundary coverage. [tests/test_track_c4_1_scanner_cli_exit_behavior.py, tests/test_track_c5_1_cache_manager_cli_entrypoint_exit_behavior.py, tests/test_track_c6_1_benchmark_cli_runtime_exit_behavior.py, tests/test_track_c7_1_clean_stocks_cli_runtime_exit_behavior.py, tests/test_track_c8_1_stock_list_updater_cli_runtime_exit_behavior.py, tests/test_track_c9_1_smoke_check_cli_runtime_exit_behavior.py]
shrink repeated serialization file-boundary wrappers. Introduce one schema-parameterized internal file helper. [src/tw_stock_tool/backtesting/serialization_files.py, src/tw_stock_tool/paper_trading/serialization_files.py]
shrink provider/cache/orchestration responsibility concentration. Extract provider and cache seams. [src/tw_stock_tool/data/data_loader.py]
shrink report builder/render/write responsibility concentration. Split one report at a time. [src/tw_stock_tool/reports/backtest_report.py, src/tw_stock_tool/reports/parameter_sweep_report.py, src/tw_stock_tool/reports/walk_forward_report.py, src/tw_stock_tool/reports/daily_report.py]
shrink large GUI controller/service modules. Split feature responsibilities. [src/tw_stock_tool/gui/gui_app.py, src/tw_stock_tool/gui/app_services.py]
yagni duplicate dependency declarations. Choose one dependency source of truth. [requirements.txt, pyproject.toml]
delete root compatibility wrappers. Remove redirect files. [root-level Python wrappers]
shrink historical README and phase-documentation volume. Reorganize navigation and archive history. [README.md, docs/]
yagni thin safety, validation, schema, and status-propagation boundaries. Merge boundary layers. [src/tw_stock_tool/paper_trading/, src/tw_stock_tool/risk/, src/tw_stock_tool/kill_switch/, tests/]
net: -350 lines, -0 deps possible.
~~~

Track P2.1 Characterization: PASS -- DECISION RECORDED
Branch disposition: HOLD
Final outcome: PROCEED_TO_P2_2
No production cleanup was implemented.
