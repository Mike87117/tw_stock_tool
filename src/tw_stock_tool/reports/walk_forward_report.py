"""Walk forward validation report generators (Markdown, Excel)."""

from __future__ import annotations

import pandas as pd
from pathlib import Path
from typing import Any, Union
from datetime import datetime

WINDOW_CANDIDATES = [
    "Window",
    "Fold",
    "Train Start",
    "Train End",
    "Test Start",
    "Test End",
    "Start Date",
    "End Date",
]

METRIC_CANDIDATES = [
    "Train Total Return %",
    "Test Total Return %",
    "Train CAGR %",
    "Test CAGR %",
    "Train Trade Count",
    "Test Trade Count",
    "Train Win Rate %",
    "Test Win Rate %",
    "Train Max Drawdown %",
    "Test Max Drawdown %",
    "Train Profit Factor",
    "Test Profit Factor",
    "Train Sharpe Ratio",
    "Test Sharpe Ratio",
    "Train Sortino Ratio",
    "Test Sortino Ratio",
    "Trade Count",
    "Profit Factor",
    "Sharpe Ratio",
    "Sortino Ratio",
    "Total Return %",
    "CAGR %",
    "Max Drawdown %",
    "Win Rate %",
]

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

def build_walk_forward_report_data(result: Union[pd.DataFrame, dict[str, Any], None]) -> dict[str, Any]:
    """
    Format walk forward result data for report generation.
    Supports DataFrame or dictionary input.
    """
    data: dict[str, Any] = {
        "Stock": "N/A",
        "Strategy": "N/A",
        "Generated At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Window Columns": [],
        "Metric Columns": [],
        "Results": pd.DataFrame(),
        "Summary": {},
        "Best Window": None,
        "Notes": [
            "Research report only, not investment advice.",
            "Historical performance does not guarantee future results."
        ]
    }
    
    if result is None:
        return data

    if isinstance(result, pd.DataFrame):
        df = result.copy()
    elif isinstance(result, dict):
        data["Stock"] = result.get("Stock", "N/A")
        data["Strategy"] = result.get("Strategy", "N/A")
        df_raw = result.get("Results")
        if isinstance(df_raw, pd.DataFrame):
            df = df_raw.copy()
        elif isinstance(df_raw, list):
            df = pd.DataFrame(df_raw)
        else:
            df = pd.DataFrame()
        
        data["Window Columns"] = result.get("Window Columns", [])
        data["Metric Columns"] = result.get("Metric Columns", [])
    else:
        df = pd.DataFrame()

    data["Results"] = df

    if df.empty:
        return data

    # Auto detect columns if not provided
    if not data["Window Columns"]:
        data["Window Columns"] = [c for c in df.columns if c in WINDOW_CANDIDATES]
        
    if not data["Metric Columns"]:
        data["Metric Columns"] = [c for c in df.columns if c in METRIC_CANDIDATES]

    # Best Window logic
    sort_cols = [
        "Test Sharpe Ratio",
        "Test Total Return %",
        "Sharpe Ratio",
        "Total Return %"
    ]
    
    sort_col = None
    for c in sort_cols:
        if c in df.columns:
            sort_col = c
            break

    if sort_col:
        temp_df = df.copy()
        temp_df[sort_col] = pd.to_numeric(temp_df[sort_col], errors='coerce')
        sorted_df = df.loc[temp_df[sort_col].sort_values(ascending=False).index]
    else:
        sorted_df = df

    if not sorted_df.empty:
        data["Best Window"] = sorted_df.iloc[0].to_dict()

    # Summary logic
    summary: dict[str, Any] = {"Rows": len(df)}
    
    if "Test Sharpe Ratio" in df.columns:
        numeric_col = pd.to_numeric(df["Test Sharpe Ratio"], errors='coerce').dropna()
        if not numeric_col.empty:
            summary["Best Test Sharpe Ratio"] = numeric_col.max()
            summary["Average Test Sharpe Ratio"] = numeric_col.mean()
            
    if "Test Total Return %" in df.columns:
        numeric_col = pd.to_numeric(df["Test Total Return %"], errors='coerce').dropna()
        if not numeric_col.empty:
            summary["Best Test Total Return %"] = numeric_col.max()
            summary["Average Test Total Return %"] = numeric_col.mean()
            
    if "Test Max Drawdown %" in df.columns:
        numeric_col = pd.to_numeric(df["Test Max Drawdown %"], errors='coerce').dropna()
        if not numeric_col.empty:
            summary["Worst Test Max Drawdown %"] = numeric_col.min()

    data["Summary"] = summary
    return data

def export_walk_forward_report_markdown(result: Union[pd.DataFrame, dict[str, Any], None], output: str | None = None) -> Path:
    """Export walk forward report to Markdown."""
    if output is None:
        output = "output/walk_forward_report.md"
        
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = build_walk_forward_report_data(result)
    
    lines = [
        "# Walk Forward Report",
        "",
        "> Research report only, not investment advice.",
        ""
    ]
    
    lines.extend([
        "## Summary",
        f"- Stock: {data['Stock']}",
        f"- Strategy: {data['Strategy']}",
        f"- Generated At: {data['Generated At']}"
    ])
    
    for k, v in data["Summary"].items():
        if isinstance(v, float):
            lines.append(f"- {k}: {v:.4f}")
        else:
            lines.append(f"- {k}: {v}")
    lines.append("")
    
    lines.append("## Best Window")
    if data["Best Window"]:
        for k, v in data["Best Window"].items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("No best window found.")
    lines.append("")
    
    lines.append("## Results")
    if data["Results"].empty:
        lines.append("No walk forward results.")
    else:
        lines.append(_df_to_markdown_table(data["Results"]))
    lines.append("")
        
    lines.append("## Notes")
    for note in data["Notes"]:
        lines.append(f"- {note}")
        
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

def export_walk_forward_report_excel(result: Union[pd.DataFrame, dict[str, Any], None], output: str | None = None) -> Path:
    """Export walk forward report to Excel."""
    if output is None:
        output = "output/walk_forward_report.xlsx"
        
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = build_walk_forward_report_data(result)
    
    summary_rows = [
        {"Field": "Stock", "Value": data["Stock"]},
        {"Field": "Strategy", "Value": data["Strategy"]},
        {"Field": "Generated At", "Value": data["Generated At"]},
    ]
    for k, v in data["Summary"].items():
        summary_rows.append({"Field": k, "Value": v})
        
    summary_df = pd.DataFrame(summary_rows)
    
    if data["Best Window"]:
        best_window_df = pd.DataFrame([data["Best Window"]])
    else:
        best_window_df = pd.DataFrame()
        
    results_df = data["Results"]
    notes_df = pd.DataFrame({"Notes": data["Notes"]})
    
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        best_window_df.to_excel(writer, sheet_name="Best Window", index=False)
        results_df.to_excel(writer, sheet_name="Results", index=False)
        notes_df.to_excel(writer, sheet_name="Notes", index=False)
        
    return path
