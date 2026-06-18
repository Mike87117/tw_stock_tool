from analysis import analyze_stock
from backtest import run_backtest
from config import (
    DEFAULT_INTERVAL,
    DEFAULT_PERIOD,
    FEE_RATE,
    INITIAL_CAPITAL,
    OUTPUT_DIR,
    TAX_RATE,
    VALID_PERIODS,
)
from data_loader import DataLoaderError
from indicators import IndicatorError
from plotter import plot_stock_chart
from report import ReportError, export_excel_report


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


def main() -> None:
    try:
        stock_id = input("請輸入股票代號：\n").strip()
        if not stock_id:
            raise ValueError("股票代號不可空白。")

        period = _ask_period()
        force_refresh = _ask_yes_no("是否強制重新下載資料？y/n")
        stop_loss_pct = _ask_optional_float("停損百分比，例如 8，空白代表不使用")
        take_profit_pct = _ask_optional_float("停利百分比，例如 20，空白代表不使用")
        max_hold_days = _ask_optional_int("最大持有天數，例如 30，空白代表不使用")
        position_size = _ask_position_size()
        export_excel = _ask_yes_no("是否匯出 Excel？y/n")
        save_chart = _ask_yes_no("是否儲存圖表？y/n")

        print("\n下載資料、計算技術指標與產生訊號中...")
        analysis = analyze_stock(
            stock_id,
            period=period,
            interval=DEFAULT_INTERVAL,
            force_refresh=force_refresh,
        )
        sig_df = analysis.signal_df
        symbol = analysis.symbol

        bt = run_backtest(
            sig_df,
            initial_capital=INITIAL_CAPITAL,
            fee_rate=FEE_RATE,
            tax_rate=TAX_RATE,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            max_hold_days=max_hold_days,
            position_size=position_size,
        )
        summary = analysis.summary

        print(f"\n股票代號：{stock_id}")
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
        chart_path = OUTPUT_DIR / f"{stock_id}_chart.png" if save_chart else None
        plot_stock_chart(sig_df, stock_id=stock_id, symbol=symbol, save_path=chart_path)
        if chart_path:
            print(f"圖表已儲存：{chart_path}")

        if export_excel:
            report_path = export_excel_report(
                stock_id=stock_id,
                df=sig_df,
                backtest_result=bt,
                summary=summary,
                output_dir=OUTPUT_DIR,
            )
            print(f"Excel 報表已匯出：{report_path}")

        print("\n提醒：本工具僅供技術分析與回測參考，不保證可準確預測股價。")
    except (ValueError, DataLoaderError, IndicatorError, ReportError) as exc:
        print(f"錯誤：{exc}")
    except Exception as exc:
        print(f"未預期錯誤：{exc}")


if __name__ == "__main__":
    main()
