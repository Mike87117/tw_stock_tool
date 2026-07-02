# Changelog

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
