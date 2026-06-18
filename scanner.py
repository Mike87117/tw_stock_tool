from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from analysis import StockAnalysis, analyze_stock
from config import DEFAULT_AUTO_ADJUST, DEFAULT_INTERVAL, DEFAULT_PERIOD

ProgressCallback = Callable[[int, int, str, str], None]


@dataclass(frozen=True)
class ScanConfig:
    period: str = DEFAULT_PERIOD
    interval: str = DEFAULT_INTERVAL
    auto_adjust: bool = DEFAULT_AUTO_ADJUST
    force_refresh: bool = False
    max_workers: int = 8
    min_score: float | None = None
    min_volume_ratio: float | None = None
    min_close: float | None = None
    max_close: float | None = None
    signals: tuple[str, ...] | None = None
    sort_by: str = "Score"
    top: int | None = None
    errors_only: bool = False


SUPPORTED_SORT_COLUMNS = {"Score", "Volume_Ratio", "RSI", "Close", "ATR"}


def normalize_stock_ids(stock_ids: Iterable[str]) -> list[str]:
    normalized = []
    seen = set()
    for stock_id in stock_ids:
        value = str(stock_id).strip()
        if not value or value.startswith("#"):
            continue
        if value not in seen:
            normalized.append(value)
            seen.add(value)
    return normalized


def load_stock_ids_from_file(file_path: str | Path) -> list[str]:
    path = Path(file_path)
    try:
        return normalize_stock_ids(path.read_text(encoding="utf-8").splitlines())
    except FileNotFoundError as exc:
        raise ValueError(f"股票清單檔案不存在: {path}") from exc
    except OSError as exc:
        raise ValueError(f"讀取股票清單失敗: {path} ({exc})") from exc


def _analysis_to_row(analysis: StockAnalysis) -> dict[str, object]:
    latest = analysis.latest
    latest_date = pd.Timestamp(latest.name).strftime("%Y-%m-%d")
    return {
        "Rank": None,
        "Stock": analysis.stock_id,
        "Symbol": analysis.symbol,
        "Date": latest_date,
        "Signal": str(latest["Signal"]),
        "Score": round(float(latest["Score"]), 2),
        "Close": round(float(latest["Close"]), 2),
        "MA5": round(float(latest["MA5"]), 2),
        "MA20": round(float(latest["MA20"]), 2),
        "MA60": round(float(latest["MA60"]), 2),
        "RSI": round(float(latest["RSI"]), 2),
        "MACD": round(float(latest["MACD"]), 4),
        "MACD_Signal": round(float(latest["MACD_Signal"]), 4),
        "K": round(float(latest["K"]), 2),
        "D": round(float(latest["D"]), 2),
        "BB_Upper": round(float(latest["BB_Upper"]), 2),
        "BB_Middle": round(float(latest["BB_Middle"]), 2),
        "BB_Lower": round(float(latest["BB_Lower"]), 2),
        "ATR": round(float(latest["ATR"]), 2),
        "OBV": round(float(latest["OBV"]), 2),
        "Volume_Ratio": round(float(latest["Volume_Ratio"]), 4),
        "Analysis": str(analysis.summary.get("Analysis", "")),
        "Status": "OK",
        "Error": "",
    }


def scan_one_stock(stock_id: str, config: ScanConfig) -> dict[str, object]:
    try:
        analysis = analyze_stock(
            stock_id=stock_id,
            period=config.period,
            interval=config.interval,
            auto_adjust=config.auto_adjust,
            force_refresh=config.force_refresh,
        )
        return _analysis_to_row(analysis)
    except Exception as exc:
        return {
            "Rank": None,
            "Stock": stock_id,
            "Symbol": "",
            "Date": "",
            "Signal": "",
            "Score": float("-inf"),
            "Close": None,
            "MA5": None,
            "MA20": None,
            "MA60": None,
            "RSI": None,
            "MACD": None,
            "MACD_Signal": None,
            "K": None,
            "D": None,
            "BB_Upper": None,
            "BB_Middle": None,
            "BB_Lower": None,
            "ATR": None,
            "OBV": None,
            "Volume_Ratio": None,
            "Analysis": "",
            "Status": "ERROR",
            "Error": str(exc),
        }


def _filter_ok_rows(ok: pd.DataFrame, config: ScanConfig) -> pd.DataFrame:
    filtered = ok.copy()
    if config.min_score is not None:
        filtered = filtered[pd.to_numeric(filtered["Score"], errors="coerce") >= config.min_score]
    if config.min_volume_ratio is not None:
        volume_ratio = pd.to_numeric(filtered["Volume_Ratio"], errors="coerce")
        filtered = filtered[volume_ratio >= config.min_volume_ratio]
    if config.min_close is not None:
        close = pd.to_numeric(filtered["Close"], errors="coerce")
        filtered = filtered[close >= config.min_close]
    if config.max_close is not None:
        close = pd.to_numeric(filtered["Close"], errors="coerce")
        filtered = filtered[close <= config.max_close]
    if config.signals:
        allowed = {signal.upper() for signal in config.signals}
        filtered = filtered[filtered["Signal"].astype(str).str.upper().isin(allowed)]
    return filtered


def _sort_ok_rows(ok: pd.DataFrame, sort_by: str) -> pd.DataFrame:
    if sort_by not in SUPPORTED_SORT_COLUMNS:
        raise ValueError(f"不支援的排序欄位: {sort_by}。")
    sortable = ok.copy()
    sortable["_SortValue"] = pd.to_numeric(sortable[sort_by], errors="coerce").fillna(float("-inf"))
    return sortable.sort_values(
        by=["_SortValue", "Stock"],
        ascending=[False, True],
        kind="mergesort",
    ).drop(columns=["_SortValue"])


def scan_stocks(
    stock_ids: Iterable[str],
    config: ScanConfig | None = None,
    progress_callback: ProgressCallback | None = None,
) -> pd.DataFrame:
    stocks = normalize_stock_ids(stock_ids)
    if not stocks:
        raise ValueError("股票清單不可空白。")

    scan_config = config or ScanConfig()
    workers = max(1, min(scan_config.max_workers, len(stocks)))
    rows: list[dict[str, object]] = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(scan_one_stock, stock_id, scan_config): stock_id
            for stock_id in stocks
        }
        total = len(future_map)
        for completed, future in enumerate(as_completed(future_map), start=1):
            stock_id = future_map[future]
            row = future.result()
            rows.append(row)
            if progress_callback:
                progress_callback(completed, total, stock_id, str(row["Status"]))

    result = pd.DataFrame(rows)
    failed = result[result["Status"] != "OK"].sort_values(by="Stock", kind="mergesort")
    if scan_config.errors_only:
        ranked = failed.reset_index(drop=True)
        ranked["Rank"] = None
        return ranked

    ok = _filter_ok_rows(result[result["Status"] == "OK"], scan_config)
    ok = _sort_ok_rows(ok, scan_config.sort_by)
    if scan_config.top is not None:
        ok = ok.head(max(scan_config.top, 0))

    ranked = pd.concat([ok, failed], ignore_index=True)
    ok_count = int((ranked["Status"] == "OK").sum())
    if ok_count:
        ranked.loc[: ok_count - 1, "Rank"] = range(1, ok_count + 1)
    ranked.loc[ranked["Status"] != "OK", "Score"] = None
    return ranked
