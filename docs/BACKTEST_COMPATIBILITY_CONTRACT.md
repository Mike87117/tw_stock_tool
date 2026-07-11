# Backtest Compatibility Contract

## A. Contract status

Phase A2 decision: **INSUFFICIENT_EVIDENCE_RETAIN_TEMPORARILY**. A3 formalizes boundaries only; it authorizes neither migration nor deprecation.

## B. Contract classification vocabulary

- `SUPPORTED_CANONICAL`: supported application-facing canonical path.
- `INTERNAL_CONSUMER_CONTRACT`: current internal consumer boundary.
- `TEMPORARY_COMPATIBILITY_RETAINED`: import retained because external use is unknown.
- `CHARACTERIZED_NOT_GUARANTEED`: observed behavior, not a public promise.
- `NOT_SUPPORTED`: no supported interoperability promise.

## C. Canonical backtest contract

`tw_stock_tool.backtesting.backtest.run_backtest`, `run_backtest_result`, and `BacktestError`; `tw_stock_tool.backtesting.results.BacktestResult`; canonical strategies, serialization, and serialization_files are `SUPPORTED_CANONICAL`. The canonical result identity, structured fields, legacy dictionary adapter, artifact ownership, report/CLI/converter ownership, and root wrapper targets are contract-protected.

## D. Alternate temporary retention contract

`tw_stock_tool.backtest.engine.BacktestEngine`, its distinct `BacktestResult`, and `tw_stock_tool.strategies.base.BaseStrategy` are `TEMPORARY_COMPATIBILITY_RETAINED`. No production caller or root wrapper target was identified. Canonical serialization and paper-trading conversion reject alternate results. Continued importability does not declare a canonical API; external usage is unknown.

## E. Root-wrapper contract

`backtest.py` redirects to `tw_stock_tool.backtesting.backtest`; `strategies.py` redirects to `tw_stock_tool.backtesting.strategies`. Redirecting either to alternate modules is breaking.

## F. Consumer evidence matrix

| Consumer | Type | Canonical source | Purpose | Classification | Risk |
|---|---|---|---|---|---|
| backtest_result_export_cli | CLI | run_backtest_result and STRATEGIES | export artifact | INTERNAL_CONSUMER_CONTRACT | High |
| backtest_artifact_cli | CLI/artifact | canonical file loader and converter | inspect/convert artifact | INTERNAL_CONSUMER_CONTRACT | High |
| backtesting serialization modules | Artifact | canonical BacktestResult | JSON read/write | INTERNAL_CONSUMER_CONTRACT | High |
| paper_trading backtest_converter | Conversion | canonical BacktestResult | simulated conversion | INTERNAL_CONSUMER_CONTRACT | High |
| src/tw_stock_tool/backtesting/parameter_sweep.py; src/tw_stock_tool/backtesting/strategy_compare.py; src/tw_stock_tool/backtesting/walk_forward.py | Runtime/report | canonical backtesting modules | research reports | INTERNAL_CONSUMER_CONTRACT | High |

## G. Result identity and artifact contract

Canonical and alternate `BacktestResult` classes are distinct. Artifact writer/reader, serializer, and converter accept only canonical results. Metadata (`stock`, `strategy`, `parameters`, dates), integer share quantities, and canonical trade columns are consumer boundaries. Automatic duck typing is prohibited.

## H. Stable and unstable behavior

| Stable contract | Characterized but not guaranteed |
|---|---|
| canonical imports, root targets, result identity, artifact return type, converter input type, established consumers | alternate NaN-open propagation, undocumented alternate edges, private helpers, internal layout, absence of unknown external users |

The alternate NaN-open behavior is `CHARACTERIZED_NOT_GUARANTEED`: it is a risk, not an endorsed promise.

## I. Breaking-change catalogue

Changing root targets, canonical result identity, artifact result type, serializer/converter input types, canonical fields, converter columns, integer-share assumptions, or consumer imports is breaking. Removing alternate imports also requires a compatibility window. Each requires consumer identity tests, artifact tests, documentation, and a dedicated production phase; package exports that create ambiguous `BacktestResult` imports are prohibited.

## J. Allowed additive changes

Separately reviewed additive metadata, report fields, tests, documentation, named adapters, and bug fixes with characterization migration may be safe. A3 implements none.

## K. Future production entry criteria

A production phase needs an approved target behavior, explicit classification, migration and artifact tests, consumer identity tests, external-risk statement, rollback path, release notes, no silent semantic change, and no unrelated cleanup.

## L. Recommended next phase

**Backtest Deprecation Evidence Collection**: collect external-import and consumer evidence before any production modification. This is safer than inventing a migration while semantic and external-usage uncertainty remain.

## M. Explicit non-goals

A3 does not modify engines, fix NaN opens, add adapters/warnings/exports, change wrappers/results/artifacts/reports/CLI/strategies, migrate consumers, remove files, or add broker, live-trading, execution, or investment-recommendation functionality.

## F. Consumer evidence matrix

The authoritative consumer list is: `src/tw_stock_tool/cli/backtest_result_export_cli.py` (CLI, run_backtest_result and JSON export); `src/tw_stock_tool/cli/backtest_artifact_cli.py` (artifact CLI, canonical loader and converter); `src/tw_stock_tool/cli/backtest_report.py` (report CLI, run_backtest); `src/tw_stock_tool/backtesting/serialization.py` and `serialization_files.py` (serialization/artifact); `src/tw_stock_tool/backtesting/parameter_sweep.py`, `strategy_compare.py`, and `walk_forward.py` (runtime/report); `src/tw_stock_tool/gui/app_services.py` and `src/tw_stock_tool/cli/main.py` (runtime); and `src/tw_stock_tool/paper_trading/backtest_converter.py` (conversion). Existing backtest, artifact, report, GUI, converter, and serialization tests protect these boundaries. All are `INTERNAL_CONSUMER_CONTRACT`, high risk; no alternate import is permitted in their canonical workflow.

## I. Breaking-change catalogue

| Change | Why breaking | Tests/docs | Window/phase | Rollback |
|---|---|---|---|---|
| Change root backtest.py or strategies.py target | breaks imports | wrapper identity tests, migration docs | yes/yes | restore target |
| Change canonical result identity or fields | breaks consumers/artifacts | identity/artifact tests, release notes | yes/yes | retain class/fields |
| Accept alternate result in serializer/converter | weakens type boundary | rejection tests, contract docs | yes/yes | reject alternate |
| Change loader return type or converter input/trade columns/integer shares/metadata | breaks artifacts/conversion | round-trip/converter tests, migration docs | yes/yes | retain old reader/adapter |
| Remove alternate engine/BaseStrategy imports | unknown external break | import tests, deprecation docs | yes/yes | retain import shim |
| Move canonical consumer to alternate engine | changes semantics | consumer AST/characterization tests | yes/yes | restore canonical import |
| Add ambiguous package BacktestResult export | ambiguous identity | import identity tests, API docs | yes/yes | remove ambiguous alias |

Concrete examples: `SUPPORTED_CANONICAL` is canonical result/import identity; `INTERNAL_CONSUMER_CONTRACT` is the listed consumer files; `TEMPORARY_COMPATIBILITY_RETAINED` is alternate engine/BaseStrategy importability; `CHARACTERIZED_NOT_GUARANTEED` is alternate NaN-open propagation; `NOT_SUPPORTED` is alternate result serialization or conversion.
