# Changelog

## v0.4.0 - 2026-07-23

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
