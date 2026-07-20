"""Daily candidate report for Taiwan stock scans."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from collections.abc import Callable
from typing import Iterable, Any

import pandas as pd

from tw_stock_tool.analysis.analysis import StockAnalysis, analyze_stock
from tw_stock_tool.backtesting.backtest import run_backtest_result
from tw_stock_tool.backtesting.parameter_sweep import SORTABLE_COLUMNS as PARAMETER_SWEEP_SORTABLE_COLUMNS, run_parameter_sweep
from tw_stock_tool.backtesting.strategies import STRATEGIES
from tw_stock_tool.backtesting.walk_forward import SORTABLE_COLUMNS, run_walk_forward

from tw_stock_tool.utils.config import DEFAULT_AUTO_ADJUST, DEFAULT_INTERVAL, DEFAULT_PERIOD, OUTPUT_DIR
from tw_stock_tool.analysis.scanner import ScanConfig, load_stock_ids_from_file, normalize_stock_ids, scan_stocks
from tw_stock_tool.data import stock_list_updater as stock_list_updater_module
from tw_stock_tool.analysis.stock_selection import apply_stock_selection

DEFAULT_SIGNALS = ("BUY", "WATCH")
DEFAULT_MIN_SCORE = 4.0
DEFAULT_TOP = 20
VALIDATION_STRATEGIES = ("ma_cross", "macd", "rsi", "score")
BACKTEST_HIGHLIGHT_COLUMNS = [
    "Rank", "Stock", "Signal", "Score", "Strategy", "Status",
    "Start Date", "End Date", "Total Return %", "Buy and Hold Return %",
    "Trade Count", "Win Rate %", "Max Drawdown %", "Sharpe Ratio", "Error",
]
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

DAILY_REPORT_SECTION_ORDER = [
    ("Report Metadata", "Report Metadata", "dict"),
    ("Report Highlights", "Report Highlights", "list"),
    ("Data Quality Notes", "Data Quality Notes", "list"),
    ("Universe Summary", "Universe Summary", "dict"),
    ("Screening Summary", "Screening Summary", "table"),
    ("Watchlist Candidates for Further Review", "Watchlist Candidates", "table"),
    ("Backtest Highlights", "Backtest Highlights", "table"),
    ("Parameter Sweep Highlights", "Parameter Sweep Highlights", "table"),
    ("Walk Forward Highlights", "Walk Forward Highlights", "table"),
    ("Risk Notes", "Risk Notes", "list_risk_notes"),
    ("Data Limitations", "Data Limitations", "list"),
    ("Next Research Actions", "Next Research Actions", "list"),
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
    analysis_provider: Callable[[str], StockAnalysis] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Path | None]:
    """Scan stocks, filter candidates, build summary, and optionally export Excel."""
    config = ScanConfig(
        period=period,
        interval=interval,
        auto_adjust=auto_adjust,
        force_refresh=force_refresh,
        sort_by="Score",
        analysis_provider=analysis_provider,
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


def build_data_limitations_from_ranking(
    ranking_df: pd.DataFrame | None,
    max_items: int = 10,
) -> list[str]:
    """Extract failure messages from scan ranking into a list for Data Limitations."""
    if ranking_df is None or ranking_df.empty or "Status" not in ranking_df.columns:
        return []

    failed_mask = ranking_df["Status"].astype(str).str.upper() != "OK"
    failed_rows = ranking_df[failed_mask]

    if failed_rows.empty:
        return []

    limitations = []
    for _, row in failed_rows.head(max_items).iterrows():
        stock_id = row.get("Stock", "Unknown")
        status = row.get("Status", "ERROR")
        error_msg = row.get("Error", "")
        if pd.isna(error_msg):
            error_msg = ""
        msg = f"{stock_id}: {status}"
        if error_msg:
            msg += f" - {error_msg}"
        limitations.append(msg)

    total_failed = len(failed_rows)
    if total_failed > max_items:
        remaining = total_failed - max_items
        limitations.append(f"... and {remaining} more failed stock(s).")

    return limitations



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

    highlights = []
    if norm_screening:
        summary_dict = norm_screening[0]
        scanned = summary_dict.get("Stocks Scanned", 0)
        candidates = summary_dict.get("Candidates", 0)
        buy_count = summary_dict.get("BUY Count", 0)
        watch_count = summary_dict.get("WATCH Count", 0)

        highlights.append(f"Report generation summary: {scanned} symbols included.")
        highlights.append(f"Notable observations: {candidates} candidates met the criteria.")
        highlights.append(f"Strategy signal counts from existing computed metrics: {buy_count} BUY labels, {watch_count} WATCH labels.")
        highlights.append("Generated from available computed metrics.")
    else:
        highlights.append("No screening summary data was provided, so highlights are limited for this report.")

    data_quality_notes = []
    data_quality_notes.append(f"Data quality summary: {len(universe_list)} symbols were included in the configured universe.")

    if norm_screening:
        data_quality_notes.append(f"Screening summary rows available: {len(norm_screening)}.")
    else:
        data_quality_notes.append("No screening summary data was provided for this report.")

    limitations_count = len(final_data_limitations)
    data_quality_notes.append(f"Data limitations recorded: {limitations_count} item(s).")
    data_quality_notes.append("Some symbols may be absent due to upstream data availability or scan errors.")

    report_data = {
        "Report Metadata": {
            "Date": report_date,
            "Type": "Daily Research Report"
        },
        "Report Highlights": highlights,
        "Data Quality Notes": data_quality_notes,
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

    for heading, data_key, renderer_type in DAILY_REPORT_SECTION_ORDER:
        lines.append(f"## {heading}\n")

        if renderer_type == "dict":
            lines.extend(_render_dict(report_data.get(data_key, {})))
        elif renderer_type == "list":
            lines.extend(_render_list_of_strings(report_data.get(data_key, [])))
        elif renderer_type == "table":
            lines.extend(_render_table(report_data.get(data_key, [])))
        elif renderer_type == "list_risk_notes":
            risk_notes = report_data.get(data_key, [])
            disclaimer = "This report is for research purposes only and does not constitute investment advice."
            if disclaimer not in risk_notes:
                risk_notes = risk_notes.copy()
                risk_notes.append(disclaimer)
            lines.extend(_render_list_of_strings(risk_notes))

    return "\n".join(lines)


def _backtest_result_value(result: Any, attribute: str, legacy_key: str) -> Any:
    if isinstance(result, dict):
        return result.get(legacy_key)
    return getattr(result, attribute, None)


def _format_backtest_date(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    try:
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return str(value)


def _round_backtest_metric(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not pd.isna(number):
        return round(number, 2)
    return None



PARAMETER_SWEEP_HIGHLIGHT_COLUMNS = [
    "Rank", "Stock", "Signal", "Score", "Strategy", "Status", "Sort By",
    "Parameter Combinations", "Successful Combinations", "Error Combinations",
    "Best Parameters", "Total Return %", "Buy and Hold Return %", "CAGR %",
    "Trade Count", "Win Rate %", "Max Drawdown %", "Profit Factor",
    "Sharpe Ratio", "Sortino Ratio", "Error",
]
WALK_FORWARD_HIGHLIGHT_COLUMNS = [
    "Rank", "Stock", "Signal", "Score", "Strategy", "Status",
    "Train Days", "Test Days", "Step Days", "Windows", "Successful Windows",
    "Error Windows", "Positive Test Windows", "Positive Test Windows %",
    "Avg Test Total Return %", "Avg Test CAGR %", "Avg Test Sharpe Ratio",
    "Avg Test Max Drawdown %", "Best Test Total Return %", "Best Test Sharpe Ratio",
    "Error",
]
WALK_FORWARD_STRATEGIES = ("ma_cross", "rsi", "score")


def _walk_forward_number(value: Any) -> float | None:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return None
    return round(float(number), 2)


def _walk_forward_error(value: Any) -> str:
    return " ".join(str(value).split())


def _parameter_sweep_number(value: Any) -> float | int | None:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return None
    numeric = float(number)
    return int(numeric) if numeric.is_integer() else round(numeric, 2)


def _parameter_sweep_error(value: Any) -> str:
    return " ".join(str(value).split())


def run_candidate_parameter_sweep_validation(
    backtest_highlights: pd.DataFrame,
    *,
    parameter_sweep_top: int,
    strategy: str,
    period: str,
    interval: str,
    auto_adjust: bool,
    force_refresh: bool,
    sort_by: str,
    initial_capital: float,
    fee_rate: float,
    tax_rate: float,
    position_size: float,
    analysis_provider: Callable[[str], StockAnalysis] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Summarize an optional in-sample parameter sweep for successful backtests."""
    if strategy not in WALK_FORWARD_STRATEGIES:
        raise ValueError(
            f"Unsupported parameter sweep strategy: {strategy}. "
            f"Choose from {', '.join(WALK_FORWARD_STRATEGIES)}."
        )
    if parameter_sweep_top < 0:
        raise ValueError("parameter_sweep_top must be non-negative.")
    if sort_by not in PARAMETER_SWEEP_SORTABLE_COLUMNS:
        raise ValueError(f"Unsupported parameter sweep sort metric: {sort_by}")

    empty = pd.DataFrame(columns=PARAMETER_SWEEP_HIGHLIGHT_COLUMNS)
    if parameter_sweep_top == 0:
        return empty, []
    if backtest_highlights.empty or "Status" not in backtest_highlights.columns:
        return empty, [
            "Parameter sweep skipped: no successful backtest candidates were available."
        ]

    eligible = backtest_highlights[
        backtest_highlights["Status"].astype(str).str.upper() == "OK"
    ].head(parameter_sweep_top)
    if eligible.empty:
        return empty, [
            "Parameter sweep skipped: no successful backtest candidates were available."
        ]

    rows: list[dict[str, Any]] = []
    limitations: list[str] = []
    for _, candidate in eligible.iterrows():
        stock_id = str(candidate.get("Stock", ""))
        metadata = {
            "Rank": candidate.get("Rank"),
            "Stock": candidate.get("Stock"),
            "Signal": candidate.get("Signal"),
            "Score": candidate.get("Score"),
            "Strategy": strategy,
            "Sort By": sort_by,
        }
        try:
            analysis = analysis_provider(stock_id) if analysis_provider else None
            detail = run_parameter_sweep(
                stock_id=stock_id,
                period=period,
                strategy=strategy,
                sort_by=sort_by,
                top=0,
                force_refresh=force_refresh,
                initial_capital=initial_capital,
                fee_rate=fee_rate,
                tax_rate=tax_rate,
                position_size=position_size,
                interval=interval,
                auto_adjust=auto_adjust,
                analysis=analysis,
            )
            if not isinstance(detail, pd.DataFrame) or detail.empty:
                raise ValueError("no parameter sweep combinations were returned")
            if "Error" not in detail.columns:
                raise ValueError("parameter sweep result is missing required Error column")

            errors = detail.get("Error", pd.Series("", index=detail.index)).fillna("").astype(str)
            errors = errors.map(_parameter_sweep_error)
            successful = detail.loc[errors == ""].copy()
            error_count = int((errors != "").sum())
            combination_count = len(detail)
            first_error = next((error for error in errors if error), "")
            if successful.empty:
                status = "ERROR"
                limitations.append(
                    f"Parameter sweep for {stock_id} completed with {error_count} failed combination(s): {first_error}"
                )
                best = {}
            else:
                status = "PARTIAL" if error_count else "OK"
                if error_count:
                    limitations.append(
                        f"Parameter sweep for {stock_id} completed with {error_count} failed combination(s): {first_error}"
                    )
                successful["_SortValue"] = pd.to_numeric(
                    successful.get(sort_by), errors="coerce"
                ).fillna(float("-inf"))
                best = successful.sort_values(
                    by="_SortValue", ascending=False, kind="mergesort"
                ).iloc[0].to_dict()

            rows.append({
                **metadata,
                "Status": status,
                "Parameter Combinations": combination_count,
                "Successful Combinations": len(successful),
                "Error Combinations": error_count,
                "Best Parameters": best.get("Parameters"),
                "Total Return %": _parameter_sweep_number(best.get("Total Return %")),
                "Buy and Hold Return %": _parameter_sweep_number(best.get("Buy and Hold Return %")),
                "CAGR %": _parameter_sweep_number(best.get("CAGR %")),
                "Trade Count": _parameter_sweep_number(best.get("Trade Count")),
                "Win Rate %": _parameter_sweep_number(best.get("Win Rate %")),
                "Max Drawdown %": _parameter_sweep_number(best.get("Max Drawdown %")),
                "Profit Factor": _parameter_sweep_number(best.get("Profit Factor")),
                "Sharpe Ratio": _parameter_sweep_number(best.get("Sharpe Ratio")),
                "Sortino Ratio": _parameter_sweep_number(best.get("Sortino Ratio")),
                "Error": first_error if status != "OK" else "",
            })
        except Exception as exc:
            error = _parameter_sweep_error(exc)
            rows.append({
                **metadata,
                "Status": "ERROR",
                "Parameter Combinations": 0,
                "Successful Combinations": 0,
                "Error Combinations": 0,
                "Best Parameters": None,
                "Total Return %": None,
                "Buy and Hold Return %": None,
                "CAGR %": None,
                "Trade Count": None,
                "Win Rate %": None,
                "Max Drawdown %": None,
                "Profit Factor": None,
                "Sharpe Ratio": None,
                "Sortino Ratio": None,
                "Error": error,
            })
            limitations.append(f"Parameter sweep for {stock_id} failed: {error}")

    return pd.DataFrame(rows, columns=PARAMETER_SWEEP_HIGHLIGHT_COLUMNS), limitations

