"""
Filesystem helpers for multi-symbol simulated portfolio trading report exports (Markdown and CSV bundle).
"""

from pathlib import Path

from tw_stock_tool.paper_trading.models import PaperTradingModelError
from tw_stock_tool.paper_trading.portfolio_exporters import (
    export_simulated_portfolio_trading_csv_bundle,
    export_simulated_portfolio_trading_markdown,
)
from tw_stock_tool.paper_trading.portfolio_results import SimulatedPortfolioTradingResult
from tw_stock_tool.utils.output import write_text_report


def export_simulated_portfolio_trading_markdown_file(
    result: SimulatedPortfolioTradingResult,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Export a SimulatedPortfolioTradingResult to a Markdown file."""
    content = export_simulated_portfolio_trading_markdown(result)
    return write_text_report(content, path, overwrite=overwrite)


def export_simulated_portfolio_trading_csv_files(
    result: SimulatedPortfolioTradingResult,
    output_dir: str | Path,
    *,
    basename: str = "simulated_portfolio_trading",
    overwrite: bool = False,
) -> dict[str, Path]:
    """Export a SimulatedPortfolioTradingResult to a 7-file CSV bundle."""
    # 1. Exact basename policy validation
    if type(basename) is not str:
        raise ValueError(f"basename must be an exact str instance, got {type(basename).__name__}")
    if not basename or basename.isspace():
        raise ValueError("basename must not be empty or whitespace-only")
    if basename in (".", ".."):
        raise ValueError("basename must not be '.' or '..'")
    if "/" in basename or "\\" in basename:
        raise ValueError("basename must not contain '/' or '\\'")

    # 2. Resolve target paths and check escaping
    resolved_output_dir = Path(output_dir).resolve()
    expected_keys = (
        "summary",
        "positions",
        "pending_orders",
        "orders",
        "fills",
        "rejections",
        "trade_log",
    )

    target_paths: dict[str, Path] = {}
    for k in expected_keys:
        filename = f"{basename}_{k}.csv"
        target_path = (resolved_output_dir / filename).resolve()
        if target_path.parent != resolved_output_dir:
            raise ValueError(f"basename '{basename}' escapes output directory")
        target_paths[k] = target_path

    # 3. Preflight check when overwrite=False
    if not overwrite:
        for k in expected_keys:
            if target_paths[k].exists():
                raise FileExistsError(f"File already exists: {target_paths[k]}")

    # 4. Generate & validate string CSV bundle
    csv_bundle = export_simulated_portfolio_trading_csv_bundle(result)
    if tuple(csv_bundle.keys()) != expected_keys:
        raise PaperTradingModelError("CSV bundle keys do not match expected portfolio 7-file schema.")

    # 5. Create output directory & write files
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: dict[str, Path] = {}
    for k in expected_keys:
        target_path = target_paths[k]
        csv_text = csv_bundle[k]
        with open(target_path, "w", encoding="utf-8", newline="") as f:
            f.write(csv_text)
        written_paths[k] = target_path

    return written_paths
