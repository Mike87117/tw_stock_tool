from pathlib import Path

from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult
from tw_stock_tool.paper_trading.serialization import (
    export_simulated_paper_trading_result_json,
    load_simulated_paper_trading_result_json,
)
from tw_stock_tool.utils.output import write_text_report


def export_simulated_paper_trading_result_json_file(
    result: SimulatedPaperTradingResult,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    content = export_simulated_paper_trading_result_json(result)
    return write_text_report(content, path, overwrite=overwrite)


def load_simulated_paper_trading_result_json_file(
    path: str | Path,
) -> SimulatedPaperTradingResult:
    content = Path(path).read_text(encoding="utf-8")
    return load_simulated_paper_trading_result_json(content)
