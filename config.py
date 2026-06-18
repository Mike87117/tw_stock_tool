from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = BASE_DIR / "cache"

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
