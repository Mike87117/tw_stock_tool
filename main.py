import argparse
import sys
from dataclasses import dataclass

from analysis import analyze_stock
from backtest import run_backtest
from config import (
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
from data_loader import DataLoaderError
from indicators import IndicatorError
from plotter import plot_stock_chart
from report import ReportError, export_excel_report


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


def run_analysis(options: MainOptions) -> None:
    _validate_options(options)
    print("\n下載資料、計算技術指標與產生訊號中...")
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

    print(f"\n股票代號：{options.stock_id}")
    print(f"資料代號：{symbol}")
    print(f"最新收盤價：{summary['Latest Close']}")
    print(f"MA5：{summary['MA5']}")
    print(f"MA20：{summary['MA20']}")
    print(f"MA60：{summary['MA60']}")
    print(f"RSI：{summary['RSI']}")
    print(f"MACD：{summary['MACD']}")
    print(f"Signal：{summary['Signal']}")
    print(f"\n技術分數：{summary['Tech Score']}")
    print(f"最新訊號：{summary['Latest Signal']}")
    print("\n分析：")
    print(summary["Analysis"])

    print("\n回測結果：")
    print(f"初始資金：{bt['Initial Capital']}")
    print(f"最終資金：{bt['Final Capital']}")
    print(f"總報酬率：{bt['Total Return %']}%")
    print(f"交易次數：{bt['Trade Count']}")
    print(f"勝率：{bt['Win Rate %']}%")
    print(f"最大回撤：{bt['Max Drawdown %']}%")
    print(f"平均獲利：{bt['Avg Profit']}")
    print(f"平均虧損：{bt['Avg Loss']}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if options.save_chart:
        chart_path = OUTPUT_DIR / f"{options.stock_id}_chart.png"
        plot_stock_chart(sig_df, stock_id=options.stock_id, symbol=symbol, save_path=chart_path)
        print(f"圖表已儲存：{chart_path}")

    if options.export_excel:
        report_path = export_excel_report(
            stock_id=options.stock_id,
            df=sig_df,
            backtest_result=bt,
            summary=summary,
            output_dir=OUTPUT_DIR,
        )
        print(f"Excel 報表已匯出：{report_path}")

    print("\n提醒：本工具僅供技術分析與回測研究，不保證投資績效，也不提供自動下單。")


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
