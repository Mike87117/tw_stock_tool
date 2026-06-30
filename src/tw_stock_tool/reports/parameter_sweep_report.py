"""Parameter sweep report generators (Markdown, Excel)."""

from __future__ import annotations

import pandas as pd
from pathlib import Path
from typing import Any, Union
from datetime import datetime

SHARPE_COLUMNS = ["Sharpe Ratio", "sharpe"]
RETURN_COLUMNS = ["Total Return %", "total_return"]
METRIC_CANDIDATES = [
    "Total Return %",
    "total_return",
    "Annual Return %",
    "annual_return",
    "Buy and Hold Return %",
    "CAGR %",
    "Max Drawdown %",
    "max_drawdown",
    "Sharpe Ratio",
    "sharpe",
    "Sortino Ratio",
    "Win Rate %",
    "win_rate",
    "Trades",
    "trades",
    "Trade Count",
    "Final Equity",
    "final_equity",
    "Profit Factor",
    "profit_factor",
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

def build_parameter_sweep_report_data(result: Union[pd.DataFrame, dict[str, Any], None]) -> dict[str, Any]:
    """
    Format parameter sweep result data for report generation.
    Supports DataFrame or dictionary input.
    """
    data: dict[str, Any] = {
        "Stock": "N/A",
        "Strategy": "N/A",
        "Parameters": {},
        "Generated At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Parameter Columns": [],
        "Metric Columns": [],
        "Results": pd.DataFrame(),
        "Top Results": pd.DataFrame(),
        "Best Row": None,
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
        data["Parameters"] = result.get("Parameters", {})
        df_raw = result.get("Results")
        if isinstance(df_raw, pd.DataFrame):
            df = df_raw.copy()
        elif isinstance(df_raw, list):
            df = pd.DataFrame(df_raw)
        else:
            df = pd.DataFrame()
        
        data["Parameter Columns"] = result.get("Parameter Columns", [])
        data["Metric Columns"] = result.get("Metric Columns", [])
    else:
        df = pd.DataFrame()

    data["Results"] = df

    if df.empty:
        return data

    # Auto detect columns if not provided
    if not data["Parameter Columns"]:
        common_params = ["short_window", "long_window", "window", "period", "rsi_period", "ma_window", "threshold"]
        data["Parameter Columns"] = [c for c in df.columns if c in common_params]
        
    if not data["Metric Columns"]:
        data["Metric Columns"] = [c for c in df.columns if c in METRIC_CANDIDATES]

    # Best row and top results
    def _first_existing(candidates: list[str]) -> str | None:
        for c in candidates:
            if c in df.columns:
                return c
        return None

    sort_col = _first_existing(SHARPE_COLUMNS)
    if not sort_col:
        sort_col = _first_existing(RETURN_COLUMNS)

    if sort_col:
        # Sort descending
        # Ensure numeric first to avoid crash if strings present
        temp_df = df.copy()
        temp_df[sort_col] = pd.to_numeric(temp_df[sort_col], errors='coerce')
        sorted_df = df.loc[temp_df[sort_col].sort_values(ascending=False).index]
    else:
        sorted_df = df

    data["Top Results"] = sorted_df.head(10).copy()
    
    if not sorted_df.empty:
        # Convert first row to dict
        data["Best Row"] = sorted_df.iloc[0].to_dict()

    return data

def export_parameter_sweep_report_markdown(result: Union[pd.DataFrame, dict[str, Any], None], output: str | None = None) -> Path:
    """Export parameter sweep report to Markdown."""
    if output is None:
        output = "output/parameter_sweep_report.md"
        
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = build_parameter_sweep_report_data(result)
    
    lines = [
        "# Parameter Sweep Report",
        "",
        "> Research report only, not investment advice.",
        ""
    ]
    
    lines.extend([
        "## Summary",
        f"- Stock: {data['Stock']}",
        f"- Strategy: {data['Strategy']}",
        f"- Rows: {len(data['Results'])}",
        f"- Parameter Columns: {', '.join(data['Parameter Columns']) if data['Parameter Columns'] else 'N/A'}",
        f"- Metric Columns: {', '.join(data['Metric Columns']) if data['Metric Columns'] else 'N/A'}",
        ""
    ])
    
    if data.get("Parameters"):
        lines.append("## Parameters / Assumptions")
        for section, params in data["Parameters"].items():
            lines.append(f"### {section.capitalize()}")
            for k, v in params.items():
                if v is not None:
                    lines.append(f"- {k}: {v}")
        lines.append("")
    lines.append("## Best Result")
    if data["Best Row"]:
        for k, v in data["Best Row"].items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("No parameter sweep results.")
    lines.append("")
        
    lines.append("## Top Results")
    if not data["Top Results"].empty:
        lines.append(_df_to_markdown_table(data["Top Results"]))
    else:
        lines.append("No parameter sweep results.")
    lines.append("")
        
    lines.append("## Full Results")
    if not data["Results"].empty:
        lines.append(_df_to_markdown_table(data["Results"]))
    else:
        lines.append("No parameter sweep results.")
    lines.append("")
        
    lines.append("## Notes")
    for note in data["Notes"]:
        lines.append(f"- {note}")
    lines.append("")
    
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

def export_parameter_sweep_report_excel(result: Union[pd.DataFrame, dict[str, Any], None], output: str | None = None) -> Path:
    """Export parameter sweep report to Excel."""
    if output is None:
        output = "output/parameter_sweep_report.xlsx"
        
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = build_parameter_sweep_report_data(result)
    
    # Create summary df
    summary_data = {
        "Field": ["Stock", "Strategy", "Rows", "Parameter Columns", "Metric Columns"],
        "Value": [
            data["Stock"],
            data["Strategy"],
            len(data["Results"]),
            ", ".join(data["Parameter Columns"]) if data["Parameter Columns"] else "N/A",
            ", ".join(data["Metric Columns"]) if data["Metric Columns"] else "N/A",
        ]
    }
    if data.get("Parameters"):
        for section, params in data["Parameters"].items():
            if isinstance(params, dict):
                for k, v in params.items():
                    if v is not None:
                        summary_data["Field"].append(f"Param ({section}): {k}")
                        summary_data["Value"].append(str(v))
    summary_df = pd.DataFrame(summary_data)
    
    notes_df = pd.DataFrame({"Notes": data["Notes"]})
    
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        data["Top Results"].to_excel(writer, sheet_name="Top Results", index=False)
        data["Results"].to_excel(writer, sheet_name="Full Results", index=False)
        notes_df.to_excel(writer, sheet_name="Notes", index=False)
        
    return path
