"""Daily candidate report for Taiwan stock scans."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Any

import pandas as pd

from tw_stock_tool.utils.config import DEFAULT_AUTO_ADJUST, DEFAULT_INTERVAL, DEFAULT_PERIOD, OUTPUT_DIR
from tw_stock_tool.analysis.scanner import ScanConfig, load_stock_ids_from_file, normalize_stock_ids, scan_stocks
from tw_stock_tool.data import stock_list_updater as stock_list_updater_module
from tw_stock_tool.analysis.stock_selection import apply_stock_selection

DEFAULT_SIGNALS = ("BUY", "WATCH")
DEFAULT_MIN_SCORE = 4.0
DEFAULT_TOP = 20
CANDIDATE_COLUMNS = [
    "Rank",
    "Stock",
    "Signal",
    "Score",
    "Close",
    "Volume_Ratio",
    "RSI",
    "Analysis",
]
SUMMARY_COLUMNS = [
    "Report Date",
    "Stocks Scanned",
    "Candidates",
    "BUY Count",
    "WATCH Count",
    "Average Score",
    "Average Volume Ratio",
]


def collect_stock_ids(
    stocks: Iterable[str] | None,
    file_path: str | None,
    auto_stock_list: bool = False,
    stock_market: str = "all",
    stock_list_output: str | Path = "stocks.txt",
    allow_partial_stock_list: bool = False,
    stock_limit: int | None = None,
    stock_sample: int | None = None,
    random_state: int = 42,
) -> list[str]:
    """Collect stock ids from auto-updater, CLI values, and/or a text file."""
    if auto_stock_list:
        stocks_df, _ = stock_list_updater_module.update_stock_list(
            market=stock_market,
            output=stock_list_output,
            allow_partial=allow_partial_stock_list,
        )
        normalized = normalize_stock_ids(stocks_df["Stock"].astype(str).tolist())
    else:
        values: list[str] = []
        if file_path:
            values.extend(load_stock_ids_from_file(file_path))
        if stocks:
            values.extend(stocks)
        normalized = normalize_stock_ids(values)
    if not normalized:
        raise ValueError("No stock ids provided. Use --stocks, --file, or --auto-stock-list.")
    return apply_stock_selection(
        normalized,
        stock_limit=stock_limit,
        stock_sample=stock_sample,
        random_state=random_state,
    )


def filter_candidates(
    ranking_df: pd.DataFrame,
    signals: Iterable[str] = DEFAULT_SIGNALS,
    min_score: float = DEFAULT_MIN_SCORE,
    top: int | None = DEFAULT_TOP,
) -> pd.DataFrame:
    """Filter and rank daily candidates from a full scan result."""
    if ranking_df.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)

    allowed = {signal.upper() for signal in signals}
    ok = ranking_df[ranking_df["Status"].astype(str).str.upper() == "OK"].copy()
    ok = ok[ok["Signal"].astype(str).str.upper().isin(allowed)]
    score = pd.to_numeric(ok["Score"], errors="coerce")
    ok = ok[score >= min_score].copy()
    ok["_ScoreSort"] = pd.to_numeric(ok["Score"], errors="coerce").fillna(float("-inf"))
    ok["_VolumeSort"] = pd.to_numeric(
        ok["Volume_Ratio"],
        errors="coerce",
    ).fillna(float("-inf"))
    ok = ok.sort_values(
        by=["_ScoreSort", "_VolumeSort", "Stock"],
        ascending=[False, False, True],
        kind="mergesort",
    ).drop(columns=["_ScoreSort", "_VolumeSort"])
    if top is not None and top > 0:
        ok = ok.head(top)
    elif top == 0:
        ok = ok.head(0)
    ok = ok.reset_index(drop=True)
    if not ok.empty:
        ok["Rank"] = range(1, len(ok) + 1)
    return ok.reindex(columns=CANDIDATE_COLUMNS)


def build_summary(
    ranking_df: pd.DataFrame,
    candidates_df: pd.DataFrame,
    report_date: str | None = None,
) -> pd.DataFrame:
    """Build the single-row daily report summary."""
    date_text = report_date or datetime.now().strftime("%Y-%m-%d")
    score = pd.to_numeric(candidates_df.get("Score"), errors="coerce")
    volume_ratio = pd.to_numeric(candidates_df.get("Volume_Ratio"), errors="coerce")
    summary = {
        "Report Date": date_text,
        "Stocks Scanned": int(len(ranking_df)),
        "Candidates": int(len(candidates_df)),
        "BUY Count": int((candidates_df.get("Signal", pd.Series(dtype=str)) == "BUY").sum()),
        "WATCH Count": int((candidates_df.get("Signal", pd.Series(dtype=str)) == "WATCH").sum()),
        "Average Score": round(float(score.mean()), 2) if not score.dropna().empty else 0.0,
        "Average Volume Ratio": (
            round(float(volume_ratio.mean()), 4) if not volume_ratio.dropna().empty else 0.0
        ),
    }
    return pd.DataFrame([summary], columns=SUMMARY_COLUMNS)


def export_daily_report(
    summary_df: pd.DataFrame,
    candidates_df: pd.DataFrame,
    ranking_df: pd.DataFrame,
    output: str | None,
) -> Path | None:
    """Export daily report sheets to Excel when requested."""
    if output is None:
        return None

    output_path = OUTPUT_DIR / "daily_report.xlsx" if output == "" else Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    errors_df = ranking_df[ranking_df["Status"].astype(str).str.upper() != "OK"].copy()
    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            summary_df.to_excel(writer, index=False, sheet_name="Summary")
            candidates_df.reindex(columns=CANDIDATE_COLUMNS).to_excel(
                writer,
                index=False,
                sheet_name="Candidates",
            )
            ranking_df.to_excel(writer, index=False, sheet_name="All")
            errors_df.to_excel(writer, index=False, sheet_name="Errors")
    except PermissionError as exc:
        raise ValueError(
            f"Failed to write Excel file: {output_path}. Please close it if it is open."
        ) from exc
    except Exception as exc:
        raise ValueError(f"Failed to write Excel file: {output_path}. {exc}") from exc
    return output_path


def run_daily_report(
    stock_ids: Iterable[str],
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    signals: Iterable[str] = DEFAULT_SIGNALS,
    min_score: float = DEFAULT_MIN_SCORE,
    top: int | None = DEFAULT_TOP,
    force_refresh: bool = False,
    auto_adjust: bool = DEFAULT_AUTO_ADJUST,
    output: str | None = None,
    progress: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Path | None]:
    """Scan stocks, filter candidates, build summary, and optionally export Excel."""
    config = ScanConfig(
        period=period,
        interval=interval,
        auto_adjust=auto_adjust,
        force_refresh=force_refresh,
        sort_by="Score",
    )

    def _progress(current: int, total: int, stock_id: str, status: str) -> None:
        if progress:
            print(f"[{current}/{total}] {stock_id} {status}", flush=True)

    ranking_df = scan_stocks(stock_ids, config=config, progress_callback=_progress)
    candidates_df = filter_candidates(ranking_df, signals=signals, min_score=min_score, top=top)
    summary_df = build_summary(ranking_df, candidates_df)
    output_path = export_daily_report(summary_df, candidates_df, ranking_df, output)
    return summary_df, candidates_df, ranking_df, output_path


def print_report_summary(
    summary_df: pd.DataFrame,
    candidates_df: pd.DataFrame,
    output_path: Path | None,
) -> None:
    """Print a compact daily report summary for terminal users."""
    summary = summary_df.iloc[0]
    print("\n=================================")
    print("Daily Report")
    print("=================================")
    print(f"掃描股票數：{summary['Stocks Scanned']}")
    print(f"候選股票：{summary['Candidates']}")
    print(f"BUY：{summary['BUY Count']}")
    print(f"WATCH：{summary['WATCH Count']}")
    print(f"平均 Score：{summary['Average Score']}")
    print("\nTop Candidates:")
    if candidates_df.empty:
        print("無符合條件的候選股票")
    else:
        for _, row in candidates_df.head(10).iterrows():
            print(
                f"{int(row['Rank'])}. {row['Stock']} {row['Signal']} "
                f"Score={row['Score']}"
            )
    if output_path:
        print(f"\nExcel：{output_path}")
    print("=================================")





def _normalize_to_list_of_dicts(data: pd.DataFrame | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, pd.DataFrame):
        return data.to_dict(orient="records")
    if isinstance(data, list):
        return data
    return []


def build_daily_report_data(
    report_date: str | None = None,
    stock_universe: list[str] | None = None,
    screening_results: pd.DataFrame | list[dict[str, Any]] | None = None,
    watchlist_candidates: pd.DataFrame | list[dict[str, Any]] | None = None,
    backtest_highlights: pd.DataFrame | list[dict[str, Any]] | None = None,
    parameter_sweep_highlights: pd.DataFrame | list[dict[str, Any]] | None = None,
    walk_forward_highlights: pd.DataFrame | list[dict[str, Any]] | None = None,
    risk_notes: list[str] | None = None,
    data_limitations: list[str] | None = None,
    next_research_actions: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build structured daily report data from existing scanner and backtest outputs.
    This builder normalizes inputs and ensures research-only language.
    """
    if report_date is None:
        report_date = "N/A"

    universe_list = stock_universe if stock_universe is not None else []

    # Normalize tabular inputs
    norm_screening = _normalize_to_list_of_dicts(screening_results)
    norm_watchlist = _normalize_to_list_of_dicts(watchlist_candidates)
    norm_backtest = _normalize_to_list_of_dicts(backtest_highlights)
    norm_parameter_sweep = _normalize_to_list_of_dicts(parameter_sweep_highlights)
    norm_walk_forward = _normalize_to_list_of_dicts(walk_forward_highlights)

    # Safe list handling for text blocks
    final_risk_notes = risk_notes.copy() if risk_notes is not None else []
    final_data_limitations = data_limitations.copy() if data_limitations is not None else []
    final_next_actions = next_research_actions.copy() if next_research_actions is not None else []

    # Enforce research-only disclaimers
    standard_disclaimer = "This report is for research purposes only and does not constitute investment advice."
    if standard_disclaimer not in final_risk_notes:
        final_risk_notes.append(standard_disclaimer)

    if not universe_list and not norm_screening and not norm_watchlist:
        final_data_limitations.append("No screening data or watchlist candidates were provided for this run.")

    report_data = {
        "Report Metadata": {
            "Date": report_date,
            "Type": "Daily Research Report"
        },
        "Universe Summary": {
            "Total Stocks": len(universe_list),
            "Universe": universe_list
        },
        "Screening Summary": norm_screening,
        "Watchlist Candidates": norm_watchlist,
        "Backtest Highlights": norm_backtest,
        "Parameter Sweep Highlights": norm_parameter_sweep,
        "Walk Forward Highlights": norm_walk_forward,
        "Risk Notes": final_risk_notes,
        "Data Limitations": final_data_limitations,
        "Next Research Actions": final_next_actions,
    }

    return report_data


