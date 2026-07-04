from pathlib import Path

from tw_stock_tool.backtesting.results import BacktestResult
from tw_stock_tool.backtesting.serialization import (
    export_backtest_result_json,
    load_backtest_result_json,
)
from tw_stock_tool.utils.output import write_text_report

def export_backtest_result_json_file(
    result: BacktestResult,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    content = export_backtest_result_json(result)
    return write_text_report(content, path, overwrite=overwrite)

def load_backtest_result_json_file(
    path: str | Path,
) -> BacktestResult:
    content = Path(path).read_text(encoding="utf-8")
    return load_backtest_result_json(content)
