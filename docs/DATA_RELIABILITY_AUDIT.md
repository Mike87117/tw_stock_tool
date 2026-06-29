# Phase 6 Data Reliability Final Audit

## 1. Purpose
This document records the final Phase 6 data reliability behavior for the Daily Report MVP. It maps out the completed reliability improvements from Phase 6.1 through Phase 6.6, remaining known risks, and out-of-scope boundaries. It serves as a comprehensive reference for how the system behaves when confronted with missing data, network timeouts, invalid stock IDs, and partial execution failures.

## 2. Current Daily Run Data Flow
1. **Stock List Update (`stock_list_updater.py`)**: Fetches official TWSE and TPEx stock lists to generate a master universe of common stocks.
2. **Scanner Execution (`scanner.py`)**: Dispatches the stock list to a thread pool (`ThreadPoolExecutor`). Each thread calls `data_loader.py`.
3. **Data Loading (`data_loader.py`)**: Checks the local cache first. If the cache misses, it attempts to download via `yfinance`. If `yfinance` fails or returns empty data (and `auto_adjust` is false), it falls back to the official TWSE/TPEx monthly endpoints.
4. **Report Building (`daily_report.py`)**: Aggregates the results, computes candidates, and exports them to Markdown and Excel (via `daily_report_cli.py`).

## 3. Price Data Failure Modes
- **yfinance behavior**: `yfinance` outputs are suppressed using a global `console_io_lock`. If it returns an empty DataFrame or fails completely, the error is caught, appended to an error tracking list, and the system proceeds to the next candidate fallback.
- **TWSE / TPEx fallback behavior**: If `yfinance` fails, the `data_loader.py` attempts to fetch from official APIs. 
  - TWSE: `https://www.twse.com.tw/exchangeReport/STOCK_DAY`
  - TPEx: `https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock` and a latest quote fallback.
  These only support `1d` intervals. If these fail, the errors are aggregated into a `DataLoaderError`.
- **Empty price data**: Empty DataFrames from any source are considered failures. `_prepare_ohlcv` checks for required columns and drops NA rows. If the resulting DataFrame is empty, it raises `DataLoaderError("... has no usable OHLC data.")`.
- **TW / TWO fallback**: The system automatically guesses the suffix (`.TW` or `.TWO`) if not provided. It will attempt both sequentially if neither is specified.
- **Invalid stock IDs**: Will exhaust all symbol candidates and ultimately raise a `DataLoaderError` containing the tried symbols and reasons.

## 4. Stock List Failure Modes
- **Stock list update failures**: The official endpoints are queried. If one fails (e.g., TWSE fails but TPEx succeeds), the behavior depends on the `--allow-partial` flag (default `False`). If `False`, the entire update fails, raising a `StockListUpdaterError`. If `True`, the tool successfully writes the partial list and prints a warning to `sys.stderr` about the failed source.
- **Empty/Short lists**: A safety check `len(normalized) < min_common_stocks` (default 100) prevents wiping out the `stocks.txt` file if the official API format unexpectedly changes and returns 0 stocks.
- **Stock List Output Format**: By default, `stock_list_updater.py` writes plain stock IDs (e.g., `2330`). The opt-in `--add-suffix` flag appends market suffixes (e.g., `2330.TW`, `8069.TWO`), which reduces subsequent fallback guessing overhead during price downloads.

## 5. Scanner Failure Modes
- **Failed-symbol handling**: In `scan_one_stock`, any `Exception` (including `DataLoaderError`) is caught and returns a default dictionary with `Status="ERROR"` and `Error=str(exc)`. 
- **Can one failed stock break an entire scan?**: No. The thread pool safely isolates failures. Failed stocks are appended to the results DataFrame with `Status="ERROR"` and placed at the bottom of the list with `Rank=None`. The rest of the scan succeeds.

## 6. Cache / Force Refresh Failure Modes
- **Cache hit / miss**: `data_loader.py` uses `_is_cache_fresh` to check freshness based on `Asia/Taipei` market-close timing.
  - Before 14:30, same-day cache is considered fresh.
  - After 14:30, the cache file must have been modified at or after 14:30 to be considered fresh.
  If a cache file is deemed fresh but reading fails, it catches the error and falls back to network download.
- **Force refresh**: The `--force-refresh` flag bypasses the cache freshness check and immediately proceeds to network download, overwriting the cache.
- **Empty data cache corruption**: If a network download succeeds but returns unusable data, it shouldn't be written to cache because `_prepare_ohlcv` raises an error before `_write_cache` is called.

## 7. Daily Report Partial-Failure Behavior
- **Empty candidates / partial failures**: If some stocks fail during the scan, they end up in `ranking_df` with `Status="ERROR"`. These failed stocks are now explicitly included in the "Data Limitations" section of the final report to provide user visibility.
- **Total failure**: If all stocks fail, the report still generates but lists 0 candidates. 

## 8. Current Test Coverage
- **Offline test coverage**: Existing tests extensively cover argument parsing, basic `daily_report` behavior, and formatting. Mocking is used in `tests/test_data_loader.py` to prevent network calls.
  Offline coverage now includes:
  - yfinance empty result triggering official fallback
  - cache read failure falling back to download
  - invalid stock ID validation
  - Daily Report Data Limitations rendering failed scan rows
  - cache write failure being non-fatal for successful downloads

## 9. Reliability Risks
- **Daily Report failure visibility**: Phase 6.4 surfaces failed scan rows in the Markdown "Data Limitations" section. Remaining risk is that very large failure sets are summarized after the configured display limit, so users may need to inspect full scan outputs for exhaustive details.
- **API Rate Limiting**: The TWSE/TPEx fallbacks use standard requests without delays between them. A large batch of `yfinance` failures could trigger rate-limiting on the official servers.

## 10. Phase 6 Completion Summary
- Phase 6.1 (Completed): Data reliability audit / failure-mode map.
- Phase 6.2 (Completed): Price data fallback and cache behavior cleanup.
- Phase 6.3 (Completed): Stock list reliability and invalid-symbol handling.
- Phase 6.4 (Completed): Daily Report partial-failure behavior and user-facing warnings.
- Phase 6.5 (Completed): Data reliability tests and documentation.
- Phase 6.6 (Completed): Final data reliability cleanup / final audit.

## 11. Out of Scope
The following are strictly out of scope for the Daily Report MVP and Phase 6 data reliability efforts:
- Broker API integrations
- Paper trading, auto trading, or semi-auto trading
- Order execution
- Portfolio optimization
- Investment recommendation wording or AI/ML prediction
- New data providers
- Real-time alerting or scheduler/automation
- GUI changes or Excel exporter restoration (Note: Excel export was later restored in Phase 10 via `--output-excel`)
- Integrating deep-dive backtest, parameter sweep, or walk-forward engines into the Daily Report CLI.
- Live-network testing.

## 12. Final Acceptance Criteria for Phase 6
- data failure modes are documented
- cache freshness and fallback behavior are documented
- stock list partial-update behavior is documented
- Daily Report failed-stock visibility is documented
- offline reliability tests cover key fallback and cache failure paths
- no live-network tests are added to unittest / CI
- no broker / trading / order execution / prediction features are introduced
