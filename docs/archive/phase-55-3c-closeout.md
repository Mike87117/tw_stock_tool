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

- Focused combined regression suite：76 tests passed.
- Phase 55.3C Workspace integration：4 tests passed.
- Unified CLI suite：56 tests passed.
- Full local suite：2283 tests passed, 5 skipped on Python 3.12.10.
- Editable package import、compile smoke and installed `twstock` help smoke passed.
- GitHub Actions run `30695032255` passed the full test matrix and package smoke on Python 3.11 and Python 3.12 for reviewed head `4b700381f6896d9ab61c312f9a7a7757a96d5013`.

## Known limitations

- Python 3.11 was unavailable locally; GitHub Actions provides the required Python 3.11 evidence.
- Windows accounts without symlink privilege rely on the existing mocked reparse-point coverage and CI real-symlink coverage.

## Independent review follow-up

- Unified `twstock scan --help`, `twstock daily --help`, and `twstock backtest-report --help` now forward to the underlying parser and display `--workspace`.
- Post-run provisional-read and manifest-conversion failures publish a valid fallback failure manifest when canonical publication remains possible.
- Callback and market-data-loader validation occurs before Workspace allocation; fallback manifests use the existing package-version resolver.
- Independent code review result：`CODE_REVIEW_PASS`; no new merge-blocking production defect was found.
