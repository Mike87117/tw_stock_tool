from dataclasses import dataclass

import pandas as pd

from tw_stock_tool.utils.config import DEFAULT_AUTO_ADJUST, DEFAULT_INTERVAL, DEFAULT_PERIOD
from tw_stock_tool.data.data_loader import download_tw_stock
from tw_stock_tool.analysis.indicators import add_indicators
from tw_stock_tool.analysis.signals import generate_signals, latest_analysis_text

SIGNAL_READY_COLUMNS = ["MA20", "MA60", "MACD_Signal", "RSI"]


@dataclass(frozen=True)
class StockAnalysis:
    stock_id: str
    symbol: str
    raw_df: pd.DataFrame
    indicator_df: pd.DataFrame
    signal_df: pd.DataFrame
    latest: pd.Series
    summary: dict[str, object]


def build_latest_summary(stock_id: str, symbol: str, latest: pd.Series) -> dict[str, object]:
    return {
        "Stock ID": stock_id,
        "Symbol": symbol,
        "Latest Close": round(float(latest["Close"]), 2),
        "MA5": round(float(latest["MA5"]), 2),
        "MA20": round(float(latest["MA20"]), 2),
        "MA60": round(float(latest["MA60"]), 2),
        "RSI": round(float(latest["RSI"]), 2),
        "MACD": round(float(latest["MACD"]), 4),
        "Signal": round(float(latest["MACD_Signal"]), 4),
        "Tech Score": round(float(latest["Score"]), 2),
        "Latest Signal": str(latest["Signal"]),
        "Analysis": latest_analysis_text(latest),
    }


def analyze_stock(
    stock_id: str,
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    auto_adjust: bool = DEFAULT_AUTO_ADJUST,
    force_refresh: bool = False,
) -> StockAnalysis:
    raw_df, symbol = download_tw_stock(
        stock_id,
        period=period,
        interval=interval,
        auto_adjust=auto_adjust,
        force_refresh=force_refresh,
    )
    indicator_df = add_indicators(raw_df)
    signal_df = generate_signals(indicator_df).dropna(subset=SIGNAL_READY_COLUMNS)
    if signal_df.empty:
        raise ValueError("資料不足，無法得到有效訊號，請改用較長 period。")

    latest = signal_df.iloc[-1]
    summary = build_latest_summary(stock_id=stock_id, symbol=symbol, latest=latest)
    return StockAnalysis(
        stock_id=stock_id,
        symbol=symbol,
        raw_df=raw_df,
        indicator_df=indicator_df,
        signal_df=signal_df,
        latest=latest,
        summary=summary,
    )
