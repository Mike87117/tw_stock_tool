import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from weakref import WeakValueDictionary

import pandas as pd


# Keep one lock per active path without retaining every historical cache key.
_cache_locks = WeakValueDictionary()
_cache_locks_guard = Lock()


def _cache_lock(path: Path):
    key = os.path.normcase(os.path.abspath(path))
    with _cache_locks_guard:
        lock = _cache_locks.get(key)
        if lock is None:
            lock = Lock()
            _cache_locks[key] = lock
        return lock


def _cache_path(symbol: str, period: str, interval: str, auto_adjust: bool, *, cache_dir: Path) -> Path:
    for name, value in (("symbol", symbol), ("period", period), ("interval", interval)):
        if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value) is None:
            raise ValueError(f"Invalid cache key component: {name}.")
    path = cache_dir / f"{symbol}_{period}_{interval}_adjusted-{auto_adjust}.csv"
    if not path.resolve().is_relative_to(cache_dir.resolve()):
        raise ValueError("Cache path must stay within cache_dir.")
    return path


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
    with _cache_lock(path):
        df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index.name = "Date"
    return df


def _write_cache(df: pd.DataFrame, path: Path) -> None:
    """Replace a cache only after a complete write, preserving it on failure."""
    # Windows can reject simultaneous replaces or a replace during a CSV read.
    with _cache_lock(path):
        _write_cache_locked(df, path)


def _write_cache_locked(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", delete=False,
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp",
        ) as temporary:
            temporary_path = Path(temporary.name)
            df.to_csv(temporary)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
