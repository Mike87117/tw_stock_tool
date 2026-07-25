"""
Filesystem helpers for multi-symbol simulated portfolio trading result JSON serialization.
"""

from pathlib import Path

from tw_stock_tool.paper_trading.portfolio_results import SimulatedPortfolioTradingResult
from tw_stock_tool.paper_trading.portfolio_serialization import (
    export_simulated_portfolio_trading_result_json,
    load_simulated_portfolio_trading_result_json,
)
from tw_stock_tool.utils.output import write_text_report


def export_simulated_portfolio_trading_result_json_file(
    result: SimulatedPortfolioTradingResult,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Export a SimulatedPortfolioTradingResult to a UTF-8 JSON file."""
    content = export_simulated_portfolio_trading_result_json(result)
    return write_text_report(content, path, overwrite=overwrite)


def load_simulated_portfolio_trading_result_json_file(
    path: str | Path,
) -> SimulatedPortfolioTradingResult:
    """Load a SimulatedPortfolioTradingResult from a UTF-8 JSON file."""
    content = Path(path).read_text(encoding="utf-8")
    return load_simulated_portfolio_trading_result_json(content)
