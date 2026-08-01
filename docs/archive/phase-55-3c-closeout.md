# Phase 55.3C Closeout：Scan／Daily／Backtest Workspace Integration

## Status

Phase 55.3C implements opt-in Workspace execution for the existing Scan, Daily Report and Backtest Report application workflows.

## Delivered behavior

- `--workspace PATH` creates an append-only managed Research Run.
- Request validation and output-path conflict checks happen before run-directory allocation.
- Each run uses the Phase 55.3B Workspace allocator and receives a canonical `manifest.json`.
- Managed artifacts are written below `artifacts/` and are published as relative POSIX references.
- Strict manifest persistence and read-back reuse the Phase 55.3B Workspace API and the existing Run Manifest schema 1.0.
- Repeated equivalent runs create distinct directories; existing runs are never overwritten.
- Controlled workflow failures publish failure or partial manifests when possible without replacing the original exception.
- Legacy mode remains the existing CLI path when `--workspace` is omitted.

## Scope boundaries

Parameter Sweep, Walk Forward, Strategy Compare, AI／ML, simulated trading, GUI, run list／inspect, registry, database and cleanup remain outside this phase.

## Verification

- Focused application and CLI compatibility tests pass.
- Focused Workspace lifecycle/catalog tests pass.
- Actual offline Scan and Backtest workflow smokes pass with fake market-data loaders.
- Full suite and package smoke remain required merge-gate evidence.

## Known limitations

- Python 3.11 local execution depends on the available interpreter; CI matrix evidence must be recorded separately when unavailable locally.
- Windows accounts without symlink privilege rely on the existing mocked reparse-point coverage and CI real-symlink coverage.


## Independent review follow-up

- Unified 	wstock scan --help, 	wstock daily --help, and 	wstock backtest-report --help now forward to the underlying parser and display --workspace.
- Post-run provisional-read and manifest-conversion failures publish a valid fallback failure manifest when canonical publication remains possible.
- Callback and market-data-loader validation occurs before Workspace allocation; fallback manifests use the existing package-version resolver.