def run_candidate_walk_forward_validation(
    backtest_highlights: pd.DataFrame,
    *,
    walk_forward_top: int,
    strategy: str,
    period: str,
    interval: str,
    auto_adjust: bool,
    force_refresh: bool,
    train_days: int,
    test_days: int,
    step_days: int | None,
    sort_by: str,
    initial_capital: float,
    fee_rate: float,
    tax_rate: float,
    position_size: float,
    analysis_provider: Callable[[str], StockAnalysis] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Validate successful backtest candidates with scalar walk-forward summaries."""
    if strategy not in WALK_FORWARD_STRATEGIES:
        raise ValueError(
            f"Unsupported walk-forward strategy: {strategy}. "
            f"Choose from {', '.join(WALK_FORWARD_STRATEGIES)}."
        )
    if walk_forward_top < 0:
        raise ValueError("walk_forward_top must be non-negative.")
    if train_days <= 0 or test_days <= 0 or (step_days is not None and step_days <= 0):
        raise ValueError("walk-forward window values must be greater than 0.")
    if sort_by not in SORTABLE_COLUMNS:
        raise ValueError(f"Unsupported walk-forward sort metric: {sort_by}")

    empty = pd.DataFrame(columns=WALK_FORWARD_HIGHLIGHT_COLUMNS)
    if walk_forward_top == 0:
        return empty, []

    if backtest_highlights.empty or "Status" not in backtest_highlights.columns:
        return empty, [
            "Walk-forward validation skipped: no successful backtest candidates were available."
        ]
    eligible = backtest_highlights[
        backtest_highlights["Status"].astype(str).str.upper() == "OK"
    ].head(walk_forward_top)
    if eligible.empty:
        return empty, [
            "Walk-forward validation skipped: no successful backtest candidates were available."
        ]

    effective_step_days = test_days if step_days is None else step_days
    rows: list[dict[str, Any]] = []
    limitations: list[str] = []
    for _, candidate in eligible.iterrows():
        stock_id = str(candidate.get("Stock", ""))
        metadata = {
            "Rank": candidate.get("Rank"),
            "Stock": candidate.get("Stock"),
            "Signal": candidate.get("Signal"),
            "Score": candidate.get("Score"),
            "Strategy": strategy,
            "Train Days": train_days,
            "Test Days": test_days,
            "Step Days": effective_step_days,
        }
        try:
            walk_forward_kwargs = dict(
                stock_id=stock_id,
                period=period,
                strategy=strategy,
                train_days=train_days,
                test_days=test_days,
                step_days=effective_step_days,
                sort_by=sort_by,
                force_refresh=force_refresh,
                position_size=position_size,
                initial_capital=initial_capital,
                fee_rate=fee_rate,
                tax_rate=tax_rate,
                interval=interval,
                auto_adjust=auto_adjust,
            )
            if analysis_provider is not None:
                walk_forward_kwargs["analysis"] = analysis_provider(stock_id)
            detail = run_walk_forward(**walk_forward_kwargs)
            if not isinstance(detail, pd.DataFrame) or detail.empty:
                raise ValueError("no walk-forward windows were returned")

            errors = detail.get("Error", pd.Series("", index=detail.index)).fillna("").astype(str)
            errors = errors.map(_walk_forward_error)
            successful = detail.loc[errors == ""]
            error_count = int((errors != "").sum())
            window_count = int(detail["Window"].nunique()) if "Window" in detail else len(detail)
            if successful.empty:
                status = "ERROR"
                first_error = next((error for error in errors if error), "no successful windows")
                limitations.append(
                    f"Walk-forward validation for {stock_id} completed with {error_count} failed window(s): {first_error}"
                )
            else:
                status = "PARTIAL" if error_count else "OK"
                if error_count:
                    first_error = next(error for error in errors if error)
                    limitations.append(
                        f"Walk-forward validation for {stock_id} completed with {error_count} failed window(s): {first_error}"
                    )

            def values(column: str) -> pd.Series:
                return pd.to_numeric(successful.get(column, pd.Series(dtype=float)), errors="coerce").dropna()

            returns = values("Test Total Return %")
            cagr = values("Test CAGR %")
            sharpe = values("Test Sharpe Ratio")
            drawdown = values("Test Max Drawdown %")
            positive = int((returns > 0).sum())
            successful_count = len(successful)
            rows.append({
                **metadata,
                "Status": status,
                "Windows": window_count,
                "Successful Windows": successful_count,
                "Error Windows": error_count,
                "Positive Test Windows": positive,
                "Positive Test Windows %": round(positive / successful_count * 100, 2) if successful_count else None,
                "Avg Test Total Return %": _walk_forward_number(returns.mean() if not returns.empty else None),
                "Avg Test CAGR %": _walk_forward_number(cagr.mean() if not cagr.empty else None),
                "Avg Test Sharpe Ratio": _walk_forward_number(sharpe.mean() if not sharpe.empty else None),
                "Avg Test Max Drawdown %": _walk_forward_number(drawdown.mean() if not drawdown.empty else None),
                "Best Test Total Return %": _walk_forward_number(returns.max() if not returns.empty else None),
                "Best Test Sharpe Ratio": _walk_forward_number(sharpe.max() if not sharpe.empty else None),
                "Error": next((error for error in errors if error), "") if status != "OK" else "",
            })
        except Exception as exc:
            error = _walk_forward_error(exc)
            rows.append({
                **metadata,
                "Status": "ERROR",
                "Windows": 0,
                "Successful Windows": 0,
                "Error Windows": 0,
                "Positive Test Windows": 0,
                "Positive Test Windows %": None,
                "Avg Test Total Return %": None,
                "Avg Test CAGR %": None,
                "Avg Test Sharpe Ratio": None,
                "Avg Test Max Drawdown %": None,
                "Best Test Total Return %": None,
                "Best Test Sharpe Ratio": None,
                "Error": error,
            })
            limitations.append(f"Walk-forward validation for {stock_id} failed: {error}")

    return pd.DataFrame(rows, columns=WALK_FORWARD_HIGHLIGHT_COLUMNS), limitations

def run_candidate_backtest_validation(
    candidates_df: pd.DataFrame,
    *,
    validate_top: int,
    strategy: str,
    period: str,
    interval: str,
    auto_adjust: bool,
    force_refresh: bool,
    initial_capital: float,
    fee_rate: float,
    tax_rate: float,
    position_size: float,
    analysis_provider: Callable[[str], StockAnalysis] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Backtest the first ranked candidates for optional research validation."""
    if strategy not in VALIDATION_STRATEGIES:
        raise ValueError(
            f"Unsupported validation strategy: {strategy}. "
            f"Choose from {', '.join(VALIDATION_STRATEGIES)}."
        )
    if validate_top <= 0 or candidates_df.empty:
        return pd.DataFrame(columns=BACKTEST_HIGHLIGHT_COLUMNS), []

    strategy_func = STRATEGIES.get(f"{strategy}_strategy")
    if strategy_func is None:
        raise ValueError(f"Unsupported validation strategy: {strategy}")

    rows: list[dict[str, Any]] = []
    limitations: list[str] = []
    for _, candidate in candidates_df.head(validate_top).iterrows():
        stock_id = str(candidate.get("Stock", ""))
        row = {
            "Rank": candidate.get("Rank"),
            "Stock": candidate.get("Stock"),
            "Signal": candidate.get("Signal"),
            "Score": candidate.get("Score"),
            "Strategy": strategy,
            "Status": "ERROR",
            "Start Date": None,
            "End Date": None,
            "Total Return %": None,
            "Buy and Hold Return %": None,
            "Trade Count": None,
            "Win Rate %": None,
            "Max Drawdown %": None,
            "Sharpe Ratio": None,
            "Error": "",
        }
        try:
            if analysis_provider is None:
                analysis = analyze_stock(
                    stock_id=stock_id,
                    period=period,
                    interval=interval,
                    auto_adjust=auto_adjust,
                    force_refresh=force_refresh,
                )
            else:
                analysis = analysis_provider(stock_id)
            source_df = analysis.signal_df if strategy == "score" else analysis.indicator_df
            strategy_df = strategy_func(source_df).dropna(subset=["Close", "Signal"])
            result = run_backtest_result(
                strategy_df,
                initial_capital=initial_capital,
                fee_rate=fee_rate,
                tax_rate=tax_rate,
                position_size=position_size,
                interval=interval,
            )
            row.update(
                {
                    "Status": "OK",
                    "Start Date": _format_backtest_date(_backtest_result_value(result, "start_date", "Start Date")),
                    "End Date": _format_backtest_date(_backtest_result_value(result, "end_date", "End Date")),
                    "Total Return %": _round_backtest_metric(_backtest_result_value(result, "total_return_pct", "Total Return %")),
                    "Buy and Hold Return %": _round_backtest_metric(_backtest_result_value(result, "buy_hold_return_pct", "Buy and Hold Return %")),
                    "Trade Count": _backtest_result_value(result, "trade_count", "Trade Count"),
                    "Win Rate %": _round_backtest_metric(_backtest_result_value(result, "win_rate_pct", "Win Rate %")),
                    "Max Drawdown %": _round_backtest_metric(_backtest_result_value(result, "max_drawdown_pct", "Max Drawdown %")),
                    "Sharpe Ratio": _round_backtest_metric(_backtest_result_value(result, "sharpe_ratio", "Sharpe Ratio")),
                }
            )
        except Exception as exc:
            error = " ".join(str(exc).split())
            row["Error"] = error
            limitations.append(f"Backtest validation for {stock_id} failed: {error}")
        rows.append(row)

    return pd.DataFrame(rows, columns=BACKTEST_HIGHLIGHT_COLUMNS), limitations
