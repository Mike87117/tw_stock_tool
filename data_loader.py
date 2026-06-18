from datetime import date
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

from config import CACHE_DIR, DEFAULT_AUTO_ADJUST, VALID_INTERVALS, VALID_PERIODS


class DataLoaderError(Exception):
    pass


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _validate_inputs(stock_id: str, period: str, interval: str) -> None:
    if not stock_id or not stock_id.strip():
        raise DataLoaderError("股票代號不可空白。")
    if period not in VALID_PERIODS:
        raise DataLoaderError(f"分析期間不合法: {period}。")
    if interval not in VALID_INTERVALS:
        raise DataLoaderError(f"K 線週期不合法: {interval}。")


def _cache_path(symbol: str, period: str, interval: str, auto_adjust: bool) -> Path:
    safe_symbol = symbol.replace("/", "_")
    return CACHE_DIR / f"{safe_symbol}_{period}_{interval}_adjusted-{auto_adjust}.csv"


def _is_cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    modified = date.fromtimestamp(path.stat().st_mtime)
    return modified == date.today()


def _read_cache(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index.name = "Date"
    return df


def _write_cache(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)


def _prepare_ohlcv(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    df = _normalize_columns(df)
    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise DataLoaderError(f"資料欄位缺失: {missing}")
    out = df[required].dropna(subset=["Open", "High", "Low", "Close"])
    if out.empty:
        raise DataLoaderError(f"{symbol} 下載後無可用 OHLC 資料。")
    out.index.name = "Date"
    return out


def _period_start(period: str) -> pd.Timestamp:
    today = pd.Timestamp.today().normalize()
    months = {
        "1d": 1,
        "5d": 1,
        "1mo": 1,
        "3mo": 3,
        "6mo": 6,
        "1y": 12,
        "2y": 24,
        "5y": 60,
        "10y": 120,
        "max": 180,
    }
    if period == "ytd":
        return pd.Timestamp(year=today.year, month=1, day=1)
    return today - pd.DateOffset(months=months.get(period, 12))


def _month_starts(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    cursor = pd.Timestamp(year=start.year, month=start.month, day=1)
    final = pd.Timestamp(year=end.year, month=end.month, day=1)
    months = []
    while cursor <= final:
        months.append(cursor)
        cursor += pd.DateOffset(months=1)
    return months


def _download_twse_stock(stock_id: str, period: str, interval: str) -> pd.DataFrame:
    if interval != "1d":
        raise DataLoaderError("TWSE fallback 僅支援 1d。")

    start = _period_start(period)
    rows = []
    for month in _month_starts(start, pd.Timestamp.today().normalize()):
        params = {
            "response": "json",
            "date": month.strftime("%Y%m01"),
            "stockNo": stock_id,
        }
        response = requests.get(
            "https://www.twse.com.tw/exchangeReport/STOCK_DAY",
            params=params,
            timeout=20,
        )
        data = response.json()
        if data.get("stat") != "OK":
            continue
        rows.extend(data.get("data", []))

    if not rows:
        raise DataLoaderError(f"TWSE fallback 無資料: {stock_id}")

    parsed = []
    for row in rows:
        roc_year, month, day = row[0].split("/")
        parsed.append(
            {
                "Date": pd.Timestamp(int(roc_year) + 1911, int(month), int(day)),
                "Open": float(row[3].replace(",", "")),
                "High": float(row[4].replace(",", "")),
                "Low": float(row[5].replace(",", "")),
                "Close": float(row[6].replace(",", "")),
                "Volume": int(row[1].replace(",", "")),
            }
        )

    df = pd.DataFrame(parsed).drop_duplicates(subset=["Date"]).set_index("Date").sort_index()
    df = df[df.index >= start]
    if period == "1d":
        df = df.tail(1)
    elif period == "5d":
        df = df.tail(5)
    return _prepare_ohlcv(df, f"{stock_id}.TW")


def download_tw_stock(
    stock_id: str,
    period: str = "1y",
    interval: str = "1d",
    auto_adjust: bool | None = None,
    force_refresh: bool = False,
    verbose: bool = False,
) -> tuple[pd.DataFrame, str]:
    _validate_inputs(stock_id, period, interval)
    stock_id = stock_id.strip()
    if auto_adjust is None:
        auto_adjust = DEFAULT_AUTO_ADJUST
    suffixes = [".TW", ".TWO"]
    errors = []

    for suffix in suffixes:
        symbol = f"{stock_id}{suffix}"
        cache_path = _cache_path(symbol, period, interval, auto_adjust)
        try:
            if not force_refresh and _is_cache_fresh(cache_path):
                try:
                    cached_df = _read_cache(cache_path)
                    if verbose:
                        print(f"{symbol}: From cache")
                    return _prepare_ohlcv(cached_df, symbol), symbol
                except Exception:
                    pass

            df = yf.download(
                symbol,
                period=period,
                interval=interval,
                auto_adjust=auto_adjust,
                progress=False,
                threads=False,
            )
            if not df.empty:
                df = _prepare_ohlcv(df, symbol)
                try:
                    _write_cache(df, cache_path)
                except Exception:
                    pass
                if verbose:
                    print(f"{symbol}: Downloaded")
                return df, symbol
            errors.append(f"{symbol} 無資料")
        except Exception as exc:
            errors.append(f"{symbol} 下載失敗: {exc}")

        if suffix == ".TW" and not auto_adjust:
            try:
                df = _download_twse_stock(stock_id, period, interval)
                try:
                    _write_cache(df, cache_path)
                except Exception:
                    pass
                if verbose:
                    print(f"{symbol}: Downloaded from TWSE fallback")
                return df, symbol
            except Exception as exc:
                errors.append(f"{symbol} TWSE fallback 失敗: {exc}")

    raise DataLoaderError(
        "找不到股票資料，請確認代號是否正確或稍後再試。\n嘗試紀錄: " + " | ".join(errors)
    )
