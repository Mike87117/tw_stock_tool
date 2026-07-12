from pathlib import Path

import pandas as pd


def cache_path(cache_dir: Path, symbol: str, period: str, interval: str, auto_adjust: bool) -> Path:
    return cache_dir / f"{symbol.replace('/', '_')}_{period}_{interval}_adjusted-{auto_adjust}.csv"


def is_cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    now = pd.Timestamp.now(tz="Asia/Taipei")
    modified = pd.Timestamp(path.stat().st_mtime, unit="s", tz="UTC").tz_convert("Asia/Taipei")
    if modified.date() != now.date():
        return False
    market_close = now.replace(hour=14, minute=30, second=0, microsecond=0)
    return modified >= market_close if now >= market_close else True


def get_cache_age_days(path: Path) -> float:
    return max(0.0, (pd.Timestamp.now(tz="UTC").timestamp() - path.stat().st_mtime) / 86400.0)


def read_cache(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index.name = "Date"
    return df


def write_cache(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)
