# Root wrapper removal record

Cleanup 4A intentionally breaks historical repository-root import and script compatibility. The supported interfaces are the `twstock` console command and `tw_stock_tool.*` package modules. No package implementation, CLI route, schema, data fallback, or runtime feature was removed.

## Removed wrappers

| Removed wrapper | Canonical replacement |
| --- | --- |
| `analysis.py` | `tw_stock_tool.analysis.analysis` |
| `analysis_session.py` | `tw_stock_tool.analysis.analysis_session` |
| `app_services.py` | `tw_stock_tool.gui.app_services` |
| `backtest.py` | `tw_stock_tool.backtesting.backtest` |
| `baseline_ml_model.py` | `tw_stock_tool.ml.baseline_ml_model` |
| `cache_utils.py` | `tw_stock_tool.data.cache_utils` |
| `config.py` | `tw_stock_tool.utils.config` |
| `console_lock.py` | `tw_stock_tool.utils.console_lock` |
| `data_loader.py` | `tw_stock_tool.data.data_loader` |
| `gui_result_formatter.py` | `tw_stock_tool.gui.gui_result_formatter` |
| `gui_tasks.py` | `tw_stock_tool.gui.gui_tasks` |
| `indicators.py` | `tw_stock_tool.analysis.indicators` |
| `plotter.py` | `tw_stock_tool.reports.plotter` |
| `report.py` | `tw_stock_tool.reports.report` |
| `scanner.py` | `tw_stock_tool.analysis.scanner` |
| `signals.py` | `tw_stock_tool.analysis.signals` |
| `stock_selection.py` | `tw_stock_tool.analysis.stock_selection` |
| `strategies.py` | `tw_stock_tool.backtesting.strategies` |
| `ai_stock_scanner.py` | `twstock ai-scan` / `tw_stock_tool.ml.ai_stock_scanner` |
| `backtest_report.py` | `twstock backtest-report` / `tw_stock_tool.cli.backtest_report` |
| `benchmark.py` | `twstock benchmark` / `tw_stock_tool.cli.benchmark` |
| `cache_manager.py` | `twstock cache` / `tw_stock_tool.data.cache_manager` |
| `clean_stocks.py` | `twstock stock-list clean` / `tw_stock_tool.cli.clean_stocks` |
| `daily_report.py` | `twstock daily` / `tw_stock_tool.reports.daily_report` |
| `doctor.py` | `twstock doctor` / `tw_stock_tool.utils.doctor` |
| `main.py` | `twstock analyze` / `tw_stock_tool.cli.main` |
| `parameter_sweep.py` | `twstock parameter-sweep` / `tw_stock_tool.backtesting.parameter_sweep` |
| `parameter_sweep_report.py` | `twstock parameter-sweep` / `tw_stock_tool.cli.parameter_sweep_report` |
| `price_data_smoke_check.py` | `twstock price-smoke-check` / `tw_stock_tool.cli.price_data_smoke_check` |
| `scan_stocks.py` | `twstock scan` / `tw_stock_tool.cli.scan_stocks` |
| `stock_list_smoke_check.py` | `twstock stock-list smoke-check` / `tw_stock_tool.cli.stock_list_smoke_check` |
| `stock_list_updater.py` | `twstock stock-list update` / `tw_stock_tool.data.stock_list_updater` |
| `strategy_compare.py` | `twstock strategy-compare` / `tw_stock_tool.backtesting.strategy_compare` |
| `twstock_cli.py` | `twstock` / `tw_stock_tool.cli.twstock_cli` |
| `walk_forward.py` | `twstock walk-forward` / `tw_stock_tool.backtesting.walk_forward` |
| `walk_forward_report.py` | `twstock walk-forward` / `tw_stock_tool.cli.walk_forward_report` |

## Policy

This is an intentional breaking change under Cleanup 4A. Existing core tests were retained or migrated to canonical imports; tests whose only purpose was root forwarding, alias identity, or root subprocess behavior were removed. The two unresolved legacy entries remain explicitly retained for Cleanup 4B.2.


## Cleanup 4B.1 canonicalization

Cleanup 4B.1 removed the remaining ML/GUI root wrappers after adding canonical interfaces:

| Removed wrapper | Canonical replacement |
| --- | --- |
| `ai_prediction_report.py` | `twstock ai-report` / `tw_stock_tool.reports.ai_prediction_report` |
| `ai_walk_forward.py` | package-only `tw_stock_tool.ml.ai_walk_forward` |
| `gui_app.py` | `twstock gui` / `tw_stock_tool.gui.gui_app` |
| `ml_dataset.py` | `twstock ml-dataset` / `tw_stock_tool.ml.ml_dataset` |

`twstock ai-report`, `twstock ml-dataset`, and `twstock gui` are the supported user-facing interfaces.
