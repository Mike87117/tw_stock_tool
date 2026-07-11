# Backtest Compatibility Contract

## A. Contract status

Phase A2 decision: **INSUFFICIENT_EVIDENCE_RETAIN_TEMPORARILY**. A3 defines boundaries only; it authorizes no migration or deprecation.

## B. Contract classification vocabulary

| Classification | Concrete examples | Contract strength | Permitted action in A3 |
|---|---|---|---|
| SUPPORTED_CANONICAL | canonical backtesting imports and result identity | public/application boundary | protect only |
| INTERNAL_CONSUMER_CONTRACT | concrete CLI, serialization, converter consumers | internal, not automatically public | protect only |
| TEMPORARY_COMPATIBILITY_RETAINED | alternate engine and BaseStrategy imports | unknown external usage | retain import |
| CHARACTERIZED_NOT_GUARANTEED | alternate NaN-open propagation | observed risk, not promise | document only |
| NOT_SUPPORTED | alternate result serialization/conversion | explicitly rejected | do not add support |

## C. Canonical backtest contract

Canonical `run_backtest`, `run_backtest_result`, `BacktestError`, `BacktestResult`, strategies, serialization, and serialization_files own artifacts, reports, CLI, and conversion boundaries.

## D. Alternate temporary retention contract

Alternate `BacktestEngine`, alternate `BacktestResult`, and `BaseStrategy` remain importable only as temporary compatibility retention. They are not canonical and their results are rejected by canonical serialization and conversion.

## E. Root-wrapper contract

`backtest.py` redirects to `tw_stock_tool.backtesting.backtest`; `strategies.py` redirects to `tw_stock_tool.backtesting.strategies`. Changing either is breaking.

## F. Consumer evidence matrix

| Consumer file/module | Consumer type | Imported symbol | Canonical source | Runtime purpose | Artifact/report impact | Existing test evidence | Contract classification | Breaking-change risk |
|---|---|---|---|---|---|---|---|---|
| src/tw_stock_tool/cli/backtest_result_export_cli.py | CLI | run_backtest_result | backtesting.backtest | JSON export | artifact writer | export CLI tests | INTERNAL_CONSUMER_CONTRACT | High |
| src/tw_stock_tool/cli/backtest_artifact_cli.py | Artifact CLI | loader, converter | serialization_files, paper_trading | inspect/convert | artifact conversion | artifact CLI tests | INTERNAL_CONSUMER_CONTRACT | High |
| src/tw_stock_tool/cli/backtest_report.py | Report CLI | run_backtest | backtesting.backtest | report execution | report output | report tests | INTERNAL_CONSUMER_CONTRACT | High |
| src/tw_stock_tool/backtesting/serialization.py | Serialization | BacktestResult | backtesting.results | JSON schema | writer/reader | serialization tests | INTERNAL_CONSUMER_CONTRACT | High |
| src/tw_stock_tool/backtesting/serialization_files.py | Artifact | BacktestResult | results/serialization | file boundary | loader identity | file tests | INTERNAL_CONSUMER_CONTRACT | High |
| src/tw_stock_tool/backtesting/parameter_sweep.py | Runtime | run_backtest | backtesting.backtest | sweep | report inputs | sweep tests | INTERNAL_CONSUMER_CONTRACT | High |
| src/tw_stock_tool/backtesting/strategy_compare.py | Report | run_backtest | backtesting.backtest | compare | report inputs | compare tests | INTERNAL_CONSUMER_CONTRACT | High |
| src/tw_stock_tool/backtesting/walk_forward.py | Walk-forward | run_backtest | backtesting.backtest | walk-forward | report inputs | walk-forward tests | INTERNAL_CONSUMER_CONTRACT | High |
| src/tw_stock_tool/gui/app_services.py | Runtime | run_backtest | backtesting.backtest | GUI service | display | app services tests | INTERNAL_CONSUMER_CONTRACT | High |
| src/tw_stock_tool/cli/main.py | Runtime CLI | run_backtest | backtesting.backtest | analysis | report inputs | main tests | INTERNAL_CONSUMER_CONTRACT | High |
| src/tw_stock_tool/paper_trading/backtest_converter.py | Conversion | BacktestResult | backtesting.results | simulation conversion | typed conversion | converter tests | INTERNAL_CONSUMER_CONTRACT | High |

## G. Result identity and artifact contract

Canonical and alternate result classes are distinct. Canonical artifact readers return canonical results; serialization and conversion reject alternate results. Metadata, integer quantities, canonical trade fields, and equity values are contract-protected.

## H. Stable and unstable behavior

Canonical imports, root targets, artifact identity, and converter input are stable. Alternate NaN-open propagation is characterized but not guaranteed.

## I. Breaking-change catalogue

| Change | Why breaking | Required contract tests | Required migration documentation | Compatibility window required | Dedicated production phase required | Rollback consideration |
|---|---|---|---|---|---|---|
| Change root backtest.py target | import break | wrapper identity | import migration | Yes | Yes | restore target |
| Change root strategies.py target | import break | wrapper identity | import migration | Yes | Yes | restore target |
| Change canonical BacktestResult identity | consumer break | identity | release notes | Yes | Yes | retain class |
| Allow alternate serialization | type boundary | rejection | contract update | Yes | Yes | reject alternate |
| Change loader return type | artifact break | round-trip | artifact migration | Yes | Yes | retain reader |
| Change converter input type | conversion break | converter | conversion migration | Yes | Yes | retain type check |
| Remove BacktestEngine path | external risk | import retention | deprecation | Yes | Yes | shim |
| Remove BaseStrategy path | external risk | import retention | deprecation | Yes | Yes | shim |
| Rename canonical fields | result break | result tests | field migration | Yes | Yes | aliases |
| Change converter trade columns | conversion break | converter | schema migration | Yes | Yes | old columns |
| Change integer shares | semantic break | converter | semantic migration | Yes | Yes | adapter |
| Change metadata semantics | artifact break | round-trip | metadata migration | Yes | Yes | preserve fields |
| Move consumers to alternate engine | semantic break | AST tests | migration plan | Yes | Yes | restore import |
| Add ambiguous result exports | identity ambiguity | import identity | API docs | Yes | Yes | remove export |

## J. Allowed additive changes

New tests, documentation, additive metadata, and named adapters may be reviewed separately. None are implemented here.

## K. Future production entry criteria

Approved behavior, classification, migration and artifact tests, consumer identity tests, external-risk statement, rollback, release notes, and no silent semantic change are required.

## L. Recommended next phase

**Backtest Deprecation Evidence Collection**; evidence remains insufficient for production modification.

## M. Explicit non-goals

No engine, NaN, adapter, warning, export, wrapper, result, artifact, report, CLI, strategy, consumer, or file-removal change is authorized.
