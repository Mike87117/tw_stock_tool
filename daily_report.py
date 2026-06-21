"""Daily candidate report for Taiwan stock scans."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from config import DEFAULT_AUTO_ADJUST, DEFAULT_INTERVAL, DEFAULT_PERIOD, OUTPUT_DIR
from scanner import ScanConfig, load_stock_ids_from_file, normalize_stock_ids, scan_stocks
import stock_list_updater as stock_list_updater_module
from stock_selection import apply_stock_selection

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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily stock candidate report")
    parser.add_argument(
        "--stocks",
        nargs="*",
        help="Stock id list, for example: --stocks 2330 2317",
    )
    parser.add_argument("--file", help="Load stock ids from txt file")
    parser.add_argument("--auto-stock-list", action="store_true", help="Update and use an official stock list before reporting")
    parser.add_argument("--stock-market", choices=("all", "twse", "tpex"), default="all")
    parser.add_argument("--stock-list-output", default="stocks.txt")
    parser.add_argument("--allow-partial-stock-list", action="store_true")
    parser.add_argument("--stock-limit", type=int, help="Only scan the first N collected stocks")
    parser.add_argument("--stock-sample", type=int, help="Randomly scan N collected stocks")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed for --stock-sample")
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--interval", default=DEFAULT_INTERVAL)
    parser.add_argument("--signals", nargs="+", default=list(DEFAULT_SIGNALS))
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--top", type=int, default=DEFAULT_TOP)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument(
        "--auto-adjust",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_AUTO_ADJUST,
        help="是否使用 yfinance 除權息調整價",
    )
    parser.add_argument(
        "--output",
        nargs="?",
        const="",
        help="Export Excel; omit path for default output",
    )
    return parser.parse_args(argv)


def main() -> None:
    try:
        args = _parse_args()
        stock_ids = collect_stock_ids(
            args.stocks,
            args.file,
            auto_stock_list=args.auto_stock_list,
            stock_market=args.stock_market,
            stock_list_output=args.stock_list_output,
            allow_partial_stock_list=args.allow_partial_stock_list,
            stock_limit=args.stock_limit,
            stock_sample=args.stock_sample,
            random_state=args.random_state,
        )
        summary_df, candidates_df, _, output_path = run_daily_report(
            stock_ids=stock_ids,
            period=args.period,
            interval=args.interval,
            signals=args.signals,
            min_score=args.min_score,
            top=args.top,
            force_refresh=args.force_refresh,
            auto_adjust=args.auto_adjust,
            output=args.output,
        )
        print_report_summary(summary_df, candidates_df, output_path)
    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()

