"""Yahoo Finance market data provider."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import logging

import pandas as pd
import yfinance as yf

from tw_stock_tool.utils.console_lock import console_io_lock


def download_yfinance_quiet(
    symbol: str,
    period: str,
    interval: str,
    auto_adjust: bool,
) -> pd.DataFrame:
    """Download Yahoo Finance data while suppressing provider console output."""
    # redirect_stdout/stderr are process-global, so serialize yfinance calls.
    with console_io_lock():
        yf_logger = logging.getLogger("yfinance")
        previous_disabled = yf_logger.disabled
        previous_level = yf_logger.level
        previous_propagate = yf_logger.propagate
        try:
            yf_logger.disabled = True
            yf_logger.setLevel(logging.CRITICAL + 1)
            yf_logger.propagate = False
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                return yf.download(
                    symbol,
                    period=period,
                    interval=interval,
                    auto_adjust=auto_adjust,
                    progress=False,
                    threads=False,
                )
        finally:
            yf_logger.disabled = previous_disabled
            yf_logger.setLevel(previous_level)
            yf_logger.propagate = previous_propagate
