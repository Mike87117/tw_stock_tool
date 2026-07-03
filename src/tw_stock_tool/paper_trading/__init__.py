"""
Simulated paper trading models.
Research-only simulated models.
"""

from .engine import run_simulated_paper_trading, run_simulated_paper_trading_result
from .results import (
    SimulatedPaperTradingResult,
    build_simulated_paper_trading_result,
    build_simulated_paper_trading_summary,
    build_simulated_order_rows,
    build_simulated_fill_rows,
    build_simulated_paper_trading_report_data,
)
from .exporters import export_simulated_paper_trading_markdown

__all__ = [
    "run_simulated_paper_trading",
    "run_simulated_paper_trading_result",
    "SimulatedPaperTradingResult",
    "build_simulated_paper_trading_result",
    "build_simulated_paper_trading_summary",
    "build_simulated_order_rows",
    "build_simulated_fill_rows",
    "build_simulated_paper_trading_report_data",
    "export_simulated_paper_trading_markdown",
]
