"""Backtest report generators (Markdown, Excel)."""

from __future__ import annotations

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Any


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    df_str = df.fillna("").astype(str)
    headers = list(df_str.columns)
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "|-" + "-|-".join(["-" * len(h) for h in headers]) + "-|"
    
    rows = []
    for _, row in df_str.iterrows():
        rows.append("| " + " | ".join(row.values) + " |")
        
    return "\n".join([header_line, sep_line] + rows)

def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors="coerce").dropna()

def build_backtest_report_data(result: dict[str, Any]) -> dict[str, Any]:
    """
    Format backtest result data for report generation.
    Handles legacy result dictionary from run_backtest().
    """
    data: dict[str, Any] = {}
    
    # Extract trades
    trades = result.get("Trades")
    if isinstance(trades, list):
        trades_df = pd.DataFrame(trades)
    elif isinstance(trades, pd.DataFrame):
        trades_df = trades.copy()
    else:
        trades_df = pd.DataFrame()
        
    data["Trades"] = trades_df

    # Extract equity curve
    equity_curve = result.get("Equity Curve")
    if isinstance(equity_curve, pd.Series):
        equity_series = equity_curve.copy()
    elif isinstance(equity_curve, (list, tuple)):
        equity_series = pd.Series(equity_curve)
    else:
        equity_series = pd.Series(dtype=float)
        
    data["Equity Curve"] = equity_series

    # Drawdown Data
    drawdown_df = pd.DataFrame()
    if not equity_series.empty:
        equity_series = pd.to_numeric(equity_series, errors='coerce')
        peak = equity_series.cummax().replace(0, np.nan)
        drawdown_pct = (equity_series / peak - 1) * 100
        drawdown_df = pd.DataFrame({
            "Equity": equity_series,
            "Running Peak": peak,
            "Drawdown %": drawdown_pct
        })
    data["Drawdown"] = drawdown_df

    # Summary Metrics
    def safe_get(key: str, default: Any = "N/A") -> Any:
        return result.get(key, default)

    data["Summary"] = {
        "Stock": safe_get("Stock"),
        "Strategy": safe_get("Strategy"),
        "Parameters": safe_get("Parameters"),
        "Start Date": safe_get("Start Date"),
        "End Date": safe_get("End Date"),
        "Initial Capital": safe_get("Initial Capital"),
        "Final Capital": safe_get("Final Capital"),
        "Total Return %": safe_get("Total Return %"),
        "Buy and Hold Return %": safe_get("Buy and Hold Return %"),
        "Trade Count": safe_get("Trade Count"),
        "Win Rate %": safe_get("Win Rate %"),
        "Max Drawdown %": safe_get("Max Drawdown %"),
    }
    
    data["Metrics"] = {
        "Total Return %": safe_get("Total Return %"),
        "Buy Hold Return %": safe_get("Buy and Hold Return %"),
        "CAGR %": safe_get("CAGR %"),
        "Exposure %": safe_get("Exposure %"),
        "Win Rate %": safe_get("Win Rate %"),
        "Max Drawdown %": safe_get("Max Drawdown %"),
        "Profit Factor": safe_get("Profit Factor"),
        "Sharpe Ratio": safe_get("Sharpe Ratio"),
        "Sortino Ratio": safe_get("Sortino Ratio"),
        "Max Profit Trade %": safe_get("Best Trade %"),
        "Max Loss Trade %": safe_get("Worst Trade %"),
        "Average Hold Days": safe_get("Avg Hold Days"),
        "Average Profit": safe_get("Avg Profit"),
        "Average Loss": safe_get("Avg Loss"),
    }
    
    # Trade Summary
    if trades_df.empty:
        trade_summary = {}
    else:
        pnl = _numeric_series(trades_df, "PnL")
        hold_days = _numeric_series(trades_df, "Hold Days")
        
        wins = pnl[pnl > 0]
        losses = pnl[pnl <= 0]
        
        trade_summary = {
            "Total Trades": len(trades_df),
            "Winning Trades": len(wins) if not pnl.empty else 0,
            "Losing Trades": len(losses) if not pnl.empty else 0,
            "Average Profit": float(wins.mean()) if not wins.empty else "N/A",
            "Average Loss": float(losses.mean()) if not losses.empty else "N/A",
            "Max Profit Trade": float(pnl.max()) if not pnl.empty else "N/A",
            "Max Loss Trade": float(pnl.min()) if not pnl.empty else "N/A",
            "Average Hold Days": float(hold_days.mean()) if not hold_days.empty else "N/A",
        }
    data["Trade Summary"] = trade_summary

    return data


