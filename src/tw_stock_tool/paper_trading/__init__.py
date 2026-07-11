"""
Simulated paper trading models.
Research-only simulated models.
"""

from .models import (
    SimulatedTradeEventType,
    SimulatedTradeStatus,
    SimulatedTradeLogRecord,
)
from .engine import run_simulated_paper_trading, run_simulated_paper_trading_result
from .results import (
    SimulatedPaperTradingResult,
    build_simulated_paper_trading_result,
    build_simulated_paper_trading_summary,
    build_simulated_order_rows,
    build_simulated_fill_rows,
    build_simulated_trade_log_rows,
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
from .serialization_files import (
    export_simulated_paper_trading_result_json_file,
    load_simulated_paper_trading_result_json_file,
)
from .backtest_converter import (
    convert_backtest_result_to_simulated_paper_trading_result,
)

__all__ = [
    "SimulatedTradeEventType",
    "SimulatedTradeStatus",
    "SimulatedTradeLogRecord",
    "run_simulated_paper_trading",
    "run_simulated_paper_trading_result",
    "SimulatedPaperTradingResult",
    "build_simulated_paper_trading_result",
    "build_simulated_paper_trading_summary",
    "build_simulated_order_rows",
    "build_simulated_fill_rows",
    "build_simulated_trade_log_rows",
    "build_simulated_paper_trading_report_data",
    "export_simulated_paper_trading_markdown",
    "export_simulated_paper_trading_csv_bundle",
    "export_simulated_paper_trading_markdown_file",
    "export_simulated_paper_trading_csv_files",
    "serialize_simulated_paper_trading_result",
    "deserialize_simulated_paper_trading_result",
    "export_simulated_paper_trading_result_json",
    "load_simulated_paper_trading_result_json",
    "export_simulated_paper_trading_result_json_file",
    "load_simulated_paper_trading_result_json_file",
    "convert_backtest_result_to_simulated_paper_trading_result",
]
