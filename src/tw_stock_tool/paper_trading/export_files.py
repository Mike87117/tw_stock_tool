from pathlib import Path

from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult
from tw_stock_tool.paper_trading.exporters import (
    export_simulated_paper_trading_markdown,
    export_simulated_paper_trading_csv_bundle,
)
from tw_stock_tool.utils.output import write_text_report, write_csv_bundle

def export_simulated_paper_trading_markdown_file(
    result: SimulatedPaperTradingResult,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Export a SimulatedPaperTradingResult to a Markdown file."""
    content = export_simulated_paper_trading_markdown(result)
    return write_text_report(content, path, overwrite=overwrite)

def export_simulated_paper_trading_csv_files(
    result: SimulatedPaperTradingResult,
    output_dir: str | Path,
    *,
    basename: str = "simulated_paper_trading",
    overwrite: bool = False,
) -> dict[str, Path]:
    """Export a SimulatedPaperTradingResult to a bundle of CSV files."""
    csv_bundle = export_simulated_paper_trading_csv_bundle(result)
    rejections_csv = csv_bundle.pop("rejections", None)
    trade_log_csv = csv_bundle.pop("trade_log", None)

    rejections_path = None
    trade_log_path = None
    if rejections_csv is not None:
        rejections_path = Path(output_dir).resolve() / f"{basename}_rejections.csv"
        if not overwrite and rejections_path.exists():
            raise FileExistsError(f"File already exists: {rejections_path}")

    if trade_log_csv is not None:
        trade_log_path = Path(output_dir).resolve() / f"{basename}_trade_log.csv"
        if not overwrite and trade_log_path.exists():
            raise FileExistsError(f"File already exists: {trade_log_path}")

    paths = write_csv_bundle(
        csv_bundle,
        output_dir,
        basename=basename,
        overwrite=overwrite,
    )

    if rejections_csv is not None and rejections_path is not None:
        with open(rejections_path, "w", encoding="utf-8") as f:
            f.write(rejections_csv)
        paths["rejections"] = rejections_path

    if trade_log_csv is not None and trade_log_path is not None:
        with open(trade_log_path, "w", encoding="utf-8") as f:
            f.write(trade_log_csv)
        paths["trade_log"] = trade_log_path

    return paths