def export_backtest_report_markdown(result: dict[str, Any], output: str | None = None) -> Path:
    """Export backtest report to a Markdown file."""
    if output is None:
        out_path = Path("output") / "backtest_report.md"
    else:
        out_path = Path(output)
        if out_path.is_dir() or not out_path.suffix:
            out_path = out_path / "backtest_report.md"
            
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = build_backtest_report_data(result)
    
    lines = [
        "# Backtest Report",
        "",
        "> Research report only, not investment advice.",
        "",
        "## Summary",
        ""
    ]
    
    for k, v in data["Summary"].items():
        lines.append(f"- **{k}**: {v}")
        
    lines.extend([
        "",
        "## Metrics",
        ""
    ])
    
    for k, v in data["Metrics"].items():
        lines.append(f"- **{k}**: {v}")
        
    lines.extend([
        "",
        "## Trade Summary",
        ""
    ])
    
    if not data["Trade Summary"]:
        lines.append("No trades.")
    else:
        for k, v in data["Trade Summary"].items():
            if isinstance(v, float) and pd.isna(v):
                v = "N/A"
            elif isinstance(v, float):
                v = round(v, 2)
            lines.append(f"- **{k}**: {v}")
            
    lines.extend([
        "",
        "## Trades",
        ""
    ])
    
    trades_df = data["Trades"]
    if trades_df.empty:
        lines.append("No trades.")
    else:
        # Suggest core columns, filter to those that exist
        core_cols = ["Entry Date", "Exit Date", "Entry Price", "Exit Price", "Shares", "PnL", "PnL_pct", "PnL %", "Hold Days", "Exit Reason"]
        cols_to_show = [c for c in core_cols if c in trades_df.columns]
        if not cols_to_show:
            cols_to_show = list(trades_df.columns)
        
        lines.append(_df_to_markdown_table(trades_df[cols_to_show]) or "No trades to display.")
        
    lines.extend([
        "",
        "## Equity Curve Data",
        ""
    ])
    
    equity_series = data["Equity Curve"]
    if equity_series.empty:
        lines.append("No equity curve data.")
    else:
        eq_df = pd.DataFrame({"Equity": equity_series})
        if len(eq_df) > 20:
            lines.append("*(Showing first 20 records. Truncated for readability)*\n")
            eq_df = eq_df.head(20)
        lines.append(_df_to_markdown_table(eq_df.reset_index()) or "No equity data to display.")
        
    lines.extend([
        "",
        "## Drawdown Data",
        ""
    ])
    
    dd_df = data["Drawdown"]
    if dd_df.empty:
        lines.append("No drawdown data.")
    else:
        if len(dd_df) > 20:
            lines.append("*(Showing first 20 records. Truncated for readability)*\n")
            dd_df = dd_df.head(20)
        lines.append(_df_to_markdown_table(dd_df.reset_index()) or "No drawdown data to display.")
        
    lines.extend([
        "",
        "## Notes",
        "",
        "- This report is for research and validation only.",
        "- It is not investment advice.",
        "- Past performance does not guarantee future results."
    ])
    
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def export_backtest_report_excel(result: dict[str, Any], output: str | None = None) -> Path:
    """Export backtest report to an Excel file."""
    if output is None:
        out_path = Path("output") / "backtest_report.xlsx"
    else:
        out_path = Path(output)
        if out_path.is_dir() or not out_path.suffix:
            out_path = out_path / "backtest_report.xlsx"
            
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = build_backtest_report_data(result)
    
    # Convert dicts to single-row DataFrames or key-value DataFrames
    summary_df = pd.DataFrame(list(data["Summary"].items()), columns=["Metric", "Value"])
    metrics_df = pd.DataFrame(list(data["Metrics"].items()), columns=["Metric", "Value"])
    
    if not data["Trade Summary"]:
        trade_summary_df = pd.DataFrame({"Note": ["No trades"]})
    else:
        trade_summary_df = pd.DataFrame(list(data["Trade Summary"].items()), columns=["Metric", "Value"])

    trades_df = data["Trades"]
    if trades_df.empty:
        trades_df = pd.DataFrame({"Note": ["No trades"]})
        
    equity_series = data["Equity Curve"]
    if equity_series.empty:
        equity_df = pd.DataFrame({"Note": ["No equity curve data"]})
    else:
        equity_df = pd.DataFrame({"Equity": equity_series})
        
    drawdown_df = data["Drawdown"]
    if drawdown_df.empty:
        drawdown_df = pd.DataFrame({"Note": ["No drawdown data"]})

    try:
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            summary_df.to_excel(writer, sheet_name="Summary", index=False)
            metrics_df.to_excel(writer, sheet_name="Metrics", index=False)
            trade_summary_df.to_excel(writer, sheet_name="Trade Summary", index=False)
            trades_df.to_excel(writer, sheet_name="Trades", index=False)
            equity_df.to_excel(writer, sheet_name="Equity Curve", index=True)
            drawdown_df.to_excel(writer, sheet_name="Drawdown", index=True)
    except PermissionError as exc:
        raise ValueError(
            f"Failed to write Excel file: {out_path}. Please close the file if it is open."
        ) from exc
        
    return out_path
