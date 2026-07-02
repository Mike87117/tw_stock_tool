import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

OUTPUT_DIR = Path(os.environ.get("TW_STOCK_TOOL_OUTPUT_DIR", Path.cwd() / "output"))
CACHE_DIR = Path(os.environ.get("TW_STOCK_TOOL_CACHE_DIR", Path.cwd() / "cache"))

try:
    MAX_STALE_CACHE_DAYS = int(os.environ.get("TW_STOCK_TOOL_MAX_STALE_CACHE_DAYS", 14))
    if MAX_STALE_CACHE_DAYS <= 0:
        MAX_STALE_CACHE_DAYS = 14
except ValueError:
    MAX_STALE_CACHE_DAYS = 14

VALID_PERIODS = {
    "1d",
    "5d",
    "1mo",
    "3mo",
    "6mo",
    "1y",
    "2y",
    "5y",
    "10y",
    "ytd",
    "max",
}
VALID_INTERVALS = {"1d", "1wk", "1mo"}

DEFAULT_PERIOD = "1y"
DEFAULT_INTERVAL = "1d"
DEFAULT_AUTO_ADJUST = False

INITIAL_CAPITAL = 100000
FEE_RATE = 0.001425
TAX_RATE = 0.003
