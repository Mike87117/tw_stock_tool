"""Service layer for future GUI or Web UI integrations.

These functions are thin wrappers around existing CLI modules. They do not
change CLI behavior and do not implement new analysis logic.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

from tw_stock_tool.reports import ai_prediction_report as ai_prediction_report_module
from tw_stock_tool.analysis import analysis as analysis_module
from tw_stock_tool.backtesting import backtest as backtest_module
from tw_stock_tool.data import cache_manager as cache_manager_module
from tw_stock_tool.utils import doctor as doctor_module
from tw_stock_tool.ml import ai_stock_scanner as ai_stock_scanner_module
from tw_stock_tool.cli import clean_stocks as clean_stocks_module
from tw_stock_tool.reports import daily_report as daily_report_module
from tw_stock_tool.cli import main as main_module
from tw_stock_tool.reports import plotter as plotter_module
from tw_stock_tool.reports import report as report_module
from tw_stock_tool.analysis import scanner as scanner_module
from tw_stock_tool.cli import price_data_smoke_check as price_data_smoke_check_module
from tw_stock_tool.cli import stock_list_smoke_check as stock_list_smoke_check_module
from tw_stock_tool.data import stock_list_updater as stock_list_updater_module
from tw_stock_tool.utils.config import (
    DEFAULT_AUTO_ADJUST,
    DEFAULT_INTERVAL,
    DEFAULT_PERIOD,
    FEE_RATE,
    INITIAL_CAPITAL,
    OUTPUT_DIR,
    TAX_RATE,
)
from tw_stock_tool.reports.daily_report import DEFAULT_MIN_SCORE, DEFAULT_SIGNALS, DEFAULT_TOP
from tw_stock_tool.analysis.scanner import ProgressCallback, ScanConfig


class AppServiceError(Exception):
    """Raised when a service-layer operation fails."""


def _wrap_error(action: str, exc: Exception) -> AppServiceError:
    return AppServiceError(f"{action} failed: {exc}")


def doctor_service(live: bool = False) -> dict[str, Any]:
    """Run environment checks for GUI/Web integrations."""
    try:
        rows = doctor_module.run_doctor(live=live)
        summary = doctor_module.summarize(rows)
        return {
            "rows": rows,
            "summary": summary,
            "has_failures": doctor_module.has_failures(rows),
        }
    except Exception as exc:
        raise _wrap_error("Doctor", exc) from exc


def stock_list_smoke_check_service(
    min_twse: int = stock_list_smoke_check_module.DEFAULT_MIN_TWSE,
    min_tpex: int = stock_list_smoke_check_module.DEFAULT_MIN_TPEX,
    min_all: int = stock_list_smoke_check_module.DEFAULT_MIN_ALL,
) -> dict[str, Any]:
    """Run the official stock-list smoke check."""
    try:
        return stock_list_smoke_check_module.run_smoke_check(
            min_twse=min_twse,
            min_tpex=min_tpex,
            min_all=min_all,
        )
    except Exception as exc:
        raise _wrap_error("Stock list smoke check", exc) from exc


def price_data_smoke_check_service(
    twse_stock: str = "2330",
    tpex_stock: str = "8069",
    period: str = "1mo",
    interval: str = "1d",
) -> dict[str, Any]:
    """Run the live price-data smoke check."""
    try:
        results = price_data_smoke_check_module.run_smoke_check(
            twse_stock=twse_stock,
            tpex_stock=tpex_stock,
            period=period,
            interval=interval,
        )
        return {"results": results, "failed": False}
    except Exception as exc:
        raise _wrap_error("Price data smoke check", exc) from exc


def single_stock_analysis_service(
    stock_id: str,
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    auto_adjust: bool = DEFAULT_AUTO_ADJUST,
    force_refresh: bool = False,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
    max_hold_days: int | None = None,
    position_size: float = 1.0,
    export_excel: bool = False,
    save_chart: bool = False,
) -> dict[str, Any]:
    """Run one-stock analysis without relying on CLI printing."""
    try:
        options = main_module.MainOptions(
            stock_id=stock_id,
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            force_refresh=force_refresh,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            max_hold_days=max_hold_days,
            position_size=position_size,
            export_excel=export_excel,
            save_chart=save_chart,
        )
        main_module._validate_options(options)
        analysis = analysis_module.analyze_stock(
            options.stock_id,
            period=options.period,
            interval=options.interval,
            auto_adjust=options.auto_adjust,
            force_refresh=options.force_refresh,
        )
        signal_df = analysis.signal_df
        backtest_result = backtest_module.run_backtest(
            signal_df,
            initial_capital=INITIAL_CAPITAL,
            fee_rate=FEE_RATE,
            tax_rate=TAX_RATE,
            stop_loss_pct=options.stop_loss_pct,
            take_profit_pct=options.take_profit_pct,
            max_hold_days=options.max_hold_days,
            position_size=options.position_size,
        )

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        chart_path = None
        if options.save_chart:
            chart_path = OUTPUT_DIR / f"{options.stock_id}_chart.png"
            plotter_module.plot_stock_chart(
                signal_df,
                stock_id=options.stock_id,
                symbol=analysis.symbol,
                save_path=chart_path,
            )

        report_path = None
        if options.export_excel:
            report_path = report_module.export_excel_report(
                stock_id=options.stock_id,
                df=signal_df,
                backtest_result=backtest_result,
                summary=analysis.summary,
                output_dir=OUTPUT_DIR,
            )

        return {
            "analysis": analysis,
            "signal": signal_df,
            "summary": analysis.summary,
            "backtest": backtest_result,
            "symbol": analysis.symbol,
            "excel_path": report_path,
            "chart_path": chart_path,
        }
    except Exception as exc:
        raise _wrap_error("Single stock analysis", exc) from exc


def cache_summary_service() -> dict[str, Any]:
    """Return cache summary data for GUI/Web integrations."""
    try:
        summary = cache_manager_module.cache_summary()
        return {
            "summary": summary,
            "count": len(summary),
            "empty": summary.empty,
        }
    except Exception as exc:
        raise _wrap_error("Cache summary", exc) from exc


def cache_clear_service() -> dict[str, Any]:
    """Clear cache files and return the number removed."""
    try:
        count = cache_manager_module.clear_cache()
        return {"cleared": count}
    except Exception as exc:
        raise _wrap_error("Cache clear", exc) from exc


def clean_stocks_service(
    file_path: str | Path,
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    auto_adjust: bool = DEFAULT_AUTO_ADJUST,
    force_refresh: bool = False,
    output: str | Path | None = None,
    clean_file: str | Path | None = None,
) -> dict[str, Any]:
    """Run stock-list cleaning and return frames plus output paths."""
    try:
        summary_df, result_df, duplicates_df, report_path, clean_path = (
            clean_stocks_module.run_clean_stocks(
                file_path=file_path,
                period=period,
                interval=interval,
                auto_adjust=auto_adjust,
                force_refresh=force_refresh,
                output=output,
                clean_file=clean_file,
            )
        )
        return {
            "summary": summary_df,
            "result": result_df,
            "duplicates": duplicates_df,
            "report_path": report_path,
            "clean_path": clean_path,
        }
    except Exception as exc:
        raise _wrap_error("Clean stocks", exc) from exc


def daily_report_service(
    stock_ids: Iterable[str],
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    signals: Iterable[str] = DEFAULT_SIGNALS,
    min_score: float = DEFAULT_MIN_SCORE,
    top: int | None = DEFAULT_TOP,
    force_refresh: bool = False,
    auto_adjust: bool = DEFAULT_AUTO_ADJUST,
    output: str | None = None,
    progress: bool = True,
) -> dict[str, Any]:
    """Run the daily candidate report service."""
    try:
        summary_df, candidates_df, ranking_df, output_path = daily_report_module.run_daily_report(
            stock_ids=stock_ids,
            period=period,
            interval=interval,
            signals=signals,
            min_score=min_score,
            top=top,
            force_refresh=force_refresh,
            auto_adjust=auto_adjust,
            output=output,
            progress=progress,
        )
        return {
            "summary": summary_df,
            "candidates": candidates_df,
            "ranking": ranking_df,
            "output_path": output_path,
        }
    except Exception as exc:
        raise _wrap_error("Daily report", exc) from exc


def scan_stocks_service(
    stock_ids: Iterable[str],
    config: ScanConfig | None = None,
    progress_callback: ProgressCallback | None = None,
) -> pd.DataFrame:
    """Run the existing technical stock scanner."""
    try:
        return scanner_module.scan_stocks(
            stock_ids,
            config=config,
            progress_callback=progress_callback,
        )
    except Exception as exc:
        raise _wrap_error("Scan stocks", exc) from exc


def scan_stocks_with_options_service(
    stock_ids: Iterable[str],
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    auto_adjust: bool = DEFAULT_AUTO_ADJUST,
    force_refresh: bool = False,
    max_workers: int = 8,
    min_score: float | None = None,
    min_volume_ratio: float | None = None,
    min_close: float | None = None,
    max_close: float | None = None,
    signals: tuple[str, ...] | None = None,
    sort_by: str = "Score",
    top: int | None = None,
    errors_only: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> pd.DataFrame:
    """Build a ScanConfig from UI-friendly options and run scan_stocks."""
    config = ScanConfig(
        period=period,
        interval=interval,
        auto_adjust=auto_adjust,
        force_refresh=force_refresh,
        max_workers=max_workers,
        min_score=min_score,
        min_volume_ratio=min_volume_ratio,
        min_close=min_close,
        max_close=max_close,
        signals=signals,
        sort_by=sort_by,
        top=top,
        errors_only=errors_only,
    )
    return scan_stocks_service(stock_ids, config=config, progress_callback=progress_callback)


def stock_list_updater_service(
    market: str = "all",
    output: str | Path = "stocks.txt",
    allow_partial: bool = False,
    min_common_stocks: int | None = None,
) -> dict[str, Any]:
    """Update the Taiwan stock list through the service layer."""
    try:
        kwargs: dict[str, Any] = {
            "market": market,
            "output": output,
            "allow_partial": allow_partial,
        }
        if min_common_stocks is not None:
            kwargs["min_common_stocks"] = min_common_stocks
        stocks_df, output_path = stock_list_updater_module.update_stock_list(**kwargs)
        return {
            "stocks": stocks_df,
            "output_path": output_path,
            "count": len(stocks_df),
        }
    except Exception as exc:
        raise _wrap_error("Stock list updater", exc) from exc


def ai_stock_scanner_service(
    stock_ids: Iterable[str],
    period: str = DEFAULT_PERIOD,
    horizon: int = 5,
    train_size: int = 252,
    test_size: int = 63,
    step_size: int | None = None,
    force_refresh: bool = False,
    dropna: bool = True,
    n_estimators: int = 100,
    random_state: int = 42,
    workers: int = 1,
    output: str | None = None,
) -> dict[str, Any]:
    """Run the multi-stock AI baseline scanner and optionally export Excel."""
    try:
        ranking_df = ai_stock_scanner_module.scan_ai_stocks(
            stock_ids=stock_ids,
            period=period,
            horizon=horizon,
            train_size=train_size,
            test_size=test_size,
            step_size=step_size,
            force_refresh=force_refresh,
            dropna=dropna,
            n_estimators=n_estimators,
            random_state=random_state,
            workers=workers,
        )
        output_path = ai_stock_scanner_module.export_ai_stock_ranking(ranking_df, output)
        return {
            "ranking": ranking_df,
            "output_path": output_path,
        }
    except Exception as exc:
        raise _wrap_error("AI stock scanner", exc) from exc


def ai_prediction_report_service(
    stock_id: str,
    period: str = DEFAULT_PERIOD,
    horizon: int = 5,
    train_size: int = 252,
    test_size: int = 63,
    step_size: int | None = None,
    force_refresh: bool = False,
    dropna: bool = True,
    n_estimators: int = 100,
    random_state: int = 42,
    output: str | None = None,
) -> dict[str, Any]:
    """Run one-stock AI prediction report and optionally export Excel."""
    try:
        frames = ai_prediction_report_module.run_ai_prediction_report(
            stock_id=stock_id,
            period=period,
            horizon=horizon,
            train_size=train_size,
            test_size=test_size,
            step_size=step_size,
            force_refresh=force_refresh,
            dropna=dropna,
            n_estimators=n_estimators,
            random_state=random_state,
        )
        output_path = ai_prediction_report_module.export_ai_prediction_report_excel(
            frames,
            stock_id=stock_id,
            output=output,
        )
        return {
            "summary": frames["Summary"],
            "detail": frames["Detail"],
            "errors": frames["Errors"],
            "frames": frames,
            "output_path": output_path,
        }
    except Exception as exc:
        raise _wrap_error("AI prediction report", exc) from exc
