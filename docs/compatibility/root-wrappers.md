# Root compatibility wrappers

正式 console entry point 是 `twstock`，正式 implementation 位於 `src/tw_stock_tool/`。以下 repository-root Python 檔案仍保留為歷史相容入口；本文件只記錄目前對應關係，不改變其 import 或直接執行行為。

`Canonical replacement` 欄優先列出正式 CLI；沒有 unified CLI 路由時則列出目前 canonical package target。

| Legacy root entry | Canonical replacement | Surface type | Current status |
| --- | --- | --- | --- |
| `ai_prediction_report.py` | `tw_stock_tool.reports.ai_prediction_report` | executable/import wrapper | retained compatibility entry |
| `ai_stock_scanner.py` | `twstock ai-scan / tw_stock_tool.ml.ai_stock_scanner` | executable/import wrapper | retained compatibility entry |
| `ai_walk_forward.py` | `tw_stock_tool.ml.ai_walk_forward` | executable/import wrapper | retained compatibility entry |
| `analysis.py` | `tw_stock_tool.analysis.analysis` | import wrapper | retained compatibility entry |
| `analysis_session.py` | `tw_stock_tool.analysis.analysis_session` | import wrapper | retained compatibility entry |
| `app_services.py` | `tw_stock_tool.gui.app_services` | import wrapper | retained compatibility entry |
| `backtest.py` | `tw_stock_tool.backtesting.backtest` | import wrapper | retained compatibility entry |
| `backtest_report.py` | `twstock backtest-report` | executable wrapper | retained compatibility entry |
| `baseline_ml_model.py` | `tw_stock_tool.ml.baseline_ml_model` | import wrapper | retained compatibility entry |
| `benchmark.py` | `twstock benchmark / tw_stock_tool.cli.benchmark` | executable/import wrapper | retained compatibility entry |
| `cache_manager.py` | `twstock cache / tw_stock_tool.data.cache_manager` | import wrapper | retained compatibility entry |
| `cache_utils.py` | `tw_stock_tool.data.cache_utils` | import wrapper | retained compatibility entry |
| `clean_stocks.py` | `twstock stock-list clean / tw_stock_tool.cli.clean_stocks` | executable/import wrapper | retained compatibility entry |
| `config.py` | `tw_stock_tool.utils.config` | import wrapper | retained compatibility entry |
| `console_lock.py` | `tw_stock_tool.utils.console_lock` | import wrapper | retained compatibility entry |
| `daily_report.py` | `twstock daily / tw_stock_tool.reports.daily_report` | executable/import wrapper | retained compatibility entry |
| `daily_watchlist.py` | `tw_stock_tool.cli.daily_watchlist` | executable/import wrapper | retained compatibility entry |
| `data_loader.py` | `tw_stock_tool.data.data_loader` | import wrapper | retained compatibility entry |
| `doctor.py` | `twstock doctor / tw_stock_tool.utils.doctor` | executable/import wrapper | retained compatibility entry |
| `gui_app.py` | `tw_stock_tool.gui.gui_app` | executable/import wrapper | retained compatibility entry |
| `gui_result_formatter.py` | `tw_stock_tool.gui.gui_result_formatter` | import wrapper | retained compatibility entry |
| `gui_tasks.py` | `tw_stock_tool.gui.gui_tasks` | import wrapper | retained compatibility entry |
| `indicators.py` | `tw_stock_tool.analysis.indicators` | import wrapper | retained compatibility entry |
| `main.py` | `twstock analyze / tw_stock_tool.cli.main` | executable/import wrapper | retained compatibility entry |
| `ml_dataset.py` | `tw_stock_tool.ml.ml_dataset` | executable/import wrapper | retained compatibility entry |
| `parameter_sweep.py` | `twstock parameter-sweep / tw_stock_tool.backtesting.parameter_sweep` | executable/import wrapper | retained compatibility entry |
| `parameter_sweep_report.py` | `twstock parameter-sweep / tw_stock_tool.cli.parameter_sweep_report` | executable wrapper | retained compatibility entry |
| `plotter.py` | `tw_stock_tool.reports.plotter` | import wrapper | retained compatibility entry |
| `price_data_smoke_check.py` | `twstock price-smoke-check / tw_stock_tool.cli.price_data_smoke_check` | executable/import wrapper | retained compatibility entry |
| `report.py` | `tw_stock_tool.reports.report` | import wrapper | retained compatibility entry |
| `scan_stocks.py` | `twstock scan / tw_stock_tool.cli.scan_stocks` | executable/import wrapper | retained compatibility entry |
| `scanner.py` | `tw_stock_tool.analysis.scanner` | import wrapper | retained compatibility entry |
| `signals.py` | `tw_stock_tool.analysis.signals` | import wrapper | retained compatibility entry |
| `stock_list_smoke_check.py` | `twstock stock-list smoke-check / tw_stock_tool.cli.stock_list_smoke_check` | executable/import wrapper | retained compatibility entry |
| `stock_list_updater.py` | `twstock stock-list update / tw_stock_tool.data.stock_list_updater` | executable/import wrapper | retained compatibility entry |
| `stock_selection.py` | `tw_stock_tool.analysis.stock_selection` | import wrapper | retained compatibility entry |
| `strategies.py` | `tw_stock_tool.backtesting.strategies` | import wrapper | retained compatibility entry |
| `strategy_compare.py` | `twstock strategy-compare / tw_stock_tool.backtesting.strategy_compare` | executable/import wrapper | retained compatibility entry |
| `twstock_cli.py` | `twstock / tw_stock_tool.cli.twstock_cli` | executable/import wrapper | retained compatibility entry |
| `verify_batch.py` | `tw_stock_tool.utils.verify_batch` | executable/import wrapper | retained compatibility entry |
| `walk_forward.py` | `twstock walk-forward / tw_stock_tool.backtesting.walk_forward` | executable/import wrapper | retained compatibility entry |
| `walk_forward_report.py` | `twstock walk-forward / tw_stock_tool.cli.walk_forward_report` | executable wrapper | retained compatibility entry |

這些檔案是 historical compatibility wrappers，而不是主要實作位置。新程式與新文件應優先使用 `twstock` 或表中的 canonical package target。
