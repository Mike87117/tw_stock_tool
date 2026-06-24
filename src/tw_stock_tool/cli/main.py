import argparse
import sys
from dataclasses import dataclass

from tw_stock_tool.analysis.analysis import analyze_stock
from tw_stock_tool.backtesting.backtest import run_backtest
from tw_stock_tool.utils.config import (
    DEFAULT_AUTO_ADJUST,
    DEFAULT_INTERVAL,
    DEFAULT_PERIOD,
    FEE_RATE,
    INITIAL_CAPITAL,
    OUTPUT_DIR,
    TAX_RATE,
    VALID_INTERVALS,
    VALID_PERIODS,
)
from tw_stock_tool.data.data_loader import DataLoaderError
from tw_stock_tool.analysis.indicators import IndicatorError
from tw_stock_tool.reports.plotter import plot_stock_chart
from tw_stock_tool.reports.report import ReportError, export_excel_report


@dataclass(frozen=True)
class MainOptions:
    stock_id: str
    period: str = DEFAULT_PERIOD
    interval: str = DEFAULT_INTERVAL
    auto_adjust: bool = DEFAULT_AUTO_ADJUST
    force_refresh: bool = False
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    max_hold_days: int | None = None
    position_size: float = 1.0
    export_excel: bool = False
    save_chart: bool = False


def _ask_period() -> str:
    period = input("請輸入分析期間：1y / 2y / 5y / max\n").strip().lower()
    if not period:
        return DEFAULT_PERIOD
    if period not in VALID_PERIODS:
        raise ValueError("期間輸入不合法，請使用 1y / 2y / 5y / max 或 yfinance 支援值。")
    return period


def _ask_yes_no(prompt: str) -> bool:
    return input(prompt + "\n").strip().lower() == "y"


def _ask_optional_float(prompt: str) -> float | None:
    value = input(prompt + "\n").strip()
    if not value:
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"{prompt} 必須是數字。") from exc
    if number <= 0:
        raise ValueError(f"{prompt} 必須大於 0。")
    return number


def _ask_optional_int(prompt: str) -> int | None:
    value = input(prompt + "\n").strip()
    if not value:
        return None
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError(f"{prompt} 必須是整數。") from exc
    if number <= 0:
        raise ValueError(f"{prompt} 必須大於 0。")
    return number


def _ask_position_size() -> float:
    value = input("每次投入資金比例，例如 1.0，空白預設 1.0\n").strip()
    if not value:
        return 1.0
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError("每次投入資金比例必須是數字。") from exc
    if not 0 < number <= 1:
        raise ValueError("每次投入資金比例必須大於 0 且小於等於 1。")
    return number


def _validate_options(options: MainOptions) -> None:
    if not options.stock_id.strip():
        raise ValueError("股票代號不可空白。")
    if options.period not in VALID_PERIODS:
        raise ValueError(f"期間不合法: {options.period}。")
    if options.interval not in VALID_INTERVALS:
        raise ValueError(f"K 線週期不合法: {options.interval}。")
    if not 0 < options.position_size <= 1:
        raise ValueError("position_size 必須大於 0 且小於等於 1。")
    if options.max_hold_days is not None and options.max_hold_days <= 0:
        raise ValueError("max_hold_days 必須大於 0。")


def _interactive_options() -> MainOptions:
    stock_id = input("請輸入股票代號：\n").strip()
    if not stock_id:
        raise ValueError("股票代號不可空白。")

    return MainOptions(
        stock_id=stock_id,
        period=_ask_period(),
        interval=DEFAULT_INTERVAL,
        auto_adjust=DEFAULT_AUTO_ADJUST,
        force_refresh=_ask_yes_no("是否強制重新下載資料？y/n"),
        stop_loss_pct=_ask_optional_float("停損百分比，例如 8，空白代表不使用"),
        take_profit_pct=_ask_optional_float("停利百分比，例如 20，空白代表不使用"),
        max_hold_days=_ask_optional_int("最大持有天數，例如 30，空白代表不使用"),
        position_size=_ask_position_size(),
        export_excel=_ask_yes_no("是否匯出 Excel？y/n"),
        save_chart=_ask_yes_no("是否儲存圖表？y/n"),
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="台股單股票技術分析工具")
    parser.add_argument("--stock", help="股票代號，例如 2330")
    parser.add_argument("--period", default=DEFAULT_PERIOD, choices=sorted(VALID_PERIODS))
    parser.add_argument("--interval", default=DEFAULT_INTERVAL, choices=sorted(VALID_INTERVALS))
    parser.add_argument("--force-refresh", action="store_true", help="忽略今日快取並重新下載")
    parser.add_argument(
        "--auto-adjust",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_AUTO_ADJUST,
        help="是否使用 yfinance 除權息調整價",
    )
    parser.add_argument("--stop-loss", type=float, dest="stop_loss_pct", help="停損百分比，例如 8")
    parser.add_argument("--take-profit", type=float, dest="take_profit_pct", help="停利百分比，例如 20")
    parser.add_argument("--max-hold-days", type=int, help="最大持有天數，例如 30")
    parser.add_argument("--position-size", type=float, default=1.0, help="每次投入資金比例，預設 1.0")
    parser.add_argument("--export-excel", action="store_true", help="匯出 Excel 報表")
    parser.add_argument("--save-chart", action="store_true", help="儲存技術分析圖表")
    return parser.parse_args(argv)


