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
from .exporters import (
    export_simulated_paper_trading_markdown,
    export_simulated_paper_trading_csv_bundle,
)
from .export_files import (
    export_simulated_paper_trading_markdown_file,
    export_simulated_paper_trading_csv_files,
)
from .serialization import (
    serialize_simulated_paper_trading_result,
    deserialize_simulated_paper_trading_result,
    export_simulated_paper_trading_result_json,
    load_simulated_paper_trading_result_json,
)

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
    "export_simulated_paper_trading_csv_bundle",
    "export_simulated_paper_trading_markdown_file",
    "export_simulated_paper_trading_csv_files",
    "serialize_simulated_paper_trading_result",
    "deserialize_simulated_paper_trading_result",
    "export_simulated_paper_trading_result_json",
    "load_simulated_paper_trading_result_json",
]
