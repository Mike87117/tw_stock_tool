from pathlib import Path

import pandas as pd

from tw_stock_tool.utils.config import CACHE_DIR


def list_cache_files(cache_dir: Path = CACHE_DIR) -> list[Path]:
    if not cache_dir.exists():
        return []
    return sorted(path for path in cache_dir.glob("*.csv") if path.is_file())


def clear_cache(cache_dir: Path = CACHE_DIR) -> int:
    count = 0
    for path in list_cache_files(cache_dir):
        path.unlink()
        count += 1
    return count


def cache_summary(cache_dir: Path = CACHE_DIR) -> pd.DataFrame:
    rows = []
    for path in list_cache_files(cache_dir):
        stat = path.stat()
        rows.append(
            {
                "File": path.name,
                "Path": str(path),
                "Size KB": round(stat.st_size / 1024, 2),
                "Modified": pd.Timestamp.fromtimestamp(stat.st_mtime),
            }
        )
    return pd.DataFrame(rows, columns=["File", "Path", "Size KB", "Modified"])