def _cli_options(argv: list[str] | None = None) -> MainOptions:
    args = _parse_args(argv)
    if not args.stock:
        raise ValueError("CLI 模式請使用 --stock 指定股票代號，或不帶參數進入互動式模式。")
    return MainOptions(
        stock_id=args.stock.strip(),
        period=args.period,
        interval=args.interval,
        auto_adjust=args.auto_adjust,
        force_refresh=args.force_refresh,
        stop_loss_pct=args.stop_loss_pct,
        take_profit_pct=args.take_profit_pct,
        max_hold_days=args.max_hold_days,
        position_size=args.position_size,
        export_excel=args.export_excel,
        save_chart=args.save_chart,
    )


def run_analysis_result(options: MainOptions) -> dict[str, object]:
    """Run analysis and return structured results without printing.

    GUI/Web integrations can use this function directly while the existing CLI
    keeps using run_analysis() for its human-readable output.
    """
    _validate_options(options)
    analysis = analyze_stock(
        options.stock_id,
        period=options.period,
        interval=options.interval,
        auto_adjust=options.auto_adjust,
        force_refresh=options.force_refresh,
    )
    sig_df = analysis.signal_df
    symbol = analysis.symbol

    bt = run_backtest(
        sig_df,
        initial_capital=INITIAL_CAPITAL,
        fee_rate=FEE_RATE,
        tax_rate=TAX_RATE,
        stop_loss_pct=options.stop_loss_pct,
        take_profit_pct=options.take_profit_pct,
        max_hold_days=options.max_hold_days,
        position_size=options.position_size,
    )
    summary = analysis.summary

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    chart_path = None
    if options.save_chart:
        chart_path = OUTPUT_DIR / f"{options.stock_id}_chart.png"
        plot_stock_chart(sig_df, stock_id=options.stock_id, symbol=symbol, save_path=chart_path)

    report_path = None
    if options.export_excel:
        report_path = export_excel_report(
            stock_id=options.stock_id,
            df=sig_df,
            backtest_result=bt,
            summary=summary,
            output_dir=OUTPUT_DIR,
        )

    return {
        "analysis": analysis,
        "signal": sig_df,
        "summary": summary,
        "backtest": bt,
        "symbol": symbol,
        "excel_path": report_path,
        "chart_path": chart_path,
    }


def run_analysis(options: MainOptions) -> None:
    print("\n\u4e0b\u8f09\u8cc7\u6599\u3001\u8a08\u7b97\u6280\u8853\u6307\u6a19\u8207\u7522\u751f\u8a0a\u865f\u4e2d...")
    result = run_analysis_result(options)
    summary = result["summary"]
    bt = result["backtest"]
    symbol = result["symbol"]

    print(f"\n\u80a1\u7968\u4ee3\u865f\uff1a{options.stock_id}")
    print(f"\u8cc7\u6599\u4ee3\u865f\uff1a{symbol}")
    print(f"\u6700\u65b0\u6536\u76e4\u50f9\uff1a{summary['Latest Close']}")
    print(f"MA5\uff1a{summary['MA5']}")
    print(f"MA20\uff1a{summary['MA20']}")
    print(f"MA60\uff1a{summary['MA60']}")
    print(f"RSI\uff1a{summary['RSI']}")
    print(f"MACD\uff1a{summary['MACD']}")
    print(f"Signal\uff1a{summary['Signal']}")
    print(f"\n\u6280\u8853\u5206\u6578\uff1a{summary['Tech Score']}")
    print(f"\u6700\u65b0\u8a0a\u865f\uff1a{summary['Latest Signal']}")
    print("\n\u5206\u6790\uff1a")
    print(summary["Analysis"])

    print("\n\u56de\u6e2c\u7d50\u679c\uff1a")
    print(f"\u521d\u59cb\u8cc7\u91d1\uff1a{bt['Initial Capital']}")
    print(f"\u6700\u7d42\u8cc7\u91d1\uff1a{bt['Final Capital']}")
    print(f"\u7e3d\u5831\u916c\u7387\uff1a{bt['Total Return %']}%")
    print(f"\u4ea4\u6613\u6b21\u6578\uff1a{bt['Trade Count']}")
    print(f"\u52dd\u7387\uff1a{bt['Win Rate %']}%")
    print(f"\u6700\u5927\u56de\u64a4\uff1a{bt['Max Drawdown %']}%")
    print(f"\u5e73\u5747\u7372\u5229\uff1a{bt['Avg Profit']}")
    print(f"\u5e73\u5747\u8667\u640d\uff1a{bt['Avg Loss']}")

    if options.save_chart:
        print(f"\u5716\u8868\u5df2\u5132\u5b58\uff1a{result['chart_path']}")

    if options.export_excel:
        print(f"Excel \u5831\u8868\u5df2\u532f\u51fa\uff1a{result['excel_path']}")

    print("\n\u63d0\u9192\uff1a\u672c\u5de5\u5177\u50c5\u4f9b\u6280\u8853\u5206\u6790\u8207\u56de\u6e2c\u7814\u7a76\uff0c\u4e0d\u4fdd\u8b49\u6295\u8cc7\u7e3e\u6548\uff0c\u4e5f\u4e0d\u63d0\u4f9b\u81ea\u52d5\u4e0b\u55ae\u3002")

def main(argv: list[str] | None = None) -> None:
    try:
        effective_argv = sys.argv[1:] if argv is None else argv
        options = _interactive_options() if not effective_argv else _cli_options(effective_argv)
        run_analysis(options)
    except (ValueError, DataLoaderError, IndicatorError, ReportError) as exc:
        print(f"錯誤：{exc}")
    except KeyboardInterrupt:
        print("\n已取消。")
    except Exception as exc:
        print(f"未預期錯誤：{exc}")


if __name__ == "__main__":
    main()