def render_daily_report_markdown(report_data: dict[str, Any]) -> str:
    """
    Render a structured daily report dict into a Markdown document.
    Ensures deterministic ordering and research-only language.
    """
    lines = ["# Daily Research Report\n"]

    def _render_dict(d: dict[str, Any]) -> list[str]:
        if not d:
            return ["No data provided.\n"]
        out = []
        for k, v in d.items():
            if isinstance(v, list) and not v:
                out.append(f"- **{k}**: None")
            elif isinstance(v, list):
                out.append(f"- **{k}**: {', '.join(str(x) for x in v)}")
            else:
                out.append(f"- **{k}**: {v}")
        out.append("")
        return out

    def _render_list_of_strings(lst: list[str]) -> list[str]:
        if not lst:
            return ["No data provided.\n"]
        out = []
        for item in lst:
            out.append(f"- {item}")
        out.append("")
        return out

    def _render_table(lst: list[dict[str, Any]]) -> list[str]:
        if not lst:
            return ["No data provided.\n"]
        headers = []
        for row in lst:
            for key in row.keys():
                if key not in headers:
                    headers.append(key)
        out = []
        out.append("| " + " | ".join(headers) + " |")
        out.append("|" + "|".join(["---"] * len(headers)) + "|")
        for row in lst:
            row_vals = [str(row.get(h, "")) for h in headers]
            out.append("| " + " | ".join(row_vals) + " |")
        out.append("")
        return out

    # 1. Report Metadata
    lines.append("## Report Metadata\n")
    lines.extend(_render_dict(report_data.get("Report Metadata", {})))

    # 2. Universe Summary
    lines.append("## Universe Summary\n")
    lines.extend(_render_dict(report_data.get("Universe Summary", {})))

    # 3. Screening Summary
    lines.append("## Screening Summary\n")
    lines.extend(_render_table(report_data.get("Screening Summary", [])))

    # 4. Watchlist Candidates for Further Review
    lines.append("## Watchlist Candidates for Further Review\n")
    lines.extend(_render_table(report_data.get("Watchlist Candidates", [])))

    # 5. Backtest Highlights
    lines.append("## Backtest Highlights\n")
    lines.extend(_render_table(report_data.get("Backtest Highlights", [])))

    # 6. Parameter Sweep Highlights
    lines.append("## Parameter Sweep Highlights\n")
    lines.extend(_render_table(report_data.get("Parameter Sweep Highlights", [])))

    # 7. Walk Forward Highlights
    lines.append("## Walk Forward Highlights\n")
    lines.extend(_render_table(report_data.get("Walk Forward Highlights", [])))

    # 8. Risk Notes
    lines.append("## Risk Notes\n")
    risk_notes = report_data.get("Risk Notes", [])
    disclaimer = "This report is for research purposes only and does not constitute investment advice."
    if disclaimer not in risk_notes:
        risk_notes = risk_notes.copy()
        risk_notes.append(disclaimer)
    lines.extend(_render_list_of_strings(risk_notes))

    # 9. Data Limitations
    lines.append("## Data Limitations\n")
    lines.extend(_render_list_of_strings(report_data.get("Data Limitations", [])))

    # 10. Next Research Actions
    lines.append("## Next Research Actions\n")
    lines.extend(_render_list_of_strings(report_data.get("Next Research Actions", [])))

    return "\n".join(lines)
