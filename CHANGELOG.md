# Changelog

## Unreleased

### Fixed

- `twstock doctor` no longer fails. It required eight root wrapper scripts that
  Cleanup 4A/4B intentionally removed, and resolved them (and `requirements.txt`)
  from `src/tw_stock_tool/utils/` instead of the repository root, so every run
  reported 9 FAIL and exited 1. The obsolete inventory is gone; repository-only
  checks now resolve from a detected source checkout and are skipped rather than
  failed when running from an installed distribution. A new `Package version`
  check reports the resolved `tw-stock-tool` version in either context.
- `twstock <command> --help` now shows the command's real options. 19 of 23
  passthrough subcommands - including `analyze`, `parameter-sweep`,
  `walk-forward`, `ai-report`, `stock-list update` and `stock-list smoke-check` -
  let the wrapper's argparse layer answer `--help` first and printed an
  option-less stub. Help is now delegated to the underlying CLI by default;
  `stock-list` and `gui` keep wrapper-owned help because they have no underlying
  parser. Research-only scope wording is unchanged: every underlying parser
  already carried it. Command arguments, exit codes and dispatch are unchanged.

### Added

- Multi-symbol historical simulated portfolio trading.
- Aggregate portfolio schema v1 JSON artifact workflow.
- Portfolio Markdown and deterministic seven-file CSV export.
- Optional portfolio risk limits:
  - max order notional
  - max position quantity
  - max position notional
  - max total exposure

### Reliability and Validation

- Exact signal-time reference-price validation.
- Chronological as-of portfolio exposure valuation.
- Pending BUY exposure reservation.
- Deterministic same-timestamp symbol ordering.
- Installed-package smoke coverage for newly supported CLI commands.
- Package smoke now runs from a temporary directory outside the repository with
  the checkout stripped from the import path, and asserts that the imported
  module resolves to the installed distribution. Running it from the checkout
  could resolve the repository-root compatibility shim instead, so it could not
  demonstrate that the installed wheel worked.
- Package smoke asserts a command-specific option in every
  `twstock <command> --help` rather than only a successful exit status, which
  the previous option-less wrapper help also satisfied.
- The shared subprocess test helper decodes child output as strict UTF-8 and
  pins `PYTHONIOENCODING=utf-8` in the child environment. It previously relied
  on the host ANSI code page, so Chinese CLI output was corrupted or failed to
  decode on Windows while Ubuntu CI stayed green.

### Performance

- `scikit-learn` and `mplfinance` are now imported when first used rather than at
  module scope. Both sat on the unified CLI's import path but are only reachable
  from the ML and chart routes, so unrelated `twstock ...` invocations no longer
  pay to initialize model and plotting machinery they never touch. In measured
  clean-interpreter probes this roughly halves CLI startup time. Public behavior,
  command routes, and output are unchanged.

### Notes

`tw_stock_tool` remains for historical research only. It has no broker integration, does not place real orders, does not provide investment advice, and provides no guarantee of returns or risk prevention.

## v0.4.0 - 2026-07-24

### Highlights

- Unified `twstock` console entrypoint and `src/tw_stock_tool/` package layout now define supported installation and research workflows.
- Daily Research workflows support opt-in historical backtest, parameter sweep, and walk-forward validation with shared analysis reuse and deterministic run configuration and summary.
- Offline artifact workflows cover Daily Report JSON, BacktestResult JSON, and simulated paper-trading JSON/Markdown/CSV outputs.

### Added

- Daily Report JSON schema v1 serialization, file export, validation, inspection, and Markdown conversion.
- Structured BacktestResult artifact validation, inspection, export, and conversion to simulated paper-trading artifacts.
- Historical simulated paper trading with risk and kill-switch boundaries, canonical Trade Log audit records, schema v3 output, and backward-compatible reading of schema v1/v2.
- `twstock ai-report`, `twstock ml-dataset`, and `twstock gui` as canonical user-facing research interfaces; AI walk-forward and baseline model remain package-level research components.
- Installed-package CI smoke for Python 3.11 and 3.12, including package import, module CLI, console script, and metadata consistency.

### Changed

- Daily Research reporting now records deterministic run configuration and pipeline summary while preserving existing output boundaries.
- CLI and artifact workflows use explicit overwrite protection and deterministic serialization.
- Shared backtest CLI parameter mapping is centralized without changing command routes or runtime behavior.
- Data/cache helper boundaries and reliability checks were consolidated while preserving fallback and stale-cache protections.

### Breaking Changes

- Repository-root Python entry points and compatibility imports are no longer supported. Use `twstock ...` or `tw_stock_tool.*`.
- AI Report uses `--output-excel`; ML Dataset uses `--output-csv`; update scripts that used generic `--output`.
- The legacy Daily Watchlist workflow was retired; use `twstock daily`.
- The obsolete Verify Batch utility was retired. Use `twstock stock-list smoke-check` and `twstock price-smoke-check` for supported source checks; the former TWSE OHLCV parity report has no direct replacement.
- Root-level standalone AI walk-forward and baseline-model entrypoints were removed; use the package-level research APIs.
- The alternate class-based `BacktestEngine`/`BaseStrategy` path was removed; use the active function-based `tw_stock_tool.backtesting` APIs.

### Removed

- Obsolete repository-root Python wrappers and compatibility import shims; canonical replacements are `twstock` commands and `tw_stock_tool.*` modules.
- The legacy Daily Watchlist and TWSE-only Verify Batch utility clusters.
- The alternate class-based backtesting path and root-level AI/ML compatibility wrappers.

### Reliability and Validation

- Installed-package CI now reads the project version from `pyproject.toml` and compares it with installed distribution metadata on Python 3.11 and 3.12.
- Artifact serialization remains deterministic, validates before conversion, preserves overwrite protection, and keeps supported schema compatibility boundaries.
- Provider/cache fallback, stale-cache protections, and offline smoke-check boundaries remain covered by the repository's validation workflows.

### Notes

`tw_stock_tool` remains a research and analysis platform. It does not connect to brokers, place real orders, provide investment advice, or guarantee returns.

Simulated paper trading uses historical/offline research data. AI/ML outputs are research baselines. v0.4.0 contains intentional compatibility removals.

## v0.3.0 - Data Source Resilience

### Added
- Added stale cache fallback when all live price data sources fail.
- Added maximum stale cache age protection with default 14-day limit.
- Added `TW_STOCK_TOOL_MAX_STALE_CACHE_DAYS` environment variable to configure the stale cache limit.
- Documented data source and cache resilience behavior in README.

### Changed
- `force_refresh=True` / `--force-refresh` now bypasses stale cache fallback and fails if live fetching fails.
- Data loading errors now include stale-cache rejection context when cache exists but is too old.

### Notes
- Stale cache fallback improves availability during temporary data-source outages or rate limits.
- It does not guarantee current market data.
- This project remains a research and analysis tool, not an auto-trading system or investment recommendation tool.
