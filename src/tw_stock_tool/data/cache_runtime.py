from pathlib import Path

import pandas as pd


def _cache_path(symbol: str, period: str, interval: str, auto_adjust: bool, *, cache_dir: Path) -> Path:
    safe_symbol = symbol.replace("/", "_")
    return cache_dir / f"{safe_symbol}_{period}_{interval}_adjusted-{auto_adjust}.csv"


def _is_cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    now = pd.Timestamp.now(tz="Asia/Taipei")
    mtime = path.stat().st_mtime
    modified = pd.Timestamp(mtime, unit="s", tz="UTC").tz_convert("Asia/Taipei")
    if modified.date() != now.date():
        return False
    market_close = now.replace(hour=14, minute=30, second=0, microsecond=0)
    if now >= market_close:
        return modified >= market_close
    return True


def _get_cache_age_days(path: Path) -> float:
    mtime = path.stat().st_mtime
    now = pd.Timestamp.now(tz="UTC").timestamp()
    return max(0.0, (now - mtime) / 86400.0)


def _read_cache(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index.name = "Date"
    return df


def _write_cache(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)
